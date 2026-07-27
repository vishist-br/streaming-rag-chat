import { NextRequest, NextResponse } from "next/server";
import { ingestDocument } from "@/lib/rag";

export const runtime = "nodejs";

export async function POST(req: NextRequest) {
  try {
    const { text, source } = await req.json();

    if (!text || !source) {
      return NextResponse.json(
        { error: "Missing required fields: text, source" },
        { status: 400 }
      );
    }

    await ingestDocument(text, source);

    return NextResponse.json({
      success: true,
      message: `Document "${source}" ingested successfully`,
    });
  } catch (err) {
    console.error("Ingestion error:", err);
    return NextResponse.json({ error: "Ingestion failed" }, { status: 500 });
  }
}
