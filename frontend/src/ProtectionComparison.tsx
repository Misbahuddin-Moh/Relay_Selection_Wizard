import type { GeneratedOptions, ProtectionReview } from './model'

type Choice = {id: string; source: string; option: GeneratedOptions['options'][number]}
const readinessLabels: Record<ProtectionReview['readiness'], string> = {
  blocked: 'Design blockers', conditional: 'Engineering review open', outside_scope: 'Outside supported hardware scope',
}
const measurementLabels = {
  absent: 'Required measurement absent', unknown: 'Measurement assignment unresolved', present: 'Modeled present · unreviewed',
}

export function ProtectionComparison({ choices, selection, select }: {
  choices: Choice[]; selection: string; select: (id: string) => void
}) {
  if (!choices.length) return null
  const selected = choices.find(item => item.id === selection)
  const review = selected?.option.review
  return <section className="panel protection-comparison" aria-label="Protection approach comparison">
    <div className="comparison-intro"><div><h3>Compare protection approaches</h3>
      <p>Same station, different zone and hardware choices. Measurement counts describe the model; they do not prove CT suitability, independent protection or complete clearing.</p></div>
      <span className="tag">Preliminary engineering</span>
    </div>
    <div className="table-scroll" tabIndex={0} role="region" aria-label="Protection comparison table">
      <table>
        <caption className="sr-only">Comparison of modeled protection approaches and unresolved engineering evidence</caption>
        <thead><tr><th scope="col">Engineering decision</th>{choices.map(item => <th scope="col" key={item.id} className={selection === item.id ? 'comparison-selected' : ''}>
          <span>{item.option.check.title}</span>
          <button type="button" className="text-button" aria-pressed={selection === item.id} onClick={() => select(item.id)}>
            {selection === item.id ? 'Selected approach' : 'Inspect approach'}<span className="sr-only">: {item.option.check.title}</span>
          </button>
        </th>)}</tr></thead>
        <tbody>
          <tr><th scope="row">Primary zones and functions</th>{choices.map(({id, option}) => <td key={id}>{option.main_coverage.transformer_a.function} · {option.main_coverage.bus.function}</td>)}</tr>
          <tr><th scope="row">Transformer Secondary</th>{choices.map(({id, option}) => <td key={id}>Separate 87T IED<br />{measurementLabels[option.review.secondary_measurements]}</td>)}</tr>
          <tr><th scope="row">Primary CT boundaries</th>{choices.map(({id, option}) => <td key={id}>{measurementLabels[option.review.primary_measurements]}</td>)}</tr>
          <tr><th scope="row">Primary phase CT banks</th>{choices.map(({id, option}) => <td key={id}>{option.review.roles[0] ? `${option.review.roles[0].phase_banks_min}–${option.review.roles[0].phase_banks_max} banks` : 'Unresolved'}<br /><small>Input reuse and auxiliary treatment may change demand.</small></td>)}</tr>
          <tr><th scope="row">Provisional trip targets</th>{choices.map(({id, option}) => <td key={id}>{[...new Set(option.review.zones.flatMap(zone => zone.trip_targets))].join(', ') || 'Unresolved'}<br /><small>Clearing paths unverified.</small></td>)}</tr>
          <tr><th scope="row">Readiness and evidence</th>{choices.map(({id, option}) => <td key={id}><strong>{readinessLabels[option.review.readiness]}</strong><br />{option.review.findings.filter(item => item.severity === 'blocker').length} blockers · {option.review.findings.filter(item => item.severity === 'open').length} open reviews<br /><small>Procurement release unavailable.</small></td>)}</tr>
        </tbody>
      </table>
    </div>
    {!review && <p className="comparison-prompt">Select an approach to inspect its boundaries, roles and required evidence.</p>}
    {review && selected && <details className="comparison-detail" open key={selected.id}>
      <summary>Engineering review · {selected.option.check.title}</summary>
      <p className={`comparison-readiness ${review.readiness}`}><strong>{readinessLabels[review.readiness]}</strong> · {review.summary}</p>
      <div className="comparison-zone-grid">{review.zones.map(zone => <article key={zone.id} className="comparison-zone">
        <h4>{zone.title}</h4><p><strong>{zone.function}</strong> · {measurementLabels[zone.measurement_status]}</p>
        <p>Hosted by: {zone.relay_roles.join('; ') || 'Unresolved'}</p>
        <ul>{zone.boundaries.map((boundary, index) => <li key={`${boundary.label}/${index}`}>{boundary.label}: <strong>{measurementLabels[boundary.state]}</strong></li>)}</ul>
        <p>Provisional trips: {zone.trip_targets.join(', ') || 'Unresolved'}. Clearing remains {zone.clearing_state}.</p>
      </article>)}</div>
      <details><summary>Relay roles and modeled input demand</summary>
        <ul>{review.roles.map(role => <li key={role.role_id}><strong>{role.role}</strong> · {role.functions} · {role.phase_banks_min}–{role.phase_banks_max} phase CT banks</li>)}</ul>
      </details>
      <h4>What must be resolved</h4>
      <ol className="comparison-findings">{review.findings.map(finding => <li key={finding.code} className={finding.severity}>
        <p><strong>{finding.severity === 'blocker' ? 'Blocker' : 'Open review'} · {finding.title}</strong></p>
        <p>{finding.detail}</p>
        <p><small>Basis: {finding.basis.replaceAll('_', ' ')}. Required evidence: {finding.required_evidence.join('; ') || 'Project engineering review'}.</small></p>
        {finding.sources.length > 0 && <p className="comparison-sources">{finding.sources.map(source => <a key={`${source.id}/${source.url}/${source.locator}`} href={source.url} target="_blank" rel="noreferrer">{source.id} · {source.locator} ↗</a>)}</p>}
      </li>)}</ol>
      <details><summary>Unconfirmed station assumptions</summary><ul>{review.assumptions.map(item => <li key={item.code}>{item.detail} · {item.state}</li>)}</ul></details>
      <p className="comparison-evidence-note">Reference links provide general engineering context. Approved project drawings, manufacturer acceptance and engineering approval have not been supplied.</p>
    </details>}
  </section>
}
