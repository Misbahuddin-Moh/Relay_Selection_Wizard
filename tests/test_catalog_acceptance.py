"""Independent fail-closed acceptance of the pinned inert ordering knowledge.

Actual imported records are incomplete research data. These tests do not turn
confidence labels, self-reported reviews, or hashes into manufacturer approval.
"""
from contextlib import contextmanager
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch

from fastapi.testclient import TestClient
from backend.main import app
from backend import catalog_package as package_module
from backend.catalog_readiness import assess_catalog, product_sha256


class CatalogReadinessAcceptanceTests(TestCase):
    def setUp(self):
        self.root = package_module.ROOT
        self.manifest = json.loads((self.root / 'manifest.json').read_text())
        self.entries = {entry['model']: entry for entry in self.manifest['products']}
        self.release = self.manifest['source_release_sha']
        self.client = TestClient(app)
        self.addCleanup(self.client.close)
        self.study = self.client.get('/api/study').json()['study']
        self.study['auxiliary'] = 'excluded'

    def product(self, model='SEL-451-5'):
        return json.loads((self.root / self.entries[model]['file']).read_text())

    def assess(self, product, model='SEL-451-5', expected=None, release=None):
        return assess_catalog(product, model, self.release if release is None else release, expected)

    @staticmethod
    def codes(result):
        return {blocker['code'] for blocker in result['blockers']}

    def conservative(self, result):
        self.assertFalse(result['complete_fit'])
        self.assertFalse(result['procurement_ready'])
        self.assertIsNone(result['order_code'])
        self.assertTrue(result['catalog_evidence_only'])
        for track in ('code_layout', 'hardware_compatibility', 'application_review'):
            self.assertIn(result['tracks'][track]['status'], ('blocked', 'evidence_recorded'))
            self.assertNotIn(result['tracks'][track]['status'], ('approved', 'compatible', 'ready'))

    @contextmanager
    def copied_package(self):
        with TemporaryDirectory() as directory:
            target = Path(directory)
            for source in self.root.glob('*.json'):
                (target / source.name).write_bytes(source.read_bytes())
            with patch.object(package_module, 'ROOT', target):
                yield target

    def calculate(self, study=None):
        response = self.client.post('/api/engineering/io', json={
            'study': study or self.study, 'scheme': 'dedicated',
            'settings': {'variant': 'LOCK', 'spare': {'di': 20, 'do': 20, 'basis': 'used'}}})
        self.assertEqual(response.status_code, 200, response.text[:500])
        return response.json()

    def test_actual_package_has_nine_pinned_distinct_products_without_readiness_promotion(self):
        result = package_module.catalog_package()
        self.assertEqual(len(result['products']), 9)
        self.assertEqual(len({r['requested_model'] for r in result['products']}), 9)
        self.assertEqual(result['source_release_sha'], self.release)
        self.assertRegex(self.release, r'^[0-9a-f]{40}$')
        self.assertRegex(result['fingerprint'], r'^[0-9a-f]{64}$')
        self.assertEqual(result['role_mapping'], 'not_performed')
        self.assertFalse(result['complete_fit'])
        self.assertFalse(result['procurement_ready'])
        for product in result['products']:
            self.conservative(product)
            self.assertEqual({t['status'] for t in product['tracks'].values()}, {'blocked'})
            self.assertTrue(product['blockers'])
            self.assertNotIn('PRODUCT_HASH_MISMATCH', self.codes(product))

    def test_actual_partial_header_and_legacy_variant_remain_explicitly_blocked(self):
        partial = self.assess(self.product('SEL-351S'), 'SEL-351S')
        self.assertTrue({'NO_ORDERING_FIELDS', 'SOURCE_PROVENANCE_INCOMPLETE', 'CONTRACT_VERSION_UNSUPPORTED'} <= self.codes(partial))
        self.conservative(partial)
        legacy = self.assess(self.product('SEL-311L-0/-6'), 'SEL-311L-0/-6')
        self.assertIn('INVALID_REQUESTED_MODEL', self.codes(legacy))
        self.assertEqual(legacy['catalog_model'], 'SEL-311L-0/-6')
        self.conservative(legacy)

    def test_exact_variant_never_inferred_from_family_name_or_neighbor_variant(self):
        product = self.product()
        for requested in ('SEL-451', 'SEL-451-4', 'SEL-451-6', '451-5', 'sel-451-5'):
            result = self.assess(product, requested)
            self.assertIn('EXACT_MODEL_MISMATCH', self.codes(result))
            self.assertTrue(all(t['status'] == 'blocked' for t in result['tracks'].values()))
            self.conservative(result)
        exact = self.assess(product)
        self.assertNotIn('EXACT_MODEL_MISMATCH', self.codes(exact))
        self.conservative(exact)

    def test_canonical_hash_ignores_key_order_and_detects_content_change(self):
        product = self.product()
        reordered = dict(reversed(list(product.items())))
        expected = sha256(json.dumps(product, ensure_ascii=True, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()
        self.assertEqual(product_sha256(product), expected)
        self.assertEqual(product_sha256(reordered), expected)
        product['prefix_note'] = product.get('prefix_note', '') + ' changed evidence'
        self.assertNotEqual(product_sha256(product), expected)
        result = self.assess(product, expected=expected)
        self.assertIn('PRODUCT_HASH_MISMATCH', self.codes(result))
        self.assertTrue(all(t['status'] == 'blocked' for t in result['tracks'].values()))

    def test_invalid_or_missing_provenance_hashes_fail_closed(self):
        product = self.product()
        for release in ('main', 'a' * 39, 'A' * 40, '', None):
            result = assess_catalog(product, 'SEL-451-5', release)
            self.assertIn('SOURCE_RELEASE_UNPINNED', self.codes(result))
            self.conservative(result)
        for expected in ('', 'f' * 63, 'F' * 64, True):
            result = self.assess(product, expected=expected)
            self.assertIn('INVALID_EXPECTED_HASH', self.codes(result))
            self.conservative(result)
        self.assertIn('REVIEW_PROVENANCE_INCOMPLETE', self.codes(self.assess(product)))
        self.assertIn('REVIEW_SOURCE_HASH_INVALID', self.codes(self.assess(product)))

    def test_unknown_constraint_and_unknown_keys_cannot_be_silently_ignored(self):
        product = self.product()
        product['constraints'] = [{'id': 'future-rule', 'type': 'future_firmware_allocator', 'confidence': 'stated'}]
        product['catalog_contract_version'] = 1
        result = self.assess(product)
        self.assertIn('RULE_TYPE_UNSUPPORTED', self.codes(result))
        blocker = next(r for r in result['blockers'] if r['code'] == 'RULE_TYPE_UNSUPPORTED')
        self.assertEqual(set(blocker['tracks']), {'code_layout', 'hardware_compatibility', 'application_review'})
        self.conservative(result)
        product['silently_approve'] = True
        self.assertIn('UNKNOWN_KEYS', self.codes(self.assess(product)))

    def test_layout_and_hardware_rule_unknowns_are_separate_from_application_evidence(self):
        product = self.product()
        product['layout_verified'] = False
        product['constraints'] = [{'id': 'bad-ref', 'type': 'requires', 'confidence': 'stated',
                                   'if': {'field': 'DOES_NOT_EXIST', 'in': ['X']},
                                   'then': {'field': 'DOES_NOT_EXIST', 'in': ['X']}}]
        result = self.assess(product)
        layout = next(r for r in result['blockers'] if r['code'] == 'LAYOUT_NOT_VERIFIED')
        self.assertEqual(layout['tracks'], ['code_layout'])
        self.assertIn('RULE_FIELD_UNKNOWN', self.codes(result))
        self.assertIn('GOLDEN_PROVENANCE_MISSING', self.codes(result))
        self.assertIn('application_review', result['tracks'])
        self.conservative(result)

    def test_confidence_and_self_reported_layout_flags_do_not_promote_catalog(self):
        product = self.product()
        product['catalog_contract_version'] = 1
        product['layout_verified'] = True
        product['doc_status'] = 'manufacturer_reviewed'
        for field in product['fields']:
            field['confidence'] = 'manufacturer_verified'
        for rule in product['constraints']:
            rule['confidence'] = 'manufacturer_verified'
        result = self.assess(product)
        self.assertIn('EXTRACTION_REQUIRES_REVIEW', self.codes(result))
        self.assertIn('REVIEW_PROVENANCE_INCOMPLETE', self.codes(result))
        self.conservative(result)

    def test_manifest_hash_mismatch_changes_package_and_engineering_fingerprint_without_releasing(self):
        baseline = self.calculate()
        with self.copied_package() as root:
            path = root / self.entries['SEL-451-5']['file']
            product = json.loads(path.read_text())
            product['prefix_note'] = 'Modified inert product for mismatch regression'
            path.write_text(json.dumps(product))
            changed = self.calculate()
            readiness = changed['catalog_readiness']
            altered = next(r for r in readiness['products'] if r['requested_model'] == 'SEL-451-5')
            self.assertIn('PRODUCT_HASH_MISMATCH', self.codes(altered))
            self.assertNotEqual(readiness['fingerprint'], baseline['catalog_readiness']['fingerprint'])
            self.assertNotEqual(changed['request_fingerprint'], baseline['request_fingerprint'])
            self.assertEqual(changed['budgets'], baseline['budgets'])
            self.assertEqual(changed['code_status'], 'not_generated')
            self.assertEqual(changed['engineering_approval'], 'unavailable')
            self.assertTrue(all(not row['complete_fit'] and row['order_code'] is None for row in changed['hardware_assessments']))

    def test_catalog_readiness_is_informational_on_supported_and_unsupported_routes(self):
        baseline = self.calculate()
        again = self.calculate()
        self.assertEqual(baseline['request_fingerprint'], again['request_fingerprint'])
        self.assertEqual(baseline['catalog_readiness'], again['catalog_readiness'])
        study = {**self.study, 'hv_kv': 34.5, 'mv_kv': 345}
        unsupported = self.calculate(study)
        self.assertEqual(unsupported['status'], 'unsupported')
        self.assertEqual(unsupported['hardware_assessments'], [])
        self.assertEqual(unsupported['catalog_readiness'], baseline['catalog_readiness'])
        self.assertEqual(unsupported['code_status'], 'not_generated')

    def test_malformed_nested_or_nonfinite_catalog_data_returns_blockers(self):
        changes = [
            ('fields', None), ('fields', [None]), ('constraints', [None]),
            ('source', []), ('readiness_evidence', []), ('prefix', float('nan')),
        ]
        for field, value in changes:
            product = self.product()
            product[field] = value
            with self.subTest(field=field, value=str(value)):
                result = self.assess(product)
                self.assertTrue(result['blockers'])
                self.conservative(result)
                if field == 'prefix':
                    self.assertIn('INVALID_JSON_VALUE', self.codes(result))
                    self.assertIsNone(result['product_sha256'])
        for product in (None, [], True):
            result = self.assess(product)
            self.assertIn('INVALID_TYPE', self.codes(result))
            self.conservative(result)

    def test_source_lookalike_domains_and_wrong_model_review_references_fail_closed(self):
        product = self.product()
        for url in ('https://selinc.com.example.net/manual', 'http://selinc.com/manual',
                    'https://selinc.com@evil.example/manual', 'https://example.net/selinc.com/manual'):
            product['source']['url'] = url
            self.assertIn('MANUFACTURER_SOURCE_UNESTABLISHED', self.codes(self.assess(product)))
        product = self.product()
        product['readiness_evidence'] = {'source_revision': {
            'source_id': 'test-unverified-reference', 'source_sha256': 'a' * 64,
            'locator': 'test locator', 'reviewer': 'unverified', 'reviewed_on': '2026-11-17',
            'model': 'SEL-451-6', 'revision': 'unverified'}}
        result = self.assess(product)
        self.assertTrue(any(b['code'] == 'REVIEW_PROVENANCE_INCOMPLETE'
                            and b['path'] == 'readiness_evidence.source_revision' for b in result['blockers']))
        self.conservative(result)

    def test_generated_golden_case_cannot_replace_independent_manufacturer_evidence(self):
        product = self.product()
        reference = {'source_id': 'generated-case', 'source_sha256': 'a' * 64,
                     'locator': 'synthetic fixture', 'reviewer': 'test', 'reviewed_on': '2026-11-17',
                     'model': product['model'], 'revision': 'test', 'source_type': 'generated_fixture'}
        product['readiness_evidence'] = {'golden_cases': [reference]}
        result = self.assess(product)
        self.assertIn('GOLDEN_PROVENANCE_INADEQUATE', self.codes(result))
        self.assertEqual(result['tracks']['code_layout']['status'], 'blocked')
        self.conservative(result)

    def test_corrupt_or_unsupported_package_cannot_break_existing_accounting(self):
        baseline = self.calculate()
        for corruption in ('unsupported_manifest_version', 'invalid_product_json'):
            with self.subTest(corruption=corruption), self.copied_package() as root:
                if corruption == 'unsupported_manifest_version':
                    manifest = json.loads((root / 'manifest.json').read_text())
                    manifest['contract_version'] = 2
                    (root / 'manifest.json').write_text(json.dumps(manifest))
                else:
                    (root / self.entries['SEL-451-5']['file']).write_text('{invalid JSON')
                result = self.calculate()
                catalog = result['catalog_readiness']
                self.assertEqual(result['status'], 'partial')
                self.assertEqual(result['budgets'], baseline['budgets'])
                self.assertEqual(catalog['products'], [])
                self.assertIsNone(catalog['source_release_sha'])
                self.assertEqual(catalog['source_url'], '')
                self.assertIn('CATALOG_PACKAGE_UNAVAILABLE', {i['code'] for i in catalog['issues']})
                self.assertFalse(catalog['complete_fit'])
                self.assertFalse(catalog['procurement_ready'])
                self.assertEqual(result['code_status'], 'not_generated')
                self.assertEqual(result['engineering_approval'], 'unavailable')
                self.assertTrue(all(not h['complete_fit'] and h['order_code'] is None for h in result['hardware_assessments']))
                self.assertNotEqual(catalog['fingerprint'], baseline['catalog_readiness']['fingerprint'])
                self.assertNotEqual(result['request_fingerprint'], baseline['request_fingerprint'])
                repeat = self.calculate()
                self.assertEqual(repeat['catalog_readiness']['fingerprint'], catalog['fingerprint'])
                self.assertEqual(repeat['request_fingerprint'], result['request_fingerprint'])

    def test_existing_portable_project_decisions_do_not_acquire_catalog_approvals(self):
        response = self.client.post('/api/projects/validate', json=self.study)
        self.assertEqual(response.status_code, 200, response.text[:500])
        project = response.json()['project']
        saved = deepcopy(project)
        self.calculate()
        response = self.client.post('/api/projects/validate', json=project)
        self.assertEqual(response.status_code, 200, response.text[:500])
        self.assertEqual(response.json()['project'], saved)
        self.assertNotIn('catalog_readiness', response.json()['project'])
        self.assertNotIn('catalog_readiness', response.json()['project']['decisions'])
