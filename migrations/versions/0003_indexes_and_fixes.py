"""add indexes, GIN full-text index, and socios.data_entrada column

Revision ID: 0003_indexes_and_fixes
Revises: 0002_auxiliary_enrichment
Create Date: 2026-02-14 00:00:00
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0003_indexes_and_fixes"
down_revision = "0002_auxiliary_enrichment"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- socios: persist data_entrada ---
    op.add_column("socios", sa.Column("data_entrada", sa.Date(), nullable=True))

    # --- performance indexes ---
    # Lookup by cnpj_basico is the hot path for estabelecimentos queries
    op.create_index(
        "idx_estabelecimentos_cnpj_basico",
        "estabelecimentos",
        ["cnpj_basico"],
    )

    # Lookup by cnpj_basico is the hot path for socios queries
    op.create_index(
        "idx_socios_cnpj_basico",
        "socios",
        ["cnpj_basico"],
    )

    # Deduplication / idempotency check on every ETL run
    op.create_index(
        "idx_importacoes_hash_arquivo",
        "importacoes",
        ["hash_arquivo"],
    )

    # GIN index for full-text search on razao_social (/empresas/search endpoint)
    op.execute(
        """
        CREATE INDEX idx_empresas_razao_social_fts
        ON empresas
        USING gin(to_tsvector('portuguese', coalesce(razao_social, '')))
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_empresas_razao_social_fts")
    op.drop_index("idx_importacoes_hash_arquivo", table_name="importacoes")
    op.drop_index("idx_socios_cnpj_basico", table_name="socios")
    op.drop_index("idx_estabelecimentos_cnpj_basico", table_name="estabelecimentos")
    op.drop_column("socios", "data_entrada")
