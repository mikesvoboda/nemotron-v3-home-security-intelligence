"""`clip <step> --round <r>`: the agent's clip loop (clips design §3).

sample -> (the agent writes motions.jsonl) -> check -> render -> (the agent looks at each
strip, writes triage.jsonl) -> triage -> report. Each step lives in its own clip_<step> module.
"""

from __future__ import annotations

import argparse

from synthbench.commands import clip_check, clip_render, clip_sample
from synthbench.commands.common import Parser


def add_parser(commands: argparse._SubParsersAction[Parser]) -> None:
    clip = commands.add_parser(
        "clip",
        help="the clip loop: animate ready stills with MiniMax-H3 turbo (the agent's)",
        allow_abbrev=False,
    )
    actions = clip.add_subparsers(dest="clip_command", required=True, parser_class=Parser)
    clip_sample.add_parser(actions)
    clip_check.add_parser(actions)
    clip_render.add_parser(actions)
