#!/usr/bin/env python3
"""Analyze test results to detect flaky tests and generate reports.

This script processes JSON Lines files containing test outcomes from multiple
CI runs and identifies tests that exhibit flaky behavior (inconsistent pass/fail).

Usage:
    python scripts/analyze-flaky-tests.py <results-dir>
    python scripts/analyze-flaky-tests.py <results-dir> --output flaky-report.json
    python scripts/analyze-flaky-tests.py <results-dir> --allowlist-file .github/flake-allowlist.yml

WP0.8: "already handled" means REGISTERED in .github/flake-allowlist.yml
(Linear tracking ref + expiry, enforced by scripts/check-flake-allowlist.py).
The legacy `--quarantine-file flaky_tests.txt` free-form manifest — which this
script used to auto-append on `--update-quarantine`, with no owner and no
expiry — was retired with that file; registration is now a reviewed edit.

Environment variables:
    FLAKY_THRESHOLD: Pass rate below which a test is considered flaky (default: 0.9)
    MIN_RUNS: Minimum runs required to flag a test as flaky (default: 3)
    RERUN_WEIGHT: How much to weight rerun successes in flakiness score (default: 0.5)

Output:
    - Console report of detected flaky tests
    - Optional JSON report for programmatic consumption
    - GitHub Actions job summary if GITHUB_STEP_SUMMARY is set
"""

import argparse
import json
import os
import sys
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path


def get_config() -> dict:
    """Get configuration from environment variables."""
    return {
        "flaky_threshold": float(os.environ.get("FLAKY_THRESHOLD", "0.9")),
        "min_runs": int(os.environ.get("MIN_RUNS", "3")),
        "rerun_weight": float(os.environ.get("RERUN_WEIGHT", "0.5")),
    }


def parse_results_file(filepath: Path) -> list[dict]:
    """Parse a JSON Lines file containing test results.

    Each line is a JSON object with test outcomes from a single CI run.
    Lines that are valid JSON but not objects (a scalars file the artifact
    regex happened to drag in) are skipped, not fatal (WP1.5: measured live —
    the harvest also contains playwright's pretty-printed e2e-results.json;
    its string lines crashed aggregation with 'str' has no attribute 'get').
    Warnings are capped per file: a foreign multi-thousand-line file must not
    flood the job log either.
    """
    results = []
    warned = 0
    try:
        with filepath.open() as f:
            for line_num, raw_line in enumerate(f, 1):
                stripped_line = raw_line.strip()
                if not stripped_line:
                    continue
                try:
                    data = json.loads(stripped_line)
                except json.JSONDecodeError as e:
                    if warned < 3:
                        print(
                            f"Warning: Could not parse line {line_num} in {filepath}: {e}",
                            file=sys.stderr,
                        )
                    warned += 1
                    continue
                if isinstance(data, dict):
                    results.append(data)
                elif warned < 3:
                    print(
                        f"Warning: line {line_num} in {filepath} is valid JSON but not an "
                        f"object ({type(data).__name__}) — skipping file's non-record lines",
                        file=sys.stderr,
                    )
                    warned += 1
        if warned > 3:
            print(
                f"Warning: {warned - 3} more unparsable/non-record lines in {filepath}",
                file=sys.stderr,
            )
    except Exception as e:
        print(f"Warning: Could not read {filepath}: {e}", file=sys.stderr)
    return results


def aggregate_test_data(results_dir: Path) -> dict:
    """Aggregate test data from all result files in directory.

    Returns a dict mapping test node IDs to their aggregated statistics.
    """
    # test_nodeid -> {runs: [], total_passed: int, total_failed: int, reruns: int}
    aggregated: dict = defaultdict(
        lambda: {"runs": [], "total_passed": 0, "total_failed": 0, "total_reruns": 0}
    )

    # Find all JSON/JSONL files
    result_files = list(results_dir.glob("**/*.json")) + list(results_dir.glob("**/*.jsonl"))

    if not result_files:
        print(f"Warning: No result files found in {results_dir}", file=sys.stderr)
        return {}

    for result_file in result_files:
        runs = parse_results_file(result_file)
        for run in runs:
            timestamp = run.get("timestamp", "")
            tests = run.get("tests", {})

            for nodeid, test_data in tests.items():
                agg = aggregated[nodeid]
                agg["runs"].append(
                    {
                        "timestamp": timestamp,
                        "passed": test_data.get("passed", 0),
                        "failed": test_data.get("failed", 0),
                        "reruns": test_data.get("reruns", 0),
                        "pass_rate": test_data.get("pass_rate", 1.0),
                    }
                )
                agg["total_passed"] += test_data.get("passed", 0)
                agg["total_failed"] += test_data.get("failed", 0)
                agg["total_reruns"] += test_data.get("reruns", 0)

    return dict(aggregated)


def calculate_flakiness_score(test_data: dict, config: dict) -> float:
    """Calculate a flakiness score for a test (0 = stable, 1 = very flaky).

    Factors:
    - Pass rate: Lower pass rate = more flaky
    - Reruns: Tests that needed reruns are likely flaky
    - Consistency: Tests that sometimes pass, sometimes fail are flaky
    """
    total_passed = test_data["total_passed"]
    total_failed = test_data["total_failed"]
    total_reruns = test_data["total_reruns"]
    total_runs = total_passed + total_failed

    if total_runs == 0:
        return 0.0

    # Base flakiness from pass rate (inverted - lower pass rate = higher score)
    pass_rate = total_passed / total_runs
    base_flakiness = 1.0 - pass_rate

    # Rerun penalty: tests that needed reruns but eventually passed are flaky
    rerun_penalty = 0.0
    if total_reruns > 0 and total_passed > 0:
        # Reruns that led to passes indicate flakiness
        rerun_penalty = min(total_reruns / total_runs, 1.0) * config["rerun_weight"]

    # Combine factors
    flakiness_score = min(base_flakiness + rerun_penalty, 1.0)

    return flakiness_score


def detect_flaky_tests(aggregated: dict, config: dict) -> list[dict]:
    """Identify tests that are flaky based on aggregated data.

    Returns a list of flaky test records sorted by flakiness score.
    """
    flaky_tests = []

    for nodeid, test_data in aggregated.items():
        total_runs = test_data["total_passed"] + test_data["total_failed"]

        # Skip tests with insufficient data
        if total_runs < config["min_runs"]:
            continue

        # Calculate pass rate
        pass_rate = test_data["total_passed"] / total_runs if total_runs > 0 else 1.0

        # Calculate flakiness score
        flakiness_score = calculate_flakiness_score(test_data, config)

        # Flag as flaky if pass rate is below threshold or has significant reruns
        is_flaky = pass_rate < config["flaky_threshold"] or (
            test_data["total_reruns"] > 0 and pass_rate < 1.0
        )

        if is_flaky:
            flaky_tests.append(
                {
                    "nodeid": nodeid,
                    "pass_rate": pass_rate,
                    "total_runs": total_runs,
                    "passed": test_data["total_passed"],
                    "failed": test_data["total_failed"],
                    "reruns": test_data["total_reruns"],
                    "flakiness_score": flakiness_score,
                    "run_count": len(test_data["runs"]),
                }
            )

    # Sort by flakiness score (most flaky first)
    flaky_tests.sort(key=lambda x: x["flakiness_score"], reverse=True)

    return flaky_tests


def load_allowlist_ids(path: Path, today: datetime | None = None) -> set[str]:
    """Return the active (unexpired) ids registered in the flake allowlist.

    Same 15-line flat-list parse as scripts/check-flake-allowlist.py and
    scripts/flake-k-filter.py — the zero-coupling convention those two share
    deliberately, so this analysis script runs anywhere (the nightly workflow
    invokes it with bare `python3`, before any dependency install).

    A registered id is a substring of the pytest nodeid, matching the -k
    semantics flake-k-filter.py ships, so `--allowlist-file` and the rerun
    wiring agree about which tests are covered.
    """
    if not path.is_file():
        return set()
    import re

    entry_re = re.compile(r"^\s*-\s+id:\s*(\S+)")
    field_re = re.compile(r"^\s+(tracking|expires):\s*(.+?)\s*$")
    entries: list[dict[str, str]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        m = entry_re.match(line)
        if m:
            entries.append({"id": m.group(1)})
            continue
        if entries:
            fm = field_re.match(line)
            if fm:
                entries[-1][fm.group(1)] = fm.group(2).strip("'\"")

    cutoff = (today or datetime.now(UTC)).date()
    active = set()
    for e in entries:
        try:
            if datetime.fromisoformat(e.get("expires", "")).date() < cutoff:
                continue
        except ValueError:
            continue
        active.add(e["id"])
    return active


def registered_ids(nodeids: list[str], allowlist_ids: set[str]) -> set[str]:
    """Map allowlist ids onto the nodeids they cover (substring = -k semantics)."""
    covered = set()
    for nodeid in nodeids:
        if any(flake_id in nodeid for flake_id in allowlist_ids):
            covered.add(nodeid)
    return covered


def load_allowlist_refs(path: Path, today: datetime | None = None) -> dict[str, str]:
    """id -> tracking ref for ACTIVE (unexpired) allowlist entries (WP1.5).

    Same parse as load_allowlist_ids (which returns only the id set); this
    keyed variant exists so the owner summary can name the owner of a
    registered flake instead of merely marking it handled.
    """
    if not path.is_file():
        return {}
    import re

    entry_re = re.compile(r"^\s*-\s+id:\s*(\S+)")
    field_re = re.compile(r"^\s+(tracking|expires):\s*(.+?)\s*$")
    entries: list[dict[str, str]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        m = entry_re.match(line)
        if m:
            entries.append({"id": m.group(1)})
            continue
        if entries:
            fm = field_re.match(line)
            if fm:
                entries[-1][fm.group(1)] = fm.group(2).strip("'\"")

    cutoff = (today or datetime.now(UTC)).date()
    refs: dict[str, str] = {}
    for e in entries:
        try:
            if datetime.fromisoformat(e.get("expires", "")).date() < cutoff:
                continue
        except ValueError:
            continue
        refs[e["id"]] = e.get("tracking", "(no tracking ref)")
    return refs


def owner_for(nodeid: str, refs: dict[str, str]) -> str:
    """Named owner line for one flaky nodeid (WP1.5 done-when: named owner).

    Registered -> its allowlist tracking ref. Unregistered -> the literal
    "no owner" — an unowned flake must be VISIBLE as unowned in the ranked
    table, not silently handled.
    """
    for flake_id, tracking in refs.items():
        if flake_id in nodeid:
            return tracking
    return "no owner (unregistered)"


def write_owner_summary(flaky_tests: list[dict], refs: dict[str, str], corpus_size: int) -> None:
    """Ranked flake table with an explicit Owner column (WP1.5)."""
    summary_file = os.environ.get("GITHUB_STEP_SUMMARY")
    if not summary_file:
        print(
            "Warning: --owner-summary needs GITHUB_STEP_SUMMARY (set by the Actions runner)",
            file=sys.stderr,
        )
        return

    # nosemgrep: path-traversal-open - runner-owned path, not user input
    with open(summary_file, "a") as f:
        f.write("## RANKED Flake Report (WP1.5 consumer)\n\n")
        f.write(
            "Source: the `flaky-test-tracking-*.jsonl` each CI shard writes and "
            "uploads — harvested from the newest previous main run of this "
            "workflow. `flake_allowlist: 0` means *nothing registered*, not "
            "*nothing flakes* — this table is the reading.\n\n"
        )
        # Corpus size printed even in the zero case: "no flakes" must be
        # distinguishable from "read nothing" (the WP0.5 vacuous-pass class).
        f.write(f"Corpus: **{corpus_size}** distinct test(s) read from the harvested window.\n\n")
        if not flaky_tests:
            f.write("No flaky tests detected in the harvested window.\n")
            return
        # detect_flaky_tests already sorts by flakiness score, descending.
        f.write(f"RANKED {len(flaky_tests)} flaky test(s), most flaky first:\n\n")
        f.write("| Rank | Test | Pass Rate | Runs (fail/total) | Score | Owner |\n")
        f.write("|------|------|-----------|-------------------|-------|-------|\n")
        for i, t in enumerate(flaky_tests[:50], 1):
            name = t["nodeid"]
            if len(name) > 70:
                name = "..." + name[-67:]
            owner = owner_for(t["nodeid"], refs)
            f.write(
                f"| {i} | `{name}` | {t['pass_rate'] * 100:.0f}% | "
                f"{t['failed']}/{t['total_runs']} | {t['flakiness_score']:.2f} | {owner} |\n"
            )
        unowned = sum(1 for t in flaky_tests if owner_for(t["nodeid"], refs).startswith("no owner"))
        f.write(
            f"\n**{unowned}/{len(flaky_tests)} flake(s) have no owner** — each needs a "
            "`.github/flake-allowlist.yml` entry (tracking ref + expiry) or a fix.\n"
        )


def print_console_report(flaky_tests: list[dict], config: dict, quarantined: set[str]) -> None:
    """Print a human-readable report to console."""
    print("=" * 70)
    print("FLAKY TEST ANALYSIS REPORT")
    print("=" * 70)
    print()
    print("Configuration:")
    print(f"  Flaky threshold: {config['flaky_threshold'] * 100:.0f}% pass rate")
    print(f"  Minimum runs: {config['min_runs']}")
    print(f"  Rerun weight: {config['rerun_weight']}")
    print()

    if not flaky_tests:
        print("No flaky tests detected.")
        print()
        return

    print(f"Detected {len(flaky_tests)} flaky test(s):")
    print("-" * 70)

    for test in flaky_tests:
        status = "[QUARANTINED]" if test["nodeid"] in quarantined else "[NEW]"
        print(f"\n{status} {test['nodeid']}")
        print(f"  Pass rate: {test['pass_rate'] * 100:.1f}%")
        print(f"  Flakiness score: {test['flakiness_score']:.2f}")
        print(
            f"  Runs: {test['total_runs']} total, {test['passed']} passed, {test['failed']} failed"
        )
        if test["reruns"] > 0:
            print(f"  Reruns: {test['reruns']} (passed after retry)")

    print()
    print("-" * 70)

    # Summary
    new_count = sum(1 for t in flaky_tests if t["nodeid"] not in quarantined)
    quarantined_count = len(flaky_tests) - new_count

    print(f"Summary: {new_count} new, {quarantined_count} already quarantined")


def write_github_summary(flaky_tests: list[dict], quarantined: set[str]) -> None:
    """Write GitHub Actions job summary if running in CI."""
    summary_file = os.environ.get("GITHUB_STEP_SUMMARY")
    if not summary_file:
        return

    # GITHUB_STEP_SUMMARY is set by the Actions runner to a per-job path, never
    # by user input (same idiom as coverage-analysis.py; surfaced now because
    # WP0.8 re-scanned this file)
    # nosemgrep: path-traversal-open - runner-owned path, not user input
    with open(summary_file, "a") as f:
        f.write("## Flaky Test Report\n\n")

        if not flaky_tests:
            f.write("No flaky tests detected.\n")
            return

        f.write(f"Detected **{len(flaky_tests)}** flaky test(s)\n\n")

        # Table header
        f.write("| Status | Test | Pass Rate | Flakiness | Runs |\n")
        f.write("|--------|------|-----------|-----------|------|\n")

        for test in flaky_tests[:20]:  # Limit to top 20
            status = "Quarantined" if test["nodeid"] in quarantined else "**NEW**"
            # Truncate long test names
            name = test["nodeid"]
            if len(name) > 60:
                name = "..." + name[-57:]
            f.write(
                f"| {status} | `{name}` | {test['pass_rate'] * 100:.0f}% | "
                f"{test['flakiness_score']:.2f} | {test['total_runs']} |\n"
            )

        if len(flaky_tests) > 20:
            f.write(f"\n*...and {len(flaky_tests) - 20} more*\n")

        # Add recommendations
        new_tests = [t for t in flaky_tests if t["nodeid"] not in quarantined]
        if new_tests:
            f.write("\n### Recommended Actions\n\n")
            f.write(
                "New flaky tests detected. Consider:\n"
                "1. Investigating the root cause of flakiness\n"
                "2. Registering the flake in `.github/flake-allowlist.yml` with a\n"
                "   Linear tracking ref and an expiry (the ONLY sanctioned\n"
                "   quarantine — a bare `@pytest.mark.flaky` without an entry\n"
                "   fails collection; see WP0.8)\n"
            )


def write_json_report(flaky_tests: list[dict], output_path: Path) -> None:
    """Write JSON report for programmatic consumption."""
    timestamp = datetime.now(UTC).isoformat()
    report = {
        "generated_at": timestamp,
        "total_flaky": len(flaky_tests),
        "tests": flaky_tests,
    }

    with output_path.open("w") as f:
        json.dump(report, f, indent=2)

    print(f"JSON report written to: {output_path}")


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Analyze test results to detect flaky tests")
    parser.add_argument("results_dir", type=Path, help="Directory containing test result files")
    parser.add_argument("--output", "-o", type=Path, help="Output JSON report file")
    parser.add_argument(
        "--allowlist-file",
        type=Path,
        default=Path(".github/flake-allowlist.yml"),
        help="Governed flake allowlist; registered (unexpired) ids are reported as handled",
    )
    parser.add_argument(
        "--owner-summary",
        action="store_true",
        help="WP1.5: also write a RANKED table with an explicit Owner column to "
        "GITHUB_STEP_SUMMARY (registered -> tracking ref, else 'no owner')",
    )

    args = parser.parse_args()

    if not args.results_dir.exists():
        print(f"Error: Directory not found: {args.results_dir}", file=sys.stderr)
        return 1

    config = get_config()

    # Aggregate test data from all result files
    aggregated = aggregate_test_data(args.results_dir)

    if not aggregated:
        print("No test data found to analyze.", file=sys.stderr)
        return 0

    # Detect flaky tests
    flaky_tests = detect_flaky_tests(aggregated, config)

    # "Handled" = registered in the governed allowlist (WP0.8): tracking ref
    # + expiry, reviewed by hand, enforced by check-flake-allowlist.py.
    allowlist_ids = load_allowlist_ids(args.allowlist_file)
    quarantined = registered_ids([t["nodeid"] for t in flaky_tests], allowlist_ids)

    # Print console report
    print_console_report(flaky_tests, config, quarantined)

    # Write GitHub summary if in CI
    write_github_summary(flaky_tests, quarantined)

    # WP1.5: ranked list with an explicit Owner column (registered -> allowlist
    # tracking ref, unregistered -> the literal "no owner").
    if args.owner_summary:
        write_owner_summary(flaky_tests, load_allowlist_refs(args.allowlist_file), len(aggregated))

    # Write JSON report if requested
    if args.output:
        write_json_report(flaky_tests, args.output)

    # Return non-zero if new (unregistered) flaky tests detected
    new_flaky = [t for t in flaky_tests if t["nodeid"] not in quarantined]
    if new_flaky:
        print(f"\nWARNING: {len(new_flaky)} new flaky test(s) detected")
        # Return 0 to not fail CI - this is informational only
        return 0

    return 0


if __name__ == "__main__":
    sys.exit(main())
