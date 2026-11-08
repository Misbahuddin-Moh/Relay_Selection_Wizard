import { useId, useState } from 'react'
import matrix from './digital-io-matrix.json'

type Signal = {
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
export type DigitalSettings = { variant: Variant; spare: Spare; edits: Partial<Record<Variant, Signal[]>> }
export const defaultDigitalSettings: DigitalSettings = { variant: 'LOCK', spare: { di: 20, do: 20, basis: 'used' }, edits: {} }

export function digitalCase(scheme: string, line: boolean, variant: Variant) {
  const prefix = scheme === 'dedicated' ? 'SEP' : scheme === 'shared' ? 'SHARED' : scheme === 'combined' ? 'COMB_ASYM' : ''
  const key = `${prefix}.${variant}.L${Number(line)}`
  const entry = matrix.cases[key as keyof typeof matrix.cases]
  if (!entry) return undefined
  const signals: Signal[] = entry.signals.map((index, id) => {
    const [name, source, destination, method, di, output, coil, included, reference, condition] = matrix.signals[index]
    return { id, name: String(name), source: String(source), destination: String(destination), method: String(method),
      di: Number(di), do: Number(output), coil: Boolean(coil), included: Boolean(included),
      reference: String(reference), condition: String(condition) }
  })
  return { ...entry, signals }
}

export function digitalBudget(signals: Signal[], device: string, spare: Spare) {
  let di = 0, coil = 0, other = 0, open = 0
  for (const signal of signals) {
    if (!signal.included) continue
    if (signal.method === 'hardwired or communicated' && (signal.source === device || signal.destination === device)) open++
    if (signal.method !== 'hardwired') continue
    if (signal.destination === device) di += signal.di
    if (signal.source === device) {
      if (signal.coil) coil += signal.do
      else other += signal.do
    }
  }
  const withSpare = (used: number, percent: number) => spare.basis === 'used'
    ? used + Math.ceil(used * percent / 100)
    : Math.ceil(used * 100 / (100 - percent))
  const coilRequired = withSpare(coil, spare.do)
  return { di, coil, other, open, diRequired: withSpare(di, spare.di), coilRequired,
    doRequired: coilRequired + withSpare(other, spare.do) }
}

export function budgetText(budget: ReturnType<typeof digitalBudget>) {
  return `${budget.di} DI / ${budget.coil + budget.other} DO used · ${budget.diRequired} DI / ${budget.doRequired} DO with spares (${budget.coilRequired} coil-duty DO)${budget.open ? ` · ${budget.open} unresolved interface(s)` : ''}`
}

export function DigitalIO({ scheme, bays, line, settings, change }: {
  scheme: string; bays: string[]; line: boolean; settings: DigitalSettings; change: (next: DigitalSettings) => void
}) {
  const [picked, setPicked] = useState('T-P')
  const deviceList = useId()
  const example = digitalCase(scheme, line, settings.variant)
  if (!example) return null
  const device = example.devices.includes(picked) ? picked : 'T-P'
  const signals = settings.edits[settings.variant] ?? example.signals
  const related = signals.filter(signal => signal.source === device || signal.destination === device)
  const budget = digitalBudget(signals, device, settings.spare)
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
      <p>Each relay has its own digital inputs (DI) and outputs (DO). Select a relay to review its signals. The overview shows required physical points with spares.</p>
      <p>Illustrative three-breaker reference wiring. Review the project trip matrix and control drawings before applying these counts. The 20% default is a worked-example assumption.</p>
      <fieldset>
        <legend>How are trips and breaker failure wired?</legend>
        <p>An 86 lockout relay trips assigned breakers and keeps them locked out until reset. Breaker-failure timing starts when a trip is issued so backup clearing can operate if the breaker fails to open.</p>
        <div className="digital-relays wiring-examples">
          {(Object.keys(variants) as Variant[]).map(variant => <label key={variant}>
            <input type="radio" name={`${deviceList}-wiring`} checked={settings.variant === variant}
              onChange={() => change({ ...settings, variant })} />
            <span><strong>{variants[variant].title}</strong><br />{variants[variant].detail}</span>
          </label>)}
        </div>
      </fieldset>
      <fieldset>
        <legend>Relay to review</legend>
        <div className="digital-relays">
          {example.devices.map(id => {
            const counts = digitalBudget(signals, id, settings.spare)
            return <label key={id}>
              <input type="radio" name={`${deviceList}-relay`} checked={device === id} onChange={() => setPicked(id)} />
              <span><strong>{relayName(id)}</strong><br />{counts.diRequired} DI / {counts.doRequired} DO</span>
            </label>
          })}
        </div>
      </fieldset>
      <h4>{relayName(device)} signal budget</h4>
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
      <p aria-live="polite"><strong>{budgetText(budget)}</strong></p>
      <p>Only included hardwired signals count toward relay contacts. Breaker coils, lockouts, and other external endpoints have separate budgets. Output reserves round up separately for coil-duty and other contacts.</p>
      <details><summary>Review and edit {relayName(device)} signals</summary>
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
              {signal.method === 'hardwired' && signal.do > 0 && <label><input type="checkbox" checked={signal.coil}
                onChange={event => update(signal.id, { coil: event.target.checked })} /> Coil-duty output</label>}
              {signal.reference === 'User entry' && <button type="button" className="text-button" onClick={() => setSignals(signals.filter(item => item.id !== signal.id))}>Remove custom signal</button>}
            </details>
          </fieldset>
        })}
      </details>
      <details><summary>SEL and GE card capacity examples</summary>
        <p>Counts are screened against the card examples in this wiring case. Verify contact ratings, isolation, slots, analog fit, and protection support separately.</p>
        {example.cards.map(index => matrix.cards[index]).filter(card => card[0] === device).map(card => {
          const [, model, hardware, di, outputs, coil, status, gate, source] = card
          const within = Number(di) >= budget.diRequired && Number(outputs) >= budget.doRequired && Number(coil) >= budget.coilRequired
          return <p key={model}><strong>{model} · {hardware}</strong> · {status === 'function_unverified' ? 'Function unverified'
            : within ? 'Within nominal point counts' : 'Exceeds this card example'} · {gate} {source.split(';').map((url, i) => <a key={url} href={url.trim()} target="_blank" rel="noreferrer">Reference {i + 1} ↗ </a>)}</p>
        })}
      </details>
    </section>
  )
}
