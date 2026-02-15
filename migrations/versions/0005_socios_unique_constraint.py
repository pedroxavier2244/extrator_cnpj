"""add unique constraint to socios for upsert support

Revision ID: 0005_socios_unique_constraint
Revises: 0004_performance_indexes
Create Date: 2026-02-15 00:00:00
"""

from __future__ import annotations

from alembic import op

revision = "0005_socios_unique_constraint"
down_revision = "0004_performance_indexes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Remove duplicate rows before adding unique constraint
    op.execute(
        """
        DELETE FROM socios a
        USING socios b
        WHERE a.id > b.id
          AND a.cnpj_basico = b.cnpj_basico
          AND COALESCE(a.nome_socio, '') = COALESCE(b.nome_socio, '')
          AND COALESCE(a.cpf_cnpj_socio, '') = COALESCE(b.cpf_cnpj_socio, '')
        """
    )
    op.create_index(
        "uq_socios_basico_nome_cpf",
        "socios",
        ["cnpj_basico", "nome_socio", "cpf_cnpj_socio"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("uq_socios_basico_nome_cpf", table_name="socios")
