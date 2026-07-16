"""
Unit tests for Bronze-to-Silver validation suites.
"""

import pandas as pd
from src.processing.bronze_to_silver import validate_stocks, validate_crypto, validate_macro, validate_news

def test_validate_stocks():
    """
    Test validate_stocks logic with valid and invalid dataframes.
    """
    # 1. Valid stocks dataframe
    valid_stocks = pd.DataFrame({
        "symbol": ["AAPL", "MSFT"],
        "timestamp": ["2026-06-01", "2026-06-02"],
        "close": [150.0, 420.0],
        "volume": [1000000, 2000000],
        "sector": ["Tech", "Tech"],
        "industry": ["Software", "Software"]
    })
    assert validate_stocks(valid_stocks) is True

    # 2. Invalid stocks dataframe (missing sector)
    invalid_stocks = pd.DataFrame({
        "symbol": ["AAPL"],
        "timestamp": ["2026-06-01"],
        "close": [150.0],
        "volume": [1000000]
    })
    assert validate_stocks(invalid_stocks) is False

def test_validate_crypto():
    """
    Test validate_crypto logic.
    """
    valid_crypto = pd.DataFrame({
        "symbol": ["BTC/USD"],
        "timestamp": ["2026-06-01"],
        "close": [64000.0],
        "volume": [5.5]
    })
    assert validate_crypto(valid_crypto) is True

    invalid_crypto = pd.DataFrame({
        "symbol": ["BTC/USD"],
        "timestamp": ["2026-06-01"],
        "close": [0.0000001], # below 0.000001
        "volume": [0]
    })
    # Since it checks close >= 0.000001, this should return False
    assert validate_crypto(invalid_crypto) is False

def test_validate_macro():
    """
    Test validate_macro logic.
    """
    valid_macro = pd.DataFrame({
        "series_id": ["FEDFUNDS"],
        "date": ["2026-06-01"],
        "value": [5.25]
    })
    assert validate_macro(valid_macro) is True

    invalid_macro = pd.DataFrame({
        "series_id": [None],
        "date": ["2026-06-01"],
        "value": [5.25]
    })
    assert validate_macro(invalid_macro) is False

def test_validate_news():
    """
    Test validate_news logic.
    """
    valid_news = pd.DataFrame({
        "title": ["Stock Market Gains Today"],
        "published_at": ["2026-06-01T12:00:00Z"],
        "url": ["https://newsapi.org/article1"]
    })
    assert validate_news(valid_news) is True

    invalid_news = pd.DataFrame({
        "title": [None],
        "published_at": ["2026-06-01T12:00:00Z"],
        "url": ["https://newsapi.org/article1"]
    })
    assert validate_news(invalid_news) is False
