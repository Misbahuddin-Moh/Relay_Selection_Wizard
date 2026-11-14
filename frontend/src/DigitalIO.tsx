import { budgetText } from './engineeringIO'
import type { CardExample, DigitalBudget, EngineeringIOResult } from './engineeringIO'
export { budgetText } from './engineeringIO'
import { useId, useState } from 'react'
import { PrimaryOrderDraft } from './PrimaryOrderDraft'

export type Signal = {
  id: number
  name: string
  source: string
  destination: string
  method: string
  di: number
  do: number
  coil: boolean
  included: boolean
  reference: string
  condition: string
}

const variants = {
  LOCK: {
    title: 'Trip through lockout relays',
    detail: 'The transformer and bus protection outputs operate 86 lockout relays. Their contacts trip the breakers and start breaker-failure timing. A separate relay handles POI breaker failure.',
  },
  DIRECT: {
    title: 'Trip breakers directly',
    detail: 'The transformer and bus protection relays use their own outputs to trip breaker coils and send separate hardwired signals to start breaker-failure timing. A separate relay still handles POI breaker failure.',
  },
  GOOSE_BFI: {
    title: 'Trip through lockouts and start breaker-failure timing over the network',
    detail: 'Breaker trips still use 86 lockout contacts. The modeled breaker-failure start signals use IEC 61850 GOOSE messages, which free up physical DI and DO points for those signals.',
  },
  LOCAL_H: {
    title: 'Put POI breaker failure in Transformer Primary',
    detail: 'Breaker trips still use 86 lockout contacts. Transformer Primary runs the POI breaker-failure logic. Its own start signal stays inside the relay, while starts from other devices use inputs on Transformer Primary.',
  },
  EXTERNAL_F: {
    title: 'Give each feeder a separate breaker-failure relay',
    detail: 'Breaker trips still use 86 lockout contacts. Each feeder gets a separate breaker-failure relay with its own input and output budget. The POI breaker-failure relay stays separate.',
  },
}
type Variant = keyof typeof variants
type Spare = { di: number; do: number; basis: 'used' | 'installed' }
export type DigitalSettings = { variant: Variant; spare: Spare; edits: Partial<Record<Variant, Signal[]>>; output_classes?: Partial<Record<Variant, Record<string, ('fast' | 'form_c')[]>>> }
export const defaultDigitalSettings: DigitalSettings = { variant: 'LOCK', spare: { di: 20, do: 20, basis: 'used' }, edits: {} }

export function PrimaryDigitalFit({ cards, variant, budget, model, phase, neutral, vt, orderingNotes, changeOrderingNotes }: {
  cards: CardExample[]
  variant: Variant
  budget: DigitalBudget
  model: string
  phase: number
  neutral: string
  vt: string
  orderingNotes: Record<string, string>
  changeOrderingNotes: (notes: Record<string, string>) => void
}) {
  const cardModel = model === 'SEL-487E-3/-4' ? 'SEL-487E-3' : model === 'Multilin T60' ? 'GE T60' : ''
  const card = cards.find(row => row.device === 'T-P' && row.model === cardModel)
  if (!card) return <p>Digital I/O fit is open. This model has no card example for the selected wiring.</p>
  const {hardware, model: name} = card
  const counts = [
    {label: 'Digital inputs', required: budget.diRequired, available: card.capacities.di, used: budget.di, spare: card.actual_spares.di_percent},
    {label: 'Total digital outputs', required: budget.doRequired, available: card.capacities.do, used: budget.doUsed, spare: card.actual_spares.do_percent},
    {label: 'Coil-duty outputs (included in total)', required: budget.coilRequired, available: card.capacities.coil, used: budget.coil, spare: card.actual_spares.coil_percent},
    {label: 'Fast outputs (can overlap other classes)', required: budget.fastRequired, available: card.capacities.fast, used: budget.fastUsed, spare: card.actual_spares.fast_percent},
    {label: 'Form-C contacts (one physical contact each)', required: budget.formCRequired, available: card.capacities.form_c, used: budget.formCUsed, spare: card.actual_spares.form_c_percent},
  ]

  return <section className="input-fit" aria-label="Transformer Primary digital I/O fit">
    <h4>Digital I/O fit</h4>
    <p>{variants[variant].title} · {name} · {hardware}</p>
    <p><strong>{card.screening === 'insufficient_nominal' ? 'This card example falls short' : card.screening === 'class_evidence_missing' ? 'Required contact class evidence is missing' : card.screening === 'within_nominal_counts' ? 'Known points fit · budget remains partial' : 'Function or capacity evidence remains unverified'}</strong></p>
    <details><summary>See point counts and hardware limits</summary>
      <div className="table-scroll">
        <table>
          <thead><tr><th scope="col">Point type</th><th scope="col">Needed with spares</th><th scope="col">Example capacity</th><th scope="col">Used points</th><th scope="col">Actual installed spares</th></tr></thead>
          <tbody>{counts.map(({ label, required, available, used, spare }) => <tr key={label}>
            <th scope="row">{label}</th><td>{required}</td>
            <td>{available ?? 'Unverified'}</td><td>{used}</td><td>{spare === null ? 'Not established' : `${spare.toFixed(1)}%`}</td>
          </tr>)}</tbody>
        </table>
      </div>
      <p>{card.module_note}</p>
    </details>
    <PrimaryOrderDraft key={JSON.stringify([variant, budget, hardware, phase, neutral, vt])}
      fields={orderingNotes} changeFields={changeOrderingNotes}
      model={cardModel === 'SEL-487E-3' ? cardModel : 'GE T60'} hardware={hardware} wiring={variants[variant].title}
      phase={phase} neutral={neutral} vt={vt} digital={budgetText(budget)} blocked={card.ordering_block} />
    <p>Before ordering, verify contact duty and that the CT/VT and digital modules fit together.</p>
    <p>{card.source_urls.map((url, index) =>
      <a key={url} href={url.trim()} target="_blank" rel="noreferrer">Card reference {index + 1} ↗ </a>)}</p>
  </section>
}

export function DigitalIO({ scheme, bays, editor, result, pending, error, retry, settings, change }: {
  scheme: string; bays: string[]; editor: NonNullable<EngineeringIOResult['editor']>; result: EngineeringIOResult | null; pending: boolean; error: string | null; retry: () => void; settings: DigitalSettings; change: (next: DigitalSettings) => void
}) {
  const [picked, setPicked] = useState('T-P')
  const [allEndpoints, setAllEndpoints] = useState(true)
  const deviceList = useId()
  const example = editor
  const device = example.devices.includes(picked) ? picked : 'T-P'
  const signals = settings.edits[settings.variant] ?? example.signals
  const related = signals.filter(signal => signal.source === device || signal.destination === device)
  const budget = result?.budgets[device]
  const label = (value: string) => value.replace(/\bF([123])\b/g, (_, number) => bays[Number(number) - 1]).replace(/\bH\b/g, 'POI breaker')
  const primaryName = scheme === 'shared' ? 'Transformer Primary + bus protection'
    : scheme === 'combined' ? 'Combined transformer + bus Primary' : 'Transformer Primary'
  const relayNames: Record<string, string> = {
    'T-P': primaryName, 'T-S': 'Transformer Secondary', BUS: 'Collector bus protection',
    'BF-H': 'POI breaker failure', 'LINE-H': 'POI line protection (local)',
  }
  bays.forEach((bay, index) => {
    relayNames[`FP-F${index + 1}`] = `${bay} feeder protection`
    relayNames[`BF-F${index + 1}`] = `${bay} breaker failure`
  })
  const relayName = (id: string) => relayNames[id] ?? label(id)
  const endpoint = (id: string) => example.devices.includes(id) ? relayName(id) : label(id)
  const setSignals = (next: Signal[]) => change({ ...settings, edits: { ...settings.edits, [settings.variant]: next } })
  const update = (id: number, patch: Partial<Signal>) => setSignals(signals.map(signal => signal.id === id ? { ...signal, ...patch } : signal))
  function add(direction: 'di' | 'do') {
    setSignals([...signals, { id: Math.max(-1, ...signals.map(signal => signal.id)) + 1,
      name: 'New signal', source: direction === 'di' ? 'External equipment' : device,
      destination: direction === 'di' ? device : 'External equipment', method: 'hardwired',
      di: Number(direction === 'di'), do: Number(direction === 'do'), coil: false, included: true,
      reference: 'User entry', condition: '' }])
  }

  return (
    <section className="detail-block digital-io" aria-label="Digital I/O budget">
      <h3>Digital I/O budget</h3>
      <p><strong>Starting assumption</strong> · {variants[settings.variant].title}</p>
      <p>Example for a straight collector bus with three feeder breakers. This is a partial interface budget. Mechanical, control, status, supervision and other categories need a complete ownership review; adding spares does not establish completeness.</p>
      <details>
        <summary>Compare wiring examples</summary>
        <p>Each example changes the trip path or which relay handles breaker failure. For a different design, start with the closest example and edit its signals below.</p>
        <fieldset>
          <legend>Wiring example</legend>
          <div className="digital-relays wiring-examples">
            {(Object.keys(variants) as Variant[]).map(variant => <label key={variant}>
              <input type="radio" name={`${deviceList}-wiring`} checked={settings.variant === variant}
                onChange={() => change({ ...settings, variant })} />
              <span><strong>{variants[variant].title}</strong><br />{variants[variant].detail}</span>
            </label>)}
          </div>
        </fieldset>
      </details>
      <fieldset>
        <legend>Relay to review</legend>
        <div className="digital-relays">
          {example.devices.map(id => {
            const counts = result?.budgets[id]
            return <label key={id}>
              <input type="radio" name={`${deviceList}-relay`} checked={device === id} onChange={() => setPicked(id)} />
              <span><strong>{relayName(id)}</strong><br />{counts ? `${counts.diRequired} DI / ${counts.doRequired} DO` : 'Pending backend calculation'}</span>
            </label>
          })}
        </div>
      </fieldset>
      <h4>{relayName(device)} signal budget</h4>
      <section aria-label="Backend I/O assessment" data-fingerprint={result?.request_fingerprint ?? ''}>
        {pending && <p role="status">Calculating backend I/O… Previous totals and fit are not current.</p>}
        {error && <p role="alert">{error} <button type="button" className="button secondary" onClick={retry}>Retry I/O calculation</button></p>}
        {budget && <><p aria-live="polite"><strong>{budgetText(budget)}</strong></p>
          <p>Backend assessment · {result?.solver_version} · {result?.matrix_version}</p>
          <p>{budget.fastRequired} fast outputs · {budget.formCRequired} form-C contacts required with spares. Class counts may overlap on one physical contact.</p>
          <details><summary>Signal category review · incomplete</summary><ul>{budget.category_review.map(item => <li key={item.category}>{item.category.replaceAll('_', ' ')}: {item.state.replaceAll('_', ' ')} ({item.enumerated_rows} rows)</li>)}</ul></details>
          <p>{budget.ordering_block}</p>
        </>}
      </section>
      <details><summary>Adjust spare I/O</summary>
        <div className="field-row">
          {(['di', 'do'] as const).map(field => <label className="field" key={field}><span>{field.toUpperCase()} spares (%)</span>
            <input type="number" min={0} max={99} value={settings.spare[field]} onChange={event => {
              const value = event.target.valueAsNumber
              if (Number.isInteger(value) && value >= 0 && value <= 99) change({ ...settings, spare: { ...settings.spare, [field]: value } })
            }} /></label>)}
          <label className="field"><span>Spare percentage basis</span><select value={settings.spare.basis}
            onChange={event => change({ ...settings, spare: { ...settings.spare, basis: event.target.value === 'installed' ? 'installed' : 'used' } })}>
            <option value="used">Used points</option><option value="installed">Installed capacity</option>
          </select></label>
        </div>
      </details>
      <details><summary>Review and edit {relayName(device)} signals</summary>
        <p>Included hardwired signals count toward relay contacts. Spares round up separately for each distinct required contact capability group; a physical contact is counted once.</p>
        <datalist id={deviceList}>{example.devices.map(id => <option key={id} value={id}>{relayName(id)}</option>)}</datalist>
        <div className="digital-io-actions">
          <button type="button" className="button secondary" onClick={() => add('di')}>Add DI</button>
          <button type="button" className="button secondary" onClick={() => add('do')}>Add DO</button>
        </div>
        {related.map(signal => {
          const di = signal.destination === device ? signal.di : 0
          const output = signal.source === device ? signal.do : 0
          const counted = signal.included && signal.method === 'hardwired' && di + output > 0
          return <fieldset className={`input-fit signal-row ${counted ? 'signal-counted' : ''}`} key={signal.id}>
            <legend>{label(signal.name)}</legend>
            <div className="signal-state">
              <label><input type="checkbox" checked={signal.included}
                onChange={event => update(signal.id, { included: event.target.checked })} /> {signal.included ? 'Included' : 'Excluded'}</label>
              <span>{counted ? `Counts ${[di && `${di} DI`, output && `${output} DO`].filter(Boolean).join(' + ')}`
                : signal.included && signal.method === 'hardwired or communicated' ? 'Wiring unresolved' : '0 physical points'}</span>
            </div>
            <p>{endpoint(signal.source)} → {endpoint(signal.destination)} · {signal.reference}</p>
            {signal.condition && <p>{signal.condition}</p>}
            <details><summary>Edit signal</summary>
              <div className="field-row">
                {(['source', 'destination'] as const).filter(field => signal[field] !== device).map(field =>
                  <label className="field" key={field}><span>{field === 'source' ? 'Source endpoint' : 'Destination endpoint'}</span>
                    <input list={deviceList} value={signal[field]} onChange={event => update(signal.id, { [field]: event.target.value })} />
                  </label>)}
                <label className="field"><span>Signal name</span><input value={signal.name} onChange={event => update(signal.id, { name: event.target.value })} /></label>
                <label className="field"><span>Signal method</span><select value={signal.method} onChange={event => {
                  const method = event.target.value
                  update(signal.id, { method, ...(method === 'hardwired' && signal.di === 0 && signal.do === 0
                    ? { di: Number(example.devices.includes(signal.destination)), do: Number(example.devices.includes(signal.source)) } : {}) })
                }}>
                  {['hardwired', 'GOOSE', 'SCADA message', 'internal', 'teleprotection', 'hardwired or communicated'].map(method =>
                    <option key={method} value={method}>{method === 'hardwired or communicated' ? 'Unresolved' : method}</option>)}
                </select></label>
                {signal.method === 'hardwired' && (['di', 'do'] as const).filter(field =>
                  example.devices.includes(field === 'di' ? signal.destination : signal.source)
                ).map(field => <label className="field" key={field}><span>{field === 'di' ? 'Destination DI points' : 'Source DO points'}</span>
                  <input type="number" min={0} max={99} value={signal[field]} onChange={event => {
                    const value = event.target.valueAsNumber
                    if (Number.isInteger(value) && value >= 0 && value <= 99) update(signal.id, { [field]: value })
                  }} /></label>)}
              </div>
              {signal.method === 'hardwired' && signal.do > 0 && <fieldset><legend>Additional required output properties</legend>{(['fast', 'form_c'] as const).map(property => {
                const selected = settings.output_classes?.[settings.variant]?.[String(signal.id)] ?? []
                return <label key={property}><input type="checkbox" checked={selected.includes(property)} onChange={event => {
                  const next = event.target.checked ? [...selected, property] : selected.filter(value => value !== property)
                  change({ ...settings, output_classes: { ...settings.output_classes, [settings.variant]: { ...settings.output_classes?.[settings.variant], [String(signal.id)]: next } } })
                }} /> {property === 'fast' ? 'Fast output required' : 'Form-C contact required'}</label>
              })}</fieldset>}
              {signal.method === 'hardwired' && signal.do > 0 && <label><input type="checkbox" checked={signal.coil}
                onChange={event => update(signal.id, { coil: event.target.checked })} /> Coil-duty output</label>}
              {signal.reference === 'User entry' && <button type="button" className="text-button" onClick={() => { const classes = {...settings.output_classes?.[settings.variant]}; delete classes[String(signal.id)]; change({ ...settings, edits: { ...settings.edits, [settings.variant]: signals.filter(item => item.id !== signal.id) }, output_classes: { ...settings.output_classes, [settings.variant]: classes } }) }}>Remove custom signal</button>}
            </details>
          </fieldset>
        })}
      </details>
      <details><summary>SEL and GE card capacity examples</summary>
        <p>Backend nominal screening only. Manufacturer contact properties, module coexistence and complete requirements remain unverified.</p>
        {!result && <p>Waiting for current backend results.</p>}
        {result?.card_examples.filter(card => card.device === device).map(card => <p key={card.model}><strong>{card.model} · {card.hardware}</strong> · {card.screening.replaceAll('_', ' ')} · {card.gate} {card.source_urls.map(url => <a href={url} key={url} target="_blank" rel="noreferrer">Reference ↗ </a>)}</p>)}
      </details>
      <details><summary>Full endpoint signal ledger</summary>
        <p>{result?.endpoint_count_basis}</p>
        <label><input type="checkbox" checked={allEndpoints} onChange={event => setAllEndpoints(event.target.checked)} /> Show all relay and field endpoints</label>
        {result?.ledger_findings?.map(item => <p role="status" key={item.code}>{item.message} ({item.count})</p>)}
        <p>Drawing tags identify required documents; actual approved drawing numbers have not been supplied. Field contacts and coil drives are separate from relay DI/DO.</p>
        {result?.ledger.filter(item => allEndpoints || item.source === device || item.destination === device || item.owner.label === relayName(device)).map(item => <article className="input-fit" key={item.ledger_id}>
          <strong>{item.name}</strong><p>{item.source_endpoint.label} → {item.destination_endpoint.label} · {item.method} · {item.included ? 'Included' : 'Excluded'}</p>
          <p>Owner: {item.owner.label} ({item.owner_state}) · {item.authority.replaceAll('_', ' ')}</p>
          <p>Source relay DO: {item.consumption.source_relay_do}; destination relay DI: {item.consumption.destination_relay_di}; external source contacts: {item.consumption.source_external_contacts ?? 'Unknown'}; destination coil drives: {item.consumption.destination_coil_drives ?? 'Unknown'}.</p>
          <p>{item.condition}</p><p>Research row {item.source_row_id} · {item.source_documents_required.map(doc => `${doc.tag}: ${doc.document} (${doc.state.replaceAll('_', ' ')})`).join('; ')}</p>
        </article>)}
      </details>
    </section>
  )
}
