import json
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch
from providers import Operations, Sku, from_env
from providers.mock import MockProvider
from providers.reloadly import ReloadlyProvider
from providers.companion import CompanionProvider
from bot.provider_main import allowed

SKU = Sku('example',operator_id=123,amount='5',currency='USD',country='DZ',request_ref='sn-test')
PHONE = '+213555000000'  # Synthetic test input; never sent to an external service.

class MockHttp:
    def __init__(self,replies): self.replies=list(replies);self.requests=[]
    def request(self,method,url,headers=None,body=None,timeout=20):
        self.requests.append((method,url,headers,body))
        reply=self.replies.pop(0)
        if isinstance(reply,Exception): raise reply
        return reply

def oauth(): return (200,{'access_token':'fake-test-token','expires_in':86400})
def success(): return (200,{'status':'SUCCESSFUL','transactionId':12,'recipientPhone':PHONE,'pinDetail':{'code':'secret-pin'},'balanceInfo':{'cost':4.8,'currencyCode':'USD'}})

class ProviderTests(unittest.TestCase):
    def setUp(self): self.tmp=tempfile.TemporaryDirectory();self.db=str(Path(self.tmp.name)/'ops.db')
    def tearDown(self): self.tmp.cleanup()
    def test_mock_success_fail_timeout(self):
        for mode,state in [('success','success'),('fail','failed'),('timeout','unknown')]:
            result=MockProvider(mode).activate('',SKU)
            self.assertEqual(result.status,state);self.assertTrue(result.raw_sanitized['simulation']);self.assertIn('MOCK',result.message)
    def test_request_oauth_and_topup(self):
        http=MockHttp([oauth(),success()]);p=ReloadlyProvider('fake-id','fake-secret',http=http)
        result=p.activate(PHONE,SKU)
        self.assertEqual(result.status,'success');self.assertEqual(result.cost,'4.8');self.assertIn('SANDBOX',result.message)
        auth=http.requests[0];self.assertEqual(auth[1],'https://auth.reloadly.com/oauth/token')
        self.assertEqual(auth[3]['audience'],'https://topups-sandbox.reloadly.com');self.assertEqual(auth[3]['grant_type'],'client_credentials')
        req=http.requests[1];self.assertEqual(req[0],'POST');self.assertTrue(req[1].endswith('/topups'))
        self.assertEqual(req[2]['Accept'],'application/com.reloadly.topups-v1+json')
        self.assertEqual(req[3],{'operatorId':123,'amount':5.0,'useLocalAmount':False,'customIdentifier':'sn-test','recipientPhone':{'countryCode':'DZ','number':PHONE[1:]}})
        self.assertNotIn(PHONE,json.dumps(result.raw_sanitized));self.assertNotIn('secret-pin',json.dumps(result.raw_sanitized))
    def test_timeout_no_retry(self):
        http=MockHttp([oauth(),TimeoutError()]);result=ReloadlyProvider('id','secret',http=http).activate(PHONE,SKU)
        self.assertEqual(result.status,'unknown');self.assertEqual(len(http.requests),2)
    def test_server_error_unknown(self):
        http=MockHttp([oauth(),(500,{})]);self.assertEqual(ReloadlyProvider('id','secret',http=http).activate(PHONE,SKU).status,'unknown')
    def test_oauth_failure_no_charge(self):
        http=MockHttp([(401,{})]);self.assertEqual(ReloadlyProvider('id','secret',http=http).activate(PHONE,SKU).status,'failed');self.assertEqual(len(http.requests),1)
    def test_live_guard_and_invalid_number(self):
        http=MockHttp([]);p=ReloadlyProvider('id','secret',sandbox=False,http=http)
        self.assertEqual(p.activate(PHONE,SKU).status,'failed');self.assertEqual(p.activate('invalid',SKU).status,'failed');self.assertEqual(http.requests,[])
    def test_processing_and_failure_mapping(self):
        for raw,state in [('PROCESSING','pending'),('REFUNDED','failed'),('FAILED','failed'),('something','unknown')]:
            p=ReloadlyProvider('id','secret',http=MockHttp([oauth(),(200,{'status':raw})]));self.assertEqual(p.activate(PHONE,SKU).status,state)
    def test_dedupe_persists_restart(self):
        class Counting(MockProvider):
            calls=0
            def activate(self,*a): self.calls+=1;return super().activate(*a)
        p=Counting();one=Operations(self.db).activate(p,1,'',SKU,now=100000)
        two=Operations(self.db).activate(p,1,'',SKU,now=100001)
        self.assertEqual(one,two);self.assertEqual(p.calls,1);self.assertEqual(len(Operations(self.db).history(1)),1)
    def test_unknown_blocks_across_days(self):
        ops=Operations(self.db);one=ops.activate(MockProvider('timeout'),1,'',SKU,now=100000)
        two=ops.activate(MockProvider('success'),1,'',SKU,now=100000+86400*10)
        self.assertEqual(one,two);self.assertEqual(two.status,'unknown')
    def test_rolling_hour_guard(self):
        ops=Operations(self.db,window='hour');one=ops.activate(MockProvider(),1,'',SKU,now=7199)
        self.assertEqual(one,ops.activate(MockProvider(),1,'',SKU,now=7201))
        self.assertNotEqual(one.ref,ops.activate(MockProvider(),1,'',SKU,now=10800).ref)
    def test_concurrent_reservation(self):
        ops=Operations(self.db)
        class Counting(MockProvider):
            calls=0
            def activate(self,*a): self.calls+=1;return super().activate(*a)
        p=Counting()
        with ThreadPoolExecutor(max_workers=5) as pool: list(pool.map(lambda _:ops.activate(p,1,'',SKU,now=100000),range(5)))
        self.assertEqual(p.calls,1);self.assertEqual(len(ops.history(1)),1)
    def test_no_failover_from_reloadly(self):
        with patch.dict('os.environ',{'PROVIDER':'auto','RELOADLY_CLIENT_ID':'fake','RELOADLY_CLIENT_SECRET':'fake'},clear=True):
            self.assertEqual(from_env().name,'reloadly')
        with patch.dict('os.environ',{'PROVIDER':'mock'},clear=True): self.assertEqual(from_env().name,'mock')
    def test_companion_never_fake_success(self):
        class Service:
            def create_command(self,*args): raise ValueError('no_linked_device')
        self.assertEqual(CompanionProvider(Service()).activate('',replace(SKU,user_id=1,companion_bid=1)).status,'failed')
    def test_whitelist(self):
        self.assertTrue(allowed(8178411819,8178411819,'private'));self.assertFalse(allowed(42,8178411819,'private'));self.assertFalse(allowed(8178411819,42,'group'))
    def test_readonly_reconcile(self):
        http=MockHttp([oauth(),(200,{'status':'PROCESSING','transactionId':12}),(200,{'status':'SUCCESSFUL','transactionId':12})])
        p=ReloadlyProvider('id','secret',http=http);ops=Operations(self.db)
        self.assertEqual(ops.activate(p,1,PHONE,SKU,now=100000).status,'pending')
        ref=ops.history(1)[0]['request_ref'];self.assertEqual(ops.reconcile_reloadly(p,1,ref).status,'success')
        self.assertEqual(http.requests[-1][0],'GET');self.assertTrue(http.requests[-1][1].endswith('/topups/12/status'))

if __name__=='__main__': unittest.main()
