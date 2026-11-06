import { useEffect, useState } from 'react'
import type { FormEvent, ReactNode } from 'react'
import { createRoot } from 'react-dom/client'
import { OneLine } from './OneLine'
import { auxiliaryLabels, ctLabels } from './model'
import type { Analysis, Candidate, Snapshot, Study } from './model'
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
  if (!response.ok) throw new Error(`The study service returned HTTP ${response.status}.`)
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
      <PanelHeader title={concept ? "Concept inputs" : "Scenario inputs"} description={concept ? "Enter the station layout and leave unconfirmed measurements unknown." : "Edit the case, then run the engineering checks."} />
      <form onSubmit={onSubmit}>
        <fieldset disabled={busy}>
          <div className="editor-fields">
            <label className="field"><span>{concept ? "Study name" : "Scenario name"}</span><input value={draft.title} onChange={event => update({ ...draft, title: event.target.value })} maxLength={100} required /></label>
            <div className="field-row">
              <label className="field"><span>HV (kV)</span><input type="number" min="0.1" step="any" value={draft.hv_kv || ''} onChange={event => update({ ...draft, hv_kv: Number(event.target.value) })} required /></label>
              <label className="field"><span>Collector (kV)</span><input type="number" min="0.1" step="any" value={draft.mv_kv || ''} onChange={event => update({ ...draft, mv_kv: Number(event.target.value) })} required /></label>
            </div>
            <div className="field-row">
              <Select label="Transformer HV CT" options={ctLabels} value={draft.hv_ct} change={hv_ct => update({ ...draft, hv_ct })} />
              <Select label="Transformer LV CT" options={ctLabels} value={draft.lv_ct} change={lv_ct => update({ ...draft, lv_ct })} />
            </div>
            <Select label="Auxiliary branch treatment" options={auxiliaryLabels} value={draft.auxiliary} change={auxiliary => update({ ...draft, auxiliary })} />
          </div>
          <div className="bay-list">
            <div className="bay-list-header"><h3>Collector bays</h3><button type="button" className="text-button" disabled={draft.bays.length >= 40} onClick={() => update({ ...draft, bays: [...draft.bays, { id: nextLabel('52-F', draft.bays.map(bay => bay.id)), ct: 'unknown', branches: [nextLabel('Feeder', branches)] }] })}><Icon name="plus" size={15} /> Add bay</button></div>
            {draft.bays.map((bay, index) => (
              <details className="bay" key={concept ? index : bay.id}>
                <summary><strong>{bay.id}</strong><span>{bay.branches.length} {bay.branches.length === 1 ? 'branch' : 'branches'} · CT {ctLabels[bay.ct].toLowerCase()}</span></summary>
                <div className="bay-fields">
                  {concept && <label className="field"><span>Breaker tag</span><input value={bay.id} maxLength={100} required onChange={event => changeBay(index, { ...bay, id: event.target.value })} /></label>}
                  <Select label={`${bay.id} boundary CT`} options={ctLabels} value={bay.ct} change={ct => changeBay(index, { ...bay, ct })} />
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
              <tr><th scope="row">Transformer LV CT</th><td>{ctLabels[baseline.study.lv_ct]}</td><td>{ctLabels[scenario.study.lv_ct]}</td></tr>
              <tr><th scope="row">Transformer HV CT</th><td>{ctLabels[baseline.study.hv_ct]}</td><td>{ctLabels[scenario.study.hv_ct]}</td></tr>
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
  const breakerTags = study.bays.map(bay => bay.id.toLowerCase())
  const branches = study.bays.flatMap(bay => bay.branches.map(branch => branch.toLowerCase()))
  if (!study.title) return 'Enter a study name.'
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
      <div className="legend"><span><i className="legend-present">•</i> CT present</span><span><i className="legend-unknown">?</i> CT unknown</span><span><i className="legend-absent">×</i> CT absent</span></div>
    </section>
  )
}

function ConceptStudy({ onCancel, onCreate }: { onCancel: () => void; onCreate: (snapshot: Snapshot) => void }) {
  const [draft, setDraft] = useState(emptyConcept)
  const [review, setReview] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  function reviewTopology(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const study = normalizeStudy(draft)
    const problem = validateStudy(study)
    setError(problem)
    if (problem) return
    setDraft(study)
    setReview(true)
  }

  async function confirmTopology() {
    setBusy(true)
    setError(null)
    try {
      const analysis = await analyzeStudy(draft)
      onCreate({ study: draft, analysis })
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
          <p className="eyebrow">{review ? 'STEP 2 OF 2 · TOPOLOGY REVIEW' : 'STEP 1 OF 2 · CONCEPT ENTRY'}</p>
          <h1>{review ? 'Review topology' : 'New protection study'}</h1>
          <p>{review ? draft.title : 'Start with one transformer and a single collector bus.'}</p>
        </div>
        <button className="button secondary" type="button" onClick={onCancel} disabled={busy}>Cancel new study</button>
      </div>
      {review ? (
        <div className="workspace-grid">
          <Topology study={draft} tag="CONCEPT DRAFT" />
          <section className="panel overview">
            <PanelHeader title="Confirm the modeled layout" description="Check the breaker and branch grouping before analysis. Unknown measurements will carry forward as open questions. Confirming makes this the active baseline and clears its prior scenario." />
            <dl>
              <div><dt>Collector breakers</dt><dd>{draft.bays.length}</dd></div>
              <div><dt>Outgoing branches</dt><dd>{draft.bays.reduce((count, bay) => count + bay.branches.length, 0)}</dd></div>
              <div><dt>Transformer HV CT</dt><dd>{ctLabels[draft.hv_ct]}</dd></div>
              <div><dt>Transformer LV CT</dt><dd>{ctLabels[draft.lv_ct]}</dd></div>
              <div><dt>Auxiliary branch</dt><dd>{auxiliaryLabels[draft.auxiliary]}</dd></div>
            </dl>
            <div className="editor-actions">
              <button className="button secondary" type="button" disabled={busy} onClick={() => { setReview(false); setError(null) }}>Edit concept</button>
              <button className="button primary" type="button" disabled={busy} onClick={confirmTopology}>{busy ? 'Analyzing…' : 'Confirm and analyze'}</button>
            </div>
            {error && <p className="error form-error" role="alert">{error}</p>}
          </section>
        </div>
      ) : (
        <div className="workspace-grid">
          <StudyEditor concept draft={draft} update={setDraft} onSubmit={reviewTopology} onReset={() => { setDraft(emptyConcept); setError(null) }} busy={false} dirty={draft !== emptyConcept} error={error} />
          <section className="panel">
            <PanelHeader title="Build the collector layout" description="Add one bay for each breaker position. Expand a bay to assign all outgoing branches served by that breaker and enter its CT status." />
          </section>
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
    const study = normalizeStudy(draft)
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
        <header className="topbar"><span>Protection studies <b>/</b> Collector substation</span><span className="tag">{creating || conceptBaseline ? 'CONCEPT STUDY' : 'SYNTHETIC STUDY'}</span></header>
        <div className="content">
          {creating && <ConceptStudy onCancel={() => setCreating(false)} onCreate={snapshot => {
            setConceptBaseline(snapshot)
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
                          <PanelHeader title="Study inputs" description="Start a scenario to change these inputs." />
                          <dl><div><dt>Transformer HV CT</dt><dd>{ctLabels[baseline.study.hv_ct]}</dd></div><div><dt>Transformer LV CT</dt><dd>{ctLabels[baseline.study.lv_ct]}</dd></div><div><dt>Auxiliary branch</dt><dd>{auxiliaryLabels[baseline.study.auxiliary]}</dd></div><div><dt>Owner criteria</dt><dd><Status value="Pending" /></dd></div></dl>
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
