import React, { createContext, useContext, useEffect, useState, useCallback } from 'react';
import { api, saveToken, clearToken, getToken } from '@/src/utils/api';

export type UserPublic = {
  id: string;
  email: string;
  referral_code?: string;
  balance_btc: number;
  balance_usd: number;
  lifetime_btc: number;
  lifetime_usd: number;
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
    await clearToken();
    setUser(null);
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
