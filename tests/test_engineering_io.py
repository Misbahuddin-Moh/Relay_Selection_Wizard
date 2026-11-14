"""Independent endpoint-budget acceptance tests; examples never confer approval."""
from collections import defaultdict
from copy import deepcopy
import csv
import json
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch
from uuid import uuid4

from fastapi.testclient import TestClient
from backend.main import app
from backend.engineering_io import allocate_contacts, reserve


def signal(identity=900, **changes):
    return {'id': identity, 'name': 'Synthetic endpoint fixture', 'source': 'T-P', 'destination': 'BF-H',
            'method': 'hardwired', 'di': 1, 'do': 1, 'coil': False, 'included': True,
            'reference': 'Synthetic fixture', 'condition': 'Test only', **changes}


class EngineeringIOTests(TestCase):
    def setUp(self):
        self.client = TestClient(app)
        self.addCleanup(self.client.close)
        self.study = self.client.get('/api/study').json()['study']
        self.request = {'study': self.study, 'scheme': 'dedicated',
                        'settings': {'variant': 'LOCK', 'spare': {'di': 20, 'do': 20, 'basis': 'used'}}}
        self.provider_patch = patch('backend.options.request_options')
        self.provider = self.provider_patch.start()
        self.addCleanup(self.provider_patch.stop)

    def tearDown(self):
        self.provider.assert_not_called()

    def io(self, request=None, status=200):
        response = self.client.post('/api/engineering/io', json=request or self.request)
        self.assertEqual(response.status_code, status, response.text[:1000])
        return response.json()

    def custom(self, rows, **settings):
        self.request['settings'].update({'edits': {'LOCK': rows}, **settings})
        return self.io()

    def test_all_researched_case_relay_totals_match_independent_csv(self):
        with Path(__file__).with_name('reference_io_totals.csv').open(newline='') as source:
            rows = list(csv.DictReader(source))
        self.assertEqual(len(rows), 217)
        grouped = defaultdict(list)
        for row in rows:
            grouped[row['case']].append(row)
        self.assertEqual(len(grouped), 30)
        for case, expected_rows in grouped.items():
            prefix, variant, line = case.split('.')
            request = deepcopy(self.request)
            request['scheme'] = {'SEP': 'dedicated', 'SHARED': 'shared', 'COMB_ASYM': 'combined'}[prefix]
            request['settings']['variant'] = variant
            request['study']['include_poi_line'] = line == 'L1'
            result = self.io(request)
            self.assertEqual(result['case_id'], case)
            self.assertEqual(set(result['budgets']), {row['relay'] for row in expected_rows})
            for row in expected_rows:
                with self.subTest(case=case, relay=row['relay']):
                    actual = result['budgets'][row['relay']]
                    for key, column in (('di', 'wired_di'), ('coil', 'coil_duty_do'), ('other', 'other_do'),
                                        ('diRequired', 'di_with_spares'), ('coilRequired', 'coil_duty_do_with_spares'),
                                        ('doRequired', 'do_with_spares')):
                        self.assertEqual(actual[key], int(row[column]), (key, row))

    def test_dedicated_primary_known_lock_direct_and_local_bf_examples(self):
        expected = {'LOCK': (1, 1, 1, 2, 4), 'DIRECT': (0, 4, 5, 0, 11), 'LOCAL_H': (5, 3, 2, 6, 7)}
        for variant, counts in expected.items():
            with self.subTest(variant=variant):
                self.request['settings']['variant'] = variant
                budget = self.io()['budgets']['T-P']
                self.assertEqual(tuple(budget[key] for key in ('di', 'coil', 'other', 'diRequired', 'doRequired')), counts)

    def test_hardwired_signals_consume_points_only_at_true_endpoints(self):
        result = self.custom([signal(), signal(901, source='86-fixture', destination='FP-F1', di=2, do=0)])
        self.assertEqual(result['budgets']['T-P']['other'], 1)
        self.assertEqual(result['budgets']['T-P']['di'], 0)
        self.assertEqual(result['budgets']['BF-H']['di'], 1)
        self.assertEqual(result['budgets']['FP-F1']['di'], 2)
        self.assertEqual(result['budgets']['FP-F2']['di'], 0)
        self.assertEqual(result['budgets']['FP-F1']['other'], 0)
        row = next(row for row in result['ledger'] if row['id'] == 901)
        self.assertEqual(row['source_endpoint']['kind'], 'external')
        self.assertEqual(row['destination_endpoint']['kind'], 'relay')
        self.assertEqual(row['consumption']['source_relay_do'], 0)
        self.assertEqual(row['consumption']['destination_relay_di'], 2)
        self.assertEqual(row['authority'], 'user_override_unreviewed')

    def test_external_lockout_contacts_are_not_originating_relay_outputs(self):
        result = self.io()
        rows = [row for row in result['ledger'] if row['included'] and row['method'] == 'hardwired'
                and row['source_endpoint']['kind'] == 'external'
                and row['consumption']['source_external_contacts']]
        self.assertTrue(rows)
        self.assertTrue(any(row['destination_endpoint']['kind'] == 'relay' for row in rows))
        self.assertTrue(all(row['consumption']['source_relay_do'] == 0 for row in rows))
        for alias, budget in result['budgets'].items():
            counted = sum(row['consumption']['source_relay_do'] for row in result['ledger']
                          if row['source_endpoint']['alias'] == alias)
            self.assertEqual(budget['coil'] + budget['other'], counted)

    def test_communicated_internal_excluded_and_unresolved_routes_are_distinct(self):
        rows = [signal(method='GOOSE'), signal(901, method='internal', destination='T-P', di=0, do=0),
                signal(902, included=False), signal(903, method='hardwired or communicated')]
        result = self.custom(rows)
        for alias in ('T-P', 'BF-H'):
            self.assertEqual(result['budgets'][alias]['di'], 0)
            self.assertEqual(result['budgets'][alias]['doRequired'], 0)
            self.assertEqual(result['budgets'][alias]['open'], 1)
        self.assertEqual(result['budgets']['T-P']['completeness'], 'partial')

    def test_spare_bases_use_integer_ceiling_at_real_thresholds(self):
        for used, percent, basis, expected in ((0, 99, 'installed', 0), (1, 20, 'used', 2),
                (4, 40, 'used', 6), (4, 40, 'installed', 7), (1, 99, 'installed', 100),
                (4, 0, 'used', 4), (4, 0, 'installed', 4)):
            with self.subTest(used=used, percent=percent, basis=basis):
                self.assertEqual(reserve(used, percent, basis), expected)
                result = self.custom([signal(do=used, di=used)],
                                     spare={'di': percent, 'do': percent, 'basis': basis})
                self.assertEqual(result['budgets']['T-P']['doRequired'], expected)
                self.assertEqual(result['budgets']['BF-H']['diRequired'], expected)

    def test_partial_counts_and_nominal_cards_never_grant_fit_or_approval(self):
        result = self.custom([])
        self.assertEqual(result['status'], 'partial')
        self.assertEqual(result['budget_completeness'], 'partial')
        self.assertEqual(result['code_status'], 'not_generated')
        self.assertEqual(result['engineering_approval'], 'unavailable')
        for budget in result['budgets'].values():
            self.assertFalse(budget['complete_fit'])
            self.assertTrue(budget['ordering_block'])
            self.assertTrue(any(category['state'] == 'unresolved' for category in budget['category_review']))
        self.assertTrue(any(card['screening'] == 'within_nominal_counts' for card in result['card_examples']))
        for card in result['card_examples']:
            self.assertFalse(card['complete_fit'])
            self.assertEqual(card['electrical_fit'], 'unverified')
            self.assertEqual(card['module_compatibility'], 'unverified')

    def test_fast_and_form_c_require_simultaneous_evidence_not_total_do(self):
        result = self.custom([signal(di=0)], output_classes={'LOCK': {'900': ['fast', 'form_c']}})
        budget = result['budgets']['T-P']
        self.assertEqual((budget['doRequired'], budget['fastRequired'], budget['formCRequired']), (2, 2, 2))
        self.assertEqual(len(budget['output_demands']), 1)
        self.assertEqual(budget['output_demands'][0]['classes'], ['fast', 'form_c'])
        for card in (row for row in result['card_examples'] if row['device'] == 'T-P'):
            self.assertIsNone(card['capacities']['fast'])
            self.assertIsNone(card['capacities']['form_c'])
            self.assertEqual(card['screening'], 'class_evidence_missing')
            self.assertIsNone(card['nominal_allocation']['feasible'])
            self.assertFalse(card['complete_fit'])

    def test_scope_guard_is_server_side_and_returns_no_usable_budget(self):
        for count, auxiliary in ((4, 'unknown'), (12, 'excluded'), (3, 'included')):
            request = deepcopy(self.request)
            request['study']['bays'] = [{'uid': str(uuid4()), 'id': f'CB-{i}', 'branches': [f'F-{i}'], 'ct': 'present'}
                                        for i in range(count)]
            request['study']['auxiliary'] = auxiliary
            result = self.io(request)
            self.assertEqual(result['status'], 'unsupported')
            self.assertEqual(result['budgets'], {})
            self.assertEqual(result['ledger'], [])
            self.assertEqual(result['card_examples'], [])
            self.assertFalse(result['scope']['reference_hardware_supported'])

    def test_fingerprints_are_deterministic_and_track_settings_and_study(self):
        first = self.io()
        self.assertEqual(self.io(), first)
        self.request['settings']['spare']['do'] = 40
        changed = self.io()
        self.assertNotEqual(changed['request_fingerprint'], first['request_fingerprint'])
        self.assertEqual(changed['study_fingerprint'], first['study_fingerprint'])
        self.request['study']['title'] = 'Edited study revision'
        self.assertNotEqual(self.io()['study_fingerprint'], first['study_fingerprint'])
        self.assertTrue(first['solver_version'])
        self.assertTrue(first['matrix_version'])

    def test_manipulated_client_totals_capacities_and_completeness_rejected(self):
        for field, value in (('totals', {'di': 0}), ('capacity', 999), ('completeness', 'complete'),
                             ('complete_fit', True), ('budget', {'doRequired': 0})):
            with self.subTest(field=field):
                self.io({**self.request, field: value}, status=422)
                request = deepcopy(self.request)
                request['settings'][field] = value
                self.io(request, status=422)

    def test_invalid_controls_signal_identity_and_unknown_classes_rejected(self):
        variants = []
        for spare in ({'di': -1, 'do': 20, 'basis': 'used'}, {'di': 20, 'do': 100, 'basis': 'installed'},
                      {'di': True, 'do': 20, 'basis': 'used'}, {'di': 1.5, 'do': 20, 'basis': 'used'}):
            variants.append({**self.request['settings'], 'spare': spare})
        variants.extend([
            {**self.request['settings'], 'edits': {'LOCK': [signal(), signal()]}},
            {**self.request['settings'], 'edits': {'LOCK': [signal(di=-1)]}},
            {**self.request['settings'], 'edits': {'LOCK': [signal(method='internal')]}},
            {**self.request['settings'], 'output_classes': {'LOCK': {'0': ['invented']}}},
            {**self.request['settings'], 'output_classes': {'LOCK': {'999999': ['fast']}}},
        ])
        for settings in variants:
            with self.subTest(settings=settings):
                self.io({**self.request, 'settings': settings}, status=422)

    def test_project_roundtrip_preserves_output_classes(self):
        result = self.client.post('/api/projects/validate', json=self.study).json()
        project = result['project']
        settings = {**self.request['settings'], 'edits': {'LOCK': [signal()]},
                    'output_classes': {'LOCK': {'900': ['fast', 'form_c']}}}
        project['decisions']['digital_settings'] = {'dedicated:poi': settings}
        response = self.client.post('/api/projects/validate', json=project)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()['project']['decisions']['digital_settings']['dedicated:poi']['output_classes'],
                         settings['output_classes'])

    def test_ledger_provenance_is_unreviewed_with_sources_and_external_ends(self):
        result = self.io()
        self.assertGreater(len(result['ledger']), len(result['editor']['signals']))
        for row in result['ledger']:
            self.assertEqual(row['evidence_state'], 'unreviewed')
            self.assertFalse(row['project_drawing_verified'])
            self.assertTrue(row['source_endpoint']['id'])
            self.assertTrue(row['destination_endpoint']['id'])
            self.assertTrue(row['owner']['id'])
        self.assertTrue(any(row['source_documents_required'] for row in result['ledger']))

    def test_unknown_function_only_card_capacity_remains_unknown(self):
        self.request['scheme'] = 'shared'
        result = self.io()
        unknown = [card for card in result['card_examples'] if card['capacities']['di'] is None]
        self.assertTrue(unknown)
        for card in unknown:
            self.assertEqual(card['screening'], 'function_unverified')
            self.assertIsNone(card['nominal_allocation']['feasible'])
            self.assertFalse(card['complete_fit'])

    def test_catalog_and_policy_changes_invalidate_fingerprint(self):
        from backend import engineering_io as domain
        first = self.io()
        changed_catalog = deepcopy(domain.EDITOR)
        changed_catalog['cards'][0][3] = str(int(changed_catalog['cards'][0][3]) + 1)
        with patch.object(domain, 'EDITOR', changed_catalog):
            catalog_result = self.io()
        self.assertNotEqual(first['catalog_fingerprint'], catalog_result['catalog_fingerprint'])
        self.assertNotEqual(first['request_fingerprint'], catalog_result['request_fingerprint'])
        self.assertEqual(first['study_fingerprint'], catalog_result['study_fingerprint'])
        with patch('backend.assessment.POLICY_VERSION', 'new-reviewed-policy-test'):
            policy_result = self.io()
        self.assertNotEqual(first['request_fingerprint'], policy_result['request_fingerprint'])
        self.assertNotEqual(first['study_fingerprint'], policy_result['study_fingerprint'])

    def test_import_rejects_semantically_invalid_saved_wiring(self):
        project = self.client.post('/api/projects/validate', json=self.study).json()['project']
        for settings in (
            {**self.request['settings'], 'edits': {'LOCK': [signal(method='internal')]}},
            {**self.request['settings'], 'output_classes': {'LOCK': {'999999': ['fast']}}},
        ):
            project['decisions']['digital_settings'] = {'dedicated:poi': settings}
            response = self.client.post('/api/projects/validate', json=project)
            self.assertEqual(response.status_code, 422)

    def test_reorder_clears_positional_class_requirements_with_signal_edits(self):
        project = self.client.post('/api/projects/validate', json=self.study).json()['project']
        project['decisions']['digital_settings'] = {'dedicated:poi': {
            **self.request['settings'], 'output_classes': {'LOCK': {'0': ['fast', 'form_c']}}}}
        project['study']['bays'].reverse()
        response = self.client.post('/api/projects/validate', json=project)
        self.assertEqual(response.status_code, 200, response.text)
        result = response.json()
        self.assertEqual(result['project']['decisions']['digital_settings']['dedicated:poi']['output_classes'], {})
        self.assertTrue(any('cleared' in warning for warning in result['warnings']))

    def test_stale_line_signature_normalizes_before_incompatible_internal_edits(self):
        self.request['study']['include_poi_line'] = True
        line_result = self.io()
        project = self.client.post('/api/projects/validate', json=self.study).json()['project']
        project['decisions']['digital_settings'] = {'dedicated:poi': {
            **self.request['settings'], 'edits': {'LOCK': line_result['editor']['signals']}}}
        project['study']['include_poi_line'] = False
        response = self.client.post('/api/projects/validate', json=project)
        self.assertEqual(response.status_code, 200, response.text)
        settings = response.json()['project']['decisions']['digital_settings']['dedicated:poi']
        self.assertEqual(settings['edits'], {})
        self.assertTrue(response.json()['warnings'])

    def test_engineering_requires_persistent_ids_and_does_not_remigrate(self):
        for subject in ('study', 'bay'):
            request = deepcopy(self.request)
            if subject == 'study': request['study'].pop('uid')
            else: request['study']['bays'][0].pop('uid')
            self.io(request, status=422)

    def test_oversize_or_invalid_json_fails_without_provider_call(self):
        response = self.client.post('/api/engineering/io', content=b' ' * (2 * 1024 * 1024 + 1))
        self.assertEqual(response.status_code, 413)
        for raw in (b'{broken', b'null', b'[]', b'\xff'):
            self.assertEqual(self.client.post('/api/engineering/io', content=raw).status_code, 422)


class ContactAllocationTests(TestCase):
    def test_one_multicapability_contact_cannot_satisfy_two_independent_outputs(self):
        result = allocate_contacts([{'classes': ['fast'], 'quantity': 1}, {'classes': ['form_c'], 'quantity': 1}],
                                   [{'capabilities': ['fast', 'form_c'], 'quantity': 1}])
        self.assertFalse(result['feasible'])
        self.assertEqual(result['allocated_contacts'], 1)
        self.assertEqual(result['required_contacts'], 2)

    def test_conjunctive_duty_cannot_be_met_by_separate_incompatible_contacts(self):
        demand = [{'classes': ['coil', 'fast'], 'quantity': 1}]
        split = [{'capabilities': ['coil'], 'quantity': 1}, {'capabilities': ['fast'], 'quantity': 1}]
        self.assertFalse(allocate_contacts(demand, split)['feasible'])
        self.assertTrue(allocate_contacts(demand, [{'capabilities': ['coil', 'fast'], 'quantity': 1}])['feasible'])

    def test_allocator_reroutes_flexible_demand_to_preserve_scarce_class(self):
        demand = [{'classes': [], 'quantity': 1}, {'classes': ['fast'], 'quantity': 1}]
        resources = [{'capabilities': ['fast'], 'quantity': 1}, {'capabilities': [], 'quantity': 1}]
        result = allocate_contacts(demand, resources)
        self.assertTrue(result['feasible'])
        self.assertEqual(result['allocated_contacts'], 2)
        self.assertEqual(sum(row['quantity'] for row in result['allocations']), 2)
