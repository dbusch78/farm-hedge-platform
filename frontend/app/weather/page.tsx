"use client";

import { useCallback, useEffect, useState } from "react";
import AnalyticsLineChart, {
  type ChartSeries,
} from "@/components/charts/AnalyticsLineChart";
import {
  getGduStatus,
  getLocalWeather,
  getLocalWeatherHistory,
  getRegionalWeather,
} from "@/lib/api";
import type {
  GduStatus,
  WeatherLocal,
  WeatherRegional,
} from "@/lib/types";

type Tab = "local" | "regional" | "gdu";

const COMPASS = ["N","NNE","NE","ENE","E","ESE","SE","SSE","S","SSW","SW","WSW","W","WNW","NW","NNW"];
const REGIONS = ["corn_belt", "mato_grosso", "parana", "pampas"] as const;
const REGION_LABELS: Record<string, string> = {
  corn_belt: "Corn Belt (IA)",
  mato_grosso: "Mato Grosso (BR)",
  parana: "Paraná (BR)",
  pampas: "Pampas (AR)",
};

function windDir(deg: number | null) {
  if (deg == null) return "—";
  return COMPASS[Math.round(deg / 22.5) % 16];
}
function fmt(v: number | null, d = 1, u = "") {
  return v == null ? "—" : `${v.toFixed(d)}${u}`;
}

function DetailRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between py-1.5 border-b border-[#1e2535] last:border-0">
      <span className="text-xs text-[#7b8aab]">{label}</span>
      <span className="text-xs text-[#e8edf5] font-medium tabular-nums">{value}</span>
    </div>
  );
}

export default function WeatherPage() {
  const [tab, setTab] = useState<Tab>("local");
  const [current, setCurrent] = useState<WeatherLocal | null>(null);
  const [history, setHistory] = useState<WeatherLocal[]>([]);
  const [regional, setRegional] = useState<Record<string, WeatherRegional>>({});
  const [gdu, setGdu] = useState<GduStatus | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    const [localRes, histRes, gduRes] = await Promise.allSettled([
      getLocalWeather(),
      getLocalWeatherHistory(7),
      getGduStatus(),
    ]);
    if (localRes.status === "fulfilled") setCurrent(localRes.value);
    if (histRes.status === "fulfilled") setHistory(histRes.value);
    if (gduRes.status === "fulfilled") setGdu(gduRes.value);

    const regResults = await Promise.allSettled(
      REGIONS.map((r) => getRegionalWeather(r)),
    );
    const reg: Record<string, WeatherRegional> = {};
    REGIONS.forEach((r, i) => {
      const res = regResults[i];
      if (res.status === "fulfilled") reg[r] = res.value;
    });
    setRegional(reg);
    setLoading(false);
  }, []);

  useEffect(() => { load(); }, [load]);

  // Build temp chart series from history
  const tempSeries: ChartSeries[] = [
    {
      key: "temp",
      label: "Temp (°F)",
      color: "#f59e0b",
      data: history.filter((r) => r.temp_f != null).map((r) => ({ time: r.time, value: r.temp_f! })),
    },
    {
      key: "dew",
      label: "Dew Point (°F)",
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
          { id: "local", label: "Local Station" },
          { id: "regional", label: "Regional / SA" },
          { id: "gdu", label: "GDU" },
        ] as { id: Tab; label: string }[]).map(({ id, label }) => (
          <button key={id} onClick={() => setTab(id)}
            className={`px-4 py-2 text-sm transition-colors border-b-2 -mb-px ${
              tab === id ? "border-[#3b82f6] text-[#e8edf5]" : "border-transparent text-[#7b8aab] hover:text-[#e8edf5]"
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
                <p className="text-sm text-[#4a5568] italic">
                  No data yet — will appear after the first ambient feed poll.
                </p>
              ) : (
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  <div className="bg-[#141920] rounded-lg border border-[#2a3044] p-4">
                    <p className="text-xs text-[#7b8aab] uppercase tracking-wider mb-3">Temperature & Humidity</p>
                    <DetailRow label="Temperature" value={fmt(current.temp_f, 0, "°F")} />
                    <DetailRow label="Humidity" value={fmt(current.humidity, 0, "%")} />
                    <DetailRow label="Dew Point" value={fmt(current.dew_point_f, 0, "°F")} />
                    <DetailRow label="Barometer" value={fmt(current.baro_rel, 2, " inHg")} />
                  </div>
                  <div className="bg-[#141920] rounded-lg border border-[#2a3044] p-4">
                    <p className="text-xs text-[#7b8aab] uppercase tracking-wider mb-3">Wind & Precip</p>
                    <DetailRow label="Wind Speed (10-min avg)" value={fmt(current.wind_speed, 1, " mph")} />
                    <DetailRow label="Wind Direction" value={windDir(current.wind_dir)} />
                    <DetailRow label="Wind Gust" value={fmt(current.wind_gust_mph, 1, " mph")} />
                    <DetailRow label="Rain (hourly)" value={fmt(current.rain_hourly, 2, "\"")} />
                    <DetailRow label="Rain (today)" value={fmt(current.rain_daily, 2, "\"")} />
                  </div>
                  <div className="bg-[#141920] rounded-lg border border-[#2a3044] p-4">
                    <p className="text-xs text-[#7b8aab] uppercase tracking-wider mb-3">Solar & Radiation</p>
                    <DetailRow label="Solar Radiation" value={fmt(current.solar_rad, 0, " W/m²")} />
                    <DetailRow label="UV Index" value={fmt(current.uv_index, 0)} />
                  </div>
                  {(current.lightning_day ?? 0) > 0 && (
                    <div className="bg-[#f59e0b10] rounded-lg border border-[#f59e0b40] p-4">
                      <p className="text-xs text-[#f59e0b] uppercase tracking-wider mb-3">Lightning</p>
                      <DetailRow label="Strikes today" value={String(current.lightning_day ?? 0)} />
                      <DetailRow label="Nearest strike" value={fmt(current.lightning_distance_mi, 1, " mi")} />
                    </div>
                  )}
                </div>
              )}

              <div className="space-y-4">
                <p className="text-xs text-[#7b8aab]">7-day temperature & dew point</p>
                <AnalyticsLineChart series={tempSeries} height={240}
                  emptyMessage="Temperature history will appear after a few hours of polling." />
                <p className="text-xs text-[#7b8aab]">7-day hourly rainfall</p>
                <AnalyticsLineChart series={rainSeries} height={160}
                  emptyMessage="Rain history will appear after polling begins." />
              </div>
            </div>
          )}

          {/* ── Regional / SA ── */}
          {tab === "regional" && (
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              {REGIONS.map((r) => {
                const d = regional[r];
                return (
                  <div key={r} className="bg-[#141920] rounded-lg border border-[#2a3044] p-4">
                    <p className="text-xs text-[#7b8aab] uppercase tracking-wider mb-3">
                      {REGION_LABELS[r]}
                    </p>
                    {d == null ? (
                      <p className="text-xs text-[#4a5568] italic">No data yet</p>
                    ) : (
                      <>
                        <DetailRow label="Temperature" value={fmt(d.temp_c, 0, "°C")} />
                        <DetailRow label="Precipitation" value={fmt(d.precip_mm, 1, " mm")} />
                        <DetailRow label="Soil Moisture" value={d.soil_moisture != null ? `${(d.soil_moisture * 100).toFixed(0)}%` : "—"} />
                        <DetailRow label="ET₀" value={fmt(d.et0, 2, " mm")} />
                        <DetailRow label="Wind (10m)" value={fmt(d.wind_speed_10m, 1, " km/h")} />
                        <p className="text-[10px] text-[#4a5568] mt-2">
                          Updated {new Date(d.time).toLocaleString("en-US", { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" })}
                        </p>
                      </>
                    )}
                  </div>
                );
              })}
            </div>
          )}

          {/* ── GDU ── */}
          {tab === "gdu" && (
            <div className="space-y-4">
              {gdu == null ? (
                <p className="text-sm text-[#4a5568] italic">
                  GDU data will appear once local weather polling has started.
                </p>
              ) : (
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  {[
                    { key: "corn" as const, label: "Corn", color: "text-[#a3e635]", icon: "🌽" },
                    { key: "beans" as const, label: "Soybeans", color: "text-[#3b82f6]", icon: "🌱" },
                  ].map(({ key, label, color, icon }) => {
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
                        <div className="mt-3 space-y-0">
                          <DetailRow label="Today's GDU" value={`+${g.today_gdu}`} />
                          <DetailRow label="Days tracked" value={String(g.days_tracked)} />
                          <DetailRow label="Planting date" value={new Date(g.planting_date + "T12:00:00").toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" })} />
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
