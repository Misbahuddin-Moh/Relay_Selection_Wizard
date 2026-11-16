import type { Ct, Study } from './model'

/** Physical CT locations, not calculated overcurrent reach. */
export const collectorGeometry = {
  bus: 246, busSideCt: 261, breakerTop: 272, breakerBottom: 288,
  circuitSideCt: 309, circuitEnd: 357, feederBottom: 364,
} as const
export function collectorCtStates(study: Study, fallback: Ct): {busSide: Ct; circuitSide: Ct} {
  const state = (count: number | null): Ct => count === null ? 'unknown' : count === 0 ? 'absent' : 'present'
  return study.ct_inventory
    ? {busSide: state(study.ct_inventory.lv_breaker_135), circuitSide: state(study.ct_inventory.lv_breaker_246)}
    : {busSide: 'unknown', circuitSide: fallback}
}
