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
    const selected = listener.address().port
    listener.close(error => error ? reject(error) : resolve(selected))
  })
})
const base = `http://127.0.0.1:${port}`
const env = {...process.env}
delete env.ANTHROPIC_API_KEY
delete env.OPENAI_API_KEY
const server = spawn(process.env.RELAY_TEST_PYTHON || path.join(root, '.venv/bin/python'),
  ['-m', 'uvicorn', 'backend.main:app', '--host', '127.0.0.1', '--port', String(port)],
  {cwd: root, env, stdio: ['ignore', 'pipe', 'pipe']})
let serverOutput = ''
for (const stream of [server.stdout, server.stderr]) stream.on('data', chunk => { serverOutput = (serverOutput + chunk).slice(-10000) })
let startError
server.once('error', error => { startError = error })
let browser
let page
const pageErrors = []
const visible = locator => locator.waitFor({state: 'visible', timeout: 15000})
const responseFor = predicate => page.waitForResponse(response => {
  if (!response.url().endsWith('/api/engineering/io') || response.request().method() !== 'POST') return false
  return predicate(response.request().postDataJSON(), response)
}, {timeout: 15000})
const ioRegion = () => page.getByRole('region', {name: 'Digital I/O budget', exact: true})
const assessment = () => page.getByRole('region', {name: 'Backend I/O assessment', exact: true})
const waitFingerprint = async fingerprint => {
  await page.waitForFunction(expected => document.querySelector('[aria-label="Backend I/O assessment"]')?.getAttribute('data-fingerprint') === expected, fingerprint, {timeout: 15000})
}
const assertBudget = async (di, output, requiredDI, requiredDO) => {
  assert.match(await assessment().innerText(), new RegExp(`Partial interface budget · ${di} DI / ${output} DO used · ${requiredDI} DI / ${requiredDO} DO with spares`))
}
async function changeOutputSpare(value) {
  const pending = responseFor(body => body.settings.spare.do === value)
  await ioRegion().getByLabel('DO spares (%)', {exact: true}).fill(String(value))
  const response = await pending
  assert.equal(response.status(), 200)
  const result = await response.json()
  await waitFingerprint(result.request_fingerprint)
  return result
}

try {
  let healthy = false
  for (let i = 0; i < 100; i++) {
    if (startError) throw startError
    if (server.exitCode !== null) throw new Error(serverOutput)
    try { if ((await fetch(`${base}/api/health`)).ok) { healthy = true; break } } catch {}
    await new Promise(resolve => setTimeout(resolve, 100))
  }
  assert.ok(healthy, `Server failed to start: ${serverOutput}`)
  browser = await chromium.launch({headless: true,
    ...(process.env.CHROMIUM_EXECUTABLE_PATH ? {executablePath: process.env.CHROMIUM_EXECUTABLE_PATH} : {})})
  page = await browser.newPage({viewport: {width: 1440, height: 1000}, acceptDownloads: true})
  page.on('pageerror', error => pageErrors.push(error.message))
  await page.goto(base)
  await page.getByRole('button', {name: /Build from a concept/}).click()
  await page.getByLabel('Study name', {exact: true}).fill('Backend I/O browser fixture')
  await page.getByLabel('HV (kV)', {exact: true}).fill('345')
  await page.getByLabel('Collector (kV)', {exact: true}).fill('34.5')
  await page.getByRole('button', {name: 'Add bay', exact: true}).click()
  await page.getByRole('button', {name: 'Add bay', exact: true}).click()
  await page.getByRole('button', {name: 'Review topology', exact: true}).click()
  await page.getByRole('button', {name: 'Confirm and analyze', exact: true}).click()
  await visible(page.getByRole('heading', {name: 'Choose a protection scheme', exact: true}))
  const initialResponse = responseFor(body => body.scheme === 'dedicated' && body.settings.variant === 'LOCK')
  await page.getByRole('radio').first().check()
  const initial = await (await initialResponse).json()
  await page.getByRole('button', {name: 'Review device requirements', exact: true}).click()
  await visible(assessment())
  await waitFingerprint(initial.request_fingerprint)
  await assertBudget(1, 2, 2, 4)
  assert.equal(initial.budget_completeness, 'partial')
  assert.equal(initial.budgets['T-P'].complete_fit, false)
  console.log('PASS reference budget is returned by backend with partial evidence and fingerprint')

  await ioRegion().getByText('Adjust spare I/O', {exact: true}).click()
  const zero = await changeOutputSpare(0)
  await assertBudget(1, 2, 2, 2)
  assert.equal(zero.budgets['T-P'].doRequired, 2)
  await page.getByRole('button', {name: 'Screen relay models', exact: true}).click()
  await visible(page.getByRole('heading', {name: 'Screen relay models', exact: true}))
  const geFit = page.getByRole('region', {name: 'Transformer Primary digital I/O fit', exact: true}).filter({hasText: 'GE T60'})
  await visible(geFit)
  await geFit.getByText('See point counts and hardware limits', {exact: true}).click()
  const outputRow = geFit.getByRole('row').filter({has: page.getByRole('rowheader', {name: 'Total digital outputs', exact: true})})
  assert.equal(await outputRow.getByRole('cell').first().innerText(), '2')
  await geFit.getByText('Prepare manufacturer ordering draft', {exact: true}).click()
  const orderingText = geFit.locator('label').filter({has: page.getByText('Ordering draft to copy', {exact: true})}).locator('textarea')
  assert.match(await orderingText.inputValue(), /1 DI \/ 2 DO used · 2 DI \/ 2 DO with spares/)
  assert.match(await orderingText.inputValue(), /Partial signal budget/)
  console.log('PASS edited spare policy drives budget, shortlist point table and ordering draft consistently')

  await page.getByRole('button', {name: 'Back', exact: true}).click()
  await visible(page.getByRole('heading', {name: 'Review relay signals', exact: true}))
  await ioRegion().getByText('Review and edit Transformer Primary signals', {exact: true}).click()
  const operate = ioRegion().locator('fieldset.signal-row').filter({has: page.getByText('87T-P operate', {exact: true})})
  await operate.getByText('Edit signal', {exact: true}).click()
  const operateSignal = initial.editor.signals.find(signal => signal.name === '87T-P operate')
  assert.ok(operateSignal)
  let pending = responseFor(body => body.settings.output_classes?.LOCK?.[String(operateSignal.id)]?.includes('fast'))
  await operate.getByLabel('Fast output required', {exact: true}).check()
  let classResult = await (await pending).json()
  await waitFingerprint(classResult.request_fingerprint)
  pending = responseFor(body => body.settings.output_classes?.LOCK?.[String(operateSignal.id)]?.includes('form_c'))
  await operate.getByLabel('Form-C contact required', {exact: true}).check()
  classResult = await (await pending).json()
  await waitFingerprint(classResult.request_fingerprint)
  await assertBudget(1, 2, 2, 2)
  assert.equal(classResult.budgets['T-P'].fastRequired, 1)
  assert.equal(classResult.budgets['T-P'].formCRequired, 1)
  assert.ok(classResult.card_examples.filter(card => card.device === 'T-P').every(card => card.screening === 'class_evidence_missing' && card.complete_fit === false))
  await ioRegion().getByText('SEL and GE card capacity examples', {exact: true}).click()
  await visible(ioRegion().getByText(/class evidence missing/).first())
  await visible(page.getByRole('region', {name: 'Project save and recovery', exact: true}).getByText('Saved in this browser.', {exact: true}))
  const downloadPending = page.waitForEvent('download')
  await page.getByRole('button', {name: 'Download project', exact: true}).click()
  const download = await downloadPending
  assert.equal(await download.failure(), null)
  const project = JSON.parse(await readFile(await download.path(), 'utf8'))
  assert.deepEqual(project.decisions.digital_settings['dedicated:poi'].output_classes.LOCK[String(operateSignal.id)].sort(), ['fast', 'form_c'])
  await page.reload()
  await visible(page.getByRole('heading', {name: 'Choose a protection scheme', exact: true}))
  await page.getByRole('button', {name: 'Review device requirements', exact: true}).click()
  await page.waitForFunction(() => document.querySelector('[aria-label="Backend I/O assessment"]')?.getAttribute('data-fingerprint'))
  assert.match(await assessment().innerText(), /1 fast outputs · 1 form-C contacts/)
  console.log('PASS conjunctive fast/form-C demand uses one physical contact and persists through project save/reload')

  await ioRegion().getByText('Adjust spare I/O', {exact: true}).click()
  let failOnce = true
  const unavailable = async route => {
    const body = route.request().postDataJSON()
    if (failOnce && body.settings.spare.do === 30) {
      failOnce = false
      await route.fulfill({status: 503, contentType: 'application/json', body: JSON.stringify({detail: 'Synthetic backend unavailable'})})
    } else await route.continue()
  }
  await page.route('**/api/engineering/io', unavailable)
  await ioRegion().getByLabel('DO spares (%)', {exact: true}).fill('30')
  await visible(assessment().getByRole('alert').filter({hasText: 'Synthetic backend unavailable'}))
  assert.equal(await assessment().getAttribute('data-fingerprint'), '')
  assert.equal(await assessment().locator('strong').count(), 0, 'Old budget remains visible after backend failure')
  await page.unroute('**/api/engineering/io', unavailable)
  const retryResponse = responseFor(body => body.settings.spare.do === 30)
  await assessment().getByRole('button', {name: 'Retry I/O calculation', exact: true}).click()
  const retried = await (await retryResponse).json()
  await waitFingerprint(retried.request_fingerprint)
  await assertBudget(1, 2, 2, 4)
  console.log('PASS backend failure hides prior totals and explicit retry restores a current result')

  let releaseOld
  let heldReady
  const oldGate = new Promise(resolve => {releaseOld = resolve})
  const oldStarted = new Promise(resolve => {heldReady = resolve})
  const holdOld = async route => {
    const body = route.request().postDataJSON()
    if (body.settings.spare.do === 40) {
      const response = await route.fetch()
      const bytes = await response.body()
      heldReady()
      await oldGate
      try { await route.fulfill({response, body: bytes}) } catch { /* The app may already have aborted this obsolete request. */ }
    } else await route.continue()
  }
  await page.route('**/api/engineering/io', holdOld)
  await ioRegion().getByLabel('DO spares (%)', {exact: true}).fill('40')
  await Promise.race([oldStarted, new Promise((_, reject) => setTimeout(() => reject(new Error('Old response was never intercepted')), 15000))])
  assert.equal(await assessment().getAttribute('data-fingerprint'), '')
  const latest = await changeOutputSpare(0)
  await assertBudget(1, 2, 2, 2)
  releaseOld()
  await page.waitForTimeout(400)
  assert.equal(await assessment().getAttribute('data-fingerprint'), latest.request_fingerprint)
  await assertBudget(1, 2, 2, 2)
  await page.unroute('**/api/engineering/io', holdOld)
  console.log('PASS delayed obsolete calculation cannot overwrite newer edited inputs')

  await ioRegion().getByText('Full endpoint signal ledger', {exact: true}).click()
  await visible(ioRegion().getByText(/actual approved drawing numbers have not been supplied/))
  assert.match(await ioRegion().innerText(), /external source contacts:/)
  assert.match(await ioRegion().innerText(), /unreviewed/)
  assert.deepEqual(pageErrors, [], 'Uncaught browser errors')
  console.log('PASS endpoint ledger distinguishes external contacts and unreviewed source requirements')
  console.log('PASS engineering I/O browser gate')
} catch (error) {
  if (page) {
    const screenshot = `/tmp/relay-engineering-io-${process.pid}.png`
    await page.screenshot({path: screenshot, fullPage: true}).catch(() => {})
    console.error(`Failure screenshot: ${screenshot}`)
  }
  throw error
} finally {
  await browser?.close().catch(() => {})
  server.kill('SIGTERM')
  await new Promise(resolve => {
    if (server.exitCode !== null || server.signalCode !== null || startError) return resolve()
    const timer = setTimeout(() => {server.kill('SIGKILL'); resolve()}, 5000)
    server.once('exit', () => {clearTimeout(timer); resolve()})
  })
}
