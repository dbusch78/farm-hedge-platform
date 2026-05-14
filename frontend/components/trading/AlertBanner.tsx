"use client";

import { useState } from "react";
import type { HedgeAlert } from "@/lib/types";
import { acknowledgeAlert } from "@/lib/api";
import { useRouter } from "next/navigation";

const ALERT_TYPE_LABEL: Record<string, string> = {
  phase1_roll_up:     "Roll-Up",
  phase1_roll_down:   "Roll-Down",
  phase2_take_profit: "Take-Profit",
};

function AlertRow({ alert, onDismiss }: { alert: HedgeAlert; onDismiss: () => void }) {
  const [dismissing, setDismissing] = useState(false);
  const isRed = alert.level === "red";

  const borderColor = isRed ? "border-[#ef444480]" : "border-[#f59e0b80]";
  const bgColor     = isRed ? "bg-[#ef444408]"    : "bg-[#f59e0b08]";
  const badgeColor  = isRed
    ? "bg-[#ef444420] text-[#ef4444]"
    : "bg-[#f59e0b20] text-[#f59e0b]";
  const labelColor  = isRed ? "text-[#ef4444]"    : "text-[#f59e0b]";

  async function handleDismiss() {
    setDismissing(true);
    try {
      await acknowledgeAlert(alert.id);
      onDismiss();
    } catch {
      setDismissing(false);
    }
  }

  return (
    <div className={`rounded border ${borderColor} ${bgColor} p-3 text-xs`}>
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-start gap-2 flex-1">
          <span className={`shrink-0 mt-0.5 text-[10px] font-bold px-1.5 py-0.5 rounded ${badgeColor}`}>
            {alert.level.toUpperCase()}
          </span>
          <div>
            <span className={`font-semibold ${labelColor}`}>
              {alert.commodity} {ALERT_TYPE_LABEL[alert.alert_type] ?? alert.alert_type}
              {alert.contract_month ? ` — ${alert.contract_month}` : ""}
            </span>
            <p className="mt-0.5 text-[#9aa5be] leading-relaxed">{alert.reason}</p>
          </div>
        </div>
        <button
          onClick={handleDismiss}
          disabled={dismissing}
          className="shrink-0 text-[#4a5568] hover:text-[#9aa5be] disabled:opacity-40 transition-colors"
          title="Dismiss alert"
        >
          ✕
        </button>
      </div>
    </div>
  );
}

export default function AlertBanner({ alerts }: { alerts: HedgeAlert[] }) {
  const router = useRouter();
  const [dismissed, setDismissed] = useState<Set<string>>(new Set());

  const visible = alerts.filter((a) => !dismissed.has(a.id));
  if (visible.length === 0) return null;

  const redCount    = visible.filter((a) => a.level === "red").length;
  const yellowCount = visible.filter((a) => a.level === "yellow").length;

  function dismiss(id: string) {
    setDismissed((prev) => new Set([...prev, id]));
    router.refresh();
  }

  return (
    <div className="space-y-2">
      <div className="flex items-center gap-2 text-xs text-[#7b8aab]">
        <span className="font-semibold text-[#e8edf5]">Phase Transition Alerts</span>
        {redCount > 0 && (
          <span className="bg-[#ef444420] text-[#ef4444] px-1.5 py-0.5 rounded text-[10px] font-bold">
            {redCount} red
          </span>
        )}
        {yellowCount > 0 && (
          <span className="bg-[#f59e0b20] text-[#f59e0b] px-1.5 py-0.5 rounded text-[10px] font-bold">
            {yellowCount} yellow
          </span>
        )}
      </div>
      {visible.map((alert) => (
        <AlertRow key={alert.id} alert={alert} onDismiss={() => dismiss(alert.id)} />
      ))}
    </div>
  );
}
