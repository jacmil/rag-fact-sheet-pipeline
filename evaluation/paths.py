"""Repo-root-relative paths for evaluation data and notebooks."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
REFERENCE_ANSWERS = REPO_ROOT / "evaluation/reference_answers.json"
DOCUMENT_METADATA = REPO_ROOT / "evaluation/document_metadata.json"
EVALUATION_RESULTS = REPO_ROOT / "evaluation/evaluation_results.json"
NOTEBOOKS_DIR = REPO_ROOT / "notebooks"
