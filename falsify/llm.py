"""Resilient LLM client wrapper with retry handling, fallback switching, and SQLite replay cache."""

from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple, Type, TypeVar, Union
import httpx
from pydantic import BaseModel, Field


T = TypeVar("T", bound=BaseModel)


# =====================================================================
# Exceptions
# =====================================================================

class LLMError(Exception):
    """Base exception for LLM operations."""
    pass


class LLMRetryExhaustedError(LLMError):
    """Raised when all retry attempts for an LLM model are exhausted."""
    pass


class LLMMalformedResponseError(LLMError):
    """Raised when the LLM returns invalid or unparseable JSON/content."""

    def __init__(self, message: str, raw_content: str):
        super().__init__(message)
        self.raw_content = raw_content


class ReplayCacheMissError(LLMError):
    """Raised when REPLAY=1 is active but no cached response exists."""
    pass


# =====================================================================
# Configuration & Response Models
# =====================================================================

class LLMConfig(BaseModel):
    """Configuration for LLM client loaded from environment or parameters."""

    primary_model: str = Field(
        default_factory=lambda: os.getenv("PRIMARY_MODEL", "gpt-4o"),
        description="Primary model identifier",
    )
    fallback_model: str = Field(
        default_factory=lambda: os.getenv("FALLBACK_MODEL", "gpt-4o-mini"),
        description="Fallback model identifier",
    )
    max_retries: int = Field(
        default_factory=lambda: int(os.getenv("LLM_MAX_RETRIES", "3")),
        description="Max retry attempts for transient errors (429, 5xx, timeout)",
    )
    timeout_sec: float = Field(
        default_factory=lambda: float(os.getenv("LLM_TIMEOUT_SEC", "30.0")),
        description="Request timeout in seconds",
    )
    backoff_factor: float = Field(
        default_factory=lambda: float(os.getenv("LLM_BACKOFF_FACTOR", "0.2")),
        description="Exponential backoff multiplier in seconds",
    )
    replay_mode: Optional[bool] = Field(
        default=None,
        description="When True, zero network calls are made and responses are served from cache only",
    )
    cache_db_path: str = Field(
        default_factory=lambda: os.getenv("REPLAY_CACHE_DB", "eval/replay_cache.sqlite"),
        description="Path to SQLite replay cache",
    )
    openai_api_key: Optional[str] = Field(
        default_factory=lambda: os.getenv("OPENAI_API_KEY"),
        description="OpenAI API key (if available)",
    )
    anthropic_api_key: Optional[str] = Field(
        default_factory=lambda: os.getenv("ANTHROPIC_API_KEY"),
        description="Anthropic API key (if available)",
    )
    openai_base_url: str = Field(
        default_factory=lambda: os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1"),
        description="OpenAI API Base URL",
    )


class LLMResponse(BaseModel):
    """Response structure returned by LLMClient."""

    content: str = Field(default="", description="Text or JSON string content returned by the LLM")
    model_used: str = Field(..., description="The actual model that answered (primary, fallback, or cached)")
    cached: bool = Field(default=False, description="Whether this response was served from replay cache")
    latency_ms: float = Field(default=0.0, description="Call latency in milliseconds")

    def json_dict(self) -> Dict[str, Any]:
        """Parse content as JSON dictionary."""
        return extract_and_parse_json(self.content)


# =====================================================================
# SQLite Replay Cache
# =====================================================================

class SQLiteReplayCache:
    """Persistent SQLite cache for recording and replaying LLM responses."""

    def __init__(self, db_path: str = "eval/replay_cache.sqlite"):
        self.db_path = db_path
        self._memory_conn: Optional[sqlite3.Connection] = None
        if db_path == ":memory:":
            self._memory_conn = sqlite3.connect(":memory:", check_same_thread=False)
            self._memory_conn.row_factory = sqlite3.Row
        else:
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        if self._memory_conn is not None:
            return self._memory_conn
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        conn = self._get_connection()
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS llm_cache (
                cache_key TEXT PRIMARY KEY,
                prompt TEXT NOT NULL,
                system TEXT,
                model TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at REAL NOT NULL
            )
            """
        )
        conn.commit()
        if self._memory_conn is None:
            conn.close()

    @staticmethod
    def compute_key(prompt: str, system: Optional[str], model: str, json_mode: bool = False) -> str:
        """Compute deterministic SHA-256 cache key."""
        payload = f"model={model}|json={json_mode}|sys={system or ''}|prompt={prompt.strip()}"
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def get(self, cache_key: str) -> Optional[str]:
        """Retrieve cached completion content if present."""
        conn = self._get_connection()
        cur = conn.cursor()
        cur.execute("SELECT content FROM llm_cache WHERE cache_key = ?", (cache_key,))
        row = cur.fetchone()
        if self._memory_conn is None:
            conn.close()
        if row:
            return row["content"]
        return None

    def set(self, cache_key: str, prompt: str, system: Optional[str], model: str, content: str) -> None:
        """Store completion in cache."""
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO llm_cache (cache_key, prompt, system, model, content, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (cache_key, prompt, system or "", model, content, time.time()),
            )


# =====================================================================
# JSON Utilities & Sanitization
# =====================================================================

def extract_and_parse_json(text: str) -> Dict[str, Any]:
    """Safely extract and parse JSON from raw LLM output (handles codeblocks and wrappers)."""
    if not text or not text.strip():
        raise LLMMalformedResponseError("Empty response cannot be parsed as JSON", raw_content=text)

    cleaned = text.strip()

    # Strip markdown code blocks if present (```json ... ``` or ``` ...)
    match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", cleaned, re.IGNORECASE)
    if match:
        cleaned = match.group(1).strip()

    try:
        data = json.loads(cleaned)
        if isinstance(data, dict):
            return data
        elif isinstance(data, list):
            return {"items": data}
        return {"value": data}
    except json.JSONDecodeError as e:
        raise LLMMalformedResponseError(f"Failed to decode JSON: {e}", raw_content=text) from e


# =====================================================================
# LLM Client
# =====================================================================

class LLMClient:
    """Production-grade resilient LLM client supporting primary/fallback, retry, and replay cache."""

    def __init__(
        self,
        config: Optional[LLMConfig] = None,
        custom_caller: Optional[Callable[[str, Optional[str], str, bool], str]] = None,
    ):
        self.config = config or LLMConfig()
        self.cache = SQLiteReplayCache(db_path=self.config.cache_db_path)
        self._custom_caller = custom_caller  # Pluggable mock/test caller

        # Resolve effective replay_mode:
        # 1. Explicit per-client/test configuration (True or False) takes precedence.
        # 2. When a custom caller is provided without explicit replay_mode, disable replay mode so test mocks run.
        # 3. Otherwise (live/production without custom caller), fallback to REPLAY environment variable.
        if self.config.replay_mode is None:
            if self._custom_caller is not None:
                self.config.replay_mode = False
            else:
                self.config.replay_mode = os.getenv("REPLAY", "0").lower() in ("1", "true", "yes")

    def _call_http_openai_compatible(
        self,
        model: str,
        prompt: str,
        system: Optional[str] = None,
        json_mode: bool = False,
    ) -> str:
        """Execute HTTP request to OpenAI-compatible Chat Completions API."""
        api_key = self.config.openai_api_key
        if not api_key:
            raise LLMError(f"No API key configured for model {model}")

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        messages: List[Dict[str, str]] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        payload: Dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": 0.1,
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}

        url = f"{self.config.openai_base_url.rstrip('/')}/chat/completions"

        with httpx.Client(timeout=self.config.timeout_sec) as client:
            resp = client.post(url, json=payload, headers=headers)
            if resp.status_code == 429:
                raise httpx.HTTPStatusError("Rate limit exceeded", request=resp.request, response=resp)
            elif resp.status_code >= 500:
                raise httpx.HTTPStatusError(f"Server error {resp.status_code}", request=resp.request, response=resp)
            resp.raise_for_status()

            data = resp.json()
            return data["choices"][0]["message"]["content"]

    def _execute_model_with_retries(
        self,
        model: str,
        prompt: str,
        system: Optional[str] = None,
        json_mode: bool = False,
    ) -> str:
        """Execute call to a specific model with exponential backoff retries."""
        last_exception: Optional[Exception] = None

        for attempt in range(1, self.config.max_retries + 1):
            try:
                if self._custom_caller:
                    return self._custom_caller(model, system, prompt, json_mode)
                return self._call_http_openai_compatible(model, prompt, system, json_mode)
            except (httpx.TimeoutException, httpx.HTTPStatusError, httpx.ConnectError, ConnectionError) as e:
                last_exception = e
                # Transient retryable error
                if attempt < self.config.max_retries:
                    sleep_time = self.config.backoff_factor * (2 ** (attempt - 1))
                    time.sleep(sleep_time)
                else:
                    break
            except Exception as e:
                # Non-retryable error
                last_exception = e
                break

        raise LLMRetryExhaustedError(f"Model {model} failed after {self.config.max_retries} attempts: {last_exception}")

    def complete(
        self,
        prompt: str,
        system: Optional[str] = None,
        json_mode: bool = False,
    ) -> LLMResponse:
        """Complete a prompt with primary model, fallback fallback switching, and replay cache."""
        start_time = time.perf_counter()

        # 1. Check Replay Cache
        cache_key_primary = SQLiteReplayCache.compute_key(prompt, system, self.config.primary_model, json_mode)
        cached_content = self.cache.get(cache_key_primary)

        if cached_content is not None:
            latency = (time.perf_counter() - start_time) * 1000.0
            return LLMResponse(
                content=cached_content,
                model_used=self.config.primary_model,
                cached=True,
                latency_ms=latency,
            )

        # 2. Check Fallback Model Cache Key
        cache_key_fallback = SQLiteReplayCache.compute_key(prompt, system, self.config.fallback_model, json_mode)
        cached_fallback = self.cache.get(cache_key_fallback)
        if cached_fallback is not None:
            latency = (time.perf_counter() - start_time) * 1000.0
            return LLMResponse(
                content=cached_fallback,
                model_used=self.config.fallback_model,
                cached=True,
                latency_ms=latency,
            )

        # If in REPLAY mode and cache miss:
        if self.config.replay_mode:
            # Replay mode forbids network calls
            raise ReplayCacheMissError(
                f"REPLAY=1 is active, but no cached response exists for key {cache_key_primary}."
            )

        # 3. Live Execution: Try Primary Model
        model_used = self.config.primary_model
        try:
            content = self._execute_model_with_retries(
                model=self.config.primary_model,
                prompt=prompt,
                system=system,
                json_mode=json_mode,
            )
            # Store primary in cache
            self.cache.set(cache_key_primary, prompt, system, self.config.primary_model, content)
        except Exception as primary_error:
            # 4. Fallback Execution: Try Fallback Model
            try:
                model_used = self.config.fallback_model
                content = self._execute_model_with_retries(
                    model=self.config.fallback_model,
                    prompt=prompt,
                    system=system,
                    json_mode=json_mode,
                )
                # Store fallback in cache
                self.cache.set(cache_key_fallback, prompt, system, self.config.fallback_model, content)
            except Exception as fallback_error:
                raise LLMError(
                    f"Both primary model ({self.config.primary_model}) and fallback model "
                    f"({self.config.fallback_model}) failed. Primary error: {primary_error}; "
                    f"Fallback error: {fallback_error}"
                ) from fallback_error

        latency = (time.perf_counter() - start_time) * 1000.0
        return LLMResponse(
            content=content,
            model_used=model_used,
            cached=False,
            latency_ms=latency,
        )

    def complete_pydantic(
        self,
        prompt: str,
        pydantic_model: Type[T],
        system: Optional[str] = None,
    ) -> Tuple[T, LLMResponse]:
        """Execute completion, parse JSON output, and validate against a Pydantic model."""
        enhanced_prompt = (
            f"{prompt}\n\nRespond strictly with valid JSON conforming to schema: "
            f"{json.dumps(pydantic_model.model_json_schema(), sort_keys=True)}"
        )
        response = self.complete(prompt=enhanced_prompt, system=system, json_mode=True)
        data = response.json_dict()
        try:
            parsed = pydantic_model.model_validate(data)
            return parsed, response
        except Exception as e:
            raise LLMMalformedResponseError(
                f"Response JSON failed schema validation for {pydantic_model.__name__}: {e}",
                raw_content=response.content,
            ) from e
