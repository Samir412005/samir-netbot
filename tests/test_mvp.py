from concurrent.futures import ThreadPoolExecutor
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, func
from core import service as s
from core.db import Session
from core.models import User, Device, Offer, Command, Gift
from api.main import app, attempts

def setup_device():
    s.ensure_user(123)
    code=s.pairing(123)
    data=s.register(code,'test Android')
    with Session.begin() as db:
        o=Offer(name='SIMULATION ONLY',operator='TEST',size='none',price_points=0,category='internet',ussd='*000*000#',success_regex='SIMULATED_ACTIVATION_OK',enabled=True)
        db.add(o); db.flush(); bid=o.bid
    return data,bid

def test_gift_24h_and_unique():
    s.ensure_user(123)
    assert s.gift(123,86399)
    assert not s.gift(123,86401) # UTC midnight is not a new 24h window
    assert not s.gift(123,172798)
    assert s.gift(123,172799)
    with Session() as db:
        assert db.get(User,123).points==20
        assert db.scalar(select(func.count()).select_from(Gift))==2

def test_gift_concurrency():
    s.ensure_user(123)
    with ThreadPoolExecutor(max_workers=4) as pool: results=list(pool.map(lambda _:s.gift(123,200000),range(4)))
    assert results.count(True)==1
    with Session() as db: assert db.get(User,123).points==10

def test_pair_single_use_and_expiry(monkeypatch):
    s.ensure_user(123); code=s.pairing(123)
    s.register(code,'Android')
    with pytest.raises(ValueError): s.register(code,'again')
    code=s.pairing(123)
    original=s.now(); monkeypatch.setattr(s,'now',lambda:original+301)
    with pytest.raises(ValueError,match='invalid_or_expired'): s.register(code,'expired')

def test_no_linked_device():
    s.ensure_user(123)
    with pytest.raises(ValueError,match='no_linked_device'): s.create_command(123,1,None,'none')

def test_offline():
    data,bid=setup_device()
    with Session.begin() as db: db.get(Device,data['device_id']).last_seen=s.now()-61
    with pytest.raises(ValueError,match='device_offline'): s.create_command(123,bid,None,'offline')

@pytest.mark.parametrize('outcome,reply,state',[('response','SIMULATED_ACTIVATION_OK','success'),('response','Insufficient balance','fail'),('fail','USSD error -1','fail'),('timeout','No callback','timeout')])
def test_command_lifecycle_idempotency(outcome,reply,state):
    d,bid=setup_device()
    c=s.create_command(123,bid,None,'same')
    assert c.state=='queued'
    assert s.create_command(123,bid,None,'same').id==c.id
    delivered=s.poll(d['device_token']); assert delivered['id']==c.id
    assert s.poll(d['device_token']) is None
    assert s.result(d['device_token'],c.id,outcome,reply)==state
    assert s.result(d['device_token'],c.id,'response','SIMULATED_ACTIVATION_OK')==state
    with Session() as db:
        c=db.get(Command,c.id); assert c.state==state; assert c.response==reply

def test_timeout_no_late_success(monkeypatch):
    d,bid=setup_device(); c=s.create_command(123,bid,None,'timeout'); s.poll(d['device_token'])
    monkeypatch.setattr(s,'now',lambda:c.expires_at+1)
    assert s.result(d['device_token'],c.id,'response','SIMULATED_ACTIVATION_OK')=='timeout'
    assert s.poll(d['device_token']) is None

def test_queued_timeout(monkeypatch):
    d,bid=setup_device(); c=s.create_command(123,bid,None,'queued-timeout')
    monkeypatch.setattr(s,'now',lambda:c.expires_at+1)
    assert s.poll(d['device_token']) is None
    with Session() as db: assert db.get(Command,c.id).state=='timeout'

def test_ownership_revocation_mask():
    d,bid=setup_device(); c=s.create_command(123,bid,None,'owner'); s.poll(d['device_token'])
    s.ensure_user(456); other=s.register(s.pairing(456),'Other')
    with pytest.raises(ValueError,match='unknown_command'): s.result(other['device_token'],c.id,'response','anything')
    s.result(d['device_token'],c.id,'response','Call +213 555 123 456 for help')
    with Session() as db: assert '555' not in db.get(Command,c.id).response
    s.revoke(123,d['device_id'])
    with pytest.raises(ValueError,match='unauthorized'): s.poll(d['device_token'])

def test_api_https_auth_and_register_rate_limit(monkeypatch):
    attempts.clear()
    client=TestClient(app,base_url='https://testserver')
    assert client.get('/health').status_code==200
    assert client.get('/device/commands').status_code==401
    assert client.get('/device/commands',headers={'Authorization':'Bearer bad'}).status_code==401
    for _ in range(5): assert client.post('/device/register',json={'code':'000000'}).status_code==400
    assert client.post('/device/register',json={'code':'000000'}).status_code==429
    monkeypatch.setenv('ALLOW_HTTP_LOCAL','false')
    assert TestClient(app).get('/health').status_code==426

def test_api_simulated_device_roundtrip():
    attempts.clear(); client=TestClient(app,base_url='https://testserver')
    s.ensure_user(123); code=s.pairing(123)
    d=client.post('/device/register',json={'code':code,'name':'SIMULATED'}).json()
    with Session.begin() as db:
        o=Offer(name='TEST',operator='TEST',size='0',price_points=0,ussd='*000*000#',success_regex='SIMULATED_ACTIVATION_OK',enabled=True); db.add(o); db.flush(); bid=o.bid
    c=s.create_command(123,bid,None,'api-proof')
    h={'Authorization':'Bearer '+d['device_token']}
    assert client.get('/device/commands',headers=h).json()['command']['id']==c.id
    assert client.post('/device/result',headers=h,json={'command_id':c.id,'outcome':'response','response':'SIMULATED_ACTIVATION_OK'}).json()['state']=='success'

def test_banned_and_unconfigured():
    d,bid=setup_device()
    with Session.begin() as db: db.get(Offer,bid).enabled=False
    with pytest.raises(ValueError,match='offer_not_configured'): s.create_command(123,bid,None,'disabled')
    with Session.begin() as db: db.get(User,123).banned=True
    with pytest.raises(ValueError,match='unauthorized'): s.poll(d['device_token'])
