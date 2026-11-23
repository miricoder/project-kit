import type {
  Activity,
  AuditEntry,
  Credential,
  CredentialProvider,
  Edge,
  NodeSummary,
  Profile,
  Provider,
  Race,
  RegistryNode,
  Result,
  Run,
  Session,
  SyncReport,
  Upload,
} from '@pankra/shared';

/** Persistence for the training API. MongoDB implements it once the owner's cluster exists. */
export interface Store {
  getProfile(userId: string): Profile | undefined;
  saveProfile(profile: Profile): void;
  listSessions(userId: string, from: string, to: string): Session[];
  saveSession(session: Session): void;
  getSession(userId: string, id: string): Session | undefined;
  getResult(userId: string, id: string): Result | undefined;
  latestResultFor(userId: string, sessionId: string): Result | undefined;
  saveResult(result: Result): void;
  getCredential(userId: string, provider: CredentialProvider): Credential | undefined;
  listCredentials(userId: string): Credential[];
  allCredentials(): Credential[];
  saveCredential(credential: Credential): void;
  deleteCredential(userId: string, provider: CredentialProvider): boolean;
  addAudit(entry: AuditEntry): void;
  listAudit(userId: string): AuditEntry[];
  /** Latest non-retired version unless a version is named. */
  getNode(kind: NodeSummary['kind'], name: string, version?: string): RegistryNode | undefined;
  listNodes(): RegistryNode[];
  saveNode(node: RegistryNode): void;
  getRun(userId: string, id: string): Run | undefined;
  listRuns(userId: string): Run[];
  saveRun(run: Run): void;
  /** Monthly spending cap in USD per provider; undefined means no cap. */
  getCap(userId: string, provider: Provider): number | undefined;
  setCap(userId: string, provider: Provider, monthlyUsd: number): void;
  listEdges(): Edge[];
  saveEdges(edges: Edge[]): void;
  getRegistryState(): RegistryState;
  setRegistryState(state: RegistryState): void;
  getUpload(userId: string, id: string): Upload | undefined;
  saveUpload(upload: Upload): void;
  getRace(userId: string, id: string): Race | undefined;
  listRaces(userId: string): Race[];
  saveRace(race: Race): void;
  listActivities(userId: string): Activity[];
  /** Insert or replace, unique on source + externalId: a repeated import changes nothing. */
  upsertActivity(activity: Activity): Activity;
  deleteActivity(userId: string, source: Activity['source'], externalId: string): void;
  /** Which user a Strava athlete id belongs to (the tokens themselves are in the vault). */
  linkStravaAthlete(userId: string, athleteId: number): void;
  userForStravaAthlete(athleteId: number): string | undefined;
}

export interface RegistryState {
  lastAttemptAt: string | null;
  lastSuccessAt: string | null;
  lastError: string | null;
  lastReport: SyncReport | null;
}

/** Compare dotted versions numerically: 0.10.0 > 0.9.1. */
export function compareVersions(a: string, b: string): number {
  const pa = a.split('.').map((x) => parseInt(x, 10) || 0);
  const pb = b.split('.').map((x) => parseInt(x, 10) || 0);
  for (let i = 0; i < Math.max(pa.length, pb.length); i++) {
    const d = (pa[i] ?? 0) - (pb[i] ?? 0);
    if (d !== 0) return d;
  }
  return 0;
}

/** In-memory store: tests and local development without a database. */
export class MemoryStore implements Store {
  private profiles = new Map<string, Profile>();
  private sessions = new Map<string, Session>();
  private credentials = new Map<string, Credential>();
  private audit: AuditEntry[] = [];
  private nodes = new Map<string, RegistryNode>();
  private runs = new Map<string, Run>();
  private results = new Map<string, Result>();
  private caps = new Map<string, number>();
  private edges: Edge[] = [];
  private registryState: RegistryState = { lastAttemptAt: null, lastSuccessAt: null, lastError: null, lastReport: null };
  private uploads = new Map<string, Upload>();
  private races = new Map<string, Race>();
  private activities = new Map<string, Activity>();
  private stravaAthletes = new Map<number, string>();

  getProfile(userId: string): Profile | undefined {
    const p = this.profiles.get(userId);
    return p && structuredClone(p);
  }

  saveProfile(profile: Profile): void {
    this.profiles.set(profile.userId, structuredClone(profile));
  }

  listSessions(userId: string, from: string, to: string): Session[] {
    return [...this.sessions.values()]
      .filter((s) => s.userId === userId && s.date >= from && s.date <= to)
      .sort((a, b) => a.date.localeCompare(b.date))
      .map((s) => structuredClone(s));
  }

  saveSession(session: Session): void {
    this.sessions.set(session.id, structuredClone(session));
  }

  getSession(userId: string, id: string): Session | undefined {
    const s = this.sessions.get(id);
    return s && s.userId === userId ? structuredClone(s) : undefined;
  }

  getResult(userId: string, id: string): Result | undefined {
    const r = this.results.get(id);
    return r && r.userId === userId ? structuredClone(r) : undefined;
  }

  latestResultFor(userId: string, sessionId: string): Result | undefined {
    const matches = [...this.results.values()]
      .filter((r) => r.userId === userId && r.sessionId === sessionId)
      .sort((a, b) => b.createdAt.localeCompare(a.createdAt));
    return matches[0] && structuredClone(matches[0]);
  }

  saveResult(result: Result): void {
    this.results.set(result.id, structuredClone(result));
  }

  getCredential(userId: string, provider: CredentialProvider): Credential | undefined {
    const c = this.credentials.get(`${userId}:${provider}`);
    return c && structuredClone(c);
  }

  listCredentials(userId: string): Credential[] {
    return this.allCredentials().filter((c) => c.userId === userId);
  }

  allCredentials(): Credential[] {
    return [...this.credentials.values()].map((c) => structuredClone(c));
  }

  saveCredential(credential: Credential): void {
    this.credentials.set(`${credential.userId}:${credential.provider}`, structuredClone(credential));
  }

  deleteCredential(userId: string, provider: CredentialProvider): boolean {
    return this.credentials.delete(`${userId}:${provider}`);
  }

  addAudit(entry: AuditEntry): void {
    this.audit.push(structuredClone(entry));
  }

  listAudit(userId: string): AuditEntry[] {
    return this.audit.filter((a) => a.userId === userId).map((a) => structuredClone(a));
  }

  getNode(kind: NodeSummary['kind'], name: string, version?: string): RegistryNode | undefined {
    const matches = [...this.nodes.values()].filter(
      (n) => n.kind === kind && n.name === name && (version ? n.version === version : !n.retired),
    );
    matches.sort((a, b) => compareVersions(b.version, a.version));
    return matches[0] && structuredClone(matches[0]);
  }

  listNodes(): RegistryNode[] {
    return [...this.nodes.values()].map((n) => structuredClone(n));
  }

  saveNode(node: RegistryNode): void {
    this.nodes.set(`${node.kind}:${node.name}:${node.version}`, structuredClone(node));
  }

  getRun(userId: string, id: string): Run | undefined {
    const r = this.runs.get(id);
    return r && r.userId === userId ? structuredClone(r) : undefined;
  }

  listRuns(userId: string): Run[] {
    return [...this.runs.values()]
      .filter((r) => r.userId === userId)
      .sort((a, b) => b.createdAt.localeCompare(a.createdAt))
      .map((r) => structuredClone(r));
  }

  saveRun(run: Run): void {
    this.runs.set(run.id, structuredClone(run));
  }

  getCap(userId: string, provider: Provider): number | undefined {
    return this.caps.get(`${userId}:${provider}`);
  }

  setCap(userId: string, provider: Provider, monthlyUsd: number): void {
    this.caps.set(`${userId}:${provider}`, monthlyUsd);
  }

  listEdges(): Edge[] {
    return structuredClone(this.edges);
  }

  saveEdges(edges: Edge[]): void {
    this.edges = structuredClone(edges);
  }

  getRegistryState(): RegistryState {
    return structuredClone(this.registryState);
  }

  setRegistryState(state: RegistryState): void {
    this.registryState = structuredClone(state);
  }

  getUpload(userId: string, id: string): Upload | undefined {
    const u = this.uploads.get(id);
    return u && u.userId === userId ? structuredClone(u) : undefined;
  }

  saveUpload(upload: Upload): void {
    this.uploads.set(upload.id, structuredClone(upload));
  }

  getRace(userId: string, id: string): Race | undefined {
    const r = this.races.get(id);
    return r && r.userId === userId ? structuredClone(r) : undefined;
  }

  listRaces(userId: string): Race[] {
    return [...this.races.values()]
      .filter((r) => r.userId === userId)
      .sort((a, b) => b.date.localeCompare(a.date))
      .map((r) => structuredClone(r));
  }

  saveRace(race: Race): void {
    this.races.set(race.id, structuredClone(race));
  }

  listActivities(userId: string): Activity[] {
    return [...this.activities.values()]
      .filter((a) => a.userId === userId)
      .sort((a, b) => b.startDate.localeCompare(a.startDate))
      .map((a) => structuredClone(a));
  }

  upsertActivity(activity: Activity): Activity {
    const key = `${activity.userId}:${activity.source}:${activity.externalId}`;
    const existing = this.activities.get(key);
    const saved = existing ? { ...activity, id: existing.id } : activity;
    this.activities.set(key, structuredClone(saved));
    return structuredClone(saved);
  }

  deleteActivity(userId: string, source: Activity['source'], externalId: string): void {
    this.activities.delete(`${userId}:${source}:${externalId}`);
  }

  linkStravaAthlete(userId: string, athleteId: number): void {
    this.stravaAthletes.set(athleteId, userId);
  }

  userForStravaAthlete(athleteId: number): string | undefined {
    return this.stravaAthletes.get(athleteId);
  }

  /** Everything stored, for tests that check what was (and was not) written. */
  dump() {
    return {
      profiles: [...this.profiles.values()],
      sessions: [...this.sessions.values()],
      credentials: [...this.credentials.values()],
      audit: this.audit,
      nodes: [...this.nodes.values()],
      runs: [...this.runs.values()],
      results: [...this.results.values()],
      uploads: [...this.uploads.values()],
      races: [...this.races.values()],
      activities: [...this.activities.values()],
    };
  }
}
