"""`audit`: the owner's 60-still audit page on 127.0.0.1 (P5a design §4).

An owner command. It reads an export, never the corpus, and appends the owner's answers to
`$SYNTHBENCH_ROOT/audits/<version>/audit.jsonl`.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Mapping
from pathlib import Path

from synthbench.audit.page import AuditApp, AuditItem, serve
from synthbench.audit.sample import questions, sample
from synthbench.commands.common import EXIT_OK, Parser, RequestError, now_iso, taxonomy
from synthbench.commands.export import export_dir
from synthbench.contract.store import DEFAULT_SYNTHBENCH_ROOT
from synthbench.export.vss import read_sets

DEFAULT_PORT = 8765


def add_parser(commands: argparse._SubParsersAction[Parser]) -> None:
    parser = commands.add_parser(
        "audit",
        help="serve the owner's audit page for an export on 127.0.0.1 (owner)",
        allow_abbrev=False,
    )
    parser.add_argument(
        "--port", type=int, default=DEFAULT_PORT, help=f"loopback port (default {DEFAULT_PORT})"
    )
    parser.add_argument(
        "--export",
        type=Path,
        default=None,
        help="export directory (default: $SYNTHBENCH_ROOT/exports/<version>/vss)",
    )
    parser.set_defaults(run=run)


def audit_log(version: str, env: Mapping[str, str]) -> Path:
    root = Path(env.get("SYNTHBENCH_ROOT", str(DEFAULT_SYNTHBENCH_ROOT)))
    return root / "audits" / version / "audit.jsonl"


def build_app(version: str, export: Path, env: Mapping[str, str]) -> AuditApp:
    """The page over this export's audit sample and this version's answer log."""
    sets = read_sets(export)
    if not sets:
        raise RequestError(f"no exported sets under {export}; run `export vss` first")
    items = [AuditItem(exported, questions(exported.facts)) for exported in sample(sets)]
    return AuditApp(items, audit_log(version, env), now_iso)


def run(args: argparse.Namespace, env: Mapping[str, str]) -> int:
    tax = taxonomy()
    export: Path = args.export if args.export is not None else export_dir(tax.version, env)
    app = build_app(tax.version, export, env)
    done = sum(1 for item in app.items if app.answered(item))
    port = args.port
    sys.stdout.write(
        f"audit {tax.version}: {len(app.items)} stills, {done} fully answered; answers go to "
        f"{app.log}\n  open http://127.0.0.1:{port}/ (remote: ssh -L {port}:127.0.0.1:{port} "
        "<this host>); Ctrl-C stops.\n"
    )
    sys.stdout.flush()
    try:
        serve(app, port)
    except KeyboardInterrupt:
        pass
    except OSError as error:
        raise RequestError(
            f"cannot listen on 127.0.0.1:{port} ({error}); pick another --port"
        ) from error
    return EXIT_OK
