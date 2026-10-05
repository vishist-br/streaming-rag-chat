"use client";

import { useState, useEffect, useRef } from "react";

interface Message {
  role: "user" | "assistant";
  content: string;
  isStreaming?: boolean;
}

// ─── The Optimized Stream Hook (Phase 1 knowledge applied) ────────────────────
function useStreamingResponse() {
  const [streamingText, setStreamingText] = useState("");
  const [isStreaming, setIsStreaming] = useState(false);
  const bufferRef = useRef(""); // Silent buffer — never triggers re-renders
  const readerRef = useRef<ReadableStreamDefaultReader | null>(null);

  const startStream = async (
    message: string,
    history: { role: string; content: string }[]
  ) => {
    bufferRef.current = "";
    setStreamingText("");
    setIsStreaming(true);

    const res = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message, history }),
    });

    if (!res.body) throw new Error("No response body");

    const reader = res.body
      .pipeThrough(new TextDecoderStream())
      .getReader();

    readerRef.current = reader;

    // Network consumer: runs at full SSE speed, silently fills buffer
    const consume = async () => {
      try {
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          // Parse SSE lines: "data: {...}\n\n"
          const lines = value.split("\n").filter((l) => l.startsWith("data: "));
          for (const line of lines) {
            const payload = line.slice(6).trim();
            if (payload === "[DONE]") { setIsStreaming(false); return; }
            try {
              const { token } = JSON.parse(payload);
              bufferRef.current += token;
            } catch {}
          }
        }
      } finally {
        setIsStreaming(false);
      }
    };

    consume();
  };

  const stopStream = () => {
    readerRef.current?.cancel("User clicked stop");
    setIsStreaming(false);
  };

  // UI Renderer: capped at 20 FPS — decouples network speed from render speed
  useEffect(() => {
    const interval = setInterval(() => {
      setStreamingText((current) => {
        if (current !== bufferRef.current) return bufferRef.current;
        return current; // Always return a value — never undefined!
      });
    }, 50);
    return () => clearInterval(interval);
  }, []);

  return { streamingText, isStreaming, startStream, stopStream };
}

// ─── Main Chat Interface ───────────────────────────────────────────────────────
export default function ChatInterface() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const { streamingText, isStreaming, startStream, stopStream } = useStreamingResponse();
  const bottomRef = useRef<HTMLDivElement>(null);
  const prevStreamingRef = useRef("");

  // Commit the streamed message to history when streaming finishes
  useEffect(() => {
    if (!isStreaming && prevStreamingRef.current && streamingText) {
      setMessages((prev) => [
        ...prev.filter((m) => !m.isStreaming),
        { role: "assistant", content: streamingText },
      ]);
      prevStreamingRef.current = "";
    }
    if (isStreaming) {
      prevStreamingRef.current = streamingText;
      setMessages((prev) => {
        const withoutStreaming = prev.filter((m) => !m.isStreaming);
        return [
          ...withoutStreaming,
          { role: "assistant", content: streamingText, isStreaming: true },
        ];
      });
    }
  }, [streamingText, isStreaming]);

  // Auto scroll to bottom
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const handleSend = async () => {
    if (!input.trim() || isStreaming) return;
    const userMessage = input.trim();
    setInput("");
    setMessages((prev) => [...prev, { role: "user", content: userMessage }]);

    const history = messages.map(({ role, content }) => ({ role, content }));
    await startStream(userMessage, history);
  };

  return (
    <div className="flex flex-col h-screen bg-gray-950 text-gray-100">
      {/* Header */}
      <header className="border-b border-gray-800 px-6 py-4 flex items-center gap-3">
        <div className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
        <h1 className="font-semibold text-lg tracking-tight">RAG Chat</h1>
        <span className="text-xs text-gray-500 ml-auto">gpt-4o-mini · text-embedding-3-small · Qdrant</span>
      </header>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-4 py-6 space-y-4">
        {messages.length === 0 && (
          <div className="text-center text-gray-500 mt-20">
            <p className="text-2xl mb-2">💬</p>
            <p>Ask anything from your knowledge base</p>
          </div>
        )}
        {messages.map((msg, i) => (
          <div
            key={i}
            className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
          >
            <div
              className={`max-w-2xl px-4 py-3 rounded-2xl text-sm leading-relaxed whitespace-pre-wrap ${
                msg.role === "user"
                  ? "bg-indigo-600 text-white rounded-br-sm"
                  : "bg-gray-800 text-gray-100 rounded-bl-sm"
              }`}
            >
              {msg.content}
              {msg.isStreaming && (
                <span className="inline-block w-1 h-4 ml-1 bg-indigo-400 animate-pulse rounded-sm" />
              )}
            </div>
          </div>
        ))}
        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <div className="border-t border-gray-800 px-4 py-4 flex gap-3">
        <input
          id="chat-input"
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && !e.shiftKey && handleSend()}
          placeholder="Ask a question..."
          disabled={isStreaming}
          className="flex-1 bg-gray-800 border border-gray-700 rounded-xl px-4 py-3 text-sm outline-none
                     focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500
                     disabled:opacity-50 disabled:cursor-not-allowed placeholder:text-gray-500"
        />
        {isStreaming ? (
          <button
            id="stop-btn"
            onClick={stopStream}
            className="px-5 py-3 rounded-xl bg-red-600 hover:bg-red-700 text-sm font-medium transition-colors"
          >
            Stop
          </button>
        ) : (
          <button
            id="send-btn"
            onClick={handleSend}
            disabled={!input.trim()}
            className="px-5 py-3 rounded-xl bg-indigo-600 hover:bg-indigo-700 disabled:opacity-40
                       disabled:cursor-not-allowed text-sm font-medium transition-colors"
          >
            Send
          </button>
        )}
      </div>
    </div>
  );
}
