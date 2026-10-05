import type { Metrics } from "@/lib/types";

const MODE_LABELS: Record<Metrics["mode"], string> = {
  vector: "Vector only",
  hybrid: "Hybrid",
  hybrid_rerank: "Hybrid + rerank",
};

function formatCost(usd: number): string {
  if (usd === 0) return "$0";
  return usd < 0.01 ? `$${usd.toFixed(5)}` : `$${usd.toFixed(3)}`;
}

/** Per-answer latency, token and cost breakdown. Collapsed to one line by default. */
export default function MetricsPanel({ metrics }: { metrics: Metrics }) {
  return (
    <details className="group rounded-lg border border-gray-800 bg-gray-900/60 text-xs text-gray-400">
      <summary className="flex cursor-pointer list-none flex-wrap items-center gap-x-4 gap-y-1 px-3 py-2 tabular-nums">
        <span>{(metrics.total_ms / 1000).toFixed(2)}s total</span>
        {metrics.first_token_ms !== null && (
          <span>{Math.round(metrics.first_token_ms)} ms to first token</span>
        )}
        <span>
          {metrics.input_tokens} in / {metrics.output_tokens} out tokens
        </span>
        <span>{formatCost(metrics.cost_usd)} est.</span>
        <span className="ml-auto text-gray-500 group-open:hidden">Details</span>
        <span className="ml-auto hidden text-gray-500 group-open:inline">Hide</span>
      </summary>
      <div className="border-t border-gray-800 px-3 py-2">
        <table className="w-full tabular-nums">
          <thead>
            <tr className="text-left text-gray-500">
              <th className="py-1 font-medium">Stage</th>
              <th className="py-1 text-right font-medium">Latency</th>
              <th className="py-1 text-right font-medium">Tokens in</th>
              <th className="py-1 text-right font-medium">Tokens out</th>
              <th className="py-1 text-right font-medium">Est. cost</th>
            </tr>
          </thead>
          <tbody>
            {Object.entries(metrics.stages).map(([name, stage]) => (
              <tr key={name} className="border-t border-gray-800/60">
                <td className="py-1 text-gray-300">{name.replace(/_/g, " ")}</td>
                <td className="py-1 text-right">{stage.ms.toFixed(1)} ms</td>
                <td className="py-1 text-right">{stage.input_tokens || "–"}</td>
                <td className="py-1 text-right">{stage.output_tokens || "–"}</td>
                <td className="py-1 text-right">
                  {stage.cost_usd ? formatCost(stage.cost_usd) : "–"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        <p className="mt-2 text-gray-500">
          {MODE_LABELS[metrics.mode]} · trace {metrics.trace_id}
        </p>
      </div>
    </details>
  );
}
