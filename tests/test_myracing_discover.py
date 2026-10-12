import copy
import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location('discover', Path(__file__).resolve().parents[1] / '.agents/skills/z24-race-manager/scripts/myracing_discover.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

class DiscoveryTests(unittest.TestCase):
    def fetcher(self, multiple=False):
        self.calls = []
        def fetch(flag, **p):
            self.calls.append((flag, p))
            if flag == 'get-race-list-group':
                items = [{'id': 1018, 'name': '2025 24小时耐力赛'}]
            elif flag == 'get-race-result-round-list':
                self.assertEqual(p['pid'], 1018)
                items = [{'id': 4322, 'name': '第七届'}]
            else:
                self.assertEqual(p['pid'], 4322)
                self.assertEqual(p['ssid'], 262)
                race = {'id': 2011448, 'name': '正赛', 'type': 3}
                if not p['itemId']:
                    items = [{'id': 77378, 'name': '耐力赛'}, {'id': 77377, 'name': '练习', 'ritems': [{'id': 9, 'name': '练习', 'type': 1}]}]
                else:
                    self.assertEqual(p['itemId'], 77378)
                    items = [{'id': 77378, 'name': '耐力赛', 'ritems': [race] + ([dict(race, id=2011449)] if multiple else [])}]
            return {'flag': 1, 'items': copy.deepcopy(items)}
        return fetch

    def test_full_chain_and_lazy_group(self):
        r = m.discover(262, 2025, fetch=self.fetcher())
        self.assertEqual(r['status'], 'ready')
        self.assertEqual([r['selected'][k] for k in ['race_id', 'round_id', 'pid']], [1018, 4322, 2011448])
        self.assertEqual(r['selected']['control_message']['pid'], 2011448)
        self.assertEqual(len(self.calls), 4)

    def test_missing_year_never_falls_back(self):
        r = m.discover(262, 2026, fetch=self.fetcher())
        self.assertEqual(r['status'], 'not_published')
        self.assertIsNone(r['selected'])
        self.assertEqual(len(self.calls), 1)

    def test_ambiguous_requires_selection(self):
        r = m.discover(262, 2025, fetch=self.fetcher(True))
        self.assertEqual(r['status'], 'ambiguous')
        self.assertIsNone(r['selected'])
        r = m.discover(262, 2025, session_id=2011449, fetch=self.fetcher(True))
        self.assertEqual(r['selected']['pid'], 2011449)

    def test_unknown_selection_not_queried_directly(self):
        r = m.discover(262, 2025, round_id=9999, fetch=self.fetcher())
        self.assertEqual(r['status'], 'not_ready')
        self.assertEqual(len(self.calls), 2)

    def test_auth_error_not_misreported_as_missing_race(self):
        with self.assertRaises(m.DiscoveryError):
            m.discover(262, 2026, fetch=lambda *a, **kw: {'flag': 0, 'msg': '请登录'})

    def test_schema_change_rejected(self):
        with self.assertRaises(m.DiscoveryError):
            m.discover(262, 2026, fetch=lambda *a, **kw: {'flag': 1, 'data': []})

if __name__ == '__main__':
    unittest.main()
