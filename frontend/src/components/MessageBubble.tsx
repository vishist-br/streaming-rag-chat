import type { Message } from "@/lib/types";
import MetricsPanel from "./MetricsPanel";

interface Props {
  message: Message;
  selectedSource: number | null;
  onCite: (sourceNumber: number) => void;
}

/** Splits "text [1][2] more" into text and clickable citation chips. */
function renderWithCitations(
  message: Message,
  selectedSource: number | null,
  onCite: (n: number) => void,
) {
  return message.content.split(/(\[\d+\])/g).map((part, index) => {
    const match = /^\[(\d+)\]$/.exec(part);
    const number = match ? Number(match[1]) : 0;
    // A number with no matching source is left as plain text rather than a dead link.
    if (!match || number < 1 || number > message.sources.length) return part;
    return (
      <button
        key={index}
        onClick={() => onCite(number)}
        title={`Show source ${number}`}
        className={`mx-0.5 inline-flex h-5 min-w-5 items-center justify-center rounded px-1 align-text-top text-[11px] font-semibold transition-colors ${
          selectedSource === number
            ? "bg-indigo-400 text-gray-950"
            : "bg-indigo-500/25 text-indigo-200 hover:bg-indigo-500/50"
        }`}
      >
        {number}
      </button>
    );
  });
}

export default function MessageBubble({ message, selectedSource, onCite }: Props) {
  if (message.role === "user") {
    return (
      <div className="flex justify-end">
        <div className="max-w-2xl whitespace-pre-wrap rounded-2xl rounded-br-sm bg-indigo-600 px-4 py-3 text-sm leading-relaxed text-white">
          {message.content}
        </div>
      </div>
    );
  }

  const waiting = message.status === "streaming" && !message.content;
  return (
    <div className="flex justify-start">
      <div className="max-w-2xl space-y-2">
        {message.rewrittenQuery && (
          <p className="text-xs text-gray-500">
            Searched for: <span className="italic">{message.rewrittenQuery}</span>
          </p>
        )}
        <div className="whitespace-pre-wrap rounded-2xl rounded-bl-sm bg-gray-800 px-4 py-3 text-sm leading-relaxed text-gray-100">
          {waiting ? (
            <span className="text-gray-400">
              {message.sources.length ? "Writing answer…" : "Searching documents…"}
            </span>
          ) : (
            renderWithCitations(message, selectedSource, onCite)
          )}
          {message.status === "streaming" && (
            <span className="ml-1 inline-block h-4 w-1 animate-pulse rounded-sm bg-indigo-400 align-text-bottom" />
          )}
        </div>
        {message.status === "stopped" && (
          <p className="text-xs text-gray-500">Stopped.</p>
        )}
        {message.status === "error" && (
          <p role="alert" className="text-xs text-red-400">
            {message.error}
          </p>
        )}
        {message.sources.length > 0 && message.status !== "streaming" && (
          <button
            onClick={() => onCite(message.metrics?.cited[0] ?? 1)}
            className="text-xs text-gray-400 underline-offset-2 hover:text-gray-200 hover:underline"
          >
            {message.sources.length} sources retrieved
            {message.metrics ? `, ${message.metrics.cited.length} cited` : ""}
          </button>
        )}
        {message.metrics && <MetricsPanel metrics={message.metrics} />}
      </div>
    </div>
  );
}
