import { MongoClient } from 'mongodb';
import { buildApp } from './app.js';
import { LogMailer } from './auth/mailer.js';
import { loadConfig } from './config.js';
import { migrations } from './migrations/index.js';
import { migrateUp } from './migrations/runner.js';

const config = loadConfig();
const client = await MongoClient.connect(config.mongodbUri);
const db = client.db(config.dbName);
await migrateUp(db, migrations);                       // spec: migrations run on deploy
const app = await buildApp({ config, db, now: () => new Date(),
  mailer: new LogMailer((msg) => console.log(msg)) });
await app.listen({ port: config.port, host: '0.0.0.0' });
