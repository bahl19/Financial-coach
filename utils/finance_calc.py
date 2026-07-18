"""Deterministic financial calculations.

This module is the "tabular RAG" retrieval/compute layer: agents pull
aggregates and slices out of the raw transactions dataframe here, then
hand those numbers to the LLM (or the offline fallback) as grounded
context instead of letting the model guess at figures.

Convention for uploaded/sample transaction data: expenses are negative
amounts, income/deposits are positive amounts.
"""
import pandas as pd

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


def actual_budget_split(df: pd.DataFrame) -> dict:
    """Average monthly spend per 50/30/20 bucket, so it's comparable to a
    single month's recommended budget rather than an all-time total."""
    num_months = max(df["date"].dt.to_period("M").nunique(), 1)
    by_cat = spending_by_category(df)
    result = {"Needs": 0.0, "Wants": 0.0, "Savings": 0.0}
    for _, row in by_cat.iterrows():
        if row["category"] in NEEDS_CATS:
            result["Needs"] += row["amount"]
        elif row["category"] in SAVINGS_CATS:
            result["Savings"] += row["amount"]
        else:
            result["Wants"] += row["amount"]
    return {k: v / num_months for k, v in result.items()}


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
