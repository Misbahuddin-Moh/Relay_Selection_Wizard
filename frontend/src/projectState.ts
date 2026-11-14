import type { Ct, Study } from './model'
import type { DigitalSettings } from './DigitalIO'

export type RelayInputs = { neutral: string; vt: string }
export type RemoteChecks = { remoteCt: Ct; remoteModel: string; compatibleModel: string; channel: boolean; dtt: 'unknown' | 'not_required' | 'pending' | 'verified' }
export interface WorkflowChoices {
  selection: string
  requirements: Record<string, RelayInputs>
  retired_requirements: Record<string, RelayInputs>
  digital_settings: Record<string, DigitalSettings>
  digital_bay_order: string[]
  digital_include_line: boolean
  ordering_notes: Record<string, Record<string, string>>
  retired_ordering_notes: Record<string, Record<string, string>>
  line_checks: RemoteChecks
  notices: string[]
}
export const emptyChoices = (): WorkflowChoices => ({ selection: '', requirements: {}, retired_requirements: {}, digital_settings: {}, digital_bay_order: [], digital_include_line: false, ordering_notes: {}, retired_ordering_notes: {},
  line_checks: {remoteCt: 'unknown', remoteModel: '', compatibleModel: '', channel: false, dtt: 'unknown'}, notices: [] })
export interface ProjectFile {
  format: 'relay-wizard-project'
  schema_version: 1
  project_id: string
  study: Study
  draft: Study | null
  decisions: WorkflowChoices
}
export function projectFile(project_id: string, study: Study, draft: Study | null, decisions: WorkflowChoices): ProjectFile {
  // Explicit allowlist: no snapshots, derived badges, provider permissions or source bytes.
  return {format: 'relay-wizard-project', schema_version: 1, project_id, study, draft, decisions}
}
export function reconcileChoices(choices: WorkflowChoices, study: Study, roles: Set<string>): WorkflowChoices {
  const next = structuredClone(choices)
  for (const key of Object.keys(next.requirements)) {
    if (!roles.has(key)) {
      next.retired_requirements[key] = next.requirements[key]
      delete next.requirements[key]
    }
  }
  for (const key of Object.keys(next.ordering_notes)) {
    if (!roles.has(key.slice(0, key.lastIndexOf('/')))) {
      next.retired_ordering_notes[key] = next.ordering_notes[key]
      delete next.ordering_notes[key]
    }
  }
  for (const key of Object.keys(next.retired_requirements)) {
    if (roles.has(key) && !next.requirements[key]) {
      next.requirements[key] = next.retired_requirements[key]
      delete next.retired_requirements[key]
    }
  }
  for (const key of Object.keys(next.retired_ordering_notes)) {
    if (roles.has(key.slice(0, key.lastIndexOf('/'))) && !next.ordering_notes[key]) {
      next.ordering_notes[key] = next.retired_ordering_notes[key]
      delete next.retired_ordering_notes[key]
    }
  }
  if (next.selection && !next.selection.endsWith(`:${study.hv_boundary ?? 'poi'}`)) next.selection = ''
  const order = study.bays.map(bay => bay.uid)
  if (JSON.stringify(order) !== JSON.stringify(next.digital_bay_order) || !!study.include_poi_line !== next.digital_include_line) {
    const hadEdits = Object.values(next.digital_settings).some(setting => Object.keys(setting.edits).length)
    for (const setting of Object.values(next.digital_settings)) setting.edits = {}
    if (hadEdits) next.notices = [...next.notices, 'Breaker order or line scope changed. Positional digital signal edits were cleared; wiring and spare choices were retained.'].slice(-30)
    next.digital_bay_order = order
    next.digital_include_line = !!study.include_poi_line
  }
  // Pair/channel assertions are revision-sensitive; retain the remote facts, request review.
  next.line_checks.compatibleModel = ''
  next.line_checks.channel = false
  if (next.line_checks.dtt === 'verified') next.line_checks.dtt = 'pending'
  return next
}
