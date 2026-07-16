
  
  
  
  create or replace view `workspace`.`default`.`int_news_sentiment`
  
  as (
    WITH word_counts AS (
    SELECT
        matched_tickers,
        CAST(published_at AS DATE) as date,
        title,
        description,
        -- Positive financial term scoring
        (CASE WHEN LOWER(title) LIKE '%up%' OR LOWER(description) LIKE '%up%' THEN 1 ELSE 0 END +
         CASE WHEN LOWER(title) LIKE '%growth%' OR LOWER(description) LIKE '%growth%' THEN 1 ELSE 0 END +
         CASE WHEN LOWER(title) LIKE '%gain%' OR LOWER(description) LIKE '%gain%' THEN 1 ELSE 0 END +
         CASE WHEN LOWER(title) LIKE '%profit%' OR LOWER(description) LIKE '%profit%' THEN 1 ELSE 0 END +
         CASE WHEN LOWER(title) LIKE '%beat%' OR LOWER(description) LIKE '%beat%' THEN 1 ELSE 0 END +
         CASE WHEN LOWER(title) LIKE '%surge%' OR LOWER(description) LIKE '%surge%' THEN 1 ELSE 0 END +
         CASE WHEN LOWER(title) LIKE '%success%' OR LOWER(description) LIKE '%success%' THEN 1 ELSE 0 END) as pos_count,
         
        -- Negative financial term scoring
        (CASE WHEN LOWER(title) LIKE '%down%' OR LOWER(description) LIKE '%down%' THEN 1 ELSE 0 END +
         CASE WHEN LOWER(title) LIKE '%loss%' OR LOWER(description) LIKE '%loss%' THEN 1 ELSE 0 END +
         CASE WHEN LOWER(title) LIKE '%decline%' OR LOWER(description) LIKE '%decline%' THEN 1 ELSE 0 END +
         CASE WHEN LOWER(title) LIKE '%fail%' OR LOWER(description) LIKE '%fail%' THEN 1 ELSE 0 END +
         CASE WHEN LOWER(title) LIKE '%slump%' OR LOWER(description) LIKE '%slump%' THEN 1 ELSE 0 END +
         CASE WHEN LOWER(title) LIKE '%warn%' OR LOWER(description) LIKE '%warn%' THEN 1 ELSE 0 END +
         CASE WHEN LOWER(title) LIKE '%crash%' OR LOWER(description) LIKE '%crash%' THEN 1 ELSE 0 END) as neg_count
    FROM `workspace`.`default`.`stg_news`
    WHERE matched_tickers IS NOT NULL AND matched_tickers != ''
),

article_sentiment AS (
    SELECT
        matched_tickers,
        date,
        pos_count,
        neg_count,
        CASE 
            WHEN pos_count > neg_count THEN 1.0
            WHEN neg_count > pos_count THEN -1.0
            ELSE 0.0
        END as net_sentiment
    FROM word_counts
),

exploded_tickers AS (
    -- Split comma-separated tickers and explode them into individual rows
    SELECT
        TRIM(ticker) as symbol,
        date,
        net_sentiment
    FROM article_sentiment
    LATERAL VIEW EXPLODE(SPLIT(matched_tickers, ',')) as ticker
)

SELECT
    symbol,
    date,
    AVG(net_sentiment) as sentiment_net
FROM exploded_tickers
GROUP BY symbol, date
  )
