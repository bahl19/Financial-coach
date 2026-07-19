"""utils/currency.py: currency symbol lookup and money formatting.

Every narrative, report, and UI label formats money through this module -
these tests pin the one behavior every call site depends on.
"""

from utils import currency as cur
from utils.contracts import SUPPORTED_CURRENCIES


def test_supported_currencies_match_contracts_canonical_list():
    assert set(cur.CURRENCY_SYMBOLS) == set(SUPPORTED_CURRENCIES)


def test_currency_symbol_for_inr_and_usd():
    assert cur.currency_symbol("INR") == "₹"
    assert cur.currency_symbol("USD") == "$"


def test_currency_symbol_falls_back_to_default_for_none_or_unknown():
    assert cur.currency_symbol(None) == cur.CURRENCY_SYMBOLS[cur.DEFAULT_CURRENCY]
    assert cur.currency_symbol("GBP") == cur.CURRENCY_SYMBOLS[cur.DEFAULT_CURRENCY]


def test_format_money_default_zero_decimals():
    assert cur.format_money(1234.5, "INR") == "₹1,234"
    assert cur.format_money(1234.5, "USD") == "$1,234"


def test_format_money_respects_decimals_argument():
    assert cur.format_money(1234.5, "USD", decimals=2) == "$1,234.50"


def test_format_money_none_currency_defaults_to_inr():
    assert cur.format_money(500.0, None) == "₹500"
