import type { AuditEntry, Credential, CredentialProvider, Profile, Session } from '@pankra/shared';

/** Persistence for the training API. MongoDB implements it once the owner's cluster exists. */
export interface Store {
  getProfile(userId: string): Profile | undefined;
  saveProfile(profile: Profile): void;
  listSessions(userId: string, from: string, to: string): Session[];
  saveSession(session: Session): void;
  getCredential(userId: string, provider: CredentialProvider): Credential | undefined;
  listCredentials(userId: string): Credential[];
  allCredentials(): Credential[];
  saveCredential(credential: Credential): void;
  deleteCredential(userId: string, provider: CredentialProvider): boolean;
  addAudit(entry: AuditEntry): void;
  listAudit(userId: string): AuditEntry[];
}

/** In-memory store: tests and local development without a database. */
export class MemoryStore implements Store {
  private profiles = new Map<string, Profile>();
  private sessions = new Map<string, Session>();
  private credentials = new Map<string, Credential>();
  private audit: AuditEntry[] = [];

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

  /** Everything stored, for tests that check nothing sensitive is kept in plain text. */
  dump(): unknown {
    return {
      profiles: [...this.profiles.values()],
      sessions: [...this.sessions.values()],
      credentials: [...this.credentials.values()],
      audit: this.audit,
    };
  }
}
