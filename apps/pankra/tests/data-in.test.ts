import { randomBytes } from 'node:crypto';
import { readFileSync } from 'node:fs';
import { describe, expect, it } from 'vitest';
import { buildApp } from '../api/src/app.ts';
import { MemoryStore } from '../api/src/store.ts';
import type { Race, RaceAnalysis, RegistryNode, Upload } from '../packages/shared/src/index.ts';

const USER = 'owner';
const NOW = new Date('2026-11-23T18:00:00Z');
const ROOT = new URL('../../../', import.meta.url);

function registryNode(kind: 'skills', name: string): RegistryNode {
  const dir = new URL(`registry/${kind}/${name}/`, ROOT);
  const node = JSON.parse(readFileSync(new URL('node.json', dir), 'utf8'));
  return { ...node, files: { 'SKILL.md': readFileSync(new URL('SKILL.md', dir), 'utf8') }, retired: false };
}

function json(status: number, body: unknown) {
  return new Response(JSON.stringify(body), { status, headers: { 'content-type': 'application/json' } });
}

/** A multipart/form-data body with one file field, as the app's upload sends it. */
function multipart(field: string, filename: string, mime: string, bytes: Buffer) {
  const boundary = '----pankra' + randomBytes(8).toString('hex');
  const head = Buffer.from(
    `--${boundary}\r\nContent-Disposition: form-data; name="${field}"; filename="${filename}"\r\nContent-Type: ${mime}\r\n\r\n`,
  );
  const tail = Buffer.from(`\r\n--${boundary}--\r\n`);
  return { payload: Buffer.concat([head, bytes, tail]), headers: { 'content-type': `multipart/form-data; boundary=${boundary}` } };
}

/** Hyrox results as screenshot-reader returns them: times exactly as shown on the screen. */
const SCREEN = {
  kind: 'race',
  data: {
    Event: 'HYROX Hamburg', Division: "Men's Pro",
    'Running 1': '00:02:59', 'Running 2': '00:04:41', 'Running 3': '00:04:44', 'Running 4': '00:04:50',
    'Running 5': '00:04:47', 'Running 6': '00:04:55', 'Running 7': '00:04:58', 'Running 8': '00:05:06',
    SkiErg: '00:04:21', 'Sled Push': '00:03:58', 'Sled Pull': '00:05:12', 'Burpee Broad Jump': '00:04:35',
    Rowing: '00:04:40', 'Farmers Carry': '00:01:58', 'Sandbag Lunges': '00:04:49', 'Wall Balls': '00:06:21',
    Roxzone: '00:06:30', Total: '01:20:26',
  },
  uncertain: [],
};

function setup(providerReplies: Response[] = []) {
  const store = new MemoryStore();
  store.saveNode(registryNode('skills', 'screenshot-reader'));
  const sent: Array<{ url: string; body: any }> = [];
  const strava: Array<{ url: string; auth?: string }> = [];
  const fetchImpl = (async (url: string | URL, init?: RequestInit) => {
    const u = String(url);
    if (u === 'https://www.strava.com/oauth/token') {
      const form = JSON.parse(String(init?.body));
      if (form.code !== 'auth-code-1' || form.client_secret !== 'test-strava-secret') return json(400, { message: 'Bad Request' });
      return json(200, {
        token_type: 'Bearer', access_token: 'strava-access-1', refresh_token: 'strava-refresh-1',
        expires_at: NOW.getTime() / 1000 + 3600, athlete: { id: 42 },
      });
    }
    if (u.startsWith('https://www.strava.com/')) {
      strava.push({ url: u, auth: (init?.headers as Record<string, string> | undefined)?.authorization });
      const id = Number(u.split('/').pop());
      return json(200, {
        id, name: 'Morning run', sport_type: 'Run', start_date: '2026-11-22T07:00:00Z',
        distance: 10000, moving_time: 2700, elapsed_time: 2760, average_speed: 3.7, athlete: { id: 42 },
      });
    }
    sent.push({ url: u, body: JSON.parse(String(init?.body)) });
    const reply = providerReplies.shift();
    if (!reply) throw new Error(`unexpected request to ${u}`);
    return reply;
  }) as unknown as typeof fetch;
  const app = buildApp({
    store, userId: () => USER, vaultKey: randomBytes(32).toString('base64'), now: () => NOW, fetch: fetchImpl,
    strava: { clientId: '1234', clientSecret: 'test-strava-secret', subscriptionId: 777, verifyToken: 'verify-me' },
  });
  return { store, app, sent, strava };
}

function claudeTool(output: unknown) {
  return json(200, { type: 'message', content: [{ type: 'tool_use', id: 't', name: 'output', input: output }], usage: { input_tokens: 1500, output_tokens: 400 } });
}

describe('Results and feedback', () => {
  it('Scenario: screenshot values need confirmation', async () => {
    const { app, sent } = setup([claudeTool(SCREEN)]);
    await app.inject({ method: 'PUT', url: '/api/v1/credentials/claude', payload: { secret: 'test-claude-key-9999', retention: '7d' } });

    // Given a Hyrox results screenshot showing Running 1 as 00:02:59
    const png = Buffer.from('89504e470d0a1a0a0000000d49484452', 'hex');
    // When the athlete uploads it
    const body = multipart('image', 'hyrox.png', 'image/png', png);
    const res = await app.inject({ method: 'POST', url: '/api/v1/uploads?kind=race&provider=claude', ...body });
    expect(res.statusCode).toBe(200);
    const upload = res.json() as Upload;

    // Then the extracted values are shown with Running 1 = 2:59
    expect(upload.confirmed).toBe(false);
    expect(upload.extracted?.fields.find((f) => f.label === 'Running 1')).toMatchObject({ text: '2:59', seconds: 179 });
    expect(upload.extracted?.race?.runs).toHaveLength(8);
    // The image itself went to the model, as an image.
    const content = sent[0].body.messages[0].content;
    expect(content[0]).toMatchObject({ type: 'image', source: { type: 'base64', media_type: 'image/png', data: png.toString('base64') } });

    // And no race is saved until the athlete taps Confirm
    expect((await app.inject({ method: 'GET', url: '/api/v1/races' })).json()).toEqual([]);
    const confirm = await app.inject({ method: 'POST', url: `/api/v1/uploads/${upload.id}/confirm`, payload: { data: upload.extracted!.race } });
    expect(confirm.statusCode).toBe(200);
    expect((confirm.json() as Upload).confirmed).toBe(true);
    const races = (await app.inject({ method: 'GET', url: '/api/v1/races' })).json() as Race[];
    expect(races).toHaveLength(1);
    expect(races[0].runs[0]).toBe(179);
  });

  it('Scenario: a race is broken down by seconds to gain', async () => {
    // Given a confirmed race with stations totalling 35:54 and a target of 60:00
    const { app, store } = setup();
    const stations = [261, 238, 312, 275, 280, 118, 289, 381]; // 35:54
    expect(stations.reduce((a, b) => a + b, 0)).toBe(35 * 60 + 54);
    const runs = [299, 281, 284, 290, 287, 295, 298, 306];
    const race: Race = {
      id: 'race-1', userId: USER, event: 'HYROX Hamburg', date: '2026-11-15', division: "Men's Pro",
      runs, stations, roxzoneS: 390, totalS: runs.reduce((a, b) => a + b, 0) + 2154 + 390,
      createdAt: NOW.toISOString(),
    };
    store.saveRace(race);
    store.saveProfile({ userId: USER, division: "Men's Pro", matLengthM: 12.5, restDay: 'Sat', units: 'metric', raceTargetS: 3600 });

    // When the athlete opens the race analysis
    const res = await app.inject({ method: 'GET', url: '/api/v1/races/race-1/analysis' });
    expect(res.statusCode).toBe(200);
    const analysis = res.json() as RaceAnalysis;

    // Then each of the 8 stations, the runs and Roxzone show seconds to gain
    const names = analysis.segments.map((s) => s.name);
    for (const s of ['SkiErg', 'Sled Push', 'Sled Pull', 'Burpee Broad Jump', 'Rowing', 'Farmers Carry', 'Sandbag Lunges', 'Wall Balls', 'Runs', 'Roxzone']) {
      expect(names).toContain(s);
    }
    expect(analysis.segments).toHaveLength(10);
    for (const s of analysis.segments) {
      expect(s.gainSeconds).toBeGreaterThan(0);
      expect(s.gainSeconds).toBe(s.actualSeconds - s.targetSeconds);
    }
    // The target split adds up to the target.
    expect(analysis.segments.reduce((a, s) => a + s.targetSeconds, 0)).toBe(3600);
    expect(analysis.targetS).toBe(3600);

    // And they are ordered from most to least
    const gains = analysis.segments.map((s) => s.gainSeconds);
    expect(gains).toEqual([...gains].sort((a, b) => b - a));
  });
});

describe('Data in', () => {
  it('Scenario: duplicate Strava event imports once', async () => {
    const { app, store, strava } = setup();
    // The athlete has connected Strava (athlete 42) through OAuth; the tokens go to the vault.
    const connect = (await app.inject({ method: 'GET', url: '/api/v1/strava/connect' })).json() as { url: string };
    const state = new URL(connect.url).searchParams.get('state');
    const callback = await app.inject({ method: 'GET', url: `/api/v1/strava/callback?code=auth-code-1&state=${state}&scope=read,activity:read_all` });
    expect(callback.statusCode).toBe(200);
    expect(JSON.stringify(store.dump())).not.toContain('strava-access-1');
    const event = {
      object_type: 'activity', object_id: 123456, aspect_type: 'create', owner_id: 42,
      subscription_id: 777, event_time: 1763800000, updates: {},
    };

    // Given Strava activity 123456 was imported
    const first = await app.inject({ method: 'POST', url: '/api/v1/webhooks/strava', payload: event });
    expect(first.statusCode).toBe(200);
    expect(store.listActivities(USER).filter((a) => a.externalId === '123456')).toHaveLength(1);

    // When the Strava webhook sends activity 123456 again
    const again = await app.inject({ method: 'POST', url: '/api/v1/webhooks/strava', payload: event });
    expect(again.statusCode).toBe(200);

    // Then exactly 1 activity 123456 exists
    expect(store.listActivities(USER).filter((a) => a.externalId === '123456')).toHaveLength(1);
    expect(strava[0]).toMatchObject({ url: 'https://www.strava.com/api/v3/activities/123456', auth: 'Bearer strava-access-1' });

    // An event from another subscription is ignored.
    const forged = await app.inject({ method: 'POST', url: '/api/v1/webhooks/strava', payload: { ...event, object_id: 999, subscription_id: 1 } });
    expect(forged.statusCode).toBe(403);
    expect(store.listActivities(USER)).toHaveLength(1);
  });
});
