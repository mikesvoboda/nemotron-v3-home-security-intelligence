#!/usr/bin/env python3
r"""Tests for scripts/audit/nav_coverage.py (W3.3).

Run explicitly (scripts/ is outside pytest testpaths):

    uv run python -m pytest scripts/audit/test_nav_coverage.py -q

The fixture tree pins the decisions this census exists to get right. Each one
is a drift this census's PREDECESSOR instruments actually made against the
live mkdocs.yml at 90f820e3d, so none is hypothetical:

  * a nav entry is `title: target` and only the TARGET covers a page. The live
    yaml has `- AGENTS.md Standard: developer/agents-md-standard.md`; a naive
    `[^\s'#]+\.md` extractor captured "AGENTS.md" out of the TITLE and believed
    docs/AGENTS.md was nav'd when mkdocs says it is missing (mkdocs covered
    132 files; that extractor could only ever name 130 leaves).
  * a target may be a DIRECTORY with or without a trailing slash and covers the
    README.md (or index.md) inside it. `mkdocs.yml` has such entries today:
    README.md, reference/troubleshooting/README.md and templates/AGENTS.md are
    covered without any .md leaf naming them. audit_mkdocs.py's nav regex
    (":\\s*([^\\s#]+\\.md)\\s*$") cannot see these entries at all.
  * README.md and index.md are the same node (mkdocs canonicalizes a
    directory's README.md to index.md), so a nav entry naming either covers
    the other when only one exists on disk.
  * external links in the nav (`- Docs site: https://…`) cover nothing and
    must not be read as dangling local refs.
  * pages with `disabled: true` are out of the nav BY DECISION. All 30
    redirect stubs at main carry exactly that frontmatter, and their nav
    absence is the point of the stub; counting them as nav debt (or deleting
    them as "unlinked pages in no nav") inverts the intent. They are reported,
    flagged separately, and never in the debt count.
  * the dated record trees are exempt from the LIVING-docs definition
    (docs/plans/, docs/superpowers/, docs/vss-integration/, docs/uplevel/ —
    the same set scripts/audit/retired_names.py ships, and this test pins the
    two copies against each other; the fixture expectations themselves are
    literals, not derived from either constant).
  * a nav target that names neither an existing file nor an existing directory
    is dangling and must surface (the directory-form case is invisible to
    audit_mkdocs.py's .md-only regex).
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).parent
SCRIPT = HERE / "nav_coverage.py"

MKDOCS_YML = """\
site_name: Fixture
theme:
  name: material
nav:
  - Home: index.md
  - Guide: guides/
  - Ops: operator/deployment
  - AGENTS.md Standard: developer/agents-md-standard.md
  - Twin: twin/index.md
  - Docs site: https://mikesvoboda.github.io/nemotron-v3-home-security-intelligence/
  - Section:
      - Deep: deep/page.md
  - Dangling file: nowhere/missing.md
  - Dangling dir: ghost/
"""

# name -> (nav target used above). Keep in sync with MKDOCS_YML.
DOCS_FILES = {
    "index.md": "# home\n",
    "guides/README.md": "# guide\n",
    "operator/deployment/index.md": "# deploy\n",
    "developer/agents-md-standard.md": "# std\n",
    "deep/page.md": "# deep\n",
    # named by the nav as twin/index.md but only the README exists: same node
    "twin/README.md": "# twin\n",
    # in NO nav: the title-collision page mkdocs itself reports as missing
    "AGENTS.md": "# agents\n",
    # out of the nav on purpose
    "off/disabled.md": "---\ndisabled: true\n---\n\n# moved\n",
    # a dated record: living-docs exempt, still nav-missing
    "plans/2026-01-01-old.md": "# record\n",
    # ordinary nav debt
    "extra/loose.md": "# loose\n",
}

# Literal expectations — NOT computed from the module under test.
COVERED = {
    "index.md",
    "guides/README.md",
    "operator/deployment/index.md",
    "developer/agents-md-standard.md",
    "deep/page.md",
    "twin/README.md",
}
MISSING = {"AGENTS.md", "off/disabled.md", "plans/2026-01-01-old.md", "extra/loose.md"}
DISABLED = {"off/disabled.md"}
RECORD = {"plans/2026-01-01-old.md"}
LIVING_MISSING = {"AGENTS.md", "extra/loose.md"}
DANGLING = {"nowhere/missing.md", "ghost/"}


def build_tree(root: Path) -> None:
    (root / "mkdocs.yml").write_text(MKDOCS_YML, encoding="utf-8")
    docs = root / "docs"
    for rel, body in DOCS_FILES.items():
        p = docs / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(body, encoding="utf-8")


def run_census(root: Path) -> dict:
    proc = subprocess.run(  # check=False: the tests assert on returncode
        [sys.executable, str(SCRIPT), "--root", str(root)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, f"census exited {proc.returncode}: {proc.stderr}"
    # A summary line on stderr is a sibling-script convention; its presence is
    # asserted so a silent instrument cannot pass on stdout alone.
    assert proc.stderr.strip(), "census printed no stderr summary"
    return json.loads(proc.stdout)


@pytest.fixture()
def census(tmp_path: Path) -> dict:
    build_tree(tmp_path)
    return run_census(tmp_path)


def keys(result: dict, field: str) -> set[str]:
    """Paths in a census field, whether it ships as [str] or [{path: str}]."""
    out = set()
    for entry in result[field]:
        out.add(entry["path"] if isinstance(entry, dict) else entry)
    return out


def test_covered_set_is_exact(census: dict) -> None:
    assert keys(census, "covered") == COVERED


def test_missing_set_is_exact(census: dict) -> None:
    assert keys(census, "missing") == MISSING


def test_covered_and_missing_partition_the_corpus(census: dict) -> None:
    covered, missing = keys(census, "covered"), keys(census, "missing")
    assert not (covered & missing), "a page cannot be both nav'd and nav-missing"
    assert covered | missing == set(DOCS_FILES), "the corpus must not silently drop pages"


def test_title_never_becomes_a_nav_target(census: dict) -> None:
    # The whole reason this file exists: `- AGENTS.md Standard: x.md` must not
    # make docs/AGENTS.md look nav'd.
    assert "AGENTS.md" in keys(census, "missing")


def test_directory_targets_cover_their_readme(census: dict) -> None:
    assert "guides/README.md" in keys(census, "covered")  # trailing slash
    assert "operator/deployment/index.md" in keys(census, "covered")  # bare dir, index.md


def test_readme_and_index_are_one_node(census: dict) -> None:
    assert "twin/README.md" in keys(census, "covered")


EXTERNAL_URL = "https://mikesvoboda.github.io/nemotron-v3-home-security-intelligence/"


def test_external_nav_links_cover_nothing(census: dict) -> None:
    # The needle must be the fixture's ACTUAL literal: an earlier version of
    # this test searched for "example.com", which the fixture never contains, so
    # it asserted nothing and passed. Present-first: the URL is in nav_targets,
    # and only then is its absence from covered/dangling evidence.
    assert EXTERNAL_URL in census["nav_targets"], "fixture's external entry vanished"
    assert not any("mikesvoboda.github.io" in p for p in keys(census, "covered"))
    assert not any("mikesvoboda.github.io" in p for p in keys(census, "dangling_nav_targets"))


def test_disabled_pages_are_missing_but_never_debt(census: dict) -> None:
    flagged = keys(census, "by_flag")
    assert flagged, "an empty flag set would make the exemption vacuously true"
    assert flagged == DISABLED | RECORD
    assert census["living_docs_missing"] == sorted(LIVING_MISSING)
    # and the disabled page is still REPORTED — reporting-only doctrine: the
    # instrument never hides a page, it classifies it.
    assert "off/disabled.md" in keys(census, "missing")


def test_record_trees_are_exempted_by_name(census: dict) -> None:
    assert keys(census, "by_flag") & RECORD == RECORD
    assert "plans/2026-01-01-old.md" not in census["living_docs_missing"]


def test_dangling_nav_targets_surfaced(census: dict) -> None:
    assert keys(census, "dangling_nav_targets") == DANGLING


def test_record_prefixes_match_the_sibling_census(census: dict) -> None:
    """Cross-file consistency, not a self-derived expectation: this census and
    retired_names.py both hard-code the record-tree tuple; drift between them
    means two W-lanes measuring different corpora. The fixture assertions above
    are literals, so this pin cannot make either constant 'free'."""
    sys.path.insert(0, str(HERE))
    import nav_coverage
    import retired_names

    assert nav_coverage.RECORD_DOC_PREFIXES == retired_names.RECORD_DOC_PREFIXES


# --- the build-log path -------------------------------------------------------
# mkdocs is NOT a declared dependency of this project (pyproject.toml carries
# mkdocs-material and the two other plugins; mkdocs arrives transitively), so the
# fallback is load-bearing and is tested here rather than merely present.
#
# The log fixture reproduces mkdocs' real formatting hazard: entries are TWO
# spaces and a dash. A four-space reader collects nothing and every headline
# becomes a confident zero, so both the happy path and the loud-failure guard are
# pinned.
BUILD_LOG_OK = """\
INFO    -  Copying 'css' files
INFO    -  The following pages exist in the docs directory, but are not \
included in the "nav" configuration:
  - AGENTS.md
  - off/disabled.md
  - plans/2026-01-01-old.md
  - extra/loose.md
INFO    -  Doc file 'x.md' contains a link 'y.md', but the target is not found.
INFO    -  Documentation built in 31.58 seconds
"""

BUILD_LOG_NO_BLOCK = """\
INFO    -  Documentation built in 12.00 seconds
"""


def run_with_log(root: Path, log_text: str) -> subprocess.CompletedProcess:
    log = root / "build.log"
    log.write_text(log_text, encoding="utf-8")
    return subprocess.run(  # check=False: caller asserts on returncode
        [sys.executable, str(SCRIPT), "--root", str(root), "--build-log", str(log)],
        capture_output=True,
        text=True,
        check=False,
    )


def test_build_log_mode_reproduces_the_authority(tmp_path: Path) -> None:
    build_tree(tmp_path)
    proc = run_with_log(tmp_path, BUILD_LOG_OK)
    assert proc.returncode == 0, proc.stderr
    result = json.loads(proc.stdout)
    assert result["nav_source"] == "build-log"
    # The log's four entries are the missing set; everything else is covered,
    # including the three files whose coverage needs no .md leaf (guides/,
    # operator/deployment, twin/README.md) -- that is what makes the log the
    # authority: it already accounts for directory entries and for
    # awesome-pages injection, which the YAML nav cannot see.
    assert keys(result, "missing") == MISSING
    assert keys(result, "covered") == COVERED
    assert result["living_docs_missing"] == sorted(LIVING_MISSING)


def test_build_log_without_a_nav_block_fails_loud(tmp_path: Path) -> None:
    """The silent-zero guard: an unparseable log must exit non-zero, never
    report '0 nav-missing pages' as a fact about the corpus."""
    build_tree(tmp_path)
    proc = run_with_log(tmp_path, BUILD_LOG_NO_BLOCK)
    assert proc.returncode != 0, "a log with no nav block must not report a coverage number"
    assert "refusing to report zero" in proc.stderr


def test_missing_build_log_and_no_mkdocs_is_not_silent(tmp_path: Path) -> None:
    """Both authorities unavailable is an error state, not an empty nav."""
    build_tree(tmp_path)
    proc = subprocess.run(  # check=False: the tests assert on returncode
        [sys.executable, str(SCRIPT), "--root", str(tmp_path)],
        capture_output=True,
        text=True,
        check=False,
    )
    # What is pinned: the census never reports a coverage number on silence.
    # If it exited 0 it must have emitted the summary line (mkdocs importable,
    # cfg.nav mode); if it could not import mkdocs it must exit 1 and name the
    # remediation. Which branch a given runner takes depends on whether the
    # transitive mkdocs install is present, so both arms are asserted, not one.
    if proc.returncode == 0:
        assert proc.stderr.strip(), "exit 0 with no stderr summary is a silent instrument"
        # The series label every scripts/audit census prints (see the note in
        # nav_coverage.py: O1.7, not W3.3).
        assert "O1.7 nav-coverage:" in proc.stderr
    else:
        assert "build-log" in proc.stderr
