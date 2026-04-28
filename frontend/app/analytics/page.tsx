"use client";

import { useCallback, useEffect, useState } from "react";
import AnalyticsLineChart, {
  type ChartSeries,
} from "@/components/charts/AnalyticsLineChart";
import PriceChart from "@/components/charts/PriceChart";
import {
  getAnalyticsBasisHistory,
  getAnalyticsFuturesHistory,
  getAnalyticsNepHistory,
  getElevatorNames,
} from "@/lib/api";
import type { BasisBar, NepBar, OhlcBar } from "@/lib/types";

type Tab = "futures" | "basis" | "nep";
type Lookback = 30 | 90 | 180 | 365;

const LOOKBACK_OPTIONS: Lookback[] = [30, 90, 180, 365];
const FUTURES_SYMBOLS = ["ZC=F", "ZS=F", "ZW=F"] as const;

const SERIES_COLORS = {
  cash: "#22c55e",
  futures_ref: "#3b82f6",
  basis: "#f59e0b",
  nep: "#a3e635",
  underlying: "#7b8aab",
};

export default function AnalyticsPage() {
  const [tab, setTab] = useState<Tab>("futures");
  const [lookback, setLookback] = useState<Lookback>(90);
  const [symbol, setSymbol] = useState<(typeof FUTURES_SYMBOLS)[number]>("ZC=F");
  const [commodity, setCommodity] = useState<"ZC" | "ZS">("ZC");
  const [elevator, setElevator] = useState<string>("");
  const [elevatorOptions, setElevatorOptions] = useState<string[]>([]);

  const [futuresData, setFuturesData] = useState<OhlcBar[]>([]);
  const [basisData, setBasisData] = useState<BasisBar[]>([]);
  const [nepData, setNepData] = useState<NepBar[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Load elevator names once
  useEffect(() => {
    getElevatorNames()
      .then((names) => {
        setElevatorOptions(names);
        if (names.length > 0) setElevator(names[0]);
      })
      .catch(() => {});
  }, []);

  const fetchData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      if (tab === "futures") {
        const data = await getAnalyticsFuturesHistory(symbol, lookback);
        setFuturesData(data);
      } else if (tab === "basis") {
        const data = await getAnalyticsBasisHistory(
          commodity,
          lookback,
          elevator || undefined,
        );
        setBasisData(data);
      } else {
        const data = await getAnalyticsNepHistory(lookback);
        setNepData(data);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load data");
    } finally {
      setLoading(false);
    }
  }, [tab, lookback, symbol, commodity, elevator]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  // Build basis series from raw rows
  const basisSeries: ChartSeries[] = [
    {
      key: "cash",
      label: "Cash",
      color: SERIES_COLORS.cash,
      data: basisData
        .map((r) => ({ time: r.time, value: r.cash_price })),
    },
    {
      key: "futures_ref",
      label: "Futures Ref",
      color: SERIES_COLORS.futures_ref,
      dashed: true,
      data: basisData
        .filter((r) => r.futures_ref != null)
        .map((r) => ({ time: r.time, value: r.futures_ref! })),
    },
    {
      key: "basis",
      label: "Basis",
      color: SERIES_COLORS.basis,
      data: basisData
        .filter((r) => r.basis != null)
        .map((r) => ({ time: r.time, value: r.basis! })),
    },
  ];

  // Build NEP series — group by position_id, show net_eff_price lines
  const nepByPosition = nepData.reduce<Record<string, NepBar[]>>((acc, r) => {
    (acc[r.position_id] ??= []).push(r);
    return acc;
  }, {});
  const nepColors = ["#a3e635", "#3b82f6", "#f59e0b", "#ef4444", "#a855f7"];
  const nepSeries: ChartSeries[] = Object.entries(nepByPosition).map(
    ([posId, rows], i) => ({
      key: posId,
      label: `Position ${posId.slice(-6)}`,
      color: nepColors[i % nepColors.length],
      data: rows
        .filter((r) => r.net_eff_price != null)
        .map((r) => ({ time: r.time, value: r.net_eff_price! })),
    }),
  );

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
        <h1 className="text-lg font-semibold text-[#e8edf5]">Analytics</h1>

        {/* Lookback selector */}
        <div className="flex items-center gap-1">
          {LOOKBACK_OPTIONS.map((d) => (
            <button
              key={d}
              onClick={() => setLookback(d)}
              className={`px-3 py-1 text-xs rounded transition-colors ${
                lookback === d
                  ? "bg-[#1e2535] text-[#e8edf5]"
                  : "text-[#7b8aab] hover:text-[#e8edf5]"
              }`}
            >
              {d === 365 ? "1yr" : `${d}d`}
            </button>
          ))}
        </div>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 border-b border-[#1e2535]">
        {(
          [
            { id: "futures", label: "Futures Prices" },
            { id: "basis", label: "Basis & Cash" },
            { id: "nep", label: "Net Eff. Price" },
          ] as { id: Tab; label: string }[]
        ).map(({ id, label }) => (
          <button
            key={id}
            onClick={() => setTab(id)}
            className={`px-4 py-2 text-sm transition-colors border-b-2 -mb-px ${
              tab === id
                ? "border-[#3b82f6] text-[#e8edf5]"
                : "border-transparent text-[#7b8aab] hover:text-[#e8edf5]"
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      {/* Filter row */}
      <div className="flex flex-wrap gap-3">
        {tab === "futures" && (
          <div className="flex gap-1">
            {FUTURES_SYMBOLS.map((s) => (
              <button
                key={s}
                onClick={() => setSymbol(s)}
                className={`px-3 py-1 text-xs rounded border transition-colors ${
                  symbol === s
                    ? "border-[#3b82f6] text-[#3b82f6] bg-[#1e2535]"
                    : "border-[#2a3044] text-[#7b8aab] hover:text-[#e8edf5]"
                }`}
              >
                {s.replace("=F", "")}
              </button>
            ))}
          </div>
        )}

        {tab === "basis" && (
          <>
            <div className="flex gap-1">
              {(["ZC", "ZS"] as const).map((c) => (
                <button
                  key={c}
                  onClick={() => setCommodity(c)}
                  className={`px-3 py-1 text-xs rounded border transition-colors ${
                    commodity === c
                      ? "border-[#3b82f6] text-[#3b82f6] bg-[#1e2535]"
                      : "border-[#2a3044] text-[#7b8aab] hover:text-[#e8edf5]"
                  }`}
                >
                  {c === "ZC" ? "Corn" : "Beans"}
                </button>
              ))}
            </div>
            {elevatorOptions.length > 0 && (
              <select
                value={elevator}
                onChange={(e) => setElevator(e.target.value)}
                className="text-xs bg-[#141920] border border-[#2a3044] text-[#7b8aab] rounded px-2 py-1"
              >
                <option value="">All elevators</option>
                {elevatorOptions.map((e) => (
                  <option key={e} value={e}>{e}</option>
                ))}
              </select>
            )}
          </>
        )}
      </div>

      {/* Status */}
      {loading && (
        <p className="text-xs text-[#7b8aab]">Loading…</p>
      )}
      {error && (
        <p className="text-xs text-red-400">⚠ {error}</p>
      )}

      {/* Chart panels */}
      {!loading && (
        <>
          {tab === "futures" && (
            <div className="space-y-2">
              <p className="text-xs text-[#7b8aab]">
                {symbol.replace("=F", "")} — {lookback === 365 ? "1 year" : `${lookback} days`} of close prices
              </p>
              <PriceChart symbol={symbol} history={futuresData} height={360} />
            </div>
          )}

          {tab === "basis" && (
            <div className="space-y-2">
              <p className="text-xs text-[#7b8aab]">
                {commodity === "ZC" ? "Corn" : "Soybeans"} cash vs. futures — basis = cash − futures
                {elevator ? ` · ${elevator}` : " · all elevators"}
              </p>
              <AnalyticsLineChart
                series={basisSeries}
                height={360}
                emptyMessage="No basis data yet — will populate once the elevator scraper has run."
              />
            </div>
          )}

          {tab === "nep" && (
            <div className="space-y-2">
              <p className="text-xs text-[#7b8aab]">
                Net effective price per bushel across all tracked positions
              </p>
              <AnalyticsLineChart
                series={
                  nepSeries.length > 0
                    ? nepSeries
                    : [{ key: "empty", label: "", color: "#fff", data: [] }]
                }
                height={360}
                emptyMessage="No snapshot data yet — NEP history is recorded each time the futures feed runs against an open position."
              />
            </div>
          )}
        </>
      )}

      {/* Context note */}
      <p className="text-[10px] text-[#4a5568]">
        All prices 15-min delayed · Futures data from yfinance · Cash/basis from River Valley Co-op scraper
      </p>
    </div>
  );
}
