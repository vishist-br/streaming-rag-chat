import type { Source } from "@/lib/types";

interface Props {
  sources: Source[];
  cited: number[];
  selected: number;
  onSelect: (sourceNumber: number) => void;
  onClose: () => void;
}

/** Right-hand panel listing the chunks behind one answer, with the clicked one highlighted. */
export default function SourcePanel({ sources, cited, selected, onSelect, onClose }: Props) {
  return (
    <aside className="flex w-96 shrink-0 flex-col border-l border-gray-800 bg-gray-900/40">
      <div className="flex items-center justify-between border-b border-gray-800 px-4 py-3">
        <h2 className="text-sm font-semibold">Sources</h2>
        <button
          onClick={onClose}
          aria-label="Close sources"
          className="rounded px-2 py-1 text-xs text-gray-400 hover:bg-gray-800 hover:text-gray-200"
        >
          Close
        </button>
      </div>
      <ol className="flex-1 space-y-3 overflow-y-auto p-4">
        {sources.map((source, index) => {
          const number = index + 1;
          const isSelected = number === selected;
          return (
            <li
              key={source.id}
              // Scroll the clicked citation's chunk into view when it mounts or is selected.
              ref={(element) => {
                if (isSelected) element?.scrollIntoView({ block: "nearest" });
              }}
              onClick={() => onSelect(number)}
              className={`cursor-pointer rounded-lg border p-3 text-xs transition-colors ${
                isSelected
                  ? "border-indigo-400 bg-indigo-500/10"
                  : "border-gray-800 hover:border-gray-600"
              }`}
            >
              <div className="mb-2 flex items-start gap-2">
                <span className="inline-flex h-5 min-w-5 items-center justify-center rounded bg-indigo-500/25 px-1 text-[11px] font-semibold text-indigo-200">
                  {number}
                </span>
                <div className="min-w-0 flex-1">
                  <p className="truncate font-medium text-gray-200">{source.document}</p>
                  <p className="text-gray-500">
                    {[source.section, source.page ? `page ${source.page}` : ""]
                      .filter(Boolean)
                      .join(" · ") || "No section"}
                  </p>
                </div>
              </div>
              <div className="mb-2 flex flex-wrap gap-1.5 text-[11px]">
                {cited.includes(number) && (
                  <span className="rounded bg-emerald-500/15 px-1.5 py-0.5 text-emerald-300">
                    Cited
                  </span>
                )}
                {source.vector_rank !== null && (
                  <span className="rounded bg-gray-800 px-1.5 py-0.5 text-gray-400">
                    Vector #{source.vector_rank}
                  </span>
                )}
                {source.fulltext_rank !== null && (
                  <span className="rounded bg-gray-800 px-1.5 py-0.5 text-gray-400">
                    Keyword #{source.fulltext_rank}
                  </span>
                )}
                {source.flagged && (
                  <span className="rounded bg-amber-500/15 px-1.5 py-0.5 text-amber-300">
                    Possible prompt injection
                  </span>
                )}
              </div>
              <p className="whitespace-pre-wrap leading-relaxed text-gray-300">
                {source.content}
              </p>
            </li>
          );
        })}
      </ol>
    </aside>
  );
}
