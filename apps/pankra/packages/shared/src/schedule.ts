import type { Profile, Session } from './types.ts';

/** One session that moved, as reported back to the athlete. */
export interface ScheduleChange {
  sessionId: string;
  title: string;
  from: string;
  to: string;
  /** The session left its Monday-to-Sunday week. */
  intoNextWeek: boolean;
  message: string;
}

export interface ShiftResult {
  /** The inserted session plus every session whose date changed. */
  updated: Session[];
  changes: ScheduleChange[];
}

const WEEKDAYS = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'] as const;
const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

function parse(date: string): Date {
  return new Date(`${date}T00:00:00Z`);
}

export function addDays(date: string, days: number): string {
  const d = parse(date);
  d.setUTCDate(d.getUTCDate() + days);
  return d.toISOString().slice(0, 10);
}

export function weekday(date: string): (typeof WEEKDAYS)[number] {
  return WEEKDAYS[parse(date).getUTCDay()];
}

/** Monday of the date's week (weeks run Monday to Sunday). */
export function weekStart(date: string): string {
  const dow = parse(date).getUTCDay();
  return addDays(date, -((dow + 6) % 7));
}

/** "Sun 29 Nov" */
export function shortDate(date: string): string {
  const d = parse(date);
  return `${weekday(date)} ${d.getUTCDate()} ${MONTHS[d.getUTCMonth()]}`;
}

/** Sessions the shifter may move: planned work not yet done, skipped or a class. */
function movable(s: Session): boolean {
  return s.type !== 'rest' && s.source === 'plan' && (s.status === 'Scheduled' || s.status === 'Today' || s.status === 'Moved');
}

/**
 * Put `inserted` on its date and push every movable session from that date on to the next
 * free day, in order. A day is free when nothing fixed sits on it and it is not a rest day
 * (the profile's rest day, or a day holding a rest session). The athlete's class wins over a
 * planned session on the same day; nothing is ever dropped, a session pushed past Sunday
 * goes into the next week and the change says so.
 */
export function shiftSchedule(sessions: Session[], inserted: Session, profile: Profile): ShiftResult {
  const start = inserted.date;
  const toMove = sessions
    .filter((s) => s.date >= start && movable(s))
    .sort((a, b) => a.date.localeCompare(b.date) || a.id.localeCompare(b.id));
  const moving = new Set(toMove.map((s) => s.id));

  const blocked = new Set<string>([start]);
  for (const s of sessions) if (!moving.has(s.id)) blocked.add(s.date);
  const isFree = (date: string) => !blocked.has(date) && weekday(date) !== profile.restDay;

  const updated: Session[] = [{ ...inserted }];
  const changes: ScheduleChange[] = [];
  let cursor = start;
  for (const s of toMove) {
    // Never earlier than it was planned: a gap in the week absorbs the push.
    const earliest = addDays(cursor, 1);
    let to = earliest > s.date ? earliest : s.date;
    while (!isFree(to)) to = addDays(to, 1);
    cursor = to;
    if (to === s.date) {
      blocked.add(to);
      continue;
    }
    blocked.add(to);
    const intoNextWeek = weekStart(to) !== weekStart(s.date);
    const original = s.movedFrom ?? s.date;
    updated.push({
      ...s,
      date: to,
      status: 'Moved',
      movedFrom: original,
      tag: `Moved from ${weekday(original)}`,
    });
    changes.push({
      sessionId: s.id,
      title: s.title,
      from: s.date,
      to,
      intoNextWeek,
      message: `${s.title}: ${shortDate(s.date)} → ${shortDate(to)}${intoNextWeek ? ' (moved into next week)' : ''}`,
    });
  }
  return { updated, changes };
}
