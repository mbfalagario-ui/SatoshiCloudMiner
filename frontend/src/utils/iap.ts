/**
 * In-App Purchase wrapper around `react-native-iap` v15+ (Nitro / openiap).
 *
 * v15 is event-driven: `requestPurchase()` does NOT return a Purchase — the
 * actual Purchase object arrives through `purchaseUpdatedListener`, errors
 * through `purchaseErrorListener`. This wrapper hides that and exposes a
 * promise-style `buyProduct()` matching how the rest of the app uses it.
 *
 * Key v15.x requirements (from `lib/typescript/src/types.d.ts`):
 *   - `requestPurchase({ request: { apple: { sku } }, type: 'in-app' })`
 *     The deprecated `ios:` key is now `apple:`. Using the old key throws
 *     synchronously on TestFlight.
 *   - You MUST call `fetchProducts({ skus, type: 'in-app' })` for every SKU
 *     before `requestPurchase`, otherwise StoreKit2 raises
 *     `E_PRODUCT_NOT_AVAILABLE`.
 *
 * Cross-platform contract:
 *  - iOS native (TestFlight / App Store) → real StoreKit prompt + receipt
 *  - Everything else (Expo Go / Web / Android) → falls through to a
 *    "dev-mode" result so the rest of the flow stays testable.
 */
import { Platform } from 'react-native';

export type IapBuyResult = {
  applePurchase: boolean;
  transactionId?: string;
  productId: string;
};

let _initialized = false;
let _connected = false;
let _iap: any = null;
let _purchaseSub: { remove: () => void } | null = null;
let _errorSub: { remove: () => void } | null = null;
const _fetchedSkus = new Set<string>();

type PendingResolver = {
  productId: string;
  resolve: (r: IapBuyResult) => void;
  reject: (e: Error) => void;
};
const _pending: PendingResolver[] = [];

function loadModule(): any | null {
  if (Platform.OS !== 'ios') return null;
  if (_iap !== null) return _iap;
  try {
    // eslint-disable-next-line @typescript-eslint/no-require-imports
    _iap = require('react-native-iap');
    return _iap;
  } catch (e) {
    // eslint-disable-next-line no-console
    console.warn('[IAP] require(react-native-iap) failed:', e);
    _iap = null;
    return null;
  }
}

export function isIapAvailable(): boolean {
  return Platform.OS === 'ios' && loadModule() !== null;
}

function _extractProductId(purchase: any): string | undefined {
  return (
    purchase?.productId ||
    (Array.isArray(purchase?.productIds) ? purchase.productIds[0] : undefined) ||
    purchase?.id
  );
}

function _extractTransactionId(purchase: any): string | undefined {
  return (
    purchase?.transactionId ||
    purchase?.originalTransactionIdentifierIOS ||
    purchase?.transactionIdentifier ||
    purchase?.id ||
    undefined
  );
}

function _ensureListeners(iap: any) {
  if (_purchaseSub || _errorSub) return;
  if (typeof iap.purchaseUpdatedListener === 'function') {
    _purchaseSub = iap.purchaseUpdatedListener(async (purchase: any) => {
      const productId = _extractProductId(purchase);
      const tx = _extractTransactionId(purchase);
      // eslint-disable-next-line no-console
      console.log('[IAP] purchaseUpdated:', { productId, tx });

      // Resolve the matching pending request (FIFO if productId unknown).
      const idx = _pending.findIndex((p) =>
        productId ? p.productId === productId : true,
      );
      if (idx >= 0) {
        const slot = _pending.splice(idx, 1)[0];
        slot.resolve({
          applePurchase: Boolean(tx),
          transactionId: tx,
          productId: productId || slot.productId,
        });
      }

      // Always finish the transaction so StoreKit doesn't redeliver it.
      try {
        if (typeof iap.finishTransaction === 'function') {
          await iap.finishTransaction({ purchase, isConsumable: true });
        }
      } catch (e) {
        // eslint-disable-next-line no-console
        console.warn('[IAP] finishTransaction failed (non-fatal):', e);
      }
    });
  }
  if (typeof iap.purchaseErrorListener === 'function') {
    _errorSub = iap.purchaseErrorListener((err: any) => {
      const productId = err?.productId;
      const msg =
        err?.message ||
        err?.debugMessage ||
        err?.code ||
        'Apple purchase failed';
      // eslint-disable-next-line no-console
      console.warn('[IAP] purchaseError:', { code: err?.code, productId, msg });
      const idx = _pending.findIndex((p) =>
        productId ? p.productId === productId : true,
      );
      if (idx >= 0) {
        const slot = _pending.splice(idx, 1)[0];
        slot.reject(new Error(msg));
      }
    });
  }
}

export async function initIap(): Promise<boolean> {
  const iap = loadModule();
  if (!iap) return false;
  if (_initialized && _connected) return true;
  try {
    if (typeof iap.initConnection === 'function') {
      // v15 returns a Promise<boolean>.
      const ok = await iap.initConnection();
      _connected = ok !== false;
    } else {
      _connected = true; // module loaded but no init — treat as connected
    }
    _ensureListeners(iap);
    _initialized = true;
    return _connected;
  } catch (e) {
    // eslint-disable-next-line no-console
    console.warn('[IAP] initConnection failed', e);
    return false;
  }
}

/**
 * Pre-warm the StoreKit product cache for the given SKUs. v15 REQUIRES this
 * call before `requestPurchase` — otherwise StoreKit raises
 * `E_PRODUCT_NOT_AVAILABLE`.
 */
export async function fetchProducts(productIds: string[]): Promise<any[]> {
  if (!productIds.length) return [];
  const iap = loadModule();
  if (!iap) return [];
  await initIap();
  try {
    if (typeof iap.fetchProducts === 'function') {
      const r = await iap.fetchProducts({ skus: productIds, type: 'in-app' });
      const arr = Array.isArray(r) ? r : r?.products || [];
      for (const p of arr) {
        const id = p?.productId || p?.id;
        if (typeof id === 'string') _fetchedSkus.add(id);
      }
      return arr;
    }
    if (typeof iap.requestProducts === 'function') {
      const r = await iap.requestProducts({ skus: productIds, type: 'in-app' });
      const arr = Array.isArray(r) ? r : [];
      for (const p of arr) {
        const id = p?.productId || p?.id;
        if (typeof id === 'string') _fetchedSkus.add(id);
      }
      return arr;
    }
    if (typeof iap.getProducts === 'function') {
      const arr = (await iap.getProducts({ skus: productIds })) || [];
      for (const p of arr) {
        const id = p?.productId || p?.id;
        if (typeof id === 'string') _fetchedSkus.add(id);
      }
      return arr;
    }
  } catch (e) {
    // eslint-disable-next-line no-console
    console.warn('[IAP] fetchProducts failed', e);
  }
  return [];
}

const PURCHASE_TIMEOUT_MS = 180_000; // 3 minutes — Apple sheet stays open longer than fetch

export async function buyProduct(productId: string): Promise<IapBuyResult> {
  const iap = loadModule();
  if (!iap) {
    // CRITICAL: don't return success when the module isn't available — that
    // would let the caller silently grant the IAP without StoreKit. This was
    // the root cause of Apple Rejections #4–#6 ("no payment sheet triggered").
    throw new Error(
      'Apple In-App Purchase is unavailable on this device. Please ensure you are on iOS, signed in to the App Store, and try again.',
    );
  }

  const ok = await initIap();
  if (!ok) {
    throw new Error(
      'Apple In-App Purchase is unavailable. Check your network and sign in to the App Store, then try again.',
    );
  }

  // v15 contract: products MUST be in the StoreKit cache. Try to warm it
  // first, but if fetchProducts returns empty (which can happen in sandbox
  // while the IAP is still in WAITING_FOR_REVIEW), DO NOT short-circuit —
  // let requestPurchase be called. StoreKit will either show its sheet
  // (sandbox resolves the SKU on demand) or raise a real error through
  // purchaseErrorListener with the actual Apple message.
  if (!_fetchedSkus.has(productId)) {
    try {
      const products = await fetchProducts([productId]);
      if (products.length === 0) {
        // eslint-disable-next-line no-console
        console.warn(
          `[IAP] fetchProducts returned empty for ${productId} — proceeding to requestPurchase anyway. StoreKit may resolve the SKU on demand or raise a precise error.`,
        );
      }
    } catch (e) {
      // eslint-disable-next-line no-console
      console.warn('[IAP] fetchProducts threw, continuing:', e);
    }
  }

  return new Promise<IapBuyResult>((resolve, reject) => {
    let timer: any = null;
    const slot: PendingResolver = {
      productId,
      resolve: (r) => {
        if (timer) clearTimeout(timer);
        resolve(r);
      },
      reject: (e) => {
        if (timer) clearTimeout(timer);
        reject(e);
      },
    };
    _pending.push(slot);

    // v15.x requestPurchase signature — note the `apple` key (NOT `ios`!).
    //   await requestPurchase({
    //     request: { apple: { sku } },
    //     type: 'in-app',
    //   })
    // Returns Promise<Purchase | Purchase[] | null> but the result we trust
    // is the Purchase delivered via purchaseUpdatedListener.
    try {
      Promise.resolve(
        iap.requestPurchase({
          request: { apple: { sku: productId } },
          type: 'in-app',
        }),
      ).catch((e: any) => {
        const idx = _pending.indexOf(slot);
        if (idx >= 0) _pending.splice(idx, 1);
        if (timer) clearTimeout(timer);
        const msg =
          e?.message ||
          e?.debugMessage ||
          e?.code ||
          'Apple purchase failed';
        // eslint-disable-next-line no-console
        console.warn('[IAP] requestPurchase rejected:', e);
        reject(new Error(msg));
      });
    } catch (e: any) {
      const idx = _pending.indexOf(slot);
      if (idx >= 0) _pending.splice(idx, 1);
      // eslint-disable-next-line no-console
      console.warn('[IAP] requestPurchase threw synchronously:', e);
      reject(new Error(e?.message || 'Apple purchase failed'));
      return;
    }

    timer = setTimeout(() => {
      const idx = _pending.indexOf(slot);
      if (idx >= 0) {
        _pending.splice(idx, 1);
        reject(new Error('Purchase timed out — please try again.'));
      }
    }, PURCHASE_TIMEOUT_MS);
  });
}

/**
 * Tear down listeners and the connection. Optional — only useful in test
 * harnesses where we want a clean slate between scenarios.
 */
export async function shutdownIap(): Promise<void> {
  if (_purchaseSub) {
    try { _purchaseSub.remove(); } catch {}
    _purchaseSub = null;
  }
  if (_errorSub) {
    try { _errorSub.remove(); } catch {}
    _errorSub = null;
  }
  const iap = _iap;
  if (iap && typeof iap.endConnection === 'function') {
    try { await iap.endConnection(); } catch {}
  }
  _initialized = false;
  _connected = false;
  _fetchedSkus.clear();
}
