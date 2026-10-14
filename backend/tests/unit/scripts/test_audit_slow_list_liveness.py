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

**Why the universe is harvested with ``git grep`` and not with ``ast``.** The
audit's own unit-tier threshold is 1.0 s, and this suite runs in that tier.
Parsing all 1,231 ``test_*.py`` files with ``ast.parse`` measures ~5.0 s and a
full-file regex scan ~2.4 s -- either would make the rot-pin itself a breach of
the gate it protects. Two ``git grep`` passes harvest every ``def test*`` and
every top-level ``class`` in 44 ms total, which is 20x under the WARN line.

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
_DEF_RE = re.compile(r"^(\d+):\s*(?:async\s+)?def\s+(test\w*)")
_CLASS_RE = re.compile(r"^(\d+):class\s+(\w+)")


def _git_grep(pattern: str) -> dict[str, list[str]]:
    """One pass over the tracked tree; {path: ["lineno:content", ...]}."""
    out = subprocess.run(
        ["git", "grep", "-I", "-n", "-E", pattern, "--", "*.py"],
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

    classname is the dotted module path, plus the enclosing top-level class when
    the test is a method -- which is the shape ``is_known_slow_test`` receives.
    """
    defs = _git_grep(r"^[[:space:]]*(async[[:space:]]+)?def test")
    classes = _git_grep(r"^class [A-Za-z_]")
    pairs: set[tuple[str, str]] = set()
    for path, lines in defs.items():
        module = path[: -len(".py")].replace("/", ".")
        class_lines = sorted(
            (int(m.group(1)), m.group(2))
            for m in (_CLASS_RE.match(x) for x in classes.get(path, []))
            if m
        )
        for entry in lines:
            m = _DEF_RE.match(entry)
            if not m:
                continue
            lineno, name = int(m.group(1)), m.group(2)
            owner = None
            for cline, cname in class_lines:
                if cline < lineno:
                    owner = cname
                else:
                    break
            pairs.add((f"{module}.{owner}" if owner else module, name))
    return pairs


_UNIVERSE = _junit_universe()
# Node ids as the audit receives them, built once: 35k `re.search` calls per
# pattern would push this suite over the audit's own 1.0 s unit threshold.
_NODES = sorted((f"{c}::{n}", (c, n)) for c, n in _UNIVERSE)


def _dead(patterns: list[str], shipped) -> list[str]:
    """Patterns no test matches.

    Attribution needs one pattern at a time, but ``is_known_slow_test`` takes no
    argument and consults the whole list -- so the fast pass finds a candidate
    with the shipped semantics spelled out, then the SHIPPED predicate must
    agree that the candidate is exempt. A reimplementation that drifted from
    ``re.IGNORECASE`` or the ``::`` separator would then disagree, not silently
    pass.
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
    assert _dead([r"test_error_handler.*test_timestamp_auto_generated"], _audit.is_known_slow_test) == []


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
