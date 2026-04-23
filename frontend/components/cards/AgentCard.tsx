import type { AgentRun } from "@/lib/types";

interface Props {
  latestRun: AgentRun | null;
}

function timeAgo(isoString: string): string {
  const diff = Date.now() - new Date(isoString).getTime();
  const hours = Math.floor(diff / 3_600_000);
  if (hours < 1) return "< 1h ago";
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}

export default function AgentCard({ latestRun }: Props) {
  const output = latestRun?.output;
  const confidence = output?.confidence;

  return (
    <div className="bg-[#1a1f2e] rounded-lg border border-[#2a3044] border-l-4 border-l-[#f59e0b] p-5 space-y-3">
      {/* Header */}
      <div className="flex items-start justify-between">
        <h2 className="text-base font-semibold text-[#e8edf5] flex items-center gap-2">
          🤖 POSITIONING ADVISOR
        </h2>
        {latestRun && (
          <span className="text-xs text-[#7b8aab]">
            Last run: {timeAgo(latestRun.run_timestamp)}
          </span>
        )}
      </div>

      {latestRun && output ? (
        <>
          {/* Summary */}
          <p className="text-sm text-[#c4cfe8] leading-relaxed">
            {output.summary ?? output.positioning_note ?? "—"}
          </p>

          {/* Confidence + flags */}
          <div className="flex items-center justify-between pt-1 border-t border-[#1e2535]">
            {confidence !== undefined && (
              <div className="flex items-center gap-2">
                <span className="text-xs text-[#7b8aab] uppercase tracking-wide">
                  Confidence
                </span>
                <span
                  className={`text-xs font-semibold tabular-nums ${
                    confidence >= 0.7
                      ? "text-[#22c55e]"
                      : confidence >= 0.5
                        ? "text-[#f59e0b]"
                        : "text-[#ef4444]"
                  }`}
                >
                  {(confidence * 100).toFixed(0)}%
                </span>
              </div>
            )}
            {output.divergence_flag && (
              <span className="text-xs text-[#f59e0b]">
                ⚠ {output.divergence_magnitude ?? "Divergence"} flag
              </span>
            )}
          </div>
        </>
      ) : (
        <div className="text-sm text-[#4a5568] italic">
          No agent run yet &mdash; trigger a run via the Agents page.
        </div>
      )}
    </div>
  );
}
