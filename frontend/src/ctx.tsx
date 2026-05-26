import React, { createContext, useContext, useEffect, useState, useCallback } from 'react';
import { InteractionManager } from 'react-native';
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
    // CRITICAL — iOS native crash mitigation (Build #11 TestFlight regression):
    //
    // The previous "clear token → setUser(null) → <Redirect> during render"
    // pattern triggered a native crash on TestFlight because:
    //   1. clearToken() is an async native call (expo-secure-store).
    //   2. When setUser(null) commits, the (tabs) layout re-renders and
    //      synchronously returns <Redirect href="/" />.
    //   3. <Redirect> from expo-router internally calls router.replace
    //      during render — while the Profile screen + AdInterstitial Modal
    //      + Tabs UIViewControllers are still resolving their own commit.
    //   4. iOS UINavigationController gets a stack mutation mid-commit and
    //      hits an internal assertion → CRASH.
    //
    // Fix: tear down listeners first, defer state clear so the navigation
    // transition starts BEFORE the React tree unmounts. The (tabs)/_layout
    // now uses a useEffect-driven redirect (not <Redirect>), and we wait
    // one frame using InteractionManager so animations finish.
    try {
      const iapMod = await import('@/src/utils/iap');
      if (typeof iapMod.shutdownIap === 'function') {
        await iapMod.shutdownIap();
      }
    } catch {
      // non-fatal — iap module may not be loaded on every platform
    }

    // Clear the stored token first so no further API calls succeed.
    try {
      await clearToken();
    } catch {
      // SecureStore can throw if the key was already removed.
    }

    // Defer the state clear to the next frame so any in-flight animations
    // (button press feedback, alert dismiss) can complete first.
    await new Promise<void>((resolve) => {
      InteractionManager.runAfterInteractions(() => {
        setUser(null);
        resolve();
      });
    });
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
