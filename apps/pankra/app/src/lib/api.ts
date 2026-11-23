import type { Health, Me } from '@pankra/shared';

export interface TokenStore {
  get(): Promise<string | null>;
  set(token: string): Promise<void>;
  clear(): Promise<void>;
}

export interface ApiOptions {
  baseUrl: string;
  platform: 'web' | 'ios' | 'android';
  fetch?: (url: string, init?: RequestInit) => Promise<Response>;
  /** iPhone keeps a bearer token; the web app relies on the HttpOnly cookie. */
  tokenStore?: TokenStore;
}

export class ApiError extends Error {
  constructor(public status: number, message: string) { super(message); }
}

export function createApi(opts: ApiOptions) {
  const doFetch = opts.fetch ?? ((url, init) => fetch(url, init));
  const base = opts.baseUrl.replace(/\/$/, '') + '/api/v1';
  const client = opts.platform === 'web' ? 'web' : 'ios';

  async function call<T>(method: string, path: string, body?: unknown): Promise<T> {
    const headers = new Headers({ accept: 'application/json' });
    if (body !== undefined) headers.set('content-type', 'application/json');
    const token = client === 'ios' ? await opts.tokenStore?.get() : null;
    if (token) headers.set('authorization', `Bearer ${token}`);
    const res = await doFetch(`${base}${path}`, {
      method, headers, credentials: 'include',
      body: body === undefined ? undefined : JSON.stringify(body),
    });
    const text = await res.text();
    const data = text ? JSON.parse(text) : undefined;
    if (!res.ok) throw new ApiError(res.status, data?.error ?? `request failed (${res.status})`);
    return data as T;
  }

  return {
    health: () => call<Health>('GET', '/health'),
    requestLink: (email: string) => call<{ sent: boolean }>('POST', '/auth/link', { email }),
    async verify(token: string): Promise<Me> {
      const res = await call<Me & { token?: string }>('POST', '/auth/verify', { token, client });
      if (res.token) await opts.tokenStore?.set(res.token);
      return { userId: res.userId, email: res.email };
    },
    async me(): Promise<Me | null> {
      try { return await call<Me>('GET', '/me'); }
      catch (e) { if (e instanceof ApiError && e.status === 401) return null; throw e; }
    },
    async signOut() {
      await call<void>('POST', '/auth/logout').catch(() => undefined);
      await opts.tokenStore?.clear();
    },
  };
}

export type Api = ReturnType<typeof createApi>;
