import Constants from 'expo-constants';
import type { Profile, ScheduleChange, Section, Session } from '@pankra/shared';

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

export interface NewClass {
  title: string;
  type: 'class';
  sections: Section[];
}

export const api = {
  sessions: (from: string, to: string) => get<Session[]>(`/sessions?from=${from}&to=${to}`),
  profile: () => get<Profile>('/profile'),
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
