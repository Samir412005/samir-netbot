import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from bot.local_state import LocalState, local_command

class LocalTests(unittest.TestCase):
    def test_gift_persists_24_hours(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'state.sqlite3'
            s=LocalState(p)
            self.assertEqual(s.gift(1,100), (True,10))
            self.assertEqual(LocalState(p).gift(1,101),(False,10))
            self.assertEqual(s.gift(1,86500),(True,20))

    def test_logs_mask_and_limit(self):
        with tempfile.TemporaryDirectory() as d:
            s=LocalState(Path(d)/'state.sqlite3')
            for _ in range(60):
                s.log('number +213555000000')
            self.assertEqual(len(s.logs()),50)
            self.assertNotIn('213555000000',s.logs()[0])

    def test_admin_catalog_persists_and_cancels(self):
        with tempfile.TemporaryDirectory() as d:
            sent=[]
            b=SimpleNamespace(local=LocalState(Path(d)/'s.sqlite3'),provider=SimpleNamespace(name='mock'),offers={},pending={'old':1},catalog_path=Path(d)/'catalog.json',send=lambda t:sent.append(t))
            self.assertTrue(local_command(b,'/offer demo {"name":"demo","sku":{"id":"demo","amount":"1","currency":"USD"}}',1))
            self.assertFalse(b.offers['demo']['enabled'])
            local_command(b,'/enable demo on',1)
            self.assertTrue(b.offers['demo']['enabled'])
            self.assertEqual(b.pending,{})
            self.assertTrue(b.catalog_path.exists())
