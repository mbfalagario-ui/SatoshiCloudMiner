/**
 * Centralised JS-side exception fence + crash telemetry.
 *
 * Why this exists (Build #33):
 *   The Build #32 .ips files showed an uncaught NSException originating
 *   on `com.facebook.react.ExceptionsManagerQueue` — which means React
 *   Native's `RCTExceptionsManager` (the native module that processes
 *   uncaught JS exceptions) is itself throwing under iOS 26.5 beta's
 *   stricter Foundation APIs. The crash chain is:
 *
 *     JS throws  →  RN bridge forwards to native RCTExceptionsManager
 *                →  RCTExceptionsManager calls Foundation APIs
 *                →  Foundation throws NSException
 *                →  abort()
 *
 *   If we intercept the JS exception in JS BEFORE it reaches the native
 *   bridge, step 1→2 never happens and the native crash path is never
 *   entered.
 *
 * Design (per GPT/Michael's calibration on Build #33 ask):
 *   - DO NOT silently swallow errors. That hides real bugs.
 *   - DO capture → persist (AsyncStorage) → telemetry POST → show
 *     fallback UI via React ErrorBoundary → user manually restarts.
 *   - DO ensure the very NEXT crash gives us a fully symbolicated JS
 *     stack trace (via the drainPendingErrors flow on next launch).
 *   - Re-throw for the ErrorBoundary to render fallback UI; do NOT
 *     forward to the default RN handler (that's what crashes).
 */
import AsyncStorage from '@react-native-async-storage/async-storage';
import { Platform } from 'react-native';
import Constants from 'expo-constants';

const STORAGE_KEY = '@hashrate/pending_crashes';
const BACKEND = process.env.EXPO_PUBLIC_BACKEND_URL || '';
const APP_VERSION =
  (Constants.expoConfig?.version as string) ||
  (Constants.manifest as any)?.version ||
  'unknown';
const BUILD_NUMBER =
  (Constants.expoConfig?.ios?.buildNumber as string) ||
  (Constants.manifest as any)?.ios?.buildNumber ||
  'unknown';

type StoredCrash = {
  ts: string;
  type: 'error' | 'unhandled-rejection' | 'render-boundary';
  fatal: boolean;
  message: string;
  stack: string;
  app_version: string;
  build_number: string;
  platform: string;
  os_version: string;
};

let _installed = false;

/* ────────────────────────────────────────────────────────────────────
 * Fatal-error broadcast.
 * Why this exists: when the global handler captures a fatal JS error,
 * we must NOT re-throw it (re-throwing routes it back through
 * `ErrorUtils.reportError` → `_globalHandler` → infinite loop). Instead
 * we publish to a tiny in-process event bus that the React
 * `ErrorBoundary` subscribes to via `componentDidMount` and flips its
 * own state to show the fallback UI. We also keep ONE pending fatal in
 * module memory so the boundary mounting AFTER the error can still
 * pick it up.
 * ──────────────────────────────────────────────────────────────────── */
type FatalListener = (message: string, stack: string) => void;
const _fatalListeners = new Set<FatalListener>();
let _pendingFatal: { message: string; stack: string } | null = null;

export function addFatalErrorListener(fn: FatalListener): () => void {
  _fatalListeners.add(fn);
  return () => {
    _fatalListeners.delete(fn);
  };
}

export function consumePendingFatal(): { message: string; stack: string } | null {
  const p = _pendingFatal;
  _pendingFatal = null;
  return p;
}

function broadcastFatal(message: string, stack: string): void {
  _pendingFatal = { message, stack };
  for (const fn of _fatalListeners) {
    try { fn(message, stack); } catch {}
  }
}

/** Persist a crash record to AsyncStorage and best-effort POST to backend.
 *  Returns once persistence has flushed (or failed). */
async function captureAndPersist(rec: StoredCrash): Promise<void> {
  // 1) Persist to AsyncStorage so we don't lose this even if the POST
  //    below fails / the app aborts before the network finishes.
  try {
    const existingRaw = await AsyncStorage.getItem(STORAGE_KEY);
    const existing: StoredCrash[] = existingRaw ? JSON.parse(existingRaw) : [];
    existing.push(rec);
    // Cap at 20 so AsyncStorage doesn't grow unboundedly.
    while (existing.length > 20) existing.shift();
    await AsyncStorage.setItem(STORAGE_KEY, JSON.stringify(existing));
  } catch (e) {
    // eslint-disable-next-line no-console
    console.warn('[errorHandler] persist failed:', e);
  }

  // 2) Best-effort fire-and-forget POST to backend telemetry. We don't
  //    `await` the response because the app may be aborting; the next
  //    launch's drain pass will retry from AsyncStorage anyway.
  if (BACKEND) {
    try {
      fetch(`${BACKEND}/api/telemetry/crash`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(rec),
      }).catch(() => {});
    } catch {}
  }
}

/** Top-level error handler installed via `global.ErrorUtils.setGlobalHandler`.
 *  Captures and persists. On fatal, broadcasts to the ErrorBoundary
 *  subscriber so it can render fallback UI. Does NOT re-throw and does
 *  NOT delegate to RN's default handler — those would route the error
 *  back to native `RCTExceptionsManager` (which aborts on iOS 26.5 beta)
 *  or back through ErrorUtils (which would re-enter THIS handler in an
 *  infinite loop). */
function handleGlobalError(error: any, isFatal?: boolean): void {
  const rec: StoredCrash = {
    ts: new Date().toISOString(),
    type: 'error',
    fatal: !!isFatal,
    message: String(error?.message || error || 'unknown'),
    stack: String(error?.stack || ''),
    app_version: APP_VERSION,
    build_number: BUILD_NUMBER,
    platform: Platform.OS,
    os_version: String(Platform.Version),
  };
  // eslint-disable-next-line no-console
  console.warn('[errorHandler] captured:', rec.type, rec.message);
  // Persist (best-effort, async). We do NOT await — JS may be unwinding.
  captureAndPersist(rec);
  // For fatal errors, broadcast to the React ErrorBoundary so it shows
  // the fallback UI. Non-fatal errors just log + telemetry; the app
  // continues running (matching RN's default production behaviour).
  if (isFatal) {
    broadcastFatal(rec.message, rec.stack);
  }
}

/** Promise rejection tracker for Hermes. */
function setupPromiseRejectionTracker(): void {
  // Hermes exposes `HermesInternal.enablePromiseRejectionTracker`.
  // We register a listener that captures and persists each unhandled
  // rejection. We DO NOT re-throw — Promise rejections are inherently
  // recoverable; just log + telemetry.
  const HermesInternal: any = (globalThis as any).HermesInternal;
  if (!HermesInternal?.enablePromiseRejectionTracker) {
    // Fallback: monkey-patch Promise to track .catch-less rejections.
    return;
  }
  HermesInternal.enablePromiseRejectionTracker({
    allRejections: true,
    onUnhandled: (_id: number, error: any) => {
      const rec: StoredCrash = {
        ts: new Date().toISOString(),
        type: 'unhandled-rejection',
        fatal: false,
        message: String(error?.message || error || 'unhandled rejection'),
        stack: String(error?.stack || ''),
        app_version: APP_VERSION,
        build_number: BUILD_NUMBER,
        platform: Platform.OS,
        os_version: String(Platform.Version),
      };
      // eslint-disable-next-line no-console
      console.warn('[errorHandler] unhandled rejection:', rec.message);
      captureAndPersist(rec);
    },
    onHandled: () => {},
  });
}

/** One-time installation. Call ONCE from the very top of the app entry
 *  (`app/_layout.tsx`) BEFORE any other module that could throw. */
export function installErrorHandlers(): void {
  if (_installed) return;
  _installed = true;
  const eu: any = (globalThis as any).ErrorUtils;
  if (eu?.setGlobalHandler) {
    eu.setGlobalHandler(handleGlobalError);
  } else {
    // eslint-disable-next-line no-console
    console.warn('[errorHandler] global.ErrorUtils not available — handlers NOT installed');
  }
  try {
    setupPromiseRejectionTracker();
  } catch (e) {
    console.warn('[errorHandler] promise tracker setup failed:', e);
  }
  // eslint-disable-next-line no-console
  console.log('[errorHandler] installed. backend =', BACKEND);
}

/** Public hook for the ErrorBoundary to record render-time errors.
 *  Called from `ErrorBoundary.componentDidCatch`. */
export function recordRenderError(error: Error, componentStack: string): void {
  const rec: StoredCrash = {
    ts: new Date().toISOString(),
    type: 'render-boundary',
    fatal: true,
    message: String(error.message || error),
    stack: `${error.stack ?? ''}\n--- componentStack ---\n${componentStack}`,
    app_version: APP_VERSION,
    build_number: BUILD_NUMBER,
    platform: Platform.OS,
    os_version: String(Platform.Version),
  };
  // eslint-disable-next-line no-console
  console.warn('[errorHandler] render boundary captured:', rec.message);
  captureAndPersist(rec);
}

/** On app launch, drain any pending error records that were persisted
 *  before the previous session ended (potentially because of a crash)
 *  and POST them to the backend so we can inspect symbolicated stacks
 *  via the admin console. Safe to call concurrently / multiple times. */
export async function drainPendingErrors(): Promise<void> {
  if (!BACKEND) return;
  let pending: StoredCrash[] = [];
  try {
    const raw = await AsyncStorage.getItem(STORAGE_KEY);
    if (!raw) return;
    pending = JSON.parse(raw);
  } catch {
    return;
  }
  if (!pending.length) return;
  // eslint-disable-next-line no-console
  console.log(`[errorHandler] draining ${pending.length} pending crash report(s)`);
  let posted = 0;
  for (const rec of pending) {
    try {
      const resp = await fetch(`${BACKEND}/api/telemetry/crash`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(rec),
      });
      if (resp.ok) posted += 1;
    } catch {
      // network down — keep this record for next launch
      break;
    }
  }
  if (posted >= pending.length) {
    try { await AsyncStorage.removeItem(STORAGE_KEY); } catch {}
  } else if (posted > 0) {
    try {
      await AsyncStorage.setItem(
        STORAGE_KEY,
        JSON.stringify(pending.slice(posted)),
      );
    } catch {}
  }
}
