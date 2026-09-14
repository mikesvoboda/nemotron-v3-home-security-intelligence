#!/usr/bin/env python3
"""Flake-allowlist hygiene (fast-confidence-loop spec §5.2/§6.6).

Every entry must carry a tracking ref and a non-expired ISO date. An expired
entry fails until it is re-registered or removed — the expiry IS the enforcement.
Parses the YAML with a stdlib line reader (the list is flat and tiny; no PyYAML
dependency so the check runs anywhere, including before `uv sync`).

Usage: check-flake-allowlist.py [--file PATH] [--today YYYY-MM-DD]
Exit: 0 ok, 1 violations, 2 malformed file.
"""

from __future__ import annotations

import argparse
import datetime as dt
import re
import sys
from pathlib import Path

DEFAULT_FILE = ".github/workflows/flake-allowlist.yml"
ENTRY_RE = re.compile(r"^\s*-\s+id:\s*(\S+)")
FIELD_RE = re.compile(r"^\s+(tracking|expires|note):\s*(.+?)\s*$")


def parse_allowlist(text: str) -> list[dict[str, str]]:
    entries: list[dict[str, str]] = []
    for line in text.splitlines():
        m = ENTRY_RE.match(line)
        if m:
            entries.append({"id": m.group(1)})
            continue
        if entries:
            fm = FIELD_RE.match(line)
            if fm:
                entries[-1][fm.group(1)] = fm.group(2).strip("'\"")
    return entries


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", default=DEFAULT_FILE)
    ap.add_argument("--today", default="")  # test seam; real runs use system date
    args = ap.parse_args(argv[1:])
    path = Path(args.file)
    if not path.is_file():
        print(f"flake-allowlist: {path} missing", file=sys.stderr)
        return 2
    entries = parse_allowlist(path.read_text(encoding="utf-8"))
    today = dt.date.fromisoformat(args.today) if args.today else dt.date.today()
    violations = []
    for e in entries:
        if not e.get("tracking"):
            violations.append(f"{e['id']}: missing tracking ref")
        raw_exp = e.get("expires", "")
        try:
            exp = dt.date.fromisoformat(raw_exp)
        except ValueError:
            violations.append(f"{e['id']}: missing/unparseable expires date")
            continue
        if exp < today:
            violations.append(f"{e['id']}: expired {exp} — fix or re-register")
    for v in violations:
        print(f"flake-allowlist: {v}", file=sys.stderr)
    if violations:
        return 1
    print(f"flake-allowlist: {len(entries)} entries, all registered and unexpired")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
