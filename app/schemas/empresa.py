from __future__ import annotations

from datetime import date

from pydantic import BaseModel, ConfigDict


class EmpresaSchema(BaseModel):
    cnpj_basico: str
    razao_social: str | None = None
    natureza_juridica: str | None = None
    natureza_juridica_descricao: str | None = None
    capital_social: str | None = None
    porte_empresa: str | None = None
    opcao_pelo_simples: str | None = None
    data_opcao_pelo_simples: date | None = None
    data_exclusao_do_simples: date | None = None
    opcao_pelo_mei: str | None = None
    data_opcao_pelo_mei: date | None = None
    data_exclusao_do_mei: date | None = None

    model_config = ConfigDict(from_attributes=True)


class EmpresaSearchResultSchema(BaseModel):
    cnpj_basico: str
    razao_social: str | None = None
    natureza_juridica: str | None = None
    capital_social: str | None = None
    porte_empresa: str | None = None
    relevancia: float | None = None

    model_config = ConfigDict(from_attributes=True)
