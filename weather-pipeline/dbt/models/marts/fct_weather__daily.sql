{{ config(materialized='table') }}

-- Latest snapshot wins: for each (location, forecast_date),
-- keep the row from the most recent fetch.

with ranked as (

    select
        location_name,
        forecast_date,
        weather_code,
        temperature_max_c,
        temperature_min_c,
        precipitation_sum_mm,
        wind_speed_max_kmh,
        fetched_at,
        row_number() over (
            partition by location_name, forecast_date
            order by fetched_at desc
        ) as recency_rank
    from {{ ref('stg_weather__daily') }}

)

select
    location_name,
    forecast_date,
    weather_code,
    temperature_max_c,
    temperature_min_c,
    precipitation_sum_mm,
    wind_speed_max_kmh,
    fetched_at as latest_snapshot_at
from ranked
where recency_rank = 1
