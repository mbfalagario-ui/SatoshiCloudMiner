/**
 * Global ad orchestration context.
 *
 * Build #28 — rewritten to use the real Google AdMob SDK via
 * `src/utils/ads.ts`. The previous version rendered a custom 5-second
 * timer modal (`AdRewarded.tsx`) which was the direct cause of Apple
 * Rejection #7 ("There was no ads available in the app").
 *
 * Public API (unchanged signature for backward compat with callers):
 *   { adFree, showInterstitial, showRewarded, isRewardedLoaded }
 *
 * Behaviour:
 *   - On mount, calls `initAds()` once (requests ATT → initialises
 *     Google Mobile Ads SDK → pre-loads rewarded + interstitial).
 *   - `showRewarded()` calls into the real `RewardedAd.show()`, returns
 *     `true` if `EARNED_REWARD` fired, `false` otherwise.
 *   - `showInterstitial()` calls real `InterstitialAd.show()` and resolves
 *     when the ad is dismissed (or immediately if no ad loaded — never
 *     blocks).
 *   - On non-iOS platforms every call is a graceful no-op so dev workflow
 *     on web/Android keeps working.
 */
import React, {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from 'react';
import { useSession } from '@/src/ctx';
import {
  initAds,
  getRewardedManager,
  getInterstitialManager,
  subscribeRewardedLoaded,
} from '@/src/utils/ads';

type Ctx = {
  adFree: boolean;
  /** True when a rewarded ad is loaded and ready to show right now. */
  isRewardedLoaded: boolean;
  /** Last load/error message from the rewarded ad SDK; null if no error. */
  rewardedError: string | null;
  /** Show an interstitial. Never blocks UI; resolves immediately if not loaded. */
  showInterstitial: (reason?: string) => Promise<void>;
  /** Show a rewarded ad. Resolves `true` if user earned the reward, `false` if cancelled. */
  showRewarded: (reason?: string) => Promise<boolean>;
};

const AdContext = createContext<Ctx | null>(null);

const MIN_INTERSTITIAL_GAP_MS = 35_000;  // never more than once every 35s

export function AdProvider({ children }: { children: React.ReactNode }) {
  const { user } = useSession();
  const [isRewardedLoaded, setIsRewardedLoaded] = useState(false);
  const [rewardedError, setRewardedError] = useState<string | null>(null);
  const lastInterstitialRef = useRef<number>(0);

  const adFree = !!user?.ad_free;

  // 1. Boot the AdMob SDK exactly once for the lifetime of the app.
  //    `initAds()` is idempotent.
  useEffect(() => {
    initAds().catch((e) => {
      // eslint-disable-next-line no-console
      console.warn('[AdProvider] initAds failed:', e);
    });
  }, []);

  // 2. Track rewarded ad load-state so the Watch button can be gated.
  useEffect(() => {
    const unsub = subscribeRewardedLoaded((loaded, err) => {
      setIsRewardedLoaded(loaded);
      setRewardedError(err);
    });
    return () => { unsub(); };
  }, []);

  const showInterstitial = useCallback(async (_reason?: string): Promise<void> => {
    if (adFree) return;
    const now = Date.now();
    if (now - lastInterstitialRef.current < MIN_INTERSTITIAL_GAP_MS) return;
    lastInterstitialRef.current = now;
    const mgr = getInterstitialManager();
    if (!mgr) return;
    try {
      await mgr.show();
    } catch (e) {
      // eslint-disable-next-line no-console
      console.warn('[AdProvider] interstitial.show failed:', e);
    }
  }, [adFree]);

  const showRewarded = useCallback(async (_reason?: string): Promise<boolean> => {
    // Rewarded ads are opt-in regardless of ad_free entitlement — the
    // user explicitly tapped a "Watch ad for free hashrate" button.
    const mgr = getRewardedManager();
    if (!mgr) {
      throw new Error('Ad system is still warming up — please try again in a moment.');
    }
    return mgr.show();
  }, []);

  const value = useMemo(
    () => ({ adFree, isRewardedLoaded, rewardedError, showInterstitial, showRewarded }),
    [adFree, isRewardedLoaded, rewardedError, showInterstitial, showRewarded],
  );

  return <AdContext.Provider value={value}>{children}</AdContext.Provider>;
}

export function useAds(): Ctx {
  const c = useContext(AdContext);
  if (!c) {
    return {
      adFree: true,
      isRewardedLoaded: false,
      rewardedError: null,
      showInterstitial: async () => {},
      showRewarded: async () => true,
    };
  }
  return c;
}
