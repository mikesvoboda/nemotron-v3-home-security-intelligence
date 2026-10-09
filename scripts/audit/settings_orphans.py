#!/usr/bin/env python3
"""Settings-orphan census (O1.7): committed scanner for the 00-audit §4.1 dead-fields count.

The audit's "50 of 337 settings fields are never read" (00-audit §4.1) came
from an uncommitted scan; B3.3 measures its cleanup against it. This script is
the scan view: it parses every field assignment in backend/core/config.py
with the stdlib AST (no import — the file needs the whole dependency tree at
import time), then counts reads of each field name OUTSIDE that file.

Field detection: a class-body annotation+assignment whose enclosing class is
transitively a BaseSettings subclass (pydantic-settings — the config module's
own nested-config classes inherit from a settings class in this same file, so
transitivity is computed within config.py, and a plain dataclass nested model
is NOT a settings field carrier unless it feeds one; top-level fields plus
fields of every transitively-settings class count).

Read detection: a word-boundary occurrence of the field name in any non-test
Python file outside backend/core/config.py — plus docker-compose*.yml and
setup.py at the repo root and in config/, because settings can be fed by env
from compose and the installer reads os.environ names directly. This is
deliberately an OVER-approximation of reads (textual, not symbol-resolved):
a name that appears in this set may still be dead, but a name absent from it
is provably unread — the direction that keeps B3.3's before-count honest and
its after-count safe to delete against. Tests never count as readers (a test
reading a field does not make it live).

Output: JSON on stdout (all/with_reads/orphans + per-field file:line of the
declaration), one summary line on stderr. Exit 0.

Run:    uv run python scripts/audit/settings_orphans.py [--root REPO]
Test:   uv run python -m pytest scripts/audit/test_settings_orphans.py -q
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from pathlib import Path

CONFIG_REL = "backend/core/config.py"
ENV_CONSUMERS_REL = ("setup.py",)
ENV_CONSUMER_GLOBS = ("docker-compose*.yml", "config/*.yml")
SKIP_DIRNAMES = {".git", "__pycache__", "node_modules", ".venv", ".pytest_cache", ".mypy_cache"}
BASE = "basesettings"


def settings_field_names(config_path: Path) -> dict[str, str]:
    """Field name -> 'file:line' for every field on a (transitively) BaseSettings class."""
    tree = ast.parse(config_path.read_text(encoding="utf-8"), filename=str(config_path))
    classes: dict[str, ast.ClassDef] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            classes[node.name] = node

    def base_names(cls: ast.ClassDef) -> set[str]:
        return {ast.unparse(b).split("[", 1)[0].split(".", 1)[-1] for b in cls.bases}

    # One case space for the whole walk: settings holds LOWERED class names,
    # base_names comes back lowered. Class identifiers are case-sensitive in
    # Python; the fold exists only so a spelling like ``Basesettings`` cannot
    # dodge detection — it must be applied to BOTH sides or the transitive
    # fixpoint below silently misses children (measured in the fixture test).
    settings = {n.lower() for n, c in classes.items() if BASE in {b.lower() for b in base_names(c)}}
    changed = True
    while changed:  # fixpoint: a class inheriting a settings class is itself settings-bearing
        changed = False
        for n, c in classes.items():
            if n.lower() not in settings and settings & {b.lower() for b in base_names(c)}:
                settings.add(n.lower())
                changed = True

    fields: dict[str, str] = {}
    for name, cls in classes.items():
        if name.lower() not in settings:
            continue
        for st in cls.body:
            if isinstance(st, ast.AnnAssign) and isinstance(st.target, ast.Name):
                loc = f"{CONFIG_REL}:{st.lineno}"
                fields.setdefault(st.target.id, loc)
    return fields


def reader_texts(root: Path) -> list[tuple[str, str]]:
    """(rel, text) for every non-test .py file plus compose/installer env surfaces."""
    out: list[tuple[str, str]] = []
    for path in sorted(root.rglob("*.py")):
        rel = path.relative_to(root).as_posix()
        if rel == CONFIG_REL or path.name.startswith("test_") or path.name == "conftest.py":
            continue
        if any(part in SKIP_DIRNAMES for part in path.relative_to(root).parts[:-1]):
            continue
        out.append((rel, path.read_text(encoding="utf-8", errors="replace")))
    surfaces: list[Path] = [root / r for r in ENV_CONSUMERS_REL if (root / r).is_file()]
    for glob in ENV_CONSUMER_GLOBS:
        surfaces += sorted(root.glob(glob))
    for path in surfaces:
        rel = path.relative_to(root).as_posix()
        out.append((rel, path.read_text(encoding="utf-8", errors="replace")))
    return out


def scan(root: Path) -> dict:
    fields = settings_field_names(root / CONFIG_REL)
    texts = reader_texts(root)
    readers: dict[str, list[str]] = {}
    for name in fields:
        # Case-insensitive on purpose: the field is ai_vlm_read_timeout, the
        # compose/env spelling is AI_VLM_READ_TIMEOUT (pydantic-settings'
        # default match is case-insensitive). Missing the case fold would
        # report live fields orphan — the false-DEAD direction this census
        # exists to avoid.
        pat = re.compile(rf"\b{re.escape(name)}\b", re.IGNORECASE)
        readers[name] = [rel for rel, text in texts if pat.search(text)]
    orphans = sorted(n for n, rs in readers.items() if not rs)
    return {
        "fields_total": len(fields),
        "fields_read": len(fields) - len(orphans),
        "orphans": len(orphans),
        "orphan_fields": [{"name": n, "declared_at": fields[n]} for n in orphans],
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    args = ap.parse_args(argv)
    if not (args.root / CONFIG_REL).is_file():
        print(f"[ERROR] {CONFIG_REL} not found under {args.root}", file=sys.stderr)
        return 1
    result = scan(args.root)
    json.dump(result, sys.stdout, indent=2, sort_keys=True)
    print(file=sys.stdout)
    print(
        f"O1.7 settings-orphans: {result['orphans']} of {result['fields_total']} "
        f"settings fields read nowhere outside {CONFIG_REL}",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
