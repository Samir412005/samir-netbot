from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select, func
from core.db import Session
from core.models import Offer
from core import service

router=APIRouter()
class LearnedOffer(BaseModel):
    name: str=Field(min_length=1,max_length=100)
    operator: str=Field(min_length=1,max_length=50)
    ussd: str=Field(min_length=2,max_length=80,pattern=r'^[*#][*#0-9]*#$')
    idempotency_key: str=Field(min_length=8,max_length=80)
    consent: bool

@router.post('/device/offers')
def learn(data: LearnedOffer, authorization: str | None=Header(default=None)):
    if not authorization or not authorization.startswith('Bearer '): raise HTTPException(401,'Missing device token')
    if not data.consent: raise HTTPException(400,'Explicit consent required')
    # Do not accept telephone numbers, dial strings with letters, or sequences of steps.
    # Only numeric single-shot USSD ending in #. No operator-app credentials involved.
    try:
        with Session.begin() as s:
            d=service.authenticate(s,authorization[7:]); d.last_seen=service.now()
            key=f'{d.user_id}:{data.idempotency_key}'
            o=s.scalar(select(Offer).where(Offer.learn_key==key))
            if not o:
                if s.scalar(select(func.count()).select_from(Offer).where(Offer.owner_user_id==d.user_id))>=50: raise HTTPException(400,'Personal offer limit reached')
                o=Offer(owner_user_id=d.user_id,learn_key=key,name=service.mask(data.name)[:100],operator=service.mask(data.operator)[:50],size='شخصي / Personnel',price_points=0,category='internet',ussd=data.ussd,success_regex='',enabled=True)
                s.add(o); s.flush(); service.audit(s,d.user_id,'learn_code_consent')
            return {'bid':o.bid,'scope':'owner_only','enabled':True,'activation_confirmation':'network_reply_only_until_operator_confirmation_is_configured'}
    except ValueError: raise HTTPException(401,'unauthorized') from None
