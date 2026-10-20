from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Literal
import re

Status = Literal['success', 'failed', 'pending', 'unknown']

@dataclass(frozen=True)
class Sku:
    id: str
    operator_id: int = 0
    amount: str = '0'
    currency: str = ''
    country: str = 'DZ'
    use_local_amount: bool = False
    companion_bid: int = 0
    request_ref: str = ''
    user_id: int = 0

    def validate_reloadly(self):
        if self.operator_id <= 0 or not Decimal(self.amount).is_finite() or Decimal(self.amount) <= 0:
            raise ValueError('Invalid operator/amount')
        if not re.fullmatch('[A-Z]{2}', self.country):
            raise ValueError('Invalid ISO country')

@dataclass(frozen=True)
class ActivationResult:
    ref: str
    status: Status
    message: str
    raw_sanitized: dict = field(default_factory=dict)
    cost: str | None = None
    currency: str | None = None

    def __post_init__(self):
        if self.status not in ('success', 'failed', 'pending', 'unknown'):
            raise ValueError('Unknown activation status')

def sanitize(text):
    return re.sub(r'\+?\d(?:[\s().-]*\d){4,}', '[رقم مخفي]', str(text))[:3000]

class TopupProvider(ABC):
    name = 'base'

    @abstractmethod
    def activate(self, msisdn: str, sku: Sku) -> ActivationResult:
        """Dispatch at most once. A timeout after dispatch is UNKNOWN, never success."""
        raise NotImplementedError
