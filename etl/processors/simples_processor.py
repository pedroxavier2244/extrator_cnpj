from __future__ import annotations

from pathlib import Path

import pandas as pd
from sqlalchemy import Engine, text

from app.config import settings
from app.database import engine as default_engine
from etl.utils.postgres_copy import copy_dataframe_to_staging, upsert_from_staging

CSV_COLUMNS = [
    "cnpj_basico",
    "opcao_pelo_simples",
    "data_opcao_pelo_simples",
    "data_exclusao_do_simples",
    "opcao_pelo_mei",
    "data_opcao_pelo_mei",
    "data_exclusao_do_mei",
]

DATE_COLUMNS = [
    "data_opcao_pelo_simples",
    "data_exclusao_do_simples",
    "data_opcao_pelo_mei",
    "data_exclusao_do_mei",
]

STAGING_TABLE = "stg_simples"
TARGET_TABLE = "simples"


def _normalize_strings(chunk: pd.DataFrame) -> pd.DataFrame:
    for col in chunk.columns:
        chunk[col] = chunk[col].astype("string").str.strip()
    chunk = chunk.replace({"": None, pd.NA: None, "00000000": None})
    return chunk


def _normalize_dates(chunk: pd.DataFrame) -> pd.DataFrame:
    for col in DATE_COLUMNS:
        parsed = pd.to_datetime(chunk[col], format="%Y%m%d", errors="coerce")
        chunk[col] = parsed.dt.strftime("%Y-%m-%d").where(parsed.notna(), None)
    return chunk


def _prepare_chunk(chunk: pd.DataFrame) -> pd.DataFrame:
    chunk = _normalize_strings(chunk)
    chunk = _normalize_dates(chunk)

    chunk["cnpj_basico"] = chunk["cnpj_basico"].str.zfill(8)
    chunk.loc[chunk["cnpj_basico"].str.len() != 8, "cnpj_basico"] = None

    prepared = chunk[CSV_COLUMNS].copy()
    prepared = prepared[prepared["cnpj_basico"].notna()]
    prepared = prepared.drop_duplicates(subset=["cnpj_basico"])
    return prepared


def _ensure_staging_table(engine: Engine) -> None:
    sql = f"""
        CREATE TABLE IF NOT EXISTS {STAGING_TABLE} (
            cnpj_basico VARCHAR(8),
            opcao_pelo_simples CHAR(1),
            data_opcao_pelo_simples DATE,
            data_exclusao_do_simples DATE,
            opcao_pelo_mei CHAR(1),
            data_opcao_pelo_mei DATE,
            data_exclusao_do_mei DATE
        )
    """
    with engine.begin() as connection:
        connection.execute(text(sql))


def process_simples_csv(
    file_path: str | Path,
    engine: Engine = default_engine,
    chunk_size: int = settings.BATCH_SIZE,
) -> int:
    _ensure_staging_table(engine)

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
            insert_columns=CSV_COLUMNS,
            conflict_columns=["cnpj_basico"],
        )
        processed += len(prepared)

    return processed
