from __future__ import annotations

import re
from collections import defaultdict
from typing import Any

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import settings
from app.core.cache import get_cache
from app.core.exceptions import NotFoundError, ValidationError
from app.core.logging import get_logger
from app.database import get_db
from app.middleware.rate_limit import limiter
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


@router.get(
    "/{cnpj}",
    response_model=CNPJResponse,
    summary="Consultar CNPJ",
    description=(
        "Retorna dados completos de empresa, estabelecimentos e socios. "
        "Aceita CNPJ com 8 digitos (raiz) ou 14 digitos (completo)."
    ),
)
@limiter.limit("60/minute")
def get_cnpj(
    request: Request,
    cnpj: str,
    response: Response,
    db: Session = Depends(get_db),
) -> CNPJResponse:
    response.headers["Cache-Control"] = "private, max-age=3600"

    cnpj_digits = _only_digits(cnpj)
    if len(cnpj_digits) not in (8, 14):
        raise ValidationError("CNPJ deve ter 8 ou 14 digitos")

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
        raise NotFoundError("CNPJ nao encontrado")

    return CNPJResponse(
        empresa=empresa,
        estabelecimentos=estabelecimentos,
        socios=socios,
    )


@router.post(
    "/batch",
    response_model=BatchCNPJResponse,
    summary="Consultar CNPJs em lote",
    description="Retorna resultados para ate 1000 CNPJs em uma unica chamada.",
)
@limiter.limit("10/minute")
def get_cnpj_batch(
    request: Request,
    payload: BatchCNPJRequest,
    response: Response,
    db: Session = Depends(get_db),
) -> BatchCNPJResponse:
    response.headers["Cache-Control"] = "private, max-age=3600"

    total = len(payload.cnpjs)
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

    for original in payload.cnpjs:
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
        payload_item = cache_hits_raw.get(key)
        if payload_item is None:
            continue
        try:
            found_by_basico[basico] = CNPJResponse.model_validate(cache.deserialize(payload_item))
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
        db.execute(text("CREATE TEMP TABLE IF NOT EXISTS _lookup_cnpj (cnpj_basico TEXT NOT NULL)"))
        db.execute(text("TRUNCATE _lookup_cnpj"))
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
            response_item = _cnpj_response_from_rows(
                empresa_by_basico.get(basico),
                estabelecimentos_by_basico.get(basico, []),
                socios_by_basico.get(basico, []),
            )
            if response_item.empresa is None and not response_item.estabelecimentos and not response_item.socios:
                continue
            found_by_basico[basico] = response_item
            cache_to_set[cache.key(basico)] = cache.serialize(response_item.model_dump(mode="json"))

        cache.set_many(cache_to_set, settings.CACHE_TTL_SECONDS)

    resultados: dict[str, CNPJResponse] = {}
    for original in payload.cnpjs:
        basico = basico_by_input.get(original)
        if basico is None:
            continue
        batch_response = found_by_basico.get(basico)
        if batch_response is None:
            nao_encontrados.append(original)
            continue
        resultados[original] = batch_response

    return BatchCNPJResponse(
        resultados=resultados,
        nao_encontrados=nao_encontrados,
        total=total,
        encontrados=len(resultados),
    )
