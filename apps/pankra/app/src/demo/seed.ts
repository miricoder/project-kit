import { addDays, weekStart, type Profile, type Race, type Result, type Session } from '@pankra/shared';

export const DEMO_USER = 'preview';

/** Sample data for the browser preview, placed on the viewer's current week. */
export function seed(today: string) {
  const mon = weekStart(today);
  const d = (i: number) => addDays(mon, i);
  const status = (date: string): Session['status'] => (date < today ? 'Done' : date === today ? 'Today' : 'Scheduled');
  const base = { userId: DEMO_USER, source: 'plan' as const };

  const profile: Profile = {
    userId: DEMO_USER,
    division: "Men's Pro",
    matLengthM: 12.5,
    restDay: 'Sat',
    units: 'metric',
    raceTargetS: 3600,
    goals: ['Sub-60 Hyrox Pro'],
  };

  const sessions: Session[] = [
    {
      ...base, id: 'demo-mon', date: d(0), status: status(d(0)), type: 'gym', title: 'Air runner intervals', tag: 'Race pace',
      log: 'distance per rep, how the last two felt',
      sections: [
        { kind: 'warmup', label: 'Warm-up', lines: ['10 min easy on the Air runner', 'Leg swings, A-skips'] },
        { kind: 'engine', label: 'Intervals', rounds: 5, restS: 90, lines: [{ exercise: 'Air runner', distanceM: 1000, speedKmh: 13.0, machine: 'Air runner' }] },
        { kind: 'cooldown', label: 'Cool-down', lines: ['5 min walk'] },
        { kind: 'daily', label: 'Daily push and core', lines: ['50 push-ups', '3 min plank'] },
      ],
    },
    {
      ...base, id: 'demo-tue', date: d(1), status: status(d(1)), type: 'gym', title: 'Sled strength', tag: 'Pro weights',
      log: 'sled load, time per 50 m',
      sections: [
        { kind: 'warmup', label: 'Warm-up', lines: ['8 min row, easy', 'Hip openers'] },
        { kind: 'strength', label: 'Sled push', rounds: 4, restS: 90, lines: [{ exercise: 'Sled push', distanceM: 50, loadKg: 202 }] },
        { kind: 'strength', label: 'Sled pull', rounds: 4, restS: 90, lines: [{ exercise: 'Sled pull', distanceM: 50, loadKg: 153 }] },
        { kind: 'core', label: 'Core', lines: ['3 x 40 s hollow hold'] },
        { kind: 'daily', label: 'Daily push and core', lines: ['50 push-ups'] },
      ],
    },
    {
      ...base, id: 'demo-wed', date: d(2), status: status(d(2)), type: 'track', title: 'Threshold 4 x 2 km', tag: 'Engine',
      sections: [{ kind: 'engine', label: 'Track', rounds: 4, restS: 120, lines: [{ exercise: 'Track run', distanceM: 2000, speedKmh: 14.4 }] }],
    },
    {
      ...base, id: 'demo-thu', date: d(3), status: status(d(3)), type: 'gym', title: 'Wall balls and lunges', tag: 'Station work',
      sections: [
        { kind: 'engine', label: 'Stations', rounds: 3, restS: 60, lines: [{ exercise: 'Wall balls', reps: 30, loadKg: 9 }, { exercise: 'Sandbag lunges', distanceM: 50, loadKg: 30 }] },
      ],
    },
    {
      ...base, id: 'demo-fri', date: d(4), status: status(d(4)), type: 'gym', title: 'SkiErg and row', tag: 'Engine',
      sections: [{ kind: 'engine', label: 'Erg pairs', rounds: 4, restS: 90, lines: [{ exercise: 'SkiErg', distanceM: 500 }, { exercise: 'Row', distanceM: 500 }] }],
    },
    { ...base, id: 'demo-sat', date: d(5), status: status(d(5)), type: 'rest', title: 'Rest', sections: [] },
    {
      ...base, id: 'demo-sun', date: d(6), status: status(d(6)), type: 'track', title: 'Long run 16 km', tag: 'Aerobic base',
      sections: [{ kind: 'engine', label: 'Run', lines: [{ exercise: 'Easy run', distanceM: 16000, speedKmh: 11.5 }] }],
    },
  ];

  // Monday's intervals already logged: the fade result-analyzer is built to spot.
  const results: Result[] = [
    {
      id: 'demo-res-mon', userId: DEMO_USER, sessionId: 'demo-mon', uploadIds: [], createdAt: `${d(0)}T18:00:00.000Z`,
      parts: [0.94, 0.89, 0.9, 0.9, 0.86].map((km, i) => ({ label: `Rep ${i + 1}`, distanceM: Math.round(km * 1000), timeS: 250 })),
      notes: 'Last rep was hard.',
    },
  ];

  const races: Race[] = [
    {
      id: 'demo-race', userId: DEMO_USER, event: 'HYROX Hamburg (sample)', date: addDays(mon, -21), division: "Men's Pro",
      runs: [299, 281, 284, 290, 287, 295, 298, 306],
      stations: [261, 238, 312, 275, 280, 118, 289, 381],
      roxzoneS: 390,
      totalS: 2340 + 2154 + 390,
      createdAt: `${addDays(mon, -21)}T12:00:00.000Z`,
    },
  ];

  return { profile, sessions, results, races };
}
