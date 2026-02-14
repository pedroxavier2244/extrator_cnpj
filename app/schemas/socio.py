from __future__ import annotations

from datetime import date

from pydantic import BaseModel


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

    class Config:
        from_attributes = True
