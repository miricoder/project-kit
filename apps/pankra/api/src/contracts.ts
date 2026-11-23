import { analyzeResult, raceFromScreen, type JSONSchema, type RegistryNode, type Run } from '@pankra/shared';
import type { ObjectStorage } from './storage.ts';
import type { Store } from './store.ts';

export interface RunImage {
  mime: string;
  data: Buffer;
}

/**
 * What PANKRA adds around a registry node: the data it reads (its `tools`, resolved before
 * the call), stricter output rules the app relies on, and what a successful run writes.
 * Writes happen only after the output has passed validation.
 */
export interface NodeContract {
  context?(store: Store, userId: string, input: Record<string, unknown>): Record<string, unknown> | string;
  /** Images the node reads (vision); a string is a refusal. */
  images?(store: Store, storage: ObjectStorage, userId: string, input: Record<string, unknown>): Promise<RunImage[] | string>;
  outputSchema?(base: JSONSchema): JSONSchema;
  finish?(output: Record<string, unknown>, context: Record<string, unknown>): Record<string, unknown>;
  persist?(store: Store, userId: string, run: Run, input: Record<string, unknown>): void;
}

const resultAnalyzer: NodeContract = {
  context(store, userId, input) {
    const sessionId = String(input.sessionId ?? '');
    const session = store.getSession(userId, sessionId);
    if (!session) return `No session ${sessionId}`;
    const result = input.resultId
      ? store.getResult(userId, String(input.resultId))
      : store.latestResultFor(userId, sessionId);
    if (!result) return 'Log a result for this session first';
    if (result.sessionId !== session.id) return 'That result belongs to another session';
    return {
      session,
      result,
      profile: store.getProfile(userId) ?? null,
      analysis: analyzeResult(session, result),
    };
  },
  // The skill promises 2 to 3 tips; the app holds it to that.
  outputSchema(base) {
    const props = (base.properties ?? {}) as Record<string, JSONSchema>;
    return { ...base, properties: { ...props, tips: { ...(props.tips ?? {}), type: 'array', minItems: 2, maxItems: 3 } } };
  },
  // Lead with the pattern worked out in code, so the numbers are never misquoted.
  finish(output, context) {
    const headline = (context.analysis as { headline?: string } | undefined)?.headline;
    const feedback = String(output.feedback ?? '');
    if (!headline || feedback.toLowerCase().includes(headline.toLowerCase())) return output;
    return { ...output, feedback: `${headline} ${feedback}`.trim() };
  },
  persist(store, userId, run, input) {
    const result = input.resultId
      ? store.getResult(userId, String(input.resultId))
      : store.latestResultFor(userId, String(input.sessionId));
    if (!result) return;
    const out = run.output as { feedback: string; tips: string[]; prs?: string[]; adjustments?: Array<{ sessionId?: string; change?: string }> };
    // Adjustments are only proposals: the app asks the athlete before changing any session.
    store.saveResult({
      ...result,
      feedback: { runId: run.id, feedback: out.feedback, tips: out.tips, prs: out.prs, adjustments: out.adjustments },
    });
  },
};

const MAX_IMAGES = 4;

/**
 * screenshot-reader: reads uploaded images; its output becomes the upload's `extracted`
 * values, parsed in code, and is never saved as a race until the athlete confirms.
 */
const screenshotReader: NodeContract = {
  async images(store, storage, userId, input) {
    const ids = Array.isArray(input.uploadIds) ? input.uploadIds.map(String) : [];
    if (ids.length === 0) return 'Upload an image first';
    if (ids.length > MAX_IMAGES) return `At most ${MAX_IMAGES} images per run`;
    const images: RunImage[] = [];
    for (const id of ids) {
      const upload = store.getUpload(userId, id);
      if (!upload) return `No upload ${id}`;
      const object = await storage.get(upload.storageKey);
      if (!object) return `The image for upload ${id} is missing`;
      images.push({ mime: object.mime, data: object.bytes });
    }
    return images;
  },
  persist(store, userId, run, input) {
    const out = run.output as { kind: string; data: Record<string, unknown>; uncertain?: Array<{ field?: string; seen?: string }> };
    const profile = store.getProfile(userId);
    for (const id of (input.uploadIds as string[]) ?? []) {
      const upload = store.getUpload(userId, id);
      if (!upload || upload.confirmed) continue;
      const extracted = raceFromScreen(out.data ?? {}, out.uncertain ?? [], {
        date: upload.createdAt.slice(0, 10),
        division: profile?.division,
      });
      store.saveUpload({ ...upload, extracted: { ...extracted, kind: out.kind || upload.kind } });
    }
  },
};

export const CONTRACTS: Record<string, NodeContract> = {
  'skill:result-analyzer': resultAnalyzer,
  'skill:screenshot-reader': screenshotReader,
};

export function contractFor(node: Pick<RegistryNode, 'kind' | 'name'>): NodeContract {
  return CONTRACTS[`${node.kind}:${node.name}`] ?? {};
}
