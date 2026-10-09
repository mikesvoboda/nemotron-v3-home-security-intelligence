#!/usr/bin/env python3
"""Tests for scripts/audit/retired_names.py (O1.7).

Run explicitly (scripts/ is outside pytest testpaths):

    uv run python -m pytest scripts/audit/test_retired_names.py -q

The fixture tree pins the four decisions this census exists to get right:
  * whole-word matching, the validator's rule: a standalone or hyphenated
    mention ("Florence2" is \\w-joined and does NOT count; "florence-light"
    DOES, hyphen is a \\b edge) — measured on the first real run, a substring
    rule matched ``compose`` for ``pose`` across every docker-compose file
    and inflated the census to 2,350 files; the validator rejected that
    implementation in its own docstring and this census adopts its rule;
  * AGENTS.md files count in their own bucket even when they live OUTSIDE
    docs/ and even at the repo root (the audit's "29 AGENTS.md files" figure);
  * living docs vs dated records: docs/uplevel/ (the program's own record
    tree) and docs/plans/ are exempt — same exemption set as the
    retired-paths gate — while an ordinary docs/*.md page counts;
  * a hit in code (a .py under a non-docs dir) counts even when the same
    name also rides a record doc.
Also pins the names list against the §O1.7 plan text (the governing list;
NOT the validator's different five — see test).
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "audit" / "retired_names.py"

NAMES = ["florence", "nemotron", "enrichment", "pose", "demographic"]


def scan(tree: Path) -> dict:
    """Run the script as its CLI runs it: JSON on stdout is the result."""
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--root", str(tree)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, f"script failed: {proc.stderr[-500:]}"
    return json.loads(proc.stdout)


def build_tree(root: Path) -> None:
    (root / "docs").mkdir(parents=True)
    # whole-word contract: "Florence" is a hit; the florence2 / GPU_FLORENCE
    # spellings are \w-joined and must NOT be (see module docstring)
    (root / "docs" / "architecture.md").write_text(
        "Florence handles OCR; the florence2 build is retired.\n", encoding="utf-8"
    )
    (root / "docs" / "plans").mkdir()
    (root / "docs" / "plans" / "2026-09-01-old.md").write_text(
        "nemotron rollout plan, dated record.\n", encoding="utf-8"
    )
    (root / "docs" / "uplevel").mkdir()
    (root / "docs" / "uplevel" / "30-ops.md").write_text("retire the pose overlay\n", encoding="utf-8")
    (root / "docs" / "goal-prompt-alpha.txt").write_text("pose and demographic\n", encoding="utf-8")
    (root / "docs" / "image.png").write_bytes(b"\x89PNG")
    (root / "backend").mkdir()
    (root / "backend" / "services").mkdir()
    # the hyphen IS a word boundary: "florence-light" is a naming mention;
    # the GPU_FLORENCE identifier is \w-joined and must not be (the validator
    # draws the same line: ENRICHMENT_LIGHT_URL is not an enrichment mention)
    (root / "backend" / "services" / "gpu.py").write_text(
        "GPU_FLORENCE = 'http://florence-light:8000'  # the florence-light host\n", encoding="utf-8"
    )
    (root / "AGENTS.md").write_text("The enrichment service is retired.\n", encoding="utf-8")
    (root / "backend" / "AGENTS.md").write_text("nothing retired here\n", encoding="utf-8")
    (root / "backend" / "tests").mkdir()
    (root / "backend" / "tests" / "test_pose.py").write_text("def test_pose():\n    assert demographic\n", encoding="utf-8")


def run_script(tree: Path) -> tuple[int, str, str]:
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--root", str(tree)],
        capture_output=True,
        text=True,
        check=False,
    )
    return proc.returncode, proc.stdout, proc.stderr


def test_fixture_tree_buckets(tmp_path: Path):
    build_tree(tmp_path)
    result = scan(tmp_path)
    # living docs: only docs/architecture.md (Florence2 is a substring hit)
    assert result["buckets"]["docs"] == 1
    # agents: root AGENTS.md (enrichment hit); backend/AGENTS.md has no name
    assert result["buckets"]["agents"] == 1
    # code: gpu.py (florence), test_pose.py (pose+demographic)
    assert result["buckets"]["code"] == 2
    # records exempt: docs/plans, docs/uplevel, goal-prompt txt; png skipped
    hit_paths = {f["path"] for f in result["files"]}
    assert "docs/architecture.md" in hit_paths
    assert not any("plans/" in p or "uplevel/" in p or "goal-prompt" in p or ".png" in p for p in hit_paths)


def test_whole_word_matching(tmp_path: Path):
    build_tree(tmp_path)
    result = scan(tmp_path)
    # florence: docs/architecture.md ("Florence" standalone; its florence2
    # mention does not count) + gpu.py (the //florence-light host; the
    # GPU_FLORENCE identifier does not count)
    assert result["hits_per_name"]["florence"] == 2
    # pose: NO hit — the only non-exempt appearance is the identifier
    # test_pose, whose _-joined spelling the validator's boundary excludes.
    # This is the false-positive class the whole-word rule exists to stop.
    assert result["hits_per_name"]["pose"] == 0
    # demographic: the standalone assert in test_pose.py
    assert result["hits_per_name"]["demographic"] == 1
    assert result["hits_per_name"]["nemotron"] == 0  # only the exempt record names it


def test_summary_line_and_exit(tmp_path: Path):
    build_tree(tmp_path)
    rc, out, err = run_script(tmp_path)
    assert rc == 0
    payload = json.loads(out)
    assert payload["files_with_hits"] == 4
    assert "O1.7 retired-names: 4 files with hits" in err


def test_names_match_plan_text():
    """The five names are §O1.7's list, in backticks — the governing source.

    Measured 2026-10-09 while writing this pin: the validator's retired-name
    baseline (scripts/agents_md_validator.py RETIRED_NAMES, fed by
    .agents-md-validator.yml) is a DIFFERENT five — florence, nemotron,
    enrichment, xclip, demographics. The package's count feeds B3.3/W1.1/
    W3.3 and its list is the plan's: florence, nemotron, enrichment, pose,
    demographic. The divergence is deliberate in each owner (a ceiling gate
    and an audit census need not agree); this pin guards drift against the
    text this package's Done-when cites, nothing more.
    """
    plan = (REPO_ROOT / "docs" / "uplevel" / "30-ops.md").read_text(encoding="utf-8")
    section = plan.split("### O1.7", 1)[1].split("### O1.8", 1)[0]
    for name in NAMES:
        assert f"`{name}`" in section, f"O1.7 plan text no longer names {name}"
