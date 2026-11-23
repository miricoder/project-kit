import { describe, expect, it } from 'vitest';
import { buildApp } from '../api/src/app.ts';
import { MemoryStore } from '../api/src/store.ts';
import type { Profile, Session, ScheduleChange } from '../packages/shared/src/index.ts';

const USER = 'owner';

const profile: Profile = {
  userId: USER,
  division: "Men's Pro",
  matLengthM: 12.5,
  restDay: 'Sat',
  units: 'metric',
};

function planned(date: string, title: string): Session {
  return {
    id: `plan-${date}`,
    userId: USER,
    date,
    title,
    type: 'gym',
    status: 'Scheduled',
    source: 'plan',
    sections: [{ kind: 'engine', label: title, lines: ['as planned'] }],
  };
}

function rest(date: string): Session {
  return { ...planned(date, 'Rest'), id: `rest-${date}`, type: 'rest', sections: [] };
}

/** Sessions planned Tue 24, Wed 25, Thu 26, Fri 27 and Sun 29 Nov, with Sat 28 as rest. */
function weekOf23Nov(): MemoryStore {
  const store = new MemoryStore();
  store.saveProfile(profile);
  store.saveSession(planned('2026-11-24', 'Tue sled'));
  store.saveSession(planned('2026-11-25', 'Wed intervals'));
  store.saveSession(planned('2026-11-26', 'Thu strength'));
  store.saveSession(planned('2026-11-27', 'Fri engine'));
  store.saveSession(rest('2026-11-28'));
  store.saveSession(planned('2026-11-29', 'Sun long run'));
  return store;
}

const boxClass = {
  title: 'Box class: HYROX conditioning',
  type: 'class' as const,
  sections: [{ kind: 'engine' as const, label: 'Class', lines: ['60 min class at the box'] }],
};

async function addClassOnTue(store: MemoryStore) {
  const app = buildApp({ store, userId: () => USER });
  const res = await app.inject({
    method: 'POST',
    url: '/api/v1/sessions/insert',
    payload: { date: '2026-11-24', session: boxClass },
  });
  expect(res.statusCode).toBe(200);
  const { changes } = res.json() as { changes: ScheduleChange[] };
  const week = await app.inject({
    method: 'GET',
    url: '/api/v1/sessions?from=2026-11-23&to=2026-12-06',
  });
  return { changes, sessions: week.json() as Session[] };
}

function on(sessions: Session[], date: string): Session[] {
  return sessions.filter((s) => s.date === date);
}

describe('Training plan as whiteboard cards', () => {
  it('Scenario: adding a class moves later sessions', async () => {
    // Given sessions planned Tue 24, Wed 25, Thu 26, Fri 27 and Sun 29 Nov, with Sat 28 as rest
    const store = weekOf23Nov();
    // When the athlete adds a box class on Tue 24 Nov
    const { sessions } = await addClassOnTue(store);

    // Then Tue 24 shows the class
    const tue = on(sessions, '2026-11-24');
    expect(tue).toHaveLength(1);
    expect(tue[0].title).toBe(boxClass.title);
    expect(tue[0].source).toBe('class');

    // And the Tue session shows on Wed 25 with status "Moved"
    const wed = on(sessions, '2026-11-25');
    expect(wed).toHaveLength(1);
    expect(wed[0].title).toBe('Tue sled');
    expect(wed[0].status).toBe('Moved');
    expect(wed[0].movedFrom).toBe('2026-11-24');

    // And the Fri session shows on Sun 29
    const sun = on(sessions, '2026-11-29');
    expect(sun.map((s) => s.title)).toEqual(['Fri engine']);

    // And Sat 28 is still a rest day
    const sat = on(sessions, '2026-11-28');
    expect(sat).toHaveLength(1);
    expect(sat[0].type).toBe('rest');
  });

  it('Scenario: a pushed session crosses into next week', async () => {
    // Given the Sun 29 Nov session is the last planned session of the week
    const store = weekOf23Nov();
    // When a class is added on Tue 24 Nov
    const { changes, sessions } = await addClassOnTue(store);

    // Then the Sun 29 Nov session moves to Mon 30 Nov
    const mon = on(sessions, '2026-11-30');
    expect(mon.map((s) => s.title)).toEqual(['Sun long run']);
    expect(mon[0].movedFrom).toBe('2026-11-29');

    // And the change list says it moved into next week
    const change = changes.find((c) => c.title === 'Sun long run');
    expect(change).toMatchObject({ from: '2026-11-29', to: '2026-11-30', intoNextWeek: true });
    expect(change?.message).toMatch(/into next week/);
    // No other session left the week.
    expect(changes.filter((c) => c.intoNextWeek)).toHaveLength(1);
  });
});
