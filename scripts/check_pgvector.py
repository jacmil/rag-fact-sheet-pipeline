#!/usr/bin/env python3
"""Verify Postgres + pgvector connectivity and basic vector search."""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine, delete, select, text
from sqlalchemy.orm import sessionmaker

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from vector_store.db import EMBEDDING_DIM, ChunkRecord

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

SMOKE_TEST_CHUNK_ID = "__smoke_test__"


def run_pgvector_smoke_test() -> None:
    load_dotenv()
    database_url = os.getenv("DATABASE_URL", "").strip()
    if not database_url:
        raise RuntimeError("DATABASE_URL is not set in .env")

    engine = create_engine(database_url)
    with engine.connect() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        conn.commit()
        version = conn.execute(text("SELECT version()")).scalar_one()
        logger.info("Connected: %s", version.split(",")[0])

    dummy = [0.0] * EMBEDDING_DIM
    dummy[0] = 1.0
    metadata = {
        "company": "SmokeCo",
        "source_file": "smoke.pdf",
        "strategy": "B",
        "pages": "[]",
    }

    session_factory = sessionmaker(bind=engine)
    with session_factory() as session:
        session.execute(
            delete(ChunkRecord).where(ChunkRecord.chunk_id == SMOKE_TEST_CHUNK_ID)
        )
        session.add(
            ChunkRecord(
                chunk_id=SMOKE_TEST_CHUNK_ID,
                content="pgvector smoke test",
                embedding=dummy,
                collection_name="smoke_test",
                metadata_=metadata,
            )
        )
        session.commit()

        result = session.scalar(
            select(ChunkRecord.content)
            .where(ChunkRecord.chunk_id == SMOKE_TEST_CHUNK_ID)
            .order_by(ChunkRecord.embedding.cosine_distance(dummy))
            .limit(1)
        )
        logger.info("Nearest-neighbour query returned: %r", result)

        session.execute(
            delete(ChunkRecord).where(ChunkRecord.chunk_id == SMOKE_TEST_CHUNK_ID)
        )
        session.commit()

    logger.info("Smoke test passed.")


def main() -> int:
    try:
        run_pgvector_smoke_test()
    except Exception:
        logger.exception("Smoke test failed.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
