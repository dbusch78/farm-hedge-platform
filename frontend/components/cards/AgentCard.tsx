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

function wasdeCountdown(): number {
  const now = new Date();
  const year = now.getUTCFullYear();
  const month = now.getUTCMonth();
  const day = now.getUTCDate();
  let targetMonth = month;
  let targetYear = year;
  if (day >= 10) {
    targetMonth = month + 1;
    if (targetMonth > 11) { targetMonth = 0; targetYear++; }
  }
  const next10th = new Date(Date.UTC(targetYear, targetMonth, 10));
  return Math.ceil((next10th.getTime() - Date.now()) / 86_400_000);
}

export default function AgentCard({ latestRun }: Props) {
  const output = latestRun?.output;
  const confidence = output?.confidence as number | undefined;
  const daysToWasde = wasdeCountdown();

  return (
    <div className="bg-[#1a1f2e] rounded-lg border border-[#2a3044] border-l-4 border-l-[#f59e0b] p-5 space-y-3">
      <div className="flex items-start justify-between">
        <h2 className="text-base font-semibold text-[#e8edf5] flex items-center gap-2">
          🤖 POSITIONING ADVISOR
        </h2>
        <div className="flex flex-col items-end gap-1">
          {latestRun && (
            <span className="text-xs text-[#7b8aab]">
              Last run: {timeAgo(latestRun.run_timestamp)}
            </span>
          )}
          <span className="text-[10px] text-[#f59e0b]">
            ⚠️ WASDE in {daysToWasde}d
          </span>
        </div>
      </div>

      {latestRun && output ? (
        <>
          <p className="text-sm text-[#c4cfe8] leading-relaxed">
            {(output.positioning_note as string | undefined) ??
             (output.summary as string | undefined) ??
             "—"}
          </p>
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
            {(output.divergence_flag as boolean | undefined) && (
              <span className="text-xs text-[#f59e0b]">
                ⚠ {(output.divergence_magnitude as string | undefined) ?? "Divergence"} flag
              </span>
            )}
            <a href="/agents" className="text-xs text-[#3b82f6] hover:underline">
              View history →
            </a>
          </div>
        </>
      ) : (
        <div className="space-y-2">
          <p className="text-sm text-[#4a5568] italic">
            No agent run yet — trigger a run via the Agents page.
          </p>
          <a href="/agents" className="text-xs text-[#3b82f6] hover:underline">
            Go to Agents →
          </a>
        </div>
      )}
    </div>
  );
}
