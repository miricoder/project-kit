import { analyzeResult, type JSONSchema, type RegistryNode, type Run } from '@pankra/shared';
import type { Store } from './store.ts';

/**
 * What PANKRA adds around a registry node: the data it reads (its `tools`, resolved before
 * the call), stricter output rules the app relies on, and what a successful run writes.
 * Writes happen only after the output has passed validation.
 */
export interface NodeContract {
  context?(store: Store, userId: string, input: Record<string, unknown>): Record<string, unknown> | string;
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

export const CONTRACTS: Record<string, NodeContract> = {
  'skill:result-analyzer': resultAnalyzer,
};

export function contractFor(node: Pick<RegistryNode, 'kind' | 'name'>): NodeContract {
  return CONTRACTS[`${node.kind}:${node.name}`] ?? {};
}
