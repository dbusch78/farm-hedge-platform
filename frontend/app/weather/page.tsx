"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import AnalyticsLineChart, {
  type ChartSeries,
} from "@/components/charts/AnalyticsLineChart";
import {
  getGduStatus,
  getLocalWeather,
  getLocalWeatherHistory,
  getRegionalHistory,
  getRegionalWeather,
} from "@/lib/api";
import type { GduStatus, WeatherLocal, WeatherRegional } from "@/lib/types";

// ── Unit helpers ──────────────────────────────────────────────────────────────

const cToF = (c: number | null): number | null =>
  c == null ? null : Math.round((c * 9) / 5 + 32);
const mmToIn = (mm: number | null): number | null =>
  mm == null ? null : Math.round((mm / 25.4) * 1000) / 1000;
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

function windDir(deg: number | null) {
  if (deg == null) return "—";
  return COMPASS[Math.round(deg / 22.5) % 16];
}

type Tab = "local" | "regional" | "gdu";

// ── Sub-components ────────────────────────────────────────────────────────────

function DetailRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between py-1.5 border-b border-[#1e2535] last:border-0">
      <span className="text-xs text-[#7b8aab]">{label}</span>
      <span className="text-xs text-[#e8edf5] font-medium tabular-nums">{value}</span>
    </div>
  );
}

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

// ── Regional History Slider ────────────────────────────────────────────────────

function RegionalHistoryView({ history }: { history: WeatherRegional[] }) {
  // Group by date (YYYY-MM-DD), take the last record per region per day
  const byDate = useMemo(() => {
    const map: Record<string, Record<string, WeatherRegional>> = {};
    for (const row of history) {
      const day = row.time.slice(0, 10);
      if (!map[day]) map[day] = {};
      map[day][row.region] = row; // later records overwrite earlier ones
    }
    return map;
  }, [history]);

  const dates = useMemo(() => Object.keys(byDate).sort(), [byDate]);

  const [sliderIdx, setSliderIdx] = useState(() => Math.max(0, dates.length - 1));

  // Keep slider at end when new dates load
  useEffect(() => {
    setSliderIdx(Math.max(0, dates.length - 1));
  }, [dates.length]);

  if (dates.length === 0) {
    return (
      <p className="text-sm text-[#4a5568] italic">
        Regional history will populate after the Open-Meteo feed runs for several days.
        Back-fill is not available for regional data (Open-Meteo only provides current
        conditions; history builds up naturally over time).
      </p>
    );
  }

  const selectedDate = dates[sliderIdx];
  const snapshot = byDate[selectedDate] ?? {};

  const displayDate = new Date(selectedDate + "T12:00:00Z").toLocaleDateString("en-US", {
    weekday: "short", month: "short", day: "numeric", year: "numeric",
  });

  return (
    <div className="space-y-4">
      {/* Slider */}
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
          onChange={(e) => setSliderIdx(Number(e.target.value))}
          className="w-full accent-[#3b82f6] h-1.5"
        />
      </div>

      {/* Snapshot cards for selected date */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        {REGIONS.map((r) => (
          <div key={r} className="bg-[#141920] rounded-lg border border-[#2a3044] p-4">
            <p className="text-xs text-[#7b8aab] uppercase tracking-wider mb-3">
              {REGION_LABELS[r]}
            </p>
            <RegionSnapshot data={snapshot[r]} />
          </div>
        ))}
      </div>

      {/* Trend charts */}
      <p className="text-xs text-[#7b8aab] pt-2">Temperature trends (°F) — growing season</p>
      <AnalyticsLineChart
        series={REGIONS.map((r, i) => {
          const colors = ["#f59e0b", "#22c55e", "#3b82f6", "#a855f7"];
          return {
            key: r,
            label: REGION_LABELS[r],
            color: colors[i],
            data: history
              .filter((row) => row.region === r && row.temp_c != null)
              .map((row) => ({ time: row.time, value: cToF(row.temp_c)! })),
          };
        })}
        height={220}
        emptyMessage="Temperature trend data builds up over time."
      />
      <p className="text-xs text-[#7b8aab]">Precipitation (inches) — growing season</p>
      <AnalyticsLineChart
        series={REGIONS.map((r, i) => {
          const colors = ["#f59e0b", "#22c55e", "#3b82f6", "#a855f7"];
          return {
            key: r,
            label: REGION_LABELS[r],
            color: colors[i],
            data: history
              .filter((row) => row.region === r && row.precip_mm != null)
              .map((row) => ({ time: row.time, value: mmToIn(row.precip_mm)! })),
          };
        })}
        height={180}
        emptyMessage="Precipitation trend data builds up over time."
      />
    </div>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────

export default function WeatherPage() {
  const [tab, setTab] = useState<Tab>("local");
  const [current, setCurrent] = useState<WeatherLocal | null>(null);
  const [history, setHistory] = useState<WeatherLocal[]>([]);
  const [regionalHistory, setRegionalHistory] = useState<WeatherRegional[]>([]);
  const [gdu, setGdu] = useState<GduStatus | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    const [localRes, histRes, gduRes, regHistRes] = await Promise.allSettled([
      getLocalWeather(),
      getLocalWeatherHistory(7),
      getGduStatus(),
      getRegionalHistory(180),
    ]);
    if (localRes.status === "fulfilled") setCurrent(localRes.value);
    if (histRes.status === "fulfilled") setHistory(histRes.value);
    if (gduRes.status === "fulfilled") setGdu(gduRes.value);
    if (regHistRes.status === "fulfilled") setRegionalHistory(regHistRes.value);
    setLoading(false);
  }, []);

  useEffect(() => { load(); }, [load]);

  const tempSeries: ChartSeries[] = [
    {
      key: "temp",
      label: "Temp (°F)",
      color: "#f59e0b",
      data: history.filter((r) => r.temp_f != null).map((r) => ({ time: r.time, value: r.temp_f! })),
    },
    {
      key: "dew",
      label: "Dew Pt (°F)",
      color: "#3b82f6",
      dashed: true,
      data: history.filter((r) => r.dew_point_f != null).map((r) => ({ time: r.time, value: r.dew_point_f! })),
    },
  ];

  const rainSeries: ChartSeries[] = [
    {
      key: "rain",
      label: "Hourly Rain (in)",
      color: "#22c55e",
      data: history.filter((r) => r.rain_hourly != null).map((r) => ({ time: r.time, value: r.rain_hourly! })),
    },
  ];

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
                    <DetailRow label="Wind (10-min avg)"  value={`${fmt(current.wind_speed, 1)} mph`} />
                    <DetailRow label="Direction"          value={windDir(current.wind_dir)} />
                    <DetailRow label="Gust"               value={`${fmt(current.wind_gust_mph, 1)} mph`} />
                    <DetailRow label="Rain (hourly)"      value={fmtIn(current.rain_hourly, 3)} />
                    <DetailRow label="Rain (today)"       value={fmtIn(current.rain_daily)} />
                  </div>
                  <div className="bg-[#141920] rounded-lg border border-[#2a3044] p-4">
                    <p className="text-xs text-[#7b8aab] uppercase tracking-wider mb-3">Solar &amp; Radiation</p>
                    <DetailRow label="Solar Radiation" value={fmt(current.solar_rad, 0, " W/m²")} />
                    <DetailRow label="UV Index"        value={fmt(current.uv_index, 0)} />
                  </div>
                  {(current.lightning_day ?? 0) > 0 && (
                    <div className="bg-[#f59e0b10] rounded-lg border border-[#f59e0b40] p-4">
                      <p className="text-xs text-[#f59e0b] uppercase tracking-wider mb-3">Lightning</p>
                      <DetailRow label="Strikes today" value={String(current.lightning_day ?? 0)} />
                      <DetailRow label="Nearest strike" value={`${fmt(current.lightning_distance_mi, 1)} mi`} />
                    </div>
                  )}
                </div>
              )}

              <div className="space-y-4">
                <p className="text-xs text-[#7b8aab]">7-day temperature &amp; dew point (°F)</p>
                <AnalyticsLineChart series={tempSeries} height={240}
                  emptyMessage="Temperature history appears after backfill or a few hours of live polling." />
                <p className="text-xs text-[#7b8aab]">7-day hourly rainfall (inches)</p>
                <AnalyticsLineChart series={rainSeries} height={160}
                  emptyMessage="Rain history appears after backfill or a few hours of live polling." />
              </div>
            </div>
          )}

          {/* ── Regional / SA ── */}
          {tab === "regional" && (
            <RegionalHistoryView history={regionalHistory} />
          )}

          {/* ── GDU ── */}
          {tab === "gdu" && (
            <div className="space-y-4">
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
                          <DetailRow label="Today's GDU" value={`+${g.today_gdu}`} />
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
            </div>
          )}
        </>
      )}
    </div>
  );
}
