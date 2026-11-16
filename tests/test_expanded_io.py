"""Regression checks for derived second-system template provenance and controls."""
from copy import deepcopy
from unittest import TestCase
from fastapi.testclient import TestClient
from backend.main import app


class ExpandedWiringControlsTests(TestCase):
    def setUp(self):
        self.client = TestClient(app)
        self.addCleanup(self.client.close)
        self.study = self.client.get('/api/study').json()['study']

    def payload(self, scheme):
        return {'study': self.study, 'scheme': scheme, 'settings': {
            'variant': 'LOCK', 'spare': {'di': 20, 'do': 20, 'basis': 'used'}}}

    def calculate(self, payload):
        response = self.client.post('/api/engineering/io', json=payload)
        self.assertEqual(response.status_code, 200, response.text[:500])
        return response.json()

    def test_dual_combined_secondary_replaces_transformer_only_measurements(self):
        result = self.calculate(self.payload('dual_combined'))
        secondary = [row for row in result['ledger'] if row['destination'] == 'T-S'
                     and row['method'] == 'hardwired CT secondary' and row['included']]
        self.assertEqual(sum(row['consumption']['destination_ct_channels'] for row in secondary), 12)
        self.assertTrue(all('T-LV' not in row['source'] for row in secondary))
        self.assertTrue(all('Secondary-core-unassigned' in row['source'] for row in secondary))
        self.assertTrue(all(row['template_source'].startswith('COMB_ASYM.LOCK.L0.') for row in secondary))
        self.assertTrue(all(row['authority'] == 'derived_reference_template_unreviewed' for row in secondary))

    def test_bus_secondary_template_has_separate_alias_and_trace(self):
        result = self.calculate(self.payload('combined_separate_secondary'))
        bus = next(row for row in result['devices'] if row['alias'] == 'BUS-S')
        analog = next(row for row in result['analog_assessments'] if row['role_id'] == bus['role_id'])
        self.assertEqual(analog['phase_channels_min'], 12)
        self.assertEqual(analog['measurement_status'], 'unknown')
        secondary_rows = [row for row in result['ledger'] if row['destination'] == 'BUS-S' or row['source'] == 'BUS-S']
        self.assertTrue(secondary_rows)
        self.assertTrue(all(row['template_source'].startswith('SEP.LOCK.L0.') for row in secondary_rows))

    def test_extended_editor_roundtrip_keeps_point_totals_and_rejects_wrong_classes(self):
        payload = self.payload('redundant_separate')
        baseline = self.calculate(payload)
        payload['settings']['edits'] = {'LOCK': baseline['editor']['signals']}
        self.assertEqual(self.calculate(payload)['budgets'], baseline['budgets'])
        payload['settings']['output_classes'] = {'LOCK': {'9999999999': ['fast']}}
        self.assertEqual(self.client.post('/api/engineering/io', json=payload).status_code, 422)

    def test_hardware_gate_requirements_track_analog_edits_without_approving(self):
        payload = self.payload('dual_combined')
        baseline = self.calculate(payload)
        role = baseline['hardware_assessments'][0]
        payload['analog_requirements'] = {role['role_id']: {'neutral': 2, 'vt': 1}}
        updated = self.calculate(payload)
        self.assertNotEqual(updated['request_fingerprint'], baseline['request_fingerprint'])
        hardware = next(row for row in updated['hardware_assessments'] if row['role_id'] == role['role_id'])
        self.assertEqual(hardware['requirements']['neutral_inputs'], 2)
        self.assertEqual(hardware['requirements']['vt_banks'], 1)
        self.assertFalse(hardware['complete_fit'])
        self.assertIsNone(hardware['order_code'])
        self.assertEqual({row['state'] for row in hardware['evidence_gates']}, {'not_verified'})
        self.assertEqual(len(hardware['evidence_gates']), 6)

    def test_dedicated_bf_analog_unknown_is_explicit_despite_ledger_counts(self):
        result = self.calculate(self.payload('redundant_separate'))
        bf = next(row for row in result['devices'] if row['alias'] == 'BF-H')
        hardware = next(row for row in result['hardware_assessments'] if row['role_id'] == bf['role_id'])
        self.assertIsNone(hardware['requirements']['phase_ct_banks_min'])
        self.assertIsNone(hardware['requirements']['vt_banks'])
        self.assertTrue(any(row['code'] == 'bf_current_detection' for row in hardware['evidence_gates']))
        self.assertFalse(hardware['complete_fit'])

    def test_dual_combined_local_h_has_one_bf_host_and_no_old_secondary_path(self):
        for include_line in (False, True):
            payload = self.payload('dual_combined')
            payload['study'] = deepcopy(self.study)
            payload['study']['include_poi_line'] = include_line
            payload['settings']['variant'] = 'LOCAL_H'
            result = self.calculate(payload)
            self.assertFalse(any('87T-S' in row[key] for row in result['ledger']
                                 for key in ('name', 'source', 'destination')))
            bfi = [row for row in result['ledger'] if row['name'] == '87TB-S BFI H']
            self.assertEqual(len(bfi), 1)
            self.assertEqual((bfi[0]['source'], bfi[0]['destination'], bfi[0]['method']),
                             ('86-87TB-S', 'T-P', 'hardwired'))
            self.assertEqual(bfi[0]['consumption']['destination_relay_di'], 1)
            for name in ('H BF current reuse', 'H BF retrip', 'H BF timeout', 'H BF DTT key'):
                rows = [row for row in result['ledger'] if row['name'] == name]
                self.assertEqual(len(rows), 1, name)
                self.assertEqual(rows[0]['source'], 'T-P', name)
