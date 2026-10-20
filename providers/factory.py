import os
from .mock import MockProvider
from .reloadly import ReloadlyProvider


def from_env():
    mode = os.getenv('PROVIDER', 'mock').lower()
    if mode == 'auto':
        # Select once BEFORE dispatch. Never fail over an uncertain charge to a second provider.
        mode = 'reloadly' if os.getenv('RELOADLY_CLIENT_ID') and os.getenv('RELOADLY_CLIENT_SECRET') else 'companion' if os.getenv('COMPANION_ENABLED') == 'true' else 'mock'
    if mode == 'manual_otp':
        from .manual_otp import ManualOtpProvider
        return ManualOtpProvider()
    if mode == 'mock':
        return MockProvider(os.getenv('MOCK_OUTCOME', 'success'))
    if mode == 'reloadly':
        return ReloadlyProvider(sandbox=os.getenv('RELOADLY_SANDBOX', 'true') != 'false', live_enabled=os.getenv('RELOADLY_LIVE_ENABLED') == 'true')
    if mode == 'companion':
        from .companion import CompanionProvider
        return CompanionProvider()
    raise ValueError('PROVIDER must be mock|reloadly|companion|auto')
