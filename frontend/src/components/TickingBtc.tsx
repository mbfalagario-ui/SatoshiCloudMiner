import React, { useEffect, useRef, useState } from 'react';
import { Text, TextStyle, StyleProp, Platform } from 'react-native';

/**
 * Smoothly ticks a BTC value upward at a per-second rate (the user's
 * "live earnings"). Re-syncs to the authoritative `baseBtc` value on
 * every prop change (i.e. each /api/earnings refresh).
 *
 * - Tunable precision via `decimals` (default 8 = BTC standard).
 * - Choose unit "BTC" (default) or "sats" (auto-multiplies by 1e8 so the
 *   sub-satoshi growth is visible even for tiny balances).
 * - Pauses when `ratePerSecondBtc` is 0 (no hashrate).
 * - Uses `requestAnimationFrame` on web; `setInterval(200ms)` on native
 *   to keep CPU/battery low.
 */
export default function TickingBtc({
  baseBtc,
  ratePerSecondBtc,
  style,
  suffix,
  decimals = 8,
  unit = 'BTC',
  testID,
}: {
  baseBtc: number;
  ratePerSecondBtc: number;
  style?: StyleProp<TextStyle>;
  suffix?: string;
  decimals?: number;
  unit?: 'BTC' | 'sats';
  testID?: string;
}) {
  const [value, setValue] = useState<number>(baseBtc || 0);
  const baseRef = useRef<number>(baseBtc || 0);
  const rateRef = useRef<number>(ratePerSecondBtc || 0);
  const startedAtRef = useRef<number>(Date.now());

  useEffect(() => {
    baseRef.current = baseBtc || 0;
    rateRef.current = ratePerSecondBtc || 0;
    startedAtRef.current = Date.now();
    setValue(baseBtc || 0);
  }, [baseBtc, ratePerSecondBtc]);

  useEffect(() => {
    if (!rateRef.current || rateRef.current <= 0) return;
    let cancelled = false;
    if (Platform.OS === 'web' && typeof requestAnimationFrame !== 'undefined') {
      let rafId: any;
      const loop = () => {
        if (cancelled) return;
        const elapsed = (Date.now() - startedAtRef.current) / 1000;
        setValue(baseRef.current + rateRef.current * elapsed);
        rafId = requestAnimationFrame(loop);
      };
      rafId = requestAnimationFrame(loop);
      return () => { cancelled = true; if (rafId) cancelAnimationFrame(rafId); };
    } else {
      const t = setInterval(() => {
        if (cancelled) return;
        const elapsed = (Date.now() - startedAtRef.current) / 1000;
        setValue(baseRef.current + rateRef.current * elapsed);
      }, 200);
      return () => { cancelled = true; clearInterval(t); };
    }
  }, [baseBtc, ratePerSecondBtc]);

  const display = unit === 'sats' ? value * 100_000_000 : value;
  const defaultSuffix = unit === 'sats' ? ' sats' : ' BTC';
  return (
    <Text style={style} testID={testID}>
      {display.toFixed(decimals)}{suffix !== undefined ? suffix : defaultSuffix}
    </Text>
  );
}
