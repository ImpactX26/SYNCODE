"""Comprehensive tests for LLM wrapper, retry handling, fallback switching, replay cache, and malformed responses."""

import json
import os
import pytest
from pydantic import BaseModel, Field
import httpx
from falsify.llm import (
    LLMClient,
    LLMConfig,
    LLMError,
    LLMMalformedResponseError,
    LLMResponse,
    LLMRetryExhaustedError,
    ReplayCacheMissError,
    SQLiteReplayCache,
    extract_and_parse_json,
)


class IncidentHypothesisOutput(BaseModel):
    root_cause: str
    confidence_estimate: float
    recommended_tool: str


def test_sqlite_replay_cache_operations(tmp_path):
    """Verify SQLite replay cache storage, key computation, and retrieval."""
    db_file = str(tmp_path / "test_cache.sqlite")
    cache = SQLiteReplayCache(db_path=db_file)

    key = SQLiteReplayCache.compute_key("Check DB status", "You are SRE", "gpt-4o", json_mode=True)
    assert cache.get(key) is None

    cache.set(key, "Check DB status", "You are SRE", "gpt-4o", '{"status": "degraded"}')
    cached_val = cache.get(key)
    assert cached_val == '{"status": "degraded"}'


def test_llm_client_success_and_caching(tmp_path):
    """Verify successful LLM response writes to cache and subsequent call hits cache."""
    db_file = str(tmp_path / "cache.sqlite")
    calls = []

    def mock_caller(model, system, prompt, json_mode):
        calls.append({"model": model, "prompt": prompt})
        return '{"result": "healthy"}'

    config = LLMConfig(cache_db_path=db_file, replay_mode=False)
    client = LLMClient(config=config, custom_caller=mock_caller)

    # First call: executes caller and caches
    resp1 = client.complete("Ping service", system="Sys")
    assert resp1.content == '{"result": "healthy"}'
    assert resp1.model_used == config.primary_model
    assert resp1.cached is False
    assert len(calls) == 1

    # Second identical call: served from SQLite cache
    resp2 = client.complete("Ping service", system="Sys")
    assert resp2.content == '{"result": "healthy"}'
    assert resp2.model_used == config.primary_model
    assert resp2.cached is True
    assert len(calls) == 1  # No additional network/caller invocation


def test_llm_retry_on_transient_error(tmp_path):
    """Verify transient errors are retried with exponential backoff and succeed."""
    db_file = str(tmp_path / "cache.sqlite")
    attempts = 0

    def transient_fail_caller(model, system, prompt, json_mode):
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            raise httpx.ConnectError("Temporary connection reset")
        return '{"status": "recovered_after_retry"}'

    config = LLMConfig(cache_db_path=db_file, max_retries=3, backoff_factor=0.01)
    client = LLMClient(config=config, custom_caller=transient_fail_caller)

    resp = client.complete("Test retry")
    assert resp.content == '{"status": "recovered_after_retry"}'
    assert attempts == 3


def test_llm_fallback_switching_when_primary_fails(tmp_path):
    """Verify fallback model is invoked when primary model fails all retries."""
    db_file = str(tmp_path / "cache.sqlite")
    invocations = []

    def fallback_caller(model, system, prompt, json_mode):
        invocations.append(model)
        if model == "gpt-4o":
            raise httpx.HTTPStatusError("500 Internal Server Error", request=None, response=None)
        return '{"status": "answered_by_fallback"}'

    config = LLMConfig(
        primary_model="gpt-4o",
        fallback_model="gpt-4o-mini",
        cache_db_path=db_file,
        max_retries=2,
        backoff_factor=0.01,
    )
    client = LLMClient(config=config, custom_caller=fallback_caller)

    resp = client.complete("Analyze logs")
    assert resp.content == '{"status": "answered_by_fallback"}'
    assert resp.model_used == "gpt-4o-mini"
    assert "gpt-4o" in invocations
    assert "gpt-4o-mini" in invocations


def test_llm_both_models_fail(tmp_path):
    """Verify LLMError is raised when both primary and fallback models fail."""
    db_file = str(tmp_path / "cache.sqlite")

    def always_fail_caller(model, system, prompt, json_mode):
        raise httpx.ConnectError(f"{model} connection refused")

    config = LLMConfig(cache_db_path=db_file, max_retries=2, backoff_factor=0.01)
    client = LLMClient(config=config, custom_caller=always_fail_caller)

    with pytest.raises(LLMError) as exc_info:
        client.complete("Test fatal failure")
    assert "Both primary model" in str(exc_info.value)


def test_replay_mode_forbids_network_calls_on_cache_miss(tmp_path):
    """Verify REPLAY=1 raises ReplayCacheMissError without calling network when key is not cached."""
    db_file = str(tmp_path / "cache.sqlite")
    called = False

    def network_caller(model, system, prompt, json_mode):
        nonlocal called
        called = True
        return '{"ok": true}'

    config = LLMConfig(cache_db_path=db_file, replay_mode=True)
    client = LLMClient(config=config, custom_caller=network_caller)

    with pytest.raises(ReplayCacheMissError) as exc_info:
        client.complete("Uncached prompt under REPLAY mode")

    assert "REPLAY=1 is active" in str(exc_info.value)
    assert called is False  # Zero network calls made


def test_extract_and_parse_json_markdown_blocks():
    """Verify extract_and_parse_json handles raw JSON and markdown code fences."""
    raw = '```json\n{"action": "restart", "target": "payment-service"}\n```'
    parsed = extract_and_parse_json(raw)
    assert parsed == {"action": "restart", "target": "payment-service"}

    raw_plain = '{"key": "value"}'
    assert extract_and_parse_json(raw_plain) == {"key": "value"}


def test_extract_and_parse_json_malformed():
    """Verify extract_and_parse_json raises LLMMalformedResponseError on malformed text."""
    with pytest.raises(LLMMalformedResponseError) as exc_info:
        extract_and_parse_json("This is not JSON at all.")
    assert "Failed to decode JSON" in str(exc_info.value)

    with pytest.raises(LLMMalformedResponseError):
        extract_and_parse_json("")


def test_complete_pydantic_validation(tmp_path):
    """Verify complete_pydantic parses and validates response against Pydantic schema."""
    db_file = str(tmp_path / "cache.sqlite")

    def pydantic_caller(model, system, prompt, json_mode):
        return json.dumps({
            "root_cause": "Database connection pool saturated",
            "confidence_estimate": 0.88,
            "recommended_tool": "restart_service"
        })

    config = LLMConfig(cache_db_path=db_file)
    client = LLMClient(config=config, custom_caller=pydantic_caller)

    parsed_obj, resp = client.complete_pydantic("Formulate hypothesis", IncidentHypothesisOutput)
    assert isinstance(parsed_obj, IncidentHypothesisOutput)
    assert parsed_obj.root_cause == "Database connection pool saturated"
    assert parsed_obj.confidence_estimate == 0.88
    assert parsed_obj.recommended_tool == "restart_service"
