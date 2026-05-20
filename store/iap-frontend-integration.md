# Apple StoreKit IAP wiring (client side)

The backend now accepts `apple_transaction_id` in `POST /api/packages/buy`
and validates it via Apple's App Store Server API.

For the App Store build you'll need to:

1. Add `expo-in-app-purchases` to `package.json` (or the `expo-iap` community
   plugin — both work with Expo's managed workflow if you use a development
   build).

   ```bash
   cd /app/frontend && yarn expo install expo-in-app-purchases
   ```

2. In the Shop screen (`app/(tabs)/shop.tsx`), replace the existing `buy()`
   handler with one that actually calls StoreKit and forwards the resulting
   transactionId to the backend. Skeleton:

   ```ts
   import * as InAppPurchases from 'expo-in-app-purchases';

   // On mount (or in app root)
   await InAppPurchases.connectAsync();
   await InAppPurchases.getProductsAsync(SHOP_PACKAGE_IDS);

   InAppPurchases.setPurchaseListener(async ({ responseCode, results }) => {
     if (responseCode !== InAppPurchases.IAPResponseCode.OK || !results) return;
     for (const purchase of results) {
       if (!purchase.acknowledged) {
         // Ship the transactionId to the backend for server-side verification
         await api('/packages/buy', {
           method: 'POST',
           body: JSON.stringify({
             package_id: purchase.productId,
             apple_transaction_id: purchase.transactionId,
           }),
         });
         await InAppPurchases.finishTransactionAsync(purchase, false);
       }
     }
   });

   // Triggered by the user pressing "Buy"
   await InAppPurchases.purchaseItemAsync(pkg.id);
   ```

3. The backend already:
   - Verifies the transactionId against Apple (`integrations/apple.py`).
   - Refuses duplicate `apple_transaction_id` redemptions.
   - Stores the Apple `environment` (Sandbox/Production/MOCK) on the
     transaction record.

4. Until the IAP product IDs are live in App Store Connect and you've built
   with a real bundle id signed by your team (`UHF3KNM9F9`), purchases run
   against StoreKit Sandbox automatically when the build is from Xcode/EAS
   in development/internal-testing mode.
