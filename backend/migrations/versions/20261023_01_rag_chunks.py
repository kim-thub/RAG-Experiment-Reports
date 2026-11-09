"""Create the local RAG vector table in the integration database."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20261023_01_rag_chunks"
down_revision = None
branch_labels = None
depends_on = None


class Vector768(sa.types.UserDefinedType):
    cache_ok = True

    def get_col_spec(self, **kw) -> str:
        return "vector(768)"


def upgrade() -> None:
    op.execute(
        """DO $preflight$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'vector') THEN
                RAISE EXCEPTION 'pgvector must be installed in the local database first';
            END IF;
            IF to_regclass('rag_test.chunks') IS NOT NULL THEN
                RAISE EXCEPTION 'rag_test.chunks already exists; inspect it before migrating';
            END IF;
        END;
        $preflight$"""
    )
    op.execute("CREATE SCHEMA IF NOT EXISTS rag_test")
    op.create_table(
        "chunks",
        sa.Column("chunk_id", sa.Text(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("embedding", Vector768(), nullable=False),
        sa.Column("source_id", sa.Text(), nullable=False),
        sa.Column("version", sa.Text(), nullable=False),
        sa.Column("publication_state", sa.Text(), nullable=False),
        sa.Column("collection_id", sa.Text(), nullable=False),
        sa.Column("content_sha256", sa.Text(), nullable=True),
        sa.Column("location", sa.Text(), nullable=True),
        sa.Column("source_title", sa.Text(), nullable=True),
        sa.Column("source_url", sa.Text(), nullable=True),
        sa.Column("publisher", sa.Text(), nullable=True),
        sa.Column("embedding_model_id", sa.Text(), nullable=True),
        sa.Column("embedding_model_revision", sa.Text(), nullable=True),
        sa.Column("is_synthetic", sa.Boolean(), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.PrimaryKeyConstraint("chunk_id"),
        sa.CheckConstraint(
            "publication_state IN ('staging', 'indexed', 'published', 'failed', 'retired')",
            name="chunks_publication_state_check",
        ),
        schema="rag_test",
    )
    op.create_index(
        "chunks_publication_scope_idx",
        "chunks",
        ["collection_id", "publication_state", "source_id", "version"],
        schema="rag_test",
    )
    op.execute(
        "CREATE INDEX chunks_embedding_hnsw_idx "
        "ON rag_test.chunks USING hnsw (embedding vector_cosine_ops)"
    )


def downgrade() -> None:
    raise RuntimeError("Destructive rag_test.chunks downgrade requires explicit local approval")
