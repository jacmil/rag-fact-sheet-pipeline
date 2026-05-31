import json
import pickle
import logging

from pathlib import Path
from tqdm import tqdm

from unstructured.partition.pdf import partition_pdf
from utils import resolve_pipeline_config, PipelineConfig, chunk_by_element_type

logger = logging.getLogger(__name__)


def run_extract() -> None:
    """Extract text from PDFs and chunk into segments."""
    config: PipelineConfig = resolve_pipeline_config()
    raw_dir = setup_directories(config)
    log_extraction_summary(config.company_dirs, config.pdf_glob)
    all_pdfs = collect_all_pdfs(config)
    extract_all_pdfs(all_pdfs, raw_dir)
    chunk_all_pdfs(all_pdfs, raw_dir, config.output_dir)


def setup_directories(config: PipelineConfig) -> Path:
    """Create output directories and return raw_dir path."""
    output_dir = config.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    raw_dir = output_dir / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    return raw_dir


def collect_all_pdfs(config: PipelineConfig) -> list[tuple[str, Path]]:
    """Collect all PDF paths across all companies as a flat list."""
    return [
        (company, pdf_path)
        for company, company_dir in config.company_dirs.items()
        for pdf_path in sorted(company_dir.glob(config.pdf_glob))
    ]


def extract_all_pdfs(all_pdfs: list[tuple[str, Path]], raw_dir: Path) -> None:
    """Run partition_pdf on each PDF and save to .pkl cache."""
    total = len(all_pdfs)
    for i, (company, pdf_path) in enumerate(tqdm(all_pdfs, desc="Extracting PDFs"), start=1):
        safe_company = company.replace(" ", "_")
        output_path = raw_dir / f"{safe_company}_{pdf_path.stem}_elements.pkl"

        if output_path.exists():
            logger.info(f"[{i}/{total}] Skipping {pdf_path.name} — already extracted")
            continue

        logger.info(f"[{i}/{total}] Extracting {pdf_path.name} ({company})")
        elements = partition_pdf(filename=str(pdf_path), strategy="auto")

        if len(elements) < 10:
            logger.warning(f"[{i}/{total}] Only {len(elements)} elements from {pdf_path.name} — check PDF quality")

        save_elements_pickle(elements, output_path)
        logger.info(f"[{i}/{total}] Done — saved {len(elements)} elements to {output_path.name}")


def chunk_all_pdfs(all_pdfs: list[tuple[str, Path]], raw_dir: Path, output_dir: Path) -> None:
    """Load .pkl files, apply chunking, save chunks as .jsonl."""
    chunks_dir = output_dir / "chunks"
    chunks_dir.mkdir(parents=True, exist_ok=True)
    total = len(all_pdfs)
    for i, (company, pdf_path) in enumerate(tqdm(all_pdfs, desc="Chunking PDFs"), start=1):
        safe_company = company.replace(" ", "_")
        pkl_path = raw_dir / f"{safe_company}_{pdf_path.stem}_elements.pkl"
        jsonl_path = chunks_dir / f"{safe_company}_{pdf_path.stem}_chunks.jsonl"

        if jsonl_path.exists():
            logger.info(f"[{i}/{total}] Skipping {pdf_path.name} — already chunked")
            continue

        if not pkl_path.exists():
            logger.warning(f"[{i}/{total}] No .pkl found for {pdf_path.name} — run extraction first")
            continue

        logger.info(f"[{i}/{total}] Chunking {pdf_path.name} ({company})")
        elements = load_elements_pickle(pkl_path)
        chunks = chunk_by_element_type(elements, source_label=company)

        save_chunks_jsonl(chunks, jsonl_path, company, pdf_path.stem)
        logger.info(f"[{i}/{total}] Done — saved {len(chunks)} chunks to {jsonl_path.name}")


def save_chunks_jsonl(chunks: list[dict], output_path: Path, company: str, source: str) -> None:
    """Save chunks to JSONL with company and source metadata."""
    with open(output_path, "w", encoding="utf-8") as f:
        for chunk in chunks:
            record = {**chunk, "company": company, "source_file": source}
            f.write(json.dumps(record) + "\n")


def save_elements_pickle(elements: list, output_path: Path) -> None:
    """Save raw elements to pickle cache."""
    with open(output_path, "wb") as f:
        pickle.dump(elements, f)


def load_elements_pickle(input_path: Path) -> list:
    """Load raw elements from a pickle cache file."""
    with open(input_path, "rb") as f:
        return pickle.load(f)


def log_extraction_summary(company_dirs: dict[str, Path], pdf_glob: str) -> None:
    """Log the number of PDFs found per company and the cumulative total."""
    total = 0
    for company, company_dir in company_dirs.items():
        count = len(list(company_dir.glob(pdf_glob)))
        logger.info(f"{company}: {count} PDF(s)")
        total += count
    logger.info(f"Total PDFs to extract: {total}")


if __name__ == "__main__":
    log_format = "%(asctime)s %(levelname)-8s %(message)s"
    try:
        import coloredlogs

        coloredlogs.install(level="INFO", fmt=log_format, datefmt="%H:%M:%S")
    except ImportError:
        logging.basicConfig(level=logging.INFO, format=log_format, datefmt="%H:%M:%S")

    run_extract()
