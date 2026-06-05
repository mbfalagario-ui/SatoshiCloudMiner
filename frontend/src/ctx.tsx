import React, { createContext, useContext, useEffect, useState, useCallback } from 'react';
import { router } from 'expo-router';
import { api, saveToken, clearToken, getToken } from '@/src/utils/api';

export type UserPublic = {
  id: string;
  email: string;
  referral_code?: string;
  created_at?: string;
  balance_btc: number;
  balance_usd: number;
  balance_sats?: number;
  lifetime_btc: number;
  lifetime_usd: number;
  lifetime_sats?: number;
  is_admin?: boolean;
  is_banned?: boolean;
  ad_free?: boolean;
  auto_checkin?: boolean;
  auto_reinvest?: boolean;
  auto_reinvest_min_balance_usd?: number;
};

type Ctx = {
  user: UserPublic | null;
  loading: boolean;
  signIn: (email: string, password: string) => Promise<void>;
  signUp: (email: string, password: string, referral?: string) => Promise<void>;
  signOut: () => Promise<void>;
  refresh: () => Promise<void>;
};

const SessionContext = createContext<Ctx | undefined>(undefined);

export function SessionProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<UserPublic | null>(null);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    try {
      const me = await api('/auth/me');
      setUser(me);
    } catch (e) {
      setUser(null);
    }
  }, []);

  useEffect(() => {
    (async () => {
      try {
        const token = await getToken();
        if (token) {
          await refresh();
        }
      } finally {
        setLoading(false);
      }
    })();
  }, [refresh]);

  const signIn = async (email: string, password: string) => {
    const r = await api('/auth/login', {
      method: 'POST',
      auth: false,
      body: JSON.stringify({ email, password }),
    });
    await saveToken(r.access_token);
    setUser(r.user);
  };

  const signUp = async (email: string, password: string, referral_code?: string) => {
    const r = await api('/auth/register', {
      method: 'POST',
      auth: false,
      body: JSON.stringify({ email, password, referral_code }),
    });
    await saveToken(r.access_token);
    setUser(r.user);
  };

  const signOut = async () => {
    // CRITICAL — Build #13 logout flow.
    //
    // Build #11 crashed natively on iOS because <Redirect> was rendered while
    // tabs/admin UIViewControllers were still committing.
    //
    // Build #12 fixed the crash by deferring `setUser(null)` AND moving the
    // redirect into a layout-side useEffect — but on TestFlight the user
    // reported a black screen that never redirected. The layout's useEffect
    // does fire, but inside an about-to-unmount layout the queued
    // `router.replace` call from `setTimeout(0)` was getting cancelled when
    // expo-router cleaned up the (tabs) navigator.
    //
    // The robust fix is to navigate IMMEDIATELY from here, BEFORE clearing
    // any session state. expo-router exposes a top-level `router` singleton
    // that does not depend on the layout being mounted. We jump to /sign-in
    // first so the auth screen tree mounts, THEN we tear down the user
    // session in the background. (tabs)/_layout never sees user=null because
    // by the time setUser(null) commits, the (tabs) tree has already been
    // popped by the navigation.
    try {
      router.replace('/sign-in');
    } catch {
      // imperative router can throw if called pre-mount — safe to ignore.
    }

    // Tear down react-native-iap listeners so they don't fire callbacks into
    // an unmounted shop screen after we navigate away.
    try {
      const iapMod = await import('@/src/utils/iap');
      if (typeof iapMod.shutdownIap === 'function') {
        await iapMod.shutdownIap();
      }
    } catch {
      // iap module may not be loaded on every platform
    }

    // Build #30: tear down AdMob managers too. Pre-existing bug since
    // Build #25 — without this, the rewarded/interstitial event
    // listeners stay alive after sign-out and crash the app when they
    // try to fire setState into the unmounted AdProvider after the
    // user lands on /sign-in. Verified against the 6 sign-out crash
    // reports from May 26 and June 5.
    try {
      const adsMod = await import('@/src/utils/ads');
      if (typeof adsMod.shutdownAds === 'function') {
        adsMod.shutdownAds();
      }
    } catch {
      // ads module may not be loaded on every platform
    }

    // Clear the SecureStore token. From this point any /api/* call will 401.
    try {
      await clearToken();
    } catch {
      // SecureStore can throw if the key was already removed.
    }

    // Now that the auth screen is on top of the navigation stack, it's safe
    // to clear the user state. A tiny defer keeps it off the same tick as
    // the imperative router.replace so React Native iOS schedules them as
    // separate commits.
    setTimeout(() => {
      setUser(null);
    }, 16);
  };

  return (
    <SessionContext.Provider value={{ user, loading, signIn, signUp, signOut, refresh }}>
      {children}
    </SessionContext.Provider>
  );
}

export function useSession() {
  const c = useContext(SessionContext);
  if (!c) throw new Error('useSession must be inside SessionProvider');
  return c;
}
