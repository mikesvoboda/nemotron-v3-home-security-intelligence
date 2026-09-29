"""cli.main: dispatch, and the mapping of the two stop kinds to exit codes (design §3)."""

from __future__ import annotations

import argparse
from collections.abc import Callable, Mapping
from pathlib import Path

import pytest
import yaml
from synthbench import cli
from synthbench.commands import common, sample
from synthbench.taxonomy.model import Taxonomy

ARGV = ["sample", "--batch", "pilot-1", "--n", "1"]


def _raising(error: BaseException) -> Callable[[argparse.Namespace, Mapping[str, str]], int]:
    def run(_args: argparse.Namespace, _env: Mapping[str, str]) -> int:
        raise error

    return run


@pytest.mark.parametrize(
    ("error", "code", "text"),
    [
        (common.RequestError("fix the request"), cli.EXIT_ERROR, "synthbench: fix the request"),
        (
            common.AskOwner("the corpus is odd."),
            cli.EXIT_ASK,
            "the corpus is odd. Stop and ask the owner.",
        ),
    ],
)
def test_stop_kinds_map_to_exit_codes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    error: Exception,
    code: int,
    text: str,
) -> None:
    monkeypatch.setattr(sample, "run", _raising(error))
    assert cli.main(ARGV, env={"SYNTHBENCH_ROOT": str(tmp_path)}) == code
    assert text in capsys.readouterr().err


def test_an_unexpected_error_is_a_stop_not_a_traceback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """A bug or a hand-edited file must not exit 1, which tells the agent to fix its request
    (and invites it to edit library code); only an interrupt still propagates."""
    env = {"SYNTHBENCH_ROOT": str(tmp_path)}
    monkeypatch.setattr(sample, "run", _raising(IndexError("tuple index out of range")))
    assert cli.main(ARGV, env=env) == cli.EXIT_ASK
    assert capsys.readouterr().err == (
        "synthbench: unexpected error: IndexError: tuple index out of range. "
        "Stop and ask the owner.\n"
    )
    monkeypatch.setattr(sample, "run", _raising(KeyboardInterrupt()))
    with pytest.raises(KeyboardInterrupt):
        cli.main(ARGV, env=env)


def test_a_taxonomy_that_does_not_load_stops_every_command(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def broken() -> Taxonomy:
        raise yaml.YAMLError("mapping values are not allowed here")

    monkeypatch.setattr(common, "load_taxonomy", broken)
    assert cli.main(ARGV, env={"SYNTHBENCH_ROOT": str(tmp_path)}) == cli.EXIT_ASK
    err = capsys.readouterr().err
    assert "the committed taxonomy does not load (YAMLError" in err
    assert "Stop and ask the owner." in err


def test_a_bad_batch_name_is_a_usage_error(tmp_path: Path) -> None:
    with pytest.raises(SystemExit) as stop:
        cli.main(
            ["sample", "--batch", "Pilot 1", "--n", "1"], env={"SYNTHBENCH_ROOT": str(tmp_path)}
        )
    assert stop.value.code == cli.EXIT_ERROR


def test_every_registered_command_dispatches_to_its_module() -> None:
    parser = cli.build_parser()
    args = parser.parse_args(ARGV)
    assert args.run is sample.run
    assert cli.COMMANDS[0] is sample
