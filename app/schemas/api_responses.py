from __future__ import annotations

from pydantic import BaseModel

from app.config import settings
from app.schemas.empresa import EmpresaSchema
from app.schemas.estabelecimento import EstabelecimentoSchema
from app.schemas.socio import SocioSchema

try:
    from pydantic import field_validator
    IS_PYDANTIC_V2 = True
except ImportError:  # pydantic v1 fallback
    from pydantic import validator as field_validator
    IS_PYDANTIC_V2 = False


class HealthResponse(BaseModel):
    status: str


class CNPJResponse(BaseModel):
    empresa: EmpresaSchema | None = None
    estabelecimentos: list[EstabelecimentoSchema] = []
    socios: list[SocioSchema] = []


class EmpresasSearchResponse(BaseModel):
    resultados: list[EmpresaSchema]


class BatchCNPJRequest(BaseModel):
    cnpjs: list[str]

    if IS_PYDANTIC_V2:
        @field_validator("cnpjs")
        @classmethod
        def validate_size(cls, v: list[str]) -> list[str]:
            if len(v) > settings.BATCH_MAX_SIZE:
                raise ValueError(f"Maximo de {settings.BATCH_MAX_SIZE} CNPJs por request")
            return v
    else:
        @field_validator("cnpjs")
        def validate_size(cls, v: list[str]) -> list[str]:
            if len(v) > settings.BATCH_MAX_SIZE:
                raise ValueError(f"Maximo de {settings.BATCH_MAX_SIZE} CNPJs por request")
            return v


class BatchCNPJResponse(BaseModel):
    resultados: dict[str, CNPJResponse]
    nao_encontrados: list[str]
    total: int
    encontrados: int
