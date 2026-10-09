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

Variable detection: the KEY= lines of .env.example — top-level keys only
(nested YAML-like indentation is not an env assignment), comments (#) and
blank lines ignored, `export KEY=` accepted.

Output: JSON on stdout (vars_total / live / dead + dead names), summary line
on stderr. Exit 0.

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
