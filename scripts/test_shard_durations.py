#!/usr/bin/env python3
"""Gate for the committed shard-planning durations file (batch-9 row 2, backend lane).

Rides ci.yml's anti-rot list (`uv run python -m pytest`, exact line — the
self-pin below enforces it), so it must stay pytest-function style like its
neighbours test_workflow_paths.py / test_retired_paths.py.

The register row: "CI count-balances shards with no committed durations file,
so a file added anywhere reshuffles shards ('shard-placement roulette' — the
root cause behind #6921's deterministic red that was actually an isolation
bug)". This gate pins the fix, and measurement corrected the row's causal
story on the one point that changes what the fix must be:

  * MEASURED (runs 37940703535 @ 5689e80ef, 37933347572 @ fb7ddce9): shard
    counts are equal (7851/7851/7851/7849) while junit TIME sums span 2.207x
    and 1.207x. Count-balancing is not time-balancing because pytest-randomly
    5.0.0 keeps module files contiguous (it shuffles within a module, then
    permutes whole module blocks by a seed-keyed sort), so one heavy file
    landing on the wrong side of a boundary decides the shard — test_redis.py
    alone is 30.9 s of the 148.3 s shard it landed on in run 37940703535
    (shard 3; the 168.2 s shard 1 lacks it), and the NEXT run it landed in
    another shard entirely (shard 4, 26.9 s of its 145.5 s).
  * MEASURED: the per-RUN reshuffle is 24,139 of 31,402 tests = 76.9%, driven by
    --randomly-seed=github.run_id re-permuting module blocks. #6921's red
    landed on a docs-only PR — no file was added — so the reshuffle that bit
    was the seed's, not an insert's. Committing durations under the default
    duration_based_chunks fixes the time spread (simulated 1.51x mean ->
    1.02x at 24 seeds, scripts/simulate-shard-spread.py) but leaves that
    churn untouched, because chunks cuts the collected ORDER. least_duration
    makes the split a pure function of (collected set, durations): churn 2%
    (the same-name tie surface: 2495 of 31403 unit tests share a full test
    name — pytest-split's
    tie-break pre-sort key is str(item) = "<Function ...>", which carries the
    param id, not the nodeid; algorithms.py:62-65). A small insert is nearly
    incremental there (0 existing movers for a 20-test module, simulated) —
    greedy LPT only cascades when the added weights straddle a group's balance
    point — while chunks moves up to 30 existing tests per insert and re-rolls
    all 31k placements with every seed. See scripts/simulate-shard-spread.py.

So the fix is both halves of the row's "commit .test_durations OR pin the
split": the committed file (minted by scripts/mint-test-durations.py) and the
algorithm pin. The WP2.1 seed pin stays exactly where it is — disjoint shard
groups need it, and least_duration composes with it (placement seed-invariant,
intra-shard execution order still fuzzed).
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
import yaml

REPO = Path(__file__).resolve().parent.parent
CI = REPO / ".github" / "workflows" / "ci.yml"
REUSABLE = REPO / ".github" / "workflows" / "integration-shard.yml"
DURATIONS = REPO / ".test_durations"

# Nodeid shape: a real test file path, then an arbitrary :: tail — the tail
# carries class chains, test names and parametrization ids, which pytest
# builds from arbitrary strings ("...blocked[/etc/passwd-absolute path to
# passwd]" is a real committed key; 2,978 keys carry a [param] id at all).
# Only the file part is shape-checkable; JSON keys cannot contain newlines.
NODEID_RE = re.compile(r"^backend/tests/[^:\n]+\.py(::.*)?$")
ALGORITHM = "--splitting-algorithm=least_duration"

# Floors set well below the 2026-10-09 mint (32,931 keys: 31,402 carry
# /unit/, 1,542 carry /integration/, 13 both — backend/tests/unit/
# integration/; 559.5 s of unit-tier time) so an ordinary refresh passes
# with room; a tier going dark, or a truncated file, cannot.
MIN_KEYS_TOTAL = 20_000
MIN_KEYS_UNIT = 15_000
MIN_KEYS_INTEGRATION = 200
MIN_SECONDS_TOTAL = 300.0
MAX_DEAD_FILE_RATIO = 0.05  # 95% of keys must still point at a file in the tree


def _durations() -> dict[str, float]:
    if not DURATIONS.exists():
        pytest.fail(
            ".test_durations is missing. Mint it:\n"
            "  gh run download <green-main-run-id> --pattern 'test-results-unit-shard-*' --dir /tmp/junit\n"
            "  gh run download <green-main-run-id> --pattern 'test-results-integration-*' --dir /tmp/junit\n"
            "  uv run python scripts/mint-test-durations.py /tmp/junit\n"
            "With no file, pytest-split count-balances and the sharded legs are a"
            " time lottery (2.207x measured spread on run 37940703535)."
        )
    return json.loads(DURATIONS.read_text())


def _code_lines(script: str) -> str:
    """Script text minus whole-line shell comments.

    A `run:` scalar is one string to YAML — a `#` line inside it is a shell
    comment pre-commit/YAML never sees as one, so raw substring matching lets a
    COMMENT satisfy an assertion about the argv. integration-shard.yml's own
    explanatory comment quotes --splitting-algorithm=least_duration: with the
    real flag line deleted, whole-script matching still passes (the shipped
    gate caught this on itself in review). Stripping #-lines first makes the
    assertion about the executed command only.
    """
    return "\n".join(
        ln for ln in script.splitlines() if not ln.lstrip().startswith("#")
    )


def _split_legs(path: Path) -> list[str]:
    """Run-scripts of every step that runs pytest-split (contains --splits).

    Text-level on the parsed YAML `run` values, comments stripped (see
    _code_lines): only the actual pytest argv is examined (mirrors
    scripts/test_coverage_denominator.py's scoped-block approach).
    """
    doc = yaml.safe_load(path.read_text())
    return [
        _code_lines(run)
        for job in (doc.get("jobs") or {}).values()
        for step in job.get("steps") or []
        if (run := step.get("run")) and "--splits" in run and "pytest" in run
    ]


def test_durations_file_is_the_shape_pytest_split_writes() -> None:
    """1. Parses, non-empty, nodeid keys -> non-negative numbers.

    A file that stops looking like pytest-split's own --store-durations output
    is a file nobody reads; redden the drift instead of letting it rot quiet.
    """
    data = _durations()
    assert isinstance(data, dict) and data, ".test_durations must be a non-empty JSON object"
    bad_shape = [k for k in data if not isinstance(k, str) or not NODEID_RE.match(k)]
    assert not bad_shape, f"{len(bad_shape)} keys are not backend/tests nodeids, e.g. {bad_shape[:3]}"
    bad_val = [k for k, v in data.items() if not isinstance(v, (int, float)) or v < 0]
    assert not bad_val, f"{len(bad_val)} values are not non-negative numbers, e.g. {bad_val[:3]}"


def test_both_tiers_present_with_room() -> None:
    """2. Coverage floors per tier, far under measurement.

    The plugin fills missing keys with the file's mean, so a tier that quietly
    vanishes from the file falls back to count-balancing for that tier only —
    invisible in one shard's wall time. Floors turn that regression red.
    """
    data = _durations()
    keys = list(data)
    unit = [k for k in keys if "/unit/" in k]
    integ = [k for k in keys if "/integration/" in k]
    assert len(keys) >= MIN_KEYS_TOTAL, f"{len(keys)} keys < floor {MIN_KEYS_TOTAL} — file truncated?"
    assert len(unit) >= MIN_KEYS_UNIT, f"{len(unit)} unit keys < floor {MIN_KEYS_UNIT} — unit-tier planning data lost"
    assert len(integ) >= MIN_KEYS_INTEGRATION, (
        f"{len(integ)} integration keys < floor {MIN_KEYS_INTEGRATION} — integration-tier planning data lost"
    )
    total_s = sum(data.values())
    assert total_s >= MIN_SECONDS_TOTAL, f"{total_s:.1f}s total < floor {MIN_SECONDS_TOTAL}s — weights look hollow"


@pytest.mark.timeout(60)  # ~5.2k stat()s over the worktree; measured ~0.4s locally
def test_file_has_not_rotted() -> None:
    """3. >=95% of keys' file parts exist in the tree.

    Dead keys are individually free (the plugin filters them via
    _remove_irrelevant_durations), but a file whose keys mostly point at
    deleted code has stopped planning anything and still LOOKS committed —
    it must say so loudly instead.
    """
    data = _durations()
    files = sorted({k.split("::", 1)[0] for k in data})
    dead = [f for f in files if not (REPO / f).exists()]
    ratio = len(dead) / len(files) if files else 1.0
    assert ratio <= MAX_DEAD_FILE_RATIO, (
        f"{len(dead)}/{len(files)} distinct test files in .test_durations no longer"
        f" exist ({ratio:.0%} > {MAX_DEAD_FILE_RATIO:.0%}) — re-mint from a current green run"
    )


@pytest.mark.parametrize("workflow", [CI, REUSABLE], ids=lambda p: p.name)
def test_sharded_legs_pin_least_duration_and_keep_the_seed(workflow: Path) -> None:
    """4. The pin this package adds, and WP2.1's pin it must not disturb.

    Without the algorithm the legs run duration_based_chunks, which cuts the
    collected ORDER — and pytest-randomly re-permutes module blocks per run,
    so 76.9% of tests change shard every run even on a docs-only PR (#6921's
    mechanism). The seed assertions here are a tripwire for THIS package's
    edit; scripts/test_coverage_denominator.py owns that property's full proof.
    """
    legs = _split_legs(workflow)
    assert legs, f"{workflow.name}: no pytest-split invocation found"
    for script in legs:
        assert ALGORITHM in script, (
            f"{workflow.name}: a --splits leg lacks {ALGORITHM} — chunks re-rolls"
            " shard placement with the seed (see module docstring)"
        )
        assert "--randomly-seed=" in script and "github.run_id" in script, (
            f"{workflow.name}: --splits leg lost the run-scoped --randomly-seed pin"
            " (WP2.1 disjoint-groups property)"
        )


def test_nodeid_mapping_round_trips_against_pytest_itself() -> None:
    """6. Every committed key, mangled by pytest's own mangle_test_address and
    unmangled by scripts/mint-test-durations.py, returns to itself.

    The mint tool's inverse is load-bearing: pytest-split looks durations up
    by nodeid (algorithms.py:157) but junit carries pytest's MANGLED form
    (classname dotted path + class folded in, name with the param id). If the
    inverse drifts from mangle_test_address, keys silently miss and the whole
    tier falls back to mean-weights — a green file that plans nothing. This
    test is that join, executable, over the entire committed file.
    """
    import importlib.util

    from _pytest.junitxml import mangle_test_address

    spec = importlib.util.spec_from_file_location(
        "mint_test_durations", REPO / "scripts" / "mint-test-durations.py"
    )
    mint = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mint)

    data = _durations()
    misses = []
    for nodeid in data:
        names = mangle_test_address(nodeid)
        classname, name = ".".join(names[:-1]), names[-1]
        if mint.junit_to_nodeid(classname, name) != nodeid:
            misses.append(nodeid)
    assert not misses, f"{len(misses)}/{len(data)} keys fail the mangle round-trip, e.g. {misses[:3]}"


def test_comment_cannot_satisfy_a_pin_assertion() -> None:
    """7. The assertion-4 mask, caught by this package's own review and pinned.

    Feed _code_lines a script whose ONLY copy of each pinned flag is a shell
    comment inside the run scalar: after stripping, both substring assertions
    must fail. Before this fix they passed — integration-shard.yml's
    explanatory comment quotes the flag, so deleting the real argv line kept
    the gate green (self-review finding #2, 2026-10-09).
    """
    masked = (
        "# run pytest with --splitting-algorithm=least_duration and\n"
        "# --randomly-seed=github.run_id, per batch-9 row 2\n"
        "uv run pytest backend/tests/ --splits 4 --group 1\n"
    )
    stripped = _code_lines(masked)
    assert ALGORITHM not in stripped
    assert "--randomly-seed=" not in stripped and "github.run_id" not in stripped
    # and the real argv still survives the strip (the fix is scoping, not
    # blinding): a comment plus the true flag line asserts green.
    assert ALGORITHM in _code_lines(masked + f"  uv run pytest {ALGORITHM}\n")


def test_gate_is_wired_into_ci() -> None:
    """5. Self-pin (mirrors scripts/test_workflow_paths.py:884-893): a gate that
    can be deleted from its only CI invocation without a red is already dead."""
    lines = [ln.strip() for ln in CI.read_text(encoding="utf-8").splitlines()]
    assert "scripts/test_shard_durations.py" in lines, (
        "this gate must ride ci.yml's anti-rot list (exact-line membership, not a"
        " substring — a substring survives the line's deletion)"
    )
