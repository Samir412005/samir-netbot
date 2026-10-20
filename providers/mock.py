from .base import ActivationResult, TopupProvider

class MockProvider(TopupProvider):
    name = 'mock'

    def __init__(self, outcome='success'):
        if outcome not in ('success', 'fail', 'timeout', 'pending'):
            raise ValueError('Invalid MOCK_OUTCOME')
        self.outcome = outcome

    def activate(self, msisdn, sku):
        status = {'success': 'success', 'fail': 'failed', 'timeout': 'unknown', 'pending': 'pending'}[self.outcome]
        return ActivationResult(sku.request_ref or 'mock-test', status,
            'محاكاة MOCK فقط — لم يقع أي شحن ولا تفعيل حقيقي. ' + self.outcome,
            {'simulation': True, 'outcome': self.outcome}, cost='0', currency=sku.currency or None)
