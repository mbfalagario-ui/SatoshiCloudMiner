// Bitcoin amount helpers shared by Wallet, Dashboard, and Admin screens.
// All amounts are tracked internally in BTC (float, 8-decimal precision); we
// expose helpers to convert to/from sats and format for the UI.

export const SATS_PER_BTC = 100_000_000;

// Updated June-2025: 150 000 sat minimum (0.00150 BTC), no maximum
// (UI shows "—"), flat 10% fee covers Lightning routing + processing.
export const WITHDRAW_MIN_SATS = 150_000;          // 0.00150000 BTC
export const WITHDRAW_MAX_SATS = 10_000_000;       // safety ceiling 0.10 BTC
export const WITHDRAW_FEE_PCT = 0.10;              // 10% flat
export const WITHDRAW_FEE_FLAT_SATS = 0;           // no baseline

export function btcToSats(btc: number): number {
  return Math.round(btc * SATS_PER_BTC);
}

export function satsToBtc(sats: number): number {
  return sats / SATS_PER_BTC;
}

export function fmtSats(sats: number): string {
  if (!isFinite(sats)) return '0 sats';
  return `${Math.max(0, Math.round(sats)).toLocaleString()} sats`;
}

export function fmtBtc(btc: number, places = 8): string {
  if (!isFinite(btc)) return '0';
  return btc.toFixed(places);
}

export function withdrawalFee(sats: number): number {
  // Flat 10% — no baseline.
  return Math.ceil(sats * WITHDRAW_FEE_PCT);
}

export function netReceive(sats: number): number {
  return Math.max(0, sats - withdrawalFee(sats));
}

export function clampWithdraw(sats: number): { sats: number; clamped: boolean; reason?: string } {
  if (sats < WITHDRAW_MIN_SATS) return { sats: WITHDRAW_MIN_SATS, clamped: true, reason: 'below_minimum' };
  if (sats > WITHDRAW_MAX_SATS) return { sats: WITHDRAW_MAX_SATS, clamped: true, reason: 'above_maximum' };
  return { sats: Math.round(sats), clamped: false };
}
