"use client";

import { useState, useTransition } from "react";
import { useRouter } from "next/navigation";
import { closePosition, expirePosition, updatePosition, deletePosition } from "@/lib/api";
import type { Position, Phase } from "@/lib/types";

type ActionMode = null | "close" | "expire" | "edit" | "delete";

const INPUT = "w-full bg-[#0d1117] border border-[#2a3044] rounded px-2 py-1.5 text-xs text-[#e8edf5] focus:outline-none focus:border-[#3b82f6]";
const LABEL = "block text-[10px] uppercase tracking-widest text-[#7b8aab] mb-1";

function today(): string {
  return new Date().toISOString().slice(0, 10);
}

function FormRow({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <label className={LABEL}>{label}</label>
      {children}
    </div>
  );
}

function ActionBtn({
  label,
  onClick,
  variant = "default",
  disabled = false,
}: {
  label: string;
  onClick: () => void;
  variant?: "default" | "danger" | "confirm";
  disabled?: boolean;
}) {
  const colors =
    variant === "danger"
      ? "text-[#ef4444] border-[#ef444440] hover:bg-[#ef444410]"
      : variant === "confirm"
        ? "text-[#22c55e] border-[#22c55e40] hover:bg-[#22c55e10]"
        : "text-[#7b8aab] border-[#2a3044] hover:bg-[#ffffff08]";
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      className={`text-[10px] font-semibold uppercase tracking-wide px-2.5 py-1 rounded border transition-colors disabled:opacity-40 disabled:cursor-not-allowed ${colors}`}
    >
      {label}
    </button>
  );
}

// ── Close form ────────────────────────────────────────────────────────────────

function CloseForm({
  pos,
  onSuccess,
  onCancel,
}: {
  pos: Position;
  onSuccess: () => void;
  onCancel: () => void;
}) {
  const [exitPrice, setExitPrice] = useState("");
  const [exitDate, setExitDate] = useState(today());
  const [notes, setNotes] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isPending, startTransition] = useTransition();

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const price = parseFloat(exitPrice);
    if (isNaN(price) || price < 0) { setError("Enter a valid exit price"); return; }
    setError(null);
    startTransition(async () => {
      try {
        await closePosition(pos.id, {
          exit_price_per_bu: price,
          exit_date: new Date(exitDate).toISOString(),
          notes,
        });
        onSuccess();
      } catch (e) {
        setError(e instanceof Error ? e.message : "Failed to close position");
      }
    });
  }

  const realized = exitPrice ? parseFloat(exitPrice) - pos.premium_paid_per_bu : null;

  return (
    <form onSubmit={handleSubmit} className="bg-[#0d1117] rounded border border-[#2a3044] p-3 space-y-3">
      <p className="text-xs font-semibold text-[#e8edf5]">Close position</p>
      <div className="grid grid-cols-2 gap-2">
        <FormRow label="Exit price ($/bu)">
          <input type="number" step="0.001" min="0" value={exitPrice}
            onChange={e => setExitPrice(e.target.value)} placeholder="0.22" required className={INPUT} />
        </FormRow>
        <FormRow label="Date closed">
          <input type="date" value={exitDate} onChange={e => setExitDate(e.target.value)} required className={INPUT} />
        </FormRow>
      </div>
      <FormRow label="Notes (optional)">
        <input type="text" value={notes} onChange={e => setNotes(e.target.value)}
          placeholder="Sold ahead of expiry…" className={INPUT} />
      </FormRow>
      {realized !== null && (
        <p className={`text-xs tabular-nums ${realized >= 0 ? "text-[#22c55e]" : "text-[#ef4444]"}`}>
          Realized P&L: {realized >= 0 ? "+" : ""}${realized.toFixed(3)}/bu
          &nbsp;({realized >= 0 ? "+" : ""}${(realized * pos.expected_bushels).toLocaleString(undefined, { maximumFractionDigits: 0 })})
        </p>
      )}
      {error && <p className="text-xs text-[#ef4444]">{error}</p>}
      <div className="flex gap-2">
        <ActionBtn label={isPending ? "Saving…" : "Confirm close"} onClick={() => {}} variant="confirm" disabled={isPending} />
        <ActionBtn label="Cancel" onClick={onCancel} />
      </div>
    </form>
  );
}

// ── Expire form ───────────────────────────────────────────────────────────────

function ExpireForm({
  pos,
  onSuccess,
  onCancel,
}: {
  pos: Position;
  onSuccess: () => void;
  onCancel: () => void;
}) {
  const [exitPrice, setExitPrice] = useState("0.00");
  const [exitDate, setExitDate] = useState(today());
  const [error, setError] = useState<string | null>(null);
  const [isPending, startTransition] = useTransition();

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const price = parseFloat(exitPrice);
    if (isNaN(price) || price < 0) { setError("Enter a valid exit price"); return; }
    setError(null);
    startTransition(async () => {
      try {
        await expirePosition(pos.id, {
          exit_price_per_bu: price,
          exit_date: new Date(exitDate).toISOString(),
        });
        onSuccess();
      } catch (e) {
        setError(e instanceof Error ? e.message : "Failed to expire position");
      }
    });
  }

  const realized = parseFloat(exitPrice) - pos.premium_paid_per_bu;

  return (
    <form onSubmit={handleSubmit} className="bg-[#0d1117] rounded border border-[#2a3044] p-3 space-y-3">
      <p className="text-xs font-semibold text-[#e8edf5]">Mark expired</p>
      <div className="grid grid-cols-2 gap-2">
        <FormRow label="Exit price ($/bu)">
          <input type="number" step="0.001" min="0" value={exitPrice}
            onChange={e => setExitPrice(e.target.value)} required className={INPUT} />
        </FormRow>
        <FormRow label="Expiry date">
          <input type="date" value={exitDate} onChange={e => setExitDate(e.target.value)} required className={INPUT} />
        </FormRow>
      </div>
      {!isNaN(realized) && (
        <p className={`text-xs tabular-nums ${realized >= 0 ? "text-[#22c55e]" : "text-[#ef4444]"}`}>
          Realized P&L: {realized >= 0 ? "+" : ""}${realized.toFixed(3)}/bu
          &nbsp;({realized >= 0 ? "+" : ""}${(realized * pos.expected_bushels).toLocaleString(undefined, { maximumFractionDigits: 0 })})
        </p>
      )}
      {error && <p className="text-xs text-[#ef4444]">{error}</p>}
      <div className="flex gap-2">
        <ActionBtn label={isPending ? "Saving…" : "Confirm expire"} onClick={() => {}} variant="confirm" disabled={isPending} />
        <ActionBtn label="Cancel" onClick={onCancel} />
      </div>
    </form>
  );
}

// ── Edit form ─────────────────────────────────────────────────────────────────

function EditForm({
  pos,
  onSuccess,
  onCancel,
}: {
  pos: Position;
  onSuccess: () => void;
  onCancel: () => void;
}) {
  const [strike, setStrike] = useState(String(pos.strike));
  const [premium, setPremium] = useState(String(pos.premium_paid_per_bu));
  const [numContracts, setNumContracts] = useState(String(pos.num_contracts));
  const [delta, setDelta] = useState(String(pos.delta_at_entry));
  const [phase, setPhase] = useState<Phase>(pos.phase);
  const [cashSale, setCashSale] = useState(pos.cash_sale_price != null ? String(pos.cash_sale_price) : "");
  const [notes, setNotes] = useState(pos.notes);
  const [error, setError] = useState<string | null>(null);
  const [isPending, startTransition] = useTransition();

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    startTransition(async () => {
      try {
        const body: Record<string, unknown> = {};
        if (strike !== String(pos.strike)) body.strike = parseFloat(strike);
        if (premium !== String(pos.premium_paid_per_bu)) body.premium_paid_per_bu = parseFloat(premium);
        if (numContracts !== String(pos.num_contracts)) body.num_contracts = parseInt(numContracts, 10);
        if (delta !== String(pos.delta_at_entry)) body.delta_at_entry = parseFloat(delta);
        if (phase !== pos.phase) body.phase = phase;
        if (cashSale !== (pos.cash_sale_price != null ? String(pos.cash_sale_price) : "")) {
          body.cash_sale_price = cashSale ? parseFloat(cashSale) : null;
        }
        if (notes !== pos.notes) body.notes = notes;

        if (Object.keys(body).length === 0) { onCancel(); return; }
        await updatePosition(pos.id, body);
        onSuccess();
      } catch (e) {
        setError(e instanceof Error ? e.message : "Failed to update position");
      }
    });
  }

  return (
    <form onSubmit={handleSubmit} className="bg-[#0d1117] rounded border border-[#2a3044] p-3 space-y-3">
      <p className="text-xs font-semibold text-[#e8edf5]">
        Edit position
        <span className="ml-2 font-normal text-[#4a5568]">
          Immutable: {pos.commodity} · {pos.contract_month} · {pos.position_type} · opened {pos.date_opened.slice(0, 10)}
        </span>
      </p>
      <div className="grid grid-cols-3 gap-2">
        <FormRow label="Strike ($)">
          <input type="number" step="0.01" value={strike} onChange={e => setStrike(e.target.value)} className={INPUT} />
        </FormRow>
        <FormRow label="Premium ($/bu)">
          <input type="number" step="0.001" value={premium} onChange={e => setPremium(e.target.value)} className={INPUT} />
        </FormRow>
        <FormRow label="# Contracts">
          <input type="number" min={1} value={numContracts} onChange={e => setNumContracts(e.target.value)} className={INPUT} />
        </FormRow>
        <FormRow label="Delta at entry">
          <input type="number" step="0.01" min="0.01" max="1" value={delta} onChange={e => setDelta(e.target.value)} className={INPUT} />
        </FormRow>
        <FormRow label="Phase">
          <select value={phase} onChange={e => setPhase(parseInt(e.target.value, 10) as Phase)} className={INPUT}>
            <option value={1}>1 — Puts</option>
            <option value={2}>2 — Calls</option>
          </select>
        </FormRow>
        {(phase === 2 || pos.cash_sale_price != null) && (
          <FormRow label="Cash sale ($/bu)">
            <input type="number" step="0.01" value={cashSale} onChange={e => setCashSale(e.target.value)} className={INPUT} />
          </FormRow>
        )}
      </div>
      <FormRow label="Notes">
        <input type="text" value={notes} onChange={e => setNotes(e.target.value)} className={INPUT} />
      </FormRow>
      {error && <p className="text-xs text-[#ef4444]">{error}</p>}
      <div className="flex gap-2">
        <ActionBtn label={isPending ? "Saving…" : "Save changes"} onClick={() => {}} variant="confirm" disabled={isPending} />
        <ActionBtn label="Cancel" onClick={onCancel} />
      </div>
    </form>
  );
}

// ── Delete confirm ────────────────────────────────────────────────────────────

function DeleteConfirm({
  pos,
  onSuccess,
  onCancel,
}: {
  pos: Position;
  onSuccess: () => void;
  onCancel: () => void;
}) {
  const [error, setError] = useState<string | null>(null);
  const [isPending, startTransition] = useTransition();

  function handleDelete() {
    startTransition(async () => {
      try {
        await deletePosition(pos.id);
        onSuccess();
      } catch (e) {
        setError(e instanceof Error ? e.message : "Failed to delete position");
      }
    });
  }

  return (
    <div className="bg-[#0d1117] rounded border border-[#ef444440] p-3 space-y-2">
      <p className="text-xs text-[#ef4444]">
        ⚠ This removes the position from all calculations. The record is retained in the database for audit purposes.
      </p>
      {error && <p className="text-xs text-[#ef4444]">{error}</p>}
      <div className="flex gap-2">
        <ActionBtn label={isPending ? "Deleting…" : "Confirm delete"} onClick={handleDelete} variant="danger" disabled={isPending} />
        <ActionBtn label="Cancel" onClick={onCancel} />
      </div>
    </div>
  );
}

// ── Main component ────────────────────────────────────────────────────────────

export default function PositionActions({ pos }: { pos: Position }) {
  const router = useRouter();
  const [mode, setMode] = useState<ActionMode>(null);

  function cancel() { setMode(null); }
  function refresh() { router.refresh(); cancel(); }

  return (
    <div className="pt-2 border-t border-[#1e2535] space-y-2">
      {mode === null && (
        <div className="flex gap-1.5 flex-wrap">
          <ActionBtn label="Close position" onClick={() => setMode("close")} />
          <ActionBtn label="Mark expired" onClick={() => setMode("expire")} />
          <ActionBtn label="Edit" onClick={() => setMode("edit")} />
          <ActionBtn label="Delete" onClick={() => setMode("delete")} variant="danger" />
        </div>
      )}
      {mode === "close"  && <CloseForm   pos={pos} onSuccess={refresh} onCancel={cancel} />}
      {mode === "expire" && <ExpireForm  pos={pos} onSuccess={refresh} onCancel={cancel} />}
      {mode === "edit"   && <EditForm    pos={pos} onSuccess={refresh} onCancel={cancel} />}
      {mode === "delete" && <DeleteConfirm pos={pos} onSuccess={refresh} onCancel={cancel} />}
    </div>
  );
}
