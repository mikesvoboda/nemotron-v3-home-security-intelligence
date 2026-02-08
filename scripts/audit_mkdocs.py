#!/usr/bin/env python3
"""Audit MkDocs documentation for rendering issues.

Checks for:
1. Mermaid diagrams hidden inside HTML comments (won't render)
2. Mermaid diagrams with syntax errors (will fail to render)
3. Image references pointing to missing files
4. Broken internal markdown links
5. Mermaid fenced blocks using wrong fence syntax
6. Files referenced in mkdocs.yml nav that don't exist
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

DOCS_DIR = Path("docs")
MKDOCS_YML = Path("mkdocs.yml")

# ANSI colors
RED = "\033[91m"
YELLOW = "\033[93m"
GREEN = "\033[92m"
CYAN = "\033[96m"
BOLD = "\033[1m"
RESET = "\033[0m"


def find_commented_mermaid(path: Path, content: str) -> list[dict]:
    """Find Mermaid blocks trapped inside HTML comments.

    If a static image (SVG/PNG) tag exists within the 5 lines preceding the
    comment, the Mermaid source is assumed to be intentionally preserved for
    maintenance.  These are reported as "info" rather than "warning".
    """
    issues = []
    lines = content.split("\n")
    for m in re.finditer(r"<!--(.*?)-->", content, re.DOTALL):
        comment = m.group(1)
        if "```mermaid" not in comment and "~~~mermaid" not in comment:
            continue

        line_num = content[: m.start()].count("\n") + 1

        # Check if a static image replacement exists in the preceding 5 lines
        has_image_replacement = False
        start_check = max(0, line_num - 6)  # line_num is 1-based
        for i in range(start_check, min(line_num - 1, len(lines))):
            if re.search(r"!\[.*\]\(.*\.(svg|png|jpg|jpeg|webp)", lines[i]):
                has_image_replacement = True
                break

        if has_image_replacement:
            issues.append(
                {
                    "file": str(path),
                    "line": line_num,
                    "severity": "info",
                    "category": "commented-mermaid",
                    "message": "Mermaid source preserved in comment (static image replacement exists above)",
                }
            )
        else:
            issues.append(
                {
                    "file": str(path),
                    "line": line_num,
                    "severity": "warning",
                    "category": "commented-mermaid",
                    "message": "Mermaid diagram hidden inside HTML comment — will not render",
                }
            )
    return issues


def find_mermaid_issues(path: Path, content: str) -> list[dict]:
    """Find Mermaid blocks with potential syntax issues."""
    issues = []

    # Find all mermaid fenced code blocks (not inside comments)
    # First, strip HTML comments
    no_comments = re.sub(r"<!--.*?-->", "", content, flags=re.DOTALL)

    for m in re.finditer(r"```mermaid\s*\n(.*?)```", no_comments, re.DOTALL):
        diagram = m.group(1).strip()
        line_num = content[: content.find(m.group(0))].count("\n") + 1

        # Check for common syntax issues
        if not diagram:
            issues.append(
                {
                    "file": str(path),
                    "line": line_num,
                    "severity": "error",
                    "category": "empty-mermaid",
                    "message": "Empty Mermaid diagram block",
                }
            )
            continue

        # Check for valid diagram type
        # Skip %%{init:}%% directives — they precede the actual diagram type
        # These can be single-line: %%{init: {'theme': 'dark'}}%%
        # Or multi-line:  %%{init: {\n  'theme': 'dark'\n}}%%
        lines = diagram.split("\n")
        first_line = lines[0].strip()
        if first_line.startswith("%%"):
            # Skip past the entire init block (may span multiple lines)
            in_init = "%%{" in first_line and "}}%%" not in first_line
            found_type = False
            for line in lines[1:]:
                stripped = line.strip()
                if in_init:
                    if "}}%%" in stripped:
                        in_init = False
                    continue
                if stripped and not stripped.startswith("%%"):
                    first_line = stripped
                    found_type = True
                    break
            if not found_type:
                # Block contains only init directives (e.g., a theme config snippet) — skip validation
                continue

        valid_types = [
            "flowchart",
            "graph",
            "sequenceDiagram",
            "classDiagram",
            "stateDiagram",
            "erDiagram",
            "gantt",
            "pie",
            "gitgraph",
            "journey",
            "mindmap",
            "timeline",
            "quadrantChart",
            "sankey",
            "xychart",
            "block",
        ]
        if not any(first_line.startswith(t) for t in valid_types):
            issues.append(
                {
                    "file": str(path),
                    "line": line_num,
                    "severity": "error",
                    "category": "invalid-mermaid-type",
                    "message": f"Mermaid block starts with unknown type: '{first_line[:50]}'",
                }
            )

        # Check for unbalanced subgraph/end (only in flowchart/graph diagrams)
        # sequenceDiagram, stateDiagram, etc. use 'end' for their own syntax
        diagram_type = first_line.split()[0] if first_line else ""
        subgraph_count = len(re.findall(r"\bsubgraph\b", diagram))
        end_count = len(re.findall(r"^\s*end\s*$", diagram, re.MULTILINE))
        if diagram_type in ("flowchart", "graph") and subgraph_count != end_count:
            issues.append(
                {
                    "file": str(path),
                    "line": line_num,
                    "severity": "error",
                    "category": "unbalanced-subgraph",
                    "message": f"Unbalanced subgraph/end: {subgraph_count} subgraph(s) vs {end_count} end(s)",
                }
            )

        # Check for 4-backtick fence (common mistake)
        if "````" in m.group(0):
            issues.append(
                {
                    "file": str(path),
                    "line": line_num,
                    "severity": "error",
                    "category": "wrong-fence",
                    "message": "Mermaid block uses 4 backticks instead of 3",
                }
            )

    return issues


def _strip_fenced_code_blocks(content: str) -> str:
    """Replace fenced code block content with blank lines to preserve line numbers.

    Handles both backtick (```) and tilde (~~~) fences, including info strings.
    The fence delimiters themselves are kept but block contents are blanked out
    so that markdown links inside code examples are not flagged as broken.
    """
    return re.sub(
        r"^(`{3,}|~{3,})([^\n]*)\n(.*?)\n\1\s*$",
        lambda m: m.group(1)
        + m.group(2)
        + "\n"
        + "\n" * m.group(3).count("\n")
        + "\n"
        + m.group(1),
        content,
        flags=re.DOTALL | re.MULTILINE,
    )


def find_broken_images(path: Path, content: str) -> list[dict]:
    """Find image references pointing to missing files."""
    issues = []
    doc_dir = path.parent

    # Strip fenced code blocks so example images inside code aren't flagged
    content = _strip_fenced_code_blocks(content)

    for m in re.finditer(r"!\[([^\]]*)\]\(([^)]+)\)", content):
        alt_text = m.group(1)
        img_path = m.group(2)

        # Skip external URLs
        if img_path.startswith(("http://", "https://", "//")):
            continue

        # Strip any anchor or query params
        img_path = img_path.split("#")[0].split("?")[0]

        # Resolve relative path
        resolved = (doc_dir / img_path).resolve()
        if not resolved.exists():
            line_num = content[: m.start()].count("\n") + 1
            issues.append(
                {
                    "file": str(path),
                    "line": line_num,
                    "severity": "error",
                    "category": "missing-image",
                    "message": f"Image not found: {img_path}",
                }
            )

    return issues


def find_broken_links(path: Path, content: str) -> list[dict]:
    """Find internal markdown links pointing to missing files."""
    issues = []
    doc_dir = path.parent

    # Strip fenced code blocks so example links inside code aren't flagged
    content = _strip_fenced_code_blocks(content)

    # Match [text](path.md) but not images ![text](path)
    for m in re.finditer(r"(?<!!)\[([^\]]*)\]\(([^)]+)\)", content):
        link_text = m.group(1)
        link_path = m.group(2)

        # Skip external URLs, anchors, mailto
        if link_path.startswith(("http://", "https://", "//", "#", "mailto:")):
            continue

        # Skip absolute paths (repo root references)
        if link_path.startswith("/"):
            continue

        # Strip anchor
        link_path = link_path.split("#")[0]
        if not link_path:
            continue

        # Resolve relative path
        resolved = (doc_dir / link_path).resolve()
        if not resolved.exists():
            line_num = content[: m.start()].count("\n") + 1
            issues.append(
                {
                    "file": str(path),
                    "line": line_num,
                    "severity": "warning",
                    "category": "broken-link",
                    "message": f"Link target not found: {link_path}",
                }
            )

    return issues


def find_wrong_mermaid_fence(path: Path, content: str) -> list[dict]:
    """Find mermaid blocks using tilde fence or wrong syntax."""
    issues = []
    for m in re.finditer(r"~~~mermaid", content):
        line_num = content[: m.start()].count("\n") + 1
        issues.append(
            {
                "file": str(path),
                "line": line_num,
                "severity": "warning",
                "category": "tilde-fence-mermaid",
                "message": "Mermaid block uses ~~~ fence — may not render with superfences",
            }
        )
    return issues


def audit_nav_references() -> list[dict]:
    """Check that files referenced in mkdocs.yml nav actually exist."""
    issues = []
    if not MKDOCS_YML.exists():
        return issues

    yml_content = MKDOCS_YML.read_text()
    # Find .md file references in nav
    for m in re.finditer(r":\s*([^\s#]+\.md)\s*$", yml_content, re.MULTILINE):
        md_path = m.group(1)
        full_path = DOCS_DIR / md_path
        if not full_path.exists():
            line_num = yml_content[: m.start()].count("\n") + 1
            issues.append(
                {
                    "file": "mkdocs.yml",
                    "line": line_num,
                    "severity": "error",
                    "category": "missing-nav-file",
                    "message": f"Nav references missing file: docs/{md_path}",
                }
            )
    return issues


def main() -> int:
    all_issues: list[dict] = []

    # Audit all markdown files under docs/
    md_files = sorted(DOCS_DIR.rglob("*.md"))
    print(f"{BOLD}Auditing {len(md_files)} markdown files in docs/{RESET}\n")

    # Directories to skip for link/image checks (templates/plans have placeholder links)
    skip_dirs = {"templates", "archive", "plans"}

    for path in md_files:
        content = path.read_text(errors="replace")
        all_issues.extend(find_commented_mermaid(path, content))
        all_issues.extend(find_mermaid_issues(path, content))

        # Skip template/archive dirs for link checks
        if not any(part in skip_dirs for part in path.parts):
            all_issues.extend(find_broken_images(path, content))
            all_issues.extend(find_broken_links(path, content))

        all_issues.extend(find_wrong_mermaid_fence(path, content))

    # Audit mkdocs.yml nav
    all_issues.extend(audit_nav_references())

    # Separate actionable issues from informational notes
    actionable = [i for i in all_issues if i["severity"] in ("error", "warning")]
    info_items = [i for i in all_issues if i["severity"] == "info"]

    if not actionable and not info_items:
        print(f"{GREEN}No issues found.{RESET}")
        return 0

    # Group by category
    categories: dict[str, list[dict]] = {}
    for issue in all_issues:
        cat = issue["category"]
        categories.setdefault(cat, []).append(issue)

    # Print summary
    errors = sum(1 for i in all_issues if i["severity"] == "error")
    warnings = sum(1 for i in all_issues if i["severity"] == "warning")
    infos = len(info_items)

    print(f"{BOLD}{'=' * 70}{RESET}")
    print(f"{BOLD}MkDocs Audit Summary{RESET}")
    print(f"{BOLD}{'=' * 70}{RESET}\n")

    print(f"  {RED}Errors:   {errors}{RESET}")
    print(f"  {YELLOW}Warnings: {warnings}{RESET}")
    if infos:
        print(f"  {CYAN}Info:     {infos}{RESET}")
    print(f"  Total:    {len(all_issues)}\n")

    # Print by category
    category_labels = {
        "commented-mermaid": "Mermaid Diagrams in Comments",
        "empty-mermaid": "Empty Mermaid Blocks",
        "invalid-mermaid-type": "Invalid Mermaid Diagram Type",
        "unbalanced-subgraph": "Unbalanced Subgraph/End",
        "wrong-fence": "Wrong Fence Syntax",
        "tilde-fence-mermaid": "Tilde Fence Mermaid",
        "missing-image": "Missing Image Files",
        "broken-link": "Broken Internal Links",
        "missing-nav-file": "Missing Nav Files (mkdocs.yml)",
    }

    severity_color = {"error": RED, "warning": YELLOW, "info": CYAN}

    for cat, issues in sorted(categories.items()):
        label = category_labels.get(cat, cat)
        # Use the highest severity in the group for the header color
        severities = {i["severity"] for i in issues}
        if "error" in severities:
            color = RED
        elif "warning" in severities:
            color = YELLOW
        else:
            color = CYAN
        print(f"{BOLD}{color}{label} ({len(issues)}){RESET}")
        print(f"  {'-' * 60}")
        for issue in sorted(issues, key=lambda i: (i["file"], i["line"])):
            tag = severity_color.get(issue["severity"], "")
            print(f"  {tag}{issue['file']}:{issue['line']}{RESET}")
            print(f"    {tag}{issue['message']}{RESET}")
        print()

    if not actionable:
        print(f"{GREEN}All issues are informational — no action required.{RESET}")
        return 0

    return 1 if errors > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
