"""Pure, versioned endpoint accounting and conservative nominal I/O screening.

Research examples are not approved project wiring or manufacturer configurations.
No client-supplied total, readiness state or installed capacity is accepted.
"""
from collections import defaultdict, deque
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import re
from uuid import NAMESPACE_URL, uuid5

from .assessment import assess
from .analog_screening import analog_screening, SOURCE_SHA256 as ANALOG_SOURCE_SHA256
from .relay_catalog import CATALOG
from .catalog_package import catalog_package
from .engine import analyze
from .options import device_requirements

DATA = Path(__file__).with_name('data')
MANIFEST = json.loads((DATA / 'ledger_manifest.json').read_text())
PATTERNS = [row for n in range(4) for row in json.loads((DATA / f'ledger_patterns_{n}.json').read_text())]
EDITOR = json.loads((DATA / 'editor_matrix.json').read_text())
VERSION = 'endpoint-budget-3'
SOLVER_SOURCE_SHA256 = sha256(Path(__file__).read_bytes()).hexdigest()
DOCUMENTS = {
    'SLD': 'Approved protection one-line', 'AC': 'Approved CT/VT three-line and core assignments',
    'TRIP': 'Approved cause-and-effect trip matrix', 'BF': 'Breaker-failure initiation/retrip/escalation diagram',
    'DC': 'Breaker trip/close DC elementary', 'DC86': 'Lockout DC schematic/contact development',
    'LOGIC': 'Protection logic and settings requirements', 'IO': 'Hardwired/SCADA I/O schedule',
    'OEM': 'Transformer/breaker OEM schematic', 'NET': 'Network/SCL design',
    'TEL': 'Teleprotection demarcation and remote interface',
    'REMOTE AC': 'Remote utility three-line', 'REMOTE DC': 'Remote breaker/control elementary',
    'VENDOR': 'Exact relay card specifications and terminal drawings',
}
CATEGORIES = ('trip', 'breaker_failure', 'status', 'mechanical', 'control', 'supervision', 'alarms', 'interlocks', 'communications')


def reserve(used, percent, basis):
    numerator, denominator = ((used * (100 + percent), 100) if basis == 'used' else (used * 100, 100 - percent))
    return (numerator + denominator - 1) // denominator


def allocate_contacts(demands, resources):
    """Integer max-flow on capability groups: a physical contact is spent once.

    Demand classes are conjunctive (coil AND fast, for example). Resources with
    unknown properties must not be passed as proof of those properties.
    """
    graph = defaultdict(dict)
    def edge(a, b, capacity):
        graph[a][b] = capacity
        graph[b].setdefault(a, 0)
    total = sum(d['quantity'] for d in demands)
    for i, demand in enumerate(demands):
        edge('source', ('d', i), demand['quantity'])
        for j, resource in enumerate(resources):
            if set(demand['classes']) <= set(resource['capabilities']):
                edge(('d', i), ('r', j), total)
    for j, resource in enumerate(resources):
        edge(('r', j), 'sink', resource['quantity'])
    flow = 0
    while True:
        parent = {'source': None}
        queue = deque(['source'])
        while queue and 'sink' not in parent:
            node = queue.popleft()
            for target, capacity in graph[node].items():
                if capacity > 0 and target not in parent:
                    parent[target] = node; queue.append(target)
        if 'sink' not in parent:
            break
        amount, node = total, 'sink'
        while parent[node] is not None:
            amount = min(amount, graph[parent[node]][node]); node = parent[node]
        node = 'sink'
        while parent[node] is not None:
            previous = parent[node]
            graph[previous][node] -= amount; graph[node][previous] += amount; node = previous
        flow += amount
    allocations = []
    for i, demand in enumerate(demands):
        for j, resource in enumerate(resources):
            used = graph[('r', j)].get(('d', i), 0)
            if used:
                allocations.append({'demand_group': i, 'resource_group': j, 'quantity': used})
    return {'feasible': flow == total, 'required_contacts': total, 'allocated_contacts': flow,
            'allocations': allocations}


def signature(signal):
    return [signal['name'], signal['source'], signal['destination'], signal['method'], signal['di'], signal['do'],
            signal['coil'], signal['included'], signal['reference'], signal['condition']]


def editor_signal(row, index):
    name, source, destination, method, di, output, coil, included, reference, condition = row
    return dict(id=index, name=name, source=source, destination=destination, method=method, di=di, do=output,
                coil=coil, included=included, reference=reference, condition=condition)


def row_signature(row):
    return [row['signal'], row['source'], row['destination'], row['method'], int(row['dst_ied_di']), int(row['src_ied_do']),
            row['output_duty'] == 'trip_or_lockout_coil', row['counted'] == '1', row['source_drawing_or_spec'], row['inclusion_condition']]


def category(row):
    name = row['name'].lower()
    if row['method'] in ('GOOSE', 'teleprotection', 'SCADA message'): return 'communications'
    if 'bfi' in name or '86bf' in name or 'retrip' in name: return 'breaker_failure'
    if '52a' in name or '52b' in name or 'indication' in name: return 'status'
    if 'watchdog' in name or 'alarm' in name: return 'alarms'
    if 'block close' in name or 'close' in name: return 'interlocks'
    if 'trip' in name or 'operate' in name: return 'trip'
    return 'supervision'


EXTENDED_SCHEMES = {'redundant_separate', 'dual_combined', 'combined_separate_secondary'}
EDITABLE_METHODS = {'hardwired', 'GOOSE', 'SCADA message', 'internal', 'teleprotection', 'hardwired or communicated'}


def reference_rows(case):
    return [dict(zip(MANIFEST['fields'], PATTERNS[index])) for index in MANIFEST['cases'][case]]


def expanded_case(study, scheme, variant):
    """Derive an unreviewed reference wiring example, preserving its source rows.

    A copied bus/combined path is a proposed second system, not evidence of
    independent CT cores, trip coils, DC, BF hosting or utility acceptance.
    """
    suffix = f"{variant}.L{int(study['include_poi_line'])}"
    original = f"{'SEP' if scheme == 'redundant_separate' else 'COMB_ASYM'}.{suffix}"
    entry = deepcopy(EDITOR['cases'][original])
    rows = reference_rows(original)
    for index, row in enumerate(rows):
        row['template_source'] = f'{original}.{index + 1:05}'
    cards = [deepcopy(EDITOR['cards'][index]) for index in entry['cards']]
    if scheme == 'dual_combined':
        # Replace the entire transformer-only Secondary path; retaining any
        # T-S analog or digital rows would misstate its combined-zone demand.
        rows = [row for row in rows if not ('T-S' in (row['source'], row['destination'], row['owner'])
                or '87T-S' in row['signal'] or '87T-S' in row['source'] or '87T-S' in row['destination'])]
        cards = [row for row in cards if row[0] != 'T-S']
        templates = [(i, row) for i, row in enumerate(reference_rows(original))
                     if 'T-P' in (row['source'], row['destination'], row['owner'])
                     or '87TB-P' in row['signal'] or '87TB-P' in row['source'] or '87TB-P' in row['destination']]
        if variant == 'LOCAL_H':
            # LOCAL_H keeps the sole HV BF host in Primary. Cloning every
            # T-P endpoint would also clone its BF current/retrip/timer/DTT
            # logic and accidentally resurrect the old transformer-only BFI.
            templates = [(i, row) for i, row in templates
                         if not row['signal'].startswith('H BF')
                         and row['signal'] not in ('H 52a', 'H 52b', '87TB-P BFI H', '87T-S BFI H')]
            for index, template in enumerate(reference_rows(original)):
                if template['signal'] == '87T-S BFI H':
                    inbound = deepcopy(template)
                    for key in ('signal', 'source', 'destination', 'owner'):
                        inbound[key] = inbound[key].replace('87T-S', '87TB-S')
                    inbound['template_source'] = f'{original}.{index + 1:05}'
                    inbound['authority'] = 'derived_reference_template_unreviewed'
                    inbound['notes'] = 'Derived combined Secondary BFI into the sole Primary-hosted HV BF logic. Independent trip/DC and lockout interfaces remain unverified.'
                    rows.append(inbound)
        replacements = [('87TB-P', '87TB-S'), ('T-P', 'T-S'), (':TC1', ':TC2')]
        source_case, source_alias, target_alias = original, 'T-P', 'T-S'
    else:
        source_case = f'SEP.{suffix}'
        templates = [(i, row) for i, row in enumerate(reference_rows(source_case))
                     if 'BUS' in (row['source'], row['destination'], row['owner'])
                     or '87B' in row['signal'] or '87B' in row['source'] or '87B' in row['destination']]
        replacements = [('87B', '87B-S'), ('BUS', 'BUS-S'), (':TC1', ':TC2')]
        source_alias, target_alias = 'BUS', 'BUS-S'
        entry['devices'].append(target_alias)
    for index, template in templates:
        row = deepcopy(template)
        for key in ('signal', 'source', 'destination', 'owner'):
            for before, after in replacements:
                row[key] = row[key].replace(before, after)
        if row['method'] == 'hardwired CT secondary':
            row['source'] += ':Secondary-core-unassigned'
        row['template_source'] = f'{source_case}.{index + 1:05}'
        row['authority'] = 'derived_reference_template_unreviewed'
        row['notes'] = (row['notes'] + ' Derived second-system example. Independent CT cores, DC, TC2 availability, '
                        'BF ownership and isolation are unverified; do not treat duplicated interfaces as approved wiring.').strip()
        rows.append(row)
    source_cards = EDITOR['cases'][source_case]['cards']
    for index in source_cards:
        card = deepcopy(EDITOR['cards'][index])
        if card[0] == source_alias:
            card[0] = target_alias
            cards.append(card)
    entry['card_rows'] = cards
    entry['full_rows'] = rows
    defaults = [editor_signal(row_signature(row), i) for i, row in enumerate(rows)
                if row['method'] in EDITABLE_METHODS
                and (row['source'] in entry['devices'] or row['destination'] in entry['devices'])]
    return f'{scheme.upper()}.{suffix}', entry, defaults


def wiring_inputs(study, scheme, settings):
    if scheme in EXTENDED_SCHEMES:
        case, entry, defaults = expanded_case(study, scheme, settings['variant'])
    else:
        prefix = {'dedicated': 'SEP', 'shared': 'SHARED', 'combined': 'COMB_ASYM'}[scheme]
        case = f"{prefix}.{settings['variant']}.L{int(study['include_poi_line'])}"
        entry = EDITOR['cases'][case]
        defaults = [editor_signal(EDITOR['signals'][idx], i) for i, idx in enumerate(entry['signals'])]
    signals = deepcopy(settings['edits'].get(settings['variant'], defaults))
    classes = settings['output_classes'].get(settings['variant'], {})
    valid_ids = {str(signal['id']) for signal in signals}
    if set(classes) - valid_ids:
        raise ValueError('Output classes reference a signal absent from this wiring case.')
    for signal in signals:
        if signal['method'] == 'internal' and (signal['source'] != signal['destination'] or signal['source'] not in entry['devices']):
            raise ValueError('Internal signals must stay within one modeled relay.')
    return case, entry, defaults, signals, classes


def validate_persisted_wiring(study, scheme, settings):
    for variant in {settings['variant'], *settings['edits'], *settings['output_classes']}:
        wiring_inputs(study, scheme, {**settings, 'variant': variant})


HARDWARE_GATES = (
    ('function_options', 'Exact model/function options and simultaneous element/input support'),
    ('analog_ratings', 'CT nominal rating/class, VT rating, neutral sensitivity and routing'),
    ('digital_electrical_duty', 'DI voltage/threshold and DO make/carry/break duty, speed, form and isolation'),
    ('joint_slot_allocation', 'Joint analog/digital card allocation, occupied slots and chassis size'),
    ('firmware_compatibility', 'Version-pinned firmware and supported card/function combinations'),
    ('ordering_symbols', 'Manufacturer-backed complete order code and accepted configuration'),
)


def joint_hardware_assessments(roles, analog, budgets, cards):
    """Expose the missing proof per role; never combine nominal capacities into fit."""
    results = []
    for role in roles:
        analog_result = next(row for row in analog if row['role_id'] == role['role_id'])
        digital = next((value for value in budgets.values() if value['role_id'] == role['role_id']), None)
        aliases = {alias for alias, value in budgets.items() if value['role_id'] == role['role_id']}
        digital_examples = [row for row in cards if row['device'] in aliases]
        results.append({
            'role_id': role['role_id'], 'role': role['role'], 'status': 'unresolved',
            'complete_fit': False, 'procurement_ready': False, 'order_code': None,
            'requirements': {'phase_ct_banks_min': analog_result['phase_banks_min'],
                             'phase_ct_banks_max': analog_result['phase_banks_max'],
                             'neutral_inputs': analog_result['neutral_inputs'], 'vt_banks': analog_result['vt_banks'],
                             'digital_budget': 'partial' if digital else 'not_enumerated',
                             'di_after_spares': digital['diRequired'] if digital else None,
                             'do_after_spares': digital['doRequired'] if digital else None},
            'analog_candidate_models': [row['model'] for row in analog_result['candidates']],
            'digital_example_models': sorted({row['model'] for row in digital_examples}),
            'evidence_gates': [{'code': code, 'state': 'not_verified', 'required_evidence': description}
                               for code, description in HARDWARE_GATES],
            'basis': 'Separate inherited analog and digital capacity examples. No exact joint configuration has been manufacturer-validated.',
        })
    known = {row['role_id'] for row in roles}
    for alias, budget in budgets.items():
        if budget['role_id'] in known:
            continue
        # Dedicated BF devices are ledger roles, not phase-demand roles in the
        # present topology model. No incidental CT row establishes their input
        # rating, current-check logic or simultaneous hardware allocation.
        results.append({
            'role_id': budget['role_id'], 'role': alias, 'status': 'unresolved',
            'complete_fit': False, 'procurement_ready': False, 'order_code': None,
            'requirements': {'phase_ct_banks_min': None, 'phase_ct_banks_max': None,
                             'neutral_inputs': None, 'vt_banks': None, 'digital_budget': 'partial',
                             'di_after_spares': budget['diRequired'], 'do_after_spares': budget['doRequired']},
            'analog_candidate_models': [],
            'digital_example_models': sorted({row['model'] for row in cards if row['device'] == alias}),
            'evidence_gates': [{'code': 'bf_current_detection', 'state': 'not_verified',
                                'required_evidence': 'BF current-check/52a logic, CT source/rating, retrip and escalation ownership'}]
                              + [{'code': code, 'state': 'not_verified', 'required_evidence': description}
                                 for code, description in HARDWARE_GATES],
            'basis': 'Dedicated breaker-failure analog demand is not enumerated. Reference ledger CT rows and digital counts do not establish a BF hardware configuration.',
        })
    return results


def engineering_io(request):
    study = request.study.model_dump()
    settings = request.settings.model_dump()
    analog_requirements = {key: value.model_dump() for key, value in request.analog_requirements.items()}
    assessment = assess(study)
    package = catalog_package()
    station_analysis = analyze(study)
    roles = device_requirements(study, request.scheme, station_analysis)
    catalog_hash = sha256(json.dumps(EDITOR, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    ledger_hash = sha256(json.dumps({'manifest': MANIFEST, 'patterns': PATTERNS}, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    fingerprint = sha256(json.dumps({'catalog_hash': catalog_hash, 'ledger_hash': ledger_hash, 'solver_source': SOLVER_SOURCE_SHA256,
                                    'assessment_fingerprint': assessment['input_fingerprint'], 'policy_version': assessment['policy_version'], 'study': study, 'scheme': request.scheme, 'settings': settings,
                                    'derived_role_requirements': roles, 'analog_requirements': analog_requirements, 'analog_source': ANALOG_SOURCE_SHA256, 'analog_catalog': CATALOG,
                                    'analog_catalog_source': sha256(Path(__file__).with_name('relay_catalog.py').read_bytes()).hexdigest(),
                                    'catalog_package_fingerprint': package['fingerprint'],
                                    'solver': VERSION, 'matrix': MANIFEST['source_sha256']},
                                   sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()
    base = {'catalog_readiness': package, 'schema_version': 1, 'solver_version': VERSION, 'matrix_version': MANIFEST['version'],
            'matrix_source_sha256': MANIFEST['source_sha256'], 'catalog_fingerprint': catalog_hash,
            'ledger_data_fingerprint': ledger_hash, 'solver_source_sha256': SOLVER_SOURCE_SHA256,
            'policy_version': assessment['policy_version'], 'request_fingerprint': fingerprint,
            'study_fingerprint': assessment['input_fingerprint'], 'scope': assessment['scope'],
            'budget_completeness': 'partial', 'code_status': 'not_generated', 'engineering_approval': 'unavailable',
            'engineering_prerequisites': next(row for row in station_analysis['candidates'] if row['id'] == request.scheme),
            'missing_evidence': ['Approved trip matrix, DC/OEM schematics and complete signal ownership',
                                 'DI voltage/threshold, output make/carry/break duty, speed, form and isolation',
                                 'Versioned module-slot/chassis/firmware compatibility and manufacturer confirmation'],
            'editor': None, 'devices': [], 'ledger': [], 'budgets': {}, 'card_examples': [], 'analog_assessments': [], 'hardware_assessments': []}
    if not assessment['scope']['reference_hardware_supported']:
        return {**base, 'status': 'unsupported'}
    case, entry, defaults, signals, classes = wiring_inputs(study, request.scheme, settings)
    analog_assessments = analog_screening(roles, study['auxiliary'], analog_requirements)
    primary = roles[0]
    aliases = {'T-P': primary, 'T-S': next(row for row in roles if row['kind'] in ('transformer', 'combined') and row['purpose'] == 'secondary')}
    for role in roles:
        if role['kind'] == 'bus': aliases['BUS-S' if role['purpose'] == 'secondary' else 'BUS'] = role
        if role['kind'] == 'line': aliases['LINE-H'] = role
        if role['kind'] == 'feeder':
            position = next(i for i, bay in enumerate(study['bays'], 1) if bay['uid'] == role['subject_id'])
            aliases[f'FP-F{position}'] = role
    for alias in entry['devices']:
        if alias in aliases: continue
        if alias == 'BF-H': subject, name = 'hv_breaker', 'POI breaker failure'
        elif alias.startswith('BF-F'):
            bay = study['bays'][int(alias[-1]) - 1]; subject, name = bay['uid'], f"{bay['id']} breaker failure"
        else: subject, name = alias, alias
        aliases[alias] = {'role_id': str(uuid5(NAMESPACE_URL, f"relay-wizard/{study['uid']}/{subject}/breaker_failure")), 'role': name}
    def label(alias):
        if alias in aliases: return aliases[alias]['role']
        return re.sub(r'\bF([123])\b', lambda match: study['bays'][int(match[1])-1]['id'], alias).replace(' H', ' POI breaker')
    def endpoint(alias):
        if alias in aliases:
            return {'alias': alias, 'id': aliases[alias]['role_id'], 'label': label(alias), 'kind': 'relay'}
        stable = re.sub(r'\bF([123])\b', lambda match: study['bays'][int(match[1])-1]['uid'], alias)
        return {'alias': alias, 'id': str(uuid5(NAMESPACE_URL, f"relay-wizard/{study['uid']}/external/{stable}")),
                'label': label(alias), 'kind': 'external'}
    full_rows = entry['full_rows'] if 'full_rows' in entry else reference_rows(case)
    full_index = {json.dumps(row_signature(row)): i for i, row in enumerate(full_rows)}
    default_row_ids = {signal['id']: full_index[json.dumps(signature(signal))] for signal in defaults}
    modified = {signal['id']: signal for signal in signals}
    # Omitted baseline rows are explicit exclusions, not silently lost interfaces.
    for signal in defaults:
        if signal['id'] not in modified: modified[signal['id']] = {**signal, 'included': False}
    ledger = []
    def emit(row, source_row_id, edited=None, original=None):
        if edited is not None:
            s = edited
            changed = original is None or signature(s) != signature(original)
        else:
            s = {'id': None, 'name': row['signal'], 'source': row['source'], 'destination': row['destination'],
                 'method': row['method'], 'di': int(row['dst_ied_di']), 'do': int(row['src_ied_do']),
                 'coil': row['output_duty'] == 'trip_or_lockout_coil', 'included': row['counted'] == '1',
                 'reference': row['source_drawing_or_spec'], 'condition': row['inclusion_condition']}
            changed = False
        active = s['included'] and s['method'] == 'hardwired'
        extra = classes.get(str(s['id']), []) if s['id'] is not None else []
        required_classes = sorted(set((['coil'] if s['coil'] else []) + extra))
        source, destination = endpoint(s['source']), endpoint(s['destination'])
        raw_external = None if changed else int(row['src_external_contact'])
        coil_circuits = None if changed else int(row['dst_coil_circuit'])
        external_inputs = None if changed else int(row['dst_external_discrete_input'])
        item = {**s, 'ledger_id': f'{case}:{source_row_id}', 'source_row_id': source_row_id,
                'owner': endpoint(s['source'] if changed else row['owner']), 'source_endpoint': source,
                'destination_endpoint': destination, 'output_classes': required_classes,
                'owner_state': 'unresolved' if changed else 'unreviewed',
                'authority': 'user_override_unreviewed' if changed else row['authority'],
                'evidence_state': 'unreviewed', 'project_drawing_verified': False,
                'source_documents_required': [{'tag': tag, 'document': DOCUMENTS.get(tag, tag), 'state': 'not_supplied'}
                                              for tag in s['reference'].split(';') if tag],
                'consumption': {'source_relay_do': s['do'] if active and source['kind'] == 'relay' else 0,
                                'destination_relay_di': s['di'] if active and destination['kind'] == 'relay' else 0,
                                'source_external_contacts': raw_external if active and source['kind'] == 'external' else 0,
                                'destination_coil_drives': coil_circuits if active else 0,
                                'destination_external_inputs': external_inputs if active else 0,
                                'destination_ct_channels': int(row['dst_ct_channels']) if not changed and s['included'] and s['method'] == 'hardwired CT secondary' else 0,
                                'destination_vt_channels': int(row['dst_vt_channels']) if not changed and s['included'] and s['method'] == 'hardwired VT secondary' else 0},
                'ct_channels': int(row['dst_ct_channels']) if not changed else None,
                'vt_channels': int(row['dst_vt_channels']) if not changed else None,
                'template_source': row.get('template_source'),
                'notes': row['notes'] if not changed else 'User edits require ownership, endpoint and electrical-duty review.'}
        item['category'] = category(item)
        ledger.append(item)
    overrides = {row_id: (modified[signal['id']], signal) for signal in defaults for row_id in [default_row_ids[signal['id']]]}
    for i, row in enumerate(full_rows):
        edited, original = overrides.get(i, (None, None))
        emit(row, f'{case}.{i+1:05}', edited, original)
    for signal in signals:
        if signal['id'] not in default_row_ids:
            emit({}, f'user.{signal["id"]}', signal)
    interface_counts = defaultdict(int)
    for row in ledger:
        if row['included']: interface_counts[json.dumps(signature(row))] += 1
    duplicate_interfaces = sum(count - 1 for count in interface_counts.values() if count > 1)
    budgets = {}
    for alias in entry['devices']:
        related = [row for row in ledger if alias in (row['source'], row['destination'])]
        di = sum(row['consumption']['destination_relay_di'] for row in related if row['destination'] == alias)
        demands = defaultdict(int)
        coil = other = 0
        for row in related:
            points = row['consumption']['source_relay_do'] if row['source'] == alias else 0
            if points:
                demands[tuple(row['output_classes'])] += points
                if row['coil']: coil += points
                else: other += points
        groups = [{'classes': list(key), 'used': used, 'quantity': reserve(used, settings['spare']['do'], settings['spare']['basis'])}
                  for key, used in sorted(demands.items())]
        checklist = [{'category': key, 'state': 'enumerated_unreviewed' if any(row['category'] == key for row in related) else 'unresolved',
                      'enumerated_rows': sum(row['category'] == key for row in related)} for key in CATEGORIES]
        analog_rows = [row for row in related if row['destination'] == alias and row['included'] and row['method'] in ('hardwired CT secondary', 'hardwired VT secondary')]
        analog_reference = {'ct_channels': sum(row['consumption']['destination_ct_channels'] for row in analog_rows),
                            'vt_channels': sum(row['consumption']['destination_vt_channels'] for row in analog_rows),
                            'ledger_ids': [row['ledger_id'] for row in analog_rows], 'evidence_state': 'illustrative_unreviewed',
                            'basis': 'Reference ledger only; conditional rows are not confirmed project requirements. Use the study phase envelope for screening.'}
        budgets[alias] = {'role_id': aliases[alias]['role_id'], 'analog_reference': analog_reference, 'completeness': 'partial', 'di': di, 'coil': coil, 'other': other, 'doUsed': coil + other,
                          'open': sum(row['included'] and row['method'] == 'hardwired or communicated' for row in related),
                          'diRequired': reserve(di, settings['spare']['di'], settings['spare']['basis']),
                          'doRequired': sum(g['quantity'] for g in groups),
                          'coilRequired': sum(g['quantity'] for g in groups if 'coil' in g['classes']),
                          'fastUsed': sum(g['used'] for g in groups if 'fast' in g['classes']),
                          'formCUsed': sum(g['used'] for g in groups if 'form_c' in g['classes']),
                          'fastRequired': sum(g['quantity'] for g in groups if 'fast' in g['classes']),
                          'formCRequired': sum(g['quantity'] for g in groups if 'form_c' in g['classes']),
                          'output_demands': groups, 'category_review': checklist,
                          'unresolved_endpoint_rows': sum(row['included'] and row['owner_state'] == 'unresolved' for row in related),
                          'complete_fit': False, 'ordering_block': 'Partial signal budget and unverified electrical/module evidence. Complete I/O fit and procurement release are unavailable.'}
    cards = []
    for card_row in entry.get('card_rows', [EDITOR['cards'][index] for index in entry['cards']]):
        alias, model, hardware, di, outputs, coil, status, gate, refs = card_row
        budget = budgets[alias]
        nominal = lambda value: int(value) if str(value).isdigit() else None
        capacities = {'di': nominal(di), 'do': nominal(outputs), 'coil': nominal(coil), 'fast': None, 'form_c': None}
        thresholds = {'di': budget['diRequired'], 'do': budget['doRequired'], 'coil': budget['coilRequired']}
        short = any(capacities[key] is not None and capacities[key] < required for key, required in thresholds.items())
        capacity_missing = any(capacities[key] is None for key in thresholds)
        class_missing = bool(budget['fastRequired'] or budget['formCRequired'])
        fit = ({'feasible': None, 'required_contacts': budget['doRequired'], 'allocated_contacts': None, 'allocations': []}
               if capacity_missing else allocate_contacts(budget['output_demands'], [
                   {'capabilities': ['coil'], 'quantity': capacities['coil']},
                   {'capabilities': [], 'quantity': capacities['do'] - capacities['coil']}]))
        if class_missing and not short:
            fit = {'feasible': None, 'required_contacts': budget['doRequired'], 'allocated_contacts': None, 'allocations': []}
        screening = ('insufficient_nominal' if short else 'function_unverified' if status != 'capacity_candidate'
                     else 'capacity_evidence_missing' if capacity_missing else 'class_evidence_missing' if class_missing
                     else 'within_nominal_counts')
        cards.append({'device': alias, 'model': model, 'hardware': hardware, 'capacities': capacities,
                      'screening': screening, 'nominal_allocation': fit,
                      'allocation_basis': 'Known nominal contact capabilities only; missing class evidence is unknown, not zero.',
                      'module_note': 'Digital cards are historical examples. Analog cards, occupied slots, chassis and function options have not been jointly validated.', 'evidence_state': 'historical_unverified_example',
                      'shortages': {key: None if capacities[key] is None else max(0, value-capacities[key]) for key, value in thresholds.items()},
                      'complete_fit': False, 'electrical_fit': 'unverified', 'module_compatibility': 'unverified',
                      'ordering_block': budget['ordering_block'], 'gate': gate, 'source_urls': [url.strip() for url in refs.split(';')],
                      'actual_spares': {'di_percent': None if not capacities['di'] or budget['di'] > capacities['di'] else 100*(capacities['di']-budget['di'])/capacities['di'],
                                        'coil_percent': None if not capacities['coil'] or budget['coil'] > capacities['coil'] else 100*(capacities['coil']-budget['coil'])/capacities['coil'],
                                        'fast_percent': None, 'form_c_percent': None,
                                        'do_percent': None if not capacities['do'] or budget['doUsed'] > capacities['do'] else 100*(capacities['do']-budget['doUsed'])/capacities['do']},
                      'over_capacity_used_points': {'di': None if capacities['di'] is None else max(0, budget['di']-capacities['di']),
                                                    'do': None if capacities['do'] is None else max(0, budget['doUsed']-capacities['do'])}})

    return {**base, 'status': 'partial', 'case_id': case,
            'ledger_findings': ([{'code': 'DUPLICATE_INTERFACE_ROWS', 'count': duplicate_interfaces, 'message': 'Repeated identical interfaces need review; they have not been silently deduplicated.'}] if duplicate_interfaces else []),
            'endpoint_count_basis': 'External contact and coil-drive counts are per interface. Multiple drives reaching one coil do not mean multiple physical coils.',
            'spare_policy': {**settings['spare'], 'rounding': 'ceil independently per mutually exclusive output capability group; no contact counted twice'},
            'editor': {'devices': entry['devices'], 'signals': signals},
            'devices': [{'alias': alias, **aliases[alias]} for alias in entry['devices']],
            'ledger': ledger, 'budgets': budgets, 'card_examples': cards, 'analog_assessments': analog_assessments,
            'wiring_basis': 'derived_reference_template_unreviewed' if request.scheme in EXTENDED_SCHEMES else 'historical_reference_example',
            'hardware_assessments': joint_hardware_assessments(roles, analog_assessments, budgets, cards)}
