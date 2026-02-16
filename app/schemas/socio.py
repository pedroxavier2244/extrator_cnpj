from __future__ import annotations

from datetime import date

from pydantic import BaseModel, ConfigDict, field_validator


class SocioSchema(BaseModel):
    id: int
    cnpj_basico: str
    nome_socio: str | None = None
    cpf_cnpj_socio: str | None = None
    qualificacao: str | None = None
    qualificacao_descricao: str | None = None
    pais: str | None = None
    pais_descricao: str | None = None
    data_entrada: date | None = None

    @field_validator("cpf_cnpj_socio", mode="before")
    @classmethod
    def mask_cpf(cls, v):
        if v and len(str(v)) == 11:
            v = str(v)
            return f"{v[:3]}******{v[9:]}"
        return v

    model_config = ConfigDict(from_attributes=True)
