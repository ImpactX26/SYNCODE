"""Untrusted data sanitization and prompt injection guards."""

from __future__ import annotations

import re
from typing import Any, Dict


def sanitize_tool_output(data: Any, max_chars: int = 10000) -> str:
    """Sanitize and truncate external tool data (logs, metrics, probe responses).
    
    All tool outputs are treated as UNTRUSTED DATA, never executable instructions.
    """
    if data is None:
        return ""
    text = str(data)
    # Strip potential control characters / null bytes
    clean = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", text)
    if len(clean) > max_chars:
        return clean[:max_chars] + f"\n... [truncated to {max_chars} characters]"
    return clean


def wrap_untrusted_context(content: str, source_tag: str = "untrusted_telemetry") -> str:
    """Wrap untrusted input in strict XML-style delimiters for prompt construction."""
    clean_content = sanitize_tool_output(content)
    return f"<{source_tag}>\n{clean_content}\n</{source_tag}>"
