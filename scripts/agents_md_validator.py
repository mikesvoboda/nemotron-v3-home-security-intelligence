#!/usr/bin/env python3
"""AGENTS.md validation script — the W1.1 ratchet.

Validates AGENTS.md files across the codebase for:
1. Stale file references (files mentioned but don't exist)
2. Missing AGENTS.md (directories with code files but no AGENTS.md)
3. Dead internal markdown links

The ratchet (W1.1): nothing new gets in; what is here can only drain. Two
committed baselines live in .agents-md-validator.yml — dead_reference_allowlist
(the dead pairs measured at baseline time, each with a tracking ref) and
retired_name_baseline (a per-name ceiling). Reference resolution is ANCHORED:
an existence hit proves a reference only when it resolves inside the scan root
and no path component is excluded — that is what makes the committed pair set
the same on CI and on every dev machine.

Usage:
    uv run python scripts/agents_md_validator.py
    uv run python scripts/agents_md_validator.py --output report.json
    uv run python scripts/agents_md_validator.py --root DIR   # fixture trees
    uv run python scripts/agents_md_validator.py --format json --config FILE

Exit codes:
    0 - the tree is clean under the baselines (allowlisted dead references are
        fine; retired-name counts are at or below baseline; missing_agents_md
        is reporting-only until W3.1 wires the boundary rule)
    1 - a CONTENT violation: a dead reference outside the allowlist, a dead
        link (zero tolerance), a retired-name count above its baseline, an
        unbalanced code fence (it would mask the rest of the file from the
        gate), or an inline ignore-reference comment without a tracking ref
    2 - the gate COULD NOT RUN: the config is absent/unparseable/incomplete,
        a pattern does not compile, or an AGENTS.md is unreadable. The report
        is NOT written — a DEFAULTS-config report would feed
        agents_md_linear_sync.py a table the tree does not support.

Output:
    Structured JSON report containing:
    - Total AGENTS.md files found
    - Issues by type (stale_reference, missing_agents_md, dead_link)
    - Summary counts
    - "ratchet": the additive gate block (counts, baseline, allowlist size,
      violations). issues[]/summary{} stay byte-identical for
      agents_md_linear_sync.py; the gate state never enters issues[].
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
from typing import Any, NamedTuple


class ConfigError(RuntimeError):
    """The gate could not run: an unreadable or incomplete baseline. Exit 2.

    A ratchet enforcing a baseline it failed to read is worse than the
    always-zero gate W1.1 replaced — it blames a docs PR for a broken tool.
    The silent-DEFAULTS fallback is deleted; nothing here may fall back.
    """


# The package's six retired names, in 40-docs.md's order. The loader requires
# ALL six keys in retired_name_baseline: a missing key is neither 0 (would
# fire on every pre-existing mention) nor unchecked (would make deleting the
# key the cheapest way to disable the gate).
RETIRED_NAMES: tuple[str, ...] = (
    "florence",
    "nemotron",
    "enrichment",
    "xclip",
    "pose",
    "demographics",
)
# Whole-word, case-insensitive (over content.lower()). Substring "pose" is
# 1457 mentions across the tree (purpose/compose/PoseResult — live English and
# live code); \b measures the mentions the plan named. \w's underscore also
# excludes pose_estimation.py while including YOLOv8-pose and enrichment-light.
RETIRED_NAME_PATTERNS = {name: re.compile(rf"\b{name}\b") for name in RETIRED_NAMES}

# An allowlist entry is a pair, not a pattern: a glob char or a leading / in a
# committed entry would widen the baseline invisibly at match time.
ALLOWLIST_FORBIDDEN_CHARS = frozenset("*?[(\\")


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
    # Compiled at load (a bad regex is exit 2 at the gate, not a swallowed
    # re.error at the scan site).
    exclude_reference_res: list[re.Pattern[str]] = field(default_factory=list)
    # W1.1 baselines — required keys; load_config raises ConfigError without
    # them. Pairs are (agents_md, reference), the exact fields report.json
    # emits, so the gate matches the emitted tuple with no translation layer.
    dead_reference_allowlist: list[tuple[str, str]] = field(default_factory=list)
    retired_name_baseline: dict[str, int] = field(default_factory=dict)
    config_loaded: bool = False


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


class Scan(NamedTuple):
    """Everything one pass over the tree produced, for the single gate point."""

    total_agents_md_files: int
    issues: list[ValidationIssue]
    retired_counts: dict[str, int]
    unbalanced_fences: list[str]
    bare_ignore_comments: list[tuple[str, str]]  # (agents_md, reference)


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
    """Load the (mandatory) configuration from YAML.

    Every failure here is a ConfigError — exit 2, before any scan and before
    any report is written. The pre-W1.1 behaviour (warn, continue with
    DEFAULTS) produced a gate enforcing a baseline it never read.
    """
    if config_path is None:
        config_path = project_root / ".agents-md-validator.yml"

    if not config_path.exists():
        raise ConfigError(
            f"config file not found at {config_path} — the committed baselines "
            "live there; a run without them cannot tell a drained pair from an "
            "unchecked one"
        )

    try:
        import yaml
    except ImportError as exc:
        raise ConfigError(
            f"PyYAML is not importable ({exc}) — the baselines in {config_path} "
            "would silently be DEFAULTS; run under `uv run` or `pip install pyyaml`"
        ) from exc

    try:
        # nosemgrep: path-traversal-open - config_path is from CLI arg, validated
        with open(config_path) as f:
            data = yaml.safe_load(f)
    except yaml.YAMLError as exc:
        raise ConfigError(f"{config_path} is not valid YAML: {exc}") from exc

    if data is None:
        data = {}
    if not isinstance(data, dict):
        raise ConfigError(f"{config_path} loaded as {type(data).__name__}, not a mapping")

    config = ValidatorConfig()
    config.exclude_directories = list(data.get("exclude_directories", []))
    config.no_agents_md_required = list(data.get("no_agents_md_required", []))
    if "code_extensions" in data:
        config.code_extensions = list(data["code_extensions"])
    if "min_code_files" in data:
        config.min_code_files = data["min_code_files"]

    patterns = list(data.get("exclude_reference_patterns", []))
    config.exclude_reference_patterns = patterns
    for pattern in patterns:
        try:
            config.exclude_reference_res.append(re.compile(pattern))
        except re.error as exc:
            raise ConfigError(
                f"exclude_reference_patterns entry {pattern!r} does not compile: {exc} "
                f"— in the file next to the baselines, this key launders the gate "
                f"silently, so it is compiled here, not swallowed at the scan site"
            ) from exc

    raw_allow = data.get("dead_reference_allowlist")
    if raw_allow is None:
        raise ConfigError(
            f"{config_path} has no dead_reference_allowlist key — absent is not "
            "'allow nothing new' and not 'check nothing'; the baseline must be explicit"
        )
    if not isinstance(raw_allow, list):
        raise ConfigError("dead_reference_allowlist must be a list of pair entries")
    for entry in raw_allow:
        if not isinstance(entry, dict):
            raise ConfigError(f"allowlist entry is not a mapping: {entry!r}")
        agents_md, reference = entry.get("agents_md"), entry.get("reference")
        if not agents_md or not reference:
            raise ConfigError(f"allowlist entry needs non-empty agents_md+reference: {entry!r}")
        if reference.startswith("/") or set(reference) & ALLOWLIST_FORBIDDEN_CHARS:
            raise ConfigError(
                f"allowlist reference {reference!r} is not a literal path (leading / or "
                "one of * ? [ ( \\) — an entry may not be silently widened into a pattern"
            )
        if not entry.get("tracking"):
            raise ConfigError(
                f"allowlist entry {agents_md} -> {reference} has no tracking ref — "
                "every admitted dead pair carries one (W1.3 drains this list; an "
                "admission without a reason to revisit is a permanent excuse)"
            )
        config.dead_reference_allowlist.append((agents_md, reference))

    raw_baseline = data.get("retired_name_baseline")
    if raw_baseline is None:
        raise ConfigError(
            f"{config_path} has no retired_name_baseline key — the per-name "
            "ceilings are the second arm of the ratchet"
        )
    if not isinstance(raw_baseline, dict):
        raise ConfigError("retired_name_baseline must be a name: count mapping")
    for name in RETIRED_NAMES:
        if name not in raw_baseline:
            raise ConfigError(
                f"retired_name_baseline is missing {name!r} — a missing name is not "
                "0 and not unchecked; all six are required"
            )
        value = raw_baseline[name]
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            raise ConfigError(f"retired_name_baseline[{name!r}] must be an int >= 0, got {value!r}")
        config.retired_name_baseline[name] = value

    config.config_loaded = True
    return config


def path_is_excluded(relative: Path, config: ValidatorConfig) -> bool:
    """True if any path component matches an exclude_directories entry."""
    return any(
        fnmatch.fnmatch(part, exclude)
        for part in relative.parts
        for exclude in config.exclude_directories
    )


def resolve_proven(candidate: Path, project_root: Path, config: ValidatorConfig) -> bool:
    """ANCHORED existence: the candidate exists, resolves inside the scan
    root, and no component of that anchored path is an excluded directory.

    Without the anchor, `.venv/` is alive on a dev machine with a local venv
    and dead on CI — a machine-dependent baseline. With it, the committed
    pair set is identical everywhere (measured: 13 on the dev workspace and a
    clean clone). The pair census must not depend on what one machine
    happens to have in its working directory.
    """
    if not candidate.exists():
        return False
    root = project_root.resolve()
    try:
        relative = candidate.resolve().relative_to(root)
    except ValueError:
        return False
    return not path_is_excluded(relative, config)


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
        if not path_is_excluded(relative, config):
            agents_md_files.append(agents_md)

    return sorted(agents_md_files)


def parse_inline_exclusions(content: str) -> tuple[set[str], list[str]]:
    """Parse inline exclusion comments from AGENTS.md content.

    The tracked form suppresses; the bare form is a violation:

        <!-- agents-md-validator: ignore-reference path/to/file.py # <ref> -->
        <!-- agents-md-validator: ignore-reference path/to/file.py -->

    W1.1: an unadorned comment measured to be a zero-diff suppression channel
    for both gate arms — one added HTML comment silenced a dead reference
    without touching the baseline. House doctrine for every suppression: it
    carries a tracking ref, or it is not a suppression.
    """
    tracked: set[str] = set()
    bare: list[str] = []
    for match in re.finditer(
        r"<!--\s*agents-md-validator:\s*ignore-reference\s+(.*?)\s*-->", content
    ):
        parts = match.group(1).split(None, 1)
        if not parts:
            continue
        reference = parts[0]
        rest = parts[1] if len(parts) > 1 else ""
        if rest.startswith("#") and rest.lstrip("#").strip():
            tracked.add(reference)
        else:
            bare.append(reference)
    return tracked, bare


def fence_mask(content: str) -> tuple[list[bool], bool]:
    """CommonMark fenced-code state per line, plus an unbalanced flag.

    A line is masked (excluded from reference/link extraction) while a fence
    is open; the opener and closer lines themselves are masked too. An opener
    is <=3 leading spaces + 3+ same-char backticks or tildes, and a backtick
    opener's info string may not contain a backtick; a closer is the same
    character with length >= the opener's and no info text.

    The pre-W1.1 toggle (`line.strip().startswith("```")`) mis-detected
    indented and tilde fences and — worse — an OPEN fence with no close
    masked the whole rest of the file, checking nothing. An unbalanced file
    is a CONTENT violation the gate raises (validate_all reports it); it is
    never "repaired" by treating the remainder as prose.
    """
    lines = content.split("\n")
    mask = [False] * len(lines)
    open_fence: tuple[str, int] | None = None
    for i, line in enumerate(lines):
        marker = re.match(r"^ {0,3}(`{3,}|~{3,})(.*)$", line)
        if open_fence is None:
            if marker:
                char, info = marker.group(1)[0], marker.group(2)
                if not (char == "`" and "`" in info):
                    open_fence = (char, len(marker.group(1)))
                    mask[i] = True
        else:
            mask[i] = True
            char, length = open_fence
            if (
                marker
                and marker.group(1)[0] == char
                and len(marker.group(1)) >= length
                and marker.group(2).strip() == ""
            ):
                open_fence = None
    return mask, open_fence is not None


def extract_file_references(
    content: str, agents_md_dir: Path, mask: list[bool]
) -> list[tuple[int, str, str]]:
    """Extract file references from AGENTS.md content.

    Looks for:
    - Backtick-wrapped paths: `backend/api/routes/foo.py`
    - Directory references ending in /

    (Table cells are skipped: they often name files in subdirectories of the
    section, not of the AGENTS.md, and cause false positives. Widening the
    grammar is W1.3's job — the committed baselines are measured under THIS
    width, and a wider extractor without a re-measured baseline reddens the
    first incidental PR.)

    Args:
        content: AGENTS.md file content
        agents_md_dir: Directory containing the AGENTS.md file
        mask: per-line fence mask from fence_mask(content)

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

    for line_num, line in enumerate(lines, start=1):
        if mask[line_num - 1]:
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

    return references


def extract_markdown_links(content: str, mask: list[bool]) -> list[tuple[int, str, str]]:
    """Extract internal markdown links from AGENTS.md content.

    Looks for:
    - [Text](../other/AGENTS.md) - relative links
    - [Text](./file.py) - local file links
    - Skips external URLs (http://, https://)

    Args:
        content: AGENTS.md file content
        mask: per-line fence mask from fence_mask(content)

    Returns:
        List of (line_number, link_text, link_target) tuples
    """
    links = []
    lines = content.split("\n")

    # Pattern for markdown links
    link_pattern = r"\[([^\]]+)\]\(([^)]+)\)"

    for line_num, line in enumerate(lines, start=1):
        if mask[line_num - 1]:
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
    mask: list[bool],
    tracked_exclusions: set[str],
) -> list[ValidationIssue]:
    """Validate file references in an AGENTS.md file (anchored resolution)."""
    issues = []
    agents_md_dir = agents_md_path.parent
    relative_agents_md = str(agents_md_path.relative_to(project_root))

    references = extract_file_references(content, agents_md_dir, mask)

    for line_num, ref, original_ref in references:
        # Skip tracked inline exclusions (bare ones are violations the gate
        # raises separately — they suppress nothing).
        if ref in tracked_exclusions or original_ref in tracked_exclusions:
            continue

        # Skip if matches an exclude pattern (compiled at load: exit 2 there,
        # not a swallowed re.error here)
        if any(rx.search(ref) for rx in config.exclude_reference_res):
            continue

        # ANCHORED resolution: relative to the AGENTS.md first, then the
        # project root. An existence hit inside an excluded directory does
        # not prove the reference (resolve_proven).
        if resolve_proven(agents_md_dir / ref, project_root, config):
            continue
        if resolve_proven(project_root / ref, project_root, config):
            continue

        if "/" not in ref and "\\" not in ref:
            resolved_path = str((agents_md_dir / ref).relative_to(project_root))
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
    config: ValidatorConfig,
    mask: list[bool],
    tracked_exclusions: set[str],
) -> list[ValidationIssue]:
    """Validate internal markdown links in an AGENTS.md file (anchored)."""
    issues = []
    agents_md_dir = agents_md_path.parent
    relative_agents_md = str(agents_md_path.relative_to(project_root))

    links = extract_markdown_links(content, mask)

    for line_num, _link_text, link_target in links:
        if link_target in tracked_exclusions:
            continue

        candidate = agents_md_dir / link_target
        if resolve_proven(candidate, project_root, config):
            continue

        resolved = candidate.resolve()
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
    """Find directories that contain code files."""
    code_dirs: dict[Path, list[str]] = {}

    for ext in config.code_extensions:
        for code_file in project_root.rglob(f"*{ext}"):
            relative = code_file.relative_to(project_root)
            if path_is_excluded(relative, config):
                continue

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

    Reporting-only in W1.1: missing_agents_md is not one of the package's
    failure conditions — wiring the boundary rule is W3.1's Phase-3 job.
    """
    issues = []

    code_dirs = find_directories_with_code(project_root, config)

    for dir_path, code_files in code_dirs.items():
        if dir_path in existing_agents_md:
            continue

        if len(code_files) < config.min_code_files:
            continue

        relative_dir = str(dir_path.relative_to(project_root))
        skip = False

        for allowed in config.no_agents_md_required:
            allowed_normalized = allowed.rstrip("/")
            relative_normalized = relative_dir.rstrip("/")

            if relative_normalized == allowed_normalized:
                skip = True
                break
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
                code_files=sorted(code_files)[:10],
            )
        )

    return issues


def count_retired_names(agents_md_files: list[Path]) -> dict[str, int]:
    """Whole-word, case-insensitive mention counts for the six retired names.

    Takes the SCANNED FILE LIST — never re-walks a wider tree, so a README
    next door is not an AGENTS.md. Fenced blocks and tables are counted (an
    exclusion would be a dodge surface; the whole-file count is the number
    the baseline was measured with).
    """
    counts = dict.fromkeys(RETIRED_NAMES, 0)
    for path in agents_md_files:
        try:
            text = path.read_text(encoding="utf-8").lower()
        except (OSError, UnicodeDecodeError) as exc:
            raise ConfigError(f"could not count retired names in {path}: {exc}") from exc
        for name in RETIRED_NAMES:
            counts[name] += len(RETIRED_NAME_PATTERNS[name].findall(text))
    return counts


def validate_all(project_root: Path, config: ValidatorConfig) -> Scan:
    """Run all validation checks in one pass over the scanned AGENTS.md set.

    A file that cannot be read is a ConfigError, not a warning: silently
    dropping one file removes its dead references AND its mentions from the
    censuses — one bad byte launders both arms.
    """
    agents_md_files = find_agents_md_files(project_root, config)

    issues: list[ValidationIssue] = []
    unbalanced_fences: list[str] = []
    bare_ignore_comments: list[tuple[str, str]] = []

    for agents_md_path in agents_md_files:
        relative = str(agents_md_path.relative_to(project_root))
        try:
            content = agents_md_path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            raise ConfigError(
                f"could not read {relative}: {exc} — an unreadable AGENTS.md "
                "disappears from the gate's censuses, so the gate refuses to "
                "report a tree it could not read"
            ) from exc

        mask, unbalanced = fence_mask(content)
        if unbalanced:
            unbalanced_fences.append(relative)

        tracked, bare = parse_inline_exclusions(content)
        bare_ignore_comments.extend((relative, ref) for ref in bare)

        issues.extend(
            validate_file_references(agents_md_path, content, project_root, config, mask, tracked)
        )
        issues.extend(
            validate_markdown_links(agents_md_path, content, project_root, config, mask, tracked)
        )

    retired_counts = count_retired_names(agents_md_files)
    agents_md_dirs = {f.parent for f in agents_md_files}
    issues.extend(check_missing_agents_md(project_root, config, agents_md_dirs))

    return Scan(
        total_agents_md_files=len(agents_md_files),
        issues=issues,
        retired_counts=retired_counts,
        unbalanced_fences=unbalanced_fences,
        bare_ignore_comments=bare_ignore_comments,
    )


def evaluate_ratchet(scan: Scan, config: ValidatorConfig) -> list[str]:
    """THE single gate decision point (ratchet-check.py's check() idiom).

    Reads the scan; mutates and filters nothing; returns violation strings.
    Empty list == green. The report is written either way; main() maps a
    non-empty list to exit 1.
    """
    allow = set(config.dead_reference_allowlist)
    violations: list[str] = []

    for issue in scan.issues:
        if issue.type == "stale_reference":
            if (issue.agents_md, issue.reference) not in allow:
                violations.append(
                    f"dead reference: {issue.agents_md}:{issue.line} -> "
                    f"`{issue.reference}` is not in dead_reference_allowlist. "
                    "Fix: create the path, delete the citation, or drain/replace "
                    "the pair in .agents-md-validator.yml only as a reviewed "
                    "adjudication with a tracking ref."
                )
        elif issue.type == "dead_link":
            violations.append(
                f"dead link: {issue.agents_md}:{issue.line}]({issue.reference}) "
                "— links have zero tolerance (no committed link baseline exists). "
                "Fix the target, or suppress deliberately with a tracked comment: "
                f"<!-- agents-md-validator: ignore-reference {issue.reference} "
                "# <W1.3/ledger-ref> -->"
            )
        # missing_agents_md: reporting-only until W3.1 (scope pin: a
        # boundary-list gate here would fail today's tree, which the
        # package's Done-when requires green).

    for name in RETIRED_NAMES:
        measured = scan.retired_counts[name]
        baseline = config.retired_name_baseline[name]
        if measured > baseline:
            violations.append(
                f"retired name above baseline: {name} measured {measured} > "
                f"baseline {baseline} (whole-word \\b{name}\\b, case-insensitive, "
                "over the scanned AGENTS.md set). Counts may only FALL: remove "
                "the mention — a raise is a hand edit in .agents-md-validator.yml "
                "that a human reviews, per scripts/ratchet-check.py's doctrine."
            )

    for relative in scan.unbalanced_fences:
        violations.append(
            f"unbalanced code fence in {relative}: an unclosed fence masks the "
            "rest of the file from both arms of the ratchet — close it."
        )

    for relative, reference in scan.bare_ignore_comments:
        violations.append(
            f"untracked inline exclusion in {relative}: "
            f"<!-- agents-md-validator: ignore-reference {reference} --> has no "
            "tracking ref, so it suppresses nothing — append ' # <W1.3/ledger-ref>' "
            "or delete the comment."
        )

    return violations


def generate_report(
    scan: Scan,
    config: ValidatorConfig,
    violations: list[str],
) -> dict[str, Any]:
    """Generate a JSON report from validation results.

    issues[] and summary{} are byte-frozen for agents_md_linear_sync.py: it
    buckets issues[] by the three exact type strings and has_issues() is
    len(issues)>0 — a fourth issue.type would make its Linear task claim
    issues while naming none. All ratchet state rides in the additive
    top-level "ratchet" block.
    """
    summary = {
        "stale_references": 0,
        "missing_agents_md": 0,
        "dead_links": 0,
    }

    issues_data = []
    for issue in scan.issues:
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
        "total_agents_md_files": scan.total_agents_md_files,
        "issues": issues_data,
        "summary": summary,
        "ratchet": {
            "counts": scan.retired_counts,
            "baseline": config.retired_name_baseline,
            "allowlist_size": len(config.dead_reference_allowlist),
            "unbalanced_fences": scan.unbalanced_fences,
            "violations": violations,
        },
    }


def print_summary(report: dict[str, Any]) -> None:
    """Print a human-readable summary to stderr."""
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
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Validate AGENTS.md files and enforce the W1.1 ratchet baselines",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Run the gate on this repository
    uv run python scripts/agents_md_validator.py

    # Output JSON to file
    uv run python scripts/agents_md_validator.py --output report.json

    # Use custom config
    uv run python scripts/agents_md_validator.py --config .agents-md-validator.yml

    # Check a fixture tree (its own .agents-md-validator.yml, not the repo's)
    uv run python scripts/agents_md_validator.py --root tmp/fixture --quiet

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
        help="Path to config YAML file (default: <root>/.agents-md-validator.yml)",
    )

    parser.add_argument(
        "--root",
        help="Directory to scan (default: the project root of this script). "
        "Fixture trees need this: without it, the walk follows __file__ and a "
        "'fixture' run silently validates the real repository.",
    )

    parser.add_argument(
        "--quiet",
        "-q",
        action="store_true",
        help="Suppress summary output to stderr (ratchet violations still print)",
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
        0 green | 1 content violation | 2 the gate could not run (see the
        module docstring; the report is never written on 2).
    """
    args = parse_args()

    project_root = Path(args.root).resolve() if args.root else get_project_root()

    config_path = Path(args.config) if args.config else None
    if config_path and not config_path.is_absolute():
        config_path = project_root / config_path

    try:
        config = load_config(config_path, project_root)
    except ConfigError as exc:
        print(f"AGENTS.md ratchet could not run: {exc}", file=sys.stderr)
        print(
            "Exit 2: this is the gate, not your docs. No report was written — "
            "a DEFAULTS-config report would feed agents_md_linear_sync.py a "
            "table the tree does not support.",
            file=sys.stderr,
        )
        return 2

    if args.verbose:
        print(f"Project root: {project_root}", file=sys.stderr)
        if args.root:
            print("  (from --root)", file=sys.stderr)
        print(f"Exclude directories: {config.exclude_directories}", file=sys.stderr)
        print(f"Code extensions: {config.code_extensions}", file=sys.stderr)

    scan = validate_all(project_root, config)
    violations = evaluate_ratchet(scan, config)
    report = generate_report(scan, config, violations)

    # Violations print even under --quiet: the gate never goes silent.
    if violations:
        print(f"\nAGENTS.md ratchet: {len(violations)} violation(s):", file=sys.stderr)
        for violation in violations:
            print(f"  - {violation}", file=sys.stderr)

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

    if not args.quiet:
        print_summary(report)

    return 1 if violations else 0


if __name__ == "__main__":
    sys.exit(main())
