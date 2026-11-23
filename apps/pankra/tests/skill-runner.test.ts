import { randomBytes } from 'node:crypto';
import { describe, expect, it } from 'vitest';
import { buildApp } from '../api/src/app.ts';
import { MemoryStore } from '../api/src/store.ts';
import type { RegistryNode, Run } from '../packages/shared/src/index.ts';

const USER = 'owner';
const VAULT_KEY = randomBytes(32).toString('base64');
const NOW = new Date('2026-11-23T10:00:00Z');

const resultAnalyzer: RegistryNode = {
  kind: 'skill',
  name: 'result-analyzer',
  version: '0.1.0',
  description: 'Analyses a logged workout against the prescription.',
  files: { 'SKILL.md': '# Result analyzer\nCompare the result with the plan. Give 2-3 tips.' },
  providers: { claude: { model: 'claude-sonnet-5-5' }, gpt: { model: 'gpt-5' } },
  requires: ['apiKey'],
  vision: false,
  tools: [],
  input: { type: 'object', properties: { sessionId: { type: 'string' } }, required: ['sessionId'] },
  output: {
    type: 'object',
    properties: {
      feedback: { type: 'string' },
      tips: { type: 'array', items: { type: 'string' } },
    },
    required: ['feedback', 'tips'],
  },
  retired: false,
};

const GOOD = { feedback: 'Steady pace, slight fade.', tips: ['Start slower', 'Hold 13.0 km/h'] };
const NO_TIPS = { feedback: 'Steady pace.' };

type Reply = { status: number; body: unknown };

/** Stands in for the providers' HTTPS APIs and records every request sent. */
function fakeProviders(replies: Record<'claude' | 'gpt', Reply[]>) {
  const calls: Array<{ provider: 'claude' | 'gpt'; url: string; headers: Record<string, string>; body: any }> = [];
  const fetchImpl = async (url: string | URL, init?: RequestInit) => {
    const u = String(url);
    const provider = u.startsWith('https://api.anthropic.com/') ? 'claude' : u.startsWith('https://api.openai.com/') ? 'gpt' : null;
    if (!provider) throw new Error(`unexpected request to ${u}`);
    calls.push({ provider, url: u, headers: init?.headers as Record<string, string>, body: JSON.parse(String(init?.body)) });
    const r = replies[provider].shift();
    if (!r) throw new Error(`no reply queued for ${provider}`);
    return new Response(JSON.stringify(r.body), { status: r.status, headers: { 'content-type': 'application/json' } });
  };
  return { calls, fetchImpl: fetchImpl as typeof fetch };
}

function claudeOk(output: unknown): Reply {
  return {
    status: 200,
    body: {
      id: 'msg_1',
      type: 'message',
      model: 'claude-sonnet-5-5',
      content: [{ type: 'tool_use', id: 'tu_1', name: 'output', input: output }],
      stop_reason: 'tool_use',
      usage: { input_tokens: 1200, output_tokens: 300 },
    },
  };
}

function gptOk(output: unknown): Reply {
  return {
    status: 200,
    body: {
      id: 'resp_1',
      object: 'response',
      model: 'gpt-5',
      status: 'completed',
      output: [{ type: 'message', role: 'assistant', content: [{ type: 'output_text', text: JSON.stringify(output) }] }],
      usage: { input_tokens: 1100, output_tokens: 250 },
    },
  };
}

async function setup(keys: Array<'claude' | 'gpt'>, replies: Record<'claude' | 'gpt', Reply[]>) {
  const store = new MemoryStore();
  store.saveNode(resultAnalyzer);
  store.saveSession({
    id: 'sess-1', userId: USER, date: '2026-11-23', title: 'Air runner 5 x 1 km', type: 'gym',
    status: 'Today', source: 'plan', sections: [],
  });
  const providers = fakeProviders(replies);
  const app = buildApp({ store, userId: () => USER, vaultKey: VAULT_KEY, now: () => NOW, fetch: providers.fetchImpl });
  for (const p of keys) {
    const res = await app.inject({
      method: 'PUT', url: `/api/v1/credentials/${p}`,
      payload: { secret: `test-${p}-key-000000wxyz`, retention: '7d' },
    });
    expect(res.statusCode).toBe(200);
  }
  const run = (provider: 'claude' | 'gpt') =>
    app.inject({
      method: 'POST', url: '/api/v1/runs',
      payload: { node: { kind: 'skill', name: 'result-analyzer' }, provider, input: { sessionId: 'sess-1' } },
    });
  return { store, app, calls: providers.calls, run };
}

describe('LLM providers and keys', () => {
  describe('Scenario Outline: a skill runs on either provider', () => {
    for (const provider of ['claude', 'gpt'] as const) {
      it(`Scenario: a skill runs on either provider (${provider})`, async () => {
        // Given a valid <provider> key is saved
        const { run, store, calls } = await setup([provider], {
          claude: [claudeOk(GOOD)],
          gpt: [gptOk(GOOD)],
        });
        // When the athlete runs result-analyzer on <provider>
        const res = await run(provider);
        expect(res.statusCode).toBe(200);
        const body = res.json() as Run;
        // Then the run is saved with provider "<provider>" and a model name
        expect(body.status).toBe('succeeded');
        expect(body.output).toEqual(GOOD);
        const saved = store.getRun(USER, body.id)!;
        expect(saved.provider).toBe(provider);
        expect(saved.model).toBe(provider === 'claude' ? 'claude-sonnet-5-5' : 'gpt-5');
        expect(saved.nodeRef).toEqual({ kind: 'skill', name: 'result-analyzer', version: '0.1.0' });
        expect(saved.tokens.in).toBeGreaterThan(0);
        expect(saved.costUsd).toBeGreaterThan(0);
        // The key reached the provider in its auth header and is not kept in the run.
        expect(calls).toHaveLength(1);
        const auth = provider === 'claude' ? calls[0].headers['x-api-key'] : calls[0].headers.authorization;
        expect(auth).toContain(`test-${provider}-key-000000wxyz`);
        expect(JSON.stringify(saved)).not.toContain('000000wxyz');
      });
    }
  });

  it('Scenario: missing key blocks a run', async () => {
    // Given a GPT key is saved and no Claude key is saved
    const { run, calls, store } = await setup(['gpt'], { claude: [claudeOk(GOOD)], gpt: [gptOk(GOOD)] });
    // When the athlete runs result-analyzer on claude
    const res = await run('claude');
    // Then the run panel asks for a Claude key
    expect(res.statusCode).toBe(409);
    expect(res.json()).toMatchObject({ needs: { credential: 'claude' }, error: 'Add a Claude key to run this' });
    // And no request is sent to any provider
    expect(calls).toHaveLength(0);
    expect(store.listRuns(USER)).toHaveLength(0);
  });

  it('Scenario: provider failure leaves no partial result', async () => {
    // Given the Claude API returns HTTP 529
    const { run, store } = await setup(['claude'], {
      claude: [{ status: 529, body: { type: 'error', error: { type: 'overloaded_error', message: 'Overloaded' } } }],
      gpt: [],
    });
    const before = JSON.stringify({ s: store.dump().sessions, r: store.dump().results });
    // When the athlete runs result-analyzer on claude
    const res = await run('claude');
    // Then the run shows status "failed" with the provider message
    const body = res.json() as Run;
    expect(body.status).toBe('failed');
    expect(body.error).toContain('Overloaded');
    expect(body.output).toBeUndefined();
    expect(store.getRun(USER, body.id)?.status).toBe('failed');
    // And no result or session is changed
    expect(JSON.stringify({ s: store.dump().sessions, r: store.dump().results })).toBe(before);
  });

  it('Scenario: invalid model output is not saved', async () => {
    // Given the provider returns output missing the required "tips" field twice
    const { run, store, calls } = await setup(['claude'], {
      claude: [claudeOk(NO_TIPS), claudeOk(NO_TIPS)],
      gpt: [],
    });
    const before = JSON.stringify({ s: store.dump().sessions, r: store.dump().results });
    // When the athlete runs result-analyzer
    const res = await run('claude');
    // Then the run shows status "failed"
    const body = res.json() as Run;
    expect(body.status).toBe('failed');
    expect(body.error).toMatch(/tips/);
    expect(body.output).toBeUndefined();
    // One automatic repair attempt was made.
    expect(calls).toHaveLength(2);
    // And nothing is written to results or sessions
    expect(JSON.stringify({ s: store.dump().sessions, r: store.dump().results })).toBe(before);
  });

  it('Scenario: cost cap stops runs', async () => {
    // Given a monthly cap of $10 for claude and $10.02 already spent this month
    const { run, store, calls, app } = await setup(['claude'], { claude: [claudeOk(GOOD)], gpt: [] });
    const cap = await app.inject({ method: 'PUT', url: '/api/v1/caps/claude', payload: { monthlyUsd: 10 } });
    expect(cap.statusCode).toBe(200);
    store.saveRun({
      id: 'earlier', userId: USER, nodeRef: { kind: 'skill', name: 'result-analyzer', version: '0.1.0' },
      provider: 'claude', model: 'claude-sonnet-5-5', input: {}, tokens: { in: 1, out: 1 },
      costUsd: 10.02, status: 'succeeded', createdAt: '2026-11-05T08:00:00.000Z',
    });
    // When the athlete runs result-analyzer on claude
    const res = await run('claude');
    // Then the run is refused with "Monthly cap reached"
    expect(res.statusCode).toBe(409);
    expect(res.json().error).toContain('Monthly cap reached');
    expect(calls).toHaveLength(0);
  });
});
