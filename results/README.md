# Screenshots

Captured from the app running with `PROVIDER=local docker compose up` and the
five files in `sample_docs/` ingested.

**These were taken with the offline demo provider, not Gemini.** That provider
is not a language model: embeddings are hashed bag-of-words vectors and the
"answer" is the best-matching sentence copied from each top source. The
screenshots show the application working end to end (upload, hybrid retrieval,
streaming, citations, metrics). They say nothing about answer quality with a
real model; for that, run the evals in `evals/` with an API key.

| File | What it shows |
|---|---|
| `01-documents-loaded.png` | Sidebar with the ingested documents and their chunk counts. |
| `02-answer-citations-sources-metrics.png` | A streamed answer with a citation, the source panel opened on the cited chunk (with its vector and keyword ranks), and the per-stage latency/token/cost table. |
| `03-conversation-and-i-dont-know.png` | Several turns, including an out-of-scope question answered with "I don't know". |
| `04-idempotent-reupload.png` | Uploading an unchanged file again is detected by its content hash and skipped. |
