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
import os
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

    The second alternative admits the same navigation in a path's INTERIOR
    (``docs/../archive/x`` — self-review round two, finding J), where the
    segment-start lookbehind can't see it because a ``.`` is off-limits
    character. It requires TWO dots after the separator on purpose: ``../``
    climbs back to the tree root, so that path really is the retired tree,
    while ``docs/./archive/x`` normalizes to ``docs/archive/x`` — a different
    entry's directory — and must stay silent here. A reviewer's proposed
    separator-lookbehind form (zero-to-two dots after ``[ \\s(/]``) was
    measured and rejected: with zero dots allowed it
    degrades to bare ``/archive`` after any separator and re-opens the
    mid-path collision class the anchor exists to close (it fired on
    ``site/archive/y`` and ``docs/build/archive/x``). Pinned in
    ``test_selftest_discriminates`` (fixture lines 8-11).

    Same lesson as the list header's declared-alias rule, one level down: that
    rule refused to derive ``ci.yml`` from ``docker-compose.ci.yml`` because a
    derived term collides with a real name. A derived *substring* collides the
    same way. Pinned both directions in ``test_selftest_discriminates``.
    """
    return re.compile(
        r"(?:(?<![A-Za-z0-9._\-/])(?:\.{0,2}/)?|(?<=/)\.\./)" + re.escape(term)
    )


def _entry_terms(entry: RetiredEntry) -> tuple[str, ...]:
    """The literal strings this entry can name a line with — ONE source of truth.

    Both the per-line matcher and the prefilter's alternation are built here, so
    the prefilter cannot drift from what the matcher actually tests. That matters
    more than it looks: the prefilter's whole soundness argument is "every string
    ``_names`` can test occurs in the line literally, so a file containing none of
    them cannot match". Stated as prose over two independently-written term
    lists, that argument is a maintenance hazard wearing a comment — add an alias
    form, or start testing a derived basename, on one side only, and the
    prefilter begins silencing real violations while every test still passes.
    Sharing this function turns it into a structural property.

    A DIRECTORY entry contributes exactly one term, its path, because
    ``_directory_term`` interpolates ``re.escape(term)`` verbatim: the anchor
    restricts WHERE the term may appear, never whether it must appear.
    """
    if entry.path.endswith("/"):
        return (entry.path,)
    base = entry.path.rsplit("/", 1)[-1]
    head = (entry.path,) if base == entry.path else (entry.path, base)
    return head + entry.aliases


def _names(entry: RetiredEntry, line: str) -> bool:
    """Does this line name the entry — by path, basename, or declared alias?"""
    if entry.path.endswith("/"):
        # directory entry: path-anchored term only (a bare word is not a path)
        return bool(_directory_term(entry.path).search(line))
    return any(term in line for term in _entry_terms(entry))


def _matchable_terms(retired: list[RetiredEntry]) -> tuple[str, ...]:
    """Every literal string any entry can test, deduped, in one fixed order.

    The per-line work costs ``lines x entries`` substring tests; this tuple
    collapses that to one alternation per file, which is what makes
    ``find_violations`` affordable enough to keep running twice per leg (O3.8).
    Terms come from ``_entry_terms``, the same source ``_names`` reads from, so
    coverage is by construction rather than by two lists agreeing.

    Neither dedup nor order changes a finding: the prefilter asks only whether
    SOME term occurs, and existence cannot depend on alternation order
    (``finditer`` tries every alternative at every position, so a term written
    anywhere in the line is found whatever its rank in the pattern) — while the
    per-entry loop still decides which entry fired on which line. The sort exists
    so the compiled pattern is a function of the term SET rather of the order the
    list file happens to be written in — which is what lets
    ``test_prefilter_skips_only_files_that_cannot_match`` pin the tuple by
    reversing the entries and requiring the same result. A term list that stops
    covering ``_names`` is the one edit here that could silence a violation;
    ``_entry_terms`` makes the two read one source, and that test's corpus checks
    the agreement file by file rather than trusting the comment.
    """
    terms: list[str] = []
    for entry in retired:
        terms.extend(_entry_terms(entry))
    return tuple(sorted(dict.fromkeys(terms), key=lambda t: (-len(t), t)))


@cache
def _terms_pattern(terms: tuple[str, ...]) -> re.Pattern[str]:
    """One alternation over ``_matchable_terms``, for the per-FILE prefilter.

    Cached on the term tuple. Every term reaches the pattern through
    ``re.escape``, so none can be read as syntax: a ``|`` inside a retired path
    matches literally instead of splitting the alternation. (An empty term would
    match every line — over-inclusive, therefore harmless, and unreachable:
    ``read_retired_paths`` drops blank entries.)
    """
    return re.compile("|".join(re.escape(term) for term in terms))


def _is_excluded_file(rel: str) -> bool:
    if rel in EXCLUDED_FILES:
        return True
    if rel.startswith("docs/goal-prompt-") and rel.endswith(".txt"):
        return True
    return any(rel.startswith(prefix) for prefix in EXCLUDED_PREFIXES)


def iter_scanned_files(root: Path):
    """Yield repo-relative paths of every file the gate reads.

    Prunes skipped directories while descending, rather than collecting the
    whole tree and filtering afterwards. The old shape called ``rglob("*")``,
    sorted the whole result, stat'd every entry, and only then ran its
    ``SKIP_DIR_NAMES`` / ``_is_excluded_file`` filter in Python — so it paid
    that filter on all 150 350 entries to keep 7 683. Same process, three reps
    interleaved, identical output every rep: old 5.56s / 5.50s / 5.59s against
    0.17s / 0.17s / 0.16s here. Where the old cost actually sits (each measured
    over this tree): a bare ``rglob`` walk is 0.28s, ``sorted(rglob)`` by ``Path``
    tuple adds ~0.55s, ``+is_file()`` reaches ~1.2s — and the full old pipeline
    is 5.5s. The ~4.3s gap is the per-entry Python filter (two ``relative_to``
    calls, ``.parts[:-1]``, ``as_posix``, ``_is_excluded_file``) that pruning
    during descent never runs. It is the filter, not the stat, not the walk.

    Two properties are preserved deliberately, and both are measured rather
    than asserted in prose:

    *MEMBERSHIP.* ``os.walk(followlinks=False)`` (the default) gives the same
    answers as ``rglob`` + ``is_file()`` — it neither descends a symlinked
    directory nor treats a dangling symlink as prose — and pruning a directory
    only ever drops files the old filter dropped too. Checked at both depths,
    against a file named like a skip directory, and over record-tree prefixes by
    ``test_walk_pruning_is_behaviour_preserving``, which carries the old
    traversal verbatim as an oracle.

    *ORDER.* Findings are appended in scan order, so a reshuffled traversal
    would silently reorder every multi-finding report a reader sees. ``os.walk``
    emits a directory's own files BEFORE its children; the shipped shape sorted
    the entire tree at once, which interleaves a directory's contents at the
    directory's name position (``aaa/inside.md`` before ``zzz.md``, where walk
    yields ``zzz.md`` first). So the pruned files are collected and sorted by
    ``Path`` — the comparator ``sorted(rglob(...))`` used, which is per-component
    and so differs from a plain posix-string sort (``.claude.md`` vs ``.claude/``)
    — before anything is yielded. Sorting a superset that included directories
    could not change file order anyway, so files alone reproduce it exactly.
    """
    root = Path(root)
    found: list[Path] = []
    for dir_path, dir_names, file_names in os.walk(root):
        base = Path(dir_path)
        rel_dir = "" if base == root else f"{base.relative_to(root).as_posix()}/"
        dir_names[:] = [
            name
            for name in dir_names
            if name not in SKIP_DIR_NAMES and not _is_excluded_file(f"{rel_dir}{name}/")
        ]
        for name in file_names:
            path = base / name
            # A dangling symlink lands in file_names; is_file() is False for it,
            # exactly as for the old shape, so it stays out of the prose scan
            # while the existence pass catches it via is_symlink().
            if path.is_file():
                found.append(path)
    for path in sorted(found):
        rel = path.relative_to(root).as_posix()
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

    terms = _matchable_terms(retired)
    finder = _terms_pattern(terms).finditer if terms else None

    for rel, path in iter_scanned_files(root):
        text = _read_prose(path)
        if text is None:
            continue  # binary or unreadable — not prose
        # Prefilter, per FILE: if no term occurs anywhere in this file, no line
        # of it can match — the term list is built by _entry_terms, which _names
        # reads from too, so every string the matcher can test occurs in the line
        # literally, and the directory branch's anchored regex still requires the
        # term verbatim. The exemptions only ever SKIP lines
        # (dated tags, string groups), so a file with no term has nothing left
        # to skip; there is no exemption-shaped false negative to lose here.
        # The per-entry loop below still runs unchanged on every file that DOES
        # contain a term, so which entry fired and what the line said are
        # decided by the shipped matcher, not by this shortcut.
        if finder is not None and next(finder(text), None) is None:
            continue
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


# Both scan tests carry a 30s mark (owner ruling 141; the suite's default
# timeout is 5s). The number is the Done-when's own budget: in CI (job
# 114837162590, 359 items) test_no_living_reference_names_a_retired_path took
# 9.15s and test_retired_paths_are_gone 8.60s — 17.75s together, which is how
# O3.8's ≤30s target is proven met. Marking each test at 30s means either one
# alone can never creep past the whole target unnoticed: as the tree grows, a
# slow scan fails loudly by itself. (Locally the same pair measures ~1.8s; the
# prefilter's win is input-dependent — a tree where most files name a retired
# path gets almost no skipping and costs what it always cost — so a breach here
# is a signal to read the scan, not to raise the mark.)
@pytest.mark.timeout(30)  # CI-measured 8.60s (ruling 141); ~1.8s on a local tree
def test_retired_paths_are_gone() -> None:
    violations = [v for v in find_violations(REPO_ROOT) if v.endswith("retired path exists again")]
    assert not violations, "retired paths must stay gone:\n" + "\n".join(violations)


@pytest.mark.timeout(30)  # CI-measured 9.15s (ruling 141); see the pin above
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
        "Never ../openapi-archive/openapi.json.\n"  # 9 — prefix + tail stays silent
        # 10 — the dot-prefix in a path's INTERIOR (self-review round two, J):
        #      docs/../archive/x normalizes to the retired tree, and the
        #      segment-start lookbehind alone could not see it
        "Reach it via docs/../archive/x.\n"
        # 11 — one interior dot does NOT climb: docs/./archive/x is
        #      docs/archive/x, a different entry's directory. Guards the
        #      two-dot requirement (a \.{0,2} interior group would fire here).
        "Link docs/./archive/y elsewhere.\n",
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
    assert any(f.startswith("docs/terms.md:10:") for f in refs), refs  # interior ../ fires (J)
    assert not any(f.startswith("docs/terms.md:11:") for f in refs), refs  # interior ./ is the OTHER tree
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


def test_walk_pruning_is_behaviour_preserving(tmp_path: Path) -> None:
    """The pruned traversal scans exactly what the ``rglob``-and-filter shape did.

    O3.8 bounds the draw by pruning skipped directories on descent instead of
    rejecting them after ``stat``. Cheaper is not the claim — SAME is. Six ways a
    rewrite could silently change coverage, each pinned with a POSITIVE witness
    (the same content under a normal path must be found), because an assertion
    that nothing was scanned passes whether or not the instrument works:

    * symlinked directories — ``os.walk`` must not follow them (following one
      would scan files outside the tree the gate guards, and can loop);
    * skip-dir names at depth, which post-hoc filtering caught at any depth and
      a top-only prune would miss;
    * a KEPT file below the first level, without which a traversal that stops
      descending entirely below depth 1 satisfies every "must not be scanned"
      assertion above;
    * record-tree prefixes, pruned as directories now rather than filtered as
      strings;
    * a FILE whose name collides with a skip-dir name, which the shipped filter
      never excluded (it tests ancestor parts only);
    * dangling symlinks, skipped by the prose scan and caught by the existence
      pass — the two passes must not be fused.

    Ordering is pinned separately and non-vacuously (see the fixture's item 6):
    findings are appended in scan order, so a reshuffle reorders every report,
    and a walk that emits each directory as it reaches it differs from the
    shipped whole-tree sort whenever a directory sorts before a sibling file.
    """
    root = tmp_path / "repo"
    (root / "scripts").mkdir(parents=True)
    (root / "scripts" / "retired_paths.txt").write_text("gone.txt\n", encoding="utf-8")
    # positive control: a living reference at a plain path IS found
    (root / "live.md").write_text("open gone.txt\n", encoding="utf-8")
    # 1. skipped directory, nested deep — the reference must NOT be scanned
    deep = root / "pkg" / "node_modules" / "a" / "b"
    deep.mkdir(parents=True)
    (deep / "hidden.md").write_text("open gone.txt\n", encoding="utf-8")
    # 2. record-tree prefix — pruned as a directory
    (root / "docs" / "plans").mkdir(parents=True)
    (root / "docs" / "plans" / "rec.md").write_text("open gone.txt\n", encoding="utf-8")
    # 3. symlinked directory holding a reference: rglob never descended it, so
    #    the rewrite must not either (following it would scan OUTSIDE the tree
    #    the gate guards, and a self-loop would not terminate)
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "elsewhere.md").write_text("open gone.txt\n", encoding="utf-8")
    (root / "linkdir").symlink_to(outside)
    # 4. a FILE named like a skip-dir name is scanned, because the shipped
    #    filter tests ancestor parts only — pruning directories must not start
    #    rejecting file names (that asymmetry is the rewrite's easy over-prune).
    (root / "build").write_text("open gone.txt in a file named build\n", encoding="utf-8")
    # 5. dangling symlink: is_file() is False, so the prose scan skips it, while
    #    the EXISTENCE pass still catches the name via is_symlink.
    (root / "dangling.md").symlink_to(root / "no-such-file")
    # 6. a directory that sorts BEFORE a sibling file — the order case. The
    #    shipped shape sorted the whole tree, so ``aaa/inside.md`` precedes
    #    ``zzz.md``, while a walk that yields each directory as it reaches it
    #    emits ``zzz.md`` first (root files, then children). Without a directory
    #    earlier than a sibling file the two orders coincide, and the assertions
    #    below pass VACUOUSLY — which is how the first version of this rewrite
    #    passed here while reversing order on 73 of 400 generated trees.
    (root / "aaa").mkdir()
    (root / "aaa" / "inside.md").write_text("open gone.txt in aaa\n", encoding="utf-8")
    (root / "zzz.md").write_text("open gone.txt in zzz\n", encoding="utf-8")
    # 7. a KEPT file below the first level. The skipped-dir witnesses above are
    #    all files that must NOT be scanned, so a traversal that stops descending
    #    entirely below depth 1 — pruning too aggressively instead of pruning the
    #    skip names — still satisfies every one of those assertions. Depth is only
    #    pinned by something the scan must reach. (Found by mutation, not by
    #    reading: a top-level-only prune mutant survived this fixture until it
    #    was added.)
    deep_keep = root / "pkg" / "src" / "app"
    deep_keep.mkdir(parents=True)
    (deep_keep / "keep.md").write_text("open gone.txt nested\n", encoding="utf-8")
    # 8. the COMPARATOR case. ``Path`` order and posix-string order disagree
    #    exactly when a directory and a dashed sibling share a stem, because
    #    ``PurePath.__lt__`` compares component TUPLES (``(".claude","x")`` vs
    #    ``(".claude.md",)`` -> the directory wins) while a posix string compares
    #    the separator ``/`` (U+002F) against ``.`` (U+002E) -> the file wins.
    #    Every entry above sorts the same under both keys, so a rewrite to
    #    ``sorted(found, key=lambda p: p.as_posix())`` passed this fixture while
    #    moving 480 positions on the live tree. This pair is the witness.
    (root / ".claude").mkdir()
    (root / ".claude" / "settings.json").write_text("no retired terms here\n", encoding="utf-8")
    (root / ".claude.md").write_text("no retired terms here either\n", encoding="utf-8")
    gone = root / "gone.txt"
    gone.write_text("back\n", encoding="utf-8")

    def old_shape(base: Path) -> list[str]:
        """The pre-O3.8 traversal verbatim: collect everything, filter after.

        An oracle, not a restatement of the shipped code — the point is that the
        pruned walk agrees with what shipped, in membership AND order.
        """
        out = []
        for path in sorted(base.rglob("*")):
            if not path.is_file():
                continue
            rel = path.relative_to(base).as_posix()
            if any(part in SKIP_DIR_NAMES for part in path.relative_to(base).parts[:-1]):
                continue
            if _is_excluded_file(rel):
                continue
            out.append(rel)
        return out

    rels = [rel for rel, _ in iter_scanned_files(root)]
    assert "live.md" in rels, "positive control failed — nothing is being scanned"
    assert "build" in rels, rels  # file named like a skip dir is still read
    assert not any(r.endswith("hidden.md") for r in rels), rels
    assert not any(r.startswith("docs/plans/") for r in rels), rels
    assert not any("elsewhere" in r for r in rels), rels
    assert "dangling.md" not in rels, rels  # is_file() False — prose scan skips it
    # Membership AND order against the shipped shape. The oracle comparison
    # alone would not fail loudly if the two orders happened to agree, so the
    # interleaving is asserted positionally as well.
    assert rels == old_shape(root), (rels, old_shape(root))
    assert rels.index("aaa/inside.md") < rels.index("zzz.md"), rels

    findings = find_violations(root)
    assert any(f.startswith("gone.txt:0: retired path exists again") for f in findings), findings
    # Report order is scan order, so this list is meaningful as written: a
    # reshuffled traversal would reorder it and fail here.
    refs = [f.split(":")[0] for f in findings if ":0: " not in f]
    assert refs == [
        "aaa/inside.md", "build", "live.md", "pkg/src/app/keep.md", "zzz.md",
    ], findings

    # A DANGLING symlink whose NAME is a retired path flags even though the
    # prose scan skips it — the two passes must not be fused.
    gone.unlink()
    (root / "gone.txt").symlink_to(root / "no-such-target")
    findings = find_violations(root)
    assert any(f.startswith("gone.txt:0: retired path exists again") for f in findings), findings


def test_prefilter_skips_only_files_that_cannot_match(tmp_path: Path) -> None:
    """The per-file term prefilter never skips a file that could yield a finding.

    The argument is that every string ``_names`` can test occurs literally, so
    a file with no term anywhere cannot match. This CHECKS it over a whole
    fixture corpus instead of only asserting the outcome, in both directions:

    * no file the prefilter skips would have produced a finding (the direction
      that could hide a violation);
    * some files ARE skipped and some are kept, so the check is not vacuous;
    * over-inclusion is allowed and pinned: ``openapi-archive/`` contains the
      literal ``archive/`` so it reaches the per-entry loop, where the anchor
      rejects it — 0 findings, which is the safe failure mode.

    Four files are DRIFT witnesses rather than findings: the prefilter shares
    ``_entry_terms`` with the matcher, so coverage is structural today, but the
    matcher's COMPARISON is still editable — fold the case, fold the entry PATH
    against a folded line, or derive a stem the way the list header refuses to,
    and it starts naming strings the term list never contains, so the prefilter
    would skip files it matches. ``case.md`` (folded alias), ``casepath.md``
    (folded path), ``stemonly.md`` (derived stem) and ``deep.md`` (term below a
    200-char window) each name a retired path in exactly one of those shapes, so
    each edit trips the per-file assertion below instead of shipping silently.
    The first two are separate witnesses because the two foldings are different
    edits: folding the LINE while still testing the terms is caught by
    ``case.md``, while widening the matcher with ``entry.path.lower() in
    line.lower()`` — which no fixture file could previously witness — is caught
    only by ``casepath.md``. ``deep.md`` witnesses a prefilter that reads a
    PREFIX of each file. Matching is case-sensitive, path-literal and
    derivation-free today, and the whole file is read; that is pinned here as the
    boundary of the term vocabulary, not as a recommendation.

    Also pins the two mechanisms' edges: an empty list disables the prefilter
    outright (a direct call, since no real tree has an empty list), and a short
    term sharing a prefix with a long one must survive, or the prefilter would
    skip files that name only the short term.
    """
    (tmp_path / "scripts").mkdir()
    (tmp_path / "scripts" / "retired_paths.txt").write_text(
        "sub/gone.md ; ghost.yml\nsub/dir/\narchive/\na/long-name.txt\n", encoding="utf-8"
    )
    (tmp_path / "notes").mkdir()
    (tmp_path / "notes" / "clean.md").write_text(
        "No reference here at all, just prose about the gate.\n" * 3, encoding="utf-8"
    )
    (tmp_path / "notes" / "shadow.md").write_text(
        "Serve it with ghost.yml.\n", encoding="utf-8"  # declared alias only
    )
    (tmp_path / "notes" / "short.md").write_text("link long-name.txt here\n", encoding="utf-8")
    # literal substring of a retired term, but the anchor rejects it
    (tmp_path / "notes" / "tailonly.md").write_text(
        "Copy to openapi-archive/openapi.json\n", encoding="utf-8"
    )
    # drift witness 1: a case-folded mention. No term occurs literally (the
    # matcher is `term in line`, case-sensitive), so the prefilter skips it and
    # the loop must find nothing — until someone makes the matcher case-insensitive.
    (tmp_path / "notes" / "case.md").write_text(
        "Serve it with GHOST.YML and nothing else here.\n", encoding="utf-8"
    )
    # drift witness 2: a DERIVED-STEM mention. `long-name` is the stem of the term
    # `long-name.txt`, so it is not a term and not a container of one; the header's
    # "declared, never derived" rule is what keeps it silent.
    (tmp_path / "notes" / "stemonly.md").write_text(
        "Link the long-name file from here instead.\n", encoding="utf-8"
    )

    # drift witness 3: a term that occurs ONLY deep in the file. Every other
    # fixture file is short, so a prefilter that scanned a PREFIX of each file
    # (``finder(text[:200])``) agreed with the shipped one on all of them and
    # survived. This file's first 200+ chars name nothing; the violation is
    # below the horizon, so truncation silently skips a MATCHING file.
    filler = "This note is about the dashboard and the nightly backup routine. "
    (tmp_path / "notes" / "deep.md").write_text(
        filler * 4 + "Serve it with ghost.yml.\n", encoding="utf-8"
    )

    # drift witness 4: a CASE-FOLDED PATH mention. case.md folds the declared
    # ALIAS; nothing here folds the entry PATH, so a matcher widened to compare
    # ``entry.path.lower() in line.lower()`` — case-insensitive, and therefore
    # naming a string the term list never contains — survived the whole suite.
    (tmp_path / "notes" / "casepath.md").write_text(
        "Copy it onto A/LONG-NAME.TXT before shipping.\n", encoding="utf-8"
    )

    retired = read_retired_paths(tmp_path / "scripts" / "retired_paths.txt")
    terms = _matchable_terms(retired)
    finder = _terms_pattern(terms).finditer
    # Exact shape, written by executing the function rather than by reasoning
    # about it: this is what a `terms == sorted(terms, ...)` assertion CANNOT
    # catch, since any ascending-by-that-key return satisfies it, including one
    # that drops the basename or sorts shortest-first. `gone.md` is the basename
    # of `sub/gone.md` (so a matcher that stopped testing basenames would skip
    # files naming it), and `archive/` precedes `sub/dir/` at equal length (so a
    # key flip changes the compiled pattern).
    assert terms == (
        "a/long-name.txt", "long-name.txt", "sub/gone.md",
        "ghost.yml", "archive/", "sub/dir/", "gone.md",
    ), terms
    # And the ORDER of the list file must not change what gets compiled: dedup
    # plus the key sort makes the result a function of the term SET.
    assert _matchable_terms(list(reversed(retired))) == terms, terms
    assert len(terms) == len(set(terms)), terms  # deduped — a dup wastes the alternation

    skipped = kept = 0
    seen_skipped: set[str] = set()
    for rel, path in iter_scanned_files(tmp_path):
        text = _read_prose(path)
        if text is None:
            continue
        has_term = next(finder(text), None) is not None
        # the shipped per-entry loop, run on EVERY file, as the reference
        reference = [
            (lineno, entry.path)
            for lineno, line in enumerate(text.splitlines(), 1)
            for entry in retired
            if _names(entry, line)
        ]
        if not has_term:
            skipped += 1
            seen_skipped.add(rel)
            assert not reference, f"prefilter skipped a MATCHING file: {rel} {reference}"
        else:
            kept += 1
    assert skipped and kept, (skipped, kept)  # non-vacuous both ways
    # Three of the four drift witnesses must be SKIPPED, or they cannot witness
    # anything; deep.md is the fourth and must be FOUND (asserted below).
    assert {"notes/case.md", "notes/stemonly.md", "notes/casepath.md"} <= seen_skipped, seen_skipped
    # Vacuity guard for drift witness 3: no term may appear in its first 200
    # chars, or the file stops witnessing truncation and the test below passes
    # for the wrong reason. Measured, not assumed.
    deep = (tmp_path / "notes" / "deep.md").read_text(encoding="utf-8")
    firsts = [deep.index(t) for t in terms if t in deep]
    assert firsts and min(firsts) > 200, (min(firsts), terms)

    findings = find_violations(tmp_path)
    hit = {f.split(":")[0] for f in findings}
    # Set equality is the presence guard for deep.md — an extra
    # `any(f.startswith("notes/deep.md"))` would say nothing this does not, and
    # each redundant find_violations() here is another full-tree scan in a
    # package whose whole subject is scan cost.
    assert hit == {"notes/shadow.md", "notes/short.md", "notes/deep.md"}, findings
    assert not any("tailonly" in f for f in findings), findings  # anchor still wins
    assert not any("case.md" in f or "stemonly" in f for f in findings), findings

    # Empty list: prefilter disabled, nothing crashes, nothing found.
    empty = tmp_path / "scripts" / "empty.txt"
    empty.write_text("# nothing retired\n", encoding="utf-8")
    assert _matchable_terms(read_retired_paths(empty)) == ()
    assert find_violations(tmp_path, empty) == []


def test_cost_guards_are_still_in_the_source() -> None:
    """Pin the two optimisations that are BEHAVIOURALLY EQUIVALENT by design.

    Deleting the prefilter, pruning only at the root, or dropping the
    ``_is_excluded_file`` half of the directory prune all produce byte-identical
    output — that equivalence IS the soundness argument, so no fixture can see
    any of them: all three survived the whole behavioural battery. What they cost
    is the point of O3.8 — with the prefilter deleted the scan here measures
    26.0s instead of 1.9s on this tree. A wall-clock assert would be runner
    noise, so the guards are pinned against the source text, brittle by intent:
    whoever removes one edits this pin on purpose.

    The test is LAST and counts only the text BEFORE its own ``def``: the file
    being grepped is this file, so a needle written here also occurs here, and an
    uncut count would be satisfied by the pin itself after production moved.
    """
    # nosemgrep: path-traversal-open - reads this file's own path, not input
    src = Path(__file__).read_text(encoding="utf-8")
    src = src[: src.index("def test_cost_guards_are_still_in_the_source")]
    assert src.count(
        "        if finder is not None and next(finder(text), None) is None:\n"
        "            continue\n") == 1, "the per-file term prefilter was removed"
    assert src.count(
        '            if name not in SKIP_DIR_NAMES and not '
        '_is_excluded_file(f"{rel_dir}{name}/")') == 1, "the directory prune was loosened"


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
