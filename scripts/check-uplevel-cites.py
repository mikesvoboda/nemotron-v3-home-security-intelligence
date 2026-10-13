#!/usr/bin/env python3
"""Uplevel cite gate: rules.md cites resolve, and their named homes carry the claim.

ABOUTME: The defect class this kills: a cite can RESOLVE (the named file exists, the quoted
heading exists) while the section behind the name states none of the claim — #7054 round 1
shipped nine false redirects through a green resolver, each one pointing at a section that
opened "Read rules.md §..." or carried none of the rule's words. So this gate runs two
instruments and one self-test. (1) RESOLVER: every ``file "Section"`` cite in docs/uplevel
resolves — live files quote a heading, bold label, or a VERBATIM (case-sensitive) prose
phrase, each tallied apart so a prose quote cannot inflate the section count; a
``the deleted X`` cite demands X dead in the live tree and its quoted names present in the
committed pre-reorg snapshot (docs/uplevel/...data/uplevel-cites/), because a CI checkout
has no history to ``git show``. (2) ENTAILMENT: the committed fixture
(entailments.json) pins, for each repaired cite, a needle from the rule's own sentence
inside the named section — and pins the OTHER direction too: expect_present=false cases
record that a home is EMPTY of a claim (UR-91 clause 4, the old circular UR-32 home), so
the day someone writes that text elsewhere, the pin fires and forces the cite to move.
(3) SELF-TEST: before judging the tree, the gate plants a fake cite and a fake section in
memory and requires its own matcher to fire; a control that cannot pass is not a gate
either. Corpus sizes print as witnesses — an empty scan reports as one, never as a pass.

Why the baseline is a data file: scripts/retired_paths.txt set the pattern — the rule a CI
test checks must be in the tree the runner has, not in git history the runner lacks.

Exit: 0 clean; 1 with every failure named; 2 on setup problems (missing corpus, self-test).
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
# The pre-reorg snapshot + entailment fixture, repo-relative. A CI checkout has no git history
# to `git show de661e070^`, so the baseline corpus and its claims ship as committed data — the
# pattern scripts/retired_paths.txt set. load_tree() takes a root so a test can point the gate
# at a throwaway tree and plant a defect there; the tree is read, never written.
DATA = Path("backend/tests/unit/scripts/data/uplevel-cites")


def load_tree(root: Path):
    """(live docs/uplevel text, snapshot text, entailment fixture) for a repo root. Read-only."""
    docs = root / "docs/uplevel"
    live = {str(p.relative_to(docs)): p.read_text() for p in docs.rglob("*.md")}
    snap_dir = root / DATA
    snap = {p.name: p.read_text() for p in snap_dir.glob("*.md")}
    fixture = snap_dir / "entailments.json"
    return live, snap, (json.loads(fixture.read_text()) if fixture.is_file() else None)

# SOURCE files whose cites the gate holds true: rules.md, where the programme's cite debt lives
# and where #7054 repaid it. README.md is deliberately NOT a source — measured, it carries 0
# cites with a quoted section name; its .md mentions (CHANGELOG.md, ../developer/patterns/…)
# are navigation and lane-ownership prose, which this resolver's grammar would red as "target
# not found live" (all four exist at the repo root; verified by hand, not by a watcher — no
# drift rule covers docs/uplevel). Every live docs/uplevel file, README included, stays a TARGET.
SCAN = ["rules.md"]
# Names that look like file cites but are not cites INTO this corpus: root files (AGENTS.md,
# CHANGELOG), historical plans (17-action-plan.md), code/config (.env.example). The skip is
# CONDITIONAL on liveness (live_bases below): 00-audit.md, 01-mutation-policy.md, r2-sheet.md
# and feature-design.md ARE live docs/uplevel files, and an unconditional name skip would
# silently stop checking every cite to one the day it was named here. Skipped mentions print
# as a witness count — the skip-set must never be an invisible coverage hole.
ARTIFACTS = {
    "uplevel.md", "AGENTS.md", "00-audit.md", "feature-design.md", "17-action-plan.md",
    "feature-inventory.md", "agents-md-standard.md", "01-mutation-policy.md", "r2-sheet.md",
    "sandboxes.toml", "api.ts", "openapi.json", "config.py", ".env.example",
}
# One cite unit is a quoted name plus the § scope that qualifies IT, and the corpus chains units
# with `,`/`;`. The § used to be a single group placed BEFORE the names group, which made it dead
# code twice over: corpus order is `file "name" §3`, so it never captured (measured: item was None
# for all 127 rules.md cites), and a mid-chain § cut the chain — `rules.md:347` `… "Review and
# merge" §4, "Hot files"` silently dropped "Hot files". Putting the scope inside the unit fixes both.
# The unit's § group is deliberately NON-capturing: a capture inside a repeated unit shifts every
# later group index, and citations() keys group(2) on the file token. Name+scope are parsed from
# the chain by CITE_NAME_RE instead, which is separately testable.
CITE_UNIT = r'"[^"]+"(?:\s*§\s*\d+)?'
CITE_NAME_RE = re.compile(r'"([^"]+)"(?:\s*§\s*(\d+))?')
# The chain separator is every joiner the corpus actually uses (peer arm-audit's Task D, re-
# measured here: `per X.md "real" and "bogus".` was rc=0 — the `and`-joined name never entered
# group 4, so it was never checked, while the same bogus name comma-joined was rc=1). Control
# for how wide to go: prose quotes in docs/uplevel join with `,` `;` bare `and`/`or` and oxford
# `, or` (roles/owner-partner.md:51 has all three shapes in one line). A bare `and|or` cannot
# misfire on prose ("coordinator decision" and sends…): the branch only extends when another
# CITE_UNIT follows the joiner, and no corpus line has one. Narrowing this class can NEVER be
# caught through the corpus — fewer names checked is always greener — so the pin is the pair of
# selftest arms below, which feed the REAL parse.
CITE_JOIN = rf'(?:[;,]\s*(?:(?:and|or)\s+)?|(?:and|or)\s+)\s*{CITE_UNIT}'
CITE_RE = re.compile(
    r'(the deleted\s+)?((?:docs/uplevel/)?[\w./-]*\.md|README)( \s*section)?'
    rf'((?:\s*{CITE_UNIT})(?:\s*{CITE_JOIN})*)?'
)
DEAD_NAMES = {"50-coordination.md", "10-backend.md", "20-frontend.md", "30-ops.md", "40-docs.md"}
# A bold LABEL line start, list markers allowed — `**Remit.**` and `3. **Fetch.**` both count.
LABEL_START = r"^[ ]*(?:[-*]\s|\d+\.\s)*\*\*"


def read(path: Path) -> str | None:
    return path.read_text() if path.is_file() else None


def heads(text: str) -> set[str]:
    """Headings, bold labels (line start, list markers allowed), backticked ids, item numbers."""
    s = set(re.findall(r"^#{1,6}\s+(.*)$", text, re.M))
    s |= {x.strip("`").strip() for x in re.findall(
        r"^[ ]*(?:[-*]\s|\d+\.\s)*\*\*([^*(]+?)(?: ?\([^)]*\))?\.?\*\*", text, re.M)}
    s |= set(re.findall(r"`([A-Z]{1,2}\d*\.?\d*[a-z]?)`", text))
    s |= set(re.findall(r"^\s*(\d+)\.\s", text, re.M))
    return s


def joined(text: str) -> str:
    """Whitespace-collapsed: needles and verbatim checks run on joined prose, because rules.md
    wraps and a line-based grep is an absence-factory (ops-b's round-3 disclosure #1)."""
    return re.sub(r"\s+", " ", text)


def section(text: str, name: str, item: int | None = None) -> str | None:
    """Text of a heading/bold label (or an id-heading starting with name); item=n narrows to
    that ZERO-indent numbered item only — a §3 cite does not mean step 1."""
    lines = text.split("\n")
    for i, line in enumerate(lines):
        is_heading = bool(re.match(r"^#{1,6}\s+" + re.escape(name) + r"(\s|$|`)", line))
        is_label = not is_heading and bool(re.match(
            r"^[ ]*(?:[-*]\s|\d+\.\s)*\*\*" + re.escape(name) + r"(?: ?\([^)]*\))?\.?\*\*", line))
        if not (is_heading or is_label):
            continue
        # A HEADING section contains bold labels — `## The tick`'s steps ARE numbered bold
        # labels — so only a next heading ends it. A BOLD-LABEL section ends at the next label
        # too. Breaking a heading on its own bold content truncates every step list at step 1.
        out = []
        for j in range(i, len(lines)):
            if j > i and (re.match(r"^#{1,6}\s", lines[j])
                          or (is_label
                              and re.match(r"^[ ]*(?:[-*]\s|\d+\.\s)*\*\*[^*]+\*\*", lines[j]))):
                break
            out.append(lines[j])
        block = "\n".join(out)
        if item is None:
            return block
        # Corpus items come in TWO typographic forms, and the old pattern matched only one:
        #   live    `3. **Reviews first** (UR-32): …`   number outside the bold
        #   snapshot `**4. Merge.** The coordinator …`  number INSIDE the bold
        # A §4 cite into the snapshot therefore located nothing — which the §-cluster audit never
        # found because its own selftest arm handed section() a literal int and never ran a real
        # document through the parse (memory: hand-fed-fixtures-pin-one-arm-only).
        start = rf"^[ ]*(?:{item}\.\s|\*\*{item}\.\s)"
        nxt = rf"^[ ]*(?:{item + 1}\.\s|\*\*{item + 1}\.\s)"
        m = re.search(start + r".*?(?=" + nxt + r"|\Z)", block, re.S | re.M)
        return m.group(0) if m else None
    return None


def citations(text: str):
    """Yield (deleted, file, section_marker, quoted_names) for every cite-shaped token, where
    quoted_names is a list of (name, item) and item is the § scope that name carries or None.
    The scope rides the NAME, not the cite: `"Review and merge" §4, "Hot files"` scopes §4 to the
    first name only. Skipping is only ever mid-token — the offset test keys on the file token,
    group(2). What is an artifact vs a cite is POLICY (the corpus decides), so it lives in resolve().
    """
    j = re.sub(r"\n[ ]+", " ", text)
    for m in CITE_RE.finditer(j):
        deleted, f, sec_marker, quotes = m.groups()
        f = f.replace("docs/uplevel/", "")
        if f == "README":  # bare "README" in prose means docs/uplevel/README.md
            f = "README.md"
        pre = j[m.start(2) - 1] if m.start(2) else ""
        if re.match(r"[\w./<>-]", pre):  # e.g. `4n-<feature>.md` placeholder text
            continue
        names = [(n, int(it) if it else None)
                 for n, it in CITE_NAME_RE.findall(quotes or "")]
        yield bool(deleted), f, bool(sec_marker), names


def scope_claim(text: str, name: str, item: int) -> str | None:
    """None when a `name §item` cite is TRUE (the section has that item); else why it is false.
    A § scope is a CLAIM, not a label: before this function existed nothing anywhere checked it,
    which is the whole reason the grammar could be broken without a single test noticing."""
    block = section(text, name)
    if block is None:
        return f"section {name!r} not located"          # caller already reports the name itself
    if section(text, name, item) is None:
        have = sorted({int(n) for n in re.findall(
            r"^[ ]*(?:\*\*)?(\d+)\.\s", block, re.M)})
        return (f"has no item {item}"
                + (f" (items present: {', '.join(map(str, have))})" if have else " (no items at all)"))
    return None


def resolve(live_text: dict[str, str], snap_text: dict[str, str]):
    """Run the resolver over every scanned file. Returns (fails, tallies)."""
    fails: list[str] = []
    tall = {"live_sections": 0, "live_phrases": 0, "dead_ok": 0,
            "snap_sections": 0, "snap_phrases": 0, "artifacts_skipped": 0}
    # SOURCES are the rule files whose cites must be true (history records what died — scanning
    # it as a source would red on legitimate tombstones); TARGETS are every live file.
    live_bases = {k.split("/")[-1] for k in live_text}
    for fname in SCAN:
        text = live_text.get(fname)
        if text is None:
            fails.append(f"scanned source {fname} missing")
            continue
        # A cite whose target IS the file it is written in cannot be evidence by quoting itself.
        # resolve() tested the phrase fallback against joined(target), and target already contains
        # the citing sentence — so `per rules.md "Some Phrase"` went GREEN on a phrase that exists
        # nowhere except inside its own quotes (measured on 2e80eca72/8ed70fd3c: plant lands, rc=0,
        # tally prints `+ 1 verbatim phrases`, i.e. the gate CERTIFIES the count it just invented).
        # Blank every cite-shaped token out of the file's own text and verify a self-cite against
        # what is left: the cite still passes when the phrase is real prose elsewhere, and fails when
        # the only occurrence is the cite. Blanking ALL cite tokens (not just this one) also closes
        # cite-to-cite laundering, where one cite's quote vouches for another's.
        # Matched-then-blanked over the SAME fold citations() searches (`\n[ ]+` -> " "), because
        # blanking in raw-text space would put every span on the wrong bytes when a cite follows a
        # wrapped line — a fix that no-ops exactly as quietly as the bug it replaces.
        own_blank = CITE_RE.sub(lambda m: " " * (m.end() - m.start()),
                                re.sub(r"\n[ ]+", " ", text))
        for deleted, f, sec_marker, names in citations(text):
            qnames = [n for n, _ in names]  # for messages: the names, not the (name, item) pairs
            base = f.split("/")[-1]  # citations() already normalised bare README → README.md
            if base in ARTIFACTS and not deleted and base not in live_bases:
                tall["artifacts_skipped"] += 1  # witness: the skip-set is counted, never silent
                continue
            if deleted and sec_marker:
                # the deleted README section "X": a dead SECTION of a STILL-LIVE file. Two-sided:
                # absent now (else the provenance is a lie), present in the snapshot (else the
                # claim has no antecedent).
                tall["dead_ok"] += 1
                # _short(), not .get(base): live_text keys by RELATIVE PATH, so a basename lookup
                # returns None for every file in a subdir and the liveness check below would be
                # skipped on the shape it exists for. Today the corpus's six dead-section cites all
                # name README.md (a root file), so .get() happens to resolve — the bug is latent,
                # not live. The markerless branch already uses _short for this exact mapping.
                now = live_text.get(base) or live_text.get(_short(live_text, base) or "")
                pre = snap_text.get(base)
                for q, item in names:
                    if now is not None and q in heads(now):
                        fails.append(f"{fname}: provenance \"{q}\" is live in {base} again")
                    if pre is None:
                        fails.append(f"{fname}: snapshot lacks {base} "
                                     "for its dead-section cite")
                    elif not (re.search(r"^#{1,6}\s+" + re.escape(q), pre, re.M)
                              or re.search(LABEL_START + re.escape(q), pre, re.M)
                              or q in joined(pre)):
                        fails.append(f"{fname}: {base} \"{q}\" absent from the pre-reorg snapshot")
                    elif item is not None:  # a §N cite claims the snapshot section HAS item N
                        bad = scope_claim(pre, q, item)
                        if bad:
                            fails.append(f"{fname}: {base} \"{q}\" §{item} {bad}, so the "
                                         "pre-reorg scope claim is false")
                continue
            if deleted:
                if base in live_text or _short(live_text, base):
                    fails.append(f"{fname}: 'the deleted {base}' is NOT dead in the live tree")
                    continue
                tall["dead_ok"] += 1
                pre = snap_text.get(base)
                if pre is None:
                    if base in DEAD_NAMES or base in snap_text:
                        fails.append(f"{fname}: snapshot lacks {base} for its provenance cite")
                    continue  # dead files with no quoted names need no snapshot (file death proved)
                for q, item in names:
                    if re.search(r"^#{1,6}\s+" + re.escape(q), pre, re.M) or re.search(
                            LABEL_START + re.escape(q), pre, re.M):
                        tall["snap_sections"] += 1
                        if item is not None:  # the § is a claim about the snapshot's structure
                            bad = scope_claim(pre, q, item)
                            if bad:
                                fails.append(f"{fname}: deleted {base} \"{q}\" §{item} {bad}")
                    elif q in joined(pre):
                        # `corrects the deleted 50-coordination.md "Roles", "makes no
                        # decisions"` chains a section name and a PROSE phrase with a comma and
                        # carries no ` section` marker anywhere — requiring the marker here made
                        # the whole comma idiom unresolvable for every cite but the ones I edited.
                        tall["snap_phrases"] += 1
                        if item is not None:
                            fails.append(f"{fname}: deleted {base} \"{q}\" §{item} scopes a § to a "
                                         "prose phrase — a § needs a section behind it")
                    else:
                        fails.append(f"{fname}: deleted {base} \"{q}\": not a heading/label in "
                                     "the pre-reorg snapshot")
                # (no "is it live again here?" arm: the markerless deleted case has already proven
                # the file is NOT live at the branch above, so a name can never be live in it —
                # the same check runs live in the `deleted and sec_marker` branch. The arm that
                # used to sit here was unreachable by construction; measured: 18-19 tokens reached
                # it across the corpus and 7 planted shapes, sec_marker False in every one.)
                continue
            if "/" in f:
                matches = [f] if f in live_text else []
            else:
                matches = sorted(k for k in live_text
                                 if k.endswith("/" + f) or k == f)
                # A bare cite with QUOTED claims must not check those claims against a
                # possibly-wrong same-named file (r2-sheet.md collides with
                # templates/r2-sheet.md TODAY). A bare cite with NO names only asserts
                # existence — both candidates satisfy that, so any pick is true; silence is
                # only unsafe where claims ride on it (memory: nonunique-join-binds-wrong).
                if len(matches) > 1 and names:
                    fails.append(f"{fname}: bare cite {f!r} is ambiguous "
                                 f"({', '.join(matches[:4])}) and quotes {qnames} — cite a path")
                    continue
            target = live_text.get(matches[0]) if matches else None
            if target is None:
                fails.append(f"{fname}: cite target {f} not found live")
                continue
            for q, item in names:
                if q in heads(target) or q.strip("`") in heads(target):
                    tall["live_sections"] += 1
                    if item is not None:  # §N claims the LIVE section has item N
                        bad = scope_claim(target, q, item)
                        if bad:
                            fails.append(f"{fname}: {f} \"{q}\" §{item} {bad}")
                elif q in joined(own_blank if matches == [fname] else target):
                    # `own_blank`, not `target`, when the cite points into its OWN file: the citing
                    # sentence is part of target, so a phrase that exists only inside this cite's
                    # quotes used to satisfy the test and the gate printed `+ 1 verbatim phrases`
                    # for a count it had just authored (peer arm-audit's Task C, re-measured on
                    # 8ed70fd3c). A phrase that is real prose elsewhere in the file still passes —
                    # only the self-quoting occurrence stops counting. The heads() branch above is
                    # deliberately NOT self-blanked: a bold label is real structure, so a cite at
                    # its own label is a degenerate pointer, not a false claim, and the gate
                    # verifies truth rather than usefulness.
                    tall["live_phrases"] += 1
                    if item is not None:
                        fails.append(f"{fname}: {f} \"{q}\" §{item} scopes a § to a prose "
                                     "phrase — a § needs a section behind it")
                else:
                    fails.append(f"{fname}: section {q!r} not found in live {f}")
    return fails, tall


def _short(live_text: dict[str, str], f: str) -> str | None:
    """Map a bare basename (operator.md) to the scanned/live path that ends with it."""
    for k in live_text:
        if k.endswith("/" + f) or k == f:
            return k
    return None


def snapshot_sums(root: Path) -> tuple[list[str], int]:
    """Verify the committed snapshots against the SHA256SUMS manifest, (fails, n_verified).

    The provenance instrument reads these bytes as the RECORD of what existed pre-reorg; silent
    drift here rewrites that record under every verdict. The manifest pins no-drift-since-
    certification in a history-less CI checkout (scripts/retired_paths.txt pattern); the claim
    that those bytes equal `git show de661e070^` needs full history and stays prose.
    A manifest that lists no file verifies nothing — so n prints as a witness and an empty
    manifest is a fail, never a pass.
    """
    man = root / DATA / "SHA256SUMS"
    if not man.is_file():
        return [f"SETUP: {DATA}/SHA256SUMS missing — snapshot integrity unchecked"], -1
    listed: dict[str, str] = {}
    for line in man.read_text().splitlines():
        if line.startswith("#") or not line.strip():
            continue
        digest, _, name = line.partition("  ")
        listed[name.strip()] = digest.strip()
    if not listed:
        return ["SHA256SUMS lists 0 files — the integrity arm is vacuous"], 0
    fails: list[str] = []
    have = sorted(p.name for p in (root / DATA).glob("*.md"))
    if sorted(listed) != have:
        fails.append(f"SHA256SUMS lists {sorted(listed)} but the data dir has {have} "
                     "— a snapshot entered or left without the manifest")
    n = 0
    for name, digest in listed.items():
        p = root / DATA / name
        if not p.is_file():
            continue  # already failed above
        got = hashlib.sha256(p.read_bytes()).hexdigest()
        if got != digest:
            fails.append(f"snapshot {name} DRIFTED from SHA256SUMS ({got[:10]}… != {digest[:10]}…)")
        else:
            n += 1
    return fails, n


def entail(live_text: dict[str, str], snap_text: dict[str, str], fixture: list[dict]):
    fails, found = [], 0
    for c in fixture:
        text = (live_text if c["ref"] == "live" else snap_text).get(c["file"])
        if text is None:
            fails.append(f"fixture {c['rule']}: file {c['file']} absent at {c['ref']}")
            continue
        raw = text if c["section"] == "" else section(text, c["section"], c.get("item"))
        sec = joined(raw) if raw is not None else None
        if sec is None:
            fails.append(f"fixture {c['rule']}: section {c['section']!r} not located in "
                         f"{c['file']} @ {c['ref']}")
            continue
        found += 1
        # Case folded on BOTH sides. `joined()` lowercases its output, so a needle compared
        # as-written could never match a section containing capitals: a sentence-case needle in a
        # presence row was an unsatisfiable claim (a false red that reads like a content
        # violation), and in an emptiness pin it was permanently unfireable — a silent green
        # beside a check that claims text is absent. Every needle shipped at 2e80eca72 happened to
        # be lowercase, so both halves were latent until a fixture edit walked into the first one.
        have = [n for n in c["needles"] if n.lower() in sec.lower()]
        want = c.get("expect_present", True)
        if want and not have:
            # "lacks any of", not "lacks all of": `have` is a filter, so this row fires only when
            # NO needle matches — the list is alternative surface forms of one claim, not a
            # conjunction. The old wording read as AND and made authors add a 2nd needle
            # believing it tightened the row when it only widened how the row can pass.
            fails.append(f"{c['rule']}: {c['file']} \"{c['section']}\" lacks any of {c['needles']}")
        if not want and have:
            fails.append(f"{c['rule']}: PIN says {c['file']} \"{c['section']}\" must NOT say "
                         f"{have} — text was written where the cite claims no home exists; "
                         "move the cite with it")
    if found != len(fixture):
        fails.append(f"floor: located {found}/{len(fixture)} fixture sections (a missing section "
                     "is not an entailment failure, it is a blind check)")
    return fails


def selftest() -> list[tuple[bool, str]]:
    """The instrument must prove it can fire BEFORE it judges the tree: a planted fake cite
    and a planted heading must be caught by its own matcher (in memory, nothing touched).
    Returns one (ok, message) per arm — the count main() prints is len() of this list, so the
    witness cannot print a compliment the checks did not earn: bypass the call and the line
    reads 0/0, which is exactly what its old literal form (`"selftest: 4 arms fired"`) could
    never do (measured at 2e80eca72: `st = selftest()` -> `st = []` left rc=0, suite green, and
    the literal still printing "4 arms fired").
    Every arm feeds the REAL parse. An earlier § arm called `section(text, "T", 3)` with a
    literal 3 — it tested the locator while the broken grammar that was supposed to PRODUCE the
    3 stayed invisible (memory: hand-fed-fixtures-pin-one-arm-only)."""
    checks: list[tuple[bool, str]] = []
    bad = 'the deleted 50-coordination.md "Roles", "Sect That Never Was"\n'
    fires = [n for _d, _f, _s, ns in citations(bad) for n, _i in ns
             if n == "Sect That Never Was"]
    checks.append((bool(fires),
                   "selftest: resolver capture dropped a planted 3rd comma-chained name"))
    snap_like = "# Roles\n\ntext\n"
    checks.append((section(snap_like, "Sect That Never Was") is None,
                   "selftest: locator matched a heading that is not there"))
    # Joiner arms — the comma arm above proves the machinery; these pin the WIDENING, both ways.
    # An `and`-joined name that is never captured ships unchecked (peer arm-audit's Task D,
    # re-measured: `"real" and "bogus"` was rc=0 while the same bogus name comma-joined was
    # rc=1). But a joiner that over-extends turns ordinary prose into a cite and manufactures
    # REDS, so the negative arm is the one that lets the widening ship at all.
    def _names(s):
        return [n for _d, _f, _s, ns in citations(s) for n, _i in ns]
    for join, label in (("and", "and"), (", or", "oxford-or"), ("or", "bare-or")):
        got = _names(f'the deleted 50-coordination.md "Roles" {join} '
                     f'"Sect That Never Was"\n')
        checks.append((got == ["Roles", "Sect That Never Was"],
                       f"selftest: a {label}-joined cite name is dropped — the name after "
                       f"`{join}` is never checked"))
    # Negative: `and` + prose + a later quote. The joiner must stop when no CITE_UNIT follows it,
    # or `"coordinator decision" and sends anything else`-shaped prose (rules.md:32) starts
    # swallowing the next quoted phrase as a second cite name.
    prose = _names('per rules.md "Claiming and assigning work" and sends "status update" on.\n')
    checks.append((prose == ["Claiming and assigning work"],
                   "selftest: the cite joiner over-extends — it captured a quoted phrase that "
                   "prose, not a cite, put after the joiner"))
    # § scope: the parse must DELIVER the item, and the claim must be checkable both ways.
    itemized = "## T\n\n1. a\n2. b\n3. c\n"
    parsed = [ns for _d, _f, _s, ns in citations('per x.md "T" §3.')]
    checks.append((bool(parsed) and bool(parsed[0]) and parsed[0][0][1] == 3,
                   "selftest: § scope never reaches the resolver — a §3 cite could borrow "
                   "step 1 and nothing would notice"))
    checks.append((section(itemized, "T", 3) == "3. c\n",
                   "selftest: §-item narrowing failed (a §3 cite could borrow step 1)"))
    checks.append((section("## T\n\n**1. a.**\n**2. b.**\n**3. c.**\n", "T", 3) is not None,
                   "selftest: item locator missed the `**4. Merge.**` form — every snapshot "
                   "§-cite would locate nothing"))
    checks.append((scope_claim(itemized, "T", 99) is not None,
                   "selftest: scope_claim accepted a §99 cite into a 3-item section — the § "
                   "claim is not being checked"))
    checks.append((scope_claim(itemized, "T", 3) is None,
                   "selftest: scope_claim rejected a TRUE §3 cite — correct cites would red"))
    # chain integrity: a mid-chain § must not truncate the comma chain (the :347 shape).
    chain = [ns for _d, _f, _s, ns in citations('per x.md "A" §4, "B".')]
    checks.append((bool(chain) and [n for n, _i in chain[0]] == ["A", "B"],
                   "selftest: a mid-chain § dropped a comma-chained name — cites after the § "
                   "go unchecked"))
    checks.append((joined("wraps\nacross") == "wraps across",
                   "selftest: wrap-join failed (line-grep absence-factory is back)"))
    # Case folding, both directions of the hazard. joined() lowercases the haystack only, so a
    # sentence-case needle is UNSATISFIABLE: in a presence row that is a false red, in an
    # emptiness pin it is a permanently unfireable check — a green beside "this text is absent".
    # Both arms feed one fixture section so they fail together if the fold is ever dropped.
    mixed = {"a.md": "## T\n\nHeavy Agents Skip This Step.\n"}
    base = {"rule": "selftest", "ref": "live", "file": "a.md", "section": "T",
            "needles": ["Heavy Agents Skip"]}
    # `not present` / `bool(absent)` on the WHOLE fail list: entail() returns [] when satisfied,
    # so indexing [0] here would raise IndexError on the very state being asserted.
    present = entail(mixed, {}, [dict(base, expect_present=True)])
    absent = entail(mixed, {}, [dict(base, expect_present=False)])
    checks.append((not present,
                   "selftest: a sentence-case needle cannot match a lowercased section — a "
                   "presence fixture written with capitals is an unsatisfiable claim"))
    checks.append((bool(absent),
                   "selftest: an emptiness pin with a sentence-case needle can never fire — the "
                   "check that text is GONE reports green whether or not it is"))
    # A self-cite must not be its own evidence. resolve() checked the phrase fallback against the
    # target file, which CONTAINS the citing sentence, so a phrase that exists only inside the
    # cite's own quotes satisfied it (peer arm-audit's Task C; re-measured on 8ed70fd3c: plant
    # landed, rc=0, tally printed `+ 1 verbatim phrases` — a count the gate had just authored).
    # These two fixtures differ ONLY in whether the phrase is real prose elsewhere in the file, so
    # together they pin both directions: a revert of the self-blank un-fails the circular one (arm
    # 1 goes blind), and an over-blanking that rejects true cites fails the evidenced one (arm 2).
    _sc = "Heavy Agents Skip This Step Zqxj"
    circ = resolve({"rules.md": f'Prose. per rules.md "{_sc}".\n'}, {})[0]
    evidenced = resolve({"rules.md": f'Body says {_sc} somewhere.\n\n'
                                     f'Also: per rules.md "{_sc}".\n'}, {})[0]
    checks.append((bool(circ),
                   "selftest: a self-cite is satisfying itself — a phrase quoted only inside the "
                   "cite's own quotes is being counted as proof it exists"))
    checks.append((not evidenced,
                   "selftest: the self-cite blank over-reaches — it rejects a self-cite whose "
                   "phrase IS real prose elsewhere in the same file"))
    return checks


def main(argv: list[str]) -> int:
    root = Path(argv[0]).resolve() if argv else REPO
    live_text, snap_text, fixture = load_tree(root)
    if not live_text or len(live_text) < 5:
        print(f"SETUP: corpus is {len(live_text)} files under {root / 'docs/uplevel'} "
              "— too small to trust")
        return 2
    if fixture is None:
        print(f"SETUP: fixture missing at {root / DATA / 'entailments.json'}")
        return 2

    st = selftest()
    if not st:
        # A zero-arm selftest is not "all arms passed". `blind` above is computed FROM st, so an
        # empty st yields an empty blind list and the guard below never fires: bypassing the call
        # (`st = selftest()` -> `st = []`) certified the whole tree at rc=0 even after the witness
        # count became derived — the derived count prints 0/0 and main() still says ALL RESOLVE.
        # Same law as snapshot_sums' "SHA256SUMS lists 0 files — the integrity arm is vacuous".
        print("SETUP: selftest ran 0 arms — nothing proves the instrument can fire; "
              "tree verdicts withheld")
        return 2
    blind = [msg for ok, msg in st if not ok]
    if blind:
        print(f"SELF-TEST FAILED ({len(blind)}/{len(st)} arms blind; tree verdicts withheld):")
        [print("  -", x) for x in blind]
        return 2
    # Derived from st, never a literal: the witness line used to hard-code "4 arms fired", so
    # bypassing selftest() entirely still printed it. Now the count IS the measurement.
    print(f"selftest: {len(st)}/{len(st)} arms fired; corpus {len(live_text)} live files "
          f"({sum(len(t) for t in live_text.values())} chars), snapshot {len(snap_text)} files")

    sums_fails, n_sums = snapshot_sums(root)
    fails, tall = resolve(live_text, snap_text)
    fails += entail(live_text, snap_text, fixture)
    fails += sums_fails
    print(f"resolver: {tall['live_sections']} live sections + {tall['live_phrases']} verbatim "
          f"phrases; provenance: {tall['dead_ok']} claims, {tall['snap_sections']} snapshot "
          f"sections + {tall['snap_phrases']} phrases; "
          f"{tall['artifacts_skipped']} non-corpus mentions skipped")
    pins = sum(1 for c in fixture if not c.get("expect_present", True))
    print(f"entailment: {len(fixture) - pins} present-claims + {pins} emptiness pins; "
          f"integrity: {n_sums} snapshots match SHA256SUMS")
    if fails:
        print("FAILS:")
        [print("  -", x) for x in fails]
        return 1
    print("ALL ULEVEL CITES RESOLVE AND ENTAIL")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
