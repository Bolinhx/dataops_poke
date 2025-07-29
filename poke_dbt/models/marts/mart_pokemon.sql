

with stg_pokemon as (

    select * from {{ ref('stg_pokemon') }}

),

-- adicionando nossas transformações e regras de negócio
final_pokemon as (

    select
        -- Mantemos as colunas que já temos
        pokemon_id,
        pokemon_name,
        generation,
        primary_type,
        secondary_type,
        height_m,
        weight_kg,
        hp,
        attack,
        defense,
        sp_attack,
        sp_defense,
        speed,
        sprite_url,

        -- Adicionamos novas colunas calculadas
        (hp + attack + defense + sp_attack + sp_defense + speed) as total_stats,

        case
            when (hp + attack + defense + sp_attack + sp_defense + speed) >= 600 then 'Lendário'
            when (hp + attack + defense + sp_attack + sp_defense + speed) >= 450 then 'Forte'
            when (hp + attack + defense + sp_attack + sp_defense + speed) >= 300 then 'Comum'
            else 'Fraco'
        end as power_tier,

        -- Criamos uma coluna que combina os tipos para facilitar a filtragem
        primary_type || coalesce(' / ' || secondary_type, '') as full_type

    from stg_pokemon
)

-- resultado final
select * from final_pokemon