"""Guard the pre-commit config against the silent-no-op hook class.

Run explicitly (scripts/ is outside pytest testpaths); wired into CI's
anti-rot list. Parsed as TEXT on purpose: PyYAML is not a declared
dependency and `uv sync` demonstrably prunes undeclared packages (it
pruned pre-commit itself on 2026-09-16) — a guard that dies on a prune is
a guard that goes red for the wrong reason.

Red-first evidence (2026-09-16, WP2.5 close): validate.sh's frontend
prettier check failed on src/hooks/{useDateRangeState,useHouseholdApi}.test.ts
— the first time ANY gate ever actually checked them. Root cause:
prettier-frontend ran `bash -c '...'` with pass_filenames: true, and
pre-commit APPENDS the selected filenames to the command's argv — `bash -c`
binds the first appended word to $0 and the command string never sees ANY
filename. prettier then formats nothing and exits 0. Live proof: running the
shipped hook over a known-drifting file printed "Passed" and left the file
untouched. Every "prettier passed" from this hook since inception was
vacuous; CI has no format:check step either, so the two blind spots stacked
(WP0.7 doctrine: a gate with no CI is a gate that rots — this guard is the
hook's own CI). The same class has a second door: pass_filenames paths are
REPO-ROOT-RELATIVE, so an entry that `cd frontend` resolves
`frontend/src/...` against frontend/, matches nothing, and --ignore-unknown
turns that into a silent 0 too.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

CONFIG = Path(__file__).resolve().parent.parent / ".pre-commit-config.yaml"
FRONTEND_LOCK = CONFIG.parent / "frontend" / "package-lock.json"


def hook_blocks():
    """(hook_id, {field: value}) per hook block — text parse, YAML-lite:
    `- id:` opens a block, `field: value` lines belong to the open block."""
    block_id, fields = None, {}
    for line in CONFIG.read_text(encoding="utf-8").splitlines():
        m = re.match(r"\s*- id:\s*(\S+)", line)
        if m:
            if block_id:
                yield block_id, fields
            block_id, fields = m.group(1), {}
            continue
        if block_id:
            f = re.match(r"\s*(\w+):\s*(.*)$", line)
            if f:
                fields[f.group(1)] = f.group(2).strip()
    if block_id:
        yield block_id, fields


def pass_filenames_bash_hooks():
    for hid, f in hook_blocks():
        entry = f.get("entry", "")
        if entry.startswith("bash -c") and f.get("pass_filenames") == "true":
            m = re.match(r"""bash -c\s+['"](.*)['"]\s*$""", entry, re.S)
            yield hid, (m.group(1) if m else entry)


def test_appended_filenames_reach_the_command_string():
    """pre-commit appends filenames AFTER the bash -c command string, where
    bash binds the first to $0 and the rest to $@ — a command that never
    references $1/$@/${...} formats NOTHING while exiting 0 (the shipped
    prettier-frontend bug, caught by WP0.1's repaired validate gate)."""
    offenders = [
        hid for hid, cmd in pass_filenames_bash_hooks() if not re.search(r"\$(?:1\b|@|\{)", cmd)
    ]
    assert not offenders, (
        f"pass_filenames bash -c hooks whose filenames never reach the command "
        f'(silent no-op): {offenders} — reference "$@" and put a sentinel word '
        f"after the command string so every filename lands in $@, not $0."
    )


def test_filenames_rebased_after_cd():
    """A command that `cd`s into a subdir must strip that prefix from the
    repo-root-relative filenames it was passed (${@#subdir/}); passing them
    unchanged makes path-based tools match nothing."""
    offenders = []
    for hid, cmd in pass_filenames_bash_hooks():
        m = re.search(r"\bcd\s+([A-Za-z0-9_./-]+)", cmd)
        if m and f"# {m.group(1)}/".replace(" ", "") not in cmd:
            offenders.append(hid)
    assert not offenders, (
        f'bash -c hooks that cd into a subdir without rebasing $@ ("${{x#subdir/}}"): {offenders}'
    )


def _dep_versions(hook_id: str) -> list[str]:
    """npm/PyPI requirement strings under hook_id's block's
    `additional_dependencies:` list. Text parse: the block runs from this
    hook's `- id:` line to the next one; inside it, the list's items are
    `- dep` lines and comments are allowed between them (config style)."""
    block, inside = [], False
    for line in CONFIG.read_text(encoding="utf-8").splitlines():
        m = re.match(r"\s*- id:\s*(\S+)", line)
        if m:
            if inside:
                break
            inside = m.group(1) == hook_id
            continue
        if inside:
            block.append(line)
    deps, listing = [], False
    for line in block:
        if re.match(r"\s*additional_dependencies:\s*$", line):
            listing = True
            continue
        if not listing:
            continue
        stripped = line.strip()
        if stripped.startswith("#"):
            continue
        dep = re.match(r"-\s*(\S+)", stripped)
        if dep:
            deps.append(dep.group(1))
        elif stripped:
            listing = False  # next key closes the list
    return deps


def test_the_two_prettier_hooks_pin_the_same_version():
    """Owner ruling 24 (2026-10-09): ONE prettier for the repo. The general
    mirrors-prettier hook (language: node — so its additional_dependencies
    are npm coords, NOT the PyPI decoy package at 0.0.7) and the local
    prettier-frontend hook (language: system, resolves node_modules) both
    claim markdown, and until this guard they pinned 3.2.4 vs 3.9.9 — the
    version changed the answer, so the same file was format-red for one hook
    and clean for the other (the split-brain that reddened #6869 for main's
    own bytes and blocked #6861/#6907). The frontend answer is the
    lockfile's; the config must follow it, and a future bump that moves one
    side alone must go RED here, not silently re-split the formatting.

    Also asserted: the mirror's `rev:` is NOT the version pin (rev only
    scaffolds a language: node hook), so reviewers must not 'fix' the split
    by touching rev alone — the real pin lives in additional_dependencies."""
    lock = json.loads(FRONTEND_LOCK.read_text(encoding="utf-8"))
    (lock_node,) = [
        node
        for path, node in lock["packages"].items()
        if path == "node_modules/prettier" or path.endswith("/node_modules/prettier")
    ]
    frontend_pin = lock_node["version"]

    general_deps = _dep_versions("prettier")
    general_pin = next(
        (
            m.group(1)
            for d in general_deps
            for m in [re.match(r"(?:@?prettier)@(.+)$", d)]
            if m
        ),
        None,
    )
    assert general_pin, f"hook id 'prettier' pins no prettier version in {general_deps}"
    assert general_pin == frontend_pin, (
        f"prettier split-brain re-opened: the mirrors-prettier hook runs "
        f"{general_pin} but frontend/node_modules is {frontend_pin} — the two "
        "hooks format the same markdown with different rules (owner ruling "
        "24; see .pre-commit-config.yaml's comment on why rev: is not the pin)"
    )
