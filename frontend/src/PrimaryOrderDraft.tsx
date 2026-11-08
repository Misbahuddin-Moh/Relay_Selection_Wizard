import { useState } from 'react'

const commonFields = {
  dc: 'Station DC supply and digital input voltage',
  ct: 'CT secondary rating by input (1 A or 5 A)',
  comms: 'Communications media and protocol options',
}

const selFields = {
  chassis: 'Chassis size and AC card count',
  analog: 'AC terminal configuration and VT input type',
  build: 'Terminal connector and coating options',
}

const geFields = {
  chassis: 'Chassis, mounting, coating and front panel',
  analog: 'CT/VT DSP modules, ground sensitivity and slot positions',
  digital: 'Digital module slot positions',
  cpu: 'CPU and software option codes',
  supply: 'Power supply option and redundancy',
}

export function PrimaryOrderDraft({ model, hardware, wiring, phase, neutral, vt, digital, blocked }: {
  model: 'SEL-487E-3' | 'GE T60'
  hardware: string
  wiring: string
  phase: number
  neutral: string
  vt: string
  digital: string
  blocked: string | null
}) {
  const [fields, setFields] = useState<Record<string, string>>({})
  const [code, setCode] = useState('')
  const sel = model === 'SEL-487E-3'
  const orderFields = Object.entries({ ...commonFields, ...(sel ? selFields : geFields) })
  const missing = [
    ...(neutral === '' ? ['Neutral CT count'] : []),
    ...(vt === '' ? ['VT bank count'] : []),
    ...orderFields.filter(([id]) => !fields[id]?.trim()).map(([, label]) => label),
  ]
  const ready = missing.length === 0 && !blocked
  const draft = [
    'Transformer Primary · preliminary manufacturer configuration request',
    `Relay model: ${model}`,
    `Protection: 87T · ${wiring}`,
    `Digital hardware example: ${hardware}`,
    `Digital I/O requirement: ${digital}`,
    `Analog inputs: ${phase} three-phase CT banks, ${neutral || 'open'} neutral CT inputs, ${vt || 'open'} three-phase VT banks`,
    ...orderFields.map(([id, label]) => `${label}: ${fields[id]?.trim() || 'open'}`),
    ...(blocked ? [blocked] : []),
    ...(ready && code.trim() ? [`Manufacturer-supplied order code: ${code.trim()}`] : []),
  ].join('\n')

  return <details>
    <summary>Prepare manufacturer ordering draft</summary>
    <p>Copy the draft with the known inputs. Open items can go to the manufacturer with the request.</p>
    {blocked && <p><strong>{blocked}</strong></p>}
    <label className="field"><span>Ordering draft to copy</span>
      <textarea readOnly rows={7} value={draft} />
    </label>
    <details><summary>Add known ordering details</summary>
      <div className="field-row">
        {orderFields.map(([id, label]) => <label className="field" key={id}>
          <span>{label}</span>
          <input value={fields[id] ?? ''} onChange={event => {
            setFields(current => ({ ...current, [id]: event.target.value }))
            setCode('')
          }} />
        </label>)}
      </div>
      <p><strong>Open fields</strong> · {missing.length ? missing.join(' · ') : 'All ordering fields entered'}</p>
      <p><a href={sel ? 'https://selinc.com/products/487e/' : 'https://www.gevernova.com/grid-solutions/sites/default/files/2025-09/Multilin-T60-brochure-EN-12650P-Hybrid-202503-R002.pdf'}
        target="_blank" rel="noreferrer">{sel ? 'SEL Configure and order' : 'GE T60 ordering guide'} ↗</a></p>
      <label className="field"><span>Manufacturer-supplied order code</span>
        <input value={code} disabled={!ready} onChange={event => setCode(event.target.value)} />
      </label>
    </details>
  </details>
}
