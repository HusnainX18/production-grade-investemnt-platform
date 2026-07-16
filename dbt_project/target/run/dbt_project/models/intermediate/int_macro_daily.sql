
  
  
  
  create or replace view `workspace`.`default`.`int_macro_daily`
  
  as (
    WITH daily_dates AS (
    SELECT DISTINCT date FROM `workspace`.`default`.`stg_stocks`
    UNION
    SELECT DISTINCT date FROM `workspace`.`default`.`stg_crypto`
),

macro_series AS (
    SELECT DISTINCT series_id FROM `workspace`.`default`.`stg_macro`
),

grid AS (
    SELECT d.date, m.series_id
    FROM daily_dates d
    CROSS JOIN macro_series m
),

joined AS (
    SELECT
        g.date,
        g.series_id,
        m.value
    FROM grid g
    LEFT JOIN `workspace`.`default`.`stg_macro` m
        ON g.date = m.date AND g.series_id = m.series_id
),

forward_filled AS (
    SELECT
        date,
        series_id,
        LAST_VALUE(value, true) OVER (
            PARTITION BY series_id 
            ORDER BY date 
            ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
        ) as value
    FROM joined
)

SELECT
    date,
    MAX(CASE WHEN series_id = 'FEDFUNDS' THEN value END) as fedfunds,
    MAX(CASE WHEN series_id = 'CPIAUCSL' THEN value END) as cpi,
    MAX(CASE WHEN series_id = 'UNRATE' THEN value END) as unemployment_rate,
    MAX(CASE WHEN series_id = 'GDP' THEN value END) as gdp,
    MAX(CASE WHEN series_id = 'DGS10' THEN value END) as treasury_10y,
    MAX(CASE WHEN series_id = 'DGS2' THEN value END) as treasury_2y,
    MAX(CASE WHEN series_id = 'VIXCLS' THEN value END) as vix,
    MAX(CASE WHEN series_id = 'M2SL' THEN value END) as m2_money_supply,
    MAX(CASE WHEN series_id = 'DCOILWTICO' THEN value END) as crude_oil,
    MAX(CASE WHEN series_id = 'DEXUSEU' THEN value END) as usd_eur,
    -- Yield Curve Slope = 10-Year minus 2-Year Treasury Yields
    (MAX(CASE WHEN series_id = 'DGS10' THEN value END) - MAX(CASE WHEN series_id = 'DGS2' THEN value END)) as yield_curve_slope
FROM forward_filled
GROUP BY date
  )
