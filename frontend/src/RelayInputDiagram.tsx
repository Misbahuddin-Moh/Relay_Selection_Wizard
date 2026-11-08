import { useState } from 'react'

export type InputGroup = {
  label: string
  kind: 'phase' | 'neutral' | 'voltage' | 'other'
  description: string
  channels: string[]
}

export type Drawing = {
  file: string
  width: number
  height: number
  hotspots: Record<string, [number, number, number, number]>
}

export function RelayInputDiagram({ groups, caption, reference, referenceLabel, drawing }: {
  groups: InputGroup[]
  caption: string
  reference: string
  referenceLabel: string
  drawing?: Drawing
}) {
  const [active, setActive] = useState<string | null>(null)
  const [showHighlights, setShowHighlights] = useState(true)
  const [zoom, setZoom] = useState(100)
  const selected = groups.find(group => group.label === active) ?? groups[0]
  return (
    <section className="input-diagram" aria-label="Relay input diagram">
      <header><strong>{drawing ? 'Vendor illustration' : 'Functional input map'}</strong><span>{caption}</span></header>
      <div className="input-diagram-source">
        {drawing && <><button type="button" className="text-button" aria-pressed={showHighlights} onClick={() => setShowHighlights(!showHighlights)}>
          {showHighlights ? 'Show original' : 'Show input highlights'}
        </button>
        <label className="drawing-zoom">Zoom
          <select value={zoom} onChange={event => setZoom(Number(event.target.value))}>
            <option value={100}>Fit</option>
            <option value={150}>150%</option>
            <option value={200}>200%</option>
            <option value={300}>300%</option>
          </select>
        </label></>}
        <a href={reference} target="_blank" rel="noreferrer">{referenceLabel} ↗</a>
      </div>
      {drawing && <div className="vendor-drawing" tabIndex={0} role="region" aria-label="Scrollable vendor drawing">
        <div className="vendor-drawing-sheet" style={{ width: `${zoom}%`, maxWidth: drawing.width * zoom / 100 }}>
          <img src={`/relay-drawings/${drawing.file}`} alt={referenceLabel}
            width={drawing.width} height={drawing.height} loading="lazy" />
          {showHighlights && groups.map(group => {
            const [x, y, width, height] = drawing.hotspots[group.label]
            return (
              <button key={group.label} type="button" className={`drawing-hotspot ${group.kind}`}
                style={{ left: `${x / drawing.width * 100}%`, top: `${y / drawing.height * 100}%`,
                  width: `${width / drawing.width * 100}%`, height: `${height / drawing.height * 100}%` }}
                aria-label={`Highlight ${group.label}`} aria-pressed={selected.label === group.label}
                onClick={() => setActive(group.label)} />
            )
          })}
        </div>
      </div>}
      <div className="input-diagram-groups" aria-label="Input groups">
        {groups.map(group => (
          <button className={`input-group ${group.kind}`} type="button" key={group.label}
            aria-pressed={selected.label === group.label} onClick={() => setActive(group.label)}>
            <strong>{group.label}</strong>
            {group.channels.length > 0 && <span className="input-channel-labels">{group.channels.map(channel => <span key={channel}>{channel}</span>)}</span>}
          </button>
        ))}
      </div>
      <p className="input-group-readout"><strong>{selected.label}</strong> · {selected.description}</p>
    </section>
  )
}

// Hotspots use PDF points relative to the original figure crops.
// Fig. 33 starts at (82, 56), Fig. 34 at (70, 56).
function selDrawing(secondVt: boolean): Drawing {
  const x = secondVt ? 21 : 20
  const upper = secondVt ? 301 : 211
  const lower = secondVt ? 360 : 272
  return {
    file: secondVt ? 'sel-487e-fig34.svg' : 'sel-487e-fig33.svg',
    width: secondVt ? 460 : 461,
    height: secondVt ? 415 : 323,
    hotspots: {
      S: [x, upper, 78, 39],
      T: [x + 81, upper, 78, 39],
      U: [x + 162, upper, 78, 39],
      V: [x + 243, upper, 78, 39],
      W: [x, lower, 78, 39],
      X: [x + 81, lower, 78, 39],
      Y: [x + 162, lower, 78, 39],
      Z: [x + 243, lower, 78, 39],
    },
  }
}

// Fig. 20 crops start at (324, 55) for 8CT and (197, 120) for 4CT / 4VT.
const geDrawings: Record<'ct' | 'mixed', Drawing> = {
  ct: { file: 'ge-t60-8ct.svg', width: 103, height: 395, hotspots: {
    'Bank 1': [23, 3, 77, 195],
    'Bank 2': [23, 198, 77, 195],
  } },
  mixed: { file: 'ge-t60-4ct-4vt.svg', width: 103, height: 330, hotspots: {
    'Bank 1': [23, 3, 77, 194],
    'Bank 2': [23, 197, 77, 130],
  } },
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
  groups.sort((a, b) => a.label.localeCompare(b.label))
  return <RelayInputDiagram groups={groups} caption="SEL-487E rear-panel example. Highlights show the modeled use of each block. Printed terminal labels follow the vendor example."
    drawing={selDrawing(vtBanks === 2)}
    reference={`https://selinc.com/api/download/99384/#page=${vtBanks === 2 ? 24 : 23}`}
    referenceLabel={`SEL datasheet · rear panel Fig. ${vtBanks === 2 ? 34 : 33}`} />
}

const urManuals = {
  T60: ['t60', 'T60-1601-0090-86x-3', 101, 20],
  B30: ['b30', 'B30-1601-0109-86x-3', 95, 24],
  B90: ['b90', 'B90-1601-0115-86x-3', 84, 23],
  F60: ['f60', 'F60-1601-0093-86x-3', 95, 20],
  L90: ['l90', 'L90-1601-0081-86x-3', 111, 22],
} as const

const b90Drawings: typeof geDrawings = {
  ct: { file: 'ge-b90-8ct.webp', width: 398, height: 104, hotspots: {
    'Bank 1': [4, 4, 195, 90],
    'Bank 2': [199, 4, 195, 90],
  } },
  mixed: { file: 'ge-b90-4ct-4vt.webp', width: 334, height: 104, hotspots: {
    'Bank 1': [4, 4, 195, 87],
    'Bank 2': [199, 4, 131, 87],
  } },
}

export function UrModulePreview({ model }: { model: keyof typeof urManuals }) {
  const [directory, manual, page, figure] = urManuals[model]
  const [module, setModule] = useState<'ct' | 'mixed'>('ct')
  const groups: InputGroup[] = [
    { label: 'Bank 1', kind: 'phase', description: 'Three phase currents plus a ground current channel.', channels: ['IA', 'IB', 'IC', 'IG'] },
    module === 'ct'
      ? { label: 'Bank 2', kind: 'phase', description: 'Second three-phase CT bank plus a ground current channel.', channels: ['IA', 'IB', 'IC', 'IG'] }
      : { label: 'Bank 2', kind: 'voltage', description: 'Three phase voltages plus an auxiliary voltage channel.', channels: ['VA', 'VB', 'VC', 'VX'] },
  ]
  return (
    <section className="input-fit" aria-label={`${model} module preview`}>
      <h4>Compare CT/VT modules</h4>
      <label className="field"><span>Module example</span>
        <select value={module} onChange={event => setModule(event.target.value === 'mixed' ? 'mixed' : 'ct')}>
          <option value="ct">8CT · 8N / 8R</option>
          <option value="mixed">4CT / 4VT · 8L / 8M</option>
        </select>
      </label>
      <p>One module shown. Confirm the ordered chassis slots and current-input type before mapping the station CTs.</p>
      <RelayInputDiagram groups={groups} caption={`GE ${model} · wiring for one CT/VT module. The tilde stands for the chassis slot.`}
        drawing={(model === 'B90' ? b90Drawings : geDrawings)[module]}
        reference={`https://www.gevernova.com/electrification/sites/default/files/resources/products/manuals/${directory}/${manual}.pdf#page=${page}`}
        referenceLabel={`GE ${model} 8.6x manual · CT/VT wiring Fig. ${figure}`} />
    </section>
  )
}
