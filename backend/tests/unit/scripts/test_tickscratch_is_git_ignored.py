""".tickscratch/ is review material (UR-89) and must be git-ignored, not merely
untracked.

The two sweep pins in this directory (`test_vlm_profile_flag_is_retired.py`,
`test_backend_image_trivy_clean.py`) keep the review scratch out of the TEST
walks. This pins the other half of what makes the tree safe to leave lying at
the repo root, which no walk can give you: `git status` reports an ignored tree,
not an untracked one. An untracked multi-GB materialisation in front of every
`git add -A` is exactly how one of this package's own controls shipped 7,650
`__pycache__`/`.pytest_cache` files into a commit (measured 2026-10-17, quoted
in #7240's review object `#issuecomment-6239406426`): the ignore rule is what
stands between "untracked review material" — the wording both sibling pins use
— and a stray that gets staged for real.

Pinned through `git check-ignore -v` (pathnames, nothing planted on disk)
because the alternatives are worse instruments: `git status` is slow and shows
this test's own file, and a live `.tickscratch/` directory on the machine
running the test is an environment property, which is the thing the sibling
pins refuse to depend on. A pattern match needs no file to exist — verified,
and relied on here.

Why the pinned forms carry a trailing slash: a directory pattern matches the
slash form and everything under it, and does so whether or not the tree is on
disk (measured: `.tickscratch/` and `.tickscratch/a/b.py` → rc 0 in a workspace
holding no `.tickscratch` at all, which is the CI shape). The BARE form `.tickscratch`
is deliberately not pinned, because matching it does depend on the directory
existing (rc 1 when it does not) — pinning it here would go red on a runner that
correctly has no scratch, for a shape no reviewer uses.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]

# `--no-index` so the answer comes from the ignore rules and not from the index:
# the test asks "is this name ignored", never "is this name untracked".
_BASE = ["git", "check-ignore", "-v", "--no-index"]
# An empty global excludes file, so the verdict is this repo's rule and not the
# machine's `~/.gitconfig` core.excludesFile (a dev ignoring scratch globally
# must not be able to green this pin). `-c` is a GIT-level flag: it goes before
# the subcommand, or git exits 129 with "unknown switch" (measured).
_GLOBAL = ["-c", "core.excludesFile=/dev/null"]


def _verdict(pathname: str) -> tuple[int, str]:
    """(rc, matched-line) for one repo-relative pathname under the ignore rules."""
    proc = subprocess.run(  # noqa: S603  # fixed argv, our own git; rc is the verdict  # real
        [_BASE[0], *_GLOBAL, *_BASE[1:], "--", pathname],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,  # rc 0/1 IS the measurement; rc>1 is raised below
    )
    if proc.returncode not in (0, 1):
        raise RuntimeError(
            f"git check-ignore failed (rc {proc.returncode}) in {REPO_ROOT}: {proc.stderr.strip()}"
        )
    return proc.returncode, proc.stdout.strip()


def _matching_gitignore_line(pattern: str) -> str | None:
    """The literal line in root `.gitignore` whose pattern is exactly `pattern`."""
    for line in (REPO_ROOT / ".gitignore").read_text(encoding="utf-8").splitlines():
        if line.strip() == pattern:
            return line.strip()
    return None


def test_the_ignore_rule_ships_in_the_root_gitignore() -> None:
    """The rule lives in the tracked file, not on a machine.

    Asserted as file content first because `check-ignore` will happily report a
    hit from `.git/info/exclude` or a global excludes file — a green that came
    from the laptop rather than from the repo would protect no one else's
    `git add -A`, which is the entire point of the rule.
    """
    assert _matching_gitignore_line(".tickscratch/") is not None, (
        "root .gitignore has no '.tickscratch/' line: review scratch stays "
        "visible to git status and one 'git add -A' in a materialisation "
        "stages the tree (measured: 7650 stray files into one control commit)"
    )


def test_review_scratch_paths_are_ignored() -> None:
    """The directory, and paths under it, resolve as ignored — at any depth.

    Nested worktree paths are the shape UR-89 materialisations actually have
    (`.tickscratch/<name>/tree/...`), and depth is what makes a directory
    pattern the right form: the walker does not need the directory to exist.
    """
    for pathname in (".tickscratch/", ".tickscratch/wt-a/tree/scripts/x.py"):
        rc, matched = _verdict(pathname)
        assert rc == 0, f"{pathname!r} is not ignored by any rule (rc 1); matched: {matched!r}"
        assert matched.startswith(".gitignore:"), (
            f"{pathname!r} is ignored by {matched!r}, not by the root .gitignore — "
            "a machine-local rule cannot protect another machine's index"
        )


def test_the_rule_ignores_scratch_and_nothing_else() -> None:
    """Controls, both directions, so neither a broken instrument nor an over-broad rule passes.

    A positive on a path the repo already ignores proves `check-ignore -v` and
    the citation assertion are live (an assertion that nothing matches passes
    when the tool is broken); a negative on a real tracked file proves the new
    line did not become something that eats the tree.
    """
    rc, matched = _verdict("__pycache__/x.pyc")
    assert rc == 0 and matched.startswith(".gitignore:"), matched

    for tracked in (
        "backend/tests/unit/scripts/test_tickscratch_is_git_ignored.py",
        ".gitignore",
        "backend/Dockerfile",
    ):
        rc, matched = _verdict(tracked)
        assert rc == 1, f"{tracked!r} is ignored by {matched!r} — the rule is eating tracked files"
