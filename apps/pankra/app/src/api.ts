import Constants from 'expo-constants';
import { Platform } from 'react-native';
import type {
  Activity,
  CredentialStatus,
  Race,
  RaceAnalysis,
  RaceDraft,
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

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, { credentials: 'include' });
  if (!res.ok) throw new Error(`${res.status}: ${await res.text()}`);
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
  const res = await fetch(`${API_URL}${path}`, {
    method: 'POST',
    credentials: 'include',
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
};

/**
 * Send a picked image; screenshot-reader reads it on `provider` and the upload comes back
 * with values to confirm. A refusal (e.g. no key) still carries the stored upload.
 */
async function uploadScreenshot(
  image: { uri: string; mimeType?: string | null; fileName?: string | null },
  kind: UploadKind,
  provider: Provider,
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
  const res = await fetch(`${API_URL}/uploads?kind=${kind}&provider=${provider}`, {
    method: 'POST',
    credentials: 'include',
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
