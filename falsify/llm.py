"""LLM client wrapper with primary/fallback models, retry with backoff, and SQLite replay cache."""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field


class LLMConfig(BaseModel):
    """Configuration for LLM client."""

    primary_model: str = Field(default="gpt-4o", description="Primary model identifier")
    fallback_model: str = Field(default="gpt-4o-mini", description="Fallback model identifier")
    max_retries: int = Field(default=3, description="Max retry attempts for transient errors (429, 5xx, timeout)")
    timeout_sec: float = Field(default=30.0, description="Request timeout in seconds")
    replay_mode: bool = Field(
        default_factory=lambda: os.getenv("REPLAY", "0").lower() in ("1", "true", "yes"),
        description="When True, zero network calls are made and responses are served from cache only",
    )
    cache_db_path: str = Field(default="eval/replay_cache.sqlite", description="Path to SQLite replay cache")


class LLMResponse(BaseModel):
    """Response structure from LLM client."""

    content: str = Field(default="", description="Text or JSON string content returned by the LLM")
    model_used: str = Field(..., description="The actual model that answered (primary or fallback)")
    cached: bool = Field(default=False, description="Whether this response was served from cache")
    latency_ms: float = Field(default=0.0, description="Call latency in milliseconds")


class LLMClient:
    """Resilient LLM client scaffolding (A2 Stub)."""

    def __init__(self, config: Optional[LLMConfig] = None):
        self.config = config or LLMConfig()

    def complete(self, prompt: str, system: Optional[str] = None, json_mode: bool = False) -> LLMResponse:
        """Execute completion with primary model, fallback handling, and replay cache support."""
        # Scaffolding stub - full client logic implemented in Phase A2
        return LLMResponse(
            content="{}",
            model_used=self.config.primary_model,
            cached=self.config.replay_mode,
            latency_ms=0.0,
        )
