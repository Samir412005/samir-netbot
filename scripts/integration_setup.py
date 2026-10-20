"""CI-only orchestrator: creates fictional offer; never shipped as an enabled catalog."""
import os
import pathlib
import time
from core.db import Session
from core.models import Offer
from core import service
root=pathlib.Path(os.environ['RUNNER_TEMP'])
service.ensure_user(900001)
(root/'pair.txt').write_text(service.pairing(900001))
with Session.begin() as s:
    o=Offer(name='CI SIMULATED ONLY',operator='TEST-NO-OPERATOR',size='0',price_points=0,category='internet',ussd='*000*000#',success_regex='SIMULATED_ACTIVATION_OK',enabled=True)
    s.add(o); s.flush(); bid=o.bid
for _ in range(180):
    if (root/'companion-ready').exists(): break
    time.sleep(1)
else: raise RuntimeError('Companion did not register')
c=service.create_command(900001,bid,None,'kotlin-jvm-integration')
print('CI simulation queued:',c.id)
