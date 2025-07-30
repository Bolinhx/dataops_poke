
with stg_pokemon as (
    select * from {{ ref('stg_pokemon') }}
),

average_stats as (
    select
        avg(attack + sp_attack) as avg_total_offense,
        
        avg(defense + sp_defense) as avg_total_defense,

        avg(speed) as avg_speed
    from stg_pokemon
),

final_pokemon as (
    select
        stg_pokemon.*,

        (stg_pokemon.attack + stg_pokemon.sp_attack) as total_offense,
        (stg_pokemon.defense + stg_pokemon.sp_defense) as total_defense,

        case
            -- 1. Sweepers: Ataque total E velocidade acima da média
            when (stg_pokemon.attack + stg_pokemon.sp_attack) >= average_stats.avg_total_offense
             and stg_pokemon.speed >= average_stats.avg_speed
             then 'Sweeper'

            -- 2. Walls: Defesa total acima da média
            when (stg_pokemon.defense + stg_pokemon.sp_defense) >= average_stats.avg_total_defense
             then 'Wall'

            -- 3. Breakers (Glass Cannons): Ataque total acima da média, mas não se qualificou como Sweeper (ou seja, velocidade não é alta)
            when (stg_pokemon.attack + stg_pokemon.sp_attack) >= average_stats.avg_total_offense
             then 'Breaker'

            else 'Utilitário'
        end as combat_role

    from stg_pokemon
    
    cross join average_stats
)

select * from final_pokemon