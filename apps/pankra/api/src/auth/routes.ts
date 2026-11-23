import { randomUUID } from 'node:crypto';
import type { FastifyInstance, FastifyReply, FastifyRequest } from 'fastify';
import type { Db } from 'mongodb';
import { SignInRequest, VerifyRequest } from '@pankra/shared';
import type { Config } from '../config.js';
import type { Mailer } from './mailer.js';
import { hashToken, newToken } from './tokens.js';

export const SESSION_COOKIE = 'pankra_session';

export interface AuthedUser { userId: string; email: string; sessionHash: string }

declare module 'fastify' {
  interface FastifyRequest { user?: AuthedUser }
}

function presentedToken(req: FastifyRequest): string | undefined {
  const header = req.headers.authorization;
  if (header?.startsWith('Bearer ')) return header.slice(7).trim();
  return req.cookies?.[SESSION_COOKIE];
}

export function authPlugin(deps: { config: Config; db: Db; mailer: Mailer; now: () => Date }) {
  const { config, db, mailer, now } = deps;
  const users = db.collection('users');
  const links = db.collection('login_tokens');
  const sessions = db.collection('auth_sessions');

  async function requireUser(req: FastifyRequest, reply: FastifyReply) {
    const token = presentedToken(req);
    if (token) {
      const session = await sessions.findOne({ tokenHash: hashToken(token), expiresAt: { $gt: now() } });
      if (session) {
        req.user = { userId: session.userId, email: session.email, sessionHash: session.tokenHash };
        return;
      }
    }
    return reply.code(401).send({ error: 'sign in required' });
  }

  return async function register(app: FastifyInstance) {
    app.decorate('requireUser', requireUser);

    app.post('/auth/link', async (req, reply) => {
      const parsed = SignInRequest.safeParse(req.body);
      if (!parsed.success) return reply.code(400).send({ error: 'a valid email is required' });
      const email = parsed.data.email.toLowerCase();
      // Same answer for everyone, so the endpoint does not reveal who the owner is.
      if (email === config.ownerEmail) {
        const token = newToken();
        const at = now();
        await links.insertOne({ tokenHash: hashToken(token), email, used: false, createdAt: at,
          expiresAt: new Date(at.getTime() + config.linkTtlMinutes * 60_000) });
        await mailer.send({ to: email, subject: 'Sign in to PANKRA',
          link: `${config.appUrl}/auth/verify?token=${encodeURIComponent(token)}` });
      }
      return reply.code(202).send({ sent: true });
    });

    app.post('/auth/verify', async (req, reply) => {
      const parsed = VerifyRequest.safeParse(req.body);
      if (!parsed.success) return reply.code(401).send({ error: 'link is invalid or expired' });
      const at = now();
      const link = await links.findOneAndUpdate(
        { tokenHash: hashToken(parsed.data.token), used: false, expiresAt: { $gt: at } },
        { $set: { used: true, usedAt: at } });
      if (!link) return reply.code(401).send({ error: 'link is invalid or expired' });

      const email = link.email as string;
      await users.updateOne({ email },
        { $setOnInsert: { email, userId: randomUUID(), schemaVersion: 1, createdAt: at },
          $set: { updatedAt: at } }, { upsert: true });
      const user = await users.findOne({ email });
      const token = newToken();
      const expiresAt = new Date(at.getTime() + config.sessionTtlDays * 86_400_000);
      await sessions.insertOne({ tokenHash: hashToken(token), userId: user!.userId, email,
        client: parsed.data.client, createdAt: at, expiresAt });

      const me = { userId: user!.userId as string, email };
      if (parsed.data.client === 'ios') return reply.send({ ...me, token, expiresAt });
      reply.setCookie(SESSION_COOKIE, token, { httpOnly: true, secure: true, sameSite: 'lax',
        path: '/', expires: expiresAt });
      return reply.send(me);
    });

    app.post('/auth/logout', { preHandler: requireUser }, async (req, reply) => {
      await sessions.deleteOne({ tokenHash: req.user!.sessionHash });
      reply.clearCookie(SESSION_COOKIE, { path: '/' });
      return reply.code(204).send();
    });

    app.get('/me', { preHandler: requireUser }, async (req) =>
      ({ userId: req.user!.userId, email: req.user!.email }));
  };
}

declare module 'fastify' {
  interface FastifyInstance {
    requireUser(req: FastifyRequest, reply: FastifyReply): Promise<unknown>;
  }
}
