import { useEffect, useRef, useState } from 'react'
import type { MutableRefObject } from 'react'
import type { Analysis } from './model'
import type { ProjectFile } from './projectState'

const prefix = 'relay-wizard/project/v1/'
const activeKey = 'relay-wizard/active/v1'
const maxBytes = 2 * 1024 * 1024
interface Validated { project: ProjectFile; analysis: Analysis; warnings: string[]; role_keys: string[] }
interface Stored { token: string; writer: string; project: ProjectFile }
async function validate(raw: string): Promise<Validated> {
  if (new Blob([raw]).size > maxBytes) throw new Error('Project files must be no larger than 2 MiB.')
  const response = await fetch('/api/projects/validate', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: raw})
  const body = await response.json()
  if (!response.ok) throw new Error(typeof body.detail === 'string' ? body.detail : 'Project validation failed. Your current study has not been replaced.')
  return body
}

export function ProjectStorage({ project, onOpen, onHydrated, onCopy, beforeSwitch }: {
  beforeSwitch: MutableRefObject<(() => Promise<boolean>) | null>
  project: ProjectFile | null; onOpen: (result: Validated) => void; onHydrated: () => void; onCopy: () => void
}) {
  const [status, setStatus] = useState('Checking saved work…')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [paused, setPaused] = useState(false)
  const [pending, setPending] = useState<Validated | null>(null)
  const [saved, setSaved] = useState<{id: string; title: string}[]>([])
  const expected = useRef<Record<string, string | null>>({})
  const writer = useRef(crypto.randomUUID())
  const pausedRef = useRef(false)
  const currentId = useRef<string | null>(null)
  const serialized = project ? JSON.stringify(project) : ''
  const latest = useRef(serialized)
  latest.current = serialized
  currentId.current = project?.project_id ?? null
  const refreshList = () => {
    const list = []
    for (let i = 0; i < localStorage.length; i++) {
      const key = localStorage.key(i)
      if (!key?.startsWith(prefix)) continue
      try { const entry: Stored = JSON.parse(localStorage.getItem(key) ?? 'null'); if (typeof entry?.project?.study?.title === 'string' && typeof entry?.token === 'string' && typeof entry?.project?.project_id === 'string' && key === prefix + entry.project.project_id) list.push({id: key.slice(prefix.length), title: entry.project.study.title}) } catch { /* Preserve corrupt entries for user-directed recovery. */ }
    }
    setSaved(list)
  }
  async function preserveCurrent() {
    const raw = latest.current
    if (!raw) return
    const result = await validate(raw)
    if (latest.current !== raw) throw new Error('Inputs changed while saving. Try the switch again; current work is still open.')
    if (!navigator.locks) throw new Error('Browser recovery is unavailable. Download your project before opening another study.')
    const copy = pausedRef.current
    const file = result.project
    if (copy) {
      file.project_id = crypto.randomUUID()
      file.study.title = `${file.study.title.slice(0, 75)} (recovery copy)`
    }
    await navigator.locks.request(prefix + file.project_id, async () => {
      if (latest.current !== raw) throw new Error('Inputs changed while saving. Try the switch again.')
      const stored = localStorage.getItem(prefix + file.project_id)
      if (!copy && (stored ? JSON.parse(stored).token : null) !== (expected.current[file.project_id] ?? null)) {
        throw new Error('Another tab changed this study. Resolve the conflict before switching.')
      }
      const token = crypto.randomUUID()
      localStorage.setItem(prefix + file.project_id, JSON.stringify({token, writer: writer.current, project: file}))
      expected.current[file.project_id] = token
      refreshList()
    })
  }
  beforeSwitch.current = async () => {
    try { const before = latest.current; await preserveCurrent(); if (latest.current !== before) throw new Error('Inputs changed while saving. Try the switch again.'); return true }
    catch (cause) { setError(cause instanceof Error ? cause.message : 'Current work could not be saved. Download a project before switching.'); return false }
  }
  async function openSaved(id: string) {
    setBusy(true); setError('')
    try {
      await preserveCurrent()
      const preservedInput = latest.current
      const raw = localStorage.getItem(prefix + id)
      if (!raw) throw new Error('Saved study is unavailable. Current work has not changed.')
      const entry: Stored = JSON.parse(raw)
      if (typeof entry?.token !== 'string' || typeof entry?.writer !== 'string' || entry?.project?.project_id !== id) throw new Error('Saved recovery metadata is invalid. Current work has not changed.')
      const validated = await validate(JSON.stringify(entry.project))
      // Re-read after the network request: another tab may have written in between.
      if (latest.current !== preservedInput) throw new Error('Current inputs changed during recovery. Your edits remain open; try again.')
      if (localStorage.getItem(prefix + id) !== raw) throw new Error('The saved study changed during recovery. Try opening it again.')
      expected.current[id] = entry.token
      pausedRef.current = false; setPaused(false)
      onOpen(validated)
      setStatus('Recovered inputs; engineering checks recalculated.')
    } catch (cause) { setError(cause instanceof Error ? cause.message : 'Saved work could not be recovered.'); setStatus('Recovery unavailable. Download a project file to protect new work.') }
    finally { setBusy(false) }
  }
  useEffect(() => {
    let disposed = false
    async function hydrate() {
      try {
        refreshList()
        const id = localStorage.getItem(activeKey)
        if (id) await openSaved(id)
        else setStatus('Recovery starts after the first study analysis.')
      } catch { setStatus('Browser storage is unavailable. Use Download project to save your work.') }
      finally { if (!disposed) onHydrated() }
    }
    void hydrate()
    return () => { disposed = true }
  }, [])
  useEffect(() => {
    pausedRef.current = false; setPaused(false)
  }, [project?.project_id])
  useEffect(() => {
    const changed = (event: StorageEvent) => {
      const id = currentId.current
      if (id && event.key === prefix + id) {
        let token: string | null = null
        try { token = event.newValue ? JSON.parse(event.newValue).token : null } catch { /* Fail closed on corrupt writes. */ }
        if (token !== expected.current[id]) {
          pausedRef.current = true; setPaused(true)
          setStatus('Another tab changed this study. Autosave paused; your local edits remain available.')
        }
      }
      try { refreshList() } catch { /* Existing warning is retained. */ }
    }
    window.addEventListener('storage', changed)
    return () => window.removeEventListener('storage', changed)
  }, [])
  useEffect(() => {
    if (!project || paused) return
    let cancelled = false
    setStatus('Unsaved changes…')
    const timer = setTimeout(async () => {
      try {
        const result = await validate(serialized)
        if (cancelled || latest.current !== serialized || pausedRef.current) return
        if (!navigator.locks) throw new Error('This browser cannot lock recovery writes. Download a project file instead.')
        await navigator.locks.request(prefix + project.project_id, async () => {
          if (cancelled || latest.current !== serialized || pausedRef.current) return
          const raw = localStorage.getItem(prefix + project.project_id)
          const entry: Stored | null = raw ? JSON.parse(raw) : null
          if ((entry?.token ?? null) !== (expected.current[project.project_id] ?? null)) {
            pausedRef.current = true; setPaused(true)
            throw new Error('Another tab changed this study. Autosave paused; save your local work as a separate copy.')
          }
          const token = crypto.randomUUID()
          localStorage.setItem(prefix + project.project_id, JSON.stringify({token, writer: writer.current, project: result.project}))
          expected.current[project.project_id] = token
          localStorage.setItem(activeKey, project.project_id)
          refreshList()
          setStatus('Saved in this browser.'); setError('')
        })
      } catch (cause) { if (!cancelled) setStatus(`Not saved: ${cause instanceof Error ? cause.message : 'Browser storage failed. Download a project file.'}`) }
    }, 600)
    return () => { cancelled = true; clearTimeout(timer) }
  }, [serialized, paused])
  async function download() {
    if (!project) return
    setBusy(true); setError('')
    try {
      const result = await validate(JSON.stringify(project))
      const url = URL.createObjectURL(new Blob([JSON.stringify(result.project, null, 2)], {type: 'application/json'}))
      const anchor = document.createElement('a'); anchor.href = url; anchor.download = 'relay-wizard-project.json'; anchor.click()
      setTimeout(() => URL.revokeObjectURL(url), 1000)
    } catch (cause) { setError(cause instanceof Error ? cause.message : 'Project download failed.') }
    finally { setBusy(false) }
  }
  async function importFile(file?: File) {
    if (!file) return
    setBusy(true); setError(''); setPending(null)
    try {
      if (file.size > maxBytes) throw new Error('Project files must be no larger than 2 MiB.')
      const result = await validate(await file.text())
      // Imports always open a separate copy. Existing local project identity is not overwritten.
      result.project.project_id = crypto.randomUUID()
      setPending(result)
    } catch (cause) { setError(cause instanceof Error ? cause.message : 'Invalid project file. Current work has not changed.') }
    finally { setBusy(false) }
  }
  return <section className="panel project-storage" aria-label="Project save and recovery">
    <p role="status" aria-live="polite">{status}</p>
    <div className="editor-actions">
      <button className="button secondary" type="button" disabled={!project || busy} onClick={download}>Download project</button>
      <label className="field"><span>Open project file</span><input type="file" accept=".json,application/json" disabled={busy} onChange={event => { void importFile(event.target.files?.[0]); event.target.value = '' }} /></label>
      {!!saved.length && <label className="field"><span>Recover saved study</span><select aria-label="Recover saved study" value="" disabled={busy} onChange={event => { if (event.target.value) void openSaved(event.target.value) }}><option value="">Choose saved study…</option>{saved.map(item => <option value={item.id} key={item.id}>{item.title}</option>)}</select></label>}
      {paused && <><button className="button secondary" type="button" onClick={onCopy}>Save this tab as a separate copy</button><button className="button secondary" type="button" disabled={busy} onClick={() => project && openSaved(project.project_id)}>Load other tab’s saved version</button></>}
    </div>
    <details><summary>What gets saved</summary><p>Active station inputs, pending scenario edits, CT origins, relay inputs, wiring choices and ordering notes. Source drawings, pasted excerpts, calculated results, approvals and earlier comparison history are excluded. Loading recalculates checks and asks for remote-channel review again. Browser storage is recovery only; download a project for transfer.</p></details>
    {pending && <div role="status"><p>Ready to open “{pending.project.study.title}” as a separate study. Current saved work remains available.</p><button className="button primary" type="button" disabled={busy} onClick={async () => { setBusy(true); setError(''); try { const before = latest.current; await preserveCurrent(); if (latest.current !== before) throw new Error('Inputs changed while saving. Try opening the import again.'); onOpen(pending); setPending(null) } catch (cause) { setError(cause instanceof Error ? cause.message : 'Current work could not be saved.') } finally { setBusy(false) } }}>Open imported copy</button><button className="button secondary" type="button" disabled={busy} onClick={() => setPending(null)}>Cancel import</button></div>}
    {error && <p role="alert">{error}</p>}
  </section>
}
