export type Ct = 'unknown' | 'present' | 'absent'
export type Auxiliary = 'unknown' | 'included' | 'excluded'

export interface Bay {
  id: string
  branches: string[]
  ct: Ct
}

export const ctInventoryFields = [
  ['lv_breaker_135', 'Collector breaker · bus side', 2],
  ['lv_breaker_246', 'Collector breaker · PV circuit side', 2],
  ['hv_breaker_135', 'HV breaker · POI side', 2],
  ['hv_breaker_246', 'HV breaker · transformer side', 2],
  ['transformer_hv_phase', 'Transformer HV phase', 3],
  ['transformer_lv_phase', 'Transformer LV phase', 3],
  ['transformer_hv_neutral', 'Transformer HV neutral', 2],
  ['transformer_lv_neutral', 'Transformer LV neutral', 2],
] as const

export type CtInventory = Record<typeof ctInventoryFields[number][0], number | null>

export function defaultCtInventory(): CtInventory {
  return Object.fromEntries(ctInventoryFields.map(([key, , count]) => [key, count])) as CtInventory
}

export interface Study {
  title: string
  hv_kv: number
  mv_kv: number
  lv_ct: Ct
  hv_ct: Ct
  bays: Bay[]
  auxiliary: Auxiliary
  ct_inventory?: CtInventory | null
}

export function withInventoryBoundaries(study: Study): Study {
  const inventory = study.ct_inventory
  if (!inventory) return study

  const phaseStatus = (count: number | null): Ct =>
    count === null ? 'unknown' : count === 0 ? 'absent' : 'present'

  return {
    ...study,
    hv_ct: phaseStatus(inventory.hv_breaker_135),
    lv_ct: phaseStatus(inventory.transformer_lv_phase),
    bays: study.bays.map(bay => ({ ...bay, ct: phaseStatus(inventory.lv_breaker_246) })),
  }
}

export interface Candidate {
  id: string
  title: string
  status: string
  reason: string
  trip_targets: string[]
}

export interface ProtectionZone {
  id: 'transformer' | 'bus' | 'combined'
  title: string
  status: string
  boundaries: { label: string; state: Ct }[]
  trip_targets: string[]
}

export interface Analysis {
  counts: {
    breakers: number
    branches: number
    confirmed_bay_cts: number
    combined_required_banks: number | null
    combined_phase_channels: number | null
  }
  trip_basis: string
  zones: ProtectionZone[]
  candidates: Candidate[]
  questions: { field: string; prompt: string; why: string }[]
}

export interface Snapshot {
  study: Study
  analysis: Analysis
}

export const ctLabels: Record<Ct, string> = {
  unknown: 'Unknown',
  present: 'Present',
  absent: 'Absent',
}

export const auxiliaryLabels: Record<Auxiliary, string> = {
  unknown: 'Unknown',
  included: 'Measured boundary',
  excluded: 'Excluded in model',
}

export interface DrawingDraft {
  scope: 'supported' | 'uncertain' | 'unsupported'
  title: string
  hv_kv: number | null
  mv_kv: number | null
  hv_ct: Ct
  lv_ct: Ct
  bays: Bay[]
  notes: string[]
}
