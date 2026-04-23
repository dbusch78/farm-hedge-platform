"use client";

import { useFuturesPrices } from "@/hooks/useFuturesPrices";
import type { FuturesPrice, NetPriceResponse, Position } from "@/lib/types";

interface Props {
  commodity: "ZC" | "ZS";
  positions: Position[];
  netPrice: NetPriceResponse | null;
  initialFuturesPrice: FuturesPrice | null;
}

const COMMODITY_LABEL: Record<string, string> = {
  ZC: "CORN",
  ZS: "SOYBEAN",
};
const COMMODITY_ICON: Record<string, string> = { ZC: "🌽", ZS: "🌱" };
const FUTURES_SYMBOL: Record<string, string> = { ZC: "ZC=F", ZS: "ZS=F" };

function fmt(n: number, decimals = 2): string {
  return n.toFixed(decimals);
}

function fmtBushels(n: number): string {
  return n.toLocaleString();
}

function fmtDollars(n: number): string {
  const abs = Math.abs(n);
  const sign = n < 0 ? "-" : "+";
  return `${sign}$${abs.toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 0 })}`;
}

export default function HedgeCard({
  commodity,
  positions,
  netPrice,
  initialFuturesPrice,
}: Props) {
  const symbol = FUTURES_SYMBOL[commodity];
  const { prices } = useFuturesPrices(
    initialFuturesPrice
      ? {
          [symbol]: {
            close: initialFuturesPrice.close,
            time: initialFuturesPrice.time,
            stale: initialFuturesPrice.stale,
          },
        }
      : undefined,
  );

  const livePrice = prices[symbol];
  const futuresClose = livePrice?.close ?? initialFuturesPrice?.close ?? null;
  const isStale = livePrice?.stale ?? initialFuturesPrice?.stale ?? false;

  // Sum across all positions for this commodity
  const totalBushels = positions.reduce((s, p) => s + p.expected_bushels, 0);
  const totalContracts = positions.reduce((s, p) => s + p.num_contracts, 0);
  const phase = positions[0]?.phase ?? 1;
  const contractMonth = positions[0]?.contract_month ?? "—";
  const positionType = positions[0]?.position_type ?? "put";

  // P&L calculation from net price data
  const pnlPerBu =
    netPrice && futuresClose !== null
      ? netPrice.net_effective_price - futuresClose
      : null;
  const totalPnl = pnlPerBu !== null ? pnlPerBu * totalBushels : null;

  const isPhase1 = phase === 1;
  const borderColor = isPhase1 ? "border-l-[#a3e635]" : "border-l-[#3b82f6]";
  const phaseBadgeBg = isPhase1 ? "bg-[#a3e63520] text-[#a3e635]" : "bg-[#3b82f620] text-[#3b82f6]";

  return (
    <div
      className={`bg-[#1a1f2e] rounded-lg border border-[#2a3044] border-l-4 ${borderColor} p-5 space-y-4`}
    >
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <h2 className="text-base font-semibold text-[#e8edf5] flex items-center gap-2">
            <span>{COMMODITY_ICON[commodity]}</span>
            {COMMODITY_LABEL[commodity]} HEDGE &mdash; {contractMonth}
          </h2>
          <p className="text-xs text-[#7b8aab] mt-0.5">
            {commodity === "ZC" ? "July ZC" : "July ZS"} &bull;{" "}
            {positionType === "put" ? "Long puts" : "Long calls"}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <span className={`text-xs font-semibold px-2 py-0.5 rounded ${phaseBadgeBg}`}>
            PHASE {phase}
          </span>
          <span className="text-xs font-semibold px-2 py-0.5 rounded bg-[#22c55e20] text-[#22c55e]">
            ACTIVE
          </span>
        </div>
      </div>

      {/* Stats row */}
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
        <StatBlock label="BUSHELS" value={fmtBushels(totalBushels)} />
        <StatBlock
          label={positionType === "put" ? "PUTS HELD" : "CALLS HELD"}
          value={`${totalContracts} contracts`}
        />
        <StatBlock
          label="NET EFF. PRICE"
          value={
            netPrice
              ? `$${fmt(netPrice.net_effective_price)} / bu`
              : "—"
          }
          highlight
        />
        <StatBlock
          label="FUTURES"
          value={
            futuresClose !== null
              ? `$${fmt(futuresClose)}`
              : "—"
          }
          stale={isStale}
        />
      </div>

      {/* P&L row */}
      <div className="pt-1 border-t border-[#1e2535] flex items-center justify-between">
        <span className="text-xs text-[#7b8aab] uppercase tracking-wide">
          Options P&amp;L (net of premium)
        </span>
        <span
          className={`text-sm font-semibold tabular-nums ${
            pnlPerBu === null
              ? "text-[#7b8aab]"
              : pnlPerBu >= 0
                ? "text-[#22c55e]"
                : "text-[#ef4444]"
          }`}
        >
          {pnlPerBu !== null ? (
            <>
              {pnlPerBu >= 0 ? "+" : ""}
              {fmt(pnlPerBu)}/bu
              {totalPnl !== null && (
                <span className="text-xs ml-2 opacity-70">
                  ({fmtDollars(totalPnl)})
                </span>
              )}
            </>
          ) : (
            "—"
          )}
        </span>
      </div>

      {/* Premium cost line */}
      {netPrice && (
        <div className="text-xs text-[#7b8aab] flex justify-between">
          <span>Premium paid</span>
          <span className="text-[#f59e0b] tabular-nums">
            −${fmt(netPrice.total_premiums_paid)} / bu
          </span>
        </div>
      )}
    </div>
  );
}

function StatBlock({
  label,
  value,
  highlight = false,
  stale = false,
}: {
  label: string;
  value: string;
  highlight?: boolean;
  stale?: boolean;
}) {
  return (
    <div>
      <p className="text-[10px] uppercase tracking-widest text-[#7b8aab] mb-1">
        {label}
      </p>
      <p
        className={`text-sm font-semibold tabular-nums ${
          highlight ? "text-[#e8edf5]" : "text-[#c4cfe8]"
        } ${stale ? "opacity-50" : ""}`}
      >
        {value}
        {stale && (
          <span className="ml-1 text-[#f59e0b] text-[10px]">(stale)</span>
        )}
      </p>
    </div>
  );
}
