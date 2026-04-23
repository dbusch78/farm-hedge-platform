"use client";

import { useEffect, useRef } from "react";
import {
  createChart,
  CandlestickSeries,
  LineSeries,
  LineStyle,
  type IChartApi,
  type ISeriesApi,
  type SeriesType,
  type CandlestickData,
  type LineData,
  type UTCTimestamp,
} from "lightweight-charts";
import type { OhlcBar, CashPrice } from "@/lib/types";

interface Props {
  symbol: string;
  history: OhlcBar[];
  cashHistory?: CashPrice[];
  strikePrice?: number;
  netEffectivePrice?: number;
  height?: number;
}

const CHART_COLORS = {
  bg: "#141920",
  grid: "#1e2535",
  text: "#7b8aab",
  border: "#2a3044",
  upCandle: "#22c55e",
  downCandle: "#ef4444",
  basis: "#3b82f6",
  strike: "#f59e0b",
  netPrice: "#a3e635",
};

function toSeconds(isoString: string): UTCTimestamp {
  return Math.floor(new Date(isoString).getTime() / 1000) as UTCTimestamp;
}

export default function PriceChart({
  symbol,
  history,
  cashHistory,
  strikePrice,
  netEffectivePrice,
  height = 320,
}: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const candleRef = useRef<ISeriesApi<SeriesType> | null>(null);
  const basisRef = useRef<ISeriesApi<SeriesType> | null>(null);

  useEffect(() => {
    if (!containerRef.current) return;

    const chart = createChart(containerRef.current, {
      width: containerRef.current.clientWidth,
      height,
      layout: {
        background: { color: CHART_COLORS.bg },
        textColor: CHART_COLORS.text,
      },
      grid: {
        vertLines: { color: CHART_COLORS.grid },
        horzLines: { color: CHART_COLORS.grid },
      },
      crosshair: { mode: 1 },
      rightPriceScale: {
        borderColor: CHART_COLORS.border,
      },
      timeScale: {
        borderColor: CHART_COLORS.border,
        timeVisible: true,
        secondsVisible: false,
      },
    });

    chartRef.current = chart;

    // Candlestick series
    const candles = chart.addSeries(CandlestickSeries, {
      upColor: CHART_COLORS.upCandle,
      downColor: CHART_COLORS.downCandle,
      borderUpColor: CHART_COLORS.upCandle,
      borderDownColor: CHART_COLORS.downCandle,
      wickUpColor: CHART_COLORS.upCandle,
      wickDownColor: CHART_COLORS.downCandle,
    });
    candleRef.current = candles;

    const candleData: CandlestickData[] = history
      .filter((b) => b.open != null && b.high != null && b.low != null && b.close != null)
      .map((b) => ({
        time: toSeconds(b.time),
        open: b.open,
        high: b.high,
        low: b.low,
        close: b.close,
      }));
    candles.setData(candleData);

    // Basis line (cash - futures) if cash history provided
    if (cashHistory && cashHistory.length > 0) {
      const basis = chart.addSeries(LineSeries, {
        color: CHART_COLORS.basis,
        lineWidth: 1,
        lineStyle: LineStyle.Dashed,
        title: "basis",
        priceScaleId: "basis",
      });
      basisRef.current = basis;

      const basisData: LineData[] = cashHistory
        .filter((c) => c.basis != null)
        .map((c) => ({
          time: toSeconds(c.time),
          value: c.basis!,
        }));
      basis.setData(basisData);
    }

    // Horizontal price lines
    if (strikePrice != null && candleData.length > 0) {
      candles.createPriceLine({
        price: strikePrice,
        color: CHART_COLORS.strike,
        lineWidth: 1,
        lineStyle: LineStyle.Dashed,
        axisLabelVisible: true,
        title: "strike",
      });
    }

    if (netEffectivePrice != null && candleData.length > 0) {
      candles.createPriceLine({
        price: netEffectivePrice,
        color: CHART_COLORS.netPrice,
        lineWidth: 1,
        lineStyle: LineStyle.Solid,
        axisLabelVisible: true,
        title: "net eff.",
      });
    }

    chart.timeScale().fitContent();

    // Resize observer
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
      candleRef.current = null;
      basisRef.current = null;
    };
  }, [history, cashHistory, strikePrice, netEffectivePrice, height]);

  return (
    <div className="w-full rounded-lg overflow-hidden border border-[#2a3044]">
      {history.length === 0 ? (
        <div
          className="flex items-center justify-center text-sm text-[#4a5568] bg-[#141920]"
          style={{ height }}
        >
          No price history — data will appear after the first futures feed run.
        </div>
      ) : (
        <div ref={containerRef} style={{ height }} />
      )}
      <div className="flex items-center gap-4 px-3 py-1.5 bg-[#141920] text-[10px] text-[#4a5568] border-t border-[#1e2535]">
        <LegendItem color={CHART_COLORS.upCandle} label={symbol} />
        {cashHistory && cashHistory.length > 0 && (
          <LegendItem color={CHART_COLORS.basis} label="basis" dashed />
        )}
        {strikePrice != null && (
          <LegendItem color={CHART_COLORS.strike} label={`strike $${strikePrice.toFixed(2)}`} dashed />
        )}
        {netEffectivePrice != null && (
          <LegendItem color={CHART_COLORS.netPrice} label={`net eff. $${netEffectivePrice.toFixed(2)}`} />
        )}
      </div>
    </div>
  );
}

function LegendItem({
  color,
  label,
  dashed = false,
}: {
  color: string;
  label: string;
  dashed?: boolean;
}) {
  return (
    <span className="flex items-center gap-1">
      <span
        className="inline-block w-4 h-px"
        style={{
          backgroundColor: color,
          borderTop: dashed ? `1px dashed ${color}` : undefined,
        }}
      />
      <span>{label}</span>
    </span>
  );
}
