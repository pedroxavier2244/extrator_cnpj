from __future__ import annotations

import re
import json
from collections import defaultdict
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import settings
from app.core.cache import get_cache
from app.core.logging import get_logger
from app.database import get_db
from app.schemas.api_responses import BatchCNPJRequest, BatchCNPJResponse, CNPJResponse
from app.schemas.empresa import EmpresaSchema
from app.schemas.estabelecimento import EstabelecimentoSchema
from app.schemas.socio import SocioSchema

logger = get_logger(__name__)

router = APIRouter(prefix="/cnpj", tags=["cnpj"])


def _only_digits(value: str) -> str:
    return re.sub(r"\D", "", value)


def _cnpj_response_from_rows(
    empresa_row: dict[str, Any] | None,
    estabelecimento_rows: list[dict[str, Any]],
    socio_rows: list[dict[str, Any]],
) -> CNPJResponse:
    empresa = EmpresaSchema(**empresa_row) if empresa_row else None
    estabelecimentos = [EstabelecimentoSchema(**row) for row in estabelecimento_rows]
    socios = [SocioSchema(**row) for row in socio_rows]
    return CNPJResponse(
        empresa=empresa,
        estabelecimentos=estabelecimentos,
        socios=socios,
    )


def _model_dump(model: Any) -> dict[str, Any]:
    if hasattr(model, "model_dump"):
        return model.model_dump(mode="json")
    return json.loads(model.json())


def _model_validate_cnpj_response(data: dict[str, Any]) -> CNPJResponse:
    if hasattr(CNPJResponse, "model_validate"):
        return CNPJResponse.model_validate(data)
    return CNPJResponse.parse_obj(data)


@router.get("/{cnpj}", response_model=CNPJResponse)
def get_cnpj(cnpj: str, db: Session = Depends(get_db)) -> CNPJResponse:
    cnpj_digits = _only_digits(cnpj)

    if len(cnpj_digits) not in (8, 14):
        raise HTTPException(status_code=400, detail="CNPJ deve ter 8 ou 14 digitos")

    cnpj_basico = cnpj_digits[:8]

    empresa_sql = text(
        """
        SELECT
            e.cnpj_basico,
            e.razao_social,
            e.natureza_juridica,
            n.descricao AS natureza_juridica_descricao,
            e.capital_social,
            e.porte_empresa,
            s.opcao_pelo_simples,
            s.data_opcao_pelo_simples,
            s.data_exclusao_do_simples,
            s.opcao_pelo_mei,
            s.data_opcao_pelo_mei,
            s.data_exclusao_do_mei
        FROM empresas e
        LEFT JOIN naturezas n ON n.codigo = e.natureza_juridica
        LEFT JOIN simples s ON s.cnpj_basico = e.cnpj_basico
        WHERE e.cnpj_basico = :cnpj_basico
        """
    )

    estabelecimentos_base_sql = """
        SELECT
            est.id,
            est.cnpj_completo,
            est.cnpj_basico,
            est.nome_fantasia,
            est.situacao,
            est.uf,
            est.municipio,
            m.descricao AS municipio_descricao,
            est.cnae_principal,
            c.descricao AS cnae_principal_descricao,
            est.cnae_secundario,
            est.pais,
            p.descricao AS pais_descricao,
            est.motivo,
            mot.descricao AS motivo_descricao
        FROM estabelecimentos est
        LEFT JOIN municipios m ON m.codigo = est.municipio
        LEFT JOIN cnaes c ON c.codigo = est.cnae_principal
        LEFT JOIN paises p ON p.codigo = est.pais
        LEFT JOIN motivos mot ON mot.codigo = est.motivo
    """

    if len(cnpj_digits) == 14:
        estabelecimentos_sql = text(
            estabelecimentos_base_sql
            + """
            WHERE est.cnpj_completo = :cnpj_completo
            ORDER BY est.cnpj_completo
            """
        )
    else:
        estabelecimentos_sql = text(
            estabelecimentos_base_sql
            + """
            WHERE est.cnpj_basico = :cnpj_basico
            ORDER BY est.cnpj_completo
            """
        )

    socios_sql = text(
        """
        SELECT
            s.id,
            s.cnpj_basico,
            s.nome_socio,
            s.cpf_cnpj_socio,
            s.qualificacao,
            q.descricao AS qualificacao_descricao,
            s.pais,
            p.descricao AS pais_descricao,
            s.data_entrada
        FROM socios s
        LEFT JOIN qualificacoes q ON q.codigo = s.qualificacao
        LEFT JOIN paises p ON p.codigo = s.pais
        WHERE s.cnpj_basico = :cnpj_basico
        ORDER BY s.id
        """
    )

    empresa_row = db.execute(empresa_sql, {"cnpj_basico": cnpj_basico}).mappings().first()

    if len(cnpj_digits) == 14:
        estabelecimento_rows = db.execute(
            estabelecimentos_sql,
            {"cnpj_completo": cnpj_digits},
        ).mappings().all()
    else:
        estabelecimento_rows = db.execute(
            estabelecimentos_sql,
            {"cnpj_basico": cnpj_basico},
        ).mappings().all()

    socio_rows = db.execute(socios_sql, {"cnpj_basico": cnpj_basico}).mappings().all()

    empresa = EmpresaSchema(**dict(empresa_row)) if empresa_row else None
    estabelecimentos = [EstabelecimentoSchema(**dict(row)) for row in estabelecimento_rows]
    socios = [SocioSchema(**dict(row)) for row in socio_rows]

    if empresa is None and not estabelecimentos and not socios:
        raise HTTPException(status_code=404, detail="CNPJ nao encontrado")

    return CNPJResponse(
        empresa=empresa,
        estabelecimentos=estabelecimentos,
        socios=socios,
    )


@router.post("/batch", response_model=BatchCNPJResponse)
def get_cnpj_batch(
    request: BatchCNPJRequest,
    db: Session = Depends(get_db),
) -> BatchCNPJResponse:
    total = len(request.cnpjs)
    if total == 0:
        return BatchCNPJResponse(
            resultados={},
            nao_encontrados=[],
            total=0,
            encontrados=0,
        )

    normalized_by_input: dict[str, str] = {}
    basico_by_input: dict[str, str] = {}
    nao_encontrados: list[str] = []

    for original in request.cnpjs:
        normalized = _only_digits(original)
        if len(normalized) not in (8, 14):
            nao_encontrados.append(original)
            continue
        normalized_by_input[original] = normalized
        basico_by_input[original] = normalized[:8]

    unique_basicos = sorted(set(basico_by_input.values()))

    cache = get_cache()
    cache_keys = {basico: cache.key(basico) for basico in unique_basicos}
    cache_hits_raw = cache.get_many(list(cache_keys.values()))

    found_by_basico: dict[str, CNPJResponse] = {}
    for basico, key in cache_keys.items():
        payload = cache_hits_raw.get(key)
        if payload is None:
            continue
        try:
            found_by_basico[basico] = _model_validate_cnpj_response(cache.deserialize(payload))
        except Exception:
            logger.exception("batch.cache_deserialize_failed", cnpj_basico=basico)

    missed_basicos = [basico for basico in unique_basicos if basico not in found_by_basico]

    logger.info(
        "batch.lookup_start",
        total=total,
        valid=len(normalized_by_input),
        cache_hits=len(found_by_basico),
        db_misses=len(missed_basicos),
    )

    if missed_basicos:
        db.execute(text("CREATE TEMP TABLE _lookup_cnpj (cnpj_basico VARCHAR(8)) ON COMMIT DROP"))
        db.execute(
            text("INSERT INTO _lookup_cnpj (cnpj_basico) VALUES (:cnpj_basico)"),
            [{"cnpj_basico": basico} for basico in missed_basicos],
        )

        empresa_sql = text(
            """
            SELECT
                e.cnpj_basico,
                e.razao_social,
                e.natureza_juridica,
                n.descricao AS natureza_juridica_descricao,
                e.capital_social,
                e.porte_empresa,
                s.opcao_pelo_simples,
                s.data_opcao_pelo_simples,
                s.data_exclusao_do_simples,
                s.opcao_pelo_mei,
                s.data_opcao_pelo_mei,
                s.data_exclusao_do_mei
            FROM empresas e
            LEFT JOIN naturezas n ON n.codigo = e.natureza_juridica
            LEFT JOIN simples s ON s.cnpj_basico = e.cnpj_basico
            JOIN _lookup_cnpj l ON l.cnpj_basico = e.cnpj_basico
            """
        )
        estabelecimentos_sql = text(
            """
            SELECT
                est.id,
                est.cnpj_completo,
                est.cnpj_basico,
                est.nome_fantasia,
                est.situacao,
                est.uf,
                est.municipio,
                m.descricao AS municipio_descricao,
                est.cnae_principal,
                c.descricao AS cnae_principal_descricao,
                est.cnae_secundario,
                est.pais,
                p.descricao AS pais_descricao,
                est.motivo,
                mot.descricao AS motivo_descricao
            FROM estabelecimentos est
            LEFT JOIN municipios m ON m.codigo = est.municipio
            LEFT JOIN cnaes c ON c.codigo = est.cnae_principal
            LEFT JOIN paises p ON p.codigo = est.pais
            LEFT JOIN motivos mot ON mot.codigo = est.motivo
            JOIN _lookup_cnpj l ON l.cnpj_basico = est.cnpj_basico
            ORDER BY est.cnpj_completo
            """
        )
        socios_sql = text(
            """
            SELECT
                s.id,
                s.cnpj_basico,
                s.nome_socio,
                s.cpf_cnpj_socio,
                s.qualificacao,
                q.descricao AS qualificacao_descricao,
                s.pais,
                p.descricao AS pais_descricao,
                s.data_entrada
            FROM socios s
            LEFT JOIN qualificacoes q ON q.codigo = s.qualificacao
            LEFT JOIN paises p ON p.codigo = s.pais
            JOIN _lookup_cnpj l ON l.cnpj_basico = s.cnpj_basico
            ORDER BY s.id
            """
        )

        empresa_rows = [dict(row) for row in db.execute(empresa_sql).mappings().all()]
        estabelecimento_rows = [dict(row) for row in db.execute(estabelecimentos_sql).mappings().all()]
        socio_rows = [dict(row) for row in db.execute(socios_sql).mappings().all()]

        empresa_by_basico: dict[str, dict[str, Any]] = {}
        for row in empresa_rows:
            empresa_by_basico[row["cnpj_basico"]] = row

        estabelecimentos_by_basico: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in estabelecimento_rows:
            estabelecimentos_by_basico[row["cnpj_basico"]].append(row)

        socios_by_basico: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in socio_rows:
            socios_by_basico[row["cnpj_basico"]].append(row)

        cache_to_set: dict[str, str] = {}
        for basico in missed_basicos:
            response = _cnpj_response_from_rows(
                empresa_by_basico.get(basico),
                estabelecimentos_by_basico.get(basico, []),
                socios_by_basico.get(basico, []),
            )
            if response.empresa is None and not response.estabelecimentos and not response.socios:
                continue
            found_by_basico[basico] = response
            cache_to_set[cache.key(basico)] = cache.serialize(_model_dump(response))

        cache.set_many(cache_to_set, settings.CACHE_TTL_SECONDS)

    resultados: dict[str, CNPJResponse] = {}
    for original in request.cnpjs:
        basico = basico_by_input.get(original)
        if basico is None:
            continue
        response = found_by_basico.get(basico)
        if response is None:
            nao_encontrados.append(original)
            continue
        resultados[original] = response

    return BatchCNPJResponse(
        resultados=resultados,
        nao_encontrados=nao_encontrados,
        total=total,
        encontrados=len(resultados),
    )
