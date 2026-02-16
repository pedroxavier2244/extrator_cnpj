from datetime import date

from sqlalchemy import Date, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Simples(Base):
    __tablename__ = "simples"

    cnpj_basico: Mapped[str] = mapped_column(String(8), primary_key=True)
    opcao_pelo_simples: Mapped[str | None] = mapped_column(String(1), nullable=True)
    data_opcao_pelo_simples: Mapped[date | None] = mapped_column(Date, nullable=True)
    data_exclusao_do_simples: Mapped[date | None] = mapped_column(Date, nullable=True)
    opcao_pelo_mei: Mapped[str | None] = mapped_column(String(1), nullable=True)
    data_opcao_pelo_mei: Mapped[date | None] = mapped_column(Date, nullable=True)
    data_exclusao_do_mei: Mapped[date | None] = mapped_column(Date, nullable=True)
