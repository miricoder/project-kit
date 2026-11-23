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

export type Provider = 'claude' | 'gpt';
export type CredentialProvider = Provider | 'strava';
/** How long a saved key is kept: this session (12 h), 24 hours, 7 days, 30 days, until deleted. */
export type Retention = 'session' | '24h' | '7d' | '30d' | 'forever';

/** A stored secret. Only the API sees it; `ciphertext` is AES-256-GCM. */
export interface Credential {
  userId: string;
  provider: CredentialProvider;
  ciphertext: string; // base64
  iv: string; // base64, 96-bit
  authTag: string; // base64
  last4: string;
  retention: Retention;
  expiresAt: string | null; // ISO time, null for "until deleted"
  createdAt: string;
}

/** What the app may see of a credential. */
export interface CredentialStatus {
  provider: CredentialProvider;
  last4: string;
  retention: Retention;
  expiresAt: string | null;
}

export type AuditAction = 'keyAdded' | 'keyDeleted' | 'retentionChanged' | 'registrySynced';

export interface AuditEntry {
  userId: string;
  action: AuditAction;
  at: string;
  detail: Record<string, unknown>;
}

/** The parts of a registry node the app needs to show and run it. */
export interface NodeSummary {
  kind: 'skill' | 'agent' | 'plugin' | 'provider';
  name: string;
  version: string;
  description?: string;
  providers: Partial<Record<Provider, { model: string }>>;
  requires: string[];
}

export type JSONSchema = Record<string, unknown>;

/** A registry node as stored by the API (a versioned copy of project-kit's registry/). */
export interface RegistryNode extends NodeSummary {
  /** Text of the node's files, keyed by file name (SKILL.md, AGENT.md, ...). */
  files: Record<string, string>;
  vision: boolean;
  tools: string[];
  input: JSONSchema;
  output?: JSONSchema;
  /** Agents: the skills they run, in order. */
  steps?: Array<{ skill: string; order: number }>;
  retired: boolean;
}

export type RunStatus = 'succeeded' | 'failed';

export interface Run {
  id: string;
  userId: string;
  nodeRef: { kind: NodeSummary['kind']; name: string; version: string };
  provider: Provider;
  model: string;
  input: unknown;
  output?: unknown;
  tokens: { in: number; out: number };
  costUsd: number;
  status: RunStatus;
  error?: string;
  createdAt: string;
}

export interface ResultPart {
  label: string;
  loadKg?: number;
  reps?: number;
  timeS?: number;
  distanceM?: number;
  speedKmh?: number;
  rpe?: number;
}

/** What result-analyzer said about a result, kept with it. */
export interface ResultFeedback {
  runId: string;
  feedback: string;
  tips: string[];
  prs?: string[];
  adjustments?: Array<{ sessionId?: string; change?: string }>;
}

export interface Result {
  id: string;
  userId: string;
  sessionId: string;
  parts: ResultPart[];
  notes?: string;
  uploadIds: string[];
  feedback?: ResultFeedback;
  createdAt: string;
}
