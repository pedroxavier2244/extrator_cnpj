from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Cnae(Base):
    __tablename__ = "cnaes"

    codigo: Mapped[str] = mapped_column(String, primary_key=True)
    descricao: Mapped[str] = mapped_column(String, nullable=False)
