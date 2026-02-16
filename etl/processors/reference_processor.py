from __future__ import annotations

from pathlib import Path

import pandas as pd
from sqlalchemy import Engine, text

from app.config import settings
from app.database import engine as default_engine
from etl.utils.postgres_copy import copy_dataframe_to_staging, quote_ident, upsert_from_staging

CSV_COLUMNS = ["codigo", "descricao"]


def _normalize_strings(chunk: pd.DataFrame) -> pd.DataFrame:
    for col in chunk.columns:
        chunk[col] = chunk[col].astype("string").str.strip()
    chunk = chunk.replace({"": None, pd.NA: None})
    return chunk


def _prepare_chunk(chunk: pd.DataFrame) -> pd.DataFrame:
    chunk = chunk.copy()
    chunk = _normalize_strings(chunk)
    prepared = chunk[CSV_COLUMNS].copy()
    prepared = prepared[prepared["codigo"].notna() & prepared["descricao"].notna()]
    prepared = prepared.drop_duplicates(subset=["codigo"])
    return prepared


def _ensure_staging_table(engine: Engine, staging_table: str) -> None:
    sql = f"""
        CREATE TABLE IF NOT EXISTS {quote_ident(staging_table)} (
            codigo TEXT,
            descricao TEXT
        )
    """
    with engine.begin() as connection:
        connection.execute(text(sql))


def process_reference_csv(
    file_path: str | Path,
    target_table: str,
    staging_table: str,
    engine: Engine = default_engine,
    chunk_size: int = settings.BATCH_SIZE,
) -> int:
    _ensure_staging_table(engine, staging_table)

    chunks = pd.read_csv(
        file_path,
        sep=";",
        dtype=str,
        encoding="latin1",
        chunksize=chunk_size,
        header=None,
        names=CSV_COLUMNS,
        usecols=[0, 1],
        keep_default_na=False,
    )

    processed = 0
    for chunk in chunks:
        prepared = _prepare_chunk(chunk)
        if prepared.empty:
            continue

        copy_dataframe_to_staging(engine, prepared, staging_table)
        upsert_from_staging(
            engine,
            staging_table=staging_table,
            target_table=target_table,
            insert_columns=CSV_COLUMNS,
            conflict_columns=["codigo"],
        )
        processed += len(prepared)

    return processed
