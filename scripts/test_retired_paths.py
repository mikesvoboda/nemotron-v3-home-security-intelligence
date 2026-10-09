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
    relative doc links are written by basename (``ai-ghcr-deployment.md``) —
    or a term the list entry DECLARES after ``;``. Declared aliases exist
    because prose names composes by shorthand: living text wrote
    ``docker-compose.ghcr.yml`` as ``ghcr.yml``, which neither the full path
    nor the basename (which at the repo root IS the full path) can see. The
    alias is declared, never derived from the name: a derived stem is how
    ``docker-compose.ci.yml`` would grow the alias ``ci.yml`` and collide with
    ``.github/workflows/ci.yml`` (measured at #6907; ops-A review's other
    suggested shape, rejected for exactly this). An entry ending in ``/`` is a
    DIRECTORY: the path itself is the term, matched only where it begins a
    path — so text naming anything under it flags, an innocent word like ``dir``
    does not, and neither does a longer path that merely ends in the term
    (``openapi-archive/`` does not match a retired ``archive/``). The anchor is
    the same "declared, never derived" rule as the alias, one level down: a
    directory term is a path segment, not a substring (O1.5, UR-19).

What is NOT living text (records keep their references — the package says so:
"Dated plans and specs keep their references; they are history")
    - Path prefixes: ``docs/plans/``, ``docs/superpowers/``,
      ``docs/vss-integration/``, ``docs/uplevel/`` — plan, spec and
      program-record trees. ``docs/uplevel/`` includes this package's own text
      in ``30-ops.md``: a gate may not flag the order that executed it.
      ``docs/archive/`` and ``archive/`` are NOT here any more (O1.5, UR-19):
      they were record trees while they existed, and are now retired entries
      above, so an exemption for them would exempt the text that names them.
      Their own historical prose is preserved as a dated note in the file that
      mentioned them, not as a tree the scanner never looks at.
    - Files named ``docs/goal-prompt-*.txt`` — dated goal prompts, records.
    - ``scripts/retired_paths.txt`` and this file — the gate lists the paths.
    - ``.secrets.baseline`` — generated, and its keys are file paths by design.
    - In a ``.py`` file only: a line carrying a dated decision-log tag,
      ``[V 2026-09-28]`` style (``[word 2026-09-28]``) — the repo's convention
      for a dated finding in living code (``scripts/a5500_precheck.py`` uses it
      throughout). The exemption covers the whole string group when the group
      BEGINS with the tag: a record entry may wrap across lines (single- or
      triple-quoted), and the record is the entry, not its first line. A group
      ends at a blank line, so a living claim cannot be parked inside a tagged
      entry by string concatenation across whitespace (ops-A review on #6907:
      measured cost of the bound at this head — zero tagged groups span a
      blank line).

Deliberately narrow: an ordinary sentence with a date in it does NOT buy an
exemption — only the bracketed tag does, and in ``.py`` only: the tag exempts
the line it rides on anywhere in the file (comment or string — pinned at
``test_selftest_discriminates``), and the string-group exemption needs the tag
at the group's head. The tag exemption is Python-only on purpose: the
convention lives in Python decision logs, and a markdown author could
otherwise exempt a fresh install-path claim by typing a bracketed date — in
prose, records are the trees above, not any line with a date in it. (Cost of
the restriction, measured on this tree: zero lines — no non-``.py`` living
file carries a dated tag at all.)
Widening the exemptions is how a gate goes hollow;
``test_selftest_discriminates`` pins both directions.

Runs as pytest (wired into ci.yml's collection-sanity list, like several
sibling gate suites — its presence there is pinned by
``test_gate_is_wired_into_ci``, mirroring ``test_shard_retry_wiring.py``,
because a gate deletable from CI without a red is the silent-rot class
ci.yml itself rails against) and standalone, like the sibling gates through
the project venv:

    uv run python scripts/test_retired_paths.py   # exit 1 + findings, or exit 0 + OK line
"""

from __future__ import annotations

import io
import re
import sys
import tokenize
from functools import cache
from pathlib import Path, PurePosixPath
from typing import NamedTuple

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]

RETIRED_LIST = REPO_ROOT / "scripts" / "retired_paths.txt"

# Trees that are records by nature: plans, specs, program records.
#
# O1.5 (UR-19, 2026-10-09) removed "docs/archive/" and "archive/" from this
# tuple with the two trees themselves. They were listed as record trees while
# they held the retired reports; once the directories are deleted no scanned
# path can start with either prefix, so keeping them would be dead quarantine
# — and worse, the two trees are now RETIRED entries in retired_paths.txt, so
# an exclusion for them would exempt the very living text the retirement is
# meant to police. pyproject.toml's exclusion-ledger rule says the same of a
# dead ignore: only a human deleting both keeps the ledger honest.
EXCLUDED_PREFIXES = (
    "docs/plans/",
    "docs/superpowers/",
    "docs/vss-integration/",
    "docs/uplevel/",
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
# chars before the quote allowed; one to three quote chars, so a triple-quoted
# constant — the natural multi-line record shape — is exempt too, ops-A review
# on #6907). Such a group is one decision-log entry; the record is the entry,
# not its first line, so every line it spans is exempt.
DATED_STRING_OPEN_RE = re.compile(
    r"""^[A-Za-z]*["']{1,3}[ \t]*\[[A-Za-z][A-Za-z0-9.]{0,4} \d{4}-\d{2}-\d{2}\]"""
)


class RetiredEntry(NamedTuple):
    """One list line: the retired path, plus declared shorthand alias terms."""

    path: str
    aliases: tuple[str, ...] = ()


def dated_entry_lines(text: str) -> set[int]:
    """Lines covered by dated-tag string groups in Python source.

    Implicit concatenation (adjacent STRING fragments separated only by NL or
    comments) is one entry; the tag rides on the first fragment. A BLANK line
    ends the group: a bracketed concat may legally outlive the record, and an
    unbracketed one dies there anyway — parking a living claim past a blank
    line inside a tagged entry is the injection the bound closes (measured at
    this head: no real tagged entry spans a blank line, so the bound exempts
    nothing that is genuinely a record). The bound is measured on the source
    LINES, not on the NL tokens: inside open parens every physical newline —
    blank or not — tokenizes to an NL whose line is "\\n", so the tokens
    cannot tell a wrapped record from a gap. A file that will not tokenize
    yields no exemptions — the gate fails toward flagging.
    """
    try:
        tokens = list(tokenize.generate_tokens(io.StringIO(text).readline))
    except (tokenize.TokenError, IndentationError, SyntaxError, ValueError):
        return set()
    blank = {no for no, line in enumerate(text.splitlines(), 1) if not line.strip()}
    lines: set[int] = set()
    i = 0
    while i < len(tokens):
        if tokens[i].type != tokenize.STRING:
            i += 1
            continue
        group = [tokens[i]]
        j = i + 1
        while j < len(tokens) and tokens[j].type in (tokenize.NL, tokenize.COMMENT, tokenize.STRING):
            # a source line between the last fragment and this token that is
            # blank ends the record, wherever the parens are (see docstring)
            if any(no in blank for no in range(group[-1].end[0] + 1, tokens[j].start[0])):
                break  # blank line ends the entry — see docstring
            if tokens[j].type == tokenize.STRING:
                group.append(tokens[j])
            j += 1
        if DATED_STRING_OPEN_RE.match(group[0].string):
            for fragment in group:
                lines.update(range(fragment.start[0], fragment.end[0] + 1))
        i = j
    return lines


def read_retired_paths(list_path: Path) -> list[RetiredEntry]:
    """Entries from the list file: one per line, ``#`` comments, ``;`` aliases.

    ``docker-compose.ghcr.yml ; ghcr.yml`` declares the shorthand. Entries must
    stay inside the repo root — an absolute path or a ``..`` would resolve the
    existence check outside the tree it guards, and a gate that can be steered
    at ``/etc`` by a list edit is not a gate (ops-A review on #6907).
    """
    entries: list[RetiredEntry] = []
    for raw in list_path.read_text(encoding="utf-8").splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        path, _, alias_text = line.partition(";")
        path = path.strip()
        if not path:
            continue
        pure = PurePosixPath(path)
        if pure.is_absolute() or ".." in pure.parts:
            raise ValueError(f"retired-paths entry escapes the repo root: {path!r}")
        aliases = tuple(a.strip() for a in alias_text.split(",") if a.strip())
        entries.append(RetiredEntry(path, aliases))
    return entries


@cache
def _directory_term(term: str) -> re.Pattern[str]:
    """Compiled matcher for a directory entry's term: a path-anchored ``term``.

    A directory term is matched only where it begins a path, not inside a longer
    one. O1.5 (UR-19) supplies the reason it had to: retiring ``archive/`` as the
    list's first root-level directory entry would otherwise substring-match
    ``openapi-archive/`` — an unrelated CI artifact directory in
    ``docs.yml`` — because plain ``in`` cannot tell a path segment from the tail
    of one. Anchoring also keeps ``archive/`` from firing on a mention of
    ``docs/archive/``, which has its own entry.

    The optional ``\\.{0,2}/`` prefix admits the parent-relative and current-dir
    forms: ``../archive/x`` and ``/archive/x`` name the retired tree as plainly
    as ``archive/x`` does, and the self-review's probe (O1.5) showed the plain
    lookbehind let them through — the leading ``.`` or ``/`` is a path
    navigation, not part of a longer name, so anchoring must not read it as one.
    A prefix followed by a COLLIDING tail stays silent (``../openapi-archive/x``):
    the group is tried once, at the path start, and the term must follow it
    immediately.

    Same lesson as the list header's declared-alias rule, one level down: that
    rule refused to derive ``ci.yml`` from ``docker-compose.ci.yml`` because a
    derived term collides with a real name. A derived *substring* collides the
    same way. Pinned both directions in ``test_selftest_discriminates``.
    """
    return re.compile(r"(?<![A-Za-z0-9._\-/])(?:\.{0,2}/)?" + re.escape(term))


def _names(entry: RetiredEntry, line: str) -> bool:
    """Does this line name the entry — by path, basename, or declared alias?"""
    if entry.path.endswith("/"):
        # directory entry: path-anchored term only (a bare word is not a path)
        return bool(_directory_term(entry.path).search(line))
    base = entry.path.rsplit("/", 1)[-1]
    terms = (entry.path,) if base == entry.path else (entry.path, base)
    return any(term in line for term in terms + entry.aliases)


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


def _read_prose(path: Path) -> str | None:
    """Text of a file to scan, or None if it is binary.

    Binary is decided by a NUL in the head, not by UnicodeDecodeError:
    decoding with replacement means a living file whose encoding drifted
    (one latin-1 byte in a markdown doc) still gets scanned — the old
    silent skip was a hollowness a stray byte could exploit (ops-A review
    on #6907).
    """
    try:
        data = path.read_bytes()
    except OSError:
        return None
    if b"\x00" in data[:8192]:
        return None
    return data.decode("utf-8", errors="replace")


def find_violations(root: Path, list_path: Path | None = None) -> list[str]:
    """All findings under ``root``, as ``path:line: text`` strings.

    Includes existence violations ("retired path is back") for a list read from
    ``list_path`` (default: the repo's own list under ``root``).
    """
    list_path = list_path or root / "scripts" / "retired_paths.txt"
    retired = read_retired_paths(list_path)
    findings: list[str] = []

    for entry in retired:
        # is_symlink, not just exists: a DANGLING symlink named like the retired
        # path is a half-reverted resurrection, and exists() follows it to False
        # (self-review on #6907).
        candidate = root / entry.path
        if candidate.is_symlink() or candidate.exists():
            findings.append(f"{entry.path}:0: retired path exists again")

    for rel, path in iter_scanned_files(root):
        text = _read_prose(path)
        if text is None:
            continue  # binary or unreadable — not prose
        entry_lines = dated_entry_lines(text) if rel.endswith(".py") else set()
        for lineno, line in enumerate(text.splitlines(), 1):
            # The dated tag exempts a line in .py only — the convention lives in
            # Python decision logs; a prose author must not buy an exemption by
            # typing a bracketed date (self-review on #6907). Records in prose are
            # the record TREES above, not any dated line.
            if lineno in entry_lines or (rel.endswith(".py") and DATED_TAG_RE.search(line)):
                continue  # dated decision-log line — a record, not a claim
            for entry in retired:
                if _names(entry, line):
                    findings.append(f"{rel}:{lineno}: {entry.path} — {line.strip()[:160]}")
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


def test_gate_is_wired_into_ci() -> None:
    """Self-pin, mirroring test_shard_retry_wiring.py's last check: a gate that
    can be deleted from its only CI invocation without a red is already dead."""
    ci = (REPO_ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    assert "scripts/test_retired_paths.py" in ci, "this gate must ride ci.yml's collection-sanity list"


def test_list_entries_stay_inside_the_repo(tmp_path: Path) -> None:
    """An absolute or ``..`` entry would point the existence check outside the
    tree; it raises at read time, loudly, instead of resolving silently."""
    bad = tmp_path / "retired_paths.txt"
    for entry in ("/etc/passwd", "../outside.txt", "ok/../../escape.txt"):
        bad.write_text(entry + "\n", encoding="utf-8")
        with pytest.raises(ValueError, match="escapes the repo root"):
            read_retired_paths(bad)


def test_selftest_discriminates(tmp_path: Path) -> None:
    """The gate catches living references AND a resurrected path, and exempts
    exactly the two record kinds and nothing else.

    The fixture list exercises every term shape the parser knows: a root file
    (basename branch dead — the alias term is where its teeth would be), a
    nested file (basename branch alive), a declared alias, and a directory
    entry. Each shape is pinned both ways — flagged when named, silent when
    only a substring of it appears in prose — because a term branch nothing
    exercises is a mutation waiting to pass (ops-A review on #6907: the old
    fixture's only entry was root-level, so deleting the basename branch kept
    the self-test green).
    """
    (tmp_path / "scripts").mkdir()
    (tmp_path / "scripts" / "retired_paths.txt").write_text(
        "gone.txt\n"
        "sub/gone.md ; ghost.yml\n"
        "sub/dir/\n"
        "archive/\n",
        encoding="utf-8",
    )
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "live.md").write_text(
        "Run it with gone.txt today.\n"
        "Deploy it with gone.txt per [V 2026-09-28].\n",  # dated tag in prose: NOT a record
        encoding="utf-8",
    )
    (tmp_path / "docs" / "terms.md").write_text(
        "Serve it with ghost.yml today.\n"  # 1 — declared alias: living text
        "A ghost sighting is not a reference.\n"  # 2 — alias is a filename term, not the word
        "Link to gone.md by basename.\n"  # 3 — basename branch of sub/gone.md
        "The dir variable stays out of the list.\n"  # 4 — bare word vs directory term
        "Nothing under sub/dir/ is innocent.\n"  # 5 — directory entry's term
        "Copy it into openapi-archive/openapi.json.\n"  # 6 — longer path ending in
        #     the term is NOT the term: the anchor (O1.5, UR-19 — measured in the
        #     real tree: docs.yml's openapi-archive/ is the only live collision)
        "Recover it under archive/ whenever.\n"  # 7 — directory entry at a segment start
        "Mount it from ../archive/ and ./archive/ too.\n"  # 8 — parent/cur-dir prefixes name
        #     the retired tree as plainly (the self-review's probe, O1.5: the plain
        #     lookbehind let these through; the optional \.{0,2}/ group catches them)
        "Never ../openapi-archive/openapi.json.\n",  # 9 — prefix + colliding tail stays silent
        encoding="utf-8",
    )
    (tmp_path / "docs" / "weird.md").write_bytes(b"caf\xe9 gone.txt lives in latin-1\n")
    (tmp_path / "scripts" / "notes.py").write_text(
        '# [V 2026-09-28] gone.txt used to hold the list\n'  # 1 tagged comment: exempt
        "# gone.txt mention with no tag\n"  # 2 living: flagged
        'ENTRY = (\n'
        '    "[V 2026-09-27] first line of the record\\n"\n'  # 4 exempt (group head)
        '    "second line names gone.txt and belongs to the record\\n"\n'  # 5 exempt
        ')\n'
        'LIVE = (\n'
        '    "no tag here\\n"\n'
        '    "and gone.txt on a continuation line is a living claim\\n"\n'  # 9 flagged
        ')\n'
        'TQ = """[V 2026-09-26] a triple-quoted record opens with the tag\n'  # 11 head
        'and its second line names gone.txt inside the record\n'  # 12 exempt
        '"""\n'  # 13
        'PARKED = ("[V 2026-09-25] record head\\n"\n'  # 14 exempt (head)
        '\n'  # 15 the blank ends the record
        '    "gone.txt parked past a blank line is a living claim")\n',  # 16 flagged
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
    assert any(f.startswith("docs/live.md:1:") for f in refs), refs
    assert any(f.startswith("docs/live.md:2:") for f in refs), refs
    assert any(f.startswith("scripts/notes.py:2:") for f in refs), refs
    assert any(f.startswith("scripts/notes.py:9:") for f in refs), refs
    assert not any(f.startswith("scripts/notes.py:1:") for f in refs), refs
    assert not any(f.startswith("scripts/notes.py:4:") for f in refs), refs
    assert not any(f.startswith("scripts/notes.py:5:") for f in refs), refs
    assert not any(f.startswith("docs/plans/") for f in refs), refs

    # Term shapes, each pinned against the mutation that would hollow it.
    assert any(f.startswith("docs/terms.md:1:") for f in refs), refs  # declared alias
    assert not any(f.startswith("docs/terms.md:2:") for f in refs), refs  # not the bare word
    assert any(f.startswith("docs/terms.md:3:") for f in refs), refs  # basename branch alive
    assert not any(f.startswith("docs/terms.md:4:") for f in refs), refs  # dir term path-anchored
    assert any(f.startswith("docs/terms.md:5:") for f in refs), refs  # directory flags contents
    assert not any(f.startswith("docs/terms.md:6:") for f in refs), refs  # openapi-archive/ survives
    assert any(f.startswith("docs/terms.md:7:") for f in refs), refs  # root dir entry alive
    assert any(f.startswith("docs/terms.md:8:") for f in refs), refs  # ../ ./ prefixes fire
    assert not any(f.startswith("docs/terms.md:9:") for f in refs), refs  # prefix+tail survives
    assert any(f.startswith("docs/weird.md:1:") for f in refs), refs  # encoding drift hides nothing

    # Python record shapes: a triple-quoted tagged record (lines 11-13) is
    # exempt whole, including its second line naming gone.txt; a claim parked
    # past a blank line inside a tagged parenthesized concat (head 14, blank 15,
    # claim 16) is NOT exempt on the far side of the blank — the bound the
    # unbounded group walk used to waive (ops-A injection demo on #6907).
    assert not any(f.startswith("scripts/notes.py:11:") for f in refs), refs
    assert not any(f.startswith("scripts/notes.py:12:") for f in refs), refs
    assert not any(f.startswith("scripts/notes.py:14:") for f in refs), refs
    assert any(f.startswith("scripts/notes.py:16:") for f in refs), refs

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
    try:
        findings = find_violations(REPO_ROOT)
    except ValueError as exc:  # list entry escapes the root — fix the list
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1
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
