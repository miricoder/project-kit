import { randomBytes } from 'node:crypto';
import { describe, expect, it } from 'vitest';
import { buildApp } from '../api/src/app.ts';
import { MemoryStore } from '../api/src/store.ts';
import { expireCredentials } from '../api/src/vault.ts';
import { nodeBadge, type NodeSummary } from '../packages/shared/src/index.ts';

const USER = 'owner';
const VAULT_KEY = randomBytes(32).toString('base64');

/** The result-analyzer node as the registry describes it (requires an API key). */
const resultAnalyzer: NodeSummary = {
  kind: 'skill',
  name: 'result-analyzer',
  version: '0.1.0',
  providers: { claude: { model: 'claude-sonnet-5-5' }, gpt: { model: 'gpt-5' } },
  requires: ['apiKey'],
};

function setup(start: string) {
  let now = new Date(start);
  const store = new MemoryStore();
  const app = buildApp({ store, userId: () => USER, vaultKey: VAULT_KEY, now: () => now });
  return { store, app, setNow: (t: string) => (now = new Date(t)), now: () => now };
}

describe('LLM providers and keys', () => {
  it('Scenario: expired key is deleted', async () => {
    // Given a Claude key saved at 2026-11-23 09:00 with 7-day retention
    const { store, app, setNow, now } = setup('2026-11-23T09:00:00Z');
    const secret = 'sk-ant-test-0000000000001234';
    const put = await app.inject({
      method: 'PUT',
      url: '/api/v1/credentials/claude',
      payload: { secret, retention: '7d' },
    });
    expect(put.statusCode).toBe(200);
    expect(put.json()).toEqual({ last4: '1234', expiresAt: '2026-11-30T09:00:00.000Z' });
    // The key is stored encrypted, never as plain text.
    expect(JSON.stringify(store.dump())).not.toContain(secret);

    // When the time is 2026-11-30 09:15 (the expiry job runs every 15 minutes)
    setNow('2026-11-30T09:15:00Z');
    expireCredentials(store, now());

    // Then no Claude key is stored
    expect(store.getCredential(USER, 'claude')).toBeUndefined();
    const status = await app.inject({ method: 'GET', url: '/api/v1/credentials' });
    expect(status.json()).toEqual([]);
    // And the audit log has a "keyDeleted" entry
    expect(store.listAudit(USER)).toContainEqual(
      expect.objectContaining({ action: 'keyDeleted', detail: expect.objectContaining({ provider: 'claude', reason: 'expired' }) }),
    );
    // And the result-analyzer node shows amber for claude
    const creds = store.listCredentials(USER);
    expect(nodeBadge(resultAnalyzer, 'claude', creds)).toBe('amber');
  });

  it('Scenario: a key is deleted on request', async () => {
    // Given a GPT key is saved with retention "until deleted"
    const { store, app } = setup('2026-11-23T09:00:00Z');
    const put = await app.inject({
      method: 'PUT',
      url: '/api/v1/credentials/gpt',
      payload: { secret: 'sk-proj-test-00000000000abcd', retention: 'forever' },
    });
    expect(put.statusCode).toBe(200);
    expect(put.json()).toEqual({ last4: 'abcd', expiresAt: null });
    expect(nodeBadge(resultAnalyzer, 'gpt', store.listCredentials(USER))).toBe('green');

    // When the athlete taps Delete key now for gpt
    const del = await app.inject({ method: 'DELETE', url: '/api/v1/credentials/gpt' });
    expect(del.statusCode).toBe(204);

    // Then no GPT key is stored
    expect(store.getCredential(USER, 'gpt')).toBeUndefined();
    // And the audit log has a "keyDeleted" entry
    expect(store.listAudit(USER)).toContainEqual(
      expect.objectContaining({ action: 'keyDeleted', detail: expect.objectContaining({ provider: 'gpt', reason: 'requested' }) }),
    );
  });
});
