from __future__ import annotations

from pydantic import BaseModel

from app.schemas.empresa import EmpresaSchema
from app.schemas.estabelecimento import EstabelecimentoSchema
from app.schemas.socio import SocioSchema


class HealthResponse(BaseModel):
    status: str


class CNPJResponse(BaseModel):
    empresa: EmpresaSchema | None = None
    estabelecimentos: list[EstabelecimentoSchema] = []
    socios: list[SocioSchema] = []


class EmpresasSearchResponse(BaseModel):
    resultados: list[EmpresaSchema]
