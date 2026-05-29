import React, { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react';
import { useSession } from '@/src/ctx';
import AdInterstitial from '@/src/components/AdInterstitial';
import AdRewarded from '@/src/components/AdRewarded';

type Ctx = {
  adFree: boolean;
  showInterstitial: (reason?: string) => Promise<void>;
  showRewarded: (reason?: string) => Promise<boolean>;
};

const AdContext = createContext<Ctx | null>(null);

const MIN_INTERSTITIAL_GAP_MS = 35_000;  // never more than once every 35s

export function AdProvider({ children }: { children: React.ReactNode }) {
  const { user } = useSession();
  const [visible, setVisible] = useState(false);
  const [rewardedVisible, setRewardedVisible] = useState(false);
  const lastShownRef = useRef<number>(0);
  const resolverRef = useRef<(() => void) | null>(null);
  const rewardedResolverRef = useRef<((ok: boolean) => void) | null>(null);

  const adFree = !!user?.ad_free;

  const showInterstitial = useCallback(async (_reason?: string) => {
    if (adFree) return;
    try {
      if (typeof window !== 'undefined' && window.localStorage?.getItem('scm_no_ads') === '1') return;
    } catch {}
    const now = Date.now();
    if (now - lastShownRef.current < MIN_INTERSTITIAL_GAP_MS) return;
    lastShownRef.current = now;
    setVisible(true);
    await new Promise<void>((resolve) => { resolverRef.current = resolve; });
  }, [adFree]);

  const showRewarded = useCallback(async (_reason?: string): Promise<boolean> => {
    // Rewarded ads are explicitly opt-in regardless of ad_free entitlement.
    try {
      if (typeof window !== 'undefined' && window.localStorage?.getItem('scm_no_ads') === '1') return true;
    } catch {}
    setRewardedVisible(true);
    return await new Promise<boolean>((resolve) => { rewardedResolverRef.current = resolve; });
  }, []);

  const onClose = useCallback(() => {
    setVisible(false);
    resolverRef.current?.();
    resolverRef.current = null;
  }, []);

  const onRewardedClose = useCallback((ok: boolean) => {
    setRewardedVisible(false);
    rewardedResolverRef.current?.(ok);
    rewardedResolverRef.current = null;
  }, []);

  const value = useMemo(() => ({ adFree, showInterstitial, showRewarded }), [adFree, showInterstitial, showRewarded]);

  return (
    <AdContext.Provider value={value}>
      {children}
      <AdInterstitial visible={visible} onClose={onClose} />
      <AdRewarded visible={rewardedVisible} onClose={onRewardedClose} />
    </AdContext.Provider>
  );
}

export function useAds(): Ctx {
  const c = useContext(AdContext);
  if (!c) {
    return {
      adFree: true,
      showInterstitial: async () => {},
      showRewarded: async () => true,
    };
  }
  return c;
}
