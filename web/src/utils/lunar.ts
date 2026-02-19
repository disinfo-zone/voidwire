export function normalizePhasePct(raw: number): number {
  if (!Number.isFinite(raw)) return 0;
  const n = raw % 1;
  return n < 0 ? n + 1 : n;
}

export function moonIllumination(phasePct: number): number {
  const angle = normalizePhasePct(phasePct) * 2 * Math.PI;
  return (1 - Math.cos(angle)) / 2;
}

export function moonIsWaxing(phasePct: number): boolean {
  return normalizePhasePct(phasePct) < 0.5;
}
