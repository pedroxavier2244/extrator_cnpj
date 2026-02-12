"""add auxiliary tables and enrichment columns

Revision ID: 0002_auxiliary_enrichment
Revises: 0001_initial
Create Date: 2026-02-12 00:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0002_auxiliary_enrichment"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("importacoes", sa.Column("registros_inseridos", sa.Integer(), nullable=True))

    op.add_column("estabelecimentos", sa.Column("cnae_principal", sa.String(), nullable=True))
    op.add_column("estabelecimentos", sa.Column("cnae_secundario", sa.String(), nullable=True))
    op.add_column("estabelecimentos", sa.Column("pais", sa.String(), nullable=True))
    op.add_column("estabelecimentos", sa.Column("motivo", sa.String(), nullable=True))

    op.add_column("socios", sa.Column("qualificacao", sa.String(), nullable=True))
    op.add_column("socios", sa.Column("pais", sa.String(), nullable=True))

    op.create_table(
        "cnaes",
        sa.Column("codigo", sa.String(), nullable=False),
        sa.Column("descricao", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("codigo"),
    )

    op.create_table(
        "motivos",
        sa.Column("codigo", sa.String(), nullable=False),
        sa.Column("descricao", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("codigo"),
    )

    op.create_table(
        "municipios",
        sa.Column("codigo", sa.String(), nullable=False),
        sa.Column("descricao", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("codigo"),
    )

    op.create_table(
        "naturezas",
        sa.Column("codigo", sa.String(), nullable=False),
        sa.Column("descricao", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("codigo"),
    )

    op.create_table(
        "paises",
        sa.Column("codigo", sa.String(), nullable=False),
        sa.Column("descricao", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("codigo"),
    )

    op.create_table(
        "qualificacoes",
        sa.Column("codigo", sa.String(), nullable=False),
        sa.Column("descricao", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("codigo"),
    )

    op.create_table(
        "simples",
        sa.Column("cnpj_basico", sa.String(length=8), nullable=False),
        sa.Column("opcao_pelo_simples", sa.String(length=1), nullable=True),
        sa.Column("data_opcao_pelo_simples", sa.Date(), nullable=True),
        sa.Column("data_exclusao_do_simples", sa.Date(), nullable=True),
        sa.Column("opcao_pelo_mei", sa.String(length=1), nullable=True),
        sa.Column("data_opcao_pelo_mei", sa.Date(), nullable=True),
        sa.Column("data_exclusao_do_mei", sa.Date(), nullable=True),
        sa.PrimaryKeyConstraint("cnpj_basico"),
    )


def downgrade() -> None:
    op.drop_table("simples")
    op.drop_table("qualificacoes")
    op.drop_table("paises")
    op.drop_table("naturezas")
    op.drop_table("municipios")
    op.drop_table("motivos")
    op.drop_table("cnaes")

    op.drop_column("socios", "pais")
    op.drop_column("socios", "qualificacao")

    op.drop_column("estabelecimentos", "motivo")
    op.drop_column("estabelecimentos", "pais")
    op.drop_column("estabelecimentos", "cnae_secundario")
    op.drop_column("estabelecimentos", "cnae_principal")

    op.drop_column("importacoes", "registros_inseridos")
