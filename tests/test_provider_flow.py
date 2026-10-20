import tempfile
import unittest
from pathlib import Path
from providers import Operations
from providers.mock import MockProvider
from providers.base import sanitize
from bot.local_state import LocalState
from bot.provider_main import ProviderBot, OWNER

class TelegramMock:
    def __init__(self):
        self.requests=[]
    def request(self, method, url, headers=None, body=None, timeout=0):
        self.requests.append((url.rsplit('/',1)[-1],body))
        return 200, {'ok': True, 'result': True}

class FlowTests(unittest.TestCase):
    def bot(self, directory):
        b=object.__new__(ProviderBot)
        b.url='https://mock.invalid/botTEST/'
        b.http=TelegramMock()
        b.provider=MockProvider('success')
        b.ops=Operations(Path(directory)/'ops.sqlite3')
        b.local=LocalState(Path(directory)/'state.sqlite3')
        b.catalog_path=Path(directory)/'catalog.json'
        b.offers={'demo':{'enabled':True,'name':'MOCK','sku':{'id':'demo','amount':'1','currency':'USD'}}}
        b.recipients={}
        b.pending={}
        return b
    def cb(self,data,user=OWNER):
        return {'callback_query':{'id':'test','from':{'id':user},'data':data,'message':{'chat':{'id':OWNER,'type':'private'},'from':{'id':123}}}}

    def test_mock_telegram_confirmation_once(self):
        with tempfile.TemporaryDirectory() as d:
            b=self.bot(d)
            b.handle(self.cb('buy:demo'))
            self.assertEqual(b.ops.history(OWNER),[])
            key=next(iter(b.pending))
            b.handle(self.cb('confirm:'+key))
            b.handle(self.cb('confirm:'+key))
            rows=b.ops.history(OWNER)
            self.assertEqual(len(rows),1)
            self.assertEqual(rows[0]['status'],'success')
            self.assertEqual(sanitize(rows[0]['request_ref']),rows[0]['request_ref'])
            sent=[p for m,p in b.http.requests if m=='sendMessage']
            self.assertIn(rows[0]['request_ref'],sent[1]['text'])
            self.assertIn('استعمل من قبل',sent[2]['text'])

    def test_unauthorized_callback_and_admin_silent(self):
        with tempfile.TemporaryDirectory() as d:
            b=self.bot(d)
            b.handle(self.cb('buy:demo',999))
            b.handle({'message':{'from':{'id':999},'chat':{'id':OWNER,'type':'private'},'text':'/enable demo off'}})
            self.assertEqual(b.pending,{})
            self.assertEqual(b.http.requests,[])
            self.assertTrue(b.offers['demo']['enabled'])

    def test_cancel_does_not_activate(self):
        with tempfile.TemporaryDirectory() as d:
            b=self.bot(d)
            b.handle(self.cb('buy:demo'))
            key=next(iter(b.pending))
            b.handle(self.cb('cancel:'+key))
            b.handle(self.cb('confirm:'+key))
            self.assertEqual(b.ops.history(OWNER),[])
