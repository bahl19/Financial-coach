"""Currency display config (Architecture Plan.md, Component 2/8 boundary).

`assumptions.currency` (utils/contracts.py) selects which symbol every
narrative, report, and UI label uses to format a rupee/dollar amount. This
module is the single place that mapping lives - no agent, report builder, or
UI call site should hardcode a currency symbol directly.

Deliberately currency-only: which vendor keywords or benchmark rates apply is
a *region* concern (utils/region.py), independent of which symbol is shown.
"""

from __future__ import annotations

from typing import Optional

from utils.contracts import SUPPORTED_CURRENCIES

CURRENCY_SYMBOLS = {
    "INR": "₹",
    "USD": "$",
}
assert set(CURRENCY_SYMBOLS) == set(SUPPORTED_CURRENCIES)

DEFAULT_CURRENCY = "INR"


def currency_symbol(currency: Optional[str]) -> str:
    """An unknown or absent currency falls back to today's default (INR),
    never a crash - display formatting must never block on a missing value."""
    return CURRENCY_SYMBOLS.get(currency or DEFAULT_CURRENCY, CURRENCY_SYMBOLS[DEFAULT_CURRENCY])


def format_money(amount: float, currency: Optional[str] = None, decimals: int = 0) -> str:
    return f"{currency_symbol(currency)}{amount:,.{decimals}f}"
