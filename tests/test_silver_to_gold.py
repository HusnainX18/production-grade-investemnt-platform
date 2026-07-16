"""
Unit tests for Silver-to-Gold feature engineering functions.
"""

import pandas as pd
from src.processing.silver_to_gold import compute_news_sentiment, compute_lexicon_sentiment

def test_compute_lexicon_sentiment():
    """
    Test fallback lexicon news sentiment scoring logic.
    """
    pos_res = compute_lexicon_sentiment("Market goes up with growth and profit gains")
    assert pos_res["label"] == "Positive"
    assert pos_res["score"] > 0.5

    neg_res = compute_lexicon_sentiment("Market crash and loss decline slump bearish")
    assert neg_res["label"] == "Negative"
    assert neg_res["score"] > 0.5

    neu_res = compute_lexicon_sentiment("Unrelated text without keyword")
    assert neu_res["label"] == "Neutral"
    assert neu_res["score"] == 1.0

def test_compute_news_sentiment_df():
    """
    Test news dataframe aggregation daily per symbol.
    """
    news_data = {
        "title": ["Apple growth gains", "Bitcoin profit rises", "Solana crash", "Google profit grows"],
        "description": ["growth gains", "profit gains", "slump loss", "success rises"],
        "url": ["url1", "url2", "url3", "url4"],
        "published_at": ["2026-06-01T12:00:00Z", "2026-06-01T14:00:00Z", "2026-06-02T10:00:00Z", "2026-06-02T11:00:00Z"],
        "matched_tickers": ["AAPL", "BTC", "SOL", "GOOGL"]
    }
    df = pd.DataFrame(news_data)
    
    res = compute_news_sentiment(df)
    
    assert "ticker" in res.columns
    assert "date_str" in res.columns
    assert "sentiment_net" in res.columns
    
    # 4 articles, each on separate tickers and dates
    assert len(res) == 4
    
    aapl_row = res[res["ticker"] == "AAPL"].iloc[0]
    assert aapl_row["date_str"] == "2026-06-01"
    assert aapl_row["sentiment_net"] > 0.0 # Positive
    
    sol_row = res[res["ticker"] == "SOL"].iloc[0]
    assert sol_row["date_str"] == "2026-06-02"
    assert sol_row["sentiment_net"] < 0.0 # Negative
