import { parseSSE } from "./sse";
import type {
  ChatEvent,
  DocumentInfo,
  Health,
  IngestResult,
  RetrievalMode,
} from "./types";

export const API_URL =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

/** Turns a non-2xx response into an Error carrying the backend's message. */
async function ensureOk(response: Response): Promise<Response> {
  if (response.ok) return response;
  let detail = `Request failed (${response.status})`;
  try {
    const body = await response.json();
    if (typeof body.detail === "string") detail = body.detail;
  } catch {
    // Not JSON; keep the generic message.
  }
  throw new Error(detail);
}

export async function getHealth(): Promise<Health> {
  return (await ensureOk(await fetch(`${API_URL}/api/health`))).json();
}

export async function listDocuments(): Promise<DocumentInfo[]> {
  return (await ensureOk(await fetch(`${API_URL}/api/documents`))).json();
}

export async function uploadDocument(file: File): Promise<IngestResult> {
  const form = new FormData();
  form.append("file", file);
  const response = await fetch(`${API_URL}/api/documents`, {
    method: "POST",
    body: form,
  });
  return (await ensureOk(response)).json();
}

export async function deleteDocument(id: string): Promise<void> {
  await ensureOk(
    await fetch(`${API_URL}/api/documents/${id}`, { method: "DELETE" }),
  );
}

export async function* streamChat(
  body: {
    question: string;
    history: { role: "user" | "assistant"; content: string }[];
    mode: RetrievalMode;
  },
  signal: AbortSignal,
): AsyncGenerator<ChatEvent> {
  const response = await ensureOk(
    await fetch(`${API_URL}/api/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
      signal,
    }),
  );
  if (!response.body) throw new Error("The server sent no response body");
  yield* parseSSE(response.body);
}
