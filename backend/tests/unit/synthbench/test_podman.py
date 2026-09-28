"""synthbench's dedicated podman store: every call carries --root/--runroot off the root fs."""

from __future__ import annotations

import os
import shlex
from pathlib import Path

import pytest
from synthbench.generate import podman


def test_the_default_store_is_under_export_models() -> None:
    assert podman.podman_argv({}, uid=1000) == [
        "podman",
        "--root",
        "/export/models/containers/storage",
        "--runroot",
        "/run/user/1000/synthbench-containers",
    ]


def test_the_store_follows_synthbench_podman_root() -> None:
    env = {"SYNTHBENCH_PODMAN_ROOT": "/x/containers"}
    assert podman.podman_root(env) == Path("/x/containers")
    assert podman.podman_argv(env, uid=7)[1:] == [
        "--root",
        "/x/containers/storage",
        "--runroot",
        "/run/user/7/synthbench-containers",
    ]


def test_the_runroot_uses_the_real_uid_by_default() -> None:
    assert podman.podman_argv({})[-1] == f"/run/user/{os.getuid()}/synthbench-containers"


def test_podman_env_stages_temp_files_in_the_store_and_keeps_the_rest() -> None:
    env = {"PATH": "/bin", "SYNTHBENCH_PODMAN_ROOT": "/x"}
    assert podman.podman_env(env) == {**env, "TMPDIR": "/x/tmp"}
    assert env == {"PATH": "/bin", "SYNTHBENCH_PODMAN_ROOT": "/x"}  # a copy, not a mutation


def test_main_prints_the_shell_prefix(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("SYNTHBENCH_PODMAN_ROOT", "/x")
    assert podman.main() == 0
    assert capsys.readouterr().out == shlex.join(podman.podman_argv()) + "\n"
    assert podman.podman_argv()[2] == "/x/storage"
