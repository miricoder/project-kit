/** Shared data model (docs/spec.md, Data model). */

export type SessionType = 'gym' | 'track' | 'class' | 'rest';
export type SessionStatus = 'Done' | 'Today' | 'Scheduled' | 'Moved' | 'Skipped';
/** `daily` is the daily push and core block: done every day, never drawn on the card. */
export type SectionKind = 'warmup' | 'strength' | 'engine' | 'core' | 'cooldown' | 'daily';

/** One structured line of a prescription; plain strings are written as they are. */
export interface Item {
  exercise: string;
  distanceM?: number;
  loadKg?: number;
  reps?: number;
  timeS?: number;
  speedKmh?: number;
  machine?: string;
}

export interface Section {
  kind: SectionKind;
  label: string;
  lines: Array<string | Item>;
  /** Rounds of the whole section, when it repeats. */
  rounds?: number;
  /** Rest after each round, in seconds. */
  restS?: number;
}

export interface Session {
  id: string;
  userId: string;
  date: string; // YYYY-MM-DD
  title: string;
  type: SessionType;
  tag?: string;
  sections: Section[];
  notes?: string;
  log?: string;
  status: SessionStatus;
  movedFrom?: string;
  source: 'plan' | 'class';
}

export interface Profile {
  userId: string;
  division: string;
  matLengthM: number;
  restDay: 'Mon' | 'Tue' | 'Wed' | 'Thu' | 'Fri' | 'Sat' | 'Sun';
  units: 'metric';
  goals?: string[];
  equipment?: string[];
}
