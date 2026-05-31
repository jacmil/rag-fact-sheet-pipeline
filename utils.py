import logging
import os
from dataclasses import dataclass
from pathlib import Path

from vector_store.types import VectorStore

try:
    from dotenv import load_dotenv as _load_dotenv
except ImportError:
    _load_dotenv = None

logger = logging.getLogger(__name__)

DEFAULT_QUERY: str = "What are the emissions targets for this company?"
CACHE_ENV_DEFAULTS: dict[str, str] = {
    "XDG_CACHE_HOME": ".cache",
    "MPLCONFIGDIR": ".cache/matplotlib",
    "NUMBA_CACHE_DIR": ".cache/numba",
}


@dataclass
class PipelineConfig:
    """Typed configuration resolved from .env at runtime."""

    company_dirs: dict[str, Path]
    pdf_glob: str
    output_dir: Path
    chroma_dir: Path
    embedding_model: str
    reranking_model: str
    generation_model: str
    vector_store_backend: str
    collection_name: str
    pg_connection_string: str


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
    load_env_file(dotenv_path)
    configure_runtime_cache_dirs()

    hf_home = os.getenv("HF_HOME", "").strip()
    if hf_home:
        os.environ["HF_HOME"] = hf_home

    if os.name == "nt":
        os.environ["KMP_DUPLICATE_LIB_OK"] = os.getenv("KMP_DUPLICATE_LIB_OK", "TRUE")


def configure_runtime_cache_dirs() -> None:
    """Use repo-local cache directories when tools need writable caches."""
    for name, default in CACHE_ENV_DEFAULTS.items():
        value = os.getenv(name, "").strip() or default
        os.environ[name] = value
        Path(value).mkdir(parents=True, exist_ok=True)


def load_env_file(dotenv_path: str = ".env") -> None:
    """Load simple KEY=VALUE pairs from .env without requiring python-dotenv."""
    if _load_dotenv is not None:
        _load_dotenv(dotenv_path=dotenv_path, encoding="utf-8-sig")
        return

    path = Path(dotenv_path)
    if not path.exists():
        return

    for line in path.read_text(encoding="utf-8-sig").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.startswith("export "):
            stripped = stripped[len("export ") :].strip()
        if "=" not in stripped:
            continue

        key, value = stripped.split("=", 1)
        key = key.strip()
        value = value.strip().strip("\"'")
        if key and key not in os.environ:
            os.environ[key] = value


def resolve_pipeline_config() -> PipelineConfig:
    """Resolve runtime configuration from .env for the pipeline.

    Company discovery is directory-based: PDF_SOURCE_DIR contains one
    subfolder per company. Folder names become company labels, with
    underscores replaced by spaces. To add a company, create a folder
    and drop PDFs in it. No code change needed.
    """
    bootstrap_runtime_env()

    pdf_source_dir = Path(require_env("PDF_SOURCE_DIR"))
    if not pdf_source_dir.is_dir():
        raise ValueError(f"PDF_SOURCE_DIR is not a valid directory: {pdf_source_dir}")

    company_dirs = {
        d.name.replace("_", " "): d
        for d in sorted(pdf_source_dir.iterdir())
            if d.is_dir()
            }

    if not company_dirs:
        raise ValueError(f"No company subdirectories found in {pdf_source_dir}")

    pdf_glob = os.getenv("PDF_GLOB", "*.pdf").strip() or "*.pdf"

    for company, company_dir in company_dirs.items():
        pdf_paths = sorted(company_dir.glob(pdf_glob))
        if not pdf_paths:
            logger.warning(f"No PDFs found for {company} in {company_dir}")

    output_dir = Path(os.getenv("OUTPUT_DIR", "data/interim"))

    return PipelineConfig(
        company_dirs=company_dirs,
        pdf_glob=pdf_glob,
        output_dir=output_dir,
        chroma_dir=Path(os.getenv("CHROMA_DIR", "data/chromadb")),
        embedding_model=os.getenv(
            "EMBEDDING_MODEL", "sentence-transformers/multi-qa-MiniLM-L6-cos-v1"
        ),
        reranking_model=os.getenv(
            "RERANKING_MODEL", "cross-encoder/ms-marco-MiniLM-L-6-v2"
        ),
        generation_model=os.getenv("GENERATION_MODEL", "Qwen/Qwen2.5-1.5B-Instruct"),
        vector_store_backend=os.getenv("VECTOR_STORE", "chroma"),
        collection_name=os.getenv("COLLECTION_NAME", "tpi_vectors"),
        pg_connection_string=os.getenv("PG_CONNECTION_STRING", ""),
    )


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
