// The device side of Dumpit: the outbox (save first, send oldest-first, one at a time),
// the read cache synced from /v1/changes, and the capture log shown on the Capture screen.
import * as idb from "./idb";
import { Item, localDateTime } from "./derive";

export type LogLine = { kind: string; tag: string; text: string; undo: boolean;
  item?: { kind: string; id: number; ref: string | null }; suggestions?: string[] };
export type LogEntry = { capture_id: string; text: string; created: number;
  status: "waiting" | "sending" | "filed" | "note" | "failed" | "too-long";
  reason?: string; lines?: LogLine[] };
export type OutboxEntry = { capture_id: string; text: string; source: "typed" | "paste";
  captured_at: string; tz: string; created: number; attempts: number };
export type Me = { email: string; tz: string; monthly_budget_cents: number | null };
export type Health = { model: string; dev: boolean; app_version?: string };

export type SendResult =
  | { kind: "filed"; status: "filed" | "note"; lines: LogLine[] }
  | { kind: "wait"; reason: string }        // limit or spend cap: keep waiting, try later
  | { kind: "retry"; reason: string }       // server or model error: retry, then offer Retry
  | { kind: "offline" }
  | { kind: "signed-out" }
  | { kind: "rejected"; reason: string };   // malformed: never going to work

type Listener = () => void;
const RETRY_DELAYS = [5000, 30000];

function cookie(name: string): string {
  if (typeof document === "undefined") return "";
  const m = document.cookie.match(new RegExp(`(?:^|; )${name}=([^;]*)`));
  return m ? decodeURIComponent(m[1]) : "";
}

export async function api(path: string, init: RequestInit = {}): Promise<Response> {
  const headers = new Headers(init.headers);
  if (init.method && init.method !== "GET") {
    headers.set("X-Dumpit-CSRF", cookie("dumpit_csrf"));
    if (init.body) headers.set("Content-Type", "application/json");
  }
  return fetch(path, { ...init, headers, credentials: "same-origin" });
}

export async function sendCapture(entry: OutboxEntry): Promise<SendResult> {
  let res: Response;
  try {
    res = await api("/v1/captures", { method: "POST", body: JSON.stringify({
      capture_id: entry.capture_id, text: entry.text, source: entry.source,
      captured_at: entry.captured_at, tz: entry.tz }) });
  } catch {
    return { kind: "offline" };
  }
  if (res.status === 200) {
    const body = await res.json();
    return { kind: "filed", status: body.status, lines: body.lines };
  }
  if (res.status === 401) return { kind: "signed-out" };
  const reason = await res.json().then((b) => b.error as string).catch(() => `HTTP ${res.status}`);
  if (res.status === 429) return { kind: "wait", reason: "Daily filing limit reached; it will file tomorrow" };
  if (res.status === 503 && /spend cap/.test(reason)) return { kind: "wait", reason: "Filing is paused for today; it will file when it resets" };
  if (res.status === 400 || res.status === 413 || res.status === 409) return { kind: "rejected", reason };
  return { kind: "retry", reason };
}

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

export class Client {
  items: Item[] = [];
  log: LogEntry[] = [];
  me: Me | null = null;
  health: Health | null = null;
  signedIn: boolean | null = null;       // null until we know
  online = typeof navigator === "undefined" ? true : navigator.onLine;
  private listeners = new Set<Listener>();
  private flushing: Promise<void> | null = null;
  private syncing: Promise<void> | null = null;

  constructor(private send: (e: OutboxEntry) => Promise<SendResult> = sendCapture,
              private delays: number[] = RETRY_DELAYS) {}

  subscribe(fn: Listener): () => void {
    this.listeners.add(fn);
    return () => this.listeners.delete(fn);
  }

  private emit(): void {
    this.listeners.forEach((fn) => fn());
  }

  async load(): Promise<void> {
    const [items, log, me] = await Promise.all([
      idb.all<Item & { key: string }>("items"), idb.all<LogEntry>("log"), idb.get<Me>("meta", "me")]);
    this.items = items;
    this.log = log.sort((a, b) => a.created - b.created);
    this.me = me || null;
    this.emit();
  }

  /** Save the capture on the device first, then try to file it. */
  async capture(text: string, source: "typed" | "paste" = "typed", now = new Date()): Promise<string> {
    const entry: OutboxEntry = { capture_id: crypto.randomUUID(), text, source,
      captured_at: localDateTime(now), tz: Intl.DateTimeFormat().resolvedOptions().timeZone,
      created: Date.now() + Math.random() / 1000, attempts: 0 };
    await idb.put("outbox", entry);
    await this.setLog({ capture_id: entry.capture_id, text, created: entry.created,
      status: this.online ? "sending" : "waiting", reason: this.online ? undefined : "you were offline" });
    void this.flush();
    return entry.capture_id;
  }

  private async setLog(entry: LogEntry): Promise<void> {
    await idb.put("log", entry);
    const i = this.log.findIndex((e) => e.capture_id === entry.capture_id);
    if (i >= 0) this.log[i] = entry; else this.log.push(entry);
    this.log = [...this.log].sort((a, b) => a.created - b.created);
    this.emit();
  }

  private logOf(id: string): LogEntry | undefined {
    return this.log.find((e) => e.capture_id === id);
  }

  /** Send waiting captures oldest-first, one at a time. Safe to call any time. */
  flush(): Promise<void> {
    if (!this.flushing) {
      this.flushing = this.doFlush().finally(() => { this.flushing = null; });
    }
    return this.flushing;
  }

  private async doFlush(): Promise<void> {
    let filedAny = false;
    for (;;) {
      const waiting = (await idb.all<OutboxEntry>("outbox")).sort((a, b) => a.created - b.created)
        .filter((e) => this.logOf(e.capture_id)?.status !== "failed");
      const entry = waiting[0];
      if (!entry) break;
      if (typeof navigator !== "undefined" && navigator.onLine === false) {
        this.online = false;          // no point trying; the "online" event flushes again
        for (const e of waiting) {
          const l = this.logOf(e.capture_id);
          if (l && l.status !== "waiting") await this.setLog({ ...l, status: "waiting", reason: "you were offline" });
        }
        break;
      }
      // an outbox entry whose log line was lost (cleared log, older version) still files
      const log: LogEntry = this.logOf(entry.capture_id) ??
        { capture_id: entry.capture_id, text: entry.text, created: entry.created, status: "waiting" };
      await this.setLog({ ...log, status: "sending", reason: undefined });
      const result = await this.send(entry);
      if (result.kind === "filed") {
        await idb.remove("outbox", entry.capture_id);
        await this.setLog({ ...log, status: result.status, lines: result.lines, reason: undefined });
        this.online = true;
        filedAny = true;
        continue;
      }
      if (result.kind === "offline") {
        this.online = false;
        await this.setLog({ ...log, status: "waiting", reason: "you were offline" });
        break;
      }
      if (result.kind === "signed-out") {
        await this.setLog({ ...log, status: "waiting", reason: "sign in to file it" });
        this.signedIn = false;
        this.emit();
        break;
      }
      if (result.kind === "wait") {
        await this.setLog({ ...log, status: "waiting", reason: result.reason });
        break;
      }
      if (result.kind === "rejected") {
        await idb.remove("outbox", entry.capture_id);
        await this.setLog({ ...log, status: "failed", reason: result.reason });
        continue;
      }
      // retry: two automatic retries, then keep the words and offer Retry
      if (entry.attempts < this.delays.length) {
        await idb.put("outbox", { ...entry, attempts: entry.attempts + 1 });
        await this.setLog({ ...log, status: "sending", reason: "Still filing — retrying" });
        await sleep(this.delays[entry.attempts]);
        continue;
      }
      await idb.put("outbox", { ...entry, attempts: 0 });
      await this.setLog({ ...log, status: "failed", reason: result.reason });
    }
    if (filedAny) await this.sync();
  }

  async retry(captureId: string): Promise<void> {
    const log = this.logOf(captureId);
    if (log) await this.setLog({ ...log, status: "sending", reason: undefined });
    await this.flush();
  }

  /** Pull everything that changed since the last sync into the read cache. */
  sync(): Promise<void> {
    if (!this.syncing) {
      this.syncing = this.doSync().finally(() => { this.syncing = null; });
    }
    return this.syncing;
  }

  private async doSync(): Promise<void> {
    const since = (await idb.get<number>("meta", "last_seq")) || 0;
    let res: Response;
    try {
      res = await api(`/v1/changes?since=${since}`);
    } catch {
      this.online = false;
      this.emit();
      return;
    }
    this.online = true;
    if (res.status === 401) {
      this.signedIn = false;
      this.emit();
      return;
    }
    if (!res.ok) return;
    const body = await res.json();
    this.signedIn = true;
    const byKey = new Map(this.items.map((i) => [`${i.kind}:${i.id}`, i]));
    for (const item of body.items) byKey.set(`${item.kind}:${item.id}`, { ...item, key: `${item.kind}:${item.id}` });
    for (const d of body.deleted) {
      byKey.delete(`${d.kind}:${d.id}`);
      await idb.remove("items", `${d.kind}:${d.id}`);
    }
    await idb.putMany("items", body.items.map((i: Item) => ({ ...i, key: `${i.kind}:${i.id}` })));
    await idb.put("meta", body.seq, "last_seq");
    await idb.put("meta", body.me, "me");
    this.items = [...byKey.values()];
    this.me = body.me;
    this.emit();
  }

  async checkHealth(): Promise<void> {
    try {
      const res = await fetch("/v1/health");
      if (res.ok) this.health = await res.json();
    } catch { /* offline: keep the cached app working */ }
    this.emit();
  }

  /** Forget everything on this device (sign-out, or a different account). */
  async forget(): Promise<void> {
    await Promise.all([idb.clear("items"), idb.clear("log"), idb.clear("meta"), idb.clear("outbox")]);
    this.items = [];
    this.log = [];
    this.me = null;
    this.emit();
  }

  signedOut(): void {
    this.signedIn = false;
    this.emit();
  }

  async setDone(taskId: number, done: boolean): Promise<void> {
    const res = await api(`/v1/tasks/${taskId}/done`, { method: "POST", body: JSON.stringify({ done }) });
    if (res.status === 401) { this.signedIn = false; this.emit(); return; }
    await this.sync();
  }
}
