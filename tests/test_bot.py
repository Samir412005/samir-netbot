import asyncio
from types import SimpleNamespace
from core import service
from core.db import Session
from core.models import Offer
from bot.main import AR, FR, keyboard, menu

class Message:
    def __init__(self,uid,text):
        self.from_user=SimpleNamespace(id=uid)
        self.chat=SimpleNamespace(type='private')
        self.text=text
        self.answers=[]
    async def answer(self,text,**kwargs): self.answers.append((text,kwargs))

def test_keyboard_and_learned_catalog_isolation():
    service.ensure_user(123)
    service.ensure_user(456)
    with Session.begin() as s:
        s.add(Offer(name='PRIVATE-123',operator='TEST',size='0',price_points=0,category='internet',ussd='*000*000#',success_regex='',enabled=True,owner_user_id=123))
    assert [r[0].text for r in keyboard(123).keyboard[:6]]==AR
    assert len(FR)==6
    own=Message(123,AR[2]); asyncio.run(menu(own))
    assert 'PRIVATE-123' in own.answers[0][1]['reply_markup'].inline_keyboard[0][0].text
    other=Message(456,AR[2]); asyncio.run(menu(other))
    assert 'reply_markup' not in other.answers[0][1]
