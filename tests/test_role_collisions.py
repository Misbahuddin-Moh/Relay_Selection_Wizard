"""Equipment display labels cannot change semantic protection identities."""
from copy import deepcopy
from unittest import TestCase
from uuid import NAMESPACE_URL, uuid5

from fastapi.testclient import TestClient
from backend.main import app


class RoleCollisionTests(TestCase):
    def setUp(self):
        self.client = TestClient(app)
        self.addCleanup(self.client.close)
        self.study = self.client.get('/api/study').json()['study']
        self.study['auxiliary'] = 'excluded'

    def preview(self, study):
        result = self.client.post('/api/protection-preview', json=study)
        self.assertEqual(result.status_code, 200, result.text)
        return result.json()['options']

    def io(self, study, scheme):
        result = self.client.post('/api/engineering/io', json={
            'study': study, 'scheme': scheme,
            'settings': {'variant': 'LOCK', 'spare': {'di': 20, 'do': 20, 'basis': 'used'}},
        })
        self.assertEqual(result.status_code, 200, result.text)
        return result.json()

    def test_reserved_display_labels_never_replace_transformer_secondary(self):
        names = ['Transformer Secondary', 'Transformer Primary',
                 'Collector bus · single path', 'Transformer Primary + collector bus',
                 'POI line · local terminal', 'Revenue / power-quality meter · proposed POI']
        self.study['include_poi_line'] = True
        baseline = self.preview(self.study)
        baseline_feeders = {option['scheme']: next(row for row in option['device_requirements']
                            if row['kind'] == 'feeder' and row['subject_id'] == self.study['bays'][0]['uid'])
                            for option in baseline}
        for name in names:
            study = deepcopy(self.study)
            study['bays'][0]['id'] = name
            for option in self.preview(study):
                with self.subTest(name=name, scheme=option['scheme']):
                    rows = option['device_requirements']
                    secondary = next(row for row in rows if row['kind'] in ('transformer', 'combined') and row['purpose'] == 'secondary')
                    feeder = next(row for row in rows if row['kind'] == 'feeder' and row['subject_id'] == study['bays'][0]['uid'])
                    self.assertEqual(feeder['purpose'], 'primary')
                    self.assertEqual(feeder['role_id'], baseline_feeders[option['scheme']]['role_id'])
                    self.assertNotEqual(feeder['role_id'], secondary['role_id'])
                    self.assertEqual(len({row['role_id'] for row in rows}), len(rows))
                    ledger = self.io(study, option['scheme'])
                    ts = next(row for row in ledger['devices'] if row['alias'] == 'T-S')
                    fp = next(row for row in ledger['devices'] if row['alias'] == 'FP-F1')
                    self.assertEqual(ts['role_id'], secondary['role_id'])
                    self.assertEqual(ts['kind'], secondary['kind'])
                    self.assertEqual(fp['role_id'], feeder['role_id'])
                    self.assertEqual(ledger['budgets']['T-S']['role_id'], secondary['role_id'])
                    self.assertNotEqual(ledger['budgets']['T-S']['role_id'], ledger['budgets']['FP-F1']['role_id'])

    def test_normal_role_ids_remain_backward_compatible(self):
        for option in self.preview(self.study):
            for row in option['device_requirements']:
                expected = str(uuid5(NAMESPACE_URL, f"relay-wizard/{self.study['uid']}/{row['subject_id']}/{row['purpose']}"))
                self.assertEqual(row['role_id'], expected)
                self.assertEqual(row['purpose'], 'secondary' if row['role'] in ('Transformer Secondary', 'Transformer Secondary + collector bus', 'Collector bus Secondary') else 'primary')

    def test_secondary_label_rename_and_reorder_keep_feeder_identity(self):
        original = next(row for row in self.preview(self.study)[0]['device_requirements'] if row['kind'] == 'feeder')
        self.study['bays'][0]['id'] = 'Transformer Secondary'
        self.study['bays'].reverse()
        changed = next(row for row in self.preview(self.study)[0]['device_requirements'] if row['subject_id'] == original['subject_id'])
        self.assertEqual(changed['role_id'], original['role_id'])
        ledger = self.io(self.study, 'dedicated')
        fp = next(row for row in ledger['devices'] if row['alias'] == 'FP-F3')
        self.assertEqual(fp['role_id'], original['role_id'])
