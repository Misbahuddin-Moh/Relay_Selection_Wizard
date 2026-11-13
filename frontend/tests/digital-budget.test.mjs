import test from 'node:test'
import assert from 'node:assert/strict'
import { digitalBudget } from '../src/digitalBudget.ts'
const signal = (patch = {}) => ({included: true, method: 'hardwired', source: 'T-P', destination: 'breaker', di: 1, do: 1, coil: true, ...patch})
test('ample capacity and resolved routes cannot establish completeness', () => {
  const result = digitalBudget([signal()], 'T-P', { di: 20, do: 20, basis: 'used' })
  assert.equal(result.completeness, 'partial')
  assert.equal(result.open, 0)
  assert.equal(result.coilRequired, 2)
})
test('endpoints consume only their own hardwired points', () => {
  const signals = [signal(), signal({ source: 'external', destination: 'T-P', do: 0, coil: false }), signal({ method: 'GOOSE' })]
  const result = digitalBudget(signals, 'T-P', {di: 0, do: 0, basis: 'used'})
  assert.equal(result.di, 1); assert.equal(result.coil, 1); assert.equal(result.other, 0)
  assert.equal(digitalBudget(signals, 'unrelated', {di: 0, do: 0, basis: 'used'}).doRequired, 0)
})
test('spare bases diverge at meaningful capacity boundary', () => {
  const signals = [signal({do: 4})]
  assert.equal(digitalBudget(signals, 'T-P', {di: 20, do: 20, basis: 'used'}).doRequired, 5)
  assert.equal(digitalBudget(signals, 'T-P', {di: 40, do: 40, basis: 'installed'}).doRequired, 7)
})
test('unresolved routes remain open and zero physical counts stay partial', () => {
  const result = digitalBudget([signal({ method: 'hardwired or communicated' })], 'T-P', {di: 99, do: 99, basis: 'installed'})
  assert.equal(result.open, 1); assert.equal(result.doRequired, 0); assert.equal(result.completeness, 'partial')
})
