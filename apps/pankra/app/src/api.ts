import Constants from 'expo-constants';
import type { Profile, Session } from '@pankra/shared';

const API_URL: string =
  (Constants.expoConfig?.extra as { apiUrl?: string } | undefined)?.apiUrl ??
  'http://localhost:3000/api/v1';

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, { credentials: 'include' });
  if (!res.ok) throw new Error(`${res.status}: ${await res.text()}`);
  return (await res.json()) as T;
}

export const api = {
  sessions: (from: string, to: string) => get<Session[]>(`/sessions?from=${from}&to=${to}`),
  profile: () => get<Profile>('/profile'),
};

/** Local calendar date as YYYY-MM-DD. */
export function today(): string {
  const d = new Date();
  const m = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  return `${d.getFullYear()}-${m}-${day}`;
}
