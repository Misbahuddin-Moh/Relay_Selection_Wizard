export type BudgetSignal = { included: boolean; method: string; source: string; destination: string; di: number; do: number; coil: boolean }
export type BudgetSpare = { di: number; do: number; basis: 'used' | 'installed' }

export function digitalBudget(signals: BudgetSignal[], device: string, spare: BudgetSpare) {
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
  return { completeness: 'partial' as const, di, coil, other, open, diRequired: withSpare(di, spare.di), coilRequired,
    doRequired: coilRequired + withSpare(other, spare.do) }
}

