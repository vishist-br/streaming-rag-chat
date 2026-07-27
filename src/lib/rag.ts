import { QdrantClient } from "@qdrant/js-client-rest";
import OpenAI from "openai";

const openai = new OpenAI({ 
  apiKey: process.env.OPENAI_API_KEY,
  baseURL: process.env.OPENAI_BASE_URL || "https://ai-gateway.vercel.sh/v1"
});
const qdrant = new QdrantClient({
  url: process.env.QDRANT_URL!,
  apiKey: process.env.QDRANT_API_KEY,
});

const COLLECTION = process.env.QDRANT_COLLECTION ?? "rag-docs";
const EMBEDDING_MODEL = "text-embedding-3-small";
const EMBEDDING_DIM = 1536;

// ─── Embedding ───────────────────────────────────────────────────────────────

export async function embedText(text: string): Promise<number[]> {
  const res = await openai.embeddings.create({
    model: EMBEDDING_MODEL,
    input: text,
  });
  return res.data[0].embedding;
}

// ─── Collection Bootstrap ────────────────────────────────────────────────────

export async function ensureCollection() {
  const collections = await qdrant.getCollections();
  const exists = collections.collections.some((c) => c.name === COLLECTION);
  if (!exists) {
    await qdrant.createCollection(COLLECTION, {
      vectors: { size: EMBEDDING_DIM, distance: "Cosine" },
    });
    console.log(`Created Qdrant collection: ${COLLECTION}`);
  }
}

// ─── Ingestion ───────────────────────────────────────────────────────────────

/**
 * Chunks a document with overlap and upserts into Qdrant.
 * Chunk size = 500 words, overlap = 100 words (20%) — industry standard.
 */
export async function ingestDocument(text: string, source: string) {
  await ensureCollection();

  const chunks = chunkWithOverlap(text, 500, 100);
  console.log(`Ingesting ${chunks.length} chunks from: ${source}`);

  for (let i = 0; i < chunks.length; i++) {
    const vector = await embedText(chunks[i]);
    await qdrant.upsert(COLLECTION, {
      points: [
        {
          id: crypto.randomUUID(),
          vector,
          payload: { text: chunks[i], source, chunkIndex: i },
        },
      ],
    });
  }
  console.log(`✅ Ingested ${chunks.length} chunks`);
}

// ─── Retrieval ───────────────────────────────────────────────────────────────

/**
 * Embeds the query, searches Qdrant for top-k similar chunks.
 * Returns the raw text of each chunk for prompt injection.
 */
export async function retrieveContext(query: string, topK = 3): Promise<string[]> {
  const queryVector = await embedText(query);

  const results = await qdrant.search(COLLECTION, {
    vector: queryVector,
    limit: topK,
    with_payload: true,
  });

  return results
    .filter((r) => (r.score ?? 0) > 0.3) // Minimum similarity threshold
    .map((r) => r.payload?.text as string);
}

// ─── Sliding Window Chunker ───────────────────────────────────────────────────

/**
 * Splits text into overlapping word-based chunks.
 * This is the Sliding Window DSA pattern applied to document indexing.
 *
 * @param text     - Full document text
 * @param size     - Words per chunk
 * @param overlap  - Words to overlap between consecutive chunks
 */
export function chunkWithOverlap(
  text: string,
  size: number,
  overlap: number
): string[] {
  const words = text.split(/\s+/);
  const chunks: string[] = [];
  let start = 0;

  while (start < words.length) {
    const end = Math.min(start + size, words.length);
    chunks.push(words.slice(start, end).join(" "));
    if (end === words.length) break;
    start += size - overlap; // Advance by (size - overlap) — the sliding step
  }

  return chunks;
}
