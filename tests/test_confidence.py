"""Placeholder tests for deterministic confidence scoring."""

from falsify.confidence import (
    CAP_CONTRADICTING,
    CAP_FEWER_THAN_TWO_SOURCES,
    CAP_ZERO_SUPPORTING,
    MAX_CONFIDENCE,
    calculate_confidence,
)
from falsify.state import Hypothesis


def test_confidence_constants():
    """Verify confidence threshold constants."""
    assert CAP_ZERO_SUPPORTING == 0.20
    assert CAP_CONTRADICTING == 0.40
    assert CAP_FEWER_THAN_TWO_SOURCES == 0.60
    assert MAX_CONFIDENCE == 0.95


def test_calculate_confidence_stub():
    """Verify calculate_confidence stub interface."""
    hyp = Hypothesis(claim="Memory leak", prediction="RSS increases linearly")
    conf = calculate_confidence([hyp])
    assert isinstance(conf, float)
    assert 0.0 <= conf <= 1.0
