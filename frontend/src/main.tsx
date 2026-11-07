import { useEffect, useState } from 'react'
import type { FormEvent, ReactNode } from 'react'
import { createRoot } from 'react-dom/client'
import { OneLine } from './OneLine'
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

function Metrics({ analysis, auxiliary }: { analysis: Analysis; auxiliary: Study['auxiliary'] }) {
  const { breakers, branches, confirmed_bay_cts, combined_required_banks } = analysis.counts
  return (
    <div className="metrics">
      {[
        ['Collector breakers', breakers, 'Independent trip positions'],
        ['Outgoing branches', branches, 'Circuits downstream of the breakers'],
        ['Confirmed bay CTs', confirmed_bay_cts, 'Per collector breaker position'],
        ['Combined zone banks', boundaryCount(combined_required_banks, auxiliary), auxiliary === 'unknown' ? 'Minimum with auxiliary treatment open' : 'Required three-phase measurements'],
      ].map(([label, value, detail]) => (
        <div className="metric" key={label}><div>{label}</div><strong>{value}</strong><small>{detail}</small></div>
      ))}
    </div>
  )
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

function DeviceRequirements({ rows, auxiliary }: {
  rows: GeneratedOptions['options'][number]['device_requirements']
  auxiliary: Study['auxiliary']
}) {
  return (
    <details>
      <summary>Per-device requirements</summary>
      <p>Counts show required hardwired phase-current inputs. Check neutral CTs, VT inputs, contacts, and communication separately.</p>
      {auxiliary === 'unknown' && <p>If the auxiliary tap needs separate measurement, add one bank to the IED carrying bus differential.</p>}
      <div className="table-scroll">
        <table>
          <thead><tr><th scope="col">Device role</th><th scope="col">Functions</th><th scope="col">Phase CT banks / inputs</th><th scope="col">Check</th></tr></thead>
          <tbody>{rows.map(row => (
            <tr key={row.role}>
              <th scope="row">{row.role}</th><td>{row.functions}</td>
              <td>{row.phase_banks}{row.alternate_phase_banks && `–${row.alternate_phase_banks}`} / {row.phase_banks * 3}{row.alternate_phase_banks && `–${row.alternate_phase_banks * 3}`}</td>
              <td>{row.note}</td>
            </tr>
          ))}</tbody>
        </table>
      </div>
    </details>
  )
}

function RelayShortlist({ rows, mainBStatus }: {
  rows: GeneratedOptions['options'][number]['device_requirements']
  mainBStatus: string
}) {
  return (
    <details>
      <summary>GE / SEL device shortlist</summary>
      <p>Function evidence and the phase-input screen are preliminary. Confirm order code, CT/VT allocation, and application before selection.</p>
      {rows.map((row, index) => (
        <details key={index}>
          <summary>{row.role}</summary>
          {row.role === 'Transformer Main B' && mainBStatus !== 'Boundaries present' && (
            <p><strong>Main B boundary check</strong> · {mainBStatus}. Models below are function candidates.</p>
          )}
          <div className="table-scroll">
            <table>
              <thead><tr><th scope="col">Model</th><th scope="col">Function evidence</th><th scope="col">Phase-input screen</th><th scope="col">Configuration check</th></tr></thead>
              <tbody>{row.candidates.map(candidate => (
                <tr key={candidate.model}>
                  <th scope="row"><a href={candidate.source} target="_blank" rel="noreferrer">{candidate.manufacturer} · {candidate.model}</a></th>
                  <td>{candidate.status}</td><td>{candidate.capacity}</td><td>{candidate.note}</td>
                </tr>
              ))}</tbody>
            </table>
          </div>
          {row.candidates.filter(candidate => candidate.allocations.length > 0).map(candidate => (
            <details key={candidate.model}>
              <summary>{candidate.model} dual AC card terminal allocation</summary>
              <p>Phase counts assume the required CT measurements are routed to the elements. Verify the ordered cards, CT ratings, LV input reuse, and REF/VT needs.</p>
              <div className="table-scroll">
                <table>
                  <thead><tr><th>Y</th><th>Z</th><th>Phase CT banks</th><th>Neutral inputs</th><th>VT banks</th><th>Phase demand</th></tr></thead>
                  <tbody>{candidate.allocations.map(allocation => (
                    <tr key={`${allocation.y}/${allocation.z}`}>
                      <td>{allocation.y}</td><td>{allocation.z}</td><td>{allocation.phase_banks}</td>
                      <td>{allocation.neutral_inputs}</td><td>{allocation.vt_banks}</td><td>{allocation.fit}</td>
                    </tr>
                  ))}</tbody>
                </table>
              </div>
            </details>
          ))}
        </details>
      ))}
    </details>
  )
}

function AIProtectionOptions({ study }: { study: Study }) {
  const [result, setResult] = useState<GeneratedOptions | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function generate() {
    setBusy(true)
    setError(null)
    try {
      setResult(await getJson<GeneratedOptions>('/api/protection-options', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(study),
      }))
    } catch (error) {
      setError(error instanceof Error ? error.message : 'Unable to generate protection options.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <section className="panel">
      <PanelHeader title="AI protection options" description="Claude receives a compact station summary and selected evidence. Review its proposals alongside the wizard’s boundary checks." />
      <div className="editor-actions">
        <button type="button" className="button primary" disabled={busy || !!result} onClick={generate}>{busy ? 'Generating…' : 'Generate protection options'}</button>
      </div>
      {error && <p className="error form-error" role="alert">{error}</p>}
      {result && (
        <div className="zone-basis">
          {result.usage.input_tokens !== null && result.usage.output_tokens !== null && (
            <p>Generation usage · {result.usage.input_tokens} input tokens · {result.usage.output_tokens} output tokens</p>
          )}
          {result.options.map((option, index) => (
            <article className="candidate" key={index}>
              <div className="candidate-heading"><h3>{option.check.title}</h3><Status value={option.check.status} /></div>
              <p><strong>{hvBoundaryLabels[option.hv_boundary]}</strong> · {ctLabels[option.boundary.state]}</p>
              <p>{option.rationale}</p>
              <div className="table-scroll">
                <table>
                  <thead><tr><th scope="col">Protection path</th><th scope="col">Function</th><th scope="col">Boundary check</th></tr></thead>
                  <tbody>
                    <tr><th scope="row">Transformer Main A</th><td>{option.main_coverage.transformer_a.function}</td><td>{option.main_coverage.transformer_a.status}</td></tr>
                    <tr>
                      <th scope="row">Transformer Main B</th>
                      <td>{option.main_coverage.transformer_b.function} · {option.main_coverage.transformer_b.hv_boundary === 'unresolved' ? 'HV boundary unresolved' : hvBoundaryLabels[option.main_coverage.transformer_b.hv_boundary]}</td>
                      <td>{option.main_coverage.transformer_b.status}{option.main_coverage.transformer_b.boundaries.filter(boundary => boundary.state !== 'present').map(boundary => (
                        <div key={boundary.label}>{boundary.label} · {ctLabels[boundary.state]}</div>
                      ))}</td>
                    </tr>
                    <tr><th scope="row">Collector bus · single path</th><td>{option.main_coverage.bus.function}</td><td>{option.main_coverage.bus.status}</td></tr>
                  </tbody>
                </table>
              </div>
              {option.scheme === 'shared' && <p><strong>Proposed hardware</strong> · One IED for transformer Main A and 87B. A separate IED for transformer Main B.</p>}
              {option.main_coverage.transformer_b.coverage && <p><strong>Main B span</strong> · {option.main_coverage.transformer_b.coverage}</p>}
              {option.main_coverage.transformer_b.alternatives.length > 0 && (
                <p><strong>Main B CT locations to evaluate</strong> · {option.main_coverage.transformer_b.alternatives.map(location => hvBoundaryLabels[location]).join(' · ')}</p>
              )}
              <p>Transformer A/B independence remains unverified. Confirm CT cores, DC supplies, and trip paths.</p>
              <DeviceRequirements rows={option.device_requirements} auxiliary={study.auxiliary} />
              <RelayShortlist rows={option.device_requirements} mainBStatus={option.main_coverage.transformer_b.status} />
              <p><strong>Time-delayed backup</strong> · {option.backup}</p>
              <p><strong>Supplemental transformer protection</strong> · Evaluate REF separately using winding grounding and the phase and neutral CT assignments.</p>
              <p><strong>Open item</strong> · {option.open_item}</p>
              <p><strong>Local boundary check</strong> · {option.check.reason} {option.boundary.coverage}</p>
              {option.poi_line && <p><strong>Illustrative 87L</strong> · Local CT {ctLabels[option.poi_line.local_ct].toLowerCase()}. {option.poi_line.coverage}</p>}
              <p><strong>Preliminary trip targets</strong> · {option.check.trip_targets.join(' · ')}. Verify source paths and breaker-failure clearing.</p>
              <ul>{option.sources.map((source, sourceIndex) => <li key={sourceIndex}><a href={source.url} target="_blank" rel="noreferrer">{source.id} · {source.locator}</a></li>)}</ul>
            </article>
          ))}
          <details>
            <summary>High-impedance bus alternatives</summary>
            <p>Evaluate the CT secondary circuit, including matching CTs, burden, and stabilization. These candidates use a separate screen from the low-impedance phase-input budget.</p>
            <ul>{result.high_impedance_bus.map(candidate => (
              <li key={candidate.model}><a href={candidate.source} target="_blank" rel="noreferrer">{candidate.manufacturer} · {candidate.model}</a>{candidate.legacy && ' · Legacy, existing equipment only'}</li>
            ))}</ul>
          </details>
        </div>
      )}
    </section>
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
      <AIProtectionOptions key={JSON.stringify(scenario.study)} study={scenario.study} />
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

function ConceptStudy({ onCancel, onCreate }: { onCancel: () => void; onCreate: (snapshot: Snapshot, source: 'concept' | 'drawing') => void }) {
  const [draft, setDraft] = useState(emptyConcept)
  const [source, setSource] = useState<'concept' | 'drawing'>('concept')
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
    if (problem) return
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

  return (
    <>
      <div className="page-heading">
        <div>
          <p className="eyebrow">{review ? 'TOPOLOGY REVIEW' : source === 'drawing' ? 'DRAWING INTAKE' : 'CONCEPT ENTRY'}</p>
          <h1>{review ? 'Review topology' : 'New protection study'}</h1>
          <p>{review ? draft.title : 'Start with one transformer and a single collector bus.'}</p>
        </div>
        <button className="button secondary" type="button" onClick={onCancel} disabled={busy}>Cancel new study</button>
      </div>
      {!review && !entry && <div className="source-actions" aria-label="Study starting point">
        <button className={source === 'concept' ? 'button primary' : 'button secondary'} type="button" aria-pressed={source === 'concept'} disabled={busy} onClick={() => selectSource('concept')}>Start with a concept</button>
        <button className={source === 'drawing' ? 'button primary' : 'button secondary'} type="button" aria-pressed={source === 'drawing'} disabled={busy} onClick={() => selectSource('drawing')}>Upload a drawing</button>
      </div>}
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
  const [creating, setCreating] = useState(false)
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
      setView('comparison')
    } catch (error) {
      setFormError(error instanceof Error ? error.message : 'Unable to analyze this scenario.')
    } finally {
      setBusy(false)
    }
  }

  const visibleStudy = draft ?? baseline?.study
  const analyzedCase = scenario ?? baseline
  const activeAnalysis = analyzedCase?.analysis
  const dirty = !!draft && JSON.stringify(draft) !== JSON.stringify(scenario?.study ?? (baseline && { ...baseline.study, title: 'What-if scenario' }))
  const isDraft = !!draft && (!scenario || dirty)

  return (
    <div className="app">
      <aside className="sidebar">
        <div className="brand">
          <span className="brand-symbol"><Icon name="bolt" size={22} /></span>
          <div>Relay Selection<span>WIZARD</span></div>
        </div>
        <nav aria-label="Study views">
          <div className="nav-label">STUDY VIEWS</div>
          <button type="button" className={view === 'workspace' ? 'active' : ''} aria-current={view === 'workspace' ? 'page' : undefined} disabled={creating} onClick={() => setView('workspace')}><Icon name="diagram" size={18} /> Study workspace</button>
          <button type="button" className={view === 'comparison' ? 'active' : ''} aria-current={view === 'comparison' ? 'page' : undefined} disabled={creating} onClick={() => setView('comparison')}><Icon name="compare" size={18} /> Scenario comparison</button>
        </nav>
        <div className="sidebar-footer"><i /> Preliminary engineering</div>
      </aside>
      <main className="main">
        <header className="topbar"><span>Protection studies <b>/</b> Collector substation</span><span className="tag">{creating ? 'NEW STUDY' : conceptBaseline ? (baselineSource === 'drawing' ? 'DRAWING STUDY' : 'CONCEPT STUDY') : 'SYNTHETIC STUDY'}</span></header>
        <div className="content">
          {creating && <ConceptStudy onCancel={() => setCreating(false)} onCreate={(snapshot, source) => {
            setConceptBaseline(snapshot)
            setBaselineSource(source)
            setDraft(null)
            setScenario(null)
            setFormError(null)
            setView('workspace')
            setCreating(false)
          }} />}
          {!creating && !baseline && (loadError
            ? <div className="panel load-state"><h1>Unable to load the study</h1><p role="alert">{loadError}</p><button type="button" className="button primary" onClick={() => { setLoadError(null); setAttempt(attempt + 1) }}>Try again</button></div>
            : <div className="panel load-state" role="status">Loading the example study…</div>)}
          {!creating && baseline && (
            <>
              <div className="page-heading">
                <div><p className="eyebrow">PROTECTION STUDY</p><h1>{view === 'workspace' ? baseline.study.title : 'Scenario comparison'}</h1><p>{view === 'workspace' ? 'Review the single-line and screen preliminary protection philosophies.' : 'See how measurement and topology changes affect protection candidates.'}</p></div>
                {view === 'workspace' && <div className="study-actions">
                  <button type="button" className="button secondary" disabled={busy} onClick={() => setCreating(true)}><Icon name="plus" size={18} /> New protection study</button>
                  {!draft && <button type="button" className="button primary" onClick={createScenario}>New scenario</button>}
                </div>}
                {view === 'comparison' && draft && <button type="button" className="button secondary" onClick={() => setView('workspace')}>Edit scenario <Icon name="arrow" size={17} /></button>}
              </div>
              {view === 'workspace' && visibleStudy && analyzedCase && activeAnalysis && (
                <>
                  {isDraft && <p className="draft-note" role="status">Draft changes appear in the one-line. Counts and findings show the last analyzed case.</p>}
                  <Metrics analysis={activeAnalysis} auxiliary={analyzedCase.study.auxiliary} />
                  <div className="workspace-grid">
                    <div className="workspace-main">
                      <Topology study={visibleStudy} tag={draft ? (isDraft ? 'DRAFT' : 'SCENARIO') : 'BASELINE'} />
                      <ProtectionZoneReview {...analyzedCase} />
                      <AIProtectionOptions key={JSON.stringify(analyzedCase.study)} study={analyzedCase.study} />
                      <section className="panel">
                        <PanelHeader title="Protection philosophies" description={scenario ? 'Most recent analyzed scenario.' : 'Preliminary results for the baseline.'} />
                        {activeAnalysis.candidates.map(candidate => <CandidateCard key={candidate.id} candidate={candidate} tripBasis={activeAnalysis.trip_basis} />)}
                      </section>
                    </div>
                    <div className="workspace-side">
                      {draft ? <StudyEditor draft={draft} update={setDraft} onSubmit={analyze} onReset={() => {
                        if (scenario) setDraft(structuredClone(scenario.study))
                        else createScenario()
                        setFormError(null)
                      }} busy={busy} dirty={dirty} error={formError} /> : (
                        <section className="panel overview">
                          <PanelHeader title="Study inputs" description="Boundary CT status drives the one-line. CT counts are inventory entries, prefilled with standard defaults in new studies. Start a scenario to change these inputs." />
                          <dl><div><dt>{hvBoundaryLabels[baseline.study.hv_boundary ?? 'poi']} CT</dt><dd>{ctLabels[baseline.study.hv_ct]}</dd></div><div><dt>Transformer LV boundary CT</dt><dd>{ctLabels[baseline.study.lv_ct]}</dd></div><div><dt>Auxiliary branch</dt><dd>{auxiliaryLabels[baseline.study.auxiliary]}</dd></div><div><dt>Owner criteria</dt><dd><Status value="Pending" /></dd></div>{ctInventoryFields.map(([key, label]) => <div key={key}><dt>{label} CT count</dt><dd>{ctInventoryValue(baseline.study, key)}</dd></div>)}</dl>
                        </section>
                      )}
                      <Questions questions={activeAnalysis.questions} />
                    </div>
                  </div>
                </>
              )}
              {view === 'comparison' && <Comparison baseline={baseline} scenario={scenario} onCreate={() => draft ? setView('workspace') : createScenario()} />}
            </>
          )}
        </div>
      </main>
    </div>
  )
}

createRoot(document.getElementById('root')!).render(<App />)
