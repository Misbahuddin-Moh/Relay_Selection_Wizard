import assert from 'node:assert/strict'
import { spawn } from 'node:child_process'
import { createRequire } from 'node:module'
import { createServer } from 'node:net'
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
server.once('error', error => {startError = error})
let browser
let page
const pageErrors = []
const visible = locator => locator.waitFor({state: 'visible', timeout: 15000})
const comparison = () => page.getByRole('region', {name: 'Protection approach comparison', exact: true})
const table = () => page.getByRole('region', {name: 'Protection comparison table', exact: true})
const toolbar = () => page.getByRole('region', {name: 'Project save and recovery', exact: true})
const responseFor = title => page.waitForResponse(response =>
  response.url().endsWith('/api/protection-preview') && response.request().method() === 'POST' &&
  response.request().postDataJSON().title === title, {timeout: 15000})
async function stageStudy(study) {
  await toolbar().getByLabel('Open project file', {exact: true}).setInputFiles({
    name: 'review-fixture.json', mimeType: 'application/json', buffer: Buffer.from(JSON.stringify(study)),
  })
  await visible(toolbar().getByRole('button', {name: 'Open imported copy', exact: true}))
}
async function openStudy(study) {
  await stageStudy(study)
  const received = responseFor(study.title)
  await toolbar().getByRole('button', {name: 'Open imported copy', exact: true}).click()
  const response = await received
  assert.equal(response.status(), 200)
  const result = await response.json()
  await visible(comparison())
  return result
}
async function inspect(title) {
  await table().getByRole('columnheader').filter({has: page.getByText(title, {exact: true})}).getByRole('button').click()
  await visible(comparison().locator('details.comparison-detail'))
  assert.match(await comparison().locator('details.comparison-detail > summary').innerText(), new RegExp(title))
}
const detail = () => comparison().locator('details.comparison-detail')
const tableRow = label => table().getByRole('row').filter({has: page.getByRole('rowheader', {name: label, exact: true})})
const clone = value => JSON.parse(JSON.stringify(value))

try {
  let healthy = false
  for (let i = 0; i < 100; i++) {
    if (startError) throw startError
    if (server.exitCode !== null) throw new Error(serverOutput)
    try {if ((await fetch(`${base}/api/health`)).ok) {healthy = true; break}} catch {}
    await new Promise(resolve => setTimeout(resolve, 100))
  }
  assert.ok(healthy, `Server failed to start: ${serverOutput}`)
  const station = (await (await fetch(`${base}/api/study`)).json()).study
  station.title = 'Visible comparison fixture'
  station.auxiliary = 'excluded'
  station.ct_inventory = Object.fromEntries(['lv_breaker_135', 'lv_breaker_246', 'hv_breaker_135', 'hv_breaker_246',
    'transformer_hv_phase', 'transformer_lv_phase', 'transformer_hv_neutral', 'transformer_lv_neutral'].map(key => [key, 2]))
  browser = await chromium.launch({headless: true,
    ...(process.env.CHROMIUM_EXECUTABLE_PATH ? {executablePath: process.env.CHROMIUM_EXECUTABLE_PATH} : {})})
  page = await browser.newPage({viewport: {width: 1440, height: 1000}})
  page.on('pageerror', error => pageErrors.push(error.message))
  page.on('request', request => {
    if (request.method() === 'POST' && /\/api\/(protection-options|drawing\/extract|requirements\/extract)$/.test(request.url())) {
      pageErrors.push('Unexpected paid-provider route request')
    }
  })
  await page.goto(base)
  const result = await openStudy(station)
  assert.equal(await table().getByRole('columnheader').count(), 7)
  assert.match(await tableRow('Primary zones and functions').innerText(), /87T.*87B/s)
  assert.match(await tableRow('Primary zones and functions').innerText(), /87TB/)
  assert.match(await tableRow('Readiness and evidence').innerText(), /Engineering review open/)
  assert.match(await tableRow('Primary CT boundaries').innerText(), /Modeled present · unreviewed/)
  const titles = result.options.map(option => option.check.title)
  await inspect(titles[0])
  assert.equal(await detail().getByRole('heading', {name: 'Transformer Primary zone', exact: true}).count(), 1)
  assert.equal(await detail().getByRole('heading', {name: 'Collector bus zone', exact: true}).count(), 1)
  assert.match(await detail().innerText(), /CT presence does not establish suitability/)
  assert.match(await detail().innerText(), /Primary and Secondary independence is unverified/)
  assert.match(await detail().innerText(), /Trip targets are provisional/)
  await inspect(titles[1])
  const sharedPrimary = detail().locator('article.comparison-zone').filter({has: page.getByRole('heading', {name: 'Transformer Primary zone', exact: true})})
  const sharedBus = detail().locator('article.comparison-zone').filter({has: page.getByRole('heading', {name: 'Collector bus zone', exact: true})})
  assert.match(await sharedPrimary.innerText(), /Hosted by: Transformer Primary \+ collector bus/)
  assert.match(await sharedBus.innerText(), /Hosted by: Transformer Primary \+ collector bus/)
  await inspect(titles[2])
  assert.equal(await detail().getByRole('heading', {name: 'Extended transformer and collector bus Primary', exact: true}).count(), 1)
  assert.equal(await detail().getByRole('heading', {name: 'Collector bus zone', exact: true}).count(), 0)
  assert.equal(await detail().getByRole('heading', {name: 'Transformer-only Secondary zone', exact: true}).count(), 1)
  assert.match(await detail().innerText(), /extended Primary zone reduces fault-location discrimination/)
  assert.match(await tableRow('Readiness and evidence').innerText(), /Procurement release unavailable/)
  for (const option of result.options) {
    await inspect(option.check.title)
    const loss = comparison().getByRole('region', {name: 'Protection system loss assessment', exact: true})
    await visible(loss)
    for (const unavailable of ['primary', 'secondary']) {
      const scenario = loss.locator(`article[data-unavailable="${unavailable}"]`)
      assert.equal(await scenario.count(), 1)
      const expectation = option.review.system_loss.find(row => row.unavailable === unavailable)
      assert.match(await scenario.innerText(), /unverified|not proven|not verified/i)
      assert.ok((await scenario.innerText()).includes(expectation.summary))
    }
    const diagram = page.locator('svg.drawing').filter({has: page.locator('[data-protection="feeder-overcurrent"]')}).last()
    assert.equal(await diagram.locator('[data-protection="feeder-overcurrent"][data-ct-source="bus-side"]').count(), station.bays.length)
    assert.equal(await diagram.locator('[data-ct-position="bus-side"]').count(), station.bays.length)
    assert.equal(await diagram.locator('[data-ct-position="circuit-side"]').count(), station.bays.length)
    const bounds = await diagram.evaluate(svg => {
      const rect = svg.querySelector('[data-protection="feeder-overcurrent"]')
      const busCt = svg.querySelector('[data-ct-position="bus-side"] .ct-symbol')
      const circuitCt = svg.querySelector('[data-ct-position="circuit-side"] .ct-symbol')
      const position = node => Number(node.getAttribute('transform').match(/translate\([^,]+,\s*([\d.]+)\)/)[1])
      const zone = svg.querySelector('[data-end-ct="circuit-side"]')
      return {start: Number(rect.getAttribute('y')), end: Number(rect.getAttribute('y')) + Number(rect.getAttribute('height')),
        busCt: position(busCt), circuitCt: position(circuitCt),
        differentialEnd: zone ? Number(zone.getAttribute('y')) + Number(zone.getAttribute('height')) : null}
    })
    assert.equal(bounds.start, bounds.busCt, 'Feeder box starts at its bus-side measurement')
    assert.ok(bounds.end > bounds.circuitCt, 'Feeder box includes the breaker and outgoing circuits')
    assert.equal(bounds.differentialEnd, bounds.circuitCt, 'Bus/combined zone ends at circuit-side CT')
    assert.match(await diagram.textContent(), /reach subject to coordination/)
    const combinedPrimary = option.main_coverage.transformer_a.function === '87TB'
    assert.equal(await diagram.locator('[data-protection="combined"]').count(), Number(combinedPrimary))
    assert.equal(await diagram.locator('[data-protection="bus"]').count(), Number(!combinedPrimary))
  }
  await page.screenshot({path: '/tmp/relay-coverage-desktop.png', fullPage: true})
  console.log('PASS all six choices retain feeder boxes, explicit opposite-side sensing, differential CT endpoints and qualified system-loss explanations')
  await page.setViewportSize({width: 390, height: 844})
  const width = await page.evaluate(() => ({viewport: document.documentElement.clientWidth, body: document.body.scrollWidth, document: document.documentElement.scrollWidth}))
  let overflowElements = []
  if (Math.max(width.body, width.document) > width.viewport + 1) {
    overflowElements = await page.evaluate(() => [...document.querySelectorAll('body *')].map(element => {
      const rectangle = element.getBoundingClientRect()
      const style = getComputedStyle(element)
      return {tag: element.tagName.toLowerCase(), class: element.getAttribute('class'), ariaLabel: element.getAttribute('aria-label'),
        left: rectangle.left, right: rectangle.right, width: rectangle.width, position: style.position,
        overflowX: style.overflowX, scrollWidth: element.scrollWidth, clientWidth: element.clientWidth}
    }).filter(element => element.width > 0 && (element.right > document.documentElement.clientWidth + 1 || element.left < -1))
      .sort((a, b) => b.right - a.right).slice(0, 35))
  }
  assert.ok(Math.max(width.body, width.document) <= width.viewport + 1,
    `Comparison causes page overflow: ${JSON.stringify({dimensions: width, elements: overflowElements})}`)
  await page.screenshot({path: '/tmp/relay-coverage-mobile.png', fullPage: true})
  await page.setViewportSize({width: 1440, height: 1000})
  console.log('PASS visible comparison distinguishes separate, shared hardware and extended Primary while retaining Secondary and unresolved evidence')

  const absent = clone(station)
  absent.title = 'Absent measurement fixture'
  absent.ct_inventory.hv_breaker_135 = 0
  await openStudy(absent)
  await inspect(titles[0])
  assert.match(await tableRow('Primary CT boundaries').innerText(), /Required measurement absent/)
  assert.match(await detail().innerText(), /Primary measurement missing/)
  assert.match(await detail().locator('.comparison-readiness').innerText(), /Design blockers/)
  const unknown = clone(station)
  unknown.title = 'Unknown measurement fixture'
  unknown.ct_inventory.hv_breaker_135 = null
  await openStudy(unknown)
  await inspect(titles[0])
  assert.match(await tableRow('Primary CT boundaries').innerText(), /Measurement assignment unresolved/)
  assert.match(await detail().innerText(), /Primary measurement assignment unresolved/)
  console.log('PASS absent and unknown CTs render distinct blockers and open measurement assignments')

  const invalidVoltage = clone(station)
  invalidVoltage.title = 'Unsupported voltage fixture'
  invalidVoltage.hv_kv = 34.5
  invalidVoltage.mv_kv = 345
  const unsupported = await openStudy(invalidVoltage)
  assert.ok(unsupported.options.every(option => option.device_requirements.every(role => role.candidates.length === 0)))
  await inspect(titles[0])
  assert.match(await tableRow('Readiness and evidence').innerText(), /Outside supported hardware scope/)
  assert.match(await detail().innerText(), /HV kV greater than collector kV/)
  console.log('PASS unsupported voltage relationship suppresses hardware candidates and visibly explains scope')

  const collision = clone(station)
  collision.title = 'Reserved feeder name fixture'
  collision.bays[0].id = 'Transformer Secondary'
  const collisionResult = await openStudy(collision)
  await inspect(titles[0])
  const originalSecondary = result.options[0].device_requirements.find(role => role.kind === 'transformer' && role.purpose === 'secondary')
  const collisionSecondary = collisionResult.options[0].device_requirements.find(role => role.kind === 'transformer' && role.purpose === 'secondary')
  const feeder = collisionResult.options[0].device_requirements.find(role => role.kind === 'feeder' && role.subject_id === collision.bays[0].uid)
  assert.equal(collisionSecondary.role_id, originalSecondary.role_id)
  assert.notEqual(feeder.role_id, collisionSecondary.role_id)
  await page.getByRole('button', {name: 'Review device requirements', exact: true}).click()
  await visible(page.getByRole('heading', {name: 'Review relay signals', exact: true}))
  const io = await fetch(`${base}/api/engineering/io`, {
    method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({study: collision, scheme: 'dedicated',
      settings: {variant: 'LOCK', spare: {di: 20, do: 20, basis: 'used'}}}),
  }).then(response => response.json())
  assert.equal(io.budgets['T-S'].role_id, collisionSecondary.role_id)
  assert.equal(io.budgets['FP-F1'].role_id, feeder.role_id)
  await page.getByRole('button', {name: 'Back', exact: true}).click()
  await visible(comparison())
  console.log('PASS reserved feeder display name cannot replace the Transformer Secondary engineering identity')

  let releaseOld
  let oldReady
  const oldGate = new Promise(resolve => {releaseOld = resolve})
  const oldStarted = new Promise(resolve => {oldReady = resolve})
  const holdOld = async route => {
    if (route.request().postDataJSON().title === 'Held obsolete review') {
      const response = await route.fetch()
      const bytes = await response.body()
      oldReady()
      await oldGate
      try {await route.fulfill({response, body: bytes})} catch { /* Aborted obsolete fetch is expected. */ }
    } else await route.continue()
  }
  await page.route('**/api/protection-preview', holdOld)
  const held = clone(absent)
  held.title = 'Held obsolete review'
  await stageStudy(held)
  await toolbar().getByRole('button', {name: 'Open imported copy', exact: true}).click()
  await Promise.race([oldStarted, new Promise((_, reject) => setTimeout(() => reject(new Error('Obsolete review request never intercepted')), 15000))])
  assert.equal(await comparison().count(), 0, 'Old comparison remains visible while a new station is pending')
  assert.equal(await page.getByRole('radio').count(), 0)
  const newest = clone(station)
  newest.title = 'Current positive review'
  await openStudy(newest)
  await inspect(titles[0])
  assert.match(await tableRow('Primary CT boundaries').innerText(), /Modeled present · unreviewed/)
  releaseOld()
  await page.waitForTimeout(400)
  assert.match(await tableRow('Primary CT boundaries').innerText(), /Modeled present · unreviewed/)
  assert.doesNotMatch(await detail().innerText(), /Primary measurement missing/)
  await page.unroute('**/api/protection-preview', holdOld)
  console.log('PASS pending study changes hide old selectable reviews and delayed obsolete results cannot replace the current comparison')

  let failOnce = true
  const failPreview = async route => {
    if (route.request().postDataJSON().title === 'Review failure fixture' && failOnce) {
      failOnce = false
      await route.fulfill({status: 503, contentType: 'application/json', body: JSON.stringify({detail: 'Preview failure fixture'})})
    } else await route.continue()
  }
  await page.route('**/api/protection-preview', failPreview)
  const failing = clone(station)
  failing.title = 'Review failure fixture'
  await stageStudy(failing)
  await toolbar().getByRole('button', {name: 'Open imported copy', exact: true}).click()
  await visible(page.getByRole('alert').filter({hasText: 'Preview failure fixture'}))
  assert.equal(await comparison().count(), 0)
  assert.equal(await page.getByRole('radio').count(), 0)
  const retry = responseFor(failing.title)
  await page.getByRole('button', {name: 'Retry station checks', exact: true}).click()
  assert.equal((await retry).status(), 200)
  await visible(comparison())
  await page.unroute('**/api/protection-preview', failPreview)
  assert.deepEqual(pageErrors, [], 'Uncaught browser errors or provider requests')
  console.log('PASS preview failure exposes retry without stale engineering results')
  console.log('PASS protection review browser gate')
} catch (error) {
  if (page) {
    const screenshot = `/tmp/relay-protection-review-${process.pid}.png`
    await page.screenshot({path: screenshot, fullPage: true}).catch(() => {})
    console.error(`Failure screenshot: ${screenshot}`)
  }
  throw error
} finally {
  await browser?.close().catch(() => {})
  server.kill('SIGTERM')
  await new Promise(resolve => {
    if (server.exitCode !== null || server.signalCode !== null || startError) return resolve()
    server.once('exit', resolve)
    const timer = setTimeout(() => {server.kill('SIGKILL'); resolve()}, 3000)
    timer.unref()
  })
}
