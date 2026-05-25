"""SQLAlchemy models for the pgvector backend."""

from __future__ import annotations

from pgvector.sqlalchemy import Vector
from sqlalchemy import Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

# sentence-transformers/multi-qa-MiniLM-L6-cos-v1
EMBEDDING_DIM = 384


class Base(DeclarativeBase):
    pass


class ChunkRecord(Base):
    """Stored chunk with embedding and string metadata (Chroma-compatible)."""

    __tablename__ = "chunk_records"
    __table_args__ = (
        Index("ix_chunk_records_collection_name", "collection_name"),
        Index("ix_chunk_records_metadata", "metadata", postgresql_using="gin"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    chunk_id: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[list[float]] = mapped_column(Vector(EMBEDDING_DIM), nullable=False)
    collection_name: Mapped[str] = mapped_column(String(128), nullable=False)
    metadata_: Mapped[dict[str, str]] = mapped_column(
        "metadata",
        JSONB,
        nullable=False,
        default=dict,
    )
