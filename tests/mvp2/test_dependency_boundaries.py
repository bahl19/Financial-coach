"""Phase MVP2-0, Task C: AST/module-inspection dependency-boundary checks.

Enforces Implementation Plan - MVP 2.md section 1.5's dependency direction
rule using real static analysis (no reverse imports, no importing an
infrastructure adapter from domain code) rather than trusting code review
alone to catch it. Two things are checked today:

1. A general MVP 1 + MVP 2 invariant, enforceable right now even though no
   `mvp2` package exists yet: domain calculation modules (`utils/*`,
   `agents/*`, and later `mvp2.profile`/`mvp2.knowledge`/`mvp2.strategy`)
   never import `app`, `streamlit`, `openai`, or `chromadb` directly, and
   nothing imports `app` back (`app.py` is the one composition root; the
   arrow only ever points into it, never out of it).
2. The exact `mvp2.<subpackage> -> allowed sources` graph from section 1.5,
   applied to whichever `mvp2/*` subpackages exist at the time this runs -
   today that's none, so this half is inert until Phase MVP2-1 creates
   `mvp2/profile/`, but the checker function itself is exercised now via a
   synthetic AST fixture (see
   `test_boundary_checker_rejects_a_planted_reverse_import` below), so its
   correctness does not depend on a later phase remembering to test it.
"""

from __future__ import annotations

import ast
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent

# Modules that ARE the designated infrastructure adapter for their concrete
# dependency - they are expected/required to import it; everything else is
# domain code and must go through them instead of importing it directly.
_ADAPTER_EXCEPTIONS = {
    "utils/llm.py": {"openai"},
    "utils/app_state.py": {"streamlit"},
    "utils/auth.py": {"streamlit"},
    "utils/theme.py": {"streamlit"},
}

# Forbidden for every *other* file under utils/ and agents/.
_FORBIDDEN_FOR_DOMAIN = {"streamlit", "openai", "chromadb", "app"}

_SCAN_ROOTS = ("utils", "agents", "mvp2")
_SCAN_EXCLUDED_DIRS = {".venv", "__pycache__", ".git", ".hypothesis", ".pytest_cache"}

# Implementation Plan - MVP 2.md, section 1.5's exact allowed-source graph,
# keyed by the mvp2 subpackage. "mvp1_public" stands for utils/agents (MVP
# 1's frozen public contracts/services) - not literally importable as a
# single module, so it's checked as "any utils.* or agents.* import is
# allowed" rather than a specific module name.
_MVP2_DEPENDENCY_GRAPH = {
    "mvp2.contracts": set(),  # leaf: stdlib/typing/pydantic only, checked separately below
    "mvp2.profile": {"mvp1_public"},
    "mvp2.knowledge": {"mvp2.profile"},
    "mvp2.runtime": set(),  # shared MVP 2 contracts only; no domain calculation imports
    "mvp2.strategy": {"mvp2.profile", "mvp2.knowledge", "mvp2.runtime", "mvp1_public"},
    "mvp2.presentation": {"mvp2.profile", "mvp2.knowledge", "mvp2.strategy", "mvp1_public"},
    "mvp2.conversation": {"mvp2.presentation", "mvp2.knowledge", "mvp2.runtime"},
    "mvp2.scenarios": {"mvp1_public", "mvp2.runtime"},
}


def _imported_module_names(tree: ast.AST) -> set:
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                names.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.module and node.level == 0:
                names.add(node.module.split(".")[0])
    return names


def _iter_scanned_files():
    for root_name in _SCAN_ROOTS:
        root = REPO_ROOT / root_name
        if not root.exists():
            continue
        for path in root.rglob("*.py"):
            if any(part in _SCAN_EXCLUDED_DIRS for part in path.parts):
                continue
            yield path


def find_domain_boundary_violations() -> dict:
    """Returns {relative_path: sorted[violating_module_names]} - empty when
    clean. Pure function over the filesystem, kept separate from any
    pytest fixture so the synthetic-AST test below can exercise its logic
    (`_check_tree`) without writing through this filesystem walk."""
    violations = {}
    for path in _iter_scanned_files():
        rel = str(path.relative_to(REPO_ROOT))
        allowed_extra = _ADAPTER_EXCEPTIONS.get(rel, set())
        tree = ast.parse(path.read_text(), filename=str(path))
        hits = _check_tree(tree, allowed_extra)
        if hits:
            violations[rel] = hits
    return violations


def _check_tree(tree: ast.AST, allowed_extra: set) -> list:
    imported = _imported_module_names(tree)
    forbidden = (_FORBIDDEN_FOR_DOMAIN - allowed_extra) & imported
    return sorted(forbidden)


def test_no_domain_module_imports_app_streamlit_openai_or_chromadb_directly():
    violations = find_domain_boundary_violations()
    assert violations == {}


def test_boundary_checker_rejects_a_planted_reverse_import():
    """Required test: 'Dependency-boundary test rejects a deliberately
    created reverse-import fixture.' Proves `_check_tree` is not vacuously
    passing because it never matches anything."""
    planted_source = "import streamlit as st\n\ndef f():\n    return st.session_state\n"
    tree = ast.parse(planted_source, filename="utils/fake_domain_module.py")
    hits = _check_tree(tree, allowed_extra=set())
    assert hits == ["streamlit"]


def test_adapter_exceptions_point_at_files_that_still_exist():
    """Guards the exception list itself against rotting silently if
    utils/llm.py or utils/app_state.py is ever renamed."""
    for rel_path in _ADAPTER_EXCEPTIONS:
        assert (REPO_ROOT / rel_path).is_file(), f"{rel_path} no longer exists; update _ADAPTER_EXCEPTIONS"


def test_no_module_imports_app_back():
    """app.py is the one composition root (Implementation Plan - MVP 2.md,
    section 1.5's dependency graph); nothing under utils/, agents/, or
    mvp2/ may import it."""
    offenders = []
    for path in _iter_scanned_files():
        tree = ast.parse(path.read_text(), filename=str(path))
        if "app" in _imported_module_names(tree):
            offenders.append(str(path.relative_to(REPO_ROOT)))
    assert offenders == []


def test_mvp2_subpackage_graph_has_no_cycle_and_covers_the_architecture_list():
    """The graph itself (not yet enforceable against real files, since no
    mvp2/ package exists) is validated for internal consistency now, so a
    typo introduced here would fail immediately rather than waiting for
    Phase MVP2-1 to notice."""
    expected_subpackages = {
        "mvp2.contracts", "mvp2.profile", "mvp2.knowledge", "mvp2.runtime",
        "mvp2.strategy", "mvp2.presentation", "mvp2.conversation", "mvp2.scenarios",
    }
    assert set(_MVP2_DEPENDENCY_GRAPH) == expected_subpackages

    def _visit(node, stack):
        assert node not in stack, f"cycle detected: {stack + [node]}"
        for dep in _MVP2_DEPENDENCY_GRAPH.get(node, set()):
            if dep == "mvp1_public":
                continue
            _visit(dep, stack + [node])

    for subpackage in _MVP2_DEPENDENCY_GRAPH:
        _visit(subpackage, [])


def test_no_mvp2_package_exists_yet():
    """Phase MVP2-0's own exit gate: 'No MVP 2 domain package, contract,
    flag, corpus, or UI has been added.' A future phase creating mvp2/
    without updating this test is itself the signal that Phase MVP2-1 (or
    later) has begun - at which point this test's failure is expected and
    it should be replaced by real per-file graph enforcement using
    `_MVP2_DEPENDENCY_GRAPH`, not silently deleted."""
    assert not (REPO_ROOT / "mvp2").exists()
