"""
Unit tests for Phase 6 feature engineering calculations.
"""

import numpy as np
import pandas as pd
import pytest
from src.processing.silver_to_gold import compute_technical_indicators, compute_macro_features

def test_compute_technical_indicators():
    """
    Test that technical indicators and target variables are calculated correctly
    grouped by symbol.
    """
    # Create test dataframe with 10 periods for symbol AAPL
    dates = pd.date_range(start="2026-06-01", periods=10)
    # Price increases by 1 each day
    close_prices = [100.0 + i for i in range(10)]
    
    df = pd.DataFrame({
        "symbol": ["AAPL"] * 10,
        "timestamp": dates.strftime("%Y-%m-%d"),
        "close": close_prices,
        "high": close_prices,
        "low": close_prices,
        "open": close_prices,
        "volume": [1000] * 10
    })
    
    res = compute_technical_indicators(df)
    
    # 1. Check target returns
    # target_1d_return for index 0 should be close(1)/close(0) - 1 = 101/100 - 1 = 0.01
    assert res.loc[0, "target_1d_return"] == pytest.approx(0.01)
    # For index 8 (day 9 vs day 10), it should be 109/108 - 1
    assert res.loc[8, "target_1d_return"] == pytest.approx(109/108 - 1)
    # The last index target should be NaN since there is no t+1 price
    assert np.isnan(res.loc[9, "target_1d_return"])
    
    # 2. Check 5d target return
    # target_5d_return for index 0 should be close(5)/close(0) - 1 = 105/100 - 1 = 0.05
    assert res.loc[0, "target_5d_return"] == pytest.approx(0.05)
    # The last 5 indices target_5d_return should be NaN
    for i in range(5, 10):
         assert np.isnan(res.loc[i, "target_5d_return"])

    # 3. Check returns
    # 1d return at index 1 should be close(1)/close(0) - 1 = 0.01
    assert res.loc[1, "return_1d"] == pytest.approx(0.01)
    
    # 5d return at index 5 should be close(5)/close(0) - 1 = 0.05
    assert res.loc[5, "return_5d"] == pytest.approx(0.05)

def test_compute_macro_features():
    """
    Test pivoting and slope calculation for macro features.
    """
    df = pd.DataFrame({
        "date": ["2026-06-01", "2026-06-01", "2026-06-02", "2026-06-02"],
        "series_id": ["DGS10", "DGS2", "DGS10", "DGS2"],
        "value": [4.2, 4.0, 4.3, 4.1]
    })
    
    res = compute_macro_features(df)
    
    assert "yield_curve_slope" in res.columns
    # yield curve slope at index 0 should be 4.2 - 4.0 = 0.2
    assert res.loc[0, "yield_curve_slope"] == pytest.approx(0.2)
    # yield curve slope at index 1 should be 4.3 - 4.1 = 0.2
    assert res.loc[1, "yield_curve_slope"] == pytest.approx(0.2)
