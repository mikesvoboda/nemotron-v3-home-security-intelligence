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

Read detection (three classes, all over-approximate on purpose):
  1. a word-boundary occurrence of the field name in any non-test Python file
     OUTSIDE backend/core/config.py — plus docker-compose*.yml and setup.py at
     the repo root and in config/, because settings can be fed by env from
     compose and the installer reads os.environ names directly;
  2. a read INSIDE config.py that a cross-file grep structurally cannot see:
     a model/field validator touching the field (self.X, info.data.get("X"),
     getattr(self, "X"), or a "X" string in a @field_validator/@model_validator
     decorator). Such a field gates a startup error and is LIVE whatever other
     code does — B3.3 found four fields (llama_slot_count, vlm_slot_count, the
     violence thresholds) reported orphan purely because of this blind spot;
  3. the ENV spelling the field actually binds: a validation_alias= name, or
     an env_prefix= class whose PREFIX+UPPER(NAME) compose sets. The plain
     \bNAME\b regex cannot match e.g. TRANSCODE_CACHE_<FIELD> (the underscore
     joining prefix to name kills the word boundary), so prefixed fields were
     false-dead too whenever an operator surface set the prefixed name.
A field's Field(description=...) text is deliberately NOT a read: descriptions
mention other field names (nemotron_context_window's describes the
llama_slot_count division) and must not rescue anything. Tests never count as
readers (a test reading a field does not make it live).

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
# The census must not read itself: its comments document dead-name spellings
# (an example like TRANSCODE_CACHE_<FIELD> would otherwise "rescue" the field
# it illustrates — measured live when this script's own examples first ran).
SELF_REL = "scripts/audit/settings_orphans.py"
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
        if rel in (CONFIG_REL, SELF_REL) or path.name.startswith("test_") or path.name == "conftest.py":
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


def config_internal_reads(config_path: Path, field_names: set[str]) -> tuple[set[str], dict[str, set[str]]]:
    """(validator-read field names, field -> extra env spellings) from config.py's own AST.

    Class 2 (validator reads): inside a model_validator body, any self.X,
    .get("X")/["X"] string key, or getattr(self, "X") that matches a known
    field name counts as a read; a @field_validator("X") decorator string
    counts as a read of X. Bare Names (locals), message prose, and Field(...)
    descriptions are NEVER scanned, so documentation text cannot rescue a field.
    Class 3 (env spellings): validation_alias/alias constants, plus
    PREFIX + NAME.upper() for any class whose model_config sets env_prefix.
    """
    tree = ast.parse(config_path.read_text(encoding="utf-8"), filename=str(config_path))
    validator_reads: set[str] = set()
    env_spellings: dict[str, set[str]] = {}

    def add_read(name: str) -> None:
        if name in field_names:
            validator_reads.add(name)

    def scan_validator_body(fn: ast.AST) -> None:
        for sub in ast.walk(fn):
            if isinstance(sub, ast.Attribute) and isinstance(sub.value, ast.Name) and sub.value.id == "self":
                add_read(sub.attr)
            elif isinstance(sub, (ast.Subscript, ast.Call)):
                # ONLY string keys that dereference: .get("X"), ["X"],
                # getattr(self, "X"). A bare Name is a LOCAL variable
                # (fields in a method body are always self.X), and message/
                # docstring prose (f-string literal parts) must not count —
                # exact-set membership keeps "context_budget too low for" out.
                nodes = (
                    [sub.slice]
                    if isinstance(sub, ast.Subscript)
                    else [*sub.args, *[k.value for k in sub.keywords]]
                )
                for node in nodes:
                    for const in ast.walk(node):
                        if isinstance(const, ast.Constant) and isinstance(const.value, str):
                            add_read(const.value)

    for cls in (n for n in ast.walk(tree) if isinstance(n, ast.ClassDef)):
        prefix = None
        for st in cls.body:
            targets = st.targets if isinstance(st, ast.Assign) else [st.target] if isinstance(st, ast.AnnAssign) else []
            if not any(isinstance(t, ast.Name) and t.id == "model_config" for t in targets):
                continue
            # both spellings pydantic accepts: SettingsConfigDict(env_prefix=...)
            # (config.py's form) and a bare {"env_prefix": ...} dict
            kw = next(
                (k.value for k in getattr(st.value, "keywords", []) if k.arg == "env_prefix"),
                None,
            )
            if kw is None and isinstance(st.value, ast.Dict):
                kw = next(
                    (v for k, v in zip(st.value.keys, st.value.values, strict=False)
                     if isinstance(k, ast.Constant) and k.value == "env_prefix"),
                    None,
                )
            if isinstance(kw, ast.Constant) and isinstance(kw.value, str):
                prefix = kw.value
        for st in cls.body:
            if not (isinstance(st, ast.AnnAssign) and isinstance(st.target, ast.Name)):
                continue
            name = st.target.id
            if prefix:
                # every field of a prefixed class binds PREFIX+UPPER(NAME),
                # bare-annotated defaults included — this is the whole point
                # of class 3 (the \bNAME\b regex cannot match the prefix half)
                env_spellings.setdefault(name, set()).add(prefix + name.upper())
            if isinstance(st.value, ast.Call):
                for kw in st.value.keywords:
                    if kw.arg in ("alias", "validation_alias"):
                        # AliasExpr unions can be Alias/str/alias() mixed;
                        # collect every string constant in the expression.
                        # ast.walk on a bare Constant yields the node AND its
                        # raw .value, so test isinstance before touching .value.
                        for k in ast.walk(kw.value):
                            if isinstance(k, ast.Constant) and isinstance(k.value, str):
                                env_spellings.setdefault(name, set()).add(k.value)
        for fn in cls.body:
            if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for dec in fn.decorator_list:
                # @model_validator / @field_validator arrive as a Call whose
                # func is a bare Name (imported) OR an Attribute (qualified);
                # a bare decorator with no args arrives as plain Name/Attribute
                inner = dec.func if isinstance(dec, ast.Call) else dec
                if isinstance(inner, ast.Attribute):
                    fname = inner.attr
                elif isinstance(inner, ast.Name):
                    fname = inner.id
                else:
                    fname = ""
                if fname not in ("model_validator", "field_validator", "validator"):
                    continue
                if fname == "model_validator":  # body reads other fields
                    scan_validator_body(fn)
                for arg in (dec.args if isinstance(dec, ast.Call) else []):  # decorator field-name strings
                    if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                        add_read(arg.value)
    return validator_reads, env_spellings


def scan(root: Path) -> dict:
    fields = settings_field_names(root / CONFIG_REL)
    texts = reader_texts(root)
    validator_reads, env_spellings = config_internal_reads(root / CONFIG_REL, set(fields))
    readers: dict[str, list[str]] = {}
    for name in fields:
        # Case-insensitive on purpose: the field is ai_vlm_read_timeout, the
        # compose/env spelling is AI_VLM_READ_TIMEOUT (pydantic-settings'
        # default match is case-insensitive). Missing the case fold would
        # report live fields orphan — the false-DEAD direction this census
        # exists to avoid.
        pat = re.compile(rf"\b{re.escape(name)}\b", re.IGNORECASE)
        readers[name] = [rel for rel, text in texts if pat.search(text)]
        if name in validator_reads:
            readers[name].append(f"{CONFIG_REL} (validator)")
        for spelling in env_spellings.get(name, ()):
            # Substring, not \b: a PREFIX+NAME spelling has no word boundary
            # before the name half. Length-guarded so a 1-2 char alias can't
            # match arbitrary prose.
            if len(spelling) >= 5 and any(spelling.lower() in text.lower() for _, text in texts):
                readers[name].append(f"env spelling {spelling}")
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
