"""The renderer unit's pre-start check and warm-up (agent-driven design §1, §5.3)."""

from __future__ import annotations

import json
import subprocess
from datetime import timedelta
from pathlib import Path
from typing import Any

import httpx
import pytest
from synthbench.generate.comfy.client import ComfyClient
from synthbench.generate.comfy.serve import ServeConfig
from synthbench.host.renderer import (
    PrecheckError,
    flagship_util,
    gpu_free_gib,
    precheck,
    prepare,
    warmup,
)
from synthbench.status import FlagshipStatus, write_status

from backend.tests.unit.synthbench import helpers as h

ENV = "PATH=/usr/bin\nENGINE_ARGS=--served-model-name claude-flagship --gpu-memory-utilization {util} --kv-cache-memory-bytes 59055800320\n"


class FakeHost:
    """docker inspect, nvidia-smi and `podman container exists`, by argv[0]."""

    def __init__(
        self, *, util: str = "0.76", used_mib: int = 191404, container: bool = False
    ) -> None:
        self.util = util
        self.used_mib = used_mib
        self.container = container

    def __call__(self, argv: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
        if argv[0] == "docker":
            out = ENV.format(util=self.util) if self.util else "PATH=/usr/bin\n"
            return subprocess.CompletedProcess(argv, 0, out, "")
        if argv[0] == "nvidia-smi":
            return subprocess.CompletedProcess(argv, 0, f"256703, {self.used_mib}\n", "")
        return subprocess.CompletedProcess(argv, 0 if self.container else 1, "", "")


def test_flagship_util_reads_engine_args() -> None:
    assert flagship_util(FakeHost(util="0.84")) == 0.84
    with pytest.raises(PrecheckError, match="no --gpu-memory-utilization"):
        flagship_util(FakeHost(util=""))


def test_gpu_free_gib() -> None:
    assert gpu_free_gib(FakeHost(used_mib=191404)) == pytest.approx((256703 - 191404) / 1024)


def test_prepare_wraps_a_farm_mismatch_as_one_problem(tmp_path: Path) -> None:
    cfg = ServeConfig(18188, tmp_path / "not-the-farm", tmp_path / "out", tmp_path / "cache")
    problems = prepare(cfg)
    assert len(problems) == 1
    assert "not-the-farm" in problems[0]


def test_prepare_creates_directories_on_success(tmp_path: Path) -> None:
    cfg = ServeConfig.from_env({"SYNTHBENCH_ROOT": str(tmp_path), "HF_HOME": "/export/models"})
    assert prepare(cfg) == []
    assert cfg.out_dir.is_dir() and cfg.cache_dir.is_dir() and cfg.log_file.parent.is_dir()


def test_precheck_passes_a_host_ready_for_the_renderer(tmp_path: Path) -> None:
    status = tmp_path / "flagship.json"
    write_status(status, FlagshipStatus(time=h.NOW, healthy=True, running=1, waiting=0))
    assert precheck(status, run=FakeHost(), now=lambda: h.NOW) == []


def test_precheck_lists_every_reason_not_to_start(tmp_path: Path) -> None:
    status = tmp_path / "flagship.json"
    write_status(status, FlagshipStatus(time=h.NOW, healthy=True, running=1, waiting=0))
    host = FakeHost(util="0.84", used_mib=200000, container=True)
    problems = precheck(status, run=host, now=lambda: h.NOW + timedelta(seconds=60))
    joined = "\n".join(problems)
    assert "util gate 0.84 is above 0.76" in joined
    assert "GiB free on the GPU" in joined
    assert "already running" in joined
    assert "s old" in joined


def test_warmup_renders_one_1280x720_image(tmp_path: Path) -> None:
    graphs: list[dict[str, Any]] = []

    def comfy(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/prompt":
            graphs.append(json.loads(request.content)["prompt"])
            return httpx.Response(200, json={"prompt_id": "w1", "node_errors": {}})
        if request.url.path == "/history/w1":
            image = {"filename": "w.png", "subfolder": "", "type": "output"}
            entry = {"status": {"status_str": "success"}, "outputs": {"13": {"images": [image]}}}
            return httpx.Response(200, json={"w1": entry})
        return httpx.Response(200, content=h.png())

    cfg = ServeConfig.from_env({"SYNTHBENCH_ROOT": str(tmp_path)})
    client = ComfyClient(cfg.base_url, transport=httpx.MockTransport(comfy))
    warmup(cfg, client=client, ready=lambda: None)
    (graph,) = graphs
    assert (graph["7"]["inputs"]["width"], graph["7"]["inputs"]["height"]) == (1280, 720)
    assert graph["13"]["inputs"]["filename_prefix"] == "synthbench/warmup"
