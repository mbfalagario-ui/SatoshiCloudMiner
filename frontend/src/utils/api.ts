import { storage } from '@/src/utils/storage';

// EXPO_PUBLIC_BACKEND_URL MUST be baked into every build (it is set in
// frontend/.env for dev/preview and in every eas.json profile for native
// builds). No hardcoded fallback: a wrong fallback URL caused Build #23 to
// 404 on iPad (Apple rejection round 4), and a hardcoded production URL
// breaks non-production deployments. Fail fast and loud instead.
const BASE = (process.env.EXPO_PUBLIC_BACKEND_URL || '').replace(/\/$/, '');
if (!BASE) {
  // eslint-disable-next-line no-console
  console.error(
    '[api] EXPO_PUBLIC_BACKEND_URL is not set — all API calls will fail. ' +
      'Set it in frontend/.env (dev) or the eas.json build profile (native).'
  );
}
const TOKEN_KEY = 'hc_access_token';

export async function saveToken(token: string) {
  await storage.secureSet(TOKEN_KEY, token);
}

export async function getToken(): Promise<string | null> {
  return await storage.secureGet<string>(TOKEN_KEY, '' as string);
}

export async function clearToken() {
  await storage.secureRemove(TOKEN_KEY);
}

import { Platform } from 'react-native';

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

export async function api(
  path: string,
  opts: RequestInit & { auth?: boolean } = {}
): Promise<any> {
  const { auth = true, headers, ...rest } = opts;
  const finalHeaders: Record<string, string> = {
    'Content-Type': 'application/json',
    // Backend uses this to enforce StoreKit on iOS clients (refuses
    // /packages/buy without an apple_transaction_id). DO NOT REMOVE.
    'X-Client-Platform': Platform.OS,
    ...(headers as Record<string, string> | undefined),
  };
  if (auth) {
    const token = await getToken();
    if (token) finalHeaders.Authorization = `Bearer ${token}`;
  }

  const url = `${BASE}/api${path}`;
  const res = await fetch(url, { ...rest, headers: finalHeaders });

  let data: any = null;
  const text = await res.text();
  try {
    data = text ? JSON.parse(text) : null;
  } catch {
    data = text;
  }

  if (!res.ok) {
    const msg =
      (data && (data.detail || data.message)) ||
      `Request failed (${res.status})`;
    throw new ApiError(res.status, typeof msg === 'string' ? msg : JSON.stringify(msg));
  }
  return data;
}
