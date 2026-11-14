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
  affected_device_indices: number[]
}

const example = `Synthetic project excerpt for demonstration only.
Transformer Primary shall have at least two three-phase VT banks.
The POI line relay shall support IEC 61850 for future use. Activation is deferred.
Transformer Primary trip outputs shall operate the 86T lockout relay.
The breaker drawing labels its trip coils TC1 and TC2.`

type ReviewedFinding = Finding & { source: string; id: string }
type Extraction = { findings: Finding[]; pages_processed: number; unreadable_pages: number[]; unverified_findings: number }
export type AppliedRequirement = ReviewedFinding & { role_id: string }

export function modeledMinimum(finding: Finding) {
  return finding.status === 'required' && finding.timing !== 'future'
    && (finding.category === 'neutral_ct' || finding.category === 'vt_banks')
    && finding.minimum != null && Number.isSafeInteger(finding.minimum) && finding.minimum > 0 && finding.minimum <= 99
}

export function ProjectRequirements({ roles, applied, onChange }: {
  roles: {id: string; label: string}[]
  applied: AppliedRequirement[]
  onChange: (update: (findings: AppliedRequirement[]) => AppliedRequirement[]) => void
}) {
  const [configured, setConfigured] = useState<boolean | null>(null)
  const [file, setFile] = useState<File | null>(null)
  const [excerpt, setExcerpt] = useState('')
  const [findings, setFindings] = useState<ReviewedFinding[]>([])
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
        headers: {
          'Content-Type': file?.name.toLowerCase().endsWith('.pdf') ? 'application/pdf' : 'text/plain',
          'X-Relay-Roles': encodeURIComponent(JSON.stringify(roles.map(role => role.label))),
        },
        body,
      })
      const data = await response.json()
      if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : 'Requirements extraction failed.')
      const result: Extraction = data
      const reviewed = result.findings.map((finding): ReviewedFinding => ({
        ...finding, source: file?.name ?? 'Pasted excerpt', id: crypto.randomUUID(),
        affected_device_indices: (finding.affected_device_indices ?? []).filter(
          index => Number.isInteger(index) && index >= 0 && index < roles.length,
        ),
      }))
      const mapped = reviewed.flatMap(finding => finding.affected_device_indices.map(device => ({ ...finding, role_id: roles[device].id })))
      setFindings(current => [...current, ...reviewed])
      onChange(current => [...current, ...mapped])
      setNotice([
        `${result.findings.length} cited findings from ${result.pages_processed} processed pages or text excerpts. ${mapped.length} relay assignments.`,
        result.unreadable_pages.length ? `Text unavailable on page(s) ${result.unreadable_pages.join(', ')}. Paste the relevant text to review it.` : '',
        result.unverified_findings ? `${result.unverified_findings} findings omitted because their excerpts could not be matched to the source.` : '',
      ].filter(Boolean).join(' '))
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Requirements extraction failed.')
    } finally {
      setBusy(false)
    }
  }

  const displayed = [...new Map([...applied, ...findings].map(finding => [finding.id, finding])).values()]

  return (
    <details className="detail-block project-requirements">
      <summary>Project documents and requirements · optional</summary>
      <p>Upload a text-readable PDF excerpt (up to 30 pages) or paste a clause. Extraction sends the readable source text and selected scheme’s relay labels to Claude. Use synthetic or approved excerpts.</p>
      {configured === false && <p className="draft-note">Provider extraction is disabled in this alpha. You can continue with manual station and scheme requirements.</p>}
      <label className="field"><span>Project excerpt file</span><input type="file" accept=".pdf,.txt,application/pdf,text/plain" disabled={busy} onChange={event => setFile(event.target.files?.[0] ?? null)} /></label>
      <label className="field"><span>Or paste project text</span><textarea rows={4} value={excerpt} disabled={busy || !!file} onChange={event => setExcerpt(event.target.value)} /></label>
      <button type="button" className="text-button" disabled={busy || !!file} onClick={() => setExcerpt(example)}>Use synthetic example</button>
      <button type="button" className="button secondary" disabled={!configured || busy || !(file || excerpt.trim())} onClick={extract}>{busy ? 'Reviewing source…' : 'Extract ordering requirements'}</button>
      {notice && <p role="status">{notice}</p>}
      {error && <p role="alert" className="draft-note">{error}</p>}
      {displayed.map(finding => {
        const active = applied.filter(item => item.id === finding.id)
        return <article className="requirement-card" key={finding.id}>
          <strong>{finding.requirement}</strong>
          <p>{finding.status} · {finding.timing} · {finding.scope || 'Scope unclear'}</p>
          {modeledMinimum(finding) && <p>Minimum to apply · {finding.minimum} {finding.category === 'neutral_ct' ? 'neutral CT inputs' : 'three-phase VT banks'}</p>}
          <blockquote>{finding.quote}</blockquote>
          <p>{finding.source} · page {finding.page}</p>
          <p><strong>{active.length ? (modeledMinimum(finding) ? 'Applied to' : 'Tracked for') : 'Relay assignment'}</strong> · {
            active.length ? active.map(item => roles.find(role => role.id === item.role_id)?.label ?? 'Retired role').join(', ')
              : finding.affected_device_indices.length ? 'Removed from screening' : 'No clear match in this scheme'
          }</p>
          {active.length > 0 && <button type="button" className="text-button"
            onClick={() => onChange(current => current.filter(item => item.id !== finding.id))}>
            Remove relay assignments
          </button>}
        </article>
      })}
    </details>
  )
}
