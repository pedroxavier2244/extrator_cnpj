"""fix socios uniqueness with NULL-safe expression index and add concurrent performance indexes

Revision ID: 0006_fix_indices_and_socios_unique
Revises: 0005_socios_unique_constraint
Create Date: 2026-02-16 00:00:00
"""

from __future__ import annotations

from alembic import op

revision = "0006_fix_indices_and_socios_unique"
down_revision = "0005_socios_unique_constraint"
branch_labels = None
depends_on = None


def upgrade() -> None:
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

    with op.get_context().autocommit_block():
        op.execute("DROP INDEX CONCURRENTLY IF EXISTS uq_socios_basico_nome_cpf")
        op.execute("DROP INDEX CONCURRENTLY IF EXISTS uix_socios_cnpj_nome_cpf")
        op.execute(
            """
            CREATE UNIQUE INDEX CONCURRENTLY uix_socios_cnpj_nome_cpf
            ON socios (cnpj_basico, COALESCE(nome_socio, ''), COALESCE(cpf_cnpj_socio, ''))
            """
        )

        op.execute("DROP INDEX CONCURRENTLY IF EXISTS idx_empresas_razao_social_fts")
        op.execute("DROP INDEX CONCURRENTLY IF EXISTS idx_empresas_razao_fts")
        op.execute(
            """
            CREATE INDEX CONCURRENTLY idx_empresas_razao_fts
            ON empresas USING GIN (to_tsvector('portuguese', COALESCE(razao_social, '')))
            """
        )


def downgrade() -> None:
    with op.get_context().autocommit_block():
        op.execute("DROP INDEX CONCURRENTLY IF EXISTS uix_socios_cnpj_nome_cpf")
        op.execute(
            """
            CREATE UNIQUE INDEX CONCURRENTLY uq_socios_basico_nome_cpf
            ON socios (cnpj_basico, nome_socio, cpf_cnpj_socio)
            """
        )

        op.execute("DROP INDEX CONCURRENTLY IF EXISTS idx_empresas_razao_fts")
        op.execute(
            """
            CREATE INDEX CONCURRENTLY idx_empresas_razao_social_fts
            ON empresas USING GIN (to_tsvector('portuguese', COALESCE(razao_social, '')))
            """
        )
