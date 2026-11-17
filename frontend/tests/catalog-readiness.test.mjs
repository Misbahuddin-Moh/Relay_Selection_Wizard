import test from 'node:test'
import assert from 'node:assert/strict'
import { catalogEvidenceLabel, catalogSourceUrl } from '../src/catalogReadiness.ts'

test('missing catalog evidence remains unknown and supplied states retain their uncertainty', () => {
  for (const value of [null, undefined, '', 0, false]) assert.equal(catalogEvidenceLabel(value), 'Unknown · not reviewed')
  assert.equal(catalogEvidenceLabel('hardware_unreviewed'), 'hardware unreviewed')
  assert.equal(catalogEvidenceLabel('package_available'), 'package available')
})

test('catalog references allow only external web source URLs', () => {
  assert.equal(catalogSourceUrl('https://selinc.com/products/487e/'), 'https://selinc.com/products/487e/')
  for (const value of ['javascript:alert(1)', 'file:///secret', '/local/path', null]) assert.equal(catalogSourceUrl(value), null)
})
