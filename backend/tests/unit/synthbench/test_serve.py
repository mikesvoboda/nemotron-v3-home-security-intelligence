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

    def test_stop_logs_a_failed_stop(self, capsys: pytest.CaptureFixture[str]) -> None:
        def run(argv: list[str], **_kw: Any) -> subprocess.CompletedProcess[str]:
            return subprocess.CompletedProcess(argv, 125, "", "Error: container is locked\n")

        serve.stop(run=run)
        err = capsys.readouterr().err
        assert "125" in err and "container is locked" in err

    def test_start_refuses_a_farm_the_image_does_not_load(self, tmp_path: Path) -> None:
        # The image's extra_model_paths.yaml loads from /export/models/comfyui; another
        # HF_HOME would mount a farm that ComfyUI never reads.
        run = FakeRunner()
        cfg = serve.ServeConfig(18188, Path("/data/hf"), tmp_path / "out", tmp_path / "cache")
        with pytest.raises(serve.ServeError, match=r"/data/hf/comfyui.*/export/models/comfyui"):
            serve.start(cfg, run=run)
        assert run.calls == []

    def test_the_baked_farm_root_is_read_from_the_committed_yaml(self) -> None:
        assert serve.baked_farm_root() == Path("/export/models/comfyui")


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
        waited: dict[str, Any] = {}

        def fake_wait(url: str, **kw: Any) -> dict[str, Any]:
            waited.update(kw)
            return {"url": url}

        monkeypatch.setenv("SYNTHBENCH_COMFYUI_PORT", "18188")
        monkeypatch.setenv("SYNTHBENCH_ROOT", "/r")
        monkeypatch.setattr(serve, "build", lambda: calls.append("build"))
        monkeypatch.setattr(serve, "start", lambda cfg: calls.append(f"start {cfg.port}"))
        monkeypatch.setattr(serve, "wait_ready", fake_wait)
        monkeypatch.setattr(serve, "stop", lambda: calls.append("stop"))
        assert [serve.main([c]) for c in ("build", "up", "down")] == [0, 0, 0]
        assert calls == ["build", "start 18188", "stop"]
        assert json.loads(capsys.readouterr().out) == {"url": "http://127.0.0.1:18188"}
        # `up` stops waiting as soon as the container is gone, and points at its log.
        assert waited == {
            "alive": serve.container_alive,
            "log_file": Path("/r/logs/comfyui.log"),
        }

    def test_rejects_an_unknown_command(self) -> None:
        with pytest.raises(SystemExit):
            serve.main(["restart"])


class TestFailuresSurface:
    """A dead renderer or a podman error surfaces at once, with its cause."""

    def test_the_log_file_lives_under_synthbench_root(self) -> None:
        assert serve.ServeConfig.from_env({}).log_file == Path(
            "/export/synthbench/logs/comfyui.log"
        )
        assert serve.ServeConfig.from_env({"SYNTHBENCH_ROOT": "/r"}).log_file == Path(
            "/r/logs/comfyui.log"
        )

    def test_container_output_goes_to_a_file_that_outlives_rm(self, tmp_path: Path) -> None:
        cfg = _cfg(tmp_path)
        args = serve.run_args(cfg)
        assert args[args.index("--log-driver") + 1] == "k8s-file"
        assert args[args.index("--log-opt") + 1] == f"path={tmp_path / 'logs' / 'comfyui.log'}"
        assert cfg.log_file == tmp_path / "logs" / "comfyui.log"
        assert "--rm" in args and args[-1] == serve.IMAGE

    def test_start_creates_the_logs_dir(self, tmp_path: Path) -> None:
        cfg = _cfg(tmp_path)
        serve.start(cfg, run=FakeRunner())
        assert cfg.log_file.parent.is_dir()

    def test_start_reports_podmans_stderr(self, tmp_path: Path) -> None:
        def run(argv: list[str], **_kw: Any) -> subprocess.CompletedProcess[str]:
            raise subprocess.CalledProcessError(125, argv, "", 'Error: name "x" is in use\n')

        with pytest.raises(serve.ServeError, match=r'exit 125.*name "x" is in use') as info:
            serve.start(_cfg(tmp_path), run=run)
        assert isinstance(info.value.__cause__, subprocess.CalledProcessError)

    def test_wait_ready_fails_fast_once_the_container_is_gone(self) -> None:
        polls: list[str] = []

        def get(url: str, **_kw: Any) -> httpx.Response:
            polls.append(url)
            raise httpx.ConnectError("refused")

        now = [0.0]
        alive = iter([True, False])
        with pytest.raises(serve.ServeError, match=r"exited.*/r/logs/comfyui\.log"):
            serve.wait_ready(
                "http://x",
                get=get,
                alive=lambda: next(alive),
                log_file=Path("/r/logs/comfyui.log"),
                sleep=lambda s: now.__setitem__(0, now[0] + s),
                clock=lambda: now[0],
            )
        assert (len(polls), now[0]) == (2, 2.0)  # one poll interval, not the 600 s deadline

    def test_a_timeout_also_points_at_the_log(self) -> None:
        now = [0.0]
        with pytest.raises(TimeoutError, match=r"not ready after 4s.*/r/logs/comfyui\.log"):
            serve.wait_ready(
                "http://x",
                timeout_s=4.0,
                get=lambda _u, **_k: httpx.Response(503),
                alive=lambda: True,
                log_file=Path("/r/logs/comfyui.log"),
                sleep=lambda s: now.__setitem__(0, now[0] + s),
                clock=lambda: now[0],
            )

    @pytest.mark.parametrize(("returncode", "alive"), [(0, True), (1, False), (125, True)])
    def test_container_alive_asks_podman_container_exists(
        self, returncode: int, alive: bool
    ) -> None:
        # Exit 1 means "no such container"; 125 is a podman error, not evidence of an exit.
        calls: list[list[str]] = []

        def run(argv: list[str], **kw: Any) -> subprocess.CompletedProcess[str]:
            calls.append(argv)
            assert kw["check"] is False
            return subprocess.CompletedProcess(argv, returncode, "", "")

        assert serve.container_alive(run=run) is alive
        assert calls == [[*podman_argv(), "container", "exists", serve.CONTAINER]]

    def test_container_alive_is_bounded_and_a_hung_podman_counts_as_alive(self) -> None:
        timeouts: list[float] = []

        def run(argv: list[str], **kw: Any) -> subprocess.CompletedProcess[str]:
            timeouts.append(kw["timeout"])
            raise subprocess.TimeoutExpired(argv, kw["timeout"])

        assert serve.container_alive(run=run) is True
        assert timeouts == [30]


def test_the_renderer_unit_runs_comfyui_in_the_foreground_with_extra_arguments() -> None:
    cfg = serve.ServeConfig.from_env({})
    argv = serve.run_args(cfg, detach=False, extra=("--reserve-vram", "4"))
    assert "-d" not in argv
    assert argv[-3:] == [serve.IMAGE, "--reserve-vram", "4"]
    assert "-d" in serve.run_args(cfg)


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
