#!/usr/bin/env python3
"""Post an owner record or an owner pointer with ruling 197's machine footer.

    uv run python scripts/uplevel/post_record.py record --ruling N --lanes a,b|all \\
        --packages r1,r2|none --body-file F [--repo OWNER/REPO] [--dry-run]
    uv run python scripts/uplevel/post_record.py pointer --ruling N --lane x --pr P \\
        --body-file F [--repo OWNER/REPO] [--dry-run]

``record`` posts to #6854 and ``pointer`` to PR ``P``; each appends ONE footer line:

    <!-- uplevel: ruling=<n> lanes=<names|all> packages=<tokens|none> -->
    <!-- uplevel: pointer ruling=<n> lane=<name> -->

``lane_tick.py`` turns that line into a ``for you:`` line for the lane it names. Before it, a record
reached a lane only through ruling 177's map filter, so a ruling the map already carried vanished
from the digest, and a pointer reached it only as a comment count -- which is how frontend missed
``6197231400``. So the format is checked where it is WRITTEN: this tool builds the footer, then
parses its own output with ``lane_tick``'s reader (``RECORD_FOOTER``/``POINTER_FOOTER``) and refuses
to post a body the reader would not read back field for field.

Refused (exit 2, nothing posted): a name outside ``lane_tick.NAMES`` (sandbox names without their
``agent-``/``uplevel-`` prefixes), ``all``/``none`` mixed with names, a package token that is not
``[\\w.]+`` (write ``r197``, not ``[r197]``), a body that already carries an ``<!-- uplevel:``
footer (two footers, and only the last is read), and a record whose first line does not start
``BINDING NOW · ruling N`` -- the shape the snapshot's 48-hour read and ruling 177's filter key on.
``--dry-run`` prints the final body and calls nothing. A failed post exits 1.

The post is ``gh api repos/<repo>/issues/<n>/comments -F body=@-`` with the body on stdin -- no
shell quoting of a multi-line body -- through one injectable ``run(cmd, stdin)``, so the tests need
no network and patch nothing.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from collections.abc import Callable, Sequence
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import coordinator_snapshot as snap  # sibling: the issue number, the repo arg, the error type
import lane_tick as tick  # sibling: the footer grammar this tool writes and the digest reads

Runner = Callable[[Sequence[str], str], str]
TOKEN = re.compile(r"[\w.]+")


class Refused(Exception):
    """An input this tool will not post; the message says which and why."""


def run_with_input(cmd: Sequence[str], stdin: str) -> str:
    """The real runner: ``cmd`` with ``stdin`` piped in; stdout, or CommandError on a non-zero exit."""
    try:
        proc = subprocess.run(
            list(cmd), input=stdin, capture_output=True, text=True, check=False, timeout=120
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise snap.CommandError(f"{' '.join(cmd[:3])}: {exc}") from exc
    if proc.returncode != 0:
        tail = (proc.stderr or proc.stdout).strip().splitlines()
        raise snap.CommandError(f"{' '.join(cmd[:3])} exited {proc.returncode}: {tail[-1] if tail else 'no output'}")  # fmt: skip
    return proc.stdout


def names(text: str, *, allow_all: bool) -> list[str]:
    """Comma-separated footer names, each one a roster name; ``all`` only alone, only if allowed."""
    got = [n.strip() for n in text.split(",")]
    if allow_all and got == ["all"]:
        return got
    unknown = [n for n in got if n not in tick.NAMES]
    if unknown:
        hint = " (or `all` alone)" if allow_all else ""
        raise Refused(f"unknown name(s) {unknown}: use {', '.join(tick.NAMES)}{hint}")
    if len(set(got)) != len(got):
        raise Refused(f"a name is repeated in {text!r}")
    return got


def packages(text: str) -> list[str]:
    got = [t.strip() for t in text.split(",")]
    if got == ["none"]:
        return got
    bad = [t for t in got if not TOKEN.fullmatch(t) or t == "none"]
    if bad:
        raise Refused(f"package token(s) {bad}: write `r197` or `F2.3`, or `none` alone")
    return got


def record_footer(ruling: int, lanes: list[str], pkgs: list[str]) -> str:
    return f"<!-- uplevel: ruling={ruling} lanes={','.join(lanes)} packages={','.join(pkgs)} -->"


def pointer_footer(ruling: int, lane: str) -> str:
    return f"<!-- uplevel: pointer ruling={ruling} lane={lane} -->"


def final_body(body: str, foot: str, expect: dict) -> str:
    """``body`` plus its footer, after the reader has read the footer back as ``expect``."""
    if tick.FOOTER_START.search(body):
        raise Refused("the body already carries an `<!-- uplevel:` footer; the tool writes it")
    out = f"{body.rstrip()}\n\n{foot}"
    if tick.footer(out) != expect:  # the writer and the digest's reader must agree, field for field
        raise Refused(f"lane_tick would read this footer as {tick.footer(out)}, not {expect}")
    return out


def compose(a: argparse.Namespace, body: str) -> tuple[int, str]:
    """``(issue or PR number, final body)`` for the parsed arguments, or ``Refused``."""
    if a.ruling < 1:
        raise Refused(f"--ruling {a.ruling} is not a ruling number")
    if not body.strip():
        raise Refused("the body file is empty")
    if a.kind == "record":
        head = snap.first_line(body)
        # `(?!\d)`: `--ruling 19` must not pass on a body about ruling 197.
        if not re.match(rf"BINDING NOW · ruling {a.ruling}(?!\d)", head):
            raise Refused(f"a record's first line must start `BINDING NOW · ruling {a.ruling}`; it reads {snap.truncate(head, 80)!r}")  # fmt: skip
        lanes, pkgs = names(a.lanes, allow_all=True), packages(a.packages)
        expect = {"kind": "record", "ruling": a.ruling, "lanes": lanes, "packages": pkgs}
        return snap.OWNER_ISSUE, final_body(body, record_footer(a.ruling, lanes, pkgs), expect)
    if a.pr < 1:
        raise Refused(f"--pr {a.pr} is not a PR number")
    if "," in a.lane:
        raise Refused("a pointer names one lane; post one pointer per lane")
    (lane,) = names(a.lane, allow_all=False)
    expect = {"kind": "pointer", "ruling": a.ruling, "lane": lane}
    return a.pr, final_body(body, pointer_footer(a.ruling, lane), expect)


def parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        prog="scripts/uplevel/post_record.py",
        description="post an owner record or pointer with ruling 197's machine footer",
    )
    sub = ap.add_subparsers(dest="kind", required=True)
    for kind in ("record", "pointer"):
        p = sub.add_parser(kind)
        p.add_argument("--ruling", type=int, required=True)
        if kind == "record":
            p.add_argument("--lanes", required=True, help="a,b or all")
            p.add_argument("--packages", required=True, help="r1,r2 or none")
        else:
            p.add_argument("--lane", required=True)
            p.add_argument("--pr", type=int, required=True)
        p.add_argument("--body-file", required=True, type=Path)
        p.add_argument("--repo", default=snap.DEFAULT_REPO, type=snap._repo_arg)
        p.add_argument("--dry-run", action="store_true", help="print the final body; post nothing")
    return ap


def main(argv: Sequence[str] | None = None, run: Runner = run_with_input) -> int:
    a = parser().parse_args(argv)
    try:
        body = a.body_file.read_text(encoding="utf-8")
    except OSError as exc:
        print(f"refused: cannot read --body-file: {exc}", file=sys.stderr)
        return 2
    try:
        number, final = compose(a, body)
    except Refused as exc:
        print(f"refused: {exc}", file=sys.stderr)
        return 2
    if a.dry_run:
        print(final)
        return 0
    cmd = ["gh", "api", f"repos/{a.repo}/issues/{number}/comments", "-F", "body=@-"]
    try:
        out = run(cmd, final)
    except Exception as exc:  # reported, and the exit says nothing was posted
        print(f"ERROR post: {snap.error_text(exc)}", file=sys.stderr)
        return 1
    try:
        answer = json.loads(out or "{}")
    except ValueError:  # posted: gh exited 0. Only the receipt is unreadable, and it says so.
        answer = {"id": "unread"}
    print(f"posted {a.kind} (ruling {a.ruling}) on #{number}: comment {answer.get('id')} {answer.get('html_url', '')}".rstrip())  # fmt: skip
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
