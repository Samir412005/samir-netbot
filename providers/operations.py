import hashlib
import json
import sqlite3
import time
from dataclasses import asdict, replace
from .base import ActivationResult

class Operations:
    def __init__(self, path='provider-operations.sqlite3', window='day'):
        self.path = str(path)
        if window not in ('hour', 'day'):
            raise ValueError('IDEMPOTENCY_WINDOW must be hour|day')
        self.seconds = 3600 if window == 'hour' else 86400
        with self._db() as db:
            db.execute('''CREATE TABLE IF NOT EXISTS activations(
                request_ref TEXT PRIMARY KEY, user INTEGER NOT NULL, offer TEXT NOT NULL,
                bucket INTEGER NOT NULL, created REAL NOT NULL, provider TEXT NOT NULL,
                status TEXT NOT NULL, cost TEXT, currency TEXT, result TEXT NOT NULL,
                UNIQUE(user,offer,bucket))''')
            db.execute('CREATE INDEX IF NOT EXISTS lookup_activation ON activations(user,offer,created)')

    def _db(self):
        db = sqlite3.connect(self.path, timeout=30)
        db.row_factory = sqlite3.Row
        return db

    def activate(self, provider, user, msisdn, sku, now=None):
        now = time.time() if now is None else now
        bucket = int(now) // self.seconds
        ref = 'sn-' + hashlib.sha256(f'{user}|{sku.id}|{bucket}'.encode()).hexdigest()[:24].translate(str.maketrans('0123456789abcdef','abcdefghijklmnop'))
        with self._db() as db:
            db.execute('BEGIN IMMEDIATE')
            old = db.execute('''SELECT result FROM activations WHERE user=? AND offer=? AND
                (bucket=? OR created>? OR status IN ('pending','unknown')) ORDER BY created DESC LIMIT 1''',
                (user, sku.id, bucket, now-self.seconds)).fetchone()
            if old:
                return ActivationResult(**json.loads(old['result']))
            pending = ActivationResult(ref, 'pending', 'محجوز مرة واحدة؛ لا تعاود الطلب حتى تتضح النتيجة.')
            db.execute('INSERT INTO activations VALUES(?,?,?,?,?,?,?,?,?,?)',
                (ref,user,sku.id,bucket,now,provider.name,'pending',None,None,json.dumps(asdict(pending))))
        # Reservation is durable before any network call. Crash leaves pending, never auto-replayed.
        try:
            result = provider.activate(msisdn, replace(sku, user_id=user, request_ref=ref))
            if not isinstance(result, ActivationResult):
                raise TypeError('Invalid provider result')
        except Exception:
            result = ActivationResult(ref,'unknown','تعذر تأكيد النتيجة؛ لا إعادة تلقائية.')
        with self._db() as db:
            db.execute('UPDATE activations SET status=?,cost=?,currency=?,result=? WHERE request_ref=?',
                (result.status,result.cost,result.currency,json.dumps(asdict(result)),ref))
        return result

    def reference(self, user, offer):
        with self._db() as db:
            row = db.execute('SELECT request_ref FROM activations WHERE user=? AND offer=? ORDER BY created DESC LIMIT 1',(user,offer)).fetchone()
            return row['request_ref'] if row else None

    def history(self, user, limit=50):
        with self._db() as db:
            return [dict(row) for row in db.execute('SELECT * FROM activations WHERE user=? ORDER BY created DESC LIMIT ?', (user,min(limit,50)))]

    def reconcile_reloadly(self, provider, user, request_ref):
        # Read-only status lookup; does not call activate or retry POST.
        with self._db() as db:
            row = db.execute('SELECT * FROM activations WHERE user=? AND request_ref=?', (user,request_ref)).fetchone()
        if not row or row['provider'] != 'reloadly':
            raise ValueError('Not a Reloadly operation owned by this user')
        old = ActivationResult(**json.loads(row['result']))
        result = provider.status(old.ref)
        if result.status == 'unknown' or old.status in ('success','failed'):
            return old
        result = replace(result,cost=result.cost or old.cost,currency=result.currency or old.currency)
        with self._db() as db:
            db.execute('UPDATE activations SET status=?,cost=?,currency=?,result=? WHERE request_ref=?',
                (result.status,result.cost,result.currency,json.dumps(asdict(result)),request_ref))
        return result
