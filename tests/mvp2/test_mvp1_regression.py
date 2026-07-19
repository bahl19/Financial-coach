"""Phase MVP2-0, Task B: the frozen MVP 1 regression baseline.

This is the No-regression Rule's "frozen MVP 1 tests and goldens" layer
(`Implementation Plan - MVP 2.md`, section 1.4), made explicit as its own
suite rather than relying only on `tests/test_golden.py` continuing to
exist. It runs the three accepted baseline profiles through the exact same
canonical pipeline `tests/test_golden.py` uses (imported, not re-implemented
- a second copy of the pipeline call sequence would itself be exactly the
kind of drift this suite exists to catch) and compares every frozen
numeric/enum/ID/priority/severity/allocation/validation/report value against
`fixtures/mvp2/mvp1_baseline_manifest.json` and
`fixtures/mvp2/mvp1_baseline_health_scores.json`.

No test in this file may import anything from an `mvp2` domain package -
none exists yet (Phase MVP2-1 creates the first one). This file is pure
test infrastructure over frozen MVP 1 contracts.
"""

from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path

import pytest

from tests.test_golden import GOLDEN_NAMES, _load_expected, _load_profile, _run_pipeline, capture_golden
from utils import reporting

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
GOLDEN_DIR = REPO_ROOT / "fixtures" / "golden"
MANIFEST_PATH = REPO_ROOT / "fixtures" / "mvp2" / "mvp1_baseline_manifest.json"
HEALTH_SCORES_PATH = REPO_ROOT / "fixtures" / "mvp2" / "mvp1_baseline_health_scores.json"

# RoadmapAllocation's exact field names (utils/contracts.py). Used by the
# second-allocation-implementation scan below - a dict literal that sets
# most of these together, outside utils/roadmap.py, would mean a second
# module is constructing a full allocation object of its own.
_ALLOCATION_FIELD_NAMES = frozenset(
    {"buffer_reserved", "debt_extra_payment", "goal_contributions", "savings_contribution", "investment_contribution"}
)
_ALLOCATION_SHAPE_THRESHOLD = 3  # sharing this many field names together is not a coincidence

_SCAN_EXCLUDED_DIRS = {".venv", "__pycache__", ".git", ".hypothesis", ".pytest_cache"}
_ALLOCATION_AUTHORITY_FILE = REPO_ROOT / "utils" / "roadmap.py"


@pytest.fixture(scope="module")
def manifest() -> dict:
    with MANIFEST_PATH.open() as f:
        return json.load(f)


@pytest.fixture(scope="module")
def baseline_health_scores() -> dict:
    with HEALTH_SCORES_PATH.open() as f:
        return json.load(f)


def _sha256_of(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


# --------------------------------------------------------------------------
# Manifest integrity
# --------------------------------------------------------------------------

def test_manifest_records_the_current_phase11_done_commit(manifest):
    import subprocess

    tagged_commit = subprocess.check_output(["git", "rev-list", "-n", "1", "phase11-done"]).decode().strip()
    assert manifest["accepted_commit_sha"] == tagged_commit


@pytest.mark.parametrize("name", GOLDEN_NAMES)
def test_manifest_golden_hashes_match_committed_fixtures(manifest, name):
    """A silent edit to a frozen golden fixture must be visible as a hash
    mismatch here, independent of whether the edited value happens to still
    pass test_golden.py's equality check."""
    recorded = manifest["golden_fixtures"][name]
    assert _sha256_of(GOLDEN_DIR / f"{name}.input.json") == recorded["input_sha256"]
    assert _sha256_of(GOLDEN_DIR / f"{name}.expected.json") == recorded["expected_sha256"]


# --------------------------------------------------------------------------
# Frozen structured output, reproduced from the manifest's accepted baseline
# --------------------------------------------------------------------------

@pytest.mark.golden
@pytest.mark.parametrize("name", GOLDEN_NAMES)
def test_baseline_profile_reproduces_frozen_structured_output(name):
    actual = capture_golden(_load_profile(name))
    expected = _load_expected(name)
    assert actual == expected


@pytest.mark.golden
@pytest.mark.parametrize("name", GOLDEN_NAMES)
def test_baseline_health_score_and_band_unchanged(name, baseline_health_scores):
    """MVP 1's health_score/health_band are excluded from
    tests/test_golden.py's captured projection (Phase 6 scope was
    allocation/finding/risk/priority numbers only), so this is the one place
    that actually enforces Implementation Plan - MVP 2.md's explicit
    requirement: 'Assert MVP 1 FinancialSnapshot.health_score remains
    unchanged. MVP 2 later adds a separate FinancialResilienceScore; it must
    not rewrite this field.'"""
    profile = _load_profile(name)
    snapshot, _trends, _findings, _risks, _result = _run_pipeline(profile)
    expected = baseline_health_scores[name]
    assert snapshot["health_score"] == expected["health_score"]
    assert snapshot["health_band"] == expected["health_band"]


@pytest.mark.golden
def test_deliberate_allocation_cent_change_fails_regression():
    """Required test (Implementation Plan - MVP 2.md, Phase MVP2-0):
    'Deliberately changing one allocation cent fails regression.' Perturbs
    the in-memory expected structure (not the committed fixture file) so
    this test needs no manual revert step and cannot leave the repository
    dirty on failure."""
    name = "income_drop_rising_dining"
    actual = capture_golden(_load_profile(name))
    tampered_expected = json.loads(json.dumps(_load_expected(name)))
    tampered_expected["roadmap_allocation"]["savings_contribution"] += 0.01
    assert actual != tampered_expected


@pytest.mark.golden
def test_deliberate_severity_change_fails_regression():
    """Required test: 'Deliberately changing one score, severity, priority,
    or ID fails regression.'"""
    name = "income_drop_rising_dining"
    actual = capture_golden(_load_profile(name))
    tampered_expected = json.loads(json.dumps(_load_expected(name)))
    tampered_expected["findings"][0]["severity"] = "positive"
    assert actual != tampered_expected


@pytest.mark.golden
def test_narrative_only_variation_does_not_fail_regression():
    """Required test: 'Narrative-only variation permitted by MVP 1 does not
    fail a structured golden.' Delegates to test_golden.py's own dedicated
    test for this rather than re-implementing the narrative-rewrite logic -
    that test already proves it; re-running it here would just be a second
    copy of the same assertion under a different name."""
    from tests.test_golden import test_golden_fixture_ignores_narrative_reword

    test_golden_fixture_ignores_narrative_reword("income_drop_rising_dining")


# --------------------------------------------------------------------------
# One allocation authority
# --------------------------------------------------------------------------

def _iter_source_files():
    for path in REPO_ROOT.rglob("*.py"):
        if any(part in _SCAN_EXCLUDED_DIRS for part in path.parts):
            continue
        if "tests" in path.parts or path.parts[-2:-1] == ("mvp2",):
            continue
        yield path


def _dict_literal_allocation_field_overlap(tree: ast.AST) -> list:
    hits = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Dict):
            keys = {k.value for k in node.keys if isinstance(k, ast.Constant) and isinstance(k.value, str)}
            overlap = keys & _ALLOCATION_FIELD_NAMES
            if len(overlap) >= _ALLOCATION_SHAPE_THRESHOLD:
                hits.append(sorted(overlap))
    return hits


def test_only_one_build_roadmap_function_exists_in_source():
    """Required test companion to Implementation Plan - MVP 2.md's Task B:
    'Add a test that scans for a second allocation implementation.'"""
    definitions = []
    for path in _iter_source_files():
        tree = ast.parse(path.read_text(), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == "build_roadmap":
                definitions.append(path)
    assert definitions == [_ALLOCATION_AUTHORITY_FILE]


def test_only_one_allocation_ledger_class_exists_in_source():
    definitions = []
    for path in _iter_source_files():
        tree = ast.parse(path.read_text(), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and "ledger" in node.name.lower():
                definitions.append(path)
    assert definitions == [_ALLOCATION_AUTHORITY_FILE]


def test_no_second_module_constructs_a_roadmap_allocation_shaped_dict():
    offenders = {}
    for path in _iter_source_files():
        if path == _ALLOCATION_AUTHORITY_FILE:
            continue
        tree = ast.parse(path.read_text(), filename=str(path))
        hits = _dict_literal_allocation_field_overlap(tree)
        if hits:
            offenders[str(path.relative_to(REPO_ROOT))] = hits
    assert offenders == {}


def test_allocation_scan_actually_detects_a_planted_second_allocator(tmp_path):
    """Required test: 'Dependency-boundary test rejects a deliberately
    created reverse-import fixture' has its allocation-scan analogue here -
    proves the scanner above is not vacuously passing because it never
    matches anything."""
    planted = tmp_path / "fake_second_allocator.py"
    planted.write_text(
        "def sneaky():\n"
        "    return {\n"
        "        'buffer_reserved': 0.0,\n"
        "        'debt_extra_payment': 50.0,\n"
        "        'goal_contributions': {},\n"
        "        'savings_contribution': 25.0,\n"
        "    }\n"
    )
    tree = ast.parse(planted.read_text(), filename=str(planted))
    hits = _dict_literal_allocation_field_overlap(tree)
    assert hits == [["buffer_reserved", "debt_extra_payment", "goal_contributions", "savings_contribution"]]


# --------------------------------------------------------------------------
# Baseline report reproducibility
# --------------------------------------------------------------------------

@pytest.mark.golden
@pytest.mark.parametrize("name", GOLDEN_NAMES)
def test_baseline_report_generation_is_reproducible_from_frozen_inputs(name):
    """Required test: 'Add a test that baseline report generation is
    reproducible from the same frozen inputs.' Runs the pipeline + report
    builder twice from the same frozen profile and asserts byte-identical
    output - `utils.reporting` has no clock/random dependency, so any
    divergence would indicate hidden non-determinism, not expected drift."""
    profile = _load_profile(name)

    snapshot_a, trends_a, findings_a, risks_a, result_a = _run_pipeline(profile)
    report_a = reporting.build_report(
        profile, snapshot_a, trends_a, findings_a, risks_a, result_a["roadmap_result"], result_a["coach_summary"]
    )

    snapshot_b, trends_b, findings_b, risks_b, result_b = _run_pipeline(profile)
    report_b = reporting.build_report(
        profile, snapshot_b, trends_b, findings_b, risks_b, result_b["roadmap_result"], result_b["coach_summary"]
    )

    assert report_a == report_b
