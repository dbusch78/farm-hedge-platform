import type {
  CashPrice,
  FuturesPrice,
  NetPriceResponse,
  OhlcBar,
  Position,
  PositionCreate,
  PositionUpdate,
  ScenarioRequest,
  ScenarioRow,
  TradingModeResponse,
  AgentRun,
} from "./types";

// Server-side: fetch directly to the backend container.
// Client-side: use relative URL — next.config.ts rewrites /api/* to fastapi,
// so the browser never needs to resolve api.farm.local.
const BASE_URL =
  typeof window === "undefined"
    ? (process.env.NEXT_PUBLIC_API_URL ?? "http://fastapi:8000")
    : "";

async function request<T>(
  path: string,
  options?: RequestInit,
  tags?: string[],
): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...options?.headers,
    },
    next: tags ? { tags } : undefined,
  });

  if (!res.ok) {
    const detail = await res.text().catch(() => res.statusText);
    throw new Error(`API ${res.status}: ${detail}`);
  }
  return res.json() as Promise<T>;
}

// ── Futures prices ────────────────────────────────────────────────────────────

export async function getFuturesPrices(): Promise<FuturesPrice[]> {
  return request<FuturesPrice[]>("/api/hedge/prices/futures");
}

export async function getCashPrices(): Promise<CashPrice[]> {
  return request<CashPrice[]>("/api/hedge/prices/cash");
}

export async function getFuturesHistory(
  symbol: string,
  days = 90,
): Promise<OhlcBar[]> {
  return request<OhlcBar[]>(
    `/api/hedge/prices/history/${encodeURIComponent(symbol)}?days=${days}`,
  );
}

// ── Hedge positions ───────────────────────────────────────────────────────────

export async function getPositions(activeOnly = true): Promise<Position[]> {
  return request<Position[]>(
    `/api/hedge/positions?active_only=${activeOnly}`,
    undefined,
    ["positions"],
  );
}

export async function getPosition(id: string): Promise<Position> {
  return request<Position>(`/api/hedge/positions/${id}`);
}

export async function createPosition(body: PositionCreate): Promise<{ id: string }> {
  return request<{ id: string }>("/api/hedge/positions", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function updatePosition(
  id: string,
  body: PositionUpdate,
): Promise<{ id: string }> {
  return request<{ id: string }>(`/api/hedge/positions/${id}`, {
    method: "PUT",
    body: JSON.stringify(body),
  });
}

// Returns all net prices; filter by commodity client-side.
export async function getNetPrices(): Promise<NetPriceResponse[]> {
  return request<NetPriceResponse[]>("/api/hedge/net-price");
}

export async function getNetPrice(
  commodity: string,
): Promise<NetPriceResponse | null> {
  const all = await getNetPrices();
  return all.find((r) => r.commodity === commodity) ?? null;
}

export async function runScenario(
  body: ScenarioRequest,
): Promise<ScenarioRow[]> {
  return request<ScenarioRow[]>("/api/hedge/scenario", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

// ── Trading mode ──────────────────────────────────────────────────────────────

export async function getTradingMode(): Promise<TradingModeResponse> {
  return request<TradingModeResponse>("/api/trading/mode", undefined, [
    "trading-mode",
  ]);
}

export async function setTradingMode(
  mode: "paper" | "live",
  confirmedPhrase: string,
): Promise<TradingModeResponse> {
  return request<TradingModeResponse>("/api/trading/mode", {
    method: "POST",
    body: JSON.stringify({ mode, confirmed_phrase: confirmedPhrase }),
  });
}

// ── Agent runs ────────────────────────────────────────────────────────────────

export async function getAgentRuns(
  agent?: string,
  limit = 10,
): Promise<AgentRun[]> {
  const qs = new URLSearchParams({ limit: String(limit) });
  if (agent) qs.set("agent", agent);
  return request<AgentRun[]>(`/api/agents/runs?${qs}`);
}

export async function triggerAgentRun(agent: string): Promise<AgentRun> {
  return request<AgentRun>(`/api/agents/${agent}/run`, { method: "POST" });
}
