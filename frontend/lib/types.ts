// TypeScript types matching FastAPI Pydantic models

export type Commodity = "ZC" | "ZS";
export type PositionType = "put" | "call";
export type Phase = 1 | 2;
export type TradingMode = "paper" | "live";

// ── Hedge positions ───────────────────────────────────────────────────────────

export interface Position {
  id: string;
  commodity: Commodity;
  contract_month: string;
  position_type: PositionType;
  strike: number;
  premium_paid_per_bu: number;
  num_contracts: number;
  delta_at_entry: number;
  expected_bushels: number;
  phase: Phase;
  date_opened: string;
  cash_sale_price: number | null;
  closed: boolean;
  date_closed: string | null;
  notes: string;
}

export interface PositionCreate {
  commodity: Commodity;
  contract_month: string;
  position_type: PositionType;
  strike: number;
  premium_paid_per_bu: number;
  num_contracts: number;
  delta_at_entry: number;
  expected_bushels: number;
  phase: Phase;
  date_opened: string;
  cash_sale_price?: number | null;
  notes?: string;
}

export interface PositionUpdate {
  strike?: number;
  premium_paid_per_bu?: number;
  num_contracts?: number;
  delta_at_entry?: number;
  phase?: Phase;
  cash_sale_price?: number | null;
  notes?: string;
  closed?: boolean;
  date_closed?: string | null;
}

// ── Net effective price ───────────────────────────────────────────────────────

export interface NetPriceResponse {
  commodity: string;
  phase: number;
  underlying_price: number;
  net_effective_price: number;
  put_intrinsic: number;
  call_intrinsic: number;
  total_premiums_paid: number;
  raw_contracts: number;
  delta_adj_contracts: number;
}

// ── Scenario model ────────────────────────────────────────────────────────────

export interface ScenarioRequest {
  hypothetical_prices: number[];
  current_cash_offset?: number;
  strike: number;
  total_premiums_paid_per_bu: number;
  expected_bushels: number;
  delta_at_entry: number;
  phase?: Phase;
  cash_sale_price?: number | null;
  call_premium_paid_per_bu?: number | null;
}

export interface ScenarioRow {
  futures_price: number;
  put_intrinsic: number;
  call_intrinsic: number;
  premiums_paid: number;
  net_effective_price: number;
}

// ── Futures prices ────────────────────────────────────────────────────────────

export type FuturesSymbol = "ZC=F" | "ZS=F" | "ZW=F";

export interface FuturesPrice {
  symbol: string;
  time: string;
  close: number | null;
  stale: boolean;
}

export interface FuturesPricesMap {
  "ZC=F": FuturesPrice | null;
  "ZS=F": FuturesPrice | null;
  "ZW=F": FuturesPrice | null;
}

// ── Cash prices ───────────────────────────────────────────────────────────────

export interface CashPrice {
  elevator: string;
  commodity: string;
  time: string;
  cash_price: number;
  futures_ref: number | null;
  basis: number | null;
  contract_month: string | null;
}

// ── WebSocket price broadcast ─────────────────────────────────────────────────

export interface WsPriceUpdate {
  symbol: string;
  close: number;
  time: string;
  stale: boolean;
}

// ── Trading mode ──────────────────────────────────────────────────────────────

export interface TradingModeResponse {
  mode: TradingMode;
}

// ── Agent runs ────────────────────────────────────────────────────────────────

export interface AgentRun {
  id: string;
  agent: string;
  run_timestamp: string;
  prompt_version: string;
  model: string;
  input_snapshot: Record<string, unknown>;
  output: AgentOutput;
  token_usage: { input: number; output: number };
  cost_usd: number;
  actual_outcome: string | null;
  outcome_notes: string | null;
  operator_rating: number | null;
}

export interface AgentOutput {
  summary: string;
  divergence_flag?: boolean;
  divergence_magnitude?: string;
  positioning_note?: string;
  confidence?: number;
  net_sentiment?: Record<string, number>;
  [key: string]: unknown;
}

// ── OHLC history ─────────────────────────────────────────────────────────────

export interface OhlcBar {
  time: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number | null;
  stale: boolean;
}

// ── Analytics ─────────────────────────────────────────────────────────────────

export interface BasisBar {
  time: string;
  elevator: string;
  commodity: string;
  cash_price: number;
  futures_ref: number | null;
  basis: number | null;
}

export interface NepBar {
  time: string;
  position_id: string;
  underlying_px: number;
  net_eff_price: number | null;
  pnl_per_bushel: number | null;
  premium_paid: number | null;
}

// ── API error ─────────────────────────────────────────────────────────────────

export interface ApiError {
  detail: string;
  status: number;
}
