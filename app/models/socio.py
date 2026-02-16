from datetime import date

from sqlalchemy import Date, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Socio(Base):
    __tablename__ = "socios"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    cnpj_basico: Mapped[str] = mapped_column(ForeignKey("empresas.cnpj_basico"), nullable=False, index=True)
    nome_socio: Mapped[str | None] = mapped_column(String, nullable=True)
    cpf_cnpj_socio: Mapped[str | None] = mapped_column(String, nullable=True)
    qualificacao: Mapped[str | None] = mapped_column(String, nullable=True)
    pais: Mapped[str | None] = mapped_column(String, nullable=True)
    data_entrada: Mapped[date | None] = mapped_column(Date, nullable=True)
