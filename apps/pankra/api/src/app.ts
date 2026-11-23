import Fastify, { type FastifyInstance } from 'fastify';
import { z } from 'zod';
import type { Store } from './store.ts';

export interface AppDeps {
  store: Store;
  /** Resolves the signed-in user for a request; undefined means not signed in. */
  userId: (headers: Record<string, unknown>) => string | undefined;
}

const isoDate = z.string().regex(/^\d{4}-\d{2}-\d{2}$/, 'expected YYYY-MM-DD');
const SessionsQuery = z.object({ from: isoDate, to: isoDate });

export function buildApp(deps: AppDeps): FastifyInstance {
  const app = Fastify({ logger: false });

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

  app.get('/api/v1/profile', async (req, reply) => {
    const userId = deps.userId(req.headers);
    if (!userId) return reply.code(401).send({ error: 'Sign in required' });
    const profile = deps.store.getProfile(userId);
    if (!profile) return reply.code(404).send({ error: 'No profile yet' });
    return profile;
  });

  return app;
}
