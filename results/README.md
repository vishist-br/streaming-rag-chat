# Screenshots

Captured from the app running with `PROVIDER=ollama docker compose up`, the five files in
`sample_docs/` ingested, and the retrieval mode set to "Hybrid + rerank".

The answers are real model output: `llama3.2` (3B) for generation, rewrite and rerank, and
`nomic-embed-text` for embeddings, both running locally through Ollama. Nothing was edited.
A model this small makes mistakes on other questions; the measured quality is in
[evals/RESULTS.md](../evals/RESULTS.md).

| File | What it shows |
|---|---|
| `01-documents-loaded.png` | Sidebar with the ingested documents and their chunk counts. |
| `02-answer-citations-sources-metrics.png` | A streamed answer with a citation, the source panel opened on the cited chunk (with its vector and keyword ranks), and the per-stage latency and token table. The rerank stage dominates latency, and the reranker placed the correct chunk third. |
| `03-follow-up-rewrite-and-i-dont-know.png` | A follow-up ("And how long does it take to charge?") rewritten into a standalone query before retrieval, and an unanswerable question answered with "I don't know". |
| `04-idempotent-reupload.png` | Uploading an unchanged file again is detected by its content hash and skipped. |
