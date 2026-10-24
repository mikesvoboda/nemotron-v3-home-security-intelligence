#!/usr/bin/env python3
r"""Tests for scripts/audit/unlinked_pages.py (W3.3 box 1).

Run explicitly (scripts/ is outside pytest testpaths):

    uv run python -m pytest scripts/audit/test_unlinked_pages.py -q

The fixture tree pins the decisions this census exists to get right. Each one is
a defect this census's PREDECESSORS actually made on the live tree, so none is
hypothetical:

  * a link whose stem is preceded by a directory separator (``api/x.md``,
    ``../deep/guide.md``) must count as a link to its target. The stem-needle
    census with a ``(?<![\w/.-])`` lookbehind (added to suppress compound
    identifiers like ``enrichment_light_url``) reported 51 unlinked pages on the
    live tree; resolving links instead returns 29 — the lookbehind hid 21 real
    links.
  * a link from a RECORD tree still counts: the question is whether a human or a
    gate loses the page, not whether the nav has it. ``audit_mkdocs.py``'s
    ``skip_dirs`` keys on the link SOURCE, so references written inside
    ``docs/plans/`` are invisible to that checker (proven there by planting the
    same link in a blind and a read source).
  * a ``--8<-- "path"`` snippet include resolves from the REPO ROOT (mkdocs.yml
    sets ``base_path: ['.']``), not from the including file's directory — and
    ``check_paths: true`` makes the include load-bearing.
  * a DIRECTORY-FORM link (``../arch/``) resolves to the page mkdocs serves for
    that directory — ``index.md``, else ``README.md`` renamed to index. An
    explicit ``README.md`` link stays a link to README.md itself when index.md
    also exists (mkdocs warns about that collision; index wins the URL).
  * a README/index candidate is matched by its DIRECTORY path, never by the
    stem: the stem ``README`` matches every README in the corpus (237 files on
    the live tree), which turned "mentioned in llms.txt" into noise.
  * a page named by a committed instrument's string literal is ``cited`` —
    deleting it orphans the citers. The live tree carries the shape:
    ``env_dead_vars.py`` cites ``operator/smtp-configuration.md``.
  * the mention needle carries identifier boundaries: ``SMTP_CONFIGURATION_URL``
    must NOT cite ``operator/smtp.md`` — the compound-identifier class is why
    retired_names.py distinguishes whole-word from substring (18 living files
    there are substring-only).
  * the self-exclusion is EXACT (``rel == docs/<cand>``): an ``endswith``
    exclusion would also swallow a same-named file in a different directory and
    invent silence. The ``notes.md`` / ``research/notes.md`` pair pins both
    directions of that.
  * the candidate set comes from nav_coverage.py's LIVING classification: a
    ``disabled: true`` stub or a dated record page must never enter it.

The fixture's arithmetic is pinned as literals, not recomputed: 16 docs pages,
nav covers ``index.md`` only, 15 missing, 1 record (``plans/``) + 1 disabled
(``development/moved.md``) flagged away, 13 living candidates -> 5 linked,
4 cited, 4 nowhere. Any resolver breakage shifts one of those numbers.

"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).parent
SCRIPT = HERE / "unlinked_pages.py"

# A tree whose nav covers exactly index.md; every other living page is nav debt.
MKDOCS_YML = """\
site_name: Fixture
theme:
  name: material
nav:
  - Home: index.md
"""

DOCS_FILES = {
    "index.md": "# home\n",
    # LINKED via a dir-prefixed relative link (the lookbehind-trap shape: the
    # stem is preceded by "api/").
    "api/analytics-endpoints.md": "# analytics\n",
    "hub.md": "# hub page\n[Analytics](api/analytics-endpoints.md#baseline)\n",
    # LINKED via a RECORD-tree link — the blind-source class: invisible to
    # audit_mkdocs.py's skip_dirs, load-bearing here.
    "plans/2026-01-01-old.md": "points at [the guide](../deep/guide.md)\n",
    "deep/guide.md": "# guide\n",
    # LINKED via a snippet include resolved from the REPO ROOT.
    "snipped.md": "# snipped\n",
    "agent.md": '--8<-- "docs/snipped.md"\n',
    # arch/ carries BOTH node files: the dir-form link must land on index.md and
    # the explicit README.md link must stay on README.md. (index.md's body says
    # "arch home", NOT "arch hub" — "hub" is hub.md's needle and a bounded hit
    # here would falsely cite it.)
    "arch/index.md": "# arch home\n",
    "arch/README.md": "# arch readme\n",
    "guides/direct.md": "[Arch](../arch/README.md)\n",
    "guides/dirlink.md": "[Arch](../arch/)\n",
    # CITED only: no link anywhere, but a code file names the stem.
    "operator/smtp.md": "# smtp\n",
    # CITED only via a record-tree PROSE mention (no link).
    "research/old-scan.md": "# stale scan\n",
    "uplevel/00-audit.md": "the scan lives in research/old-scan.md historically\n",
    # The same-named pair: each cites the other by stem, neither by link.
    "notes.md": "# notes\n",
    "research/notes.md": "# research notes\n",
    # README candidates that REACH the mention needle (arch/README.md never does —
    # the link phase rescues it first). research/README.md exercises the
    # directory-needle path ("research" appears in the uplevel prose and in
    # research/notes.md's own title). The ROOT README.md exercises the
    # parent-'.' fallback: str(parent) would be "." — a needle matching every
    # period in the corpus — so the census must fall back to the stem, whose
    # only bounded mention is the explicit README.md link target above.
    "research/README.md": "# research readme\n",
    "README.md": "# root readme\n",
    # A disabled stub: out of the nav by design, never a candidate.
    "development/moved.md": "---\ndisabled: true\n---\n# moved\n",
}

CODE_FILES = {
    # outside docs/: a committed instrument's literal naming the page
    "scripts/audit/env_dead_vars.py": 'X = "docs/operator/smtp.md; re-check"\n',
    # a compound identifier sharing smtp's prefix: must NOT cite smtp.md
    "scripts/audit/other.py": "SMTP_CONFIGURATION_URL = 'x'\n",
}

EXPECTED_COUNTS = {"linked": 5, "cited": 6, "nowhere": 4}
EXPECTED_CANDIDATES = 15
EXPECTED_STDERR = (
    "O1.7 unlinked-pages: 15 living nav-missing candidates -> "
    "5 linked, 6 cited, 4 nowhere (nowhere = the deletion-review list)\n"
)


def build_tree(root: Path) -> None:
    (root / "mkdocs.yml").write_text(MKDOCS_YML, encoding="utf-8")
    docs = root / "docs"
    for rel, body in DOCS_FILES.items():
        p = docs / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(body, encoding="utf-8")
    for rel, body in CODE_FILES.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(body, encoding="utf-8")


def run_census(root: Path) -> tuple[dict, str]:
    # The census invokes nav_coverage.py by ITS OWN path, not root-relative —
    # the fixture tree has no scripts/ of its own. mkdocs is importable in the
    # sandbox venv, so the cfg-nav authority works without a build log. The
    # fixture tree is not a git work tree, so the corpus comes from the rglob
    # fallback — which this suite exercises on purpose.
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--root", str(root)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, f"census exited {proc.returncode}: {proc.stderr}"
    assert proc.stderr.strip(), "census printed no stderr summary"
    return json.loads(proc.stdout), proc.stderr


@pytest.fixture(scope="module")
def census(tmp_path_factory: pytest.TempPathFactory) -> tuple[dict, str]:
    root = tmp_path_factory.mktemp("unlinked")
    build_tree(root)
    return run_census(root)


def page(result: dict, path: str) -> dict:
    hits = [p for p in result["pages"] if p["path"] == path]
    assert hits, f"{path} not in candidates: {[p['path'] for p in result['pages']]}"
    return hits[0]


def test_counts_sum_to_candidates(census: tuple[dict, str]) -> None:
    result, _ = census
    assert sum(result["counts"].values()) == result["candidates"]


def test_exact_counts_pinned(census: tuple[dict, str]) -> None:
    result, _ = census
    assert result["candidates"] == EXPECTED_CANDIDATES
    assert result["counts"] == EXPECTED_COUNTS


def test_stderr_summary_line_exact(census: tuple[dict, str]) -> None:
    _, stderr = census
    assert stderr == EXPECTED_STDERR


def test_dir_prefixed_link_is_a_link(census: tuple[dict, str]) -> None:
    # THE regression: a directory separator before the stem must not hide the link.
    result, _ = census
    got = page(result, "api/analytics-endpoints.md")
    assert got["cls"] == "linked"
    assert got["refs"] == ["docs/hub.md"]


def test_record_tree_link_rescues(census: tuple[dict, str]) -> None:
    result, _ = census
    got = page(result, "deep/guide.md")
    assert got["cls"] == "linked"
    assert got["refs"] == ["docs/plans/2026-01-01-old.md"]


def test_snippet_include_resolves_from_repo_root(census: tuple[dict, str]) -> None:
    result, _ = census
    got = page(result, "snipped.md")
    assert got["cls"] == "linked"
    assert got["refs"] == ["docs/agent.md"]


def test_directory_form_link_resolves_to_index(census: tuple[dict, str]) -> None:
    # ../arch/ must land on arch/index.md — the page mkdocs serves for the dir.
    result, _ = census
    got = page(result, "arch/index.md")
    assert got["cls"] == "linked"
    assert got["refs"] == ["docs/guides/dirlink.md"]


def test_explicit_readme_link_stays_on_readme(census: tuple[dict, str]) -> None:
    # When both node files exist, ../arch/README.md is a link to README.md, NOT
    # to index.md — the two links above must not have collapsed into one page.
    result, _ = census
    got = page(result, "arch/README.md")
    assert got["cls"] == "linked"
    assert got["refs"] == ["docs/guides/direct.md"]


def test_code_citation_is_cited_not_nowhere(census: tuple[dict, str]) -> None:
    result, _ = census
    got = page(result, "operator/smtp.md")
    assert got["cls"] == "cited"
    assert got["refs"] == ["scripts/audit/env_dead_vars.py"]


def test_compound_identifier_does_not_cite(census: tuple[dict, str]) -> None:
    # SMTP_CONFIGURATION_URL shares smtp's prefix — the lookbehind class. The
    # env_dead_vars.py literal must survive the boundary rule with it.
    result, _ = census
    got = page(result, "operator/smtp.md")
    assert "scripts/audit/other.py" not in got["refs"]


def test_record_tree_prose_mention_is_cited(census: tuple[dict, str]) -> None:
    result, _ = census
    got = page(result, "research/old-scan.md")
    assert got["cls"] == "cited"
    assert got["refs"] == ["docs/uplevel/00-audit.md"]


def test_self_exclusion_is_exact_same_name_other_dir(
    census: tuple[dict, str],
) -> None:
    # The pair cites each other by stem only. An endswith(cand) exclusion would
    # swallow BOTH referrers (each referrer's path ends in the candidate's name)
    # and flip each candidate to nowhere — pin both directions.
    result, _ = census
    assert page(result, "notes.md") == {
        "path": "notes.md",
        "cls": "cited",
        "refs": ["docs/research/notes.md"],
    }
    assert page(result, "research/notes.md") == {
        "path": "research/notes.md",
        "cls": "cited",
        "refs": ["docs/notes.md"],
    }


def test_readme_dir_needle_is_the_directory(census: tuple[dict, str]) -> None:
    # research/README.md is unlinked; its honest needle is "research", and it is
    # cited by the record prose AND by research/notes.md's own title — pinned
    # exactly so a needle of "README" (237-file noise on the live tree) or a
    # dropped needle path both die here.
    result, _ = census
    assert page(result, "research/README.md") == {
        "path": "research/README.md",
        "cls": "cited",
        "refs": ["docs/research/notes.md", "docs/uplevel/00-audit.md"],
    }


def test_root_readme_dot_parent_falls_back_to_stem(census: tuple[dict, str]) -> None:
    # The root README's parent is "." — without the fallback the needle would be
    # "." and cite every file containing a period. With it, the needle is
    # "README", and the case-insensitive bounded sweep honestly reports the
    # sibling READMEs' own titles ("# arch readme") plus the explicit link —
    # noise, but in the SAFE direction: a false "cited" costs a review line, a
    # false "nowhere" costs a deletion. Pinned exactly so the noise stays visible
    # instead of being laundered into a smaller list.
    result, _ = census
    assert page(result, "README.md") == {
        "path": "README.md",
        "cls": "cited",
        "refs": [
            "docs/arch/README.md",
            "docs/guides/direct.md",
            "docs/research/README.md",
        ],
    }


def test_unmentioned_page_is_nowhere(tmp_path: Path) -> None:
    build_tree(tmp_path)
    # Strip the one prose mention; the page must go NOWHERE with empty refs.
    (tmp_path / "docs/uplevel/00-audit.md").write_text("nothing here\n", encoding="utf-8")
    result, _ = run_census(tmp_path)
    got = page(result, "research/old-scan.md")
    assert got["cls"] == "nowhere"
    assert got["refs"] == []


def test_nowhere_pages_have_no_refs(census: tuple[dict, str]) -> None:
    # hub.md carries its own stem in its own text ("# hub page") — the
    # self-exclusion keeps that from rescuing it. Same for the other three.
    result, _ = census
    for path in ("hub.md", "agent.md", "guides/direct.md", "guides/dirlink.md"):
        got = page(result, path)
        assert got["cls"] == "nowhere", got
        assert got["refs"] == [], got


def test_candidates_are_living_nav_missing_only(census: tuple[dict, str]) -> None:
    result, _ = census
    paths = {p["path"] for p in result["pages"]}
    # index.md is nav'd -> never a candidate.
    assert "index.md" not in paths
    # plans/ is a record tree -> nav_coverage flags it record, not living debt.
    assert "plans/2026-01-01-old.md" not in paths
    # A disabled stub is out of the nav by design -> never a candidate.
    assert "development/moved.md" not in paths
    # hub.md is living, nav-missing, and not itself linked TO -> in candidates.
    assert "hub.md" in paths
