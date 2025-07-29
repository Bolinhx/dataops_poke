with source as (

    select * from {{ source('raw_pokemon_data', 'pokemon_top_20') }} 

)

select
    national_number as pokemon_id,
    name as pokemon_name,
    gen as generation,
    primary_type,
    secondary_type,
    classification,
    cast(height_m as float) as height_m,
    cast(weight_kg as float) as weight_kg,
    cast(capture_rate as int) as capture_rate,
    hp,
    attack,
    defense,
    sp_attack,
    sp_defense,
    speed,
    sprite_url
from source