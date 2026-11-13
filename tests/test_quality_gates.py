"""Independent HTTP acceptance checks for the foundation alpha boundaries."""
from copy import deepcopy
from unittest import TestCase
from unittest.mock import patch

from fastapi.testclient import TestClient

from backend.main import app


class FoundationQualityGates(TestCase):
    def setUp(self):
        self.client = TestClient(app)
        self.addCleanup(self.client.close)
        response = self.client.get('/api/study')
        self.assertEqual(response.status_code, 200)
        self.study = response.json()['study']
        self.study['ct_inventory'] = {
            'lv_breaker_135': 2, 'lv_breaker_246': 2,
            'hv_breaker_135': 2, 'hv_breaker_246': 2,
            'transformer_hv_phase': 3, 'transformer_lv_phase': 3,
            'transformer_hv_neutral': 2, 'transformer_lv_neutral': 2,
        }

    def assessment(self, study=None):
        response = self.client.post('/api/analyze', json=study or self.study)
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()['assessment']

    def test_public_provider_routes_are_blocked_before_body_validation(self):
        with patch.dict('os.environ', {'ANTHROPIC_API_KEY': 'fake-key', 'OPENAI_API_KEY': 'fake-key'}), \
                patch('backend.main.generate_options') as options, \
                patch('backend.main.extract_drawing') as drawing, \
                patch('backend.main.extract_requirements') as requirements:
            for route in ('/api/protection-options', '/api/drawing/extract', '/api/requirements/extract'):
                for suffix in ('', '/'):
                    for method in ('POST', 'GET', 'OPTIONS'):
                        with self.subTest(route=route, suffix=suffix, method=method):
                            response = self.client.request(method, route + suffix, content=b'invalid',
                                                           headers={'content-type': 'application/json'})
                            self.assertEqual(response.status_code, 403, response.text)
            options.assert_not_called()
            drawing.assert_not_called()
            requirements.assert_not_called()

    def test_provider_status_does_not_become_enabled_when_keys_exist(self):
        with patch.dict('os.environ', {'ANTHROPIC_API_KEY': 'fake-key', 'OPENAI_API_KEY': 'fake-key'}):
            for route in ('/api/drawing/status', '/api/requirements/status'):
                with self.subTest(route=route):
                    self.assertIs(self.client.get(route).json()['configured'], False)
            self.assertEqual(self.client.get('/api/health').json()['provider_operations'], 'disabled')

    def test_matching_provenance_is_retained_without_granting_review(self):
        key = 'hv_breaker_135'
        for origin in ('assumed', 'user', 'document', 'unknown'):
            with self.subTest(origin=origin):
                self.study['ct_provenance'] = {key: {'value': 2, 'origin': origin, 'revision': 'fixture-r1'}}
                fact = next(fact for fact in self.assessment()['facts'] if fact['subject'] == key)
                self.assertEqual(fact['origin'], origin)
                self.assertEqual(fact['revision'], 'fixture-r1')
                self.assertEqual(fact['review_state'], 'unreviewed')

    def test_old_provenance_cannot_describe_an_edited_count(self):
        key = 'hv_breaker_135'
        self.study['ct_provenance'] = {key: {'value': 2, 'origin': 'document', 'revision': 'fixture-r1'}}
        self.study['ct_inventory'][key] = 0
        fact = next(fact for fact in self.assessment()['facts'] if fact['subject'] == key)
        self.assertEqual(fact['value'], 0)
        self.assertEqual(fact['origin'], 'unknown')
        self.assertIsNone(fact['revision'])
        self.assertEqual(fact['review_state'], 'unreviewed')

    def test_legacy_counts_have_unknown_unreviewed_origin(self):
        self.study.pop('ct_provenance', None)
        facts = self.assessment()['facts']
        self.assertEqual(len(facts), 8)
        self.assertTrue(all(fact['origin'] == 'unknown' for fact in facts))
        self.assertTrue(all(fact['review_state'] == 'unreviewed' for fact in facts))

    def test_null_zero_positive_counts_remain_distinct(self):
        key = 'hv_breaker_135'
        fingerprints = set()
        for value in (None, 0, 2):
            with self.subTest(value=value):
                self.study['ct_inventory'][key] = value
                assessment = self.assessment()
                fact = next(fact for fact in assessment['facts'] if fact['subject'] == key)
                self.assertEqual(fact['value'], value)
                fingerprints.add(assessment['input_fingerprint'])
        self.assertEqual(len(fingerprints), 3)

    def test_fingerprint_is_repeatable_and_ignores_json_key_order(self):
        baseline = self.assessment()['input_fingerprint']
        self.assertEqual(self.assessment()['input_fingerprint'], baseline)
        reversed_study = dict(reversed(list(self.study.items())))
        reversed_study['ct_inventory'] = dict(reversed(list(self.study['ct_inventory'].items())))
        self.assertEqual(self.assessment(reversed_study)['input_fingerprint'], baseline)
        self.study['ct_inventory']['transformer_hv_phase'] = 4
        self.assertNotEqual(self.assessment()['input_fingerprint'], baseline)

    def test_reference_scope_does_not_grant_engineering_or_code_approval(self):
        assessment = self.assessment()
        self.assertIs(assessment['scope']['reference_hardware_supported'], True)
        self.assertEqual(assessment['scope']['reasons'], [])
        self.assertEqual(assessment['budget_completeness'], 'partial')
        self.assertEqual(assessment['code_status'], 'not_generated')
        self.assertEqual(assessment['engineering_approval'], 'unavailable')
        self.assertEqual(assessment['independence_status'], 'unverified')

    def test_outside_reference_breaker_counts_block_hardware_through_api(self):
        for count in (1, 2, 4, 12):
            with self.subTest(count=count):
                study = deepcopy(self.study)
                study['bays'] = [{'id': f'CB-{i}', 'branches': [f'F-{i}'], 'ct': 'present'}
                                 for i in range(count)]
                assessment = self.assessment(study)
                self.assertIs(assessment['scope']['reference_hardware_supported'], False)
                self.assertIn('COLLECTOR_BREAKER_COUNT_OUTSIDE_REFERENCE',
                              [reason['code'] for reason in assessment['scope']['reasons']])
                self.assert_no_hardware_candidates(study)

    def test_measured_auxiliary_is_draft_only_through_api(self):
        self.study['auxiliary'] = 'included'
        assessment = self.assessment()
        self.assertIs(assessment['scope']['reference_hardware_supported'], False)
        self.assertIn('MEASURED_AUXILIARY_POLICY_UNREVIEWED',
                      [reason['code'] for reason in assessment['scope']['reasons']])
        self.assert_no_hardware_candidates(self.study)

    def assert_no_hardware_candidates(self, study):
        with patch('backend.options.request_options') as request:
            response = self.client.post('/api/protection-preview', json=study)
        request.assert_not_called()
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()['high_impedance_bus'], [])
        options = response.json()['options']
        self.assertTrue(options, 'Retain preliminary alternatives rather than dropping unsupported work.')
        for option in options:
            self.assertTrue(option['device_requirements'])
            for row in option['device_requirements']:
                self.assertEqual(row['candidates'], [], row)
                self.assertEqual(row['support'], 'unsupported')

    def test_unknown_provenance_keys_and_fields_are_rejected(self):
        invalid = (
            {'invented_ct': {'value': 2, 'origin': 'user', 'revision': 'r1'}},
            {'hv_breaker_135': {'value': 2, 'origin': 'user', 'revision': 'r1', 'approved': True}},
            {'hv_breaker_135': {'value': 2, 'origin': 'confirmed', 'revision': 'r1'}},
        )
        for provenance in invalid:
            with self.subTest(provenance=provenance):
                study = {**self.study, 'ct_provenance': provenance}
                for route in ('/api/analyze', '/api/protection-preview'):
                    self.assertEqual(self.client.post(route, json=study).status_code, 422)

    def test_invalid_counts_are_rejected_at_http_boundary(self):
        for value in (-1, 1.5, True, '2'):
            with self.subTest(value=value):
                study = deepcopy(self.study)
                study['ct_inventory']['hv_breaker_135'] = value
                self.assertEqual(self.client.post('/api/analyze', json=study).status_code, 422)
