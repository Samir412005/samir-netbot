"""Optional provider bot: python -m bot.provider_main. Not part of mobile-only APK."""
import json
import os
import secrets
import time
from pathlib import Path
from providers import Operations, Sku, from_env
from providers.base import sanitize
from providers.http import Http

OWNER = 8178411819

def allowed(user, chat, chat_type):
    return user == OWNER and chat == OWNER and chat_type == 'private'

class ProviderBot:
    def __init__(self, http=None):
        token = os.environ['BOT_TOKEN']
        self.url = 'https://api.telegram.org/bot' + token + '/'
        self.http = http or Http()
        self.provider = from_env()
        self.ops = Operations(os.getenv('PROVIDER_DB', 'provider-operations.sqlite3'), os.getenv('IDEMPOTENCY_WINDOW', 'day'))
        self.offers = json.loads(Path(os.getenv('PROVIDER_CATALOG', 'providers/catalog.example.json')).read_text())
        self.recipients = json.loads(os.getenv('RECIPIENTS_JSON', '{}'))
        self.pending = {}
        self.offset_path = Path(os.getenv('PROVIDER_OFFSET', 'provider-offset.txt'))
        self.offset = int(self.offset_path.read_text()) if self.offset_path.exists() else 0

    def call(self, method, body):
        code, obj = self.http.request('POST',self.url+method,body=body,timeout=40)
        if code != 200 or not isinstance(obj,dict) or not obj.get('ok'):
            raise RuntimeError('Telegram request failed')
        return obj.get('result')

    def send(self, text, markup=None):
        body = {'chat_id': OWNER, 'text': sanitize(text)}
        if markup:
            body['reply_markup'] = markup
        self.call('sendMessage',body)

    def catalog(self):
        rows = [[{'text': sanitize(f"{o['name']} — مبلغ الطلب {o['sku']['amount']} {o['sku']['currency']}"),
                  'callback_data': 'buy:'+key}] for key,o in self.offers.items() if o.get('enabled')]
        self.send('المزود: '+self.provider.name+'\nMOCK وSANDBOX محاكاة فقط. الشحن live مدفوع، والتكلفة النهائية حسب المزود. اختار ثم أكد:', {'inline_keyboard': rows})

    def handle(self, update):
        callback = update.get('callback_query')
        message = (callback or {}).get('message') or update.get('message') or {}
        user = ((callback or {}).get('from') or message.get('from') or {}).get('id')
        chat = message.get('chat') or {}
        if not allowed(user,chat.get('id'),chat.get('type')):
            return
        self.pending = {k:v for k,v in self.pending.items() if v[1]>time.time()}
        if callback:
            try:
                self.call('answerCallbackQuery',{'callback_query_id': callback['id']})
            except Exception:
                pass
            data = callback.get('data','')
            if data.startswith('buy:'):
                key = data[4:]
                offer = self.offers.get(key)
                if not offer or not offer.get('enabled'):
                    return self.send('العرض غير مهيأ؛ لا يوجد أي تنفيذ.')
                confirmation = secrets.token_hex(12)
                self.pending[confirmation] = (key,time.time()+120)
                sku = offer['sku']
                mode = 'SANDBOX محاكاة' if getattr(self.provider,'sandbox',False) else self.provider.name
                return self.send(f"تأكيد: {offer['name']}\nالمزود: {mode}\nمبلغ الطلب: {sku['amount']} {sku['currency']}\nالرسوم/التكلفة النهائية حسب المزود، ليست نقاطاً مجانية. الرقم مضبوط محلياً وما نعرضوهش. هل توافق؟",
                    {'inline_keyboard': [[{'text':'أوافق على الطلب','callback_data':'confirm:'+confirmation}],[{'text':'إلغاء','callback_data':'cancel:'+confirmation}]]})
            if data.startswith('cancel:'):
                self.pending.pop(data[7:],None)
                return self.send('ألغي الطلب؛ ما أرسلنا حتى شحن.')
            if data.startswith('confirm:'):
                item = self.pending.pop(data[8:],None)
                if not item or item[1]<time.time():
                    return self.send('التأكيد انتهى أو استعمل من قبل.')
                offer = self.offers[item[0]]
                sku = Sku(**offer['sku'])
                recipient = self.recipients.get(str(user),'')
                if self.provider.name=='reloadly' and not recipient:
                    return self.send('رقم المستفيد غير مضبوط محلياً. ما نطلبوش رقم ولا OTP في Telegram؛ لا شحن.')
                result = self.ops.activate(self.provider,user,recipient,sku)
                return self.send(f"{self.provider.name}: {result.status}\nالمرجع: {result.ref}\nالتكلفة المؤكدة: {result.cost if result.cost is not None else 'غير معروفة'} {result.currency or ''}\n{result.message}")
        text = message.get('text','')
        if text.startswith('/history'):
            rows = self.ops.history(user)
            return self.send('\n\n'.join(f"{r['request_ref']} | {r['provider']} | {r['status']} | تكلفة {r['cost'] or 'غير معروفة'} {r['currency'] or ''}" for r in rows) or 'السجل فارغ')
        if text.startswith('/status '):
            if self.provider.name!='reloadly':
                return self.send('فحص الحالة هنا متاح لـReloadly؛ سجل المرافق في /history بالبوت القديم.')
            try:
                result = self.ops.reconcile_reloadly(self.provider,user,text.split(maxsplit=1)[1])
                return self.send(f'{result.status}\n{result.message}')
            except ValueError:
                return self.send('مرجع غير موجود لك.')
        self.catalog()

    def run(self):
        # This entrypoint must be the sole poller for this bot token.
        self.call('deleteWebhook',{'drop_pending_updates':False})
        while True:
            try:
                updates = self.call('getUpdates',{'offset':self.offset,'timeout':25,'allowed_updates':['message','callback_query']})
                for update in updates:
                    self.offset = update['update_id']+1
                    self.offset_path.write_text(str(self.offset))
                    self.handle(update)
            except Exception:
                # Never log a URL, token, credential, msisdn or raw provider payload.
                time.sleep(4)

if __name__ == '__main__':
    ProviderBot().run()
