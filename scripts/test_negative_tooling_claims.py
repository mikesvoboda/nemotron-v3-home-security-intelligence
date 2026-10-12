#!/usr/bin/env python3
"""Negative tooling claims in docs are executable claims (DOCS-NJT).

A sentence like "X runs in **no** workflow" is not a style choice, it is a
command nobody ran. It is also the highest-consequence claim shape in `docs/`,
because its function is to tell the next reader to STOP LOOKING: a false "no CI
job checks this" is how a blind gate stays blind, and how a wired gate gets
re-wired out. The one this package caught shipped wrapped in its own disproof —
`docs/architecture/ai-pipeline-current-state.md` asserted `scripts/validate_docs`
"runs in **no** workflow either" and printed the very command that refutes it
(`grep -rn validate_docs .github/workflows/`) twenty words later, in the same
sentence. Both halves arrived in the SAME commit (`e40d69f56`, 2026-10-02), and
nothing in CI executed the command: the sentence was proofread for grammar and
the command for plausibility, which is exactly how a claim and its disproof stay
mutually invisible.

The class is not hypothetical, and it is not one sentence — but no headline count of
it survives contact with an instrument, so none is printed here. An earlier revision of
this docstring claimed "53 lines making a negative CI/gate claim" at `origin/main`
`9bc51ece0`; fifteen predicate sweeps over `docs/` yield 27 / 32 / 43 / 50 / 55 and
never 53, because every sweep changes the definition on the way (per line vs per
3-line window, in-frame vs whole tree, matched vs decided), and the frame matters more
than it looks: this module's own frame excludes `docs/vss-integration`, which alone
holds 7 of the 10 anchor lines a looser frame counts. `anchor_census()` is now the
instrument for that figure and `test_the_class_census_keeps_its_relations` re-derives
it — a headline number nobody can regenerate is the defect this gate exists to retire.
Most of the class is legitimately unfalsifiable-about-this-repo (a platform fact — "GitHub
Actions has no workflow-level `if`"; a missing FEATURE — "no workflow to add
faces"; synthbench's "no gate", where *gate* names a JSON file, not CI). Those
must NOT be scanned: a checker that flags them gets its findings ignored, and a
drowned gate is a dead gate (the lesson `test_workflow_paths.py` ships in its own
header). So this gate checks the ONE shape it can decide mechanically:

    a negative-CI claim whose SENTENCE names a repository path  ->  does any
    `.github/workflows/*.yml` mention that path?

Deliberately NOT executed: the command the doc quotes. Quoted commands are
untrusted text with unbounded effects — two in this corpus (`grep -rn
"server-cuda"`, `grep -iE "jpegdec|..."`) name no path and would block on stdin
forever, which is how the author's own measurement would have hung too. The
predicate is evaluated here, in Python, over the workflow text.

Also deliberately excluded: `docs/uplevel/` (owner-shared plan text) and
`docs/plans/` + `docs/superpowers/` (dated records, per `40-docs.md` "plans stay
as history"). A gate that rewrites history notes is a gate people route around.
"""

from __future__ import annotations

import bisect
import functools
import os
import re
import tempfile
import unittest
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
WORKFLOWS = REPO / ".github" / "workflows"
DOCS = REPO / "docs"

# Directories whose text is dated history or owner-shared plan prose. See module
# docstring: checking these buys re-litigated records, not truth.
EXCLUDED_DIRS = (
    "docs/uplevel",
    "docs/plans",
    "docs/superpowers",
    "docs/vss-integration",
)

# A claim that CI does NOT do something. Narrow on purpose.
NEG_CLAIM = re.compile(
    r"""(?:
        runs?\ in\ \**no\**\ (?:workflow|CI)      # "runs in **no** workflow"
      | runs?\ in\ no\ (?:workflow|CI)
      | in\ \**no\**\ workflow
      | no\ workflow\ (?:currently\ )?(?:runs?|calls|targets|mentions|references?)
        # …and the wrapped form, where the search scope sits between the negation and
        # the verb: "no workflow in `.github/workflows/` calls X". Anchoring the verb
        # right after "no workflow" loses the corpus's most common phrasing.
      | no\ workflow\b[^\n]{0,80}?\b(?:runs?|calls|targets|mentions|references?|invokes?)\b
        # The phrasing this file's own probe test found missing: the clause leads with
        # "nothing in CI", so the noun sits BEFORE the verb and there is no second `CI`
        # for the pattern below to anchor on. Added because branch 7 below needs TWO
        # mentions of CI; "nothing in CI runs X" says it once.
        # NO trailing `[^\n]*` here, and not for tidiness. In `flat` text (newlines
        # joined to spaces) there is no `\n` left to stop at, so the quantifier greedily
        # consumes the rest of the 3-line WINDOW: measured, a 2-line doc made this branch
        # match 121 of 121 chars, and the claim's sentence span then ran into the NEXT
        # sentence and adopted a path the claim never named. Detection is unaffected
        # either way (an unanchored `search` with a `*` tail matches the same prefix), so
        # the tail buys nothing and its cost is a false accusation — resolve() calls that
        # the worse error. Pinned by test_a_claim_does_not_borrow_the_next_sentences_path.
      | nothing\ in\ (?:CI|any\ workflow)\b
      | nothing\ (?:in\ CI\ )?(?:runs?|checks|verifies|calls)\b[^\n]{0,60}?\bCI\b
      | referenced\ by\ NO\ workflow
      | no\ CI\ job\ (?:validates|runs|checks|covers)?
        # `to` as well as `into`, and `workflow` as well as `CI`. This branch used to
        # read `not wired into (any )?CI`, which MISSES the corpus's own wording —
        # `ai-pipeline-current-state.md` says two scripts are "**not wired to any
        # workflow**", both of which CI runs, and the gate could not see it. A branch
        # that matches one preposition and one noun is a branch with one arm.
      | not\ wired\ (?:into|to)\ (?:any\ )?(?:workflow|CI)
      | never\ (?:runs?|wired|reached)\ in\ CI
      | isn['\u2019]t\ in\ CI
      | not\ (?:checked|run|verified)\ by\ CI
    )""",
    re.VERBOSE | re.IGNORECASE,
)

# A repository path named inside the claim. Prose compounds are not paths, and
# the two that bite here are `CI/CD` and `Bandit/Semgrep`-style tool pairs, so a
# candidate must RESOLVE in the tree to count as a subject (see resolve()).
REPO_PATH = re.compile(
    r"(?<![\w./-])"
    r"((?:[\w.-]+/)+[\w.+-]+(?:\.(?:py|sh|mjs|ts|tsx|json|yml|yaml|toml|md|txt))?"
    r"|[\w.-]+\.(?:py|sh|mjs|ts|tsx|yml|yaml|toml))"  # bare filename, resolved by uniqueness
)

WORKFLOWS_REL = ".github/workflows"


# Cheap gate in front of NEG_CLAIM. ONE measurement, stated once, machine-dependent
# by construction (re-measure before quoting it anywhere else): on 2026-10-12 over
# the 406 in-frame docs, an ungated pass cost ~1.9 s and the gated pass ~0.4 s
# (0.35 s of prefilter over every window + 0.06 s of regex on the ~1.1% it admits).
# The regex fires 9 times in 149,438 in-frame 3-line windows, so >99.9% of its
# searches ran on text that cannot match.
#
# The predicate is a SUPERSET argument, not a sampled one. Every top-level
# alternation requires either the literal `workflow` or a word-boundary `CI` — see
# branch_texts(), which enumerates them — so admitting every window that contains
# `workflow` or `\bci\b` cannot drop a claim, whichever way the grammar grows.
# Branch NUMBERS are deliberately not listed here: they moved the day `not wired
# to any workflow` was added, and a stale `#6` in prose is indistinguishable from a
# live one. `test_the_cheap_prefilter_admits_everything_the_regex_admits` checks the
# property against the real corpus, so the argument above is a comment, not a gate.
#
# What I deliberately did NOT add: a second condition on the NEGATOR. An earlier
# revision required `no` or `isn` as well, on the reasoning that every negator
# contains `no` — which is false for `never … in CI`, so that branch would have been
# silently dead forever, the exact failure this file's whole design is about. The
# noun test alone already admits ~1.1% of windows, so the extra condition bought
# nothing and could have cost a gate.
def cheap_maybe(seg_lower: str) -> bool:
    return "workflow" in seg_lower or bool(re.search(r"\bci\b", seg_lower))


# A sentence terminator: punctuation followed by whitespace. Coarse on purpose — it
# cuts at `e.g.` too, which only ever SHORTENS the span a subject is read from, so it
# can cost coverage but can never widen an accusation onto a neighbouring sentence.
SENTENCE_END = re.compile(r"(?<=[.!?])\s")

# A markdown heading starts a new unit but ends the previous one with no punctuation,
# so SENTENCE_END alone won't cut there. Without this the span reached back over
# `## Continuous Validation` / `### CI/CD Integration` to the last real period two
# headings earlier — wide enough to drag a heading's path into the next sentence's
# "no workflow runs X". `(?<=\s)` so an inline `#` (an issue number, a C fragment) does
# not count; only a heading marker that opens a line, which in flat text means one
# preceded by the space that replaced its newline.
HEAD_START = re.compile(r"(?<!\S)#{1,6}\s")


def sentence_span(flat: str, start: int, end: int) -> tuple[int, int]:
    """Character span of the sentence enclosing [start, end) in `flat`.

    Subjects are read from the SENTENCE, not from the 3-line match window, because a
    claim's paths routinely sit outside the window that recognised it.
    `detection-validation-coverage.md`:285 shipped the shape: "no workflow in
    `.github/workflows/` / calls `validate_detections.py` or
    `test_risk_score_validation.py`" wraps between the verb and its objects, so the
    window that MATCHED resolved it to NO subjects — and a claim with no subject is a
    claim the gate silently does not check, a false negative wearing the costume of
    the unresolved-claim census.

    Bounded on BOTH sides because the failure directions are real and opposite: cut
    too late and a path on the line BEFORE the negation (`scripts/foo.py` / "runs in
    no workflow") is dropped, the same miss mirrored; cut too wide and the next
    sentence's paths join the accusation, indicting an innocent file — which
    `resolve()`'s docstring calls the worse error.

    Both boundaries are searched on both sides: a terminator or a heading can fall
    either before or after the match, and markdown headings end a unit with no
    punctuation, so SENTENCE_END alone lets the left edge run back over `### CI/CD
    Integration` to a period two headings earlier.
    """
    lo = 0
    for pat in (SENTENCE_END, HEAD_START):
        for mt in pat.finditer(flat, 0, start):
            lo = max(lo, mt.end())
    hi = len(flat)
    for pat in (SENTENCE_END, HEAD_START):
        mt = pat.search(flat, end)
        if mt is not None:
            hi = min(hi, mt.start())
    return lo, hi


def branch_count(pattern: str | None = None) -> int:
    """How many top-level alternations NEG_CLAIM has (default: the live grammar).

    Used as a tripwire: the probe list below must stay the same length, so a branch
    added without a probe fails loudly instead of being silently dropped by the
    prefilter. Counted by scanning the PATTERN TEXT with a paren-depth counter that
    skips escapes and character classes — `re._parser` would work too, but it is a
    private module and this file has to keep running on CI's interpreter, whatever
    version that turns out to be.
    """
    pat = NEG_CLAIM.pattern if pattern is None else pattern
    depth = escapes = in_class = 0
    pipes = 0
    for ch in pat:
        if escapes:
            escapes = False
        elif ch == "\\":
            escapes = True
        elif in_class:
            in_class = ch != "]"
        elif ch == "[":
            in_class = True
        elif ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        elif ch == "|" and depth == 1:
            pipes += 1
    return pipes + 1


def branch_texts(pattern: str | None = None) -> list[str]:
    """NEG_CLAIM's top-level alternations, each independently compilable.

    Splits at the SAME bars `branch_count` counts (depth 1, escapes and character
    classes skipped), so the two can never disagree about what a branch is. Then the
    grammar's own wrapper comes off — `(?:` from the first piece, the single trailing
    `)` from the last — so every element compiles alone. The wrapper close is always
    the pattern's final character, which is why dropping one char from the last piece
    is exact even when that piece itself ends in a group.

    Exists because a COUNT of branches and a LIST of probes prove different things:
    with 13 of each, `assertEqual(n, len(probes))` passed while one branch had no
    probe at all and two probes exercised the same branch. Only per-branch matching
    can tell those situations apart.
    """
    pat = NEG_CLAIM.pattern if pattern is None else pattern
    if not pat.lstrip().startswith("(?:") or not pat.rstrip().endswith(")"):
        raise AssertionError(f"NEG_CLAIM is no longer a single (?:…) group: {pat[:40]!r}")
    pieces: list[str] = []
    buf: list[str] = []
    depth = escapes = in_class = 0
    for ch in pat:
        if escapes:
            escapes = False
        elif ch == "\\":
            escapes = True
        elif in_class:
            in_class = ch != "]"
        elif ch == "[":
            in_class = True
        elif ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        elif ch == "|" and depth == 1:
            pieces.append("".join(buf))
            buf = []
            continue
        buf.append(ch)
    pieces.append("".join(buf))
    pieces[0] = pieces[0].lstrip()[3:]  # the wrapper's `(?:`
    pieces[-1] = pieces[-1].rstrip()[:-1]  # the wrapper's `)`
    return [p.strip() for p in pieces]


def doc_claims(text: str) -> list[tuple[int, str, str]]:
    """(0-based line, that line's text, claim's SENTENCE) for each NEG_CLAIM hit.

    Returns RAW hits — no frame filter, no subject resolution — so the caller decides
    what to do with them: the real gate applies the frame BEFORE scanning, the
    mutation control wants everything.

    HOW THE SCAN WORKS, and why it stopped being per-line. The doc is joined once into
    `flat` (newlines -> spaces) and every line's offset is precomputed, so a
    "3 consecutive lines" window is a slice and a match's line number is one `bisect`.
    The line-by-line version needed a cumulative-offset walk to answer "which line did
    this match start on", and got it wrong the first time — it counted "\n" in a string
    joined with spaces, found 0 every time, and reported one claim three times. Two
    consequences of flat text, both handled here:

      * `\\n` no longer exists in `flat`, so a trailing `[^\n]*` matches everything to
        the END OF THE SEARCH WINDOW (the 3 lines, not the file — `search` is bounded
        by `b`). It has been removed from every branch, and that is load-bearing: a
        greedy tail does not change WHETHER a claim matches but it does move `m.end()`,
        which `sentence_span` uses as its right cut, so the span reaches into the next
        sentence and can adopt a path the claim never named.
        `test_a_claim_does_not_borrow_the_next_sentences_path` pins it; this note used
        to claim the tail was already gone when branch 6 still had it, which is the
        same defect (a comment asserting a property the code does not have) the test
        now catches in the grammar.
      * Offsets are taken ONLY from searches of `flat`, never of its lowercase copy.
        `str.lower()` is not guaranteed length-preserving across Unicode, and an offset
        from a string of different length would slice the sentence at the wrong place —
        silently, in the one doc that happens to contain the character.
    """
    lines = text.splitlines()
    if not lines:
        return []
    flat = " ".join(lines)
    low = flat.lower()  # prefilter boolean only; never a source of offsets
    starts = [0]
    for ln in lines[:-1]:
        starts.append(starts[-1] + len(ln) + 1)
    ends = [starts[k] + len(lines[k]) for k in range(len(lines))]
    out: list[tuple[int, str, str]] = []
    reported: set[int] = set()
    last = len(lines) - 1
    for i in range(len(lines)):
        # A 3-line window, because markdown wraps near 100 columns and the noun and its
        # negation routinely land on different physical lines — the class hides in the
        # wrap, which is exactly where prose about CI has already wrapped itself.
        a, b = starts[i], ends[min(i + 2, last)]
        if not cheap_maybe(low[a:b]):
            continue
        m = NEG_CLAIM.search(flat, a, b)
        if m is None:
            continue
        line = bisect.bisect_right(starts, m.start()) - 1
        if line in reported:
            continue
        reported.add(line)
        lo, hi = sentence_span(flat, m.start(), m.end())
        # A heading's words are a TITLE, not sentence prose, so the left cut has to
        # skip the whole line rather than just the `###` marker. Flat text cannot see a
        # line start (a wrap and a line break are both one space), which is why this one
        # boundary is resolved from `lines` instead of from `flat`: without it the span
        # began at `CI/CD Integration Nothing runs these checks…`, and a heading that
        # names a script (`### validate_detections.py — unwired`) would hand its path to
        # the NEXT sentence's "no workflow runs X" — the false accusation resolve() calls
        # the worse error. Guarded on `ends[idx] <= m.start()` so a heading that CONTAINS
        # the claim is never skipped past.
        idx = bisect.bisect_right(starts, lo) - 1
        if ends[idx] <= m.start() and lines[idx].lstrip().startswith("#"):
            lo = min(ends[idx], hi)
        out.append((line, lines[line].strip(), flat[lo:hi]))
    return out


def annotated(text: str) -> list[tuple[int, str, list[str]]]:
    """`doc_claims` plus each claim's resolved subject paths.

    The gate needs the subjects and the unresolved-claim census needs their
    absence, but both need the same scan; the per-doc cache below means the corpus
    is walked once however many tests consume it.
    """
    wf_names = set(workflow_texts())
    out: list[tuple[int, str, list[str]]] = []
    for anchor, line_text, window in doc_claims(text):
        subjects: list[str] = []
        for cand in REPO_PATH.findall(window):
            r = resolve(cand, wf_names)
            if r and r not in subjects:
                subjects.append(r)
        out.append((anchor, line_text, subjects))
    return out


@functools.cache
def _annotated_doc(rel: str) -> tuple[tuple[int, str, tuple[str, ...]], ...]:
    """Per-doc `annotated()`, cached by repo-relative path for the process.

    Cached on the PATH, not the text: passing the text would defeat the point, since
    the caller has to read the file to produce it. The trade is that the cache is
    blind to edits made after the first read — which is right for a gate over a
    checked-out tree, and wrong for the synthetic control, so `claims_raw` below
    deliberately bypasses it.
    """
    text = (REPO / rel).read_text(encoding="utf-8", errors="replace")
    return tuple((a, t, tuple(s)) for a, t, s in annotated(text))


@functools.lru_cache(maxsize=1)
def workflow_texts() -> dict[str, str]:
    """All workflow text, read ONCE per process.

    Cached because `annotated()` runs per doc: without this, 406 docs re-read the 34
    workflows (~0.8 s) and the per-doc cache below only pays for itself if the
    workflow reads are cached too. Treat the returned dict as read-only.
    """
    out: dict[str, str] = {}
    for p in sorted(WORKFLOWS.glob("*.yml")) + sorted(WORKFLOWS.glob("*.yaml")):
        out[p.name] = p.read_text(encoding="utf-8", errors="replace")
    return out


_PRUNE = {
    ".git",
    ".venv",
    "node_modules",
    ".pytest_cache",
    "__pycache__",
    ".mypy_cache",
    ".ruff_cache",
}


@functools.lru_cache(maxsize=1)
def name_index() -> dict[str, list[Path]]:
    """basename -> paths, built ONCE for the process.

    Built with os.walk and pruned at the directory level, not `rglob` per lookup: the
    first version called `REPO.rglob(name)` for every unresolved candidate and blew the
    5 s root timeout on a worktree whose `.venv` holds ~100k files, because a filter
    applied AFTER the walk still pays for the walk. Same lesson as the fence-scan hoist
    this repo just shipped — scan once, ask many. Cached via lru_cache rather than a
    module global: the global drew PLW0603 and bought nothing over this.
    """
    idx: dict[str, list[Path]] = {}
    for root, dirs, files in os.walk(REPO):
        dirs[:] = [d for d in dirs if d not in _PRUNE and not d.endswith(".egg-info")]
        for f in files:
            idx.setdefault(f, []).append(Path(root) / f)
    return idx


def _unique_bare(name: str) -> Path | None:
    """Resolve a bare filename, but only when the tree holds exactly one of it.

    Docs routinely name a script by basename alone ("no workflow calls
    `validate_detections.py`"), and the path form never matches that. Ambiguity is
    resolved AGAINST binding: two candidates return None rather than a guess,
    because a wrong subject indicts an innocent file — and the file it picks is
    usually the one that IS wired.
    """
    hits = name_index().get(name, [])
    return hits[0] if len(hits) == 1 else None


def resolve(candidate: str, wf_names: set[str]) -> str | None:
    """Return a normalised subject, or None if the candidate is not one.

    Three exclusions, each learned from a false accusation this gate made on its
    first run over a KNOWN-FALSE doc:
      * prose compounds (`CI/CD`) — do not resolve, so they are never subjects;
      * the search SCOPE (`.github/workflows`, `.github`) — the sentence says "no
        workflow in `.github/workflows/`", naming where it looked, not a thing
        claimed unwired. Flagging it would indict the sentence for CI's own content;
      * a WORKFLOW file itself — that is the sentence's evidence (`gpu-tests.yml`
        was deleted), and matching it against workflow text is circular.
    """
    if candidate.startswith("//"):
        return None
    p = REPO / candidate
    if not p.exists():
        p = _unique_bare(candidate) if "/" not in candidate else None
        if p is None:
            return None  # prose compound, gone from the tree, or ambiguous
    norm = p.resolve().relative_to(REPO).as_posix()
    # The scope of the search, or a workflow itself, is not a subject. NOTE the
    # shape of this test: an earlier revision wrote `(WORKFLOWS / norm).is_relative_to(
    # WORKFLOWS)`, which is TRUE for every path on earth — joining anything onto a
    # directory and asking whether the result is inside it is a tautology. It excluded
    # every subject, every claim resolved to [], and the gate passed over a KNOWN-FALSE
    # doc while all three controls stayed green. Test a guard's EXCLUSION by asserting
    # it still lets a real subject through (below), never only that it blocks one.
    if norm == WORKFLOWS_REL or norm.startswith(WORKFLOWS_REL + "/") or norm == ".github":
        return None
    if Path(norm).name in wf_names:
        return None
    return norm


def spellings(subject: str) -> list[str]:
    """Every form a workflow could use to name `subject`.

    The lesson of the first run: CI runs the docs validator as
    `python -m scripts.validate_docs` — a DOTTED module. A needle built only from
    the path the doc printed misses the wiring that refutes it, and the miss looks
    like a clean bill. A package dir therefore matches its module form too.
    """
    p = REPO / subject
    out = [subject, Path(subject).name]
    is_pkg = p.is_dir() and ((p / "__main__.py").exists() or (p / "__init__.py").exists())
    if is_pkg:
        out.append(subject.replace("/", "."))
    return out


def scanned(rel: str) -> bool:
    """Is this docs path in the gate's frame? Split out so the frame has its own test.

    Excludes dated history and owner-shared plan prose (see module docstring) and the
    stale `.pytest_cache` trees — a copy of `docs/` from a branch that no longer
    exists has produced false findings here before.
    """
    if any(rel == d or rel.startswith(d + "/") for d in EXCLUDED_DIRS):
        return False
    return ".pytest_cache" not in Path(rel).parts


def _row(doc: str, anchor: int, text: str, subjects) -> dict:
    return {"doc": doc, "line": anchor + 1, "text": text, "subjects": list(subjects)}


def claims_raw(docs_dir: Path) -> list[dict]:
    """Scan a directory with NO frame filter — for the synthetic control.

    Reads every .md itself rather than sharing the real run's per-doc cache: the
    control's files live outside the repo and change between runs, so a cache keyed
    on repo-relative path would neither see them nor be allowed to remember them.
    """
    return [
        _row(str(path), anchor, text, subjects)
        for path in sorted(docs_dir.rglob("*.md"))
        for anchor, text, subjects in annotated(path.read_text(encoding="utf-8", errors="replace"))
    ]


def doc_paths() -> list[str]:
    """Every in-frame docs path, as repo-relative posix strings.

    The frame is applied HERE, before anything is read or searched. It used to sit in
    the caller, AFTER the regex had already run over all 573 docs — the same mistake
    shape as a filter applied after a walk still pays for the walk (see name_index).
    """
    return [
        p.relative_to(REPO).as_posix()
        for p in sorted(DOCS.rglob("*.md"))
        if scanned(p.relative_to(REPO).as_posix())
    ]


def claims() -> list[dict]:
    """Every negative-CI claim in the frame, with its resolved subjects."""
    return [
        _row(rel, anchor, text, subjects)
        for rel in doc_paths()
        for anchor, text, subjects in _annotated_doc(rel)
    ]


def anchor_census() -> dict[str, object]:
    """How big the class is, counted by THIS module's grammar over THIS module's frame.

    The module docstring used to print "53 lines making a negative CI/gate claim" and
    nothing in the repo could reproduce it. A fresh-context review ran ~15 predicate
    sweeps over `docs/` and reported 27 / 32 / 43 / 50 / 55 — never 53 (that list is
    the reviewer's measurement, quoted as such; three of my own frames appear below and
    none of them is 53 either). Sweeps drift because each quietly changes the definition
    (per-line vs per-window, in-frame vs whole tree, mentions vs decides). A headline
    number with no instrument behind it is the same defect this gate exists to retire —
    a claim nobody ran — so the count lives HERE, and its own test re-derives it.

    Definitions, because the frame is the whole argument:
      anchors   in-frame `.md` LINES the grammar matches at all (the class's outer edge)
      docs      how many in-frame docs hold at least one anchor
      decided   rows from `claims()` — anchors whose sentence names a resolvable path,
                i.e. the subset this gate can actually rule on
      counted   the in-frame docs holding an anchor, by path, so a reader can audit the
                frame by hand and the test can check it against `scanned()`

    Per LINE, not per 3-line search window: windows overlap, so a window census
    multi-counts one sentence, and a reader repeating the count with `grep -c` gets the
    line figure and calls this file wrong.

    The frame is the whole argument, and these are three true figures for ONE grammar
    over ONE tree (`origin/main` `9bc51ece0`): every `.md` in the repo, 27 lines in 19
    files; `docs/` minus this module's exclusions, 8 in 7; the 406 in-frame paths that
    also exist at main, 5 in 4. A "class size" without its frame is not one number — it
    is one number per frame, and 53 is a number none of them produces. A count names a
    grammar AND a tree: run this widened grammar over main and you get the figures
    above, run main's own grammar and you get another pair. Quote this dict with its
    frame, or quote nothing.
    """
    anchors = 0
    counted: list[str] = []
    for rel in doc_paths():
        text = (REPO / rel).read_text(encoding="utf-8", errors="replace")
        hits = sum(1 for ln in text.splitlines() if NEG_CLAIM.search(ln))
        if hits:
            counted.append(rel)
            anchors += hits
    # `counted` is returned so the frame can be checked against `scanned()` — a
    # separate implementation. A census that reports only a COUNT cannot be audited
    # for frame errors at all, and the obvious relation (count <= frame size) is
    # satisfied by every mutant short of a catastrophe.
    return {"anchors": anchors, "docs": len(counted), "decided": len(claims()), "counted": counted}


def executable_lines(text: str) -> list[tuple[int, str]]:
    """(1-based line, text) for lines that can CARRY a command, comments dropped.

    A `#` line is not a command — not to YAML, not to the shell inside a `run:`
    block — so it cannot refute a doc that says CI never runs X. Without this the
    probe read the prose around the wiring as evidence of the wiring: at this head
    `mentions("docs-negative-claims")` returns `ci.yml:3711`, which is a comment
    this very job's own header. Both directions of that error are live: a comment
    clears a FALSE claim (the bug ships) and can also redden an HONEST one (some
    unrelated comment names the subject). Measured over the current in-frame
    subjects, dropping comments flips zero verdicts — so this is the rule that
    should have been there, not a behaviour change.
    """
    out: list[tuple[int, str]] = []
    for n, line in enumerate(text.splitlines(), 1):
        if line.lstrip().startswith("#"):
            continue
        out.append((n, line))
    return out


def mentions_in(subject: str, texts: dict[str, str]) -> list[str]:
    """Where `texts` NAMES `subject` on a line that could run it.

    Split out from `mentions()` so the comment rule is testable against a synthetic
    corpus — the alternative is a fixture comment in ci.yml, i.e. shipping a decoy
    in production config to keep a test green.
    """
    hits: list[str] = []
    pats = [re.compile(rf"(?<![\w./-]){re.escape(s)}(?![\w-])") for s in spellings(subject)]
    for name, text in texts.items():
        for n, line in executable_lines(text):
            if any(p.search(line) for p in pats):
                hits.append(f"{name}:{n}")
                break
    return hits


def mentions(subject: str) -> list[str]:
    """Where the workflows name `subject`, in any spelling it can take."""
    return mentions_in(subject, workflow_texts())


class NegativeToolingClaims(unittest.TestCase):
    """The gate, plus the guards that keep it from passing vacuously."""

    def setUp(self) -> None:
        self.assertTrue(WORKFLOWS.is_dir(), f"no workflows dir at {WORKFLOWS}")
        self.assertGreater(len(workflow_texts()), 5, "workflow corpus looks empty")

    # -- guards: the instrument must be able to fail, and must be able to see --

    def test_workflow_probe_has_teeth_on_a_path_we_knock(self) -> None:
        """POSITIVE control: a subject CI really does run must be detected.

        Without this, `mentions()` returning [] for everything would look like a
        clean bill. `scripts/validate_docs` is run by the docs-citation step, so
        a probe naming it must come back non-empty on ANY head that has that step.
        """
        self.assertTrue(
            mentions("scripts/validate_docs"),
            "probe could not find validate_docs in any workflow — the instrument is blind",
        )

    def test_workflow_probe_is_negative_on_a_path_ci_never_names(self) -> None:
        """NEGATIVE control: a fabricated path must produce zero mentions.

        Pair with the test above: a matcher that matched everything would pass the
        positive control and be caught here.
        """
        self.assertEqual([], mentions("scripts/zz_no_such_gate_zz.py"))

    def test_a_comment_line_is_not_evidence_that_ci_runs_something(self) -> None:
        """The refutation must come from a line that could EXECUTE the subject.

        Synthetic corpus, deliberately: the alternative is a decoy comment parked in
        ci.yml to keep this green, which trades one defect for another.
        """
        corpus = {
            "a.yml": "\n".join(
                [
                    "# scripts/zz_comment_only_zz.py is mentioned here in prose",  # 1 comment
                    "  - name: does not run it",  # 2
                    "    run: echo hello",  # 3
                ]
            ),
            "b.yml": "\n".join(
                ["  steps:", "    run: pytest scripts/zz_real_run_zz.py -q"]  # 2 real command
            ),
        }
        self.assertEqual(
            [],
            mentions_in("scripts/zz_comment_only_zz.py", corpus),
            "a # comment cleared a claim — prose is not a command",
        )
        self.assertEqual(
            ["b.yml:2"],
            mentions_in("scripts/zz_real_run_zz.py", corpus),
            "the real run: line must still count, or this 'fix' just blinded the probe",
        )

    def test_the_claim_scanner_is_not_vacuous(self) -> None:
        """Collapse-to-zero guard. Deliberately a FLOOR, not a count.

        The failure mode is a broken pattern or a broken scan frame producing zero
        claims, which reads identical to a clean docs/. An exact count would make an
        honest docs deletion red, so the floor sits below the measured population at
        this head (3 claims in scope, per `anchor_census()["decided"]`). The real teeth are in the two synthetic tests
        below: they prove the pipeline has teeth without depending on a defect
        surviving in the tree — a gate that asserts its own bug is still present is a
        gate that has to be weakened the moment the bug is fixed.
        """
        found = claims()
        self.assertGreaterEqual(
            len(found),
            2,
            "negative-CI claim scanner found almost nothing — the pattern or the scan "
            "frame broke (a silent zero reads identical to a clean docs/)",
        )

    def test_the_class_census_keeps_its_relations(self) -> None:
        """The census figure is computed here, and its parts must stay consistent.

        Deliberately NOT an exact count, and not a number pasted into the docstring:
        an exact pin reddens the moment anyone honestly deletes a claim sentence — a
        gate that punishes a fix gets routed around (the note in
        `test_the_claim_scanner_is_not_vacuous` reaches the same call for the same
        reason). Two floors and two relations, each with its own failure direction:

          anchors >= decided   every ruled-on row sits on a line the grammar matched;
                               decided > anchors means the census and `claims()` are no
                               longer the same scan.
          docs    <= len(doc_paths())  a doc counted that the frame excludes — the
                               silent-growth half of the same defect.
          anchors >= 2         below today's measured population, so it catches collapse
                               (0 anchors reads identical to clean docs/) without
                               punishing honest repair.

        The relation that does the real work is the frame check: `claims()` rows and
        the census must read the SAME corpus, or a published count and the running gate
        describe different trees while both looking green.

        Known blind spot, measured rather than assumed: a mutant that counts anchors
        PER DOC instead of per line stays green, because at this head every in-frame
        doc holds exactly one anchor line (3 / 3 / 3), so no relation between these
        three figures can tell the two definitions apart. Closing it would need a
        second, independent definition of "line count" — re-running this predicate is
        not one. It is listed here so nobody reads the four assertions as coverage of
        every way a census can be wrong.
        """
        c = anchor_census()
        self.assertGreaterEqual(c["anchors"], 2, "class collapsed: pattern or scan frame broke")
        self.assertGreaterEqual(c["anchors"], c["decided"], "decided rows exceed anchor lines")
        # The frame check is an INDEPENDENT predicate (`scanned`), not a count
        # comparison — measured: a mutant that replaces `doc_paths()` with an unframed
        # `docs/**/*.md` walk passes `docs <= len(doc_paths())` (7 <= 406) and reports
        # GREEN while describing a corpus this gate does not scan.
        strays = [d for d in c["counted"] if not scanned(d)]
        self.assertEqual(strays, [], f"census counted docs outside the frame: {strays}")
        in_frame = set(doc_paths())
        strays2 = [r["doc"] for r in claims() if r["doc"] not in in_frame]
        self.assertEqual(strays2, [], f"claims() rows outside the census frame: {strays2}")
        self.assertEqual(
            c["decided"],
            len(claims()),
            "the census's `decided` is not `claims()` — two definitions of the same count",
        )

    def test_the_prefilter_admits_a_probe_for_every_grammar_branch(self) -> None:
        """Every NEG_CLAIM branch, one sentence, each admitted by the prefilter.

        Why probes and not only the corpus test below: a branch that no doc currently
        uses has no window in the corpus to check, so a grammar widened that way would
        stay green while the prefilter silently dropped it. Each probe must (a) match
        NEG_CLAIM — so editing or deleting a branch lands here rather than in a
        mystery — and (b) be admitted by `cheap_maybe`.

        A branch added WITHOUT a probe is caught by the PER-BRANCH assertion, not the
        old `branch_count() == len(probes)` count-match. That count is a COVER proxy
        and a weak one: 13 branches and 13 probes pass on ANY pairing of equal size,
        so the list here — which double-probed branch 1 while branch 7 (`nothing … in
        CI`) sat unprobed — was green while a whole branch could be edited or deleted
        unnoticed. `branch_texts()` splits at the same bars `branch_count()` counts, so
        a branch with no probe is now named by text, and a probe that matches two
        branches no longer hides the gap it used to.
        """
        probes = [
            "the checker runs in **no** workflow today",
            "the checker runs in no CI job today",
            "it sits in **no** workflow at all",
            "no workflow currently runs the audit",
            "no workflow in `.github/workflows/` calls it",
            "nothing in CI runs that gate",
            "nothing in any workflow calls the validator",
            "nothing checks that legacy gate in CI today",  # branch 7: `nothing … CI`, one CI
            "it is referenced by NO workflow",
            "there is no CI job to consult",
            "the tool is not wired to any workflow",  # the `to`/`workflow` arm of `wired`
            "the hook is not wired into CI",
            "the scan never runs in CI",
            "the check isn't in CI yet",
            "the claim is not checked by CI",
        ]
        for p in probes:
            self.assertTrue(NEG_CLAIM.search(p), f"probe no longer matches NEG_CLAIM: {p}")
            self.assertTrue(
                cheap_maybe(p.lower()), f"prefilter rejects a claim the grammar matches: {p}"
            )
        branches = branch_texts()
        self.assertEqual(
            branch_count(),
            len(branches),
            "branch_count() and branch_texts() disagree about what a branch is — the two "
            "share a scanner and must not drift",
        )
        for i, btext in enumerate(branches):
            pat = re.compile(btext, re.VERBOSE | re.IGNORECASE)
            hit = [p for p in probes if pat.search(p)]
            self.assertTrue(
                hit,
                f"branch {i + 1} has NO probe that matches it alone: {btext[:60]!r} — a "
                "branch with no probe can be edited or dropped with every gate green",
            )

    @pytest.mark.timeout(30)  # full re-scan of the 406 in-frame docs by design
    def test_the_cheap_prefilter_admits_everything_the_regex_admits(self) -> None:
        """The prefilter's superset property, checked against the REAL grammar.

        `cheap_maybe` stands in front of a regex that costs seconds to skip most of
        the corpus (one measurement, stated at its definition — not restated here,
        because restating a number is how this file ended up citing the same cost as
        three different values), which is a trade that is only worth making if it
        cannot lose a claim — and a lost claim
        is not a loud failure, it is a green run over a false doc. Asserting it over
        the actual corpus (rather than trusting the comment above the function) makes
        the two stay welded together: widen NEG_CLAIM with a branch that needs
        neither `workflow` nor `CI` and THIS goes red, naming the window.

        Runs over in-frame windows only, the same frame the gate uses, so it tests
        the population the predicate actually faces.
        """
        misses = []
        for rel in doc_paths():
            lines = (REPO / rel).read_text(encoding="utf-8", errors="replace").splitlines()
            for i in range(len(lines)):
                window = " ".join(lines[i : i + 3])
                if NEG_CLAIM.search(window) and not cheap_maybe(window.lower()):
                    misses.append(f"{rel}:{i + 1}  {window[:110]}")
        self.assertEqual(
            [],
            misses,
            "NEG_CLAIM now matches text the prefilter rejects — the gate is blind:\n  "
            + "\n  ".join(misses[:10]),
        )

    def test_the_prefilter_is_not_itself_a_no_op(self) -> None:
        """The other arm: a prefilter that admits EVERYTHING saves nothing.

        `cheap_maybe` returning True unconditionally would keep the suite green and
        quietly restore the ungated scan — the slow path is measured at its
        definition; at CI's ~2x runner factor that is how a gate gets moved out of
        the battery. Measured selectivity, with a floor loose enough not to break on
        prose edits (98.9% of windows are rejected today).
        """
        probes = [
            "the detector raises on a malformed frame here",  # no noun at all
            "workflow dispatch triggers the build",  # noun, no claim
        ]
        self.assertFalse(
            cheap_maybe(probes[0]), "prefilter admits a window with no CI noun — it is vacuous"
        )
        self.assertTrue(cheap_maybe(probes[1]), "prefilter must admit any window naming a workflow")

    def test_the_scan_frame_admits_docs_and_excludes_history(self) -> None:
        """Frame test, both arms, on synthetic paths (no writes into the tree).

        The include arm is what makes the exclude arm mean anything: an earlier
        revision of this file had a scope guard that was true for every path, so it
        excluded the whole corpus and stayed green over a known-false doc.
        """
        self.assertTrue(scanned("docs/architecture/x.md"))
        self.assertTrue(scanned("docs/guides/y.md"))
        self.assertFalse(scanned("docs/plans/2026-09-12-context-map.md"))
        self.assertFalse(scanned("docs/uplevel/30-ops.md"))
        self.assertFalse(scanned("docs/superpowers/plans/z.md"))
        self.assertFalse(scanned("docs/vss-integration/17-action-plan.md"))
        self.assertFalse(scanned("docs/x/.pytest_cache/main-wt/y.md"))

    def test_a_synthetic_false_claim_goes_red_through_the_whole_pipeline(self) -> None:
        """MUTATION control on the REAL pipeline, over a synthetic tree.

        Writes the exact shape this package fixed — the shipped sentence, verbatim in
        form — into a temp doc and asserts all three stages fire: the grammar sees it,
        the resolver names its subject, and the workflow probe refutes it. An earlier
        version of this control re-ran the regexes by hand instead of calling claims();
        that proves nothing about the scanner, because the bug lived between them.
        """
        sentence = (
            "And `scripts/validate_docs` — the tool that catches dead `source_refs` — "
            "runs in **no** workflow either (`grep -rn validate_docs .github/workflows/` "
            "returns nothing)."
        )
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "synthetic.md"
            path.write_text(sentence + "\n", encoding="utf-8")
            found = claims_raw(Path(td))
        self.assertEqual(1, len(found), "the scanner did not see the injected claim")
        self.assertEqual(["scripts/validate_docs"], found[0]["subjects"])
        self.assertTrue(mentions("scripts/validate_docs"), "the refutation is missing")

    def test_a_claim_whose_path_wraps_to_the_next_line_still_gets_a_subject(self) -> None:
        """The false negative this file found in itself, pinned as a control.

        `detection-validation-coverage.md`:285 matched NEG_CLAIM but resolved to NO
        subjects, because the 3-line window that recognised it ends before the paths
        appear — the sentence wraps between the verb and its objects. A claim with no
        subject is a claim the gate does not check, so the class hides as "nothing to
        verify" rather than as a miss. Two arms, because the bug is directional:
          * path AFTER the negation (the shipped shape), across the wrap;
          * path BEFORE it, which the first fix would have lost in the other direction.
        Both must yield the subject. Written against a temp tree so it keeps its teeth
        after the real doc is edited.
        """
        cases = [
            (
                "path after the verb",
                "### CI/CD Integration\nNothing runs these checks in CI today — no "
                "workflow in `.github/workflows/`\ncalls `scripts/validate_detections.py`.\n",
            ),
            (
                "path before the negation",
                "Some prose first. `scripts/validate_detections.py` then\n"
                "runs in **no** workflow at all.\n",
            ),
        ]
        for label, text in cases:
            with tempfile.TemporaryDirectory() as td:
                (Path(td) / "wrap.md").write_text(text, encoding="utf-8")
                found = claims_raw(Path(td))
            self.assertEqual(1, len(found), f"{label}: scanner missed the claim")
            self.assertIn(
                "scripts/validate_detections.py",
                found[0]["subjects"],
                f"{label}: subject not resolved — the gate would silently skip this claim",
            )

    def test_the_subject_resolver_still_admits_a_real_subject(self) -> None:
        """The guard on the guard: exclusions must not become a total exclusion.

        Asserts the resolver (a) still returns a real subject, (b) refuses a prose
        compound, (c) refuses the search scope. Only the middle assertion was ever
        wanted; the first is what makes the second mean anything.
        """
        wf = set(workflow_texts())
        self.assertEqual("scripts/validate_docs", resolve("scripts/validate_docs", wf))
        self.assertIsNone(resolve("CI/CD", wf))
        self.assertIsNone(resolve(".github/workflows", wf))

    # -- the gate --

    def test_a_claim_does_not_borrow_the_next_sentences_path(self) -> None:
        """A claim's sentence span must end at its own sentence.

        Why this exists: branch 6 (`nothing in CI …`) used to end in `[^\n]*`, and in
        `flat` text — newlines joined to spaces — there is no `\\n` left to stop the
        quantifier at. Measured on a two-line doc it consumed the whole window (121 of
        121 chars), so the claim's sentence ran past its own full stop and collected a
        path from the NEXT sentence. If that path happens to be one CI runs, `mentions()`
        returns hits and the gate goes red accusing the doc of a claim it never made —
        resolve()'s self-declared worse error. The comment in NEG_CLAIM claimed this
        tail had been dropped; it had not, which is the second reason for the test.
        """
        doc = "\n".join(
            [
                "Nothing in CI runs these legacy probes any more.",
                # A path that DOES resolve in this repo, so the false accusation is the
                # realistic shape rather than a synthetic one: the neighbour is a real
                # suite, and the claim is about something else entirely.
                "The census in scripts/test_ai_surface_census.py covers the loader set.",
            ]
        )
        found = doc_claims(doc)
        self.assertEqual(1, len(found), f"expected exactly one claim, got {found}")
        _line, _raw, sentence = found[0]
        self.assertNotIn(
            "test_ai_surface_census",
            sentence,
            f"the claim's span borrowed the next sentence's path: {sentence!r}",
        )
        self.assertEqual(
            "Nothing in CI runs these legacy probes any more.",
            sentence,
            "the span is no longer the claim's own sentence — check NEG_CLAIM's quantifiers "
            "and sentence_span's right cut before changing this expectation",
        )

    def test_no_doc_claims_a_path_ci_runs_is_unwired(self) -> None:
        """Every negative-CI claim naming a repo path must survive the grep it cites.

        Red means: some doc tells a reader nothing checks X, while `.github/
        workflows/` says otherwise. Fix the SENTENCE (that is the bug), and if the
        wiring is genuinely new since the sentence was written, say when.
        """
        bad = []
        for c in claims():
            for s in c["subjects"]:
                hits = mentions(s)
                if hits:
                    bad.append(f"{c['doc']}:{c['line']}  '{s}' IS run at {', '.join(hits)}")
        self.assertEqual([], bad, "false negative tooling claims:\n  " + "\n  ".join(bad))

    def test_claims_whose_subject_cannot_be_resolved_stay_visible(self) -> None:
        """Unresolved subjects are reported, never silently skipped, and capped.

        A scanner that quietly stops resolving subjects shrinks the gate to a no-op
        while staying green. The ceiling is measured, not guessed; raising it must
        be a deliberate act in the PR that adds the claims.
        """
        found = claims()
        unresolved = [c for c in found if not c["subjects"]]
        resolved = [c for c in found if c["subjects"]]
        # The anti-collapse arm: the gate only ever checks claims WITH a subject, so if
        # resolution silently stopped the gate would go green while checking nothing.
        # A ceiling alone cannot catch that — with 3 claims in frame, a ceiling of 12
        # (this test's first draft) would have passed at 3-unresolved-out-of-3, which is
        # precisely total collapse. So assert the positive first, then cap the list.
        self.assertGreaterEqual(
            len(resolved),
            1,
            "no negative-CI claim resolves to a repository path any more — the gate has "
            "nothing to check and is reporting a clean bill it never read: "
            + "\n  ".join(f"{c['doc']}:{c['line']}" for c in found[:10]),
        )
        self.assertLessEqual(
            len(unresolved),
            4,
            "too many negative-CI claims now name no resolvable path: "
            + "\n  ".join(f"{c['doc']}:{c['line']}" for c in unresolved[:20]),
        )


if __name__ == "__main__":
    unittest.main()
