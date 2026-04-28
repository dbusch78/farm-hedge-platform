const MONTH_CODE_TO_NAME: Record<string, string> = {
  F: "Jan", G: "Feb", H: "Mar", J: "Apr", K: "May", M: "Jun",
  N: "Jul", Q: "Aug", U: "Sep", V: "Oct", X: "Nov", Z: "Dec",
};

/**
 * Convert a CME contract symbol to a short human label.
 * ZCN26 → "Jul '26"   ZSZ25 → "Dec '25"
 * Returns the raw symbol if it doesn't match the expected format.
 */
export function cmeSymbolToLabel(symbol: string): string {
  if (!symbol || symbol.length < 4) return symbol;
  const monthCode = symbol[symbol.length - 3];
  const year = symbol.slice(-2);
  const month = MONTH_CODE_TO_NAME[monthCode];
  if (!month) return symbol;
  return `${month} '${year}`;
}
