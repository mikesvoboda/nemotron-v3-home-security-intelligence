#!/usr/bin/env python3
"""PR gate script to enforce test requirements for new code.

This script is run during CI to verify:
1. New backend files have corresponding test files
2. Coverage diff does not decrease
3. API route changes require integration tests
4. New components/services have unit tests

Usage:
    ./scripts/check-test-coverage-gate.py [--base-branch main]
"""

import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

# Test requirement thresholds
REQUIREMENTS = {
    "backend/api/routes/*.py": {
        "type": "API Route",
        "required_tests": ["integration", "unit"],
        "min_coverage": 85,
    },
    "backend/services/*.py": {
        "type": "Service",
        "required_tests": ["unit", "integration"],
        "min_coverage": 85,
    },
    "backend/models/*.py": {
        "type": "ORM Model",
        "required_tests": ["unit"],
        "min_coverage": 85,
    },
    "frontend/src/components/*.tsx": {
        "type": "Component",
        "required_tests": ["unit"],
        "min_coverage": 80,
    },
    "frontend/src/hooks/*.ts": {
        "type": "Hook",
        "required_tests": ["unit"],
        "min_coverage": 80,
    },
}


@dataclass
class FileChange:
    """Represents a changed file in the PR."""

    path: str
    status: str  # "added", "modified", "deleted"
    additions: int
    deletions: int


@dataclass
class TestRequirement:
    """Represents a test requirement for a file."""

    file_path: str
    file_type: str
    required_tests: list[str]
    min_coverage: int
    has_tests: bool
    test_files: list[str]


def _numstat_new_path(p: str) -> str:
    """Resolve numstat's path column to the file's NEW name.

    Rename detection renders paths as `old => new` or `dir/{old => new}.py`;
    the requirement checks care about the new path.
    """
    if " => " in p:
        if "{" in p and "}" in p:
            pre, rest = p.split("{", 1)
            mid, post = rest.split("}", 1)
            _old, new_part = mid.split(" => ", 1)
            return pre + new_part + post
        return p.split(" => ", 1)[1]
    return p


def get_changed_files(base_branch: str = "origin/main") -> list[FileChange]:
    """Get list of changed files in the PR.

    Returns:
        List of FileChange objects
    """
    try:
        # Get merge base for comparison
        merge_base = subprocess.check_output(
            ["git", "merge-base", base_branch, "HEAD"],
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()

        # PRE-EXISTING parser bug fixed: git does NOT combine --name-status
        # with --numstat — name-status wins and lines come out `M\tpath`
        # (2 fields), which the old 3-field parser dropped wholesale: every
        # diff read as zero changes. Run the two formats separately and join
        # on the new path (WP0.1's first full-tree pre-push surfaced this).
        status_output = subprocess.check_output(
            ["git", "diff", "--name-status", f"{merge_base}...HEAD"],
            text=True,
        )
        numstat_output = subprocess.check_output(
            ["git", "diff", "--numstat", f"{merge_base}...HEAD"],
            text=True,
        )
    except subprocess.CalledProcessError as e:
        print(f"Error getting changed files: {e}", file=sys.stderr)
        return []

    counts: dict[str, tuple[int, int]] = {}
    for line in numstat_output.strip().split("\n"):
        if not line:
            continue
        parts = line.split("\t")
        if len(parts) < 3:
            continue
        # Binary files report "-" instead of counts.
        additions = int(parts[0]) if parts[0].isdigit() else 0
        deletions = int(parts[1]) if parts[1].isdigit() else 0
        counts[_numstat_new_path(parts[2])] = (additions, deletions)

    status_map = {
        "A": "added",
        "M": "modified",
        "D": "deleted",
        "R": "renamed",
        "C": "copied",
    }
    changes = []
    for line in status_output.strip().split("\n"):
        if not line:
            continue
        parts = line.split("\t")
        code = parts[0][0]
        status = status_map.get(code, "modified")
        # R/C lines carry old AND new path; the new path is the last field.
        path = parts[-1]
        additions, deletions = counts.get(path, (0, 0))
        changes.append(FileChange(path, status, additions, deletions))

    return changes


def find_test_file(source_file: str) -> str | None:
    """Find the corresponding test file for a source file.

    Args:
        source_file: Path to source file (e.g., backend/api/routes/cameras.py)

    Returns:
        Path to test file if found, None otherwise
    """
    project_root = Path(__file__).parent.parent
    source_path = project_root / source_file

    if not source_path.exists():
        return None

    # Determine test directory based on source location
    if source_file.startswith("backend/"):
        # For backend files, look in backend/tests/unit and backend/tests/integration
        relative_path = source_file[len("backend/") :]
        test_unit = project_root / f"backend/tests/unit/{relative_path}"
        test_integration = project_root / f"backend/tests/integration/{relative_path}"

        # Replace .py with _test.py or test_.py
        test_unit_alt = test_unit.with_name(f"test_{test_unit.name}")
        test_integration_alt = test_integration.with_name(f"test_{test_integration.name}")

        for test_path in [test_unit, test_unit_alt, test_integration, test_integration_alt]:
            if test_path.exists():
                return str(test_path.relative_to(project_root))

    elif source_file.startswith("frontend/src/"):
        # For frontend files, look in same directory with .test.ts/tsx
        source_path_obj = Path(source_file)
        test_path = source_path_obj.with_name(
            source_path_obj.stem + ".test" + "".join(source_path_obj.suffixes)
        )

        if (project_root / test_path).exists():
            return str(test_path)

    return None


_TEST_FILE_MARKER = re.compile(
    r"(^|/)(test_[^/]+|[^/]+[._](test|spec)\.(tsx?|jsx?))$|(^|/)(tests?|__tests__)/"
)


def _is_test_file(path: str) -> bool:
    """Whether a path IS a test (test files carry no test requirement).

    WP0.6 CI truth: once get_changed_files actually parsed, the gate flagged
    the very test files it had demanded — a *.test.ts under frontend/src/
    hooks/ matches the Hook requirement, and find_test_file has nothing to
    resolve for it. The gate then fails a PR for OBEYING it. Test sources
    are exempt by kind, the same way deleted files are.
    """
    return bool(_TEST_FILE_MARKER.search(path))


def check_file_requirements(file_change: FileChange) -> TestRequirement | None:
    """Check if a changed file has test requirements.

    Args:
        file_change: The changed file

    Returns:
        TestRequirement object if file has requirements, None otherwise
    """
    file_path = file_change.path

    # Only check added/modified files with substantial changes
    if file_change.status == "deleted" or (file_change.additions + file_change.deletions) < 5:
        return None

    if _is_test_file(file_path):
        return None

    # Match against requirement patterns
    for pattern, requirement_spec in REQUIREMENTS.items():
        # Simple glob matching
        pattern_parts = pattern.split("/")
        file_parts = file_path.split("/")

        if len(file_parts) >= len(pattern_parts):
            matches = True
            for i, pattern_part in enumerate(pattern_parts):
                if pattern_part == "*":
                    continue
                if pattern_part.startswith("*."):
                    # Extension match
                    if not file_parts[i].endswith(pattern_part[1:]):
                        matches = False
                        break
                elif pattern_part != file_parts[i]:
                    matches = False
                    break

            if matches:
                # Find test file
                test_files = []
                test_file = find_test_file(file_path)
                if test_file:
                    test_files = [test_file]

                return TestRequirement(
                    file_path=file_path,
                    file_type=requirement_spec["type"],
                    required_tests=requirement_spec["required_tests"],
                    min_coverage=requirement_spec["min_coverage"],
                    has_tests=bool(test_files),
                    test_files=test_files,
                )

    return None


BASELINE_FILENAME = "coverage-baseline.json"

# Exception tuples, not parenthesized except clauses: this file is invoked as
# BARE python3 by test-coverage-gate.yml (runner interpreter, 3.12-era), and
# ruff format at target py314 STRIPS `except (A, B):` parens back to the
# PEP-758 bare form — which is a SyntaxError below 3.14 (PR #6549's first
# real gate run died exactly there). A tuple reference parses on every
# Python and the formatter never touches it.
_READ_ERRORS = (OSError, ValueError)
_GIT_ERRORS = (subprocess.CalledProcessError, OSError)


def _read_percent(path: Path) -> float | None:
    """Read a coverage percentage from a coverage.json report or a baseline file.

    Accepts both shapes: coverage's own report nests the number under
    "totals" ({"totals": {"percent_covered": ...}}) while a committed baseline
    file is the flat {"percent_covered": ...} it was written from. Returns None
    for absent/unparseable input so the caller can apply skip semantics.
    """
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text())
    except _READ_ERRORS:
        return None
    if not isinstance(data, dict):
        return None
    if isinstance(data.get("totals"), dict):
        value = data["totals"].get("percent_covered")
    else:
        value = data.get("percent_covered")
    return float(value) if isinstance(value, (int, float)) else None


def _current_via_seam() -> tuple[bool, float | None]:
    """(seam_present, percent) for the working tree.

    Seam = COVERAGE_JSON env (explicit, e.g. CI that collected coverage in an
    earlier step) or ./coverage.json. A SET-but-UNREADABLE seam is an honest
    "no data" answer — skip, never collect over the top of a caller's explicit
    choice. Only when NO seam exists (classic CI invocation: the gate job
    collects inline) does the caller fall through to collection.
    """
    env_path = os.environ.get("COVERAGE_JSON")
    if env_path:
        return True, _read_percent(Path(env_path))
    path = Path("coverage.json")
    if path.is_file():
        return True, _read_percent(path)
    return False, None


def _base_percent_from_git(base_branch: str) -> tuple[float | None, str]:
    """Base coverage from the baseline file committed at the base ref.

    Returns (percent, note). This is the mechanism that makes the gate work in
    CI without running the suite twice: `main` publishes
    coverage-baseline.json, so the PR side only needs its own number.
    """
    try:
        raw = subprocess.check_output(
            ["git", "show", f"{base_branch}:{BASELINE_FILENAME}"],
            text=True,
            stderr=subprocess.DEVNULL,
        )
    except _GIT_ERRORS:
        return None, f"no {BASELINE_FILENAME} at {base_branch}"
    try:
        data = json.loads(raw)
    except ValueError:
        return None, f"{BASELINE_FILENAME} at {base_branch} is not valid JSON"
    value = data.get("percent_covered") if isinstance(data, dict) else None
    if not isinstance(value, (int, float)):
        return None, f"{BASELINE_FILENAME} at {base_branch} has no percent_covered"
    return float(value), f"baseline from {base_branch}:{BASELINE_FILENAME}"


def check_coverage_diff(
    base_branch: str = "origin/main",
    current_percent: float | None = None,
    base_percent: float | None = None,
) -> tuple[bool, str]:
    """Fail when coverage has DROPPED relative to the base branch.

    The name is now the contract. Pre-WP0.9 this ran the suite and reported
    `True, "Current coverage: X%"` for every input, so no drop could ever be
    detected — the spec's "misleading name is the actual defect".

    Resolution order, base side first: explicit `base_percent`, then
    COVERAGE_BASE_JSON, then `git show <base_branch>:coverage-baseline.json`.
    An unresolvable base skips BEFORE any collection — the old order ran the
    full suite and only then discovered there was nothing to diff against.
    Current side: explicit `current_percent`, then the coverage.json seam
    (COVERAGE_JSON env, else ./coverage.json), then a full suite run that
    generates the report (the classic no-seam call, where the gate collects
    inline; never vacuous in production).

    Skip semantics are genuine, not vacuous: an explicit seam that points at
    nothing (coverage never collected) or an unpublished baseline skips with a
    message saying so. What it can never do again is see both numbers
    and still pass a drop.

    Returns:
        Tuple of (passed, message)
    """
    if base_percent is None:
        env_base = os.environ.get("COVERAGE_BASE_JSON")
        if env_base:
            base_percent = _read_percent(Path(env_base))
            base_note = f"base from COVERAGE_BASE_JSON={env_base}"
        else:
            base_percent, base_note = _base_percent_from_git(base_branch)
    else:
        base_note = "explicit base"

    if base_percent is None:
        # Skip BEFORE collecting: no baseline exists to diff against, so the
        # 90s+ suite run would buy nothing (the first full-tree pre-push
        # proved it — collection ran, then the diff skipped for want of a base).
        return True, f"No base coverage available ({base_note}), skipping diff"

    if current_percent is None:
        seam, seam_percent = _current_via_seam()
        if seam:
            if seam_percent is None:
                return True, "Coverage seam present but unreadable/empty, skipping coverage diff"
            current_percent = seam_percent
        else:
            # Nothing collected yet (classic invocation): collect once inline,
            # anchored at the repo root like the pre-WP0.9 code (the script may
            # be invoked from any directory). --cov-fail-under=0 because this
            # call EXISTS to extract the number: pytest-cov would otherwise
            # apply pyproject's fail_under=85 to the run, and unit-tier-only
            # coverage (84.12% blended measured 2026-09-20 at HEAD; the 84.39
            # lineage in the ledger is the same path) would exit 1 and fail the
            # gate for the wrong reason — collection, not diff (same
            # extraction-not-floor rationale as the ci.yml shard jobs).
            project_root = Path(__file__).resolve().parent.parent
            try:
                proc = subprocess.run(
                    [
                        "uv",
                        "run",
                        "pytest",
                        "backend/tests/unit/",
                        "--cov=backend",
                        "--cov-report=json",
                        "--cov-fail-under=0",
                        # Rerun parity with the shard jobs (ci.yml:675,797).
                        # This inline collection under -n 8 load was the only
                        # full-tier invocation WITHOUT the repo's rerun
                        # convention, and it reddened the REQUIRED gate three
                        # times on one branch with a DIFFERENT pytest-timeout
                        # flake each time (all green locally + in shards).
                        # Extraction is not enforcement: --cov-fail-under=0
                        # above stays, so retries move no floor. Pinned by
                        # backend/tests/unit/scripts/test_check_test_coverage_gate.py
                        "--reruns",
                        "2",
                        "--reruns-delay",
                        "5",
                        "-q",
                    ],
                    cwd=project_root,
                    check=True,
                    capture_output=True,
                    text=True,
                )
            except subprocess.CalledProcessError as e:
                # pytest writes findings to stdout; reporting only stderr gave
                # a useless empty "collection failed:" detail on the first
                # real occurrence. Report whichever side has content.
                detail = ((e.stderr or "") + "\n" + (e.stdout or "")).strip()[-300:]
                return False, f"Coverage collection failed (rc={e.returncode}): {detail}"
            except OSError as e:
                return False, f"Coverage collection failed to launch: {e}"
            current_percent = _read_percent(project_root / "coverage.json")
            if current_percent is None:
                return True, "No coverage data collected, skipping coverage diff check"

    if current_percent < base_percent:
        return (
            False,
            f"Coverage DROPPED {base_percent:.1f}% -> {current_percent:.1f}% "
            f"(-{base_percent - current_percent:.1f}pp; {base_note})",
        )

    return (
        True,
        f"Coverage {current_percent:.1f}% vs base {base_percent:.1f}% (+{current_percent - base_percent:.1f}pp)",
    )


def main() -> int:
    """Main entry point.

    Returns:
        0 on success, 1 on failure
    """
    import argparse

    parser = argparse.ArgumentParser(description="PR gate for test coverage enforcement")
    parser.add_argument(
        "--base-branch",
        default="origin/main",
        help="Base branch to compare against (default: origin/main)",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Fail on any missing tests (default: warning only)",
    )
    args = parser.parse_args()

    print("Checking test coverage requirements...\n")

    # Get changed files. An empty change list must NOT short-circuit the
    # coverage diff below — that early return was a second vacuous exit: a
    # shallow checkout or an unresolvable base ref yields no changes and would
    # have skipped the drop check entirely (same bug family WP0.7 catalogued).
    changes = get_changed_files(args.base_branch)
    if not changes:
        print("No changed files detected (requirement checks skipped)")

    # Check requirements for each file
    requirements = []
    for change in changes:
        req = check_file_requirements(change)
        if req:
            requirements.append(req)

    # Report findings
    if requirements:
        print("Files with test requirements:\n")
        failed = False

        for req in requirements:
            status = "✓ HAS TESTS" if req.has_tests else "✗ MISSING TESTS"
            print(f"  {status}: {req.file_path}")
            print(f"    Type: {req.file_type}")
            print(f"    Required: {', '.join(req.required_tests)}")
            print(f"    Min Coverage: {req.min_coverage}%")

            if req.test_files:
                print(f"    Tests: {', '.join(req.test_files)}")
            else:
                print("    Tests: None found")
                if args.strict or req.file_type == "API Route":
                    failed = True

            print()

        if failed and args.strict:
            print("\nERROR: Some files have missing test requirements")
            print("Add tests or update REQUIREMENTS in check-test-coverage-gate.py")
            return 1

    # Check coverage diff
    coverage_passed, coverage_msg = check_coverage_diff(args.base_branch)
    print(f"Coverage check: {coverage_msg}")

    if not coverage_passed:
        print("\nERROR: Coverage validation failed")
        return 1

    print("\nAll test coverage checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
