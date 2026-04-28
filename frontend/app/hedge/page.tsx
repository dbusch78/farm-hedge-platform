import {
  getFuturesPrices,
  getFuturesHistory,
  getCashPrices,
  getPositions,
  getNetPrices,
} from "@/lib/api";
import { cmeSymbolToLabel } from "@/lib/cme";
import { calcLiveDelta, calcHedgeCoverage } from "@/lib/blackScholes";
import type { FuturesPrice, NetPriceResponse, Position, OhlcBar, CashPrice } from "@/lib/types";
import PriceChart from "@/components/charts/PriceChart";
import ScenarioModeler from "@/components/trading/ScenarioModeler";
import PositionEntry from "@/components/trading/PositionEntry";

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

export default async function HedgePage() {
  const [positions, futuresPrices, netPrices, zcHistory, zsHistory, cashPrices] =
    await Promise.all([
      safeFetch(() => getPositions()),
      safeFetch(() => getFuturesPrices()),
      safeFetch(() => getNetPrices()),
      safeFetch(() => getFuturesHistory("ZC=F", 120)),
      safeFetch(() => getFuturesHistory("ZS=F", 120)),
      safeFetch(() => getCashPrices()),
    ]);

  const allPositions: Position[] = positions ?? [];
  const prices: FuturesPrice[] = futuresPrices ?? [];
  const netPriceList: NetPriceResponse[] = netPrices ?? [];

  const zcPositions = allPositions.filter((p) => p.commodity === "ZC");
  const zsPositions = allPositions.filter((p) => p.commodity === "ZS");

  const findPrice = (sym: string) => prices.find((p) => p.symbol === sym) ?? null;
  const findNetPrice = (c: string) => netPriceList.find((r) => r.commodity === c) ?? null;

  const zcPrice = findPrice("ZC=F");
  const zsPrice = findPrice("ZS=F");
  const zcNet = findNetPrice("ZC");
  const zsNet = findNetPrice("ZS");

  const zcCash = (cashPrices ?? []).filter((c) => c.commodity === "ZC");
  const zsCash = (cashPrices ?? []).filter((c) => c.commodity === "ZS");

  return (
    <div className="space-y-8">
      <div className="flex items-center justify-between">
        <h1 className="text-lg font-semibold text-[#e8edf5]">Hedge Positions</h1>
        <a href="/" className="text-xs text-[#3b82f6] hover:underline">
          ← Dashboard
        </a>
      </div>

      {allPositions.length === 0 && (
        <div className="bg-[#f59e0b10] border border-[#f59e0b40] rounded-lg px-4 py-3 text-xs text-[#f59e0b]">
          No active positions. Add one below, or run{" "}
          <code className="text-[#7b8aab]">python -m scripts.seed_positions</code>.
        </div>
      )}

      {/* ── Corn section ─────────────────────────────────────────────────── */}
      <CommoditySection
        commodity="ZC"
        label={`Corn${zcPositions[0]?.contract_month ? ` — ${cmeSymbolToLabel(zcPositions[0].contract_month)}` : ""}`}
        icon="🌽"
        positions={zcPositions}
        netPrice={zcNet}
        currentPrice={zcPrice}
        history={zcHistory ?? []}
        cashHistory={zcCash}
        borderColor="border-l-[#a3e635]"
      />

      {/* ── Soybeans section ─────────────────────────────────────────────── */}
      <CommoditySection
        commodity="ZS"
        label={`Soybeans${zsPositions[0]?.contract_month ? ` — ${cmeSymbolToLabel(zsPositions[0].contract_month)}` : ""}`}
        icon="🌱"
        positions={zsPositions}
        netPrice={zsNet}
        currentPrice={zsPrice}
        history={zsHistory ?? []}
        cashHistory={zsCash}
        borderColor="border-l-[#3b82f6]"
      />

      {/* ── Add position ──────────────────────────────────────────────────── */}
      <section className="bg-[#1a1f2e] rounded-lg border border-[#2a3044] p-5">
        <PositionEntry />
      </section>
    </div>
  );
}

function CommoditySection({
  commodity,
  label,
  icon,
  positions,
  netPrice,
  currentPrice,
  history,
  cashHistory,
  borderColor,
}: {
  commodity: string;
  label: string;
  icon: string;
  positions: Position[];
  netPrice: NetPriceResponse | null;
  currentPrice: FuturesPrice | null;
  history: OhlcBar[];
  cashHistory: CashPrice[];
  borderColor: string;
}) {
  const futuresClose = currentPrice?.close ?? null;
  const primaryPosition = positions[0] ?? null;

  return (
    <section className={`bg-[#1a1f2e] rounded-lg border border-[#2a3044] border-l-4 ${borderColor} p-5 space-y-5`}>
      {/* Header */}
      <div className="flex items-start justify-between">
        <h2 className="text-base font-semibold text-[#e8edf5]">
          {icon} {label}
        </h2>
        {futuresClose !== null && (
          <div className="text-right">
            <p className="text-[10px] text-[#7b8aab] uppercase tracking-wide mb-0.5">
              Futures {currentPrice?.stale ? "(stale)" : ""}
            </p>
            <p className={`text-xl font-bold tabular-nums ${currentPrice?.stale ? "text-[#f59e0b] opacity-60" : "text-[#e8edf5]"}`}>
              ${fmt(futuresClose)}
            </p>
          </div>
        )}
      </div>

      {/* Price chart */}
      <PriceChart
        symbol={commodity === "ZC" ? "ZC=F" : "ZS=F"}
        history={history}
        cashHistory={cashHistory}
        strikePrice={primaryPosition?.strike}
        netEffectivePrice={netPrice?.net_effective_price}
        height={300}
      />

      {/* Positions list */}
      {positions.length > 0 ? (
        <div className="space-y-2">
          <h3 className="text-xs font-semibold text-[#7b8aab] uppercase tracking-wide">
            Active Positions ({positions.length})
          </h3>
          {positions.map((pos) => (
            <PositionRow key={pos.id} pos={pos} netPrice={netPrice} futuresClose={futuresClose} />
          ))}
        </div>
      ) : (
        <p className="text-sm text-[#4a5568] italic">No {commodity} positions yet.</p>
      )}

      {/* Scenario modeler */}
      {primaryPosition && (
        <div className="pt-4 border-t border-[#1e2535]">
          <ScenarioModeler
            strike={primaryPosition.strike}
            totalPremiumPerBu={primaryPosition.premium_paid_per_bu}
            expectedBushels={primaryPosition.expected_bushels}
            deltaAtEntry={primaryPosition.delta_at_entry}
            phase={primaryPosition.phase as 1 | 2}
            cashSalePrice={primaryPosition.cash_sale_price}
            currentFuturesPrice={futuresClose}
          />
        </div>
      )}
    </section>
  );
}

function PositionRow({
  pos,
  netPrice,
  futuresClose,
}: {
  pos: Position;
  netPrice: NetPriceResponse | null;
  futuresClose: number | null;
}) {
  const isPhase1 = pos.phase === 1;
  const phaseBg = isPhase1 ? "bg-[#a3e63515] text-[#a3e635]" : "bg-[#3b82f615] text-[#3b82f6]";

  // Live delta via Black-76 (hardcoded IV); falls back to delta_at_entry
  const liveDelta = futuresClose !== null
    ? calcLiveDelta({
        futuresPrice: futuresClose,
        strike: pos.strike,
        commodity: pos.commodity,
        contractMonth: pos.contract_month,
        positionType: pos.position_type,
        deltaAtEntry: pos.delta_at_entry,
      })
    : pos.delta_at_entry;
  const { fullHedgeTarget, coveragePct } = calcHedgeCoverage(
    pos.num_contracts,
    pos.expected_bushels,
    liveDelta,
  );
  const coverageTooltip = isPhase1
    ? `Holding ${pos.num_contracts} of ${fmt(fullHedgeTarget, 1)} contracts for full delta-neutral coverage of ${pos.expected_bushels.toLocaleString()} bu at live Δ=${liveDelta.toFixed(2)}. Partial coverage is intentional — this is floor protection, not a 1:1 hedge.`
    : `Phase 2 calls provide upside participation, not full coverage. ${pos.num_contracts} contracts at live Δ=${liveDelta.toFixed(2)} captures premium on a proportional share of production. Partial is the strategy.`;

  // Options P&L: intrinsic value minus premium paid, per bushel
  const pnl = netPrice ? netPrice.options_pnl_per_bu : null;

  return (
    <div className="bg-[#141920] rounded border border-[#2a3044] p-3 text-sm space-y-2">
      <div className="flex items-center justify-between gap-2 flex-wrap">
        <div className="flex items-center gap-2">
          <span className={`text-xs font-semibold px-2 py-0.5 rounded ${phaseBg}`}>
            PHASE {pos.phase}
          </span>
          <span className="text-[#e8edf5] font-semibold">
            {pos.contract_month} {pos.position_type.toUpperCase()} @${fmt(pos.strike)}
          </span>
        </div>
        <span className="text-xs text-[#7b8aab]">
          {pos.num_contracts} contracts &bull; {pos.expected_bushels.toLocaleString()} bu
        </span>
      </div>

      <div className="grid grid-cols-3 gap-2 text-xs">
        <Stat label="Premium paid" value={`$${fmt(pos.premium_paid_per_bu)}/bu`} muted />
        <Stat label="Δ live / entry" value={`${liveDelta.toFixed(2)} / ${pos.delta_at_entry.toFixed(2)}`} />
        <Stat label="Held / Target" value={`${pos.num_contracts} / ${fmt(fullHedgeTarget, 1)}`} />
        <Stat label="Coverage" value={`${fmt(coveragePct, 0)}%`} tooltip={coverageTooltip} />
        {netPrice && (
          <Stat
            label="Net eff. price"
            value={`$${fmt(netPrice.net_effective_price)}/bu`}
            highlight
          />
        )}
        {pnl !== null && (
          <Stat
            label="Options P&L"
            value={`${pnl >= 0 ? "+" : ""}$${fmt(pnl)}/bu`}
            positive={pnl >= 0}
          />
        )}
        {netPrice && futuresClose !== null && (
          <Stat
            label="Net Eff. vs Spot"
            value={`${netPrice.net_effective_vs_spot_per_bu >= 0 ? "+" : ""}$${fmt(netPrice.net_effective_vs_spot_per_bu)}/bu`}
            positive={netPrice.net_effective_vs_spot_per_bu >= 0}
            tooltip="How your locked-in net price compares to current market. Negative means the market rallied after your sale — expected for Phase 2 calls."
          />
        )}
        {pos.phase === 2 && pos.cash_sale_price != null && (
          <Stat label="Cash locked" value={`$${fmt(pos.cash_sale_price)}/bu`} />
        )}
      </div>

      {pos.notes && (
        <p className="text-xs text-[#7b8aab] italic">{pos.notes}</p>
      )}
    </div>
  );
}

function Stat({
  label,
  value,
  highlight = false,
  positive,
  muted = false,
  tooltip,
}: {
  label: string;
  value: string;
  highlight?: boolean;
  positive?: boolean;
  muted?: boolean;
  tooltip?: string;
}) {
  return (
    <div title={tooltip}>
      <p className={`text-[10px] uppercase tracking-widest text-[#7b8aab] mb-0.5 ${tooltip ? "cursor-help" : ""}`}>{label}</p>
      <p
        className={`tabular-nums font-medium ${
          highlight
            ? "text-[#e8edf5]"
            : positive === true
              ? "text-[#22c55e]"
              : positive === false
                ? "text-[#ef4444]"
                : muted
                  ? "text-[#f59e0b]"
                  : "text-[#c4cfe8]"
        }`}
      >
        {value}
      </p>
    </div>
  );
}
