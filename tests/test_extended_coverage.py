"""Expanded role derivation checks, independent of nominal hardware fit."""
from unittest import TestCase
from backend.main import reference_study
from backend.options import Option, main_coverage, device_requirements, present_options
from backend.engine import analyze

SCHEMES = ('dedicated', 'shared', 'combined', 'redundant_separate', 'dual_combined', 'combined_separate_secondary')

class ExtendedCoverageTests(TestCase):
    def setUp(self):
        self.study = reference_study()['study']
        self.study['auxiliary'] = 'excluded'
        self.study['ct_inventory'] = dict(lv_breaker_135=2, lv_breaker_246=2,
            hv_breaker_135=2, hv_breaker_246=2, transformer_hv_phase=3,
            transformer_lv_phase=3, transformer_hv_neutral=2, transformer_lv_neutral=2)

    def option(self, scheme, secondary='unresolved'):
        return Option(scheme=scheme, hv_boundary='poi', transformer_main_b_hv=secondary,
                      rationale='Reference test', open_item='Review core assignments', evidence=['T_SEPARATE'])

    def result(self, scheme, secondary='unresolved'):
        return present_options(self.study, [self.option(scheme, secondary)], {})['options'][0]

    def test_role_counts_distinguish_three_new_arrangements(self):
        expected = {'redundant_separate': [('transformer','primary',2),('bus','primary',4),('transformer','secondary',2),('bus','secondary',4)],
                    'dual_combined': [('combined','primary',4),('combined','secondary',4)],
                    'combined_separate_secondary': [('combined','primary',4),('transformer','secondary',2),('bus','secondary',4)]}
        for scheme, roles in expected.items():
            result = self.result(scheme)
            actual = [(row['kind'], row['purpose'], row['phase_banks']) for row in result['device_requirements'] if row['kind'] in ('transformer','bus','combined')]
            self.assertEqual(actual, roles)
            ids = [row['role_id'] for row in result['device_requirements']]
            self.assertEqual(len(ids),len(set(ids)))
            for row in result['device_requirements']:
                if row['purpose'] == 'secondary':
                    self.assertTrue(all(s['core_assignment'] == 'unverified' for s in row['measurement_sources']))

    def test_dual_combined_does_not_consume_or_require_lv_incomer_measurement(self):
        self.study['ct_inventory']['transformer_lv_phase'] = 0
        result = self.result('dual_combined', 'bushing')
        self.assertEqual(result['main_coverage']['transformer_b']['status'], 'Boundaries present')
        self.assertEqual(result['review']['secondary_measurements'], 'present')
        for role in result['device_requirements']:
            if role['kind'] == 'combined':
                self.assertFalse(any('LV phase' in row['label'] for row in role['measurement_sources']))
        hybrid = self.result('combined_separate_secondary', 'bushing')
        self.assertEqual(hybrid['review']['secondary_measurements'], 'absent')
        self.assertEqual(hybrid['review']['readiness'], 'blocked')

    def test_loss_statements_report_nominal_coverage_without_approval(self):
        for scheme in SCHEMES:
            result = self.result(scheme)
            primary_loss, secondary_loss = result['review']['system_loss']
            self.assertEqual(primary_loss['unavailable'], 'primary')
            self.assertTrue(primary_loss['transformer_differential'])
            self.assertEqual(primary_loss['bus_differential'], scheme in SCHEMES[3:])
            self.assertTrue(secondary_loss['transformer_differential'])
            self.assertTrue(secondary_loss['bus_differential'])
            for loss in (primary_loss, secondary_loss):
                self.assertFalse(loss['independence_verified'])
                self.assertTrue(all(path['independence'] == 'unverified' for path in loss['paths']))
                self.assertTrue(all(path['clearing'] == 'unverified' for path in loss['paths']))

    def test_secondary_hv_assignment_propagates_to_extended_zone(self):
        result = self.result('dual_combined','bushing')
        self.assertEqual(result['main_coverage']['transformer_b']['function'], '87TB')
        secondary = next(row for row in result['device_requirements'] if row['purpose'] == 'secondary')
        self.assertIn('HV bushing',secondary['measurement_sources'][0]['label'])
        self.study['ct_inventory']['transformer_hv_phase'] = 0
        result = self.result('dual_combined','bushing')
        self.assertEqual(result['review']['secondary_measurements'], 'absent')
        self.assertEqual(result['review']['readiness'], 'blocked')
