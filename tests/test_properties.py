"""Phase 9 tests: property-based tests (hypothesis) over the full legal
input space, not just the examples we thought to write by hand.

Per the Phase 9 execution prompt: a property failure is information, not
an obstacle - when hypothesis finds a counterexample, the fix belongs in
the code under test, never in narrowing the generator or relaxing the
assertion. Each property below is exactly one of the five required by
`Implementation Plan - MVP 1.md`'s Phase 9 task list.
"""

from hypothesis import HealthCheck, assume, given, settings
from hypothesis import strategies as st

from utils import finance_calc as fc
from utils.contracts import default_assumptions
from utils.roadmap import build_roadmap

_SUPPRESSED_HEALTH_CHECKS = [HealthCheck.too_slow, HealthCheck.data_too_large, HealthCheck.function_scoped_fixture]
_SETTINGS = dict(max_examples=200, deadline=None, suppress_health_check=_SUPPRESSED_HEALTH_CHECKS)

_NAME_ALPHABET = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJ 0123456789"
_CATEGORIES = ("Rent/Mortgage", "Groceries", "Dining", "Utilities", "Transport", "Other")

_money = st.floats(min_value=0, max_value=50_000, allow_nan=False, allow_infinity=False)
_small_money = st.floats(min_value=0, max_value=5_000, allow_nan=False, allow_infinity=False)
_name = st.text(alphabet=_NAME_ALPHABET, min_size=1, max_size=12)

debt_strategy = st.fixed_dictionaries({
    "name": _name,
    "balance": _money,
    "apr": st.floats(min_value=0, max_value=35, allow_nan=False, allow_infinity=False),
    "min_payment": st.floats(min_value=0, max_value=2_000, allow_nan=False, allow_infinity=False),
})

goal_strategy = st.fixed_dictionaries({
    "name": _name,
    "amount": st.floats(min_value=1, max_value=50_000, allow_nan=False, allow_infinity=False),
    "months": st.integers(min_value=1, max_value=60),
    "current": _money,
    "priority": st.sampled_from(["high", "medium", "low"]),
})


@st.composite
def transactions_strategy(draw):
    n_months = draw(st.integers(min_value=1, max_value=6))
    transactions = []
    for m in range(n_months):
        month = 1 + m
        income = draw(st.floats(min_value=0, max_value=20_000, allow_nan=False, allow_infinity=False))
        transactions.append({
            "date": f"2026-{month:02d}-01", "description": "Income", "amount": round(income, 2),
            "category": "Income", "category_confidence": 1.0, "needs_review": False, "transaction_type": "income",
        })
        n_expenses = draw(st.integers(min_value=0, max_value=4))
        for e in range(n_expenses):
            amount = draw(st.floats(min_value=0, max_value=5_000, allow_nan=False, allow_infinity=False))
            category = draw(st.sampled_from(_CATEGORIES))
            day = 2 + e * 5
            transactions.append({
                "date": f"2026-{month:02d}-{day:02d}", "description": "Expense", "amount": -round(amount, 2),
                "category": category, "category_confidence": 1.0, "needs_review": False, "transaction_type": "expense",
            })
    return transactions


@st.composite
def profile_strategy(draw):
    return {
        "schema_version": "1.0",
        "transactions": draw(transactions_strategy()),
        "monthly_income": draw(st.floats(min_value=0, max_value=20_000, allow_nan=False, allow_infinity=False)),
        "current_savings": draw(_money),
        "debts": draw(st.lists(debt_strategy, min_size=0, max_size=4)),
        "goals": draw(st.lists(goal_strategy, min_size=0, max_size=3)),
        "constraints": {
            "minimum_monthly_buffer": draw(st.floats(min_value=0, max_value=2_000, allow_nan=False, allow_infinity=False)),
            "protected_categories": [],
        },
        "assumptions": default_assumptions(),
    }


def _pipeline_through_roadmap(profile):
    snapshot = fc.calculate_financial_snapshot(profile)
    trends = fc.compute_trends(profile, snapshot)
    findings = fc.derive_findings(snapshot, trends)
    risks = fc.derive_risks(snapshot, findings)
    return snapshot, build_roadmap(profile, snapshot, findings, risks)


# --------------------------------------------------------------------------
# Property 1: sum(distributed allocation) <= allocatable_surplus always
# --------------------------------------------------------------------------

@settings(**_SETTINGS)
@given(profile=profile_strategy())
def test_distributed_allocation_never_exceeds_allocatable_surplus(profile):
    snapshot, roadmap = _pipeline_through_roadmap(profile)
    allocatable = snapshot["metrics"]["allocatable_surplus"] or 0.0
    allocation = roadmap["allocation"]
    distributed = (
        allocation["debt_extra_payment"] + allocation["savings_contribution"] + sum(allocation["goal_contributions"].values())
    )
    assert distributed <= allocatable + 1e-6


# --------------------------------------------------------------------------
# Property 2: allocatable_surplus >= 0 always
# --------------------------------------------------------------------------

@settings(**_SETTINGS)
@given(profile=profile_strategy())
def test_allocatable_surplus_is_never_negative(profile):
    snapshot = fc.calculate_financial_snapshot(profile)
    allocatable = snapshot["metrics"]["allocatable_surplus"]
    assert allocatable is None or allocatable >= 0


# --------------------------------------------------------------------------
# Property 3: no debt balance goes negative in any payoff schedule
# --------------------------------------------------------------------------

@settings(**_SETTINGS)
@given(
    debts=st.lists(debt_strategy, min_size=1, max_size=4),
    extra_monthly=st.floats(min_value=0, max_value=5_000, allow_nan=False, allow_infinity=False),
    strategy=st.sampled_from(["avalanche", "snowball"]),
)
def test_payoff_timeline_balance_never_goes_negative(debts, extra_monthly, strategy):
    result = fc.simulate_payoff(debts, extra_monthly=extra_monthly, strategy=strategy)
    assert all(row["total_balance"] >= 0 for row in result["timeline"])
    assert result["months_to_payoff"] <= 600  # the documented max_months cap - proves the loop always terminates


# --------------------------------------------------------------------------
# Property 4: payoff month count is monotonically non-increasing as extra
# payment increases
# --------------------------------------------------------------------------

@settings(**_SETTINGS)
@given(
    debts=st.lists(debt_strategy, min_size=1, max_size=4),
    extra1=st.floats(min_value=0, max_value=2_500, allow_nan=False, allow_infinity=False),
    extra_increment=st.floats(min_value=0, max_value=2_500, allow_nan=False, allow_infinity=False),
    strategy=st.sampled_from(["avalanche", "snowball"]),
)
def test_more_extra_payment_never_increases_months_to_payoff(debts, extra1, extra_increment, strategy):
    extra2 = extra1 + extra_increment
    months1 = fc.simulate_payoff(debts, extra_monthly=extra1, strategy=strategy)["months_to_payoff"]
    months2 = fc.simulate_payoff(debts, extra_monthly=extra2, strategy=strategy)["months_to_payoff"]
    assert months2 <= months1


# --------------------------------------------------------------------------
# Property 5: gross_surplus <= 0 implies every distributed allocation is 0
# --------------------------------------------------------------------------

@settings(**_SETTINGS)
@given(profile=profile_strategy())
def test_non_positive_gross_surplus_implies_zero_distributed_allocation(profile):
    snapshot = fc.calculate_financial_snapshot(profile)
    gross_surplus = snapshot["metrics"]["gross_surplus"]
    assume(gross_surplus is not None and gross_surplus <= 0)
    trends = fc.compute_trends(profile, snapshot)
    findings = fc.derive_findings(snapshot, trends)
    risks = fc.derive_risks(snapshot, findings)
    roadmap = build_roadmap(profile, snapshot, findings, risks)
    allocation = roadmap["allocation"]
    assert allocation["debt_extra_payment"] == 0.0
    assert allocation["savings_contribution"] == 0.0
    assert all(value == 0.0 for value in allocation["goal_contributions"].values())
