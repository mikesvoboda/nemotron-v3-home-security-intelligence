#!/usr/bin/env python3
"""Nav-coverage census (W3.3): committed scanner for "every living doc is in the nav".

W3.3's Done-when says "every living doc is in the nav", and until this file
existed that quantity had NO committed instrument. Two predecessors exist and
neither computes it: ``scripts/audit_mkdocs.py`` checks that nav targets exist
(check 6) but never the reverse, and its nav regex ``":\\s*([^\\s#]+\\.md)\\s*$"``
cannot see a directory-form entry at all, so a nav entry ``- Section: some/dir/``
pointing at nothing is invisible to it. The plan text quotes "54 at d6ba78d5"
for "pages in no nav and linked from nowhere" and that figure came from an
uncommitted scan — it does not reproduce at d6ba78d5 under any definition tried
here (this census's parent-of-record instrument returns 230 unlinked there, 459
nav-missing, 424 nav-missing-and-living), so it is reported as unmatched rather
than inherited. See the PR body; the numbers in this paragraph are the argument
for why the instrument had to be committed before the cleanup started.

AUTHORITY. The nav is not re-parsed from YAML text. The YAML nav is a tree of
``{title: target}`` pairs and hand-parsing it drifts on exactly the live file:
``mkdocs.yml`` contains ``- AGENTS.md Standard: developer/agents-md-standard.md``
(a TITLE containing "AGENTS.md"), and a ``[^\\s'#]+\\.md`` extractor reading
whole lines captures "AGENTS.md" and concludes docs/AGENTS.md is nav'd when
mkdocs reports it missing. It also contains directory-form entries covering a
README.md no leaf names. So this census binds mkdocs' own resolution — the same
code path that emits the build warning — and falls back to the build log's own
warning block (mkdocs' words, not mine) when mkdocs cannot be imported.

mkdocs is NOT a declared dependency of this project: ``pyproject.toml`` carries
``mkdocs-material`` / ``mkdocs-awesome-pages-plugin`` / ``mkdocs-minify-plugin``
and mkdocs arrives transitively. The fallback is therefore load-bearing, not
decorative: it must be exercised by the test suite, not merely present.

CLASSIFICATION, not filtering. Every nav-missing page is reported. Pages the
plan does not mean are FLAGGED, never dropped:
  * ``disabled`` — frontmatter ``disabled: true``. All 30 redirect stubs under
    docs/development/ at main carry exactly this flag (set-equal: no other page
    in docs/ carries it, and no stub lacks it). Their nav absence is the stub's
    PURPOSE — a stub is a page that must not be in the nav.
  * ``record`` — the dated record trees, the same tuple
    ``scripts/audit/retired_names.py`` ships (docs/plans/, docs/superpowers/,
    docs/vss-integration/, docs/uplevel/). Records are history; B3.3/W1.1/W3.3
    do not edit them, and counting them measures the wrong corpus.
The headline is the LIVING and NOT-disabled count; the other buckets are
reported beside it so the flip to gating is a switch, not a rewrite — the same
reporting-only-then-flip shape ``line_caps:`` in .agents-md-validator.yml uses.

Output: JSON on stdout (corpus + covered/missing + per-page flags + dangling nav
targets + a per-directory rollup), one summary line on stderr. Exit 0 always:
the census measures, it does not judge; a read failure is loud (exit 1).

Run:    uv run python scripts/audit/nav_coverage.py [--root REPO]
Test:   uv run python -m pytest scripts/audit/test_nav_coverage.py -q
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

# Must stay equal to retired_names.RECORD_DOC_PREFIXES; the test pins it.
RECORD_DOC_PREFIXES = (
    "docs/plans/",
    "docs/superpowers/",
    "docs/vss-integration/",
    "docs/uplevel/",
)
# The tuples above are REPO-relative because retired_names.py walks the whole
# repo. This census walks docs/, so its paths are DOCS-relative and a raw
# startswith("docs/plans/") against them is never true -- which silently turns
# the record exemption off and would have billed ~100 dated record pages as nav
# debt. Derive, never duplicate: one literal, one translation.
RECORD_DOC_REL = tuple(p[len("docs/") :] for p in RECORD_DOC_PREFIXES)
NAV_WARNING_HEAD = "not included in the"


def is_record(rel: str) -> bool:
    return rel.startswith(RECORD_DOC_REL)


def frontmatter_flags(text: str) -> dict[str, str]:
    """Top-level scalar keys of a YAML frontmatter block, stdlib only.

    Deliberately not a YAML parse: a frontmatter block is small and flat, and a
    YAML import makes this script fail on documents the docs tree actually
    contains. Only top-level keys are read (indented lines are skipped) so a
    nested ``search: exclude: true`` cannot be misread as ``disabled: true``.
    """
    m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    if not m:
        return {}
    out: dict[str, str] = {}
    for line in m.group(1).splitlines():
        if not line or line[0] in " \t#":
            continue
        if ":" not in line:
            continue
        key, _, val = line.partition(":")
        out[key.strip()] = val.strip().strip("'\"")
    return out


def is_disabled(text: str) -> bool:
    return frontmatter_flags(text).get("disabled", "").lower() == "true"


def _node_targets(node) -> list[str]:
    """Every string target inside one nav node, at any depth, title-free.

    mkdocs nav nodes are: a list of children; a {key: value} where the key is a
    TITLE and the value is a child (so titles never become targets); or a plain
    string target. A ``- AGENTS.md Standard: x.md`` line is the {key: value}
    case and yields only ``x.md``.
    """
    out: list[str] = []
    if isinstance(node, str):
        out.append(node)
    elif isinstance(node, dict):
        for value in node.values():
            out.extend(_node_targets(value))
    elif isinstance(node, list):
        for child in node:
            out.extend(_node_targets(child))
    return out


def nav_targets_via_mkdocs(root: Path) -> list[str] | None:
    """Raw nav targets via mkdocs' config loader, or None if unavailable.

    ``load_config`` validates the file and runs each plugin's ``on_config`` hook,
    but awesome-pages builds its nav during ``on_files`` — later — so the ``nav``
    key this returns is the YAML nav, NOT the nav the site renders. Measured on
    this repo at 90f820e3d: the build log treats ``README.md`` and
    ``templates/AGENTS.md`` as nav'd and cfg.nav does not list them, so this mode
    reports 440 missing where mkdocs itself says 438 -- and cfg.nav mode agrees
    with the log EXACTLY once those two are subtracted, which is what makes the
    divergence attributable rather than noise. That is why the caller prefers a
    build log and warns here when the plugin is enabled.
    """
    try:
        from mkdocs.config import load_config
    except Exception:  # pragma: no cover - exercised via the fallback path
        return None
    try:
        cfg = load_config(str(root / "mkdocs.yml"))
    except Exception as exc:  # a broken config must not look like an empty nav
        print(f"nav_coverage: mkdocs could not load mkdocs.yml: {exc}", file=sys.stderr)
        return None
    nav = cfg.get("nav")
    if "awesome-pages" in cfg.get("plugins", {}):
        print(
            "nav_coverage: WARNING awesome-pages is enabled and --build-log was not "
            "given; the YAML nav is being read directly, so pages the plugin injects "
            "will be counted as nav-missing",
            file=sys.stderr,
        )
    if nav is None:
        # nav: absent means awesome-pages auto-generates the whole nav; nothing
        # can be "missing" from a nav nobody wrote. Say so loudly.
        print("nav_coverage: mkdocs.yml has no nav: block; nothing to measure", file=sys.stderr)
        return []
    return _node_targets(nav)


def nav_targets_via_build_log(log_path: Path) -> list[str]:
    """Inverse of mkdocs' own warning block: everything NOT listed is covered.

    The block mkdocs emits is two-spspace indented (``  - path.md``). A
    four-space guess silently yields an empty set and every downstream headline
    becomes a confident zero, so the parser asserts on itself.
    """
    lines = log_path.read_text(errors="replace").splitlines()
    in_block = False
    entries: list[str] = []
    for line in lines:
        if NAV_WARNING_HEAD in line and "nav" in line:
            in_block = True
            continue
        if in_block and re.match(r"^  - \S", line):
            entries.append(line[4:].strip())
        elif in_block:
            in_block = False
    if not entries:
        raise SystemExit(
            "nav_coverage: build log contained no 'not included in the nav' block; "
            "refusing to report zero nav-missing pages"
        )
    return entries


def canonicalize(target: str, corpus: set[str]) -> set[str]:
    """Which corpus files a raw nav target covers, honoring mkdocs' node rules.

    A target may be `a/b.md`, `a/b`, `a/b/`, `a/b/index.md`, or a directory
    whose README.md mkdocs canonicalizes to index.md. External links (any
    scheme, or an absolute URL) cover nothing and are not dangling.
    """
    t = target.strip().strip("'\"")
    if not t or "://" in t or t.startswith(("mailto:", "//")) or t.startswith("#"):
        return set()
    t = t.removeprefix("/")
    parts = t.split("/")
    last = parts[-1]
    if last.endswith(".md"):
        stem = last[: -len(".md")]
        parent = "/".join(parts[:-1])
        if stem in ("index", "README"):
            # an explicit node file: it and its sibling ARE the same node
            node_dir = parent
            cands = {t, f"{node_dir}/README.md", f"{node_dir}/index.md"}
        else:
            # A plain file node covers ONLY itself. The temptation is to also
            # cover the sibling directory of the same name when it exists --
            # don't. mkdocs.yml has `architecture/data-model.md` in the nav and
            # `architecture/data-model/README.md` on disk; mkdocs' own build
            # warning lists the README as NOT in the nav (a URL collision it
            # resolves its own way), so covering it here makes a real nav gap
            # read as covered. Measured, not theorized: the candidate-soup form
            # of this function disagreed with the build log on exactly that file.
            cands = {t}
    else:
        # a directory (with or without a trailing slash) covers its node file
        base = t.rstrip("/")
        cands = {base + ".md", f"{base}/index.md", f"{base}/README.md"}
        if not base:  # target was "/"
            cands |= {"index.md", "README.md"}
    return {c for c in cands if c in corpus}


def is_local_target(target: str) -> bool:
    t = target.strip().strip("'\"")
    return bool(t) and "://" not in t and not t.startswith(("//", "mailto:", "#", "mailto"))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--root", default=".", type=Path)
    ap.add_argument(
        "--build-log",
        type=Path,
        default=None,
        help="mkdocs build log to read the nav warning block from instead of importing mkdocs",
    )
    args = ap.parse_args()
    root = args.root.resolve()
    docs = root / "docs"
    if not docs.is_dir():
        print(f"nav_coverage: no docs/ under {root}", file=sys.stderr)
        return 1

    corpus: dict[str, str] = {}
    for p in sorted(docs.rglob("*.md")):
        rel = str(p.relative_to(docs))
        if any(part.startswith(".") for part in p.relative_to(docs).parts):
            continue
        try:
            corpus[rel] = p.read_text(errors="replace")
        except OSError as exc:
            print(f"nav_coverage: cannot read {p}: {exc}", file=sys.stderr)
            return 1

    # AUTHORITY ORDER, established by measurement rather than preference: the
    # build log is mkdocs' own answer AFTER plugins have run, and cfg.nav is the
    # YAML nav BEFORE them. On this repo the difference is real -- the log says
    # README.md and templates/AGENTS.md are in the nav and cfg.nav does not
    # contain them, because awesome-pages injects them. So: log when we have one,
    # cfg.nav otherwise, and never let cfg.nav mode pass silently while the
    # plugin is enabled.
    via = "build-log" if args.build_log else "mkdocs"
    targets = None
    if args.build_log:
        missing_from_log = set(nav_targets_via_build_log(args.build_log))
        targets = sorted(set(corpus) - missing_from_log)
    else:
        targets = nav_targets_via_mkdocs(root)
        if targets is None:
            print(
                "nav_coverage: mkdocs is not importable and no --build-log was given; "
                "mkdocs is a transitive dep here, so pass --build-log or install it",
                file=sys.stderr,
            )
            return 1

    covered: set[str] = set()
    dangling: list[str] = []
    for t in targets:
        hit = canonicalize(t, set(corpus))
        if not hit and is_local_target(t):
            dangling.append(t)
        covered |= hit
    # build-log mode: the log already IS the missing set; intersect to stay exact
    if via == "build-log":
        covered &= set(corpus)

    missing = set(corpus) - covered
    flags: dict[str, list[str]] = {}
    for rel in sorted(missing):
        f: list[str] = []
        if is_disabled(corpus[rel]):
            f.append("disabled")
        if is_record(rel):
            f.append("record")
        if f:
            flags[rel] = f
    living_missing = sorted(missing - {r for r, f in flags.items() if "disabled" in f or "record" in f})

    by_dir: dict[str, int] = {}
    for rel in living_missing:
        by_dir[rel.split("/", 1)[0] if "/" in rel else "<docs-root>"] = (
            by_dir.get(rel.split("/", 1)[0] if "/" in rel else "<docs-root>", 0) + 1
        )

    result = {
        "nav_source": via,
        "corpus_size": len(corpus),
        "nav_targets": sorted(targets),
        "covered": sorted(covered),
        "missing": [{"path": r, "flags": flags.get(r, [])} for r in sorted(missing)],
        "living_docs_missing": living_missing,
        "by_flag": [{"path": r, "flags": f} for r, f in sorted(flags.items())],
        "dangling_nav_targets": sorted(set(dangling)),
        "living_missing_by_dir": dict(sorted(by_dir.items(), key=lambda kv: (-kv[1], kv[0]))),
    }
    json.dump(result, sys.stdout, indent=2)
    sys.stdout.write("\n")
    # The `O1.7 <name>:` prefix is the scripts/audit series label, not the
    # owning package: env_dead_vars.py serves O3.3 and literal_groups.py serves
    # BB.1 and both print O1.7, so a census here that invented a W3.3 prefix
    # would fall out of any grep on the series. The owner goes in the body.
    print(
        f"O1.7 nav-coverage: {len(corpus)} docs pages, {len(covered)} in nav, "
        f"{len(missing)} not in nav ({len(living_missing)} living, W3.3's nav debt; "
        f"source={via}), {len(dangling)} dangling nav targets",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
