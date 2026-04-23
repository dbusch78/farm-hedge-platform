"use client";

import { useState, useTransition } from "react";
import { createPosition } from "@/lib/api";
import type { Commodity, Phase, PositionType } from "@/lib/types";

interface Props {
  onSuccess?: () => void;
}

interface FormState {
  commodity: Commodity;
  contract_month: string;
  position_type: PositionType;
  strike: string;
  premium_paid_per_bu: string;
  num_contracts: string;
  delta_at_entry: string;
  expected_bushels: string;
  phase: Phase;
  date_opened: string;
  cash_sale_price: string;
  notes: string;
}

const INITIAL: FormState = {
  commodity: "ZC",
  contract_month: "Jul25",
  position_type: "put",
  strike: "",
  premium_paid_per_bu: "",
  num_contracts: "",
  delta_at_entry: "",
  expected_bushels: "",
  phase: 1,
  date_opened: new Date().toISOString().slice(0, 10),
  cash_sale_price: "",
  notes: "",
};

export default function PositionEntry({ onSuccess }: Props) {
  const [form, setForm] = useState<FormState>(INITIAL);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [isPending, startTransition] = useTransition();

  function set<K extends keyof FormState>(k: K, v: FormState[K]) {
    setForm((prev) => ({ ...prev, [k]: v }));
  }

  // Live delta-adjusted contract count
  const expectedBu = parseInt(form.expected_bushels, 10);
  const delta = parseFloat(form.delta_at_entry);
  const rawContracts = !isNaN(expectedBu) ? expectedBu / 5000 : null;
  const deltaAdj =
    rawContracts != null && !isNaN(delta) && delta > 0
      ? rawContracts / delta
      : null;

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setSuccess(null);

    startTransition(async () => {
      try {
        const body = {
          commodity: form.commodity,
          contract_month: form.contract_month,
          position_type: form.position_type,
          strike: parseFloat(form.strike),
          premium_paid_per_bu: parseFloat(form.premium_paid_per_bu),
          num_contracts: parseInt(form.num_contracts, 10),
          delta_at_entry: parseFloat(form.delta_at_entry),
          expected_bushels: parseInt(form.expected_bushels, 10),
          phase: form.phase,
          date_opened: new Date(form.date_opened).toISOString(),
          cash_sale_price:
            form.phase === 2 && form.cash_sale_price
              ? parseFloat(form.cash_sale_price)
              : null,
          notes: form.notes,
        };
        const result = await createPosition(body);
        setSuccess(`Position created (ID: ${result.id})`);
        setForm(INITIAL);
        onSuccess?.();
      } catch (e) {
        setError(e instanceof Error ? e.message : "Failed to create position");
      }
    });
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <h3 className="text-sm font-semibold text-[#e8edf5]">Add Position</h3>

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
        <Field label="Commodity">
          <select
            value={form.commodity}
            onChange={(e) => set("commodity", e.target.value as Commodity)}
            className="input-dark"
          >
            <option value="ZC">ZC — Corn</option>
            <option value="ZS">ZS — Soybeans</option>
          </select>
        </Field>

        <Field label="Contract month">
          <input
            type="text"
            value={form.contract_month}
            onChange={(e) => set("contract_month", e.target.value)}
            placeholder="Jul25"
            required
            className="input-dark"
          />
        </Field>

        <Field label="Type">
          <select
            value={form.position_type}
            onChange={(e) => {
              const t = e.target.value as PositionType;
              set("position_type", t);
              if (t === "call") set("phase", 2);
              if (t === "put") set("phase", 1);
            }}
            className="input-dark"
          >
            <option value="put">Put (Phase 1)</option>
            <option value="call">Call (Phase 2)</option>
          </select>
        </Field>

        <Field label="Strike ($)">
          <input
            type="number"
            step="0.01"
            value={form.strike}
            onChange={(e) => set("strike", e.target.value)}
            placeholder="4.20"
            required
            className="input-dark"
          />
        </Field>

        <Field label="Premium paid ($/bu)">
          <input
            type="number"
            step="0.001"
            value={form.premium_paid_per_bu}
            onChange={(e) => set("premium_paid_per_bu", e.target.value)}
            placeholder="0.14"
            required
            className="input-dark"
          />
        </Field>

        <Field label="# Contracts">
          <input
            type="number"
            min={1}
            value={form.num_contracts}
            onChange={(e) => set("num_contracts", e.target.value)}
            placeholder="9"
            required
            className="input-dark"
          />
        </Field>

        <Field label="Delta at entry">
          <input
            type="number"
            step="0.01"
            min="0.01"
            max="1"
            value={form.delta_at_entry}
            onChange={(e) => set("delta_at_entry", e.target.value)}
            placeholder="0.40"
            required
            className="input-dark"
          />
        </Field>

        <Field label="Expected bushels">
          <input
            type="number"
            step="1000"
            value={form.expected_bushels}
            onChange={(e) => set("expected_bushels", e.target.value)}
            placeholder="45000"
            required
            className="input-dark"
          />
        </Field>

        <Field label="Date opened">
          <input
            type="date"
            value={form.date_opened}
            onChange={(e) => set("date_opened", e.target.value)}
            required
            className="input-dark"
          />
        </Field>

        {form.phase === 2 && (
          <Field label="Cash sale price ($/bu)">
            <input
              type="number"
              step="0.01"
              value={form.cash_sale_price}
              onChange={(e) => set("cash_sale_price", e.target.value)}
              placeholder="11.42"
              required
              className="input-dark"
            />
          </Field>
        )}
      </div>

      {/* Delta-adjusted contract count (live) */}
      {rawContracts !== null && (
        <div className="bg-[#141920] border border-[#2a3044] rounded px-3 py-2 text-xs space-y-0.5">
          <p className="text-[#7b8aab]">
            Raw contracts (expected bu ÷ 5,000):{" "}
            <span className="text-[#e8edf5] font-semibold">
              {rawContracts.toFixed(2)}
            </span>
          </p>
          {deltaAdj !== null && (
            <p className="text-[#7b8aab]">
              Delta-adjusted contracts (÷ {delta}):{" "}
              <span className="text-[#a3e635] font-semibold">
                {deltaAdj.toFixed(2)}
              </span>
            </p>
          )}
        </div>
      )}

      <Field label="Notes (optional)">
        <textarea
          value={form.notes}
          onChange={(e) => set("notes", e.target.value)}
          rows={2}
          placeholder="Entry rationale, market context…"
          className="input-dark resize-none"
        />
      </Field>

      {error && (
        <p className="text-xs text-[#ef4444] bg-[#ef444410] border border-[#ef444440] rounded px-3 py-2">
          {error}
        </p>
      )}
      {success && (
        <p className="text-xs text-[#22c55e] bg-[#22c55e10] border border-[#22c55e40] rounded px-3 py-2">
          {success}
        </p>
      )}

      <button
        type="submit"
        disabled={isPending}
        className="px-4 py-2 text-sm font-semibold bg-[#22c55e20] text-[#22c55e] border border-[#22c55e40] rounded hover:bg-[#22c55e30] transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
      >
        {isPending ? "Saving…" : "Save Position"}
      </button>
    </form>
  );
}

function Field({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <div>
      <label className="block text-[10px] uppercase tracking-widest text-[#7b8aab] mb-1">
        {label}
      </label>
      {children}
    </div>
  );
}
