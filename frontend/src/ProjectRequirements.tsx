import { useEffect, useState } from 'react'

export type Finding = {
  page: number
  quote: string
  scope: string
  requirement: string
  category: string
  status: 'required' | 'tentative' | 'unclear'
  timing: 'purchase' | 'commissioning' | 'future' | 'unspecified'
  minimum: number | null
}

const example = `Synthetic project excerpt for demonstration only.
Transformer Primary shall have at least two three-phase VT banks.
The POI line relay shall support IEC 61850 for future use. Activation is deferred.
Transformer Primary trip outputs shall operate the 86T lockout relay.
The breaker drawing labels its trip coils TC1 and TC2.`

type ReviewedFinding = Finding & { source: string; id: number }
type Extraction = { findings: Finding[]; pages_processed: number; unreadable_pages: number[]; unverified_findings: number }
export type AppliedRequirement = ReviewedFinding & { device: number }

export function modeledMinimum(finding: Finding) {
  return finding.status === 'required' && finding.timing !== 'future'
    && (finding.category === 'neutral_ct' || finding.category === 'vt_banks')
    && finding.minimum != null && Number.isSafeInteger(finding.minimum) && finding.minimum > 0 && finding.minimum <= 99
}

export function ProjectRequirements({ roles, applied, onChange }: {
  roles: string[]
  applied: AppliedRequirement[]
  onChange: (findings: AppliedRequirement[]) => void
}) {
  const [configured, setConfigured] = useState<boolean | null>(null)
  const [file, setFile] = useState<File | null>(null)
  const [excerpt, setExcerpt] = useState('')
  const [findings, setFindings] = useState<ReviewedFinding[]>([])
  const [targets, setTargets] = useState<Record<number, string>>({})
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')

  useEffect(() => {
    const controller = new AbortController()
    fetch('/api/requirements/status', { signal: controller.signal })
      .then(response => response.json()).then(status => setConfigured(status.configured === true))
      .catch(() => { if (!controller.signal.aborted) setConfigured(false) })
    return () => controller.abort()
  }, [])

  async function extract() {
    const body = file ?? excerpt.trim()
    if (!body) return
    setBusy(true)
    setError('')
    setNotice('')
    try {
      const response = await fetch('/api/requirements/extract', {
        method: 'POST',
        headers: { 'Content-Type': file?.name.toLowerCase().endsWith('.pdf') ? 'application/pdf' : 'text/plain' },
        body,
      })
      const data = await response.json()
      if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : 'Requirements extraction failed.')
      const result: Extraction = data
      setFindings(current => [...current, ...result.findings.map((finding, index) => ({
        ...finding, source: file?.name ?? 'Pasted excerpt', id: current.length + index,
      }))])
      setNotice([
        `${result.findings.length} cited findings from ${result.pages_processed} processed pages or text excerpts.`,
        result.unreadable_pages.length ? `Text unavailable on page(s) ${result.unreadable_pages.join(', ')}. Paste the relevant text to review it.` : '',
        result.unverified_findings ? `${result.unverified_findings} findings omitted because their excerpts could not be matched to the source.` : '',
      ].filter(Boolean).join(' '))
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Requirements extraction failed.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <details className="detail-block project-requirements">
      <summary>Project documents and requirements · optional</summary>
      <p>Upload a text-readable PDF excerpt (up to 30 pages) or paste a clause. Extraction sends the readable source text to Claude for review. Use synthetic or approved excerpts.</p>
      {configured === false && <p className="draft-note">Claude is unconfigured. You can continue with the station and scheme requirements.</p>}
      <label className="field"><span>Project excerpt file</span><input type="file" accept=".pdf,.txt,application/pdf,text/plain" disabled={busy} onChange={event => setFile(event.target.files?.[0] ?? null)} /></label>
      <label className="field"><span>Or paste project text</span><textarea rows={4} value={excerpt} disabled={busy || !!file} onChange={event => setExcerpt(event.target.value)} /></label>
      <button type="button" className="text-button" disabled={busy || !!file} onClick={() => setExcerpt(example)}>Use synthetic example</button>
      <button type="button" className="button secondary" disabled={!configured || busy || !(file || excerpt.trim())} onClick={extract}>{busy ? 'Reviewing source…' : 'Extract ordering requirements'}</button>
      {notice && <p role="status">{notice}</p>}
      {error && <p role="alert" className="draft-note">{error}</p>}
      {findings.map(finding => {
        const active = applied.find(item => item.id === finding.id)
        const target = targets[finding.id] ?? ''
        return <article className="requirement-card" key={finding.id}>
          <strong>{finding.requirement}</strong>
          <p>{finding.status} · {finding.timing} · {finding.scope || 'Scope unclear'}</p>
          {modeledMinimum(finding) && <p>Minimum to apply · {finding.minimum} {finding.category === 'neutral_ct' ? 'neutral CT inputs' : 'three-phase VT banks'}</p>}
          <blockquote>{finding.quote}</blockquote>
          <p>{finding.source} · page {finding.page}</p>
          <label className="field"><span>Affected device</span><select value={target} disabled={!!active}
            onChange={event => setTargets({ ...targets, [finding.id]: event.target.value })}>
            <option value="">Select a device</option>
            {roles.map((role, index) => <option key={index} value={index}>{role}</option>)}
          </select></label>
          <button type="button" className="button secondary" disabled={!active && target === ''}
            onClick={() => onChange(active ? applied.filter(item => item.id !== finding.id) : [...applied, { ...finding, device: Number(target) }])}>
            {active ? 'Remove from device' : modeledMinimum(finding) ? 'Confirm and apply minimum' : 'Track for device review'}
          </button>
        </article>
      })}
    </details>
  )
}
