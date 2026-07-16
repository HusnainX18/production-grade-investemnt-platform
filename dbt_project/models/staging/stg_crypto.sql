SELECT
    symbol,
    CAST(timestamp AS DATE) as date,
    CAST(open AS DOUBLE) as open,
    CAST(high AS DOUBLE) as high,
    CAST(low AS DOUBLE) as low,
    CAST(close AS DOUBLE) as close,
    CAST(volume AS DOUBLE) as volume,
    CAST(trade_count AS BIGINT) as trade_count,
    CAST(vwap AS DOUBLE) as vwap,
    asset_class,
    CAST(ingestion_timestamp AS TIMESTAMP) as ingestion_timestamp
FROM workspace.default.silver_crypto
