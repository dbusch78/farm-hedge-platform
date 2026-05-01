"use client";

import { useState, useTransition } from "react";
import { createPosition } from "@/lib/api";
import type { CashSale, Commodity, Phase, PositionType } from "@/lib/types";

interface Props {
  cashSales?: CashSale[];
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
  // Phase 1 — HEDGE
  hedge_documentation: string;
  irc_1221_acknowledgment: boolean;
  // Phase 2 — SPECULATIVE
  linked_cash_sale_ids: string[];
  speculative_acknowledgment: boolean;
}

const INITIAL: FormState = {
  commodity: "ZC",
  contract_month: "ZCN26",
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
  hedge_documentation: "",
  irc_1221_acknowledgment: false,
  linked_cash_sale_ids: [],
  speculative_acknowledgment: false,
};

export default function PositionEntry({ cashSales = [], onSuccess }: Props) {
  const [form, setForm] = useState<FormState>(INITIAL);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [isPending, startTransition] = useTransition();

  function set<K extends keyof FormState>(k: K, v: FormState[K]) {
    setForm((prev) => ({ ...prev, [k]: v }));
  }

  function toggleLinkedSale(id: string) {
    setForm((prev) => ({
      ...prev,
      linked_cash_sale_ids: prev.linked_cash_sale_ids.includes(id)
        ? prev.linked_cash_sale_ids.filter((x) => x !== id)
        : [...prev.linked_cash_sale_ids, id],
    }));
  }

  // Live delta-adjusted contract count
  const expectedBu = parseInt(form.expected_bushels, 10);
  const delta = parseFloat(form.delta_at_entry);
  const rawContracts = !isNaN(expectedBu) ? expectedBu / 5000 : null;
  const deltaAdj =
    rawContracts != null && !isNaN(delta) && delta > 0
      ? rawContracts / delta
      : null;

  const isPhase1 = form.position_type === "put";
  const relevantSales = cashSales.filter((s) => s.commodity === form.commodity);

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setSuccess(null);

    // Frontend gate: Phase 1 requires acknowledgment if documentation is entered
    if (isPhase1 && form.hedge_documentation && !form.irc_1221_acknowledgment) {
      setError("Check the IRC §1221 acknowledgment to confirm hedge identification.");
      return;
    }

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
          // Tax fields
          hedge_documentation: isPhase1 && form.hedge_documentation
            ? form.hedge_documentation
            : undefined,
          irc_1221_acknowledgment: isPhase1 ? form.irc_1221_acknowledgment : undefined,
          linked_cash_sale_ids: !isPhase1 ? form.linked_cash_sale_ids : undefined,
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
            placeholder="ZCN26"
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
            <option value="put">Put (Phase 1 — Hedge)</option>
            <option value="call">Call (Phase 2 — Speculative)</option>
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

      {/* ── Phase 1: HEDGE documentation ───────────────────────────────────── */}
      {isPhase1 && (
        <div className="border border-[#a3e63540] bg-[#a3e63508] rounded-lg p-4 space-y-3">
          <p className="text-xs font-semibold text-[#a3e635] uppercase tracking-wide">
            IRC §1221 Hedge Identification
          </p>
          <p className="text-[11px] text-[#7b8aab]">
            Identification must be made before the close of trading on the day of entry.
            This timestamp is locked once saved.
          </p>

          <Field label="Hedge documentation statement">
            <textarea
              value={form.hedge_documentation}
              onChange={(e) => set("hedge_documentation", e.target.value)}
              rows={2}
              placeholder="e.g. Hedging anticipated ZC corn harvest, 2026 crop year, Dennis C. Busch Farm"
              className="input-dark resize-none w-full"
            />
          </Field>

          <div className="flex items-start gap-2 text-xs text-[#7b8aab]">
            <span className="text-[#4a5568]">Identification date:</span>
            <span className="text-[#e8edf5]">{form.date_opened}</span>
            <span className="text-[#4a5568]">(UTC, locked on save)</span>
          </div>

          <label className="flex items-start gap-2 cursor-pointer group">
            <input
              type="checkbox"
              checked={form.irc_1221_acknowledgment}
              onChange={(e) => set("irc_1221_acknowledgment", e.target.checked)}
              className="mt-0.5 accent-[#a3e635]"
            />
            <span className="text-[11px] text-[#7b8aab] group-hover:text-[#e8edf5] transition-colors leading-relaxed">
              I identify this as a hedge transaction under IRC §1221 as of the date and
              time of entry. I understand this identification is contemporaneous and
              cannot be changed after the close of trading today.
            </span>
          </label>
        </div>
      )}

      {/* ── Phase 2: SPECULATIVE — cash sale linkage ────────────────────────── */}
      {!isPhase1 && (
        <div className="border border-[#3b82f640] bg-[#3b82f608] rounded-lg p-4 space-y-3">
          <p className="text-xs font-semibold text-[#3b82f6] uppercase tracking-wide">
            Section 1256 Speculative Position
          </p>

          {relevantSales.length > 0 ? (
            <div className="space-y-1.5">
              <p className="text-[11px] text-[#7b8aab]">
                Link to related cash sale(s) — informational only, no bushel match
                required. You can link zero, one, or multiple.
              </p>
              {relevantSales.map((sale) => {
                const checked = form.linked_cash_sale_ids.includes(sale.id);
                return (
                  <label
                    key={sale.id}
                    className="flex items-center gap-2 cursor-pointer group"
                  >
                    <input
                      type="checkbox"
                      checked={checked}
                      onChange={() => toggleLinkedSale(sale.id)}
                      className="accent-[#3b82f6]"
                    />
                    <span className={`text-xs transition-colors ${checked ? "text-[#e8edf5]" : "text-[#7b8aab] group-hover:text-[#e8edf5]"}`}>
                      {sale.sale_date} &bull; {sale.bushels.toLocaleString()} bu @{" "}
                      ${sale.cash_price_per_bu.toFixed(4)}/bu
                      {sale.delivery_location && (
                        <span className="text-[#4a5568]"> — {sale.delivery_location}</span>
                      )}
                    </span>
                  </label>
                );
              })}
            </div>
          ) : (
            <p className="text-[11px] text-[#4a5568] italic">
              No {form.commodity} cash sales on record.{" "}
              <a href="/tax" className="text-[#3b82f6] hover:underline">Add one in Tax →</a>
            </p>
          )}

          <label className="flex items-start gap-2 cursor-pointer group">
            <input
              type="checkbox"
              checked={form.speculative_acknowledgment}
              onChange={(e) => set("speculative_acknowledgment", e.target.checked)}
              className="mt-0.5 accent-[#3b82f6]"
            />
            <span className="text-[11px] text-[#7b8aab] group-hover:text-[#e8edf5] transition-colors leading-relaxed">
              I acknowledge this is a speculative position subject to IRC §1256
              mark-to-market treatment. Open positions will be valued at fair market
              value on December 31. Gains and losses are treated as 60% long-term /
              40% short-term capital gains regardless of holding period.
            </span>
          </label>
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
