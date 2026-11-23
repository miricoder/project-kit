import { defineConfig } from 'vitest/config';

// The first run downloads a MongoDB binary for mongodb-memory-server; allow for it.
export default defineConfig({ test: { hookTimeout: 180_000, testTimeout: 30_000 } });
