"use client";

import { useEffect, useRef, useState } from "react";
import type { WsPriceUpdate } from "@/lib/types";

const WS_URL =
  typeof window !== "undefined"
    ? (process.env.NEXT_PUBLIC_WS_URL ?? "ws://localhost:8000")
    : "";

const STALE_THRESHOLD_MS = 60_000;
const RECONNECT_BASE_MS = 2_000;
const RECONNECT_MAX_MS = 30_000;

export interface PriceState {
  close: number | null;
  time: string | null;
  stale: boolean;
  lastUpdated: number | null;
}

export type PricesMap = Record<string, PriceState>;

export function useFuturesPrices(
  initialPrices?: Record<string, { close: number | null; time: string; stale: boolean }>,
) {
  const [prices, setPrices] = useState<PricesMap>(() => {
    const map: PricesMap = {};
    if (initialPrices) {
      for (const [symbol, p] of Object.entries(initialPrices)) {
        map[symbol] = { ...p, lastUpdated: Date.now() };
      }
    }
    return map;
  });

  const [connected, setConnected] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectDelayRef = useRef(RECONNECT_BASE_MS);
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const staleTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const mountedRef = useRef(true);

  useEffect(() => {
    mountedRef.current = true;

    function connect() {
      if (!WS_URL || !mountedRef.current) return;

      const ws = new WebSocket(`${WS_URL}/ws/prices`);
      wsRef.current = ws;

      ws.onopen = () => {
        if (!mountedRef.current) return;
        setConnected(true);
        reconnectDelayRef.current = RECONNECT_BASE_MS;
      };

      ws.onmessage = (event: MessageEvent) => {
        if (!mountedRef.current) return;
        try {
          const update = JSON.parse(event.data as string) as WsPriceUpdate;
          setPrices((prev) => ({
            ...prev,
            [update.symbol]: {
              close: update.close,
              time: update.time,
              stale: update.stale,
              lastUpdated: Date.now(),
            },
          }));
        } catch {
          // malformed message -- ignore
        }
      };

      ws.onclose = () => {
        if (!mountedRef.current) return;
        setConnected(false);
        wsRef.current = null;
        const delay = reconnectDelayRef.current;
        reconnectDelayRef.current = Math.min(delay * 2, RECONNECT_MAX_MS);
        reconnectTimerRef.current = setTimeout(connect, delay);
      };

      ws.onerror = () => {
        ws.close();
      };
    }

    connect();

    // Periodically mark prices as stale if no update received
    staleTimerRef.current = setInterval(() => {
      const now = Date.now();
      setPrices((prev) => {
        const next = { ...prev };
        let changed = false;
        for (const symbol of Object.keys(next)) {
          const p = next[symbol];
          if (p.lastUpdated !== null && !p.stale && now - p.lastUpdated > STALE_THRESHOLD_MS) {
            next[symbol] = { ...p, stale: true };
            changed = true;
          }
        }
        return changed ? next : prev;
      });
    }, 10_000);

    return () => {
      mountedRef.current = false;
      if (reconnectTimerRef.current) clearTimeout(reconnectTimerRef.current);
      if (staleTimerRef.current) clearInterval(staleTimerRef.current);
      wsRef.current?.close();
    };
  }, []);

  return { prices, connected };
}
