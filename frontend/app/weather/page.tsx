"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import AnalyticsLineChart, {
  type ChartSeries,
} from "@/components/charts/AnalyticsLineChart";
import {
  deletePlantingDate,
  getGduStatus,
  getLocalWeather,
  getLocalWeatherHistory,
  getPlantingDates,
  getRainTotals,
  getRegionalHistory,
  setPlantingDate,
} from "@/lib/api";
import type { GduStatus, PlantingDate, RainTotals, WeatherLocal, WeatherRegional } from "@/lib/types";

// ── Unit helpers ──────────────────────────────────────────────────────────────

const cToF = (c: number | null): number | null =>
  c == null ? null : Math.round((c * 9) / 5 + 32);
const mmToIn = (mm: number | null): number | null =>
  mm == null ? null : Math.round((mm / 25.4) * 100000) / 100000;
const kmhToMph = (k: number | null): number | null =>
  k == null ? null : Math.round(k * 0.621371 * 10) / 10;

function fmtF(v: number | null, d = 0) {
  return v == null ? "—" : `${v.toFixed(d)}°F`;
}
function fmtIn(v: number | null, d = 2) {
  return v == null ? "—" : `${v.toFixed(d)}"`;
}
function fmtMph(v: number | null) {
  return v == null ? "—" : `${v.toFixed(1)} mph`;
}
function fmt(v: number | null, d = 1, u = "") {
  return v == null ? "—" : `${v.toFixed(d)}${u}`;
}

// ── Constants ─────────────────────────────────────────────────────────────────

const COMPASS = ["N","NNE","NE","ENE","E","ESE","SE","SSE","S","SSW","SW","WSW","W","WNW","NW","NNW"];
const REGIONS = ["corn_belt", "mato_grosso", "parana", "pampas"] as const;
const REGION_LABELS: Record<string, string> = {
  corn_belt:   "Corn Belt (IA)",
  mato_grosso: "Mato Grosso (BR)",
  parana:      "Paraná (BR)",
  pampas:      "Pampas (AR)",
};
const REGION_COLORS = ["#f59e0b", "#22c55e", "#3b82f6", "#a855f7"] as const;

function windDir(deg: number | null) {
  if (deg == null) return "—";
  return COMPASS[Math.round(deg / 22.5) % 16];
}

type Tab = "local" | "regional" | "gdu";

// ── Shared sub-components ─────────────────────────────────────────────────────

function DetailRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between py-1.5 border-b border-[#1e2535] last:border-0">
      <span className="text-xs text-[#7b8aab]">{label}</span>
      <span className="text-xs text-[#e8edf5] font-medium tabular-nums">{value}</span>
    </div>
  );
}

function DateSlider({
  dates,
  sliderIdx,
  onChange,
}: {
  dates: string[];
  sliderIdx: number;
  onChange: (i: number) => void;
}) {
  if (dates.length === 0) return null;
  const displayDate = new Date(dates[sliderIdx] + "T12:00:00Z").toLocaleDateString("en-US", {
    weekday: "short", month: "short", day: "numeric", year: "numeric",
  });
  return (
    <div className="space-y-1">
      <div className="flex justify-between text-[10px] text-[#4a5568]">
        <span>{new Date(dates[0] + "T12:00:00Z").toLocaleDateString("en-US", { month: "short", day: "numeric" })}</span>
        <span className="text-[#e8edf5] text-xs font-medium">{displayDate}</span>
        <span>{new Date(dates[dates.length - 1] + "T12:00:00Z").toLocaleDateString("en-US", { month: "short", day: "numeric" })}</span>
      </div>
      <input
        type="range"
        min={0}
        max={Math.max(0, dates.length - 1)}
        value={sliderIdx}
        onChange={(e) => onChange(Number(e.target.value))}
        className="w-full accent-[#3b82f6] h-1.5"
      />
    </div>
  );
}

// ── Local station date slider view ────────────────────────────────────────────

function LocalHistorySlider({ history }: { history: WeatherLocal[] }) {
  // Group by calendar day, take last record per day
  const byDate = useMemo(() => {
    const map: Record<string, WeatherLocal> = {};
    for (const row of history) {
      map[row.time.slice(0, 10)] = row;
    }
    return map;
  }, [history]);

  const dates = useMemo(() => Object.keys(byDate).sort(), [byDate]);
  const [sliderIdx, setSliderIdx] = useState(() => Math.max(0, dates.length - 1));
  useEffect(() => { setSliderIdx(Math.max(0, dates.length - 1)); }, [dates.length]);

  if (dates.length === 0) return null;
  const snap = byDate[dates[sliderIdx]];

  return (
    <div className="bg-[#141920] rounded-lg border border-[#2a3044] p-4 space-y-3">
      <p className="text-xs text-[#7b8aab] uppercase tracking-wider">Daily Snapshot</p>
      <DateSlider dates={dates} sliderIdx={sliderIdx} onChange={setSliderIdx} />
      <div className="grid grid-cols-2 sm:grid-cols-3 gap-4 pt-1">
        <div>
          <p className="text-[9px] uppercase tracking-widest text-[#7b8aab] mb-0.5">Temperature</p>
          <p className="text-sm font-semibold text-[#e8edf5]">{fmtF(snap.temp_f)}</p>
          <p className="text-[10px] text-[#4a5568]">Dew {fmtF(snap.dew_point_f)} · RH {fmt(snap.humidity, 0, "%")}</p>
        </div>
        <div>
          <p className="text-[9px] uppercase tracking-widest text-[#7b8aab] mb-0.5">Wind</p>
          <p className="text-sm font-semibold text-[#e8edf5]">{fmt(snap.wind_speed, 1)} mph {windDir(snap.wind_dir)}</p>
          {snap.wind_gust_mph != null && <p className="text-[10px] text-[#4a5568]">Gust {snap.wind_gust_mph.toFixed(1)} mph</p>}
        </div>
        <div>
          <p className="text-[9px] uppercase tracking-widest text-[#7b8aab] mb-0.5">Rain (day)</p>
          <p className="text-sm font-semibold text-[#e8edf5]">{fmtIn(snap.rain_daily)}</p>
          <p className="text-[10px] text-[#4a5568]">{fmtIn(snap.rain_hourly, 3)} last hour</p>
        </div>
        <div>
          <p className="text-[9px] uppercase tracking-widest text-[#7b8aab] mb-0.5">Solar</p>
          <p className="text-sm font-semibold text-[#e8edf5]">{fmt(snap.solar_rad, 0, " W/m²")}</p>
          {snap.uv_index != null && <p className="text-[10px] text-[#4a5568]">UV {snap.uv_index}</p>}
        </div>
        <div>
          <p className="text-[9px] uppercase tracking-widest text-[#7b8aab] mb-0.5">Barometer</p>
          <p className="text-sm font-semibold text-[#e8edf5]">{fmt(snap.baro_rel, 2, " inHg")}</p>
        </div>
        {(snap.lightning_day ?? 0) > 0 && (
          <div>
            <p className="text-[9px] uppercase tracking-widest text-[#7b8aab] mb-0.5">Lightning</p>
            <p className="text-sm font-semibold text-[#f59e0b]">{snap.lightning_day} strike{snap.lightning_day !== 1 ? "s" : ""}</p>
            {snap.lightning_distance_mi != null && <p className="text-[10px] text-[#4a5568]">nearest {snap.lightning_distance_mi.toFixed(1)} mi</p>}
          </div>
        )}
      </div>
    </div>
  );
}

// ── Regional History view ─────────────────────────────────────────────────────

function RegionSnapshot({ data }: { data: WeatherRegional | undefined }) {
  if (!data) return <p className="text-xs text-[#4a5568] italic">No data for this date</p>;
  return (
    <div className="space-y-0">
      <DetailRow label="Temperature" value={fmtF(cToF(data.temp_c))} />
      <DetailRow label="Precipitation" value={fmtIn(mmToIn(data.precip_mm), 3)} />
      <DetailRow label="Soil Moisture" value={data.soil_moisture != null ? `${(data.soil_moisture * 100).toFixed(0)}%` : "—"} />
      <DetailRow label="ET₀" value={fmtIn(mmToIn(data.et0), 3)} />
      <DetailRow label="Wind (10m)" value={fmtMph(kmhToMph(data.wind_speed_10m))} />
    </div>
  );
}

function RegionalHistoryView({ history }: { history: WeatherRegional[] }) {
  // Group by date (YYYY-MM-DD), take last record per region per day
  const byDate = useMemo(() => {
    const map: Record<string, Record<string, WeatherRegional>> = {};
    for (const row of history) {
      const day = row.time.slice(0, 10);
      if (!map[day]) map[day] = {};
      map[day][row.region] = row;
    }
    return map;
  }, [history]);

  const dates = useMemo(() => Object.keys(byDate).sort(), [byDate]);
  const [sliderIdx, setSliderIdx] = useState(() => Math.max(0, dates.length - 1));
  useEffect(() => { setSliderIdx(Math.max(0, dates.length - 1)); }, [dates.length]);

  // Monthly rain totals per region: group by YYYY-MM, sum daily precip (one max per day)
  const monthlyRain = useMemo(() => {
    // dailyPrecip[region][YYYY-MM-DD] = max precip_mm for that day
    const daily: Record<string, Record<string, number>> = {};
    for (const row of history) {
      if (row.precip_mm == null) continue;
      const day = row.time.slice(0, 10);
      if (!daily[row.region]) daily[row.region] = {};
      daily[row.region][day] = Math.max(daily[row.region][day] ?? 0, row.precip_mm);
    }
    // Sum by month per region
    const monthly: Record<string, Record<string, number>> = {};
    for (const region of Object.keys(daily)) {
      monthly[region] = {};
      for (const [day, mm] of Object.entries(daily[region])) {
        const month = day.slice(0, 7); // YYYY-MM
        monthly[region][month] = (monthly[region][month] ?? 0) + mm;
      }
    }
    // Collect sorted month keys
    const months = [...new Set(Object.values(monthly).flatMap((m) => Object.keys(m)))].sort();
    return { monthly, months };
  }, [history]);

  if (dates.length === 0) {
    return (
      <div className="space-y-3">
        <p className="text-sm text-[#4a5568] italic">
          No regional history yet. Run the ERA5 backfill to load up to 180 days:
        </p>
        <code className="block text-xs text-[#7b8aab] bg-[#141920] border border-[#2a3044] rounded px-3 py-2">
          docker compose exec fastapi python scripts/backfill_openmeteo.py
        </code>
      </div>
    );
  }

  const snapshot = byDate[dates[sliderIdx]] ?? {};

  return (
    <div className="space-y-6">
      {/* Date slider */}
      <DateSlider dates={dates} sliderIdx={sliderIdx} onChange={setSliderIdx} />

      {/* Snapshot cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        {REGIONS.map((r) => (
          <div key={r} className="bg-[#141920] rounded-lg border border-[#2a3044] p-4">
            <p className="text-xs text-[#7b8aab] uppercase tracking-wider mb-3">{REGION_LABELS[r]}</p>
            <RegionSnapshot data={snapshot[r]} />
          </div>
        ))}
      </div>

      {/* Trend charts */}
      <p className="text-xs text-[#7b8aab] pt-1">Temperature trends (°F) — click legend to toggle regions</p>
      <AnalyticsLineChart
        series={REGIONS.map((r, i) => ({
          key: r,
          label: REGION_LABELS[r],
          color: REGION_COLORS[i],
          data: history
            .filter((row) => row.region === r && row.temp_c != null)
            .map((row) => ({ time: row.time, value: cToF(row.temp_c)! })),
        }))}
        height={220}
        emptyMessage="Temperature trend data builds up over time."
      />
      <p className="text-xs text-[#7b8aab]">Precipitation (inches) — click legend to toggle regions</p>
      <AnalyticsLineChart
        series={REGIONS.map((r, i) => ({
          key: r,
          label: REGION_LABELS[r],
          color: REGION_COLORS[i],
          data: history
            .filter((row) => row.region === r && row.precip_mm != null)
            .map((row) => ({ time: row.time, value: mmToIn(row.precip_mm)! })),
        }))}
        height={180}
        emptyMessage="Precipitation trend data builds up over time."
      />

      {/* Monthly rain totals table */}
      {monthlyRain.months.length > 0 && (
        <div className="bg-[#141920] rounded-lg border border-[#2a3044] p-4">
          <p className="text-xs text-[#7b8aab] uppercase tracking-wider mb-3">Monthly Rain Totals (inches)</p>
          <div className="overflow-x-auto">
            <table className="w-full text-xs min-w-[400px]">
              <thead>
                <tr className="text-[#4a5568] text-left">
                  <th className="pb-2 font-normal pr-4">Month</th>
                  {REGIONS.map((r) => (
                    <th key={r} className="pb-2 font-normal pr-4" style={{ color: REGION_COLORS[REGIONS.indexOf(r)] }}>
                      {REGION_LABELS[r].split(" ")[0]}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {monthlyRain.months.map((month) => {
                  const [y, m] = month.split("-");
                  const label = new Date(Number(y), Number(m) - 1, 1).toLocaleDateString("en-US", {
                    month: "short", year: "numeric",
                  });
                  return (
                    <tr key={month} className="border-t border-[#1e2535]">
                      <td className="py-1.5 pr-4 text-[#7b8aab]">{label}</td>
                      {REGIONS.map((r) => {
                        const mm = monthlyRain.monthly[r]?.[month];
                        return (
                          <td key={r} className="py-1.5 pr-4 text-[#e8edf5] tabular-nums">
                            {mm != null ? `${(mm / 25.4).toFixed(2)}"` : "—"}
                          </td>
                        );
                      })}
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}

// ── Cumulative 7-day rain computation ─────────────────────────────────────────

function buildRainSeries(history: WeatherLocal[]): { hourly: ChartSeries; cumulative: ChartSeries } {
  // Per-day totals (max rain_daily per calendar day = that day's total inches)
  const dailyMap = new Map<string, number>();
  for (const r of history) {
    if (r.rain_daily == null) continue;
    const day = r.time.slice(0, 10);
    dailyMap.set(day, Math.max(dailyMap.get(day) ?? 0, r.rain_daily));
  }
  const sortedDays = [...dailyMap.keys()].sort();

  // For each data point: cumulative = sum of completed prior days + current rain_daily
  const cumulativeData = history
    .filter((r) => r.rain_daily != null)
    .map((r) => {
      const day = r.time.slice(0, 10);
      const dayIdx = sortedDays.indexOf(day);
      const priorTotal = sortedDays
        .slice(0, dayIdx)
        .reduce((sum, d) => sum + (dailyMap.get(d) ?? 0), 0);
      return { time: r.time, value: Math.round((priorTotal + r.rain_daily!) * 1000) / 1000 };
    });

  return {
    hourly: {
      key: "rain_hourly",
      label: "Hourly Rain (in)",
      color: "#22c55e",
      data: history.filter((r) => r.rain_hourly != null).map((r) => ({ time: r.time, value: r.rain_hourly! })),
    },
    cumulative: {
      key: "rain_cumulative",
      label: "7-day Total (in)",
      color: "#3b82f6",
      dashed: true,
      data: cumulativeData,
    },
  };
}

// ── Main page ─────────────────────────────────────────────────────────────────

export default function WeatherPage() {
  const [tab, setTab] = useState<Tab>("local");
  const [current, setCurrent] = useState<WeatherLocal | null>(null);
  const [rain, setRain] = useState<RainTotals | null>(null);
  const [history, setHistory] = useState<WeatherLocal[]>([]);
  const [regionalHistory, setRegionalHistory] = useState<WeatherRegional[]>([]);
  const [gdu, setGdu] = useState<GduStatus | null>(null);
  const [plantingDates, setPlantingDates] = useState<PlantingDate[]>([]);
  const [loading, setLoading] = useState(true);
  const [plantingForm, setPlantingForm] = useState<{ commodity: string; year: string; date: string; notes: string }>({
    commodity: "corn", year: String(new Date().getFullYear()), date: "", notes: "",
  });
  const [plantingSaving, setPlantingSaving] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    const [localRes, histRes, rainRes, gduRes, regHistRes, plantRes] = await Promise.allSettled([
      getLocalWeather(),
      getLocalWeatherHistory(30),   // expanded to 30 days for the slider
      getRainTotals(),
      getGduStatus(),
      getRegionalHistory(180),
      getPlantingDates(),
    ]);
    if (localRes.status === "fulfilled") setCurrent(localRes.value);
    if (histRes.status === "fulfilled") setHistory(histRes.value);
    if (rainRes.status === "fulfilled") setRain(rainRes.value);
    if (gduRes.status === "fulfilled") setGdu(gduRes.value);
    if (regHistRes.status === "fulfilled") setRegionalHistory(regHistRes.value);
    if (plantRes.status === "fulfilled") setPlantingDates(plantRes.value);
    setLoading(false);
  }, []);

  useEffect(() => { load(); }, [load]);

  // Last 7 days of history for the rain/temp charts
  const recentHistory = useMemo(() => {
    const cutoff = Date.now() - 7 * 24 * 60 * 60 * 1000;
    return history.filter((r) => new Date(r.time).getTime() >= cutoff);
  }, [history]);

  const tempSeries: ChartSeries[] = [
    {
      key: "temp",
      label: "Temp (°F)",
      color: "#f59e0b",
      data: recentHistory.filter((r) => r.temp_f != null).map((r) => ({ time: r.time, value: r.temp_f! })),
    },
    {
      key: "dew",
      label: "Dew Pt (°F)",
      color: "#3b82f6",
      dashed: true,
      data: recentHistory.filter((r) => r.dew_point_f != null).map((r) => ({ time: r.time, value: r.dew_point_f! })),
    },
  ];

  const rainSeries = useMemo(() => buildRainSeries(recentHistory), [recentHistory]);

  const hasLightning = (current?.lightning_day ?? 0) > 0;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-lg font-semibold text-[#e8edf5]">Weather</h1>
        {current && (
          <span className="text-xs text-[#7b8aab]">
            Updated {new Date(current.time).toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit" })}
          </span>
        )}
      </div>

      {hasLightning && (
        <div className="flex items-center gap-2 bg-[#f59e0b15] border border-[#f59e0b40] rounded px-3 py-2 text-sm text-[#f59e0b]">
          ⚡ {current!.lightning_day} lightning strike{current!.lightning_day !== 1 ? "s" : ""} today
          {current!.lightning_distance_mi != null && (
            <span className="text-[#f59e0b80] text-xs">· nearest {current!.lightning_distance_mi.toFixed(1)} mi away</span>
          )}
        </div>
      )}

      {/* Tabs */}
      <div className="flex gap-1 border-b border-[#1e2535]">
        {([
          { id: "local",    label: "Local Station" },
          { id: "regional", label: "Regional / SA" },
          { id: "gdu",      label: "GDU" },
        ] as { id: Tab; label: string }[]).map(({ id, label }) => (
          <button key={id} onClick={() => setTab(id)}
            className={`px-4 py-2 text-sm transition-colors border-b-2 -mb-px ${
              tab === id
                ? "border-[#3b82f6] text-[#e8edf5]"
                : "border-transparent text-[#7b8aab] hover:text-[#e8edf5]"
            }`}
          >{label}</button>
        ))}
      </div>

      {loading ? (
        <p className="text-sm text-[#4a5568]">Loading…</p>
      ) : (
        <>
          {/* ── Local Station ── */}
          {tab === "local" && (
            <div className="space-y-6">
              {current == null ? (
                <div className="space-y-3">
                  <p className="text-sm text-[#4a5568] italic">
                    No data yet. Run the backfill to load historical data:
                  </p>
                  <code className="block text-xs text-[#7b8aab] bg-[#141920] border border-[#2a3044] rounded px-3 py-2">
                    docker compose exec fastapi python scripts/backfill_ambient.py
                  </code>
                  <p className="text-xs text-[#4a5568]">
                    Or wait — live data will appear within 5 minutes once the ambient feed runs.
                  </p>
                </div>
              ) : (
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  <div className="bg-[#141920] rounded-lg border border-[#2a3044] p-4">
                    <p className="text-xs text-[#7b8aab] uppercase tracking-wider mb-3">Temperature &amp; Humidity</p>
                    <DetailRow label="Temperature"  value={fmtF(current.temp_f)} />
                    <DetailRow label="Humidity"     value={fmt(current.humidity, 0, "%")} />
                    <DetailRow label="Dew Point"    value={fmtF(current.dew_point_f)} />
                    <DetailRow label="Barometer"    value={fmt(current.baro_rel, 2, " inHg")} />
                  </div>
                  <div className="bg-[#141920] rounded-lg border border-[#2a3044] p-4">
                    <p className="text-xs text-[#7b8aab] uppercase tracking-wider mb-3">Wind &amp; Precip</p>
                    <DetailRow label="Wind (10-min avg)"    value={`${fmt(current.wind_speed, 1)} mph`} />
                    <DetailRow label="Direction"            value={windDir(current.wind_dir)} />
                    <DetailRow label="Gust"                 value={`${fmt(current.wind_gust_mph, 1)} mph`} />
                    <DetailRow label="Rain (hourly)"        value={fmtIn(current.rain_hourly, 3)} />
                    <DetailRow label="Rain (today)"         value={fmtIn(current.rain_daily)} />
                    {rain && <>
                      <DetailRow label="Rain (month-to-date)" value={rain.mtd_in != null ? fmtIn(rain.mtd_in) : "—"} />
                      <DetailRow label="Rain (year-to-date)"  value={rain.ytd_in != null ? fmtIn(rain.ytd_in) : "—"} />
                    </>}
                  </div>
                  <div className="bg-[#141920] rounded-lg border border-[#2a3044] p-4">
                    <p className="text-xs text-[#7b8aab] uppercase tracking-wider mb-3">Solar &amp; Radiation</p>
                    <DetailRow label="Solar Radiation" value={fmt(current.solar_rad, 0, " W/m²")} />
                    <DetailRow label="UV Index"        value={fmt(current.uv_index, 0)} />
                  </div>
                  {(current.lightning_day ?? 0) > 0 && (
                    <div className="bg-[#f59e0b10] rounded-lg border border-[#f59e0b40] p-4">
                      <p className="text-xs text-[#f59e0b] uppercase tracking-wider mb-3">Lightning</p>
                      <DetailRow label="Strikes today"  value={String(current.lightning_day ?? 0)} />
                      <DetailRow label="Nearest strike" value={`${fmt(current.lightning_distance_mi, 1)} mi`} />
                    </div>
                  )}
                </div>
              )}

              {/* 30-day date slider */}
              {history.length > 0 && <LocalHistorySlider history={history} />}

              {/* Charts — last 7 days */}
              <div className="space-y-4">
                <p className="text-xs text-[#7b8aab]">7-day temperature &amp; dew point (°F) — click legend to toggle</p>
                <AnalyticsLineChart series={tempSeries} height={240}
                  emptyMessage="Temperature history appears after backfill or a few hours of live polling." />
                <p className="text-xs text-[#7b8aab]">7-day rainfall — hourly + running total (inches) — click legend to toggle</p>
                <AnalyticsLineChart
                  series={[rainSeries.hourly, rainSeries.cumulative]}
                  height={180}
                  emptyMessage="Rain history appears after backfill or a few hours of live polling."
                />
              </div>
            </div>
          )}

          {/* ── Regional / SA ── */}
          {tab === "regional" && (
            <RegionalHistoryView history={regionalHistory} />
          )}

          {/* ── GDU ── */}
          {tab === "gdu" && (
            <div className="space-y-6">
              {gdu == null ? (
                <p className="text-sm text-[#4a5568] italic">
                  GDU data will appear once local weather polling has run for at least one day.
                  Run the backfill script to populate immediately.
                </p>
              ) : (
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  {([
                    { key: "corn" as const,  label: "Corn",     color: "text-[#a3e635]", icon: "🌽" },
                    { key: "beans" as const, label: "Soybeans", color: "text-[#3b82f6]", icon: "🌱" },
                  ]).map(({ key, label, color, icon }) => {
                    const g = gdu[key];
                    return (
                      <div key={key} className="bg-[#141920] rounded-lg border border-[#2a3044] p-4">
                        <p className="text-xs text-[#7b8aab] uppercase tracking-wider mb-3">
                          {icon} {label} GDU
                        </p>
                        <p className={`text-3xl font-bold tabular-nums mb-1 ${color}`}>
                          {g.cumulative_gdu.toLocaleString()}
                        </p>
                        <p className="text-xs text-[#7b8aab]">cumulative from planting</p>
                        <div className="mt-3">
                          <DetailRow label="Today's GDU"  value={`+${g.today_gdu}`} />
                          <DetailRow label="Days tracked" value={String(g.days_tracked)} />
                          <DetailRow label="Planting date" value={
                            new Date(g.planting_date + "T12:00:00").toLocaleDateString("en-US", {
                              month: "short", day: "numeric", year: "numeric",
                            })
                          } />
                        </div>
                        <p className="text-[10px] text-[#4a5568] mt-3">
                          Formula: base 50°F · GDU = max((max+min)/2 − 50, 0)
                        </p>
                      </div>
                    );
                  })}
                </div>
              )}

              {/* Planting date records & management */}
              <div className="bg-[#141920] rounded-lg border border-[#2a3044] p-4 space-y-4">
                <p className="text-xs text-[#7b8aab] uppercase tracking-wider">Planting Date Records</p>

                {plantingDates.length === 0 ? (
                  <p className="text-xs text-[#4a5568] italic">No planting dates recorded yet.</p>
                ) : (
                  <table className="w-full text-xs">
                    <thead>
                      <tr className="text-[#4a5568] text-left">
                        <th className="pb-1 font-normal">Crop</th>
                        <th className="pb-1 font-normal">Year</th>
                        <th className="pb-1 font-normal">Planted</th>
                        <th className="pb-1 font-normal">Notes</th>
                        <th className="pb-1 font-normal"></th>
                      </tr>
                    </thead>
                    <tbody>
                      {plantingDates.map((p) => (
                        <tr key={`${p.commodity}-${p.year}`} className="border-t border-[#1e2535]">
                          <td className="py-1.5 text-[#e8edf5] capitalize">{p.commodity}</td>
                          <td className="py-1.5 text-[#e8edf5]">{p.year}</td>
                          <td className="py-1.5 text-[#e8edf5] tabular-nums">
                            {new Date(p.planted_date + "T12:00:00").toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" })}
                          </td>
                          <td className="py-1.5 text-[#7b8aab]">{p.notes ?? ""}</td>
                          <td className="py-1.5 text-right">
                            <button
                              onClick={async () => {
                                await deletePlantingDate(p.commodity, p.year);
                                setPlantingDates((d) => d.filter((x) => !(x.commodity === p.commodity && x.year === p.year)));
                              }}
                              className="text-[#ef4444] hover:text-red-300 text-[10px]"
                            >
                              Remove
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}

                {/* Add / update form */}
                <div className="pt-2 border-t border-[#1e2535]">
                  <p className="text-[10px] text-[#4a5568] mb-2">Add or update a planting date</p>
                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 items-end">
                    <div>
                      <label className="text-[9px] uppercase tracking-widest text-[#7b8aab] block mb-0.5">Crop</label>
                      <select
                        value={plantingForm.commodity}
                        onChange={(e) => setPlantingForm((f) => ({ ...f, commodity: e.target.value }))}
                        className="w-full bg-[#0d1117] border border-[#2a3044] rounded px-2 py-1 text-xs text-[#e8edf5]"
                      >
                        <option value="corn">Corn</option>
                        <option value="beans">Soybeans</option>
                      </select>
                    </div>
                    <div>
                      <label className="text-[9px] uppercase tracking-widest text-[#7b8aab] block mb-0.5">Year</label>
                      <input
                        type="number"
                        value={plantingForm.year}
                        onChange={(e) => setPlantingForm((f) => ({ ...f, year: e.target.value }))}
                        className="w-full bg-[#0d1117] border border-[#2a3044] rounded px-2 py-1 text-xs text-[#e8edf5]"
                        min={2020}
                        max={2040}
                      />
                    </div>
                    <div>
                      <label className="text-[9px] uppercase tracking-widest text-[#7b8aab] block mb-0.5">Date</label>
                      <input
                        type="date"
                        value={plantingForm.date}
                        onChange={(e) => setPlantingForm((f) => ({ ...f, date: e.target.value }))}
                        className="w-full bg-[#0d1117] border border-[#2a3044] rounded px-2 py-1 text-xs text-[#e8edf5]"
                      />
                    </div>
                    <div>
                      <label className="text-[9px] uppercase tracking-widest text-[#7b8aab] block mb-0.5">Notes</label>
                      <input
                        type="text"
                        value={plantingForm.notes}
                        onChange={(e) => setPlantingForm((f) => ({ ...f, notes: e.target.value }))}
                        placeholder="optional"
                        className="w-full bg-[#0d1117] border border-[#2a3044] rounded px-2 py-1 text-xs text-[#e8edf5] placeholder-[#4a5568]"
                      />
                    </div>
                  </div>
                  <button
                    disabled={!plantingForm.date || plantingSaving}
                    onClick={async () => {
                      if (!plantingForm.date) return;
                      setPlantingSaving(true);
                      try {
                        await setPlantingDate(
                          plantingForm.commodity,
                          Number(plantingForm.year),
                          plantingForm.date,
                          plantingForm.notes || undefined,
                        );
                        const updated = await getPlantingDates();
                        setPlantingDates(updated);
                        setPlantingForm((f) => ({ ...f, date: "", notes: "" }));
                      } finally {
                        setPlantingSaving(false);
                      }
                    }}
                    className="mt-2 px-4 py-1.5 text-xs bg-[#3b82f6] text-white rounded disabled:opacity-40 hover:bg-[#2563eb] transition-colors"
                  >
                    {plantingSaving ? "Saving…" : "Save"}
                  </button>
                </div>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}
