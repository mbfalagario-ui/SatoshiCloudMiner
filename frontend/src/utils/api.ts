import { storage } from '@/src/utils/storage';

// Fallback if EXPO_PUBLIC_BACKEND_URL isn't baked into the build.
// IMPORTANT: This MUST be a production-grade URL. Previous use of the
// `preview.emergentagent.com` URL caused Build #23 to 404 on iPad
// (Apple rejection round 4). The Fly.io production backend is always-on
// and serves both legal/support and the API.
const FALLBACK_BACKEND = 'https://api.hashratecloudminer.com';
const BASE = (process.env.EXPO_PUBLIC_BACKEND_URL || FALLBACK_BACKEND).replace(/\/$/, '');
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
