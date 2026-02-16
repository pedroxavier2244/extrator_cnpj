from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Estabelecimento(Base):
    __tablename__ = "estabelecimentos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    cnpj_completo: Mapped[str] = mapped_column(String(14), unique=True, nullable=False)
    cnpj_basico: Mapped[str] = mapped_column(ForeignKey("empresas.cnpj_basico"), nullable=False, index=True)
    nome_fantasia: Mapped[str | None] = mapped_column(String, nullable=True)
    situacao: Mapped[str | None] = mapped_column(String, nullable=True)
    uf: Mapped[str | None] = mapped_column(String(2), nullable=True)
    municipio: Mapped[str | None] = mapped_column(String, nullable=True)
    cnae_principal: Mapped[str | None] = mapped_column(String, nullable=True)
    cnae_secundario: Mapped[str | None] = mapped_column(String, nullable=True)
    pais: Mapped[str | None] = mapped_column(String, nullable=True)
    motivo: Mapped[str | None] = mapped_column(String, nullable=True)
