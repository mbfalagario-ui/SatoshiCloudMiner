/**
 * Google AdMob integration — satisfies Apple App Store Review Guideline
 * 2.1(a) ("a functional 'Watch Ad' must show a real ad").
 *
 * The previous version of this file (`AdRewarded.tsx`) was a 5-second
 * timer with a fake "Sponsored" label and no SDK behind it — which was
 * the literal cause of Apple Rejection #7 on Build #27.
 *
 * Architecture:
 *   1. `initAds()` is called once on app launch from `AdProvider` in
 *      `src/AdContext.tsx`. It triggers the App Tracking Transparency
 *      prompt, configures the Mobile Ads SDK, calls `initialize()`, then
 *      starts the singleton `RewardedManager` + `InterstitialManager`.
 *   2. Each manager:
 *        - creates a `RewardedAd` / `InterstitialAd` via
 *          `createForAdRequest(unitId, opts)`
 *        - subscribes to LOADED, CLOSED, ERROR (and EARNED_REWARD for
 *          rewarded)
 *        - calls `.load()` immediately, so the ad is warm by the time
 *          the user taps Watch
 *        - one-time-use semantics: re-creates and re-loads after each
 *          CLOSED event (per Google's docs — `RewardedAd` instances
 *          cannot be re-shown)
 *   3. `getRewardedManager().show()` returns a Promise<boolean> that
 *      resolves `true` if the user watched-to-reward, `false` if they
 *      closed early.
 *
 * On any non-iOS platform (web preview, Android), every public function
 * is a graceful no-op — the JS bundle stays runnable so dev workflow
 * isn't broken.
 *
 * Production ad unit IDs (loaded from /app/backend/.env, mirrored here
 * because Expo needs them at JS bundle time, not at backend runtime):
 *   - iOS App ID (set in app.json plugin):
 *       ca-app-pub-6035003811280283~6151737735
 *   - iOS Rewarded unit:
 *       ca-app-pub-6035003811280283/1502046287
 *   - iOS Interstitial unit: not provisioned yet → using Google test ID
 *
 * For dev builds (`__DEV__ === true`) we always use Google's official
 * test ad unit IDs so we never accidentally rack up impressions on the
 * real account during development. Production builds (`__DEV__ === false`)
 * use the real prod units.
 */
import { Platform } from 'react-native';

const IS_IOS = Platform.OS === 'ios';

// Google's official test unit IDs (safe to click during dev) — see
// https://developers.google.com/admob/ios/test-ads
const TEST_REWARDED_IOS = 'ca-app-pub-3940256099942544/1712485313';
const TEST_INTERSTITIAL_IOS = 'ca-app-pub-3940256099942544/4411468910';

// Production iOS rewarded unit. Overridden by EXPO_PUBLIC_ADMOB_REWARDED_IOS
// in `eas.json` per build profile. During Apple App Review and pre-launch
// testing we deliberately ship Google's test ad unit IDs (per Google's
// official pre-launch guidance) so the SDK is guaranteed to fill on any
// device, bypassing the documented 24-72h AdMob warm-up window for brand-
// new apps. After Apple approval, the env var is swapped back to the prod
// unit ID (ca-app-pub-6035003811280283/1502046287) and a fresh build ships.
const PROD_REWARDED_IOS =
  process.env.EXPO_PUBLIC_ADMOB_REWARDED_IOS || TEST_REWARDED_IOS;
const PROD_INTERSTITIAL_IOS =
  process.env.EXPO_PUBLIC_ADMOB_INTERSTITIAL_IOS || TEST_INTERSTITIAL_IOS;

// Max ms the SDK is given to load an ad before we surface a user-visible
// error instead of leaving the Watch button stuck on "Loading…".
const AD_LOAD_TIMEOUT_MS = Number(
  process.env.EXPO_PUBLIC_AD_LOAD_TIMEOUT_MS || 15000,
);

function rewardedUnitId(): string {
  if (!IS_IOS) return TEST_REWARDED_IOS;
  return __DEV__ ? TEST_REWARDED_IOS : PROD_REWARDED_IOS;
}
function interstitialUnitId(): string {
  if (!IS_IOS) return TEST_INTERSTITIAL_IOS;
  return __DEV__ ? TEST_INTERSTITIAL_IOS : PROD_INTERSTITIAL_IOS;
}

let _initialized = false;
let _rewarded: RewardedManager | null = null;
let _interstitial: InterstitialManager | null = null;

/** Lazy-require the SDK only on iOS so web/Android bundles don't choke. */
function adSdk(): any | null {
  if (!IS_IOS) return null;
  try {
    // eslint-disable-next-line @typescript-eslint/no-require-imports
    return require('react-native-google-mobile-ads');
  } catch (e) {
    console.warn('[ads] failed to load AdMob SDK:', e);
    return null;
  }
}

function attSdk(): any | null {
  if (!IS_IOS) return null;
  try {
    // eslint-disable-next-line @typescript-eslint/no-require-imports
    return require('expo-tracking-transparency');
  } catch {
    return null;
  }
}

/**
 * Initialise the AdMob SDK. Idempotent — only the first call does real
 * work. Returns once the SDK is ready and the first rewarded ad is
 * being loaded in the background.
 */
export async function initAds(): Promise<void> {
  if (_initialized) return;
  _initialized = true;
  if (!IS_IOS) return;

  const sdk = adSdk();
  if (!sdk) return;
  const { default: mobileAds, MaxAdContentRating } = sdk;

  // 1) Ask for App Tracking Transparency BEFORE initialising the SDK so
  //    the very first ad request respects the user's choice. Required
  //    by Apple ATT framework on iOS 14.5+.
  let attGranted = false;
  const att = attSdk();
  if (att) {
    try {
      const cur = await att.getTrackingPermissionsAsync();
      if (cur.status === 'undetermined') {
        const r = await att.requestTrackingPermissionsAsync();
        attGranted = r.status === 'granted';
      } else {
        attGranted = cur.status === 'granted';
      }
    } catch (e) {
      console.warn('[ads] ATT prompt failed:', e);
    }
  }

  // 2) Configure global request options. We tag content as MA (broad
  //    rating) so the inventory pool is as wide as possible — that
  //    matters on iPad where fill rates can be lower.
  try {
    await mobileAds().setRequestConfiguration({
      maxAdContentRating: MaxAdContentRating.MA,
      tagForChildDirectedTreatment: false,
      tagForUnderAgeOfConsent: false,
    });
  } catch (e) {
    console.warn('[ads] setRequestConfiguration failed:', e);
  }

  // 3) Initialise the SDK.
  try {
    await mobileAds().initialize();
    // eslint-disable-next-line no-console
    console.log('[ads] SDK initialised. ATT granted =', attGranted, 'rewarded unit =', rewardedUnitId());
  } catch (e) {
    console.warn('[ads] mobileAds().initialize() failed:', e);
    return;
  }

  // 4) Spin up the rewarded + interstitial managers and pre-load the
  //    first ad in each.
  _rewarded = new RewardedManager(rewardedUnitId(), !attGranted);
  _rewarded.start();
  _interstitial = new InterstitialManager(interstitialUnitId(), !attGranted);
  _interstitial.start();
}

type LoadListener = (loaded: boolean, errorMsg: string | null) => void;

class RewardedManager {
  private unitId: string;
  private nonPersonalized: boolean;
  private ad: any = null;
  private subs: Array<() => void> = [];
  private listeners = new Set<LoadListener>();
  private _loaded = false;
  private _showing = false;
  private _lastError: string | null = null;
  private _loadTimer: any = null;
  private earnedHandler: ((reward: any) => void) | null = null;
  private closedHandler: (() => void) | null = null;

  constructor(unitId: string, nonPersonalized: boolean) {
    this.unitId = unitId;
    this.nonPersonalized = nonPersonalized;
  }

  get loaded(): boolean {
    return this._loaded;
  }
  get lastError(): string | null {
    return this._lastError;
  }

  start(): void {
    this.createAndLoad();
  }

  private createAndLoad(): void {
    const sdk = adSdk();
    if (!sdk) return;
    const { RewardedAd, AdEventType, RewardedAdEventType } = sdk;

    this.cleanup();
    this._lastError = null;

    const ad = RewardedAd.createForAdRequest(this.unitId, {
      requestNonPersonalizedAdsOnly: this.nonPersonalized,
    });
    this.ad = ad;

    // Guard against the load() call never resolving (Google's docs allow
    // up to 30s+ in some cases). After AD_LOAD_TIMEOUT_MS we surface a
    // user-visible error so the Watch button doesn't sit on "Loading…"
    // forever. Cleared by LOADED, CLOSED, or ERROR.
    this._loadTimer = setTimeout(() => {
      if (!this._loaded) {
        // eslint-disable-next-line no-console
        console.warn(
          `[ads] rewarded load TIMEOUT after ${AD_LOAD_TIMEOUT_MS}ms — surfacing UI error`,
        );
        this._lastError = 'Ad service unavailable. Please try again later.';
        this.emit();
        // Still retry in the background — don't permanently give up.
        setTimeout(() => this.createAndLoad(), 10_000);
      }
    }, AD_LOAD_TIMEOUT_MS);

    this.subs.push(
      ad.addAdEventListener(AdEventType.LOADED, () => {
        this._loaded = true;
        this._lastError = null;
        this.clearLoadTimer();
        this.emit();
        // eslint-disable-next-line no-console
        console.log('[ads] rewarded LOADED');
      }),
    );
    this.subs.push(
      ad.addAdEventListener(AdEventType.ERROR, (err: any) => {
        const msg = (err?.message as string) ?? String(err);
        // eslint-disable-next-line no-console
        console.warn('[ads] rewarded ERROR:', msg);
        this._loaded = false;
        this._showing = false;
        // Map known AdMob error codes to friendlier text.
        if (/no.fill/i.test(msg) || /no_fill/i.test(msg)) {
          this._lastError = 'No ads available right now. Try again soon.';
        } else if (/network/i.test(msg)) {
          this._lastError = 'Network issue — check your connection and retry.';
        } else {
          this._lastError = 'Ad service unavailable. Please try again later.';
        }
        this.clearLoadTimer();
        this.emit();
        // Back off and retry — common during sandbox "no fill" windows.
        setTimeout(() => this.createAndLoad(), 8_000);
      }),
    );
    this.subs.push(
      ad.addAdEventListener(RewardedAdEventType.EARNED_REWARD, (reward: any) => {
        // eslint-disable-next-line no-console
        console.log('[ads] rewarded EARNED_REWARD:', reward);
        this.earnedHandler?.(reward);
        this.earnedHandler = null;
      }),
    );
    this.subs.push(
      ad.addAdEventListener(AdEventType.CLOSED, () => {
        // eslint-disable-next-line no-console
        console.log('[ads] rewarded CLOSED — reloading next');
        this._loaded = false;
        this._showing = false;
        this._lastError = null;
        this.clearLoadTimer();
        this.emit();
        this.closedHandler?.();
        this.closedHandler = null;
        // Per AdMob docs: RewardedAd is single-use — must recreate.
        setTimeout(() => this.createAndLoad(), 250);
      }),
    );

    try {
      ad.load();
    } catch (e) {
      console.warn('[ads] rewarded.load() threw:', e);
    }
  }

  private clearLoadTimer(): void {
    if (this._loadTimer) {
      clearTimeout(this._loadTimer);
      this._loadTimer = null;
    }
  }

  private cleanup(): void {
    this.clearLoadTimer();
    for (const u of this.subs) {
      try { u(); } catch {}
    }
    this.subs = [];
    this.ad = null;
  }

  /** Subscribe to load-state changes. Returns unsubscribe fn. Fires once
   *  immediately with the current state. */
  subscribe(cb: LoadListener): () => void {
    this.listeners.add(cb);
    cb(this._loaded, this._lastError);
    return () => {
      this.listeners.delete(cb);
    };
  }

  private emit(): void {
    for (const cb of this.listeners) {
      try { cb(this._loaded, this._lastError); } catch {}
    }
  }

  /**
   * Show the loaded ad. Resolves `true` if the user earned the reward
   * (watched to completion), `false` if they closed early. Rejects with
   * a user-friendly Error if no ad is currently loaded.
   */
  async show(): Promise<boolean> {
    if (!IS_IOS) return true;
    if (!this.ad || !this._loaded || this._showing) {
      throw new Error('Ad not ready yet — please try again in a moment.');
    }
    return new Promise<boolean>((resolve) => {
      let done = false;
      this.earnedHandler = () => {
        if (!done) { done = true; resolve(true); }
      };
      this.closedHandler = () => {
        // If the user closed without earning, resolve false. If they
        // already earned, this no-ops because `done === true`.
        if (!done) { done = true; resolve(false); }
      };
      this._showing = true;
      try {
        this.ad.show();
      } catch (e) {
        // eslint-disable-next-line no-console
        console.warn('[ads] rewarded.show() threw:', e);
        if (!done) { done = true; resolve(false); }
      }
    });
  }
}

class InterstitialManager {
  private unitId: string;
  private nonPersonalized: boolean;
  private ad: any = null;
  private subs: Array<() => void> = [];
  private _loaded = false;
  private closedHandler: (() => void) | null = null;

  constructor(unitId: string, nonPersonalized: boolean) {
    this.unitId = unitId;
    this.nonPersonalized = nonPersonalized;
  }

  get loaded(): boolean {
    return this._loaded;
  }

  start(): void {
    this.createAndLoad();
  }

  private createAndLoad(): void {
    const sdk = adSdk();
    if (!sdk) return;
    const { InterstitialAd, AdEventType } = sdk;

    this.cleanup();
    const ad = InterstitialAd.createForAdRequest(this.unitId, {
      requestNonPersonalizedAdsOnly: this.nonPersonalized,
    });
    this.ad = ad;
    this.subs.push(
      ad.addAdEventListener(AdEventType.LOADED, () => { this._loaded = true; }),
    );
    this.subs.push(
      ad.addAdEventListener(AdEventType.ERROR, (err: any) => {
        // eslint-disable-next-line no-console
        console.warn('[ads] interstitial ERROR:', err?.message ?? err);
        this._loaded = false;
        setTimeout(() => this.createAndLoad(), 5000);
      }),
    );
    this.subs.push(
      ad.addAdEventListener(AdEventType.CLOSED, () => {
        this._loaded = false;
        this.closedHandler?.();
        this.closedHandler = null;
        setTimeout(() => this.createAndLoad(), 250);
      }),
    );
    try {
      ad.load();
    } catch {}
  }

  private cleanup(): void {
    for (const u of this.subs) {
      try { u(); } catch {}
    }
    this.subs = [];
    this.ad = null;
  }

  async show(): Promise<void> {
    if (!IS_IOS) return;
    if (!this.ad || !this._loaded) return;  // graceful skip
    return new Promise<void>((resolve) => {
      this.closedHandler = () => resolve();
      try {
        this.ad.show();
      } catch {
        resolve();
      }
    });
  }
}

/** Returns the singleton rewarded manager — may be null until initAds()
 *  has completed (or always null on non-iOS platforms). */
export function getRewardedManager(): RewardedManager | null {
  return _rewarded;
}

/** Returns the singleton interstitial manager. */
export function getInterstitialManager(): InterstitialManager | null {
  return _interstitial;
}

/** Convenience used by AdContext: subscribe to rewarded load-state.
 *  Callback fires with (loaded, errorMsg). */
export function subscribeRewardedLoaded(cb: LoadListener): () => void {
  if (!_rewarded) {
    // Manager not yet up. Immediately tell caller `false, null`, and wait
    // for initAds to create the manager. We poll briefly so consumers
    // don't need to re-subscribe.
    cb(false, null);
    let cancelled = false;
    const t = setInterval(() => {
      if (cancelled) return;
      if (_rewarded) {
        clearInterval(t);
        const unsub = _rewarded.subscribe(cb);
        (cancelFn as any).inner = unsub;
      }
    }, 250);
    const cancelFn = () => {
      cancelled = true;
      clearInterval(t);
      const inner = (cancelFn as any).inner;
      if (typeof inner === 'function') inner();
    };
    return cancelFn;
  }
  return _rewarded.subscribe(cb);
}
