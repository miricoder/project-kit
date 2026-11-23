import type { Migration } from './runner.js';

const AUTH_COLLECTIONS = ['users', 'login_tokens', 'auth_sessions'];

export const migrations: Migration[] = [
  {
    id: '0001-init-auth',
    async up(db) {
      await db.collection('users').createIndex({ email: 1 }, { unique: true });
      await db.collection('users').createIndex({ userId: 1 }, { unique: true, sparse: true });
      await db.collection('login_tokens').createIndex({ tokenHash: 1 }, { unique: true });
      await db.collection('login_tokens').createIndex({ expiresAt: 1 }, { expireAfterSeconds: 0 });
      await db.collection('auth_sessions').createIndex({ tokenHash: 1 }, { unique: true });
      await db.collection('auth_sessions').createIndex({ expiresAt: 1 }, { expireAfterSeconds: 0 });
    },
    async down(db) {
      for (const name of AUTH_COLLECTIONS) {
        if (await db.listCollections({ name }).hasNext()) await db.collection(name).drop();
      }
    },
    dropsOnDown: AUTH_COLLECTIONS,
  },
];
