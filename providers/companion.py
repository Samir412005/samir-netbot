from .base import ActivationResult, TopupProvider

class CompanionProvider(TopupProvider):
    name = 'companion'

    def __init__(self, service=None):
        if service is None:
            from core import service
        self.service = service

    def activate(self, msisdn, sku):
        # Legacy paired companion bridge, NOT the standalone mobile-only polling app.
        # The standalone APK cannot accept commands from this Python process.
        try:
            if not sku.user_id or not sku.companion_bid or not sku.request_ref:
                raise ValueError('Companion user/bid/reference required')
            command = self.service.create_command(sku.user_id, sku.companion_bid, None, sku.request_ref)
        except ValueError:
            return ActivationResult(sku.request_ref, 'failed', 'المرافق القديم غير مربوط/غير متصل أو العرض غير مهيأ. يلزم الجسر والتطبيق وموافقة محلية؛ لم ندّعِ التفعيل.')
        state = {'success': 'success', 'fail': 'failed', 'timeout': 'unknown'}.get(command.state, 'pending')
        return ActivationResult(command.id, state, 'طلب المرافق: ' + state + '؛ التنفيذ يحتاج موافقة محلية على الهاتف.',
            {'command_state': command.state, 'operator_cost': 'unknown'})
