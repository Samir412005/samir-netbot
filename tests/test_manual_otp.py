import unittest
from unittest.mock import patch
from providers.base import Sku
from providers.manual_otp import ManualOtpProvider
from providers.factory import from_env
from bot.provider_main import ProviderBot, OWNER

class ManualTests(unittest.TestCase):
    def test_interface_only(self):
        with self.assertRaises(NotImplementedError):
            ManualOtpProvider().activate('', Sku('demo'))

    def test_explicit_selection_and_default(self):
        with patch.dict('os.environ', {'PROVIDER': 'manual_otp'}, clear=True):
            self.assertIsInstance(from_env(), ManualOtpProvider)
        with patch.dict('os.environ', {}, clear=True):
            self.assertEqual(from_env().name, 'mock')

    def test_disabled_message(self):
        b = object.__new__(ProviderBot)
        b.provider = ManualOtpProvider()
        sent = []
        b.send = lambda text, markup=None: sent.append(text)
        b.handle({'message': {'from': {'id': OWNER}, 'chat': {'id': OWNER, 'type': 'private'}, 'text': '/start'}})
        self.assertEqual(sent, ['هذا المسار غير مفعّل'])
