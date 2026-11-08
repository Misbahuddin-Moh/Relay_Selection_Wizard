import { useState } from 'react'

type InputGroup = {
  label: string
  kind: 'phase' | 'neutral' | 'voltage'
  description: string
  channels: string[]
}

export function RelayInputDiagram({ groups, caption, reference, referenceLabel }: {
  groups: InputGroup[]
  caption: string
  reference: string
  referenceLabel: string
}) {
  const [active, setActive] = useState<string | null>(null)
  const [showDrawing, setShowDrawing] = useState(false)
  const selected = groups.find(group => group.label === active) ?? groups[0]
  return (
    <section className="input-diagram" aria-label="Relay input diagram">
      <header><strong>Input map</strong><span>{caption}</span></header>
      <div className="input-diagram-groups" aria-label="Input groups">
        {groups.map(group => (
          <button className={`input-group ${group.kind}`} type="button" key={group.label}
            aria-pressed={selected.label === group.label} onClick={() => setActive(group.label)}>
            <strong>{group.label}</strong>
            <span className="input-channel-labels">{group.channels.map(channel => <span key={channel}>{channel}</span>)}</span>
          </button>
        ))}
      </div>
      <p className="input-group-readout"><strong>{selected.label}</strong> · {selected.description}</p>
      <div className="input-diagram-source">
        <button type="button" className="text-button" aria-expanded={showDrawing} onClick={() => setShowDrawing(!showDrawing)}>
          {showDrawing ? 'Hide vendor drawing' : 'Show vendor drawing'}
        </button>
        <a href={reference} target="_blank" rel="noreferrer">{referenceLabel} ↗</a>
      </div>
      {showDrawing && <iframe className="vendor-drawing" src={reference} title={referenceLabel} loading="lazy" />}
    </section>
  )
}

const phaseChannels = ['A', 'B', 'C']

export function Sel487eInputDiagram({ neutralInputs, vtBanks }: { neutralInputs: number; vtBanks: number }) {
  const groups: InputGroup[] = ['S', 'T', 'U', 'W', 'X'].map(label => ({
    label, kind: 'phase', description: 'Three-phase CT bank.', channels: phaseChannels,
  }))
  groups.push(
    neutralInputs
      ? { label: 'Y', kind: 'neutral', description: 'Three individual neutral CT inputs.', channels: ['N1', 'N2', 'N3'] }
      : { label: 'Y', kind: 'phase', description: 'One three-phase CT bank with matching input ratings.', channels: phaseChannels },
    { label: 'V', kind: 'voltage', description: 'Three-phase VT bank.', channels: phaseChannels },
    vtBanks === 2
      ? { label: 'Z', kind: 'voltage', description: 'Ordered as a second three-phase VT bank.', channels: phaseChannels }
      : { label: 'Z', kind: 'phase', description: 'Ordered as an additional three-phase CT bank.', channels: phaseChannels },
  )
  return <RelayInputDiagram groups={groups} caption="SEL-487E dual AC cards · functional view"
    reference={`https://selinc.com/api/download/99384/#page=${vtBanks === 2 ? 24 : 23}`}
    referenceLabel={`SEL datasheet · rear panel Fig. ${vtBanks === 2 ? 34 : 33}`} />
}

export function T60ModulePreview() {
  const [module, setModule] = useState<'ct' | 'mixed'>('ct')
  const groups: InputGroup[] = [
    { label: 'Bank 1', kind: 'phase', description: 'Three phase currents plus a ground current channel.', channels: ['IA', 'IB', 'IC', 'IG'] },
    module === 'ct'
      ? { label: 'Bank 2', kind: 'phase', description: 'Second three-phase CT bank plus a ground current channel.', channels: ['IA', 'IB', 'IC', 'IG'] }
      : { label: 'Bank 2', kind: 'voltage', description: 'Three phase voltages plus an auxiliary voltage channel.', channels: ['VA', 'VB', 'VC', 'VX'] },
  ]
  return (
    <section className="input-fit" aria-label="T60 module preview">
      <h4>Compare CT/VT modules</h4>
      <label className="field"><span>Module example</span>
        <select value={module} onChange={event => setModule(event.target.value === 'mixed' ? 'mixed' : 'ct')}>
          <option value="ct">8CT · 8N / 8R</option>
          <option value="mixed">4CT / 4VT · 8L / 8M</option>
        </select>
      </label>
      <p>One module shown. Confirm the ordered chassis slots and current-input type before mapping the station CTs.</p>
      <RelayInputDiagram groups={groups} caption="GE T60 · functional view of one CT/VT module"
        reference="https://www.gevernova.com/electrification/sites/default/files/resources/products/manuals/t60/T60-1601-0090-86x-3.pdf#page=101"
        referenceLabel="GE T60 8.6x manual · CT/VT wiring Fig. 20" />
    </section>
  )
}
