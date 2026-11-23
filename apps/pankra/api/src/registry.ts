import { Ajv2020, type ErrorObject } from 'ajv/dist/2020.js';
import type { Edge, NodeSummary, RegistryNode, SyncReport } from '@pankra/shared';
import type { FetchLike } from './providers/types.ts';
import type { Store } from './store.ts';

export interface RegistryConfig {
  /** GitHub owner/repo holding registry/, e.g. miricoder/project-kit. */
  repo: string;
  /** Branch or tag; pin a tag for a release. */
  ref: string;
}

export interface SyncDeps {
  store: Store;
  fetch: FetchLike;
  config: RegistryConfig;
  now: () => Date;
  /** Audit entries are written for this user (the single owner). */
  auditUserId?: string;
}

interface IndexEntry {
  kind: NodeSummary['kind'];
  name: string;
  version: string;
  files: string[];
}

const MAX_FILE_BYTES = 256 * 1024;
const TIMEOUT_MS = 20_000;
const NAME = /^[a-z0-9][a-z0-9-]{1,63}$/;

class SyncError extends Error {}

function rawUrl(config: RegistryConfig, path: string): string {
  return `https://raw.githubusercontent.com/${config.repo}/${encodeURIComponent(config.ref)}/${path}`;
}

async function fetchText(deps: SyncDeps, path: string): Promise<string> {
  let res: Response;
  try {
    res = await deps.fetch(rawUrl(deps.config, path), { signal: AbortSignal.timeout(TIMEOUT_MS) });
  } catch (e) {
    throw new SyncError(`GitHub could not be reached for ${path}: ${(e as Error).message}`);
  }
  if (!res.ok) throw new SyncError(`GitHub returned HTTP ${res.status} for ${path}`);
  const text = await res.text();
  if (text.length > MAX_FILE_BYTES) throw new SyncError(`${path} is larger than ${MAX_FILE_BYTES} bytes`);
  return text;
}

function parseJson(text: string, path: string): any {
  try {
    return JSON.parse(text);
  } catch {
    throw new SyncError(`${path} is not valid JSON`);
  }
}

function describe(errors: ErrorObject[] | null | undefined): string {
  const seen = new Set<string>();
  for (const e of errors ?? []) {
    if (e.keyword === 'if') continue;
    const missing = (e.params as { missingProperty?: string }).missingProperty;
    seen.add(missing ? `missing required field "${missing}"` : `${e.instancePath || 'node'} ${e.message}`);
  }
  return [...seen].join('; ');
}

/** The registry path must stay inside registry/ for the node it belongs to. */
function safePath(path: string): boolean {
  return /^registry\/(skills|agents|plugins)\/[a-z0-9-]+\/[A-Za-z0-9_.-]+$/.test(path) && !path.includes('..');
}

function toNode(json: any, files: Record<string, string>): RegistryNode {
  return {
    kind: json.kind,
    name: json.name,
    version: json.version,
    description: json.description,
    providers: json.providers ?? {},
    requires: json.requires ?? [],
    files,
    vision: json.vision ?? false,
    tools: json.tools ?? [],
    input: json.input ?? { type: 'object' },
    output: json.output,
    steps: Array.isArray(json.steps)
      ? json.steps.map((skill: string, i: number) => ({ skill, order: i + 1 }))
      : undefined,
    skills: json.skills,
    agents: json.agents,
    retired: false,
  };
}

/**
 * Pull registry/index.json at the configured ref; load every node whose version is new,
 * validated against the registry's own schema; retire nodes no longer listed (never delete);
 * replace the edges. If GitHub cannot be reached, nothing changes and the error is recorded.
 */
export async function syncRegistry(deps: SyncDeps): Promise<SyncReport> {
  const { store, config } = deps;
  const at = deps.now().toISOString();
  const state = store.getRegistryState();
  const report: SyncReport = { ok: false, added: 0, updated: 0, retired: 0, skipped: [] };

  try {
    const index = parseJson(await fetchText(deps, 'registry/index.json'), 'registry/index.json');
    if (!Array.isArray(index?.nodes) || !Array.isArray(index?.edges)) {
      throw new SyncError('registry/index.json has no nodes or edges list');
    }
    const schema = parseJson(await fetchText(deps, 'registry/schema/node.schema.json'), 'node.schema.json');
    const ajv = new Ajv2020({ allErrors: true, strict: false });
    const validate = ajv.compile(schema);

    const listed = new Set<string>();
    for (const entry of index.nodes as IndexEntry[]) {
      const label = { kind: String(entry?.kind), name: String(entry?.name) };
      if (!entry || !NAME.test(String(entry.name)) || !Array.isArray(entry.files)) {
        report.skipped.push({ ...label, reason: 'index entry is malformed' });
        continue;
      }
      listed.add(`${entry.kind}:${entry.name}`);
      if (store.getNode(entry.kind, entry.name, entry.version)) continue; // already have this version

      try {
        const files: Record<string, string> = {};
        let nodeJson: any;
        for (const path of entry.files) {
          if (!safePath(path)) throw new SyncError(`file path ${path} is outside the registry`);
          const text = await fetchText(deps, path);
          const file = path.slice(path.lastIndexOf('/') + 1);
          if (file === 'node.json') nodeJson = parseJson(text, path);
          else files[file] = text;
        }
        if (!nodeJson) throw new SyncError('node.json is missing');
        const parsed: any = nodeJson;
        if (!validate(parsed)) throw new SyncError(describe(validate.errors));
        if (nodeJson.kind !== entry.kind || nodeJson.name !== entry.name || nodeJson.version !== entry.version) {
          throw new SyncError('node.json does not match its index entry');
        }
        const existed = store.getNode(entry.kind, entry.name) !== undefined;
        store.saveNode(toNode(nodeJson, files));
        if (existed) report.updated++;
        else report.added++;
      } catch (e) {
        // One bad node is skipped and reported; a GitHub outage stops the whole sync.
        if (e instanceof SyncError && /GitHub (returned HTTP 5|could not be reached)/.test(e.message)) throw e;
        report.skipped.push({ ...label, reason: (e as Error).message });
      }
    }

    for (const node of store.listNodes()) {
      if (!node.retired && !listed.has(`${node.kind}:${node.name}`)) {
        store.saveNode({ ...node, retired: true });
        report.retired++;
      }
    }
    const edges: Edge[] = (index.edges as Edge[])
      .filter((e) => e && typeof e.from === 'string' && typeof e.to === 'string' && typeof e.type === 'string')
      .map((e) => ({ from: e.from, to: e.to, type: e.type, ...(e.order !== undefined ? { order: Number(e.order) } : {}) }));
    store.saveEdges(edges);
    report.ok = true;
  } catch (e) {
    report.error = (e as Error).message;
  }

  store.setRegistryState({
    lastAttemptAt: at,
    lastSuccessAt: report.ok ? at : state.lastSuccessAt,
    lastError: report.ok ? null : (report.error ?? 'unknown error'),
    lastReport: report,
  });
  if (deps.auditUserId) {
    store.addAudit({
      userId: deps.auditUserId,
      action: 'registrySynced',
      at,
      detail: { ref: config.ref, ...report },
    });
  }
  return report;
}
