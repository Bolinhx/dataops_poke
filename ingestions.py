import pandas as pd
import requests
import time
from sqlalchemy import create_engine
from prefect import task, flow, get_run_logger

@task(retries=3, retry_delay_seconds=10, log_prints=True)
def fetch_and_prepare_data(path: str) -> pd.DataFrame:
    """Lê os dados de Pokémon de um arquivo, trata erros e padroniza o DataFrame."""
    logger = get_run_logger()
    logger.info("Iniciando a leitura e preparação dos dados...")
    try:
        df = pd.read_csv(path, encoding='utf-16', delimiter='\t')
        logger.info(f"Arquivo lido com sucesso de '{path}'. Total de {len(df)} registros.")

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
def enrich_data_with_api(df: pd.DataFrame, num_records: int) -> pd.DataFrame:
    """Busca informações na PokeApi para um número definido de registros e adiciona a URL do sprite."""
    logger = get_run_logger()
    if df is None:
        logger.warning("DataFrame vazio, pulando etapa de enriquecimento.")
        return None

    df_sample = df.head(num_records).copy()
    image_urls = []
    logger.info(f"Iniciando o enriquecimento com a PokeApi para {num_records} registros...")
    
    for index, row in df_sample.iterrows():
        pokemon_name = row['name'].lower()
        logger.info(f"  -> Buscando dados para: {pokemon_name}")
        try:
            response = requests.get(f"https://pokeapi.co/api/v2/pokemon/{pokemon_name}", timeout=10)
            if response.status_code == 200:
                data = response.json()
                image_url = data.get('sprites', {}).get('front_default')
                image_urls.append(image_url)
            else:
                image_urls.append(None)
                logger.warning(f"Pokémon {pokemon_name} não encontrado (Status: {response.status_code}).")
        except requests.exceptions.RequestException as e:
            logger.error(f"ERRO de conexão ao buscar {pokemon_name}: {e}")
            image_urls.append(None)
        time.sleep(0.5)

    df_sample['sprite_url'] = image_urls
    logger.info("Processo de enriquecimento finalizado.")
    return df_sample

@task(log_prints=True)
def save_data_to_db(df: pd.DataFrame, db_name: str, table_name: str):
    """Salva o DataFrame em uma tabela do DuckDB."""
    logger = get_run_logger()
    if df is None:
        logger.warning("Nenhum dado para salvar.")
        return

    logger.info(f"Iniciando salvamento no banco de dados '{db_name}.db'...")
    try:
        engine = create_engine(f"duckdb:///{db_name}.db")
        df.to_sql(table_name, con=engine, if_exists='replace', index=False)
        logger.info(f"Dados salvos com sucesso na tabela '{table_name}'!")
    except Exception as e:
        logger.error(f"Falha ao salvar os dados no DuckDB: {e}")
        raise

@flow(name="ETL de Pokémon - Ingestão e Enriquecimento", log_prints=True)
def pokemon_etl_flow(num_pokemon: int = 10):
    """
    Fluxo principal que orquestra a ingestão de dados de Pokémon,
    o enriquecimento via API e o salvamento em um banco de dados.
    """
    path = 'data/pokemon.csv'
    database_name = 'pokemon_raw'
    
    df_raw = fetch_and_prepare_data(path)
    df_enriched = enrich_data_with_api(df_raw, num_records=num_pokemon)
    save_data_to_db(df_enriched, database_name, table_name=f'pokemon_top_{num_pokemon}')

if __name__ == "__main__":
    # Executa o fluxo com um número específico de pokémons
    pokemon_etl_flow(num_pokemon=20)