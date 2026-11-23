import Fastify, { type FastifyInstance } from 'fastify';
import { z } from 'zod';
import { randomUUID } from 'node:crypto';
import { shiftSchedule, type CredentialStatus, type Session } from '@pankra/shared';
import type { Store } from './store.ts';
import { Vault, isExpired } from './vault.ts';

export interface AppDeps {
  store: Store;
  /** Resolves the signed-in user for a request; undefined means not signed in. */
  userId: (headers: Record<string, unknown>) => string | undefined;
  /** Base64 32-byte master key for the key vault (host secret VAULT_KEY). */
  vaultKey?: string;
  /** The clock; injected so retention can be tested. */
  now?: () => Date;
}

const CredentialParams = z.object({ provider: z.enum(['claude', 'gpt']) });
const CredentialBody = z.object({
  secret: z.string().trim().min(8).max(500),
  retention: z.enum(['session', '24h', '7d', '30d', 'forever']),
});

const isoDate = z.string().regex(/^\d{4}-\d{2}-\d{2}$/, 'expected YYYY-MM-DD');
const SessionsQuery = z.object({ from: isoDate, to: isoDate });

const Item = z.object({
  exercise: z.string().min(1),
  distanceM: z.number().positive().optional(),
  loadKg: z.number().nonnegative().optional(),
  reps: z.number().int().positive().optional(),
  timeS: z.number().positive().optional(),
  speedKmh: z.number().positive().optional(),
  machine: z.string().optional(),
});
const Section = z.object({
  kind: z.enum(['warmup', 'strength', 'engine', 'core', 'cooldown', 'daily']),
  label: z.string().min(1),
  lines: z.array(z.union([z.string(), Item])),
  rounds: z.number().int().positive().optional(),
  restS: z.number().positive().optional(),
});
const InsertBody = z.object({
  date: isoDate,
  session: z.object({
    title: z.string().min(1).max(200),
    type: z.enum(['gym', 'track', 'class']).default('class'),
    tag: z.string().max(100).optional(),
    sections: z.array(Section).default([]),
    notes: z.string().max(5000).optional(),
    log: z.string().max(500).optional(),
  }),
});

function errorText(error: z.ZodError): string {
  return error.issues.map((i) => `${i.path.join('.') || 'body'}: ${i.message}`).join('; ');
}

export function buildApp(deps: AppDeps): FastifyInstance {
  // Request bodies are never logged: they can carry keys.
  const app = Fastify({ logger: false });
  const now = deps.now ?? (() => new Date());
  const vault = deps.vaultKey ? new Vault(deps.vaultKey) : undefined;

  app.get('/api/v1/health', async () => ({ ok: true }));

  app.get('/api/v1/sessions', async (req, reply) => {
    const userId = deps.userId(req.headers);
    if (!userId) return reply.code(401).send({ error: 'Sign in required' });
    const parsed = SessionsQuery.safeParse(req.query);
    if (!parsed.success) {
      return reply.code(400).send({ error: parsed.error.issues.map((i) => i.message).join('; ') });
    }
    const { from, to } = parsed.data;
    if (from > to) return reply.code(400).send({ error: '"from" is after "to"' });
    return deps.store.listSessions(userId, from, to);
  });

  // Insert a session (usually a box class) and push later planned sessions (schedule-shifter).
  app.post('/api/v1/sessions/insert', async (req, reply) => {
    const userId = deps.userId(req.headers);
    if (!userId) return reply.code(401).send({ error: 'Sign in required' });
    const parsed = InsertBody.safeParse(req.body);
    if (!parsed.success) return reply.code(400).send({ error: errorText(parsed.error) });
    const profile = deps.store.getProfile(userId);
    if (!profile) return reply.code(409).send({ error: 'Set up the profile (rest day) first' });

    const { date, session } = parsed.data;
    const inserted: Session = {
      ...session,
      id: randomUUID(),
      userId,
      date,
      status: 'Scheduled',
      source: session.type === 'class' ? 'class' : 'plan',
    };
    const existing = deps.store.listSessions(userId, date, '9999-12-31');
    const { updated, changes } = shiftSchedule(existing, inserted, profile);
    for (const s of updated) deps.store.saveSession(s);
    return { session: inserted, changes };
  });

  // Keys: the app only ever sees provider, last4 and expiry.
  app.get('/api/v1/credentials', async (req, reply) => {
    const userId = deps.userId(req.headers);
    if (!userId) return reply.code(401).send({ error: 'Sign in required' });
    const at = now();
    return deps.store
      .listCredentials(userId)
      .filter((c) => !isExpired(c, at))
      .map(({ provider, last4, retention, expiresAt }): CredentialStatus => ({ provider, last4, retention, expiresAt }));
  });

  app.put('/api/v1/credentials/:provider', async (req, reply) => {
    const userId = deps.userId(req.headers);
    if (!userId) return reply.code(401).send({ error: 'Sign in required' });
    const params = CredentialParams.safeParse(req.params);
    if (!params.success) return reply.code(404).send({ error: 'Unknown provider' });
    const body = CredentialBody.safeParse(req.body);
    if (!body.success) return reply.code(400).send({ error: errorText(body.error) });
    if (!vault) return reply.code(503).send({ error: 'Key vault is not configured (VAULT_KEY)' });

    const at = now();
    const { provider } = params.data;
    const replaced = deps.store.getCredential(userId, provider);
    const credential = vault.seal(userId, provider, body.data.secret, body.data.retention, at);
    deps.store.saveCredential(credential);
    deps.store.addAudit({
      userId,
      action: 'keyAdded',
      at: at.toISOString(),
      detail: { provider, last4: credential.last4, retention: credential.retention, replaced: Boolean(replaced) },
    });
    return { last4: credential.last4, expiresAt: credential.expiresAt };
  });

  app.delete('/api/v1/credentials/:provider', async (req, reply) => {
    const userId = deps.userId(req.headers);
    if (!userId) return reply.code(401).send({ error: 'Sign in required' });
    const params = CredentialParams.safeParse(req.params);
    if (!params.success) return reply.code(404).send({ error: 'Unknown provider' });
    const existing = deps.store.getCredential(userId, params.data.provider);
    if (existing && deps.store.deleteCredential(userId, params.data.provider)) {
      deps.store.addAudit({
        userId,
        action: 'keyDeleted',
        at: now().toISOString(),
        detail: { provider: params.data.provider, reason: 'requested', last4: existing.last4 },
      });
    }
    return reply.code(204).send();
  });

  app.get('/api/v1/profile', async (req, reply) => {
    const userId = deps.userId(req.headers);
    if (!userId) return reply.code(401).send({ error: 'Sign in required' });
    const profile = deps.store.getProfile(userId);
    if (!profile) return reply.code(404).send({ error: 'No profile yet' });
    return profile;
  });

  return app;
}
