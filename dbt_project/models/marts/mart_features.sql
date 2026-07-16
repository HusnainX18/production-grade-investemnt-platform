WITH prices AS (
    SELECT 
        symbol, 
        date, 
        open, 
        high, 
        low, 
        close, 
        volume, 
        trade_count, 
        vwap, 
        asset_class, 
        sector, 
        industry 
    FROM {{ ref('stg_stocks') }}
    UNION ALL
    SELECT 
        symbol, 
        date, 
        open, 
        high, 
        low, 
        close, 
        volume, 
        trade_count, 
        vwap, 
        asset_class, 
        'Crypto' as sector, 
        'Cryptocurrency' as industry 
    FROM {{ ref('stg_crypto') }}
),

technicals AS (
    SELECT
        symbol,
        date,
        open,
        high,
        low,
        close,
        volume,
        trade_count,
        vwap,
        asset_class,
        sector,
        industry,
        
        -- Simple Moving Averages (SMAs)
        AVG(close) OVER (PARTITION BY symbol ORDER BY date ROWS BETWEEN 19 PRECEDING AND CURRENT ROW) as sma_20,
        AVG(close) OVER (PARTITION BY symbol ORDER BY date ROWS BETWEEN 49 PRECEDING AND CURRENT ROW) as sma_50,
        AVG(close) OVER (PARTITION BY symbol ORDER BY date ROWS BETWEEN 199 PRECEDING AND CURRENT ROW) as sma_200,
        
        -- Bollinger Bands
        STDDEV_SAMP(close) OVER (PARTITION BY symbol ORDER BY date ROWS BETWEEN 19 PRECEDING AND CURRENT ROW) as bb_std,
        
        -- Returns (1d, 5d, 20d)
        (close - LAG(close, 1) OVER (PARTITION BY symbol ORDER BY date)) / LAG(close, 1) OVER (PARTITION BY symbol ORDER BY date) as return_1d,
        (close - LAG(close, 5) OVER (PARTITION BY symbol ORDER BY date)) / LAG(close, 5) OVER (PARTITION BY symbol ORDER BY date) as return_5d,
        (close - LAG(close, 20) OVER (PARTITION BY symbol ORDER BY date)) / LAG(close, 20) OVER (PARTITION BY symbol ORDER BY date) as return_20d
    FROM prices
),

targets AS (
    SELECT
        *,
        -- Bollinger Bands calculations
        sma_20 + (2.0 * bb_std) as bb_upper,
        sma_20 - (2.0 * bb_std) as bb_lower,
        CASE WHEN sma_20 != 0 THEN (4.0 * bb_std) / sma_20 ELSE 0 END as bb_width,
        
        -- Price Volatility (rolling standard deviation of daily returns)
        STDDEV_SAMP(return_1d) OVER (PARTITION BY symbol ORDER BY date ROWS BETWEEN 19 PRECEDING AND CURRENT ROW) as volatility_20d,

        -- Relative Strength vs. Sector: how much this symbol outperforms its sector peers on this day
        return_1d - AVG(return_1d) OVER (PARTITION BY sector, date) as rel_strength_sector,
        
        -- ML Target Variables (Next-day return, and next 5-day return)
        LEAD(return_1d, 1) OVER (PARTITION BY symbol ORDER BY date) as target_1d_return,
        (LEAD(close, 5) OVER (PARTITION BY symbol ORDER BY date) - close) / close as target_5d_return
    FROM technicals
)

SELECT
    t.symbol,
    t.date,
    t.open,
    t.high,
    t.low,
    t.close,
    t.volume,
    t.trade_count,
    t.vwap,
    t.asset_class,
    t.sector,
    t.industry,
    
    -- Technicals
    t.sma_20,
    t.sma_50,
    t.sma_200,
    t.bb_upper,
    t.bb_lower,
    t.bb_width,
    t.return_1d,
    t.return_5d,
    t.return_20d,
    t.volatility_20d,
    t.rel_strength_sector,
    
    -- Targets
    t.target_1d_return,
    t.target_5d_return,
    
    -- Macro indicators (from intermediate pivoted macro)
    m.fedfunds,
    m.cpi,
    m.unemployment_rate,
    m.gdp,
    m.treasury_10y,
    m.treasury_2y,
    m.vix,
    m.m2_money_supply,
    m.crude_oil,
    m.usd_eur,
    m.yield_curve_slope,
    
    -- News Sentiment (COALESCE to 0 if no news matches)
    COALESCE(s.sentiment_net, 0.0) as sentiment_net
    
FROM targets t
LEFT JOIN {{ ref('int_macro_daily') }} m
    ON t.date = m.date
LEFT JOIN {{ ref('int_news_sentiment') }} s
    ON t.symbol = s.symbol AND t.date = s.date
