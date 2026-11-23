import { createCipheriv, createDecipheriv, randomBytes } from 'node:crypto';
import type { Credential, CredentialProvider, Retention } from '@pankra/shared';
import type { Store } from './store.ts';

const HOUR = 3_600_000;
const RETENTION_MS: Record<Retention, number | null> = {
  session: 12 * HOUR,
  '24h': 24 * HOUR,
  '7d': 7 * 24 * HOUR,
  '30d': 30 * 24 * HOUR,
  forever: null,
};

export function expiryFor(retention: Retention, now: Date): string | null {
  const ms = RETENTION_MS[retention];
  return ms === null ? null : new Date(now.getTime() + ms).toISOString();
}

/** AES-256-GCM with a fresh 96-bit IV per secret; the master key lives only in host secrets. */
export class Vault {
  private key: Buffer;

  constructor(masterKeyBase64: string) {
    const key = Buffer.from(masterKeyBase64, 'base64');
    if (key.length !== 32) throw new Error('VAULT_KEY must be 32 bytes, base64-encoded');
    this.key = key;
  }

  seal(
    userId: string,
    provider: CredentialProvider,
    secret: string,
    retention: Retention,
    now: Date,
  ): Credential {
    const iv = randomBytes(12);
    const cipher = createCipheriv('aes-256-gcm', this.key, iv);
    cipher.setAAD(Buffer.from(`${userId}:${provider}`));
    const ciphertext = Buffer.concat([cipher.update(secret, 'utf8'), cipher.final()]);
    return {
      userId,
      provider,
      ciphertext: ciphertext.toString('base64'),
      iv: iv.toString('base64'),
      authTag: cipher.getAuthTag().toString('base64'),
      last4: secret.slice(-4),
      retention,
      expiresAt: expiryFor(retention, now),
      createdAt: now.toISOString(),
    };
  }

  open(credential: Credential): string {
    const decipher = createDecipheriv('aes-256-gcm', this.key, Buffer.from(credential.iv, 'base64'));
    decipher.setAAD(Buffer.from(`${credential.userId}:${credential.provider}`));
    decipher.setAuthTag(Buffer.from(credential.authTag, 'base64'));
    return Buffer.concat([
      decipher.update(Buffer.from(credential.ciphertext, 'base64')),
      decipher.final(),
    ]).toString('utf8');
  }
}

/** A credential past its retention is never usable, even before the job removes it. */
export function isExpired(credential: Credential, now: Date): boolean {
  return credential.expiresAt !== null && new Date(credential.expiresAt) <= now;
}

/** The expiry job (every 15 minutes): delete expired credentials and audit each one. */
export function expireCredentials(store: Store, now: Date): number {
  let deleted = 0;
  for (const c of store.allCredentials()) {
    if (!isExpired(c, now)) continue;
    store.deleteCredential(c.userId, c.provider);
    store.addAudit({
      userId: c.userId,
      action: 'keyDeleted',
      at: now.toISOString(),
      detail: { provider: c.provider, reason: 'expired', last4: c.last4 },
    });
    deleted++;
  }
  return deleted;
}
