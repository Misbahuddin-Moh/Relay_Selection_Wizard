import assert from 'node:assert/strict'
import { spawn } from 'node:child_process'
import { createRequire } from 'node:module'
import { createServer } from 'node:net'
import { readFile } from 'node:fs/promises'
import { fileURLToPath } from 'node:url'
import path from 'node:path'

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const require = createRequire(path.join(root, 'frontend/package.json'))
const { chromium } = require('playwright')
const port = await new Promise((resolve, reject) => {
  const listener = createServer()
  listener.once('error', reject)
  listener.listen(0, '127.0.0.1', () => {
    const value = listener.address().port
    listener.close(error => error ? reject(error) : resolve(value))
  })
})
const base = `http://127.0.0.1:${port}`
const env = { ...process.env }
delete env.ANTHROPIC_API_KEY
delete env.OPENAI_API_KEY
const server = spawn(process.env.RELAY_TEST_PYTHON || path.join(root, '.venv/bin/python'),
  ['-m', 'uvicorn', 'backend.main:app', '--host', '127.0.0.1', '--port', String(port)],
  { cwd: root, env, stdio: ['ignore', 'pipe', 'pipe'] })
let serverOutput = ''
for (const stream of [server.stdout, server.stderr]) stream.on('data', value => { serverOutput = (serverOutput + value).slice(-10000) })
let startError
server.once('error', error => { startError = error })
let browser
let currentPage
const pageErrors = []
const contexts = []
const visible = locator => locator.waitFor({ state: 'visible', timeout: 15000 })
const toolbar = page => page.getByRole('region', { name: 'Project save and recovery', exact: true })
const saved = page => visible(toolbar(page).getByText('Saved in this browser.', { exact: true }))
const attachPage = async context => {
  const page = await context.newPage()
  page.on('pageerror', error => pageErrors.push(error.message))
  currentPage = page
  return page
}
async function downloadProject(page) {
  const pending = page.waitForEvent('download')
  await toolbar(page).getByRole('button', { name: 'Download project', exact: true }).click()
  const download = await pending
  assert.equal(await download.failure(), null)
  return JSON.parse(await readFile(await download.path(), 'utf8'))
}
async function stageImport(page, project) {
  await toolbar(page).getByLabel('Open project file', { exact: true }).setInputFiles({
    name: 'portable-fixture.json', mimeType: 'application/json', buffer: Buffer.from(JSON.stringify(project)),
  })
  await visible(toolbar(page).getByRole('button', { name: 'Open imported copy', exact: true }))
}
async function openImport(page, project) {
  await stageImport(page, project)
  await toolbar(page).getByRole('button', { name: 'Open imported copy', exact: true }).click()
  await visible(page.getByRole('heading', { name: 'Choose a protection scheme', exact: true }))
}
async function openSignals(page) {
  await visible(page.getByRole('heading', { name: 'Choose a protection scheme', exact: true }))
  await page.getByRole('button', { name: 'Review device requirements', exact: true }).click()
  await visible(page.getByRole('heading', { name: 'Review relay signals', exact: true }))
}
const inputCard = (page, roleId) => page.locator(`article[data-role-id="${roleId}"]`)
const assertInputs = async (page, roleId) => {
  const card = inputCard(page, roleId)
  assert.equal(await card.getByLabel('Neutral CT inputs', { exact: true }).inputValue(), '2')
  assert.equal(await card.getByLabel('Three-phase VT banks', { exact: true }).inputValue(), '1')
}
const scenarioStart = async page => {
  await page.getByRole('button', { name: /^1\s*Station$/ }).click()
  await page.getByRole('button', { name: 'Create what-if scenario', exact: true }).click()
  await visible(page.getByRole('heading', { name: 'Scenario inputs', exact: true }))
}

try {
  let healthy = false
  for (let attempt = 0; attempt < 100; attempt++) {
    if (startError) throw startError
    if (server.exitCode !== null) throw new Error(serverOutput)
    try { if ((await fetch(`${base}/api/health`)).ok) { healthy = true; break } } catch {}
    await new Promise(resolve => setTimeout(resolve, 100))
  }
  assert.ok(healthy, `Server did not start: ${serverOutput}`)
  browser = await chromium.launch({ headless: true,
    ...(process.env.CHROMIUM_EXECUTABLE_PATH ? { executablePath: process.env.CHROMIUM_EXECUTABLE_PATH } : {}) })
  const context = await browser.newContext({ acceptDownloads: true })
  contexts.push(context)
  const page = await attachPage(context)
  await page.goto(base)
  await page.getByRole('button', { name: /Build from a concept/ }).click()
  await page.getByLabel('Study name', { exact: true }).fill('Portable recovery fixture')
  await page.getByLabel('HV (kV)', { exact: true }).fill('345')
  await page.getByLabel('Collector (kV)', { exact: true }).fill('34.5')
  await page.getByRole('button', { name: 'Add bay', exact: true }).click()
  await page.getByRole('button', { name: 'Add bay', exact: true }).click()
  await page.getByRole('button', { name: 'Review topology', exact: true }).click()
  await page.getByRole('button', { name: 'Confirm and analyze', exact: true }).click()
  await visible(page.getByRole('heading', { name: 'Choose a protection scheme', exact: true }))
  await page.getByRole('radio').first().check()
  await openSignals(page)
  const feeder = page.locator('article[data-role-id]').filter({ has: page.getByRole('heading', { name: '52-F-1', exact: true }) })
  const roleId = await feeder.getAttribute('data-role-id')
  assert.ok(roleId)
  await feeder.getByLabel('Neutral CT inputs', { exact: true }).fill('2')
  await feeder.getByLabel('Three-phase VT banks', { exact: true }).fill('1')
  await saved(page)
  const original = await downloadProject(page)
  const roleKey = `dedicated:poi/${roleId}`
  assert.deepEqual(original.decisions.requirements[roleKey], { neutral: '2', vt: '1' })
  for (const excluded of ['analysis', 'approvals', 'api_key', 'provider_permission', 'source_text']) assert.ok(!(excluded in original))
  assert.equal(original.draft, null)
  await page.reload()
  await openSignals(page)
  await assertInputs(page, roleId)
  console.log('PASS autosave/reload preserves stable feeder role and relay choices')

  await toolbar(page).getByLabel('Open project file', { exact: true }).setInputFiles({
    name: 'broken.json', mimeType: 'application/json', buffer: Buffer.from('{broken'),
  })
  await visible(toolbar(page).getByRole('alert'))
  await assertInputs(page, roleId)
  assert.equal(await toolbar(page).getByRole('button', { name: 'Open imported copy', exact: true }).count(), 0)
  console.log('PASS invalid import leaves current work and decisions intact')

  await scenarioStart(page)
  const firstBay = page.locator('details.bay').first()
  await firstBay.locator('summary').click()
  await firstBay.getByLabel('Breaker tag', { exact: true }).fill('52-RENAMED')
  await firstBay.getByRole('button', { name: 'Move 52-RENAMED down', exact: true }).click()
  let labels = await page.locator('details.bay summary strong').allTextContents()
  assert.equal(labels[1], '52-RENAMED')
  await page.getByRole('button', { name: 'Undo input edit', exact: true }).click()
  labels = await page.locator('details.bay summary strong').allTextContents()
  assert.equal(labels[0], '52-RENAMED')
  await page.getByRole('button', { name: 'Redo input edit', exact: true }).click()
  labels = await page.locator('details.bay summary strong').allTextContents()
  assert.equal(labels[1], '52-RENAMED')
  await page.getByRole('button', { name: 'Analyze scenario', exact: true }).click()
  await openSignals(page)
  await assertInputs(page, roleId)
  assert.equal(await inputCard(page, roleId).getByRole('heading').innerText(), '52-RENAMED')
  await saved(page)
  const renamed = await downloadProject(page)
  assert.equal(renamed.study.uid, original.study.uid)
  assert.equal(renamed.study.bays[1].uid, original.study.bays[0].uid)
  assert.deepEqual(renamed.decisions.requirements[roleKey], original.decisions.requirements[roleKey])
  console.log('PASS rename/reorder/undo/redo keep relay choices attached to equipment identity')

  const portableContext = await browser.newContext({ acceptDownloads: true })
  contexts.push(portableContext)
  const importedPage = await attachPage(portableContext)
  await importedPage.goto(base)
  await stageImport(importedPage, renamed)
  assert.equal(await importedPage.getByRole('heading', { name: 'Choose a protection scheme', exact: true }).count(), 0)
  await toolbar(importedPage).getByRole('button', { name: 'Open imported copy', exact: true }).click()
  await openSignals(importedPage)
  await assertInputs(importedPage, roleId)
  await saved(importedPage)
  const imported = await downloadProject(importedPage)
  assert.notEqual(imported.project_id, renamed.project_id)
  assert.equal(imported.study.uid, renamed.study.uid)
  assert.deepEqual(imported.study.bays.map(bay => bay.uid), renamed.study.bays.map(bay => bay.uid))
  console.log('PASS portable download/import opens separate project with original equipment identities')

  await scenarioStart(importedPage)
  await importedPage.getByLabel('Scenario name', { exact: true }).fill('Pending draft recovered')
  await importedPage.getByLabel('HV (kV)', { exact: true }).fill('')
  await saved(importedPage)
  await importedPage.reload()
  await visible(importedPage.getByRole('heading', { name: 'Scenario inputs', exact: true }))
  assert.equal(await importedPage.getByLabel('Scenario name', { exact: true }).inputValue(), 'Pending draft recovered')
  assert.equal(await importedPage.getByLabel('HV (kV)', { exact: true }).inputValue(), '')
  const evidence = importedPage.getByRole('region', { name: 'Study evidence and support', exact: true })
  await visible(evidence.getByText(/Inputs changed\. Analyze this draft/))
  assert.equal(await evidence.locator('li').count(), 0)
  const pending = await downloadProject(importedPage)
  assert.equal(pending.draft.hv_kv, 0)
  assert.equal(pending.draft.title, 'Pending draft recovered')
  assert.ok(pending.study.hv_kv > 0)
  console.log('PASS incomplete draft refresh/download preserves pending inputs without stale evidence')

  // Hold target validation after preservation, then edit the still-open draft.
  // The response must not replace that newer input revision.
  await saved(importedPage)
  let releaseTarget
  let targetReady
  const heldTarget = new Promise(resolve => { releaseTarget = resolve })
  const targetStarted = new Promise(resolve => { targetReady = resolve })
  let validationRequests = 0
  await importedPage.route('**/api/projects/validate', async route => {
    validationRequests++
    if (validationRequests === 2) { targetReady(); await heldTarget }
    await route.continue()
  })
  await toolbar(importedPage).getByLabel('Recover saved study', { exact: true }).selectOption(imported.project_id)
  await Promise.race([targetStarted, new Promise((_, reject) => setTimeout(() => reject(new Error('Target validation was not reached')), 15000))])
  await importedPage.getByLabel('Scenario name', { exact: true }).fill('Newer edit during recovery')
  releaseTarget()
  await visible(toolbar(importedPage).getByRole('alert').filter({hasText: /Current inputs changed during recovery/}))
  assert.equal(await importedPage.getByLabel('Scenario name', { exact: true }).inputValue(), 'Newer edit during recovery')
  await importedPage.unroute('**/api/projects/validate')
  await saved(importedPage)
  console.log('PASS late recovery response cannot overwrite edits made during validation')

  const secondTab = await attachPage(portableContext)
  await secondTab.goto(base)
  await visible(secondTab.getByRole('heading', { name: 'Scenario inputs', exact: true }))
  await secondTab.getByLabel('Scenario name', { exact: true }).fill('Other tab saved version')
  await saved(secondTab)
  await visible(toolbar(importedPage).getByText(/Another tab changed this study\. Autosave paused/))
  await importedPage.getByLabel('Scenario name', { exact: true }).fill('Local paused edits remain')
  await importedPage.waitForTimeout(900)
  const persisted = await importedPage.evaluate(id => JSON.parse(localStorage.getItem(`relay-wizard/project/v1/${id}`)), imported.project_id)
  assert.equal(persisted.project.draft.title, 'Other tab saved version')
  assert.equal(await importedPage.getByLabel('Scenario name', { exact: true }).inputValue(), 'Local paused edits remain')
  console.log('PASS second tab pauses conflicting autosave and preserves local edits')

  const failedStorage = await browser.newContext({ acceptDownloads: true })
  contexts.push(failedStorage)
  await failedStorage.addInitScript(() => {
    const originalSet = Storage.prototype.setItem
    Storage.prototype.setItem = function (key, value) {
      if (key.startsWith('relay-wizard/')) throw new DOMException('Synthetic quota exhaustion', 'QuotaExceededError')
      return originalSet.call(this, key, value)
    }
  })
  const failedPage = await attachPage(failedStorage)
  await failedPage.goto(base)
  await openImport(failedPage, renamed)
  await visible(toolbar(failedPage).getByText(/Not saved:.*quota/i))
  const recoverable = await downloadProject(failedPage)
  assert.equal(recoverable.study.uid, renamed.study.uid)
  console.log('PASS storage failure is visible and portable download remains available')

  const corruptStorage = await browser.newContext()
  contexts.push(corruptStorage)
  await corruptStorage.addInitScript(() => {
    localStorage.setItem('relay-wizard/active/v1', 'corrupt-entry')
    localStorage.setItem('relay-wizard/project/v1/corrupt-entry', '{broken')
  })
  const corruptPage = await attachPage(corruptStorage)
  await corruptPage.goto(base)
  await visible(toolbar(corruptPage).getByText(/Recovery unavailable/))
  await visible(corruptPage.getByRole('button', { name: /Build from a concept/ }))
  const corruptRaw = await corruptPage.evaluate(() => localStorage.getItem('relay-wizard/project/v1/corrupt-entry'))
  assert.equal(corruptRaw, '{broken')
  assert.deepEqual(pageErrors, [], 'Uncaught browser errors')
  console.log('PASS corrupt recovery is preserved and does not prevent a fresh study')
  console.log('PASS project recovery browser gate')
} catch (error) {
  if (currentPage) {
    const screenshot = `/tmp/relay-project-recovery-${process.pid}.png`
    await currentPage.screenshot({ path: screenshot, fullPage: true }).catch(() => {})
    console.error(`Failure screenshot: ${screenshot}`)
  }
  throw error
} finally {
  for (const context of contexts) await context.close().catch(() => {})
  await browser?.close().catch(() => {})
  server.kill('SIGTERM')
  await new Promise(resolve => {
    if (server.exitCode !== null || server.signalCode !== null || startError) return resolve()
    const timer = setTimeout(() => { server.kill('SIGKILL'); resolve() }, 5000)
    server.once('exit', () => { clearTimeout(timer); resolve() })
  })
}
