from __future__ import annotations

from pydantic import BaseModel


class EstabelecimentoSchema(BaseModel):
    id: int
    cnpj_completo: str
    cnpj_basico: str
    nome_fantasia: str | None = None
    situacao: str | None = None
    uf: str | None = None
    municipio: str | None = None
    municipio_descricao: str | None = None
    cnae_principal: str | None = None
    cnae_principal_descricao: str | None = None
    cnae_secundario: str | None = None
    pais: str | None = None
    pais_descricao: str | None = None
    motivo: str | None = None
    motivo_descricao: str | None = None

    class Config:
        from_attributes = True
