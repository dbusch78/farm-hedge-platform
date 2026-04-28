import {
  getFuturesPrices,
  getPositions,
  getNetPrice,
  getTradingMode,
  getAgentRuns,
} from "@/lib/api";
import type { FuturesPrice, Position } from "@/lib/types";

import HedgeCard from "@/components/cards/HedgeCard";
import WheatCard from "@/components/cards/WheatCard";
import AgentCard from "@/components/cards/AgentCard";
import WeatherCard from "@/components/cards/WeatherCard";
import DayTradingCard from "@/components/cards/DayTradingCard";
import CongressionalCard from "@/components/cards/CongressionalCard";

// Re-fetch on every request; data is real-time
export const dynamic = "force-dynamic";

async function safeFetch<T>(fn: () => Promise<T>): Promise<T | null> {
  try {
    return await fn();
  } catch {
    return null;
  }
}

export default async function Dashboard() {
  const [positions, futuresPrices, zcNetPrice, zsNetPrice, tradingMode, agentRuns] =
    await Promise.all([
      safeFetch(() => getPositions()),
      safeFetch(() => getFuturesPrices()),
      safeFetch(() => getNetPrice("ZC")),
      safeFetch(() => getNetPrice("ZS")),
      safeFetch(() => getTradingMode()),
      safeFetch(() => getAgentRuns("positioning_advisor", 1)),
    ]);

  const allPositions: Position[] = positions ?? [];
  const prices: FuturesPrice[] = futuresPrices ?? [];

  const zcPositions = allPositions.filter((p) => p.commodity === "ZC");
  const zsPositions = allPositions.filter((p) => p.commodity === "ZS");

  const findPrice = (symbol: string): FuturesPrice | null =>
    prices.find((p) => p.symbol === symbol) ?? null;

  const zcPrice = findPrice("ZC=F");
  const zsPrice = findPrice("ZS=F");
  const zwPrice = findPrice("ZW=F");

  const latestAgentRun = agentRuns?.[0] ?? null;

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between mb-2">
        <h1 className="text-lg font-semibold text-[#e8edf5]">Dashboard</h1>
        <p className="text-xs text-[#7b8aab]">
          {new Date().toLocaleDateString("en-US", {
            weekday: "short",
            month: "short",
            day: "numeric",
            year: "numeric",
          })}
        </p>
      </div>

      {positions === null && (
        <div className="bg-[#f59e0b10] border border-[#f59e0b40] rounded-lg px-4 py-3 text-xs text-[#f59e0b]">
          ⚠ Backend not reachable &mdash; start the FastAPI service to see live data.
        </div>
      )}

      {zcPositions.length > 0 ? (
        <HedgeCard
          commodity="ZC"
          positions={zcPositions}
          netPrice={zcNetPrice}
          initialFuturesPrice={zcPrice}
        />
      ) : (
        <EmptyHedgeCard commodity="ZC" price={zcPrice} />
      )}

      {zsPositions.length > 0 ? (
        <HedgeCard
          commodity="ZS"
          positions={zsPositions}
          netPrice={zsNetPrice}
          initialFuturesPrice={zsPrice}
        />
      ) : (
        <EmptyHedgeCard commodity="ZS" price={zsPrice} />
      )}

      <WheatCard initialPrice={zwPrice} />
      <AgentCard latestRun={latestAgentRun} />

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <DayTradingCard modeData={tradingMode} />
        <CongressionalCard />
      </div>

      <WeatherCard />
    </div>
  );
}

function EmptyHedgeCard({
  commodity,
  price,
}: {
  commodity: "ZC" | "ZS";
  price: FuturesPrice | null;
}) {
  const icons: Record<string, string> = { ZC: "🌽", ZS: "🌱" };
  const labels: Record<string, string> = { ZC: "CORN", ZS: "SOYBEAN" };
  const borderColors: Record<string, string> = {
    ZC: "border-l-[#a3e635]",
    ZS: "border-l-[#3b82f6]",
  };

  return (
    <div
      className={`bg-[#1a1f2e] rounded-lg border border-[#2a3044] border-l-4 ${borderColors[commodity]} p-5`}
    >
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-base font-semibold text-[#e8edf5] flex items-center gap-2">
            {icons[commodity]} {labels[commodity]} HEDGE
          </h2>
          <p className="text-sm text-[#4a5568] mt-1 italic">No active positions</p>
        </div>
        {price?.close !== null && price !== null && (
          <div className="text-right">
            <p className="text-[10px] text-[#7b8aab] uppercase tracking-wide mb-0.5">Futures</p>
            <p className={`text-lg font-bold tabular-nums ${price.stale ? "opacity-50 text-[#f59e0b]" : "text-[#e8edf5]"}`}>
              ${price.close?.toFixed(2) ?? "—"}
            </p>
          </div>
        )}
      </div>
      <p className="text-xs text-[#4a5568] mt-3">
        Add a position via{" "}
        <a href="/hedge" className="text-[#3b82f6] hover:underline">
          Hedge →
        </a>{" "}
        or run{" "}
        <code className="text-[#7b8aab] text-[10px]">
          python -m scripts.seed_positions
        </code>{" "}
        to seed existing positions.
      </p>
    </div>
  );
}
