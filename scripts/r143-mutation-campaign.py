#!/usr/bin/env python3
"""Revert-campaign driver for ruling 143's golden-container pins (contract rule 3).

    python3 scripts/r143-mutation-campaign.py

Run from the repo root. It picks the repo's ``.venv/bin/python`` when that can
import pytest, because the suite needs the project's dependencies and the
interpreter you launched this with usually is not that one; ``--python`` names
one explicitly.

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
import re
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
        'entry = (packages or {}).get(f"node_modules/{PLAYWRIGHT_LOCK_KEY}") or {}',
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


def run_suite(worktree: pathlib.Path, suite: str, python: str) -> tuple[set[str], int, str]:
    """FAILED test ids, executed count, and the summary line for one run in WORKTREE.

    The count is returned, not discarded, because the campaign's whole signal is
    an ABSENCE ("this mutant reddened nothing") and an absence is exactly what a
    broken instrument produces: run this file with an interpreter that cannot
    import pytest and every suite run collects zero tests, so every mutant
    reports ESCAPED and the driver accused these pins of having no teeth. A
    count of zero, or a count that moves between runs, is now refused as
    INSTRUMENT rather than read as a measurement.
    """
    result = subprocess.run(
        [
            python,
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
    failed = {
        line.split("::")[-1] for line in result.stdout.splitlines() if line.startswith("FAILED")
    }
    summary = next(
        (
            line
            for line in reversed(result.stdout.splitlines())
            if re.search(r"\d+ (passed|failed|error)", line) or "no tests ran" in line
        ),
        "",
    )
    executed = sum(int(n) for n, _ in re.findall(r"(\d+) (?:passed|failed|errors?)", summary))
    if not summary:  # pytest never got to reporting: surface its output, not silence
        summary = (result.stderr or result.stdout).strip().splitlines()[-1:] or ["<no output>"]
        summary = summary[0]
    return failed, executed, summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--suite",
        default="backend/tests/unit/scripts/test_feature_check.py",
        help="test file to mutate against, relative to the worktree root",
    )
    parser.add_argument(
        "--python",
        help="interpreter to run the suite with; defaults to the first candidate that can import pytest",
    )
    args = parser.parse_args()

    root = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True, check=True
    ).stdout.strip()
    script = pathlib.Path(root) / "scripts" / "feature_check.py"
    pristine = script.read_text(encoding="utf-8")

    candidates = [args.python] if args.python else [f"{root}/.venv/bin/python", sys.executable]
    python = next(
        (
            c
            for c in candidates
            if c
            and subprocess.run(
                [c, "-c", "import pytest"], capture_output=True, check=False
            ).returncode
            == 0
        ),
        None,
    )
    if python is None:
        print(f"INSTRUMENT | no interpreter can import pytest: tried {candidates}", file=sys.stderr)
        return 2

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
            baseline, baseline_count, baseline_summary = run_suite(worktree, args.suite, python)
            if baseline_count == 0:
                print(
                    f"INSTRUMENT | baseline executed 0 tests: {baseline_summary}", file=sys.stderr
                )
                return 2
            print(f"python: {python}\nbaseline: {baseline_count} executed, {len(baseline)} red")
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
                reds, executed, summary = run_suite(worktree, args.suite, python)
                if executed != baseline_count:
                    print(
                        f"INSTRUMENT | mutant ran {executed} tests, baseline ran "
                        f"{baseline_count}: {summary}",
                        file=sys.stderr,
                    )
                    failures += 1
                    target.write_text(pristine, encoding="utf-8")
                    continue
                new_reds = sorted(reds - baseline)
                if new_reds:
                    print(f"CAUGHT({len(new_reds)}) | {description}")
                    for name in new_reds:
                        print(f"           {name}")
                else:
                    print(f"ESCAPED     | {description}")
                    failures += 1
                target.write_text(pristine, encoding="utf-8")
            restored, restored_count, _ = run_suite(worktree, args.suite, python)
            print(
                f"restored: {restored_count} executed, {len(restored)} red "
                f"(baseline {baseline_count}/{len(baseline)}) same={restored == baseline}"
            )
            if restored_count != baseline_count:
                print("INSTRUMENT | restored run executed a different count", file=sys.stderr)
                failures += 1
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
