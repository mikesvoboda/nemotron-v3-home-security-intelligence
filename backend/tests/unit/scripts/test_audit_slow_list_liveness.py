"""Every exemption pattern in the Test Performance Audit must match a test that exists.

**The defect (UR-48 lane work, ops cell B).** ``SLOW_TEST_PATTERNS`` and
``BENCHMARK_PATTERNS`` in ``scripts/audit-test-durations.py`` are matched with
``re.search(pattern, f"{classname}::{name}", re.IGNORECASE)`` against junit's
node-id morphology. Nothing in the harness asks whether a pattern still matches
*anything*, so a list of exemptions rots in both directions: a row left behind
after its test was deleted silently certifies "we measured this one" for a test
no longer in the tree, and an over-broad row can keep matching a renamed test
forever, exempting a test nobody ever measured. Two rows were dead on ``main``
when this suite was written -- ``test_pipeline_e2e.*test_pipeline_llm_failure_fallback``
(the file survived, the ``def`` did not) and
``test_enrichment_pipeline_household_matching.*test_vehicle_household_matching_via_license_plate``
(both gone, in ``602379e29`` with ``enrichment_pipeline.py``; the census comment in
``scripts/test_suppression_census.py`` already recorded that deletion).

**The owner rule, not "nearest class".** junit's ``classname`` is the dotted
module plus the *collected* class, and pytest collects a method only under a
column-0 ``class Test*`` (``pyproject`` ``python_classes``). The first version
of this harvest owned every test to the nearest preceding ``class``, which
fabricated node ids pytest would never emit. Measured against a real
``--collect-only`` of 36,967 nodes: it mis-owned **3,894** module-level
``def test``s to a class that merely appears earlier in the file (fabricating a
``module.Class::name`` the audit never runs), and having given each a phantom
owner it then reported the true module-only twin missing -- **3,826** nodes
pytest emits that the harvest lacked, **3,750** of which are exactly those
twins. One bug, two faces: a fabricated id is the dangerous one, because an
exemption row matching it reads "live" forever for a test the audit never runs.
(Only the fabrication *total* shifts by a couple of units with how one strips
pytest's ``[param]`` suffix; 3,894 / 3,826 / 3,750 are tree properties, not
parser artifacts, so they are the numbers quoted.) The rule below mirrors the
collection contract instead -- column-0 def -> module-level, indented def under
``class Test*`` -> that class, anything else -> not in the universe.

**Why the universe is harvested with ``git grep`` and not with ``ast``.** The
audit gates the unit tier at ``UNIT_TEST_THRESHOLD`` = **4.0 s** in CI
(``ci.yml`` and ``scripts/test_audit_gate.sh``; the 1.0 s in the script's
default is not what runs -- WP0.5 raised the gate to 4.0 s), and the rot-pin
must not itself be a breach. Re-measured on this tree (1,232 ``test_*.py``
files): ``ast.parse`` over all of them is ~4.5 s -- that WOULD breach the
enforced 4.0 s line and is the whole reason not to use it -- while a full-file
regex scan is ~0.28 s and the two ``git grep`` passes here ~0.19 s warm. The
worst single test in this file (the one that triggers the module-level harvest)
measures ~0.98 s, about a quarter of the enforced line. The earlier draft of
this file claimed "44 ms", a "2.4 s" regex scan, and a 1.0 s tier -- all stale;
these were re-measured at this head, the same re-measure that made the owner-
logic fix safe to land (0 shipped rows change verdict either way).

**Positive witness, not absence-of-behavior.** ``test_the_dead_check_fires_on_a_bogus_pattern``
feeds the same code path a pattern that matches nothing and asserts it is
reported dead. Without it, a bug in the harvest (empty universe, wrong path
filter) would make the liveness loop pass vacuously -- the exact failure mode
that let the two dead rows hide.
"""

from __future__ import annotations

import importlib.util
import re
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
SCRIPT = REPO_ROOT / "scripts" / "audit-test-durations.py"

# Loaded the way the sibling duration-budget suite loads its subject: by path, so
# the SHIPPED matcher is what gets exercised, not a reimplementation of it.
_spec = importlib.util.spec_from_file_location("_tpa_under_test", SCRIPT)
assert _spec is not None and _spec.loader is not None
_audit = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_audit)

# `\s*`, NOT `.+?`: a lazy "one-or-more" here silently drops every test defined
# at column 0 (module-level functions), which reads as a DEAD pattern rather
# than a broken harvest. Measured: that version reported
# `test_compose_render_lists_ai_vlm.*` dead, and it is live.
# The whitespace after the line-number colon is CAPTURED (group 2) because the
# owner rule below needs the def's indentation: a `def test` at column 0 is a
# module-level function and has no owner no matter what class precedes it.
_DEF_RE = re.compile(r"^(\d+):(\s*)(?:async\s+)?def\s+(test\w*)")
# Column-0 scope openers only. pytest's collection contract (pyproject
# `python_classes = ["Test*"]`) admits a method only under a column-0 `class`
# whose name starts with `Test`; a `def` nested in a column-0 `def` (a test
# factory) and a method of a non-`Test*` class are never collected, so they
# must not be attributed to the nearest preceding class -- the old rule's bug.
_SCOPE_RE = re.compile(r"^(\d+):(class|def)\s+(\w+)")


def _git_grep(pattern: str) -> dict[str, list[str]]:
    """One pass over the tracked tree; {path: ["lineno:content", ...]}."""
    out = subprocess.run(  # noqa: S603  # real git grep, fixed argv, tests our own script
        [  # noqa: S607  # partial path OK for test script
            "git",
            "grep",
            "-I",
            "-n",
            "-E",
            pattern,
            "--",
            "*.py",
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    by_file: dict[str, list[str]] = {}
    for line in out.stdout.splitlines():
        path, _, rest = line.partition(":")
        by_file.setdefault(path, []).append(rest)
    return by_file


def _junit_universe() -> set[tuple[str, str]]:
    """Every (classname, name) pair pytest-junit would emit, from the tracked tree.

    classname is the dotted module path, plus the enclosing class when the test
    is a *collected* method -- the shape ``is_known_slow_test`` receives.

    The owner rule mirrors pytest's collection contract rather than "nearest
    preceding class". Measured against the real 36,967-node collect, "nearest
    class" mis-owned 3,894 module-level ``def test``s to a class that merely
    precedes them (fabricating ids the audit never runs) and thereby reported
    their true module-level twins missing -- 3,826 missing, 3,750 of them
    exactly those twins, so the two sets are one bug seen twice (the module
    docstring has the full derivation and the 4.0 s gate arithmetic). Three cases:

    * ``def test`` at column 0 -> module-level function, ownerless, whether or
      not a class appears above it in the file (the old rule gave it one).
    * indented ``def test`` whose nearest column-0 scope opener is
      ``class Test*`` -> a collected method, owned by that class.
    * indented ``def test`` under a non-``Test*`` class, or nested inside a
      column-0 ``def`` (a test factory) -> pytest never collects it, so it is
      not in the universe at all. Attributing it to a class invented a node id
      the audit could never see, which is exactly how a dead exemption row can
      read live.
    """
    defs = _git_grep(r"^[[:space:]]*(async[[:space:]]+)?def test")
    scopes = _git_grep(r"^(class|def) [A-Za-z_]")
    pairs: set[tuple[str, str]] = set()
    for path, lines in defs.items():
        module = path[: -len(".py")].replace("/", ".")
        scope_lines = sorted(
            (int(m.group(1)), m.group(2), m.group(3))
            for m in (_SCOPE_RE.match(x) for x in scopes.get(path, []))
            if m
        )
        for entry in lines:
            m = _DEF_RE.match(entry)
            if not m:
                continue
            lineno, indent, name = int(m.group(1)), m.group(2), m.group(3)
            if not indent:
                # Column 0: a module-level test function. No owner, ever.
                pairs.add((module, name))
                continue
            kind = owner = None
            for slin, skind, sname in scope_lines:
                if slin < lineno:
                    kind, owner = skind, sname
                else:
                    break
            if kind == "class" and owner.startswith("Test"):
                pairs.add((f"{module}.{owner}", name))
            # otherwise: not collected by pytest -> deliberately not in the universe
    return pairs


_UNIVERSE = _junit_universe()
# Node ids as the audit receives them, built once: ``_dead`` and the witnesses
# scan the universe per pattern, so materialising the (node, pair) list a single
# time keeps every check a linear pass instead of re-sorting 35k tuples each call.
_NODES = sorted((f"{c}::{n}", (c, n)) for c, n in _UNIVERSE)


def _dead(patterns: list[str], shipped) -> list[str]:
    """Patterns no test matches.

    Attribution needs one pattern at a time, but ``is_known_slow_test`` takes no
    argument and consults the whole list -- so the fast pass finds a candidate
    with the shipped semantics spelled out, then the SHIPPED predicate must
    agree on that FIRST matching node. State the assert's real reach so it is not
    read as a stronger guard than it is: it only ever sees the *first* match of a
    pattern, and it is one-directional -- measured, dropping ``re.IGNORECASE``
    from the shipped predicate keeps every shipped row's first match case-safe,
    so the assert does NOT fire (0 disagreements across all rows). It is a
    cheap sanity check that the two matchers agree on the node they both land on,
    not a comprehensive drift detector.
    """
    dead = []
    for pat in patterns:
        hit = next(((node, cn) for node, cn in _NODES if re.search(pat, node, re.IGNORECASE)), None)
        if hit is None:
            dead.append(pat)
            continue
        classname, name = hit[1]
        assert shipped(classname, name), (
            f"pattern {pat!r} matched {hit[0]} but the shipped predicate calls it "
            "not-slow: this test's matcher and the audit's have drifted"
        )
    return dead


def test_harvest_found_a_real_universe():
    """Guard before anything else: an empty universe would certify every pattern dead."""
    assert len(_UNIVERSE) > 20_000, f"harvest returned {len(_UNIVERSE)} pairs"
    # A method pair (test under a top-level class), so the owner logic holds...
    assert (
        "backend.tests.unit.test_job_progress_reporter.TestJobCompletion",
        "test_complete_calculates_duration",
    ) in _UNIVERSE
    # ...AND a module-level pair defined at column 0, which is the arm a lazy
    # `\s*` -> `.+?` regression drops. Both morphologies must be present or the
    # liveness loop below can report a live row as dead.
    assert (
        "backend.tests.unit.core.test_compose_render_lists_ai_vlm",
        "test_default_services_render_lists_ai_vlm",
    ) in _UNIVERSE


def test_the_dead_check_fires_on_a_bogus_pattern():
    """Positive witness: the instrument CAN see a dead row (else the pin below is vacuous)."""
    bogus = r"test_no_such_file_zzz.*test_no_such_def_zzz"
    assert _dead([bogus], _audit.is_known_slow_test) == [bogus]
    # ...and it does NOT flag a row known to be live.
    assert (
        _dead([r"test_error_handler.*test_timestamp_auto_generated"], _audit.is_known_slow_test)
        == []
    )


# The owner-rule witness, both directions at once. ``test_pipeline_e2e.py``
# defines ``class ScriptedVlmClient`` and then SIXTEEN module-level ``def test``
# functions below it -- none are methods of that class, so pytest never emits a
# ``ScriptedVlmClient::`` classname for them. These two patterns are the same
# 16 tests seen from the two morphologies the owner bug swapped, so they pin the
# rule on the arm the bogus-pattern witness above cannot reach: a pattern that
# is DEAD to pytest but was LIVE to the old nearest-class harvest (the false
# green), and the TRUE module-level form the same harvest reported DEAD (the
# false red). Under the old rule these two results are exactly inverted.
_PHANTOM_OWNER = r"test_pipeline_e2e\.ScriptedVlmClient::"
_TRUE_MODULE_FORM = r"test_pipeline_e2e::test_batch_close"


def test_the_owner_rule_keeps_the_phantom_class_owner_dead():
    """A module-level def below a class must NOT be owned by that class.

    This is the direction the ``>20_000`` floor and the ``in _UNIVERSE`` pins
    cannot see: a fabricated ``ScriptedVlmClient::`` id would keep a dead
    exemption reading live forever, which is the false green the whole suite
    exists to prevent. If someone reverts the owner rule to "nearest preceding
    class", this goes red.
    """
    assert _dead([_PHANTOM_OWNER], _audit.is_known_slow_test) == [_PHANTOM_OWNER]


def test_the_owner_rule_keeps_the_true_module_form_live():
    """The same tests ARE live under their real module-level classname.

    The other half: the phantom must be replaced by the correct node, not merely
    dropped -- otherwise the harvest shrank and a genuine module-level def would
    now read dead (a false red, the reviewer's WITNESS B). This checks node
    EXISTENCE, not ``_dead``: ``_TRUE_MODULE_FORM`` is not a shipped exemption
    row, so the shipped predicate would (correctly) call it not-slow -- the
    assertion here is only that pytest emits the node at all.
    """
    rx = re.compile(_TRUE_MODULE_FORM, re.IGNORECASE)
    live = [node for node, _ in _NODES if rx.search(node)]
    assert live, f"module-level form {_TRUE_MODULE_FORM!r} matches no harvested node"
    # and it is genuinely the module-level shape, not a class owner
    assert all("::" in node and "." not in node.split("::", 1)[1] for node in live)


def test_every_slow_test_pattern_matches_a_real_test():
    """The rot pin: an exemption for a deleted test must go red, not hide."""
    assert _dead(_audit.SLOW_TEST_PATTERNS, _audit.is_known_slow_test) == []


def test_every_benchmark_pattern_matches_a_real_test():
    """Same failure mode, same list, one file over -- audited on the same terms."""
    assert _dead(_audit.BENCHMARK_PATTERNS, _audit.is_benchmark_test) == []


def test_the_two_rows_removed_from_the_list_stay_removed():
    """A deletion witness: re-adding either row re-introduces a dead exemption.

    Pinned by id (the census's own key discipline -- "no line numbers, they
    drift") rather than by list length, which a third row could satisfy by luck.
    """
    removed = [
        r"test_pipeline_e2e.*test_pipeline_llm_failure_fallback",
        r"test_enrichment_pipeline_household_matching.*"
        r"test_vehicle_household_matching_via_license_plate",
    ]
    for pat in removed:
        assert pat not in _audit.SLOW_TEST_PATTERNS, f"dead exemption re-added: {pat}"
        # And it is genuinely the dead kind, so re-adding it would re-break
        # test_every_slow_test_pattern_matches_a_real_test rather than fix it.
        assert _dead([pat], _audit.is_known_slow_test) == [pat]
