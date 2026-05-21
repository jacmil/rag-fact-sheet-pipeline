import os
from pathlib import Path
from dotenv import load_dotenv
from vector_store.types import VectorStore

DEFAULT_QUERY: str = "What are the emissions targets for this company?"

def require_env(name: str) -> str:
    """Return a required environment variable value or raise a clear setup error."""
    value = os.getenv(name, "").strip()
    if not value:
        raise ValueError(
            f"{name} is not set. Copy .env.example to .env and set {name}."
        )
    return value


def bootstrap_runtime_env(dotenv_path: str = ".env") -> None:
    """Load `.env` and apply runtime environment defaults safely."""
    load_dotenv(dotenv_path=dotenv_path, encoding="utf-8-sig")

    hf_home = os.getenv("HF_HOME", "").strip()
    if hf_home:
        os.environ["HF_HOME"] = hf_home

    if os.name == "nt":
        os.environ["KMP_DUPLICATE_LIB_OK"] = os.getenv("KMP_DUPLICATE_LIB_OK", "TRUE")


def resolve_pipeline_config() -> dict:
    """Resolve runtime configuration for the multi-company PDF pipeline."""
    bootstrap_runtime_env()

    company_dirs = {
        "Hershey Company": Path(require_env("HERSHEY_PDF_DIR")),
        "Nomad Foods": Path(require_env("NOMAD_PDF_DIR")),
        # Add more companies here later if needed
    }

    pdf_glob = os.getenv("PDF_GLOB", "*.pdf").strip() or "*.pdf"

    for company, company_dir in company_dirs.items():
        if not company_dir.is_dir():
            raise ValueError(f"{company} directory is not valid: {company_dir}")

        pdf_paths = sorted(company_dir.glob(pdf_glob))
        if not pdf_paths:
            raise ValueError(
                f"No PDFs found for {company} in {company_dir} with pattern: {pdf_glob}"
            )

    output_dir = Path(os.getenv("OUTPUT_DIR", "data/interim"))

    return {
        "company_dirs": company_dirs,
        "pdf_glob": pdf_glob,
        "output_dir": output_dir,
        "chroma_dir": Path(os.getenv("CHROMA_DIR", "data/chromadb")),
        "embedding_model": os.getenv(
            "EMBEDDING_MODEL", "sentence-transformers/multi-qa-MiniLM-L6-cos-v1"
        ),
        "reranking_model": os.getenv(
            "RERANKING_MODEL", "cross-encoder/ms-marco-MiniLM-L-6-v2"
        ),
        "generation_model": os.getenv("GENERATION_MODEL", "Qwen/Qwen2.5-1.5B-Instruct"),
        # Vector store abstraction config (Project D)
        "vector_store_backend": os.getenv(
            "VECTOR_STORE", "chroma"
        ),  # "chroma" or "pgvector"
        "collection_name": os.getenv("COLLECTION_NAME", "tpi_vectors"),
        "pg_connection_string": os.getenv(
            "PG_CONNECTION_STRING", ""
        ),  # required when backend=pgvector
    }


#####################################
# Chunking
#####################################

def build_sections_from_elements(elements: list) -> list[dict]:
    """Group elements into header-delimited sections with running title context."""
    sections: list[dict] = []
    running_title = ""
    section_title = ""
    section_header = ""
    section_body: list[str] = []
    section_pages: set = set()
    section_types: set = set()

    for el in elements:
        text = (getattr(el, "text", None) or "").strip()
        if not text:
            continue

        el_type = type(el).__name__
        page = getattr(el.metadata, "page_number", None)

        if el_type == "Title":
            running_title = text
            continue

        if el_type == "Header":
            if section_header and section_body:
                sections.append(
                    {
                        "running_title": section_title,
                        "header": section_header,
                        "body": section_body,
                        "pages": section_pages,
                        "element_types": section_types,
                    }
                )
            section_title = running_title
            section_header = text
            section_body = []
            section_pages = {page} if page else set()
            section_types = {"Header"}
            if section_title:
                section_types.add("Title")
            continue

        if not section_header:
            section_title = running_title
            section_header = "(no header)"
            section_body = []
            section_pages = set()
            section_types = set()
            if section_title:
                section_types.add("Title")

        section_body.append(text)
        section_types.add(el_type)
        if page:
            section_pages.add(page)

    if section_header and section_body:
        sections.append(
            {
                "running_title": section_title,
                "header": section_header,
                "body": section_body,
                "pages": section_pages,
                "element_types": section_types,
            }
        )

    return sections


def emit_chunks_from_sections(
    sections: list[dict],
    char_limit: int = 1000,
    source_label: str = "",
) -> list[dict]:
    """Split header-delimited sections into char-limited chunks."""
    chunks: list[dict] = []

    for section in sections:
        body_texts = section["body"]
        if not body_texts:
            continue

        prefix_parts = []
        if section["running_title"]:
            prefix_parts.append(f"RUNNING TITLE: {section['running_title']}")
        prefix_parts.append(f"HEADER (H2): {section['header']}")
        prefix = "\n\n".join(prefix_parts)

        available = char_limit - len(prefix) - 2
        if available < 100:
            available = max(char_limit // 2, 100)

        body_buffer: list[str] = []
        body_buffer_len = 0

        for body_piece in body_texts:
            if body_buffer_len + len(body_piece) > available and body_buffer:
                chunks.append(
                    {
                        "id": f"elem_{len(chunks):04d}",
                        "text": f"{prefix}\n\n" + "\n".join(body_buffer),
                        "strategy": "element_type",
                        "source": source_label,
                        "pages": sorted(section["pages"]),
                        "element_types": sorted(section["element_types"]),
                    }
                )
                body_buffer = []
                body_buffer_len = 0

            body_buffer.append(body_piece)
            body_buffer_len += len(body_piece)

        if body_buffer:
            chunks.append(
                {
                    "id": f"elem_{len(chunks):04d}",
                    "text": f"{prefix}\n\n" + "\n".join(body_buffer),
                    "strategy": "element_type",
                    "source": source_label,
                    "pages": sorted(section["pages"]),
                    "element_types": sorted(section["element_types"]),
                }
            )

    return chunks


def chunk_by_element_type(
    elements: list,
    char_limit: int = 1000,
    source_label: str = "",
) -> list[dict]:
    """Strategy B: chunk by heading-delimited sections."""
    sections = build_sections_from_elements(elements)
    return emit_chunks_from_sections(sections, char_limit, source_label)


#####################################
# Evalutation for Retrieval Metrics
#####################################
def evaluate_retrieval(
    ground_truth: list[dict],
    store: "VectorStore",
    model: "SentenceTransformer",
    k: int = 5,
) -> "pd.DataFrame":
    """Run queries against a VectorStore and compute retrieval metrics.

    TODO (benchmarker): extend with per-query latency timing, per-company
    breakdowns, and any additional metrics needed for the benchmark report.
    Consider whether DataFrame is the right output format for your harness.
    """
    import pandas as pd
    import numpy as np

    rows: list[dict] = []
    for entry in ground_truth:
        query: str = entry["query"]
        relevant: set[str] = set(entry["relevant_ids"])

        q_vec: np.ndarray = model.encode([query], normalize_embeddings=True)[0]
        results = store.query(embedding=q_vec, k=k)
        retrieved_ids: list[str] = [r.chunk_id for r in results]

        hits_in_k: int = len(relevant & set(retrieved_ids))
        recall: float = hits_in_k / len(relevant) if relevant else 0.0
        precision: float = hits_in_k / k

        mrr: float = 0.0
        for rank, rid in enumerate(retrieved_ids, 1):
            if rid in relevant:
                mrr = 1.0 / rank
                break

        rows.append({
            "query": query[:60] + "..." if len(query) > 60 else query,
            f"recall@{k}": recall,
            f"precision@{k}": precision,
            "mrr": mrr,
        })

    return pd.DataFrame(rows)

