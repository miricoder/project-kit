// The web app for Vercel. With PANKRA_API_URL set (the deployed API), it is the full app;
// without it, the self-contained version: the API's routes answered in the browser with
// sample data (src/demo/), so the site works before the API is deployed.
// Output: dist-web/ (index.html + _expo/ + assets/).
import { execFileSync } from 'node:child_process';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const project = join(dirname(fileURLToPath(import.meta.url)), '..');
const full = Boolean(process.env.PANKRA_API_URL);
console.log(full ? `web build: full app, API ${process.env.PANKRA_API_URL}` : 'web build: self-contained (no PANKRA_API_URL)');

execFileSync('node', [join(project, 'scripts/bundle-registry.mjs')], { stdio: 'inherit' });
execFileSync('npx', ['expo', 'export', '--platform', 'web', '--output-dir', join(project, 'dist-web'), '--clear'], {
  cwd: join(project, 'app'),
  stdio: 'inherit',
  env: { ...process.env, CI: '1', PANKRA_PREVIEW: full ? '0' : '1' },
});
