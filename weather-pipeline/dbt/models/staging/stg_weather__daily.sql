{{ config(materialized='view') }}

-- Parse the raw Open-Meteo daily arrays into one row per
-- (location, snapshot, forecast day). Staging keeps every snapshot —
-- no deduping here; the mart layer picks the latest.

with snapshots as (

    select
        location_name,
        latitude,
        longitude,
        fetched_at,
        payload
    from {{ source('raw', 'weather_responses') }}

),

indices as (

    select
        location_name,
        latitude,
        longitude,
        fetched_at,
        payload,
        unnest(range(cast(json_array_length(payload, '$.daily.time') as bigint))) as day_index
    from snapshots

)

select
    location_name,
    latitude,
    longitude,
    fetched_at,
    cast(json_extract_string(payload, '$.daily.time[' || day_index || ']') as date)         as forecast_date,
    cast(json_extract_string(payload, '$.daily.weather_code[' || day_index || ']') as integer)   as weather_code,
    cast(json_extract_string(payload, '$.daily.temperature_2m_max[' || day_index || ']') as double) as temperature_max_c,
    cast(json_extract_string(payload, '$.daily.temperature_2m_min[' || day_index || ']') as double) as temperature_min_c,
    cast(json_extract_string(payload, '$.daily.precipitation_sum[' || day_index || ']') as double)   as precipitation_sum_mm,
    cast(json_extract_string(payload, '$.daily.wind_speed_10m_max[' || day_index || ']') as double)   as wind_speed_max_kmh
from indices
