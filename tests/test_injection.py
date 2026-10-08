"""Placeholder tests for untrusted telemetry sanitization and prompt injection defense."""

from falsify.sanitize import sanitize_tool_output, wrap_untrusted_context


def test_sanitize_tool_output():
    """Verify tool output sanitization strips control characters and truncates excessive payload."""
    raw = "log output\x00\x08with control characters"
    clean = sanitize_tool_output(raw)
    assert "\x00" not in clean
    assert "\x08" not in clean
    assert "log outputwith control characters" in clean

    long_payload = "a" * 20000
    truncated = sanitize_tool_output(long_payload, max_chars=100)
    assert len(truncated) < 200
    assert "truncated" in truncated


def test_wrap_untrusted_context():
    """Verify untrusted telemetry is enclosed in explicit XML delimiters."""
    context = wrap_untrusted_context("DROP TABLE users;", source_tag="db_logs")
    assert context.startswith("<db_logs>")
    assert context.endswith("</db_logs>")
    assert "DROP TABLE users;" in context
