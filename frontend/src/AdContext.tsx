import React, { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react';
import { useSession } from '@/src/ctx';
import AdInterstitial from '@/src/components/AdInterstitial';

type Ctx = {
  adFree: boolean;
  showInterstitial: (reason?: string) => Promise<void>;
};

const AdContext = createContext<Ctx | null>(null);

const MIN_INTERSTITIAL_GAP_MS = 35_000;  // never more than once every 35s

export function AdProvider({ children }: { children: React.ReactNode }) {
  const { user } = useSession();
  const [visible, setVisible] = useState(false);
  const lastShownRef = useRef<number>(0);
  const resolverRef = useRef<(() => void) | null>(null);

  const adFree = !!user?.ad_free;

  const showInterstitial = useCallback(async (_reason?: string) => {
    if (adFree) return;
    const now = Date.now();
    if (now - lastShownRef.current < MIN_INTERSTITIAL_GAP_MS) return;
    lastShownRef.current = now;
    setVisible(true);
    await new Promise<void>((resolve) => { resolverRef.current = resolve; });
  }, [adFree]);

  const onClose = useCallback(() => {
    setVisible(false);
    resolverRef.current?.();
    resolverRef.current = null;
  }, []);

  const value = useMemo(() => ({ adFree, showInterstitial }), [adFree, showInterstitial]);

  return (
    <AdContext.Provider value={value}>
      {children}
      <AdInterstitial visible={visible} onClose={onClose} />
    </AdContext.Provider>
  );
}

export function useAds(): Ctx {
  const c = useContext(AdContext);
  if (!c) {
    // Outside the provider (e.g. on the auth screens) — return a no-op shim.
    return { adFree: true, showInterstitial: async () => {} };
  }
  return c;
}
