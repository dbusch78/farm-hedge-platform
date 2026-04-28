/**
 * Black-76 live delta for display and coverage calculations.
 * Hardcoded IV: ZC=22%, ZS=18%. Falls back to delta_at_entry if any input is missing.
 * Do NOT use this for P&L pricing — the hedge calculator owns that logic.
 */

const HARDCODED_IV: Record<string, number> = { ZC: 0.22, ZS: 0.18 };

const MONTH_CODE_TO_NUM: Record<string, number> = {
  F: 1, G: 2, H: 3, J: 4, K: 5, M: 6,
  N: 7, Q: 8, U: 9, V: 10, X: 11, Z: 12,
};

// Abramowitz & Stegun 26.2.17 — max error 7.5e-8
function normalCDF(x: number): number {
  if (x > 8) return 1;
  if (x < -8) return 0;
  const a1 = 0.319381530, a2 = -0.356563782, a3 = 1.781477937;
  const a4 = -1.821255978, a5 = 1.330274429, p = 0.2316419;
  const ax = Math.abs(x);
  const t = 1 / (1 + p * ax);
  const phi = Math.exp(-ax * ax / 2) / Math.sqrt(2 * Math.PI);
  const cdf = 1 - phi * t * (a1 + t * (a2 + t * (a3 + t * (a4 + t * a5))));
  return x >= 0 ? cdf : 1 - cdf;
}

/**
 * Approximate CME grain option expiry: last Friday of the month before the
 * contract delivery month (e.g. ZCN26 → last Friday of June 2026).
 */
export function cmeSymbolToExpiry(symbol: string): Date | null {
  if (symbol.length < 4) return null;
  const monthCode = symbol[symbol.length - 3];
  const year = 2000 + parseInt(symbol.slice(-2), 10);
  const contractMonth = MONTH_CODE_TO_NUM[monthCode]; // 1-indexed
  if (!contractMonth || isNaN(year)) return null;

  // Previous calendar month (1-indexed)
  const prevMonth = contractMonth === 1 ? 12 : contractMonth - 1;
  const prevYear = contractMonth === 1 ? year - 1 : year;

  // new Date(y, m, 0) with 1-indexed m gives the last day of month m in year y
  const lastDay = new Date(prevYear, prevMonth, 0);
  const dow = lastDay.getDay(); // 0=Sun … 5=Fri … 6=Sat
  lastDay.setDate(lastDay.getDate() - ((dow - 5 + 7) % 7)); // rewind to last Friday
  return lastDay;
}

/**
 * Black-76 delta (absolute value, matching delta_at_entry sign convention).
 * Returns NaN on bad inputs; callers should fall back to delta_at_entry.
 */
function black76DeltaMagnitude(
  F: number,
  K: number,
  T: number,
  sigma: number,
  isCall: boolean,
): number {
  if (T <= 0 || sigma <= 0 || F <= 0 || K <= 0) return NaN;
  const d1 = (Math.log(F / K) + 0.5 * sigma * sigma * T) / (sigma * Math.sqrt(T));
  const nd1 = normalCDF(d1);
  return isCall ? nd1 : 1 - nd1; // |Δ| — puts have negative conventional delta
}

export interface LiveDeltaParams {
  futuresPrice: number;
  strike: number;
  commodity: string;       // "ZC" | "ZS"
  contractMonth: string;   // CME symbol e.g. "ZCN26"
  positionType: "put" | "call";
  deltaAtEntry: number;    // fallback
}

/**
 * Returns live Black-76 |delta| for display/coverage.
 * Falls back to deltaAtEntry if futures price is missing, option is expired,
 * or the IV lookup fails.
 */
export function calcLiveDelta(params: LiveDeltaParams): number {
  const { futuresPrice, strike, commodity, contractMonth, positionType, deltaAtEntry } = params;
  const sigma = HARDCODED_IV[commodity];
  const expiry = cmeSymbolToExpiry(contractMonth);

  if (!sigma || !expiry || futuresPrice <= 0 || strike <= 0) return deltaAtEntry;

  const T = (expiry.getTime() - Date.now()) / (365.25 * 24 * 60 * 60 * 1000);
  const d = black76DeltaMagnitude(futuresPrice, strike, T, sigma, positionType === "call");
  return isNaN(d) ? deltaAtEntry : d;
}

export interface HedgeCoverage {
  rawContracts: number;      // expectedBushels / 5000
  fullHedgeTarget: number;   // rawContracts / effectiveDelta
  coveragePct: number;       // (numContracts / fullHedgeTarget) * 100
}

export function calcHedgeCoverage(
  numContracts: number,
  expectedBushels: number,
  effectiveDelta: number,
): HedgeCoverage {
  const rawContracts = expectedBushels / 5000;
  const fullHedgeTarget = rawContracts / effectiveDelta;
  const coveragePct = (numContracts / fullHedgeTarget) * 100;
  return { rawContracts, fullHedgeTarget, coveragePct };
}
