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
const app = buildApp({ store, userId: () => OWNER, vaultKey: process.env.VAULT_KEY, registry });

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
