
  
    
        create or replace table `workspace`.`default`.`mart_sector_perf`
      
      
    using delta
  
      
      
      
      
      
      
      
      
      as
      SELECT
    sector,
    date,
    -- Average daily return across all assets in the sector
    AVG(return_1d) as avg_return_1d,
    -- Average volatility in the sector
    AVG(volatility_20d) as avg_volatility_20d,
    -- Total trading volume
    SUM(volume) as total_volume,
    -- Count of active assets on that day
    COUNT(DISTINCT symbol) as active_assets
FROM `workspace`.`default`.`mart_features`
GROUP BY sector, date
  