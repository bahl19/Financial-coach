"""Ingestion boundary (Architecture Plan.md, Component 2).

This is the only layer tolerant of messy input - a missing column, an
unmatched category, a malformed date are all handled here. Everything past
this boundary (utils/finance_calc.py, Component 3) is entitled to assume a
transaction already carries `category`, `category_confidence`, `needs_review`,
and `transaction_type`.

Depends only on utils/contracts.py and agents/data_agent.py's tolerant file
parsing, per Component 2's declared dependencies. It does not import from
utils/finance_calc.py (Component 3) and finance_calc.py must not import from
here - the two components each depend only on contracts.py, not on each other.

As of Phase 8, `utils/finance_calc.py`'s older `categorize_transactions()`/
`CATEGORY_KEYWORDS` have been retired - `app.py` categorizes exclusively
through this module's `categorize_with_confidence()`, so only one keyword
table remains in the codebase.
"""

from __future__ import annotations

from typing import List, Optional

import pandas as pd

from agents.data_agent import DataIngestionAgent
from utils.contracts import ReviewItem
from utils.region import DEFAULT_REGION, resolve_region

# --------------------------------------------------------------------------
# Category-confidence keyword catalogue (Component 2 owns this)
# --------------------------------------------------------------------------
#
# Split into a region-neutral base table (generic terms + widely-known/US
# brands) and a per-region add-on layered on top by category_keywords().
# "india" reproduces the original, pre-region-selector CATEGORY_KEYWORDS
# exactly - it was the only table that existed before this split.

_BASE_CATEGORY_KEYWORDS = {
    "Rent/Mortgage": ["rent", "mortgage", "landlord", "apartments"],
    "Groceries": ["grocery", "groceries", "supermarket", "whole foods", "trader joe", "safeway", "kroger"],
    "Dining": ["restaurant", "cafe", "coffee", "starbucks", "doordash", "ubereats", "grubhub", "mcdonald", "chipotle", "rooftop"],
    "Transport": ["uber", "lyft", "gas station", "shell", "chevron", "exxon", "parking", "transit", "metro", "fuel"],
    "Utilities": ["electric", "water bill", "gas bill", "internet", "comcast", "at&t", "verizon", "utility", "broadband"],
    "Subscriptions": ["netflix", "spotify", "hulu", "amazon prime", "subscription", "gym", "planet fitness"],
    "Entertainment": ["movie", "cinema", "amc", "concert", "steam", "playstation", "xbox", "tickets"],
    "Shopping": ["amazon.com", "target", "walmart", "best buy", "mall"],
    "Insurance": ["insurance", "geico", "state farm"],
    "Healthcare": ["pharmacy", "cvs", "walgreens", "doctor", "clinic", "hospital"],
    "Debt Payment": ["credit card payment", "loan payment", "student loan", "auto loan", "personal loan", "home loan", "car loan"],
    "Savings/Investing": ["transfer to savings", "401k", "ira contribution", "brokerage", "investment", "mutual fund"],
}

_INDIA_CATEGORY_KEYWORDS = {
    "Rent/Mortgage": ["house rent", "flat owner"],
    "Groceries": ["bigbasket", "big basket", "dmart", "d-mart", "reliance fresh", "reliance smart", "more supermarket", "jiomart", "nature's basket", "spencer's"],
    "Dining": ["swiggy", "zomato", "dominos", "cafe coffee day", "ccd"],
    "Transport": ["ola", "rapido", "irctc", "petrol", "petrol pump", "hpcl", "bpcl", "indian oil"],
    "Utilities": ["bescom", "electricity board", "discom", "jio", "airtel", "vodafone", "vi ", "gas cylinder", "lpg"],
    "Subscriptions": ["hotstar", "jiocinema", "sonyliv", "cult.fit", "cultfit"],
    "Entertainment": ["pvr", "inox", "bookmyshow"],
    "Shopping": ["amazon.in", "flipkart", "myntra", "ajio"],
    "Insurance": ["lic", "policybazaar", "hdfc life", "sbi life"],
    "Healthcare": ["apollo pharmacy", "1mg", "practo", "medplus", "netmeds"],
    "Debt Payment": ["emi"],
    "Savings/Investing": ["sip", "zerodha", "groww", "ppf", "nps", "recurring deposit", "rd deposit", "fixed deposit"],
}

_REGION_ADD_ONS = {
    "india": _INDIA_CATEGORY_KEYWORDS,
    "generic": {},
}


def category_keywords(region: str = DEFAULT_REGION) -> dict:
    """Returns the base keyword table plus the given region's add-on. Never
    mutates either source table."""
    merged = {category: list(words) for category, words in _BASE_CATEGORY_KEYWORDS.items()}
    for category, extra in _REGION_ADD_ONS[resolve_region(region)].items():
        merged.setdefault(category, []).extend(extra)
    return merged


# Kept as a module-level default (today's behavior, byte-identical) so every
# existing call site and test that references CATEGORY_KEYWORDS directly, or
# calls categorize_with_confidence()/_match_category() without a region,
# keeps working unchanged.
CATEGORY_KEYWORDS = category_keywords(DEFAULT_REGION)

_UNMATCHED_CATEGORY = "Other"
_MATCHED_CONFIDENCE = 1.0
_UNMATCHED_CONFIDENCE = 0.0

# Cheap, category-derived transaction_type tagging (not a dedicated classifier;
# Architecture Plan.md, Component 2). Any category not listed here is typed
# by amount sign alone: positive -> income, negative -> expense.
_CATEGORY_TO_TRANSACTION_TYPE = {
    "Debt Payment": "debt_payment",
    "Income": "income",
    "Savings/Investing": "savings_transfer",
}


def _match_category(description: str, amount: float, keyword_table: dict = None) -> tuple:
    """Returns (category, confidence). A keyword match is full confidence.
    An unmatched positive amount is "Income" at full confidence (the sign is
    an observed fact, not a guess). An unmatched negative amount is "Other"
    at zero confidence and must be reviewed - it is never silently guessed."""
    desc = str(description).lower()
    for category, keywords in (keyword_table if keyword_table is not None else CATEGORY_KEYWORDS).items():
        if any(keyword in desc for keyword in keywords):
            return category, _MATCHED_CONFIDENCE
    if amount > 0:
        return "Income", _MATCHED_CONFIDENCE
    return _UNMATCHED_CATEGORY, _UNMATCHED_CONFIDENCE


def load_transactions(uploaded_file) -> pd.DataFrame:
    """Parses an uploaded CSV/PDF statement into a raw (date, description,
    amount) dataframe. The tolerant parsing itself is owned by
    agents.data_agent.DataIngestionAgent; this function is the Component 2
    entry point the rest of the pipeline calls."""
    return DataIngestionAgent().load(uploaded_file)


def categorize_with_confidence(transactions: pd.DataFrame, keyword_table: dict = None) -> pd.DataFrame:
    """Assigns category, category_confidence, and needs_review to every
    transaction. Returns a new dataframe; never mutates the input.

    An unmatched transaction is categorized "Other" at confidence 0.0 and
    flagged needs_review=True - it is surfaced for a human decision, never
    silently guessed at.

    `keyword_table` defaults to CATEGORY_KEYWORDS (today's India-region
    table) - pass `category_keywords(region)` for a region-aware call."""
    out = transactions.copy()
    categories: List[str] = []
    confidences: List[float] = []
    for _, row in out.iterrows():
        category, confidence = _match_category(row["description"], row["amount"], keyword_table)
        categories.append(category)
        confidences.append(confidence)
    out["category"] = categories
    out["category_confidence"] = confidences
    out["needs_review"] = out["category_confidence"] < _MATCHED_CONFIDENCE
    return out


def tag_transaction_types(transactions: pd.DataFrame) -> pd.DataFrame:
    """Cheap, category-derived transaction_type tagging. Requires `category`
    to already be assigned (run categorize_with_confidence() first) - this
    function adds no categorization judgment of its own, only a lookup."""
    if "category" not in transactions.columns:
        raise ValueError("tag_transaction_types() requires categorize_with_confidence() to run first")
    out = transactions.copy()
    fallback = out["amount"].apply(lambda amount: "income" if amount > 0 else "expense")
    out["transaction_type"] = out["category"].map(_CATEGORY_TO_TRANSACTION_TYPE).fillna(fallback)
    return out


def apply_category_corrections(transactions: pd.DataFrame, corrections: dict) -> pd.DataFrame:
    """Applies user-supplied category corrections (`transaction_index ->
    new category`, as produced by a category-review UI) on top of an
    already-`categorize_with_confidence()`'d frame. A corrected row is full
    confidence and no longer needs review. `transaction_type` is re-tagged
    afterward since it is category-derived (`tag_transaction_types()`) - a
    corrected category left pointing at its pre-correction type would be a
    silent inconsistency. Returns a new dataframe; never mutates the input."""
    out = transactions.copy()
    for index, category in corrections.items():
        out.loc[index, "category"] = category
        out.loc[index, "category_confidence"] = _MATCHED_CONFIDENCE
        out.loc[index, "needs_review"] = False
    return tag_transaction_types(out)


def build_review_items(transactions: pd.DataFrame) -> List[ReviewItem]:
    """Builds the review queue from every transaction flagged needs_review.
    Requires categorize_with_confidence() to have already run."""
    if "needs_review" not in transactions.columns:
        raise ValueError("build_review_items() requires categorize_with_confidence() to run first")
    items: List[ReviewItem] = []
    for index, row in transactions.iterrows():
        if not row["needs_review"]:
            continue
        items.append({
            "transaction_index": int(index),
            "description": row["description"],
            "amount": float(row["amount"]),
            "suggested_category": row["category"],
            "reason": "No matching category keyword",
        })
    return items


def _blank_to_none(value):
    """An absent or blank questionnaire answer is unknown, not zero or empty
    string - Contract rule 3 (Architecture Plan.md)."""
    return value if value not in (None, "") else None


def questionnaire_to_profile_fields(form_values: dict) -> dict:
    """Maps a manual-entry questionnaire's raw form values onto
    FinancialProfile fields, for users without a statement to upload."""
    return {
        "monthly_income": _blank_to_none(form_values.get("monthly_income")),
        "current_savings": _blank_to_none(form_values.get("current_savings")),
        "debts": form_values.get("debts") or [],
        "goals": form_values.get("goals") or [],
        "constraints": {
            "minimum_monthly_buffer": form_values.get("minimum_monthly_buffer") or 0.0,
            "protected_categories": form_values.get("protected_categories") or [],
        },
    }


# --------------------------------------------------------------------------
# Data quality detection
# --------------------------------------------------------------------------
#
# Each check is an independent predicate over the transaction frame,
# answering one question, individually testable. This is deliberately a
# handful of cheap checks, not the full anomaly engine (Architecture Plan.md,
# Data Quality Detection) - that stays in the Production tier.

_MINIMUM_COMPLETE_MONTHS = 2


def _duplicate_transaction_flag(transactions: pd.DataFrame) -> Optional[dict]:
    duplicate_mask = transactions.duplicated(subset=["date", "description", "amount"], keep=False)
    count = int(duplicate_mask.sum())
    if count == 0:
        return None
    return {
        "code": "DUPLICATE_TRANSACTIONS",
        "detail": f"{count} exact duplicate rows (same date, description, and amount)",
        "affects": ["average_monthly_expenses", "gross_surplus"],
    }


def _missing_months_flag(transactions: pd.DataFrame) -> Optional[dict]:
    dates = pd.to_datetime(transactions["date"])
    months_present = set(dates.dt.to_period("M"))
    if not months_present:
        return None
    full_range = pd.period_range(min(months_present), max(months_present), freq="M")
    missing = sorted(str(month) for month in full_range if month not in months_present)
    if not missing:
        return None
    return {
        "code": "MISSING_MONTHS",
        "detail": f"No transactions found for: {', '.join(missing)}",
        "affects": ["average_monthly_expenses", "trend calculations"],
    }


def _partial_trailing_month_flag(transactions: pd.DataFrame) -> Optional[dict]:
    dates = pd.to_datetime(transactions["date"])
    last_date = dates.max()
    month_end = last_date.to_period("M").end_time
    if last_date.normalize() < month_end.normalize():
        return {
            "code": "PARTIAL_TRAILING_MONTH",
            "detail": f"Latest month's data ends {last_date.date()}, before month-end",
            "affects": ["average_monthly_expenses", "the latest month's trend"],
        }
    return None


def _insufficient_history_flag(transactions: pd.DataFrame) -> Optional[dict]:
    dates = pd.to_datetime(transactions["date"])
    complete_months = dates.dt.to_period("M").nunique()
    if complete_months < _MINIMUM_COMPLETE_MONTHS:
        return {
            "code": "INSUFFICIENT_HISTORY",
            "detail": f"Only {complete_months} month(s) of transaction history available",
            "affects": ["average_monthly_expenses", "trend calculations"],
        }
    return None


def _zero_income_flag(transactions: pd.DataFrame) -> Optional[dict]:
    if (transactions["amount"] > 0).any():
        return None
    return {
        "code": "ZERO_INCOME_TRANSACTIONS",
        "detail": "No income transactions found in the uploaded history",
        "affects": ["gross_surplus", "savings_rate_percent"],
    }


_DATA_QUALITY_CHECKS = (
    _duplicate_transaction_flag,
    _missing_months_flag,
    _partial_trailing_month_flag,
    _insufficient_history_flag,
    _zero_income_flag,
)


def detect_data_quality_issues(transactions: pd.DataFrame) -> List[dict]:
    """Runs the fixed set of data-quality predicates above. Returns a list
    of flags (possibly empty); never raises on malformed input."""
    if transactions.empty:
        return [{
            "code": "NO_TRANSACTIONS",
            "detail": "No transactions were provided",
            "affects": ["every snapshot metric"],
        }]
    flags = []
    for check in _DATA_QUALITY_CHECKS:
        flag = check(transactions)
        if flag is not None:
            flags.append(flag)
    return flags
