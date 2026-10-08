#!/usr/bin/env python3
"""Retired-paths gate (O1.2, UR-17): listed paths stay gone, and living text stops naming them.

``scripts/retired_paths.txt`` lists repo-relative paths deleted on purpose. This
gate fails when (a) a listed path exists again, or (b) a LIVING doc, workflow,
hook, script or test names one. It is the guard against the failure mode this
package retires: ``docs/operator/ai-ghcr-deployment.md`` advertised the ghcr
compose install path as an install path after that compose file grew no
``ai-vlm`` service — docs describing a path the product no longer ships.

What counts as a reference
    A line containing the retired path, or (for a file path) its basename —
    relative doc links are written by basename (``ai-ghcr-deployment.md``).

What is NOT living text (records keep their references — the package says so:
"Dated plans and specs keep their references; they are history")
    - Path prefixes: ``docs/plans/``, ``docs/superpowers/``,
      ``docs/vss-integration/``, ``docs/uplevel/``, ``docs/archive/``,
      ``archive/`` — plan, spec, program-record and archive trees.
      ``docs/uplevel/`` includes this package's own text in ``30-ops.md``:
      a gate may not flag the order that executed it.
    - Files named ``docs/goal-prompt-*.txt`` — dated goal prompts, records.
    - ``scripts/retired_paths.txt`` and this file — the gate lists the paths.
    - ``.secrets.baseline`` — generated, and its keys are file paths by design.
    - In a ``.py`` file only: a line carrying a dated decision-log tag,
      ``[V 2026-09-28]`` style (``[word 2026-09-28]``) — the repo's convention
      for a dated finding in living code (``scripts/a5500_precheck.py`` uses it
      throughout). The exemption covers the whole string constant when the
      constant BEGINS with the tag: a record entry may wrap across lines, and
      the record is the entry, not its first line.

Deliberately narrow: an ordinary sentence with a date in it does NOT buy an
exemption — only the bracketed tag does, and in Python only at the head of a
string. The tag exemption is Python-only on purpose: the convention lives in
Python decision logs, and a markdown author could otherwise exempt a fresh
install-path claim by typing a bracketed date — in prose, records are the trees
above, not any line with a date in it. (Cost of the restriction, measured on
this tree: zero lines — no non-``.py`` living file carries a dated tag at all.)
Widening the exemptions is how a gate goes hollow;
``test_selftest_discriminates`` pins both directions.

Runs as pytest (wired into ci.yml's collection-sanity list, like every other
``scripts/test_*.py`` gate suite) and standalone, like the sibling gates
through the project venv:

    uv run python scripts/test_retired_paths.py   # exit 1 + findings, or exit 0 + OK line
"""

from __future__ import annotations

import io
import re
import sys
import tokenize
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]

RETIRED_LIST = REPO_ROOT / "scripts" / "retired_paths.txt"

# Trees that are records by nature: plans, specs, program records, archives.
EXCLUDED_PREFIXES = (
    "docs/plans/",
    "docs/superpowers/",
    "docs/vss-integration/",
    "docs/uplevel/",
    "docs/archive/",
    "archive/",
)

# Directory names skipped at any depth (VCS, deps, caches, build output).
SKIP_DIR_NAMES = {
    ".git",
    "node_modules",
    ".venv",
    "venv",
    "__pycache__",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    "dist",
    "build",
    "htmlcov",
    "coverage",
    ".next",
}

# Files exempt by exact repo-relative path (reasons in the module docstring).
EXCLUDED_FILES = {
    "scripts/retired_paths.txt",
    "scripts/test_retired_paths.py",
    ".secrets.baseline",
}

# Dated decision-log tag: [V 2026-09-28], [P 2026-10-03] — short word, ISO date.
DATED_TAG_RE = re.compile(r"\[[A-Za-z][A-Za-z0-9.]{0,4} \d{4}-\d{2}-\d{2}\]")
# A .py string group whose FIRST fragment opens with a dated tag (f/r prefix
# chars before the quote allowed). Such a group is one decision-log entry; the
# record is the entry, not its first line, so every line it spans is exempt.
DATED_STRING_OPEN_RE = re.compile(r"""^[A-Za-z]*["'][ \t]*\[[A-Za-z][A-Za-z0-9.]{0,4} \d{4}-\d{2}-\d{2}\]""")


def dated_entry_lines(text: str) -> set[int]:
    """Lines covered by dated-tag string groups in Python source.

    Implicit concatenation (adjacent STRING fragments separated only by NL or
    comments) is one entry; the tag rides on the first fragment. A file that
    will not tokenize yields no exemptions — the gate fails toward flagging.
    """
    try:
        tokens = list(tokenize.generate_tokens(io.StringIO(text).readline))
    except (tokenize.TokenError, IndentationError, SyntaxError, ValueError):
        return set()
    lines: set[int] = set()
    i = 0
    while i < len(tokens):
        if tokens[i].type != tokenize.STRING:
            i += 1
            continue
        group = [tokens[i]]
        j = i + 1
        while j < len(tokens) and tokens[j].type in (tokenize.NL, tokenize.COMMENT, tokenize.STRING):
            if tokens[j].type == tokenize.STRING:
                group.append(tokens[j])
            j += 1
        if DATED_STRING_OPEN_RE.match(group[0].string):
            for fragment in group:
                lines.update(range(fragment.start[0], fragment.end[0] + 1))
        i = j
    return lines


def read_retired_paths(list_path: Path) -> list[str]:
    """Repo-relative paths from the list file: one per line, ``#`` comments."""
    paths = []
    for raw in list_path.read_text(encoding="utf-8").splitlines():
        line = raw.split("#", 1)[0].strip()
        if line:
            paths.append(line.rstrip("/"))
    return paths


def _search_terms(retired_path: str) -> tuple[str, ...]:
    """A line mentioning the path or (for files) its basename is a reference."""
    if retired_path.endswith("/"):
        return (retired_path,)
    base = retired_path.rsplit("/", 1)[-1]
    return (retired_path,) if base == retired_path else (retired_path, base)


def _is_excluded_file(rel: str) -> bool:
    if rel in EXCLUDED_FILES:
        return True
    if rel.startswith("docs/goal-prompt-") and rel.endswith(".txt"):
        return True
    return any(rel.startswith(prefix) for prefix in EXCLUDED_PREFIXES)


def iter_scanned_files(root: Path):
    """Yield repo-relative paths of every file the gate reads."""
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(root).as_posix()
        if any(part in SKIP_DIR_NAMES for part in path.relative_to(root).parts[:-1]):
            continue
        if _is_excluded_file(rel):
            continue
        yield rel, path


def find_violations(root: Path, list_path: Path | None = None) -> list[str]:
    """All findings under ``root``, as ``path:line: text`` strings.

    Includes existence violations ("retired path is back") for a list read from
    ``list_path`` (default: the repo's own list under ``root``).
    """
    list_path = list_path or root / "scripts" / "retired_paths.txt"
    retired = read_retired_paths(list_path)
    findings: list[str] = []

    for retired_path in retired:
        # is_symlink, not just exists: a DANGLING symlink named like the retired
        # path is a half-reverted resurrection, and exists() follows it to False
        # (self-review on #6907).
        candidate = root / retired_path
        if candidate.is_symlink() or candidate.exists():
            findings.append(f"{retired_path}:0: retired path exists again")

    for rel, path in iter_scanned_files(root):
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue  # binary or unreadable — not prose
        entry_lines = dated_entry_lines(text) if rel.endswith(".py") else set()
        for lineno, line in enumerate(text.splitlines(), 1):
            # The dated tag exempts a line in .py only — the convention lives in
            # Python decision logs; a prose author must not buy an exemption by
            # typing a bracketed date (self-review on #6907). Records in prose are
            # the record TREES above, not any dated line.
            if lineno in entry_lines or (rel.endswith(".py") and DATED_TAG_RE.search(line)):
                continue  # dated decision-log line — a record, not a claim
            for retired_path in retired:
                if any(term in line for term in _search_terms(retired_path)):
                    findings.append(f"{rel}:{lineno}: {retired_path} — {line.strip()[:160]}")
    return findings


# ---------------------------------------------------------------- pytest face

def test_retired_list_is_committed_and_nonempty() -> None:
    assert RETIRED_LIST.is_file(), "scripts/retired_paths.txt must be committed"
    assert read_retired_paths(RETIRED_LIST), "the retired-paths list is empty — a gate with nothing on it"


@pytest.mark.timeout(120)  # full-tree scan ~11s; the suite's default timeout is 5s
def test_retired_paths_are_gone() -> None:
    violations = [v for v in find_violations(REPO_ROOT) if v.endswith("retired path exists again")]
    assert not violations, "retired paths must stay gone:\n" + "\n".join(violations)


@pytest.mark.timeout(120)  # same full-tree scan; see the pin above
def test_no_living_reference_names_a_retired_path() -> None:
    violations = [v for v in find_violations(REPO_ROOT) if not v.endswith("retired path exists again")]
    assert not violations, (
        "living text names a retired path — rewrite it (or record it with a\n"
        "dated [V YYYY-MM-DD] tag if it is history):\n" + "\n".join(violations)
    )


def test_selftest_discriminates(tmp_path: Path) -> None:
    """The gate catches living references AND a resurrected path, and exempts
    exactly the two record kinds and nothing else."""
    (tmp_path / "scripts").mkdir()
    (tmp_path / "scripts" / "retired_paths.txt").write_text("gone.txt\n", encoding="utf-8")
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "live.md").write_text(
        "Run it with gone.txt today.\n"
        "Deploy it with gone.txt per [V 2026-09-28].\n",  # dated tag in prose: NOT a record
        encoding="utf-8",
    )
    (tmp_path / "scripts" / "notes.py").write_text(
        '# [V 2026-09-28] gone.txt used to hold the list\n'
        "# gone.txt mention with no tag\n"
        'ENTRY = (\n'
        '    "[V 2026-09-27] first line of the record\\n"\n'
        '    "second line names gone.txt and belongs to the record\\n"\n'
        ')\n'
        'LIVE = (\n'
        '    "no tag here\\n"\n'
        '    "and gone.txt on a continuation line is a living claim\\n"\n'
        ')\n',
        encoding="utf-8",
    )
    (tmp_path / "docs" / "plans").mkdir()
    (tmp_path / "docs" / "plans" / "2026-09-28-rec.md").write_text("gone.txt was deleted.\n", encoding="utf-8")

    # Path resurrected: existence violation is reported.
    (tmp_path / "gone.txt").write_text("i am back\n", encoding="utf-8")
    findings = find_violations(tmp_path)
    assert any(f.startswith("gone.txt:0: retired path exists again") for f in findings)

    # Living reference caught; dated-tag and plan-dir mentions exempt; the
    # untagged second line of notes.py caught alongside the doc. The dated
    # markdown line (line 2 of live.md) is caught too: prose buys no exemption.
    refs = [f for f in findings if not f.startswith("gone.txt:0:")]
    assert any(f.startswith("docs/live.md:1:") for f in findings), findings
    assert any(f.startswith("docs/live.md:2:") for f in findings), findings
    assert any(f.startswith("scripts/notes.py:2:") for f in findings), findings
    assert any(f.startswith("scripts/notes.py:9:") for f in findings), findings
    assert not any(f.startswith("scripts/notes.py:1:") for f in findings), findings
    assert not any(f.startswith("scripts/notes.py:4:") for f in findings), findings
    assert not any(f.startswith("scripts/notes.py:5:") for f in findings), findings
    assert not any(f.startswith("docs/plans/") for f in findings), findings

    # Path removed again: existence violation goes, references remain.
    (tmp_path / "gone.txt").unlink()
    findings = find_violations(tmp_path)
    assert not any("exists again" in f for f in findings), findings
    assert any(f.startswith("docs/live.md:1:") for f in findings), findings

    # A DANGLING symlink resurrecting the name flags too — exists() alone
    # follows it to False and the gate would call the path gone.
    (tmp_path / "gone.txt").symlink_to(tmp_path / "nowhere-at-all")
    findings = find_violations(tmp_path)
    assert any(f.startswith("gone.txt:0: retired path exists again") for f in findings), findings


# --------------------------------------------------------------- standalone

def main() -> int:
    if not RETIRED_LIST.is_file():
        print("FAIL: scripts/retired_paths.txt is missing", file=sys.stderr)
        return 1
    findings = find_violations(REPO_ROOT)
    if findings:
        print(f"FAIL: {len(findings)} retired-path violation(s):", file=sys.stderr)
        for finding in findings:
            print(f"  {finding}", file=sys.stderr)
        return 1
    count = len(read_retired_paths(RETIRED_LIST))
    print(f"OK: {count} retired path(s) stay gone; no living text names one")
    return 0


if __name__ == "__main__":
    sys.exit(main())
