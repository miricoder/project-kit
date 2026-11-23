import type { Db } from 'mongodb';

export interface Migration {
  /** Ordered id, e.g. "0001-init". */
  id: string;
  up(db: Db): Promise<void>;
  down(db: Db): Promise<void>;
  /** Collections `up` drops: copied to <name>_archive first. */
  drops?: string[];
  /** Collections `down` drops: copied to <name>_archive first. */
  dropsOnDown?: string[];
}

const LEDGER = 'migrations';

async function archive(db: Db, names: string[] = []) {
  for (const name of names) {
    const exists = await db.listCollections({ name }).hasNext();
    if (!exists) continue;
    const docs = await db.collection(name).find().toArray();
    if (docs.length) await db.collection(`${name}_archive`).insertMany(docs, { ordered: false })
      .catch((err: { code?: number }) => { if (err.code !== 11000) throw err; });
  }
}

async function appliedIds(db: Db): Promise<string[]> {
  const rows = await db.collection(LEDGER).find({}, { sort: { id: 1 } }).toArray();
  return rows.map((r) => r.id as string);
}

/** Apply every migration not yet recorded, in id order. Returns the ids applied. */
export async function migrateUp(db: Db, all: Migration[], now = () => new Date()): Promise<string[]> {
  const done = new Set(await appliedIds(db));
  const applied: string[] = [];
  for (const m of [...all].sort((a, b) => a.id.localeCompare(b.id))) {
    if (done.has(m.id)) continue;
    await archive(db, m.drops);
    await m.up(db);
    await db.collection(LEDGER).insertOne({ id: m.id, appliedAt: now() });
    applied.push(m.id);
  }
  return applied;
}

/** Revert the last `steps` applied migrations, newest first. Returns the ids reverted. */
export async function migrateDown(db: Db, all: Migration[], steps = 1, now = () => new Date()): Promise<string[]> {
  const byId = new Map(all.map((m) => [m.id, m]));
  const reverted: string[] = [];
  for (const id of (await appliedIds(db)).reverse().slice(0, steps)) {
    const m = byId.get(id);
    if (!m) throw new Error(`migration ${id} is recorded but not known to this build`);
    await archive(db, m.dropsOnDown);
    await m.down(db);
    await db.collection(LEDGER).deleteOne({ id });
    await db.collection(`${LEDGER}_log`).insertOne({ id, revertedAt: now() });
    reverted.push(id);
  }
  return reverted;
}
