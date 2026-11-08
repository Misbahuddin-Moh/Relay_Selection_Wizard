import { useEffect, useState } from 'react'
import type { FormEvent, ReactNode } from 'react'
import { createRoot } from 'react-dom/client'
import { OneLine } from './OneLine'
import { Sel487eInputDiagram, T60ModulePreview } from './RelayInputDiagram'
import { extractionFile, maxDrawingBytes } from './drawingUpload'
import { auxiliaryLabels, ctInventoryFields, ctLabels, defaultCtInventory, hvBoundaryLabels, withInventoryBoundaries } from './model'
import type { Analysis, Candidate, CtInventory, DrawingDraft, GeneratedOptions, Snapshot, Study } from './model'
import './styles.css'

const icons = {
  bolt: 'M13 2 4 14h7l-1 8 10-12h-7l1-8Z',
  diagram: 'M12 3v6m0 0v3m0-3h7v3M12 9H5v3M3 12h4v5H3zm7 0h4v5h-4zm7 0h4v5h-4zM5 17v4m7-4v4m7-4v4',
  compare: 'M7 3v12m10-6v12M4 6l3-3 3 3m4 12 3 3 3-3M3 9h8m2 6h8',
  plus: 'M12 5v14M5 12h14',
  arrow: 'M5 12h14m-6-6 6 6-6 6',
  help: 'M12 17h.01M9.1 9a3 3 0 0 1 5.8 1c0 2-3 2.5-3 4m10-2a10 10 0 1 1-20 0 10 10 0 0 1 20 0Z',
  close: 'm6 6 12 12M18 6 6 18',
}

function Icon({ name, size = 20 }: { name: keyof typeof icons; size?: number }) {
  return <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.65" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d={icons[name]} /></svg>
}

async function getJson<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, init)
  if (!response.ok) {
    const body = await response.json().catch(() => null)
    const detail = body?.detail
    if (typeof detail === 'string') throw new Error(detail)
    if (Array.isArray(detail) && detail.length && typeof detail[0]?.msg === 'string') {
      const field = Array.isArray(detail[0].loc) ? detail[0].loc.slice(1).join('.') : ''
      throw new Error(field ? `${field} — ${detail[0].msg}` : detail[0].msg)
    }
    throw new Error(`The study service returned HTTP ${response.status}.`)
  }
  return response.json() as Promise<T>
}

function Select<T extends string>({ label, value, options, change }: {
  label: string
  value: T
  options: Record<T, string>
  change: (next: T) => void
}) {
  return (
    <label className="field">
      <span>{label}</span>
      <select value={value} onChange={event => change(event.target.value as T)}>
        {Object.entries(options).map(([key, name]) => <option value={key} key={key}>{String(name)}</option>)}
      </select>
    </label>
  )
}

function Status({ value }: { value: string }) {
  const readable = value.replace(/[_-]+/g, ' ')
  const category = /unavailable|unsupported|blocked|excluded|ruled|infeasible|missing measurement/i.test(readable) ? 'blocked'
    : /conditional|pending|study|review|unknown/i.test(readable) ? 'open' : 'neutral'
  return <span className={`status ${category}`}><i />{readable}</span>
}

function PanelHeader({ title, description, action }: { title: string; description: string; action?: ReactNode }) {
  return <header className="panel-header"><div><h2>{title}</h2><p>{description}</p></div>{action}</header>
}

function boundaryCount(value: number | null, auxiliary: Study['auxiliary']) {
  if (value === null) return 'Open'
  return auxiliary === 'unknown' ? `≥ ${value}` : value
}

function nextLabel(prefix: string, existing: string[]) {
  const used = new Set(existing.map(label => label.toLowerCase()))
  let id = 1
  while (used.has(`${prefix.toLowerCase()}-${id}`)) id++
  return `${prefix}-${id}`
}

const unknownCtInventory: CtInventory = {
  lv_breaker_135: null,
  lv_breaker_246: null,
  hv_breaker_135: null,
  hv_breaker_246: null,
  transformer_hv_phase: null,
  transformer_lv_phase: null,
  transformer_hv_neutral: null,
  transformer_lv_neutral: null,
}

function CtInventoryEditor({ study, update, disabled = false }: {
  study: Study
  update: (next: Study) => void
  disabled?: boolean
}) {
  const inventory = study.ct_inventory ?? unknownCtInventory
  return (
    <fieldset className="editor-fields ct-inventory" disabled={disabled}>
      <legend>Number of CTs</legend>
      <p className="draft-note">Count phase CTs per phase and neutral CTs per winding neutral. Collector settings apply to all {study.bays.length} collector breaker positions. Use 0 for none or leave blank for unknown. New studies start with standard defaults. Boundary status follows the selected HV CT location, the collector breaker PV circuit-side count, and the transformer LV phase count.</p>
      <div className="field-row">
        {ctInventoryFields.map(([key, label]) => (
          <label className="field" key={key}>
            <span>{label}</span>
            <input type="number" min="0" max="99" step="1" placeholder="Unknown" value={inventory[key] ?? ''} onChange={event => {
              const count = event.target.value === '' ? null : event.target.valueAsNumber
              update({ ...study, ct_inventory: { ...inventory, [key]: count } })
            }} />
          </label>
        ))}
      </div>
      <Select label="Station differential HV boundary" options={hvBoundaryLabels} value={study.hv_boundary ?? 'poi'} change={hv_boundary => update({ ...study, hv_boundary })} />
      <label><input type="checkbox" checked={study.include_poi_line ?? false} onChange={event => update({ ...study, include_poi_line: event.target.checked })} /> Include POI line protection area</label>
      <button type="button" className="text-button" onClick={() => update({ ...study, ct_inventory: defaultCtInventory() })}>Use standard defaults</button>
    </fieldset>
  )
}

function ctInventoryValue(study: Study, key: keyof CtInventory) {
  return study.ct_inventory?.[key] ?? 'Unknown'
}

function StudyEditor({ draft, update, onSubmit, onReset, busy, dirty, error, concept = false }: {
  draft: Study
  update: (next: Study) => void
  onSubmit: (event: FormEvent<HTMLFormElement>) => void
  onReset: () => void
  busy: boolean
  dirty: boolean
  error: string | null
  concept?: boolean
}) {
  const changeBay = (index: number, next: Study['bays'][number]) => update({
    ...draft,
    bays: draft.bays.map((bay, i) => i === index ? next : bay),
  })
  const branches = draft.bays.flatMap(bay => bay.branches)
  return (
    <section className="panel editor" id="scenario-editor">
      <PanelHeader title={concept ? "Concept inputs" : "Scenario inputs"} description={concept ? "Enter the station layout. Review CT counts in the next step." : "Edit the case, then run the engineering checks."} />
      <form noValidate onSubmit={onSubmit}>
        <fieldset disabled={busy}>
          <div className="editor-fields">
            <label className="field"><span>{concept ? "Study name" : "Scenario name"}</span><input value={draft.title} onChange={event => update({ ...draft, title: event.target.value })} maxLength={100} required /></label>
            <div className="field-row">
              <label className="field"><span>HV (kV)</span><input type="number" min="0.1" step="any" value={draft.hv_kv || ''} onChange={event => update({ ...draft, hv_kv: Number(event.target.value) })} required /></label>
              <label className="field"><span>Collector (kV)</span><input type="number" min="0.1" step="any" value={draft.mv_kv || ''} onChange={event => update({ ...draft, mv_kv: Number(event.target.value) })} required /></label>
            </div>
            <Select label="Auxiliary branch treatment" options={auxiliaryLabels} value={draft.auxiliary} change={auxiliary => update({ ...draft, auxiliary })} />
          </div>
          <div className="bay-list">
            <div className="bay-list-header"><h3>Collector breaker bays</h3><button type="button" className="text-button" disabled={draft.bays.length >= 40} onClick={() => update({ ...draft, bays: [...draft.bays, { id: nextLabel('52-F', draft.bays.map(bay => bay.id)), ct: 'unknown', branches: [nextLabel('Feeder', branches)] }] })}><Icon name="plus" size={15} /> Add bay</button></div>
            {draft.bays.map((bay, index) => (
              <details className="bay" key={concept ? index : bay.id}>
                <summary><strong>{bay.id}</strong><span>{bay.branches.length} {bay.branches.length === 1 ? 'branch' : 'branches'}</span></summary>
                <div className="bay-fields">
                  {concept && <label className="field"><span>Breaker tag</span><input value={bay.id} maxLength={100} required onChange={event => changeBay(index, { ...bay, id: event.target.value })} /></label>}
                  {bay.branches.map((branch, branchIndex) => (
                    <div className="branch-row" key={branchIndex}>
                      <label className="field"><span>Branch {branchIndex + 1}</span><input value={branch} maxLength={100} required onChange={event => changeBay(index, { ...bay, branches: bay.branches.map((name, i) => i === branchIndex ? event.target.value : name) })} /></label>
                      <button type="button" className="icon-button" aria-label={`Remove branch ${branch || branchIndex + 1} from ${bay.id}`} disabled={bay.branches.length === 1} onClick={() => changeBay(index, { ...bay, branches: bay.branches.filter((_, i) => i !== branchIndex) })}><Icon name="close" size={17} /></button>
                    </div>
                  ))}
                  <div className="bay-actions">
                    <button type="button" className="text-button" disabled={bay.branches.length >= 30} onClick={() => changeBay(index, { ...bay, branches: [...bay.branches, nextLabel('Feeder', branches)] })}><Icon name="plus" size={15} /> Add branch</button>
                    <button type="button" className="text-button danger" disabled={draft.bays.length === 1} onClick={() => update({ ...draft, bays: draft.bays.filter((_, i) => i !== index) })}>Remove bay</button>
                  </div>
                </div>
              </details>
            ))}
          </div>
          {!concept && <CtInventoryEditor study={draft} update={update} />}
          <div className="editor-actions">
            <button className="button secondary" type="button" onClick={onReset} disabled={!dirty}>Reset edits</button>
            <button className="button primary" type="submit">{concept ? 'Review topology' : busy ? 'Analyzing…' : 'Analyze scenario'}<Icon name="arrow" size={17} /></button>
          </div>
        </fieldset>
        {error && <p className="error form-error" role="alert">{error}</p>}
      </form>
    </section>
  )
}

function CandidateCard({ candidate, tripBasis }: { candidate: Candidate; tripBasis: string }) {
  return (
    <article className="candidate">
      <div className="candidate-heading"><h3>{candidate.title}</h3><Status value={candidate.status} /></div>
      <p>{candidate.reason}</p>
      {candidate.trip_targets.length > 0 && <p className="trip-targets"><strong>Proposed trip targets</strong> {candidate.trip_targets.join(' · ')}<br />{tripBasis}</p>}
    </article>
  )
}

function ProtectionZoneReview({ study, analysis }: Snapshot) {
  const options = [
    { id: 'dedicated', title: 'Separate transformer and bus zones', zones: analysis.zones.filter(zone => zone.id !== 'combined') },
    { id: 'combined', title: 'Combined transformer and bus zone', zones: analysis.zones.filter(zone => zone.id === 'combined') },
  ]

  return (
    <section className="panel">
      <PanelHeader title="Protection-zone review" description="Compare the proposed measurement boundaries and preliminary trip targets. Shading shows intended coverage, including where a CT is missing or unconfirmed." />
      <div className="zone-options">
        {options.map(option => {
          const candidate = analysis.candidates.find(item => item.id === option.id)
          return (
            <article key={option.id} className="zone-option" aria-label={option.title}>
              <div className="candidate-heading"><h3>{option.title}</h3>{candidate && <Status value={candidate.status} />}</div>
              <p><strong>{option.zones.length + analysis.feeder_areas.length + Number(!!analysis.poi_line)} protection areas</strong> in this layout</p>
              <OneLine study={study} zones={option.zones.map(zone => zone.id)} />
              {option.zones.map(zone => (
                <div className="zone-details" key={zone.id}>
                  <div className="candidate-heading">
                    <h4><i className={`zone-swatch zone-${zone.id}`} aria-hidden="true" />{zone.title}</h4>
                    <Status value={zone.status} />
                  </div>
                  <ul className="zone-boundaries">
                    {zone.boundaries.map(boundary => (
                      <li key={boundary.label}><span>{boundary.label}</span><span className={`boundary-state ${boundary.state}`}>{ctLabels[boundary.state]}</span></li>
                    ))}
                  </ul>
                  <p className="trip-targets"><strong>Proposed trip targets</strong> {zone.trip_targets.join(' · ')}</p>
                </div>
              ))}
              {candidate && <p>{candidate.reason}</p>}
            </article>
          )
        })}
      </div>
      <div className="zone-basis">
        <h3>HV boundary locations</h3>
        <ul className="zone-boundaries">
          {analysis.hv_boundaries.map(boundary => (
            <li key={boundary.id}>
              <span>{boundary.label}{boundary.id === (study.hv_boundary ?? 'poi') && <strong> · Selected</strong>}<br />{boundary.coverage}</span>
              <span className={`boundary-state ${boundary.state}`}>{ctLabels[boundary.state]}</span>
            </li>
          ))}
        </ul>
      </div>
      <div className="zone-basis">
        <h3>Collector feeder protection areas</h3>
        <p>The amber outlines show one local area per collector breaker. Circuits behind a shared breaker have a common local trip point.</p>
        <div className="table-scroll">
          <table>
            <thead><tr><th>Local trip breaker</th><th>Circuits served</th><th>PV circuit-side CT</th><th>Bus-side CT</th></tr></thead>
            <tbody>{analysis.feeder_areas.map(area => (
              <tr key={area.breaker}>
                <th scope="row">{area.breaker}</th><td>{area.circuits.join(', ')}</td>
                {area.measurements.map(measurement => <td key={measurement.label}>{ctLabels[measurement.state]}</td>)}
              </tr>
            ))}</tbody>
          </table>
        </div>
      </div>
      {analysis.poi_line && <div className="zone-basis">
        <h3>POI line protection area · 87L example</h3>
        <p>Remote line CT to the transformer-side CT of the HV breaker. Local CT {ctLabels[analysis.poi_line.local_ct].toLowerCase()}. Confirm the remote endpoint, CT assignments, communications, and local and remote trip paths.</p>
        <p>{analysis.poi_line.coverage}</p>
      </div>}
      <p className="zone-basis"><strong>Auxiliary tap</strong> {study.auxiliary === 'included'
        ? 'Modeled as a separately measured boundary for the bus and combined zones.'
        : study.auxiliary === 'excluded'
          ? 'Excluded from the measurement model. Verify actual tap treatment.'
          : 'Measurement treatment is open for the bus and combined zones.'}</p>
      <p className="zone-basis">{analysis.trip_basis}</p>
    </section>
  )
}

function TerminalAllocation({ candidate, device, neutral, vt }: {
  candidate: Option['device_requirements'][number]['candidates'][number]
  device: Option['device_requirements'][number]
  neutral: string
  vt: string
}) {
  const [selectedLayout, setSelectedLayout] = useState('')
  const complete = neutral !== '' && vt !== ''
  const layouts = candidate.allocations.filter(layout =>
    layout.fit !== 'Insufficient phase banks' &&
    (neutral === '' || layout.neutral_inputs >= Number(neutral)) &&
    (vt === '' || layout.vt_banks >= Number(vt)),
  )
  const active = layouts.find(layout => `${layout.y}/${layout.z}` === selectedLayout) ?? layouts[0]

  return (
    <section className="input-fit" aria-label="Input fit">
      <h4>Input fit</h4>
      <p><strong>Study needs</strong> · {phaseDemand(device)} · {neutral || 'Unknown'} neutral CT inputs · {vt || 'Unknown'} VT banks</p>
      <p>{layouts.length === 0
        ? 'No modeled layout meets the entered requirements.'
        : !complete ? 'Possible layouts based on known inputs. Confirm neutral and VT requirements.'
          : layouts.some(layout => layout.fit === 'All listed phase cases')
            ? 'At least one layout meets the modeled input requirements.'
            : 'Fits only the lower phase demand. Confirm which phase case applies.'}</p>
      {layouts.map(layout => (
        <button className="input-layout input-layout-choice" type="button" key={`${layout.y}/${layout.z}`}
          aria-pressed={active === layout} onClick={() => setSelectedLayout(`${layout.y}/${layout.z}`)}>
          <strong>{layout.neutral_inputs > 0 ? 'Keep dedicated neutral inputs' : 'Trade neutral inputs for a phase CT bank'}</strong>
          <span>{layout.phase_banks} phase CT banks · {layout.neutral_inputs} neutral CT inputs · {layout.vt_banks} VT banks</span>
          {layout.fit === 'Lower phase demand only' && <span className="layout-condition">Fits only the lower phase demand.</span>}
          {layout.neutral_inputs === 0 && <span className="layout-condition">This layout leaves no dedicated neutral CT inputs.</span>}
        </button>
      ))}
      {active && <Sel487eInputDiagram neutralInputs={active.neutral_inputs} vtBanks={active.vt_banks} />}
    </section>
  )
}

type Option = GeneratedOptions['options'][number]
type Requirements = { neutral: string; vt: string }
const unknownRequirements = { neutral: '', vt: '' }

function phaseDemand(device: Option['device_requirements'][number]) {
  const { phase_banks: banks, alternate_phase_banks: alternate } = device
  return alternate == null ? `${banks} phase CT banks · ${banks * 3} phase inputs`
    : `${banks}–${alternate} phase CT banks · ${banks * 3}–${alternate * 3} phase inputs`
}

function StudySteps({ step }: { step: number }) {
  return (
    <ol className="study-steps" aria-label="Study progress">
      {['Station', 'Protection scheme', 'Device requirements', 'Relay shortlist'].map((label, index) => (
        <li key={label} aria-current={step === index + 1 ? 'step' : undefined} className={step === index + 1 ? 'current' : step > index + 1 ? 'complete' : ''}>
          <span>{index + 1}</span>{label}
        </li>
      ))}
    </ol>
  )
}

function SelectedCoverage({ option, study }: { option: Option; study: Study }) {
  const zones = option.zones.filter(zone => option.scheme === 'combined' ? zone.id === 'combined' : zone.id !== 'combined')
  return (
    <section className="panel">
      <PanelHeader title={option.check.title} description={option.rationale} action={<Status value={option.check.status} />} />
      <div className="scheme-detail">
        <OneLine study={{ ...study, hv_boundary: option.hv_boundary, hv_ct: option.boundary.state }} zones={zones.map(zone => zone.id)} />
        <div className="scheme-notes">
          <h3>Protection paths</h3>
          <dl>
            <div><dt>Transformer Main A</dt><dd>{option.main_coverage.transformer_a.function} · {option.main_coverage.transformer_a.status}</dd></div>
            <div><dt>Transformer Main B</dt><dd>87T · {option.main_coverage.transformer_b.hv_boundary === 'unresolved' ? 'HV boundary unresolved' : hvBoundaryLabels[option.main_coverage.transformer_b.hv_boundary]} · {option.main_coverage.transformer_b.status}</dd></div>
            <div><dt>Collector bus</dt><dd>{option.main_coverage.bus.function} · {option.main_coverage.bus.status}</dd></div>
          </dl>
          <p>{option.check.reason}</p>
          <p><strong>Open item</strong> · {option.open_item}</p>
        </div>
      </div>
      <details className="detail-block">
        <summary>Boundaries, trip targets and evidence</summary>
        <p>{option.boundary.coverage}</p>
        {zones.map(zone => <p key={zone.id}><strong>{zone.title}</strong> · {zone.boundaries.map(boundary => `${boundary.label} (${ctLabels[boundary.state]})`).join(' · ')}</p>)}
        <p><strong>Preliminary trip targets</strong> · {option.check.trip_targets.join(' · ')}. Verify source paths and breaker-failure clearing.</p>
        {option.main_coverage.transformer_b.coverage && <p><strong>Main B span</strong> · {option.main_coverage.transformer_b.coverage}</p>}
        {option.main_coverage.transformer_b.alternatives.length > 0 && <p><strong>Main B CT locations to evaluate</strong> · {option.main_coverage.transformer_b.alternatives.map(location => hvBoundaryLabels[location]).join(' · ')}</p>}
        {option.poi_line && <p><strong>Illustrative 87L</strong> · Local CT {ctLabels[option.poi_line.local_ct].toLowerCase()}. {option.poi_line.coverage}</p>}
        <p><strong>Time-delayed backup</strong> · {option.backup}</p>
        <p>Evaluate REF separately. Confirm transformer A/B independence, including CT cores, DC supplies and trip paths.</p>
        <ul>{Array.from(new Map(option.sources.map(source => [`${source.id}:${source.locator}`, source])).values()).map(source => (
          <li key={`${source.id}:${source.locator}`}><a href={source.url} target="_blank" rel="noreferrer">{source.id} · {source.locator}</a></li>
        ))}</ul>
      </details>
    </section>
  )
}

function DeviceInput({ label, value, onChange }: { label: string; value: string; onChange: (value: string) => void }) {
  return (
    <label className="field"><span>{label}</span>
      <input type="number" inputMode="numeric" min="0" step="1" placeholder="Unknown" value={value} onChange={event => {
        const next = event.target.value
        if (next === '' || (Number.isSafeInteger(Number(next)) && Number(next) >= 0)) onChange(next)
      }} />
    </label>
  )
}

function ProtectionWorkflow({ study, analysis, onStation }: Snapshot & { onStation: () => void }) {
  const [preview, setPreview] = useState<GeneratedOptions | null>(null)
  const [generated, setGenerated] = useState<GeneratedOptions | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [previewError, setPreviewError] = useState<string | null>(null)
  const [retry, setRetry] = useState(0)
  const [step, setStep] = useState(2)
  const [selection, setSelection] = useState('')
  const [role, setRole] = useState(0)
  const [requirements, setRequirements] = useState<Record<string, Requirements>>({})
  const options = [
    ...(preview?.options.map((option, index) => ({ option, id: `local-${index}`, source: 'Station checks' })) ?? []),
    ...(generated?.options.map((option, index) => ({ option, id: `ai-${index}`, source: 'AI proposal' })) ?? []),
  ]
  const selected = options.find(item => item.id === selection)
  const option = selected?.option
  const row = option?.device_requirements[role]
  const values = (index: number) => requirements[`${selection}/${index}`] ?? unknownRequirements

  useEffect(() => {
    const controller = new AbortController()
    setPreviewError(null)
    getJson<GeneratedOptions>('/api/protection-preview', {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(study), signal: controller.signal,
    }).then(setPreview).catch(error => { if (!controller.signal.aborted) setPreviewError(error.message) })
    return () => controller.abort()
  }, [study, retry])

  async function generate() {
    setBusy(true)
    setError(null)
    try {
      setGenerated(await getJson<GeneratedOptions>('/api/protection-options', {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(study),
      }))
    } catch (error) {
      setError(error instanceof Error ? error.message : 'Unable to generate protection options.')
    } finally {
      setBusy(false)
    }
  }

  function changeStep(next: number) {
    setStep(next)
    window.scrollTo(0, 0)
  }

  return (
    <>
      <StudySteps step={step} />
      {step === 2 && <>
        <div className="stage-intro">
          <div><h2>Choose a protection scheme</h2><p>Compare zone boundaries first. Relay models come after you confirm the device inputs.</p></div>
          <button type="button" className="button secondary" onClick={generate} disabled={busy || !!generated}>{busy ? 'Generating…' : generated ? 'AI alternatives added' : 'Generate AI alternatives'}</button>
        </div>
        {error && <p className="draft-note" role="alert">{error} You can continue with the station checks below.</p>}
        {previewError && <p role="alert" className="draft-note">{previewError} <button type="button" className="text-button" onClick={() => setRetry(retry + 1)}>Retry station checks</button></p>}
        {!preview && !previewError && <p role="status">Loading station checks…</p>}
        <fieldset className="scheme-choices">
          <legend className="sr-only">Protection scheme</legend>
          {options.map(item => (
            <label className={`scheme-choice${item.id === selection ? ' selected' : ''}`} key={item.id}>
              <input type="radio" name="scheme" checked={item.id === selection} onChange={() => { setSelection(item.id); setRole(0) }} />
              <span><small>{item.source}</small><strong>{item.option.check.title}</strong><span>{item.option.rationale}</span></span>
              <Status value={item.option.check.status} />
            </label>
          ))}
        </fieldset>
        {option && <SelectedCoverage option={option} study={study} />}
        <details className="panel detail-block"><summary>Open engineering questions</summary><Questions questions={analysis.questions} /></details>
        {generated?.usage.input_tokens != null && <p className="workflow-meta">AI usage · {generated.usage.input_tokens} input / {generated.usage.output_tokens} output tokens</p>}
      </>}
      {step === 3 && option && (
        <section className="panel">
          <PanelHeader title="Review device requirements" description={option.check.title} />
          <div className="detail-block"><p>Phase demand comes from the selected scheme. Set neutral CT and VT requirements for each device. A blank field means unknown.</p>
            {study.auxiliary === 'unknown' && <p className="draft-note">A separately measured auxiliary tap may add one phase bank to bus differential.</p>}
          </div>
          <div className="requirement-grid">{option.device_requirements.map((device, index) => (
            <article className="requirement-card" key={index}>
              <h3>{device.role}</h3><p>{device.functions} · {phaseDemand(device)}</p>
              <div className="field-row">
                <DeviceInput label="Neutral CT inputs" value={values(index).neutral} onChange={neutral => setRequirements({ ...requirements, [`${selection}/${index}`]: { ...values(index), neutral } })} />
                <DeviceInput label="Three-phase VT banks" value={values(index).vt} onChange={vt => setRequirements({ ...requirements, [`${selection}/${index}`]: { ...values(index), vt } })} />
              </div>
              <p>{device.note}</p>
            </article>
          ))}</div>
        </section>
      )}
      {step === 4 && option && row && (
        <section className="panel">
          <PanelHeader title="Screen relay models" description={option.check.title} />
          <div className="detail-block">
            <label className="field"><span>Device role</span><select value={role} onChange={event => setRole(Number(event.target.value))}>{option.device_requirements.map((device, index) => <option key={index} value={index}>{device.role}</option>)}</select></label>
            <p><strong>{row.functions}</strong> · {phaseDemand(row)} · {values(role).neutral || 'Unknown'} neutral CT inputs · {values(role).vt || 'Unknown'} VT banks</p>
            {row.role === 'Transformer Main B' && option.main_coverage.transformer_b.status !== 'Boundaries present' && <p className="draft-note">Main B · {option.main_coverage.transformer_b.status}. The models below are function candidates.</p>}
            <p>Terminal fit is shown where modeled. Verify the exact order code and application before selection.</p>
          </div>
          <div className="relay-grid">
            {row.candidates.map(candidate => {
              const { neutral, vt } = values(role)
              return (
                <article className="requirement-card" key={candidate.model}>
                  <div className="candidate-heading"><h3>{candidate.model}</h3><span className="tag">{candidate.manufacturer}</span></div>
                  <p><strong>{candidate.status}</strong></p>
                  {candidate.allocations.length === 0 && <p>{candidate.capacity}</p>}
                  <p>{candidate.note}</p>
                  <a href={candidate.source} target="_blank" rel="noreferrer">Manufacturer documentation</a>
                  {candidate.allocations.length > 0 && <TerminalAllocation candidate={candidate} device={row} neutral={neutral} vt={vt} />}
                  {candidate.manufacturer === 'GE' && candidate.model.startsWith('Multilin T60') && <T60ModulePreview />}
                </article>
              )
            })}
          </div>
          <details className="detail-block">
            <summary>High-impedance bus alternatives</summary>
            <p>These require a separate CT secondary circuit check.</p>
            <ul>{(preview ?? generated)?.high_impedance_bus.map(candidate => (
              <li key={candidate.model}><a href={candidate.source} target="_blank" rel="noreferrer">{candidate.manufacturer} · {candidate.model}</a>{candidate.legacy && ' · Legacy, existing equipment only'}</li>
            ))}</ul>
          </details>
        </section>
      )}
      <div className="workflow-actions">
        <button type="button" className="button secondary" onClick={() => step === 2 ? onStation() : changeStep(step - 1)}>{step === 2 ? 'Back to station' : 'Back'}</button>
        {step < 4 && <button type="button" className="button primary" disabled={!option} onClick={() => changeStep(step + 1)}>
          {step === 2 ? 'Review device requirements' : 'Screen relay models'} <Icon name="arrow" size={16} />
        </button>}
      </div>
    </>
  )
}

function Questions({ questions }: { questions: Analysis['questions'] }) {
  return (
    <section className="panel questions">
      <PanelHeader title="Engineering questions" description="Resolve the information that affects candidate selection." />
      {questions.length ? questions.map(({ field, prompt, why }, index) => (
        <div className="question" key={`${field}-${index}`}><Icon name="help" size={17} /><div><h3>{prompt}</h3><p>{why}</p></div></div>
      )) : <p className="empty">The current screening checks have no open questions.</p>}
    </section>
  )
}

function Comparison({ baseline, scenario, onCreate }: { baseline: Snapshot; scenario: Snapshot | null; onCreate: () => void }) {
  const counts = [
    ['Collector breakers', 'breakers'],
    ['Outgoing branches', 'branches'],
    ['Confirmed bay CTs', 'confirmed_bay_cts'],
    ['Combined zone phase banks', 'combined_required_banks'],
    ['Combined zone phase channels', 'combined_phase_channels'],
  ] as const

  if (!scenario) return (
    <section className="panel compare-empty">
      <Icon name="compare" size={32} />
      <h2>Compare a scenario</h2>
      <p>Create a scenario from the baseline, edit the study inputs, and analyze the result to see the cases side by side.</p>
      <button type="button" className="button primary" onClick={onCreate}><Icon name="plus" size={17} /> New scenario</button>
    </section>
  )

  return (
    <div className="comparison">
      <section className="panel">
        <PanelHeader title="Study comparison" description="Baseline and the most recent analyzed scenario." />
        <div className="table-scroll">
          <table>
            <thead><tr><th scope="col">Study inputs and counts</th><th scope="col">Baseline</th><th scope="col">{scenario.study.title}</th></tr></thead>
            <tbody>
              <tr><th scope="row">Transformer LV boundary CT</th><td>{ctLabels[baseline.study.lv_ct]}</td><td>{ctLabels[scenario.study.lv_ct]}</td></tr>
              <tr><th scope="row">Station differential HV boundary</th><td>{hvBoundaryLabels[baseline.study.hv_boundary ?? 'poi']} · {ctLabels[baseline.study.hv_ct]}</td><td>{hvBoundaryLabels[scenario.study.hv_boundary ?? 'poi']} · {ctLabels[scenario.study.hv_ct]}</td></tr>
              {ctInventoryFields.map(([key, label]) => <tr key={key}><th scope="row">{label} CT count</th><td>{ctInventoryValue(baseline.study, key)}</td><td>{ctInventoryValue(scenario.study, key)}</td></tr>)}
              <tr><th scope="row">Auxiliary branch treatment</th><td>{auxiliaryLabels[baseline.study.auxiliary]}</td><td>{auxiliaryLabels[scenario.study.auxiliary]}</td></tr>
              {counts.map(([label, key]) => {
                const combined = key === 'combined_required_banks' || key === 'combined_phase_channels'
                const value = (snapshot: Snapshot) => combined
                  ? boundaryCount(snapshot.analysis.counts[key], snapshot.study.auxiliary)
                  : snapshot.analysis.counts[key]
                return <tr key={key}><th scope="row">{label}</th><td>{value(baseline)}</td><td>{value(scenario)}</td></tr>
              })}
            </tbody>
          </table>
        </div>
        {(baseline.study.auxiliary === 'unknown' || scenario.study.auxiliary === 'unknown') && (
          <p className="trip-basis">≥ indicates a minimum while auxiliary branch treatment is open.</p>
        )}
      </section>
      <section className="panel">
        <PanelHeader title="Protection philosophy comparison" description="Review each candidate’s status and reasoning for both cases." />
        {baseline.analysis.candidates.map(candidate => {
          const alternative = scenario.analysis.candidates.find(item => item.id === candidate.id)
          return (
            <div className="candidate-pair" key={candidate.id}>
              <div><span className="eyebrow">BASELINE</span><CandidateCard candidate={candidate} tripBasis={baseline.analysis.trip_basis} /></div>
              <div><span className="eyebrow">SCENARIO</span>{alternative ? <CandidateCard candidate={alternative} tripBasis={scenario.analysis.trip_basis} /> : <p className="empty">No corresponding candidate.</p>}</div>
            </div>
          )
        })}
      </section>
      <ProtectionZoneReview {...scenario} />
      <Questions questions={scenario.analysis.questions} />
    </div>
  )
}

const emptyConcept: Study = {
  title: '',
  hv_kv: 0,
  mv_kv: 0,
  hv_ct: 'unknown',
  lv_ct: 'unknown',
  auxiliary: 'unknown',
  bays: [{ id: '52-F-1', branches: ['Feeder-1'], ct: 'unknown' }],
}

function normalizeStudy(draft: Study) {
  return {
    ...draft,
    title: draft.title.trim(),
    bays: draft.bays.map(bay => ({ ...bay, id: bay.id.trim(), branches: bay.branches.map(name => name.trim()) })),
  }
}

function validateStudy(study: Study) {
  if (study.ct_inventory && Object.values(study.ct_inventory).some(count => count !== null && (!Number.isInteger(count) || count < 0 || count > 99))) {
    return 'CT counts must be whole numbers from 0 to 99 or blank for unknown.'
  }

  const breakerTags = study.bays.map(bay => bay.id.toLowerCase())
  const branches = study.bays.flatMap(bay => bay.branches.map(branch => branch.toLowerCase()))
  if (!study.title) return 'Enter a study name.'
  if (![study.hv_kv, study.mv_kv].every(kv => Number.isFinite(kv) && kv >= 0.1)) {
    return 'Enter HV and collector voltages of at least 0.1 kV.'
  }
  if ([study.title, ...breakerTags, ...branches].some(label => label.length > 100)) {
    return 'Keep study, breaker, and branch names to 100 characters or fewer.'
  }
  if (breakerTags.includes('') || new Set(breakerTags).size !== breakerTags.length) return 'Enter a distinct tag for every breaker.'
  if (branches.includes('') || new Set(branches).size !== branches.length) return 'Enter a distinct name for every branch.'
  return null
}

function analyzeStudy(study: Study) {
  return getJson<Analysis>('/api/analyze', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(study),
  })
}

function Topology({ study, tag }: { study: Study; tag: string }) {
  return (
    <section className="panel topology">
      <PanelHeader title="Single-line topology" description="One MPT with a single collector bus." action={<span className="tag diagram-tag">{tag}</span>} />
      <OneLine study={study} />
      <div className="legend"><span><i className="legend-present">•</i> Boundary CT present</span><span><i className="legend-unknown">?</i> Boundary CT unknown</span><span><i className="legend-absent">×</i> Boundary CT absent</span></div>
    </section>
  )
}

function DrawingSource({ file, notes }: { file: File; notes: string[] }) {
  const [url, setUrl] = useState('')
  useEffect(() => {
    const source = URL.createObjectURL(file)
    setUrl(source)
    return () => URL.revokeObjectURL(source)
  }, [file])

  return (
    <section className="panel drawing-source">
      <PanelHeader title="Source drawing" description={file.name} />
      <div className="drawing-source-body">
        {url && file.type.startsWith('image/') && <img src={url} alt="Uploaded single-line drawing" />}
        {url && <a href={url} target="_blank" rel="noreferrer">Open original drawing</a>}
        {!!notes.length && <div>
          <h3>Extraction notes to verify</h3>
          <ul>{notes.map((note, index) => <li key={index}>{note}</li>)}</ul>
        </div>}
      </div>
    </section>
  )
}

function ConceptStudy({ onCancel, onCreate, hasStudy }: { onCancel: () => void; onCreate: (snapshot: Snapshot, source: 'concept' | 'drawing') => void; hasStudy: boolean }) {
  const [draft, setDraft] = useState(emptyConcept)
  const [source, setSource] = useState<'concept' | 'drawing' | null>(null)
  const [file, setFile] = useState<File | null>(null)
  const [provider, setProvider] = useState<'Claude' | 'OpenAI' | null>(null)
  const [entry, setEntry] = useState(false)
  const [notes, setNotes] = useState<string[]>([])

  useEffect(() => {
    const controller = new AbortController()
    getJson<{ provider: 'Claude' | 'OpenAI' | null }>('/api/drawing/status', { signal: controller.signal })
      .then(status => setProvider(status.provider)).catch(() => {})
    return () => controller.abort()
  }, [])

  function selectSource(next: 'concept' | 'drawing') {
    setSource(next)
    setEntry(false)
    setError(null)
  }

  async function extract() {
    if (!file) return
    setBusy(true)
    setError(null)
    setNotes([])
    try {
      const upload = await extractionFile(file, provider)
      const result = await getJson<DrawingDraft>('/api/drawing/extract', {
        method: 'POST',
        headers: { 'Content-Type': upload.type },
        body: upload,
      })
      setNotes(result.notes)
      if (result.scope === 'unsupported') {
        setError('The drawing appears outside the supported layout. This study requires one utility-side breaker, one MPT, one unsectioned collector bus, and no LV main breaker.')
        return
      }
      if (result.bays.length > 40 || result.bays.some(bay => bay.branches.length > 30)) {
        setError('The extracted layout exceeds the editable bay or branch limits.')
        return
      }
      if (result.scope === 'uncertain') {
        setNotes(['The drawing scope could not be established. Check the supported layout before continuing.', ...result.notes])
      }
      setDraft({
        ...emptyConcept,
        title: (result.title.trim() || file.name).slice(0, 100),
        hv_kv: result.hv_kv ?? 0,
        mv_kv: result.mv_kv ?? 0,
        hv_ct: result.hv_ct,
        lv_ct: result.lv_ct,
        bays: result.bays.length
          ? result.bays.map(({ id, ct, branches }) => ({
            id,
            ct,
            branches: branches.length ? branches : [''],
          }))
          : emptyConcept.bays.map(bay => ({ ...bay, id: '', branches: [''] })),
      })
      setEntry(true)
    } catch (error) {
      setError(error instanceof Error ? error.message : 'Unable to extract the drawing.')
    } finally {
      setBusy(false)
    }
  }
  const [review, setReview] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  function reviewTopology(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const study = withInventoryBoundaries(normalizeStudy(draft))
    const problem = validateStudy(study)
    setError(problem)
    if (problem) return
    setDraft({ ...study, ct_inventory: study.ct_inventory ?? defaultCtInventory() })
    setReview(true)
  }

  async function confirmTopology() {
    const problem = validateStudy(draft)
    setError(problem)
    if (problem || !source) return
    setBusy(true)
    try {
      const study = withInventoryBoundaries(draft)
      const analysis = await analyzeStudy(study)
      onCreate({ study, analysis }, source)
    } catch (error) {
      setError(error instanceof Error ? error.message : 'Unable to analyze this study.')
    } finally {
      setBusy(false)
    }
  }

  if (!source) return (
    <>
      <StudySteps step={1} />
      <div className="start-heading"><p className="eyebrow">NEW PROTECTION STUDY</p><h1>Start with the station</h1>
        <p>Confirm the station layout, compare protection schemes, and screen relay configurations.</p></div>
      <div className="start-paths">
        <button type="button" className="start-path" onClick={() => selectSource('drawing')}>
          <Icon name="diagram" size={24} /><strong>Upload a single-line</strong>
          <span>Review a PDF or image, then confirm the breaker layout and CTs.</span><span className="path-link">Choose drawing <Icon name="arrow" size={16} /></span>
        </button>
        <button type="button" className="start-path" onClick={() => selectSource('concept')}>
          <Icon name="plus" size={24} /><strong>Build from a concept</strong>
          <span>Enter voltages, breaker bays and circuits to create the station model.</span><span className="path-link">Enter station inputs <Icon name="arrow" size={16} /></span>
        </button>
      </div>
      <button className="button secondary" type="button" onClick={onCancel}>{hasStudy ? 'Return to current study' : 'Open example study'}</button>
    </>
  )

  return (
    <>
      <StudySteps step={1} />
      <div className="page-heading">
        <div>
          <p className="eyebrow">{source === 'drawing' ? 'DRAWING' : 'CONCEPT'}</p>
          <h1>{review ? 'Confirm the station' : source === 'drawing' && !entry ? 'Upload a single-line' : 'Enter station inputs'}</h1>
          <p>{review ? draft.title : 'One transformer and a single collector bus.'}</p>
        </div>
        <button className="button secondary" type="button" onClick={() => { setSource(null); setReview(false); setEntry(false); setError(null) }} disabled={busy}>Change starting point</button>
      </div>
      {review ? (
        <div className="workspace-grid">
          <div className="workspace-main">
            <Topology study={draft} tag={source === 'drawing' ? "DRAWING DRAFT" : "CONCEPT DRAFT"} />
            {source === 'drawing' && file && <DrawingSource file={file} notes={notes} />}
          </div>
          <section className="panel overview">
            <PanelHeader title="Confirm the modeled layout" description="Confirm one HV breaker, one MPT, one unsectioned collector bus, and no LV main breaker. Check which branches share each breaker. Keep auxiliary taps separate. Unknown measurements carry forward as open questions. Confirming makes this the active baseline and clears its prior scenario." />
            <dl>
              <div><dt>Collector breakers</dt><dd>{draft.bays.length}</dd></div>
              <div><dt>Outgoing branches</dt><dd>{draft.bays.reduce((count, bay) => count + bay.branches.length, 0)}</dd></div>
              <div><dt>Auxiliary branch</dt><dd>{auxiliaryLabels[draft.auxiliary]}</dd></div>
            </dl>
            <CtInventoryEditor study={draft} update={setDraft} disabled={busy} />
            <div className="editor-actions">
              <button className="button secondary" type="button" disabled={busy} onClick={() => { setReview(false); setError(null) }}>Edit inputs</button>
              <button className="button primary" type="button" disabled={busy} onClick={confirmTopology}>{busy ? 'Analyzing…' : 'Confirm and analyze'}</button>
            </div>
            {error && <p className="error form-error" role="alert">{error}</p>}
          </section>
        </div>
      ) : source === 'drawing' && !entry ? (
        <div className="workspace-grid">
          <section className="panel">
            <PanelHeader title="Select a single-line drawing" description={provider ? `Use a PDF, PNG, or JPEG up to 20 MiB. Extraction sends the drawing to ${provider}. Use a synthetic or approved drawing.` : "Use a PDF, PNG, or JPEG up to 20 MiB."} />
            <div className="editor-fields">
              <label className="field"><span>Drawing file</span><input type="file" accept=".pdf,.png,.jpg,.jpeg,application/pdf,image/png,image/jpeg" disabled={busy} onChange={event => {
                const selected = event.target.files?.[0]
                const allowed = selected && ['application/pdf', 'image/png', 'image/jpeg'].includes(selected.type) && selected.size > 0 && selected.size <= maxDrawingBytes
                setFile(allowed ? selected : null)
                setNotes([])
                setError(selected && !allowed ? 'Choose a nonempty PDF, PNG, or JPEG no larger than 20 MiB.' : null)
              }} /></label>
              {!provider && <p className="draft-note">Live extraction is unavailable. You can still enter the layout while viewing the drawing.</p>}
            </div>
            <div className="editor-actions">
              <button className="button secondary" type="button" disabled={!file || busy} onClick={() => {
                setDraft({ ...emptyConcept, title: file?.name.slice(0, 100) ?? '' })
                setError(null)
                setEntry(true)
              }}>Enter manually</button>
              <button className="button primary" type="button" disabled={!file || busy || !provider} onClick={extract}>{busy ? 'Extracting…' : 'Extract topology'}</button>
            </div>
            {error && <p className="error form-error" role="alert">{error}</p>}
          </section>
          {file && <DrawingSource file={file} notes={notes} />}
        </div>
      ) : (
        <div className="workspace-grid">
          <StudyEditor concept draft={draft} update={setDraft} onSubmit={reviewTopology} onReset={() => { setDraft(emptyConcept); setError(null) }} busy={false} dirty={draft !== emptyConcept} error={error} />
          {source === 'drawing' && file ? <DrawingSource file={file} notes={notes} /> : <section className="panel">
            <PanelHeader title="Build the collector layout" description="Add one bay for each breaker position. Expand a bay to assign all outgoing branches served by that breaker then review the breaker CT counts." />
          </section>}
        </div>
      )}
    </>
  )
}

function App() {
  const [example, setExample] = useState<Snapshot | null>(null)
  const [scenario, setScenario] = useState<Snapshot | null>(null)
  const [draft, setDraft] = useState<Study | null>(null)
  const [view, setView] = useState<'workspace' | 'comparison'>('workspace')
  const [loadError, setLoadError] = useState<string | null>(null)
  const [formError, setFormError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [attempt, setAttempt] = useState(0)
  const [creating, setCreating] = useState(true)
  const [stationReview, setStationReview] = useState(false)
  const [conceptBaseline, setConceptBaseline] = useState<Snapshot | null>(null)
  const [baselineSource, setBaselineSource] = useState<'concept' | 'drawing'>('concept')

  useEffect(() => {
    const controller = new AbortController()
    getJson<Snapshot>('/api/study', { signal: controller.signal }).then(setExample).catch(error => {
      if (!controller.signal.aborted) setLoadError(error.message)
    })
    return () => controller.abort()
  }, [attempt])

  const baseline = conceptBaseline ?? example

  function createScenario() {
    if (!baseline) return
    setDraft({ ...structuredClone(baseline.study), title: 'What-if scenario' })
    setFormError(null)
    setView('workspace')
    setStationReview(true)
  }

  async function analyze(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!draft) return
    const study = withInventoryBoundaries(normalizeStudy(draft))
    const problem = validateStudy(study)
    if (problem) {
      setFormError(problem)
      return
    }

    setBusy(true)
    setFormError(null)
    try {
      const analysis = await analyzeStudy(study)
      setDraft(study)
      setScenario({ study, analysis })
      setView('workspace')
      setStationReview(false)
    } catch (error) {
      setFormError(error instanceof Error ? error.message : 'Unable to analyze this scenario.')
    } finally {
      setBusy(false)
    }
  }

  const visibleStudy = draft ?? baseline?.study
  const circuitCount = visibleStudy?.bays.reduce((count, bay) => count + bay.branches.length, 0) ?? 0
  const analyzedCase = scenario ?? baseline
  const activeAnalysis = analyzedCase?.analysis
  const dirty = !!draft && JSON.stringify(draft) !== JSON.stringify(scenario?.study ?? (baseline && { ...baseline.study, title: 'What-if scenario' }))
  const isDraft = !!draft && (!scenario || dirty)

  return (
    <div className="study-app">
      <header className="study-header">
        <div className="brand"><span className="brand-symbol"><Icon name="bolt" size={21} /></span><div>Relay Selection<span>WIZARD</span></div></div>
        <div className="study-actions">
          {!creating && baseline && <>
            <button type="button" className="button secondary" disabled={busy} onClick={() => setCreating(true)}>New study</button>
            <button type="button" className="button secondary" disabled={busy} onClick={() => setView(view === 'workspace' ? 'comparison' : 'workspace')}>{view === 'workspace' ? 'Compare scenarios' : 'Back to study'}</button>
          </>}
          <span className="header-label">Preliminary engineering</span>
        </div>
      </header>
      <main className="content">
        {creating && <ConceptStudy hasStudy={!!conceptBaseline || !!scenario} onCancel={() => {
          setCreating(false)
          setView('workspace')
          if (!conceptBaseline && !scenario) setStationReview(true)
        }} onCreate={(snapshot, source) => {
          setConceptBaseline(snapshot)
          setBaselineSource(source)
          setDraft(null)
          setScenario(null)
          setFormError(null)
          setView('workspace')
          setStationReview(false)
          setCreating(false)
        }} />}
        {!creating && !baseline && (loadError
          ? <div className="panel load-state"><h1>Unable to load the example</h1><p role="alert">{loadError}</p><button type="button" className="button primary" onClick={() => { setLoadError(null); setAttempt(attempt + 1) }}>Try again</button></div>
          : <div className="panel load-state" role="status">Loading the example study…</div>)}
        {!creating && baseline && visibleStudy && analyzedCase && activeAnalysis && (
          <>
            <div className="page-heading study-context">
              <div><p className="eyebrow">{isDraft ? 'SCENARIO DRAFT' : scenario ? 'ANALYZED SCENARIO' : conceptBaseline ? (baselineSource === 'drawing' ? 'DRAWING STUDY' : 'CONCEPT STUDY') : 'EXAMPLE STUDY'}</p>
                <h1>{view === 'comparison' ? 'Scenario comparison' : visibleStudy.title}</h1>
                <p>{visibleStudy.hv_kv} / {visibleStudy.mv_kv} kV · {visibleStudy.bays.length} collector {visibleStudy.bays.length === 1 ? 'breaker' : 'breakers'} · {circuitCount} {circuitCount === 1 ? 'circuit' : 'circuits'}</p>
              </div>
              {view === 'comparison' && draft && <button className="button secondary" type="button" onClick={() => { setView('workspace'); setStationReview(true) }}>Edit scenario</button>}
            </div>
            {view === 'workspace' && (stationReview || isDraft) && <>
              <StudySteps step={1} />
              <div className="workspace-grid station-workspace">
                <div className="workspace-main">
                  <Topology study={visibleStudy} tag={isDraft ? 'DRAFT' : 'CONFIRMED'} />
                  {!isDraft && <details className="panel detail-block"><summary>Engineering questions</summary><Questions questions={activeAnalysis.questions} /></details>}
                </div>
                {draft ? <StudyEditor draft={draft} update={setDraft} onSubmit={analyze} onReset={() => {
                  if (scenario) setDraft(structuredClone(scenario.study))
                  else createScenario()
                  setFormError(null)
                }} busy={busy} dirty={dirty} error={formError} /> : (
                  <section className="panel overview">
                    <PanelHeader title="Station measurements" description="Review the confirmed CT inventory and auxiliary branch treatment." />
                    <dl><div><dt>{hvBoundaryLabels[baseline.study.hv_boundary ?? 'poi']} CT</dt><dd>{ctLabels[baseline.study.hv_ct]}</dd></div>
                      <div><dt>Transformer LV boundary CT</dt><dd>{ctLabels[baseline.study.lv_ct]}</dd></div>
                      <div><dt>Auxiliary branch</dt><dd>{auxiliaryLabels[baseline.study.auxiliary]}</dd></div>
                      {ctInventoryFields.map(([key, label]) => <div key={key}><dt>{label} CT count</dt><dd>{ctInventoryValue(baseline.study, key)}</dd></div>)}</dl>
                    <div className="editor-actions"><button type="button" className="button secondary" onClick={createScenario}>Create what-if scenario</button></div>
                  </section>
                )}
              </div>
              {isDraft && <div className="workflow-actions"><button type="button" className="button secondary" disabled={busy} onClick={() => {
                setDraft(scenario?.study ?? null)
                setFormError(null)
                setStationReview(false)
              }}>Discard draft changes</button></div>}
              {!isDraft && <div className="workflow-actions"><button type="button" className="button primary" onClick={() => setStationReview(false)}>Compare protection schemes <Icon name="arrow" size={16} /></button></div>}
            </>}
            <div hidden={view !== 'workspace' || stationReview || isDraft}>
              <ProtectionWorkflow key={JSON.stringify(analyzedCase.study)} {...analyzedCase} onStation={() => { setStationReview(true); window.scrollTo(0, 0) }} />
            </div>
            {view === 'comparison' && <Comparison baseline={baseline} scenario={scenario} onCreate={() => {
              if (draft) { setView('workspace'); setStationReview(true) }
              else createScenario()
            }} />}
          </>
        )}
      </main>
    </div>
  )
}

createRoot(document.getElementById('root')!).render(<App />)
