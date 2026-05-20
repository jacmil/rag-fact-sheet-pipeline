from __future__ import annotations

import logging
import os
import platform
import coloredlogs

from transformers import pipeline as hf_pipeline, Pipeline

from utils import resolve_pipeline_config, DEFAULT_QUERY


logger = logging.getLogger(__name__)

# Budget for generated tokens. Larger values allow longer answers but
# consume more of the model's context window alongside the source chunks.
MAX_NEW_TOKENS: int = 512


def load_generation_model(config: dict) -> Pipeline:
    """Load the generation model, with 8-bit quantisation where supported.

    bitsandbytes does not work on macOS Apple Silicon (no CUDA backend).
    On those systems the model loads at full precision. On Linux/Nuvolos
    systems, 8-bit quantisation roughly halves memory usage.
    """
    model_name: str = config["generation_model"]
    logger.info(f"Loading generation model: {model_name}")

    model_kwargs: dict = {}
    is_mac_arm: bool = platform.system() == "Darwin" and platform.machine() == "arm64"

    if not is_mac_arm:
        try:
            from transformers import BitsAndBytesConfig

            model_kwargs["quantization_config"] = BitsAndBytesConfig(load_in_8bit=True)
            logger.info("Using 8-bit quantisation")
        except ImportError:
            logger.warning("bitsandbytes not available, loading without quantisation")
    else:
        logger.info("macOS Apple Silicon detected, skipping quantisation")

    generator: Pipeline = hf_pipeline(
        "text-generation",
        model=model_name,
        model_kwargs=model_kwargs,
        device_map="auto",
        # Only return the generated text, not the prompt + generation
        return_full_text=False,
    )
    return generator


def build_prompt(query_text: str, chunk_texts: list[str]) -> list[dict[str, str]]:
    """Build chat messages with numbered source labels.

    Sources are numbered [1], [2], etc. so the model can cite them
    inline. The system message constrains the model to only use
    provided sources and quote exact figures.
    """
    # Number each chunk for inline citation
    sources: list[str] = [
        f"[{i}] {text}" for i, text in enumerate(chunk_texts, start=1)
    ]
    sources_block: str = "\n\n".join(sources)

    user_content: str = (
        "Below are source documents from corporate sustainability reports.\n"
        "Answer the question using only these sources.\n\n"
        "SOURCES:\n"
        f"{sources_block}\n\n"
        "QUESTION:\n"
        f"{query_text}\n\n"
        "ANSWER (cite sources inline):"
    )

    return [
        {
            "role": "system",
            "content": (
                "You are a climate data analyst specialising in corporate "
                "emissions reporting. Your task is to answer questions about "
                "company emissions targets using only the provided source "
                "documents. "
                "Rules:\n"
                "1. Always cite sources inline using [1], [2] etc.\n"
                "2. Quote exact figures: percentages, scopes, baseline "
                "years, and target years.\n"
                "3. If a question asks about Scope 1, 2, or 3 emissions, "
                "state the scope explicitly.\n"
                "4. If the answer spans multiple sources, synthesise them "
                "and cite each.\n"
                "5. If the information is not in the sources, say exactly: "
                "'The provided sources do not contain this information.'\n"
                "6. Never invent figures or dates not present in the sources."
            ),
        },
        {
            "role": "user",
            "content": user_content,
        },
    ]


def generate_answer(generator: Pipeline, messages: list[dict[str, str]]) -> str:
    """Generate an answer from the model given chat messages.

    apply_chat_template formats the messages with the model's expected
    special tokens (e.g. <|im_start|> for Qwen). Without this, instruct
    models produce garbage or runaway generation.
    """
    prompt: str = generator.tokenizer.apply_chat_template(
        messages,
        tokenize=False,
        add_generation_prompt=True,
    )

    output = generator(
        prompt,
        max_new_tokens=MAX_NEW_TOKENS,
        do_sample=False,  # greedy decoding for reproducible output
    )
    return output[0]["generated_text"]


def run_generate(
    query_text: str | None = None,
    chunk_texts: list[str] | None = None,
) -> str:
    """Generate a cited answer from retrieved chunks.

    Receives chunk texts directly from the pipeline orchestrator.
    The retrieve -> generate handoff is managed by pipeline.py, not here.
    """
    config: dict = resolve_pipeline_config()
    final_query: str = query_text or os.getenv("QUERY_TEXT", DEFAULT_QUERY)

    if not chunk_texts:
        logger.warning("No chunks provided, nothing to generate from")
        return ""

    logger.info(f"Generating answer for: {final_query}")
    messages: list[dict[str, str]] = build_prompt(final_query, chunk_texts)
    generator: Pipeline = load_generation_model(config)
    answer: str = generate_answer(generator, messages)
    logger.info("Generation complete")
    return answer


if __name__ == "__main__":
    coloredlogs.install(
        level="INFO",
        fmt="%(asctime)s %(levelname)-8s %(message)s",
        datefmt="%H:%M:%S",
    )
    # Standalone run: retrieve chunks first, then generate
    from vector_store import get_vector_store
    from retrieve import run_retrieve

    config: dict = resolve_pipeline_config()
    store = get_vector_store(config["collection_name"])
    results = run_retrieve(store=store)
    run_generate(chunk_texts=[r.text for r in results])
