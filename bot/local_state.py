import json
import re
import sqlite3
import time
from pathlib import Path
from providers.base import Sku, sanitize

class LocalState:
    def __init__(self, path):
        self.path = str(path)
        with self.db() as db:
            db.execute('CREATE TABLE IF NOT EXISTS wallet(user INTEGER PRIMARY KEY, points INTEGER NOT NULL, gift REAL)')
            db.execute('CREATE TABLE IF NOT EXISTS audit(id INTEGER PRIMARY KEY, at REAL, event TEXT)')

    def db(self):
        return sqlite3.connect(self.path, timeout=30)

    def points(self, user):
        with self.db() as db:
            row = db.execute('SELECT points FROM wallet WHERE user=?', (user,)).fetchone()
            return row[0] if row else 0

    def gift(self, user, now=None):
        now = time.time() if now is None else now
        with self.db() as db:
            db.execute('BEGIN IMMEDIATE')
            db.execute('INSERT OR IGNORE INTO wallet VALUES(?,0,NULL)', (user,))
            points, last = db.execute('SELECT points,gift FROM wallet WHERE user=?', (user,)).fetchone()
            if last is not None and now-last < 86400:
                return False, points
            db.execute('UPDATE wallet SET points=points+10,gift=? WHERE user=?', (now,user))
            return True, points+10

    def log(self, event):
        with self.db() as db:
            db.execute('INSERT INTO audit(at,event) VALUES(?,?)', (time.time(),sanitize(event)[:300]))
            db.execute('DELETE FROM audit WHERE id NOT IN (SELECT id FROM audit ORDER BY id DESC LIMIT 50)')

    def logs(self):
        with self.db() as db:
            return [r[0] for r in db.execute('SELECT event FROM audit ORDER BY id DESC LIMIT 50')]

def local_command(bot, text, user):
    if not hasattr(bot,'local'):
        return False
    if text == '/points':
        bot.send('نقاطك المحلية: '+str(bot.local.points(user))+' — ليست رصيد شحن ولا مالاً.')
    elif text == '/gift':
        ok, points = bot.local.gift(user)
        bot.local.log('gift granted' if ok else 'gift already claimed')
        bot.send(('زدنالك 10 نقاط. ' if ok else 'الهدية مرة كل 24 ساعة. ')+'المجموع: '+str(points))
    elif text == '/logs':
        bot.send('\n'.join(bot.local.logs()) or 'السجل فارغ')
    elif text == '/admin':
        bot.send('/points — النقاط\n/gift — هدية 24 ساعة\n/history — سجل التفعيل\n/logs — آخر 50 حدثاً\n/offer KEY JSON — حفظ عرض (موقوف افتراضياً)\n/enable KEY on|off — تفعيل/إخفاء عرض\n/5g و /snap — قريباً.\nالإدارة للمالك فقط؛ لا تضع أسراراً في المحادثة.')
    elif text in ('/5g','/snap'):
        bot.send('قريباً')
    elif text.startswith('/offer ') or text.startswith('/enable '):
        try:
            _, key, payload = text.split(maxsplit=2)
            if not re.fullmatch(r'[a-zA-Z0-9_-]{1,30}',key):
                raise ValueError()
            offers = dict(bot.offers)
            if text.startswith('/offer '):
                obj = json.loads(payload)
                if not isinstance(obj.get('name'),str) or not 1<=len(obj['name'])<=80:
                    raise ValueError()
                sku = Sku(**obj['sku'])
                if sku.id != key or sku.user_id or sku.request_ref:
                    raise ValueError()
                if bot.provider.name=='reloadly':
                    sku.validate_reloadly()
                offers[key] = {'name':obj['name'],'sku':obj['sku'],'enabled':False}
            else:
                if key not in offers or payload not in ('on','off'):
                    raise ValueError()
                offers[key] = dict(offers[key],enabled=payload=='on')
            path = bot.catalog_path
            tmp = Path(str(path)+'.tmp')
            tmp.write_text(json.dumps(offers,ensure_ascii=False),encoding='utf-8')
            tmp.replace(path)
            bot.offers = offers
            bot.pending.clear()
            bot.local.log('catalog updated')
            bot.send('حفظنا الكتالوج وألغينا التأكيدات القديمة. لا يوجد شحن بهذا الأمر.')
        except (ValueError,TypeError,KeyError,OSError):
            bot.send('إعداد غير صالح أو تعذر الحفظ؛ لم نغيّر الكتالوج في الذاكرة. استعمل /admin.')
    else:
        return False
    return True
