import test from 'node:test'
import assert from 'node:assert/strict'
import { emptyChoices, projectFile, reconcileChoices } from '../src/projectState.ts'
const study = () => ({uid: 'station', title: 'Station', hv_boundary: 'poi', include_poi_line: false, bays: [{uid: 'bay-a', id: 'CB-A'}, {uid: 'bay-b', id: 'CB-B'}]})
test('rename keeps choices; reorder clears positional signal edits only', () => {
  const choices = emptyChoices()
  choices.requirements = {'dedicated:poi/role-a': {neutral: '2', vt: '1'}}
  choices.digital_bay_order = ['bay-a', 'bay-b']
  choices.digital_settings = {'dedicated:poi': {variant: 'DIRECT', spare: {di:20, do:20, basis:'used'}, edits: {DIRECT: [{id:1}]}, output_classes: {DIRECT: {'1': ['fast']}}}}
  const renamed = study(); renamed.bays[0].id = 'Renamed breaker'
  const stable = reconcileChoices(choices, renamed, new Set(['dedicated:poi/role-a']))
  assert.deepEqual(stable.requirements, choices.requirements)
  assert.deepEqual(stable.digital_settings, choices.digital_settings)
  const reversed = {...renamed, bays: [...renamed.bays].reverse()}
  const changed = reconcileChoices(stable, reversed, new Set(['dedicated:poi/role-a']))
  assert.deepEqual(changed.digital_settings['dedicated:poi'].edits, {})
  assert.deepEqual(changed.digital_settings['dedicated:poi'].output_classes, {})
  assert.equal(changed.digital_settings['dedicated:poi'].variant, 'DIRECT')
  assert.equal(changed.digital_settings['dedicated:poi'].spare.di, 20)
  assert.match(changed.notices[0], /Positional/)
})
test('removed role inputs and ordering notes are retired and restored only by identity', () => {
  const choices = emptyChoices(); choices.requirements = {'dedicated:poi/old-role': {neutral:'2',vt:'0'}}
  choices.ordering_notes = {'dedicated:poi/old-role/GE T60': {ct:'5A'}}
  const retired = reconcileChoices(choices, study(), new Set(['dedicated:poi/new-role']))
  assert.deepEqual(retired.requirements, {}); assert.deepEqual(retired.ordering_notes, {})
  assert.equal(retired.retired_requirements['dedicated:poi/old-role'].neutral, '2')
  const restored = reconcileChoices(retired, study(), new Set(['dedicated:poi/old-role']))
  assert.equal(restored.requirements['dedicated:poi/old-role'].neutral, '2')
  assert.equal(restored.ordering_notes['dedicated:poi/old-role/GE T60'].ct, '5A')
  assert.deepEqual(restored.retired_requirements, {})
})
test('remote verification is invalidated and unavailable selection cleared', () => {
  const choices = emptyChoices(); choices.selection='dedicated:bushing'
  choices.line_checks = {remoteCt:'present',remoteModel:'peer',compatibleModel:'local',channel:true,dtt:'verified'}
  const result = reconcileChoices(choices, study(), new Set())
  assert.equal(result.selection, ''); assert.equal(result.line_checks.remoteModel, 'peer')
  assert.equal(result.line_checks.compatibleModel, ''); assert.equal(result.line_checks.channel, false); assert.equal(result.line_checks.dtt, 'pending')
})
test('portable file wrapper is an explicit input-only allowlist', () => {
  const file = projectFile('project', study(), null, emptyChoices())
  assert.deepEqual(Object.keys(file).sort(), ['decisions','draft','format','project_id','schema_version','study'])
  assert.ok(!('analysis' in file)); assert.ok(!('engineering_approval' in file)); assert.ok(!('api_key' in file))
})
