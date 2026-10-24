#!/usr/bin/env python3
"""Unlinked-pages census (W3.3 box 1): committed scanner for "pages in no nav and
linked from nowhere".

W3.3's first checkbox deletes "the pages in no nav and linked from nowhere (54 at
``d6ba78d5``; review the list in the PR)". Until this file existed that quantity had no
committed instrument either: ``audit_mkdocs.py`` checks nav->file existence (its check 6)
but never file->nav, and its link graph keys ``skip_dirs`` on the link's SOURCE, so a
reference written inside ``docs/plans/`` or ``docs/archive``/``templates`` is invisible
to it (proven there by planting the same impossible link in both a blind and a read
source: the blind one never reported). The plan's "(54 at d6ba78d5)" is unmatched, not
stale — this census's predecessors measured 230/459/424 there under different
definitions, and none reached 54; like the nav census (``nav_coverage.py``), the figure
is reported as unmatched rather than inherited.

WHAT COUNTS AS A LINK. The census resolves every markdown link and
``pymdownx.snippets`` include (``--8<-- "path"``; ``mkdocs.yml`` sets ``base_path:
['.']`` so those resolve from the REPO ROOT, and ``check_paths: true`` makes a missing
one fail the build — these are load-bearing edges) to its target on disk. A candidate
is *linked* when any of those resolve to it, from a living source OR from a record tree
— the deletion question is "would a human or a gate lose the page", not "does the nav
have it". A target that resolves to a DIRECTORY (``../detection-pipeline/``) is the
directory-form link: mkdocs serves that directory's ``index.md`` as the page, falling
back to the ``README.md`` it renames to index, so the link is recorded against that
page — the directory itself is not something a reader can land on. README/index
candidates are matched by their directory, never by the stem ``README``, which matches
every README in the tree.

THE LOOKBEHIND TRAP this file exists to close. A stem-needle census with a
``(?<![\\w/.-])`` lookbehind (added to suppress compound-identifier false positives like
``enrichment_light_url``) is blind to every markdown link that carries a directory
prefix — the ``/`` before the stem fails the lookbehind. Measured on this tree: that
form reported 51 unlinked pages; resolving links instead returns 29. Deleting to the
lower wrong number would have been the same Done-when-by-destruction the nav census
warns about; the resolved link graph is the instrument the PR executes against.

CLASSIFICATION. Only nav-missing LIVING pages enter the candidate set (from
``nav_coverage.py``'s classification — record trees and ``disabled`` stubs are already
out). Each candidate is then classified by who still mentions it:

  * ``linked``    — a resolved link or snippet include reaches it (NOT deletion
                    candidates; box 3's nav rebuild covers them).
  * ``cited``     — no link, but the basename appears in code, scripts, tests, or the
                    record trees (a committed instrument citing a page —
                    ``env_dead_vars.py`` cites ``operator/smtp-configuration.md`` — or a
                    live test's reference line). The mention needle is case-insensitive
                    with IDENTIFIER boundaries — a hit must not be preceded or followed
                    by ``[A-Za-z0-9_]`` — so ``enrichment_light_url`` does not cite an
                    ``enrichment`` page: that compound-identifier class is the reason the
                    retired-names census distinguishes whole-word from substring (18
                    living files there are substring-only). Deleting these needs the
                    citing file edited first; the PR triages, it does not assume.
  * ``nowhere``   — no resolved link and no mention anywhere in the scanned corpus.
                    This is the deletion-eligible list; every entry still gets a
                    per-page review in the PR (content may be box-3 nav work, not junk).

Output: JSON on stdout (candidates, counts, per-page class + referring files), one
summary line on stderr. Exit 0 always: the census measures, it does not judge; a read
failure is loud (exit 1).

Run:    uv run python scripts/audit/unlinked_pages.py [--root REPO] [--nav-json PATH]
Test:   uv run python -m pytest scripts/audit/test_unlinked_pages.py -q
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

# Extensions scanned for mentions (citations can live in code, configs and tests, not
# just markdown). Everything else is skipped; binary-ish suffixes are never grepped.
TEXT_SUFFIXES = {
    ".md",
    ".txt",
    ".yml",
    ".yaml",
    ".py",
    ".toml",
    ".sh",
    ".ts",
    ".tsx",
    ".json",
    ".html",
    ".css",
    ".cfg",
    ".ini",
    ".env",
}
# Markdown link: [text](target). Anchors (#) are stripped before resolution; external
# schemes and pure-fragment links are not file references.
LINK_RE = re.compile(r"\[[^\]]*\]\(\s*([^)\s]+)")
# pymdownx.snippets include: --8<-- "path"  (mkdocs.yml base_path: ['.'] → repo root).
SNIPPET_RE = re.compile(r'--8<--\s*["\']?([^\s"\']+)')
# nav_coverage.py lives NEXT TO this file in scripts/audit/. Reference it by this
# file's own location, not root-relative: --root may point at a checkout whose
# scripts/ tree is not this one (the tests point it at a bare fixture tree).
NAV_SCRIPT = Path(__file__).resolve().parent / "nav_coverage.py"


def resolve_link(target: str, src: Path, docs: Path) -> str | None:
    """Docs-relative path a link target resolves to, or None for non-file targets.

    ``docs`` must already be resolved (``docs.resolve()``). A target that lands on
    a DIRECTORY is the directory-form link: mkdocs serves that directory's
    ``index.md`` as the page (it renames ``README.md`` to index when index.md is
    absent; when both exist mkdocs itself warns about the collision and index.md,
    written last, wins — hence the probe order).
    """
    t = target.split("#", 1)[0]
    if not t or "://" in t or t.startswith(("mailto:", "//")):
        return None
    tgt = (src.parent / t).resolve()
    try:
        rel = tgt.relative_to(docs)
    except ValueError:
        return None
    rel_posix = rel.as_posix()
    if not rel_posix.endswith(".md"):
        for name in ("index.md", "README.md"):
            if (docs / rel_posix / name).is_file():
                return f"{rel_posix}/{name}"
    return rel_posix


def resolve_snippet(target: str, src: Path, docs: Path, root: Path) -> str | None:
    """Docs-relative path a --8<-- include resolves to.

    base_path is ['.'] (repo root), so try the root first; a relative include written
    src-relative is accepted too, but the root form is the one mkdocs actually loads.
    """
    if "://" in target:
        return None
    for base in (root, src.parent):
        cand = (base / target).resolve()
        try:
            rel = cand.relative_to(docs)
        except ValueError:
            continue
        return rel.as_posix()
    return None


def mention_pattern(needle: str) -> re.Pattern[str]:
    """Case-insensitive needle with identifier boundaries on both sides.

    ``\\b`` is not enough: it treats ``_`` as a word character but draws a
    boundary at ``-`` and ``.`` too, which is fine for hyphenated stems, while
    the underscore class is the one that must NOT count (``enrichment_light_url``
    naming an identifier, not the page). Both sides get the same custom class so
    a compound cannot cite a page by sharing its prefix or suffix.
    """
    return re.compile(r"(?<![A-Za-z0-9_])" + re.escape(needle) + r"(?![A-Za-z0-9_])", re.IGNORECASE)


def scan_corpus(root: Path) -> list[tuple[str, str]]:
    """(repo-relative path, text) for every scanned text file under root.

    Runs ``git ls-files`` when the root is a work tree so the census sees the same file
    set every other committed instrument sees (generated junk, caches and node_modules
    are untracked and must not become mentions); falls back to a suffix walk outside a
    work tree.
    """
    files: list[Path] = []
    tracked = None
    try:
        out = subprocess.run(
            ["git", "ls-files"], cwd=root, capture_output=True, text=True, timeout=60
        )
        if out.returncode == 0:
            tracked = out.stdout.splitlines()
    except (OSError, subprocess.SubprocessError):
        tracked = None
    if tracked is not None:
        for rel in tracked:
            p = root / rel
            if p.suffix.lower() in TEXT_SUFFIXES:
                files.append(p)
    else:
        skip = {".git", "__pycache__", "node_modules", ".venv", ".pytest_cache", ".mypy_cache"}
        for p in root.rglob("*"):
            if p.suffix.lower() not in TEXT_SUFFIXES:
                continue
            if any(part in skip for part in p.parts):
                continue
            files.append(p)
    corpus: list[tuple[str, str]] = []
    for p in files:
        try:
            corpus.append((p.relative_to(root).as_posix(), p.read_text(errors="replace")))
        except OSError as exc:
            print(f"unlinked_pages: cannot read {p}: {exc}", file=sys.stderr)
            raise SystemExit(1)
    return corpus


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--root", default=".", type=Path)
    ap.add_argument(
        "--nav-json",
        type=Path,
        default=None,
        help="nav_coverage.py JSON to take living_docs_missing from; default runs it",
    )
    args = ap.parse_args()
    root = args.root.resolve()
    docs = root / "docs"
    if not docs.is_dir():
        print(f"unlinked_pages: no docs/ under {root}", file=sys.stderr)
        return 1
    docs_resolved = docs.resolve()

    if args.nav_json:
        nav = json.loads(args.nav_json.read_text())
    else:
        proc = subprocess.run(
            [sys.executable, str(NAV_SCRIPT), "--root", str(root)],
            capture_output=True,
            text=True,
            timeout=300,
        )
        if proc.returncode != 0:
            print(f"unlinked_pages: nav_coverage.py failed: {proc.stderr[-400:]}", file=sys.stderr)
            return 1
        nav = json.loads(proc.stdout)
    candidates: list[str] = nav["living_docs_missing"]

    corpus = scan_corpus(root)
    link_in: dict[str, list[str]] = {}
    snippet_in: dict[str, list[str]] = {}
    for rel, text in corpus:
        src = root / rel
        # Only files under docs/ can carry markdown links into docs/ pages.
        try:
            src_rel_docs = src.relative_to(docs_resolved)
        except ValueError:
            src_rel_docs = None
        if src_rel_docs is not None and src.suffix == ".md":
            for t in LINK_RE.findall(text):
                r = resolve_link(t, src, docs_resolved)
                if r:
                    link_in.setdefault(r, []).append(rel)
            for t in SNIPPET_RE.findall(text):
                r = resolve_snippet(t, src, docs_resolved, root)
                if r and (docs_resolved / r).is_file():
                    snippet_in.setdefault(r, []).append(rel)

    classes: dict[str, dict] = {}
    for cand in candidates:
        p = Path(cand)
        links = link_in.get(cand, []) + snippet_in.get(cand, [])
        if links:
            classes[cand] = {"cls": "linked", "refs": sorted(set(links))}
            continue
        # README/index: the only mention needle that is honest is the directory path;
        # the stem matches every README in the corpus. EXCEPT at the docs root, where
        # the parent is "." — a needle of "." matches every period in the corpus and
        # would cite the whole tree. Root README/index references are real file links
        # (``(README.md)``), which the link graph already resolved; fall back to the
        # stem here so the mention sweep stays bounded.
        if p.stem in ("README", "index"):
            parent = str(p.parent)
            needle = p.stem if parent == "." else parent
        else:
            needle = p.stem
        pat = mention_pattern(needle)
        refs = [
            rel
            for rel, text in corpus
            # exclude the candidate ITSELF, exactly: an endswith() test would also
            # swallow a same-named file in a different directory (candidate
            # guide.md, referrer docs/deep/guide.md) and invent silence.
            if rel != f"docs/{cand}" and pat.search(text)
        ]
        classes[cand] = {"cls": "cited" if refs else "nowhere", "refs": sorted(set(refs))}

    counts = {"linked": 0, "cited": 0, "nowhere": 0}
    for c in classes.values():
        counts[c["cls"]] += 1

    result = {
        "nav_source": nav.get("nav_source"),
        "candidates": len(candidates),
        "counts": counts,
        "pages": [
            {"path": k, "cls": v["cls"], "refs": v["refs"]} for k, v in sorted(classes.items())
        ],
    }
    json.dump(result, sys.stdout, indent=2)
    sys.stdout.write("\n")
    print(
        f"O1.7 unlinked-pages: {len(candidates)} living nav-missing candidates -> "
        f"{counts['linked']} linked, {counts['cited']} cited, {counts['nowhere']} nowhere "
        f"(nowhere = the deletion-review list)",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
