"""utils/region.py: region-driven vendor-keyword and benchmark-rate config.

"india" must reproduce this app's original, pre-region-selector behavior
exactly (see utils/ingestion.py's category_keywords() parity test and
app.py's original hardcoded FD/PPF/SIP tab) - these tests pin that default.
"""

from utils import region as rg
from utils.contracts import SUPPORTED_REGIONS


def test_supported_regions_match_contracts_canonical_list():
    assert set(rg.SUPPORTED_REGIONS) == set(SUPPORTED_REGIONS)


def test_default_region_is_india():
    assert rg.DEFAULT_REGION == "india"


def test_resolve_region_falls_back_to_default_for_none_or_unknown():
    assert rg.resolve_region(None) == rg.DEFAULT_REGION
    assert rg.resolve_region("atlantis") == rg.DEFAULT_REGION


def test_resolve_region_passes_through_supported_values():
    for region in rg.SUPPORTED_REGIONS:
        assert rg.resolve_region(region) == region


def test_benchmark_rates_every_region_has_three_options():
    for region in rg.SUPPORTED_REGIONS:
        rates = rg.benchmark_rates(region)
        assert len(rates) == 3
        for label, rate in rates:
            assert isinstance(label, str) and label
            assert 0.0 < rate < 1.0


def test_india_benchmark_rates_are_fd_ppf_sip():
    labels = [label for label, _ in rg.benchmark_rates("india")]
    assert labels == ["Fixed Deposit (FD)", "PPF", "Equity SIP (illustrative)"]


def test_benchmark_caption_differs_by_region():
    assert rg.benchmark_caption("india") != rg.benchmark_caption("generic")
    assert "Indian" in rg.benchmark_caption("india")
