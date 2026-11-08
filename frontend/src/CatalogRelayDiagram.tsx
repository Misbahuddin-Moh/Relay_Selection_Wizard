import { RelayInputDiagram, Sel487eInputDiagram, UrModulePreview } from './RelayInputDiagram'
import type { Drawing, InputGroup } from './RelayInputDiagram'

type Hotspot = [number, number, number, number]
type FigureGroup = [label: string, kind: InputGroup['kind'], description: string, hotspot: Hotspot]
type Figure = {
  drawing: Drawing
  groups: InputGroup[]
  reference: string
  referenceLabel: string
}

function figure(file: string, width: number, height: number, reference: string, referenceLabel: string, entries: FigureGroup[]): Figure {
  return {
    drawing: { file: `${file}.webp`, width, height, hotspots: Object.fromEntries(entries.map(([label, , , hotspot]) => [label, hotspot])) },
    groups: entries.map(([label, kind, description]) => ({ label, kind, description, channels: [] })),
    reference,
    referenceLabel,
  }
}

const sel = (id: number, page: number) => `https://selinc.com/api/download/${id}/#page=${page}`
const ge = 'https://www.gevernova.com'
const phase = 'Phase CT inputs'
const voltage = 'Voltage inputs'
const ctDescription = 'Review the phase current connections shown for this example.'
const vtDescription = 'Review the voltage connections shown for this example.'

// Rectangle coordinates use PDF points relative to each cropped manufacturer figure.
const figures: Record<string, Figure> = {
  'SEL-787 family': figure('sel-787', 196, 260, sel(2818, 13), 'SEL-787 data sheet · Fig. 14A', [
    ['Current / voltage card', 'other', 'Slot Z on the illustrated two-winding SEL-787. Verify the variant and CT/VT card before assigning channels.', [12, 204, 174, 48]],
  ]),
  'SEL-751': figure('sel-751', 470, 216, sel(10734, 31), 'SEL-751 data sheet · Fig. 37A/B', [
    [phase, 'phase', 'Slot Z current-input designations on the side label for this hardware example.', [30, 162, 55, 35]],
    ['LEA voltage inputs', 'voltage', 'Slot Z low-energy analog voltage input designations. Confirm the ordered sensing option.', [85, 162, 54, 35]],
  ]),
  'SEL-487B-1': figure('sel-487b', 478, 337, sel(2842, 19), 'SEL-487B data sheet · Fig. 28', [
    ['Upper CT banks', 'phase', ctDescription, [19, 215, 254, 48]],
    ['Lower CT banks', 'phase', ctDescription, [19, 277, 342, 47]],
    [voltage, 'voltage', vtDescription, [273, 215, 87, 48]],
  ]),
  'SEL-411L': figure('sel-411l', 428, 172, sel(10519, 24), 'SEL-411L data sheet · Fig. 34', [
    [phase, 'phase', ctDescription, [15, 118, 146, 47]],
    [voltage, 'voltage', vtDescription, [162, 118, 152, 47]],
    ['87L communications', 'other', 'Review the differential channel interfaces and remote relay compatibility.', [33, 11, 84, 47]],
  ]),
  'SEL-451': figure('sel-451', 454, 140, sel(7413, 17), 'SEL-451 data sheet · Fig. 24', [
    [phase, 'phase', ctDescription, [15, 84, 159, 47]],
    [voltage, 'voltage', vtDescription, [174, 84, 161, 47]],
  ]),
  'SEL-787Z + SEL-HZM': figure('sel-787z-hzm', 489, 458, sel(137960, 19), 'SEL-787Z data sheet · Fig. 28', [
    ['SEL-HZM', 'other', 'High-impedance module and bypass connections in the illustrated circuit.', [35, 3, 220, 403]],
    ['SEL-787Z', 'other', 'Relay input and output connections for this high-impedance example.', [270, 3, 213, 403]],
  ]),
  'SEL-735': figure('sel-735', 370, 147, sel(10343, 22), 'SEL-735 data sheet · Fig. 26', [
    ['Front panel', 'other', 'Horizontal meter face and controls.', [4, 4, 158, 116]],
    ['Rear connections', 'other', 'Side view shows the rear terminal edge. Use the ordered meter’s wiring documentation for CT and VT assignments.', [216, 18, 49, 102]],
  ]),
  'Multilin 845': figure('ge-845', 413, 199,
    `${ge}/electrification/sites/default/files/2025-09/Multilin-845-Comprehensive-Management-Brochure-EN-12875E-Hybrid-202503-R002.pdf#page=9`,
    'GE Multilin 845 brochure · rear view', [
      ['CT / VT inputs', 'other', 'The brochure labels this rear-panel section for CT and VT inputs. Confirm the ordered analog card.', [180, 87, 80, 85]],
      ['Digital I/O', 'other', 'The brochure identifies this area for digital I/O and optional interfaces.', [117, 50, 57, 121]],
    ]),
  'Multilin 850': figure('ge-850', 302, 155,
    `${ge}/electrification/sites/default/files/2025-06/Multilin%20850-brochure-EN-32050A-Hybrid-202503-R002.pdf#page=2`,
    'GE Multilin 850 brochure · 850D functional block diagram', [
      [phase, 'phase', 'The left feeder’s three CTs feed protection functions including 51P. Use the ordered model’s wiring drawing for terminal assignments.', [9, 50, 62, 16]],
      [voltage, 'voltage', 'The left feeder’s three VTs are shown here in the dual-feeder functional example.', [13, 124, 17, 15]],
    ]),
  'Multilin MIB': figure('ge-mib', 431, 236,
    'https://www.gedigitalenergy.com/products/brochures/mib.pdf#page=3',
    'GE Multilin MIB brochure · typical wiring diagram', [
      ['Differential phase circuits', 'phase', 'The illustrated A, B and C differential circuits connect through the stabilizing components.', [3, 8, 112, 104]],
      ['MIB current inputs', 'phase', 'Review the C1–C6 current terminals shown for this wiring example.', [134, 13, 68, 68]],
      ['Trip contact', 'other', 'The example identifies the relay trip contact at A5–A6.', [287, 155, 38, 36]],
    ]),
  'Multilin EPM 7000P': figure('ge-epm7000p', 401, 463,
    `${ge}/grid-solutions/sites/default/files/resources/products/manuals/epm/EPM7000P-A1-GEV.pdf#page=60`,
    'GE EPM 7000P manual · Fig. 4-9', [
      [phase, 'phase', 'Three CTs feed the meter through the illustrated shorting block.', [25, 42, 98, 118]],
      [voltage, 'voltage', 'Three VTs feed the meter through the illustrated fused circuits.', [145, 352, 126, 63]],
    ]),
  'Multilin EPM 9900P': figure('ge-epm9900p', 368, 431,
    `${ge}/electrification/sites/default/files/resources/products/manuals/epm/EPM9900P-A3-GEV.pdf#page=65`,
    'GE EPM 9900P manual · Fig. 4-6', [
      [phase, 'phase', 'The wiring example shows three phase CTs and an optional fourth CT for current measurement.', [31, 29, 111, 122]],
      [voltage, 'voltage', 'Three VTs feed the meter through the illustrated fused circuits.', [155, 270, 175, 62]],
    ]),
}

const highImpedanceGroups: InputGroup[] = [
  { label: 'Bus CT secondary circuit', kind: 'phase', description: 'Review how the bus CT secondary circuits connect to the high-impedance protection scheme.', channels: [] },
  { label: 'High-impedance sensing', kind: 'other', description: 'Confirm the model-specific sensing circuit, component ratings and terminal assignments in the manufacturer documentation.', channels: [] },
]

const urModels = ['T60', 'B30', 'B90', 'F60', 'L90'] as const

export function CatalogRelayDiagram({ model, source, highImpedance = false, selLayout }: {
  model: string
  source: string
  highImpedance?: boolean
  selLayout?: { neutral_inputs: number; vt_banks: number }
}) {
  const ur = urModels.find(family => model === `Multilin ${family}` || model.startsWith(`Multilin ${family} `))
  const illustration = figures[model]
  const is487e = model.startsWith('SEL-487E')
  const groups = highImpedance ? highImpedanceGroups : undefined

  return (
    <details className="catalog-relay-diagram">
      <summary>Inspect relay inputs</summary>
      {ur ? <UrModulePreview model={ur} /> : illustration ? (
        <RelayInputDiagram {...illustration} caption={`${model} · Manufacturer example. Confirm the ordered hardware before assigning terminals.`} />
      ) : is487e ? (
        <Sel487eInputDiagram neutralInputs={selLayout?.neutral_inputs ?? 3} vtBanks={selLayout?.vt_banks ?? 2} />
      ) : groups ? (
        <RelayInputDiagram groups={groups} caption={`${model} · Application overview. Vendor terminal drawing pending.`}
          reference={source} referenceLabel="Manufacturer documentation" />
      ) : (
        <p>Vendor terminal drawing pending. <a href={source} target="_blank" rel="noreferrer">Manufacturer documentation ↗</a></p>
      )}
    </details>
  )
}
