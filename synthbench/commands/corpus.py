"""`corpus snapshot`, the owner's timer's maintenance (design §6), and `corpus coverage`."""

from __future__ import annotations

import argparse
import subprocess
import sys
import traceback
from collections.abc import Callable, Mapping
from datetime import UTC, datetime

from synthbench.commands import coverage
from synthbench.commands.common import EXIT_OK, AskOwner, Parser
from synthbench.host.snapshot import snapshot_and_prune
from synthbench.status import snapshots_file

Runner = Callable[..., subprocess.CompletedProcess[str]]


def add_parser(commands: argparse._SubParsersAction[Parser]) -> None:
    corpus = commands.add_parser(
        "corpus",
        help="whole-corpus commands: coverage (read-only) and snapshot (the owner's timer)",
        allow_abbrev=False,
    )
    actions = corpus.add_subparsers(dest="corpus_command", required=True, parser_class=Parser)
    snapshot = actions.add_parser(
        "snapshot",
        help="snapshot the corpus dataset, then prune by the design's §6 rule",
        allow_abbrev=False,
    )
    snapshot.set_defaults(run=run_snapshot)
    coverage.add_parser(actions)


def run_snapshot(args: argparse.Namespace, env: Mapping[str, str]) -> int:
    del args  # no options
    return execute_snapshot(env, run=subprocess.run, now=datetime.now(UTC))


def execute_snapshot(env: Mapping[str, str], *, run: Runner, now: datetime) -> int:
    try:
        status = snapshot_and_prune(env, run=run, now=now)
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError, ValueError) as error:
        raise AskOwner(f"the corpus snapshot failed ({type(error).__name__}: {error}).") from error
    except Exception:
        # The timer's journal is the only record of this host run; cli.main prints one line.
        traceback.print_exc(file=sys.stderr)
        raise
    if status.hold is not None:
        raise AskOwner(
            f"{status.hold.snapshot} holds the only copy of {status.hold.count} removed or changed "
            f"file(s); pruning stopped with {status.snapshots} snapshots. See "
            f"{snapshots_file(env)} and the operator runbook."
        )
    sys.stdout.write(f"corpus snapshot: {status.snapshots} kept, no hold\n")
    return EXIT_OK
