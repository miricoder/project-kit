import cors from '@fastify/cors';
import Fastify, { type FastifyInstance } from 'fastify';
import { z } from 'zod';
import { randomUUID } from 'node:crypto';
import {
  analyzeRace,
  buildCard,
  postFromCard,
  postSvg,
  shiftSchedule,
  type CredentialStatus,
  type Race,
  type RegistryNode,
  type RegistryStatus,
  type Result,
  type Session,
  type Upload,
} from '@pankra/shared';
import { compareVersions, type Store } from './store.ts';
import { Vault, isExpired } from './vault.ts';
import { claudeAdapter } from './providers/claude.ts';
import { gptAdapter } from './providers/gpt.ts';
import type { FetchLike } from './providers/types.ts';
import { runNode, spentThisMonth } from './runner.ts';
import { syncRegistry, type RegistryConfig } from './registry.ts';
import { MemoryStorage, type ObjectStorage } from './storage.ts';
import { authorizeUrl, connect, importActivity, type StravaConfig } from './strava.ts';
import multipart from '@fastify/multipart';
import cookie from '@fastify/cookie';
import { AuthError, SESSION_COOKIE, requestLink, signOut, userForRequest, verifyLink, type AuthConfig } from './auth.ts';
import { Resvg } from '@resvg/resvg-js';

export interface AppDeps {
  store: Store;
  /**
   * Resolves the signed-in user for a request; undefined means not signed in. Tests inject
   * one; without it, sign-in (`auth`) decides.
   */
  userId?: (headers: Record<string, unknown>) => string | undefined;
  /** Email-link sign-in for the single owner. */
  auth?: AuthConfig;
  /** Base64 32-byte master key for the key vault (host secret VAULT_KEY). */
  vaultKey?: string;
  /** The clock; injected so retention can be tested. */
  now?: () => Date;
  /** HTTP client for the provider APIs and GitHub; injected so tests stand in for them. */
  fetch?: FetchLike;
  /** Where the registry is pulled from (REGISTRY_REPO, REGISTRY_REF). */
  registry?: RegistryConfig;
  /** Origins the web app is served from (CORS_ORIGINS, comma-separated). */
  corsOrigins?: string[];
  /** Private image storage (R2 in production). */
  storage?: ObjectStorage;
  /** Strava app credentials and webhook subscription. */
  strava?: StravaConfig;
  /** The API's public base URL (for OAuth callbacks), e.g. https://api.pankra.app */
  publicApiUrl?: string;
  /** The web app's URL, to send the athlete back after connecting Strava. */
  webUrl?: string;
}

/** Expo's web dev server and a local static preview. */
export const DEFAULT_CORS_ORIGINS = ['http://localhost:8081', 'http://localhost:8080'];

export const DEFAULT_REGISTRY: RegistryConfig = { repo: 'miricoder/project-kit', ref: 'main' };

const ProviderParam = z.object({ provider: z.enum(['claude', 'gpt']) });
const CapBody = z.object({ monthlyUsd: z.number().nonnegative().max(10_000) });
const RunBody = z.object({
  node: z.object({
    kind: z.enum(['skill', 'agent', 'plugin', 'provider']),
    name: z.string().min(1).max(100),
    version: z.string().max(40).optional(),
  }),
  provider: z.enum(['claude', 'gpt']),
  model: z.string().min(1).max(100).optional(),
  input: z.record(z.unknown()),
});

// Dates are calendar days, YYYY-MM-DD.
const isoDate = z.string().regex(/^\d{4}-\d{2}-\d{2}$/, 'expected YYYY-MM-DD');

const MAX_UPLOAD_BYTES = 10 * 1024 * 1024;
const IMAGE_TYPES = new Set(['image/png', 'image/jpeg', 'image/webp', 'image/heic']);
const UploadQuery = z.object({
  kind: z.enum(['race', 'run', 'class', 'meal', 'other']).default('other'),
  /** When given, screenshot-reader reads the image on this provider right away. */
  provider: z.enum(['claude', 'gpt']).optional(),
});
const seconds = z.number().int().nonnegative().max(6 * 3600);
const ConfirmRace = z.object({
  data: z.object({
    event: z.string().min(1).max(200),
    date: isoDate,
    division: z.string().max(100),
    totalS: seconds.positive(),
    runs: z.array(seconds.positive()).length(8),
    stations: z.array(seconds.positive()).length(8),
    roxzoneS: seconds,
    ranks: z.object({ overall: z.number().int().positive().optional(), ageGroup: z.number().int().positive().optional() }).optional(),
    lapsPerKm: z.number().positive().optional(),
  }),
});
const StravaEvent = z.object({
  object_type: z.enum(['activity', 'athlete']),
  object_id: z.number().int().positive(),
  aspect_type: z.enum(['create', 'update', 'delete']),
  owner_id: z.number().int().positive(),
  subscription_id: z.number().int(),
  event_time: z.number().optional(),
  updates: z.record(z.string()).optional(),
});

const PostThemeSchema = z.enum(['whiteboard', 'game-inspired', 'clean']);
const RenderBody = z.object({
  theme: PostThemeSchema,
  post: z.object({
    date: z.string().max(40).optional(),
    title: z.string().min(1).max(200),
    sections: z
      .array(z.object({ label: z.string().max(100), lines: z.array(z.string().max(300)).max(40) }))
      .max(20),
  }),
});

/** SVG to PNG at the SVG's own size, with the host's fonts. */
function renderPng(svg: string): Buffer {
  return new Resvg(svg, { font: { loadSystemFonts: true, defaultFontFamily: 'DejaVu Sans' } }).render().asPng();
}

const ResultBody = z.object({
  sessionId: z.string().min(1),
  parts: z
    .array(
      z.object({
        label: z.string().min(1).max(100),
        loadKg: z.number().nonnegative().optional(),
        reps: z.number().int().nonnegative().optional(),
        timeS: z.number().positive().optional(),
        distanceM: z.number().nonnegative().optional(),
        speedKmh: z.number().positive().optional(),
        rpe: z.number().min(1).max(10).optional(),
      }),
    )
    .min(1)
    .max(100),
  notes: z.string().max(5000).optional(),
});

const CredentialParams = z.object({ provider: z.enum(['claude', 'gpt']) });
const CredentialBody = z.object({
  secret: z.string().trim().min(8).max(500),
  retention: z.enum(['session', '24h', '7d', '30d', 'forever']),
});

const SessionsQuery = z.object({ from: isoDate, to: isoDate });

const Item = z.object({
  exercise: z.string().min(1),
  distanceM: z.number().positive().optional(),
  loadKg: z.number().nonnegative().optional(),
  reps: z.number().int().positive().optional(),
  timeS: z.number().positive().optional(),
  speedKmh: z.number().positive().optional(),
  machine: z.string().optional(),
});
const Section = z.object({
  kind: z.enum(['warmup', 'strength', 'engine', 'core', 'cooldown', 'daily']),
  label: z.string().min(1),
  lines: z.array(z.union([z.string(), Item])),
  rounds: z.number().int().positive().optional(),
  restS: z.number().positive().optional(),
});
const InsertBody = z.object({
  date: isoDate,
  session: z.object({
    title: z.string().min(1).max(200),
    type: z.enum(['gym', 'track', 'class']).default('class'),
    tag: z.string().max(100).optional(),
    sections: z.array(Section).default([]),
    notes: z.string().max(5000).optional(),
    log: z.string().max(500).optional(),
  }),
});

function errorText(error: z.ZodError): string {
  return error.issues.map((i) => `${i.path.join('.') || 'body'}: ${i.message}`).join('; ');
}

export function buildApp(deps: AppDeps): FastifyInstance {
  // Request bodies are never logged: they can carry keys.
  const app = Fastify({ logger: false });
  // The web app is served from another origin (Vercel; Expo's dev server locally).
  void app.register(cors, {
    origin: deps.corsOrigins ?? DEFAULT_CORS_ORIGINS,
    credentials: true,
    methods: ['GET', 'POST', 'PUT', 'DELETE'],
  });
  const now = deps.now ?? (() => new Date());
  const userOf = deps.userId ?? ((headers: Record<string, unknown>) => userForRequest(deps.store, headers, now()));
  const vault = deps.vaultKey ? new Vault(deps.vaultKey) : undefined;
  const fetchImpl = deps.fetch ?? fetch;
  const adapters = { claude: claudeAdapter(fetchImpl), gpt: gptAdapter(fetchImpl) };
  const storage = deps.storage ?? new MemoryStorage();
  void app.register(multipart, { limits: { fileSize: MAX_UPLOAD_BYTES, files: 1, fields: 5 } });
  void app.register(cookie);

  // Sign-in: an email link for the owner; a bearer token on iPhone, a cookie on the web.
  app.post('/api/v1/auth/magic-link', async (req, reply) => {
    const body = z.object({ email: z.string().email().max(320), client: z.enum(['web', 'ios']).default('web') }).safeParse(req.body);
    if (!body.success) return reply.code(400).send({ error: errorText(body.error) });
    if (!deps.auth) return reply.code(503).send({ error: 'Sign-in is not configured (OWNER_EMAIL)' });
    try {
      await requestLink({ store: deps.store, config: deps.auth, fetch: fetchImpl, now: now(), webUrl: deps.webUrl }, body.data.email, body.data.client);
    } catch (e) {
      if (e instanceof AuthError) return reply.code(e.status).send({ error: e.message });
      throw e;
    }
    // The same answer whether or not the address is the owner's.
    return reply.code(202).send({ sent: true, message: 'If that address can sign in, a link is on its way.' });
  });

  app.post('/api/v1/auth/verify', async (req, reply) => {
    const body = z.object({ token: z.string().min(20).max(200) }).safeParse(req.body);
    if (!body.success) return reply.code(400).send({ error: errorText(body.error) });
    try {
      const session = verifyLink(deps.store, body.data.token, now());
      reply.setCookie(SESSION_COOKIE, session.token, {
        httpOnly: true,
        secure: true,
        sameSite: 'lax',
        path: '/',
        expires: new Date(session.expiresAt),
      });
      // The web app relies on the cookie; the iPhone keeps the token in its keychain.
      return session.client === 'ios'
        ? { token: session.token, expiresAt: session.expiresAt }
        : { signedIn: true, expiresAt: session.expiresAt };
    } catch (e) {
      if (e instanceof AuthError) return reply.code(e.status).send({ error: e.message });
      throw e;
    }
  });

  app.post('/api/v1/auth/sign-out', async (req, reply) => {
    signOut(deps.store, req.headers);
    reply.clearCookie(SESSION_COOKIE, { path: '/' });
    return reply.code(204).send();
  });

  app.get('/api/v1/auth/me', async (req, reply) => {
    const userId = userOf(req.headers);
    return userId ? { userId } : reply.code(401).send({ error: 'Sign in required' });
  });

  // Registry: skills, agents and plugins pulled from project-kit's registry/ by the API.
  const registry = deps.registry ?? DEFAULT_REGISTRY;

  app.post('/api/v1/registry/sync', async (req, reply) => {
    const userId = userOf(req.headers);
    if (!userId) return reply.code(401).send({ error: 'Sign in required' });
    const report = await syncRegistry({ store: deps.store, fetch: fetchImpl, config: registry, now, auditUserId: userId });
    return report.ok ? report : reply.code(502).send(report);
  });

  app.get('/api/v1/registry/status', async (req, reply) => {
    const userId = userOf(req.headers);
    if (!userId) return reply.code(401).send({ error: 'Sign in required' });
    const state = deps.store.getRegistryState();
    const status: RegistryStatus = {
      repo: registry.repo,
      ref: registry.ref,
      ...state,
      nodes: deps.store.listNodes().filter((n) => !n.retired).length,
    };
    return status;
  });

  // The graph: the latest version of every node still in the registry, and the edges.
  app.get('/api/v1/nodes', async (req, reply) => {
    const userId = userOf(req.headers);
    if (!userId) return reply.code(401).send({ error: 'Sign in required' });
    const latest = new Map<string, RegistryNode>();
    for (const n of deps.store.listNodes()) {
      if (n.retired) continue;
      const key = `${n.kind}:${n.name}`;
      const have = latest.get(key);
      if (!have || compareVersions(n.version, have.version) > 0) latest.set(key, n);
    }
    return [...latest.values()]
      .sort((a, b) => a.kind.localeCompare(b.kind) || a.name.localeCompare(b.name))
      .map(({ kind, name, version, description, providers, requires, vision, tools, input, steps, skills, agents }) => ({
        kind, name, version, description, providers, requires, vision, tools, input, steps, skills, agents,
      }));
  });

  app.get('/api/v1/edges', async (req, reply) => {
    const userId = userOf(req.headers);
    if (!userId) return reply.code(401).send({ error: 'Sign in required' });
    return deps.store.listEdges();
  });

  // Runs: a skill or agent on a chosen provider. Refusals happen before any provider call.
  app.post('/api/v1/runs', async (req, reply) => {
    const userId = userOf(req.headers);
    if (!userId) return reply.code(401).send({ error: 'Sign in required' });
    const body = RunBody.safeParse(req.body);
    if (!body.success) return reply.code(400).send({ error: errorText(body.error) });
    const outcome = await runNode({ store: deps.store, vault, adapters, now, storage }, userId, body.data);
    if (outcome.refused) return reply.code(outcome.httpStatus).send(outcome.body);
    return outcome.run;
  });

  app.get('/api/v1/runs/:id', async (req, reply) => {
    const userId = userOf(req.headers);
    if (!userId) return reply.code(401).send({ error: 'Sign in required' });
    const run = deps.store.getRun(userId, (req.params as { id: string }).id);
    if (!run) return reply.code(404).send({ error: 'No such run' });
    return run;
  });

  // Monthly spending caps per provider, and what has been spent this month.
  app.get('/api/v1/caps', async (req, reply) => {
    const userId = userOf(req.headers);
    if (!userId) return reply.code(401).send({ error: 'Sign in required' });
    const at = now();
    return (['claude', 'gpt'] as const).map((provider) => ({
      provider,
      monthlyUsd: deps.store.getCap(userId, provider) ?? null,
      spentUsd: Math.round(spentThisMonth(deps.store, userId, provider, at) * 100) / 100,
    }));
  });

  app.put('/api/v1/caps/:provider', async (req, reply) => {
    const userId = userOf(req.headers);
    if (!userId) return reply.code(401).send({ error: 'Sign in required' });
    const params = ProviderParam.safeParse(req.params);
    if (!params.success) return reply.code(404).send({ error: 'Unknown provider' });
    const body = CapBody.safeParse(req.body);
    if (!body.success) return reply.code(400).send({ error: errorText(body.error) });
    deps.store.setCap(userId, params.data.provider, body.data.monthlyUsd);
    return { provider: params.data.provider, monthlyUsd: body.data.monthlyUsd };
  });

  app.get('/api/v1/health', async () => ({ ok: true }));

  app.get('/api/v1/sessions', async (req, reply) => {
    const userId = userOf(req.headers);
    if (!userId) return reply.code(401).send({ error: 'Sign in required' });
    const parsed = SessionsQuery.safeParse(req.query);
    if (!parsed.success) {
      return reply.code(400).send({ error: parsed.error.issues.map((i) => i.message).join('; ') });
    }
    const { from, to } = parsed.data;
    if (from > to) return reply.code(400).send({ error: '"from" is after "to"' });
    return deps.store.listSessions(userId, from, to);
  });

  // Insert a session (usually a box class) and push later planned sessions (schedule-shifter).
  app.post('/api/v1/sessions/insert', async (req, reply) => {
    const userId = userOf(req.headers);
    if (!userId) return reply.code(401).send({ error: 'Sign in required' });
    const parsed = InsertBody.safeParse(req.body);
    if (!parsed.success) return reply.code(400).send({ error: errorText(parsed.error) });
    const profile = deps.store.getProfile(userId);
    if (!profile) return reply.code(409).send({ error: 'Set up the profile (rest day) first' });

    const { date, session } = parsed.data;
    const inserted: Session = {
      ...session,
      id: randomUUID(),
      userId,
      date,
      status: 'Scheduled',
      source: session.type === 'class' ? 'class' : 'plan',
    };
    const existing = deps.store.listSessions(userId, date, '9999-12-31');
    const { updated, changes } = shiftSchedule(existing, inserted, profile);
    for (const s of updated) deps.store.saveSession(s);
    return { session: inserted, changes };
  });

  // Keys: the app only ever sees provider, last4 and expiry.
  app.get('/api/v1/credentials', async (req, reply) => {
    const userId = userOf(req.headers);
    if (!userId) return reply.code(401).send({ error: 'Sign in required' });
    const at = now();
    return deps.store
      .listCredentials(userId)
      .filter((c) => !isExpired(c, at))
      .map(({ provider, last4, retention, expiresAt }): CredentialStatus => ({ provider, last4, retention, expiresAt }));
  });

  app.put('/api/v1/credentials/:provider', async (req, reply) => {
    const userId = userOf(req.headers);
    if (!userId) return reply.code(401).send({ error: 'Sign in required' });
    const params = CredentialParams.safeParse(req.params);
    if (!params.success) return reply.code(404).send({ error: 'Unknown provider' });
    const body = CredentialBody.safeParse(req.body);
    if (!body.success) return reply.code(400).send({ error: errorText(body.error) });
    if (!vault) return reply.code(503).send({ error: 'Key vault is not configured (VAULT_KEY)' });

    const at = now();
    const { provider } = params.data;
    const replaced = deps.store.getCredential(userId, provider);
    const credential = vault.seal(userId, provider, body.data.secret, body.data.retention, at);
    deps.store.saveCredential(credential);
    deps.store.addAudit({
      userId,
      action: 'keyAdded',
      at: at.toISOString(),
      detail: { provider, last4: credential.last4, retention: credential.retention, replaced: Boolean(replaced) },
    });
    return { last4: credential.last4, expiresAt: credential.expiresAt };
  });

  app.delete('/api/v1/credentials/:provider', async (req, reply) => {
    const userId = userOf(req.headers);
    if (!userId) return reply.code(401).send({ error: 'Sign in required' });
    const params = CredentialParams.safeParse(req.params);
    if (!params.success) return reply.code(404).send({ error: 'Unknown provider' });
    const existing = deps.store.getCredential(userId, params.data.provider);
    if (existing && deps.store.deleteCredential(userId, params.data.provider)) {
      deps.store.addAudit({
        userId,
        action: 'keyDeleted',
        at: now().toISOString(),
        detail: { provider: params.data.provider, reason: 'requested', last4: existing.last4 },
      });
    }
    return reply.code(204).send();
  });

  // Results: typed against a session; result-analyzer's feedback is kept with them.
  app.post('/api/v1/results', async (req, reply) => {
    const userId = userOf(req.headers);
    if (!userId) return reply.code(401).send({ error: 'Sign in required' });
    const body = ResultBody.safeParse(req.body);
    if (!body.success) return reply.code(400).send({ error: errorText(body.error) });
    if (!deps.store.getSession(userId, body.data.sessionId)) {
      return reply.code(404).send({ error: 'No such session' });
    }
    const result: Result = {
      id: randomUUID(),
      userId,
      sessionId: body.data.sessionId,
      parts: body.data.parts,
      notes: body.data.notes,
      uploadIds: [],
      createdAt: now().toISOString(),
    };
    deps.store.saveResult(result);
    return result;
  });

  // A week's results, for the Week screen.
  app.get('/api/v1/results', async (req, reply) => {
    const userId = userOf(req.headers);
    if (!userId) return reply.code(401).send({ error: 'Sign in required' });
    const parsed = SessionsQuery.safeParse(req.query);
    if (!parsed.success) return reply.code(400).send({ error: errorText(parsed.error) });
    const ids = new Set(deps.store.listSessions(userId, parsed.data.from, parsed.data.to).map((s) => s.id));
    return deps.store
      .listResults(userId)
      .filter((r) => ids.has(r.sessionId))
      .sort((a, b) => a.createdAt.localeCompare(b.createdAt));
  });

  app.get('/api/v1/results/:id', async (req, reply) => {
    const userId = userOf(req.headers);
    if (!userId) return reply.code(401).send({ error: 'Sign in required' });
    const result = deps.store.getResult(userId, (req.params as { id: string }).id);
    if (!result) return reply.code(404).send({ error: 'No such result' });
    return result;
  });

  app.get('/api/v1/profile', async (req, reply) => {
    const userId = userOf(req.headers);
    if (!userId) return reply.code(401).send({ error: 'Sign in required' });
    const profile = deps.store.getProfile(userId);
    if (!profile) return reply.code(404).send({ error: 'No profile yet' });
    return profile;
  });

  // Uploads: an image is stored privately, read by screenshot-reader, and shown for
  // confirmation. Nothing becomes a race until the athlete confirms.
  app.post('/api/v1/uploads', async (req, reply) => {
    const userId = userOf(req.headers);
    if (!userId) return reply.code(401).send({ error: 'Sign in required' });
    const query = UploadQuery.safeParse(req.query);
    if (!query.success) return reply.code(400).send({ error: errorText(query.error) });
    if (!req.isMultipart()) return reply.code(400).send({ error: 'Send the image as multipart/form-data' });
    const file = await req.file();
    if (!file) return reply.code(400).send({ error: 'No image in the upload' });
    if (!IMAGE_TYPES.has(file.mimetype)) return reply.code(415).send({ error: 'Upload a PNG, JPEG, WebP or HEIC image' });
    let bytes: Buffer;
    try {
      bytes = await file.toBuffer();
    } catch {
      return reply.code(413).send({ error: `Images are limited to ${MAX_UPLOAD_BYTES / 1024 / 1024} MB` });
    }

    const id = randomUUID();
    const upload: Upload = {
      id,
      userId,
      storageKey: `${userId}/uploads/${id}`,
      mime: file.mimetype,
      kind: query.data.kind,
      extracted: null,
      confirmed: false,
      createdAt: now().toISOString(),
    };
    await storage.put(upload.storageKey, bytes, upload.mime);
    deps.store.saveUpload(upload);
    if (!query.data.provider) return upload;

    const outcome = await runNode(
      { store: deps.store, vault, adapters, now, storage },
      userId,
      { node: { kind: 'skill', name: 'screenshot-reader' }, provider: query.data.provider, input: { uploadIds: [id] } },
    );
    if (outcome.refused) return reply.code(outcome.httpStatus).send({ ...outcome.body, upload });
    if (outcome.run.status === 'failed') {
      return reply.code(502).send({ error: outcome.run.error, runId: outcome.run.id, upload });
    }
    return deps.store.getUpload(userId, id);
  });

  app.post('/api/v1/uploads/:id/confirm', async (req, reply) => {
    const userId = userOf(req.headers);
    if (!userId) return reply.code(401).send({ error: 'Sign in required' });
    const upload = deps.store.getUpload(userId, (req.params as { id: string }).id);
    if (!upload) return reply.code(404).send({ error: 'No such upload' });
    if (upload.confirmed) return reply.code(409).send({ error: 'Already confirmed' });
    const body = ConfirmRace.safeParse(req.body);
    if (!body.success) return reply.code(400).send({ error: errorText(body.error) });
    const race: Race = { ...body.data.data, id: randomUUID(), userId, uploadId: upload.id, createdAt: now().toISOString() };
    deps.store.saveRace(race);
    const confirmed: Upload = { ...upload, confirmed: true, raceId: race.id };
    deps.store.saveUpload(confirmed);
    return confirmed;
  });

  app.get('/api/v1/races', async (req, reply) => {
    const userId = userOf(req.headers);
    if (!userId) return reply.code(401).send({ error: 'Sign in required' });
    return deps.store.listRaces(userId);
  });

  app.get('/api/v1/races/:id', async (req, reply) => {
    const userId = userOf(req.headers);
    if (!userId) return reply.code(401).send({ error: 'Sign in required' });
    const race = deps.store.getRace(userId, (req.params as { id: string }).id);
    return race ?? reply.code(404).send({ error: 'No such race' });
  });

  app.get('/api/v1/races/:id/analysis', async (req, reply) => {
    const userId = userOf(req.headers);
    if (!userId) return reply.code(401).send({ error: 'Sign in required' });
    const race = deps.store.getRace(userId, (req.params as { id: string }).id);
    if (!race) return reply.code(404).send({ error: 'No such race' });
    const q = z.object({ targetS: z.coerce.number().int().positive().optional() }).safeParse(req.query);
    if (!q.success) return reply.code(400).send({ error: errorText(q.error) });
    const targetS = q.data.targetS ?? deps.store.getProfile(userId)?.raceTargetS;
    if (!targetS) return reply.code(400).send({ error: 'Set a race target first, e.g. 60:00' });
    return analyzeRace(race, targetS);
  });

  // Share: the day's workout as a 1080 x 1350 PNG for Instagram.
  app.get('/api/v1/sessions/:id/post.png', async (req, reply) => {
    const userId = userOf(req.headers);
    if (!userId) return reply.code(401).send({ error: 'Sign in required' });
    const q = z.object({ theme: PostThemeSchema.default('whiteboard') }).safeParse(req.query);
    if (!q.success) return reply.code(400).send({ error: errorText(q.error) });
    const session = deps.store.getSession(userId, (req.params as { id: string }).id);
    if (!session) return reply.code(404).send({ error: 'No such session' });
    const profile = deps.store.getProfile(userId);
    if (!profile) return reply.code(409).send({ error: 'Set up the profile first' });
    const png = renderPng(postSvg(postFromCard(buildCard(session, profile)), q.data.theme));
    return reply
      .type('image/png')
      .header('content-disposition', `attachment; filename="pankra-${session.date}.png"`)
      .send(png);
  });

  app.post('/api/v1/posts/render', async (req, reply) => {
    const userId = userOf(req.headers);
    if (!userId) return reply.code(401).send({ error: 'Sign in required' });
    const body = RenderBody.safeParse(req.body);
    if (!body.success) return reply.code(400).send({ error: errorText(body.error) });
    return reply.type('image/png').send(renderPng(postSvg(body.data.post, body.data.theme)));
  });

  app.get('/api/v1/activities', async (req, reply) => {
    const userId = userOf(req.headers);
    if (!userId) return reply.code(401).send({ error: 'Sign in required' });
    return deps.store.listActivities(userId);
  });

  // Strava: OAuth connect, and the webhook that imports runs as they are recorded.
  const oauthStates = new Map<string, { userId: string; expires: number }>();
  const stravaDeps = () => {
    if (!deps.strava || !vault) return undefined;
    return { store: deps.store, vault, fetch: fetchImpl, config: deps.strava, now: now() };
  };

  app.get('/api/v1/strava/connect', async (req, reply) => {
    const userId = userOf(req.headers);
    if (!userId) return reply.code(401).send({ error: 'Sign in required' });
    if (!deps.strava) return reply.code(503).send({ error: 'Strava is not configured (STRAVA_CLIENT_ID)' });
    const state = randomUUID();
    oauthStates.set(state, { userId, expires: now().getTime() + 10 * 60_000 });
    const redirect = `${deps.publicApiUrl ?? `${req.protocol}://${req.host}`}/api/v1/strava/callback`;
    return { url: authorizeUrl(deps.strava, redirect, state) };
  });

  app.get('/api/v1/strava/callback', async (req, reply) => {
    const q = z.object({ code: z.string().min(1).optional(), state: z.string().min(1), error: z.string().optional() }).safeParse(req.query);
    if (!q.success) return reply.code(400).send({ error: errorText(q.error) });
    const pending = oauthStates.get(q.data.state);
    oauthStates.delete(q.data.state);
    if (!pending || pending.expires < now().getTime()) return reply.code(400).send({ error: 'This Strava link has expired; connect again' });
    if (q.data.error || !q.data.code) return reply.code(400).send({ error: 'Strava access was not granted' });
    const sd = stravaDeps();
    if (!sd) return reply.code(503).send({ error: 'Strava or the key vault is not configured' });
    try {
      const athleteId = await connect(sd, pending.userId, q.data.code);
      if (deps.webUrl) return reply.redirect(`${deps.webUrl}/paces?strava=connected`);
      return { connected: true, athleteId };
    } catch (e) {
      return reply.code(502).send({ error: (e as Error).message });
    }
  });

  // Strava's subscription check.
  app.get('/api/v1/webhooks/strava', async (req, reply) => {
    const q = req.query as Record<string, string>;
    if (!deps.strava?.verifyToken || q['hub.mode'] !== 'subscribe' || q['hub.verify_token'] !== deps.strava.verifyToken) {
      return reply.code(403).send({ error: 'Not a valid subscription request' });
    }
    return { 'hub.challenge': q['hub.challenge'] };
  });

  app.post('/api/v1/webhooks/strava', async (req, reply) => {
    const event = StravaEvent.safeParse(req.body);
    if (!event.success) return reply.code(400).send({ error: errorText(event.error) });
    // Strava does not sign events: only our subscription's events are accepted.
    if (!deps.strava?.subscriptionId || event.data.subscription_id !== deps.strava.subscriptionId) {
      return reply.code(403).send({ error: 'Unknown subscription' });
    }
    const userId = deps.store.userForStravaAthlete(event.data.owner_id);
    const sd = stravaDeps();
    if (!userId || !sd) return { ignored: true };
    if (event.data.object_type === 'athlete') {
      if (event.data.updates?.authorized === 'false') deps.store.deleteCredential(userId, 'strava');
      return { ok: true };
    }
    if (event.data.aspect_type === 'delete') {
      deps.store.deleteActivity(userId, 'strava', String(event.data.object_id));
      return { ok: true };
    }
    try {
      const activity = await importActivity(sd, userId, event.data.object_id);
      return { ok: true, activityId: activity.id };
    } catch (e) {
      // A failed import answers 502 so Strava retries; importing is idempotent.
      return reply.code(502).send({ error: (e as Error).message });
    }
  });

  return app;
}
