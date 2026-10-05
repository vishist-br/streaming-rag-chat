import type { ChatEvent } from "./types";

/**
 * Parses a Server-Sent Events byte stream into typed events.
 *
 * EventSource only supports GET, and chat needs a POST body, so we read the
 * fetch stream ourselves. Network chunks do not line up with events: one read
 * can hold several events or end halfway through one. So text is appended to
 * a buffer and only complete events (terminated by a blank line) are emitted.
 */
export async function* parseSSE(
  stream: ReadableStream<Uint8Array>,
): AsyncGenerator<ChatEvent> {
  const reader = stream.getReader();
  // stream: true keeps a multi-byte character that was split across reads intact.
  const decoder = new TextDecoder();
  let buffer = "";
  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) return;
      buffer += decoder.decode(value, { stream: true });
      let boundary: number;
      while ((boundary = buffer.indexOf("\n\n")) !== -1) {
        const event = parseEvent(buffer.slice(0, boundary));
        buffer = buffer.slice(boundary + 2);
        if (event) yield event;
      }
    }
  } finally {
    // Runs when the consumer stops early too; cancelling closes the connection.
    await reader.cancel().catch(() => {});
  }
}

function parseEvent(raw: string): ChatEvent | null {
  let event = "message";
  let data = "";
  for (const line of raw.split("\n")) {
    if (line.startsWith("event:")) event = line.slice(6).trim();
    else if (line.startsWith("data:")) data += line.slice(5).trim();
  }
  if (!data) return null;
  return { event, data: JSON.parse(data) } as ChatEvent;
}
