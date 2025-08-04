import os
import pandas as pd
import requests
import time
from sqlalchemy import create_engine
from dotenv import load_dotenv
from prefect import task, flow, get_run_logger

@task(retries=3, retry_delay_seconds=10, log_prints=True)
def fetch_and_prepare_data(path: str) -> pd.DataFrame:
    """Lê os dados de Pokémon de um arquivo, trata erros e padroniza o DataFrame."""
    logger = get_run_logger()
    logger.info(f"Iniciando a leitura e preparação dos dados de '{path}'...")
    try:
        df = pd.read_csv(path, encoding='utf-16', delimiter='\t')
        logger.info(f"Arquivo lido com sucesso. Total de {len(df)} registros encontrados.")

        df.columns = df.columns.str.strip().str.lower()
        logger.info("Nomes de colunas limpos (sem espaços e em minúsculas).")

        if 'english_name' in df.columns:
            df.rename(columns={'english_name': 'name'}, inplace=True)
            logger.info("Coluna 'english_name' renomeada para 'name'.")
        
        return df
    except Exception as e:
        logger.error(f"Falha ao ler ou preparar os dados: {e}")
        raise

@task(log_prints=True)
def enrich_data_with_api(df_to_process: pd.DataFrame) -> pd.DataFrame:
    """Busca informações na PokeApi para os registros do DataFrame fornecido."""
    logger = get_run_logger()
    if df_to_process.empty:
        logger.warning("DataFrame vazio, pulando etapa de enriquecimento.")
        return None

    enriched_rows = []
    logger.info(f"Iniciando o enriquecimento com a PokeApi para {len(df_to_process)} registros...")
    
    for index, row in df_to_process.iterrows():
        pokemon_name = row['name'].lower()
        logger.info(f"  -> Buscando dados para: {pokemon_name}")
        
        # Faz uma cópia da linha para evitar SettingWithCopyWarning
        new_row = row.to_dict()
        
        try:
            response = requests.get(f"https://pokeapi.co/api/v2/pokemon/{pokemon_name}", timeout=10)
            if response.status_code == 200:
                data = response.json()
                new_row['sprite_url'] = data.get('sprites', {}).get('front_default')
            else:
                new_row['sprite_url'] = None
                logger.warning(f"Pokémon {pokemon_name} não encontrado (Status: {response.status_code}).")
        except requests.exceptions.RequestException as e:
            new_row['sprite_url'] = None
            logger.error(f"ERRO de conexão ao buscar {pokemon_name}: {e}")
        
        enriched_rows.append(new_row)
        time.sleep(0.2) # Podemos diminuir um pouco o sleep

    logger.info("Processo de enriquecimento finalizado.")
    return pd.DataFrame(enriched_rows)

@task(log_prints=True)
def save_data_to_db(df: pd.DataFrame, table_name: str, connection_string: str):
    """Salva o DataFrame no banco de dados"""
    logger = get_run_logger()
    if df is None or df.empty:
        logger.warning("Nenhum dado para salvar.")
        return

    logger.info(f"Iniciando salvamento na tabela '{table_name}' do banco de dados na nuvem...")
    try:
        engine = create_engine(connection_string)
        df.to_sql(table_name, con=engine, if_exists='replace', index=False, schema='public')
        logger.info(f"Dados salvos com sucesso!")
    except Exception as e:
        logger.error(f"Falha ao salvar os dados: {e}")
        raise

@task(log_prints=True)
def clean_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Limpa o DataFrame, tratando valores nulos em colunas numéricas."""
    logger = get_run_logger()
    if df is None or df.empty:
        logger.warning("DataFrame vazio, pulando etapa de limpeza.")
        return None

    logger.info("Iniciando limpeza do DataFrame...")
    
    # Lista de colunas que esperamos que sejam numéricas
    numeric_cols = [
        'national_number', 'height_m', 'weight_kg', 
        'hp', 'attack', 'defense', 'sp_attack', 'sp_defense', 'speed'
    ]
    
    # Tratamento para capture_rate que pode ser não-numérico
    df['capture_rate'] = pd.to_numeric(df['capture_rate'], errors='coerce').fillna(0)
    
    for col in numeric_cols:
        if col in df.columns:
            # Preenche valores nulos com 0 e converte a coluna para inteiro
            df[col] = df[col].fillna(0).astype(int)
    
    logger.info("Limpeza de valores nulos e coerção de tipos concluída.")
    return df

@flow(name="ETL de Pokémon - Ingestão por Quantidade", log_prints=True)
def pokemon_etl_flow(num_pokemon: int):
    """
    Fluxo que ingere, limpa, enriquece e salva dados de Pokémon.
    """
    load_dotenv(dotenv_path='pokedb.env')
    
    connection_string = (
        f"postgresql://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}"
        f"@{os.getenv('DB_HOST')}:{os.getenv('DB_PORT')}/{os.getenv('DB_NAME')}"
    )

    path = 'data/pokemon.csv'
    table_name = f'pokemon_first_{num_pokemon}'

    df_raw = fetch_and_prepare_data(path)
    df_to_process = df_raw.head(num_pokemon)
    df_enriched = enrich_data_with_api(df_to_process)
    df_cleaned = clean_dataframe(df_enriched)
    
    # Passa a string de conexão para a task de salvamento
    save_data_to_db(df_cleaned, table_name=table_name, connection_string=connection_string)

if __name__ == "__main__":
    pokemon_count = 898
    pokemon_etl_flow(num_pokemon=pokemon_count)