import { buildApp } from './app.ts';
import { MemoryStore } from './store.ts';

// Local development entry point. Sign-in and MongoDB arrive with their slices; until then
// every request is the single owner and data lives in memory.
const store = new MemoryStore();
const app = buildApp({ store, userId: () => 'owner' });
const port = Number(process.env.PORT ?? 3000);
await app.listen({ port, host: '0.0.0.0' });
