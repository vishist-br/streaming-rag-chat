import { NextRequest } from "next/server";
import OpenAI from "openai";
import { retrieveContext } from "@/lib/rag";

const openai = new OpenAI({ 
  apiKey: process.env.OPENAI_API_KEY,
  baseURL: process.env.OPENAI_BASE_URL || "https://ai-gateway.vercel.sh/v1"
});

export const runtime = "nodejs";

export async function POST(req: NextRequest) {
  const { message, history } = await req.json();

  if (!message) {
    return new Response("Missing message", { status: 400 });
  }

  // ─── Step 1: Retrieve relevant context from Qdrant ───────────────────────
  const contextChunks = await retrieveContext(message, 3);
  const context = contextChunks.length > 0
    ? contextChunks.map((c, i) => `[Source ${i + 1}]\n${c}`).join("\n\n")
    : "No relevant documents found in the knowledge base.";

  // ─── Step 2: Assemble the augmented prompt ────────────────────────────────
  const systemPrompt = `You are a helpful AI assistant. Answer questions using ONLY the provided context below.
If the context does not contain the answer, say "I don't have that information in my knowledge base."
Never hallucinate or make up information.

CONTEXT:
${context}`;

  // ─── Step 3: Stream from GPT-4o-mini via SSE ─────────────────────────────
  const messages: OpenAI.Chat.ChatCompletionMessageParam[] = [
    { role: "system", content: systemPrompt },
    ...(history ?? []),
    { role: "user", content: message },
  ];

  const stream = await openai.chat.completions.create({
    model: "gpt-4o-mini",
    messages,
    stream: true,
    temperature: 0.2, // Low temp for factual RAG responses
    max_tokens: 1024,
  });

  // ─── Step 4: Return SSE response ─────────────────────────────────────────
  const encoder = new TextEncoder();

  const readable = new ReadableStream({
    async start(controller) {
      try {
        for await (const chunk of stream) {
          const token = chunk.choices[0]?.delta?.content ?? "";
          if (token) {
            // SSE format: "data: {...}\n\n"
            const payload = JSON.stringify({ token });
            controller.enqueue(encoder.encode(`data: ${payload}\n\n`));
          }
        }
        // Signal stream completion
        controller.enqueue(encoder.encode("data: [DONE]\n\n"));
        controller.close();
      } catch (err) {
        console.error("Stream error:", err);
        controller.error(err);
      }
    },
    cancel() {
      // User clicked Stop — abort the OpenAI stream
      stream.controller.abort();
    },
  });

  return new Response(readable, {
    headers: {
      "Content-Type": "text/event-stream",
      "Cache-Control": "no-cache",
      Connection: "keep-alive",
    },
  });
}
