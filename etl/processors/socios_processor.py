from __future__ import annotations

from pathlib import Path

import pandas as pd
from sqlalchemy import Engine, text

from app.config import settings
from app.database import engine as default_engine
from etl.utils.postgres_copy import copy_dataframe_to_staging, quote_ident, upsert_from_staging

CSV_COLUMNS = [
    "cnpj_basico",
    "tipo",
    "nome",
    "cpf_cnpj",
    "qualificacao",
    "data_entrada",
    "pais",
    "cpf_rep",
    "nome_rep",
    "qualificacao_rep",
    "faixa_etaria",
]

DATE_COLUMNS = ["data_entrada"]

INSERT_COLUMNS = ["cnpj_basico", "nome_socio", "cpf_cnpj_socio", "qualificacao", "pais", "data_entrada"]

STAGING_TABLE = "stg_socios"
TARGET_TABLE = "socios"


def _normalize_strings(chunk: pd.DataFrame) -> pd.DataFrame:
    for col in chunk.columns:
        chunk[col] = chunk[col].astype("string").str.strip()
    chunk = chunk.replace({"": None, pd.NA: None})
    return chunk


def _normalize_dates(chunk: pd.DataFrame) -> pd.DataFrame:
    for col in DATE_COLUMNS:
        series = chunk[col].astype(str).str.strip()
        # Try YYYYMMDD first (standard RFB format)
        parsed = pd.to_datetime(series, format="%Y%m%d", errors="coerce")
        mask = parsed.isna() & ~series.isin(["", "None", "nan", "<NA>", "NaT"])
        if mask.any():
            parsed[mask] = pd.to_datetime(series[mask], errors="coerce", dayfirst=False)
        # Invalidate dates outside reasonable range (avoids year 21 AD etc.)
        valid = parsed.notna() & (parsed.dt.year >= 1900) & (parsed.dt.year <= 2100)
        chunk[col] = parsed.dt.strftime("%Y-%m-%d").where(valid, None)
    return chunk


def _prepare_chunk(chunk: pd.DataFrame) -> pd.DataFrame:
    chunk = _normalize_strings(chunk)
    chunk = _normalize_dates(chunk)

    prepared = pd.DataFrame(
        {
            "cnpj_basico": chunk["cnpj_basico"],
            "nome_socio": chunk["nome"],
            "cpf_cnpj_socio": chunk["cpf_cnpj"],
            "qualificacao": chunk["qualificacao"],
            "pais": chunk["pais"],
            "data_entrada": chunk["data_entrada"],
        }
    )
    prepared = prepared[prepared["cnpj_basico"].notna()]
    return prepared


def _ensure_staging_table(engine: Engine) -> None:
    sql = f"""
        CREATE TABLE IF NOT EXISTS {quote_ident(STAGING_TABLE)} (
            cnpj_basico VARCHAR(8),
            nome_socio TEXT,
            cpf_cnpj_socio TEXT,
            qualificacao TEXT,
            pais TEXT,
            data_entrada DATE
        )
    """
    with engine.begin() as connection:
        connection.execute(text(sql))


def process_socios_csv(
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
            conflict_columns=["cnpj_basico", "nome_socio", "cpf_cnpj_socio"],
        )
        processed += len(prepared)

    return processed
