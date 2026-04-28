"use client";

import { useEffect, useRef } from "react";
import {
  createChart,
  LineSeries,
  LineStyle,
  type IChartApi,
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

  const hasData = series.some((s) => s.data.length > 0);

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

    for (const s of series) {
      if (s.data.length === 0) continue;
      const line = chart.addSeries(LineSeries, {
        color: s.color,
        lineWidth: 2,
        lineStyle: s.dashed ? LineStyle.Dashed : LineStyle.Solid,
        title: s.label,
      });
      line.setData(
        s.data.map((d) => ({ time: toSeconds(d.time), value: d.value })),
      );
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
    };
  }, [series, height, hasData]);

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
        <div className="flex flex-wrap items-center gap-4 px-3 py-1.5 bg-[#141920] text-[10px] text-[#4a5568] border-t border-[#1e2535]">
          {series
            .filter((s) => s.data.length > 0)
            .map((s) => (
              <span key={s.key} className="flex items-center gap-1">
                <span
                  className="inline-block w-4"
                  style={{
                    height: 2,
                    backgroundColor: s.color,
                    borderTop: s.dashed ? `2px dashed ${s.color}` : undefined,
                    background: s.dashed ? "none" : s.color,
                  }}
                />
                <span>{s.label}</span>
              </span>
            ))}
        </div>
      )}
    </div>
  );
}
