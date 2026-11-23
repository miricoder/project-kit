import { afterAll, beforeAll, describe, expect, it } from 'vitest';
import { migrateDown, migrateUp, type Migration } from '../src/migrations/runner.js';
import { migrations } from '../src/migrations/index.js';
import { startDb } from './helpers.js';

let mongo: Awaited<ReturnType<typeof startDb>>;
beforeAll(async () => { mongo = await startDb(); });
afterAll(async () => { await mongo.stop(); });

const now = () => new Date('2026-11-23T10:00:00Z');

describe('migrations', () => {
  it('run up then down on a seeded database and are recorded', async () => {
    const db = mongo.db();
    const applied = await migrateUp(db, migrations, now);
    expect(applied).toEqual(migrations.map((m) => m.id));
    expect(await migrateUp(db, migrations, now)).toEqual([]);           // idempotent
    const recorded = await db.collection('migrations').find().toArray();
    expect(recorded.map((r) => r.id)).toEqual(migrations.map((m) => m.id));

    await db.collection('users').insertOne({ email: 'owner@example.com', userId: 'u1',
      schemaVersion: 1, createdAt: now(), updatedAt: now() });
    await expect(db.collection('users').insertOne({ email: 'owner@example.com' }))
      .rejects.toThrow();                                               // unique email index

    const reverted = await migrateDown(db, migrations, 1, now);
    expect(reverted).toEqual([migrations.at(-1)!.id]);
    expect(await db.collection('migrations').countDocuments()).toBe(migrations.length - 1);
    // the init migration's down drops users: the seeded owner survives in the archive
    const archived = await db.collection('users_archive').find().toArray();
    expect(archived.map((d) => d.email)).toContain('owner@example.com');
  });

  it('copies a collection to <name>_archive before a migration that drops it', async () => {
    const db = mongo.db();
    await db.collection('old_things').insertMany([{ a: 1 }, { a: 2 }]);
    const drop: Migration = {
      id: '9001-drop-old-things', drops: ['old_things'],
      up: async (d) => { await d.collection('old_things').drop(); },
      down: async () => {},
    };
    await migrateUp(db, [drop], now);
    expect(await db.collection('old_things_archive').countDocuments()).toBe(2);
    expect(await db.listCollections({ name: 'old_things' }).toArray()).toHaveLength(0);
  });
});
