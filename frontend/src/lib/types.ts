// Mirrors the Pydantic models in backend/app/models.py.

export type RetrievalMode = "vector" | "hybrid" | "hybrid_rerank";

export interface Source {
  id: number;
  document: string;
  section: string;
  page: number | null;
  content: string;
  vector_rank: number | null;
  fulltext_rank: number | null;
  flagged: boolean;
}

export interface StageMetrics {
  ms: number;
  input_tokens: number;
  output_tokens: number;
  cost_usd: number;
}

export interface Metrics {
  trace_id: string;
  total_ms: number;
  first_token_ms: number | null;
  input_tokens: number;
  output_tokens: number;
  cost_usd: number;
  mode: RetrievalMode;
  cited: number[];
  stages: Record<string, StageMetrics>;
}

export type ChatEvent =
  | { event: "rewrite"; data: { query: string } }
  | { event: "sources"; data: { sources: Source[] } }
  | { event: "token"; data: { text: string } }
  | { event: "metrics"; data: Metrics }
  | { event: "done"; data: Record<string, never> }
  | { event: "error"; data: { message: string } };

export interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  status: "streaming" | "done" | "stopped" | "error";
  sources: Source[];
  rewrittenQuery?: string;
  metrics?: Metrics;
  error?: string;
}

export interface DocumentInfo {
  id: string;
  filename: string;
  num_chunks: number;
  updated_at: string;
}

export interface IngestResult {
  filename: string;
  status: "created" | "updated" | "unchanged";
  num_chunks: number;
  embedded_chunks: number;
  reused_chunks: number;
}

export interface Health {
  status: string;
  provider: string;
  generation_model: string;
  embedding_model: string;
}
