"""`corpus snapshot`: host-side corpus maintenance, run by the owner's timer (design §6)."""

from __future__ import annotations

import argparse
import subprocess
import sys
from collections.abc import Callable, Mapping
from datetime import UTC, datetime

from synthbench.commands.common import EXIT_OK, AskOwner, Parser
from synthbench.host.snapshot import snapshot_and_prune
from synthbench.status import snapshots_file

Runner = Callable[..., subprocess.CompletedProcess[str]]


def add_parser(commands: argparse._SubParsersAction[Parser]) -> None:
    corpus = commands.add_parser(
        "corpus",
        help="host-side corpus maintenance (the owner's timer runs it)",
        allow_abbrev=False,
    )
    actions = corpus.add_subparsers(dest="corpus_command", required=True, parser_class=Parser)
    snapshot = actions.add_parser(
        "snapshot",
        help="snapshot the corpus dataset, then prune by the design's §6 rule",
        allow_abbrev=False,
    )
    snapshot.set_defaults(run=run_snapshot)


def run_snapshot(args: argparse.Namespace, env: Mapping[str, str]) -> int:
    del args  # no options
    return execute_snapshot(env, run=subprocess.run, now=datetime.now(UTC))


def execute_snapshot(env: Mapping[str, str], *, run: Runner, now: datetime) -> int:
    try:
        status = snapshot_and_prune(env, run=run, now=now)
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError, ValueError) as error:
        raise AskOwner(f"the corpus snapshot failed ({type(error).__name__}: {error}).") from error
    if status.hold is not None:
        raise AskOwner(
            f"{status.hold.snapshot} holds the only copy of {status.hold.count} removed or changed "
            f"file(s); pruning stopped with {status.snapshots} snapshots. See "
            f"{snapshots_file(env)} and the operator runbook."
        )
    sys.stdout.write(f"corpus snapshot: {status.snapshots} kept, no hold\n")
    return EXIT_OK
