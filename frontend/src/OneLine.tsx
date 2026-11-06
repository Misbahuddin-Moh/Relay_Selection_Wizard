import { withInventoryBoundaries } from './model'
import type { Ct, Study } from './model'

function CtSymbol({ x, y, state, label }: { x: number; y: number; state: Ct; label: string }) {
  return (
    <g className={`ct-symbol ${state}`} transform={`translate(${x}, ${y})`}>
      <title>{label} · {state}</title>
      <circle r="7" />
      {state === 'absent' && <path d="M -3.5 -3.5 L 3.5 3.5 M -3.5 3.5 L 3.5 -3.5" />}
      {state === 'unknown' && <text y="3.5" textAnchor="middle">?</text>}
      {state === 'present' && <circle r="2.3" className="center" />}
    </g>
  )
}

function branchLabel(name: string) {
  return name.length > 11 ? `${name.slice(0, 10)}…` : name
}

export function OneLine({ study: input }: { study: Study }) {
  const study = withInventoryBoundaries(input)
  const spans = study.bays.map(bay => Math.max(130, bay.branches.length * 80))
  const span = spans.reduce((total, width) => total + width, 0)
  const width = Math.max(640, span + 70)
  const center = width / 2
  const start = (width - span) / 2

  return (
    <div className="drawing-scroll" tabIndex={0} aria-label="Scrollable single-line diagram">
      <svg
        className="drawing"
        viewBox={`0 0 ${width} 402`}
        style={{ minWidth: Math.max(540, width - 65) }}
        role="img"
        aria-label={`Utility, ${study.hv_kv} kV high-side breaker, transformer, and ${study.mv_kv} kV collector bus with ${study.bays.length} breaker positions`}
      >
        <g className="primary-wire">
          <path d={`M ${center} 39 V 246 M ${start} 246 H ${width - start}`} />
          <path d={`M ${center - 5} 46 L ${center} 39 L ${center + 5} 46`} />
          <rect x={center - 9} y="72" width="18" height="18" rx="2" className="device" />
          <rect x={center - 14} y="138" width="28" height="41" className="diagram-mask" />
          <circle cx={center} cy="151" r="11" className="device" />
          <circle cx={center} cy="167" r="11" className="transformer-winding" />
        </g>
        <CtSymbol x={center} y={56} state={study.hv_ct} label="HV breaker POI-side CT" />
        <CtSymbol x={center} y={207} state={study.lv_ct} label="Transformer LV CT" />
        <g className="svg-label">
          <text x={center} y="27" textAnchor="middle" className="source-label">UTILITY SOURCE</text>
          <text x={center + 22} y="86">HV breaker</text>
          <text x={center - 18} y="60" textAnchor="end">POI-side CT</text>
          <text x={center + 22} y="156">MPT</text>
          <text x={center + 22} y="172" className="muted-svg">{study.hv_kv} / {study.mv_kv} kV</text>
          <text x={center - 18} y="211" textAnchor="end">LV CT</text>
          <text x={start} y="234" className="bus-label">{study.mv_kv} kV COLLECTOR BUS</text>
        </g>
        <path className="aux-wire" d={`M ${width - start - 10} 246 V 213`} />
        <text x={width - start - 10} y="202" textAnchor="middle" className="svg-label muted-svg">Auxiliary branch</text>
        {study.bays.map((bay, index) => {
          const x = start + spans.slice(0, index).reduce((sum, value) => sum + value, 0) + spans[index] / 2
          const ends = bay.branches.map((_, branchIndex) => x + (branchIndex - (bay.branches.length - 1) / 2) * 74)
          return (
            <g key={bay.id}>
              <g className="primary-wire">
                <path d={`M ${x} 246 V 327`} />
                <rect x={x - 8} y="272" width="16" height="16" rx="2" className="device" />
                <path d={`M ${ends[0]} 327 H ${ends[ends.length - 1]}`} />
                {ends.map((end, branchIndex) => (
                  <path key={branchIndex} d={`M ${end} 327 V 357 M ${end - 4} 352 L ${end} 357 L ${end + 4} 352`} />
                ))}
              </g>
              <CtSymbol x={x} y={309} state={bay.ct} label={`${bay.id} boundary CT`} />
              <text x={x + 14} y="284" className="svg-label breaker-label">{bay.id}</text>
              {ends.map((end, branchIndex) => (
                <text key={branchIndex} x={end} y="379" textAnchor="middle" className="svg-label branch-label"><title>{bay.branches[branchIndex]}</title>{branchLabel(bay.branches[branchIndex])}</text>
              ))}
            </g>
          )
        })}
      </svg>
    </div>
  )
}
