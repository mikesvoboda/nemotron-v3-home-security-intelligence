"""r109 evidence harness — the measurement tool PR #7003's evidence rests on.

Contract rule 3 (docs/uplevel/README.md:135): "Every script, fixture and harness a
package relies on is committed. Work from /tmp or a home directory does not count as
evidence." The r109 investigation measured through throwaway scripts under /tmp; this
file folds the load-bearing ones into the repo so a reviewer can re-measure every
claim after that sandbox is gone. Precedent: 8521f42bb committed B1.1's latency probe.

Placement is deliberate. backend/tests/evidence/ is OUTSIDE the nightly unit tier
(nightly-full-gate.yml:106 passes the explicit dirs unit/contracts/security) and
outside the PR-gate shard (ci.yml:755 runs pytest backend/tests/unit/). It IS
collected by a bare `pytest` (testpaths covers backend/tests, pyproject.toml:539),
and two probes write real hundreds-of-MB payloads, so every probe here is gated on
EVIDENCE_R109=1; a bare run gets clean skips and the tier cost stays zero.

    EVIDENCE_R109=1 uv run pytest backend/tests/evidence/ -p no:randomly \\
        --no-cov -v

Honest boundary (PROVENANCE): these probes re-measure the CLAIMS and re-derive the
comparisons from git blobs, so nothing here is retyped from memory. They do NOT
re-create the one-off exploratory orderings — the seed-pinned full-tier reds and the
seed-paired -n 8 / -n 2 control were single draws, labelled as such in the body.
Nor do they reproduce the hosted log shape: nightly-full-gate.yml:110 redirects the
tier's output to a file and :112 publishes only `tail -80`, so the run's real
collection header is not in the hosted artifact at all (a REST refetch of run 26's
job log returns the same 67,774 bytes the tail contains). Any collection count
quoted in the body from a LOCAL run says so at the point of use.
"""

from __future__ import annotations

import asyncio
import importlib.util
import logging
import os
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

import pytest

REPO = Path(__file__).resolve().parents[3]
BASE = "33735c95f"  # the commit #7003 branched from (pre-fix tree)
EVIDENCE_ON = os.environ.get("EVIDENCE_R109") == "1"

requires_evidence = pytest.mark.skipif(
    not EVIDENCE_ON,
    reason="r109 evidence probe: heavy by design; set EVIDENCE_R109=1 to run",
)
# The heavy probes measure work that legitimately exceeds 5s (the BASE census alone
# is ~2.8s per rep and a rep must complete for the comparison to exist), so they
# carry their own explicit budget. This is NOT the tier timeout: pyproject's
# `timeout = 5` still governs every gated test, untouched, and the shape probe at
# the bottom of this file pins exactly that fact. (Writing the BASE census probe
# without a marker failed against the ini timeout on the first run — the harness
# tripping the bug's own budget is the mechanism, restated here so nobody reads
# these markers as the ruling-83 line: no gated timeout or baseline is raised.)
heavy_budget = pytest.mark.timeout(300)


def _git_show(rev: str, relpath: str) -> str:
    """Read a file out of git — the blobs are the source of truth, never a retyped copy.

    Shelling out to git IS the mechanism here: rule 3 says evidence tools live in the
    repo, and re-deriving a claim from a committed blob is only honest if the tool
    reads the blob. So this call is deliberately unmocked, sanctioned with the same
    escapes the repo already uses for a test that shells out to build its own fixture
    (unit/test_r8_s3_florence_provider_retirement.py:161, and the "# real" entry in
    scripts/check-test-timeouts.py's own SAFE_COMMENTS list).
    """
    out = subprocess.run(  # noqa: S603 - argv is a literal list  # real - git is the fixture source
        ["git", "-C", str(REPO), "show", f"{rev}:{relpath}"],  # noqa: S607 - git resolved on PATH
        capture_output=True,
        text=True,
        check=True,
    )
    return out.stdout


def _load(name: str, source: str) -> Any:
    """Exec module source from its own temp dir (isolated: no import shadowing)."""
    home = Path(tempfile.mkdtemp(prefix=f"r109-evidence-{name}-"))
    path = home / f"{name}.py"
    path.write_text(source)
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _cache_settings(cache_dir: Path, max_cache_size_gb: float) -> Any:
    from backend.core.config import TranscodeCacheSettings

    # max_cache_size_gb has a pydantic ge=0.1 floor, so a probe that needs "over the
    # eviction target at low cost" scales its BYTES, not the config: the 0.1 GB floor
    # puts the target at int(0.1 * 0.8 * 1024**3) = 85_899_345 B, which 3 x 40 MB
    # declared exceeds. The shipped LRU test uses the file's own 1.0 GB config.
    return TranscodeCacheSettings(
        cache_dir=str(cache_dir),
        max_cache_size_gb=max_cache_size_gb,
        max_file_age_days=7,
        cleanup_threshold_percent=0.9,
        cleanup_target_percent=0.8,
        lock_timeout_seconds=30,
        enabled=True,
    )


# ---------------------------------------------------------------------------
# Census descent (claim: 2.79s -> 0.13s with an IDENTICAL file set, i.e. an
# optimization, not a scope change and not a raised timeout). Both versions are
# loaded from git: BASE has the rglob descent, HEAD has the pruned os.walk.
# ---------------------------------------------------------------------------


_ROOT_ANCHOR = "REPO_ROOT = Path(__file__).resolve().parents[4]"


def _census_module(name: str, rev: str) -> Any:
    """The census test module from a revision, retargeted at the real repo root.

    The blob resolves REPO_ROOT from its own __file__ at MODULE level, so the value
    cannot be patched after loading — exec would raise IndexError in the temp dir
    first. The line is rewritten instead, anchor-checked so a refactor is a loud
    failure rather than a census of the wrong tree.
    """
    src = _git_show(rev, "backend/tests/unit/scripts/test_vlm_profile_flag_is_retired.py")
    assert src.count(_ROOT_ANCHOR) == 1, (
        f"REPO_ROOT line moved in {rev} — re-anchor before trusting this probe"
    )
    src = src.replace(_ROOT_ANCHOR, f"REPO_ROOT = Path({str(REPO)!r})")
    return _load(name, src)


@requires_evidence
@heavy_budget
def test_census_prune_is_faster_and_the_file_set_is_identical() -> None:
    old = _census_module("r109_census_base", BASE)
    new = _census_module("r109_census_head", "HEAD")

    def best(fn: Any, reps: int = 2) -> tuple[float, set[Path], list[float]]:
        times: list[float] = []
        result: set[Path] = set()
        for _ in range(reps):
            t0 = time.perf_counter()
            found = set(fn())
            times.append(time.perf_counter() - t0)
            result = found
        return min(times), result, times

    old_dt, old_set, old_times = best(old._living_surfaces)
    new_dt, new_set, new_times = best(new._living_surfaces)
    print(
        f"\ncensus BASE reps {[f'{t:.2f}s' for t in old_times]} -> best {old_dt:.2f}s ({len(old_set)} files)"
    )
    print(
        f"census HEAD reps {[f'{t:.3f}s' for t in new_times]} -> best {new_dt:.3f}s ({len(new_set)} files)"
    )
    assert old_set == new_set, "the prune changed the scope — that would be a silent narrowing"
    assert new_dt < old_dt, "the pruned descent is not faster; the body's claim is wrong"


# ---------------------------------------------------------------------------
# Root-logging leak at the REAL call site. The shipped pin
# (unit/core/test_root_logging_isolation.py) mimics setup_logging's shape to stay
# hermetic; this probe re-measures the shipped backend.core.logging.setup_logging()
# itself: it arms an asctime-formatted handler that outlives the call, which is the
# leak the two isolation reds came from. The between-tests REVERSAL is the shipped
# pin's job; this probe pins the precondition only.
# ---------------------------------------------------------------------------


def _handler_snapshot() -> dict[str, dict[int, logging.Handler]]:
    snapshot: dict[str, dict[int, logging.Handler]] = {}
    snapshot["<root>"] = {id(h): h for h in logging.getLogger().handlers}
    for name, lg in logging.Logger.manager.loggerDict.items():
        if isinstance(lg, logging.PlaceHolder):
            continue
        snapshot[name] = {id(h): h for h in lg.handlers}
    return snapshot


def _asctime_leak_lines(before: dict[str, dict[int, logging.Handler]]) -> list[str]:
    lines: list[str] = []
    for name, handlers in _handler_snapshot().items():
        for hid, handler in handlers.items():
            if hid in before.get(name, {}):
                continue  # already there before the call -> not this call's doing
            if type(handler).__module__.startswith("_pytest"):
                continue  # pytest's own capturing handlers are not the product leak
            fmt = getattr(handler.formatter, "_fmt", None) if handler.formatter else None
            if fmt and "asctime" in fmt:
                lines.append(f"LEAK logger={name} handler={type(handler).__name__} fmt={fmt!r}")
    return lines


@requires_evidence
def test_setup_logging_arms_an_asctime_handler_that_leaks() -> None:
    from backend.core.logging import setup_logging

    before = _handler_snapshot()
    setup_logging()
    leaked = _asctime_leak_lines(before)
    print("\n" + "\n".join(leaked))
    assert leaked, (
        "setup_logging() no longer arms an asctime-formatted handler — the leak "
        "mechanism in #7003's Evidence section needs re-deriving"
    )


# ---------------------------------------------------------------------------
# Fat-bytes LRU test vs the shipped metadata-only one. Both bodies are extracted
# from git blobs, so this compares the real code, not a paraphrase — which means
# the fat leg writes the real 1.2 GB the fix removes. Claim: same verdict, ~100x
# cheaper (body cites 2.01s on 2 CPUs for the fat call, <=0.02s for every call in
# the file after the fix).
# ---------------------------------------------------------------------------

_LRU_HEADER = (
    "import time\n"
    "import pytest\n"
    "from backend.core.config import TranscodeCacheSettings\n"
    "from backend.services.transcode_cache import CacheEntry, TranscodeCache\n\n\n"
    "@pytest.mark.asyncio\n"
)
_LRU_DEF = re.compile(
    r"^(async )?def test_cache_cleanup_removes_lru_entries\([^)]*\):", re.MULTILINE
)


def _lru_test_from(rev: str, alias: str) -> Any:
    """The LRU cleanup test from a module blob, verbatim but renamed and de-fixture'd.

    BASE's signature is (cache, temp_dir); HEAD's is (cache). Both are rewritten to
    a single `cache` argument supplied by the caller, and the `def` keyword is
    normalized because BASE's line already says `async def`.
    """
    lines = _git_show(rev, "backend/tests/unit/services/test_transcode_cache.py").splitlines()
    start = next(
        i for i, ln in enumerate(lines) if "def test_cache_cleanup_removes_lru_entries" in ln
    )
    end = next(i for i in range(start + 1, len(lines)) if lines[i].startswith("@pytest.mark"))
    body = "\n".join(lines[start:end]).rstrip()
    body, nsubs = _LRU_DEF.subn(f"async def {alias}(cache):", body, count=1)
    assert nsubs == 1, f"LRU test signature moved in {rev} — re-anchor before trusting this probe"
    return _load(f"r109_lru_{alias}", _LRU_HEADER + body + "\n")


@requires_evidence
@heavy_budget
def test_metadata_only_lru_test_keeps_the_verdict_at_fraction_the_cost(tmp_path: Path) -> None:
    fat_mod = _lru_test_from(BASE, "fat")
    lean_mod = _lru_test_from("HEAD", "lean")

    wall: dict[str, float] = {}
    for label, module, test_fn in (
        ("fat", fat_mod, fat_mod.fat),
        ("lean", lean_mod, lean_mod.lean),
    ):
        cache_dir = tmp_path / label
        cache_dir.mkdir()
        cache = module.TranscodeCache(config=_cache_settings(cache_dir, 1.0))
        t0 = time.perf_counter()
        asyncio.run(test_fn(cache))  # each body asserts its own verdict internally
        wall[label] = time.perf_counter() - t0
    print(f"\nLRU fat  call: {wall['fat']:.2f}s (writes 1.2 GB)")
    print(f"LRU lean call: {wall['lean']:.3f}s (declares the same sizes)")
    assert wall["lean"] < wall["fat"] / 10, "the lean rewrite is not materially cheaper"


# ---------------------------------------------------------------------------
# Mutation control for the stat() blind spot (the claim: the old fat-bytes test
# could not tell a metadata-summing cleanup from a stat-summing one, because its
# real files made the two numerically identical; the shipped lean test can). The
# mutant is a temp copy of the service source — the repo tree is never touched.
# Bytes are scaled 10x below the shipped test (40 MB per entry against the 0.1 GB
# config floor); the relationship the claim depends on is unchanged.
# ---------------------------------------------------------------------------

_MUTANT_ANCHOR = "current_size = sum(e.size_bytes for e in self._metadata.values())"
_MUTANT_BODY = (
    "current_size = sum(Path(e.cached_path).stat().st_size for e in self._metadata.values())"
)


def _cleanup_mutant(rev: str = "HEAD") -> Any:
    src = _git_show(rev, "backend/services/transcode_cache.py")
    assert src.count(_MUTANT_ANCHOR) == 1, (
        "mutation anchor moved — re-anchor before trusting this probe"
    )
    return _load("r109_cleanup_mutant", src.replace(_MUTANT_ANCHOR, _MUTANT_BODY))


@requires_evidence
@heavy_budget
def test_stat_based_cleanup_survives_the_fat_shape_and_breaks_the_lean_one(tmp_path: Path) -> None:
    mutant = _cleanup_mutant()
    declared = 40_000_000  # 3 x declared = 120 MB > target 85,899,345 B (0.1 GB floor)

    def removed_under_mutant(write_real_bytes: bool) -> int:
        cache_dir = tmp_path / ("fat" if write_real_bytes else "lean")
        cache_dir.mkdir()
        cache = mutant.TranscodeCache(config=_cache_settings(cache_dir, 0.1))
        asyncio.run(cache.initialize())
        now = time.time()
        for i, age in enumerate(
            [1000, 500, 100]
        ):  # oldest to newest, as the shipped test orders them
            path = cache.cache_dir / f"entry{i}.mp4"
            if write_real_bytes:
                path.write_bytes(b"x" * declared)
            cache._metadata[f"entry{i}"] = mutant.CacheEntry(
                source_path=f"/video/{i}.mp4",
                source_mtime=1234567890.0 + i,
                cached_path=str(path),
                cached_at=now - age,
                last_accessed=now - age,
                size_bytes=declared,
            )
        try:
            return asyncio.run(cache.cleanup())
        except OSError:
            return -1  # a stat-based cleanup dies outright where the file was never written

    fat_removed = removed_under_mutant(True)
    lean_removed = removed_under_mutant(False)
    print(
        f"\nmutant(stat) cleanup: fat-shape removed={fat_removed}, lean-shape removed={lean_removed} (-1 = raised)"
    )
    assert fat_removed >= 1, (
        "the fat shape no longer survives a stat-based cleanup — then the old test "
        "WAS discriminating and #7003's blind-spot sentence must be reworded"
    )
    assert lean_removed <= 0, (
        "the shipped lean test must fail under a stat-based cleanup; it is the control"
    )


# ---------------------------------------------------------------------------
# Collection-shape facts the corrected body cites. The nightly and the PR gate
# differ in SHAPE, not in "subset vs whole": both start from the same addopts
# (-n 8 --dist=worksteal, pyproject.toml:545), and the difference that hid the
# r109 failures is the per-test budget — the nightly passes no --timeout, so
# pyproject's `timeout = 5` (:546) governs, while the PR shard raises it to 60s
# (ci.yml:760) and never co-invokes contracts/security with unit. Asserted from
# the workflow files so a future edit that changes the shape fails HERE instead of
# quietly invalidating the PR body.
# ---------------------------------------------------------------------------


def test_the_two_gates_differ_in_per_test_budget_not_subset_selection() -> None:
    nightly = (REPO / ".github/workflows/nightly-full-gate.yml").read_text()
    ci = (REPO / ".github/workflows/ci.yml").read_text()
    pyproject = (REPO / "pyproject.toml").read_text()

    # Both tiers inherit the same parallel defaults: neither passes -n/-p no:randomly.
    # Deliberate scope: this probe asserts the PER-TEST BUDGET (no --timeout on the
    # nightly), which is r109's load-bearing claim. It does NOT assert that the nightly
    # passes no `-n`, because ops-b's #7006 (ruling 113) adds `-n auto` to exactly this
    # tier — an assertion on the worker count would go red on a merge that changes
    # nothing about the 5 s deadline this package is about. Verified against #7006's
    # patch: the two string splits below still resolve and the tier still passes no
    # --timeout.
    assert 'addopts = "-n 8 --dist=worksteal' in pyproject
    assert "timeout = 5" in pyproject

    # Nightly: the three dirs in ONE invocation, and no --timeout override.
    unit_tier = nightly.split("uv run pytest backend/tests/unit backend/tests/contracts", 1)[1]
    unit_tier = unit_tier.split("nightly-backend-unit.log", 1)[0]
    assert "--timeout" not in unit_tier, (
        "the nightly now sets its own budget — the 5s claim needs re-deriving"
    )

    # PR gate: unit only, sharded, and a 60s per-test budget.
    assert "uv run pytest backend/tests/unit/ \\" in ci
    assert "--timeout=60" in ci

    # contracts and security run as their own invocations, never beside unit.
    assert "uv run pytest backend/tests/contracts/" in ci
    assert "uv run pytest backend/tests/security/" in ci

    # fast_select is a LOCAL selector: its only appearances in workflows are comments
    # and the invocation of its own test file. A real CI selection through
    # fast_select would make this fail, which is the point (the original body
    # claimed 50 skips in a PR shard were "fast_select rendering" — false).
    for wf in (nightly, ci):
        for line in wf.splitlines():
            if "fast_select" in line:
                stripped = line.strip()
                assert stripped.startswith("#") or "test_fast_select.py" in stripped, line


# ---------------------------------------------------------------------------
# Why 50 PR-gate jobs SKIP while this PR is a draft — and why that is not a
# test result. The lane agent first explained the 50 skips as "fast_select
# rendering"; the self-review disproved that, and the real mechanism turned out
# to be bigger than the wrong guess: `detect-changes` is itself draft-gated, so on
# a draft PR it publishes none of the outputs every test job consumes, and the
# unit shard (the job that carries --timeout=60) never runs at all. Asserted here
# because "CI Gate: success" is then an aggregate reading skipped inputs as
# satisfied, and a reviewer must not read it as "the suite passed" (ruling 109's
# pre-approval is conditioned on green CI).
# ---------------------------------------------------------------------------

_DRAFT_CLAUSE = "github.event_name != 'pull_request' || github.event.pull_request.draft != true"
_DRAFT_IF_LINE = f"if: {_DRAFT_CLAUSE}"  # the flow-scalar form detect-changes uses


def _job_block(ci: str, job_id: str, terminator: str) -> str:
    """One job's definition, cut at its first structural child, so a sibling's
    `if:` can never be credited to this job."""
    head = f"\n  {job_id}:\n"
    assert head in ci, f"job {job_id} moved/renamed — re-anchor before trusting this probe"
    block = ci.split(head, 1)[1]
    return block.split(terminator, 1)[0]


def _normalize(expr: str) -> str:
    return " ".join(expr.split())


def _job_if_expr(block: str) -> str:
    """The job's `if:` condition in EITHER YAML form, whitespace-normalized.

    ci.yml uses both: a one-line flow scalar (`detect-changes`) and a block scalar
    whose clause is wrapped in parens and split across lines (`unit-tests`). A
    probe that only matched the first form would silently pass on a job that was
    de-gated into the second — which is exactly how this helper was first written
    wrong, and the failure is why it reads the expression instead of grepping.
    """
    lines = block.splitlines()
    for i, ln in enumerate(lines):
        stripped = ln.strip()
        if not stripped.startswith("if:"):
            continue
        rest = stripped[len("if:") :].strip()
        if rest not in {"|", "|-", ">", ">-"}:
            return _normalize(rest)
        body: list[str] = []
        for cont in lines[i + 1 :]:
            if cont.strip() and not cont.startswith("      "):
                break  # dedent back to a job-level key ends the block scalar
            body.append(cont)
        return _normalize("\n".join(body))
    raise AssertionError("job has no `if:` at all — the draft-gate claim is now wrong")


def _is_draft_gated(block: str) -> bool:
    return _DRAFT_CLAUSE in _job_if_expr(block)


def _detect_changes_is_draft_gated(ci: str) -> bool:
    return _is_draft_gated(_job_block(ci, "detect-changes", "\n    steps:"))


def _unit_shard_waits_on_detect_changes(ci: str) -> bool:
    block = _job_block(ci, "unit-tests", "\n    services:")
    return "needs.detect-changes.outputs.backend == 'true'" in block


def test_the_pr_gate_never_runs_the_unit_shard_while_the_pr_is_a_draft() -> None:
    ci = (REPO / ".github/workflows/ci.yml").read_text()

    assert _detect_changes_is_draft_gated(ci), (
        "detect-changes is no longer draft-gated — then a draft PR DOES get change "
        "outputs and #7003's CI-read section needs re-deriving"
    )
    assert _unit_shard_waits_on_detect_changes(ci), (
        "the unit shard no longer consumes detect-changes outputs — the skip "
        "explanation in the body needs re-deriving"
    )
    # The shard ALSO carries its own draft gate, so it is doubly conditional: even
    # if someone de-gated detect-changes, the shard still would not run here.
    assert _is_draft_gated(_job_block(ci, "unit-tests", "\n    services:"))

    # Negative control: the helpers must be reading the GATE, not just finding the
    # job name. De-gate detect-changes (keep a non-draft condition so the shape is
    # still an `if:`) and the helper must go False.
    anchor = (
        "      should-run-all: ${{ github.ref == 'refs/heads/main' "
        "|| steps.filter.outputs.workflow == 'true' }}\n    " + _DRAFT_IF_LINE + "\n"
    )
    mutant = ci.replace(
        anchor,
        anchor.replace(_DRAFT_IF_LINE, "if: github.event_name != 'pull_request'", 1),
        1,
    )
    assert mutant != ci, "detect-changes draft-gate anchor moved — the control is vacuous"
    assert not _detect_changes_is_draft_gated(mutant), (
        "the helper does not actually track the draft gate — it is not a control"
    )
    # ...and the shard's own gate is a separate condition, so it still skips.
    assert _is_draft_gated(_job_block(mutant, "unit-tests", "\n    services:"))
