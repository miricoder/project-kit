import { createHash, randomBytes } from 'node:crypto';

/** 256-bit random token, URL-safe. Only its hash is ever stored. */
export function newToken(): string { return randomBytes(32).toString('base64url'); }

export function hashToken(token: string): string {
  return createHash('sha256').update(token).digest('hex');
}
