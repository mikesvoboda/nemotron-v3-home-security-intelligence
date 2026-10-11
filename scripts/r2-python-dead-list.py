#!/usr/bin/env python3
"""O2.3b (ruling 73): regenerate R2's Python input for "Modules serving no
feature" from the reachability tool.

R2's input is the non-shipping list of `scripts/reachability.py` MINUS every
module a feature row claims (`docs/uplevel/templates/r2-sheet.md` §3; owner
ruling 50 pre-authorized both landing spots to receive this list when O2.3
merged — the pending paragraphs said so verbatim). O2.3b's ancestor fix
(ruling 73) is why the list is regenerated rather than pasted from O2.3's
run: the 19 parent `__init__.py` files the old walk reported dead run at
import time and must not sit on a deletion list.

Writes two marker-delimited regions (single source of truth = this tool):

  docs/reference/feature-inventory.md  §4 "Python"   — the full table
  docs/uplevel/r2-sheet.md             §3 "Python"   — the session prose

Columns follow the R2 template and the frontend precedent: module | lane |
lines | last meaningful commit | notes. "Last meaningful commit" is the
newest commit touching the file that changed fewer than 100 files — the
inventory §4 definition verbatim, so squash merges and lockfile sweeps do
not mask a file's age. Merges emit no file list under default diff-merges
and never match a path query, which matches the frontend method.

    uv run python scripts/r2-python-dead-list.py            # rewrite regions
    uv run python scripts/r2-python-dead-list.py --check    # verify, exit 1 on drift

--check regenerates the table from the CURRENT tree (that is the point: an
R2 input that stopped matching the tool is stale), but the git-history
column cannot be recomputed in a shallow CI checkout (30 of 31 battery-job
checkouts are depth-1, measured), so it is masked there and validated by
format only. The full-history box regenerates and compares everything.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
INVENTORY = REPO_ROOT / "docs" / "reference" / "feature-inventory.md"
R2_SHEET = REPO_ROOT / "docs" / "uplevel" / "r2-sheet.md"
START = "<!-- r2-python-dead-list:start -->"
END = "<!-- r2-python-dead-list:end -->"
MEANINGFUL_MAX_FILES = 100


def _load_reach():
    spec = importlib.util.spec_from_file_location(
        "reachability", REPO_ROOT / "scripts" / "reachability.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _git(*args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(REPO_ROOT), *args],
        capture_output=True,
        text=True,
        check=True,
    ).stdout


# ------------------------------------------------------- claims from rows --


def claimed_by_rows() -> dict[str, list[str]]:
    return _claims_from_text(INVENTORY.read_text(encoding="utf-8"))


def _claims_from_text(text: str) -> dict[str, list[str]]:
    """path -> row ids, from the inventory's `modules` column (a row's claim
    set — evidence cites are not claims). Column located by header name so a
    column move cannot silently empty the claim set."""
    rows = [line for line in text.splitlines() if re.match(r"^\|\s*F-\d+\s*\|", line)]
    header = None
    for line in text.splitlines():
        if not line.startswith("|"):
            continue
        cols = [c.strip().lower() for c in line.strip().strip("|").split("|")]
        if "id" in cols and "modules" in cols:
            header = line
            break
    if header is None:
        raise SystemExit("r2-python-dead-list: no inventory header with both id+modules")
    cols = [c.strip().lower() for c in header.strip().strip("|").split("|")]
    try:
        mods_idx = cols.index("modules")
    except ValueError:
        raise SystemExit("r2-python-dead-list: inventory header has no `modules` column")
    claims: dict[str, list[str]] = {}
    for line in rows:
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) <= mods_idx:
            continue
        row_id = cells[0]
        for m in re.finditer(
            r"`((?:backend|ai|synthbench)/[A-Za-z0-9_./-]+\.py)(?::[\d,. -]+)?`",
            cells[mods_idx],
        ):
            claims.setdefault(m.group(1), []).append(row_id)
    return claims


# ------------------------------------------------------- history columns --


def _width_map() -> dict[str, tuple[str, str, int]]:
    """sha -> (short sha, YYYY-MM-DD, files touched by this commit).
    Default `git log --name-only` omits merge diffs, so merges carry zero
    files — consistent with a path query never matching a merge."""
    out = _git(
        "log",
        "--format=\x01%H \x01%h \x01%ad",
        "--date=short",
        "--name-only",
    )
    widths: dict[str, tuple[str, str, int]] = {}
    cur: str | None = None
    count = 0
    for line in out.splitlines():
        if line.startswith("\x01"):
            if cur is not None:
                widths[cur] = (short, date, count)  # type: ignore[name-defined]
            full, short, date = line.strip("\x01").split(" \x01")
            cur, count = full, 0
        elif line.strip():
            count += 1
    if cur is not None:
        widths[cur] = (short, date, count)  # type: ignore[name-only]
    return widths


def last_meaningful(rel: str, widths: dict[str, tuple[str, str, int]]) -> str:
    """Newest commit touching `rel` that changed < 100 files; '-' if none
    (a file newer than history, or only touched by wide commits — both are
    visible in the table rather than hidden)."""
    for full in _git("log", "--format=%H", "--", rel).split():
        hit = widths.get(full)
        if hit and hit[2] < MEANINGFUL_MAX_FILES:
            return f"`{hit[0]}` {hit[1]}"
    return "-"


# ------------------------------------------------------------- rendering --


def build_table(
    dead: dict[str, int], claimed: dict[str, list[str]], head: str, history: bool
) -> tuple[str, int, int]:
    """Returns (region markdown, list size, listed lines). `dead` excludes
    tests by construction (the tool's candidate rule); claims are the
    exceptions. Region is pure markdown — no heading — between the markers."""
    exceptions = sorted(set(dead) & set(claimed))
    listed = sorted(set(dead) - set(claimed))
    listed_lines = sum(dead[rel] for rel in listed)
    widths = _width_map() if history else {}
    rows = []
    for rel in listed:
        lane = rel.split("/", 1)[0]
        col = last_meaningful(rel, widths) if history else "`-` 1970-01-01"
        rows.append(f"| `{rel}` | {lane} | {dead[rel]} | {col} | non-shipping |")
    ex_rows = [
        f"| `{rel}` | {dead[rel]} | {'/'.join(sorted(set(claimed[rel])))} |"
        for rel in exceptions
    ]
    parts = [
        f"Measured at tool-inputs `{head}` by `scripts/r2-python-dead-list.py` — the "
        f"non-shipping output of `scripts/reachability.py` after the O2.3b ancestor fix "
        f"(ruling 73: the 19 parent `__init__.py` files a module's import runs are NOT "
        f"here), minus every module a row claims, which are named below.",
        "",
        f"**{len(listed)} non-shipping Python modules ({listed_lines} lines).** "
        f"Deleted as a whole by the `R2` ruling (exceptions named); `B3.2` executes.",
        "",
        "<!-- prettier-ignore -->",
        "| module | lane | lines | last meaningful commit | notes |",
        "| --- | --- | --- | --- | --- |",
        *rows,
        "",
        f"**Claimed by a row, excluded from the list ({len(exceptions)}):**",
        "",
        "<!-- prettier-ignore -->",
        "| module | lines | claimed by |",
        "| --- | --- | --- |",
        *ex_rows,
    ]
    return "\n".join(parts), len(listed), listed_lines


def build_r2_prose(listed: int, listed_lines: int, dead: dict[str, int],
                   claimed: dict[str, list[str]], head: str) -> str:
    exceptions = sorted(set(dead) & set(claimed))
    ex_clause = "; ".join(
        f"`{rel}` ({'/'.join(sorted(set(claimed[rel])))})" for rel in exceptions
    )
    return (
        f"Measured at tool-inputs `{head}` from the fixed tool (`scripts/reachability.py` "
        f"after the O2.3b ancestor fix, ruling 73): {listed} non-shipping Python modules "
        f"({listed_lines} lines), listed with lines and last meaningful commit in "
        f"[`feature-inventory.md` §4](../reference/feature-inventory.md#4-modules-serving-no-feature), "
        f"Python. The {len(exceptions)} modules a row claims are named as exceptions there — "
        f"{ex_clause}. "
        f"The ancestor-rule note for the ruling: parent packages of shipping modules ship "
        f"(import runs them), so the list cannot be the pre-O2.3b count; regenerating it "
        f"is `scripts/r2-python-dead-list.py`.")


def replace_region(text: str, label: str, body: str) -> str:
    s, e = text.find(START), text.find(END)
    if s == -1 or e == -1 or e < s:
        raise SystemExit(f"r2-python-dead-list: markers not found in {label}")
    return text[: s + len(START)] + "\n" + body.rstrip("\n") + "\n" + text[e:]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--check", action="store_true",
                    help="regenerate in memory and compare; exit 1 on drift")
    ap.add_argument("--history", action="store_true",
                    help="recompute the git-history column (needs full history)")
    args = ap.parse_args(argv)

    reach = _load_reach()
    entries, allow = reach.load_entry_points(reach.DEFAULT_ENTRIES)
    keep = reach.load_keep(reach.DEFAULT_KEEP)
    out = reach.analyze(
        REPO_ROOT, entries=entries, candidate_dirs=reach.DEFAULT_CANDIDATE_DIRS,
        keep=keep, dynamic_allow=allow)
    dead = {m["module"]: m["lines"] for m in out["not_shipping"]}
    claimed = claimed_by_rows()
    # Stamp = hash of the tool's INPUTS (walker + both configs), not a commit
    # id: a commit stamp drifts red for unrelated reasons (it is recomputed
    # from HEAD, which a pre-commit hook sees before the commit that
    # regenerates the region, and an update-branch merge moves without
    # touching the table). If the walker changes, this hash changes — and a
    # stale table is exactly what --check must catch. A row edit changing
    # claims shows up as real exception-row drift.
    head = _walker_hash()
    history = args.history or not args.check or _has_full_history()

    inv_table, listed, listed_lines = build_table(dead, claimed, head, history=history)
    r2_body = build_r2_prose(listed, listed_lines, dead, claimed, head)

    inv_text = INVENTORY.read_text(encoding="utf-8")
    r2_text = R2_SHEET.read_text(encoding="utf-8")
    new_inv = replace_region(inv_text, str(INVENTORY.relative_to(REPO_ROOT)), inv_table)
    new_r2 = replace_region(r2_text, str(R2_SHEET.relative_to(REPO_ROOT)), r2_body)

    if not args.check:
        INVENTORY.write_text(new_inv, encoding="utf-8")
        R2_SHEET.write_text(new_r2, encoding="utf-8")
        print(f"wrote §4 table ({listed} modules, {listed_lines} lines) + r2-sheet prose "
              f"at head {head} (history column: {'on' if history else 'off'})")
        return 0

    # --check: compare against committed regions. The history column is
    # masked when it could not be recomputed (shallow CI checkout); format
    # validated instead. Table columns 1-3 (path, lane, lines) always
    # compare. EDGES ARE STRIPPED: prettier (a registered hook over these
    # docs) owns the blank lines between the markers and the region's first/
    # last block — and it normalizes a table-ending region differently from
    # a prose-ending one (measured 2026-10-10). Content is what must match;
    # marker-edge whitespace matching byte-for-byte would make the gate
    # redden on formatting, which is not freshness.
    problems: list[str] = []
    for label, old, new in (
        ("feature-inventory.md", _region(inv_text), _region(new_inv)),
        ("r2-sheet.md", _region(r2_text), _region(new_r2)),
    ):
        if not history:
            old, new = _mask_history(old), _mask_history(new)
            problems += _history_format_problems(_region(inv_text))
        if old.strip() != new.strip():
            problems.append(f"{label}: region drifted (run the tool without --check)")
    if problems:
        for p in problems:
            print(f"STALE: {p}", file=sys.stderr)
        return 1
    print(f"fresh: {listed} modules / {listed_lines} lines at head {head} "
          f"(history column: {'recomputed' if history else 'format-checked'})")
    return 0


def _walker_hash() -> str:
    """First 10 hex of sha256 over the walker + both configs, path+bytes.
    Content-addressed: stable across clones, checkouts, and time; changes
    exactly when the tool that produced the table changes."""
    h = hashlib.sha256()
    for rel in ("scripts/reachability.py", "scripts/reachability/entry_points.toml",
                "scripts/reachability/keep.toml"):
        h.update(rel.encode())
        h.update((REPO_ROOT / rel).read_bytes())
    return h.hexdigest()[:10]


def _region(text: str) -> str:
    s, e = text.find(START), text.find(END)
    return text[s + len(START):e]


def _mask_history(text: str) -> str:
    # The per-file history column (4th cell; the 3-col exceptions rows are
    # anchored out by the "non-shipping" note cell). The tool-inputs stamp
    # needs no mask: it hashes file CONTENT, identical in every checkout.
    return re.sub(r"^\| (`[^`]+`) \| (\w+) \| (\d+) \| .+? \| (non-shipping) \|$",
                  r"| \1 | \2 | \3 | @H@ | \4 |", text, flags=re.M)


def _history_format_problems(text: str) -> list[str]:
    bad = []
    for line in text.splitlines():
        # only the 5-col list rows carry a history cell; the 3-col
        # exceptions rows start the same way
        if not re.match(r"^\| `(?:backend|ai|synthbench)/", line):
            continue
        if not line.endswith("non-shipping |"):
            continue
        # real sha + date cell anywhere, or the documented bare "-" cell
        # (every commit touching the file was wide — 22 rows today,
        # reproduced from history)
        if not re.search(r"\| `[0-9a-f]{7,40}` \d{4}-\d{2}-\d{2} \||\| - \| non-shipping \|$",
                        line):
            bad.append(f"malformed history cell: {line[:80]}")
    return bad


def _has_full_history() -> bool:
    try:
        return int(_git("rev-list", "--count", "HEAD").strip()) > 200
    except subprocess.CalledProcessError:
        return False


if __name__ == "__main__":
    sys.exit(main())
