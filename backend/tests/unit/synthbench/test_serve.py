"""The pinned ComfyUI renderer runs loopback-only, with models read-only at the same path."""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path
from typing import Any

import httpx
import pytest
from synthbench.generate.comfy import serve
from synthbench.generate.podman import podman_argv


def _cfg(tmp_path: Path) -> serve.ServeConfig:
    return serve.ServeConfig(
        port=18188,
        models_root=Path("/export/models"),
        out_dir=tmp_path / "out",
        cache_dir=tmp_path / "cache",
    )


class FakeRunner:
    """Stands in for subprocess.run and records every argv and env."""

    def __init__(self) -> None:
        self.calls: list[list[str]] = []
        self.envs: list[dict[str, str] | None] = []

    def __call__(
        self, argv: list[str], *, env: dict[str, str] | None = None, **_kw: Any
    ) -> subprocess.CompletedProcess[str]:
        self.calls.append(argv)
        self.envs.append(env)
        return subprocess.CompletedProcess(argv, 0, "", "")


class TestConfig:
    def test_defaults(self) -> None:
        cfg = serve.ServeConfig.from_env({})
        assert cfg.port == 8188
        assert cfg.models_root == Path("/export/models")
        assert cfg.out_dir == Path("/export/synthbench/comfy-out")
        assert cfg.cache_dir == Path("/export/synthbench/cache")
        assert cfg.base_url == "http://127.0.0.1:8188"

    def test_env_overrides(self) -> None:
        cfg = serve.ServeConfig.from_env(
            {"SYNTHBENCH_COMFYUI_PORT": "9999", "HF_HOME": "/m", "SYNTHBENCH_ROOT": "/r"}
        )
        assert (cfg.port, cfg.models_root, cfg.out_dir) == (9999, Path("/m"), Path("/r/comfy-out"))


class TestRunArgs:
    def test_binds_loopback_only(self, tmp_path: Path) -> None:
        args = serve.run_args(_cfg(tmp_path))
        assert args[args.index("-p") + 1] == "127.0.0.1:18188:8188"

    def test_mounts_models_read_only_at_the_same_path(self, tmp_path: Path) -> None:
        assert "/export/models:/export/models:ro" in serve.run_args(_cfg(tmp_path))

    def test_gpu_label_device_and_pinned_image(self, tmp_path: Path) -> None:
        args = serve.run_args(_cfg(tmp_path))
        assert args[: len(podman_argv()) + 1] == [*podman_argv(), "run"]
        assert args[args.index("--device") + 1] == "nvidia.com/gpu=all"
        assert args[args.index("--label") + 1] == serve.GPU_LABEL
        assert args[-1] == serve.IMAGE == "localhost/synthbench-comfyui:v0.37.0"


class TestStartStop:
    def test_start_creates_dirs_and_runs(self, tmp_path: Path) -> None:
        run = FakeRunner()
        cfg = _cfg(tmp_path)
        serve.start(cfg, run=run)
        assert cfg.out_dir.is_dir() and cfg.cache_dir.is_dir()
        assert run.calls == [serve.run_args(cfg)]

    def test_stop_ignores_a_missing_container(self) -> None:
        run = FakeRunner()
        serve.stop(run=run)
        assert run.calls == [[*podman_argv(), "stop", "--ignore", "--time", "30", serve.CONTAINER]]


class TestBuild:
    def test_builds_into_the_synthbench_store_with_its_tmpdir(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        store = tmp_path / "containers"
        monkeypatch.setenv("SYNTHBENCH_PODMAN_ROOT", str(store))
        run = FakeRunner()
        serve.build(run=run)
        assert (store / "storage").is_dir() and (store / "tmp").is_dir()
        assert run.calls == [serve.build_args()]
        assert serve.build_args()[:3] == ["podman", "--root", str(store / "storage")]
        assert serve.build_args()[3:6] == ["--runroot", podman_argv()[4], "build"]
        (env,) = run.envs
        assert env is not None and env["TMPDIR"] == str(store / "tmp")


class TestWaitReady:
    def test_polls_until_system_stats_answers(self) -> None:
        answers = iter(
            [
                httpx.ConnectError("refused"),
                httpx.Response(503),
                httpx.Response(200, json={"ok": 1}),
            ]
        )

        def get(_url: str, **_kw: Any) -> httpx.Response:
            answer = next(answers)
            if isinstance(answer, Exception):
                raise answer
            return answer

        now = [0.0]
        stats = serve.wait_ready(
            "http://x",
            get=get,
            sleep=lambda s: now.__setitem__(0, now[0] + s),
            clock=lambda: now[0],
        )
        assert stats == {"ok": 1}

    def test_times_out(self) -> None:
        now = [0.0]
        with pytest.raises(TimeoutError, match="not ready"):
            serve.wait_ready(
                "http://x",
                timeout_s=4.0,
                poll_s=2.0,
                get=lambda _u, **_k: httpx.Response(503),
                sleep=lambda s: now.__setitem__(0, now[0] + s),
                clock=lambda: now[0],
            )


class TestMain:
    def test_dispatches_build_up_and_down(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        calls: list[str] = []
        monkeypatch.setenv("SYNTHBENCH_COMFYUI_PORT", "18188")
        monkeypatch.setattr(serve, "build", lambda: calls.append("build"))
        monkeypatch.setattr(serve, "start", lambda cfg: calls.append(f"start {cfg.port}"))
        monkeypatch.setattr(serve, "wait_ready", lambda url: {"url": url})
        monkeypatch.setattr(serve, "stop", lambda: calls.append("stop"))
        assert [serve.main([c]) for c in ("build", "up", "down")] == [0, 0, 0]
        assert calls == ["build", "start 18188", "stop"]
        assert json.loads(capsys.readouterr().out) == {"url": "http://127.0.0.1:18188"}

    def test_rejects_an_unknown_command(self) -> None:
        with pytest.raises(SystemExit):
            serve.main(["restart"])


def _containerfile() -> str:
    return (serve.CONTAINERFILE_DIR / "Containerfile").read_text()


class TestContainerfile:
    """pip only adds packages around the base image's CUDA torch stack, never replaces it."""

    def test_every_pip_install_is_constrained_or_dependency_free(self) -> None:
        installs = re.findall(r"pip install [^\n&]*", _containerfile())
        assert len(installs) >= 4
        for cmd in installs:
            assert "-c /tmp/constraints.txt" in cmd or "--no-deps" in cmd, cmd

    def test_torchaudio_is_compiled_against_the_base_torch_and_then_pinned(self) -> None:
        # v0.37.0 imports torchaudio at module level (comfy.sd, gemma4, the LTX nodes); the base
        # has none and PyPI's aarch64 wheel is a CUDA 13.0 build that refuses the base torch.
        text = _containerfile()
        assert "ARG TORCHAUDIO_REF=v2.11.0" in text
        assert "https://github.com/pytorch/audio.git /tmp/audio" in text
        assert "--no-build-isolation --no-deps /tmp/audio" in text
        assert text.index("pytorch/audio.git") < text.index("> /tmp/constraints.txt")
        assert "sed -i" not in text
