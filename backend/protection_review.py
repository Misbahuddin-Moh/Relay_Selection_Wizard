"""Traceable deterministic review of the supported reference philosophies.

Measurement presence is distinct from suitable/independent CT cores, proven trip
paths, function support and owner acceptance. This module cannot grant approval.
"""
VERSION = 'protection-review-1'


def measurement_state(boundaries):
    states = [row['state'] for row in boundaries]
    return 'absent' if 'absent' in states else 'unknown' if not states or 'unknown' in states else 'present'


def protection_review(study, option, checked, coverage, roles, evidence):
    combined = option.scheme == 'combined'
    primary = next(row for row in roles if row['purpose'] == 'primary' and row['kind'] in ('transformer', 'shared', 'combined'))
    secondary = next(row for row in roles if row['kind'] == 'transformer' and row['purpose'] == 'secondary')
    modeled_zones = {row['id']: row for row in checked['zones']}
    zones = []
    def zone(identity, title, function, owners, boundaries, targets):
        zones.append({'id': identity, 'title': title, 'function': function, 'relay_roles': owners,
                      'boundaries': boundaries, 'measurement_status': measurement_state(boundaries),
                      'trip_targets': targets, 'clearing_state': 'unverified'})
    primary_zone = modeled_zones['combined' if combined else 'transformer']
    zone('transformer_primary', 'Extended transformer and collector bus Primary' if combined else 'Transformer Primary zone',
         '87TB' if combined else '87T', [primary['role']], primary_zone['boundaries'], primary_zone['trip_targets'])
    secondary_boundaries = coverage['transformer_b']['boundaries']
    # Without an assigned HV boundary, the LV CT alone cannot make an 87T zone.
    if coverage['transformer_b']['hv_boundary'] == 'unresolved':
        secondary_boundaries = [{'label': 'Independent Secondary HV CT assignment', 'state': 'unknown'}, *secondary_boundaries]
    zone('transformer_secondary', 'Transformer-only Secondary zone', '87T', [secondary['role']], secondary_boundaries, primary_zone['trip_targets'])
    if not combined:
        bus = next((row for row in roles if row['kind'] == 'bus'), primary)
        zone('bus', 'Collector bus zone', '87B', [bus['role']], modeled_zones['bus']['boundaries'], modeled_zones['bus']['trip_targets'])
    for row in roles:
        if row['kind'] == 'feeder':
            zone(f"feeder/{row['subject_id']}", f"{row['role']} feeder area", row['functions'], [row['role']],
                 row['measurement_sources'], [row['role']])
        elif row['kind'] == 'line':
            zone('line', 'Optional POI line zone', '87L', [row['role']], row['measurement_sources'], ['HV breaker', 'Remote breaker (unverified)'])
    primary_state = zones[0]['measurement_status']
    secondary_state = zones[1]['measurement_status']
    findings = []
    def finding(code, severity, title, detail, documents, keys=(), basis='unresolved_project_requirement'):
        sources = []
        for key in keys:
            for source in evidence[key]['sources']:
                if source not in sources:
                    sources.append(source)
        findings.append({'code': code, 'severity': severity, 'title': title, 'detail': detail,
                         'required_evidence': documents, 'sources': sources, 'basis': basis})
    if not checked['assessment']['scope']['reference_hardware_supported']:
        finding('OUTSIDE_REFERENCE_SCOPE', 'blocker', 'Outside the reference hardware scope',
                ' '.join(item['message'] for item in checked['assessment']['scope']['reasons']),
                ['Reviewed topology, measurement and clearing policy'], basis='modeled_fact')
    for identity, state, label in (('PRIMARY', primary_state, 'Primary'), ('SECONDARY', secondary_state, 'Secondary')):
        if state == 'absent':
            missing = ', '.join(row['label'] for row in zones[0 if identity == 'PRIMARY' else 1]['boundaries'] if row['state'] == 'absent')
            finding(f'MISSING_{identity}_MEASUREMENT', 'blocker', f'{label} measurement missing',
                    f'The proposed {label.lower()} zone has an absent modeled CT boundary: {missing}.', ['CT three-line and revised zone boundaries'], basis='modeled_fact')
        elif state == 'unknown':
            finding(f'UNKNOWN_{identity}_MEASUREMENT', 'open', f'{label} measurement assignment unresolved',
                    'Unknown or unassigned measurements cannot establish a usable differential zone.', ['CT core/terminal assignment schedule'], basis='modeled_fact')
    if any(z['measurement_status'] == 'absent' for z in zones[2:]):
        finding('MISSING_OTHER_ZONE_MEASUREMENT', 'blocker', 'Bus, feeder or line measurement missing',
                'At least one modeled bus, feeder or line zone has an absent CT source. Review the individual zones.', ['Zone diagram and CT three-line'], basis='modeled_fact')
    finding('CT_SUITABILITY_UNREVIEWED', 'open', 'CT presence does not establish suitability',
            'Positive counts record modeled presence only. Ratios, polarity, class, burden, saturation and terminal orientation have not been checked.',
            ['CT data sheets', 'AC three-line', 'Fault and CT performance study'], ('T_SEPARATE', 'B_FULL'))
    finding('CT_CORE_INDEPENDENCE_UNVERIFIED', 'open', 'Primary and Secondary independence is unverified',
            'Separate relay names and positive CT quantities do not prove independent cores, DC supplies, trip coils or wiring.',
            ['Core assignment schedule', 'Primary/Secondary DC and trip schematics', 'Owner redundancy requirements'], ('SHARED_IED',))
    finding('TRIP_CLEARING_UNVERIFIED', 'open', 'Trip targets are provisional',
            'HV and collector trip lists assume possible collector backfeed and no LV main. Breaker positions do not prove complete clearing or end-fault coverage.',
            ['Fault-source model', 'Cause-and-effect trip matrix', 'DC breaker schematics'], ('BF_LOCAL_REMOTE',))
    finding('BREAKER_FAILURE_UNRESOLVED', 'open', 'Breaker-failure hosting and escalation remain open',
            'For each breaker, confirm initiation, current detection, retrip, timer coordination, upstream/remote escalation and isolation of every remaining source.',
            ['BF logic and timing study', 'Trip matrix', 'Remote clearing agreement'], ('BF_LOCAL_REMOTE',))
    finding('LOCKOUT_WIRING_UNREVIEWED', 'open', 'Direct trip versus lockout is not an approved wiring choice',
            'The interface examples do not establish lockout contact development, reset policy, contact duty or separate trip paths.',
            ['86/DC elementary drawings', 'Contact duty and trip-coil data'], ('BF_LOCAL_REMOTE',))
    finding('OC_COORDINATION_UNRESOLVED', 'open', 'Time-graded backup requires a coordination study',
            'Feeder 51 and transformer/line backup functions are candidate functions. No pickup, delay, distance reach or IBR fault-response settings have been calculated.',
            ['Short-circuit and coordination studies', 'Inverter fault-response data', 'Utility protection requirements'], ('T_REF_BACKUP',))
    finding('REF_GROUNDING_UNRESOLVED', 'open', 'REF applicability requires winding and grounding evidence',
            'Neutral CT quantities alone do not establish REF applicability, sensitivity or CT assignment for a grounded winding.',
            ['Transformer vector group and grounding', 'Neutral/phase CT data and assignments'], ('T_REF_BACKUP',))
    finding('MANUFACTURER_CONFIGURATION_UNVERIFIED', 'open', 'Relay hardware and simultaneous functions remain unverified',
            'Published function candidates and nominal channel counts are not a validated model, module-slot allocation, firmware configuration or order code.',
            ['Exact manufacturer configuration and firmware', 'Terminal/slot drawings', 'Manufacturer application confirmation'], ('SHARED_IED',))
    finding('PARTIAL_SIGNAL_BUDGET', 'open', 'The signal budget is still partial',
            'Research examples and editable rows are not a complete approved project I/O schedule. Missing mechanical, supervision and control interfaces must be resolved.',
            ['Approved I/O schedule', 'OEM schematics', 'Project specifications'])
    finding('HV_BOUNDARY_COVERAGE_REVIEW', 'open', 'Selected HV cut changes breaker and lead coverage',
            next(row['coverage'] for row in checked['hv_boundaries'] if row['id'] == option.hv_boundary),
            ['Protection zone overlap and end-fault clearing review'], ('T_SEPARATE',), basis='modeled_fact')
    if option.scheme == 'shared':
        finding('SHARED_HARDWARE_COMMON_MODE', 'open', 'Separate zones share one Primary IED',
                '87T and 87B remain separate elements but share hardware. Verify simultaneous element/input support and assess common-mode loss against owner requirements.',
                ['Exact function options and input mapping', 'Owner redundancy requirements'], ('SHARED_IED',))
    if combined:
        finding('COMBINED_ZONE_DISCRIMINATION', 'open', 'The extended Primary zone reduces fault-location discrimination',
                'One Primary differential zone spans transformer and collector bus. Verify compensation, source grouping, inrush/security and sensitivity; the Secondary remains transformer-only.',
                ['Manufacturer application review', 'Sensitivity and external-fault study', 'Owner acceptance'], ('TB_COMBINED',))
    if study['auxiliary'] == 'unknown':
        finding('AUXILIARY_TREATMENT_UNKNOWN', 'open', 'Auxiliary tap treatment is unresolved',
                'The upper phase-bank case permits a measured tap; actual measurement and clearing treatment has not been established.', ['Auxiliary tap protection and isolation design'], ('B_FULL',))
    if study['include_poi_line']:
        finding('LINE_REMOTE_UNRESOLVED', 'open', '87L needs a verified remote pair and clearing path',
                'Remote CT data, peer compatibility, current channel, DTT disposition and remote breaker clearing remain unresolved. Received remote currents do not consume another local phase CT bank.',
                ['Remote AC/DC drawings', 'Relay-pair/channel design', 'Teleprotection and DTT agreement'], ('L_87L',))
    blockers = any(row['severity'] == 'blocker' for row in findings)
    readiness = ('outside_scope' if not checked['assessment']['scope']['reference_hardware_supported'] else 'blocked' if blockers else 'conditional')
    return {'version': VERSION, 'readiness': readiness,
            'primary_measurements': primary_state, 'secondary_measurements': secondary_state,
            'summary': {'blocked': 'An absent modeled measurement blocks at least one required protection path. Remaining evidence also needs review.',
                        'conditional': 'A preliminary philosophy comparison only. CT suitability, independence, clearing and manufacturer configuration remain unresolved.',
                        'outside_scope': 'Draft zone comparison only; this topology has no supported reference hardware configuration.'}[readiness],
            'zones': zones,
            'roles': [{'role_id': row['role_id'], 'role': row['role'], 'kind': row['kind'], 'functions': row['functions'],
                       'phase_banks_min': row['phase_banks'],
                       'phase_banks_max': (row['alternate_phase_banks'] or row['phase_banks']) + int(study['auxiliary'] == 'unknown' and row['kind'] in ('bus', 'shared', 'combined'))} for row in roles],
            'findings': findings,
            'assumptions': [{'code': 'SINGLE_TRANSFORMER_STRAIGHT_BUS', 'detail': 'One transformer and straight collector bus; no LV main breaker is modeled.', 'state': 'unconfirmed'},
                            {'code': 'COLLECTOR_BACKFEED', 'detail': 'Every modeled collector breaker is treated as a possible source path for provisional station trips.', 'state': 'unconfirmed'},
                            {'code': 'RESEARCH_NOT_PROJECT_APPROVAL', 'detail': 'Research citations are application guidance; no project-specific drawing or owner acceptance has been verified.', 'state': 'unconfirmed'}],
            'procurement_ready': False}
