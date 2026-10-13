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
# Tokens that look like file cites but are not: artifacts, templates, placeholders.
ARTIFACTS = {
    "uplevel.md", "AGENTS.md", "00-audit.md", "feature-design.md", "17-action-plan.md",
    "feature-inventory.md", "agents-md-standard.md", "01-mutation-policy.md", "r2-sheet.md",
    "sandboxes.toml", "api.ts", "openapi.json", "config.py", ".env.example",
}
CITE_RE = re.compile(
    r'(the deleted\s+)?((?:docs/uplevel/)?[\w./-]*\.md|README)( \s*section)?'
    r'((?:\s*§\d+)?)((?:\s*"[^"]+")(?:\s*[;,]\s*"[^"]+")*)?'
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
        m = re.search(rf"^{item}\.\s.*?(?=^\s*{item + 1}\.\s|\Z)", block, re.S | re.M)
        return m.group(0) if m else None
    return None


def citations(text: str):
    """Yield (deleted, file, section_marker, item, quoted_names) skipping artifact and
    mid-token matches — the offset test keys on the file token itself, group(2)."""
    j = re.sub(r"\n[ ]+", " ", text)
    for m in CITE_RE.finditer(j):
        deleted, f, sec_marker, sec_n, quotes = m.groups()
        f = f.replace("docs/uplevel/", "")
        if f == "README":  # bare "README" in prose means docs/uplevel/README.md
            f = "README.md"
        if f.split("/")[-1] in ARTIFACTS and not deleted:
            continue
        pre = j[m.start(2) - 1] if m.start(2) else ""
        if re.match(r"[\w./<>-]", pre):  # e.g. `4n-<feature>.md` placeholder text
            continue
        names = re.findall(r'"([^"]+)"', quotes or "")
        item = int(sec_n.strip("§")) if sec_n and sec_n.strip("§").isdigit() else None
        yield bool(deleted), f, bool(sec_marker), item, names


def resolve(live_text: dict[str, str], snap_text: dict[str, str]):
    """Run the resolver over every scanned file. Returns (fails, tallies)."""
    fails: list[str] = []
    tall = {"live_sections": 0, "live_phrases": 0, "dead_ok": 0,
            "snap_sections": 0, "snap_phrases": 0}
    # SOURCES are the rule files whose cites must be true (history records what died — scanning
    # it as a source would red on legitimate tombstones); TARGETS are every live file.
    for fname in SCAN:
        text = live_text.get(fname)
        if text is None:
            fails.append(f"scanned source {fname} missing")
            continue
        for deleted, f, sec_marker, _item, names in citations(text):
            base = f.split("/")[-1]  # citations() already normalised bare README → README.md
            if deleted and sec_marker:
                # the deleted README section "X": a dead SECTION of a STILL-LIVE file. Two-sided:
                # absent now (else the provenance is a lie), present in the snapshot (else the
                # claim has no antecedent).
                tall["dead_ok"] += 1
                now = live_text.get(base)
                pre = snap_text.get(base)
                for q in names:
                    if now is not None and q in heads(now):
                        fails.append(f"{fname}: provenance \"{q}\" is live in {base} again")
                    if pre is None:
                        fails.append(f"{fname}: snapshot lacks {base} "
                                     "for its dead-section cite")
                    elif not (re.search(r"^#{1,6}\s+" + re.escape(q), pre, re.M)
                              or re.search(LABEL_START + re.escape(q), pre, re.M)
                              or q in joined(pre)):
                        fails.append(f"{fname}: {base} \"{q}\" absent from the pre-reorg snapshot")
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
                for q in names:
                    if re.search(r"^#{1,6}\s+" + re.escape(q), pre, re.M) or re.search(
                            LABEL_START + re.escape(q), pre, re.M):
                        tall["snap_sections"] += 1
                    elif q in joined(pre):
                        # `corrects the deleted 50-coordination.md "Roles", "makes no
                        # decisions"` chains a section name and a PROSE phrase with a comma and
                        # carries no ` section` marker anywhere — requiring the marker here made
                        # the whole comma idiom unresolvable for every cite but the ones I edited.
                        tall["snap_phrases"] += 1
                    else:
                        fails.append(f"{fname}: deleted {base} \"{q}\": not a heading/label in "
                                     "the pre-reorg snapshot")
                if sec_marker and names:
                    # a dead SECTION of a STILL-LIVE file (README case): also require absence now
                    now = live_text.get(base, "")
                    for q in names:
                        if q in heads(now):
                            fails.append(f"{fname}: provenance \"{q}\" is live in {base} again")
                continue
            target = live_text.get(f if "/" in f else _short(live_text, f))
            if target is None:
                fails.append(f"{fname}: cite target {f} not found live")
                continue
            for q in names:
                if q in heads(target) or q.strip("`") in heads(target):
                    tall["live_sections"] += 1
                elif q in joined(target):
                    tall["live_phrases"] += 1
                else:
                    fails.append(f"{fname}: section {q!r} not found in live {f}")
    return fails, tall


def _short(live_text: dict[str, str], f: str) -> str | None:
    """Map a bare basename (operator.md) to the scanned/live path that ends with it."""
    for k in live_text:
        if k.endswith("/" + f) or k == f:
            return k
    return None


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
        have = [n for n in c["needles"] if n in sec.lower()]
        want = c.get("expect_present", True)
        if want and not have:
            fails.append(f"{c['rule']}: {c['file']} \"{c['section']}\" lacks all of {c['needles']}")
        if not want and have:
            fails.append(f"{c['rule']}: PIN says {c['file']} \"{c['section']}\" must NOT say "
                         f"{have} — text was written where the cite claims no home exists; "
                         "move the cite with it")
    if found != len(fixture):
        fails.append(f"floor: located {found}/{len(fixture)} fixture sections (a missing section "
                     "is not an entailment failure, it is a blind check)")
    return fails


def selftest() -> list[str]:
    """The instrument must prove it can fire BEFORE it judges the tree: a planted fake cite
    and a planted heading must be caught by its own matcher (in memory, nothing touched)."""
    bad = 'the deleted 50-coordination.md "Roles", "Sect That Never Was"\n'
    fires = [n for d, f, s, i, ns in citations(bad) for n in ns if n == "Sect That Never Was"]
    out = []
    if not fires:
        out.append("selftest: resolver capture dropped a planted 3rd comma-chained name")
    snap_like = "# Roles\n\ntext\n"
    if section(snap_like, "Sect That Never Was") is not None:
        out.append("selftest: locator matched a heading that is not there")
    if section("## T\n\n1. a\n2. b\n3. c\n", "T", 3) != "3. c\n":
        out.append("selftest: §-item narrowing failed (a §3 cite could borrow step 1)")
    if joined("wraps\nacross") != "wraps across":
        out.append("selftest: wrap-join failed (line-grep absence-factory is back)")
    return out


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
    if st:
        print("SELF-TEST FAILED (the instrument is blind; tree verdicts withheld):")
        [print("  -", x) for x in st]
        return 2
    print(f"selftest: 4 arms fired; corpus {len(live_text)} live files "
          f"({sum(len(t) for t in live_text.values())} chars), snapshot {len(snap_text)} files")

    fails, tall = resolve(live_text, snap_text)
    fails += entail(live_text, snap_text, fixture)
    print(f"resolver: {tall['live_sections']} live sections + {tall['live_phrases']} verbatim "
          f"phrases; provenance: {tall['dead_ok']} claims, {tall['snap_sections']} snapshot "
          f"sections + {tall['snap_phrases']} phrases")
    pins = sum(1 for c in fixture if not c.get("expect_present", True))
    print(f"entailment: {len(fixture) - pins} present-claims + {pins} emptiness pins")
    if fails:
        print("FAILS:")
        [print("  -", x) for x in fails]
        return 1
    print("ALL ULEVEL CITES RESOLVE AND ENTAIL")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
