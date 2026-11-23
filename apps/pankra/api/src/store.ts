import type { Profile, Session } from '@pankra/shared';

/** Persistence for the training API. MongoDB implements it once the owner's cluster exists. */
export interface Store {
  getProfile(userId: string): Profile | undefined;
  saveProfile(profile: Profile): void;
  listSessions(userId: string, from: string, to: string): Session[];
  saveSession(session: Session): void;
}

/** In-memory store: tests and local development without a database. */
export class MemoryStore implements Store {
  private profiles = new Map<string, Profile>();
  private sessions = new Map<string, Session>();

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
}
