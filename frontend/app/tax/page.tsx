import { getCashSales, getTaxSummary } from "@/lib/api";
import type { CashSale, TaxSummary } from "@/lib/types";
import CashSaleEditor from "@/components/tax/CashSaleEditor";

export const dynamic = "force-dynamic";

async function safeFetch<T>(fn: () => Promise<T>): Promise<T | null> {
  try {
    return await fn();
  } catch {
    return null;
  }
}

function fmt(n: number, d = 2) {
  return n.toFixed(d);
}

function fmtDollar(n: number) {
  const sign = n < 0 ? "-" : n > 0 ? "+" : "";
  return `${sign}$${Math.abs(n).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

export default async function TaxPage() {
  const [sales, summary] = await Promise.all([
    safeFetch(() => getCashSales()),
    safeFetch(() => getTaxSummary()),
  ]);

  const cashSales: CashSale[] = sales ?? [];
  const taxSummary: TaxSummary | null = summary;

  const zcSales = cashSales.filter((s) => s.commodity === "ZC");
  const zsSales = cashSales.filter((s) => s.commodity === "ZS");

  return (
    <div className="space-y-8">
      <div className="flex items-center justify-between">
        <h1 className="text-lg font-semibold text-[#e8edf5]">Tax Records</h1>
        <a href="/" className="text-xs text-[#3b82f6] hover:underline">
          ← Dashboard
        </a>
      </div>

      {/* ── Tax summary ──────────────────────────────────────────────────────── */}
      {taxSummary && (
        <section className="bg-[#1a1f2e] rounded-lg border border-[#2a3044] p-5 space-y-4">
          <h2 className="text-sm font-semibold text-[#e8edf5]">
            {taxSummary.tax_year} Tax Summary
          </h2>

          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            <SummaryCard
              label="Hedge P&L (Schedule F)"
              value={fmtDollar(taxSummary.hedge_realized_total)}
              subLabel="Ordinary income"
              color={taxSummary.hedge_realized_total >= 0 ? "text-[#a3e635]" : "text-[#ef4444]"}
            />
            <SummaryCard
              label="Speculative Realized"
              value={fmtDollar(taxSummary.speculative_realized_total)}
              subLabel="Sec. 1256 realized"
              color={taxSummary.speculative_realized_total >= 0 ? "text-[#a3e635]" : "text-[#ef4444]"}
            />
            <SummaryCard
              label="Speculative MTM"
              value={fmtDollar(taxSummary.speculative_mtm_total)}
              subLabel="Open positions Dec 31"
              color={taxSummary.speculative_mtm_total >= 0 ? "text-[#a3e635]" : "text-[#ef4444]"}
            />
            <SummaryCard
              label="Sec. 1256 Total"
              value={fmtDollar(taxSummary.speculative_section_1256_total)}
              subLabel={`60/40 split: LTCG ${fmtDollar(taxSummary.ltcg_60pct)} / STCG ${fmtDollar(taxSummary.stcg_40pct)}`}
              color={taxSummary.speculative_section_1256_total >= 0 ? "text-[#a3e635]" : "text-[#ef4444]"}
            />
          </div>

          <p className="text-[10px] text-[#4a5568]">
            Hedge positions (Phase 1 puts) → Schedule F ordinary income. Speculative positions
            (Phase 2 calls) → Form 6781, marked to market Dec 31, 60% LTCG / 40% STCG.
          </p>
        </section>
      )}

      {/* ── Cash sales ───────────────────────────────────────────────────────── */}
      <SalesSection
        label="Corn Cash Sales"
        icon="🌽"
        commodity="ZC"
        sales={zcSales}
      />
      <SalesSection
        label="Soybean Cash Sales"
        icon="🌱"
        commodity="ZS"
        sales={zsSales}
      />

      {cashSales.length === 0 && (
        <div className="bg-[#f59e0b10] border border-[#f59e0b40] rounded-lg px-4 py-3 text-xs text-[#f59e0b]">
          No cash sales found. Run the migration script or add a new sale.
        </div>
      )}

      {/* ── Position tax classification ───────────────────────────────────── */}
      {taxSummary && taxSummary.positions.length > 0 && (
        <section className="bg-[#1a1f2e] rounded-lg border border-[#2a3044] p-5 space-y-3">
          <h2 className="text-sm font-semibold text-[#e8edf5]">Position Tax Classification</h2>
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="text-left text-[#4a5568] border-b border-[#1e2535]">
                  <th className="pb-2 pr-3">Commodity</th>
                  <th className="pb-2 pr-3">Contract</th>
                  <th className="pb-2 pr-3">Type</th>
                  <th className="pb-2 pr-3">Strike</th>
                  <th className="pb-2 pr-3">Bushels</th>
                  <th className="pb-2 pr-3">Opened</th>
                  <th className="pb-2 pr-3">Treatment</th>
                  <th className="pb-2 pr-3">Status</th>
                  <th className="pb-2 pr-3">Realized P&L</th>
                  <th className="pb-2">MTM P&L</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#1e2535]">
                {taxSummary.positions.map((pos) => {
                  const isHedge = pos.tax_treatment === "HEDGE";
                  return (
                    <tr key={pos.id} className="text-[#7b8aab] hover:text-[#e8edf5] transition-colors">
                      <td className="py-2 pr-3 font-medium text-[#e8edf5]">{pos.commodity}</td>
                      <td className="py-2 pr-3">{pos.contract_month}</td>
                      <td className="py-2 pr-3 capitalize">{pos.position_type}</td>
                      <td className="py-2 pr-3">${fmt(pos.strike)}</td>
                      <td className="py-2 pr-3">{pos.expected_bushels.toLocaleString()}</td>
                      <td className="py-2 pr-3">{pos.date_opened}</td>
                      <td className="py-2 pr-3">
                        <span className={`px-1.5 py-0.5 rounded text-[10px] font-medium ${
                          isHedge
                            ? "bg-[#a3e63520] text-[#a3e635]"
                            : "bg-[#3b82f620] text-[#3b82f6]"
                        }`}>
                          {pos.tax_treatment}
                        </span>
                      </td>
                      <td className="py-2 pr-3">
                        <span className={`text-[10px] ${
                          pos.status === "ACTIVE" ? "text-[#a3e635]" :
                          pos.status === "CLOSED" ? "text-[#7b8aab]" :
                          "text-[#f59e0b]"
                        }`}>{pos.status}</span>
                      </td>
                      <td className="py-2 pr-3">
                        {pos.realized_pnl_total != null ? (
                          <span className={pos.realized_pnl_total >= 0 ? "text-[#a3e635]" : "text-[#ef4444]"}>
                            {fmtDollar(pos.realized_pnl_total)}
                          </span>
                        ) : "—"}
                      </td>
                      <td className="py-2">
                        {pos.options_pnl_total != null && pos.status === "ACTIVE" ? (
                          <span className={pos.options_pnl_total >= 0 ? "text-[#a3e635]" : "text-[#ef4444]"}>
                            {fmtDollar(pos.options_pnl_total)}
                          </span>
                        ) : "—"}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </section>
      )}
    </div>
  );
}


// ── Sub-components ─────────────────────────────────────────────────────────────

function SummaryCard({
  label,
  value,
  subLabel,
  color,
}: {
  label: string;
  value: string;
  subLabel: string;
  color: string;
}) {
  return (
    <div className="bg-[#0d1117] rounded border border-[#2a3044] p-3 space-y-1">
      <div className="text-[10px] text-[#4a5568] uppercase tracking-wide">{label}</div>
      <div className={`text-base font-semibold ${color}`}>{value}</div>
      <div className="text-[10px] text-[#4a5568]">{subLabel}</div>
    </div>
  );
}

function SalesSection({
  label,
  icon,
  commodity,
  sales,
}: {
  label: string;
  icon: string;
  commodity: string;
  sales: CashSale[];
}) {
  if (sales.length === 0) return null;

  const totalBushels = sales.reduce((s, r) => s + r.bushels, 0);
  const totalNet = sales.reduce((s, r) => s + r.net_amount, 0);
  const avgPrice = totalBushels > 0 ? totalNet / totalBushels : 0;

  return (
    <section className="bg-[#1a1f2e] rounded-lg border border-[#2a3044] p-5 space-y-3">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-semibold text-[#e8edf5]">
          {icon} {label}
        </h2>
        <div className="text-xs text-[#4a5568]">
          {totalBushels.toLocaleString()} bu &bull; avg ${avgPrice.toFixed(2)}/bu net
        </div>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-xs">
          <thead>
            <tr className="text-left text-[#4a5568] border-b border-[#1e2535]">
              <th className="pb-2 pr-3">Date</th>
              <th className="pb-2 pr-3">Bushels</th>
              <th className="pb-2 pr-3">Cash Price</th>
              <th className="pb-2 pr-3">Gross</th>
              <th className="pb-2 pr-3">Adjustments</th>
              <th className="pb-2 pr-3">Trucking</th>
              <th className="pb-2 pr-3">Net</th>
              <th className="pb-2 pr-3">Location</th>
              <th className="pb-2 pr-3">Entity</th>
              <th className="pb-2 pr-3">Settlement #</th>
              <th className="pb-2">Notes</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[#1e2535]">
            {sales.map((sale) => (
              <CashSaleEditor key={sale.id} sale={sale} />
            ))}
          </tbody>
          <tfoot>
            <tr className="text-[#7b8aab] border-t border-[#2a3044] font-medium">
              <td className="pt-2 pr-3">Total</td>
              <td className="pt-2 pr-3">{totalBushels.toLocaleString()}</td>
              <td className="pt-2 pr-3"></td>
              <td className="pt-2 pr-3">
                ${sales.reduce((s, r) => s + r.gross_amount, 0).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
              </td>
              <td className="pt-2 pr-3">
                ${sales.reduce((s, r) => s + r.adjustments, 0).toFixed(2)}
              </td>
              <td className="pt-2 pr-3">
                ${sales.reduce((s, r) => s + (r.trucking_total ?? 0), 0).toFixed(2)}
              </td>
              <td className="pt-2 pr-3 text-[#a3e635]">
                ${totalNet.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
              </td>
              <td colSpan={4} />
            </tr>
          </tfoot>
        </table>
      </div>
    </section>
  );
}
