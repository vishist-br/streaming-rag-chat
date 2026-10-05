"use client";

import { useEffect, useRef, useState } from "react";
import { useChat } from "@/hooks/useChat";
import { getHealth } from "@/lib/api";
import type { Health, RetrievalMode } from "@/lib/types";
import DocumentsPanel from "./DocumentsPanel";
import MessageBubble from "./MessageBubble";
import SourcePanel from "./SourcePanel";

const MODES: { value: RetrievalMode; label: string }[] = [
  { value: "hybrid_rerank", label: "Hybrid + rerank" },
  { value: "hybrid", label: "Hybrid" },
  { value: "vector", label: "Vector only" },
];
const MAX_QUESTION_CHARS = 2000; // keep in sync with max_question_chars in the backend config

export default function ChatInterface() {
  const { messages, isStreaming, send, stop } = useChat();
  const [input, setInput] = useState("");
  const [mode, setMode] = useState<RetrievalMode>("hybrid_rerank");
  const [health, setHealth] = useState<Health | null>(null);
  // Which citation is open in the source panel: a message and a 1-based source number.
  const [selected, setSelected] = useState<{ messageId: string; source: number } | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    getHealth().then(setHealth).catch(() => setHealth(null));
  }, []);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const handleSend = () => {
    const question = input.trim();
    if (!question || isStreaming) return;
    setInput("");
    void send(question, mode);
  };

  const selectedMessage = messages.find((m) => m.id === selected?.messageId);

  return (
    <div className="flex h-screen bg-gray-950 text-gray-100">
      <DocumentsPanel />

      <main className="flex min-w-0 flex-1 flex-col">
        <header className="flex flex-wrap items-center gap-3 border-b border-gray-800 px-6 py-3">
          <h1 className="text-lg font-semibold tracking-tight">RAG Chat</h1>
          {health?.provider === "local" && (
            <span className="rounded bg-amber-500/15 px-2 py-0.5 text-xs text-amber-300">
              Offline demo provider (no LLM)
            </span>
          )}
          <span className="text-xs text-gray-500">
            {health
              ? `${health.generation_model} · ${health.embedding_model} · pgvector`
              : "Backend not reachable"}
          </span>
          <label className="ml-auto flex items-center gap-2 text-xs text-gray-400">
            Retrieval
            <select
              value={mode}
              onChange={(e) => setMode(e.target.value as RetrievalMode)}
              className="rounded-md border border-gray-700 bg-gray-800 px-2 py-1 text-gray-200 outline-none focus:border-indigo-500"
            >
              {MODES.map((m) => (
                <option key={m.value} value={m.value}>
                  {m.label}
                </option>
              ))}
            </select>
          </label>
        </header>

        <div className="flex-1 space-y-4 overflow-y-auto px-4 py-6">
          {messages.length === 0 && (
            <div className="mt-20 text-center text-sm text-gray-500">
              <p className="mb-1 text-base text-gray-300">Ask a question about your documents</p>
              <p>Answers cite the passages they are based on. Click a citation to read it.</p>
            </div>
          )}
          {messages.map((message) => (
            <MessageBubble
              key={message.id}
              message={message}
              selectedSource={selected?.messageId === message.id ? selected.source : null}
              onCite={(source) => setSelected({ messageId: message.id, source })}
            />
          ))}
          <div ref={bottomRef} />
        </div>

        <div className="flex gap-3 border-t border-gray-800 px-4 py-4">
          <input
            id="chat-input"
            type="text"
            value={input}
            maxLength={MAX_QUESTION_CHARS}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && !e.shiftKey && handleSend()}
            placeholder="Ask a question…"
            aria-label="Question"
            className="flex-1 rounded-xl border border-gray-700 bg-gray-800 px-4 py-3 text-sm outline-none placeholder:text-gray-500 focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500"
          />
          {isStreaming ? (
            <button
              id="stop-btn"
              onClick={stop}
              className="rounded-xl bg-red-600 px-5 py-3 text-sm font-medium transition-colors hover:bg-red-700"
            >
              Stop
            </button>
          ) : (
            <button
              id="send-btn"
              onClick={handleSend}
              disabled={!input.trim()}
              className="rounded-xl bg-indigo-600 px-5 py-3 text-sm font-medium transition-colors hover:bg-indigo-700 disabled:cursor-not-allowed disabled:opacity-40"
            >
              Send
            </button>
          )}
        </div>
      </main>

      {selected && selectedMessage && (
        <SourcePanel
          sources={selectedMessage.sources}
          cited={selectedMessage.metrics?.cited ?? []}
          selected={selected.source}
          onSelect={(source) => setSelected({ messageId: selectedMessage.id, source })}
          onClose={() => setSelected(null)}
        />
      )}
    </div>
  );
}
