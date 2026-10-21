#!/usr/bin/env python3
"""Tests for O3.7 (`scripts/` truth).

Run explicitly; outside testpaths (wired into `.github/workflows/ci.yml`'s
`collection-sanity` step `Run the anti-rot gates' own tests`):

    uv run python -m pytest scripts/test_scripts_truth.py -q

Pins O3.7's Done-when and boxes:
  1. Every tracked file in `scripts/` is referenced by CI, a hook, `setup.py`,
     another script, or the operator/living docs; no unreferenced or one-off
     investigation script remains, and a synthetic tree with an unreferenced
     script fails the scanner (teeth control).
  2. `.pre-commit-config.yaml` extends `ruff`, `ruff-format`, and `mypy`
     `files:` scope to `scripts/`, and `scripts/` passes `ruff check`,
     `ruff format --check`, and `mypy` (with ruling 298 item 2's open-PR
     deferrals named explicitly).
  3. `scripts/test_gen_ai_contract.py`, `scripts/test_synthetic_media.py`, and
     this suite are wired into CI, while `scripts/test_vlm_probes.py`,
     `scripts/benchmark/`, and `tests/benchmark/` are gone.
"""

from __future__ import annotations

import re
import shlex
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent

# Ruling 298 item 2: files under scripts/ edited by open PRs at claim time
# (#7327 [r278], #7328 [r291], #7322 [B3.3 box 4]) are left byte-untouched by
# O3.7 so they do not conflict; the two lane_tick files that need formatting
# are deferred in ruff-format's exclude until #7327 merges.
R298_DEFERRED_FORMAT_FILES = {
    "scripts/test_lane_tick.py",
    "scripts/uplevel/lane_tick.py",
}

DELETED_PATHS = (
    # Box 1: unreferenced scripts (~14 at d6ba78d5, 00 §7) and one-off investigation scripts
    "scripts/ai-entrypoint.sh",
    "scripts/analyze_coverage_gaps.py",
    "scripts/collect-calibration-frames.py",
    "scripts/curate_external_samples.py",
    "scripts/fix_flaky_tests.py",
    "scripts/generate_security_dataflows_images.sh",
    "scripts/migrate_cosmos_videos.py",
    "scripts/regenerate_subpar_images.sh",
    "scripts/run-setup-deploy.sh",
    "scripts/timeout-guard.py",
    "scripts/validate-metrics-coverage.py",
    "scripts/validate_external_datasets.py",
    "scripts/vlm_probes/s1_nvext.py",
    "scripts/vlm_probes/s3_salience_stock.py",
    "scripts/r143-launch-probe.cjs",
    "scripts/r143-mutation-campaign.py",
    "scripts/r269-mutation-campaign.py",
    "scripts/uplevel/r195-host-loopback-probe.sh",
    "scripts/uplevel-f1-webhook-sanitize/battery.py",
    "scripts/uplevel-r94-mutation/README.md",
    "scripts/uplevel-r94-mutation/battery.py",
    "scripts/uplevel-r94-mutation/sourcing_shapes.py",
    # Box 1 DECIDE: scripts referenced only by scripts/AGENTS.md (or README.md) deleted
    "scripts/a11y-smoke-test.sh",
    "scripts/analyze-ci-dependencies.py",
    "scripts/check-api-contracts.sh",
    "scripts/check-branch-name.sh",
    "scripts/download_yolo26.py",
    "scripts/find-slow-tests.sh",
    "scripts/git-bisect-helper.sh",
    "scripts/linear-label-issues.sh",
    "scripts/setup.ps1",
    "scripts/smoke-test.sh",
    "scripts/test-fast.sh",
    "scripts/test-in-container.sh",
    "scripts/test-prod-connectivity.sh",
    "scripts/trigger-filewatcher.sh",
    # Box 3: unrun script tests and benchmark harness deleted
    "scripts/test_vlm_probes.py",
    "scripts/benchmark",
    "tests/benchmark",
)

BINARY_SUFFIXES = {
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".webp",
    ".ico",
    ".woff",
    ".woff2",
    ".ttf",
    ".pdf",
    ".db",
    ".onnx",
    ".pt",
}

HISTORY_PREFIXES = (
    "docs/plans/",
    "docs/superpowers/",
    "docs/vss-integration/",
    "backend/tests/unit/scripts/data/uplevel-cites/",
)

NON_REFERRER_FILES = {
    ".gitignore",
    ".prettierignore",
    "frontend/.prettierignore",
    ".secrets.baseline",
    ".test_durations",
    ".github/mutation-history.json",
    "docs/openapi.json",
    "frontend/package-lock.json",
    "frontend/src/types/generated/api.ts",
    "uv.lock",
    "scripts/retired_paths.txt",
    "scripts/test_scripts_truth.py",
}


def _tracked_files(root: Path) -> list[str]:
    if (root / ".git").exists():
        out = subprocess.check_output(["git", "-C", str(root), "ls-files"], text=True).splitlines()
        return [f for f in out if (root / f).exists()]
    return sorted(p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file())


def _is_valid_referrer(rel: str) -> bool:
    """Is `rel` an eligible referrer (CI, hook, setup.py, another script/test, or living docs)?"""
    if rel in NON_REFERRER_FILES:
        return False
    return not any(rel.startswith(prefix) for prefix in HISTORY_PREFIXES)


def find_unreferenced_scripts(root: Path) -> list[str]:
    """Return any file under `scripts/` not referenced by CI, a hook, `setup.py`,
    another script, or the operator/living docs."""
    tracked = _tracked_files(root)
    scripts_files = [f for f in tracked if f.startswith("scripts/")]

    contents: dict[str, str] = {}
    for rel in tracked:
        if not _is_valid_referrer(rel):
            continue
        p = root / rel
        if p.suffix in BINARY_SUFFIXES:
            continue
        try:
            contents[rel] = p.read_text(encoding="utf-8")
        except OSError:
            continue

    corpus_items = list(contents.items())
    unreferenced: list[str] = []

    for sf in sorted(scripts_files):
        p = Path(sf)
        name = p.name
        stem = p.stem
        sub_rel = sf[len("scripts/") :]
        is_top = "/" not in sub_rel

        # AGENTS.md and README.md inside scripts/ are documentation indexes themselves;
        # scenarios/*.json are loaded via directory walk by
        # scripts/synthetic/scenarios/__init__.py (`_discover_scenarios()`).
        if name in {"AGENTS.md", "README.md"}:
            continue
        if (
            sf.startswith("scripts/synthetic/scenarios/")
            and sf.endswith(".json")
            and (
                "_discover_scenarios" in contents.get("scripts/synthetic/scenarios/__init__.py", "")
            )
        ):
            continue

        mod_dot = sf[:-3].replace("/", ".") if sf.endswith(".py") else None
        pkg_dot = (
            str(p.parent).replace("/", ".") if name in {"__init__.py", "__main__.py"} else None
        )
        sub_mod_dot = sub_rel[:-3].replace("/", ".") if sf.endswith(".py") and not is_top else None

        referenced = False
        for rf, text in corpus_items:
            if rf == sf:
                continue
            if name not in text and stem not in text and (not pkg_dot or pkg_dot not in text):
                continue
            if sf in text or (not is_top and sub_rel in text):
                referenced = True
                break
            if is_top and re.search(r"(?<![\w.-])" + re.escape(name) + r"(?![\w.-])", text):
                referenced = True
                break
            if (
                is_top
                and sf.endswith(".py")
                and re.search(r"\bscripts\." + re.escape(stem) + r"\b", text)
            ):
                referenced = True
                break
            if (
                is_top
                and sf.endswith(".py")
                and rf.startswith(("scripts/", "backend/tests/unit/scripts/"))
                and re.search(r"\b(?:import|from)\s+" + re.escape(stem) + r"\b", text)
            ):
                referenced = True
                break
            if mod_dot and re.search(r"\b" + re.escape(mod_dot) + r"\b", text):
                referenced = True
                break
            if pkg_dot and re.search(r"\b" + re.escape(pkg_dot) + r"\b", text):
                referenced = True
                break
            if (
                sub_mod_dot
                and rf.startswith(("scripts/", "backend/tests/", "tests/"))
                and re.search(r"\b" + re.escape(sub_mod_dot) + r"\b", text)
            ):
                referenced = True
                break
            if p.parent == Path(rf).parent and re.search(
                r"(?<![\w.-])" + re.escape(name) + r"(?![\w.-])", text
            ):
                referenced = True
                break
            if (
                p.parent == Path(rf).parent
                and sf.endswith(".py")
                and re.search(r"(?<![\w.-])" + re.escape(stem) + r"(?![\w.-])", text)
            ):
                referenced = True
                break

        if not referenced:
            unreferenced.append(sf)

    return unreferenced


def test_scanner_catches_unreferenced_script_on_synthetic_tree(tmp_path: Path) -> None:
    """Teeth control: an unreferenced script in `scripts/` is reported, and a
    referenced script is not."""
    (tmp_path / "scripts").mkdir()
    (tmp_path / ".github" / "workflows").mkdir(parents=True)
    (tmp_path / "scripts" / "used.py").write_text("print('used')\n", encoding="utf-8")
    (tmp_path / "scripts" / "orphan.py").write_text("print('orphan')\n", encoding="utf-8")
    (tmp_path / ".github" / "workflows" / "ci.yml").write_text(
        "steps:\n  - run: python scripts/used.py\n", encoding="utf-8"
    )
    assert find_unreferenced_scripts(tmp_path) == ["scripts/orphan.py"]


def test_deleted_scripts_and_benchmarks_stay_gone() -> None:
    present = [rel for rel in DELETED_PATHS if (REPO_ROOT / rel).exists()]
    assert present == [], f"deleted O3.7 paths exist on disk: {present}"


@pytest.mark.timeout(60)
def test_every_file_in_scripts_is_referenced() -> None:
    unreferenced = find_unreferenced_scripts(REPO_ROOT)
    assert unreferenced == [], f"unreferenced files in scripts/: {unreferenced}"


def test_precommit_config_extends_ruff_and_mypy_to_scripts() -> None:
    cfg = yaml.safe_load((REPO_ROOT / ".pre-commit-config.yaml").read_text(encoding="utf-8"))
    hooks: dict[str, dict[str, object]] = {}
    for repo in cfg["repos"]:
        for hook in repo.get("hooks", []):
            hid = hook.get("id")
            if hid in {"ruff", "ruff-format", "mypy"}:
                hooks[str(hid)] = hook

    assert set(hooks) == {"ruff", "ruff-format", "mypy"}
    for hid, hook in hooks.items():
        files_pat = str(hook.get("files", ""))
        assert re.search(r"scripts/something\.py", "scripts/something.py") and re.search(
            files_pat, "scripts/something.py"
        ), f"pre-commit hook {hid!r} files pattern {files_pat!r} does not match scripts/"


def test_ci_wires_script_test_suites() -> None:
    ci = yaml.safe_load(
        (REPO_ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    )
    steps = ci["jobs"]["collection-sanity"]["steps"]
    antirot = next(s["run"] for s in steps if s.get("name") == "Run the anti-rot gates' own tests")
    tokens = set(shlex.split(antirot))
    for suite in (
        "scripts/test_gen_ai_contract.py",
        "scripts/test_synthetic_media.py",
        "scripts/test_scripts_truth.py",
    ):
        assert suite in tokens, f"{suite} is not wired into collection-sanity's anti-rot step"


@pytest.mark.timeout(60)
def test_scripts_passes_ruff_and_mypy() -> None:
    ruff_check = subprocess.run(
        [sys.executable, "-m", "ruff", "check", "scripts/"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert ruff_check.returncode == 0, ruff_check.stdout + ruff_check.stderr

    tracked_py = [
        f
        for f in _tracked_files(REPO_ROOT)
        if f.startswith("scripts/") and f.endswith(".py") and f not in R298_DEFERRED_FORMAT_FILES
    ]
    ruff_fmt = subprocess.run(
        [sys.executable, "-m", "ruff", "format", "--check", *tracked_py],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert ruff_fmt.returncode == 0, ruff_fmt.stdout + ruff_fmt.stderr

    mypy_res = subprocess.run(
        [
            sys.executable,
            "-m",
            "mypy",
            "--ignore-missing-imports",
            "--explicit-package-bases",
            "scripts/",
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert mypy_res.returncode == 0, mypy_res.stdout + mypy_res.stderr
