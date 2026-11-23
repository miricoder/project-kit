import { afterAll, beforeAll, describe, expect, it } from 'vitest';
import { makeApp, startDb } from './helpers.js';

let mongo: Awaited<ReturnType<typeof startDb>>;
beforeAll(async () => { mongo = await startDb(); });
afterAll(async () => { await mongo.stop(); });

describe('health', () => {
  // Scenario: the API reports its health
  it('reports the API and database as up under /api/v1', async () => {
    const { app } = await makeApp(mongo.db());
    const res = await app.inject({ method: 'GET', url: '/api/v1/health' });
    expect(res.statusCode).toBe(200);
    expect(res.json()).toEqual({ ok: true, db: true, version: 'test' });
    await app.close();
  });

  // Scenario: the API reports its health
  it('still answers when the database is unreachable, and says so', async () => {
    const { MongoClient } = await import('mongodb');
    const dead = new MongoClient('mongodb://127.0.0.1:1', { serverSelectionTimeoutMS: 200 });
    const { app } = await makeApp(dead.db('x'));
    const res = await app.inject({ method: 'GET', url: '/api/v1/health' });
    expect(res.statusCode).toBe(200);
    expect(res.json()).toEqual({ ok: true, db: false, version: 'test' });
    await app.close();
    await dead.close();
  });
});
