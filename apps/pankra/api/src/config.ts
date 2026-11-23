export interface Config {
  port: number;
  mongodbUri: string;
  dbName: string;
  ownerEmail: string;
  appUrl: string;
  version: string;
  linkTtlMinutes: number;
  sessionTtlDays: number;
}

function required(env: NodeJS.ProcessEnv, name: string): string {
  const value = env[name];
  if (!value) throw new Error(`missing environment variable ${name}`);
  return value;
}

/** Infrastructure settings come from the host's environment, never from the repository. */
export function loadConfig(env: NodeJS.ProcessEnv = process.env): Config {
  return {
    port: Number(env.PORT ?? 3000),
    mongodbUri: required(env, 'MONGODB_URI'),
    dbName: env.MONGODB_DB ?? 'pankra',
    ownerEmail: required(env, 'OWNER_EMAIL').toLowerCase(),
    appUrl: required(env, 'APP_URL').replace(/\/$/, ''),
    version: env.RELEASE_VERSION ?? 'dev',
    linkTtlMinutes: Number(env.LINK_TTL_MINUTES ?? 15),
    sessionTtlDays: Number(env.SESSION_TTL_DAYS ?? 30),
  };
}
