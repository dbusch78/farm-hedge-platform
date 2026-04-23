export default function WeatherCard() {
  return (
    <div className="bg-[#1a1f2e] rounded-lg border border-[#2a3044] border-l-4 border-l-[#3b82f6] p-5 space-y-3">
      <div className="flex items-start justify-between">
        <h2 className="text-base font-semibold text-[#e8edf5] flex items-center gap-2">
          🌤 WEATHER
        </h2>
        <span className="text-xs text-[#7b8aab]">On-farm + Corn Belt</span>
      </div>
      <div className="text-sm text-[#4a5568] italic">
        Weather feeds coming in Milestone 3.
      </div>
      <div className="grid grid-cols-3 gap-3 opacity-30">
        <PlaceholderStat label="LOCAL TEMP" />
        <PlaceholderStat label="7-DAY RAIN" />
        <PlaceholderStat label="GDU TOTAL" />
      </div>
    </div>
  );
}

function PlaceholderStat({ label }: { label: string }) {
  return (
    <div>
      <p className="text-[10px] uppercase tracking-widest text-[#7b8aab] mb-1">{label}</p>
      <div className="h-4 w-12 bg-[#2a3044] rounded animate-pulse" />
    </div>
  );
}
