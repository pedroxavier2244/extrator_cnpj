"""add additional performance indexes

Revision ID: 0004_performance_indexes
Revises: 0003_indexes_and_fixes
Create Date: 2026-02-14 00:00:00
"""

from __future__ import annotations

from alembic import op

revision = "0004_performance_indexes"
down_revision = "0003_indexes_and_fixes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "idx_estabelecimentos_cnpj_completo",
        "estabelecimentos",
        ["cnpj_completo"],
    )
    op.create_index(
        "idx_socios_cpf_cnpj_socio",
        "socios",
        ["cpf_cnpj_socio"],
    )
    op.execute(
        """
        CREATE INDEX idx_estabelecimentos_ativos
        ON estabelecimentos (cnpj_basico)
        WHERE situacao = '02'
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_estabelecimentos_ativos")
    op.drop_index("idx_socios_cpf_cnpj_socio", table_name="socios")
    op.drop_index("idx_estabelecimentos_cnpj_completo", table_name="estabelecimentos")
