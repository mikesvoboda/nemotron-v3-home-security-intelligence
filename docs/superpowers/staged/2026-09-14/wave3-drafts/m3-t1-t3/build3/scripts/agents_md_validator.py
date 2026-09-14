#!/usr/bin/env python3
"""AGENTS.md validation script.

Validates AGENTS.md files across the codebase for:
1. Stale file references (files mentioned but don't exist)
2. Missing AGENTS.md (directories with code files but no AGENTS.md)
3. Dead internal markdown links

Usage:
    uv run python scripts/agents_md_validator.py
    uv run python scripts/agents_md_validator.py --output report.json
    uv run python scripts/agents_md_validator.py --format json --config .agents-md-validator.yml

Exit codes:
    0 - Always (soft gate, issues are informational)

Output:
    Structured JSON report containing:
    - Total AGENTS.md files found
    - Issues by type (stale_reference, missing_agents_md, dead_link)
    - Summary counts
"""

from __future__ import annotations

import argparse
import fnmatch
import json
import re
import sys
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


@dataclass
class ValidatorConfig:
    """Configuration for the AGENTS.md validator."""

    exclude_directories: list[str] = field(default_factory=list)
    no_agents_md_required: list[str] = field(default_factory=list)
    code_extensions: list[str] = field(
        default_factory=lambda: [".py", ".ts", ".tsx", ".js", ".jsx"]
    )
    min_code_files: int = 2
    exclude_reference_patterns: list[str] = field(default_factory=list)


@dataclass
class ValidationIssue:
    """A detected validation issue."""

    type: str  # "stale_reference", "missing_agents_md", "dead_link"
    agents_md: str | None  # Path to AGENTS.md file (None for missing_agents_md)
    line: int | None  # Line number where issue found
    reference: str | None  # The problematic reference/link
    resolved_path: str | None  # The resolved path that was checked
    reason: str  # "file_not_found", "directory_not_found", "target_not_found"
    directory: str | None = None  # For missing_agents_md type
    code_files: list[str] | None = None  # For missing_agents_md type


def get_project_root() -> Path:
    """Find project root by looking for pyproject.toml."""
    current = Path(__file__).resolve().parent.parent
    while current != current.parent:
        if (current / "pyproject.toml").exists():
            return current
        current = current.parent
    # Fallback to script's parent's parent
    return Path(__file__).resolve().parent.parent


def load_config(config_path: Path | None, project_root: Path) -> ValidatorConfig:
    """Load configuration from YAML file.

    Args:
        config_path: Path to config file (optional)
        project_root: Project root directory

    Returns:
        ValidatorConfig with loaded settings
    """
    config = ValidatorConfig()

    if config_path is None:
        config_path = project_root / ".agents-md-validator.yml"

    if not config_path.exists():
        return config

    try:
        import yaml

        # nosemgrep: path-traversal-open - config_path is from CLI arg, validated
        with open(config_path) as f:
            data = yaml.safe_load(f)

        if data:
            if "exclude_directories" in data:
                config.exclude_directories = data["exclude_directories"]
            if "no_agents_md_required" in data:
                config.no_agents_md_required = data["no_agents_md_required"]
            if "code_extensions" in data:
                config.code_extensions = data["code_extensions"]
            if "min_code_files" in data:
                config.min_code_files = data["min_code_files"]
            if "exclude_reference_patterns" in data:
                config.exclude_reference_patterns = data["exclude_reference_patterns"]

    except ImportError:
        print("Warning: PyYAML not installed, using default config", file=sys.stderr)
    except Exception as e:
        print(f"Warning: Failed to load config: {e}", file=sys.stderr)

    return config


def find_agents_md_files(project_root: Path, config: ValidatorConfig) -> list[Path]:
    """Find all AGENTS.md files in the project.

    Args:
        project_root: Root directory to search
        config: Validator configuration

    Returns:
        List of paths to AGENTS.md files
    """
    agents_md_files = []

    for agents_md in project_root.rglob("AGENTS.md"):
        # Check if in excluded directory
        relative = agents_md.relative_to(project_root)
        skip = False

        for exclude in config.exclude_directories:
            # Check each part of the path
            for part in relative.parts:
                if fnmatch.fnmatch(part, exclude):
                    skip = True
                    break
            if skip:
                break

        if not skip:
            agents_md_files.append(agents_md)

    return sorted(agents_md_files)


def parse_inline_exclusions(content: str) -> set[str]:
    """Parse inline exclusion comments from AGENTS.md content.

    Supports:
        <!-- agents-md-validator: ignore-reference path/to/file.py -->

    Args:
        content: AGENTS.md file content

    Returns:
        Set of paths to ignore
    """
    exclusions = set()
    pattern = r"<!--\s*agents-md-validator:\s*ignore-reference\s+([^\s>]+)\s*-->"

    for match in re.finditer(pattern, content):
        exclusions.add(match.group(1))

    return exclusions


def extract_file_references(content: str, agents_md_dir: Path) -> list[tuple[int, str, str]]:
    """Extract file references from AGENTS.md content.

    Looks for:
    - Backtick-wrapped paths: `backend/api/routes/foo.py`
    - Directory references ending in /
    - Table cells with filenames: | config.py | Purpose |

    Args:
        content: AGENTS.md file content
        agents_md_dir: Directory containing the AGENTS.md file

    Returns:
        List of (line_number, reference, resolved_path) tuples
    """
    references = []
    lines = content.split("\n")

    # Patterns to match file references
    # Backtick-wrapped paths (but not code blocks)
    backtick_pattern = r"`([^`\n]+\.(py|ts|tsx|js|jsx|yml|yaml|json|md|txt|sh|sql|toml|cfg))`"
    # Directory references (ending with /)
    dir_pattern = r"`([^`\n]+/)`"

    in_code_block = False

    for line_num, line in enumerate(lines, start=1):
        # Track code blocks
        if line.strip().startswith("```"):
            in_code_block = not in_code_block
            continue

        if in_code_block:
            continue

        # Find backtick-wrapped file paths
        for match in re.finditer(backtick_pattern, line):
            ref = match.group(1)
            # Skip if it looks like a code snippet, not a path
            if " " in ref or "=" in ref or "(" in ref:
                continue
            # Skip external URLs
            if ref.startswith(("http://", "https://", "mailto:")):
                continue
            # Skip glob patterns (contain * or ?)
            if "*" in ref or "?" in ref:
                continue
            # Skip absolute paths (start with /)
            if ref.startswith("/"):
                continue
            # Only validate references that look like paths (have directory components)
            # Bare filenames like "index.ts" are often describing files in subdirectories
            # and cause too many false positives
            if "/" not in ref and not ref.startswith("."):
                continue
            references.append((line_num, ref, ref))

        # Find directory references
        for match in re.finditer(dir_pattern, line):
            ref = match.group(1)
            if " " not in ref and not ref.startswith(("http://", "https://")):
                # Skip glob patterns
                if "*" in ref or "?" in ref:
                    continue
                # Skip absolute paths
                if ref.startswith("/"):
                    continue
                references.append((line_num, ref, ref))

        # Note: We skip table cell filenames (e.g., | config.py | Purpose |)
        # because they often refer to files in subdirectories documented
        # in that section, not in the AGENTS.md directory itself.
        # This pattern causes too many false positives.

    return references


def extract_markdown_links(content: str) -> list[tuple[int, str, str]]:
    """Extract internal markdown links from AGENTS.md content.

    Looks for:
    - [Text](../other/AGENTS.md) - relative links
    - [Text](./file.py) - local file links
    - Skips external URLs (http://, https://)

    Args:
        content: AGENTS.md file content

    Returns:
        List of (line_number, link_text, link_target) tuples
    """
    links = []
    lines = content.split("\n")

    # Pattern for markdown links
    link_pattern = r"\[([^\]]+)\]\(([^)]+)\)"

    in_code_block = False

    for line_num, line in enumerate(lines, start=1):
        # Track code blocks
        if line.strip().startswith("```"):
            in_code_block = not in_code_block
            continue

        if in_code_block:
            continue

        for match in re.finditer(link_pattern, line):
            link_text = match.group(1)
            link_target = match.group(2)

            # Skip external URLs
            if link_target.startswith(("http://", "https://", "mailto:", "#")):
                continue

            # Skip anchor-only links
            if link_target.startswith("#"):
                continue

            # Remove anchor from link target
            if "#" in link_target:
                link_target = link_target.split("#")[0]

            if link_target:
                links.append((line_num, link_text, link_target))

    return links


def validate_file_references(
    agents_md_path: Path,
    content: str,
    project_root: Path,
    config: ValidatorConfig,
) -> list[ValidationIssue]:
    """Validate file references in an AGENTS.md file.

    Args:
        agents_md_path: Path to the AGENTS.md file
        content: File content
        project_root: Project root directory
        config: Validator configuration

    Returns:
        List of validation issues found
    """
    issues = []
    agents_md_dir = agents_md_path.parent
    relative_agents_md = str(agents_md_path.relative_to(project_root))

    # Get inline exclusions
    inline_exclusions = parse_inline_exclusions(content)

    # Extract and validate references
    references = extract_file_references(content, agents_md_dir)

    for line_num, ref, original_ref in references:
        # Skip inline exclusions
        if ref in inline_exclusions or original_ref in inline_exclusions:
            continue

        # Skip if matches exclude pattern
        skip = False
        for pattern in config.exclude_reference_patterns:
            try:
                if re.search(pattern, ref):
                    skip = True
                    break
            except re.error:
                continue
        if skip:
            continue

        # Resolve the path
        # First try relative to AGENTS.md directory
        resolved = agents_md_dir / ref
        if not resolved.exists():
            # Try relative to project root
            resolved = project_root / ref
            if not resolved.exists():
                # Check if it's a simple filename (current directory file)
                if "/" not in ref and "\\" not in ref:
                    resolved = agents_md_dir / ref
                    resolved_path = str(resolved.relative_to(project_root))
                else:
                    resolved_path = ref

                is_dir_ref = ref.endswith("/")
                reason = "directory_not_found" if is_dir_ref else "file_not_found"

                issues.append(
                    ValidationIssue(
                        type="stale_reference",
                        agents_md=relative_agents_md,
                        line=line_num,
                        reference=original_ref,
                        resolved_path=resolved_path,
                        reason=reason,
                    )
                )

    return issues


def validate_markdown_links(
    agents_md_path: Path,
    content: str,
    project_root: Path,
) -> list[ValidationIssue]:
    """Validate internal markdown links in an AGENTS.md file.

    Args:
        agents_md_path: Path to the AGENTS.md file
        content: File content
        project_root: Project root directory

    Returns:
        List of validation issues found
    """
    issues = []
    agents_md_dir = agents_md_path.parent
    relative_agents_md = str(agents_md_path.relative_to(project_root))

    # Get inline exclusions
    inline_exclusions = parse_inline_exclusions(content)

    # Extract and validate links
    links = extract_markdown_links(content)

    for line_num, _link_text, link_target in links:
        # Skip inline exclusions
        if link_target in inline_exclusions:
            continue

        # Resolve the link target relative to AGENTS.md directory
        resolved = (agents_md_dir / link_target).resolve()

        # Check if target exists
        if not resolved.exists():
            try:
                resolved_path = str(resolved.relative_to(project_root))
            except ValueError:
                resolved_path = str(resolved)

            issues.append(
                ValidationIssue(
                    type="dead_link",
                    agents_md=relative_agents_md,
                    line=line_num,
                    reference=link_target,
                    resolved_path=resolved_path,
                    reason="target_not_found",
                )
            )

    return issues


def find_directories_with_code(
    project_root: Path,
    config: ValidatorConfig,
) -> dict[Path, list[str]]:
    """Find directories that contain code files.

    Args:
        project_root: Root directory to search
        config: Validator configuration

    Returns:
        Dictionary mapping directory paths to list of code files
    """
    code_dirs: dict[Path, list[str]] = {}

    for ext in config.code_extensions:
        for code_file in project_root.rglob(f"*{ext}"):
            # Check if in excluded directory
            relative = code_file.relative_to(project_root)
            skip = False

            for exclude in config.exclude_directories:
                for part in relative.parts:
                    if fnmatch.fnmatch(part, exclude):
                        skip = True
                        break
                if skip:
                    break

            if skip:
                continue

            # Add to directory's file list
            parent = code_file.parent
            if parent not in code_dirs:
                code_dirs[parent] = []
            code_dirs[parent].append(code_file.name)

    return code_dirs


def check_missing_agents_md(
    project_root: Path,
    config: ValidatorConfig,
    existing_agents_md: set[Path],
) -> list[ValidationIssue]:
    """Check for directories with code files but no AGENTS.md.

    Args:
        project_root: Root directory
        config: Validator configuration
        existing_agents_md: Set of directories that have AGENTS.md

    Returns:
        List of validation issues for missing AGENTS.md files
    """
    issues = []

    # Find directories with code
    code_dirs = find_directories_with_code(project_root, config)

    for dir_path, code_files in code_dirs.items():
        # Skip if directory already has AGENTS.md
        if dir_path in existing_agents_md:
            continue

        # Skip if below threshold
        if len(code_files) < config.min_code_files:
            continue

        # Check if in no_agents_md_required list
        relative_dir = str(dir_path.relative_to(project_root))
        skip = False

        for allowed in config.no_agents_md_required:
            # Normalize paths for comparison
            allowed_normalized = allowed.rstrip("/")
            relative_normalized = relative_dir.rstrip("/")

            if relative_normalized == allowed_normalized:
                skip = True
                break
            # Check if it's a subdirectory of an allowed path
            if relative_dir.startswith(allowed_normalized + "/"):
                skip = True
                break

        if skip:
            continue

        issues.append(
            ValidationIssue(
                type="missing_agents_md",
                agents_md=None,
                line=None,
                reference=None,
                resolved_path=None,
                reason="directory_has_code_files",
                directory=relative_dir + "/",
                code_files=sorted(code_files)[:10],  # Limit to first 10 files
            )
        )

    return issues


def validate_all(project_root: Path, config: ValidatorConfig) -> tuple[int, list[ValidationIssue]]:
    """Run all validation checks.

    Args:
        project_root: Root directory
        config: Validator configuration

    Returns:
        Tuple of (total_agents_md_count, list_of_issues)
    """
    issues: list[ValidationIssue] = []

    # Find all AGENTS.md files
    agents_md_files = find_agents_md_files(project_root, config)
    total_count = len(agents_md_files)

    # Track directories that have AGENTS.md
    agents_md_dirs = {f.parent for f in agents_md_files}

    # Validate each AGENTS.md file
    for agents_md_path in agents_md_files:
        try:
            content = agents_md_path.read_text(encoding="utf-8")
        except Exception as e:
            print(f"Warning: Could not read {agents_md_path}: {e}", file=sys.stderr)
            continue

        # Check 1: Stale file references
        issues.extend(validate_file_references(agents_md_path, content, project_root, config))

        # Check 3: Dead markdown links
        issues.extend(validate_markdown_links(agents_md_path, content, project_root))

    # Check 2: Missing AGENTS.md
    issues.extend(check_missing_agents_md(project_root, config, agents_md_dirs))

    return total_count, issues


def generate_report(
    total_count: int,
    issues: list[ValidationIssue],
) -> dict[str, Any]:
    """Generate a JSON report from validation results.

    Args:
        total_count: Total number of AGENTS.md files found
        issues: List of validation issues

    Returns:
        Report dictionary ready for JSON serialization
    """
    # Count by type
    summary = {
        "stale_references": 0,
        "missing_agents_md": 0,
        "dead_links": 0,
    }

    issues_data = []
    for issue in issues:
        if issue.type == "stale_reference":
            summary["stale_references"] += 1
        elif issue.type == "missing_agents_md":
            summary["missing_agents_md"] += 1
        elif issue.type == "dead_link":
            summary["dead_links"] += 1

        issue_dict: dict[str, Any] = {
            "type": issue.type,
        }

        if issue.agents_md:
            issue_dict["agents_md"] = issue.agents_md
        if issue.line is not None:
            issue_dict["line"] = issue.line
        if issue.reference:
            issue_dict["reference"] = issue.reference
        if issue.resolved_path:
            issue_dict["resolved_path"] = issue.resolved_path
        if issue.reason:
            issue_dict["reason"] = issue.reason
        if issue.directory:
            issue_dict["directory"] = issue.directory
        if issue.code_files:
            issue_dict["code_files"] = issue.code_files

        issues_data.append(issue_dict)

    return {
        "timestamp": datetime.now(UTC).isoformat(),
        "total_agents_md_files": total_count,
        "issues": issues_data,
        "summary": summary,
    }


def print_summary(report: dict[str, Any]) -> None:
    """Print a human-readable summary to stderr.

    Args:
        report: The generated report dictionary
    """
    summary = report["summary"]
    total_issues = sum(summary.values())

    print("\n=== AGENTS.md Validation Summary ===", file=sys.stderr)
    print(f"Total AGENTS.md files: {report['total_agents_md_files']}", file=sys.stderr)
    print(f"Total issues found: {total_issues}", file=sys.stderr)

    if total_issues > 0:
        print("\nIssues by type:", file=sys.stderr)
        print(f"  - Stale references: {summary['stale_references']}", file=sys.stderr)
        print(f"  - Missing AGENTS.md: {summary['missing_agents_md']}", file=sys.stderr)
        print(f"  - Dead links: {summary['dead_links']}", file=sys.stderr)

        # Show first few issues of each type
        print("\nSample issues:", file=sys.stderr)
        shown = {"stale_reference": 0, "missing_agents_md": 0, "dead_link": 0}
        max_shown = 3

        for issue in report["issues"]:
            issue_type = issue["type"]
            if shown.get(issue_type, 0) >= max_shown:
                continue

            if issue_type == "stale_reference":
                print(
                    f"  [{issue_type}] {issue['agents_md']}:{issue['line']} "
                    f"- {issue['reference']} ({issue['reason']})",
                    file=sys.stderr,
                )
            elif issue_type == "missing_agents_md":
                files_preview = ", ".join(issue["code_files"][:3])
                print(
                    f"  [{issue_type}] {issue['directory']} "
                    f"- {len(issue['code_files'])} code files ({files_preview}...)",
                    file=sys.stderr,
                )
            elif issue_type == "dead_link":
                print(
                    f"  [{issue_type}] {issue['agents_md']}:{issue['line']} "
                    f"- {issue['reference']} ({issue['reason']})",
                    file=sys.stderr,
                )

            shown[issue_type] = shown.get(issue_type, 0) + 1
    else:
        print("\nNo issues found!", file=sys.stderr)

    print("", file=sys.stderr)


def parse_args() -> argparse.Namespace:
    """Parse command line arguments.

    Returns:
        Parsed arguments namespace
    """
    parser = argparse.ArgumentParser(
        description="Validate AGENTS.md files for stale references, missing files, and dead links",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Run validation with default config
    uv run python scripts/agents_md_validator.py

    # Output JSON to file
    uv run python scripts/agents_md_validator.py --output report.json

    # Use custom config
    uv run python scripts/agents_md_validator.py --config .agents-md-validator.yml

    # Output only JSON (no summary)
    uv run python scripts/agents_md_validator.py --format json --quiet
        """,
    )

    parser.add_argument(
        "--output",
        "-o",
        help="Output file path for JSON report (default: stdout)",
    )

    parser.add_argument(
        "--format",
        choices=["json", "text"],
        default="json",
        help="Output format (default: json)",
    )

    parser.add_argument(
        "--config",
        "-c",
        help="Path to config YAML file (default: .agents-md-validator.yml)",
    )

    parser.add_argument(
        "--quiet",
        "-q",
        action="store_true",
        help="Suppress summary output to stderr",
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
        0 always (soft gate)
    """
    args = parse_args()

    project_root = get_project_root()

    # Load configuration
    config_path = Path(args.config) if args.config else None
    if config_path and not config_path.is_absolute():
        config_path = project_root / config_path

    config = load_config(config_path, project_root)

    if args.verbose:
        print(f"Project root: {project_root}", file=sys.stderr)
        print(f"Exclude directories: {config.exclude_directories}", file=sys.stderr)
        print(f"Code extensions: {config.code_extensions}", file=sys.stderr)

    # Run validation
    total_count, issues = validate_all(project_root, config)

    # Generate report
    report = generate_report(total_count, issues)

    # Output results
    if args.format == "json":
        json_output = json.dumps(report, indent=2)

        if args.output:
            output_path = Path(args.output)
            if not output_path.is_absolute():
                output_path = project_root / output_path
            output_path.write_text(json_output)
            if not args.quiet:
                print(f"Report written to {output_path}", file=sys.stderr)
        else:
            print(json_output)

    # Print summary
    if not args.quiet:
        print_summary(report)

    # Always return 0 (soft gate)
    return 0


if __name__ == "__main__":
    sys.exit(main())
