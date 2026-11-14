"""Independent portable-project and identity acceptance checks through HTTP."""
from copy import deepcopy
import json
from unittest import TestCase
from unittest.mock import patch
from uuid import UUID, uuid4

from fastapi.testclient import TestClient
from backend.main import app


class PortableProjectTests(TestCase):
    def setUp(self):
        self.client = TestClient(app)
        self.addCleanup(self.client.close)
        self.providers = []
        for target in ('backend.options.request_options', 'backend.main.extract_drawing',
                       'backend.main.extract_requirements'):
            mock = patch(target).start()
            self.providers.append(mock)
        self.addCleanup(patch.stopall)
        self.study = self.client.get('/api/study').json()['study']
        self.project = {
            'format': 'relay-wizard-project', 'schema_version': 1,
            'project_id': str(uuid4()), 'study': deepcopy(self.study), 'draft': None,
            'decisions': {},
        }

    def tearDown(self):
        for provider in self.providers:
            provider.assert_not_called()

    def validate(self, project=None, status=200):
        response = self.client.post('/api/projects/validate', json=self.project if project is None else project)
        self.assertEqual(response.status_code, status, response.text)
        return response.json()

    def preview(self, study):
        response = self.client.post('/api/protection-preview', json=study)
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()['options']

    def feeders(self, study):
        return {row['subject_id']: row for row in self.preview(study)[0]['device_requirements']
                if row['kind'] == 'feeder'}

    def test_reference_identity_is_deterministic(self):
        again = self.client.get('/api/study').json()['study']
        self.assertEqual(again['uid'], self.study['uid'])
        self.assertEqual([bay['uid'] for bay in again['bays']], [bay['uid'] for bay in self.study['bays']])
        for identity in [self.study['uid'], *(bay['uid'] for bay in self.study['bays'])]:
            self.assertEqual(str(UUID(identity)), identity)

    def test_legacy_raw_station_migrates_once_then_roundtrips_with_ids(self):
        legacy = deepcopy(self.study)
        legacy.pop('uid')
        for bay in legacy['bays']:
            bay.pop('uid')
        first = self.validate(legacy)
        self.assertTrue(first['warnings'])
        project = first['project']
        self.assertEqual(project['format'], 'relay-wizard-project')
        self.assertEqual(project['schema_version'], 1)
        self.assertEqual(str(UUID(project['project_id'])), project['project_id'])
        second = self.validate(project)
        self.assertEqual(second['project'], project)
        self.assertEqual(second['analysis'], first['analysis'])
        self.assertEqual(second['role_keys'], first['role_keys'])
        self.assertEqual(second['warnings'], [])

    def test_role_ids_survive_tag_rename_and_bay_reorder(self):
        before = self.feeders(self.study)
        modified = deepcopy(self.study)
        modified['bays'][0]['id'] = 'RENAMED-FEEDER-BREAKER'
        modified['bays'].reverse()
        after = self.feeders(modified)
        self.assertEqual(set(before), set(after))
        for uid in before:
            self.assertEqual(after[uid]['role_id'], before[uid]['role_id'])
        renamed_uid = self.study['bays'][0]['uid']
        self.assertEqual(after[renamed_uid]['role'], 'RENAMED-FEEDER-BREAKER')

    def test_deleted_and_recreated_display_tag_cannot_reuse_identity_or_role(self):
        before = self.feeders(self.study)
        modified = deepcopy(self.study)
        old = modified['bays'].pop(0)
        replacement = {**old, 'uid': str(uuid4())}
        modified['bays'].append(replacement)
        after = self.feeders(modified)
        self.assertNotIn(old['uid'], after)
        self.assertNotEqual(after[replacement['uid']]['role_id'], before[old['uid']]['role_id'])
        for bay in modified['bays'][:-1]:
            self.assertEqual(after[bay['uid']]['role_id'], before[bay['uid']]['role_id'])

    def test_option_and_role_keys_are_distinct_and_reproducible(self):
        options = self.preview(self.study)
        self.assertEqual([option['option_id'] for option in options],
                         ['dedicated:poi', 'shared:poi', 'combined:poi'])
        for option in options:
            role_ids = [row['role_id'] for row in option['device_requirements']]
            self.assertEqual(len(role_ids), len(set(role_ids)))
            for identity in role_ids:
                self.assertEqual(UUID(identity).version, 5)
        first = self.validate()
        second = self.validate(first['project'])
        self.assertEqual(first['role_keys'], second['role_keys'])
        self.assertEqual(len(first['role_keys']), len(set(first['role_keys'])))

    def test_relay_decisions_follow_role_after_rename_and_reorder(self):
        option = self.preview(self.study)[0]
        feeder = next(row for row in option['device_requirements'] if row['kind'] == 'feeder')
        key = f"{option['option_id']}/{feeder['role_id']}"
        note_key = f'{key}/GE T60'
        self.project['decisions'] = {
            'selection': option['option_id'], 'requirements': {key: {'neutral': '2', 'vt': '1'}},
            'ordering_notes': {note_key: {'dc': '125 VDC pending confirmation'}},
        }
        self.project['study']['bays'][0]['id'] = '52-RENAMED'
        self.project['study']['bays'].reverse()
        result = self.validate()
        self.assertEqual(result['project']['decisions']['requirements'][key], {'neutral': '2', 'vt': '1'})
        self.assertEqual(result['project']['decisions']['ordering_notes'][note_key]['dc'], '125 VDC pending confirmation')
        self.assertIn(key, result['role_keys'])

    def test_absent_equipment_decisions_must_be_explicitly_retired(self):
        option = self.preview(self.study)[0]
        feeder = next(row for row in option['device_requirements'] if row['kind'] == 'feeder')
        key = f"{option['option_id']}/{feeder['role_id']}"
        self.project['study']['bays'] = [bay for bay in self.study['bays'] if bay['uid'] != feeder['subject_id']]
        self.project['decisions'] = {'requirements': {key: {'neutral': '2', 'vt': ''}}}
        self.validate(status=422)
        self.project['decisions'] = {'retired_requirements': {key: {'neutral': '2', 'vt': ''}}}
        result = self.validate()
        self.assertNotIn(key, result['role_keys'])
        self.assertEqual(result['project']['decisions']['retired_requirements'][key]['neutral'], '2')

    def test_strict_envelope_rejects_missing_version_and_persistent_ids(self):
        for field in ('schema_version', 'project_id'):
            with self.subTest(field=field):
                project = deepcopy(self.project)
                project.pop(field)
                self.validate(project, status=422)
        for level in ('study', 'bay'):
            with self.subTest(level=level):
                project = deepcopy(self.project)
                if level == 'study':
                    project['study'].pop('uid')
                else:
                    project['study']['bays'][0].pop('uid')
                self.validate(project, status=422)

    def test_retired_ordering_notes_cannot_restore_an_unknown_model(self):
        option = self.preview(self.study)[0]
        role = option['device_requirements'][0]['role_id']
        key = f"{option['option_id']}/{role}"
        self.project['decisions'] = {'retired_ordering_notes': {f'{key}/UnknownModel': {'ct': '5A'}}}
        self.validate(status=422)
        self.project['decisions'] = {'retired_ordering_notes': {f'{key}/GE T60': {'ct': '5A'}}}
        result = self.validate()
        self.validate(result['project'])

    def test_malformed_bay_shapes_return_422_instead_of_500(self):
        for bays in (None, [1], [None], ['bad'], {'not': 'a list'}):
            with self.subTest(bays=bays):
                project = deepcopy(self.project)
                project['study']['bays'] = bays
                self.validate(project, status=422)

    def test_future_wrongly_typed_versions_and_unknown_fields_are_rejected(self):
        for version in (2, 0, True, '1', 1.0):
            with self.subTest(version=version):
                self.validate({**self.project, 'schema_version': version}, status=422)
        for field in ('analysis', 'approvals', 'api_key', 'provider_permission', 'source_text'):
            with self.subTest(field=field):
                self.validate({**self.project, field: 'untrusted'}, status=422)
        project = deepcopy(self.project)
        project['study']['engineering_approval'] = 'approved'
        self.validate(project, status=422)
        project = deepcopy(self.project)
        project['decisions']['api_key'] = 'fake-key'
        self.validate(project, status=422)

    def test_duplicate_or_malformed_equipment_ids_are_rejected(self):
        variants = []
        duplicate = deepcopy(self.project)
        duplicate['study']['bays'][1]['uid'] = duplicate['study']['bays'][0]['uid']
        variants.append(duplicate)
        same_as_study = deepcopy(self.project)
        same_as_study['study']['bays'][0]['uid'] = same_as_study['study']['uid']
        variants.append(same_as_study)
        malformed = deepcopy(self.project)
        malformed['project_id'] = 'display-name'
        variants.append(malformed)
        for project in variants:
            with self.subTest(project=project):
                self.validate(project, status=422)

    def test_incomplete_pending_draft_roundtrips_but_cannot_be_analyzed(self):
        self.project['draft'] = deepcopy(self.study)
        self.project['draft']['title'] = ''
        self.project['draft']['hv_kv'] = 0
        self.project['draft']['bays'][0]['id'] = ''
        result = self.validate()
        self.assertEqual(result['project']['draft'], self.project['draft'])
        response = self.client.post('/api/analyze', json=self.project['draft'])
        self.assertEqual(response.status_code, 422)
        active = self.client.post('/api/analyze', json=self.study).json()
        for field in ('assessment', 'counts', 'zones'):
            self.assertEqual(result['analysis'][field], active[field])

    def test_pending_draft_still_enforces_identity_count_and_provenance_integrity(self):
        for mutate in (
            lambda draft: draft.update(uid=str(uuid4())),
            lambda draft: draft['bays'][0].update(uid=draft['bays'][1]['uid']),
            lambda draft: draft.update(ct_inventory={**{key: None for key in (
                'lv_breaker_135', 'lv_breaker_246', 'hv_breaker_135', 'hv_breaker_246',
                'transformer_hv_phase', 'transformer_lv_phase', 'transformer_hv_neutral', 'transformer_lv_neutral')},
                'hv_breaker_135': -1}),
            lambda draft: draft.update(ct_provenance={'invented': {'value': None, 'origin': 'unknown', 'revision': 'r1'}}),
        ):
            project = deepcopy(self.project)
            project['draft'] = deepcopy(self.study)
            mutate(project['draft'])
            self.validate(project, status=422)

    def test_inventory_unknown_zero_and_origins_survive_portable_roundtrip(self):
        self.project['study']['ct_inventory'] = {
            'lv_breaker_135': None, 'lv_breaker_246': 0, 'hv_breaker_135': 2, 'hv_breaker_246': 2,
            'transformer_hv_phase': 3, 'transformer_lv_phase': 3,
            'transformer_hv_neutral': None, 'transformer_lv_neutral': 0,
        }
        self.project['study']['ct_provenance'] = {
            'lv_breaker_135': {'value': None, 'origin': 'unknown', 'revision': 'r1'},
            'lv_breaker_246': {'value': 0, 'origin': 'document', 'revision': 'r2'},
            'hv_breaker_135': {'value': 2, 'origin': 'assumed', 'revision': 'r3'},
        }
        first = self.validate()
        second = self.validate(first['project'])
        self.assertEqual(first['project'], second['project'])
        self.assertEqual(second['project']['study']['ct_inventory'], self.project['study']['ct_inventory'])
        self.assertEqual(second['project']['study']['ct_provenance'], self.project['study']['ct_provenance'])
        self.assertTrue(all(fact['review_state'] == 'unreviewed' for fact in second['analysis']['assessment']['facts']))

    def test_digital_edits_retained_only_for_matching_equipment_order_and_line_scope(self):
        project = self.validate()['project']
        signal = {'id': 900, 'name': 'Synthetic trip', 'source': 'T-P', 'destination': '86T',
                  'method': 'hardwired', 'di': 0, 'do': 1, 'coil': True, 'included': True,
                  'reference': 'Synthetic fixture', 'condition': 'Reviewed example only'}
        settings = {'variant': 'LOCK', 'spare': {'di': 20, 'do': 20, 'basis': 'used'},
                    'edits': {'LOCK': [signal]}}
        project['decisions']['digital_settings'] = {'dedicated:poi': settings}
        retained = self.validate(project)
        self.assertEqual(retained['project']['decisions']['digital_settings']['dedicated:poi']['edits']['LOCK'], [signal])
        self.assertEqual(retained['warnings'], [])
        for change in ('order', 'line'):
            modified = deepcopy(project)
            if change == 'order':
                modified['study']['bays'].reverse()
            else:
                modified['study']['include_poi_line'] = True
            result = self.validate(modified)
            self.assertEqual(result['project']['decisions']['digital_settings']['dedicated:poi']['edits'], {})
            self.assertEqual(result['project']['decisions']['digital_settings']['dedicated:poi']['spare'], settings['spare'])
            self.assertTrue(any('cleared' in warning for warning in result['warnings']))

    def test_unknown_role_selection_model_and_invalid_decision_values_rejected(self):
        role = self.validate()['role_keys'][0]
        for decisions in (
            {'requirements': {'dedicated:poi/' + str(uuid4()): {'neutral': '', 'vt': ''}}},
            {'selection': 'invented:poi'},
            {'ordering_notes': {f'{role}/invented-relay': {'dc': '125'}}},
            {'requirements': {role: {'neutral': '-1', 'vt': ''}}},
            {'requirements': {role: {'neutral': '1.5', 'vt': ''}}},
            {'requirements': {role: {'neutral': 2, 'vt': ''}}},
        ):
            with self.subTest(decisions=decisions):
                self.validate({**self.project, 'decisions': decisions}, status=422)

    def test_corrupt_nonobject_and_oversize_files_fail_cleanly(self):
        for raw in (b'{broken', b'null', b'[]', b'"hello"', b'\xff', b'{"schema_version": 99}'):
            with self.subTest(raw=raw):
                response = self.client.post('/api/projects/validate', content=raw)
                self.assertEqual(response.status_code, 422, response.text)
        raw = json.dumps(self.project).encode()
        limit = 2 * 1024 * 1024
        exact = raw + b' ' * (limit - len(raw))
        self.assertEqual(self.client.post('/api/projects/validate', content=exact).status_code, 200)
        self.assertEqual(self.client.post('/api/projects/validate', content=exact + b' ').status_code, 413)
