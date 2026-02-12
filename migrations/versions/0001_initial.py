"""initial schema

Revision ID: 0001_initial
Revises:
Create Date: 2026-02-11 00:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "empresas",
        sa.Column("cnpj_basico", sa.String(length=8), primary_key=True, nullable=False),
        sa.Column("razao_social", sa.String(), nullable=True),
        sa.Column("natureza_juridica", sa.String(), nullable=True),
        sa.Column("capital_social", sa.String(), nullable=True),
        sa.Column("porte_empresa", sa.String(), nullable=True),
    )

    op.create_table(
        "estabelecimentos",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
        sa.Column("cnpj_completo", sa.String(length=14), nullable=False),
        sa.Column("cnpj_basico", sa.String(length=8), nullable=False),
        sa.Column("nome_fantasia", sa.String(), nullable=True),
        sa.Column("situacao", sa.String(), nullable=True),
        sa.Column("uf", sa.String(length=2), nullable=True),
        sa.Column("municipio", sa.String(), nullable=True),
        sa.ForeignKeyConstraint(["cnpj_basico"], ["empresas.cnpj_basico"]),
        sa.UniqueConstraint("cnpj_completo"),
    )

    op.create_table(
        "socios",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
        sa.Column("cnpj_basico", sa.String(length=8), nullable=False),
        sa.Column("nome_socio", sa.String(), nullable=True),
        sa.Column("cpf_cnpj_socio", sa.String(), nullable=True),
        sa.ForeignKeyConstraint(["cnpj_basico"], ["empresas.cnpj_basico"]),
    )

    op.create_table(
        "importacoes",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
        sa.Column("nome_arquivo", sa.String(), nullable=True),
        sa.Column("hash_arquivo", sa.String(), nullable=True),
        sa.Column("status", sa.String(), nullable=True),
        sa.Column("registros_processados", sa.Integer(), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("importacoes")
    op.drop_table("socios")
    op.drop_table("estabelecimentos")
    op.drop_table("empresas")
