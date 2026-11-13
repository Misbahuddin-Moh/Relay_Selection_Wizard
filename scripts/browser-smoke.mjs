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
  const server = createServer()
  server.once('error', reject)
  server.listen(0, '127.0.0.1', () => {
    const selected = server.address().port
    server.close(error => error ? reject(error) : resolve(selected))
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
server.stdout.on('data', chunk => { serverOutput = (serverOutput + chunk).slice(-10000) })
server.stderr.on('data', chunk => { serverOutput = (serverOutput + chunk).slice(-10000) })
let startError
server.once('error', error => { startError = error })
let browser
let page
const pageErrors = []
const waitVisible = async locator => locator.waitFor({ state: 'visible', timeout: 15000 })
const assertNoOverflow = async () => {
  const dimensions = await page.evaluate(() => ({
    viewport: document.documentElement.clientWidth,
    document: document.documentElement.scrollWidth,
    body: document.body.scrollWidth,
  }))
  assert.ok(Math.max(dimensions.document, dimensions.body) <= dimensions.viewport + 1,
    `Horizontal overflow: ${JSON.stringify(dimensions)}`)
}

try {
  let healthy = false
  for (let attempt = 0; attempt < 100; attempt++) {
    if (startError) throw startError
    if (server.exitCode !== null) throw new Error(`Server exited: ${serverOutput}`)
    try {
      const response = await fetch(`${base}/api/health`)
      if (response.ok) { healthy = true; break }
    } catch {}
    await new Promise(resolve => setTimeout(resolve, 100))
  }
  assert.ok(healthy, `Server never became healthy: ${serverOutput}`)
  browser = await chromium.launch({ headless: true,
    ...(process.env.CHROMIUM_EXECUTABLE_PATH ? { executablePath: process.env.CHROMIUM_EXECUTABLE_PATH } : {}) })
  page = await browser.newPage({ viewport: { width: 1440, height: 1000 } })
  page.on('pageerror', error => pageErrors.push(error.message))
  await page.goto(base)
  await page.getByRole('button', { name: /Build from a concept/ }).click()
  await page.getByLabel('Study name', { exact: true }).fill('Browser release fixture')
  await page.getByLabel('HV (kV)', { exact: true }).fill('345')
  await page.getByLabel('Collector (kV)', { exact: true }).fill('34.5')
  await page.getByRole('button', { name: 'Add bay', exact: true }).click()
  await page.getByRole('button', { name: 'Add bay', exact: true }).click()
  await page.getByRole('button', { name: 'Review topology', exact: true }).click()
  assert.equal(await page.locator('.ct-inventory label').filter({ hasText: /· assumed/ }).count(), 8)
  await page.getByRole('button', { name: 'Confirm and analyze', exact: true }).click()
  const evidence = page.getByRole('region', { name: 'Study evidence and support' })
  await waitVisible(evidence)
  await evidence.getByText('CT fact origins and review state', { exact: true }).click()
  assert.equal(await evidence.locator('li').filter({ hasText: /· assumed · unreviewed/ }).count(), 8)
  await waitVisible(page.getByRole('heading', { name: 'Choose a protection scheme', exact: true }))
  assert.ok(await page.getByRole('button', { name: 'AI alternatives disabled in alpha', exact: true }).isDisabled())
  console.log('PASS concept creation; eight assumed/unreviewed facts; provider button disabled')

  await page.getByRole('radio').first().check()
  await page.getByRole('button', { name: 'Review device requirements', exact: true }).click()
  const io = page.getByRole('region', { name: 'Digital I/O budget', exact: true })
  await waitVisible(io)
  assert.match(await io.innerText(), /partial interface budget/)
  console.log('PASS reference scheme displays explicitly partial I/O budget')
  await page.setViewportSize({ width: 390, height: 844 })
  await assertNoOverflow()
  console.log('PASS narrow viewport relay-signals screen has no document overflow')
  await page.setViewportSize({ width: 1440, height: 1000 })

  await page.getByRole('button', { name: /^1\s*Station$/ }).click()
  await page.getByRole('button', { name: 'Create what-if scenario', exact: true }).click()
  await waitVisible(evidence.getByText(/Inputs changed\. Analyze this draft/))
  assert.equal(await evidence.locator('li').count(), 0, 'Previous assessment facts remain in dirty scenario DOM')
  assert.equal(await evidence.getByText('CT fact origins and review state', { exact: true }).count(), 0)
  console.log('PASS dirty scenario removes previous assessment facts')
  await page.getByRole('button', { name: 'Add bay', exact: true }).click()
  await page.getByRole('button', { name: 'Analyze scenario', exact: true }).click()
  await waitVisible(evidence.getByText(/Reference hardware screening covers three collector breakers only/))
  await waitVisible(page.getByRole('heading', { name: 'Choose a protection scheme', exact: true }))
  await page.getByRole('radio').first().check()
  await page.getByRole('button', { name: 'Review device requirements', exact: true }).click()
  await waitVisible(page.getByText('Reference hardware screening is unavailable for this layout. Modeled functions and measurement quantities remain visible for draft review.', { exact: true }))
  assert.ok(!(await io.isVisible()), 'Reference I/O still visible for four-breaker layout')
  await page.getByRole('button', { name: 'Screen relay models', exact: true }).click()
  await waitVisible(page.getByRole('heading', { name: 'Screen relay models', exact: true }))
  for (const vendor of ['GE', 'SEL']) {
    assert.equal(await page.getByRole('region', { name: `${vendor} devices`, exact: true }).locator('article').count(), 0)
  }
  await page.getByText('High-impedance bus alternatives', { exact: true }).click()
  assert.equal(await page.locator('details').filter({ has: page.getByText('High-impedance bus alternatives', { exact: true }) }).locator('li').count(), 0)
  console.log('PASS fourth-breaker layout suppresses digital examples and all hardware alternatives')
  assert.deepEqual(pageErrors, [], 'Browser page errors')
  console.log('PASS browser release smoke')
} catch (error) {
  if (page) {
    const screenshot = `/tmp/relay-browser-smoke-${process.pid}.png`
    await page.screenshot({ path: screenshot, fullPage: true }).catch(() => {})
    console.error(`Failure screenshot: ${screenshot}`)
  }
  throw error
} finally {
  await browser?.close().catch(() => {})
  server.kill('SIGTERM')
  await new Promise(resolve => {
    if (server.exitCode !== null || server.signalCode !== null || startError) return resolve()
    const timer = setTimeout(() => { server.kill('SIGKILL'); resolve() }, 5000)
    server.once('exit', () => { clearTimeout(timer); resolve() })
  })
}
