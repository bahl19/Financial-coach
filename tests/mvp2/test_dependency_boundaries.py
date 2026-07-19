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
   applied per-file to whichever `mvp2/*` subpackages exist at the time this
   runs. Until Phase MVP2-1 creates `mvp2/profile/` there are no real files
   for it to reject, so the checker is exercised regardless via synthetic AST
   fixtures (`test_graph_checker_rejects_planted_*` below) - its correctness
   never depends on a later phase remembering to test it.

Phase MVP2-0 originally carried a `test_no_mvp2_package_exists_yet` tripwire
asserting `mvp2/` was absent, to hold its own exit gate ("No MVP 2 domain
package, contract, flag, corpus, or UI has been added"). That gate is
verified and tagged (`mvp2-phase-0-done`), and the tripwire's own docstring
specified that the next phase should *replace* it with real per-file graph
enforcement rather than delete it. That replacement is what section 2 below
now is (see `Implementation Plan - MVP 2 Priority.md`, Task 0). What
survives of the old guard is `test_no_unknown_mvp2_subpackage_appears`,
which still fails on any `mvp2/` directory the architecture never approved.
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

# Shared leaf MODULES (not subpackages): `mvp2/contracts.py`, `mvp2/errors.py`,
# `mvp2/hashing.py` from Implementation Plan - MVP 2.md's package layout.
# Every mvp2 subpackage may import these; they may import nothing
# project-specific themselves (stdlib/typing/Pydantic only).
#
# These are deliberately NOT rows in the graph below. Phase MVP2-0's first
# encoding listed `mvp2.contracts` as a graph key with no allowed sources,
# which - enforced literally - made `mvp2/profile/*` importing
# `mvp2.contracts` a boundary violation, even though the plan's own package
# layout requires exactly that import. Modelling them as universally-allowed
# leaves fixes that contradiction without loosening any real arrow
# (Implementation Plan - MVP 2 Priority.md, Task 0).
_MVP2_SHARED_LEAVES = {"mvp2.contracts", "mvp2.errors", "mvp2.hashing"}

# Implementation Plan - MVP 2.md, section 1.5's exact allowed-source graph,
# keyed by the mvp2 subpackage. "mvp1_public" stands for utils/agents (MVP
# 1's frozen public contracts/services) - not literally importable as a
# single module, so it's checked as "any utils.* or agents.* import is
# allowed" rather than a specific module name. Every subpackage additionally
# gets `_MVP2_SHARED_LEAVES` for free.
_MVP2_DEPENDENCY_GRAPH = {
    "mvp2.profile": {"mvp1_public"},
    "mvp2.knowledge": {"mvp2.profile"},
    "mvp2.runtime": set(),  # shared MVP 2 contracts only; no domain calculation imports
    "mvp2.strategy": {"mvp2.profile", "mvp2.knowledge", "mvp2.runtime", "mvp1_public"},
    "mvp2.presentation": {"mvp2.profile", "mvp2.knowledge", "mvp2.strategy", "mvp1_public"},
    "mvp2.conversation": {"mvp2.presentation", "mvp2.knowledge", "mvp2.runtime"},
    "mvp2.scenarios": {"mvp1_public", "mvp2.runtime"},
}

_MVP1_PUBLIC_ROOTS = {"utils", "agents"}


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


# --------------------------------------------------------------------------
# mvp2 subpackage graph enforcement
# --------------------------------------------------------------------------
#
# Unlike `_imported_module_names` above (which only needs the top-level root,
# e.g. "streamlit"), graph enforcement needs the *second* component too -
# "mvp2.profile" and "mvp2.knowledge" are different nodes. Relative imports
# are resolved rather than skipped: `from ..contracts import X` inside
# `mvp2/profile/scoring.py` is a real `mvp2.contracts` edge, and ignoring it
# would leave a trivial bypass hole in the very check this file exists for.


def _owner_of(rel_parts: tuple) -> str:
    """The graph node a file belongs to, from its path parts relative to the
    repo root, e.g. ("mvp2", "profile", "scoring.py") -> "mvp2.profile" and
    ("mvp2", "contracts.py") -> "mvp2.contracts"."""
    if len(rel_parts) >= 3:
        return f"{rel_parts[0]}.{rel_parts[1]}"
    return f"{rel_parts[0]}.{Path(rel_parts[-1]).stem}"


def _package_parts_of(rel_parts: tuple) -> list:
    """The dotted package a file lives in, for resolving relative imports:
    ("mvp2", "profile", "scoring.py") -> ["mvp2", "profile"]."""
    return list(rel_parts[:-1])


def _mvp2_edges(tree: ast.AST, package_parts: list) -> set:
    """Every `mvp2.<x>` node this file imports from, absolute or relative."""
    edges = set()

    def _record(dotted_parts):
        if len(dotted_parts) >= 2 and dotted_parts[0] == "mvp2":
            edges.add(f"mvp2.{dotted_parts[1]}")

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                _record(alias.name.split("."))
        elif isinstance(node, ast.ImportFrom):
            if node.level == 0:
                if node.module:
                    _record(node.module.split("."))
                continue
            # Relative: level 1 is the file's own package, each extra level
            # walks one further up.
            base = package_parts[: len(package_parts) - (node.level - 1)]
            if node.module:
                _record(base + node.module.split("."))
            else:
                # `from . import contracts` / `from .. import errors`
                for alias in node.names:
                    _record(base + [alias.name])
    return edges


def _mvp1_public_imported(tree: ast.AST) -> bool:
    return bool(_imported_module_names(tree) & _MVP1_PUBLIC_ROOTS)


def check_mvp2_file(tree: ast.AST, rel_parts: tuple) -> list:
    """Returns a sorted list of violation strings for one mvp2 file - empty
    when clean. Pure over the AST + path so planted fixtures can exercise it
    with no filesystem writes."""
    owner = _owner_of(rel_parts)
    violations = []

    if owner in _MVP2_SHARED_LEAVES:
        # Leaves may import stdlib/typing/Pydantic only.
        for edge in sorted(_mvp2_edges(tree, _package_parts_of(rel_parts)) - {owner}):
            violations.append(f"shared leaf {owner} imports {edge}")
        if _mvp1_public_imported(tree):
            violations.append(f"shared leaf {owner} imports MVP 1 code (utils/agents)")
        return sorted(violations)

    allowed = _MVP2_DEPENDENCY_GRAPH.get(owner)
    if allowed is None:
        return [f"{owner} is not a known mvp2 subpackage in the architecture graph"]

    for edge in sorted(_mvp2_edges(tree, _package_parts_of(rel_parts))):
        if edge == owner or edge in _MVP2_SHARED_LEAVES or edge in allowed:
            continue
        violations.append(f"{owner} imports {edge}, which is not in its allowed set")

    if _mvp1_public_imported(tree) and "mvp1_public" not in allowed:
        violations.append(f"{owner} imports MVP 1 code (utils/agents) but is not allowed mvp1_public")

    return sorted(violations)


def _iter_mvp2_files():
    root = REPO_ROOT / "mvp2"
    if not root.exists():
        return
    for path in root.rglob("*.py"):
        if any(part in _SCAN_EXCLUDED_DIRS for part in path.parts):
            continue
        rel_parts = path.relative_to(REPO_ROOT).parts
        if len(rel_parts) == 2 and rel_parts[1] == "__init__.py":
            continue  # the mvp2/__init__.py package marker owns no node
        yield path, rel_parts


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
    """The graph itself is validated for internal consistency, so a typo
    introduced here fails immediately rather than silently widening what a
    later phase is allowed to import."""
    expected_nodes = {
        "mvp2.contracts", "mvp2.errors", "mvp2.hashing",
        "mvp2.profile", "mvp2.knowledge", "mvp2.runtime",
        "mvp2.strategy", "mvp2.presentation", "mvp2.conversation", "mvp2.scenarios",
    }
    assert set(_MVP2_DEPENDENCY_GRAPH) | _MVP2_SHARED_LEAVES == expected_nodes
    assert not (set(_MVP2_DEPENDENCY_GRAPH) & _MVP2_SHARED_LEAVES), "a node cannot be both a subpackage and a leaf"

    def _visit(node, stack):
        assert node not in stack, f"cycle detected: {stack + [node]}"
        for dep in _MVP2_DEPENDENCY_GRAPH.get(node, set()):
            if dep == "mvp1_public":
                continue
            _visit(dep, stack + [node])

    for subpackage in _MVP2_DEPENDENCY_GRAPH:
        _visit(subpackage, [])


def test_mvp2_files_respect_the_dependency_graph():
    """Real per-file enforcement. Inert while `mvp2/` is absent (Phase
    MVP2-1 creates the first files); the planted-violation tests below are
    what prove the checker itself works in the meantime."""
    violations = {}
    for path, rel_parts in _iter_mvp2_files():
        tree = ast.parse(path.read_text(), filename=str(path))
        hits = check_mvp2_file(tree, rel_parts)
        if hits:
            violations[str(path.relative_to(REPO_ROOT))] = hits
    assert violations == {}


def test_no_unknown_mvp2_subpackage_appears():
    """What survives of Phase MVP2-0's `test_no_mvp2_package_exists_yet`:
    `mvp2/` may now exist, but every directory in it must be a node the
    architecture actually approved - so an unplanned `mvp2/whatever/` is
    still caught, rather than silently inheriting no rules at all."""
    root = REPO_ROOT / "mvp2"
    if not root.exists():
        return
    unknown = [
        d.name for d in root.iterdir()
        if d.is_dir() and d.name not in _SCAN_EXCLUDED_DIRS and f"mvp2.{d.name}" not in _MVP2_DEPENDENCY_GRAPH
    ]
    assert unknown == [], f"unapproved mvp2 subpackage(s): {unknown}"


def test_graph_checker_allows_the_planned_profile_layout():
    """The exact imports Phase MVP2-1's package layout requires must pass -
    this is the case Phase MVP2-0's first encoding wrongly rejected, so it
    is pinned as a regression test, not just fixed."""
    source = (
        "from mvp2.contracts import FinancialResilienceScore\n"
        "from mvp2.errors import Mvp2DomainError\n"
        "from ..hashing import canonical_sha256\n"
        "from utils.contracts import FinancialSnapshot\n"
    )
    tree = ast.parse(source, filename="mvp2/profile/scoring.py")
    assert check_mvp2_file(tree, ("mvp2", "profile", "scoring.py")) == []


def test_graph_checker_rejects_a_planted_later_phase_import():
    """`mvp2.profile` may not reach forward to a later phase."""
    tree = ast.parse("from mvp2.strategy import pick_policy\n", filename="mvp2/profile/actions.py")
    hits = check_mvp2_file(tree, ("mvp2", "profile", "actions.py"))
    assert hits == ["mvp2.profile imports mvp2.strategy, which is not in its allowed set"]


def test_graph_checker_rejects_a_planted_relative_later_phase_import():
    """The same violation written as a relative import must not slip past -
    otherwise the check is trivially bypassable."""
    tree = ast.parse("from ..strategy import pick_policy\n", filename="mvp2/profile/actions.py")
    hits = check_mvp2_file(tree, ("mvp2", "profile", "actions.py"))
    assert hits == ["mvp2.profile imports mvp2.strategy, which is not in its allowed set"]


def test_graph_checker_rejects_mvp1_imports_from_a_subpackage_denied_mvp1_public():
    """`mvp2.runtime` is "no domain calculation imports" per section 1.5."""
    tree = ast.parse("from utils import finance_calc\n", filename="mvp2/runtime/budgets.py")
    hits = check_mvp2_file(tree, ("mvp2", "runtime", "budgets.py"))
    assert hits == ["mvp2.runtime imports MVP 1 code (utils/agents) but is not allowed mvp1_public"]


def test_graph_checker_rejects_a_shared_leaf_importing_project_code():
    """`mvp2/contracts.py` is a leaf: stdlib/typing/Pydantic only."""
    tree = ast.parse("from utils.contracts import Roadmap\n", filename="mvp2/contracts.py")
    hits = check_mvp2_file(tree, ("mvp2", "contracts.py"))
    assert hits == ["shared leaf mvp2.contracts imports MVP 1 code (utils/agents)"]


def test_graph_checker_rejects_an_unknown_subpackage():
    tree = ast.parse("x = 1\n", filename="mvp2/whatever/thing.py")
    hits = check_mvp2_file(tree, ("mvp2", "whatever", "thing.py"))
    assert hits == ["mvp2.whatever is not a known mvp2 subpackage in the architecture graph"]
