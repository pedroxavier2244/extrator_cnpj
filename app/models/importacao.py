from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Importacao(Base):
    __tablename__ = "importacoes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    nome_arquivo: Mapped[str | None] = mapped_column(String, nullable=True)
    hash_arquivo: Mapped[str | None] = mapped_column(String, nullable=True)
    status: Mapped[str | None] = mapped_column(String, nullable=True)
    registros_processados: Mapped[int | None] = mapped_column(Integer, nullable=True)
    registros_inseridos: Mapped[int | None] = mapped_column(Integer, nullable=True)
