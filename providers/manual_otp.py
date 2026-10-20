from .base import TopupProvider, ActivationResult, Sku

class ManualOtpProvider(TopupProvider):
    name = 'manual_otp'

    def activate(self, msisdn: str, sku: Sku) -> ActivationResult:
        """Interface only. Operator/user owns this layer; we do not implement it.

        No OTP collection, operator session, undocumented API or activation is supplied.
        The user may independently implement an authorized adapter matching base.py.
        """
        raise NotImplementedError('هذا المسار غير مفعّل')
