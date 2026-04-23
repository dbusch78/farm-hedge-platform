"use client";

import { useState, useTransition } from "react";
import { runScenario } from "@/lib/api";
import type { ScenarioRow, Phase } from "@/lib/types";

interface Props {
  strike: number;
  totalPremiumPerBu: number;
  expectedBushels: number;
  deltaAtEntry: number;
  phase: Phase;
  cashSalePrice?: number | null;
  currentFuturesPrice?: number | null;
}

export default function ScenarioModeler({
  strike,
  totalPremiumPerBu,
  expectedBushels,
  deltaAtEntry,
  phase,
  cashSalePrice,
  currentFuturesPrice,
}: Props) {
  const [minPrice, setMinPrice] = useState(
    currentFuturesPrice ? Math.floor(currentFuturesPrice * 0.8 * 20) / 20 : strike * 0.8,
  );
  const [maxPrice, setMaxPrice] = useState(
    currentFuturesPrice ? Math.ceil(currentFuturesPrice * 1.2 * 20) / 20 : strike * 1.2,
  );
  const [steps, setSteps] = useState(10);
  const [rows, setRows] = useState<ScenarioRow[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isPending, startTransition] = useTransition();

  function buildPrices(): number[] {
    const range = maxPrice - minPrice;
    const step = range / (steps - 1);
    return Array.from({ length: steps }, (_, i) =>
      parseFloat((minPrice + step * i).toFixed(4)),
    );
  }

  function handleRun() {
    setError(null);
    startTransition(async () => {
      try {
        const prices = buildPrices();
        const data = await runScenario({
          hypothetical_prices: prices,
          strike,
          total_premiums_paid_per_bu: totalPremiumPerBu,
          expected_bushels: expectedBushels,
          delta_at_entry: deltaAtEntry,
          phase,
          cash_sale_price: cashSalePrice ?? null,
          call_premium_paid_per_bu: phase === 2 ? totalPremiumPerBu : null,
        });
        setRows(data);
      } catch (e) {
        setError(e instanceof Error ? e.message : "Failed to run scenario");
      }
    });
  }

  return (
    <div className="space-y-4">
      <h3 className="text-sm font-semibold text-[#e8edf5]">Scenario Modeler</h3>

      {/* Controls */}
      <div className="grid grid-cols-3 gap-3">
        <Field label="Min futures price ($)">
          <input
            type="number"
            step="0.05"
            value={minPrice}
            onChange={(e) => setMinPrice(parseFloat(e.target.value))}
            className="input-dark"
          />
        </Field>
        <Field label="Max futures price ($)">
          <input
            type="number"
            step="0.05"
            value={maxPrice}
            onChange={(e) => setMaxPrice(parseFloat(e.target.value))}
            className="input-dark"
          />
        </Field>
        <Field label="Steps">
          <input
            type="number"
            min={3}
            max={20}
            value={steps}
            onChange={(e) => setSteps(parseInt(e.target.value, 10))}
            className="input-dark"
          />
        </Field>
      </div>

      <button
        onClick={handleRun}
        disabled={isPending}
        className="px-4 py-2 text-sm font-semibold bg-[#22c55e20] text-[#22c55e] border border-[#22c55e40] rounded hover:bg-[#22c55e30] transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
      >
        {isPending ? "Running…" : "Run Scenario"}
      </button>

      {error && (
        <p className="text-xs text-[#ef4444] bg-[#ef444410] border border-[#ef444440] rounded px-3 py-2">
          {error}
        </p>
      )}

      {/* Results table */}
      {rows && rows.length > 0 && (
        <div className="overflow-x-auto rounded-lg border border-[#2a3044]">
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-[#2a3044] bg-[#141920]">
                <Th>Futures</Th>
                {phase === 1 ? <Th>Put Value</Th> : <Th>Call Value</Th>}
                <Th>Premiums Paid</Th>
                <Th>Net Eff. Price</Th>
                <Th>Total P&amp;L</Th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row, i) => {
                const isAtStrike = Math.abs(row.futures_price - strike) < 0.03;
                const isCurrent =
                  currentFuturesPrice != null &&
                  Math.abs(row.futures_price - currentFuturesPrice) <
                    (maxPrice - minPrice) / (steps * 2);

                return (
                  <tr
                    key={i}
                    className={`border-b border-[#1e2535] ${
                      isCurrent
                        ? "bg-[#3b82f615]"
                        : i % 2 === 0
                          ? "bg-[#1a1f2e]"
                          : "bg-[#141920]"
                    }`}
                  >
                    <Td highlight={isCurrent}>
                      ${row.futures_price.toFixed(2)}
                      {isAtStrike && (
                        <span className="ml-1 text-[#f59e0b]">← strike</span>
                      )}
                      {isCurrent && (
                        <span className="ml-1 text-[#3b82f6]">← current</span>
                      )}
                    </Td>
                    <Td>
                      ${(phase === 1 ? row.put_intrinsic : row.call_intrinsic).toFixed(4)}
                    </Td>
                    <Td negative>${row.premiums_paid.toFixed(4)}</Td>
                    <Td highlight>
                      <span className="font-semibold">
                        ${row.net_effective_price.toFixed(4)}
                      </span>
                    </Td>
                    <Td positive={row.net_effective_price >= row.futures_price}>
                      ${((row.net_effective_price - row.futures_price) * expectedBushels).toFixed(0)}
                    </Td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
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

function Th({ children }: { children: React.ReactNode }) {
  return (
    <th className="text-left px-3 py-2 text-[10px] uppercase tracking-widest text-[#7b8aab] font-medium">
      {children}
    </th>
  );
}

function Td({
  children,
  highlight = false,
  positive,
  negative = false,
}: {
  children: React.ReactNode;
  highlight?: boolean;
  positive?: boolean;
  negative?: boolean;
}) {
  return (
    <td
      className={`px-3 py-2 tabular-nums ${
        highlight
          ? "text-[#e8edf5]"
          : negative
            ? "text-[#f59e0b]"
            : positive === true
              ? "text-[#22c55e]"
              : positive === false
                ? "text-[#ef4444]"
                : "text-[#c4cfe8]"
      }`}
    >
      {children}
    </td>
  );
}
