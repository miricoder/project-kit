import { randomUUID } from 'node:crypto';
import type { Activity } from '@pankra/shared';
import type { FetchLike } from './providers/types.ts';
import type { Store } from './store.ts';
import type { Vault } from './vault.ts';

/** Host secrets STRAVA_CLIENT_ID, STRAVA_CLIENT_SECRET; the webhook subscription's id and verify token. */
export interface StravaConfig {
  clientId: string;
  clientSecret: string;
  subscriptionId?: number;
  verifyToken?: string;
}

interface Tokens {
  accessToken: string;
  refreshToken: string;
  /** Unix seconds. */
  expiresAt: number;
  athleteId: number;
}

const API = 'https://www.strava.com/api/v3';
const TOKEN_URL = 'https://www.strava.com/oauth/token';
const TIMEOUT_MS = 15_000;

export class StravaError extends Error {}

export function authorizeUrl(config: StravaConfig, redirectUri: string, state: string): string {
  const u = new URL('https://www.strava.com/oauth/authorize');
  u.searchParams.set('client_id', config.clientId);
  u.searchParams.set('response_type', 'code');
  u.searchParams.set('redirect_uri', redirectUri);
  u.searchParams.set('approval_prompt', 'auto');
  u.searchParams.set('scope', 'read,activity:read_all');
  u.searchParams.set('state', state);
  return u.toString();
}

async function tokenRequest(fetchImpl: FetchLike, body: Record<string, string>): Promise<Tokens & { athleteId: number }> {
  let res: Response;
  try {
    res = await fetchImpl(TOKEN_URL, {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify(body),
      signal: AbortSignal.timeout(TIMEOUT_MS),
    });
  } catch (e) {
    throw new StravaError(`Strava could not be reached: ${(e as Error).message}`);
  }
  const json = (await res.json().catch(() => null)) as any;
  if (!res.ok || !json?.access_token) throw new StravaError(`Strava refused the token request (HTTP ${res.status})`);
  return {
    accessToken: json.access_token,
    refreshToken: json.refresh_token,
    expiresAt: Number(json.expires_at),
    athleteId: Number(json.athlete?.id ?? 0),
  };
}

function saveTokens(store: Store, vault: Vault, userId: string, tokens: Tokens, now: Date) {
  const credential = vault.seal(userId, 'strava', JSON.stringify(tokens), 'forever', now);
  store.saveCredential({ ...credential, last4: String(tokens.athleteId).slice(-4) });
}

/** OAuth callback: exchange the code, keep the tokens in the vault, link the athlete. */
export async function connect(
  deps: { store: Store; vault: Vault; fetch: FetchLike; config: StravaConfig; now: Date },
  userId: string,
  code: string,
): Promise<number> {
  const tokens = await tokenRequest(deps.fetch, {
    client_id: deps.config.clientId,
    client_secret: deps.config.clientSecret,
    code,
    grant_type: 'authorization_code',
  });
  if (!tokens.athleteId) throw new StravaError('Strava did not say which athlete connected');
  saveTokens(deps.store, deps.vault, userId, tokens, deps.now);
  deps.store.linkStravaAthlete(userId, tokens.athleteId);
  deps.store.addAudit({ userId, action: 'keyAdded', at: deps.now.toISOString(), detail: { provider: 'strava', athleteId: tokens.athleteId } });
  return tokens.athleteId;
}

/** A usable access token, refreshed when it expires within a minute. */
async function accessToken(deps: { store: Store; vault: Vault; fetch: FetchLike; config: StravaConfig; now: Date }, userId: string) {
  const credential = deps.store.getCredential(userId, 'strava');
  if (!credential) throw new StravaError('Strava is not connected');
  let tokens = JSON.parse(deps.vault.open(credential)) as Tokens;
  if (tokens.expiresAt - 60 <= deps.now.getTime() / 1000) {
    const fresh = await tokenRequest(deps.fetch, {
      client_id: deps.config.clientId,
      client_secret: deps.config.clientSecret,
      refresh_token: tokens.refreshToken,
      grant_type: 'refresh_token',
    });
    tokens = { ...fresh, athleteId: tokens.athleteId };
    saveTokens(deps.store, deps.vault, userId, tokens, deps.now);
  }
  return tokens.accessToken;
}

/** Fetch one activity and store it; importing the same id again leaves exactly one. */
export async function importActivity(
  deps: { store: Store; vault: Vault; fetch: FetchLike; config: StravaConfig; now: Date },
  userId: string,
  activityId: number,
): Promise<Activity> {
  const token = await accessToken(deps, userId);
  let res: Response;
  try {
    res = await deps.fetch(`${API}/activities/${activityId}`, {
      headers: { authorization: `Bearer ${token}` },
      signal: AbortSignal.timeout(TIMEOUT_MS),
    });
  } catch (e) {
    throw new StravaError(`Strava could not be reached: ${(e as Error).message}`);
  }
  if (!res.ok) throw new StravaError(`Strava returned HTTP ${res.status} for activity ${activityId}`);
  const a = (await res.json()) as any;
  return deps.store.upsertActivity({
    id: randomUUID(),
    userId,
    source: 'strava',
    externalId: String(a.id ?? activityId),
    name: String(a.name ?? ''),
    sport: String(a.sport_type ?? a.type ?? ''),
    startDate: String(a.start_date ?? ''),
    distanceM: Number(a.distance ?? 0),
    movingTimeS: Number(a.moving_time ?? 0),
    averageSpeedMs: Number(a.average_speed ?? 0),
    importedAt: deps.now.toISOString(),
  });
}
