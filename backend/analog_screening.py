"""Backend-owned preliminary analog screening using inherited catalog examples.

No layout establishes simultaneous analog/digital slot compatibility or approval.
"""
from hashlib import sha256
from pathlib import Path

SOURCE_SHA256 = sha256(Path(__file__).read_bytes()).hexdigest()
T60_SOURCE = 'https://www.gevernova.com/grid-solutions/sites/default/files/resources/products/software/ur/GER-4976D.pdf'


def analog_screening(roles, auxiliary, requirements):
    known = {row['role_id'] for row in roles}
    if set(requirements) - known:
        raise ValueError('Analog requirements reference a role absent from the current scheme.')
    results = []
    for role in roles:
        entered = requirements.get(role['role_id'], {})
        neutral, vt = entered.get('neutral'), entered.get('vt')
        minimum = role['phase_banks']
        maximum = role['alternate_phase_banks'] or minimum
        if auxiliary == 'unknown' and role['kind'] in ('bus', 'shared', 'combined'):
            maximum += 1
        candidates = []
        for candidate in role['candidates']:
            layouts = []
            status = 'capacity_evidence_missing'
            if candidate['allocations']:
                # The catalog supplies phase capacities; input requirements are
                # applied only here so the browser cannot create another fit.
                for layout in candidate['allocations']:
                    if layout['phase_banks'] < minimum or (neutral is not None and layout['neutral_inputs'] < neutral) or (vt is not None and layout['vt_banks'] < vt):
                        continue
                    layouts.append({**layout, 'fit': 'All listed phase cases' if layout['phase_banks'] >= maximum else 'Lower phase demand only'})
                status = ('insufficient_modeled_capacity' if not layouts else 'requirements_unknown' if neutral is None or vt is None
                          else 'within_modeled_envelope' if any(row['phase_banks'] >= maximum for row in layouts) else 'lower_phase_case_only')
            t60_cases = []
            if candidate['model'].startswith('Multilin T60'):
                # Inherited three-module examples, not validated orderable
                # hardware. Ground-channel routing is deliberately unresolved.
                for banks in sorted({minimum, maximum}):
                    mixed = vt or 0
                    current = (max(0, banks - mixed) + 1) // 2
                    t60_cases.append({'phase_banks': banks, 'mixed_modules': mixed, 'current_only_modules': current,
                                      'module_count': mixed + current, 'within_three_module_example': mixed + current <= 3,
                                      'populated_phase_banks': mixed + 2 * current,
                                      'neutral_capacity': None, 'neutral_routing': 'unverified',
                                      'vt_requirement_known': vt is not None})
                status = ('insufficient_modeled_capacity' if all(not row['within_three_module_example'] for row in t60_cases)
                          else 'lower_phase_case_only' if not all(row['within_three_module_example'] for row in t60_cases)
                          else 'module_evidence_missing')
            candidates.append({'model': candidate['model'], 'manufacturer': candidate['manufacturer'], 'screening': status,
                               'layouts': layouts, 't60_cases': t60_cases, 'function_status': candidate['status'],
                               'complete_fit': False, 'module_compatibility': 'unverified', 'electrical_fit': 'unverified',
                               'evidence_state': 'inherited_unverified_example',
                               'source_urls': [candidate['source']] + ([T60_SOURCE] if t60_cases else []),
                               'ordering_block': 'Analog capacity examples do not validate CT core assignment, ratings, neutral routing, simultaneous functions, or analog/digital slots.'})
        results.append({'role_id': role['role_id'], 'role': role['role'],
                        'phase_banks_min': minimum, 'phase_banks_max': maximum,
                        'phase_channels_min': minimum * 3, 'phase_channels_max': maximum * 3,
                        'neutral_inputs': neutral, 'vt_banks': vt, 'requirements_state': 'unreviewed',
                        'phase_basis': 'Derived study boundaries; alternate input reuse and unknown auxiliary treatment remain separate phase cases.',
                        'measurement_sources': role['measurement_sources'], 'candidates': candidates,
                        'complete_fit': False})
    return results
