"""
Unit tests for Phase 3 ingestion utilities and helpers.
"""

import os
import pytest
from src.ingestion.ingest_news import map_article_to_tickers
from src.utils.s3_helper import get_storage_options
from src.utils.api_helper import get_resilient_session

def test_map_article_to_tickers_exact_match():
    """
    Test that map_article_to_tickers correctly extracts tickers mentioned in title or description.
    """
    query_tickers = ["AAPL", "MSFT", "GOOGL"]
    
    # Apple mentioned
    res = map_article_to_tickers(
        title="Apple releases new iOS update",
        description="Nothing new here.",
        query_tickers=query_tickers
    )
    assert res == "AAPL"
    
    # Microsoft and Google mentioned
    res = map_article_to_tickers(
        title="Microsoft partners with Alphabet",
        description="This will affect the search engine GOOGL market.",
        query_tickers=query_tickers
    )
    # Tickers are matching the order in query_tickers
    assert "MSFT" in res
    assert "GOOGL" in res
    assert "AAPL" not in res

def test_map_article_to_tickers_fallback():
    """
    Test that map_article_to_tickers falls back to query tickers when no keywords match.
    """
    query_tickers = ["AAPL", "MSFT"]
    res = map_article_to_tickers(
        title="Unrelated headline here",
        description="Some random description.",
        query_tickers=query_tickers
    )
    assert res == "AAPL,MSFT"

def test_map_article_to_tickers_word_boundary():
    """
    Test that keyword matching respects word boundaries (no substring false-positives).
    For instance, "cost" (for COST) shouldn't match "costly" or "accost".
    """
    query_tickers = ["COST"]
    
    # Costly should NOT match COST
    res = map_article_to_tickers(
        title="The lawsuit was costly",
        description="A costly mistake.",
        query_tickers=query_tickers
    )
    assert res == "COST"  # Fallback to query_tickers because no keywords matched
    
    # Exact word "cost" or "costco" should match
    res = map_article_to_tickers(
        title="Costco earnings report",
        description="Checking the cost of items.",
        query_tickers=query_tickers
    )
    assert res == "COST"  # Matched specifically

def test_get_storage_options_error_on_missing_env(monkeypatch):
    """
    Test that ValueError is raised if AWS keys are not set.
    """
    monkeypatch.delenv("AWS_ACCESS_KEY_ID", raising=False)
    monkeypatch.delenv("AWS_SECRET_ACCESS_KEY", raising=False)
    
    with pytest.raises(ValueError) as excinfo:
        get_storage_options()
    assert "AWS credentials" in str(excinfo.value)

def test_get_resilient_session():
    """
    Test that session builder returns requests.Session with Retry configuration.
    """
    session = get_resilient_session(retries=3)
    assert session is not None
    
    # Verify adapter retry limits
    adapter_http = session.adapters.get("http://")
    adapter_https = session.adapters.get("https://")
    
    assert adapter_http is not None
    assert adapter_https is not None
    assert adapter_http.max_retries.total == 3
