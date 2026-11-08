const releaseNotes = 'https://www.gevernova.com/grid-solutions/sites/default/files/resources/products/software/ur/GER-4976D.pdf'

export function T60InputFit({ minimum, maximum, vt, neutral, auxiliaryUnknown }: {
  minimum: number
  maximum: number
  vt: string
  neutral: string
  auxiliaryUnknown: boolean
}) {
  const knownVt = vt === '' ? null : Number(vt)
  const cases = Array.from(new Set([minimum, maximum + Number(auxiliaryUnknown)]))

  return (
    <section className="input-fit" aria-label="T60 analog capacity screen">
      <h4>Analog module capacity</h4>
      {cases.map(banks => {
        const mixed = knownVt ?? 0
        const currentOnly = Math.ceil(Math.max(0, banks - mixed) / 2)
        const populated = mixed + 2 * currentOnly
        return <p key={banks}><strong>{banks} phase CT banks</strong> · {
          mixed + currentOnly > 3
            ? 'Exceeds the modeled three-module combinations.'
            : `${[currentOnly && `${currentOnly} × 8CT`, mixed && `${mixed} × 4CT/4VT`].filter(Boolean).join(' + ')} capacity example${knownVt === null ? ' before VT requirements are known' : ''}.${populated >= 5 ? ' Check software and firmware for five or six populated CT banks.' : ''}`
        }</p>
      })}
      <p>{neutral === '' ? 'Neutral CT assignment is open.' : `${neutral} neutral CT inputs requested. Verify compatible ground channels and function routing.`} Verify exact slots, ratings, and simultaneous functions. <a href={releaseNotes} target="_blank" rel="noreferrer">GE firmware evidence ↗</a></p>
    </section>
  )
}
