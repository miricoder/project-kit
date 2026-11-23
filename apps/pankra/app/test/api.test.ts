import { describe, expect, it, vi } from 'vitest';
import { createApi } from '../src/lib/api';

function fakeFetch(responses: Record<string, { status: number; body?: unknown }>) {
  return vi.fn(async (url: string, init?: RequestInit) => {
    const key = `${init?.method ?? 'GET'} ${new URL(url).pathname}`;
    const r = responses[key] ?? { status: 404 };
    return new Response(r.body === undefined ? null : JSON.stringify(r.body), {
      status: r.status, headers: { 'content-type': 'application/json' } });
  });
}

describe('API client', () => {
  it('asks for a sign-in link at /api/v1/auth/link', async () => {
    const fetch = fakeFetch({ 'POST /api/v1/auth/link': { status: 202, body: { sent: true } } });
    const api = createApi({ baseUrl: 'https://api.example.com', fetch, platform: 'web' });
    await api.requestLink('owner@example.com');
    const [url, init] = fetch.mock.calls[0];
    expect(url).toBe('https://api.example.com/api/v1/auth/link');
    expect(JSON.parse(String(init!.body))).toEqual({ email: 'owner@example.com' });
  });

  it('signs the web app in with the session cookie (credentials included)', async () => {
    const me = { userId: 'u1', email: 'owner@example.com' };
    const fetch = fakeFetch({ 'POST /api/v1/auth/verify': { status: 200, body: me } });
    const api = createApi({ baseUrl: 'https://api.example.com', fetch, platform: 'web' });
    expect(await api.verify('t'.repeat(43))).toEqual(me);
    expect(fetch.mock.calls[0][1]!.credentials).toBe('include');
    expect(JSON.parse(String(fetch.mock.calls[0][1]!.body)).client).toBe('web');
  });

  it('keeps the iPhone bearer token and sends it on later calls', async () => {
    const store = new Map<string, string>();
    const fetch = fakeFetch({
      'POST /api/v1/auth/verify': { status: 200, body: { userId: 'u1', email: 'o@e.com', token: 'secret-token' } },
      'GET /api/v1/me': { status: 200, body: { userId: 'u1', email: 'o@e.com' } },
    });
    const api = createApi({ baseUrl: 'https://api.example.com', fetch, platform: 'ios',
      tokenStore: { get: async () => store.get('t') ?? null, set: async (v) => { store.set('t', v); },
        clear: async () => { store.delete('t'); } } });
    await api.verify('t'.repeat(43));
    expect(store.get('t')).toBe('secret-token');
    await api.me();
    const headers = new Headers(fetch.mock.calls[1][1]!.headers);
    expect(headers.get('authorization')).toBe('Bearer secret-token');
  });

  it('treats 401 from /me as signed out, not as an error', async () => {
    const fetch = fakeFetch({ 'GET /api/v1/me': { status: 401, body: { error: 'sign in required' } } });
    const api = createApi({ baseUrl: 'https://api.example.com', fetch, platform: 'web' });
    expect(await api.me()).toBeNull();
  });

  it('reports a refused link with the server message', async () => {
    const fetch = fakeFetch({ 'POST /api/v1/auth/verify': { status: 401, body: { error: 'link is invalid or expired' } } });
    const api = createApi({ baseUrl: 'https://api.example.com', fetch, platform: 'web' });
    await expect(api.verify('t'.repeat(43))).rejects.toThrow('link is invalid or expired');
  });
});
