"""`replay --model <name>`: one served VLM over the exported items (P5a design §3).

An owner command. The backend half (`synthbench.run.replay`) is imported inside `run()`: `cli.py`
imports every command at startup, and the generation agent's commands must not load `backend`.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from synthbench.commands.common import EXIT_OK, AskOwner, Parser, RequestError, taxonomy
from synthbench.commands.export import export_dir
from synthbench.contract.store import DEFAULT_SYNTHBENCH_ROOT
from synthbench.run.models import MODELS


def _limit(text: str) -> int:
    try:
        value = int(text)
    except ValueError:
        raise argparse.ArgumentTypeError(f"limit must be a positive integer: {text!r}") from None
    if value < 1:
        raise argparse.ArgumentTypeError(f"limit must be a positive integer, got {value}")
    return value


def add_parser(commands: argparse._SubParsersAction[Parser]) -> None:
    parser = commands.add_parser(
        "replay",
        help="replay one served VLM over the exported items and record the run (owner)",
        allow_abbrev=False,
    )
    parser.add_argument("--model", required=True, choices=sorted(MODELS), help="the served model")
    parser.add_argument("--url", default=None, help="its endpoint (default: per model)")
    parser.add_argument("--limit", type=_limit, default=None, help="replay only the first n items")
    parser.add_argument(
        "--export",
        type=Path,
        default=None,
        help="export directory (default: $SYNTHBENCH_ROOT/exports/<version>/vss)",
    )
    parser.set_defaults(run=run)


def run(args: argparse.Namespace, env: Mapping[str, str]) -> int:
    from synthbench.run.replay import Deps, ImportRefused, ReplayRefused, execute

    tax = taxonomy()
    model = MODELS[args.model]
    url: str = args.url or env.get(model.url_env, model.default_url)
    export: Path = args.export if args.export is not None else export_dir(tax.version, env)
    export = export.resolve()  # the importer stores media paths as joined from the export
    if not any(export.glob("*/*/expected_labels.json")):
        raise RequestError(f"no exported sets under {export}; run `export vss` first")
    root = Path(env.get("SYNTHBENCH_ROOT", str(DEFAULT_SYNTHBENCH_ROOT)))
    try:
        result = execute(
            model,
            url,
            export,
            root / "eval" / tax.version / "eval.sqlite",
            root / "runs" / "replays",
            args.limit,
            Deps(),
        )
    except ReplayRefused as error:
        raise AskOwner(f"{error}.") from error
    except ImportRefused as error:
        raise AskOwner(f"the export did not import cleanly: {error}.") from error
    report = result.report
    s2, s3 = report["s2"], report["s3"]["all"]
    sys.stdout.write(
        f"replay {model.name}: {report['n_items']} items; S2 {s2['fp']}/{s2['n']} false alarms, "
        f"S3 {s3['hit']}/{s3['n']} incidents at level; {_refused(report['s5'])}\n"
        f"  {result.run_dir / 'run.json'}\n"
    )
    return EXIT_OK


def _refused(s5: Mapping[str, Any]) -> str:
    """ "n refused", with the error classes when any: a budget reads apart from plumbing (an
    open breaker fails every later item as VlmUnavailableError)."""
    classes = [f"{name} {count}" for name, count in sorted(s5["by_error_class"].items())]
    if s5.get("unclassifiable"):
        classes.append(f"no cause {s5['unclassifiable']}")
    return f"{s5['refusals']} refused" + (f" ({', '.join(classes)})" if classes else "")
