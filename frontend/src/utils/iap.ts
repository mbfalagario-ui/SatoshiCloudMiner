/**
 * In-App Purchase wrapper around `react-native-iap` v15+.
 *
 * The v15 API is event-driven: `requestPurchase()` returns void; the actual
 * Purchase object is delivered through a `purchaseUpdatedListener` and
 * errors through `purchaseErrorListener`. This wrapper hides that and
 * exposes a promise-style `buyProduct()` matching how the rest of the app
 * already uses it.
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
let _iap: any = null;
let _purchaseSub: { remove: () => void } | null = null;
let _errorSub: { remove: () => void } | null = null;

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
  } catch {
    _iap = null;
    return null;
  }
}

export function isIapAvailable(): boolean {
  return Platform.OS === 'ios' && loadModule() !== null;
}

function _ensureListeners(iap: any) {
  if (_purchaseSub || _errorSub) return;
  if (typeof iap.purchaseUpdatedListener === 'function') {
    _purchaseSub = iap.purchaseUpdatedListener(async (purchase: any) => {
      const productId =
        purchase?.productId || purchase?.id || purchase?.product?.id;
      const tx =
        purchase?.transactionId ||
        purchase?.transactionIdentifier ||
        purchase?.id ||
        purchase?.originalTransactionIdentifierIOS ||
        purchase?.originalTransactionIdentifier;

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
      } catch {
        /* non-fatal */
      }
    });
  }
  if (typeof iap.purchaseErrorListener === 'function') {
    _errorSub = iap.purchaseErrorListener((err: any) => {
      const productId = err?.productId;
      const msg =
        err?.message || err?.code || 'Apple purchase failed';
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
  if (_initialized) return true;
  try {
    if (typeof iap.initConnection === 'function') {
      await iap.initConnection();
    } else if (typeof iap.IAP?.initConnection === 'function') {
      await iap.IAP.initConnection();
    }
    _ensureListeners(iap);
    _initialized = true;
    return true;
  } catch (e) {
    // eslint-disable-next-line no-console
    console.warn('[IAP] initConnection failed', e);
    return false;
  }
}

export async function fetchProducts(productIds: string[]): Promise<any[]> {
  if (!productIds.length) return [];
  const iap = loadModule();
  if (!iap) return [];
  await initIap();
  try {
    if (typeof iap.fetchProducts === 'function') {
      const r = await iap.fetchProducts({ skus: productIds, type: 'in-app' });
      return Array.isArray(r) ? r : r?.products || [];
    }
    if (typeof iap.requestProducts === 'function') {
      const r = await iap.requestProducts({ skus: productIds, type: 'in-app' });
      return Array.isArray(r) ? r : [];
    }
    if (typeof iap.getProducts === 'function') {
      return (await iap.getProducts({ skus: productIds })) || [];
    }
  } catch (e) {
    // eslint-disable-next-line no-console
    console.warn('[IAP] fetchProducts failed', e);
  }
  return [];
}

const PURCHASE_TIMEOUT_MS = 120_000; // 2 minutes — Apple sheet stays open longer than fetch

export async function buyProduct(productId: string): Promise<IapBuyResult> {
  const iap = loadModule();
  if (!iap) return { applePurchase: false, productId };
  await initIap();

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

    // The v15+ requestPurchase shape:
    //   requestPurchase({ request: { ios: { sku } }, type: 'in-app' })
    // Returns Promise<void> — the actual Purchase comes via the
    // purchaseUpdatedListener that we wired up in _ensureListeners().
    try {
      Promise.resolve(
        iap.requestPurchase({
          request: { ios: { sku: productId } },
          type: 'in-app',
        }),
      ).catch((e: any) => {
        // The async call itself may reject for parameter / connection errors.
        const idx = _pending.indexOf(slot);
        if (idx >= 0) _pending.splice(idx, 1);
        if (timer) clearTimeout(timer);
        reject(new Error(e?.message || 'Apple purchase failed'));
      });
    } catch (e: any) {
      const idx = _pending.indexOf(slot);
      if (idx >= 0) _pending.splice(idx, 1);
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
