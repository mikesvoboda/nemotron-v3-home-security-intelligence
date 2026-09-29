"""docs/synthbench (agent-driven design §8): the command reference matches argparse, and the
agent's handoff names only the agent's commands."""

from __future__ import annotations

import argparse
import re
from pathlib import Path

from synthbench import cli

REPO_ROOT = Path(__file__).resolve().parents[4]
DOCS = REPO_ROOT / "docs" / "synthbench"
AGENT_COMMANDS = {"sample", "check", "render", "camera", "triage", "report", "doctor"}


def _leaves(
    parser: argparse.ArgumentParser, prefix: str = ""
) -> dict[str, argparse.ArgumentParser]:
    """Every runnable command by its full name: "check", "corpus snapshot"."""
    groups = [a for a in parser._actions if isinstance(a, argparse._SubParsersAction)]
    if not groups:
        return {prefix: parser}
    found: dict[str, argparse.ArgumentParser] = {}
    for name, child in groups[0].choices.items():
        found |= _leaves(child, f"{prefix} {name}".strip())
    return found


def _options(parser: argparse.ArgumentParser) -> set[str]:
    return {s for a in parser._actions for s in a.option_strings if s not in {"-h", "--help"}}


def _documented() -> dict[str, set[str]]:
    """`## \\`<command>\\`` sections, and the `--options` named in each one's table rows."""
    sections: dict[str, set[str]] = {}
    current: str | None = None
    for line in (DOCS / "command-reference.md").read_text(encoding="utf-8").splitlines():
        if heading := re.fullmatch(r"## `([a-z ]+)`", line):
            current = heading.group(1)
            sections[current] = set()
        elif line.startswith("## "):
            current = None
        elif current is not None and (row := re.match(r"\| `(--[a-z-]+)", line)):
            sections[current].add(row.group(1))
    return sections


def test_the_reference_documents_every_command_and_option() -> None:
    commands = _leaves(cli.build_parser())
    documented = _documented()
    assert sorted(documented) == sorted(commands)
    for name, parser in commands.items():
        assert documented[name] == _options(parser), name


def test_the_handoff_names_only_the_agents_commands() -> None:
    text = (DOCS / "agent-handoff.md").read_text(encoding="utf-8")
    assert set(re.findall(r"python -m synthbench ([a-z]+)", text)) == AGENT_COMMANDS
