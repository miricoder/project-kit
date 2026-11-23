import { readFileSync } from 'node:fs';

export const REPO = 'miricoder/project-kit';
export const REF = 'registry-v0.1.0';
export const RAW = `https://raw.githubusercontent.com/${REPO}/${REF}/`;
/** The project-kit checkout these tests run in. */
export const ROOT = new URL('../../../../', import.meta.url);

type Override = (path: string, text: string) => string;

/** Stands in for raw.githubusercontent.com, serving this checkout's registry/ at REF. */
export function fakeGitHub(opts: { down?: boolean; override?: Override } = {}) {
  const requested: string[] = [];
  const fetchImpl = (async (url: string | URL) => {
    const u = String(url);
    requested.push(u);
    if (opts.down) return new Response('Service Unavailable', { status: 503 });
    if (!u.startsWith(RAW)) return new Response('Not Found', { status: 404 });
    const path = u.slice(RAW.length);
    if (!path.startsWith('registry/') || path.includes('..')) return new Response('Not Found', { status: 404 });
    let text: string;
    try {
      text = readFileSync(new URL(path, ROOT), 'utf8');
    } catch {
      return new Response('Not Found', { status: 404 });
    }
    return new Response(opts.override ? opts.override(path, text) : text, { status: 200 });
  }) as unknown as typeof fetch;
  return { fetchImpl, requested };
}
