#!/usr/bin/env python3
"""Dead-env-variable census (O1.7): committed scanner for the 00-audit §7 env count.

The audit's ".env.example: 182 variables; 34 are read by neither config.py nor
compose" (00-audit §7) was an uncommitted scan; O3.3 deletes against it and
adds the ratchet this census seeds. A variable is LIVE when its name appears
word-boundary in any of the three readers the package names:

  1. backend/core/config.py      (a settings field of that name, or an
                                  os.environ reference — textual, same
                                  over-approximation direction as
                                  settings_orphans.py: false-LIVE is safe,
                                  false-DEAD would delete a working var),
  2. any docker-compose*.yml at the repo root or under config/
     (env interpolation, ${VAR} and $VAR),
  3. setup.py at the repo root (the installer writes/reads the env file).

Variable detection: the KEY= lines of .env.example — leading whitespace
accepted (measured 2026-10-09: the real .env.example has zero indented key
lines, so tolerance is measurement-neutral and future-proof), comments (#)
and blank lines ignored, `export KEY=` accepted. Duplicate names count once
(vars_total is unique names; a duplicate IS drift — it is visible in the
raw file and in the duplicate-API_PORT note in 00-audit.md §7).

Output: JSON on stdout (vars_total / live / dead + dead names + a caveat that
names the live readers OUTSIDE the three contract readers — "dead to
config.py/compose/setup.py" is not the same claim as "deletable"), summary
line on stderr. Exit 0.

Run:    uv run python scripts/audit/env_dead_vars.py [--root REPO]
Test:   uv run python -m pytest scripts/audit/test_env_dead_vars.py -q
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ENV_EXAMPLE_REL = ".env.example"
READERS_FIXED = ("backend/core/config.py", "setup.py")
READER_GLOBS = ("docker-compose*.yml", "config/docker-compose*.yml")
KEY_RE = re.compile(r"^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=")

# Measured 2026-10-09 while answering the fresh-context review: the three
# readers are what §O1.7 names, but the tree holds more consumers. Travels
# with the JSON so a delete-list read downstream cannot mistake contract-
# dead for deletable (the doctrine's false-DEAD direction, stated by name).
DEAD_NOT_DELETABLE_NOTE = (
    "dead to the three contract readers (config.py/compose/setup.py) is not "
    "the same claim as deletable — known live readers elsewhere: VITE_* in "
    "frontend/src/config/env.ts, SYNTHBENCH_* in synthbench/, TMPDIR in "
    "scripts/fast-validation-playbook.sh, ALERTMANAGER_SMTP_* in "
    "docs/operator/smtp-configuration.md; re-check each against the whole tree"
)


def env_vars(env_text: str) -> list[str]:
    seen: dict[str, None] = {}
    for line in env_text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        m = KEY_RE.match(line)
        if m:
            seen.setdefault(m.group(1), None)
    return list(seen)


def reader_texts(root: Path) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    for rel in READERS_FIXED:
        p = root / rel
        if p.is_file():
            out.append((rel, p.read_text(encoding="utf-8", errors="replace")))
    for glob in READER_GLOBS:
        for p in sorted(root.glob(glob)):
            out.append((p.relative_to(root).as_posix(), p.read_text(encoding="utf-8", errors="replace")))
    return out


def scan(root: Path) -> dict:
    names = env_vars((root / ENV_EXAMPLE_REL).read_text(encoding="utf-8", errors="replace"))
    texts = reader_texts(root)
    dead = []
    for name in names:
        # Case-insensitive: pydantic-settings binds REDIS_SSL_ENABLED to the
        # field redis_ssl_enabled (case_sensitive=False default), so the
        # UPPER_SNAKE spelling lives in .env.example while the lowercase twin
        # is what appears in config.py. Measured on the first run: without the
        # fold, 41 of 63 "dead" names had a lowercase field — the false-DEAD
        # direction, which would have O3.3 deleting working variables.
        pat = re.compile(rf"\b{re.escape(name)}\b", re.IGNORECASE)
        if not any(pat.search(text) for _, text in texts):
            dead.append(name)
    return {
        "vars_total": len(names),
        "vars_live": len(names) - len(dead),
        "vars_dead": len(dead),
        "dead_vars": dead,
        "caveat": DEAD_NOT_DELETABLE_NOTE,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    args = ap.parse_args(argv)
    if not (root := args.root).is_dir() or not (root / ENV_EXAMPLE_REL).is_file():
        print(f"[ERROR] {ENV_EXAMPLE_REL} not found under {args.root}", file=sys.stderr)
        return 1
    result = scan(root)
    json.dump(result, sys.stdout, indent=2, sort_keys=True)
    print(file=sys.stdout)
    print(
        f"O1.7 env-dead-vars: {result['vars_dead']} of {result['vars_total']} "
        f"{ENV_EXAMPLE_REL} variables read by neither config.py, compose nor setup.py",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
