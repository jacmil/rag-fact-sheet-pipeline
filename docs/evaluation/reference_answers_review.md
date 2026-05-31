# Reference Answer Labelling Notes

`reference_answers.json` is the manual Recall@5 reference set used by
`benchmark_exploration.ipynb` and `benchmark_metrics.py`. It is used to compare
ChromaDB and pgvector retrieval, not to grade generated answers.

## Current Set

The current local set contains:

| Item | Count |
|------|------:|
| Reference queries | 20 |
| Chunk files | 17 |
| Chunks | 5,913 |
| Companies represented in labels | 15 |
| Missing labelled chunk IDs | 0 |

Sector coverage:

| Sector | Reference queries |
|--------|------------------:|
| Energy Utilities | 8 |
| Diversified Mining | 8 |
| Food | 4 |

Year coverage runs from 2016 to 2024. The labelled companies are AGL, Alliant,
BHP, Capital Power, Center Point, Chubu, Danone, Freeport, Glencore, Hershey
Company, Kraft Heinz, Orkla, Rio Tinto, Vale, and Vedanta.

The labels were created manually. For each question, the PDF was inspected,
candidate extracted chunks were searched in `reference_answer_builder.ipynb`,
and the final `chunk_id` values were added to `reference_answers.json` only
after reading the full chunk text. This matters because Recall@5 depends on the
manual judgement of which chunks actually contain the answer.

## Current Benchmark Result

The latest full local benchmark used all 20 queries with `k=5` and 3 query
repeats. ChromaDB and pgvector returned the same top-5 chunk order for every
query.

| Metric | ChromaDB | pgvector |
|--------|---------:|---------:|
| Mean recall@5 | 0.4267 | 0.4267 |
| Mean precision@5 | 0.18 | 0.18 |
| Mean MRR | 0.4125 | 0.4125 |
| Same top-5 order | 20 / 20 | 20 / 20 |

These numbers show backend parity for retrieval quality. They do not prove that
the retrieval method is strong enough for production use. The labelled set is
small and was built for this backend comparison.

## Metadata Used In The Benchmark

Metadata is attached during embedding in `embed.py`.

| Metadata key | Source |
|--------------|--------|
| `company` | PDF folder name |
| `source_file` | PDF filename stem |
| `pages` | extracted chunk page numbers |
| `strategy` | chunking strategy |
| `year` | `document_metadata.json` or filename inference |
| `sector` | `document_metadata.json` |

The benchmark checks unfiltered search and `where` filters for company, year,
and sector.

## Labelling Workflow

1. Add PDFs under `data/pdfs/<Company Name>/`.
2. Run `python pipeline.py extract` to create chunk JSONL files.
3. Add company and document metadata to `document_metadata.json`.
4. Read the relevant page or passage in the source PDF.
5. Use `reference_answer_builder.ipynb` to search candidate chunks by phrase,
   page, company, or source file.
6. Inspect the full chunk text, not only the truncated preview.
7. Manually copy the selected `chunk_id` values into `reference_answers.json`
   under the query's `relevant_ids` list.
8. Validate that every labelled chunk ID exists before running the benchmark.

## Labelling Rules

- Choose labels before comparing backend results.
- Each query should be answerable from the listed chunks.
- A relevant chunk should contain evidence that directly answers the query.
- Do not label a chunk just because it mentions the topic.
- Do not change labels after seeing benchmark output unless there is a real
  labelling error.
- One relevant chunk is acceptable when the answer is contained in one chunk.
  Use multiple chunks when the answer spans a table or nearby text.

## Validation Commands

Check JSON syntax:

```bash
python -m json.tool reference_answers.json > /dev/null
```

Run the benchmark:

```bash
docker compose up -d
alembic upgrade head
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 python benchmark_metrics.py
```

Open `benchmark_exploration.ipynb` when you want pandas DataFrames and optional
JSON export. Only run `write_results_json(results, "evaluation_results.json")`
after the notebook output looks correct.
