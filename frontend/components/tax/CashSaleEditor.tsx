"use client";

import { useState, useTransition } from "react";
import { useRouter } from "next/navigation";
import type { CashSale } from "@/lib/types";
import { updateCashSale } from "@/lib/api";

interface Props {
  sale: CashSale;
}

export default function CashSaleEditor({ sale }: Props) {
  const router = useRouter();
  const [editing, setEditing] = useState(false);
  const [isPending, startTransition] = useTransition();
  const [error, setError] = useState<string | null>(null);

  const [form, setForm] = useState({
    sale_date: sale.sale_date ?? "",
    delivery_location: sale.delivery_location ?? "",
    selling_entity: sale.selling_entity ?? "",
    contract_settlement_id: sale.contract_settlement_id ?? "",
    notes: sale.notes ?? "",
    adjustments: String(sale.adjustments ?? 0),
    trucking_per_bu: String(sale.trucking_per_bu ?? ""),
  });

  function handleChange(e: React.ChangeEvent<HTMLInputElement>) {
    setForm((prev) => ({ ...prev, [e.target.name]: e.target.value }));
  }

  function handleSave() {
    setError(null);
    startTransition(async () => {
      try {
        await updateCashSale(sale.id, {
          sale_date: form.sale_date || undefined,
          delivery_location: form.delivery_location || null,
          selling_entity: form.selling_entity || null,
          contract_settlement_id: form.contract_settlement_id || null,
          notes: form.notes || undefined,
          adjustments: form.adjustments ? parseFloat(form.adjustments) : undefined,
          trucking_per_bu: form.trucking_per_bu ? parseFloat(form.trucking_per_bu) : null,
        });
        setEditing(false);
        router.refresh();
      } catch (err) {
        setError(err instanceof Error ? err.message : "Save failed");
      }
    });
  }

  const cellCls = "py-2 pr-3 text-[#7b8aab]";
  const inputCls =
    "w-full bg-[#0d1117] border border-[#2a3044] rounded px-1.5 py-1 text-[#e8edf5] text-xs focus:outline-none focus:border-[#3b82f6]";

  if (editing) {
    return (
      <>
        <tr className="bg-[#0d111790] text-[#e8edf5]">
          <td className={cellCls}>
            <input
              name="sale_date"
              type="date"
              value={form.sale_date}
              onChange={handleChange}
              className={inputCls}
              style={{ width: 120 }}
            />
          </td>
          <td className={cellCls}>{sale.bushels.toLocaleString()}</td>
          <td className={cellCls}>${sale.cash_price_per_bu.toFixed(4)}</td>
          <td className={cellCls}>${sale.gross_amount.toLocaleString("en-US", { minimumFractionDigits: 2 })}</td>
          <td className={cellCls}>
            <input
              name="adjustments"
              value={form.adjustments}
              onChange={handleChange}
              className={inputCls}
              placeholder="0.00"
              style={{ width: 70 }}
            />
          </td>
          <td className={cellCls}>
            <input
              name="trucking_per_bu"
              value={form.trucking_per_bu}
              onChange={handleChange}
              className={inputCls}
              placeholder="$/bu"
              style={{ width: 60 }}
            />
          </td>
          <td className={cellCls}>
            {/* recompute net optimistically */}
            ${(
              sale.gross_amount
              - parseFloat(form.adjustments || "0")
              - (form.trucking_per_bu ? parseFloat(form.trucking_per_bu) * sale.bushels : (sale.trucking_total ?? 0))
            ).toLocaleString("en-US", { minimumFractionDigits: 2 })}
          </td>
          <td className={cellCls}>
            <input
              name="delivery_location"
              value={form.delivery_location}
              onChange={handleChange}
              className={inputCls}
              placeholder="Location"
              style={{ width: 100 }}
            />
          </td>
          <td className={cellCls}>
            <input
              name="selling_entity"
              value={form.selling_entity}
              onChange={handleChange}
              className={inputCls}
              placeholder="Entity"
              style={{ width: 100 }}
            />
          </td>
          <td className={cellCls}>
            <input
              name="contract_settlement_id"
              value={form.contract_settlement_id}
              onChange={handleChange}
              className={inputCls}
              placeholder="Settlement #"
              style={{ width: 90 }}
            />
          </td>
          <td className="py-2">
            <input
              name="notes"
              value={form.notes}
              onChange={handleChange}
              className={inputCls}
              placeholder="Notes"
              style={{ width: 120 }}
            />
          </td>
        </tr>
        <tr className="bg-[#0d111790]">
          <td colSpan={11} className="pb-2 pt-0.5 pr-3">
            <div className="flex items-center gap-2">
              <button
                onClick={handleSave}
                disabled={isPending}
                className="px-3 py-1 bg-[#3b82f6] hover:bg-[#2563eb] text-white text-xs rounded disabled:opacity-50"
              >
                {isPending ? "Saving…" : "Save"}
              </button>
              <button
                onClick={() => { setEditing(false); setError(null); }}
                className="px-3 py-1 bg-[#1e2535] hover:bg-[#2a3044] text-[#7b8aab] text-xs rounded"
              >
                Cancel
              </button>
              {error && <span className="text-xs text-[#ef4444]">{error}</span>}
              {sale.migrated && (
                <span className="text-[10px] text-[#f59e0b] ml-2">Migrated record — fill in any missing fields</span>
              )}
            </div>
          </td>
        </tr>
      </>
    );
  }

  return (
    <tr
      className="text-[#7b8aab] hover:text-[#e8edf5] hover:bg-[#1e253580] cursor-pointer transition-colors"
      onClick={() => setEditing(true)}
      title="Click to edit"
    >
      <td className={cellCls}>{sale.sale_date}</td>
      <td className={cellCls}>{sale.bushels.toLocaleString()}</td>
      <td className={cellCls}>${sale.cash_price_per_bu.toFixed(4)}</td>
      <td className={cellCls}>${sale.gross_amount.toLocaleString("en-US", { minimumFractionDigits: 2 })}</td>
      <td className={cellCls}>${sale.adjustments.toFixed(2)}</td>
      <td className={cellCls}>
        {sale.trucking_total != null ? `$${sale.trucking_total.toFixed(2)}` : "—"}
      </td>
      <td className="py-2 pr-3 text-[#a3e635] font-medium">
        ${sale.net_amount.toLocaleString("en-US", { minimumFractionDigits: 2 })}
      </td>
      <td className={cellCls}>
        {sale.delivery_location ?? <span className="text-[#ef444480] italic">missing</span>}
      </td>
      <td className={cellCls}>
        {sale.selling_entity ?? <span className="text-[#ef444480] italic">missing</span>}
      </td>
      <td className={cellCls}>
        {sale.contract_settlement_id ?? <span className="text-[#ef444480] italic">missing</span>}
      </td>
      <td className="py-2 text-[#4a5568]">{sale.notes || "—"}</td>
    </tr>
  );
}
