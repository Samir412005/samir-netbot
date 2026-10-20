import hashlib
import os
import re
import secrets
import time
import uuid
from sqlalchemy import delete, select, update
from sqlalchemy.exc import IntegrityError
from .db import Session
from .models import Audit, Command, Device, Gift, Offer, PairCode, User

TERMINAL = ('success', 'fail', 'timeout')
def now(): return int(time.time())
def digest(value): return hashlib.sha256(value.encode()).hexdigest()
def mask(text): return re.sub(r'\+?\d[\d ()-]{6,}\d', '[masked-number]', str(text))[:4000]
def audit(s, uid, event): s.add(Audit(user_id=uid, event=event, at=now()))

def ensure_user(uid, referrer=None):
    with Session.begin() as s:
        u = s.get(User, uid)
        if u is None:
            # Referral attribution only; no monetary or activation reward.
            parent = s.get(User, referrer) if referrer and referrer != uid else None
            u = User(id=uid, referrer=parent.id if parent else None)
            s.add(u)
            audit(s, uid, 'start')
        s.flush()
        return u

def gift(uid, at=None):
    t = now() if at is None else at
    try:
        with Session.begin() as s:
            u = s.scalar(select(User).where(User.id == uid).with_for_update())
            if not u or u.banned: raise ValueError('blocked')
            previous = s.scalar(select(Gift).where(Gift.user_id == uid).order_by(Gift.claimed_at.desc()).limit(1))
            if previous and t - previous.claimed_at < 86400: return False
            s.add(Gift(user_id=uid, day=t // 86400, claimed_at=t))
            s.flush()  # Unique day constraint handles concurrent SQLite claims.
            s.execute(update(User).where(User.id == uid).values(points=User.points + int(os.getenv('GIFT_POINTS', '10'))))
            audit(s, uid, 'daily_gift')
        return True
    except IntegrityError:
        return False

def pairing(uid):
    with Session.begin() as s:
        u = s.get(User, uid)
        if not u or u.banned: raise ValueError('blocked')
        s.execute(delete(PairCode).where(PairCode.user_id == uid))
        s.execute(delete(PairCode).where(PairCode.expires_at < now()))
        for _ in range(20):
            code = f'{secrets.randbelow(1000000):06d}'
            if s.get(PairCode, digest(code)) is None: break
        else: raise ValueError('try_later')
        s.add(PairCode(code_hash=digest(code), user_id=uid, expires_at=now()+300))
        audit(s, uid, 'pair_code')
        return code

def register(code, name):
    with Session.begin() as s:
        p = s.scalar(select(PairCode).where(PairCode.code_hash == digest(code)).with_for_update())
        if not p or p.expires_at < now(): raise ValueError('invalid_or_expired_code')
        u = s.get(User, p.user_id)
        if not u or u.banned: raise ValueError('blocked')
        # Consume atomically, including SQLite, before issuing a bearer credential.
        n = s.execute(delete(PairCode).where(PairCode.code_hash == p.code_hash, PairCode.expires_at >= now())).rowcount
        if n != 1: raise ValueError('code_used')
        token = secrets.token_urlsafe(32)
        d = Device(user_id=p.user_id, name=mask(name)[:80], token_hash=digest(token), last_seen=now())
        s.add(d); s.flush(); audit(s, p.user_id, 'device_registered')
        return {'device_id': d.id, 'device_token': token}

def expire(s):
    s.execute(update(Command).where(Command.state.in_(('queued','delivered')), Command.expires_at <= now()).values(state='timeout', reason='deadline_expired_unknown_network_outcome'))

def create_command(uid, bid, device_id, key):
    try:
        with Session.begin() as s:
            expire(s)
            u = s.scalar(select(User).where(User.id == uid).with_for_update())
            if not u or u.banned: raise ValueError('blocked')
            old = s.scalar(select(Command).where(Command.user_id == uid, Command.idempotency_key == key))
            if old: return old
            d = s.get(Device, device_id) if device_id else s.scalar(select(Device).where(Device.user_id == uid, Device.revoked == False).order_by(Device.last_seen.desc()).limit(1))
            if not d or d.user_id != uid or d.revoked: raise ValueError('no_linked_device')
            if d.last_seen < now() - int(os.getenv('ONLINE_SECONDS','60')): raise ValueError('device_offline')
            o = s.get(Offer, bid)
            if not o or not o.enabled or not o.success_regex or 'PLACEHOLDER' in o.ussd: raise ValueError('offer_not_configured')
            if s.scalar(select(Command.id).where(Command.device_id == d.id, Command.state.in_(('queued','delivered'))).limit(1)): raise ValueError('device_busy')
            if u.points < o.price_points: raise ValueError('insufficient_points')
            # Points are demo loyalty only; operator charges are separate and shown on the phone.
            if o.price_points:
                n = s.execute(update(User).where(User.id == uid, User.points >= o.price_points).values(points=User.points-o.price_points)).rowcount
                if not n: raise ValueError('insufficient_points')
            c = Command(id=str(uuid.uuid4()), user_id=uid, device_id=d.id, offer_id=o.bid, idempotency_key=key, ussd=o.ussd, offer_name=o.name, success_regex=o.success_regex, created_at=now(), expires_at=now()+int(os.getenv('COMMAND_TTL','180')))
            s.add(c); s.flush(); audit(s, uid, 'ussd_queued')
            return c
    except IntegrityError:
        with Session() as s:
            old = s.scalar(select(Command).where(Command.user_id == uid, Command.idempotency_key == key))
            if old: return old
        raise

def authenticate(s, token):
    d = s.scalar(select(Device).where(Device.token_hash == digest(token), Device.revoked == False))
    if not d or s.get(User, d.user_id).banned: raise ValueError('unauthorized')
    return d

def poll(token):
    with Session.begin() as s:
        d = authenticate(s, token)
        d.last_seen = now(); expire(s)
        c = s.scalar(select(Command).where(Command.device_id == d.id, Command.state == 'queued').order_by(Command.created_at).limit(1))
        if not c: return None
        # At most one delivery; never retry a delivered USSD on network loss.
        changed = s.execute(update(Command).where(Command.id == c.id, Command.state == 'queued').values(state='delivered')).rowcount
        if changed != 1: return None
        audit(s, d.user_id, 'ussd_delivered')
        return {'id': c.id, 'ussd': c.ussd, 'offer_name': c.offer_name, 'expires_at': c.expires_at}

def result(token, cid, outcome, response):
    with Session.begin() as s:
        d = authenticate(s, token); d.last_seen = now(); expire(s)
        c = s.get(Command, cid)
        if not c or c.device_id != d.id: raise ValueError('unknown_command')
        if c.state in TERMINAL: return c.state
        if c.state != 'delivered': raise ValueError('not_delivered')
        text = mask(response)
        state = 'timeout' if outcome == 'timeout' else 'fail'
        reason = 'network_or_user_failure'
        if outcome == 'response':
            # A callback is NOT evidence of subscription activation. Match only an operator-reviewed confirmation.
            state = 'success' if c.success_regex and re.search(c.success_regex, text, re.I) else 'fail'
            reason = 'confirmed_by_configured_response' if state == 'success' else 'activation_not_confirmed_check_network_reply'
        n = s.execute(update(Command).where(Command.id == cid, Command.state == 'delivered', Command.expires_at > now()).values(state=state, response=text, reason=reason)).rowcount
        if n: audit(s, d.user_id, 'ussd_'+state)
        else: state = s.get(Command, cid, populate_existing=True).state
        return state

def revoke(uid, did):
    with Session.begin() as s:
        s.execute(update(Device).where(Device.id == did, Device.user_id == uid).values(revoked=True))
        s.execute(update(Command).where(Command.device_id == did, Command.user_id == uid, Command.state == 'queued').values(state='fail', reason='device_revoked'))
        audit(s, uid, 'device_revoked')
