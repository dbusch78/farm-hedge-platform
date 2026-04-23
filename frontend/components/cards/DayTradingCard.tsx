import type { TradingModeResponse } from "@/lib/types";

interface Props {
  modeData: TradingModeResponse | null;
}

export default function DayTradingCard({ modeData }: Props) {
  const mode = modeData?.mode ?? "paper";
  const isLive = mode === "live";

  return (
    <div
      className={`bg-[#1a1f2e] rounded-lg border border-[#2a3044] border-l-4 ${
        isLive ? "border-l-[#ef4444]" : "border-l-[#22c55e]"
      } p-5 space-y-3`}
    >
      <div className="flex items-start justify-between">
        <h2 className="text-base font-semibold text-[#e8edf5] flex items-center gap-2">
          📈 DAY TRADING
        </h2>
        <ModeBadge mode={mode} />
      </div>

      <div className="grid grid-cols-2 gap-3">
        <div>
          <p className="text-[10px] uppercase tracking-widest text-[#7b8aab] mb-1">Today P&L</p>
          <p className="text-sm font-semibold text-[#4a5568]">— (Milestone 5)</p>
        </div>
        <div>
          <p className="text-[10px] uppercase tracking-widest text-[#7b8aab] mb-1">Open Positions</p>
          <p className="text-sm font-semibold text-[#4a5568]">—</p>
        </div>
      </div>

      <div className="pt-1 border-t border-[#1e2535]">
        <button
          disabled
          className="text-xs text-[#4a5568] border border-[#2a3044] rounded px-3 py-1.5 cursor-not-allowed"
          title="Live mode toggle available in Milestone 5"
        >
          {isLive ? "Switch to Paper ▶" : "Go Live ▶"}
        </button>
        <p className="text-[10px] text-[#4a5568] mt-1">
          Full live mode toggle in Milestone 5
        </p>
      </div>
    </div>
  );
}

function ModeBadge({ mode }: { mode: "paper" | "live" }) {
  const isLive = mode === "live";
  return (
    <span
      className={`flex items-center gap-1.5 text-xs font-semibold px-2 py-0.5 rounded ${
        isLive
          ? "bg-[#ef444420] text-[#ef4444]"
          : "bg-[#22c55e20] text-[#22c55e]"
      }`}
    >
      <span className={`w-1.5 h-1.5 rounded-full ${isLive ? "bg-[#ef4444]" : "bg-[#22c55e]"}`} />
      {isLive ? "LIVE" : "PAPER"}
    </span>
  );
}
