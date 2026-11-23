import { randomBytes } from 'node:crypto';
import { readFileSync } from 'node:fs';
import { describe, expect, it } from 'vitest';
import { buildApp } from '../api/src/app.ts';
import { MemoryStore } from '../api/src/store.ts';
import type { RegistryNode, Result, Run } from '../packages/shared/src/index.ts';

const USER = 'owner';
const REGISTRY = new URL('../../../registry/skills/result-analyzer/', import.meta.url);

/** result-analyzer exactly as project-kit's registry defines it. */
function resultAnalyzer(): RegistryNode {
  const node = JSON.parse(readFileSync(new URL('node.json', REGISTRY), 'utf8'));
  return { ...node, files: { 'SKILL.md': readFileSync(new URL('SKILL.md', REGISTRY), 'utf8') }, retired: false };
}

/** Claude's reply: generic feedback and the given tips, through the forced output tool. */
function claudeReply(output: unknown) {
  return new Response(
    JSON.stringify({
      type: 'message',
      content: [{ type: 'tool_use', id: 'tu', name: 'output', input: output }],
      usage: { input_tokens: 900, output_tokens: 200 },
    }),
    { status: 200, headers: { 'content-type': 'application/json' } },
  );
}

describe('Results and feedback', () => {
  it('Scenario: a result gets feedback against the plan', async () => {
    // Given a prescription of 5 x 1 km at 13.0 km/h on the Air runner
    const store = new MemoryStore();
    store.saveNode(resultAnalyzer());
    store.saveProfile({ userId: USER, division: "Men's Pro", matLengthM: 12.5, restDay: 'Sat', units: 'metric' });
    store.saveSession({
      id: 'air-1', userId: USER, date: '2026-11-23', title: 'Air runner intervals', type: 'gym',
      status: 'Today', source: 'plan',
      sections: [{
        kind: 'engine', label: 'Intervals', rounds: 5, restS: 90,
        lines: [{ exercise: 'Air runner', distanceM: 1000, speedKmh: 13.0, machine: 'Air runner' }],
      }],
    });
    const sent: any[] = [];
    const replies = [
      // First answer breaks the 2-3 tips rule; the repair attempt fixes it.
      claudeReply({ feedback: 'Solid session overall.', tips: ['One tip only'] }),
      claudeReply({ feedback: 'Solid session overall.', tips: ['Start at 13.0 km/h, not faster', 'Take the full 1:30 rest', 'Hold cadence on the last rep'] }),
    ];
    const fetchImpl = (async (_url: string, init: RequestInit) => {
      sent.push(JSON.parse(String(init.body)));
      return replies.shift()!;
    }) as unknown as typeof fetch;
    const app = buildApp({
      store, userId: () => USER, vaultKey: randomBytes(32).toString('base64'),
      now: () => new Date('2026-11-23T18:00:00Z'), fetch: fetchImpl,
    });
    await app.inject({ method: 'PUT', url: '/api/v1/credentials/claude', payload: { secret: 'test-claude-key-1234', retention: '7d' } });

    // And a logged result of 0.94, 0.89, 0.90, 0.90 and 0.86 km in 4:10 each
    const logged = await app.inject({
      method: 'POST', url: '/api/v1/results',
      payload: {
        sessionId: 'air-1',
        parts: [0.94, 0.89, 0.9, 0.9, 0.86].map((km, i) => ({ label: `Rep ${i + 1}`, distanceM: km * 1000, timeS: 250 })),
      },
    });
    expect(logged.statusCode).toBe(200);
    const result = logged.json() as Result;

    // When the athlete runs result-analyzer
    const res = await app.inject({
      method: 'POST', url: '/api/v1/runs',
      payload: { node: { kind: 'skill', name: 'result-analyzer' }, provider: 'claude', input: { sessionId: 'air-1', resultId: result.id } },
    });
    const run = res.json() as Run;
    expect(run.status).toBe('succeeded');
    const output = run.output as { feedback: string; tips: string[] };

    // Then the feedback names a fade from 0.94 km to 0.86 km
    expect(output.feedback).toMatch(/fade from 0\.94 km to 0\.86 km/i);
    // And it gives between 2 and 3 tips
    expect(output.tips.length).toBeGreaterThanOrEqual(2);
    expect(output.tips.length).toBeLessThanOrEqual(3);

    // The model saw the plan, the result and the numbers behind the pattern.
    const firstInput = JSON.parse(sent[0].messages[0].content.at(-1).text);
    expect(firstInput.context.session.id).toBe('air-1');
    expect(firstInput.context.result.id).toBe(result.id);
    expect(firstInput.context.analysis.fade).toMatchObject({ fromKm: 0.94, toKm: 0.86 });
    // The feedback is kept with the result.
    const saved = await app.inject({ method: 'GET', url: `/api/v1/results/${result.id}` });
    expect((saved.json() as Result).feedback?.feedback).toBe(output.feedback);
  });
});
