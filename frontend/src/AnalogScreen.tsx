import { useState } from 'react'
import { CatalogRelayDiagram } from './CatalogRelayDiagram'
import type { AnalogAssessment } from './engineeringIO'

export function AnalogScreen({ assessment, model, source }: {
  assessment: AnalogAssessment | undefined; model: string; source: string
}) {
  const [selection, setSelection] = useState('')
  const candidate = assessment?.candidates.find(item => item.model === model)
  if (!assessment || !candidate) return <p>Current backend analog screening is unavailable.</p>
  const layouts = candidate.layouts
  const active = layouts.find(layout => `${layout.y}/${layout.z}` === selection) ?? layouts[0]
  return <section className="input-fit" aria-label={`${model} backend analog screen`}>
    <h4>Analog input screening</h4>
    <p><strong>Study envelope</strong> · {assessment.phase_banks_min}–{assessment.phase_banks_max} phase CT banks · {assessment.neutral_inputs ?? 'Unknown'} neutral CT inputs · {assessment.vt_banks ?? 'Unknown'} VT banks</p>
    <p><strong>{candidate.screening.replaceAll('_', ' ')}</strong> · Unreviewed capacity examples.</p>
    <p>{assessment.phase_basis}</p>
    {candidate.t60_cases.map(item => <p key={item.phase_banks}>
      <strong>{item.phase_banks} phase CT banks</strong> · {item.within_three_module_example
        ? `${item.current_only_modules} × 8CT + ${item.mixed_modules} × 4CT/4VT historical capacity example.`
        : 'Exceeds the modeled three-module combinations.'}
      {!item.vt_requirement_known && ' VT requirements are unknown; this example reserves no VT modules.'}
      {item.populated_phase_banks >= 5 && ' Software and firmware for five or six populated phase banks remain unverified.'}
      {' Neutral/ground-channel assignment remains unverified.'}
    </p>)}
    {layouts.map(layout => <button className="input-layout input-layout-choice" type="button" key={`${layout.y}/${layout.z}`}
      aria-pressed={active === layout} onClick={() => setSelection(`${layout.y}/${layout.z}`)}>
      <strong>{layout.neutral_inputs > 0 ? 'Keep dedicated neutral inputs' : 'Trade neutral inputs for a phase CT bank'}</strong>
      <span>{layout.phase_banks} phase CT banks · {layout.neutral_inputs} neutral CT inputs · {layout.vt_banks} VT banks</span>
      <span className="layout-condition">{layout.fit}</span>
    </button>)}
    <p>{candidate.ordering_block}</p>
    <p>{candidate.source_urls.map(url => <a href={url} key={url} target="_blank" rel="noreferrer">Analog reference ↗ </a>)}</p>
    {(!model.startsWith('SEL-487E') || active) && <CatalogRelayDiagram model={model} source={source} selLayout={active} />}
  </section>
}
