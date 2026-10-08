"""Placeholder tests for LLM client configuration, fallback, and replay mode."""

from falsify.llm import LLMClient, LLMConfig, LLMResponse


def test_llm_config_defaults():
    """Verify default LLM configuration."""
    config = LLMConfig()
    assert config.primary_model == "gpt-4o"
    assert config.fallback_model == "gpt-4o-mini"
    assert config.max_retries == 3
    assert config.cache_db_path == "eval/replay_cache.sqlite"


def test_llm_client_stub():
    """Verify LLM client stub completion response."""
    client = LLMClient(LLMConfig(replay_mode=True))
    res = client.complete("Diagnose incident")
    assert isinstance(res, LLMResponse)
    assert res.model_used == "gpt-4o"
    assert res.cached is True
