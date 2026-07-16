
    
    

with all_values as (

    select
        asset_class as value_field,
        count(*) as n_records

    from `investment_platform_db_ws`.`default`.`stg_crypto`
    group by asset_class

)

select *
from all_values
where value_field not in (
    'crypto'
)


