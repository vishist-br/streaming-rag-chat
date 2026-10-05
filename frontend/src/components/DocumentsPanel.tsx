"use client";

import { useEffect, useRef, useState } from "react";
import { deleteDocument, listDocuments, uploadDocument } from "@/lib/api";
import type { DocumentInfo } from "@/lib/types";

interface Notice {
  kind: "ok" | "error";
  text: string;
}

/** Left sidebar: upload files and list what has been ingested. */
export default function DocumentsPanel() {
  const [documents, setDocuments] = useState<DocumentInfo[]>([]);
  const [uploading, setUploading] = useState(false);
  const [notices, setNotices] = useState<Notice[]>([]);
  const inputRef = useRef<HTMLInputElement>(null);

  const refresh = () =>
    listDocuments()
      .then(setDocuments)
      .catch(() =>
        setNotices([{ kind: "error", text: "Can't reach the backend. Is it running?" }]),
      );

  useEffect(() => {
    refresh();
  }, []);

  const handleFiles = async (files: FileList | null) => {
    if (!files?.length) return;
    setUploading(true);
    const results: Notice[] = [];
    // One at a time: embedding is the slow part and this keeps error messages per file.
    for (const file of Array.from(files)) {
      try {
        const result = await uploadDocument(file);
        const detail =
          result.status === "unchanged"
            ? "unchanged, skipped"
            : `${result.status}, ${result.num_chunks} chunks (${result.embedded_chunks} embedded, ${result.reused_chunks} reused)`;
        results.push({ kind: "ok", text: `${file.name}: ${detail}` });
      } catch (error) {
        const reason = error instanceof Error ? error.message : "upload failed";
        results.push({ kind: "error", text: `${file.name}: ${reason}` });
      }
    }
    setNotices(results);
    setUploading(false);
    if (inputRef.current) inputRef.current.value = "";
    await refresh();
  };

  const handleDelete = async (doc: DocumentInfo) => {
    if (!window.confirm(`Remove "${doc.filename}" and its chunks?`)) return;
    try {
      await deleteDocument(doc.id);
      setNotices([]);
    } catch {
      setNotices([{ kind: "error", text: `Couldn't remove ${doc.filename}. Try again.` }]);
    }
    await refresh();
  };

  return (
    <aside className="flex w-72 shrink-0 flex-col border-r border-gray-800 bg-gray-900/40">
      <div className="border-b border-gray-800 p-4">
        <h2 className="mb-3 text-sm font-semibold">Documents</h2>
        <label
          className={`block cursor-pointer rounded-lg border border-dashed border-gray-700 px-3 py-4 text-center text-xs text-gray-400 transition-colors hover:border-indigo-500 hover:text-gray-200 ${
            uploading ? "pointer-events-none opacity-50" : ""
          }`}
        >
          {uploading ? "Uploading and embedding…" : "Upload PDF, Markdown or text"}
          <input
            ref={inputRef}
            type="file"
            multiple
            accept=".pdf,.md,.markdown,.txt"
            className="sr-only"
            disabled={uploading}
            onChange={(e) => handleFiles(e.target.files)}
          />
        </label>
        {notices.map((notice) => (
          <p
            key={notice.text}
            role={notice.kind === "error" ? "alert" : "status"}
            className={`mt-2 break-words text-xs ${
              notice.kind === "error" ? "text-red-400" : "text-emerald-400"
            }`}
          >
            {notice.text}
          </p>
        ))}
      </div>
      <ul className="flex-1 space-y-1 overflow-y-auto p-2">
        {documents.length === 0 && (
          <li className="px-2 py-3 text-xs text-gray-500">
            No documents yet. Upload one to start asking questions.
          </li>
        )}
        {documents.map((doc) => (
          <li
            key={doc.id}
            className="group flex items-center gap-2 rounded-md px-2 py-2 text-xs hover:bg-gray-800/60"
          >
            <div className="min-w-0 flex-1">
              <p className="truncate text-gray-200" title={doc.filename}>
                {doc.filename}
              </p>
              <p className="text-gray-500">{doc.num_chunks} chunks</p>
            </div>
            <button
              onClick={() => handleDelete(doc)}
              aria-label={`Remove ${doc.filename}`}
              className="rounded px-1.5 py-1 text-gray-500 opacity-0 hover:bg-gray-700 hover:text-red-300 focus:opacity-100 group-hover:opacity-100"
            >
              Remove
            </button>
          </li>
        ))}
      </ul>
    </aside>
  );
}
