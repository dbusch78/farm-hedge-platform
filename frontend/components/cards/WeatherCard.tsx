"use client";

import { useEffect, useState } from "react";
import { getGduStatus, getLocalWeather, getRegionalWeather } from "@/lib/api";
import type { GduStatus, WeatherLocal, WeatherRegional } from "@/lib/types";

const COMPASS = ["N","NNE","NE","ENE","E","ESE","SE","SSE","S","SSW","SW","WSW","W","WNW","NW","NNW"];

function windDir(deg: number | null): string {
  if (deg == null) return "—";
  return COMPASS[Math.round(deg / 22.5) % 16];
}

function fmt(v: number | null, decimals = 1, unit = ""): string {
  if (v == null) return "—";
  return `${v.toFixed(decimals)}${unit}`;
}

function tempColor(f: number | null): string {
  if (f == null) return "text-[#e8edf5]";
  if (f >= 90) return "text-red-400";
  if (f >= 75) return "text-amber-400";
  if (f <= 32) return "text-blue-400";
  return "text-[#e8edf5]";
}

function Stat({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div>
      <p className="text-[9px] uppercase tracking-widest text-[#7b8aab] mb-0.5">{label}</p>
      <p className="text-sm font-semibold text-[#e8edf5] tabular-nums">{value}</p>
      {sub && <p className="text-[10px] text-[#4a5568]">{sub}</p>}
    </div>
  );
}

export default function WeatherCard() {
  const [local, setLocal] = useState<WeatherLocal | null>(null);
  const [matoGrosso, setMatoGrosso] = useState<WeatherRegional | null>(null);
  const [pampas, setPampas] = useState<WeatherRegional | null>(null);
  const [gdu, setGdu] = useState<GduStatus | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.allSettled([
      getLocalWeather(),
      getRegionalWeather("mato_grosso"),
      getRegionalWeather("pampas"),
      getGduStatus(),
    ]).then(([localRes, mgRes, pampasRes, gduRes]) => {
      if (localRes.status === "fulfilled") setLocal(localRes.value);
      if (mgRes.status === "fulfilled") setMatoGrosso(mgRes.value);
      if (pampasRes.status === "fulfilled") setPampas(pampasRes.value);
      if (gduRes.status === "fulfilled") setGdu(gduRes.value);
      setLoading(false);
    });
  }, []);

  const hasLightning = (local?.lightning_day ?? 0) > 0;

  return (
    <div className="bg-[#1a1f2e] rounded-lg border border-[#2a3044] border-l-4 border-l-[#3b82f6] p-5 space-y-4">
      {/* Header */}
      <div className="flex items-start justify-between">
        <h2 className="text-base font-semibold text-[#e8edf5] flex items-center gap-2">
          🌤 WEATHER
        </h2>
        <div className="text-right">
          <span className="text-xs text-[#7b8aab]">La Fayette, IL · On-farm</span>
          {local && (
            <p className="text-[10px] text-[#4a5568]">
              {new Date(local.time).toLocaleTimeString("en-US", {
                hour: "numeric", minute: "2-digit", timeZoneName: "short",
              })}
            </p>
          )}
        </div>
      </div>

      {/* Lightning alert */}
      {hasLightning && (
        <div className="flex items-center gap-2 bg-[#f59e0b15] border border-[#f59e0b40] rounded px-3 py-2 text-xs text-[#f59e0b]">
          ⚡ {local!.lightning_day} lightning strike{local!.lightning_day !== 1 ? "s" : ""} today
          {local!.lightning_distance_mi != null && (
            <span className="text-[#f59e0b80]">· nearest {local!.lightning_distance_mi.toFixed(1)} mi</span>
          )}
        </div>
      )}

      {loading ? (
        <div className="grid grid-cols-3 gap-3 opacity-30">
          {["LOCAL TEMP", "WIND", "RAIN TODAY"].map((l) => (
            <div key={l}>
              <p className="text-[9px] uppercase tracking-widest text-[#7b8aab] mb-0.5">{l}</p>
              <div className="h-4 w-12 bg-[#2a3044] rounded animate-pulse" />
            </div>
          ))}
        </div>
      ) : local == null ? (
        <p className="text-sm text-[#4a5568] italic">
          Weather feed starting up — data appears after first poll cycle.
        </p>
      ) : (
        <>
          {/* Primary row */}
          <div className="grid grid-cols-3 gap-3">
            <div>
              <p className="text-[9px] uppercase tracking-widest text-[#7b8aab] mb-0.5">LOCAL TEMP</p>
              <p className={`text-2xl font-bold tabular-nums ${tempColor(local.temp_f)}`}>
                {fmt(local.temp_f, 0, "°F")}
              </p>
              <p className="text-[10px] text-[#4a5568]">
                Dew pt {fmt(local.dew_point_f, 0, "°F")} · RH {fmt(local.humidity, 0, "%")}
              </p>
            </div>
            <Stat
              label="Wind"
              value={`${fmt(local.wind_speed, 0)} mph ${windDir(local.wind_dir)}`}
              sub={local.wind_gust_mph != null ? `gust ${local.wind_gust_mph.toFixed(0)} mph` : undefined}
            />
            <Stat
              label="Rain Today"
              value={fmt(local.rain_daily, 2, "\"")}
              sub={`${fmt(local.rain_hourly, 2, "\"")} this hour`}
            />
          </div>

          {/* Secondary row */}
          <div className="grid grid-cols-3 gap-3 pt-1 border-t border-[#1e2535]">
            <Stat
              label="Solar"
              value={fmt(local.solar_rad, 0, " W/m²")}
              sub={local.uv_index != null ? `UV ${local.uv_index}` : undefined}
            />
            <Stat label="Barometer" value={fmt(local.baro_rel, 2, "\"")} />
            <Stat label="Pressure" value={local.baro_rel != null ? (local.baro_rel > 30 ? "High ↑" : local.baro_rel < 29.7 ? "Low ↓" : "Normal") : "—"} />
          </div>
        </>
      )}

      {/* GDU row */}
      {gdu && (
        <div className="grid grid-cols-2 gap-3 pt-1 border-t border-[#1e2535]">
          <div>
            <p className="text-[9px] uppercase tracking-widest text-[#7b8aab] mb-0.5">GDU — Corn</p>
            <p className="text-sm font-semibold text-[#a3e635] tabular-nums">
              {gdu.corn.cumulative_gdu.toLocaleString()} total
            </p>
            <p className="text-[10px] text-[#4a5568]">
              +{gdu.corn.today_gdu} today · {gdu.corn.days_tracked} days tracked
            </p>
          </div>
          <div>
            <p className="text-[9px] uppercase tracking-widest text-[#7b8aab] mb-0.5">GDU — Beans</p>
            <p className="text-sm font-semibold text-[#3b82f6] tabular-nums">
              {gdu.beans.cumulative_gdu.toLocaleString()} total
            </p>
            <p className="text-[10px] text-[#4a5568]">
              +{gdu.beans.today_gdu} today · {gdu.beans.days_tracked} days tracked
            </p>
          </div>
        </div>
      )}

      {/* SA summary */}
      {(matoGrosso || pampas) && (
        <div className="pt-1 border-t border-[#1e2535]">
          <p className="text-[9px] uppercase tracking-widest text-[#7b8aab] mb-1.5">South America</p>
          <div className="grid grid-cols-2 gap-3">
            {matoGrosso && (
              <div>
                <p className="text-[10px] text-[#7b8aab]">Mato Grosso</p>
                <p className="text-xs text-[#e8edf5]">
                  {fmt(matoGrosso.temp_c, 0, "°C")} · {fmt(matoGrosso.precip_mm, 1, "mm rain")}
                </p>
                {matoGrosso.soil_moisture != null && (
                  <p className="text-[10px] text-[#4a5568]">
                    Soil moisture {(matoGrosso.soil_moisture * 100).toFixed(0)}%
                  </p>
                )}
              </div>
            )}
            {pampas && (
              <div>
                <p className="text-[10px] text-[#7b8aab]">Pampas (AR)</p>
                <p className="text-xs text-[#e8edf5]">
                  {fmt(pampas.temp_c, 0, "°C")} · {fmt(pampas.precip_mm, 1, "mm rain")}
                </p>
                {pampas.soil_moisture != null && (
                  <p className="text-[10px] text-[#4a5568]">
                    Soil moisture {(pampas.soil_moisture * 100).toFixed(0)}%
                  </p>
                )}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
