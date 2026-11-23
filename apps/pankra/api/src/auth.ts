import { createHash, randomBytes } from 'node:crypto';
import type { FetchLike } from './providers/types.ts';
import type { Store } from './store.ts';

/**
 * Single-owner sign-in by email link (docs/spec.md, Security). The link signs in once and
 * expires after 15 minutes; a session lasts 30 days. Web keeps it in an HttpOnly cookie,
 * iPhone as a bearer token in the keychain. Only hashes of tokens are stored.
 */
export interface AuthConfig {
  ownerEmail: string;
  ownerId: string;
  /** Host secret RESEND_API_KEY: the email service that sends the links. */
  resendApiKey?: string;
  /** Sender, e.g. "PANKRA <login@yourdomain>" (a domain verified in Resend). */
  from: string;
}

export interface AuthToken {
  hash: string;
  kind: 'link' | 'session';
  userId: string;
  client: 'web' | 'ios';
  createdAt: string;
  expiresAt: string;
}

export const SESSION_COOKIE = 'pankra_session';
export const LINK_TTL_MS = 15 * 60_000;
export const SESSION_TTL_MS = 30 * 24 * 3_600_000;
const LINKS_PER_HOUR = 5;

export class AuthError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

const hash = (token: string) => createHash('sha256').update(token).digest('hex');
const newToken = () => randomBytes(32).toString('base64url');

/** Send a sign-in link to the owner. Any other address gets the same answer and no email. */
export async function requestLink(
  deps: { store: Store; config: AuthConfig; fetch: FetchLike; now: Date; webUrl?: string },
  email: string,
  client: 'web' | 'ios',
): Promise<void> {
  if (email.trim().toLowerCase() !== deps.config.ownerEmail.trim().toLowerCase()) return;
  const userId = deps.config.ownerId;
  const hourAgo = deps.now.getTime() - 3_600_000;
  const recent = deps.store.listAuthTokens(userId).filter((t) => t.kind === 'link' && Date.parse(t.createdAt) > hourAgo);
  if (recent.length >= LINKS_PER_HOUR) throw new AuthError(429, 'Too many sign-in links; try again in an hour');
  if (!deps.config.resendApiKey) throw new AuthError(503, 'Email sign-in is not configured (RESEND_API_KEY)');
  if (client === 'web' && !deps.webUrl) throw new AuthError(503, 'WEB_URL is not configured');

  const token = newToken();
  deps.store.saveAuthToken({
    hash: hash(token),
    kind: 'link',
    userId,
    client,
    createdAt: deps.now.toISOString(),
    expiresAt: new Date(deps.now.getTime() + LINK_TTL_MS).toISOString(),
  });
  const link = client === 'ios' ? `pankra://sign-in?token=${token}` : `${deps.webUrl}/sign-in?token=${token}`;
  let res: Response;
  try {
    res = await deps.fetch('https://api.resend.com/emails', {
      method: 'POST',
      headers: { 'content-type': 'application/json', authorization: `Bearer ${deps.config.resendApiKey}` },
      body: JSON.stringify({
        from: deps.config.from,
        to: [deps.config.ownerEmail],
        subject: 'Sign in to PANKRA',
        text: `Open this link to sign in to PANKRA. It works once, for 15 minutes:\n\n${link}\n\nIf you did not ask for it, ignore this email.`,
      }),
      signal: AbortSignal.timeout(15_000),
    });
  } catch (e) {
    throw new AuthError(502, `The email could not be sent: ${(e as Error).message}`);
  }
  if (!res.ok) throw new AuthError(502, `The email service refused the message (HTTP ${res.status})`);
}

/** Exchange a link token (once) for a session token. */
export function verifyLink(store: Store, token: string, now: Date): { token: string; userId: string; client: 'web' | 'ios'; expiresAt: string } {
  const link = store.getAuthToken(hash(token));
  if (link) store.deleteAuthToken(link.hash); // used or not, a link works only once
  if (!link || link.kind !== 'link' || Date.parse(link.expiresAt) <= now.getTime()) {
    throw new AuthError(401, 'This sign-in link has expired or was already used; ask for a new one');
  }
  const session = newToken();
  const expiresAt = new Date(now.getTime() + SESSION_TTL_MS).toISOString();
  store.saveAuthToken({ hash: hash(session), kind: 'session', userId: link.userId, client: link.client, createdAt: now.toISOString(), expiresAt });
  return { token: session, userId: link.userId, client: link.client, expiresAt };
}

/** The session token a request carries: a bearer token (iPhone) or the session cookie (web). */
export function sessionToken(headers: Record<string, unknown>): string | undefined {
  const auth = headers.authorization;
  if (typeof auth === 'string' && auth.startsWith('Bearer ')) return auth.slice(7).trim() || undefined;
  const cookie = headers.cookie;
  if (typeof cookie !== 'string') return undefined;
  for (const part of cookie.split(';')) {
    const [name, ...rest] = part.trim().split('=');
    if (name === SESSION_COOKIE) return decodeURIComponent(rest.join('='));
  }
  return undefined;
}

export function userForRequest(store: Store, headers: Record<string, unknown>, now: Date): string | undefined {
  const token = sessionToken(headers);
  if (!token) return undefined;
  const session = store.getAuthToken(hash(token));
  if (!session || session.kind !== 'session' || Date.parse(session.expiresAt) <= now.getTime()) return undefined;
  return session.userId;
}

export function signOut(store: Store, headers: Record<string, unknown>): void {
  const token = sessionToken(headers);
  if (token) store.deleteAuthToken(hash(token));
}
