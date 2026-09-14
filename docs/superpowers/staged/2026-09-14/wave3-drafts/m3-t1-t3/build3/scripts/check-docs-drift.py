#!/usr/bin/env python3
"""Documentation drift detection script.

Analyzes git changes and identifies documentation that may need updating.
Outputs structured JSON for Linear task creation.

Usage:
    uv run python scripts/check-docs-drift.py --output drift-report.json
    uv run python scripts/check-docs-drift.py --base main --head HEAD
    uv run python scripts/check-docs-drift.py --base origin/main --head feature-branch

Exit codes:
    0 - Success (drift items found or not)
    1 - Error (invalid arguments, missing files, etc.)

Output:
    Structured JSON report containing:
    - Detected drift items with priority, source files, and suggestions
    - Summary counts by priority level
    - Metadata about the analysis (timestamps, refs)
"""

from __future__ import annotations

import argparse
import fnmatch
import json
import re
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


@dataclass
class DriftRule:
    """Configuration for a documentation drift detection rule."""

    id: str
    description: str
    file_patterns: list[str]
    priority: str
    required_docs: list[str]
    content_patterns: list[str] = field(default_factory=list)
    new_file_only: bool = False


@dataclass
class DriftItem:
    """A detected documentation drift item."""

    rule_id: str
    priority: str
    source_file: str
    change_type: str  # "new_file" or "modified"
    description: str
    diff_excerpt: str
    missing_docs: list[str]
    outdated_docs: list[str]
    suggested_updates: list[str]
    line_range: tuple[int, int] | None = None


def get_project_root() -> Path:
    """Find project root by looking for pyproject.toml."""
    current = Path(__file__).resolve().parent.parent
    while current != current.parent:
        if (current / "pyproject.toml").exists():
            return current
        current = current.parent
    # Fallback to script's parent's parent
    return Path(__file__).resolve().parent.parent


def load_rules(rules_path: Path) -> tuple[list[DriftRule], list[str]]:
    """Load drift detection rules from YAML configuration.

    Args:
        rules_path: Path to the YAML rules file

    Returns:
        Tuple of (list of DriftRule objects, list of ignore patterns)

    Raises:
        FileNotFoundError: If rules file doesn't exist
        ValueError: If rules file is invalid
    """
    try:
        # Use PyYAML if available, otherwise use a simple parser
        try:
            import yaml

            # nosemgrep: path-traversal-open - rules_path is from CLI arg, validated by Path existence check
            with open(rules_path) as f:
                config = yaml.safe_load(f)
        except ImportError:
            # Fallback to simple YAML parsing for basic structures
            config = _parse_simple_yaml(rules_path)

        if not config:
            raise ValueError("Empty rules configuration")

        rules_data = config.get("rules", [])
        ignore_patterns = config.get("ignore_patterns", [])

        rules = []
        for rule_data in rules_data:
            rules.append(
                DriftRule(
                    id=rule_data["id"],
                    description=rule_data["description"],
                    file_patterns=rule_data["file_patterns"],
                    priority=rule_data["priority"],
                    required_docs=rule_data["required_docs"],
                    content_patterns=rule_data.get("content_patterns", []),
                    new_file_only=rule_data.get("new_file_only", False),
                )
            )

        return rules, ignore_patterns

    except FileNotFoundError as err:
        raise FileNotFoundError(f"Rules file not found: {rules_path}") from err
    except (KeyError, TypeError) as e:
        raise ValueError(f"Invalid rules configuration: {e}") from e


def _parse_simple_yaml(path: Path) -> dict[str, Any]:
    """Simple YAML parser for basic structures (fallback when PyYAML not available).

    Handles:
    - Top-level keys with list values
    - Nested dictionaries in lists
    - Simple string values

    Args:
        path: Path to YAML file

    Returns:
        Parsed configuration dictionary
    """
    result: dict[str, Any] = {}
    current_key: str | None = None
    current_list: list[Any] = []
    current_dict: dict[str, Any] = {}
    in_list = False
    in_dict = False
    indent_level = 0

    # nosemgrep: path-traversal-open - path is from internal config, not user input
    with open(path) as f:
        for line in f:
            # Skip comments and empty lines
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue

            # Calculate indent
            line_indent = len(line) - len(line.lstrip())

            # Top-level key
            if line_indent == 0 and ":" in stripped:
                # Save previous key's data
                if current_key:
                    if in_dict and current_dict:
                        current_list.append(current_dict)
                    if current_list:
                        result[current_key] = current_list

                key, _value = stripped.split(":", 1)
                current_key = key.strip()
                current_list = []
                current_dict = {}
                in_list = False
                in_dict = False
                indent_level = 0
                continue

            # List item
            if stripped.startswith("- "):
                # If we were building a dict, save it
                if in_dict and current_dict:
                    current_list.append(current_dict)
                    current_dict = {}

                content = stripped[2:].strip()
                if ":" in content:
                    # Dict item in list
                    in_dict = True
                    current_dict = {}
                    k, v = content.split(":", 1)
                    v = v.strip().strip("\"'")
                    current_dict[k.strip()] = _parse_yaml_value(v)
                else:
                    # Simple list item
                    in_list = True
                    in_dict = False
                    current_list.append(content.strip("\"'"))
                indent_level = line_indent
                continue

            # Nested key-value in dict
            if in_dict and ":" in stripped and line_indent > indent_level:
                k, v = stripped.split(":", 1)
                k = k.strip()
                v = v.strip()

                # Check if value is a list indicator
                if not v:
                    # Next lines are list items
                    current_dict[k] = []
                else:
                    current_dict[k] = _parse_yaml_value(v.strip("\"'"))
                continue

            # List item within nested structure
            if in_dict and stripped.startswith("- ") and line_indent > indent_level:
                content = stripped[2:].strip().strip("\"'")
                # Find the last key that was a list
                for k in reversed(list(current_dict.keys())):
                    if isinstance(current_dict[k], list):
                        current_dict[k].append(content)
                        break
                continue

    # Save final data
    if current_key:
        if in_dict and current_dict:
            current_list.append(current_dict)
        if current_list:
            result[current_key] = current_list

    return result


def _parse_yaml_value(value: str) -> Any:
    """Parse a YAML value string to appropriate Python type."""
    if value.lower() == "true":
        return True
    if value.lower() == "false":
        return False
    if value.isdigit():
        return int(value)
    return value


def get_changed_files(base_ref: str, head_ref: str, project_root: Path) -> dict[str, str]:
    """Get changed files between two git refs.

    Args:
        base_ref: Base git reference (e.g., "main", "origin/main")
        head_ref: Head git reference (e.g., "HEAD", commit SHA)
        project_root: Root directory of the git repository

    Returns:
        Dictionary mapping file paths to their diff content
    """
    changed_files: dict[str, str] = {}

    try:
        # Get list of changed files
        result = subprocess.run(
            ["git", "diff", "--name-only", f"{base_ref}...{head_ref}"],
            cwd=project_root,
            capture_output=True,
            text=True,
            check=True,
        )

        file_list = [f.strip() for f in result.stdout.strip().split("\n") if f.strip()]

        # Get diff content for each file
        for file_path in file_list:
            try:
                diff_result = subprocess.run(
                    ["git", "diff", f"{base_ref}...{head_ref}", "--", file_path],
                    cwd=project_root,
                    capture_output=True,
                    text=True,
                    check=True,
                )
                changed_files[file_path] = diff_result.stdout
            except subprocess.CalledProcessError:
                # File might have been deleted or renamed
                changed_files[file_path] = ""

    except subprocess.CalledProcessError as e:
        print(f"Error running git diff: {e.stderr}", file=sys.stderr)
        raise RuntimeError(f"Failed to get git diff: {e.stderr}") from e

    return changed_files


def is_new_file(file_path: str, base_ref: str, project_root: Path) -> bool:
    """Check if a file is new (doesn't exist in base ref).

    Args:
        file_path: Path to the file relative to project root
        base_ref: Base git reference
        project_root: Root directory of the git repository

    Returns:
        True if the file is new, False otherwise
    """
    try:
        result = subprocess.run(
            ["git", "cat-file", "-e", f"{base_ref}:{file_path}"],
            cwd=project_root,
            capture_output=True,
            check=False,
        )
        return result.returncode != 0
    except subprocess.CalledProcessError:
        return True


def matches_file_pattern(file_path: str, patterns: list[str]) -> bool:
    """Check if a file path matches any of the given glob patterns.

    Args:
        file_path: File path to check
        patterns: List of glob patterns

    Returns:
        True if the file matches any pattern
    """
    for pattern in patterns:
        # Convert glob pattern to regex-compatible pattern
        if fnmatch.fnmatch(file_path, pattern):
            return True
        # Handle ** for recursive matching
        if "**" in pattern:
            # Replace ** with a more flexible pattern
            regex_pattern = pattern.replace("**", "*")
            if fnmatch.fnmatch(file_path, regex_pattern):
                return True
            # Also try without the ** for direct matches
            parts = pattern.split("**")
            if len(parts) == 2:
                prefix, suffix = parts
                if file_path.startswith(prefix.rstrip("/")) and file_path.endswith(
                    suffix.lstrip("/")
                ):
                    return True
    return False


def should_ignore_file(file_path: str, ignore_patterns: list[str]) -> bool:
    """Check if a file should be ignored based on ignore patterns.

    Args:
        file_path: File path to check
        ignore_patterns: List of glob patterns to ignore

    Returns:
        True if the file should be ignored
    """
    return matches_file_pattern(file_path, ignore_patterns)


def has_pattern_match(diff_content: str, patterns: list[str]) -> bool:
    """Check if diff content contains any of the given regex patterns.

    Args:
        diff_content: Git diff content
        patterns: List of regex patterns

    Returns:
        True if any pattern matches
    """
    if not patterns:
        return True  # No patterns means always match

    # Extract only added lines from diff
    added_lines = []
    for line in diff_content.split("\n"):
        if line.startswith("+") and not line.startswith("+++"):
            added_lines.append(line[1:])  # Remove the + prefix

    combined_content = "\n".join(added_lines)

    for pattern in patterns:
        try:
            if re.search(pattern, combined_content, re.MULTILINE):
                return True
        except re.error:
            # Invalid regex, skip
            continue

    return False


def find_missing_docs(required_docs: list[str], source_file: str, project_root: Path) -> list[str]:
    """Find documentation files that don't exist.

    Args:
        required_docs: List of required doc patterns
        source_file: Source file path for template substitution
        project_root: Project root directory

    Returns:
        List of missing documentation file paths
    """
    missing: list[str] = []
    source_path = Path(source_file)

    for doc_pattern in required_docs:
        # Substitute template variables
        doc_path = doc_pattern.replace("{dir}", str(source_path.parent))
        doc_path = doc_path.replace("{file}", source_path.stem)

        # Handle glob patterns
        if "*" in doc_path:
            # Check if any file matching the pattern exists
            matches = list(project_root.glob(doc_path))
            if not matches:
                missing.append(doc_pattern)
        else:
            # Check exact path
            full_path = project_root / doc_path
            if not full_path.exists():
                missing.append(doc_path)

    return missing


def find_outdated_docs(required_docs: list[str], source_file: str, project_root: Path) -> list[str]:
    """Find documentation files that exist but may be outdated.

    Currently returns docs that exist - actual staleness detection would
    require content analysis.

    Args:
        required_docs: List of required doc patterns
        source_file: Source file path for template substitution
        project_root: Project root directory

    Returns:
        List of potentially outdated documentation file paths
    """
    potentially_outdated: list[str] = []
    source_path = Path(source_file)

    for doc_pattern in required_docs:
        # Substitute template variables
        doc_path = doc_pattern.replace("{dir}", str(source_path.parent))
        doc_path = doc_path.replace("{file}", source_path.stem)

        # Handle glob patterns
        if "*" in doc_path:
            matches = list(project_root.glob(doc_path))
            for match in matches:
                potentially_outdated.append(str(match.relative_to(project_root)))
        else:
            full_path = project_root / doc_path
            if full_path.exists():
                potentially_outdated.append(doc_path)

    return potentially_outdated


def create_drift_item(
    rule: DriftRule,
    file_path: str,
    diff_content: str,
    change_type: str,
    project_root: Path,
) -> DriftItem:
    """Create a drift item from a rule match.

    Args:
        rule: The matched drift rule
        file_path: Path to the changed file
        diff_content: Git diff content
        change_type: "new_file" or "modified"
        project_root: Project root directory

    Returns:
        DriftItem with all relevant information
    """
    # Create description
    description = f"{rule.description}: {file_path}"

    # Extract a relevant excerpt from the diff (max 500 chars)
    excerpt_lines = []
    for line in diff_content.split("\n"):
        if line.startswith("+") and not line.startswith("+++"):
            excerpt_lines.append(line)
        if len("\n".join(excerpt_lines)) > 500:
            break
    diff_excerpt = "\n".join(excerpt_lines[:10])
    if len(excerpt_lines) > 10:
        diff_excerpt += "\n... (truncated)"

    # Find missing and outdated docs
    missing_docs = find_missing_docs(rule.required_docs, file_path, project_root)
    outdated_docs = find_outdated_docs(rule.required_docs, file_path, project_root)

    # Generate suggestions
    suggestions = []
    if missing_docs:
        for doc in missing_docs:
            suggestions.append(f"Create documentation: {doc}")
    if outdated_docs:
        for doc in outdated_docs:
            suggestions.append(f"Update documentation: {doc}")

    return DriftItem(
        rule_id=rule.id,
        priority=rule.priority,
        source_file=file_path,
        change_type=change_type,
        description=description,
        diff_excerpt=diff_excerpt,
        missing_docs=missing_docs,
        outdated_docs=outdated_docs,
        suggested_updates=suggestions,
    )


def detect_drift(
    base_ref: str,
    head_ref: str,
    rules: list[DriftRule],
    ignore_patterns: list[str],
    project_root: Path,
) -> list[DriftItem]:
    """Analyze git diff and detect documentation drift.

    Args:
        base_ref: Base git reference
        head_ref: Head git reference
        rules: List of drift detection rules
        ignore_patterns: List of file patterns to ignore
        project_root: Project root directory

    Returns:
        List of detected drift items
    """
    # Get changed files
    changed_files = get_changed_files(base_ref, head_ref, project_root)

    # Categorize changes by drift rules
    drift_items: list[DriftItem] = []

    for file_path, diff_content in changed_files.items():
        # Skip ignored files
        if should_ignore_file(file_path, ignore_patterns):
            continue

        for rule in rules:
            if matches_file_pattern(file_path, rule.file_patterns):
                is_new = is_new_file(file_path, base_ref, project_root)

                # Check if rule applies
                if rule.new_file_only and not is_new:
                    continue

                if is_new:
                    # New file - definitely needs docs
                    drift_items.append(
                        create_drift_item(rule, file_path, diff_content, "new_file", project_root)
                    )
                elif has_pattern_match(diff_content, rule.content_patterns):
                    # Existing file with significant changes
                    drift_items.append(
                        create_drift_item(rule, file_path, diff_content, "modified", project_root)
                    )

    return drift_items


def group_related_drift(items: list[DriftItem]) -> list[DriftItem]:
    """Group drift items that should be one task.

    Items are grouped if they have the same required documentation.

    Args:
        items: List of drift items to group

    Returns:
        Grouped drift items (potentially merged)
    """
    if not items:
        return []

    # Group by target documentation files
    groups: dict[tuple[str, ...], list[DriftItem]] = {}
    for item in items:
        key = tuple(sorted(item.missing_docs + item.outdated_docs))
        if not key:
            # No docs to update - keep item separate
            key = (item.source_file,)
        if key not in groups:
            groups[key] = []
        groups[key].append(item)

    # For now, return ungrouped items (grouping can be added later)
    # This keeps the report more detailed
    return items


def generate_report(
    drift_items: list[DriftItem],
    base_ref: str,
    head_ref: str,
    pr_number: int | None = None,
) -> dict[str, Any]:
    """Generate a JSON report from drift items.

    Args:
        drift_items: List of detected drift items
        base_ref: Base git reference
        head_ref: Head git reference
        pr_number: Optional PR number

    Returns:
        Report dictionary ready for JSON serialization
    """
    # Count by priority
    summary = {"high_priority": 0, "medium_priority": 0, "low_priority": 0, "total": 0}

    items_data = []
    for item in drift_items:
        summary["total"] += 1
        summary[f"{item.priority}_priority"] += 1

        items_data.append(
            {
                "id": item.rule_id,
                "priority": item.priority,
                "source_file": item.source_file,
                "change_type": item.change_type,
                "description": item.description,
                "diff_excerpt": item.diff_excerpt,
                "missing_docs": item.missing_docs,
                "outdated_docs": item.outdated_docs,
                "suggested_updates": item.suggested_updates,
            }
        )

    report: dict[str, Any] = {
        "detected_at": datetime.now(UTC).isoformat(),
        "base_ref": base_ref,
        "head_ref": head_ref,
        "drift_items": items_data,
        "summary": summary,
    }

    if pr_number is not None:
        report["pr_number"] = pr_number

    return report


def parse_args() -> argparse.Namespace:
    """Parse command line arguments.

    Returns:
        Parsed arguments namespace
    """
    parser = argparse.ArgumentParser(
        description="Detect documentation drift from code changes",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Compare against main branch
    uv run python scripts/check-docs-drift.py --base main --head HEAD

    # Output to file
    uv run python scripts/check-docs-drift.py --output drift-report.json

    # Compare specific refs
    uv run python scripts/check-docs-drift.py --base origin/main --head feature-branch

    # Include PR number in report
    uv run python scripts/check-docs-drift.py --pr 142 --output report.json
        """,
    )

    parser.add_argument(
        "--base",
        default="origin/main",
        help="Base git reference (default: origin/main)",
    )

    parser.add_argument(
        "--head",
        default="HEAD",
        help="Head git reference (default: HEAD)",
    )

    parser.add_argument(
        "--output",
        "-o",
        help="Output file path for JSON report (default: stdout)",
    )

    parser.add_argument(
        "--pr",
        type=int,
        help="PR number to include in report",
    )

    parser.add_argument(
        "--rules",
        default=None,
        help="Path to rules YAML file (default: scripts/docs-drift-rules.yml)",
    )

    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose output",
    )

    return parser.parse_args()


def main() -> int:
    """Main entry point.

    Returns:
        0 on success, 1 on error
    """
    args = parse_args()

    project_root = get_project_root()

    # Determine rules file path
    if args.rules:
        rules_path = Path(args.rules)
        if not rules_path.is_absolute():
            rules_path = project_root / rules_path
    else:
        rules_path = project_root / "scripts" / "docs-drift-rules.yml"

    # Load rules
    try:
        rules, ignore_patterns = load_rules(rules_path)
        if args.verbose:
            print(f"Loaded {len(rules)} rules from {rules_path}", file=sys.stderr)
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    # Detect drift
    try:
        drift_items = detect_drift(
            base_ref=args.base,
            head_ref=args.head,
            rules=rules,
            ignore_patterns=ignore_patterns,
            project_root=project_root,
        )
    except RuntimeError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    # Group related items
    drift_items = group_related_drift(drift_items)

    # Generate report
    report = generate_report(
        drift_items=drift_items,
        base_ref=args.base,
        head_ref=args.head,
        pr_number=args.pr,
    )

    # Output report
    json_output = json.dumps(report, indent=2)

    if args.output:
        output_path = Path(args.output)
        if not output_path.is_absolute():
            output_path = project_root / output_path
        output_path.write_text(json_output)
        if args.verbose:
            print(f"Report written to {output_path}", file=sys.stderr)
    else:
        print(json_output)

    # Print summary to stderr if verbose
    if args.verbose:
        summary = report["summary"]
        print(
            f"\nDrift Summary: {summary['total']} items "
            f"(high: {summary['high_priority']}, "
            f"medium: {summary['medium_priority']}, "
            f"low: {summary['low_priority']})",
            file=sys.stderr,
        )

    return 0


if __name__ == "__main__":
    sys.exit(main())
