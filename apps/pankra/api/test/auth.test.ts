import { afterAll, beforeAll, describe, expect, it } from 'vitest';
import { makeApp, startDb } from './helpers.js';

let mongo: Awaited<ReturnType<typeof startDb>>;
beforeAll(async () => { mongo = await startDb(); });
afterAll(async () => { await mongo.stop(); });

async function signedOutApp(now?: () => Date) {
  return makeApp(mongo.db(), now ? { now } : {});
}

function cookieOf(res: { headers: Record<string, unknown> }): string {
  const raw = res.headers['set-cookie'];
  return String(Array.isArray(raw) ? raw[0] : raw);
}

describe('owner sign-in with an email magic link', () => {
  // Scenario: the owner signs in with an email link
  it('sends a link to the owner and the link signs the web app in with a safe cookie', async () => {
    const { app, mailer } = await signedOutApp();
    const ask = await app.inject({ method: 'POST', url: '/api/v1/auth/link',
      payload: { email: 'Owner@Example.com' } });
    expect(ask.statusCode).toBe(202);
    expect(mailer.sent).toHaveLength(1);
    expect(mailer.sent[0].to).toBe('owner@example.com');
    expect(mailer.sent[0].link.startsWith('https://app.example.com/auth/verify?token=')).toBe(true);

    const verify = await app.inject({ method: 'POST', url: '/api/v1/auth/verify',
      payload: { token: mailer.lastToken(), client: 'web' } });
    expect(verify.statusCode).toBe(200);
    const cookie = cookieOf(verify);
    expect(cookie).toMatch(/^pankra_session=/);
    expect(cookie).toMatch(/HttpOnly/i);
    expect(cookie).toMatch(/Secure/i);
    expect(cookie).toMatch(/SameSite=Lax/i);

    const me = await app.inject({ method: 'GET', url: '/api/v1/me',
      headers: { cookie: cookie.split(';')[0] } });
    expect(me.statusCode).toBe(200);
    expect(me.json()).toMatchObject({ email: 'owner@example.com' });
    expect(me.json().userId).toMatch(/\S+/);
    await app.close();
  });

  it('answers the same for a stranger but sends nothing', async () => {
    const { app, mailer } = await signedOutApp();
    const res = await app.inject({ method: 'POST', url: '/api/v1/auth/link',
      payload: { email: 'someone@else.com' } });
    expect(res.statusCode).toBe(202);
    expect(mailer.sent).toHaveLength(0);
    await app.close();
  });

  it('gives the iPhone app a bearer token instead of a cookie', async () => {
    const { app, mailer } = await signedOutApp();
    await app.inject({ method: 'POST', url: '/api/v1/auth/link', payload: { email: 'owner@example.com' } });
    const verify = await app.inject({ method: 'POST', url: '/api/v1/auth/verify',
      payload: { token: mailer.lastToken(), client: 'ios' } });
    expect(verify.statusCode).toBe(200);
    expect(verify.headers['set-cookie']).toBeUndefined();
    const { token } = verify.json();
    const me = await app.inject({ method: 'GET', url: '/api/v1/me',
      headers: { authorization: `Bearer ${token}` } });
    expect(me.statusCode).toBe(200);
    await app.close();
  });

  // Scenario: a sign-in link works only once
  it('refuses a link used twice, an expired link, and a forged one', async () => {
    let clock = new Date('2026-11-23T10:00:00Z');
    const { app, mailer } = await signedOutApp(() => clock);
    await app.inject({ method: 'POST', url: '/api/v1/auth/link', payload: { email: 'owner@example.com' } });
    const token = mailer.lastToken();
    expect((await app.inject({ method: 'POST', url: '/api/v1/auth/verify', payload: { token } })).statusCode).toBe(200);
    expect((await app.inject({ method: 'POST', url: '/api/v1/auth/verify', payload: { token } })).statusCode).toBe(401);

    await app.inject({ method: 'POST', url: '/api/v1/auth/link', payload: { email: 'owner@example.com' } });
    const late = mailer.lastToken();
    clock = new Date(clock.getTime() + 16 * 60_000);
    expect((await app.inject({ method: 'POST', url: '/api/v1/auth/verify', payload: { token: late } })).statusCode).toBe(401);

    expect((await app.inject({ method: 'POST', url: '/api/v1/auth/verify',
      payload: { token: 'x'.repeat(43) } })).statusCode).toBe(401);
    await app.close();
  });

  it('keeps /me closed without a session and after sign-out', async () => {
    const { app, mailer } = await signedOutApp();
    expect((await app.inject({ method: 'GET', url: '/api/v1/me' })).statusCode).toBe(401);
    await app.inject({ method: 'POST', url: '/api/v1/auth/link', payload: { email: 'owner@example.com' } });
    const verify = await app.inject({ method: 'POST', url: '/api/v1/auth/verify',
      payload: { token: mailer.lastToken(), client: 'ios' } });
    const auth = { authorization: `Bearer ${verify.json().token}` };
    expect((await app.inject({ method: 'POST', url: '/api/v1/auth/logout', headers: auth })).statusCode).toBe(204);
    expect((await app.inject({ method: 'GET', url: '/api/v1/me', headers: auth })).statusCode).toBe(401);
    await app.close();
  });

  it('stores only hashes of link and session tokens, never the tokens', async () => {
    const db = mongo.db();
    const { app, mailer } = await makeApp(db);
    await app.inject({ method: 'POST', url: '/api/v1/auth/link', payload: { email: 'owner@example.com' } });
    const token = mailer.lastToken()!;
    const verify = await app.inject({ method: 'POST', url: '/api/v1/auth/verify', payload: { token, client: 'ios' } });
    const session = verify.json().token as string;
    const dump = JSON.stringify([
      ...(await db.collection('login_tokens').find().toArray()),
      ...(await db.collection('auth_sessions').find().toArray()),
    ]);
    expect(dump).not.toContain(token);
    expect(dump).not.toContain(session);
    const user = await db.collection('users').findOne({ email: 'owner@example.com' });
    expect(user).toMatchObject({ schemaVersion: 1 });
    expect(user?.userId).toBeTruthy();
    expect(user?.createdAt).toBeInstanceOf(Date);
    await app.close();
  });
});
