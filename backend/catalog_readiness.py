"""Read-only, fail-closed adapter for version-pinned SEL ordering evidence.

This module never imports KB tools, parses/assembles order codes, allocates
hardware or grants approval. Evidence recorded by a catalog remains evidence,
not a project-specific suitability decision.
"""
from datetime import date
from hashlib import sha256
import json
import re

CONTRACT_VERSION = 1
ADAPTER_VERSION = 'sel-catalog-readiness-1'
TRACKS = ('code_layout', 'hardware_compatibility', 'application_review')
ROOT_KEYS = {'model', 'family', 'category', 'prefix', 'prefix_note', 'source', 'doc_status',
             'layout_verified', 'fields', 'constraints', 'accessories', 'open_questions',
             'evidence', 'firmware_compat', 'catalog_contract_version', 'readiness_evidence'}
SOURCE_KEYS = {'doc_id', 'url', 'doc_date', 'method'}
FIELD_KEYS = {'id', 'name', 'width', 'confidence', 'options', 'order', 'note'}
OPTION_KEYS = {'code', 'desc', 'extra_cost', 'note'}
RULE_KEYS = {'id', 'type', 'if', 'then', 'confidence', 'note', 'fields', 'match_prefix', 'max'}
EVIDENCE_KEYS = {'source_revision', 'layout_review', 'golden_cases', 'hardware_review', 'application_review'}
REVIEW_KEYS = {'source_id', 'source_sha256', 'locator', 'reviewer', 'reviewed_on', 'model', 'revision', 'source_type'}
SHA40 = re.compile(r'^[0-9a-f]{40}$')
SHA64 = re.compile(r'^[0-9a-f]{64}$')
MODEL = re.compile(r'^SEL-[0-9A-Z]+(?:-[0-9A-Z]+)*$')
TOKEN = re.compile(r'^[A-Z0-9]+$')


def product_sha256(product):
    """Canonical semantic JSON hash, never a hash of executable KB tooling."""
    return sha256(json.dumps(product, sort_keys=True, separators=(',', ':'),
                             ensure_ascii=True, allow_nan=False).encode('utf-8')).hexdigest()


def assess_catalog(product, requested_model, source_release_sha, expected_product_sha256=None):
    """Inspect one raw KB product and return machine-readable evidence blockers.

    `source_release_sha` is the externally pinned source Git commit (40 lowercase
    hex); `expected_product_sha256`, when supplied, is the manifest's canonical
    product hash. Exact model matching has no family aliases or variant inference.
    Optional contract-v1 readiness_evidence contains documentary references only;
    this adapter checks their presence/shape, not their truth or engineering merit.
    """
    blockers = []
    def block(code, path, message, tracks=TRACKS):
        blockers.append({'code': code, 'path': path, 'message': message, 'tracks': list(tracks)})
    def mapping(value, path, keys, tracks=TRACKS):
        if not isinstance(value, dict):
            block('INVALID_TYPE', path, 'Expected an object.', tracks); return {}
        if 'note' in value and not isinstance(value['note'], str):
            block('INVALID_TYPE', path + '.note', 'Expected a string note.', tracks)
        if set(value) - keys:
            block('UNKNOWN_KEYS', path, 'Unsupported keys: ' + ', '.join(sorted(str(k) for k in set(value) - keys)), tracks)
        return value
    def text(value):
        return isinstance(value, str) and bool(value.strip())
    digest = None
    try:
        digest = product_sha256(product)
    except (TypeError, ValueError, OverflowError):
        block('INVALID_JSON_VALUE', '$', 'Product is not finite, JSON-serializable catalog data.')
    if not isinstance(source_release_sha, str) or not SHA40.fullmatch(source_release_sha):
        block('SOURCE_RELEASE_UNPINNED', 'source_release_sha', 'An exact lowercase 40-hex source Git commit is required.')
    if expected_product_sha256 is not None:
        if not isinstance(expected_product_sha256, str) or not SHA64.fullmatch(expected_product_sha256):
            block('INVALID_EXPECTED_HASH', 'expected_product_sha256', 'Expected a lowercase SHA-256 hash.')
        elif digest != expected_product_sha256:
            block('PRODUCT_HASH_MISMATCH', '$', 'Product does not match the pinned manifest hash.')
    product = mapping(product, '$', ROOT_KEYS)
    for key in ('family', 'category', 'prefix_note'):
        if key in product and not text(product[key]):
            block('INVALID_TYPE', key, 'Expected a nonempty string.')
    if 'evidence' in product and (not isinstance(product['evidence'], list) or any(not text(value) for value in product['evidence'])):
        block('INVALID_TYPE', 'evidence', 'Expected a list of evidence text.')
    if 'firmware_compat' in product:
        firmware = product['firmware_compat']
        if not isinstance(firmware, list) or any(not isinstance(pair, list) or len(pair) != 2
                or not text(pair[0]) or pair[1] is not None and not text(pair[1]) for pair in firmware):
            block('INVALID_TYPE', 'firmware_compat', 'Expected explicit firmware range pairs; an open upper bound may be null.')
    accessories = product.get('accessories')
    if not isinstance(accessories, list):
        block('INVALID_TYPE', 'accessories', 'An explicit accessory list is required.'); accessories = []
    for index, raw in enumerate(accessories):
        accessory = mapping(raw, f'accessories[{index}]', {'item', 'pn', 'in_code', 'extra_cost', 'note'})
        if not text(accessory.get('item')) or type(accessory.get('in_code')) is not bool or 'pn' not in accessory or accessory.get('pn') is not None and not text(accessory['pn']):
            block('INVALID_TYPE', f'accessories[{index}]', 'Expected accessory description, nullable string part number and boolean in_code.')
        if 'extra_cost' in accessory and type(accessory['extra_cost']) is not bool:
            block('INVALID_TYPE', f'accessories[{index}].extra_cost', 'Expected an exact boolean.')
    model = product.get('model')
    if not isinstance(requested_model, str) or not MODEL.fullmatch(requested_model):
        block('INVALID_REQUESTED_MODEL', 'requested_model', 'Use an exact SEL model identifier, without descriptions or family aliases.')
    if not isinstance(model, str) or model != requested_model:
        block('EXACT_MODEL_MISMATCH', 'model', 'Catalog model must exactly match the requested model; variants are not inferred.')
    if type(product.get('catalog_contract_version')) is not int or product.get('catalog_contract_version') != CONTRACT_VERSION:
        block('CONTRACT_VERSION_UNSUPPORTED', 'catalog_contract_version', 'Missing or unsupported catalog evidence contract version.')
    source = mapping(product.get('source'), 'source', SOURCE_KEYS)
    for key in ('doc_id', 'url', 'doc_date', 'method'):
        if not text(source.get(key)):
            block('SOURCE_PROVENANCE_INCOMPLETE', f'source.{key}', 'A source identifier, URL, revision/date and extraction method are required.')
    if text(source.get('url')) and not re.match(r'^https://(?:[a-z0-9-]+\.)*selinc\.com/', source['url']):
        block('MANUFACTURER_SOURCE_UNESTABLISHED', 'source.url', 'Manufacturer source URL is not an exact HTTPS SEL domain.')
    if text(source.get('method')) and re.search(r'llm|inferred|webfetch|automated', source['method'], re.I):
        block('EXTRACTION_REQUIRES_REVIEW', 'source.method', 'Automated or inferred extraction is not reviewed manufacturer evidence.')
    if product.get('doc_status') != 'manufacturer_reviewed':
        block('DOCUMENT_NOT_REVIEWED', 'doc_status', 'Document status does not establish a current manufacturer-reviewed catalog.')
    if product.get('layout_verified') is not True:
        block('LAYOUT_NOT_VERIFIED', 'layout_verified', 'Code layout is not recorded as verified.', ('code_layout',))
    prefix = product.get('prefix')
    if not isinstance(prefix, str) or not TOKEN.fullmatch(prefix):
        block('PREFIX_UNRESOLVED', 'prefix', 'An explicit manufacturer prefix is required.', ('code_layout',))
    fields = product.get('fields')
    if not isinstance(fields, list) or not fields:
        block('NO_ORDERING_FIELDS', 'fields', 'No complete ordering-field table is present.', ('code_layout', 'hardware_compatibility'))
        fields = []
    ids, orders, options_by_field = set(), [], {}
    for index, raw in enumerate(fields):
        path = f'fields[{index}]'
        field = mapping(raw, path, FIELD_KEYS, ('code_layout', 'hardware_compatibility'))
        fid = field.get('id')
        if not text(fid) or fid in ids:
            block('FIELD_ID_INVALID', path + '.id', 'Field IDs must be nonempty and unique.', ('code_layout', 'hardware_compatibility'))
        else:
            ids.add(fid)
        if not text(field.get('name')):
            block('FIELD_NAME_MISSING', path + '.name', 'Field name is required.', ('code_layout',))
        order = field.get('order')
        if type(order) is not int or order <= 0:
            block('FIELD_ORDER_UNRESOLVED', path + '.order', 'Field order must be a positive integer.', ('code_layout',))
        else:
            orders.append(order)
        width = field.get('width')
        if type(width) is not int or width <= 0:
            block('FIELD_WIDTH_UNRESOLVED', path + '.width', 'A positive, exact field width is required.', ('code_layout',))
        if field.get('confidence') not in ('stated', 'manufacturer_verified'):
            block('FIELD_EVIDENCE_UNVERIFIED', path + '.confidence', 'Confidence labels alone are not manufacturer verification.', ('code_layout', 'hardware_compatibility'))
        options = field.get('options')
        if not isinstance(options, list) or not options:
            block('FIELD_OPTIONS_MISSING', path + '.options', 'An explicit nonempty option table is required.', ('code_layout', 'hardware_compatibility')); options = []
        codes = set()
        for oi, raw_option in enumerate(options):
            opath = f'{path}.options[{oi}]'
            option = mapping(raw_option, opath, OPTION_KEYS, ('code_layout', 'hardware_compatibility'))
            code = option.get('code')
            if not isinstance(code, str) or not TOKEN.fullmatch(code) or code in ('UNRESOLVED', 'UNKNOWN', 'TBD') or code in codes:
                block('OPTION_CODE_INVALID', opath + '.code', 'Option codes must be explicit, unique manufacturer tokens.', ('code_layout', 'hardware_compatibility'))
            elif type(width) is int and width > 0 and len(code) != width:
                block('OPTION_WIDTH_MISMATCH', opath + '.code', 'Option token does not match its declared field width.', ('code_layout',))
            if isinstance(code, str): codes.add(code)
            if not text(option.get('desc')) or type(option.get('extra_cost')) is not bool:
                block('OPTION_METADATA_INVALID', opath, 'Description and exact boolean extra_cost are required.', ('code_layout',))
        if isinstance(fid, str): options_by_field[fid] = codes
    if orders != list(range(1, len(fields) + 1)):
        block('FIELD_ORDER_NONCONTIGUOUS', 'fields', 'Fields must be listed in unique contiguous manufacturer order.', ('code_layout',))
    constraints = product.get('constraints')
    if not isinstance(constraints, list):
        block('CONSTRAINTS_MISSING', 'constraints', 'An explicit constraint list is required.'); constraints = []
    rule_ids = set()
    for index, raw in enumerate(constraints):
        path = f'constraints[{index}]'
        rule = mapping(raw, path, RULE_KEYS)
        rid = rule.get('id')
        if not text(rid) or rid in rule_ids:
            block('RULE_ID_INVALID', path + '.id', 'Rule IDs must be nonempty and unique.')
        elif isinstance(rid, str): rule_ids.add(rid)
        if rule.get('confidence') not in ('stated', 'manufacturer_verified'):
            block('RULE_EVIDENCE_UNVERIFIED', path + '.confidence', 'Inferred or unreviewed constraints cannot establish compatibility.')
        if rule.get('type') == 'requires':
            for side in ('if', 'then'):
                clause = mapping(rule.get(side), path + '.' + side, {'field', 'in', 'not_in'})
                fid = clause.get('field')
                if not isinstance(fid, str) or fid not in ids:
                    block('RULE_FIELD_UNKNOWN', path + '.' + side, 'Rule references a missing field.')
                operators = set(clause) & {'in', 'not_in'}
                if len(operators) != 1:
                    block('RULE_OPERATOR_INVALID', path + '.' + side, 'Exactly one in/not_in operator is required.')
                for op in operators:
                    values = clause[op]
                    if not isinstance(values, list) or not values or any(not isinstance(v, str) for v in values):
                        block('RULE_VALUES_INVALID', path + '.' + side + '.' + op, 'Expected nonempty string option-code list.')
                    elif isinstance(fid, str) and any(value not in options_by_field.get(fid, set()) for value in values):
                        block('RULE_CODE_UNKNOWN', path + '.' + side, 'Rule references a code absent from the field option table.')
            if set(rule) & {'fields', 'match_prefix', 'max'}:
                block('RULE_SHAPE_INVALID', path, 'requires cannot contain max_per_chassis parameters.')
        elif rule.get('type') == 'max_per_chassis':
            refs = rule.get('fields')
            if not isinstance(refs, list) or not refs or any(not isinstance(fid, str) or fid not in ids for fid in refs):
                block('RULE_FIELD_UNKNOWN', path + '.fields', 'Every chassis rule field must exist.')
            if type(rule.get('max')) is not int or rule['max'] < 0 or not text(rule.get('match_prefix')) or set(rule) & {'if', 'then'}:
                block('RULE_SHAPE_INVALID', path, 'Invalid max_per_chassis parameters.')
        else:
            block('RULE_TYPE_UNSUPPORTED', path + '.type', 'Unknown or missing constraint types fail closed.')
    questions = product.get('open_questions')
    if not isinstance(questions, list) or any(not text(q) for q in questions):
        block('OPEN_QUESTIONS_INVALID', 'open_questions', 'An explicit string list is required.')
    elif questions:
        block('OPEN_QUESTIONS_REMAIN', 'open_questions', 'Catalog has unresolved questions; review their scope before use.')
    evidence = mapping(product.get('readiness_evidence'), 'readiness_evidence', EVIDENCE_KEYS)
    def review_reference(raw, path, tracks):
        ref = mapping(raw, path, REVIEW_KEYS, tracks)
        if any(not text(ref.get(key)) for key in REVIEW_KEYS - {'source_type'}) or ref.get('model') != model:
            block('REVIEW_PROVENANCE_INCOMPLETE', path, 'Require exact-model source ID, hash, locator, revision, reviewer and review date.', tracks)
        try:
            if not isinstance(ref.get('reviewed_on'), str):
                raise ValueError()
            date.fromisoformat(ref['reviewed_on'])
        except ValueError:
            block('REVIEW_DATE_INVALID', path + '.reviewed_on', 'Review date must be ISO YYYY-MM-DD.', tracks)
        if not isinstance(ref.get('source_sha256'), str) or not SHA64.fullmatch(ref['source_sha256']):
            block('REVIEW_SOURCE_HASH_INVALID', path + '.source_sha256', 'Reviewed source artifact requires a SHA-256 hash.', tracks)
    review_reference(evidence.get('source_revision'), 'readiness_evidence.source_revision', TRACKS)
    review_reference(evidence.get('layout_review'), 'readiness_evidence.layout_review', ('code_layout',))
    golden = evidence.get('golden_cases')
    if not isinstance(golden, list) or not golden:
        block('GOLDEN_PROVENANCE_MISSING', 'readiness_evidence.golden_cases', 'Manufacturer-backed, independently sourced golden-case references are required.', ('code_layout',))
    else:
        for index, case in enumerate(golden):
            review_reference(case, f'readiness_evidence.golden_cases[{index}]', ('code_layout',))
            if not isinstance(case, dict) or case.get('source_type') not in ('manufacturer_configurator', 'manufacturer_quote', 'approved_as_built'):
                block('GOLDEN_PROVENANCE_INADEQUATE', f'readiness_evidence.golden_cases[{index}].source_type',
                      'Self-generated examples and tests are not independent golden evidence. Identify a manufacturer configurator, quote or approved as-built source.', ('code_layout',))
    review_reference(evidence.get('hardware_review'), 'readiness_evidence.hardware_review', ('hardware_compatibility',))
    review_reference(evidence.get('application_review'), 'readiness_evidence.application_review', ('application_review',))
    tracks = {track: {'status': 'blocked' if any(track in b['tracks'] for b in blockers) else 'evidence_recorded',
                      'blocker_codes': sorted({b['code'] for b in blockers if track in b['tracks']})}
              for track in TRACKS}
    return {'adapter_version': ADAPTER_VERSION, 'contract_version': CONTRACT_VERSION,
            'requested_model': requested_model if isinstance(requested_model, str) else None,
            'catalog_model': model if isinstance(model, str) else None,
            'source_release_sha': source_release_sha if isinstance(source_release_sha, str) else None,
            'product_sha256': digest, 'hash_basis': 'canonical-json-utf8-sort-keys-compact-ensure-ascii-true',
            'tracks': tracks, 'blockers': blockers, 'catalog_evidence_only': True,
            'complete_fit': False, 'procurement_ready': False, 'order_code': None,
            'limitation': 'Documentary references are not independently authenticated. No code assembly, hardware allocation or application approval is performed.'}
