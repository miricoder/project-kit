import { randomBytes } from 'node:crypto';
import { describe, expect, it } from 'vitest';
import { buildApp } from '../api/src/app.ts';
import { MemoryStore } from '../api/src/store.ts';
import type { Result, Session } from '../packages/shared/src/index.ts';

const OWNER_EMAIL = 'owner@example.com';
const OWNER = 'owner';
const WEEK = ['2026-11-22', '2026-11-23', '2026-11-24', '2026-11-25', '2026-11-26', '2026-11-27', '2026-11-28'];

/** The server as deployed: real sign-in (no test user), email delivery stood in for. */
function server(now: () => Date) {
  const store = new MemoryStore();
  const emails: Array<{ to: string; subject: string; text: string }> = [];
  const fetchImpl = (async (url: string | URL, init?: RequestInit) => {
    if (String(url) !== 'https://api.resend.com/emails') throw new Error(`unexpected request to ${url}`);
    const body = JSON.parse(String(init?.body));
    emails.push({ to: body.to[0], subject: body.subject, text: body.text });
    return new Response(JSON.stringify({ id: 'email_1' }), { status: 200 });
  }) as unknown as typeof fetch;
  const app = buildApp({
    store,
    now,
    fetch: fetchImpl,
    vaultKey: randomBytes(32).toString('base64'),
    auth: { ownerEmail: OWNER_EMAIL, ownerId: OWNER, resendApiKey: 'test-resend-key', from: 'PANKRA <login@example.com>' },
    webUrl: 'https://pankra.example.com',
  });
  return { store, app, emails };
}

/** The app's sign-in on iPhone: ask for a link, open it, keep the bearer token. */
async function signInOnIPhone(s: ReturnType<typeof server>): Promise<string> {
  const ask = await s.app.inject({ method: 'POST', url: '/api/v1/auth/magic-link', payload: { email: OWNER_EMAIL, client: 'ios' } });
  expect(ask.statusCode).toBe(202);
  const link = s.emails.at(-1)!.text.match(/pankra:\/\/sign-in\?token=[A-Za-z0-9_-]+/)![0];
  const token = new URL(link).searchParams.get('token');
  const verify = await s.app.inject({ method: 'POST', url: '/api/v1/auth/verify', payload: { token } });
  expect(verify.statusCode).toBe(200);
  return (verify.json() as { token: string }).token;
}

describe('iPhone app', () => {
  it('Scenario: reinstalled iPhone app shows the same week', async () => {
    let now = new Date('2026-11-22T07:00:00Z');
    const s = server(() => now);

    // Given the week of 22 Nov 2026 has 6 sessions on the server
    const days = WEEK.filter((d) => d !== '2026-11-28'); // Sat 28 is rest
    for (const [i, date] of days.entries()) {
      const session: Session = {
        id: `wk-${i}`, userId: OWNER, date, title: `Session ${i + 1}`, type: 'gym',
        status: 'Done', source: 'plan', sections: [],
      };
      s.store.saveSession(session);
      const result: Result = {
        id: `res-${i}`, userId: OWNER, sessionId: session.id, uploadIds: [], createdAt: `${date}T18:00:00.000Z`,
        parts: [{ label: 'Main set', timeS: 600 + i }],
      };
      s.store.saveResult(result);
    }
    const firstInstall = await signInOnIPhone(s);
    const before = await s.app.inject({ method: 'GET', url: '/api/v1/sessions?from=2026-11-22&to=2026-11-28', headers: { authorization: `Bearer ${firstInstall}` } });
    expect(before.json()).toHaveLength(6);

    // And the iPhone app expired after 7 days (its storage, and the token in it, are gone)
    now = new Date('2026-11-29T08:00:00Z');
    const noToken = await s.app.inject({ method: 'GET', url: '/api/v1/sessions?from=2026-11-22&to=2026-11-28' });
    expect(noToken.statusCode).toBe(401);

    // When the athlete reinstalls it from Xcode and signs in
    const reinstalled = await signInOnIPhone(s);
    expect(reinstalled).not.toBe(firstInstall);
    const auth = { authorization: `Bearer ${reinstalled}` };

    // Then the Week screen shows the same 6 sessions with their results
    const sessions = (await s.app.inject({ method: 'GET', url: '/api/v1/sessions?from=2026-11-22&to=2026-11-28', headers: auth })).json() as Session[];
    expect(sessions.map((x) => x.id)).toEqual(days.map((_, i) => `wk-${i}`));
    const results = (await s.app.inject({ method: 'GET', url: '/api/v1/results?from=2026-11-22&to=2026-11-28', headers: auth })).json() as Result[];
    expect(results.map((r) => r.sessionId).sort()).toEqual(days.map((_, i) => `wk-${i}`).sort());
    expect(results.find((r) => r.sessionId === 'wk-3')?.parts[0].timeS).toBe(603);
  });

  it('a sign-in link works once, expires, and only the owner gets one', async () => {
    let now = new Date('2026-11-22T07:00:00Z');
    const s = server(() => now);
    await s.app.inject({ method: 'POST', url: '/api/v1/auth/magic-link', payload: { email: OWNER_EMAIL, client: 'web' } });
    const link = s.emails[0].text.match(/https:\/\/pankra\.example\.com\/sign-in\?token=[A-Za-z0-9_-]+/)![0];
    const token = new URL(link).searchParams.get('token');

    // Web gets an HttpOnly, Secure, SameSite=Lax cookie.
    const web = await s.app.inject({ method: 'POST', url: '/api/v1/auth/verify', payload: { token } });
    expect(web.statusCode).toBe(200);
    const cookie = String(web.headers['set-cookie']);
    expect(cookie).toMatch(/pankra_session=/);
    expect(cookie).toMatch(/HttpOnly/);
    expect(cookie).toMatch(/Secure/);
    expect(cookie).toMatch(/SameSite=Lax/);
    const sessionCookie = cookie.split(';')[0];
    expect((await s.app.inject({ method: 'GET', url: '/api/v1/credentials', headers: { cookie: sessionCookie } })).statusCode).toBe(200);

    // The same link again is refused.
    expect((await s.app.inject({ method: 'POST', url: '/api/v1/auth/verify', payload: { token } })).statusCode).toBe(401);

    // A link older than 15 minutes is refused.
    await s.app.inject({ method: 'POST', url: '/api/v1/auth/magic-link', payload: { email: OWNER_EMAIL, client: 'web' } });
    const late = new URL(s.emails[1].text.match(/https:\/\/\S+/)![0]).searchParams.get('token');
    now = new Date('2026-11-22T07:16:00Z');
    expect((await s.app.inject({ method: 'POST', url: '/api/v1/auth/verify', payload: { token: late } })).statusCode).toBe(401);

    // Anyone else gets the same answer and no email.
    const stranger = await s.app.inject({ method: 'POST', url: '/api/v1/auth/magic-link', payload: { email: 'someone@else.com', client: 'web' } });
    expect(stranger.statusCode).toBe(202);
    expect(s.emails).toHaveLength(2);

    // Signing out ends the session.
    await s.app.inject({ method: 'POST', url: '/api/v1/auth/sign-out', headers: { cookie: sessionCookie } });
    expect((await s.app.inject({ method: 'GET', url: '/api/v1/credentials', headers: { cookie: sessionCookie } })).statusCode).toBe(401);
  });
});
