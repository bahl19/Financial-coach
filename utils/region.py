"""Region config (Architecture Plan.md, Component 2/3 boundary).

`assumptions.region` (utils/contracts.py) selects two things, both
independent of `assumptions.currency`:
  1. which vendor-keyword add-ons `utils.ingestion.category_keywords()` layers
     on top of the base, region-neutral table.
  2. which illustrative benchmark-rate trio the Scenario Comparison page's
     FD/PPF/SIP-style tab (app.py) offers.

"india" reproduces this app's original, pre-region-selector behavior exactly
(the India vendor keywords and FD/PPF/SIP rates were unconditional before
this module existed) - it is the default so an unselected/unknown region
never changes existing behavior.
"""

from __future__ import annotations

from typing import Optional

from utils.contracts import SUPPORTED_REGIONS

DEFAULT_REGION = "india"

# (label, annual rate) triples, ordered low-to-high risk/return, shown in the
# Scenario Comparison page's benchmark tab. Rates are illustrative, as the
# existing India trio already was.
BENCHMARK_RATES = {
    "india": (
        ("Fixed Deposit (FD)", 0.065),
        ("PPF", 0.071),
        ("Equity SIP (illustrative)", 0.12),
    ),
    "generic": (
        ("Savings account", 0.045),
        ("Bond fund", 0.05),
        ("Index fund (illustrative)", 0.10),
    ),
}

BENCHMARK_CAPTION = {
    "india": "a few common Indian rate benchmarks",
    "generic": "a few common generic rate benchmarks (savings account / bond fund / index fund)",
}


def resolve_region(region: Optional[str]) -> str:
    """An unknown or absent region falls back to DEFAULT_REGION, never a
    crash or an empty benchmark/keyword set."""
    return region if region in SUPPORTED_REGIONS else DEFAULT_REGION


def benchmark_rates(region: Optional[str]):
    return BENCHMARK_RATES[resolve_region(region)]


def benchmark_caption(region: Optional[str]) -> str:
    return BENCHMARK_CAPTION[resolve_region(region)]
