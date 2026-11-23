// Slice 9 (Fuel and share) has no acceptance scenarios; these unit tests are its checks.
import { randomBytes } from 'node:crypto';
import { readFileSync } from 'node:fs';
import { describe, expect, it } from 'vitest';
import { buildApp } from '../api/src/app.ts';
import { MemoryStore } from '../api/src/store.ts';
import { buildCard, postFromCard, postSvg, type RegistryNode, type Run, type Session, type Upload } from '../packages/shared/src/index.ts';

const USER = 'owner';
const ROOT = new URL('../../../', import.meta.url);
const profile = { userId: USER, division: "Men's Pro", matLengthM: 12.5, restDay: 'Sat' as const, units: 'metric' as const };

function registryNode(name: string): RegistryNode {
  const dir = new URL(`registry/skills/${name}/`, ROOT);
  const node = JSON.parse(readFileSync(new URL('node.json', dir), 'utf8'));
  return { ...node, files: { 'SKILL.md': readFileSync(new URL('SKILL.md', dir), 'utf8') }, retired: false };
}

const session: Session = {
  id: 'sled-day', userId: USER, date: '2026-11-25', title: 'Sled strength <heavy> & fast', type: 'gym',
  status: 'Scheduled', source: 'plan', tag: 'Race-pace sleds',
  sections: [
    { kind: 'warmup', label: 'Warm-up', lines: ['10 min easy row', 'Leg swings'] },
    { kind: 'strength', label: 'Sled push', rounds: 4, restS: 90, lines: [{ exercise: 'Sled push', distanceM: 50, loadKg: 202 }] },
    { kind: 'daily', label: 'Daily push and core', lines: ['50 push-ups'] },
  ],
};

function setup(replies: Response[] = []) {
  const store = new MemoryStore();
  store.saveProfile(profile);
  store.saveSession(session);
  store.saveNode(registryNode('meal-planner'));
  const sent: any[] = [];
  const fetchImpl = (async (_u: string, init: RequestInit) => {
    sent.push(JSON.parse(String(init.body)));
    const r = replies.shift();
    if (!r) throw new Error('unexpected provider call');
    return r;
  }) as unknown as typeof fetch;
  const app = buildApp({ store, userId: () => USER, vaultKey: randomBytes(32).toString('base64'), now: () => new Date('2026-11-25T06:00:00Z'), fetch: fetchImpl });
  return { app, store, sent };
}

function pngSize(png: Buffer) {
  expect(png.subarray(0, 8).toString('hex')).toBe('89504e470d0a1a0a');
  return { width: png.readUInt32BE(16), height: png.readUInt32BE(20) };
}

describe('Fuel', () => {
  it('meal-planner reads the fridge photo with the day\'s session and profile', async () => {
    const meals = { seen: ['eggs', 'rice', 'yoghurt'], before: ['Rice with eggs, 3 h out'], after: ['Yoghurt and rice bowl'], buy: 'bananas' };
    const { app, sent } = setup([
      new Response(JSON.stringify({ type: 'message', content: [{ type: 'tool_use', id: 't', name: 'output', input: meals }], usage: { input_tokens: 2000, output_tokens: 300 } }), { status: 200 }),
    ]);
    await app.inject({ method: 'PUT', url: '/api/v1/credentials/claude', payload: { secret: 'test-claude-key-5555', retention: '7d' } });
    const boundary = 'b' + randomBytes(6).toString('hex');
    const jpeg = Buffer.from('ffd8ffe000104a464946', 'hex');
    const payload = Buffer.concat([
      Buffer.from(`--${boundary}\r\nContent-Disposition: form-data; name="image"; filename="fridge.jpg"\r\nContent-Type: image/jpeg\r\n\r\n`),
      jpeg,
      Buffer.from(`\r\n--${boundary}--\r\n`),
    ]);
    const up = await app.inject({ method: 'POST', url: '/api/v1/uploads?kind=meal', payload, headers: { 'content-type': `multipart/form-data; boundary=${boundary}` } });
    const upload = up.json() as Upload;
    expect(upload.extracted).toBeNull(); // a meal photo is not read until meal-planner runs

    const res = await app.inject({
      method: 'POST', url: '/api/v1/runs',
      payload: { node: { kind: 'skill', name: 'meal-planner' }, provider: 'claude', input: { date: '2026-11-25', uploadIds: [upload.id] } },
    });
    const run = res.json() as Run;
    expect(run.status).toBe('succeeded');
    expect(run.output).toMatchObject({ before: meals.before, after: meals.after });
    const content = sent[0].messages[0].content;
    expect(content[0]).toMatchObject({ type: 'image', source: { media_type: 'image/jpeg', data: jpeg.toString('base64') } });
    const input = JSON.parse(content.at(-1).text);
    expect(input.context.sessions.map((s: Session) => s.id)).toEqual(['sled-day']);
    expect(input.context.profile.division).toBe("Men's Pro");
  });

  it('meal-planner without a photo or a list is refused before any call', async () => {
    const { app, sent } = setup();
    await app.inject({ method: 'PUT', url: '/api/v1/credentials/claude', payload: { secret: 'test-claude-key-5555', retention: '7d' } });
    const res = await app.inject({
      method: 'POST', url: '/api/v1/runs',
      payload: { node: { kind: 'skill', name: 'meal-planner' }, provider: 'claude', input: { date: '2026-11-25' } },
    });
    expect(res.statusCode).toBe(400);
    expect(res.json().error).toMatch(/fridge/i);
    expect(sent).toHaveLength(0);
  });
});

describe('Share', () => {
  it('the post is built from the card: no daily block, text escaped, readable sizes', () => {
    const post = postFromCard(buildCard(session, profile));
    const svg = postSvg(post, 'whiteboard');
    expect(svg).toContain('width="1080" height="1350"');
    expect(svg).toContain('50 m · 4 lengths · 202 kg');
    expect(svg).not.toMatch(/push and core/i);
    // The title may wrap; wherever it does, it is escaped and nothing raw gets through.
    expect(svg).toContain('&lt;heavy&gt;');
    expect(svg).toContain('&amp;');
    expect(svg).not.toContain('<heavy>');
    expect(svg).not.toMatch(/&(?!amp;|lt;|gt;|quot;)/);
    const sizes = [...svg.matchAll(/font-size="(\d+)"/g)].map((m) => Number(m[1]));
    expect(Math.min(...sizes)).toBeGreaterThanOrEqual(28);
    expect(Math.max(...sizes)).toBeGreaterThanOrEqual(40);
  });

  for (const theme of ['whiteboard', 'game-inspired', 'clean'] as const) {
    it(`the day's workout exports as a 1080 x 1350 PNG (${theme})`, async () => {
      const { app } = setup();
      const res = await app.inject({ method: 'GET', url: `/api/v1/sessions/sled-day/post.png?theme=${theme}` });
      expect(res.statusCode).toBe(200);
      expect(res.headers['content-type']).toBe('image/png');
      expect(pngSize(res.rawPayload)).toEqual({ width: 1080, height: 1350 });
    });
  }

  it('a layout from ig-post-designer renders the same way', async () => {
    const { app } = setup();
    const res = await app.inject({
      method: 'POST', url: '/api/v1/posts/render',
      payload: { theme: 'clean', post: { date: '2026-11-25', title: 'Sleds', sections: [{ label: 'Push', lines: ['4 x 50 m'] }] } },
    });
    expect(res.statusCode).toBe(200);
    expect(pngSize(res.rawPayload)).toEqual({ width: 1080, height: 1350 });
  });
});
