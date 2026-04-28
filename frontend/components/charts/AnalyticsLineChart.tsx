"use client";

import { useEffect, useRef, useState } from "react";
import {
  createChart,
  LineSeries,
  LineStyle,
  type IChartApi,
  type ISeriesApi,
  type UTCTimestamp,
} from "lightweight-charts";

export interface ChartSeries {
  key: string;
  label: string;
  color: string;
  data: Array<{ time: string; value: number }>;
  dashed?: boolean;
}

interface Props {
  series: ChartSeries[];
  height?: number;
  emptyMessage?: string;
}

const COLORS = {
  bg: "#141920",
  grid: "#1e2535",
  text: "#7b8aab",
  border: "#2a3044",
};

function toSeconds(iso: string): UTCTimestamp {
  return Math.floor(new Date(iso).getTime() / 1000) as UTCTimestamp;
}

export default function AnalyticsLineChart({
  series,
  height = 300,
  emptyMessage = "No data yet — will populate once the feed has run.",
}: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const seriesMapRef = useRef<Map<string, ISeriesApi<"Line">>>(new Map());

  // Keys of series the user has hidden — starts with all series visible
  const [hiddenKeys, setHiddenKeys] = useState<Set<string>>(() => new Set());

  const hasData = series.some((s) => s.data.length > 0);

  // Build / rebuild the chart when series data changes
  useEffect(() => {
    if (!containerRef.current || !hasData) return;

    const chart = createChart(containerRef.current, {
      width: containerRef.current.clientWidth,
      height,
      layout: {
        background: { color: COLORS.bg },
        textColor: COLORS.text,
      },
      grid: {
        vertLines: { color: COLORS.grid },
        horzLines: { color: COLORS.grid },
      },
      crosshair: { mode: 1 },
      rightPriceScale: { borderColor: COLORS.border },
      timeScale: {
        borderColor: COLORS.border,
        timeVisible: true,
        secondsVisible: false,
      },
    });

    chartRef.current = chart;
    seriesMapRef.current = new Map();

    for (const s of series) {
      if (s.data.length === 0) continue;
      const line = chart.addSeries(LineSeries, {
        color: s.color,
        lineWidth: 2,
        lineStyle: s.dashed ? LineStyle.Dashed : LineStyle.Solid,
        title: s.label,
        visible: !hiddenKeys.has(s.key),
      });
      line.setData(
        s.data.map((d) => ({ time: toSeconds(d.time), value: d.value })),
      );
      seriesMapRef.current.set(s.key, line);
    }

    chart.timeScale().fitContent();

    const ro = new ResizeObserver((entries) => {
      for (const entry of entries) {
        chart.applyOptions({ width: entry.contentRect.width });
      }
    });
    ro.observe(containerRef.current);

    return () => {
      ro.disconnect();
      chart.remove();
      chartRef.current = null;
      seriesMapRef.current = new Map();
    };
    // hiddenKeys intentionally excluded — visibility is applied in the effect below
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [series, height, hasData]);

  // Sync visibility whenever hiddenKeys changes (without recreating the chart)
  useEffect(() => {
    seriesMapRef.current.forEach((s, key) => {
      s.applyOptions({ visible: !hiddenKeys.has(key) });
    });
  }, [hiddenKeys]);

  function toggleKey(key: string) {
    setHiddenKeys((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  }

  return (
    <div className="w-full rounded-lg overflow-hidden border border-[#2a3044]">
      {!hasData ? (
        <div
          className="flex items-center justify-center text-sm text-[#4a5568] bg-[#141920]"
          style={{ height }}
        >
          {emptyMessage}
        </div>
      ) : (
        <div ref={containerRef} style={{ height }} />
      )}
      {hasData && (
        <div className="flex flex-wrap items-center gap-3 px-3 py-1.5 bg-[#141920] text-[10px] border-t border-[#1e2535]">
          {series
            .filter((s) => s.data.length > 0)
            .map((s) => {
              const hidden = hiddenKeys.has(s.key);
              return (
                <button
                  key={s.key}
                  onClick={() => toggleKey(s.key)}
                  className={`flex items-center gap-1 transition-opacity ${hidden ? "opacity-35" : "opacity-100"}`}
                  title={hidden ? `Show ${s.label}` : `Hide ${s.label}`}
                >
                  <span
                    className="inline-block w-4 shrink-0"
                    style={{
                      height: 2,
                      borderTop: s.dashed ? `2px dashed ${s.color}` : undefined,
                      background: s.dashed ? "none" : s.color,
                    }}
                  />
                  <span
                    className={`text-[#7b8aab] ${hidden ? "line-through" : ""}`}
                  >
                    {s.label}
                  </span>
                </button>
              );
            })}
          <span className="ml-auto text-[9px] text-[#2a3044] select-none">click to toggle</span>
        </div>
      )}
    </div>
  );
}
