import pytest
from fastapi.testclient import TestClient
from core import service
from core.db import Session
from core.models import Offer
from api.main import app, attempts

@pytest.fixture
def linked():
    attempts.clear(); service.ensure_user(123)
    d=service.register(service.pairing(123),'personal')
    return TestClient(app,base_url='https://testserver'),d

def test_learn_private_consent_and_real_pipeline(linked):
    client,d=linked; h={'Authorization':'Bearer '+d['device_token']}
    data={'name':'My manual code','operator':'MY-SIM','ussd':'*000*000#','idempotency_key':'learn-test-1','consent':False}
    assert client.post('/device/offers',headers=h,json=data).status_code==400
    data['consent']=True
    r=client.post('/device/offers',headers=h,json=data); assert r.status_code==200
    bid=r.json()['bid']; assert r.json()['scope']=='owner_only'
    assert client.post('/device/offers',headers=h,json=data).json()['bid']==bid
    with Session() as s:
        o=s.get(Offer,bid); assert o.owner_user_id==123; assert o.enabled; assert o.ussd==data['ussd']; assert o.price_points==0
    command=service.create_command(123,bid,None,'learn-activate')
    assert service.poll(d['device_token'])['ussd']==data['ussd']
    # Successful transport alone must never fabricate successful subscription activation.
    assert service.result(d['device_token'],command.id,'response','Network menu, choose option 1')=='fail'
    service.ensure_user(456); other=service.register(service.pairing(456),'Other')
    with pytest.raises(ValueError,match='offer_not_configured'): service.create_command(456,bid,None,'steal')

@pytest.mark.parametrize('code',['0555123456','OTP123456','*XXX#','*123#;*456#','tel:+213555123456',''])
def test_learn_rejects_non_ussd(linked,code):
    client,d=linked
    assert client.post('/device/offers',headers={'Authorization':'Bearer '+d['device_token']},json={'name':'N','operator':'O','ussd':code,'idempotency_key':'invalid-1','consent':True}).status_code==422
