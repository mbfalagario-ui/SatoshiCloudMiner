import { storage } from '@/src/utils/storage';

const BASE = process.env.EXPO_PUBLIC_BACKEND_URL || '';
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
