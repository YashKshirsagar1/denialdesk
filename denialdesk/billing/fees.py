"""
Fee calculation for recovery outcomes.

Standard rate (default 22%): applies when denial_date is within aged_threshold_days.
Aged rate (default 32%): applies when denial_date is older than aged_threshold_days.
Both rates are configurable per practice contract.
"""
from decimal import Decimal, ROUND_HALF_UP
from datetime import date


def is_aged(denial_date: date | None, aged_threshold_days: int, reference_date: date | None = None) -> bool:
    if denial_date is None:
        return False
    ref = reference_date or date.today()
    return (ref - denial_date).days > aged_threshold_days


def calculate_fee(
    amount_recovered: Decimal,
    denial_date: date | None,
    fee_rate_standard: Decimal,
    fee_rate_aged: Decimal,
    aged_threshold_days: int,
) -> tuple[Decimal, bool, Decimal]:
    """Returns (fee_amount, is_aged_flag, rate_applied)."""
    aged = is_aged(denial_date, aged_threshold_days)
    rate = fee_rate_aged if aged else fee_rate_standard
    fee = (amount_recovered * rate).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return fee, aged, rate
