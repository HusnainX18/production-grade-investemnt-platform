"""
Unit tests for data quality verification and validation helpers.
"""

import pandas as pd
from src.processing.bronze_to_silver import _check_not_null, _check_between, _check_column_exists

def test_data_quality_helpers():
    """
    Test individual validation rules against mock data.
    """
    # Create mock dataset
    data = {
        "valid_col": [1, 2, 3],
        "null_col": [1, None, 3],
        "low_col": [0.005, 10.0, 5.0],
        "high_col": [10.0, 20.0, 30.0]
    }
    df = pd.DataFrame(data)
    
    # 1. Test _check_not_null
    ok_not_null, _ = _check_not_null(df, "valid_col")
    assert bool(ok_not_null) is True
    
    fail_not_null, msg_not_null = _check_not_null(df, "null_col")
    assert bool(fail_not_null) is False
    assert "nulls found" in msg_not_null
    
    # 2. Test _check_between
    ok_between, _ = _check_between(df, "high_col", 5.0)
    assert bool(ok_between) is True
    
    fail_between, msg_between = _check_between(df, "low_col", 1.0)
    assert bool(fail_between) is False
    assert "below threshold" in msg_between

    # 3. Test _check_column_exists
    ok_exists, _ = _check_column_exists(df, "valid_col")
    assert bool(ok_exists) is True
    
    fail_exists, msg_exists = _check_column_exists(df, "missing_col")
    assert bool(fail_exists) is False
    assert "column missing" in msg_exists
