from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Empresa(Base):
    __tablename__ = "empresas"

    cnpj_basico: Mapped[str] = mapped_column(String(8), primary_key=True)
    razao_social: Mapped[str | None] = mapped_column(String, nullable=True)
    natureza_juridica: Mapped[str | None] = mapped_column(String, nullable=True)
    capital_social: Mapped[str | None] = mapped_column(String, nullable=True)
    porte_empresa: Mapped[str | None] = mapped_column(String, nullable=True)
