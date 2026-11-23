import type { Item, Profile, Section, SectionKind, Session } from './types.ts';

/** A section as drawn on the whiteboard card. */
export interface CardSection {
  kind: Exclude<SectionKind, 'daily'>;
  label: string;
  lines: string[];
  /** What follows what, and exactly where rest goes. */
  flow?: string;
}

export interface Card {
  date: string;
  title: string;
  tag?: string;
  status: Session['status'];
  sections: CardSection[];
  log?: string;
}

const DEFAULT_MAT_M = 12.5;

/** "1:30" for 90 seconds. */
export function formatRest(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = Math.round(seconds % 60);
  return `${m}:${String(s).padStart(2, '0')}`;
}

/** Whole mat lengths plus any remainder: 50 m on 12.5 m = "4 lengths", 80 m = "6 lengths + 5 m". */
export function matLengths(distanceM: number, matM: number = DEFAULT_MAT_M): string {
  const whole = Math.floor(distanceM / matM + 1e-9);
  const rest = Math.round((distanceM - whole * matM) * 10) / 10;
  const lengths = `${whole} ${whole === 1 ? 'length' : 'lengths'}`;
  return rest > 0 ? `${lengths} + ${rest} m` : lengths;
}

function isSled(item: Item): boolean {
  return /sled/i.test(item.exercise);
}

/** The numbers of an item, e.g. "50 m · 4 lengths · 202 kg". */
export function itemLine(item: Item, profile: Profile): string {
  const parts: string[] = [];
  if (item.reps !== undefined) parts.push(`${item.reps} reps`);
  if (item.distanceM !== undefined) {
    parts.push(`${item.distanceM} m`);
    if (isSled(item)) parts.push(matLengths(item.distanceM, profile.matLengthM || DEFAULT_MAT_M));
  }
  if (item.timeS !== undefined) parts.push(formatRest(item.timeS));
  if (item.speedKmh !== undefined) parts.push(`${item.speedKmh.toFixed(1)} km/h`);
  if (item.loadKg !== undefined) parts.push(`${item.loadKg} kg`);
  if (item.machine) parts.push(item.machine);
  return parts.join(' · ');
}

function verb(item: Item): string {
  const m = /sled\s+(push|pull)/i.exec(item.exercise);
  return m ? m[1][0].toUpperCase() + m[1].slice(1) : item.exercise;
}

/** "Push 50 m, rest 1:30, repeat 4 times total." */
function sectionFlow(section: Section): string | undefined {
  if (!section.rounds || section.rounds < 2) return undefined;
  const items = section.lines.filter((l): l is Item => typeof l !== 'string');
  const steps = items.map((i) => (i.distanceM !== undefined ? `${verb(i)} ${i.distanceM} m` : verb(i)));
  const work = steps.length > 1 ? `${steps.join(' then straight into ')}` : steps[0] ?? section.label;
  const rest = section.restS ? `, rest ${formatRest(section.restS)}` : '';
  return `${work}${rest}, repeat ${section.rounds} times total.`;
}

/** Turn a planned session into the card the athlete trains from (workout-whiteboard rules). */
export function buildCard(session: Session, profile: Profile): Card {
  const sections: CardSection[] = session.sections
    .filter((s): s is Section & { kind: CardSection['kind'] } => s.kind !== 'daily')
    .map((s) => ({
      kind: s.kind,
      label: s.label,
      lines: s.lines.map((l) =>
        typeof l === 'string' ? l : `${l.exercise}: ${itemLine(l, profile)}`,
      ),
      flow: sectionFlow(s),
    }));
  return {
    date: session.date,
    title: session.title,
    tag: session.tag,
    status: session.status,
    sections,
    log: session.log,
  };
}
