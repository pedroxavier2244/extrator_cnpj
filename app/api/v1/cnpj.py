from __future__ import annotations

import re

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.api_responses import CNPJResponse
from app.schemas.empresa import EmpresaSchema
from app.schemas.estabelecimento import EstabelecimentoSchema
from app.schemas.socio import SocioSchema

router = APIRouter(prefix="/cnpj", tags=["cnpj"])


def _only_digits(value: str) -> str:
    return re.sub(r"\D", "", value)


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
            p.descricao AS pais_descricao
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
