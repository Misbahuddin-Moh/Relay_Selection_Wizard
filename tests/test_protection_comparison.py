"""Independent reference-station comparison acceptance cases.

Literal topology expectations do not establish approved engineering designs.
"""
import json
from copy import deepcopy
from unittest import TestCase
from unittest.mock import patch
from uuid import uuid4

from fastapi.testclient import TestClient
from backend.main import app


COMMON_GAPS = {
    'CT_SUITABILITY_UNREVIEWED', 'CT_CORE_INDEPENDENCE_UNVERIFIED',
    'TRIP_CLEARING_UNVERIFIED', 'BREAKER_FAILURE_UNRESOLVED',
    'LOCKOUT_WIRING_UNREVIEWED', 'OC_COORDINATION_UNRESOLVED',
    'REF_GROUNDING_UNRESOLVED', 'MANUFACTURER_CONFIGURATION_UNVERIFIED',
    'PARTIAL_SIGNAL_BUDGET',
}


class ProtectionComparisonAcceptanceTests(TestCase):
    def setUp(self):
        self.client = TestClient(app)
        self.addCleanup(self.client.close)
        self.study = self.client.get('/api/study').json()['study']
        self.study['auxiliary'] = 'excluded'
        self.study['ct_inventory'] = {
            'lv_breaker_135': 2, 'lv_breaker_246': 2,
            'hv_breaker_135': 2, 'hv_breaker_246': 2,
            'transformer_hv_phase': 3, 'transformer_lv_phase': 3,
            'transformer_hv_neutral': 2, 'transformer_lv_neutral': 2,
        }
        self.provider_patch = patch('backend.options.request_options', side_effect=AssertionError('Unexpected provider call'))
        self.provider = self.provider_patch.start()
        self.addCleanup(self.provider_patch.stop)

    def tearDown(self):
        self.provider.assert_not_called()

    def options(self, study=None):
        response = self.client.post('/api/protection-preview', json=study or self.study)
        self.assertEqual(response.status_code, 200, response.text[:1000])
        return {item['scheme']: item for item in response.json()['options']}

    @staticmethod
    def zones(option):
        return {zone['id']: zone for zone in option['review']['zones']}

    def test_three_approaches_distinguish_zone_functions_and_relay_hosting(self):
        options = self.options()
        self.assertEqual(set(options), {'dedicated', 'shared', 'combined'})
        for scheme in ('dedicated', 'shared', 'combined'):
            review = options[scheme]['review']
            zones = self.zones(options[scheme])
            self.assertEqual(zones['transformer_primary']['function'], '87TB' if scheme == 'combined' else '87T')
            self.assertEqual(zones['transformer_secondary']['function'], '87T')
            self.assertNotEqual(zones['transformer_primary']['relay_roles'], zones['transformer_secondary']['relay_roles'])
            if scheme == 'combined':
                self.assertNotIn('bus', zones)
            else:
                self.assertEqual(zones['bus']['function'], '87B')
                if scheme == 'shared':
                    self.assertEqual(zones['transformer_primary']['relay_roles'], zones['bus']['relay_roles'])
                else:
                    self.assertNotEqual(zones['transformer_primary']['relay_roles'], zones['bus']['relay_roles'])
            expected = {'transformer_primary', 'transformer_secondary', *('feeder/' + bay['uid'] for bay in self.study['bays'])}
            if scheme != 'combined':
                expected.add('bus')
            self.assertEqual(set(zones), expected)
            self.assertTrue(review['version'])

    def test_positive_counts_never_confirm_independence_or_procurement(self):
        for option in self.options().values():
            review = option['review']
            self.assertEqual(review['primary_measurements'], 'present')
            self.assertEqual(review['secondary_measurements'], 'unknown')
            self.assertEqual(review['readiness'], 'conditional')
            self.assertFalse(review['procurement_ready'])
            self.assertTrue(COMMON_GAPS <= {item['code'] for item in review['findings']})
            self.assertTrue(all(item['state'] == 'unconfirmed' for item in review['assumptions']))
            self.assertTrue(all(zone['clearing_state'] == 'unverified' for zone in review['zones']))

    def test_absent_transformer_lv_blocks_secondary_even_when_combined_primary_does_not_need_it(self):
        self.study['ct_inventory']['transformer_lv_phase'] = 0
        options = self.options()
        self.assertEqual(options['combined']['review']['primary_measurements'], 'present')
        for scheme, option in options.items():
            review = option['review']
            if scheme != 'combined':
                self.assertEqual(review['primary_measurements'], 'absent')
            self.assertEqual(review['secondary_measurements'], 'absent')
            self.assertEqual(review['readiness'], 'blocked')
            self.assertFalse(review['procurement_ready'])

    def test_unknown_and_absent_hv_measurements_are_not_interchangeable(self):
        for count, state, readiness in ((None, 'unknown', 'conditional'), (0, 'absent', 'blocked')):
            self.study['ct_inventory']['hv_breaker_135'] = count
            for option in self.options().values():
                with self.subTest(count=count, scheme=option['scheme']):
                    self.assertEqual(option['review']['primary_measurements'], state)
                    self.assertEqual(option['review']['readiness'], readiness)

    def test_primary_phase_envelopes_preserve_shared_input_reuse_cases(self):
        expected = {'dedicated': (2, 2), 'shared': (5, 6), 'combined': (4, 4)}
        for scheme, option in self.options().items():
            primary = option['review']['roles'][0]
            self.assertEqual((primary['phase_banks_min'], primary['phase_banks_max']), expected[scheme])
            for role in option['review']['roles']:
                self.assertTrue(role['role_id'])
                self.assertGreaterEqual(role['phase_banks_max'], role['phase_banks_min'])

    def test_local_feeder_zones_follow_breaker_identity_and_do_not_multiply_shared_branches(self):
        expected = {'feeder/' + bay['uid']: bay['id'] for bay in self.study['bays']}
        for option in self.options().values():
            zones = self.zones(option)
            actual = {key: zone for key, zone in zones.items() if key.startswith('feeder/')}
            self.assertEqual(set(actual), set(expected))
            for identity, breaker in expected.items():
                self.assertEqual(actual[identity]['trip_targets'], [breaker])
        # A display rename preserves identity while the clearing label changes.
        renamed = deepcopy(self.study)
        renamed['bays'][0]['id'] = 'RENAMED-CB'
        for option in self.options(renamed).values():
            self.assertEqual(self.zones(option)['feeder/' + renamed['bays'][0]['uid']]['trip_targets'], ['RENAMED-CB'])

    def test_differential_trip_targets_are_provisional_all_source_targets(self):
        expected = ['HV breaker', 'CB-01', 'CB-02', 'CB-03']
        for option in self.options().values():
            for zone in option['review']['zones']:
                if zone['id'] in ('transformer_primary', 'transformer_secondary', 'bus'):
                    self.assertEqual(zone['trip_targets'], expected)
                    self.assertEqual(zone['clearing_state'], 'unverified')
            assumptions = ' '.join(row['detail'].lower() for row in option['review']['assumptions'])
            self.assertIn('main breaker', assumptions)
            self.assertIn('COLLECTOR_BACKFEED', {row['code'] for row in option['review']['assumptions']})

    def test_optional_line_retains_remote_and_channel_gaps_without_invented_remote_trip(self):
        before = self.options()
        for option in before.values():
            self.assertNotIn('line', self.zones(option))
            self.assertNotIn('LINE_REMOTE_UNRESOLVED', {row['code'] for row in option['review']['findings']})
        self.study['include_poi_line'] = True
        for option in self.options().values():
            review = option['review']
            line = self.zones(option)['line']
            self.assertEqual(line['function'], '87L')
            self.assertEqual(line['clearing_state'], 'unverified')
            self.assertIn('LINE_REMOTE_UNRESOLVED', {row['code'] for row in review['findings']})
            role = next(row for row in review['roles'] if row['kind'] == 'line')
            self.assertEqual((role['phase_banks_min'], role['phase_banks_max']), (1, 1))
            self.assertFalse(review['procurement_ready'])

    def test_alternate_hv_boundary_changes_primary_span_not_secondary_assignment(self):
        self.study['hv_boundary'] = 'bushing'
        for option in self.options().values():
            primary = self.zones(option)['transformer_primary']
            self.assertTrue(any('HV bushing' in boundary['label'] for boundary in primary['boundaries']))
            self.assertFalse(any('HV breaker POI-side' in boundary['label'] for boundary in primary['boundaries']))
            self.assertEqual(option['review']['secondary_measurements'], 'unknown')

    def test_findings_explain_the_evidence_needed_without_claiming_project_approval(self):
        for option in self.options().values():
            for finding in option['review']['findings']:
                self.assertIn(finding['severity'], ('blocker', 'open'))
                self.assertTrue(finding['title'])
                self.assertTrue(finding['detail'])
                self.assertTrue(finding['required_evidence'])
                self.assertTrue(finding['basis'])
                for source in finding['sources']:
                    self.assertTrue(source['id'])
                    self.assertTrue(source['locator'])
                    self.assertTrue(source['url'].startswith('https://'))

    def test_unsupported_reference_cases_cannot_be_presented_as_ready(self):
        variants = []
        measured_auxiliary = deepcopy(self.study)
        measured_auxiliary['auxiliary'] = 'included'
        variants.append(measured_auxiliary)
        four_breakers = deepcopy(self.study)
        four_breakers['bays'].append({'uid': str(uuid4()), 'id': 'CB-04', 'branches': ['F-04'], 'ct': 'present'})
        variants.append(four_breakers)
        for study in variants:
            for option in self.options(study).values():
                review = option['review']
                self.assertEqual(review['readiness'], 'outside_scope')
                self.assertIn('OUTSIDE_REFERENCE_SCOPE', {row['code'] for row in review['findings']})
                self.assertFalse(review['procurement_ready'])
                self.assertTrue(all(not role['candidates'] for role in option['device_requirements']))

    def test_preview_recomputes_review_after_input_revision(self):
        before = self.options()
        self.study['ct_inventory']['lv_breaker_246'] = 0
        after = self.options()
        for scheme in before:
            self.assertEqual(before[scheme]['review']['primary_measurements'], 'present')
            self.assertEqual(after[scheme]['review']['primary_measurements'], 'absent' if scheme == 'combined' else 'present')
            self.assertEqual(after[scheme]['review']['readiness'], 'blocked')
            if scheme != 'combined':
                self.assertEqual(self.zones(after[scheme])['bus']['measurement_status'], 'absent')
            self.assertNotEqual(before[scheme]['assessment']['input_fingerprint'], after[scheme]['assessment']['input_fingerprint'])

    def engineering_io(self, study=None, scheme='dedicated', requirements=None):
        request = {'study': study or self.study, 'scheme': scheme,
                   'settings': {'variant': 'LOCK', 'spare': {'di': 20, 'do': 20, 'basis': 'used'}}}
        if requirements is not None:
            request['analog_requirements'] = requirements
        response = self.client.post('/api/engineering/io', json=request)
        self.assertEqual(response.status_code, 200, response.text[:1000])
        return response.json()

    def test_reversed_or_equal_voltage_levels_are_outside_reference_not_hardware_candidates(self):
        for hv, mv in ((34.5, 345), (34.5, 34.5)):
            study = {**self.study, 'hv_kv': hv, 'mv_kv': mv}
            for option in self.options(study).values():
                self.assertEqual(option['review']['readiness'], 'outside_scope')
                self.assertIn('VOLTAGE_ORDER_OUTSIDE_REFERENCE', {row['code'] for row in option['assessment']['scope']['reasons']})
                self.assertTrue(all(not row['candidates'] for row in option['device_requirements']))
            result = self.engineering_io(study)
            self.assertEqual(result['status'], 'unsupported')
            self.assertEqual(result['analog_assessments'], [])
            self.assertEqual(result['card_examples'], [])

    def test_voltage_inputs_reject_boolean_string_zero_and_negative_values(self):
        for field in ('hv_kv', 'mv_kv'):
            for value in (True, False, '345', 0, -1):
                study = {**self.study, field: value}
                for route in ('/api/analyze', '/api/protection-preview'):
                    with self.subTest(field=field, value=value, route=route):
                        self.assertEqual(self.client.post(route, json=study).status_code, 422)
        # Strict numeric inputs may be JSON integers or floating-point values.
        self.assertEqual(self.client.post('/api/analyze', json={**self.study, 'hv_kv': 345, 'mv_kv': 34.5}).status_code, 200)

    def test_missing_ct_boundary_remains_absent_even_when_nominal_capacity_is_enough(self):
        initial = self.engineering_io()
        primary_id = initial['analog_assessments'][0]['role_id']
        self.study['ct_inventory']['hv_breaker_135'] = 0
        result = self.engineering_io(requirements={primary_id: {'neutral': 0, 'vt': 0}})
        primary = result['analog_assessments'][0]
        self.assertEqual(primary['measurement_status'], 'absent')
        self.assertTrue(any('POI-side' in label for label in primary['absent_measurements']))
        sel = next(row for row in primary['candidates'] if row['model'].startswith('SEL-487E'))
        self.assertEqual(sel['screening'], 'within_modeled_envelope')
        self.assertFalse(sel['complete_fit'])
        self.assertFalse(primary['complete_fit'])
        self.assertTrue(primary['measurement_basis'])

    def test_unknown_ct_count_is_exposed_separately_from_absent_measurement(self):
        self.study['ct_inventory']['hv_breaker_135'] = None
        primary = self.engineering_io()['analog_assessments'][0]
        self.assertEqual(primary['measurement_status'], 'unknown')
        self.assertEqual(primary['absent_measurements'], [])
        self.assertTrue(any('POI-side' in label for label in primary['unknown_measurements']))
        self.assertFalse(primary['complete_fit'])

    def test_secondary_analog_assignment_is_unknown_with_all_counts_present(self):
        result = self.engineering_io()
        secondary = next(row for row in result['analog_assessments'] if row['role'] == 'Transformer Secondary')
        self.assertEqual(secondary['measurement_status'], 'unknown')
        self.assertEqual(secondary['absent_measurements'], [])
        self.assertTrue(any('Secondary' in label for label in secondary['unknown_measurements']))
        self.assertFalse(secondary['complete_fit'])

    def test_optional_line_analog_applicability_retains_unknown_remote_measurement(self):
        self.study['include_poi_line'] = True
        result = self.engineering_io()
        line = next(row for row in result['analog_assessments'] if row['role'] == 'POI line · local terminal')
        self.assertEqual(line['phase_banks_min'], 1)
        self.assertEqual(line['phase_banks_max'], 1)
        self.assertEqual(line['measurement_status'], 'unknown')
        self.assertTrue(any('Remote' in label for label in line['unknown_measurements']))
        self.assertFalse(line['complete_fit'])

    def test_nonfinite_raw_json_is_rejected_without_echoing_confidential_input(self):
        # Python's JSON parser accepts these extensions, but validation must not
        # fail while trying to serialize a nonfinite value in an error response.
        with TestClient(app, raise_server_exceptions=False) as client:
            for field in ('hv_kv', 'mv_kv'):
                for value in (float('nan'), float('inf'), -float('inf')):
                    study = {**self.study, field: value, 'title': 'Confidential-title-sentinel'}
                    for route in ('/api/analyze', '/api/protection-preview'):
                        with self.subTest(field=field, value=str(value), route=route):
                            response = client.post(route, content=json.dumps(study), headers={'content-type': 'application/json'})
                            self.assertEqual(response.status_code, 422)
                            self.assertNotIn('Confidential-title-sentinel', response.text)
