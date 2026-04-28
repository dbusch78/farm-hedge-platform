import type {
  BasisBar,
  CashPrice,
  CloseRequest,
  ExpireRequest,
  FuturesPrice,
  GduStatus,
  NepBar,
  NetPriceResponse,
  OhlcBar,
  PlantingDate,
  Position,
  PositionCreate,
  PositionUpdate,
  RainTotals,
  ScenarioRequest,
  ScenarioRow,
  TradingModeResponse,
  AgentRun,
  WeatherLocal,
  WeatherRegional,
} from "./types";

// Server-side: fetch directly to the backend container via Docker service name.
// Client-side: use relative URL — next.config.ts rewrites /api/* to fastapi,
// so the browser never needs to resolve api.farm.local.
const BASE_URL =
  typeof window === "undefined"
    ? (process.env.INTERNAL_API_URL ?? "http://fastapi:8000")
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

export async function getPositions(
  status: "active" | "closed" | "all" = "active",
): Promise<Position[]> {
  return request<Position[]>(
    `/api/hedge/positions?status=${status}`,
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

export async function closePosition(
  id: string,
  body: CloseRequest,
): Promise<{ id: string }> {
  return request<{ id: string }>(`/api/hedge/positions/${id}/close`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function expirePosition(
  id: string,
  body: ExpireRequest,
): Promise<{ id: string }> {
  return request<{ id: string }>(`/api/hedge/positions/${id}/expire`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function deletePosition(id: string): Promise<void> {
  await request<void>(`/api/hedge/positions/${id}`, { method: "DELETE" });
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

// ── Analytics ─────────────────────────────────────────────────────────────────

export async function getAnalyticsFuturesHistory(
  symbol: string,
  days = 365,
): Promise<OhlcBar[]> {
  return request<OhlcBar[]>(
    `/api/analytics/futures-history?symbol=${encodeURIComponent(symbol)}&days=${days}`,
  );
}

export async function getAnalyticsBasisHistory(
  commodity: string,
  days = 180,
  elevator?: string,
): Promise<BasisBar[]> {
  const qs = new URLSearchParams({ commodity, days: String(days) });
  if (elevator) qs.set("elevator", elevator);
  return request<BasisBar[]>(`/api/analytics/basis-history?${qs}`);
}

export async function getAnalyticsNepHistory(days = 365): Promise<NepBar[]> {
  return request<NepBar[]>(`/api/analytics/nep-history?days=${days}`);
}

export async function getElevatorNames(): Promise<string[]> {
  return request<string[]>("/api/analytics/elevators");
}

// ── Weather ───────────────────────────────────────────────────────────────────

export async function getLocalWeather(): Promise<WeatherLocal> {
  return request<WeatherLocal>("/api/weather/local");
}

export async function getLocalWeatherHistory(days = 7): Promise<WeatherLocal[]> {
  return request<WeatherLocal[]>(`/api/weather/local/history?days=${days}`);
}

export async function getRegionalWeather(region: string): Promise<WeatherRegional> {
  return request<WeatherRegional>(`/api/weather/regional/${region}`);
}

export async function getRegionalHistory(days = 180): Promise<WeatherRegional[]> {
  return request<WeatherRegional[]>(`/api/weather/regional-history?days=${days}`);
}

export async function getGduStatus(): Promise<GduStatus> {
  return request<GduStatus>("/api/weather/gdu");
}

export async function getRainTotals(): Promise<RainTotals> {
  return request<RainTotals>("/api/weather/local/rain-totals");
}

// ── Planting dates ────────────────────────────────────────────────────────────

export async function getPlantingDates(): Promise<PlantingDate[]> {
  return request<PlantingDate[]>("/api/weather/planting-dates");
}

export async function setPlantingDate(
  commodity: string,
  year: number,
  planted_date: string,
  notes?: string,
): Promise<PlantingDate> {
  return request<PlantingDate>(`/api/weather/planting-dates/${commodity}/${year}`, {
    method: "PUT",
    body: JSON.stringify({ planted_date, notes }),
  });
}

export async function deletePlantingDate(commodity: string, year: number): Promise<void> {
  await request<void>(`/api/weather/planting-dates/${commodity}/${year}`, {
    method: "DELETE",
  });
}
