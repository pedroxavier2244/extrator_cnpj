from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.api_responses import EmpresasSearchResponse
from app.schemas.empresa import EmpresaSchema

router = APIRouter(prefix="/empresas", tags=["empresas"])


@router.get("/search", response_model=EmpresasSearchResponse)
def search_empresas(
    q: str = Query(..., min_length=1),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
) -> EmpresasSearchResponse:
    sql = text(
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
        """
    )

    rows = db.execute(sql, {"q": q, "limit": limit}).mappings().all()
    resultados = [EmpresaSchema(**dict(row)) for row in rows]
    return EmpresasSearchResponse(resultados=resultados)
