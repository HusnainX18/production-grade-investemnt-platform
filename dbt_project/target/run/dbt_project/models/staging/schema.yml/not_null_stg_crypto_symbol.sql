
    
    select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
  
    
    



select symbol
from `investment_platform_db_ws`.`default`.`stg_crypto`
where symbol is null



  
  
      
    ) dbt_internal_test