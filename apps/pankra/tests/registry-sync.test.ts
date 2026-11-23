import { readFileSync } from 'node:fs';
import { describe, expect, it } from 'vitest';
import { buildApp } from '../api/src/app.ts';
import { MemoryStore } from '../api/src/store.ts';
import type { NodeSummary, RegistryNode } from '../packages/shared/src/index.ts';
import { RAW, REF, REPO, ROOT, fakeGitHub } from './helpers/fake-github.ts';

const USER = 'owner';

function appWith(store: MemoryStore, github: ReturnType<typeof fakeGitHub>, at: string) {
  return buildApp({
    store,
    userId: () => USER,
    now: () => new Date(at),
    fetch: github.fetchImpl,
    registry: { repo: REPO, ref: REF },
  });
}

async function sync(app: ReturnType<typeof buildApp>) {
  const res = await app.inject({ method: 'POST', url: '/api/v1/registry/sync' });
  return res;
}

async function nodes(app: ReturnType<typeof buildApp>) {
  const res = await app.inject({ method: 'GET', url: '/api/v1/nodes' });
  expect(res.statusCode).toBe(200);
  return res.json() as Array<NodeSummary & { steps?: RegistryNode['steps'] }>;
}

describe('Registry and skills graph', () => {
  it('Scenario: the app pulls the registry by itself', async () => {
    // Given REGISTRY_REF points at a tag whose index.json lists 13 nodes
    const index = JSON.parse(readFileSync(new URL('registry/index.json', ROOT), 'utf8'));
    expect(index.nodes).toHaveLength(13);
    const store = new MemoryStore();
    const github = fakeGitHub();
    const app = appWith(store, github, '2026-11-23T12:00:00Z');

    // When the registry sync runs
    const res = await sync(app);
    expect(res.statusCode).toBe(200);
    expect(res.json()).toMatchObject({ ok: true, added: 13, updated: 0, retired: 0, skipped: [] });

    // Then the Skills screen shows 13 nodes
    const list = await nodes(app);
    expect(list).toHaveLength(13);
    // And the weekly-coach agent has 3 numbered steps
    const coach = list.find((n) => n.name === 'weekly-coach');
    expect(coach?.kind).toBe('agent');
    expect(coach?.steps).toEqual([
      { skill: 'purposed-convo-workout-readjust', order: 1 },
      { skill: 'schedule-shifter', order: 2 },
      { skill: 'workout-whiteboard', order: 3 },
    ]);
    const edges = (await app.inject({ method: 'GET', url: '/api/v1/edges' })).json() as Array<{ from: string; type: string; order?: number }>;
    expect(edges.filter((e) => e.from === 'agent:weekly-coach' && e.type === 'calls').map((e) => e.order)).toEqual([1, 2, 3]);
    // Instructions came along with the node, so it can run.
    expect(store.getNode('skill', 'result-analyzer')?.files['SKILL.md']).toContain('# Result analyser');
    // Every request went to the pinned ref.
    expect(github.requested.every((u) => u.startsWith(RAW))).toBe(true);

    // A second sync with nothing new fetches only the index and the schema.
    github.requested.length = 0;
    expect((await sync(app)).json()).toMatchObject({ ok: true, added: 0, updated: 0 });
    expect(github.requested).toHaveLength(2);
  });

  it('Scenario: registry offline keeps current skills', async () => {
    // Given 13 nodes are loaded
    const store = new MemoryStore();
    const first = appWith(store, fakeGitHub(), '2026-11-23T12:00:00Z');
    expect((await sync(first)).json()).toMatchObject({ ok: true, added: 13 });
    // And GitHub returns HTTP 503
    const app = appWith(store, fakeGitHub({ down: true }), '2026-11-23T18:00:00Z');

    // When the registry sync runs
    const res = await sync(app);
    expect(res.statusCode).toBe(502);
    expect(res.json().error).toContain('503');

    // Then 13 nodes are still available
    expect(await nodes(app)).toHaveLength(13);
    // And Settings shows the last successful sync time
    const status = (await app.inject({ method: 'GET', url: '/api/v1/registry/status' })).json();
    expect(status).toMatchObject({
      lastSuccessAt: '2026-11-23T12:00:00.000Z',
      lastAttemptAt: '2026-11-23T18:00:00.000Z',
      ref: REF,
      nodes: 13,
    });
    expect(status.lastError).toContain('503');
  });

  it('Scenario: invalid registry node is skipped', async () => {
    // Given the index lists a skill whose node.json has no "requires"
    const broken = 'registry/skills/pace-planner/node.json';
    const github = fakeGitHub({
      override: (path, text) => {
        if (path !== broken) return text;
        const node = JSON.parse(text);
        delete node.requires;
        return JSON.stringify(node);
      },
    });
    const store = new MemoryStore();
    const app = appWith(store, github, '2026-11-23T12:00:00Z');

    // When the registry sync runs
    const report = (await sync(app)).json();

    // Then that skill is not loaded
    const list = await nodes(app);
    expect(list.find((n) => n.name === 'pace-planner')).toBeUndefined();
    // And the sync report names it
    expect(report.skipped).toEqual([
      { kind: 'skill', name: 'pace-planner', reason: expect.stringContaining('requires') },
    ]);
    // And every other node loads
    expect(list).toHaveLength(12);
    expect(report).toMatchObject({ ok: true, added: 12 });
  });
});
