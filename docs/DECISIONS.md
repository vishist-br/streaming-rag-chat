# Decisions

Short ADR-style records. Each has the context, the decision, and what it costs.

## 1. No orchestration framework for the core pipeline

**Context.** Frameworks such as LangChain provide ready-made loaders, retrievers and chains.
**Decision.** Write ingestion, retrieval, prompting and streaming by hand.
**Why.** The whole pipeline is a few hundred lines. Hand-written, every step is visible,
testable as a pure function, and debuggable without reading framework internals.
**Cost.** No ready-made integrations; each new file type or provider is our code.

## 2. Postgres + pgvector instead of a dedicated vector database

**Context.** The previous prototype used Qdrant.
**Decision.** Store vectors, text, metadata and the full-text index in one Postgres.
**Why.** Hybrid search becomes two SQL queries against one table. Ingestion is
transactional. There is one service to run, back up and reason about.
**Cost.** At very large scale (hundreds of millions of vectors) or with heavy filtering, a
dedicated engine performs better. HNSW indexes also use significant memory and slow down
bulk inserts.

## 3. Hybrid retrieval fused with Reciprocal Rank Fusion

**Context.** Vector search misses exact identifiers; keyword search misses paraphrases.
**Decision.** Run both, take 20 candidates from each, fuse with RRF (k = 60).
**Why.** RRF needs only ranks, so there is no score normalisation between cosine similarity
and `ts_rank_cd`, and no weights to tune.
**Cost.** Two queries instead of one. Equal weighting of the two retrievers is a default,
not a measured optimum.

## 4. Full-text query terms are OR-ed

**Context.** `plainto_tsquery` ANDs all terms. A natural-language question then matches
only chunks containing every word, which is usually none.
**Decision.** Replace `&` with `|` and let `ts_rank_cd` order chunks by how well they match.
**Why.** Recall first; ranking and fusion handle precision.
**Cost.** Common words match many chunks. The `LIMIT` and the rank keep this bounded.

## 5. Rerank with one listwise LLM call

**Context.** Gemini has no rerank endpoint. The alternative is a local cross-encoder.
**Decision.** Send the top 20 fused candidates (truncated) to the fast model and ask for a
JSON array of passage numbers in relevance order. Fall back to the fused order on any
parsing problem.
**Why.** No extra model to host, and no PyTorch in the image. One call regardless of the
number of candidates.
**Cost.** A full LLM round trip before the first token, plus tokens. A cross-encoder would
be cheaper per query and deterministic. Whether the rerank is worth it is exactly what the
evals compare; it can be turned off per request.

## 6. Structure-aware chunks of about 400 tokens with 15% overlap

**Context.** The prototype used a 500-word sliding window that ignored document structure.
**Decision.** Never cross a heading. Pack whole paragraphs to about 400 tokens. Split
oversized paragraphs at sentence ends. Overlap consecutive chunks of a section by about 60
tokens. Prepend the heading path to the text that is embedded.
**Why.** A chunk about one topic embeds cleanly, and the heading gives a short chunk its
context ("70 minutes" means little without "Battery > Charging").
**Cost.** Sections shorter than the target become small chunks. Sizes are estimates
(4 characters per token), not tokenizer counts.

## 7. Idempotent ingestion with two levels of hashing

**Decision.** A document hash skips unchanged files. Per-chunk hashes let an edited file
reuse embeddings for chunks that did not change. The swap happens in one transaction.
**Why.** Re-running ingestion is safe and cheap; embedding is the only paid step.
**Cost.** Documents are identified by filename, so two different files with the same name
are treated as versions of one document.

## 8. Generation sees only the standalone question, not the chat history

**Decision.** History is used to rewrite the question, then dropped. The answer prompt holds
the sources and the rewritten question.
**Why.** Smaller prompts, and earlier answers cannot be recycled as if they were sources,
which keeps every answer grounded in retrieved text.
**Cost.** The model cannot refer back to its own earlier wording ("as I said above").

## 9. Server-Sent Events over POST, parsed by hand in the browser

**Decision.** One HTTP response carrying typed events (`sources`, `token`, `metrics`, ...).
**Why.** The stream is one-directional, so WebSockets add nothing. SSE works through
ordinary HTTP infrastructure. `EventSource` cannot send a body, so the client reads the
`fetch` stream and parses events itself (about 40 lines).
**Cost.** No automatic reconnection, which is fine for a single answer.

## 10. Prompt-injection handling: delimit, instruct, flag

**Decision.** Retrieved text is wrapped in `<source>` tags; our delimiter tags inside
document text are escaped so a document cannot close its block; the system prompt states
that sources are data, not instructions; chunks matching known injection phrases are logged
and flagged in the UI but still shown to the model.
**Why.** Dropping flagged chunks on a regex match would give anyone who can upload a
document a way to hide content, and regexes produce false positives.
**Cost.** This lowers risk but does not eliminate it. The app has no tools or side effects
the model could trigger, which limits what a successful injection can do.

## 11. In-memory, per-IP sliding-window rate limiter

**Decision.** A dictionary of timestamps per client address, checked in a FastAPI dependency.
**Why.** No extra infrastructure, and exact for a single process.
**Cost.** Each replica counts separately, and behind a proxy the address is the proxy's
unless forwarded headers are configured. A shared store such as Redis is the fix.

## 12. A provider interface with an offline implementation

**Decision.** The pipeline depends on a three-method `Provider` protocol. Besides Gemini
there is a `local` provider using hashed bag-of-words embeddings and extractive answers.
**Why.** Swapping models is one class. The offline provider lets CI run real integration
tests against Postgres and lets the app be demoed without a key.
**Cost.** The offline provider is not a model and must not be used to judge quality. The
eval script refuses to write results when it is active.

## 13. Evals measure retrieval by evidence phrase, not chunk id

**Decision.** Each golden question stores its source document and a short verbatim phrase.
A retrieved chunk counts as relevant if it is from that document and contains the phrase.
**Why.** Chunk ids change whenever chunking parameters change. Phrases survive, so the same
golden set can compare chunking strategies. A unit test checks every phrase still exists in
its document.
**Cost.** A chunk that answers the question in different words would not count.
