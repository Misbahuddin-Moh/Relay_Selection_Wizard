"""Independent acceptance examples for preliminary backend analog screening.

Expected phase envelopes and threshold cases are stated explicitly; no test
confers manufacturer compatibility or engineering approval on a nominal example.
"""
from copy import deepcopy
from unittest import TestCase
from unittest.mock import patch

from fastapi.testclient import TestClient
from backend.main import app


class AnalogScreeningAcceptanceTests(TestCase):
    def setUp(self):
        self.client = TestClient(app)
        self.addCleanup(self.client.close)
        self.study = self.client.get('/api/study').json()['study']
        self.study['auxiliary'] = 'excluded'
        self.request = {
            'study': self.study,
            'scheme': 'dedicated',
            'settings': {'variant': 'LOCK', 'spare': {'di': 20, 'do': 20, 'basis': 'used'}},
        }
        self.provider_patch = patch('backend.options.request_options', side_effect=AssertionError('Unexpected provider call'))
        self.provider = self.provider_patch.start()
        self.addCleanup(self.provider_patch.stop)

    def tearDown(self):
        self.provider.assert_not_called()

    def io(self, request=None, status=200):
        response = self.client.post('/api/engineering/io', json=request or self.request)
        self.assertEqual(response.status_code, status, response.text[:1000])
        return response.json()

    @staticmethod
    def role(result, label):
        return next(row for row in result['analog_assessments'] if row['role'] == label)

    @staticmethod
    def candidate(role, prefix):
        return next(row for row in role['candidates'] if row['model'].startswith(prefix))

    def primary(self, scheme='dedicated', auxiliary='excluded', neutral=None, vt=None):
        request = deepcopy(self.request)
        request['scheme'] = scheme
        request['study']['auxiliary'] = auxiliary
        initial = self.io(request)
        role = initial['analog_assessments'][0]
        request['analog_requirements'] = {role['role_id']: {'neutral': neutral, 'vt': vt}}
        return request, self.io(request)

    def test_literal_reference_phase_envelopes_across_philosophies(self):
        expected = {
            'dedicated': {'Transformer Primary': (2, 2), 'Transformer Secondary': (2, 2), 'Collector bus · single path': (4, 4)},
            'shared': {'Transformer Primary + collector bus': (5, 6), 'Transformer Secondary': (2, 2)},
            'combined': {'Transformer Primary + collector bus': (4, 4), 'Transformer Secondary': (2, 2)},
        }
        for scheme, roles in expected.items():
            request = {**self.request, 'scheme': scheme}
            result = self.io(request)
            for label, (lower, upper) in roles.items():
                with self.subTest(scheme=scheme, role=label):
                    row = self.role(result, label)
                    self.assertEqual((row['phase_banks_min'], row['phase_banks_max']), (lower, upper))
                    self.assertEqual((row['phase_channels_min'], row['phase_channels_max']), (lower * 3, upper * 3))
            for bay in self.study['bays']:
                row = self.role(result, bay['id'])
                self.assertEqual((row['phase_banks_min'], row['phase_banks_max']), (1, 1))

    def test_unknown_auxiliary_changes_upper_case_only_where_applicable(self):
        for scheme, label, expected in (
            ('dedicated', 'Collector bus · single path', (4, 5)),
            ('shared', 'Transformer Primary + collector bus', (5, 7)),
            ('combined', 'Transformer Primary + collector bus', (4, 5)),
        ):
            request = deepcopy(self.request)
            request.update(scheme=scheme)
            request['study']['auxiliary'] = 'unknown'
            result = self.io(request)
            row = self.role(result, label)
            self.assertEqual((row['phase_banks_min'], row['phase_banks_max']), expected)
            secondary = self.role(result, 'Transformer Secondary')
            self.assertEqual((secondary['phase_banks_min'], secondary['phase_banks_max']), (2, 2))

    def test_unknown_requirements_are_not_explicit_zero(self):
        unknown = self.io()
        unknown_role = unknown['analog_assessments'][0]
        self.assertIsNone(unknown_role['neutral_inputs'])
        self.assertIsNone(unknown_role['vt_banks'])
        self.assertEqual(self.candidate(unknown_role, 'SEL-487E')['screening'], 'requirements_unknown')
        request = deepcopy(self.request)
        request['analog_requirements'] = {unknown_role['role_id']: {'neutral': 0, 'vt': 0}}
        zero = self.io(request)
        zero_role = zero['analog_assessments'][0]
        self.assertEqual((zero_role['neutral_inputs'], zero_role['vt_banks']), (0, 0))
        self.assertEqual(self.candidate(zero_role, 'SEL-487E')['screening'], 'within_modeled_envelope')
        self.assertNotEqual(unknown['request_fingerprint'], zero['request_fingerprint'])
        self.assertEqual(unknown['study_fingerprint'], zero['study_fingerprint'])

    def test_sel_known_neutral_and_voltage_requirements_filter_layouts(self):
        _, result = self.primary('shared', neutral=1, vt=1)
        row = result['analog_assessments'][0]
        candidate = self.candidate(row, 'SEL-487E')
        self.assertEqual(candidate['screening'], 'within_modeled_envelope')
        self.assertEqual(sorted((layout['phase_banks'], layout['neutral_inputs'], layout['vt_banks']) for layout in candidate['layouts']),
                         [(5, 3, 2), (6, 3, 1)])
        _, restricted = self.primary('shared', neutral=1, vt=2)
        candidate = self.candidate(restricted['analog_assessments'][0], 'SEL-487E')
        self.assertEqual(candidate['screening'], 'lower_phase_case_only')
        self.assertEqual(len(candidate['layouts']), 1)
        self.assertEqual(candidate['layouts'][0]['phase_banks'], 5)
        self.assertEqual(candidate['layouts'][0]['fit'], 'Lower phase demand only')
        _, insufficient = self.primary(neutral=4, vt=1)
        candidate = self.candidate(insufficient['analog_assessments'][0], 'SEL-487E')
        self.assertEqual(candidate['screening'], 'insufficient_modeled_capacity')
        self.assertEqual(candidate['layouts'], [])

    def test_sel_preserves_lower_case_warning_for_unknown_auxiliary(self):
        _, result = self.primary('shared', auxiliary='unknown', neutral=1, vt=1)
        candidate = self.candidate(result['analog_assessments'][0], 'SEL-487E')
        self.assertEqual(candidate['screening'], 'lower_phase_case_only')
        self.assertTrue(all(layout['fit'] == 'Lower phase demand only' for layout in candidate['layouts']))

    def test_t60_three_module_threshold_and_unknown_neutral_routing(self):
        _, result = self.primary('shared', neutral=2, vt=1)
        candidate = self.candidate(result['analog_assessments'][0], 'Multilin T60')
        self.assertEqual(candidate['screening'], 'lower_phase_case_only')
        self.assertEqual([(case['phase_banks'], case['module_count'], case['within_three_module_example'])
                          for case in candidate['t60_cases']], [(5, 3, True), (6, 4, False)])
        for case in candidate['t60_cases']:
            self.assertIsNone(case['neutral_capacity'])
            self.assertEqual(case['neutral_routing'], 'unverified')
        _, impossible = self.primary(neutral=0, vt=4)
        candidate = self.candidate(impossible['analog_assessments'][0], 'Multilin T60')
        self.assertEqual(candidate['screening'], 'insufficient_modeled_capacity')
        self.assertFalse(candidate['t60_cases'][0]['within_three_module_example'])

    def test_reference_analog_counts_retain_ledger_trace_and_do_not_replace_envelope(self):
        _, result = self.primary('shared', auxiliary='unknown', neutral=2, vt=2)
        row = result['analog_assessments'][0]
        reference = result['budgets']['T-P']['analog_reference']
        self.assertEqual(reference['ct_channels'], 15)
        self.assertEqual((row['phase_channels_min'], row['phase_channels_max']), (15, 21))
        self.assertEqual((row['neutral_inputs'], row['vt_banks']), (2, 2))
        self.assertEqual(reference['evidence_state'], 'illustrative_unreviewed')
        ledger = {entry['ledger_id']: entry for entry in result['ledger']}
        self.assertTrue(reference['ledger_ids'])
        traced = [ledger[identity] for identity in reference['ledger_ids']]
        self.assertTrue(all(entry['included'] and entry['destination'] == 'T-P' for entry in traced))
        self.assertEqual(reference['ct_channels'], sum(entry['consumption']['destination_ct_channels'] for entry in traced))
        self.assertTrue(all(entry['source_documents_required'] for entry in traced))

    def test_remote_line_data_does_not_double_local_current_inputs(self):
        self.request['study']['include_poi_line'] = True
        result = self.io()
        row = self.role(result, 'POI line · local terminal')
        self.assertEqual((row['phase_banks_min'], row['phase_banks_max']), (1, 1))
        self.assertEqual((row['phase_channels_min'], row['phase_channels_max']), (3, 3))
        self.assertEqual(result['budgets']['LINE-H']['analog_reference']['ct_channels'], 3)
        self.assertTrue(any(source.get('remote') for source in row['measurement_sources']))

    def test_invalid_or_foreign_role_inputs_and_derived_claims_are_rejected(self):
        result = self.io()
        role_id = result['analog_assessments'][0]['role_id']
        invalid = [True, 1.5, -1, 1000, '2']
        for field in ('neutral', 'vt'):
            for value in invalid:
                request = deepcopy(self.request)
                request['analog_requirements'] = {role_id: {field: value}}
                with self.subTest(field=field, value=value):
                    self.io(request, status=422)
        for requirements in ({'foreign-role': {'neutral': 0, 'vt': 0}},
                             {role_id: {'neutral': 0, 'vt': 0, 'complete_fit': True}}):
            self.io({**self.request, 'analog_requirements': requirements}, status=422)
        request = {**self.request, 'analog_assessments': [{'complete_fit': True}]}
        self.io(request, status=422)

    def test_analog_inputs_do_not_change_digital_budget_or_confer_approval(self):
        before = self.io()
        _, after = self.primary(neutral=0, vt=0)
        self.assertEqual(before['budgets'], after['budgets'])
        self.assertEqual(before['card_examples'], after['card_examples'])
        self.assertFalse(after['analog_assessments'][0]['complete_fit'])
        for role in after['analog_assessments']:
            for candidate in role['candidates']:
                self.assertFalse(candidate['complete_fit'])
                self.assertEqual(candidate['module_compatibility'], 'unverified')
                self.assertEqual(candidate['electrical_fit'], 'unverified')
                self.assertTrue(candidate['ordering_block'])
                self.assertTrue(candidate['source_urls'])
        self.assertEqual(after['budget_completeness'], 'partial')
        self.assertEqual(after['code_status'], 'not_generated')
        self.assertEqual(after['engineering_approval'], 'unavailable')

    def test_role_bound_requirements_survive_renames_without_leaking_to_other_roles(self):
        initial = self.io()
        feeder = self.role(initial, self.study['bays'][0]['id'])
        request = deepcopy(self.request)
        request['analog_requirements'] = {feeder['role_id']: {'neutral': 2, 'vt': 0}}
        request['study']['title'] = 'Renamed synthetic station'
        request['study']['bays'][0]['id'] = 'Renamed collector breaker'
        result = self.io(request)
        renamed = self.role(result, 'Renamed collector breaker')
        self.assertEqual(renamed['role_id'], feeder['role_id'])
        self.assertEqual((renamed['neutral_inputs'], renamed['vt_banks']), (2, 0))
        for row in result['analog_assessments']:
            if row['role_id'] != feeder['role_id']:
                self.assertIsNone(row['neutral_inputs'])
                self.assertIsNone(row['vt_banks'])

    def test_omitted_requirement_stays_unknown_and_existing_upper_bound_is_accepted(self):
        initial = self.io()
        role_id = initial['analog_assessments'][0]['role_id']
        result = self.io({**self.request, 'analog_requirements': {role_id: {'neutral': 999}}})
        row = result['analog_assessments'][0]
        self.assertEqual(row['neutral_inputs'], 999)
        self.assertIsNone(row['vt_banks'])
        self.assertEqual(self.candidate(row, 'SEL-487E')['screening'], 'insufficient_modeled_capacity')
        self.assertFalse(row['complete_fit'])

    def test_changed_terminal_capacity_invalidates_request_fingerprint(self):
        from backend.relay_catalog import sel_487e_allocations
        before = self.io()
        def changed_allocations(minimum, maximum):
            layouts = deepcopy(sel_487e_allocations(minimum, maximum))
            for layout in layouts:
                layout['phase_banks'] += 1
            return layouts
        with patch('backend.relay_catalog.sel_487e_allocations', side_effect=changed_allocations):
            after = self.io()
        self.assertNotEqual(before['analog_assessments'], after['analog_assessments'])
        self.assertNotEqual(before['request_fingerprint'], after['request_fingerprint'])
        self.assertEqual(before['study_fingerprint'], after['study_fingerprint'])

    def test_unsupported_station_exposes_no_analog_screen(self):
        self.request['study']['auxiliary'] = 'included'
        result = self.io()
        self.assertEqual(result['status'], 'unsupported')
        self.assertEqual(result['analog_assessments'], [])
        self.assertEqual(result['budgets'], {})
