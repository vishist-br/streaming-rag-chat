"use client";

import { useCallback, useRef, useState } from "react";
import { streamChat } from "@/lib/api";
import type { Message, RetrievalMode } from "@/lib/types";

// Tokens can arrive faster than the screen refreshes. Rendering on every
// token would re-render the message list hundreds of times per answer, so
// tokens go into a plain variable and the UI is updated at most 20x a second.
const RENDER_INTERVAL_MS = 50;

export function useChat() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const abortRef = useRef<AbortController | null>(null);

  const send = useCallback(
    async (question: string, mode: RetrievalMode) => {
      // Only completed turns are useful context for rewriting a follow-up.
      const history = messages
        .filter((m) => m.status === "done" && m.content)
        .map(({ role, content }) => ({ role, content }));

      const answerId = crypto.randomUUID();
      const patch = (changes: Partial<Message>) =>
        setMessages((prev) =>
          prev.map((m) => (m.id === answerId ? { ...m, ...changes } : m)),
        );

      setMessages((prev) => [
        ...prev,
        { id: crypto.randomUUID(), role: "user", content: question, status: "done", sources: [] },
        { id: answerId, role: "assistant", content: "", status: "streaming", sources: [] },
      ]);
      setIsStreaming(true);

      const controller = new AbortController();
      abortRef.current = controller;
      let text = "";
      let rendered = "";
      const timer = setInterval(() => {
        if (text !== rendered) {
          rendered = text;
          patch({ content: text });
        }
      }, RENDER_INTERVAL_MS);

      try {
        let failed = false;
        for await (const { event, data } of streamChat(
          { question, history, mode },
          controller.signal,
        )) {
          if (event === "token") text += data.text;
          else if (event === "sources") patch({ sources: data.sources });
          else if (event === "rewrite") patch({ rewrittenQuery: data.query });
          else if (event === "metrics") patch({ metrics: data });
          else if (event === "error") {
            failed = true;
            patch({ content: text, status: "error", error: data.message });
          }
        }
        if (!failed) patch({ content: text.trim(), status: "done" });
      } catch (error) {
        if (controller.signal.aborted) {
          patch({ content: text, status: "stopped" });
        } else {
          const message = error instanceof Error ? error.message : "Request failed";
          patch({ content: text, status: "error", error: message });
        }
      } finally {
        clearInterval(timer);
        setIsStreaming(false);
      }
    },
    [messages],
  );

  // Aborting the fetch closes the connection, which also stops the backend generator.
  const stop = useCallback(() => abortRef.current?.abort(), []);

  return { messages, isStreaming, send, stop };
}
