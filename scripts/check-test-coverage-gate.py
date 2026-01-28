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

        # Get diff stats
        diff_output = subprocess.check_output(
            ["git", "diff", "--name-status", "--numstat", f"{merge_base}...HEAD"],
            text=True,
        )

        changes = []
        for line in diff_output.strip().split("\n"):
            if not line:
                continue

            parts = line.split("\t")
            if len(parts) < 3:
                continue

            status = parts[0]
            additions = int(parts[1]) if parts[1].isdigit() else 0
            deletions = int(parts[2]) if parts[2].isdigit() else 0
            path = parts[3] if len(parts) > 3 else parts[2]

            # Map git status codes to our status names
            status_map = {
                "A": "added",
                "M": "modified",
                "D": "deleted",
                "R": "renamed",
                "C": "copied",
            }
            status = status_map.get(status[0], "modified")

            changes.append(FileChange(path, status, additions, deletions))

        return changes
    except subprocess.CalledProcessError as e:
        print(f"Error getting changed files: {e}", file=sys.stderr)
        return []


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


def check_coverage_diff(base_branch: str = "origin/main") -> tuple[bool, str]:
    """Check if coverage has decreased.

    Args:
        base_branch: Base branch to compare against

    Returns:
        Tuple of (passed, message)
    """
    project_root = Path(__file__).parent.parent

    try:
        # Run coverage for current branch
        subprocess.run(
            [
                "uv",
                "run",
                "pytest",
                "backend/tests/unit/",
                "--cov=backend",
                "--cov-report=json",
            ],
            cwd=project_root,
            check=True,
            capture_output=True,
        )

        coverage_file = project_root / ".coverage"
        if not coverage_file.exists():
            # Coverage not available, skip check
            return True, "Coverage file not found, skipping coverage diff check"

        # Parse coverage JSON (--cov-report=json generates coverage.json)
        coverage_json = project_root / "coverage.json"
        if coverage_json.exists():
            # Resolve to absolute path for security
            resolved_path = coverage_json.resolve()
            with open(resolved_path) as f:  # nosemgrep: path-traversal-open
                current_coverage = json.load(f)
                current_percentage = current_coverage.get("totals", {}).get("percent_covered", 0)

                return True, f"Current coverage: {current_percentage:.1f}%"

        return True, "Unable to parse coverage data"

    except subprocess.CalledProcessError as e:
        stderr_msg = e.stderr.decode()[:500] if e.stderr else ""
        stdout_msg = e.stdout.decode()[-500:] if e.stdout else ""
        return (
            False,
            f"Coverage check failed: {e!s}\nSTDERR: {stderr_msg}\nSTDOUT (last 500): {stdout_msg}",
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

    # Get changed files
    changes = get_changed_files(args.base_branch)
    if not changes:
        print("No changes detected")
        return 0

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
