"use client";

import { useState } from "react";
import type { Position } from "@/lib/types";

function fmt(n: number, d = 2) {
  return n.toFixed(d);
}

const CLOSE_REASON_DISPLAY: Record<string, string> = {
  profit_take:      "Profit take",
  phase_transition: "Phase transition",
  roll:             "Rolled",
  stop:             "Stop",
  expiry:           "Expiry",
  manual:           "Manual",
};

function ClosedPositionRow({ pos }: { pos: Position }) {
  const isClosed = pos.status === "CLOSED";
  const statusColor = isClosed ? "text-[#7b8aab]" : "text-[#4a5568]";
  const reason = pos.close_reason ?? pos.exit_reason;
  const statusLabel = pos.status === "EXPIRED"
    ? "EXPIRED WORTHLESS"
    : `CLOSED${reason && reason !== "manual" ? ` · ${CLOSE_REASON_DISPLAY[reason] ?? reason}` : ""}`;

  const realizedPnl = pos.realized_pnl_per_bu;
  const totalRealized = realizedPnl != null ? realizedPnl * pos.expected_bushels : null;
  const exitDateStr = pos.exit_date ? pos.exit_date.slice(0, 10) : null;

  return (
    <div className="bg-[#0d1117] rounded border border-[#1e2535] p-3 text-sm opacity-80">
      <div className="flex items-center justify-between gap-2 flex-wrap">
        <div className="flex items-center gap-2">
          <span className={`text-[10px] font-semibold uppercase px-2 py-0.5 rounded border border-[#2a3044] ${statusColor}`}>
            {statusLabel}
          </span>
          <span className="text-[#7b8aab] font-medium">
            {pos.contract_month} {pos.position_type.toUpperCase()} @${fmt(pos.strike)}
          </span>
          {exitDateStr && (
            <span className="text-[#4a5568] text-xs">{exitDateStr}</span>
          )}
        </div>
        <div className="flex items-center gap-3 text-xs">
          {pos.exit_price_per_bu != null && pos.exit_price_per_bu > 0 && (
            <span className="text-[#7b8aab]">
              Exit: ${fmt(pos.exit_price_per_bu, 3)}/bu
            </span>
          )}
          {realizedPnl != null && (
            <span className={`font-semibold tabular-nums ${realizedPnl >= 0 ? "text-[#22c55e]" : "text-[#ef4444]"}`}>
              {realizedPnl >= 0 ? "+" : ""}${fmt(realizedPnl, 3)}/bu
              {totalRealized != null && (
                <span className="ml-1 opacity-70 font-normal">
                  ({totalRealized >= 0 ? "+" : ""}${Math.abs(totalRealized).toLocaleString(undefined, { maximumFractionDigits: 0 })})
                </span>
              )}
            </span>
          )}
        </div>
      </div>
      {pos.notes && <p className="text-xs text-[#4a5568] italic mt-1">{pos.notes}</p>}
    </div>
  );
}

export default function ClosedPositionsPanel({ positions }: { positions: Position[] }) {
  const [open, setOpen] = useState(false);

  return (
    <div>
      <button
        onClick={() => setOpen((v) => !v)}
        className="text-[10px] uppercase tracking-widest text-[#4a5568] hover:text-[#7b8aab] transition-colors flex items-center gap-1.5"
      >
        <span>{open ? "▾" : "▸"}</span>
        {open ? "Hide" : "Show"} closed / expired ({positions.length})
      </button>

      {open && (
        <div className="mt-2 space-y-2">
          {positions.map((pos) => (
            <ClosedPositionRow key={pos.id} pos={pos} />
          ))}
        </div>
      )}
    </div>
  );
}
