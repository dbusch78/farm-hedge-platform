export default function CongressionalCard() {
  return (
    <div className="bg-[#1a1f2e] rounded-lg border border-[#2a3044] border-l-4 border-l-[#f59e0b] p-5 space-y-3">
      <div className="flex items-start justify-between">
        <h2 className="text-base font-semibold text-[#e8edf5] flex items-center gap-2">
          🏛 CONGRESSIONAL SIGNALS
        </h2>
        <span className="text-xs text-[#f59e0b]">45-day lag</span>
      </div>

      <div className="text-sm text-[#4a5568] italic">
        Congressional trade feed coming in Milestone 6.
      </div>

      <div className="text-[10px] text-[#4a5568] border border-[#1e2535] rounded px-2 py-1.5">
        ⚠ Disclosures carry up to a 45-day legal reporting lag.
        These are trailing confirmation signals, not leading ones.
      </div>
    </div>
  );
}
