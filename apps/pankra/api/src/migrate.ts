import { MongoClient } from 'mongodb';
import { loadConfig } from './config.js';
import { migrations } from './migrations/index.js';
import { migrateDown, migrateUp } from './migrations/runner.js';

// npm run migrate            apply pending migrations
// npm run migrate -- down 1  revert the newest one (rollback)
const config = loadConfig();
const client = await MongoClient.connect(config.mongodbUri);
const db = client.db(config.dbName);
const [cmd, n] = process.argv.slice(2);
const ids = cmd === 'down' ? await migrateDown(db, migrations, Number(n ?? 1)) : await migrateUp(db, migrations);
console.log(JSON.stringify({ [cmd === 'down' ? 'reverted' : 'applied']: ids }));
await client.close();
