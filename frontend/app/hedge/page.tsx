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
import PositionActions from "@/components/trading/PositionActions";

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
  const [positions, closedPositionsData, futuresPrices, netPrices, zcHistory, zsHistory, cashPrices] =
    await Promise.all([
      safeFetch(() => getPositions("active")),
      safeFetch(() => getPositions("closed")),
      safeFetch(() => getFuturesPrices()),
      safeFetch(() => getNetPrices()),
      safeFetch(() => getFuturesHistory("ZC=F", 120)),
      safeFetch(() => getFuturesHistory("ZS=F", 120)),
      safeFetch(() => getCashPrices()),
    ]);

  const allPositions: Position[] = positions ?? [];
  const closedPositions: Position[] = closedPositionsData ?? [];
  const prices: FuturesPrice[] = futuresPrices ?? [];
  const netPriceList: NetPriceResponse[] = netPrices ?? [];

  const zcPositions = allPositions.filter((p) => p.commodity === "ZC");
  const zsPositions = allPositions.filter((p) => p.commodity === "ZS");
  const zcClosed = closedPositions.filter((p) => p.commodity === "ZC");
  const zsClosed = closedPositions.filter((p) => p.commodity === "ZS");

  const findPrice = (sym: string) => prices.find((p) => p.symbol === sym) ?? null;
  const findNetPrice = (c: string) => netPriceList.find((r) => r.commodity === c) ?? null;

  const zcPrice = findPrice("ZC=F");
  const zsPrice = findPrice("ZS=F");
  const zcNet = findNetPrice("ZC");
  const zsNet = findNetPrice("ZS");

  const zcCash = (cashPrices ?? []).filter((c) => c.commodity === "ZC");
  const zsCash = (cashPrices ?? []).filter((c) => c.commodity === "ZS");

  const contractLabel = (positions: Position[]) =>
    positions[0]?.contract_month ? ` — ${cmeSymbolToLabel(positions[0].contract_month)}` : "";

  return (
    <div className="space-y-8">
      <div className="flex items-center justify-between">
        <h1 className="text-lg font-semibold text-[#e8edf5]">Hedge Positions</h1>
        <a href="/" className="text-xs text-[#3b82f6] hover:underline">
          ← Dashboard
        </a>
      </div>

      {allPositions.length === 0 && closedPositions.length === 0 && (
        <div className="bg-[#f59e0b10] border border-[#f59e0b40] rounded-lg px-4 py-3 text-xs text-[#f59e0b]">
          No active positions. Add one below, or run{" "}
          <code className="text-[#7b8aab]">python -m scripts.seed_positions</code>.
        </div>
      )}

      {/* ── Corn section ─────────────────────────────────────────────────── */}
      <CommoditySection
        commodity="ZC"
        label={`Corn${contractLabel(zcPositions.length ? zcPositions : zcClosed)}`}
        icon="🌽"
        positions={zcPositions}
        closedPositions={zcClosed}
        netPrice={zcNet}
        currentPrice={zcPrice}
        history={zcHistory ?? []}
        cashHistory={zcCash}
        borderColor="border-l-[#a3e635]"
      />

      {/* ── Soybeans section ─────────────────────────────────────────────── */}
      <CommoditySection
        commodity="ZS"
        label={`Soybeans${contractLabel(zsPositions.length ? zsPositions : zsClosed)}`}
        icon="🌱"
        positions={zsPositions}
        closedPositions={zsClosed}
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

function SeasonSummary({
  activePositions,
  closedPositions,
  netPrice,
}: {
  activePositions: Position[];
  closedPositions: Position[];
  netPrice: NetPriceResponse | null;
}) {
  if (closedPositions.length === 0) return null;

  const activeBushels = activePositions.reduce((s, p) => s + p.expected_bushels, 0);
  const closedBushels = closedPositions.reduce((s, p) => s + p.expected_bushels, 0);

  const realizedTotal = closedPositions.reduce(
    (sum, p) => sum + (p.realized_pnl_per_bu ?? 0) * p.expected_bushels,
    0,
  );

  const activeMtmTotal =
    netPrice && activeBushels > 0
      ? netPrice.options_pnl_per_bu * activeBushels
      : null;

  const combinedTotal =
    activeMtmTotal !== null ? activeMtmTotal + realizedTotal : null;

  function fmtDollars(n: number) {
    const sign = n >= 0 ? "+" : "";
    return `${sign}$${Math.abs(n).toLocaleString(undefined, { maximumFractionDigits: 0 })}`;
  }

  return (
    <div className="flex flex-wrap gap-4 text-xs text-[#7b8aab] pt-1">
      <span className="uppercase tracking-wide">Season:</span>
      {activeMtmTotal !== null && (
        <span>
          Active MTM{" "}
          <span className={activeMtmTotal >= 0 ? "text-[#22c55e]" : "text-[#ef4444]"}>
            {fmtDollars(activeMtmTotal)}
          </span>
        </span>
      )}
      <span>
        Realized{" "}
        <span className={realizedTotal >= 0 ? "text-[#22c55e]" : "text-[#ef4444]"}>
          {fmtDollars(realizedTotal)}
        </span>
        <span className="text-[#4a5568]"> ({closedBushels.toLocaleString()} bu)</span>
      </span>
      {combinedTotal !== null && (
        <span>
          Combined{" "}
          <span className={`font-semibold ${combinedTotal >= 0 ? "text-[#22c55e]" : "text-[#ef4444]"}`}>
            {fmtDollars(combinedTotal)}
          </span>
        </span>
      )}
    </div>
  );
}

function CommoditySection({
  commodity,
  label,
  icon,
  positions,
  closedPositions,
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
  closedPositions: Position[];
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
        <div className="space-y-1">
          <h2 className="text-base font-semibold text-[#e8edf5]">
            {icon} {label}
          </h2>
          <SeasonSummary
            activePositions={positions}
            closedPositions={closedPositions}
            netPrice={netPrice}
          />
        </div>
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

      {/* Active positions list */}
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
        <p className="text-sm text-[#4a5568] italic">No active {commodity} positions.</p>
      )}

      {/* Closed / expired positions */}
      {closedPositions.length > 0 && (
        <div className="space-y-2">
          <h3 className="text-xs font-semibold text-[#7b8aab] uppercase tracking-wide">
            Closed Positions ({closedPositions.length})
          </h3>
          {closedPositions.map((pos) => (
            <ClosedPositionRow key={pos.id} pos={pos} />
          ))}
        </div>
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
          <Stat label="Net eff. price" value={`$${fmt(netPrice.net_effective_price)}/bu`} highlight />
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

      <PositionActions pos={pos} />
    </div>
  );
}

function ClosedPositionRow({ pos }: { pos: Position }) {
  const isClosed = pos.status === "CLOSED";
  const statusColor = isClosed ? "text-[#7b8aab]" : "text-[#4a5568]";
  const statusLabel = pos.status === "EXPIRED"
    ? (pos.exit_reason === "expired_with_value" ? "EXPIRED (w/ value)" : "EXPIRED WORTHLESS")
    : "CLOSED";

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
          {pos.exit_price_per_bu != null && (
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
