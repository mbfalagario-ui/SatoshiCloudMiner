/**
 * Web-only Metro stub for `react-native-google-mobile-ads`.
 *
 * WHY: the real package imports react-native native internals
 * (codegenNativeComponent) that crash the Expo WEB bundler, which broke
 * the browser preview used for QA. `src/utils/ads.ts` only ever calls
 * require('react-native-google-mobile-ads') behind an `IS_IOS` guard, so
 * on web this stub is bundled but never actually executed.
 *
 * SCOPE: metro.config.js maps the module to this file ONLY when
 * `platform === 'web'`. iOS / Android native builds (including EAS
 * production builds) resolve the REAL package — this file has zero
 * effect on the shipped App Store binary.
 */
const noop = () => {};
const noopAsync = () => Promise.resolve();

const stubAd = {
  load: noop,
  show: noopAsync,
  addAdEventListener: () => noop, // returns an unsubscribe fn
  loaded: false,
};

const MobileAds = () => ({
  initialize: noopAsync,
  setRequestConfiguration: noopAsync,
});

module.exports = {
  __esModule: true,
  default: MobileAds,
  MobileAds,
  RewardedAd: { createForAdRequest: () => ({ ...stubAd }) },
  InterstitialAd: { createForAdRequest: () => ({ ...stubAd }) },
  AdEventType: { LOADED: 'loaded', ERROR: 'error', CLOSED: 'closed', OPENED: 'opened' },
  RewardedAdEventType: { LOADED: 'rewarded_loaded', EARNED_REWARD: 'rewarded_earned_reward' },
  TestIds: { REWARDED: 'web-stub', INTERSTITIAL: 'web-stub' },
  MaxAdContentRating: { G: 'G', PG: 'PG', T: 'T', MA: 'MA' },
};
