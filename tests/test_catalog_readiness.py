"""Read-only catalog boundary tests; fixture claims never establish approval."""
from copy import deepcopy
import json
from pathlib import Path
from unittest import TestCase
from backend.catalog_readiness import assess_catalog, product_sha256

SHA = 'a' * 40


def reference(model='SEL-451-5'):
    return {'source_id': 'Synthetic manufacturer fixture', 'source_sha256': 'b' * 64,
            'locator': 'Table 1', 'reviewer': 'Synthetic reviewer', 'reviewed_on': '2026-11-16',
            'model': model, 'revision': 'Fixture revision1', 'source_type': 'manufacturer_configurator'}


def record():
    return {'catalog_contract_version': 1, 'model': 'SEL-451-5', 'prefix': '0451',
            'source': {'doc_id': 'Synthetic test', 'url': 'https://selinc.com/example', 'doc_date': '2026-11-16', 'method': 'human manufacturer document review'},
            'doc_status': 'manufacturer_reviewed', 'layout_verified': True,
            'fields': [{'id': 'supply', 'name': 'Supply', 'order': 1, 'width': 1,
                        'confidence': 'manufacturer_verified', 'options': [{'code': '1', 'desc': 'Fixture supply', 'extra_cost': False}]}],
            'constraints': [], 'accessories': [], 'open_questions': [],
            'readiness_evidence': {**{key: reference() for key in ('source_revision', 'layout_review', 'hardware_review', 'application_review')},
                                   'golden_cases': [reference()]}}


class CatalogReadinessTests(TestCase):
    def assess(self, product=None, requested_model='SEL-451-5', **kwargs):
        return assess_catalog(record() if product is None else product, requested_model, SHA, **kwargs)

    def codes(self, product):
        return {row['code'] for row in self.assess(product)['blockers']}

    def test_documentary_references_are_recorded_without_approval_or_code(self):
        product = record(); before = deepcopy(product)
        result = self.assess(product, expected_product_sha256=product_sha256(product))
        self.assertEqual(product, before)
        self.assertEqual(result['blockers'], [])
        self.assertEqual({row['status'] for row in result['tracks'].values()}, {'evidence_recorded'})
        self.assertFalse(result['complete_fit']); self.assertFalse(result['procurement_ready'])
        self.assertIsNone(result['order_code'])
        self.assertTrue(result['catalog_evidence_only'])
        self.assertEqual(result['source_release_sha'], SHA)

    def test_model_variants_are_never_inferred(self):
        for requested in ('SEL-451', 'SEL-451-6', 'SEL-487E-4', 'SEL-487E-3/-4', 'SEL-451-5 with BF'):
            with self.subTest(requested=requested):
                self.assertIn('EXACT_MODEL_MISMATCH', {row['code'] for row in self.assess(requested_model=requested)['blockers']})

    def test_unknown_rule_and_bad_clause_shapes_fail_closed(self):
        for rule in ({'id': 'x', 'type': 'magic', 'confidence': 'stated'},
                     {'id': 'x', 'confidence': 'stated'},
                     {'id': 'x', 'type': 'requires', 'confidence': 'stated', 'if': {'field': 'supply', 'in': ['1'], 'not_in': ['1']}, 'then': {'field': 'supply', 'in': ['1']}},
                     {'id': 'x', 'type': 'max_per_chassis', 'confidence': 'stated', 'fields': ['unknown'], 'max': True, 'match_prefix': '1'}):
            product = record(); product['constraints'] = [rule]
            self.assertTrue(self.assess(product)['blockers'])

    def test_unresolved_widths_empty_fields_and_inference_block(self):
        for change, code in (({'fields': []}, 'NO_ORDERING_FIELDS'), ({'layout_verified': 'true'}, 'LAYOUT_NOT_VERIFIED'),
                             ({'doc_status': 'extracted_unverified'}, 'DOCUMENT_NOT_REVIEWED')):
            product = record(); product.update(change); self.assertIn(code, self.codes(product))
        product = record(); product['fields'][0]['width'] = None
        self.assertIn('FIELD_WIDTH_UNRESOLVED', self.codes(product))
        product = record(); product['source']['method'] = 'WebFetch LLM extraction'
        self.assertIn('EXTRACTION_REQUIRES_REVIEW', self.codes(product))

    def test_hash_tracks_any_mutation_and_manifest_mismatch_blocks_all_tracks(self):
        product = record(); digest = product_sha256(product)
        product['fields'][0]['name'] += 'µ'
        self.assertNotEqual(product_sha256(product), digest)
        result = self.assess(product, expected_product_sha256=digest)
        self.assertIn('PRODUCT_HASH_MISMATCH', {r['code'] for r in result['blockers']})
        self.assertEqual({row['status'] for row in result['tracks'].values()}, {'blocked'})

    def test_bad_types_nonfinite_json_and_unknown_keys_do_not_raise(self):
        for product in ([], 3, 'hello', {'fields': float('nan')}, {'model': []}, {'model': 'SEL-451-5', 'surprise': 1}):
            with self.subTest(product=product): self.assertTrue(self.assess(product)['blockers'])
        for field_value in (None, True, 1.5, [], {}):
            product = record(); product['fields'][0]['width'] = field_value
            self.assertIn('FIELD_WIDTH_UNRESOLVED', self.codes(product))
        product = record(); product['readiness_evidence']['layout_review']['reviewed_on'] = 'yesterday'
        self.assertIn('REVIEW_DATE_INVALID', self.codes(product))

    def test_source_hash_and_exact_release_are_required(self):
        for sha in (None, 'main', 'a' * 7, True):
            result = assess_catalog(record(), 'SEL-451-5', sha)
            self.assertIn('SOURCE_RELEASE_UNPINNED', {r['code'] for r in result['blockers']})
        product = record(); product['readiness_evidence']['golden_cases'] = []
        self.assertIn('GOLDEN_PROVENANCE_MISSING', self.codes(product))
        product = record(); product['readiness_evidence']['source_revision']['source_sha256'] = 'guessed'
        self.assertIn('REVIEW_SOURCE_HASH_INVALID', self.codes(product))

    def test_self_generated_golden_example_cannot_supply_provenance(self):
        product = record(); product['readiness_evidence']['golden_cases'][0]['source_type'] = 'generated_by_selpn'
        self.assertIn('GOLDEN_PROVENANCE_INADEQUATE', self.codes(product))
