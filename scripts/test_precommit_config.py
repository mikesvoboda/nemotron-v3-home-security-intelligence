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

import re
from pathlib import Path

CONFIG = Path(__file__).resolve().parent.parent / ".pre-commit-config.yaml"


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
