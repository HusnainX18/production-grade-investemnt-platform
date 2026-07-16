SELECT
    title,
    description,
    url,
    source,
    CAST(published_at AS TIMESTAMP) as published_at,
    query_tickers,
    matched_tickers,
    data_source,
    CAST(ingestion_timestamp AS TIMESTAMP) as ingestion_timestamp
FROM workspace.default.silver_news
