// Builds the claude.ai browser preview: the real web app in preview mode (src/demo/), with
// its JavaScript and images inlined into one page, as claude.ai pages load scripts only from
// a few CDNs. Output: dist-preview/index.html.
import { execFileSync } from 'node:child_process';
import { existsSync, readFileSync, writeFileSync, mkdirSync } from 'node:fs';
import { dirname, extname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const project = join(dirname(fileURLToPath(import.meta.url)), '..');
const raw = join(project, 'dist-preview', 'raw');
mkdirSync(raw, { recursive: true });

execFileSync('node', [join(project, 'scripts/bundle-registry.mjs')], { stdio: 'inherit' });
execFileSync('npx', ['expo', 'export', '--platform', 'web', '--output-dir', raw, '--clear'], {
  cwd: join(project, 'app'),
  stdio: 'inherit',
  env: { ...process.env, CI: '1', PANKRA_PREVIEW: '1' },
});

const html = readFileSync(join(raw, 'index.html'), 'utf8');
const scripts = [...html.matchAll(/<script src="([^"]+)"[^>]*><\/script>/g)].map((m) => m[1]);
if (scripts.length === 0) throw new Error('no script tags found in the export');
const style = (html.match(/<style[^>]*>([\s\S]*?)<\/style>/) ?? [])[1] ?? '';

const MIME = { '.png': 'image/png', '.jpg': 'image/jpeg', '.svg': 'image/svg+xml', '.ttf': 'font/ttf', '.gif': 'image/gif' };
let js = scripts.map((src) => readFileSync(join(raw, src.replace(/^\//, '')), 'utf8')).join('\n;\n');
// Images the bundle points at become data: URIs (the page cannot fetch them from a path).
js = js.replace(/"\/(assets\/[^"]+?\.(png|jpg|gif|svg|ttf))"/g, (whole, path) => {
  const file = join(raw, path);
  if (!existsSync(file)) return whole;
  const data = readFileSync(file).toString('base64');
  return JSON.stringify(`data:${MIME[extname(file)]};base64,${data}`);
});
// Never end the inline <script> early.
js = js.replace(/<\/script/gi, '<\\/script');

const page = `<title>PANKRA</title>
<style>
${style}
html, body { height: 100%; background: #f5f5f4; color: #111827; color-scheme: light; }
#root { display: flex; height: 100%; flex: 1; }
</style>
<div id="root"></div>
<script>
// The app's router reads the path; this page is served at a path of its own.
try { if (location.pathname !== '/') history.replaceState(null, '', '/'); } catch (e) {}
</script>
<script>
${js}
</script>
`;
const out = join(project, 'dist-preview', 'index.html');
writeFileSync(out, page);
console.log(`preview: ${out} (${(page.length / 1024 / 1024).toFixed(2)} MB)`);
