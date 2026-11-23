import { buildApp } from './app.ts';
import { MemoryStore } from './store.ts';
import { expireCredentials } from './vault.ts';

// Local development entry point. Sign-in and MongoDB arrive with their slices; until then
// every request is the single owner and data lives in memory.
const store = new MemoryStore();
const app = buildApp({ store, userId: () => 'owner', vaultKey: process.env.VAULT_KEY });

// Key expiry job: every 15 minutes (Agenda on MongoDB replaces this timer with the database).
const EXPIRY_INTERVAL_MS = 15 * 60 * 1000;
setInterval(() => expireCredentials(store, new Date()), EXPIRY_INTERVAL_MS).unref();

const port = Number(process.env.PORT ?? 3000);
await app.listen({ port, host: '0.0.0.0' });
