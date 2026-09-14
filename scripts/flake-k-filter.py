#!/usr/bin/env python3
"""Print allowlist flake ids as a pytest -k expression ('' when none).

Standalone by design (spec §5.2 T2 correction): the 15-line flat-list parser is
duplicated from check-flake-allowlist.py rather than imported, so both scripts
run anywhere with zero package coupling. Expired entries are excluded — an
expired id never reaches pytest.
"""

from __future__ import annotations

import argparse
import datetime as dt
import re
import sys
from pathlib import Path

DEFAULT_FILE = ".github/flake-allowlist.yml"
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


def active_ids(path: Path | None = None, today: dt.date | None = None) -> list[str]:
    path = path or Path(DEFAULT_FILE)
    if not path.is_file():
        return []
    today = today or dt.date.today()
    ids = []
    for e in parse_allowlist(path.read_text(encoding="utf-8")):
        try:
            if dt.date.fromisoformat(e.get("expires", "")) < today:
                continue  # expired = unregistered (hygiene script fails CI on it)
        except ValueError:
            continue
        ids.append(e["id"])
    return ids


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", default=DEFAULT_FILE)
    ap.add_argument("--today", default="")  # test seam; CI runs argless
    args = ap.parse_args(argv[1:])
    today = dt.date.fromisoformat(args.today) if args.today else None
    print(" or ".join(active_ids(Path(args.file), today)))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
