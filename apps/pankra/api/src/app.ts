import Fastify, { type FastifyInstance } from 'fastify';
import cookie from '@fastify/cookie';
import cors from '@fastify/cors';
import type { Db } from 'mongodb';
import { API_PREFIX } from '@pankra/shared';
import type { Config } from './config.js';
import type { Mailer } from './auth/mailer.js';
import { authPlugin } from './auth/routes.js';

export interface AppDeps {
  config: Config;
  db: Db;
  mailer: Mailer;
  now: () => Date;
}

/**
 * The API. Logging records request ids, routes and timings only: never bodies, tokens or
 * cookies (spec: Security and privacy).
 */
export async function buildApp(deps: AppDeps): Promise<FastifyInstance> {
  const app = Fastify({
    logger: process.env.NODE_ENV === 'test' || process.env.VITEST ? false : {
      redact: ['req.headers.authorization', 'req.headers.cookie', 'res.headers["set-cookie"]'],
    },
  });
  await app.register(cookie);
  await app.register(cors, { origin: deps.config.appUrl, credentials: true });

  await app.register(async (api) => {
    api.get('/health', async () => {
      let db = false;
      try { db = (await deps.db.command({ ping: 1 })).ok === 1; } catch { db = false; }
      return { ok: true, db, version: deps.config.version };
    });
    await api.register(authPlugin(deps));
  }, { prefix: API_PREFIX });

  return app;
}
