"""Deterministic financial calculations (Architecture Plan.md, Component 3).

This module is the "tabular RAG" retrieval/compute layer: agents pull
aggregates and slices out of the raw transactions dataframe here, then
hand those numbers to the LLM (or the offline fallback) as grounded
context instead of letting the model guess at figures.

Convention for uploaded/sample transaction data: expenses are negative
amounts, income/deposits are positive amounts.

No LLM call anywhere in this module - it is deterministic arithmetic only,
over data the caller has already validated (utils/contracts.validate_profile).
It depends only on utils/contracts.py, per Component 3's declared
dependencies; it does not import from utils/ingestion.py (Component 2) even
though both modules happen to reference the same category names as string
literals - see utils/ingestion.py's module docstring for the categorization
duplication this implies until Phase 8 retires this module's legacy
`categorize_transactions()`/`CATEGORY_KEYWORDS`.
"""
from typing import List, Optional, Tuple

import pandas as pd

from utils.contracts import FinancialProfile, FinancialSnapshot, Finding, Risk, Trend, validate_profile

CATEGORY_KEYWORDS = {
    "Rent/Mortgage": ["rent", "mortgage", "landlord", "apartments"],
    "Groceries": ["grocery", "groceries", "supermarket", "whole foods", "trader joe", "safeway", "kroger"],
    "Dining": ["restaurant", "cafe", "coffee", "starbucks", "doordash", "ubereats", "grubhub",
               "mcdonald", "chipotle", "rooftop"],
    "Transport": ["uber", "lyft", "gas station", "shell", "chevron", "exxon", "parking", "transit", "metro"],
    "Utilities": ["electric", "water bill", "gas bill", "internet", "comcast", "at&t", "verizon", "utility"],
    "Subscriptions": ["netflix", "spotify", "hulu", "amazon prime", "subscription", "gym", "planet fitness"],
    "Entertainment": ["movie", "cinema", "amc", "concert", "steam", "playstation", "xbox", "tickets"],
    "Shopping": ["amazon.com", "target", "walmart", "best buy", "mall"],
    "Insurance": ["insurance", "geico", "state farm"],
    "Healthcare": ["pharmacy", "cvs", "walgreens", "doctor", "clinic", "hospital"],
    "Debt Payment": ["credit card payment", "loan payment", "student loan", "auto loan"],
    "Savings/Investing": ["transfer to savings", "401k", "ira contribution", "brokerage", "investment"],
}

NEEDS_CATS = {"Rent/Mortgage", "Groceries", "Utilities", "Insurance", "Healthcare", "Transport", "Debt Payment"}
SAVINGS_CATS = {"Savings/Investing"}
# everything else (Dining, Subscriptions, Entertainment, Shopping, Other) counts as "Wants"


def _categorize_row(row) -> str:
    desc = str(row["description"]).lower()
    for category, keywords in CATEGORY_KEYWORDS.items():
        if any(kw in desc for kw in keywords):
            return category
    return "Income" if row["amount"] > 0 else "Other"


def categorize_transactions(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["category"] = out.apply(_categorize_row, axis=1)
    return out


def spending_by_category(df: pd.DataFrame) -> pd.DataFrame:
    expenses = df[df["category"] != "Income"].copy()
    expenses["amount"] = expenses["amount"].abs()
    out = expenses.groupby("category", as_index=False)["amount"].sum()
    return out.sort_values("amount", ascending=False).reset_index(drop=True)


def monthly_cashflow(df: pd.DataFrame) -> pd.DataFrame:
    d = df.copy()
    d["month"] = d["date"].dt.to_period("M")
    income = d[d["amount"] > 0].groupby("month")["amount"].sum()
    expenses = d[d["amount"] < 0].groupby("month")["amount"].sum().abs()
    out = pd.DataFrame({"income": income, "expenses": expenses}).fillna(0.0)
    out["net"] = out["income"] - out["expenses"]
    out = out.sort_index().reset_index()
    out["month"] = out["month"].astype(str)
    return out


def category_trends(df: pd.DataFrame) -> pd.DataFrame:
    """Month-over-month % change in spending per category, comparing the two most recent months."""
    d = df[df["category"] != "Income"].copy()
    d["month"] = d["date"].dt.to_period("M")
    d["amount"] = d["amount"].abs()
    pivot = d.pivot_table(index="month", columns="category", values="amount", aggfunc="sum").fillna(0.0)
    pivot = pivot.sort_index()
    if len(pivot) < 2:
        return pd.DataFrame(columns=["category", "pct_change"])
    prev, last = pivot.iloc[-2], pivot.iloc[-1]
    rows = []
    for cat in pivot.columns:
        if prev[cat] > 0:
            pct = (last[cat] - prev[cat]) / prev[cat] * 100
            rows.append({"category": cat, "pct_change": pct})
    return pd.DataFrame(rows).sort_values("pct_change", ascending=False).reset_index(drop=True)


def recommended_budget(income: float) -> dict:
    return {"Needs": income * 0.5, "Wants": income * 0.3, "Savings": income * 0.2}


def actual_budget_split_from_categories(by_cat: pd.DataFrame, num_months: int) -> dict:
    """Average monthly spend per 50/30/20 bucket, given an already-computed
    per-category breakdown (e.g. spending_result's `by_category`) - callers
    that already have this must not recompute spending_by_category() a
    second time (Implementation Plan - MVP 1.md, Phase 3)."""
    num_months = max(num_months, 1)
    result = {"Needs": 0.0, "Wants": 0.0, "Savings": 0.0}
    for _, row in by_cat.iterrows():
        if row["category"] in NEEDS_CATS:
            result["Needs"] += row["amount"]
        elif row["category"] in SAVINGS_CATS:
            result["Savings"] += row["amount"]
        else:
            result["Wants"] += row["amount"]
    return {k: v / num_months for k, v in result.items()}


def actual_budget_split(df: pd.DataFrame) -> dict:
    """Convenience wrapper over actual_budget_split_from_categories() for a
    caller that only has raw transactions (e.g. a report rebuilding this
    from scratch, not the live specialist pipeline, which reuses
    spending_result's by_category instead of calling this)."""
    num_months = max(df["date"].dt.to_period("M").nunique(), 1)
    return actual_budget_split_from_categories(spending_by_category(df), num_months)


def emergency_fund_target(monthly_expenses: float) -> tuple:
    return (monthly_expenses * 3, monthly_expenses * 6)


def savings_projection(current: float, monthly_contribution: float, months: int = 24, apr: float = 0.04) -> list:
    balance = current
    rate = apr / 12
    out = []
    for m in range(1, months + 1):
        balance = balance * (1 + rate) + monthly_contribution
        out.append({"month": m, "balance": balance})
    return out


def goal_feasibility(amount: float, months: int, surplus: float, current: float = 0.0) -> dict:
    remaining = max(amount - current, 0.0)
    required_monthly = remaining / months if months > 0 else remaining
    feasible = required_monthly <= surplus
    shortfall = max(required_monthly - surplus, 0.0)
    return {"required_monthly": required_monthly, "feasible": feasible, "shortfall": shortfall}


def simulate_payoff(debts: list, extra_monthly: float, strategy: str = "avalanche") -> dict:
    """Simulate month-by-month payoff. strategy: 'avalanche' (highest APR first)
    or 'snowball' (smallest balance first). Freed-up minimum payments from paid-off
    debts roll into the extra payment pool, as in standard payoff calculators."""
    if strategy == "avalanche":
        order = sorted(debts, key=lambda d: -float(d["apr"]))
    else:
        order = sorted(debts, key=lambda d: float(d["balance"]))

    names = [d["name"] for d in order]
    balances = {d["name"]: float(d["balance"]) for d in order}
    min_payments = {d["name"]: float(d["min_payment"]) for d in order}
    aprs = {d["name"]: float(d["apr"]) for d in order}

    timeline = []
    month = 0
    total_interest = 0.0
    freed = 0.0
    max_months = 600

    while any(b > 0.01 for b in balances.values()) and month < max_months:
        month += 1
        for name in names:
            if balances[name] > 0:
                interest = balances[name] * (aprs[name] / 100 / 12)
                balances[name] += interest
                total_interest += interest

        for name in names:
            if balances[name] > 0:
                pay = min(min_payments[name], balances[name])
                balances[name] -= pay

        available_extra = extra_monthly + freed
        for name in names:
            if balances[name] > 0 and available_extra > 0:
                pay = min(available_extra, balances[name])
                balances[name] -= pay
                available_extra -= pay

        freed = sum(min_payments[n] for n in names if balances[n] <= 0.01)
        timeline.append({"month": month, "total_balance": sum(max(b, 0.0) for b in balances.values())})

    return {
        "months_to_payoff": month,
        "total_interest": total_interest,
        "payoff_order": names,
        "timeline": timeline,
    }


# --------------------------------------------------------------------------
# Snapshot: surplus/allocation semantics (Architecture Plan.md, Surplus and
# Allocation Semantics). These names are deliberately distinct and each
# documented at its definition site - "surplus" was ambiguous across this
# codebase before this section existed, and that ambiguity is a documented
# source of the double-allocation bug this plan exists to fix.
# --------------------------------------------------------------------------

_EMPTY_TRANSACTIONS_COLUMNS = [
    "date", "description", "amount", "category", "category_confidence", "needs_review", "transaction_type",
]


def _transactions_to_frame(transactions: list) -> pd.DataFrame:
    """Converts a list of Transaction records into a dataframe with a
    datetime `date` column. Returns a well-formed empty frame for an empty
    list rather than letting an empty-input edge case surface as a crash
    somewhere downstream."""
    if not transactions:
        return pd.DataFrame(columns=_EMPTY_TRANSACTIONS_COLUMNS)
    df = pd.DataFrame(transactions)
    df["date"] = pd.to_datetime(df["date"])
    return df


def _average_monthly_expenses(transactions_df: pd.DataFrame) -> float:
    if transactions_df.empty:
        return 0.0
    monthly = monthly_cashflow(transactions_df)
    if monthly.empty:
        return 0.0
    return float(monthly["expenses"].mean())


def _average_debt_payment_category_spend(transactions_df: pd.DataFrame) -> float:
    """Average monthly spend already categorized "Debt Payment" - the part
    of debt minimums already reflected inside average_monthly_expenses."""
    if transactions_df.empty:
        return 0.0
    debt_rows = transactions_df[transactions_df["category"] == "Debt Payment"]
    if debt_rows.empty:
        return 0.0
    num_months = max(transactions_df["date"].dt.to_period("M").nunique(), 1)
    return float(debt_rows["amount"].abs().sum()) / num_months


def required_commitments(debts: list, transactions_df: pd.DataFrame) -> float:
    """Debt minimum payments NOT already reflected in average_monthly_expenses.

    "Reflected" means the historical average "Debt Payment"-category spend
    already covers the total of today's minimum payments; only the shortfall
    (e.g. a debt just added to the profile with no payment history yet) is
    counted here. This is what prevents a minimum payment from being
    subtracted from surplus twice - once inside expenses, once again here.
    """
    total_minimums = sum(float(debt.get("min_payment") or 0.0) for debt in (debts or []))
    already_reflected = _average_debt_payment_category_spend(transactions_df)
    return max(0.0, total_minimums - already_reflected)


def calculate_gross_surplus(monthly_income: Optional[float], average_monthly_expenses: float) -> Optional[float]:
    """gross_surplus = confirmed monthly_income - average_monthly_expenses.

    Returns None (unknown) rather than a number when income is unconfirmed -
    a missing value must never be silently treated as zero income."""
    if monthly_income is None:
        return None
    return monthly_income - average_monthly_expenses


def calculate_allocatable_surplus(
    gross_surplus: Optional[float], commitments: float, minimum_buffer: float
) -> Optional[float]:
    """allocatable_surplus = max(0, gross_surplus - required_commitments - minimum_buffer).

    None (unknown) propagates rather than being coerced to zero - an unknown
    surplus is not the same fact as a surplus of exactly zero."""
    if gross_surplus is None:
        return None
    return max(0.0, gross_surplus - commitments - minimum_buffer)


# --------------------------------------------------------------------------
# Health score
# --------------------------------------------------------------------------
#
# Every weight and threshold is a named constant, not a literal, so a
# reviewer can see and adjust the scoring rule without reverse-engineering
# it from call sites. Weights sum to 100 (the score's ceiling).

_WEIGHT_SAVINGS_RATE = 30
_WEIGHT_EMERGENCY_FUND = 30
_WEIGHT_DEBT_TO_INCOME = 25
_WEIGHT_POSITIVE_SURPLUS = 15

_SAVINGS_RATE_TARGET_PERCENT = 20.0
_EMERGENCY_FUND_TARGET_MONTHS = 6.0
_DEBT_TO_INCOME_HEALTHY_PERCENT = 15.0
_DEBT_TO_INCOME_UNHEALTHY_PERCENT = 40.0

_HEALTH_SCORE_MIN = 0
_HEALTH_SCORE_MAX = 100

_HEALTH_BAND_THRESHOLDS = (
    (80, "Thriving"),
    (60, "Building"),
    (40, "Stabilizing"),
    (_HEALTH_SCORE_MIN, "At Risk"),
)


def _health_band(score: int) -> str:
    for threshold, band in _HEALTH_BAND_THRESHOLDS:
        if score >= threshold:
            return band
    return "At Risk"


def calculate_health_score(metrics: dict, assumptions: dict) -> Tuple[int, str]:
    """Bounded 0-100 coaching indicator, not a credit score. `assumptions`
    is accepted for signature stability (Architecture Plan.md, Component 3)
    even though the current weighting does not yet vary by assumption;
    every deduction below is explainable by naming the metric that drove it."""
    score = 0.0

    savings_rate = metrics.get("savings_rate_percent")
    if savings_rate is not None:
        score += _WEIGHT_SAVINGS_RATE * min(1.0, max(0.0, savings_rate / _SAVINGS_RATE_TARGET_PERCENT))

    emergency_months = metrics.get("emergency_fund_months")
    if emergency_months is not None:
        score += _WEIGHT_EMERGENCY_FUND * min(1.0, max(0.0, emergency_months / _EMERGENCY_FUND_TARGET_MONTHS))

    debt_to_income = metrics.get("debt_to_income_percent")
    if debt_to_income is None:
        score += _WEIGHT_DEBT_TO_INCOME  # no debt is not a penalty
    elif debt_to_income <= _DEBT_TO_INCOME_HEALTHY_PERCENT:
        score += _WEIGHT_DEBT_TO_INCOME
    elif debt_to_income < _DEBT_TO_INCOME_UNHEALTHY_PERCENT:
        span = _DEBT_TO_INCOME_UNHEALTHY_PERCENT - _DEBT_TO_INCOME_HEALTHY_PERCENT
        score += _WEIGHT_DEBT_TO_INCOME * (1.0 - (debt_to_income - _DEBT_TO_INCOME_HEALTHY_PERCENT) / span)
    # else: at or above the unhealthy threshold earns zero credit for this weight

    gross_surplus = metrics.get("gross_surplus")
    if gross_surplus is not None and gross_surplus > 0:
        score += _WEIGHT_POSITIVE_SURPLUS

    bounded_score = int(round(min(_HEALTH_SCORE_MAX, max(_HEALTH_SCORE_MIN, score))))
    return bounded_score, _health_band(bounded_score)


# --------------------------------------------------------------------------
# risk_flags: legacy projection
# --------------------------------------------------------------------------
#
# Phase 1 computed a preliminary, independently-derived risk_flags list here,
# because the contract requires the field and Phase 2's Risk engine did not
# exist yet. Phase 2 now exists, so that preliminary logic is retired rather
# than kept as a second source that could disagree with Risk[] (Architecture
# Plan.md, Component 3: "keep risk_flags as a derived, backward-compatible
# projection of Risk objects, never a second independent source").
#
# calculate_financial_snapshot() therefore returns risk_flags=[] - Risk[]
# does not exist until derive_risks() runs, which itself needs this snapshot
# as an input, so risk_flags cannot be correctly populated inside this
# function. The caller must call project_risk_flags(derive_risks(...)) and
# assign the result onto the snapshot before showing risk_flags to anyone.

def project_risk_flags(risks: List[Risk]) -> List[dict]:
    """The only correct source of legacy risk_flags once Risk[] exists -
    never compute risk_flags independently alongside this."""
    return [
        {"code": risk["risk_id"], "severity": risk["severity"], "metric": (risk["metric_refs"] or [None])[0]}
        for risk in risks
    ]


# --------------------------------------------------------------------------
# Budget variance (not part of the frozen FinancialSnapshot contract shape -
# a standalone helper Component 4/6/7 may call, so Phase 1 does not need to
# reopen Phase 0's already-shipped contract to satisfy Component 3's
# "budget variance" description)
# --------------------------------------------------------------------------

def budget_variance(actual: dict, recommended: dict) -> dict:
    """actual - recommended, per 50/30/20 bucket. A positive value means
    overspending that bucket relative to the recommendation."""
    return {bucket: actual.get(bucket, 0.0) - recommended.get(bucket, 0.0) for bucket in recommended}


def _period_label(transactions_df: pd.DataFrame) -> Optional[str]:
    if transactions_df.empty:
        return None
    return str(transactions_df["date"].max().to_period("M"))


def _is_partial_trailing_period(transactions_df: pd.DataFrame) -> bool:
    if transactions_df.empty:
        return False
    last_date = transactions_df["date"].max()
    month_end = last_date.to_period("M").end_time
    return last_date.normalize() < month_end.normalize()


# --------------------------------------------------------------------------
# calculate_financial_snapshot: composes everything above into the single
# FinancialSnapshot every downstream component reads.
#
# `data_quality_flags` is a parameter, not computed here, because detecting
# it is Component 2's job (utils/ingestion.detect_data_quality_issues) and
# Component 3 depends only on Component 1 (utils/contracts) - it must not
# import Component 2. The caller runs ingestion's detection and passes the
# result in.
# --------------------------------------------------------------------------

def calculate_financial_snapshot(
    profile: FinancialProfile, data_quality_flags: Optional[List[dict]] = None
) -> FinancialSnapshot:
    transactions_df = _transactions_to_frame(profile.get("transactions") or [])

    average_monthly_expenses = _average_monthly_expenses(transactions_df)
    monthly_income = profile.get("monthly_income")
    gross_surplus = calculate_gross_surplus(monthly_income, average_monthly_expenses)

    debts = profile.get("debts") or []
    commitments = required_commitments(debts, transactions_df)
    minimum_buffer = float((profile.get("constraints") or {}).get("minimum_monthly_buffer") or 0.0)
    allocatable_surplus = calculate_allocatable_surplus(gross_surplus, commitments, minimum_buffer)

    total_minimum_payments = sum(float(debt.get("min_payment") or 0.0) for debt in debts)
    debt_to_income_percent = None
    if monthly_income is not None and monthly_income > 0:
        debt_to_income_percent = total_minimum_payments / monthly_income * 100

    savings_rate_percent = None
    if monthly_income is not None and monthly_income > 0:
        savings_rate_percent = (monthly_income - average_monthly_expenses) / monthly_income * 100

    current_savings = profile.get("current_savings")
    emergency_fund_months = None
    if current_savings is not None and average_monthly_expenses > 0:
        emergency_fund_months = current_savings / average_monthly_expenses

    total_debt = sum(float(debt.get("balance") or 0.0) for debt in debts)

    # Baseline (minimums-only) payoff comparison. This is a diagnostic view at
    # the snapshot stage, not an allocation decision - Component 4's
    # build_roadmap() computes its own payoff comparison using the actual
    # allocated extra payment; nothing here feeds a dollar figure to a
    # specialist narrative.
    if debts:
        debt_comparison = {
            "avalanche": simulate_payoff(debts, extra_monthly=0.0, strategy="avalanche"),
            "snowball": simulate_payoff(debts, extra_monthly=0.0, strategy="snowball"),
        }
    else:
        debt_comparison = {"avalanche": None, "snowball": None}

    # Preliminary, allocation-unaware feasibility using the full available
    # surplus - Component 4's build_roadmap() computes the authoritative,
    # allocation-constrained feasibility per goal.
    preliminary_surplus_for_goals = allocatable_surplus if allocatable_surplus is not None else 0.0
    goal_results = [
        {
            "name": goal.get("name"),
            **goal_feasibility(
                goal.get("amount", 0.0),
                goal.get("months", 0),
                preliminary_surplus_for_goals,
                goal.get("current", 0.0),
            ),
        }
        for goal in (profile.get("goals") or [])
    ]

    metrics = {
        "average_monthly_expenses": average_monthly_expenses,
        "monthly_surplus": gross_surplus,  # backward-compatible alias of gross_surplus
        "gross_surplus": gross_surplus,
        "allocatable_surplus": allocatable_surplus,
        "required_commitments": commitments,
        "savings_rate_percent": savings_rate_percent,
        "debt_to_income_percent": debt_to_income_percent,
        "emergency_fund_months": emergency_fund_months,
        "total_debt": total_debt,
        "period": _period_label(transactions_df),
        "is_partial_period": _is_partial_trailing_period(transactions_df),
    }

    health_score, health_band = calculate_health_score(metrics, profile.get("assumptions") or {})

    return {
        "schema_version": "1.0",
        "metrics": metrics,
        "health_score": health_score,
        "health_band": health_band,
        "risk_flags": [],  # populate via project_risk_flags(derive_risks(...)) once Risk[] exists
        "data_quality_flags": data_quality_flags or [],
        "debt_comparison": debt_comparison,
        "goal_results": goal_results,
        "validation_issues": validate_profile(profile),
    }


# ==========================================================================
# Trend, Insight, and Risk Engines (Architecture Plan.md, Insight, Trend,
# and Risk Engines). Everything below is a pure function; no LLM call
# anywhere in this section. Every finding/risk-producing rule is
# independent and registered in a tuple - adding a new one means writing a
# function and appending it, never editing a growing conditional.
# ==========================================================================

# --------------------------------------------------------------------------
# Trend Engine
# --------------------------------------------------------------------------

_TREND_WINDOW_MONTHS = 3
_SHARP_CHANGE_THRESHOLD_PERCENT = 50.0
_MODERATE_CHANGE_THRESHOLD_PERCENT = 15.0
_EMERGENCY_FUND_RUNWAY_TREND_ID = "TREND_EMERGENCY_FUND_RUNWAY"


def _trend_direction(absolute_change: float) -> str:
    if absolute_change > 0:
        return "increasing"
    if absolute_change < 0:
        return "decreasing"
    return "flat"


def _classify_change(percent_change: Optional[float]) -> str:
    """Deterministic classification rule, documented once here - every
    Trend's `classification` traces back to this single function, never a
    per-call judgment."""
    if percent_change is None:
        return "stable"
    magnitude = abs(percent_change)
    if magnitude >= _SHARP_CHANGE_THRESHOLD_PERCENT:
        return "sharp_increase" if percent_change > 0 else "sharp_decrease"
    if magnitude >= _MODERATE_CHANGE_THRESHOLD_PERCENT:
        return "moderate_increase" if percent_change > 0 else "moderate_decrease"
    return "stable"


def _build_trend(trend_id: str, metric: str, period: str, start_value: float, end_value: float) -> Trend:
    absolute_change = end_value - start_value
    percent_change = (absolute_change / start_value * 100) if start_value else None
    return {
        "trend_id": trend_id,
        "metric": metric,
        "period": period,
        "start_value": start_value,
        "end_value": end_value,
        "absolute_change": absolute_change,
        "percent_change": percent_change,
        "direction": _trend_direction(absolute_change),
        "classification": _classify_change(percent_change),
    }


def _monthly_series_trend(trend_id: str, metric: str, monthly: pd.DataFrame, column: str) -> Optional[Trend]:
    window = monthly.tail(_TREND_WINDOW_MONTHS)
    if len(window) < 2:
        return None
    return _build_trend(
        trend_id, metric, f"{len(window)}_months", float(window.iloc[0][column]), float(window.iloc[-1][column])
    )


def _category_spending_trends(transactions_df: pd.DataFrame) -> List[Trend]:
    if transactions_df.empty:
        return []
    expenses = transactions_df[transactions_df["category"] != "Income"].copy()
    if expenses.empty:
        return []
    expenses["month"] = expenses["date"].dt.to_period("M").astype(str)
    expenses["amount"] = expenses["amount"].abs()
    pivot = expenses.pivot_table(index="month", columns="category", values="amount", aggfunc="sum").fillna(0.0)
    pivot = pivot.sort_index().tail(_TREND_WINDOW_MONTHS)
    if len(pivot) < 2:
        return []

    trends: List[Trend] = []
    for category in pivot.columns:
        start, end = float(pivot[category].iloc[0]), float(pivot[category].iloc[-1])
        if start == 0.0 and end == 0.0:
            continue  # no activity in this category during the window
        slug = category.upper().replace("/", "_").replace(" ", "_")
        trends.append(_build_trend(f"TREND_CATEGORY_{slug}", f"{category}_spend", f"{len(pivot)}_months", start, end))
    return trends


def _debt_payment_trend(transactions_df: pd.DataFrame) -> Optional[Trend]:
    """Proxy for a debt-balance trend. MVP 1 has no persisted historical
    balance snapshots (no case history / database - Architecture Plan.md,
    Explicitly deferred), so this tracks monthly "Debt Payment"-category
    spend instead: the only debt-related time series actually available
    from transaction history. A rising trend here means faster paydown, not
    a growing balance - the metric name says spend, not balance, on purpose."""
    if transactions_df.empty:
        return None
    debt_rows = transactions_df[transactions_df["category"] == "Debt Payment"].copy()
    if debt_rows.empty:
        return None
    debt_rows["month"] = debt_rows["date"].dt.to_period("M").astype(str)
    debt_rows["amount"] = debt_rows["amount"].abs()
    monthly = debt_rows.groupby("month")["amount"].sum().sort_index().tail(_TREND_WINDOW_MONTHS)
    if len(monthly) < 2:
        return None
    return _build_trend(
        "TREND_DEBT_PAYMENT", "debt_payment_spend", f"{len(monthly)}_months",
        float(monthly.iloc[0]), float(monthly.iloc[-1]),
    )


def _savings_contribution_trend(transactions_df: pd.DataFrame) -> Optional[Trend]:
    """Proxy for a savings-balance trend, for the same reason as
    _debt_payment_trend: tracks monthly "Savings/Investing"-category spend,
    the only savings-related time series available from transaction history."""
    if transactions_df.empty:
        return None
    savings_rows = transactions_df[transactions_df["category"] == "Savings/Investing"].copy()
    if savings_rows.empty:
        return None
    savings_rows["month"] = savings_rows["date"].dt.to_period("M").astype(str)
    savings_rows["amount"] = savings_rows["amount"].abs()
    monthly = savings_rows.groupby("month")["amount"].sum().sort_index().tail(_TREND_WINDOW_MONTHS)
    if len(monthly) < 2:
        return None
    return _build_trend(
        "TREND_SAVINGS_CONTRIBUTIONS", "savings_contribution_spend", f"{len(monthly)}_months",
        float(monthly.iloc[0]), float(monthly.iloc[-1]),
    )


def _emergency_fund_runway_trend(metrics: dict, assumptions: dict) -> Optional[Trend]:
    """Not a time-series trend - MVP 1 has no historical current_savings
    series to compare month-over-month. Instead compares the actual
    emergency-fund runway against the user's target, both available from a
    single snapshot: a "distance to target" trend rather than a "change
    over calendar time" trend. `period` reflects this explicitly."""
    actual_months = metrics.get("emergency_fund_months")
    target_months = (assumptions or {}).get("emergency_fund_months")
    if actual_months is None or not target_months:
        return None
    return _build_trend(
        _EMERGENCY_FUND_RUNWAY_TREND_ID, "emergency_fund_months", "current_vs_target",
        float(target_months), float(actual_months),
    )


def compute_trends(profile: FinancialProfile, snapshot: FinancialSnapshot) -> List[Trend]:
    transactions_df = _transactions_to_frame(profile.get("transactions") or [])
    monthly = _monthly_cashflow_or_empty(transactions_df)

    trends: List[Trend] = []
    for trend in (
        _monthly_series_trend("TREND_INCOME", "monthly_income", monthly, "income"),
        _monthly_series_trend("TREND_EXPENSES", "monthly_expenses", monthly, "expenses"),
        _monthly_series_trend("TREND_SURPLUS", "monthly_surplus", monthly, "net"),
        _debt_payment_trend(transactions_df),
        _savings_contribution_trend(transactions_df),
        _emergency_fund_runway_trend(snapshot["metrics"], profile.get("assumptions")),
    ):
        if trend is not None:
            trends.append(trend)
    trends.extend(_category_spending_trends(transactions_df))
    return trends


def _monthly_cashflow_or_empty(transactions_df: pd.DataFrame) -> pd.DataFrame:
    if transactions_df.empty:
        return pd.DataFrame(columns=["month", "income", "expenses", "net"])
    return monthly_cashflow(transactions_df)


# --------------------------------------------------------------------------
# Insight Engine (Finding rules)
# --------------------------------------------------------------------------
#
# MVP 1 scope is 8 finding types (Architecture Plan.md): income changes,
# expense changes, category trends, cashflow deterioration/improvement,
# debt risks, emergency-fund risks, goal feasibility issues, data-quality
# problems. Every finding is `fact` or `deterministic_inference` - never
# `hypothesis` (reserved for MVP 2+).

_INCOME_SHARP_DROP_PERCENT = -30.0
_INCOME_MODERATE_DROP_PERCENT = -15.0
_INCOME_SHARP_RISE_PERCENT = 30.0
_EXPENSE_SHARP_RISE_PERCENT = 30.0
_EXPENSE_MODERATE_RISE_PERCENT = 15.0
_LOW_EMERGENCY_FUND_RUNWAY_RATIO = 0.5  # actual/target below this triggers a finding


def _finding(
    finding_id: str, type_: str, title: str, severity: str, urgency: str, confidence: float,
    fact_or_inference: str, metric_refs: list, trend_refs: list, impact: str, recommended_response: str,
) -> Finding:
    return {
        "finding_id": finding_id, "type": type_, "title": title, "severity": severity, "urgency": urgency,
        "confidence": confidence, "fact_or_inference": fact_or_inference, "metric_refs": metric_refs,
        "trend_refs": trend_refs, "impact": impact, "recommended_response": recommended_response,
    }


def _trend_by_id(trends: List[Trend], trend_id: str) -> Optional[Trend]:
    return next((t for t in trends if t["trend_id"] == trend_id), None)


def _trends_by_prefix(trends: List[Trend], prefix: str) -> List[Trend]:
    return [t for t in trends if t["trend_id"].startswith(prefix)]


def _income_change_findings(snapshot: dict, trends: List[Trend]) -> List[Finding]:
    trend = _trend_by_id(trends, "TREND_INCOME")
    if trend is None or trend["percent_change"] is None:
        return []
    pct = trend["percent_change"]
    if pct <= _INCOME_SHARP_DROP_PERCENT:
        return [_finding(
            "FINDING_INCOME_DROP", "income_trend", "Income declined sharply", "critical", "immediate", 1.0, "fact",
            ["gross_surplus"], [trend["trend_id"]],
            "Current spending may no longer be supported by income.",
            "Stabilize cashflow before accelerating debt or savings.",
        )]
    if pct <= _INCOME_MODERATE_DROP_PERCENT:
        return [_finding(
            "FINDING_INCOME_DECLINE", "income_trend", "Income declined", "high", "this_month", 1.0, "fact",
            ["gross_surplus"], [trend["trend_id"]],
            "Surplus available for goals and debt paydown has likely shrunk.",
            "Review discretionary spending before committing to new allocations.",
        )]
    if pct >= _INCOME_SHARP_RISE_PERCENT:
        return [_finding(
            "FINDING_INCOME_INCREASE", "income_trend", "Income increased", "positive", "long_term", 1.0, "fact",
            ["gross_surplus"], [trend["trend_id"]],
            "More surplus may be available for goals, debt payoff, or savings.",
            "Consider directing the increase toward the highest-priority roadmap action.",
        )]
    return []


def _expense_change_findings(snapshot: dict, trends: List[Trend]) -> List[Finding]:
    trend = _trend_by_id(trends, "TREND_EXPENSES")
    if trend is None or trend["percent_change"] is None:
        return []
    pct = trend["percent_change"]
    if pct >= _EXPENSE_SHARP_RISE_PERCENT:
        return [_finding(
            "FINDING_EXPENSES_UP_SHARPLY", "expense_trend", "Expenses rose sharply", "high", "this_month", 1.0,
            "fact", ["average_monthly_expenses"], [trend["trend_id"]],
            "Rising expenses reduce the surplus available for the roadmap.",
            "Identify which category drove the increase before adjusting the plan.",
        )]
    if pct >= _EXPENSE_MODERATE_RISE_PERCENT:
        return [_finding(
            "FINDING_EXPENSES_UP", "expense_trend", "Expenses increased", "medium", "this_month", 1.0, "fact",
            ["average_monthly_expenses"], [trend["trend_id"]],
            "A moderate expense increase is worth monitoring.",
            "Watch next month to see if this is a one-time or ongoing change.",
        )]
    return []


_CATEGORY_FINDING_CLASSIFICATIONS = ("sharp_increase", "sharp_decrease")


def _category_trend_findings(snapshot: dict, trends: List[Trend]) -> List[Finding]:
    findings: List[Finding] = []
    for trend in _trends_by_prefix(trends, "TREND_CATEGORY_"):
        if trend["classification"] not in _CATEGORY_FINDING_CLASSIFICATIONS:
            continue
        rising = trend["classification"] == "sharp_increase"
        severity = "medium" if rising else "positive"
        findings.append(_finding(
            f"FINDING_{trend['trend_id'][len('TREND_'):]}_CHANGE", "category_trend",
            f"{trend['metric']} {'increased' if rising else 'decreased'} sharply", severity,
            "this_month" if rising else "long_term", 1.0, "fact", [], [trend["trend_id"]],
            f"{trend['metric']} changed {trend['percent_change']:.0f}% over the recent period.",
            "Review whether this category change is intentional." if rising else "Keep up the trend.",
        ))
    return findings


def _cashflow_findings(snapshot: dict, trends: List[Trend]) -> List[Finding]:
    gross_surplus = snapshot["metrics"].get("gross_surplus")
    if gross_surplus is None:
        return []
    if gross_surplus <= 0:
        return [_finding(
            "FINDING_NEGATIVE_CASHFLOW", "cashflow", "Spending exceeds income", "critical", "immediate", 1.0,
            "fact", ["gross_surplus"], [],
            "Every dollar of debt paydown or savings right now would come from a deficit.",
            "Prioritize expense reduction and income stability before any other allocation.",
        )]
    surplus_trend = _trend_by_id(trends, "TREND_SURPLUS")
    if surplus_trend is None:
        return []
    if surplus_trend["classification"] in ("sharp_decrease", "moderate_decrease"):
        return [_finding(
            "FINDING_CASHFLOW_DETERIORATING", "cashflow", "Cashflow is weakening", "high", "this_month", 1.0,
            "fact", ["gross_surplus"], [surplus_trend["trend_id"]],
            "Surplus available for the roadmap is shrinking.",
            "Recheck the roadmap allocation once the trend is confirmed over another month.",
        )]
    if surplus_trend["classification"] in ("sharp_increase", "moderate_increase"):
        return [_finding(
            "FINDING_CASHFLOW_IMPROVING", "cashflow", "Cashflow is improving", "positive", "long_term", 1.0,
            "fact", ["gross_surplus"], [surplus_trend["trend_id"]],
            "More surplus is becoming available for the roadmap.",
            "Consider directing the improvement toward the highest-priority action.",
        )]
    return []


def _debt_risk_findings(snapshot: dict, trends: List[Trend]) -> List[Finding]:
    """Limitation: derive_findings()'s signature is (snapshot, trends) only,
    per Implementation Plan - MVP 1.md - it does not receive raw `debts`, so
    this cannot check an individual debt's APR directly. It uses
    debt_to_income_percent (available in snapshot.metrics) as the proxy for
    "the debt load is a risk", not "a specific debt's rate is high". See the
    Phase 2 report for the accuracy tradeoff this implies."""
    total_debt = snapshot["metrics"].get("total_debt", 0.0)
    debt_to_income = snapshot["metrics"].get("debt_to_income_percent")
    if not total_debt or debt_to_income is None:
        return []
    if debt_to_income >= _DEBT_TO_INCOME_UNHEALTHY_PERCENT:
        return [_finding(
            "FINDING_HIGH_DEBT_BURDEN", "debt_risk", "Debt payments are a large share of income", "high",
            "this_month", 1.0, "fact", ["debt_to_income_percent"], [],
            "A high debt-service burden limits flexibility for other goals.",
            "Prioritize accelerated debt paydown in the roadmap.",
        )]
    return []


def _emergency_fund_findings(snapshot: dict, trends: List[Trend]) -> List[Finding]:
    runway = _trend_by_id(trends, _EMERGENCY_FUND_RUNWAY_TREND_ID)
    if runway is None or not runway["start_value"]:
        return []
    target, actual = runway["start_value"], runway["end_value"]
    if actual / target < _LOW_EMERGENCY_FUND_RUNWAY_RATIO:
        return [_finding(
            "FINDING_LOW_EMERGENCY_FUND", "emergency_fund_risk", "Emergency fund is below target", "high",
            "this_month", 1.0, "fact", ["emergency_fund_months"], [runway["trend_id"]],
            f"Current runway ({actual:.1f} months) is well below the {target:.0f}-month target.",
            "Prioritize a starter emergency buffer before discretionary savings.",
        )]
    return []


def _goal_feasibility_findings(snapshot: dict, trends: List[Trend]) -> List[Finding]:
    findings: List[Finding] = []
    for index, goal in enumerate(snapshot.get("goal_results") or []):
        if goal.get("feasible") is not False:
            continue
        slug = str(goal.get("name") or f"GOAL_{index}").upper().replace(" ", "_")
        findings.append(_finding(
            f"FINDING_GOAL_SHORTFALL_{slug}", "goal_feasibility", f"{goal.get('name')} is not currently feasible",
            "medium", "next_90_days", 1.0, "fact", [], [],
            f"Required monthly contribution exceeds available surplus by ${goal.get('shortfall', 0):.0f}.",
            "Extend the timeline, reduce the target amount, or free up more surplus.",
        ))
    return findings


_DATA_QUALITY_FINDING_SEVERITY = {
    "DUPLICATE_TRANSACTIONS": "medium",
    "MISSING_MONTHS": "medium",
    "PARTIAL_TRAILING_MONTH": "low",
    "INSUFFICIENT_HISTORY": "medium",
    "ZERO_INCOME_TRANSACTIONS": "high",
    "NO_TRANSACTIONS": "critical",
}


def _data_quality_findings(snapshot: dict, trends: List[Trend]) -> List[Finding]:
    findings: List[Finding] = []
    for flag in snapshot.get("data_quality_flags") or []:
        severity = _DATA_QUALITY_FINDING_SEVERITY.get(flag["code"], "low")
        affects = flag.get("affects", [])
        findings.append(_finding(
            f"FINDING_DATA_QUALITY_{flag['code']}", "data_quality", flag["detail"], severity, "immediate", 1.0,
            "fact", affects, [],
            f"This may affect: {', '.join(affects)}." if affects else "Data completeness is limited.",
            "Review the underlying data before relying heavily on affected metrics.",
        ))
    return findings


_FINDING_RULES = (
    _income_change_findings,
    _expense_change_findings,
    _category_trend_findings,
    _cashflow_findings,
    _debt_risk_findings,
    _emergency_fund_findings,
    _goal_feasibility_findings,
    _data_quality_findings,
)


def derive_findings(snapshot: FinancialSnapshot, trends: List[Trend]) -> List[Finding]:
    findings: List[Finding] = []
    for rule in _FINDING_RULES:
        findings.extend(rule(snapshot, trends))
    return findings


# --------------------------------------------------------------------------
# Risk Engine
# --------------------------------------------------------------------------
#
# MVP 1 scope is 6 risk types (Architecture Plan.md): negative cashflow,
# insufficient emergency fund, high-interest debt, high debt-service
# burden, overspending vs. budget, goal failure.

def _risk(
    risk_id: str, category: str, severity: str, urgency: str, likelihood: str, impact: str,
    metric_refs: list, finding_refs: list, mitigation_refs: list,
) -> Risk:
    return {
        "risk_id": risk_id, "category": category, "severity": severity, "urgency": urgency,
        "likelihood": likelihood, "impact": impact, "metric_refs": metric_refs,
        "finding_refs": finding_refs, "mitigation_refs": mitigation_refs,
    }


def _finding_ids_of_type(findings: List[Finding], *types: str) -> List[str]:
    return [f["finding_id"] for f in findings if f["type"] in types]


def _negative_cashflow_risk(snapshot: dict, findings: List[Finding]) -> List[Risk]:
    gross_surplus = snapshot["metrics"].get("gross_surplus")
    if gross_surplus is None or gross_surplus > 0:
        return []
    return [_risk(
        "RISK_NEGATIVE_CASHFLOW", "cashflow", "critical", "immediate", "high",
        "Savings will decline and debt may grow if the pattern continues.",
        ["gross_surplus", "emergency_fund_months"],
        _finding_ids_of_type(findings, "cashflow", "income_trend"), [],
    )]


def _insufficient_emergency_fund_risk(snapshot: dict, findings: List[Finding]) -> List[Risk]:
    months = snapshot["metrics"].get("emergency_fund_months")
    if months is None or months >= _EMERGENCY_FUND_TARGET_MONTHS / 2:
        return []
    return [_risk(
        "RISK_INSUFFICIENT_EMERGENCY_FUND", "savings", "high", "this_month", "high",
        "A single unexpected expense could force new debt.",
        ["emergency_fund_months"], _finding_ids_of_type(findings, "emergency_fund_risk"), [],
    )]


_HIGH_INTEREST_TOTAL_INTEREST_TO_DEBT_RATIO = 0.30


def _high_interest_debt_risk(snapshot: dict, findings: List[Finding]) -> List[Risk]:
    """Limitation: derive_risks()'s signature is (snapshot, findings) only,
    so this cannot inspect individual debt APRs directly (they are not in
    FinancialSnapshot.metrics). An earlier version of this rule compared
    avalanche vs. snowball total_interest as a proxy for "APR spread is
    high" - that is structurally broken, because the baseline
    debt_comparison in calculate_financial_snapshot() always simulates with
    extra_monthly=0.0 (it must not depend on Phase 3's roadmap allocation),
    and with no extra payment to allocate differently, avalanche and
    snowball produce byte-identical results regardless of the debts'
    APRs - the gap is always exactly zero. This rule instead compares
    total_interest accrued at minimums-only against total_debt: a high
    ratio means minimum payments are barely outpacing interest, which is
    what "high-interest debt" concretely costs the user, and is computable
    from data already in the baseline comparison."""
    metrics = snapshot["metrics"]
    total_debt = metrics.get("total_debt", 0.0)
    baseline = (snapshot.get("debt_comparison") or {}).get("avalanche")
    if not total_debt or not baseline:
        return []
    total_interest = baseline.get("total_interest", 0.0)
    if total_interest / total_debt < _HIGH_INTEREST_TOTAL_INTEREST_TO_DEBT_RATIO:
        return []
    return [_risk(
        "RISK_HIGH_INTEREST_DEBT", "debt", "high", "this_month", "high",
        "Paying only minimums accrues substantial interest relative to the balance.",
        ["total_debt"], _finding_ids_of_type(findings, "debt_risk"), [],
    )]


def _high_debt_service_burden_risk(snapshot: dict, findings: List[Finding]) -> List[Risk]:
    debt_to_income = snapshot["metrics"].get("debt_to_income_percent")
    if debt_to_income is None or debt_to_income < _DEBT_TO_INCOME_UNHEALTHY_PERCENT:
        return []
    return [_risk(
        "RISK_HIGH_DEBT_SERVICE_BURDEN", "debt", "high", "this_month", "high",
        "Required minimum payments leave little room for other priorities.",
        ["debt_to_income_percent"], _finding_ids_of_type(findings, "debt_risk"), [],
    )]


def _overspending_risk(snapshot: dict, findings: List[Finding]) -> List[Risk]:
    """Limitation: "overspending vs. budget" would ideally compare actual
    spend per 50/30/20 bucket against the recommendation
    (actual_budget_split()/recommended_budget()), but derive_risks()'s
    signature is (snapshot, findings) only and the bucketed split is not in
    FinancialSnapshot.metrics. This uses the sharp-expense-increase finding
    as a proxy for "overspending relative to recent history" instead of
    "overspending relative to the 50/30/20 recommendation" - a narrower
    claim than the risk's name implies."""
    sharp_expense_findings = [
        fid for fid in _finding_ids_of_type(findings, "expense_trend") if fid == "FINDING_EXPENSES_UP_SHARPLY"
    ]
    if not sharp_expense_findings:
        return []
    return [_risk(
        "RISK_OVERSPENDING", "spending", "medium", "this_month", "medium",
        "Sustained overspending erodes the surplus available for the roadmap.",
        ["average_monthly_expenses"], sharp_expense_findings, [],
    )]


def _goal_failure_risk(snapshot: dict, findings: List[Finding]) -> List[Risk]:
    goal_finding_ids = _finding_ids_of_type(findings, "goal_feasibility")
    if not goal_finding_ids:
        return []
    return [_risk(
        "RISK_GOAL_FAILURE", "goals", "medium", "next_90_days", "medium",
        "One or more goals will not be met on their current timeline without a change.",
        [], goal_finding_ids, [],
    )]


_RISK_RULES = (
    _negative_cashflow_risk,
    _insufficient_emergency_fund_risk,
    _high_interest_debt_risk,
    _high_debt_service_burden_risk,
    _overspending_risk,
    _goal_failure_risk,
)


def derive_risks(snapshot: FinancialSnapshot, findings: List[Finding]) -> List[Risk]:
    risks: List[Risk] = []
    for rule in _RISK_RULES:
        risks.extend(rule(snapshot, findings))
    return risks
