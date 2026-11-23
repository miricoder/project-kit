import Constants from 'expo-constants';
import type { CredentialStatus, Profile, Provider, Retention, ScheduleChange, Section, Session } from '@pankra/shared';

const API_URL: string =
  (Constants.expoConfig?.extra as { apiUrl?: string } | undefined)?.apiUrl ??
  'http://localhost:3000/api/v1';

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, { credentials: 'include' });
  if (!res.ok) throw new Error(`${res.status}: ${await res.text()}`);
  return (await res.json()) as T;
}

async function post<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    method: 'POST',
    credentials: 'include',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const detail = (await res.json().catch(() => null)) as { error?: string } | null;
    throw new Error(detail?.error ?? `HTTP ${res.status}`);
  }
  return (await res.json()) as T;
}

async function send(method: 'PUT' | 'DELETE', path: string, body?: unknown): Promise<unknown> {
  const res = await fetch(`${API_URL}${path}`, {
    method,
    credentials: 'include',
    headers: body ? { 'content-type': 'application/json' } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) {
    const detail = (await res.json().catch(() => null)) as { error?: string } | null;
    throw new Error(detail?.error ?? `HTTP ${res.status}`);
  }
  return res.status === 204 ? null : res.json();
}

export interface NewClass {
  title: string;
  type: 'class';
  sections: Section[];
}

export const api = {
  sessions: (from: string, to: string) => get<Session[]>(`/sessions?from=${from}&to=${to}`),
  profile: () => get<Profile>('/profile'),
  credentials: () => get<CredentialStatus[]>('/credentials'),
  saveKey: (provider: Provider, secret: string, retention: Retention) =>
    send('PUT', `/credentials/${provider}`, { secret, retention }) as Promise<{ last4: string; expiresAt: string | null }>,
  deleteKey: (provider: Provider) => send('DELETE', `/credentials/${provider}`),
  insert: (date: string, session: NewClass) =>
    post<{ session: Session; changes: ScheduleChange[] }>('/sessions/insert', { date, session }),
};

/** Local calendar date as YYYY-MM-DD. */
export function today(): string {
  const d = new Date();
  const m = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  return `${d.getFullYear()}-${m}-${day}`;
}
