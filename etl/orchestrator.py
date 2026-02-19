from __future__ import annotations

import argparse
import shutil
import zipfile
from pathlib import Path

from sqlalchemy import text

from app.config import settings
from app.core.logging import get_logger
from app.database import SessionLocal, engine
from etl.processors.cnaes_processor import process_cnaes_csv
from etl.processors.empresas_processor import process_empresas_csv
from etl.processors.estabelecimentos_processor import process_estabelecimentos_csv
from etl.processors.motivos_processor import process_motivos_csv
from etl.processors.municipios_processor import process_municipios_csv
from etl.processors.naturezas_processor import process_naturezas_csv
from etl.processors.paises_processor import process_paises_csv
from etl.processors.qualificacoes_processor import process_qualificacoes_csv
from etl.processors.simples_processor import process_simples_csv
from etl.processors.socios_processor import process_socios_csv
from etl.utils.file_hash import calculate_file_hash

logger = get_logger(__name__)

REQUIRED_AUXILIARY_TYPES = {
    "cnaes",
    "motivos",
    "municipios",
    "naturezas",
    "paises",
    "qualificacoes",
    "simples",
}


def _ensure_directories() -> None:
    Path(settings.RAW_DATA_PATH).mkdir(parents=True, exist_ok=True)
    Path(settings.STAGING_PATH).mkdir(parents=True, exist_ok=True)
    Path(settings.PROCESSED_PATH).mkdir(parents=True, exist_ok=True)


def _already_processed(file_hash: str) -> bool:
    query = text(
        """
        SELECT 1
        FROM importacoes
        WHERE hash_arquivo = :hash_arquivo
          AND status = 'SUCCESS'
          AND (
                COALESCE(registros_processados, 0) > 0
                OR COALESCE(registros_inseridos, 0) > 0
              )
        LIMIT 1
        """
    )
    with engine.begin() as connection:
        row = connection.execute(query, {"hash_arquivo": file_hash}).first()
    return row is not None


def _create_importacao(nome_arquivo: str, hash_arquivo: str, status: str) -> int:
    query = text(
        """
        INSERT INTO importacoes (
            nome_arquivo,
            hash_arquivo,
            status,
            registros_processados,
            registros_inseridos
        )
        VALUES (:nome_arquivo, :hash_arquivo, :status, 0, 0)
        RETURNING id
        """
    )
    with SessionLocal() as db:
        importacao_id = db.execute(
            query,
            {"nome_arquivo": nome_arquivo, "hash_arquivo": hash_arquivo, "status": status},
        ).scalar_one()
        db.commit()

    return int(importacao_id)


def _update_importacao(
    importacao_id: int,
    status: str,
    registros_processados: int,
    registros_inseridos: int | None = None,
) -> None:
    query = text(
        """
        UPDATE importacoes
        SET status = :status,
            registros_processados = :registros_processados,
            registros_inseridos = :registros_inseridos
        WHERE id = :id
        """
    )
    params = {
        "id": importacao_id,
        "status": status,
        "registros_processados": registros_processados,
        "registros_inseridos": registros_inseridos if registros_inseridos is not None else registros_processados,
    }
    with SessionLocal() as db:
        db.execute(query, params)
        db.commit()


def _classify_name(file_name: str) -> str | None:
    upper = Path(file_name).name.upper()

    if "EMPRE" in upper:
        return "empresas"
    if "ESTABELE" in upper:
        return "estabelecimentos"
    if "SOCIO" in upper:
        return "socios"
    if "CNAE" in upper:
        return "cnaes"
    if "MOTI" in upper:
        return "motivos"
    if "MUNIC" in upper:
        return "municipios"
    if "NATJU" in upper:
        return "naturezas"
    if "PAIS" in upper:
        return "paises"
    if "QUALS" in upper:
        return "qualificacoes"
    if "SIMPLES" in upper:
        return "simples"

    return None


def _extract_classified_files(zip_path: Path) -> dict[str, list[Path]]:
    destination_dir = Path(settings.STAGING_PATH) / zip_path.stem
    destination_dir.mkdir(parents=True, exist_ok=True)

    extracted: dict[str, list[Path]] = {
        "empresas": [],
        "estabelecimentos": [],
        "socios": [],
        "cnaes": [],
        "motivos": [],
        "municipios": [],
        "naturezas": [],
        "paises": [],
        "qualificacoes": [],
        "simples": [],
    }

    with zipfile.ZipFile(zip_path, "r") as archive:
        for member in archive.infolist():
            if member.is_dir():
                continue

            member_name = Path(member.filename).name
            if member_name.upper().endswith(".ZIP"):
                outer_stem = Path(member.filename).stem
                nested_zip_path = destination_dir / f"{outer_stem}.zip"
                with archive.open(member, "r") as src, open(nested_zip_path, "wb") as dst:
                    shutil.copyfileobj(src, dst)

                try:
                    with zipfile.ZipFile(nested_zip_path, "r") as nested:
                        for inner in nested.infolist():
                            if inner.is_dir():
                                continue

                            file_type = _classify_name(inner.filename)
                            if file_type is None:
                                continue

                            inner_name = Path(inner.filename).name
                            target_path = destination_dir / outer_stem / inner_name
                            target_path.parent.mkdir(parents=True, exist_ok=True)
                            with nested.open(inner, "r") as src, open(target_path, "wb") as dst:
                                shutil.copyfileobj(src, dst)
                            extracted[file_type].append(target_path)
                finally:
                    nested_zip_path.unlink(missing_ok=True)
                continue

            file_type = _classify_name(member_name)
            if file_type is None:
                continue

            extracted_path = Path(archive.extract(member, path=destination_dir))
            extracted[file_type].append(extracted_path)

    return extracted


def _move_to_processed(zip_path: Path) -> None:
    destination = Path(settings.PROCESSED_PATH) / zip_path.name
    if destination.exists():
        destination.unlink()
    shutil.move(str(zip_path), str(destination))


def process_zip_file(zip_path: Path, force: bool = False) -> int:
    file_hash = calculate_file_hash(zip_path, algorithm=settings.ETL_HASH_ALGORITHM)

    if not force and _already_processed(file_hash):
        logger.info(
            "etl.arquivo_ignorado",
            arquivo=zip_path.name,
            motivo="hash_ja_processado",
        )
        _move_to_processed(zip_path)
        return 0

    importacao_id = _create_importacao(zip_path.name, file_hash, "PROCESSING")

    try:
        extracted = _extract_classified_files(zip_path)
        all_found = sum(len(paths) for paths in extracted.values())
        if all_found == 0:
            _update_importacao(importacao_id, "FAILED", 0, 0)
            raise RuntimeError("Nenhum CSV encontrado (zip aninhado?)")

        total_processed = 0

        for file_path in extracted["empresas"]:
            total_processed += process_empresas_csv(file_path)
        for file_path in extracted["estabelecimentos"]:
            total_processed += process_estabelecimentos_csv(file_path)
        for file_path in extracted["socios"]:
            total_processed += process_socios_csv(file_path)

        for file_path in extracted["cnaes"]:
            total_processed += process_cnaes_csv(file_path)
        for file_path in extracted["motivos"]:
            total_processed += process_motivos_csv(file_path)
        for file_path in extracted["municipios"]:
            total_processed += process_municipios_csv(file_path)
        for file_path in extracted["naturezas"]:
            total_processed += process_naturezas_csv(file_path)
        for file_path in extracted["paises"]:
            total_processed += process_paises_csv(file_path)
        for file_path in extracted["qualificacoes"]:
            total_processed += process_qualificacoes_csv(file_path)
        for file_path in extracted["simples"]:
            total_processed += process_simples_csv(file_path)

        if total_processed <= 0:
            _update_importacao(importacao_id, "FAILED", 0, 0)
            raise RuntimeError("Nenhum registro processado")

        missing_aux = sorted(aux for aux in REQUIRED_AUXILIARY_TYPES if not extracted[aux])
        if missing_aux:
            logger.warning(
                "tipos auxiliares ausentes no arquivo",
                arquivo=zip_path.name,
                tipos=missing_aux,
            )
            _update_importacao(importacao_id, "PARTIAL", total_processed, total_processed)
            _move_to_processed(zip_path)
            return total_processed

        _update_importacao(importacao_id, "SUCCESS", total_processed, total_processed)
        _move_to_processed(zip_path)
        return total_processed
    except Exception:
        try:
            _update_importacao(importacao_id, "FAILED", 0, 0)
        except Exception:
            logger.exception(
                "Falha ao atualizar status de importação para FAILED",
                importacao_id=importacao_id,
            )
        raise


def run(force: bool = False) -> int:
    _ensure_directories()

    total = 0
    raw_dir = Path(settings.RAW_DATA_PATH)

    for zip_path in sorted(raw_dir.glob("*.zip")):
        try:
            total += process_zip_file(zip_path, force=force)
        except Exception:
            logger.exception(
                "Erro ao processar arquivo, continuando com os demais",
                arquivo=str(zip_path),
            )

    return total


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="ETL orchestrator")
    parser.add_argument("--force", action="store_true", help="ignora bloqueio por hash")
    args = parser.parse_args()
    print(run(force=args.force))
