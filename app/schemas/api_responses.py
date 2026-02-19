from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.config import settings
from app.schemas.empresa import EmpresaSchema, EmpresaSearchResultSchema
from app.schemas.estabelecimento import EstabelecimentoSchema
from app.schemas.socio import SocioSchema


class ErrorDetail(BaseModel):
    code: str
    message: str
    request_id: str | None = None


class ErrorResponse(BaseModel):
    error: ErrorDetail


class HealthResponse(BaseModel):
    status: str
    database: str
    cache: str
    version: str
    uptime_seconds: float


class CNPJResponse(BaseModel):
    empresa: EmpresaSchema | None = None
    estabelecimentos: list[EstabelecimentoSchema] = Field(default_factory=list)
    socios: list[SocioSchema] = Field(default_factory=list)


class EmpresasSearchResponse(BaseModel):
    resultados: list[EmpresaSearchResultSchema] = Field(default_factory=list)
    total: int
    page: int
    page_size: int
    pages: int


class BatchCNPJRequest(BaseModel):
    cnpjs: list[str] = Field(
        description="Lista de CNPJs com 8 ou 14 digitos. Maximo 1000 por request.",
        examples=[["00000000000100", "11111111000191"]],
    )

    model_config = ConfigDict(extra="forbid")

    @field_validator("cnpjs")
    @classmethod
    def validate_size(cls, value: list[str]) -> list[str]:
        if len(value) > settings.BATCH_MAX_SIZE:
            raise ValueError(f"Maximo de {settings.BATCH_MAX_SIZE} CNPJs por request")
        return value


class BatchCNPJResponse(BaseModel):
    resultados: dict[str, CNPJResponse]
    nao_encontrados: list[str]
    total: int
    encontrados: int
