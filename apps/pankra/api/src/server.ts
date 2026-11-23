import { buildApp, DEFAULT_REGISTRY } from './app.ts';
import { syncRegistry } from './registry.ts';
import { MemoryStore } from './store.ts';
import { expireCredentials } from './vault.ts';

// Local development entry point. Sign-in and MongoDB arrive with their slices; until then
// every request is the single owner and data lives in memory.
const OWNER = 'owner';
const store = new MemoryStore();
const registry = {
  repo: process.env.REGISTRY_REPO ?? DEFAULT_REGISTRY.repo,
  ref: process.env.REGISTRY_REF ?? DEFAULT_REGISTRY.ref,
};
const env = process.env;
const corsOrigins = env.CORS_ORIGINS?.split(',').map((o) => o.trim()).filter(Boolean);
const strava =
  env.STRAVA_CLIENT_ID && env.STRAVA_CLIENT_SECRET
    ? {
        clientId: env.STRAVA_CLIENT_ID,
        clientSecret: env.STRAVA_CLIENT_SECRET,
        subscriptionId: env.STRAVA_SUBSCRIPTION_ID ? Number(env.STRAVA_SUBSCRIPTION_ID) : undefined,
        verifyToken: env.STRAVA_VERIFY_TOKEN,
      }
    : undefined;
const auth = env.OWNER_EMAIL
  ? { ownerEmail: env.OWNER_EMAIL, ownerId: OWNER, resendApiKey: env.RESEND_API_KEY, from: env.EMAIL_FROM ?? 'PANKRA <onboarding@resend.dev>' }
  : undefined;
if (!auth) console.warn('OWNER_EMAIL is not set: local dev mode, every request is the owner and nobody signs in.');
const app = buildApp({
  store,
  userId: auth ? undefined : () => OWNER,
  auth,
  vaultKey: env.VAULT_KEY,
  registry,
  corsOrigins,
  strava,
  publicApiUrl: env.PUBLIC_API_URL,
  webUrl: env.WEB_URL,
});

// Jobs (Agenda on MongoDB replaces these timers once the database is in place).
const MINUTE = 60_000;
setInterval(() => expireCredentials(store, new Date()), 15 * MINUTE).unref();
const sync = () =>
  syncRegistry({ store, fetch, config: registry, now: () => new Date(), auditUserId: OWNER }).then((r) =>
    console.log(r.ok ? `registry ${registry.ref}: +${r.added} ~${r.updated} retired ${r.retired}, skipped ${r.skipped.length}` : `registry sync failed: ${r.error}`),
  );
setInterval(sync, 6 * 60 * MINUTE).unref();

const port = Number(process.env.PORT ?? 3000);
await app.listen({ port, host: '0.0.0.0' });
void sync();
