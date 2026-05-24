"""create chunk_records table with pgvector embedding column

Revision ID: 001
Revises:
Create Date: 2026-05-18

"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.create_table(
        "chunk_records",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("chunk_id", sa.String(length=128), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("embedding", Vector(384), nullable=False),
        sa.Column("collection_name", sa.String(length=128), nullable=False),
        sa.Column(
            "metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("chunk_id"),
    )
    op.create_index(
        "ix_chunk_records_collection_name",
        "chunk_records",
        ["collection_name"],
    )
    op.create_index(
        "ix_chunk_records_metadata",
        "chunk_records",
        ["metadata"],
        postgresql_using="gin",
    )


def downgrade() -> None:
    op.drop_index("ix_chunk_records_metadata", table_name="chunk_records")
    op.drop_index("ix_chunk_records_collection_name", table_name="chunk_records")
    op.drop_table("chunk_records")
