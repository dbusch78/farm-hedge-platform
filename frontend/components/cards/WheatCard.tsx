"use client";

import { useFuturesPrices } from "@/hooks/useFuturesPrices";
import type { FuturesPrice } from "@/lib/types";

interface Props {
  initialPrice: FuturesPrice | null;
}

export default function WheatCard({ initialPrice }: Props) {
  const { prices } = useFuturesPrices(
    initialPrice
      ? {
          "ZW=F": {
            close: initialPrice.close,
            time: initialPrice.time,
            stale: initialPrice.stale,
          },
        }
      : undefined,
  );

  const livePrice = prices["ZW=F"];
  const close = livePrice?.close ?? initialPrice?.close ?? null;
  const isStale = livePrice?.stale ?? initialPrice?.stale ?? false;

  return (
    <div className="bg-[#1a1f2e] rounded-lg border border-[#2a3044] border-l-4 border-l-[#7b8aab] p-5">
      <div className="flex items-start justify-between">
        <div>
          <h2 className="text-base font-semibold text-[#e8edf5] flex items-center gap-2">
            🌾 WHEAT &mdash; ZW
          </h2>
          <p className="text-xs text-[#7b8aab] mt-0.5">
            Leading indicator &bull; No hedge position
          </p>
        </div>
        {close !== null && (
          <div className="text-right">
            <p className={`text-lg font-bold tabular-nums text-[#e8edf5] ${isStale ? "opacity-50" : ""}`}>
              ${close.toFixed(2)}
              {isStale && (
                <span className="ml-1 text-[#f59e0b] text-xs">(stale)</span>
              )}
            </p>
          </div>
        )}
      </div>
      <p className="text-xs text-[#7b8aab] mt-3">
        ZW often prices correlated weather and fund flows before corn and beans.
        Monitor as a directional signal for the grain complex.
      </p>
    </div>
  );
}
