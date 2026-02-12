from __future__ import annotations

from pathlib import Path

from sqlalchemy import Engine

from app.database import engine as default_engine
from etl.processors.reference_processor import process_reference_csv


def process_naturezas_csv(file_path: str | Path, engine: Engine = default_engine) -> int:
    return process_reference_csv(file_path, target_table="naturezas", staging_table="stg_naturezas", engine=engine)
