# Evaluation results

**Not measured yet.** This table is filled in by `evals/run_evals.py`, which needs a
Gemini API key. No numbers are written here by hand.

| Configuration | Hit rate@5 | MRR@5 | Faithfulness (1-5) | Relevance (1-5) | Abstention rate | Mean latency (ms) | Mean cost (USD) |
|---|---|---|---|---|---|---|---|
| Vector only | | | | | | | |
| Hybrid (RRF) | | | | | | | |
| Hybrid + rerank | | | | | | | |

## How to produce the numbers

1. Put your key in `.env` at the repo root: `GEMINI_API_KEY=...` and `PROVIDER=gemini`.
2. Start an empty database: `docker compose up -d db`.
3. Run the script:

   ```bash
   cd backend && pip install -e . && cd ..
   python evals/run_evals.py
   ```

The script ingests `sample_docs/`, runs all 31 questions in `evals/golden.jsonl`
through each configuration, and overwrites this file with the measured table.
A full run makes roughly 250 model calls. Use `--retrieval-only` to measure
hit rate and MRR without generation or judge calls, or `--limit 5` for a quick check.
