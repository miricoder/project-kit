/**
 * USD per million tokens (input, output). Update from the providers' pricing pages when they
 * change; an unknown model is charged at the dearest known rate, so the monthly cap errs
 * on the safe side.
 */
const PRICES: Record<string, { in: number; out: number }> = {
  'claude-sonnet-5-5': { in: 3, out: 15 },
  'claude-haiku-5-5': { in: 1, out: 5 },
  'claude-opus-5-5': { in: 5, out: 25 },
  'gpt-5': { in: 1.25, out: 10 },
  'gpt-5-mini': { in: 0.25, out: 2 },
};

const DEAREST = Object.values(PRICES).reduce(
  (a, b) => ({ in: Math.max(a.in, b.in), out: Math.max(a.out, b.out) }),
  { in: 0, out: 0 },
);

export function costUsd(model: string, tokensIn: number, tokensOut: number): number {
  const p = PRICES[model] ?? DEAREST;
  return Math.round(((tokensIn * p.in + tokensOut * p.out) / 1_000_000) * 1e6) / 1e6;
}
