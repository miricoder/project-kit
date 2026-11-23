import Constants from 'expo-constants';
import * as SecureStore from 'expo-secure-store';
import { Platform } from 'react-native';
import type {
  Activity,
  CredentialStatus,
  Race,
  RaceAnalysis,
  RaceDraft,
  PostTheme,
  Upload,
  UploadKind,
  Edge,
  NodeSummary,
  RegistryNode,
  RegistryStatus,
  SyncReport,
  Profile,
  Provider,
  Result,
  ResultPart,
  Retention,
  Run,
  ScheduleChange,
  Section,
  Session,
} from '@pankra/shared';

const API_URL: string =
  (Constants.expoConfig?.extra as { apiUrl?: string } | undefined)?.apiUrl ??
  'http://localhost:3000/api/v1';

/**
 * The session: an HttpOnly cookie on the web (the browser keeps it), a bearer token in the
 * iPhone's keychain.
 */
const TOKEN_KEY = 'pankra.session';
let tokenCache: string | null | undefined;

async function sessionToken(): Promise<string | null> {
  if (Platform.OS === 'web') return null;
  if (tokenCache === undefined) tokenCache = await SecureStore.getItemAsync(TOKEN_KEY);
  return tokenCache;
}

async function setSessionToken(token: string | null): Promise<void> {
  if (Platform.OS === 'web') return;
  tokenCache = token;
  if (token) await SecureStore.setItemAsync(TOKEN_KEY, token);
  else await SecureStore.deleteItemAsync(TOKEN_KEY);
}

async function request(path: string, init: RequestInit = {}): Promise<Response> {
  const token = await sessionToken();
  const headers = new Headers(init.headers);
  if (token) headers.set('authorization', `Bearer ${token}`);
  return fetch(`${API_URL}${path}`, { ...init, headers, credentials: 'include' });
}

async function get<T>(path: string): Promise<T> {
  const res = await request(path);
  if (!res.ok) {
    const detail = (await res.json().catch(() => null)) as { error?: string } | null;
    throw new ApiError(res.status, detail?.error ?? `HTTP ${res.status}`);
  }
  return (await res.json()) as T;
}

/** An API refusal, with the server's explanation (and what it needs, for runs). */
export class ApiError extends Error {
  status: number;
  needs?: { credential: Provider };

  constructor(status: number, message: string, needs?: { credential: Provider }) {
    super(message);
    this.status = status;
    this.needs = needs;
  }
}

async function post<T>(path: string, body: unknown): Promise<T> {
  const res = await request(path, {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const detail = (await res.json().catch(() => null)) as { error?: string; needs?: { credential: Provider } } | null;
    throw new ApiError(res.status, detail?.error ?? `HTTP ${res.status}`, detail?.needs);
  }
  return (await res.json()) as T;
}

async function send(method: 'PUT' | 'DELETE', path: string, body?: unknown): Promise<unknown> {
  const res = await request(path, {
    method,
    headers: body ? { 'content-type': 'application/json' } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) {
    const detail = (await res.json().catch(() => null)) as { error?: string } | null;
    throw new ApiError(res.status, detail?.error ?? `HTTP ${res.status}`);
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
  run: (node: Pick<NodeSummary, 'kind' | 'name'>, provider: Provider, input: Record<string, unknown>) =>
    post<Run>('/runs', { node: { kind: node.kind, name: node.name }, provider, input }),
  caps: () => get<Array<{ provider: Provider; monthlyUsd: number | null; spentUsd: number }>>('/caps'),
  setCap: (provider: Provider, monthlyUsd: number) => send('PUT', `/caps/${provider}`, { monthlyUsd }),
  insert: (date: string, session: NewClass) =>
    post<{ session: Session; changes: ScheduleChange[] }>('/sessions/insert', { date, session }),
  logResult: (sessionId: string, parts: ResultPart[], notes?: string) =>
    post<Result>('/results', { sessionId, parts, notes }),
  result: (id: string) => get<Result>(`/results/${id}`),
  nodes: () => get<GraphNode[]>('/nodes'),
  edges: () => get<Edge[]>('/edges'),
  registryStatus: () => get<RegistryStatus>('/registry/status'),
  syncRegistry: () => post<SyncReport>('/registry/sync', {}),
  uploadScreenshot,
  confirmRace: (uploadId: string, data: RaceDraft) => post<Upload>(`/uploads/${uploadId}/confirm`, { data }),
  races: () => get<Race[]>('/races'),
  raceAnalysis: (id: string, targetS?: number) =>
    get<RaceAnalysis>(`/races/${id}/analysis${targetS ? `?targetS=${targetS}` : ''}`),
  activities: () => get<Activity[]>('/activities'),
  stravaConnectUrl: () => get<{ url: string }>('/strava/connect'),
  results: (from: string, to: string) => get<Result[]>(`/results?from=${from}&to=${to}`),
  me: () => get<{ userId: string }>('/auth/me'),
  requestSignInLink: (email: string) =>
    post<{ sent: boolean; message: string }>('/auth/magic-link', { email, client: Platform.OS === 'web' ? 'web' : 'ios' }),
  verifySignIn: async (token: string) => {
    const session = await post<{ token?: string; expiresAt: string }>('/auth/verify', { token });
    if (session.token) await setSessionToken(session.token);
  },
  signOut: async () => {
    await request('/auth/sign-out', { method: 'POST' }).catch(() => undefined);
    await setSessionToken(null);
  },
  /** The day's workout as a 1080 x 1350 PNG. */
  postUrl: (sessionId: string, theme: PostTheme) =>
    `${API_URL}/sessions/${encodeURIComponent(sessionId)}/post.png?theme=${theme}`,
};

/**
 * Send a picked image; screenshot-reader reads it on `provider` and the upload comes back
 * with values to confirm. A refusal (e.g. no key) still carries the stored upload.
 */
async function uploadScreenshot(
  image: { uri: string; mimeType?: string | null; fileName?: string | null },
  kind: UploadKind,
  /** Read it with screenshot-reader on this provider; omit to only store it. */
  provider?: Provider,
): Promise<Upload> {
  const form = new FormData();
  const mime = image.mimeType ?? 'image/jpeg';
  const name = image.fileName ?? `screenshot.${mime.split('/')[1] ?? 'jpg'}`;
  if (Platform.OS === 'web') {
    form.append('image', await (await fetch(image.uri)).blob(), name);
  } else {
    // React Native's FormData takes a file reference instead of a Blob.
    form.append('image', { uri: image.uri, name, type: mime } as unknown as Blob);
  }
  const res = await request(`/uploads?kind=${kind}${provider ? `&provider=${provider}` : ''}`, {
    method: 'POST',
    body: form,
  });
  const body = (await res.json().catch(() => null)) as (Upload & { error?: string; needs?: { credential: Provider } }) | null;
  if (!res.ok) throw new ApiError(res.status, body?.error ?? `HTTP ${res.status}`, body?.needs);
  return body as Upload;
}

/** A node as GET /nodes serves it. */
export type GraphNode = NodeSummary & Pick<RegistryNode, 'vision' | 'tools' | 'input' | 'steps' | 'skills' | 'agents'>;

/** Local calendar date as YYYY-MM-DD. */
export function today(): string {
  const d = new Date();
  const m = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  return `${d.getFullYear()}-${m}-${day}`;
}
