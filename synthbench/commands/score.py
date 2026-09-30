"""`score --replay <id>...`: metrics and the report for one or more replays (P5a design §5).

An owner command. The backend half (`synthbench.score`) is imported inside `run()`: `cli.py`
imports every command at startup, and the generation agent's commands must not load `backend`.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path

from synthbench.commands.audit import audit_log
from synthbench.commands.common import EXIT_OK, AskOwner, Parser, RequestError, taxonomy
from synthbench.contract.store import DEFAULT_SYNTHBENCH_ROOT


def add_parser(commands: argparse._SubParsersAction[Parser]) -> None:
    parser = commands.add_parser(
        "score",
        help="score one or more replays: metrics and the report (owner)",
        allow_abbrev=False,
    )
    parser.add_argument(
        "--replay",
        action="append",
        required=True,
        metavar="ID",
        help="a replay id under runs/replays/; repeat it to compare models",
    )
    parser.set_defaults(run=run)


def run(args: argparse.Namespace, env: Mapping[str, str]) -> int:
    from synthbench.score.report import fmt
    from synthbench.score.scoring import ScoreRefused, ScoreRequestError, execute

    tax = taxonomy()
    root = Path(env.get("SYNTHBENCH_ROOT", str(DEFAULT_SYNTHBENCH_ROOT)))
    try:
        result = execute(
            args.replay,
            root / "runs" / "replays",
            root / "runs" / "scores",
            audit_log(tax.version, env),
            env,
            datetime.now(UTC),
        )
    except ScoreRequestError as error:
        raise RequestError(str(error)) from error
    except ScoreRefused as error:
        raise AskOwner(f"{error}.") from error
    audit = result.metrics["audit"]
    lines = [
        f"score {result.score_id}: audit {audit['answered']}/{audit['sampled']} stills answered, "
        f"{len(audit['generation_errors'])} generation error(s) excluded"
    ]
    for model, metrics in result.metrics["models"].items():
        headline = metrics["all"]
        lines.append(
            f"  {model}: S2 {fmt(headline['s2_cell'])}; S3 {fmt(headline['s3_cell'])}; "
            f"{headline['s5']['refusals']} refused"
        )
    lines.append(f"  {result.out_dir / 'report.md'}")
    sys.stdout.write("\n".join(lines) + "\n")
    return EXIT_OK
