#!/usr/bin/env python3
"""Revert-campaign driver for ruling 143's golden-container pins (contract rule 3).

    uv run --no-project python scripts/r143-mutation-campaign.py

The body of #7034 claims these pins have teeth. A claim about teeth is only
evidence if the reader can bite, so the campaign the body reports runs from the
repo rather than from a scratch directory: every mutant below is applied to
``scripts/feature_check.py`` INSIDE A THROWAWAY GIT WORKTREE at HEAD, so the
live worktree is never written to, and the driver exits non-zero if any mutant
escapes or any anchor stops matching.

Why a worktree and not a copy of one file: the unit file resolves
``REPO_ROOT = parents[4]`` and reads ``frontend/package-lock.json`` through it,
so a lone file copy gives 78 collection errors and a campaign that measures
nothing. A detached worktree is the cheapest tree where the suite can actually
run; ``git archive`` will not do, because ``.gitattributes`` ships
``backend/tests/ export-ignore``.

Why ``-p no:randomly``: the campaign compares SETS of failed test ids between
runs. ``pytest-randomly`` reorders and reseeded per run, which is exactly the
noise that would let a mutant look caught or look escaped by accident. The
addopts ``-n 8`` is kept -- it is the sharding, not the ordering.

Every anchor below was re-anchored at head 162be08bd; an anchor that no longer
matches is reported as ``ANCHOR`` and fails the run, because a silently-skipped
mutant is how "caught 16/16; escaped: none" once became a false line in this
PR's own body.
"""

from __future__ import annotations

import argparse
import pathlib
import subprocess
import sys
import tempfile

# (what breaking it would mean, the exact text, its replacement)
MUTANTS: list[tuple[str, str, str]] = [
    (
        "--no-install dropped: a bare npx fetches an unlocked runner and exits 0",
        '                    "--no-install",\n',
        "",
    ),
    (
        "frontend mount loses :ro: the leg can write into the source tree",
        'f"{path}:{path}:ro{suffix}"',
        'f"{path}:{path}{suffix}"',
    ),
    (
        "image variant noble -> jammy: the tag leaves the lock's contract",
        'PLAYWRIGHT_IMAGE_VARIANT = "noble"',
        'PLAYWRIGHT_IMAGE_VARIANT = "jammy"',
    ),
    (
        "junit name dropped from the whitelist: the leg reports into nowhere",
        '    "PLAYWRIGHT_JUNIT_OUTPUT_FILE",\n    "CI",\n)',
        '    "CI",\n)',
    ),
    (
        "CI dropped from the whitelist: forbidOnly off, retries 0 (UR-128/129)",
        '    "PLAYWRIGHT_JUNIT_OUTPUT_FILE",\n    "CI",\n)',
        '    "PLAYWRIGHT_JUNIT_OUTPUT_FILE",\n)',
    ),
    (
        "blocked-pull problem line dropped: UR-131's clause stops being printed",
        'f"golden: {self.engine} pull of {image}',
        'f"golden: nope {image}',
    ),
    (
        "operator instruction stops naming a host: the allow list becomes a guess",
        'f"(registry: {PLAYWRIGHT_IMAGE_REGISTRY} — the host to allow; the "',
        'f"(see the failure text; the "',
    ),
    (
        "registry constant -> cdn.playwright.dev: UR-131 names the wrong host",
        'PLAYWRIGHT_IMAGE_REGISTRY = "mcr.microsoft.com"',
        'PLAYWRIGHT_IMAGE_REGISTRY = "cdn.playwright.dev"',
    ),
    (
        "lock key -> playwright: the tag reads a sibling package's version",
        'PLAYWRIGHT_LOCK_KEY = "@playwright/test"',
        'PLAYWRIGHT_LOCK_KEY = "playwright"',
    ),
    (
        "image repo -> public.ecr.aws: the named registry and the pull disagree",
        'PLAYWRIGHT_IMAGE_REPOSITORY = "mcr.microsoft.com/playwright"',
        'PLAYWRIGHT_IMAGE_REPOSITORY = "public.ecr.aws/docker/playwright"',
    ),
    (
        "pull timeout 1800 -> 300: a slow mirror becomes a false block",
        'pull = self._run([self.engine, "pull", image], check=False, timeout=1800)',
        'pull = self._run([self.engine, "pull", image], check=False, timeout=300)',
    ),
    (
        "version read from the top-level lock version: the tag leaves the package",
        "entry = (packages or {}).get(f\"node_modules/{PLAYWRIGHT_LOCK_KEY}\") or {}",
        "entry = lock if isinstance(lock, dict) else {}",
    ),
    (
        "vacuity guard skipped on the no-image path: ruling 114's hole reopens",
        'problems += golden_execution_problems("playwright", {})\n'
        '                self.summary["results"]["golden"] = results\n'
        "                return problems\n"
        "            # The leg, in the image.",
        'self.summary["results"]["golden"] = results\n'
        "                return problems\n"
        "            # The leg, in the image.",
    ),
]


def run_suite(worktree: pathlib.Path, suite: str) -> set[str]:
    """The failed test ids of one suite run inside WORKTREE."""
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            suite,
            "-q",
            "--tb=no",
            "-p",
            "no:randomly",
        ],
        cwd=worktree,
        capture_output=True,
        text=True,
        check=False,
    )
    return {
        line.split("::")[-1] for line in result.stdout.splitlines() if line.startswith("FAILED")
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--suite",
        default="backend/tests/unit/scripts/test_feature_check.py",
        help="test file to mutate against, relative to the worktree root",
    )
    args = parser.parse_args()

    root = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True, check=True
    ).stdout.strip()
    script = pathlib.Path(root) / "scripts" / "feature_check.py"
    pristine = script.read_text(encoding="utf-8")

    failures = 0
    with tempfile.TemporaryDirectory(prefix="r143-campaign-") as tmp:
        worktree = pathlib.Path(tmp) / "wt"
        subprocess.run(
            ["git", "worktree", "add", "--detach", str(worktree), "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        )
        target = worktree / "scripts" / "feature_check.py"
        try:
            target.write_text(pristine, encoding="utf-8")
            baseline = run_suite(worktree, args.suite)
            print(f"baseline reds: {len(baseline)}")
            for description, old, new in MUTANTS:
                count = pristine.count(old)
                if count != 1:
                    print(f"  ANCHOR x{count} | {description}")
                    failures += 1
                    continue
                target.write_text(pristine.replace(old, new), encoding="utf-8")
                try:
                    compile(target.read_text(encoding="utf-8"), "mutant.py", "exec")
                except SyntaxError as error:
                    print(f"  SYNTAX   | {description}: {error}")
                    failures += 1
                    target.write_text(pristine, encoding="utf-8")
                    continue
                new_reds = sorted(run_suite(worktree, args.suite) - baseline)
                if new_reds:
                    print(f"CAUGHT({len(new_reds)}) | {description}")
                    for name in new_reds:
                        print(f"           {name}")
                else:
                    print(f"ESCAPED     | {description}")
                    failures += 1
                target.write_text(pristine, encoding="utf-8")
            restored = run_suite(worktree, args.suite)
            print(
                f"restored reds: {len(restored)} (baseline {len(baseline)}) "
                f"same={restored == baseline}"
            )
            if restored != baseline:
                failures += 1
        finally:
            subprocess.run(
                ["git", "worktree", "remove", "--force", str(worktree)],
                capture_output=True,
                text=True,
                check=False,
            )

    print(f"\n{len(MUTANTS)} mutants, {failures} problem(s)")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
