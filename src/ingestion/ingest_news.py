"""
News API Financial News Ingestion (Bronze Layer).
Ingests financial news headlines for the equity universe into AWS S3 Data Lake.
Note: Free tier provides articles from the last 30 days only.
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

if sys.platform.startswith("win"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")  # type: ignore
        sys.stderr.reconfigure(encoding="utf-8")  # type: ignore
    except Exception:
        pass

import time
import re
import yaml
import pandas as pd
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv
from src.utils.s3_helper import write_bronze_delta, get_s3_path
from src.utils.api_helper import get_resilient_session


NEWS_BASE_URL = "https://newsapi.org/v2/everything"

TICKER_KEYWORDS = {
    "AAPL":  ["apple", "aapl"],
    "MSFT":  ["microsoft", "msft"],
    "GOOGL": ["google", "googl", "alphabet"],
    "AMZN":  ["amazon", "amzn"],
    "NVDA":  ["nvidia", "nvda"],
    "META":  ["meta", "facebook", "instagram"],
    "TSLA":  ["tesla", "tsla"],
    "LLY":   ["eli lilly", "lilly", "lly"],
    "V":     ["visa"],
    "UNH":   ["unitedhealth", "unh", "united health"],
    "JPM":   ["jpmorgan", "chase", "jp morgan", "jpm"],
    "JNJ":   ["johnson & johnson", "jnj", "johnson and johnson"],
    "WMT":   ["walmart", "wmt"],
    "XOM":   ["exxon", "mobil", "xom", "exxonmobil"],
    "PG":    ["procter", "gamble", "p&g", "pg"],
    "AVGO":  ["broadcom", "avgo"],
    "HD":    ["home depot", "hd"],
    "CVX":   ["chevron", "cvx"],
    "ORCL":  ["oracle", "orcl"],
    "MRK":   ["merck", "mrk"],
    "KO":    ["coca-cola", "coke", "ko"],
    "ABBV":  ["abbvie", "abbv"],
    "PEP":   ["pepsi", "pep"],
    "COST":  ["costco", "cost"],
    "BAC":   ["bank of america", "bac", "bofa"],
    "ADBE":  ["adobe", "adbe"],
    "MCD":   ["mcdonald", "mcd"],
    "CSCO":  ["cisco", "csco"],
    "AMD":   ["amd", "ryzen"],
    "NFLX":  ["netflix", "nflx"],
    "CRM":   ["salesforce", "crm"],
    "TMO":   ["thermo fisher", "tmo"],
    "ABT":   ["abbott", "abt"],
    "NKE":   ["nike", "nke"],
    "DIS":   ["disney", "dis"],
    "BTC":   ["bitcoin", "btc"],
    "ETH":   ["ethereum", "eth"],
    "SOL":   ["solana", "sol"],
}

SEARCH_QUERIES = [
    {"query": "Apple OR Microsoft OR Google OR Amazon OR NVIDIA",
     "tickers": ["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA"]},
    {"query": "Meta OR Tesla OR Eli Lilly OR Visa OR UnitedHealth",
     "tickers": ["META", "TSLA", "LLY", "V", "UNH"]},
    {"query": "JPMorgan OR Johnson stock OR Walmart stock OR ExxonMobil OR Procter",
     "tickers": ["JPM", "JNJ", "WMT", "XOM", "PG"]},
    {"query": "Broadcom OR Home Depot OR Chevron OR Oracle OR Merck",
     "tickers": ["AVGO", "HD", "CVX", "ORCL", "MRK"]},
    {"query": "Coca-Cola OR AbbVie OR Pepsi OR Costco OR Bank of America",
     "tickers": ["KO", "ABBV", "PEP", "COST", "BAC"]},
    {"query": "Adobe OR McDonald OR Cisco OR AMD OR Netflix stock",
     "tickers": ["ADBE", "MCD", "CSCO", "AMD", "NFLX"]},
    {"query": "Salesforce OR Thermo Fisher OR Abbott OR Nike OR Disney",
     "tickers": ["CRM", "TMO", "ABT", "NKE", "DIS"]},
    {"query": "Bitcoin OR Ethereum OR Solana OR crypto market",
     "tickers": ["BTC", "ETH", "SOL", "CRYPTO"]},
]


def map_article_to_tickers(title: str, description: str, query_tickers: list[str]) -> str:
    """
    Scan article title and description for keywords matching query_tickers.

    Returns:
        Comma-separated matched tickers, or all query_tickers as a fallback.
    """
    text = f"{title or ''} {description or ''}".lower()
    matched = []

    for ticker in query_tickers:
        keywords = TICKER_KEYWORDS.get(ticker, [ticker.lower()])
        for kw in keywords:
            if re.search(rf"\b{re.escape(kw)}\b", text):
                matched.append(ticker)
                break

    return ",".join(matched) if matched else ",".join(query_tickers)


def main() -> None:
    load_dotenv()

    news_api_key = os.getenv("NEWS_API_KEY")
    if not news_api_key:
        print("[ERROR] NEWS_API_KEY is not set in .env — aborting.")
        sys.exit(1)
    api_key: str = news_api_key  # narrowed: str | None -> str

    end_date = datetime.today()
    start_date = end_date - timedelta(days=29)

    print("=" * 60)
    print("News Ingestion (Bronze Layer)")
    print("=" * 60)
    print(f"Date Range  : {start_date.date()} -> {end_date.date()}")
    print(f"Queries     : {len(SEARCH_QUERIES)} topic groups")
    print(f"Destination : {get_s3_path('news')}")
    print("(Note: Free tier = last 30 days only)")
    print("=" * 60)

    session = get_resilient_session()
    all_articles = []
    failed = []

    for group in SEARCH_QUERIES:
        query = group["query"]
        tickers = group["tickers"]
        assert isinstance(tickers, list), f"Expected list for 'tickers', got {type(tickers)}"
        print(f"\nFetching: {tickers}")

        try:
            params = {
                "q":        query,
                "language": "en",
                "sortBy":   "publishedAt",
                "pageSize": 100,
                "from":     start_date.strftime("%Y-%m-%d"),
                "to":       end_date.strftime("%Y-%m-%d"),
            }
            headers = {
                "X-Api-Key": api_key
            }

            response = session.get(NEWS_BASE_URL, params=params, headers=headers, timeout=30)
            response.raise_for_status()

            articles = response.json().get("articles", [])

            if not articles:
                print(f"  [WARNING]  No articles found for query: {query[:40]}...")
                continue

            for article in articles:
                title = article.get("title", "")
                desc = article.get("description", "")
                all_articles.append({
                    "title":               title,
                    "description":         desc,
                    "url":                 article.get("url", ""),
                    "source":              article.get("source", {}).get("name", ""),
                    "published_at":        article.get("publishedAt", ""),
                    "query_tickers":       ",".join(tickers),
                    "matched_tickers":     map_article_to_tickers(title, desc, tickers),
                    "ingestion_timestamp": datetime.now(timezone.utc).isoformat(),
                    "data_source":         "newsapi",
                })

            print(f"   Retrieved {len(articles)} articles")

        except Exception as e:
            print(f"  [ERROR] Failed: {e}")
            failed.append(query[:30])

        time.sleep(1)

    if not all_articles:
        print("\n[ERROR] No articles retrieved. Check your NEWS_API_KEY.")
        sys.exit(1)

    df = pd.DataFrame(all_articles)
    df = pd.DataFrame(df.drop_duplicates(subset=["url"]))
    # Use .loc[mask] instead of df[mask]: pandas stubs type .loc with a boolean
    # indexer as returning DataFrame, whereas __getitem__(mask) is typed as Series.
    # Wrap in pd.DataFrame() to narrow the inferred type from DataFrame|Series
    # to DataFrame — Pyright cannot narrow .loc[bool].reset_index() further.
    title_mask = df["title"].notna() & (df["title"] != "[Removed]")
    df = pd.DataFrame(df.loc[title_mask].reset_index(drop=True))

    print(f"\n Total articles collected : {len(df):,}")
    print(f" Unique sources           : {df['source'].nunique()}")

    write_bronze_delta(df, "news", mode="overwrite")

    print("\n" + "=" * 60)
    print("INGESTION SUMMARY")
    print("=" * 60)
    # Safely build date-range strings: .min()/.max() return scalar objects;
    # convert to str first, then slice — avoids Pyright unknown-index errors.
    pub_min = str(df["published_at"].min())[:10]
    pub_max = str(df["published_at"].max())[:10]

    print(f" Articles collected : {len(df):,}")
    print(f"📰 Unique sources     : {df['source'].nunique()}")
    print(f"[ERROR] Failed queries     : {failed if failed else 'None'}")
    print(f"📅 Date range         : {pub_min} -> {pub_max}")
    print(f"📦 AWS Storage path : {get_s3_path('news')}")
    print("=" * 60)


if __name__ == "__main__":
    main()