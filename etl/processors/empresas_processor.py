from __future__ import annotations

from pathlib import Path

import pandas as pd
from sqlalchemy import Engine, text

from app.config import settings
from app.database import engine as default_engine
from etl.utils.postgres_copy import copy_dataframe_to_staging, quote_ident, upsert_from_staging

CSV_COLUMNS = [
    "cnpj_basico",
    "razao_social",
    "natureza_juridica",
    "qualificacao_responsavel",
    "capital_social",
    "porte_empresa",
    "ente_federativo",
]

INSERT_COLUMNS = [
    "cnpj_basico",
    "razao_social",
    "natureza_juridica",
    "capital_social",
    "porte_empresa",
]

STAGING_TABLE = "stg_empresas"
TARGET_TABLE = "empresas"


def _normalize_strings(chunk: pd.DataFrame) -> pd.DataFrame:
    for col in chunk.columns:
        chunk[col] = chunk[col].astype("string").str.strip()
    chunk = chunk.replace({"": None, pd.NA: None})
    return chunk


def _prepare_chunk(chunk: pd.DataFrame) -> pd.DataFrame:
    chunk = chunk.copy()
    chunk = _normalize_strings(chunk)
    prepared = chunk[INSERT_COLUMNS].copy()
    prepared = prepared[prepared["cnpj_basico"].notna()]
    return prepared


def _ensure_staging_table(engine: Engine) -> None:
    sql = f"""
        CREATE TABLE IF NOT EXISTS {quote_ident(STAGING_TABLE)} (
            cnpj_basico VARCHAR(8),
            razao_social TEXT,
            natureza_juridica TEXT,
            capital_social TEXT,
            porte_empresa TEXT
        )
    """
    with engine.begin() as connection:
        connection.execute(text(sql))


def process_empresas_csv(
    file_path: str | Path,
    engine: Engine = default_engine,
    chunk_size: int = settings.BATCH_SIZE,
) -> int:
    _ensure_staging_table(engine)

    processed = 0
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
        # Receita files may come without header; map fields by fixed SPEC order.
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
            conflict_columns=["cnpj_basico"],
        )
        processed += len(prepared)

    return processed
