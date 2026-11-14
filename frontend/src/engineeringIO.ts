import { useEffect, useRef, useState } from 'react'
import type { Assessment, Study } from './model'
import type { DigitalSettings, Signal } from './DigitalIO'
export interface DigitalBudget {
  role_id: string; completeness: 'partial'; di: number; coil: number; other: number; doUsed: number; open: number
  diRequired: number; doRequired: number; coilRequired: number; fastRequired: number; formCRequired: number; fastUsed: number; formCUsed: number
  unresolved_endpoint_rows: number; complete_fit: false; ordering_block: string
  output_demands: {classes: string[]; used: number; quantity: number}[]
  category_review: {category: string; state: string; enumerated_rows: number}[]
}
export interface CardExample {
  device: string; model: string; hardware: string; screening: string; complete_fit: false
  capacities: {di: number | null; do: number | null; coil: number | null; fast: number | null; form_c: number | null}
  shortages: {di: number | null; do: number | null; coil: number | null}; ordering_block: string; gate: string; source_urls: string[]
  actual_spares: {di_percent: number | null; do_percent: number | null; coil_percent: number | null; fast_percent: number | null; form_c_percent: number | null}
  module_note: string; electrical_fit: string; module_compatibility: string; evidence_state: string
}
export interface LedgerRow {
  ledger_id: string; source_row_id: string; name: string; source: string; destination: string; method: string
  included: boolean; category: string; condition: string; authority: string; evidence_state: string; owner_state: string
  owner: {label: string; kind: string}; source_endpoint: {label: string; kind: string}; destination_endpoint: {label: string; kind: string}
  consumption: {source_relay_do: number; destination_relay_di: number; source_external_contacts: number | null; destination_coil_drives: number | null; destination_external_inputs: number | null}
  source_documents_required: {tag: string; document: string; state: string}[]
}
export interface EngineeringIOResult {
  schema_version: number; solver_version: string; matrix_version: string; request_fingerprint: string; study_fingerprint: string
  status: 'partial' | 'unsupported'; scope: Assessment['scope']; budget_completeness: 'partial'; code_status: string
  engineering_prerequisites: {status: string; reason: string}; missing_evidence: string[]
  editor: {devices: string[]; signals: Signal[]} | null
  devices: {alias: string; role_id: string; role: string}[]
  ledger: LedgerRow[]; budgets: Record<string, DigitalBudget>; card_examples: CardExample[]
  endpoint_count_basis?: string; ledger_findings?: {code: string; message: string; count: number}[]
}
export function budgetText(budget: DigitalBudget) {
  return `Partial interface budget · ${budget.di} DI / ${budget.doUsed} DO used · ${budget.diRequired} DI / ${budget.doRequired} DO with spares (${budget.coilRequired} coil-duty DO)${budget.open ? ` · ${budget.open} unresolved interface(s)` : ''}`
}
export function useEngineeringIO(study: Study, scheme: string | null, settings: DigitalSettings) {
  const [attempt, setAttempt] = useState(0)
  const [state, setState] = useState<{key: string; template: string; result: EngineeringIOResult} | null>(null)
  const [failure, setFailure] = useState<{key: string; message: string} | null>(null)
  const key = scheme ? JSON.stringify({study, scheme, settings}) : ''
  const revision = useRef({key: '', value: 0})
  if (revision.current.key !== key) revision.current = {key, value: revision.current.value + 1}
  const requestKey = `${revision.current.value}/${attempt}:${key}`
  const template = JSON.stringify([study.uid, scheme, settings.variant, study.include_poi_line, study.bays.map(bay => bay.uid)])
  useEffect(() => {
    if (!key) return
    const controller = new AbortController()
    let active = true
    setFailure(null)
    const timer = setTimeout(async () => {
      try {
        const response = await fetch('/api/engineering/io', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: key, signal: controller.signal})
        const body = await response.json()
        if (!response.ok) throw new Error(typeof body.detail === 'string' ? body.detail : 'Backend I/O calculation failed.')
        if (active) setState({key: requestKey, template, result: body})
      } catch (cause) { if (active && !controller.signal.aborted) setFailure({key: requestKey, message: cause instanceof Error ? cause.message : 'Backend I/O calculation failed.'}) }
    }, 150)
    return () => { active = false; clearTimeout(timer); controller.abort() }
  }, [key, attempt])
  const result = state?.key === requestKey ? state.result : null
  // Retain only the editor while an edit is pending. Never reuse prior derived totals or fit.
  const editor = state?.template === template ? state.result.editor : null
  const error = failure?.key === requestKey ? failure.message : null
  return {result, editor, pending: !!key && !result && !error, error, retry: () => setAttempt(value => value + 1)}
}
