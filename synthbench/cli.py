"""`python -m synthbench <command>`: the synthbench command line (agent-driven design §3).

Every command exits 0 when done, 1 on an error (fix the request and retry), and 2 when the
agent must stop and ask the owner. Each command lives in synthbench/commands/.
"""

from __future__ import annotations

import os
from collections.abc import Mapping, Sequence
from types import ModuleType

from synthbench.commands import camera, check, corpus, render, report, sample, triage
from synthbench.commands.common import (
    ASK_OWNER,
    EXIT_ASK,
    EXIT_ERROR,
    EXIT_OK,
    AskOwner,
    Parser,
    RequestError,
    fail,
)

__all__ = ["COMMANDS", "EXIT_ASK", "EXIT_ERROR", "EXIT_OK", "build_parser", "main"]

# In help order. Each module has add_parser(commands) and run(args, env).
COMMANDS: tuple[ModuleType, ...] = (sample, check, render, camera, triage, report, corpus)


def build_parser() -> Parser:
    parser = Parser(
        prog="python -m synthbench",
        description=(
            "Synthetic benchmark generation. Exit codes: 0 done, 1 error (fix the request), "
            "2 stop and ask the owner."
        ),
        allow_abbrev=False,
    )
    commands = parser.add_subparsers(dest="command", required=True, parser_class=Parser)
    for module in COMMANDS:
        module.add_parser(commands)
    return parser


def main(argv: Sequence[str] | None = None, env: Mapping[str, str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    environment: Mapping[str, str] = os.environ if env is None else env
    try:
        code: int = args.run(args, environment)
    except RequestError as error:
        return fail(EXIT_ERROR, str(error))
    except AskOwner as error:
        return fail(EXIT_ASK, f"{error} {ASK_OWNER}")
    return code
