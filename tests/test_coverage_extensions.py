"""Independent cross-layer regression cases for expanded reference coverage.

Expected zone counts and survival functions are literal engineering-contract
expectations; these checks do not establish manufacturer or project approval.
"""
from copy import deepcopy
from unittest import TestCase
from uuid import uuid4

from fastapi.testclient import TestClient
from backend.main import app

SCHEMES = ('dedicated', 'shared', 'combined', 'redundant_separate', 'dual_combined', 'combined_separate_secondary')
COMBINED = {'combined', 'dual_combined', 'combined_separate_secondary'}


class CoverageExtensionAcceptanceTests(TestCase):
    def setUp(self):
        self.client = TestClient(app)
        self.addCleanup(self.client.close)
        self.study = self.client.get('/api/study').json()['study']
        self.study['auxiliary'] = 'excluded'
        self.study['ct_inventory'] = {key: 2 for key in (
            'lv_breaker_135', 'lv_breaker_246', 'hv_breaker_135', 'hv_breaker_246',
            'transformer_hv_phase', 'transformer_lv_phase', 'transformer_hv_neutral', 'transformer_lv_neutral')}

    def options(self, study=None):
        response = self.client.post('/api/protection-preview', json=study or self.study)
        self.assertEqual(response.status_code, 200, response.text[:500])
        return {option['scheme']: option for option in response.json()['options']}

    def io(self, scheme, variant='LOCK', study=None):
        response = self.client.post('/api/engineering/io', json={
            'study': study or self.study, 'scheme': scheme,
            'settings': {'variant': variant, 'spare': {'di': 20, 'do': 20, 'basis': 'used'}}})
        self.assertEqual(response.status_code, 200, response.text[:500])
        return response.json()

    def test_literal_zone_and_hardware_role_counts_for_all_six_choices(self):
        # Main station protection IEDs; feeder/line/meter devices are extra.
        expected = {'dedicated': (3, 3), 'shared': (2, 3), 'combined': (2, 2),
                    'redundant_separate': (4, 4), 'dual_combined': (2, 2), 'combined_separate_secondary': (3, 3)}
        self.assertEqual(set(self.options()), set(SCHEMES))
        for scheme, option in self.options().items():
            roles = [r for r in option['device_requirements'] if r['kind'] in ('transformer', 'bus', 'shared', 'combined')]
            zones = [z for z in option['review']['zones'] if z['function'] in ('87T', '87B', '87TB')]
            self.assertEqual((len(roles), len(zones)), expected[scheme], scheme)
            self.assertEqual(len({r['role_id'] for r in roles}), len(roles), scheme)
            self.assertEqual({r['purpose'] for r in roles}, {'primary', 'secondary'})

    def test_single_system_loss_retains_only_explicitly_modeled_differentials(self):
        for scheme, option in self.options().items():
            losses = {loss['unavailable']: loss for loss in option['review']['system_loss']}
            self.assertEqual(set(losses), {'primary', 'secondary'})
            roles = {r['role_id']: r for r in option['device_requirements']}
            for unavailable, loss in losses.items():
                self.assertEqual(loss['remaining'], 'secondary' if unavailable == 'primary' else 'primary')
                self.assertTrue(loss['transformer_differential'])
                self.assertEqual(loss['bus_differential'], unavailable == 'secondary' or scheme in SCHEMES[3:], scheme)
                self.assertFalse(loss['independence_verified'])
                self.assertTrue(loss['limitations'])
                for path in loss['paths']:
                    self.assertEqual(roles[path['role_id']]['purpose'], loss['remaining'])
                    self.assertEqual(path['independence'], 'unverified')
                    self.assertEqual(path['clearing'], 'unverified')
            if scheme == 'shared':
                self.assertEqual(len(losses['secondary']['paths']), 1, 'Shared Primary loss must not count bus as a separate surviving IED')

    def test_collector_sensing_and_differential_boundaries_use_opposite_breaker_sides(self):
        self.study['ct_inventory']['lv_breaker_135'] = 0
        options = self.options()
        for scheme, option in options.items():
            feeders = [z for z in option['review']['zones'] if z['id'].startswith('feeder/')]
            self.assertEqual(len(feeders), len(self.study['bays']))
            self.assertTrue(all(z['measurement_status'] == 'absent' for z in feeders))
            for z in feeders:
                self.assertTrue(all('Bus-side' in b['label'] for b in z['boundaries']))
            differential = [z for z in option['review']['zones'] if z['function'] in ('87B', '87TB')]
            for zone in differential:
                self.assertFalse(any(b['state'] == 'absent' and 'circuit-side' in b['label'] for b in zone['boundaries']))
                self.assertTrue(any('circuit-side' in b['label'] for b in zone['boundaries']))
        self.study['ct_inventory']['lv_breaker_135'] = 2
        self.study['ct_inventory']['lv_breaker_246'] = 0
        for option in self.options().values():
            for zone in option['review']['zones']:
                if zone['id'].startswith('feeder/'):
                    self.assertEqual(zone['measurement_status'], 'present')
                elif zone['function'] in ('87B', '87TB'):
                    self.assertEqual(zone['measurement_status'], 'absent')

    def test_dual_combined_secondary_does_not_require_transformer_lv_boundary(self):
        self.study['ct_inventory']['transformer_lv_phase'] = 0
        for scheme, option in self.options().items():
            secondary = next(z for z in option['review']['zones'] if z['id'] == 'transformer_secondary')
            self.assertEqual(secondary['measurement_status'], 'unknown' if scheme == 'dual_combined' else 'absent')
            if scheme == 'dual_combined':
                self.assertFalse(any('Transformer LV' in b['label'] for b in secondary['boundaries']))
                role = next(r for r in option['device_requirements'] if r['purpose'] == 'secondary')
                self.assertEqual(role['kind'], 'combined')
                self.assertEqual(role['phase_banks'], 4)

    def test_every_option_wiring_variant_has_conservative_consistent_budget(self):
        options = self.options()
        for scheme in SCHEMES:
            for variant in ('LOCK', 'DIRECT', 'GOOSE_BFI', 'LOCAL_H', 'EXTERNAL_F'):
                with self.subTest(scheme=scheme, variant=variant):
                    result = self.io(scheme, variant)
                    self.assertEqual(result['status'], 'partial')
                    self.assertEqual(result['budget_completeness'], 'partial')
                    self.assertEqual(result['code_status'], 'not_generated')
                    self.assertEqual(result['engineering_approval'], 'unavailable')
                    expected_roles = {r['role_id'] for r in options[scheme]['device_requirements'] if r['kind'] != 'meter'}
                    actual_roles = {r['role_id'] for r in result['devices']}
                    self.assertTrue(expected_roles <= actual_roles, f'Missing modeled protection role for {scheme}')
                    for budget in result['budgets'].values():
                        self.assertFalse(budget['complete_fit'])
                        self.assertEqual(budget['completeness'], 'partial')
                        self.assertGreaterEqual(budget['diRequired'], budget['di'])
                        self.assertGreaterEqual(budget['doRequired'], budget['doUsed'])
                        self.assertEqual(budget['doRequired'], sum(g['quantity'] for g in budget['output_demands']))
                    for row in result['ledger']:
                        if scheme == 'dual_combined' and row['included']:
                            self.assertNotIn('87T-S', row['source'])
                            self.assertNotIn('87T-S', row['destination'])
                        self.assertFalse(row['project_drawing_verified'])
                        self.assertTrue(row['source_row_id'])
                        self.assertTrue(all(value is None or value >= 0 for value in row['consumption'].values()))
                    self.assertEqual({r['role_id'] for r in result['hardware_assessments']}, {r['role_id'] for r in options[scheme]['device_requirements']} | {r['role_id'] for r in result['devices']})
                    for hardware in result['hardware_assessments']:
                        self.assertFalse(hardware['complete_fit'])
                        self.assertFalse(hardware['procurement_ready'])
                        self.assertIsNone(hardware['order_code'])
                        gate_codes = {g['code'] for g in hardware['evidence_gates']}
                        self.assertTrue({'function_options', 'analog_ratings', 'digital_electrical_duty', 'joint_slot_allocation', 'firmware_compatibility', 'ordering_symbols'} <= gate_codes)
                        if hardware['role_id'] not in {r['role_id'] for r in options[scheme]['device_requirements']}:
                            self.assertIsNone(hardware['requirements']['phase_ct_banks_min'])
                            self.assertIsNone(hardware['requirements']['phase_ct_banks_max'])
                        self.assertTrue(all(g['state'] == 'not_verified' and g['required_evidence'] for g in hardware['evidence_gates']))
                    for analog in result['analog_assessments']:
                        self.assertFalse(analog['complete_fit'])
                        for candidate in analog['candidates']:
                            self.assertFalse(candidate['complete_fit'])
                            self.assertEqual(candidate['module_compatibility'], 'unverified')
                            self.assertTrue(candidate['ordering_block'])
                    for card in result['card_examples']:
                        self.assertFalse(card['complete_fit'])
                        self.assertEqual(card['module_compatibility'], 'unverified')

    def test_line_on_off_uses_one_local_bank_and_does_not_leak_between_schemes(self):
        self.study['include_poi_line'] = True
        options = self.options()
        for scheme in SCHEMES:
            for variant in ('LOCK', 'DIRECT', 'GOOSE_BFI', 'LOCAL_H', 'EXTERNAL_F'):
                result = self.io(scheme, variant)
                line = next(r for r in options[scheme]['device_requirements'] if r['kind'] == 'line')
                self.assertEqual(line['phase_banks'], 1)
                self.assertEqual(sum(r.get('kind') == 'line' for r in result['devices']), 1)
                analog = next(r for r in result['analog_assessments'] if r['role_id'] == line['role_id'])
                self.assertEqual((analog['phase_banks_min'], analog['phase_banks_max']), (1, 1))
                self.assertEqual(analog['measurement_status'], 'unknown')
                self.assertTrue(any('Remote' in label for label in analog['unknown_measurements']))
                self.assertFalse(analog['complete_fit'])
        self.study['include_poi_line'] = False
        for scheme in SCHEMES:
            result = self.io(scheme)
            self.assertFalse(any(r.get('kind') == 'line' for r in result['devices']))

    def test_new_choices_and_retired_role_decisions_roundtrip_through_portable_project(self):
        for scheme, option in self.options().items():
            secondary = next(r for r in option['device_requirements'] if r['purpose'] == 'secondary')
            key = f"{option['option_id']}/{secondary['role_id']}"
            retired_key = f"{scheme}:poi/{uuid4()}"
            project = {'format': 'relay-wizard-project', 'schema_version': 1, 'project_id': str(uuid4()),
                       'study': deepcopy(self.study), 'draft': None,
                       'decisions': {'selection': option['option_id'], 'requirements': {key: {'neutral': '2', 'vt': '1'}},
                                     'retired_requirements': {retired_key: {'neutral': '1', 'vt': ''}},
                                     'retired_ordering_notes': {retired_key + '/GE T60': {'dc': 'review'}},
                                     'digital_settings': {option['option_id']: {'variant': 'LOCK', 'spare': {'di': 20, 'do': 20, 'basis': 'used'}}},
                                     'digital_bay_order': [b['uid'] for b in self.study['bays']],
                                     'digital_include_line': False}}
            response = self.client.post('/api/projects/validate', json=project)
            self.assertEqual(response.status_code, 200, response.text[:1000])
            accepted = response.json()
            self.assertIn(key, accepted['role_keys'])
            second = self.client.post('/api/projects/validate', json=accepted['project'])
            self.assertEqual(second.status_code, 200, second.text[:500])
            self.assertEqual(second.json()['project'], accepted['project'])
