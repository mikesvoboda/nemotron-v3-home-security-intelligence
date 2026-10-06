"""OD-31's narrow reachability guard: the ONE live notify function must stay live.

ISS-001's acceptance asks for "an AST reachability guard [that] fails if
``should_notify``, ``evaluate_event``, ``create_alerts_for_event`` or
``deliver_alert`` has zero non-test callers". Read literally, that guard cannot
be satisfied on the branch the owner ruled the same day: the OD-1 follow-up of
2026-10-05 ("the smallest slice") PARKS the rules engine and the delivery
channels - not deleted, not wired - so three of the four names have, by ruling,
no production caller. That collision between the acceptance's words and the
ruling was raised as **OD-31** and ruled 2026-10-05 as "(a) check the one live
function" (docs/vss-integration/17-action-plan.md, Intake log, and the OD
table's OD-31 row): the guard narrows to ``should_notify``, "(or recorded
delivery)" is the persisted ``EventNotifyDecision`` row, closure is the live-DB
``notify=true``-reaches-a-surface test, and the parked functions stay
UNGUARDED. The acceptance text itself was never amended - the owner construed
the existing words - which is why this file cites the ruling instead of quietly
implementing a different one.

What the narrowed guard asserts, and nothing more
-------------------------------------------------
    NotificationFilterService.should_notify
        <- notification_filter.decide_notification      (the live seam)
    decide_notification
        <- VlmAnalyzer._notify_decision                 (the post-commit producer)

The CHAIN matters more than a bare non-zero count. "should_notify has one
caller" is satisfied by any fresh dead wrapper; requiring the caller to be
``decide_notification``, and that seam to have a non-test caller of its own,
pins the SHAPE of the wiring - the verdict-to-decision function is reached from
the analyzer, and that edge is what ISS-001 was about.

Why AST and not grep (the repo's standing lesson, voiced in
``test_no_legacy_pipeline_branches.py`` and
``test_r8_s3_florence_provider_retirement.py``: prose is allowed to name the
dead). ``should_notify`` is spelled in shipped PROSE - ``decide_notification``'s
own docstring, ``WebSocketEventData``'s field comment, the new model's
docstring - so a textual "who mentions it" scan over ``backend/`` hits those
first and would go green on a fully unwired tree. Only ``Load``-context
``Attribute``/``Name`` nodes count as reads: a docstring is not a node, an
import is a wiring rather than a call, and a definition is not a use of its own
name.

The parked trio - deliberately NOT asserted about
-------------------------------------------------
``AlertEngine.evaluate_event`` and ``AlertEngine.create_alerts_for_event``
(``backend/services/alert_engine.py``) and ``NotificationService.deliver_alert``
(``backend/services/notification.py``) are the acceptance's other three names,
and OD-31 leaves them out of the guard. This file asserts NOTHING about their
callers, in either direction:

  * "zero non-test callers" would re-impose the pre-OD-31 acceptance and would
    FAIL the day a later slice wires delivery - the opposite of what the ruling
    wants;
  * "non-zero callers" is the reading the owner rejected outright.

``PARKED_BY_OD31`` below records them as a ruling rather than as scan input:
its only job is pinning that the guarded set does not include them, so that a
future reader of ISS-001's acceptance sentence finds, at the guard itself, why
the guard is narrower than that sentence.

Speed: a substring pre-filter (a module that never spells either name cannot
hold a read of it) ahead of ``ast.parse``, so ~2 of the 510 shipped modules are
actually parsed.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from functools import cache
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

# backend/ is the shipped tree, which is what "non-test caller" ranges over.
# The repo-root test trees sit outside it; backend/tests sits inside it and is
# excluded by _is_excluded. (Four levels up from backend/tests/unit/services/,
# which is this file's home; the sibling idiom is
# backend/tests/unit/test_no_legacy_pipeline_branches.py.)
BACKEND = Path(__file__).resolve().parents[4] / "backend"

# The level/decision seam ISS-001's acceptance names, and the module-level
# function that resolves the owner's preferences and calls it.
LIVE_FUNCTION = "should_notify"
LIVE_SEAM = "decide_notification"

# The guarded set, as data, so the narrowness pin asserts against it instead of
# against a reader's memory of the ruling.
_GUARDED: frozenset[str] = frozenset({LIVE_FUNCTION, LIVE_SEAM})

# The acceptance's other three names, PARKED by OD-31 (module docstring). Never
# passed to the scanner; the only thing they pin is that _GUARDED excludes them.
PARKED_BY_OD31: frozenset[str] = frozenset(
    {"evaluate_event", "create_alerts_for_event", "deliver_alert"}
)

# The two production modules whose wiring is under test, as seen from backend/.
FILTER_MODULE = "services/notification_filter.py"
ANALYZER_MODULE = "services/vlm_analyzer.py"


@dataclass(frozen=True, slots=True)
class Reference:
    """One non-test AST read of a guarded symbol."""

    symbol: str
    module: str  # path relative to backend/, POSIX separators
    caller: str  # dotted scope the read sits in; "<module>" at top level
    kind: str  # "attribute" (obj.sym) or "name" (bare sym)
    lineno: int

    def __str__(self) -> str:
        return f"{self.module}:{self.lineno} in {self.caller} [{self.kind}]"


def _is_excluded(path: Path) -> bool:
    """Bytecode, or anything below a tests/test directory under backend/.

    ``backend/tests`` is the only test tree under ``backend/`` today; the check
    is positional rather than a single literal so a future ``backend/api/tests/``
    cannot smuggle a helper in as "production". The final component is not
    tested, so a test FILE named e.g. ``tests.py`` at backend root is still
    scanned as the production file it is - only test DIRECTORIES are excluded.
    """
    relative = path.relative_to(BACKEND).parts
    return "__pycache__" in relative or any(part in {"tests", "test"} for part in relative[:-1])


class _ReferenceVisitor(ast.NodeVisitor):
    """Collects Load-context reads of the guarded symbols, tagged with scope.

    Deliberately NOT collected:

      * the definition - a ``FunctionDef.name`` is not a ``Name`` node;
      * ``from ... import decide_notification`` - an ``ast.alias``, not a
        ``Name``. An import is a wiring, not a call, and must not be able to
        satisfy a reachability guard on its own;
      * docstrings and comments - not nodes at all;
      * a write target - ``Store``/``Del`` context is not a read.
    """

    def __init__(self, module: str) -> None:
        self._module = module
        self._scope: list[str] = []
        self.found: list[Reference] = []

    def _visit_scoped(self, node) -> None:
        self._scope.append(node.name)
        self.generic_visit(node)
        self._scope.pop()

    visit_ClassDef = _visit_scoped
    visit_FunctionDef = _visit_scoped
    visit_AsyncFunctionDef = _visit_scoped

    def _record(self, symbol: str, node: ast.expr, kind: str) -> None:
        self.found.append(
            Reference(
                symbol=symbol,
                module=self._module,
                caller=".".join(self._scope) or "<module>",
                kind=kind,
                lineno=node.lineno,
            )
        )

    def visit_Attribute(self, node: ast.Attribute) -> None:
        if node.attr in _GUARDED and isinstance(node.ctx, ast.Load):
            self._record(node.attr, node, "attribute")
        self.generic_visit(node)

    def visit_Name(self, node: ast.Name) -> None:
        if node.id in _GUARDED and isinstance(node.ctx, ast.Load):
            self._record(node.id, node, "name")
        self.generic_visit(node)


@cache
def _scan() -> tuple[list[Reference], int]:
    """Every non-test read of a guarded symbol, plus how many modules were parsed.

    Cached because four tests ask the same question of it. The parse count comes
    back with the references so callers can assert NON-VACUITY: a broken scan
    root or a rename that stopped every shipped module from spelling these names
    would leave the reference list empty, and "a list is non-empty" is the one
    claim an empty list makes vacuous. That is the trap named in
    ``test_r8_s3_florence_provider_retirement.py`` ("a test iterating a deleted
    thing passes happily on an empty list"), and here it has extra bite: an
    empty caller list is exactly the state ISS-001 shipped in.
    """
    found: list[Reference] = []
    parsed = 0
    for path in sorted(BACKEND.rglob("*.py")):
        if _is_excluded(path):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except OSError, UnicodeDecodeError:  # pragma: no cover - defensive
            continue
        if not any(symbol in text for symbol in _GUARDED):
            continue
        parsed += 1
        visitor = _ReferenceVisitor(path.relative_to(BACKEND).as_posix())
        visitor.visit(ast.parse(text, filename=str(path)))
        found.extend(visitor.found)
    return found, parsed


def _reads(symbol: str) -> list[Reference]:
    """Non-test reads of one guarded symbol."""
    references, _parsed = _scan()
    return [reference for reference in references if reference.symbol == symbol]


class TestScanIsSound:
    """The guard's instrument, pinned before its verdicts.

    Every reachability claim below is an assertion over ``_scan``'s output, so
    these run first: an unsound scan does not fail loudly, it reports a healthy
    tree.
    """

    def test_the_scan_actually_parsed_the_defining_modules(self):
        references, parsed = _scan()
        assert parsed >= 2, (
            f"only {parsed} shipped modules were parsed - the pre-filter or the "
            "scan root is broken and every caller assertion below is vacuous"
        )
        spelling = {reference.module for reference in references}
        assert FILTER_MODULE in spelling, (
            f"{FILTER_MODULE} defines both guarded symbols and contributed no "
            f"reference at all; scan saw {sorted(spelling)}"
        )

    def test_only_guarded_symbols_are_matched(self):
        """The matcher set, checked against the output rather than the source.

        If someone widens the scanner's matcher without widening ``_GUARDED``
        (or vice versa) this fails, which is the mechanical form of "the guard
        is exactly as wide as OD-31 ruled"."""
        references, _parsed = _scan()
        matched = {reference.symbol for reference in references}
        assert matched <= _GUARDED, (
            f"the scan matched unguarded names: {sorted(matched - _GUARDED)}"
        )

    def test_the_test_tree_is_excluded_from_the_scan(self):
        """The exclusion is load-bearing, so its PRECONDITION is pinned too.

        ``should_notify`` is spelled all over ``backend/tests`` - which is
        precisely the state ISS-001 shipped in (implemented, unit-tested, zero
        production callers). A scan that counted test modules would have called
        that function reachable and gone green on the bug.
        """
        assert BACKEND.is_dir(), f"scan root missing: {BACKEND}"
        spelled_by_tests = [
            path
            for path in (BACKEND / "tests").rglob("*.py")
            if LIVE_FUNCTION in path.read_text(encoding="utf-8")
        ]
        assert spelled_by_tests, (
            "no test module spells should_notify any more - the exclusion is then "
            "unproven, and this file's premise (tested but unwired) wants a re-read"
        )
        references, _parsed = _scan()
        leaked = sorted({r.module for r in references if r.module.startswith("tests/")})
        assert not leaked, f"test modules leaked into the reference set: {leaked}"

    def test_the_scan_is_fast_enough_to_belong_in_the_unit_tier(self):
        """All 510 shipped modules are walked on every run, so the substring
        pre-filter is what pays for that. The ceiling is deliberately generous:
        the claim is "parses a handful, not hundreds", not a benchmark - the repo
        has a ``benchmark`` marker for real measurement, and pytest-randomly
        (repo addopts) makes a tight timing pin flaky.
        """
        import time

        _scan.cache_clear()
        started = time.perf_counter()
        _references, parsed = _scan()
        elapsed = time.perf_counter() - started
        assert elapsed < 2.0, f"reachability scan took {elapsed:.2f}s - pre-filter is not working"
        assert parsed < 25, (
            f"{parsed} modules parsed: the pre-filter is letting too much through "
            "for this file to stay in the fast lane"
        )


class TestShouldNotifyReachability:
    """OD-31's narrowed guard, arm 1: the live function has a live caller."""

    def test_should_notify_has_at_least_one_non_test_caller(self):
        """The one clause of the acceptance OD-31 kept.

        ISS-001's entire existence is this predicate having been false:
        ``should_notify`` was implemented, unit-tested and unreachable, so every
        spec section 6 safety net - rejected never notifies, the NULL-score
        detector rule, an outage must not leave the owner blind - shipped as
        dead code. This is the pin that makes that state unshippable again.
        """
        callers = _reads(LIVE_FUNCTION)
        assert callers, (
            f"{LIVE_FUNCTION} has no non-test read anywhere in backend/ - the "
            "notification decision is unreachable again (ISS-001 reopened)"
        )

    def test_the_caller_is_decide_notification(self):
        """Not merely "a caller": the seam the slice wired, named by module+caller.

        A non-zero count is a weak claim - a fresh dead wrapper satisfies it
        while nothing reaches the wrapper. The acceptance's live function is
        reached through the module's own settings-resolving seam, so that seam
        is what this demands by name rather than by count. The read is an
        ``Attribute`` (``NotificationFilterService().should_notify``), which is
        why the visitor counts attribute reads as calls.
        """
        seam_callers = [
            reference
            for reference in _reads(LIVE_FUNCTION)
            if reference.module == FILTER_MODULE and reference.caller == LIVE_SEAM
        ]
        assert seam_callers, (
            f"{LIVE_FUNCTION}'s non-test callers are "
            f"{[str(r) for r in _reads(LIVE_FUNCTION)]}; none is "
            f"{FILTER_MODULE}::{LIVE_SEAM} - the live function must be reached "
            "from the seam that resolves the owner's preferences"
        )

    def test_should_notify_is_still_a_method_of_the_filter_service(self):
        """Definition-side non-vacuity for the two pins above.

        ``test_p04_verification_field.py`` AST-pins the filter seam's existence,
        which is why ISS-018 had to delegate rather than delete. This pins the
        same fact from the reachability side: the guarded name is still the
        method on ``NotificationFilterService``. A module-level function of the
        same name would keep the caller assertions green while the thing under
        guard had moved somewhere else entirely.
        """
        path = BACKEND / FILTER_MODULE
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        service = next(
            (
                node
                for node in tree.body
                if isinstance(node, ast.ClassDef) and node.name == "NotificationFilterService"
            ),
            None,
        )
        assert service is not None, "NotificationFilterService is gone from the filter module"
        methods = {
            node.name
            for node in service.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        }
        assert LIVE_FUNCTION in methods, (
            f"{LIVE_FUNCTION} is no longer a method of NotificationFilterService "
            f"(methods: {sorted(methods)}) - move this guard in the same change, "
            "do not delete it"
        )


class TestDecideNotificationReachability:
    """OD-31's narrowed guard, arm 2: the seam is itself reached from production.

    ``decide_notification`` only makes ``should_notify`` reachable if something
    calls ``decide_notification``. ISS-001's title - "wire the notification
    decision into the VLM event path" - names exactly this edge:
    ``VlmAnalyzer._notify_decision`` runs the seam after the event commits, in
    its own short session, and persists the answer.
    """

    def test_decide_notification_has_a_non_test_caller(self):
        callers = _reads(LIVE_SEAM)
        assert callers, (
            f"{LIVE_SEAM} has no non-test read in backend/ - a seam nobody calls "
            f"does not make {LIVE_FUNCTION} reachable"
        )

    def test_the_caller_is_the_analyzers_notify_decision(self):
        """The producer OD-31's closure names: ``VlmAnalyzer._notify_decision``.

        Both call sites inside that method count - the session path and the
        no-session fallback for a failed settings read - because the claim is
        about the CALLER, not the line count. A moved or renamed producer is
        what fails here.
        """
        producers = [
            reference
            for reference in _reads(LIVE_SEAM)
            if reference.module == ANALYZER_MODULE
            and reference.caller == "VlmAnalyzer._notify_decision"
        ]
        assert producers, (
            f"{LIVE_SEAM}'s non-test callers are {[str(r) for r in _reads(LIVE_SEAM)]}; "
            "none is the analyzer's post-commit notify stage"
        )

    def test_the_producer_persists_the_answer_it_computed(self):
        """The OD-31 equivalence, structurally: the function that calls the seam
        is the function that writes the row.

        OD-31 makes the persisted ``EventNotifyDecision`` the referent of "(or
        recorded delivery)", so the guard is incomplete while the computed answer
        can vanish: ``_notify_decision`` must reach BOTH the seam and
        ``_persist_notify_decision``. The end-to-end form of that claim - a real
        ``notify=true`` arriving on a real REST surface - is
        ``backend/tests/integration/test_notify_decision_wiring.py``; this pin
        only keeps the compute and the record inside one function.
        """
        path = BACKEND / ANALYZER_MODULE
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        methods = {
            node.name: node
            for cls in tree.body
            if isinstance(cls, ast.ClassDef)
            for node in cls.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        }
        producer = methods.get("_notify_decision")
        assert producer is not None, "VlmAnalyzer._notify_decision is gone"
        reads = {
            node.attr
            for node in ast.walk(producer)
            if isinstance(node, ast.Attribute) and isinstance(node.ctx, ast.Load)
        } | {
            node.id
            for node in ast.walk(producer)
            if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load)
        }
        assert LIVE_SEAM in reads, (
            f"_notify_decision no longer reaches {LIVE_SEAM}: {sorted(reads)}"
        )
        assert "_persist_notify_decision" in reads, (
            "_notify_decision no longer persists its answer - with the row gone "
            "there is no 'recorded delivery' left for OD-31's closure"
        )


class TestGuardIsNarrow:
    """The guard's own boundary: it does not police the parked trio.

    Nothing here counts callers of ``evaluate_event``,
    ``create_alerts_for_event`` or ``deliver_alert`` - in EITHER direction - and
    this class is where that choice is stated as structure rather than left as a
    silence a future agent fills in by "completing" the acceptance.
    """

    def test_the_guarded_set_is_exactly_the_live_pair(self):
        """OD-31's narrowing, asserted as data.

        A change that widened ``_GUARDED`` to the acceptance's full four-name
        list would make this fail first, pointing at the ruling. Widening is
        legitimate only as a PAIRED change with the wiring that gives those
        functions callers - i.e. the next slice, never a test edit.
        """
        assert frozenset({LIVE_FUNCTION, LIVE_SEAM}) == _GUARDED, sorted(_GUARDED)
        assert _GUARDED.isdisjoint(PARKED_BY_OD31), (
            f"{sorted(_GUARDED & PARKED_BY_OD31)} is parked by OD-31 and must not "
            "be guarded: guard it when it has a caller, not before"
        )

    def test_the_parked_trio_is_documented_not_scan_input(self):
        """The park is recorded, and recording it costs the scan nothing.

        No assertion about the trio's CALLERS exists in this file, which is the
        point: the OD-1 ruling parks them "not deleted, not wired", so a future
        wiring must not fail here, and the pre-OD-31 zero-caller reading must not
        come back either. This pin keeps the record honest (the names are still
        the acceptance's) without asserting anything about reachability.
        """
        assert (
            frozenset({"evaluate_event", "create_alerts_for_event", "deliver_alert"})
            == PARKED_BY_OD31
        ), "the parked set drifted from ISS-001's acceptance names"
        module_text = Path(__file__).read_text(encoding="utf-8")
        for name in PARKED_BY_OD31:
            assert name in module_text, f"{name} must stay named here, with its ruling"
        # ...and none of them is fed to the scanner - the scan's matcher set is
        # _GUARDED alone, already pinned by test_only_guarded_symbols_are_matched.
        assert not _GUARDED & PARKED_BY_OD31
