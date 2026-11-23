import type { Extracted, ExtractedField, Race, RaceAnalysis, RaceDraft, RaceSegment } from './types.ts';

/** The 8 Hyrox stations in race order. */
export const STATIONS = [
  'SkiErg',
  'Sled Push',
  'Sled Pull',
  'Burpee Broad Jump',
  'Rowing',
  'Farmers Carry',
  'Sandbag Lunges',
  'Wall Balls',
] as const;

const RUNS = Array.from({ length: 8 }, (_, i) => `Running ${i + 1}`);

/** "00:02:59", "2:59", "1:20:26" -> seconds; undefined when it is not a time. */
export function parseDuration(text: string): number | undefined {
  const m = /^\s*(?:(\d{1,2}):)?(\d{1,2}):(\d{2})(?:\.\d+)?\s*$/.exec(text);
  if (!m) return undefined;
  const [h, min, s] = [Number(m[1] ?? 0), Number(m[2]), Number(m[3])];
  if (s >= 60 || (m[1] !== undefined && min >= 60)) return undefined;
  return h * 3600 + min * 60 + s;
}

/** 179 -> "2:59", 4826 -> "1:20:26" */
export function formatDuration(seconds: number): string {
  const sign = seconds < 0 ? '-' : '';
  const t = Math.abs(Math.round(seconds));
  const h = Math.floor(t / 3600);
  const m = Math.floor((t % 3600) / 60);
  const s = String(t % 60).padStart(2, '0');
  return h > 0 ? `${sign}${h}:${String(m).padStart(2, '0')}:${s}` : `${sign}${m}:${s}`;
}

const norm = (label: string) => label.toLowerCase().replace(/[^a-z0-9]/g, '');

/** Labels a results screen may use for the same segment. */
const ALIASES: Record<string, string> = {
  ...Object.fromEntries(RUNS.map((r, i) => [norm(r), r]).concat(RUNS.map((r, i) => [`run${i + 1}`, r]))),
  ...Object.fromEntries(STATIONS.map((s) => [norm(s), s])),
  row: 'Rowing',
  burpeebroadjumps: 'Burpee Broad Jump',
  farmerscarry: 'Farmers Carry',
  farmercarry: 'Farmers Carry',
  sandbaglunge: 'Sandbag Lunges',
  wallball: 'Wall Balls',
  roxzone: 'Roxzone',
  roxzonetime: 'Roxzone',
  total: 'Total',
  totaltime: 'Total',
  finishtime: 'Total',
};

/**
 * Turn screenshot-reader's output into fields to confirm and, when every split is there, a
 * race draft. Times are parsed in code; nothing is estimated or filled in.
 */
export function raceFromScreen(
  data: Record<string, unknown>,
  uncertain: Array<{ field?: string; seen?: string }>,
  defaults: { date: string; division?: string },
): Extracted {
  const unsure = new Map(uncertain.filter((u) => u.field).map((u) => [norm(u.field!), u.seen]));
  const fields: ExtractedField[] = [];
  const seconds = new Map<string, number>();
  const text = new Map<string, string>();

  for (const [rawLabel, rawValue] of Object.entries(data ?? {})) {
    const label = ALIASES[norm(rawLabel)] ?? rawLabel;
    const value = String(rawValue ?? '').trim();
    const s = parseDuration(value);
    const field: ExtractedField = {
      label,
      text: s !== undefined ? formatDuration(s) : value,
      uncertain: unsure.has(norm(rawLabel)),
    };
    if (s !== undefined) {
      field.seconds = s;
      seconds.set(label, s);
    } else {
      text.set(label, value);
    }
    const seen = unsure.get(norm(rawLabel));
    if (seen) field.seen = seen;
    fields.push(field);
  }

  const needed = [...RUNS, ...STATIONS, 'Roxzone'];
  const missing = needed.filter((n) => !seconds.has(n));
  const extracted: Extracted = { kind: 'race', fields, missing };
  if (missing.length === 0) {
    const runs = RUNS.map((r) => seconds.get(r)!);
    const stations = STATIONS.map((s) => seconds.get(s)!);
    const roxzoneS = seconds.get('Roxzone')!;
    const sum = runs.reduce((a, b) => a + b, 0) + stations.reduce((a, b) => a + b, 0) + roxzoneS;
    extracted.race = {
      event: text.get('Event') ?? 'Hyrox',
      date: text.get('Date') ?? defaults.date,
      division: text.get('Division') ?? defaults.division ?? '',
      runs,
      stations,
      roxzoneS,
      totalS: seconds.get('Total') ?? sum,
    } satisfies RaceDraft;
  }
  return extracted;
}

/**
 * Seconds to gain per segment against a target time. The target is split in proportion to
 * the athlete's own race (largest remainder, so the parts add up to the target exactly):
 * a model to aim at, shown as such.
 */
export function analyzeRace(race: Race, targetS: number): RaceAnalysis {
  const actual: Array<{ name: string; s: number }> = [
    ...STATIONS.map((name, i) => ({ name: name as string, s: race.stations[i] })),
    { name: 'Runs', s: race.runs.reduce((a, b) => a + b, 0) },
    { name: 'Roxzone', s: race.roxzoneS },
  ];
  const total = actual.reduce((a, x) => a + x.s, 0);
  const exact = actual.map((x) => (x.s * targetS) / total);
  const floors = exact.map(Math.floor);
  let left = targetS - floors.reduce((a, b) => a + b, 0);
  const byRemainder = exact.map((e, i) => ({ i, r: e - Math.floor(e) })).sort((a, b) => b.r - a.r);
  for (const { i } of byRemainder) {
    if (left <= 0) break;
    floors[i]++;
    left--;
  }
  const segments: RaceSegment[] = actual
    .map((x, i) => ({ name: x.name, actualSeconds: x.s, targetSeconds: floors[i], gainSeconds: x.s - floors[i] }))
    .sort((a, b) => b.gainSeconds - a.gainSeconds || a.name.localeCompare(b.name));
  return {
    raceId: race.id,
    totalS: total,
    targetS,
    model: 'Target split in proportion to this race',
    segments,
  };
}
