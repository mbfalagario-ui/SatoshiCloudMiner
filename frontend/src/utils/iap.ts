/**
 * In-App Purchase wrapper around `react-native-iap`.
 *
 * Behaviour:
 *  - On iOS in a custom dev/TestFlight/App Store build → uses StoreKit to
 *    present Apple's native purchase sheet, then forwards the resulting
 *    `transactionId` to the backend for server-side receipt validation.
 *  - On every other surface (Expo Go, Web preview, Android, etc.) → falls
 *    back to a "dev-mode" purchase that just hits the backend directly so
 *    the rest of the flow remains testable. This is the same behaviour the
 *    backend already supports when no Apple transaction id is supplied.
 *
 * The native module is lazily required so a missing build does not crash
 * the JS bundle in Expo Go.
 */
import { Platform } from 'react-native';

export type IapBuyResult = {
  applePurchase: boolean;
  transactionId?: string;
  productId: string;
};

let _initialized = false;
let _iap: any = null;

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
    if (typeof iap.requestProducts === 'function') {
      const r = await iap.requestProducts({ skus: productIds, type: 'inapp' });
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

export async function buyProduct(productId: string): Promise<IapBuyResult> {
  const iap = loadModule();
  if (!iap) return { applePurchase: false, productId };
  await initIap();

  try {
    // react-native-iap v15+ exposes `requestPurchase` returning the purchase.
    let purchase: any | null = null;
    if (typeof iap.requestPurchase === 'function') {
      purchase = await iap.requestPurchase({ sku: productId, ios: { sku: productId } });
    } else if (typeof iap.purchaseProduct === 'function') {
      purchase = await iap.purchaseProduct(productId);
    }

    const tx =
      purchase?.transactionId ||
      purchase?.transactionIdentifier ||
      purchase?.id ||
      purchase?.originalTransactionIdentifierIOS ||
      purchase?.originalTransactionIdentifier;

    // Finish the transaction so StoreKit doesn't keep redelivering it.
    try {
      if (purchase && typeof iap.finishTransaction === 'function') {
        await iap.finishTransaction({ purchase, isConsumable: true });
      }
    } catch {
      /* non-fatal */
    }

    return {
      applePurchase: Boolean(tx),
      transactionId: tx,
      productId,
    };
  } catch (e: any) {
    // User cancelled or sandbox error — rethrow so caller can show a message.
    throw new Error(e?.message || 'Apple purchase failed');
  }
}
