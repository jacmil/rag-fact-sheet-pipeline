from __future__ import annotations

import click
import coloredlogs

from extract import run_extract
from embed import run_embed
from retrieve import run_retrieve
from generate import run_generate
from vector_store import get_vector_store, VectorStore, QueryResult
from utils import resolve_pipeline_config


def _get_store() -> VectorStore:
    """Create the vector store instance from environment config.

    Called per-command rather than at group level so that extract
    (which doesn't need a store) doesn't pay the setup cost.
    """
    config: dict = resolve_pipeline_config()
    return get_vector_store(config["collection_name"])


@click.group()
def cli() -> None:
    """TPI Carbon Performance RAG pipeline."""
    coloredlogs.install(
        level="INFO",
        fmt="%(asctime)s %(levelname)-8s %(message)s",
        datefmt="%H:%M:%S",
    )


@cli.command()
def extract() -> None:
    """Extract text from PDFs and chunk into segments."""
    run_extract()


@cli.command()
def embed() -> None:
    """Generate embeddings and store chunks in the vector store."""
    store: VectorStore = _get_store()
    run_embed(store)


@cli.command()
@click.option("--query", "-q", default=None, help="Question to ask the pipeline")
def retrieve(query: str | None) -> None:
    """Retrieve relevant chunks for a query."""
    store: VectorStore = _get_store()
    results: list[QueryResult] = run_retrieve(query, store)
    for i, r in enumerate(results, start=1):
        click.echo(f"[{i}] (score={r.score:.3f}) {r.text[:200]}...")


@cli.command()
@click.option("--query", "-q", default=None, help="Question to ask the pipeline")
def generate(query: str | None) -> None:
    """Retrieve chunks then generate a cited answer."""
    store: VectorStore = _get_store()
    # Retrieve → generate handoff: extract text from QueryResults
    results: list[QueryResult] = run_retrieve(query, store)
    chunk_texts: list[str] = [r.text for r in results]
    answer = run_generate(query, chunk_texts)
    click.echo(answer)


@cli.command("run-all")
@click.option("--query", "-q", default=None, help="Question to ask the pipeline")
def run_all(query: str | None) -> None:
    """Run all pipeline stages in sequence.

    Calls Python functions directly rather than Click commands because
    the retrieve -> generate handoff needs the intermediate QueryResult
    list, which can't pass through Click's command dispatch.
    """
    # Stage 1: extract PDFs and chunk (no store needed)
    run_extract()

    # Stage 2-4: embed, retrieve, generate (share a single store instance)
    store: VectorStore = _get_store()
    run_embed(store)
    results: list[QueryResult] = run_retrieve(query, store)
    chunk_texts: list[str] = [r.text for r in results]
    answer = run_generate(query, chunk_texts)
    click.echo(answer)


if __name__ == "__main__":
    cli()
