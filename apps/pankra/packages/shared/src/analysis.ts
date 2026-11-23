import { formatRest } from './card.ts';
import type { Item, Result, Session } from './types.ts';

export interface RepFact {
  label: string;
  km: number;
  timeS: number;
  kmh: number;
}

/** Numbers behind a result, worked out in code so the feedback never misreads them. */
export interface ResultAnalysis {
  reps: RepFact[];
  targetKmh?: number;
  fade?: { fromKm: number; toKm: number; fromKmh: number; toKmh: number };
  headline?: string;
}

const round = (n: number, dp: number) => Math.round(n * 10 ** dp) / 10 ** dp;

/** A drop of more than 3% from the first rep to the last is a fade. */
const FADE_THRESHOLD = 0.97;

function targetSpeed(session: Session): number | undefined {
  for (const section of session.sections) {
    for (const line of section.lines) {
      if (typeof line !== 'string' && (line as Item).speedKmh !== undefined) return (line as Item).speedKmh;
    }
  }
  return undefined;
}

export function analyzeResult(session: Session, result: Result): ResultAnalysis {
  const reps: RepFact[] = result.parts
    .filter((p) => p.distanceM !== undefined && p.timeS !== undefined && p.timeS > 0)
    .map((p) => ({
      label: p.label,
      km: round(p.distanceM! / 1000, 2),
      timeS: p.timeS!,
      kmh: round(p.distanceM! / 1000 / (p.timeS! / 3600), 1),
    }));
  const targetKmh = targetSpeed(session);
  const analysis: ResultAnalysis = { reps, targetKmh };
  if (reps.length >= 2) {
    const first = reps[0];
    const last = reps[reps.length - 1];
    if (last.km < first.km * FADE_THRESHOLD) {
      analysis.fade = { fromKm: first.km, toKm: last.km, fromKmh: first.kmh, toKmh: last.kmh };
      const sameTime = reps.every((r) => r.timeS === first.timeS);
      const time = sameTime ? ` in ${formatRest(first.timeS)} each` : '';
      const target = targetKmh !== undefined ? ` against a ${targetKmh.toFixed(1)} km/h target` : '';
      analysis.headline =
        `Fade from ${first.km.toFixed(2)} km to ${last.km.toFixed(2)} km${time} ` +
        `(${first.kmh.toFixed(1)} → ${last.kmh.toFixed(1)} km/h${target}).`;
    }
  }
  return analysis;
}
