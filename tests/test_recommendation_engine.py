"""
Unit tests for Phase 11 Recommendation Engine helpers.
"""

import pytest
from src.recommendation.engine import get_risk_label, get_confidence_score

def test_get_risk_label():
    """
    Test that volatility ranges map to correct risk labels.
    """
    assert get_risk_label(0.01) == "Low"
    assert get_risk_label(0.0149) == "Low"
    assert get_risk_label(0.015) == "Medium"
    assert get_risk_label(0.03) == "Medium"
    assert get_risk_label(0.035) == "High"
    assert get_risk_label(0.05) == "High"

def test_get_confidence_score():
    """
    Test confidence score scaling and clipping.
    """
    # Standard behavior: ratio of prediction to maximum prediction
    assert get_confidence_score(0.05, 0.10) == pytest.approx(50.0)
    assert get_confidence_score(-0.02, 0.08) == pytest.approx(25.0)
    
    # Boundary cases: max_pred <= 0
    assert get_confidence_score(0.02, 0.0) == 50.0
    assert get_confidence_score(0.02, -0.01) == 50.0
    
    # Clipping behavior: min is 10.0, max is 99.0
    assert get_confidence_score(0.001, 0.10) == 10.0  # Would be 1%, clipped to 10%
    assert get_confidence_score(0.10, 0.10) == 99.0   # Would be 100%, clipped to 99%
    assert get_confidence_score(0.12, 0.10) == 99.0   # Out of bounds clipped to 99%
