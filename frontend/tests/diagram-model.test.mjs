import test from 'node:test'
import assert from 'node:assert/strict'
import { collectorCtStates, collectorGeometry as g } from '../src/diagramModel.ts'
test('feeder area starts on bus side and differential ends beyond breaker, preserving overlap', () => {
  assert.ok(g.bus < g.busSideCt)
  assert.ok(g.busSideCt < g.breakerTop)
  assert.ok(g.breakerBottom < g.circuitSideCt)
  assert.ok(g.circuitSideCt < g.feederBottom)
  assert.ok(g.circuitEnd < g.feederBottom)
})
test('collector CT locations retain separate absent and unknown inventories', () => {
  assert.deepEqual(collectorCtStates({ct_inventory: {lv_breaker_135: 0, lv_breaker_246: null}}, 'present'), {busSide:'absent', circuitSide:'unknown'})
  assert.deepEqual(collectorCtStates({}, 'present'), {busSide:'unknown', circuitSide:'present'})
})
