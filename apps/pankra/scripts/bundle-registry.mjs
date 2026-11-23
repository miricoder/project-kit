// Packs project-kit's registry/ (index, node.json, instructions) into one JSON file for the
// browser preview, which cannot call GitHub from inside a claude.ai page.
import { readFileSync, writeFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = join(dirname(fileURLToPath(import.meta.url)), '..', '..', '..');
const index = JSON.parse(readFileSync(join(root, 'registry/index.json'), 'utf8'));
const nodes = index.nodes.map((entry) => {
  let node = {};
  const files = {};
  for (const path of entry.files) {
    const text = readFileSync(join(root, path), 'utf8');
    const name = path.slice(path.lastIndexOf('/') + 1);
    if (name === 'node.json') node = JSON.parse(text);
    else files[name] = text;
  }
  return {
    ...node,
    providers: node.providers ?? {},
    requires: node.requires ?? [],
    vision: node.vision ?? false,
    tools: node.tools ?? [],
    input: node.input ?? { type: 'object' },
    steps: Array.isArray(node.steps) ? node.steps.map((skill, i) => ({ skill, order: i + 1 })) : undefined,
    files,
    retired: false,
  };
});
const out = join(root, 'apps/pankra/app/src/demo/registry.json');
writeFileSync(out, JSON.stringify({ nodes, edges: index.edges }));
console.log(`registry: ${nodes.length} nodes, ${index.edges.length} edges -> ${out}`);
