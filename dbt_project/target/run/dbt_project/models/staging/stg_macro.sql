
  
  
  
  create or replace view `workspace`.`default`.`stg_macro`
  
  as (
    SELECT
    CAST(date AS DATE) as date,
    CAST(value AS DOUBLE) as value,
    series_id,
    series_name,
    data_source,
    CAST(ingestion_timestamp AS TIMESTAMP) as ingestion_timestamp
FROM workspace.default.silver_macro
  )
