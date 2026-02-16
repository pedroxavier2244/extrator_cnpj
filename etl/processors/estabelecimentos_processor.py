from __future__ import annotations

from pathlib import Path

import pandas as pd
from sqlalchemy import Engine, text

from app.config import settings
from app.database import engine as default_engine
from etl.utils.normalize import normalize_date_columns
from etl.utils.postgres_copy import copy_dataframe_to_staging, quote_ident, upsert_from_staging

CSV_COLUMNS = [
    "cnpj_basico",
    "cnpj_ordem",
    "cnpj_dv",
    "matriz_filial",
    "nome_fantasia",
    "situacao",
    "data_situacao",
    "motivo",
    "cidade_exterior",
    "pais",
    "inicio",
    "cnae_principal",
    "cnae_secundario",
    "tipo_logradouro",
    "logradouro",
    "numero",
    "complemento",
    "bairro",
    "cep",
    "uf",
    "municipio",
    "ddd1",
    "telefone1",
    "ddd2",
    "telefone2",
    "email",
    "situacao_especial",
    "data_situacao_especial",
]

DATE_COLUMNS = ["data_situacao", "inicio", "data_situacao_especial"]

INSERT_COLUMNS = [
    "cnpj_completo",
    "cnpj_basico",
    "nome_fantasia",
    "situacao",
    "uf",
    "municipio",
    "cnae_principal",
    "cnae_secundario",
    "pais",
    "motivo",
]

STAGING_TABLE = "stg_estabelecimentos"
TARGET_TABLE = "estabelecimentos"


def _normalize_strings(chunk: pd.DataFrame) -> pd.DataFrame:
    for col in chunk.columns:
        chunk[col] = chunk[col].astype("string").str.strip()
    chunk = chunk.replace({"": None, pd.NA: None})
    return chunk


def _normalize_dates(chunk: pd.DataFrame) -> pd.DataFrame:
    return normalize_date_columns(chunk, DATE_COLUMNS)


def _prepare_chunk(chunk: pd.DataFrame) -> pd.DataFrame:
    chunk = chunk.copy()
    chunk = _normalize_strings(chunk)
    chunk = _normalize_dates(chunk)

    chunk["cnpj_completo"] = (
        chunk["cnpj_basico"].fillna("") + chunk["cnpj_ordem"].fillna("") + chunk["cnpj_dv"].fillna("")
    )
    chunk.loc[chunk["cnpj_completo"].str.len() != 14, "cnpj_completo"] = None

    prepared = chunk[INSERT_COLUMNS].copy()
    prepared = prepared[prepared["cnpj_basico"].notna() & prepared["cnpj_completo"].notna()]
    prepared = prepared.drop_duplicates(subset=["cnpj_completo"])
    return prepared


def _ensure_staging_table(engine: Engine) -> None:
    sql = f"""
        CREATE TABLE IF NOT EXISTS {quote_ident(STAGING_TABLE)} (
            cnpj_completo VARCHAR(14),
            cnpj_basico VARCHAR(8),
            nome_fantasia TEXT,
            situacao TEXT,
            uf VARCHAR(2),
            municipio TEXT,
            cnae_principal TEXT,
            cnae_secundario TEXT,
            pais TEXT,
            motivo TEXT
        )
    """
    with engine.begin() as connection:
        connection.execute(text(sql))


def process_estabelecimentos_csv(
    file_path: str | Path,
    engine: Engine = default_engine,
    chunk_size: int = settings.BATCH_SIZE,
) -> int:
    _ensure_staging_table(engine)

    try:
        chunks = pd.read_csv(
            file_path,
            sep=";",
            dtype=str,
            encoding="latin1",
            chunksize=chunk_size,
            usecols=CSV_COLUMNS,
            keep_default_na=False,
        )
    except ValueError:
        chunks = pd.read_csv(
            file_path,
            sep=";",
            dtype=str,
            encoding="latin1",
            chunksize=chunk_size,
            header=None,
            names=CSV_COLUMNS,
            usecols=list(range(len(CSV_COLUMNS))),
            keep_default_na=False,
        )

    processed = 0
    for chunk in chunks:
        prepared = _prepare_chunk(chunk)
        if prepared.empty:
            continue

        copy_dataframe_to_staging(engine, prepared, STAGING_TABLE)
        upsert_from_staging(
            engine,
            staging_table=STAGING_TABLE,
            target_table=TARGET_TABLE,
            insert_columns=INSERT_COLUMNS,
            conflict_columns=["cnpj_completo"],
        )
        processed += len(prepared)

    return processed
