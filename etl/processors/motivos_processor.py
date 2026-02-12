from __future__ import annotations

from pathlib import Path

from sqlalchemy import Engine

from app.database import engine as default_engine
from etl.processors.reference_processor import process_reference_csv


def process_motivos_csv(file_path: str | Path, engine: Engine = default_engine) -> int:
    return process_reference_csv(file_path, target_table="motivos", staging_table="stg_motivos", engine=engine)
