import { describe, expect, it } from 'vitest';
import { buildApp } from '../api/src/app.ts';
import { MemoryStore } from '../api/src/store.ts';
import { buildCard } from '../packages/shared/src/index.ts';
import type { Profile, Session } from '../packages/shared/src/index.ts';

const USER = 'owner';

function profile(): Profile {
  return {
    userId: USER,
    division: "Men's Pro",
    matLengthM: 12.5,
    restDay: 'Sat',
    units: 'metric',
  };
}

function sledSession(): Session {
  return {
    id: 's-2026-11-25',
    userId: USER,
    date: '2026-11-25',
    title: 'Sled strength',
    type: 'gym',
    status: 'Scheduled',
    source: 'plan',
    sections: [
      { kind: 'warmup', label: 'Warm-up', lines: ['10 min easy row'] },
      {
        kind: 'strength',
        label: 'Sled push',
        rounds: 4,
        restS: 90,
        lines: [{ exercise: 'Sled push', distanceM: 50, loadKg: 202 }],
      },
      { kind: 'daily', label: 'Daily push and core', lines: ['50 push-ups', '3 min plank'] },
    ],
  };
}

describe('Training plan as whiteboard cards', () => {
  it('Scenario: a session shows as a fully spelled-out card', async () => {
    // Given a gym session on 2026-11-25 with 4 rounds of 50 m sled push at 202 kg
    // And the profile sled mat is 12.5 m
    const store = new MemoryStore();
    store.saveProfile(profile());
    store.saveSession(sledSession());
    const app = buildApp({ store, userId: () => USER });

    // When the athlete opens Today on 2026-11-25
    const res = await app.inject({
      method: 'GET',
      url: '/api/v1/sessions?from=2026-11-25&to=2026-11-25',
    });
    expect(res.statusCode).toBe(200);
    const sessions = res.json() as Session[];
    expect(sessions).toHaveLength(1);
    const card = buildCard(sessions[0], profile());
    const text = card.sections.flatMap((s) => [s.label, ...s.lines, s.flow ?? '']).join('\n');

    // Then the card shows "50 m · 4 lengths · 202 kg"
    expect(text).toContain('50 m · 4 lengths · 202 kg');
    // And the card shows where the 1:30 rest goes
    const sled = card.sections.find((s) => s.label === 'Sled push');
    expect(sled?.flow).toBe('Push 50 m, rest 1:30, repeat 4 times total.');
    // And the card shows no daily push and core block
    expect(card.sections.map((s) => s.kind)).not.toContain('daily');
    expect(text).not.toMatch(/push and core/i);
    expect(text).not.toContain('50 push-ups');
  });
});
