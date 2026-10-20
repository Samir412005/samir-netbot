import os
import re
import time
from decimal import Decimal, InvalidOperation
from .base import ActivationResult, TopupProvider
from .http import Http

class ReloadlyProvider(TopupProvider):
    name = 'reloadly'
    AUTH = 'https://auth.reloadly.com/oauth/token'

    def __init__(self, client_id=None, client_secret=None, sandbox=True, live_enabled=False, http=None):
        self.client_id = client_id or os.getenv('RELOADLY_CLIENT_ID', '')
        self.client_secret = client_secret or os.getenv('RELOADLY_CLIENT_SECRET', '')
        self.sandbox = sandbox
        self.live_enabled = live_enabled
        self.base = 'https://topups-sandbox.reloadly.com' if sandbox else 'https://topups.reloadly.com'
        self.http = http or Http()
        self.token = None
        self.expires = 0

    def _headers(self):
        if not self.client_id or not self.client_secret:
            raise ValueError('Reloadly credentials missing')
        if not self.token or self.expires <= time.time():
            code, obj = self.http.request('POST', self.AUTH, body={
                'client_id': self.client_id, 'client_secret': self.client_secret,
                'grant_type': 'client_credentials', 'audience': self.base})
            if code != 200 or not isinstance(obj, dict) or not obj.get('access_token'):
                raise ValueError('Reloadly OAuth failed')
            self.token = obj['access_token']
            self.expires = time.time() + max(0, int(obj.get('expires_in', 0)) - 60)
        return {'Accept': 'application/com.reloadly.topups-v1+json', 'Authorization': 'Bearer ' + self.token}

    @staticmethod
    def _number(value):
        value = str(value).strip()
        if not re.fullmatch(r'\+[1-9][0-9]{7,14}', value):
            raise ValueError('E.164 recipient required in local configuration')
        return value[1:]

    def _result(self, obj, fallback):
        if not isinstance(obj, dict):
            obj = {}
        transaction = obj.get('transaction')
        transaction = transaction if isinstance(transaction, dict) else obj
        status = str(obj.get('status') or transaction.get('status', '')).upper()
        state = {'SUCCESSFUL': 'success', 'PROCESSING': 'pending', 'PENDING': 'pending',
                 'FAILED': 'failed', 'REFUNDED': 'failed'}.get(status, 'unknown')
        ref = str(transaction.get('transactionId') or obj.get('transactionId') or fallback)
        balance = transaction.get('balanceInfo') or {}
        balance = balance if isinstance(balance, dict) else {}
        cost, currency = None, None
        try:
            if balance.get('cost') is not None and Decimal(str(balance['cost'])).is_finite():
                cost = str(balance['cost'])
                currency = str(balance.get('currencyCode', ''))[:8]
        except (ValueError, InvalidOperation):
            pass
        # Deliberate allowlist: never persist raw recipientPhone, PIN, email, secrets or arbitrary error messages.
        safe = {'provider_status': status if status in ('SUCCESSFUL','PROCESSING','PENDING','FAILED','REFUNDED') else 'UNRECOGNIZED',
                'transaction_ref': ref, 'environment': 'sandbox' if self.sandbox else 'live',
                'cost': cost, 'currency': currency}
        prefix = 'SANDBOX — محاكاة وليست شحناً حقيقياً. ' if self.sandbox else ''
        message = prefix + {'success': 'أكد Reloadly نجاح الشحن؛ هذا ليس إثبات اشتراك USSD معين.',
            'failed': 'رفض/فشل أو استرجاع من المزود؛ راجع لوحة المعاملات قبل طلب جديد.',
            'pending': 'الشحن قيد المعالجة؛ لا تعاود الإرسال.',
            'unknown': 'النتيجة غير معروفة؛ راجع لوحة المزود قبل أي إعادة.'}[state]
        return ActivationResult(ref, state, message, safe, cost, currency)

    def activate(self, msisdn, sku):
        ref = sku.request_ref
        try:
            sku.validate_reloadly()
            number = self._number(msisdn)
            if not ref:
                raise ValueError('Idempotent request reference required')
            if not self.sandbox and not self.live_enabled:
                raise ValueError('Live charging disabled')
            headers = self._headers()
        except Exception:
            return ActivationResult(ref, 'failed', 'الإعداد أو OAuth غير صالح؛ لم نرسل طلب شحن.')
        payload = {'operatorId': sku.operator_id, 'amount': float(Decimal(sku.amount)),
                   'useLocalAmount': sku.use_local_amount, 'customIdentifier': ref,
                   'recipientPhone': {'countryCode': sku.country, 'number': number}}
        try:
            # NEVER retry a charge POST, including 401, 429, 5xx or socket timeout.
            code, obj = self.http.request('POST', self.base + '/topups', headers=headers, body=payload, timeout=30)
        except Exception:
            return ActivationResult(ref, 'unknown', 'انقطع الرد بعد محاولة الشحن؛ النتيجة غير معروفة، لا تعاود قبل مراجعة المزود.')
        if code in (400, 401, 403, 404, 422):
            if code == 401:
                self.token = None
            return ActivationResult(ref, 'failed', 'رفض Reloadly الطلب؛ لا إعادة تلقائية.', {'http_status': code})
        if not 200 <= code < 300:
            return ActivationResult(ref, 'unknown', 'حالة HTTP غير مؤكدة بعد الإرسال؛ تحقق من المزود.', {'http_status': code})
        return self._result(obj, ref)

    def status(self, ref):
        if not re.fullmatch(r'[0-9]+', str(ref)):
            return ActivationResult(str(ref), 'unknown', 'ما كاش transactionId؛ استعمل customIdentifier في لوحة المزود. لا تعاود الشحن.')
        try:
            code, obj = self.http.request('GET', self.base + '/topups/' + str(ref) + '/status', headers=self._headers())
            if code == 200:
                return self._result(obj, str(ref))
        except Exception:
            pass
        return ActivationResult(str(ref), 'unknown', 'تعذر التحقق من الحالة؛ لم نرسل شحناً جديداً.')

    def operators(self, country='DZ'):
        if not re.fullmatch('[A-Z]{2}', country):
            raise ValueError('ISO country required')
        return self.http.request('GET', self.base + '/operators/countries/' + country, headers=self._headers())
