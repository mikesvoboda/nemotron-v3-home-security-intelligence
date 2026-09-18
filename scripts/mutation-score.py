#!/usr/bin/env python3
"""WP4.3: per-module mutation scores from mutmut 3.x's cache.

mutmut 3 parks verdicts in `mutants/<source-path>.meta` (`exit_code_by_key`:
mutant-key -> pytest exit code) and publishes only ONE aggregate
(export-cicd-stats -> mutants/mutmut-cicd-stats.json). The PLAN's done-when --
"mutation score is reported for the widened set and tracked over time" --
needs the per-module view and a commit-stable artifact; this is that
aggregation. Nothing else in the tree computes it, and the workflow's
`mutmut results | tee $GITHUB_STEP_SUMMARY` (14-day artifact retention) is
visibility, not history.

Verdict classification is IMPORTED from mutmut (stats.status_by_exit_code),
never copied, so a mutmut upgrade moves our semantics with it; the only thing
held locally is the subset of codes the score formula uses (pinned against
the import by scripts/test_mutation_score.py). The score formula is mutmut's
own `badge`:  (killed + timeout) / (total - skipped) * 100
(timeout counts as caught because a mutant that hangs a test was detected by
the test suite; `no tests`/`suspicious`/`not checked` are neither numerator
nor denominator members only where mutmut's badge excludes them -- see
http://localhost:8000 badge's tested = total - skipped).

Output (stdout JSON):
    { "generated": ..., "modules": [{module, killed, timeout, survived,
      suspicious, no_tests, skipped, not_checked, total, score}],
      "totals": {..., score}, "target_modules": [relpaths] }

`--targets` alone prints the WP4.3 denominator (the modules `mutation-run.sh`
mutates) so the CI publish step can verify the run covered the PLAN's widened
set -- a partial run then shows in the artifact, never masquerades as the
whole.

A missing/empty mutants/ tree is rc=1 (the run never happened) -- a 0-module
report would otherwise be committed as a baseline reset.

Usage:
    uv run python scripts/mutation-score.py [--root DIR]   # full report
    uv run python scripts/mutation-score.py --targets      # denominator only

Tests: uv run pytest scripts/test_mutation_score.py -q
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT_DEFAULT = Path(__file__).resolve().parent.parent

# The codes the score formula cares about, as mutmut names them. The test
# file pins every pair against mutmut.stats.status_by_exit_code.
VERDICT_CODES = {
    1: "killed",
    3: "killed",  # internal error in pytest means a kill
    0: "survived",
    36: "timeout",
    255: "timeout",
    24: "timeout",
    -24: "timeout",
    152: "timeout",
    5: "no_tests",
    33: "no_tests",
    34: "skipped",
    35: "suspicious",
    37: "caught_by_type_check",
}
_KILLED = {"killed", "timeout"}  # badge: timeout counts as caught


def _mutmut_status_map() -> dict[int, str]:
    """mutmut's authoritative exit-code -> status map (imported, not copied)."""
    from mutmut.stats import status_by_exit_code

    # None ("not checked") keys are our own classify() branch, never a lookup;
    # the defaultdict's key type is the only reason the cast below exists.
    return {
        int(code): str(status).replace(" ", "_")
        for code, status in status_by_exit_code.items()
        if code is not None
    }


def classify(exit_code: int | None, status_map: dict[int, str]) -> str:
    if exit_code is None:
        return "not_checked"
    return status_map.get(exit_code, "suspicious")


def target_modules(root: Path) -> list[str]:
    """The WP4.3 denominator: every module under backend/services/ and
    backend/api/routes/, package __init__ files included -- mutmut mutates
    them (baseline run 2026-09-17: should_mutate() is True for them; 269
    generated files = 266 concrete + 3 init, and services/__init__.py alone
    is 703 lines of re-export logic). Excluding them here would print a gap
    for a module the run actually covered."""
    out = []
    for base in ("backend/services", "backend/api/routes"):
        for p in sorted((root / base).rglob("*.py")):
            out.append(p.relative_to(root).as_posix())
    return sorted(out)


def score(stats: dict[str, int]) -> float | None:
    tested = stats["total"] - stats["skipped"]
    if tested <= 0:
        return None
    caught = sum(stats[k] for k in _KILLED)
    return caught / tested * 100


def _metas(root: Path) -> list[Path]:
    mutants = root / "mutants"
    return sorted(
        p
        for p in mutants.glob("backend/**/*.py.meta")
        if "tests" not in p.relative_to(mutants).parts
    )


def repair_metas(root: Path) -> list[str]:
    """Delete torn (unparseable) .meta files AND their mutant .py copies.

    A checking step killed by the CI budget can die mid-save (json.dump is
    not atomic); mutmut's own loader guards only FileNotFoundError, so a torn
    file would crash EVERY later run against a restored cache. Deletion --
    not a rewritten all-empty meta -- is the sound repair:
    create_mutants_for_file SKIPS regeneration when the mutant copy is newer
    than the source (its mtime gate runs before any meta is consulted), so a
    reset-but-present meta would never be refilled and the module's mutants
    would silently vanish from the denominator. Removing the copy forces the
    OSError regeneration path; generation then writes a fresh meta with None
    for every mutant, so they all recount and recheck. Returns the deleted
    meta paths (repo-relative) so the caller can be loud."""
    repaired = []
    for meta_path in _metas(root):
        try:
            json.loads(meta_path.read_text())
        except json.JSONDecodeError, UnicodeDecodeError:
            meta_path.unlink()
            mutant_copy = meta_path.with_suffix("")  # drop ".meta", not ".py.meta"
            if mutant_copy.exists():
                mutant_copy.unlink()
            repaired.append(meta_path.relative_to(root).as_posix())
    return repaired


def aggregate(root: Path) -> dict:
    status_map = _mutmut_status_map()
    mutants = root / "mutants"
    metas = _metas(root)
    if not metas:
        raise SystemExit  # caller prints and rc=1; see main()
    modules = []
    stats_list: list[dict[str, int]] = []
    torn_metas = 0
    for meta_path in metas:
        rel = meta_path.relative_to(mutants).as_posix()[: -len(".meta")]
        try:
            meta = json.loads(meta_path.read_text())
        except json.JSONDecodeError, UnicodeDecodeError:
            # A timeout-killed checking step can truncate a meta mid-save.
            # Counting it (completed=False) beats the two silent failures:
            # crashing every later run (mutmut's own loader's behavior) or
            # skipping it so a cache with holes reads as complete.
            torn_metas += 1
            print(f"torn meta (unparseable): {rel} -- run with --repair", file=sys.stderr)
            continue
        stats = dict.fromkeys(
            (
                "killed",
                "timeout",
                "survived",
                "suspicious",
                "no_tests",
                "skipped",
                "not_checked",
                "caught_by_type_check",
                "segfault",
                "check_was_interrupted_by_user",
            ),
            0,
        )
        for code in meta["exit_code_by_key"].values():
            stats[classify(code, status_map)] += 1
        stats["total"] = sum(stats.values())
        if stats["total"] - stats["not_checked"] == 0:
            continue  # generated, never checked -- nothing was measured
        stats_list.append(stats)
        modules.append({"module": rel, **stats, "score": score(stats)})
    if not stats_list:
        raise SystemExit  # every mutant unchecked (interrupted run) -- rc=1 below
    counts = {k: sum(s[k] for s in stats_list) for k in stats_list[0]}
    totals: dict[str, object] = {**counts, "score": score(counts)}
    # The weekly-convergence contract (WP4.3 CI repair): a cold run cannot
    # finish the whole denominator inside one job's budget, so verdicts
    # accumulate across runs. An ACCUMULATING cache must never read as a
    # finished one -- that is how a trend launders progress. completed is
    # false while anything is unchecked OR any meta is torn.
    progress = {
        "total": counts["total"],
        "checked": counts["total"] - counts["not_checked"],
        "not_checked": counts["not_checked"],
        "torn_metas": torn_metas,
        "completed": counts["not_checked"] == 0 and torn_metas == 0,
    }
    return {
        "schema_version": 1,
        "modules": modules,
        "totals": totals,
        "progress": progress,
        "target_modules": target_modules(root),
    }


HISTORY_MAX_RUNS = 60  # weekly cadence -> ~a year of runs kept in the file


def append_history(path: Path, entry: dict, cap: int = HISTORY_MAX_RUNS) -> None:
    """Add this run to the committed history file, oldest-first, capped.
    The file is the artifact the schedule's PR commits -- 'tracked over time'
    means the series, not just the latest number."""
    try:
        data = json.loads(path.read_text())
        runs = data["runs"]
    except OSError, KeyError, ValueError:
        runs = []
    runs.append(entry)
    path.write_text(json.dumps({"schema_version": 1, "runs": runs[-cap:]}, indent=2) + "\n")


def main() -> int:
    ap = argparse.ArgumentParser(description="WP4.3 per-module mutation score from mutmut's cache")
    ap.add_argument("--root", default=str(REPO_ROOT_DEFAULT))
    ap.add_argument("--targets", action="store_true", help="print the widened denominator only")
    ap.add_argument(
        "--history",
        type=Path,
        help="append the run entry to this JSON history file (the committed series)",
    )
    ap.add_argument("--date", default="", help="stamp for the history entry (CI passes run_date)")
    ap.add_argument(
        "--repair",
        action="store_true",
        help="delete torn (unparseable) .meta files and their mutant copies, then exit 0",
    )
    args = ap.parse_args()
    root = Path(args.root).resolve()
    if args.targets:
        print(json.dumps(target_modules(root), indent=2))
        return 0
    if args.repair:
        # Standalone step: CI runs this after restoring the cache and BEFORE
        # mutation-run.sh, because mutmut's own loader crashes on a torn meta
        # -- repairing at score time would be too late to let the run start.
        # Runs BEFORE the missing-tree guard: on a cold cache there is no
        # mutants/ yet (generation in the run step creates it), and repair
        # there is a no-op, not a failure. Safe on a nothing-measured cache.
        for rel in repair_metas(root):
            print(f"deleted torn meta + mutant copy (will regenerate): {rel}", file=sys.stderr)
        return 0
    if not (root / "mutants").is_dir():
        print(
            "no mutants/ tree -- mutation-run.sh must run first (a missing cache is not a score of 0)",
            file=sys.stderr,
        )
        return 1
    try:
        report = aggregate(root)
    except SystemExit:
        print(
            "no mutants/*.meta with checked verdicts under mutants/ -- nothing was measured",
            file=sys.stderr,
        )
        return 1
    print(json.dumps(report, indent=2, sort_keys=False))
    if args.history:
        append_history(
            args.history,
            {
                "date": args.date,
                "totals": report["totals"],
                "progress": report["progress"],
                "modules": report["modules"],
            },
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
