import { MongoMemoryServer } from 'mongodb-memory-server';
import { MongoClient, type Db } from 'mongodb';
import { buildApp, type AppDeps } from '../src/app.js';
import type { Mailer, SentMail } from '../src/auth/mailer.js';
import type { Config } from '../src/config.js';

export class OutboxMailer implements Mailer {
  sent: SentMail[] = [];
  async send(mail: SentMail) { this.sent.push(mail); }
  lastToken(): string | undefined {
    const link = this.sent.at(-1)?.link;
    return link ? new URL(link).searchParams.get('token') ?? undefined : undefined;
  }
}

export const testConfig: Config = {
  port: 0,
  mongodbUri: 'unused',
  dbName: 'pankra_test',
  ownerEmail: 'owner@example.com',
  appUrl: 'https://app.example.com',
  version: 'test',
  linkTtlMinutes: 15,
  sessionTtlDays: 30,
};

export async function startDb() {
  const server = await MongoMemoryServer.create();
  const client = await MongoClient.connect(server.getUri());
  return {
    client,
    db(name = `t_${Math.random().toString(36).slice(2)}`): Db { return client.db(name); },
    async stop() { await client.close(); await server.stop(); },
  };
}

export async function makeApp(db: Db, overrides: Partial<AppDeps> = {}) {
  const mailer = new OutboxMailer();
  const app = await buildApp({ config: testConfig, db, mailer, now: () => new Date(), ...overrides });
  return { app, mailer };
}
