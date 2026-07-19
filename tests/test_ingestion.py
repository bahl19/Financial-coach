"""Phase 1 tests: utils/ingestion.py (Component 2).

Each test maps to a Phase 1 exit-gate item in `Implementation Plan - MVP 1.md`
that concerns ingestion, categorization, or data-quality detection.
"""

import json
from pathlib import Path

import pandas as pd
import pytest

from utils import ingestion

REPO_ROOT = Path(__file__).resolve().parent.parent
FIXTURES_DIR = REPO_ROOT / "fixtures"


def _load(path: Path) -> dict:
    with path.open() as f:
        return json.load(f)


def _transactions_frame(records: list) -> pd.DataFrame:
    df = pd.DataFrame(records)
    df["date"] = pd.to_datetime(df["date"])
    return df


# --------------------------------------------------------------------------
# Gate: "An unmatched expense is Other, confidence 0.0, appears in the
# review list"
# --------------------------------------------------------------------------

def test_unmatched_expense_is_other_with_zero_confidence_and_needs_review():
    raw = pd.DataFrame([
        {"date": "2026-05-01", "description": "ACME PAYMENTS XYZ123", "amount": -45.0},
    ])
    raw["date"] = pd.to_datetime(raw["date"])
    categorized = ingestion.categorize_with_confidence(raw)

    row = categorized.iloc[0]
    assert row["category"] == "Other"
    assert row["category_confidence"] == 0.0
    assert row["needs_review"] is True or row["needs_review"] == True  # noqa: E712 (pandas bool)


def test_unmatched_expense_appears_in_review_items():
    raw = pd.DataFrame([
        {"date": "2026-05-01", "description": "ACME PAYMENTS XYZ123", "amount": -45.0},
        {"date": "2026-05-02", "description": "Whole Foods", "amount": -80.0},
    ])
    raw["date"] = pd.to_datetime(raw["date"])
    categorized = ingestion.categorize_with_confidence(raw)
    items = ingestion.build_review_items(categorized)

    assert len(items) == 1
    assert items[0]["description"] == "ACME PAYMENTS XYZ123"
    assert items[0]["suggested_category"] == "Other"
    assert items[0]["reason"]


def test_matched_expense_is_not_flagged_for_review():
    raw = pd.DataFrame([{"date": "2026-05-01", "description": "Whole Foods", "amount": -80.0}])
    raw["date"] = pd.to_datetime(raw["date"])
    categorized = ingestion.categorize_with_confidence(raw)
    assert categorized.iloc[0]["category"] == "Groceries"
    assert categorized.iloc[0]["category_confidence"] == 1.0
    assert ingestion.build_review_items(categorized) == []


def test_unmatched_positive_amount_is_income_not_other():
    """The sign of an amount is an observed fact, not a guess - an
    unmatched deposit is Income at full confidence, not Other."""
    raw = pd.DataFrame([{"date": "2026-05-01", "description": "MYSTERY DEPOSIT CORP", "amount": 500.0}])
    raw["date"] = pd.to_datetime(raw["date"])
    categorized = ingestion.categorize_with_confidence(raw)
    assert categorized.iloc[0]["category"] == "Income"
    assert categorized.iloc[0]["category_confidence"] == 1.0
    assert categorized.iloc[0]["needs_review"] == False  # noqa: E712


# --------------------------------------------------------------------------
# Gate: "A user category correction persists into the profile used by
# calculation" - this is a UI/session-state concern (Phase 8), but the
# contract-level guarantee Phase 1 owns is that categorize_with_confidence()
# never mutates its input, so a corrected copy safely coexists with the
# original.
# --------------------------------------------------------------------------

def test_categorize_with_confidence_does_not_mutate_input():
    raw = pd.DataFrame([{"date": "2026-05-01", "description": "Whole Foods", "amount": -80.0}])
    raw["date"] = pd.to_datetime(raw["date"])
    original_columns = list(raw.columns)

    ingestion.categorize_with_confidence(raw)

    assert list(raw.columns) == original_columns


def test_a_correction_written_to_a_copy_does_not_affect_the_original():
    raw = pd.DataFrame([{"date": "2026-05-01", "description": "ACME PAYMENTS", "amount": -45.0}])
    raw["date"] = pd.to_datetime(raw["date"])
    categorized = ingestion.categorize_with_confidence(raw)

    corrected = categorized.copy()
    corrected.loc[0, "category"] = "Shopping"
    corrected.loc[0, "needs_review"] = False

    assert categorized.iloc[0]["category"] == "Other"  # original untouched
    assert corrected.iloc[0]["category"] == "Shopping"


# --------------------------------------------------------------------------
# Gate: "Existing sample data still loads without new required columns"
# --------------------------------------------------------------------------

def test_existing_sample_csv_loads_and_categorizes_without_new_columns():
    sample_path = REPO_ROOT / "data" / "sample_transactions.csv"
    df = pd.read_csv(sample_path)
    df.columns = [c.strip().lower() for c in df.columns]
    assert {"date", "description", "amount"}.issubset(df.columns)

    df["date"] = pd.to_datetime(df["date"])
    categorized = ingestion.categorize_with_confidence(df)
    tagged = ingestion.tag_transaction_types(categorized)
    assert "category" in tagged.columns
    assert "transaction_type" in tagged.columns
    assert len(tagged) == len(df)


# --------------------------------------------------------------------------
# Gate: "A Debt Payment-categorized transaction is tagged
# transaction_type: 'debt_payment'"
# --------------------------------------------------------------------------

def test_debt_payment_category_is_tagged_debt_payment_type():
    raw = pd.DataFrame([{"date": "2026-05-01", "description": "Credit Card Payment", "amount": -120.0}])
    raw["date"] = pd.to_datetime(raw["date"])
    categorized = ingestion.categorize_with_confidence(raw)
    assert categorized.iloc[0]["category"] == "Debt Payment"

    tagged = ingestion.tag_transaction_types(categorized)
    assert tagged.iloc[0]["transaction_type"] == "debt_payment"


def test_tag_transaction_types_requires_categorization_first():
    raw = pd.DataFrame([{"date": "2026-05-01", "description": "Visa Payment", "amount": -120.0}])
    raw["date"] = pd.to_datetime(raw["date"])
    with pytest.raises(ValueError):
        ingestion.tag_transaction_types(raw)


def test_income_and_expense_types_derive_from_amount_sign_when_uncategorized_specially():
    raw = pd.DataFrame([
        {"date": "2026-05-01", "description": "Employer Payroll", "amount": 5000.0},
        {"date": "2026-05-02", "description": "ACME PAYMENTS", "amount": -45.0},
    ])
    raw["date"] = pd.to_datetime(raw["date"])
    tagged = ingestion.tag_transaction_types(ingestion.categorize_with_confidence(raw))
    assert tagged.iloc[0]["transaction_type"] == "income"
    assert tagged.iloc[1]["transaction_type"] == "expense"


# --------------------------------------------------------------------------
# questionnaire_to_profile_fields
# --------------------------------------------------------------------------

def test_questionnaire_preserves_blank_answers_as_none_not_zero():
    fields = ingestion.questionnaire_to_profile_fields({"monthly_income": "", "current_savings": None})
    assert fields["monthly_income"] is None
    assert fields["current_savings"] is None


def test_questionnaire_defaults_missing_debts_goals_to_empty_list():
    fields = ingestion.questionnaire_to_profile_fields({"monthly_income": 5000.0})
    assert fields["debts"] == []
    assert fields["goals"] == []


# --------------------------------------------------------------------------
# Gate: "A fixture with a duplicated transaction and a missing month
# produces the corresponding data_quality_flags"
# --------------------------------------------------------------------------

def test_duplicate_and_missing_month_fixture_produces_both_flags():
    profile = _load(FIXTURES_DIR / "data_quality_duplicate_and_missing_month.json")
    df = _transactions_frame(profile["transactions"])

    flags = ingestion.detect_data_quality_issues(df)
    codes = {flag["code"] for flag in flags}

    assert "DUPLICATE_TRANSACTIONS" in codes
    assert "MISSING_MONTHS" in codes


def test_missing_months_flag_names_the_actual_missing_month():
    profile = _load(FIXTURES_DIR / "data_quality_duplicate_and_missing_month.json")
    df = _transactions_frame(profile["transactions"])
    flags = ingestion.detect_data_quality_issues(df)
    missing_flag = next(f for f in flags if f["code"] == "MISSING_MONTHS")
    assert "2026-02" in missing_flag["detail"]


def test_empty_transactions_produce_no_transactions_flag_not_a_crash():
    df = pd.DataFrame(columns=["date", "description", "amount", "category"])
    flags = ingestion.detect_data_quality_issues(df)
    assert flags == [{
        "code": "NO_TRANSACTIONS",
        "detail": "No transactions were provided",
        "affects": ["every snapshot metric"],
    }]


def test_zero_income_transactions_are_flagged():
    raw = pd.DataFrame([
        {"date": "2026-05-01", "description": "Whole Foods", "amount": -80.0},
        {"date": "2026-06-01", "description": "Whole Foods", "amount": -85.0},
    ])
    raw["date"] = pd.to_datetime(raw["date"])
    flags = ingestion.detect_data_quality_issues(raw)
    codes = {flag["code"] for flag in flags}
    assert "ZERO_INCOME_TRANSACTIONS" in codes


def test_no_duplicate_flag_when_transactions_are_genuinely_distinct():
    profile = _load(FIXTURES_DIR / "golden" / "stable_high_surplus.input.json")
    df = _transactions_frame(profile["transactions"])
    flags = ingestion.detect_data_quality_issues(df)
    codes = {flag["code"] for flag in flags}
    assert "DUPLICATE_TRANSACTIONS" not in codes
    assert "MISSING_MONTHS" not in codes


# --------------------------------------------------------------------------
# Region-aware categorization: category_keywords(region) and the optional
# keyword_table parameter it threads into categorize_with_confidence().
# --------------------------------------------------------------------------

def test_india_region_keywords_match_the_legacy_module_default_exactly():
    # "india" must reproduce today's CATEGORY_KEYWORDS byte-for-byte - it was
    # the only table that existed before the region split.
    assert ingestion.category_keywords("india") == ingestion.CATEGORY_KEYWORDS


def test_generic_region_excludes_india_only_vendor_keywords():
    generic_words = {w for words in ingestion.category_keywords("generic").values() for w in words}
    assert "swiggy" not in generic_words
    assert "bigbasket" not in generic_words
    assert "emi" not in generic_words
    # Region-neutral/US brand keywords still present.
    assert "starbucks" in generic_words
    assert "whole foods" in generic_words


def test_unknown_region_falls_back_to_india():
    assert ingestion.category_keywords("atlantis") == ingestion.category_keywords("india")


def test_categorize_with_confidence_respects_explicit_keyword_table():
    raw = pd.DataFrame([{"date": "2026-05-01", "description": "Swiggy order", "amount": -20.0}])
    raw["date"] = pd.to_datetime(raw["date"])

    india_categorized = ingestion.categorize_with_confidence(raw, ingestion.category_keywords("india"))
    assert india_categorized.iloc[0]["category"] == "Dining"

    generic_categorized = ingestion.categorize_with_confidence(raw, ingestion.category_keywords("generic"))
    assert generic_categorized.iloc[0]["category"] == "Other"
    assert generic_categorized.iloc[0]["category_confidence"] == 0.0


def test_categorize_with_confidence_defaults_to_india_region_without_a_table_argument():
    raw = pd.DataFrame([{"date": "2026-05-01", "description": "Swiggy order", "amount": -20.0}])
    raw["date"] = pd.to_datetime(raw["date"])
    categorized = ingestion.categorize_with_confidence(raw)
    assert categorized.iloc[0]["category"] == "Dining"
