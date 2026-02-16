from __future__ import annotations

import math

from fastapi import APIRouter, Depends, Query, Request, Response
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.database import get_db
from app.middleware.rate_limit import limiter
from app.schemas.api_responses import EmpresasSearchResponse
from app.schemas.empresa import EmpresaSchema

router = APIRouter(prefix="/empresas", tags=["empresas"])


@router.get(
    "/search",
    response_model=EmpresasSearchResponse,
    summary="Buscar empresas",
    description="Busca empresas por razao social usando full-text search com paginacao.",
)
@limiter.limit("30/minute")
def search_empresas(
    request: Request,
    response: Response,
    q: str = Query(..., min_length=1, max_length=200, description="Termo de busca"),
    page: int = Query(1, ge=1, description="Pagina atual"),
    page_size: int = Query(20, ge=1, le=100, description="Quantidade de itens por pagina"),
    db: Session = Depends(get_db),
) -> EmpresasSearchResponse:
    response.headers["Cache-Control"] = "public, max-age=300"

    offset = (page - 1) * page_size

    count_sql = text(
        """
        SELECT COUNT(*) AS total
        FROM empresas e
        WHERE to_tsvector('portuguese', coalesce(e.razao_social, ''))
              @@ plainto_tsquery('portuguese', :q)
        """
    )

    data_sql = text(
        """
        SELECT
            e.cnpj_basico,
            e.razao_social,
            e.natureza_juridica,
            e.capital_social,
            e.porte_empresa,
            ts_rank(
                to_tsvector('portuguese', coalesce(e.razao_social, '')),
                plainto_tsquery('portuguese', :q)
            ) AS relevancia
        FROM empresas e
        WHERE to_tsvector('portuguese', coalesce(e.razao_social, ''))
              @@ plainto_tsquery('portuguese', :q)
        ORDER BY relevancia DESC, e.razao_social ASC
        LIMIT :limit
        OFFSET :offset
        """
    )

    total = int(db.execute(count_sql, {"q": q}).scalar() or 0)
    rows = db.execute(data_sql, {"q": q, "limit": page_size, "offset": offset}).mappings().all()
    resultados = [EmpresaSchema(**dict(row)) for row in rows]

    pages = math.ceil(total / page_size) if total > 0 else 0

    return EmpresasSearchResponse(
        resultados=resultados,
        total=total,
        page=page,
        page_size=page_size,
        pages=pages,
    )
