"""P1 runner: records failures without stopping, writes outputs, samples VRAM."""

from __future__ import annotations

import itertools
import json
from pathlib import Path
from typing import Any

import pytest
from synthbench.spikes.p1_bakeoff import run
from synthbench.spikes.p1_bakeoff.plan import image_jobs

# The real settle_vram, bound before the autouse fixture below replaces run.settle_vram.
from synthbench.spikes.p1_bakeoff.run import settle_vram


class FakeClient:
    def __init__(self, fail: bool = False) -> None:
        self.fail = fail
        self.graphs: list[dict[str, Any]] = []
        self.calls: list[str] = []

    def free(self) -> None:
        self.calls.append("free")

    def upload_image(self, path: Path) -> str:
        return path.name

    def run(self, graph: dict[str, Any], *, timeout_s: float) -> list[bytes]:
        self.calls.append("run")
        self.graphs.append(graph)
        if self.fail:
            raise RuntimeError("CUDA out of memory")
        return [b"\x89PNG-bytes"]


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0
        self.sleeps: list[float] = []

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.now += seconds

    def clock(self) -> float:
        return self.now


@pytest.fixture(autouse=True)
def instant_settle(monkeypatch: pytest.MonkeyPatch) -> None:
    """execute() waits for /free's asynchronous unload (PF19), which really sleeps.

    Here it returns at once; settle_vram's own tests below drive it with a fake clock.
    """
    monkeypatch.setattr(run, "settle_vram", lambda: True)


def test_parse_used_mib_takes_the_max_line() -> None:
    assert run.parse_used_mib("1024\n  2048 \n\n") == 2048


def test_a_successful_job_writes_its_output_and_a_record(tmp_path: Path) -> None:
    job = image_jobs()[0]
    record = run.run_job(job, FakeClient(), tmp_path)
    assert (tmp_path / job.output).read_bytes() == b"\x89PNG-bytes"
    assert record["ok"] is True and record["error"] is None and record["seconds"] >= 0
    rows = [json.loads(line) for line in (tmp_path / "records.jsonl").read_text().splitlines()]
    assert rows == [record]


def test_a_failed_job_is_recorded_and_does_not_raise(tmp_path: Path) -> None:
    job = image_jobs()[0]
    record = run.run_job(job, FakeClient(fail=True), tmp_path)
    assert record["ok"] is False
    assert record["error"].startswith("RuntimeError: CUDA out of memory")
    assert not (tmp_path / job.output).exists()


def test_execute_writes_one_group_row_per_model(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(run, "_query_used_mib", lambda: 4096)
    jobs = [j for j in image_jobs() if j.case == "knife" and j.seed == 11]
    run.execute(jobs, FakeClient(), tmp_path)
    groups = [json.loads(line) for line in (tmp_path / "groups.jsonl").read_text().splitlines()]
    assert [g["model"] for g in groups] == sorted(
        {j.model for j in jobs}, key=[j.model for j in jobs].index
    )
    assert all(g["jobs"] == 1 and g["peak_vram_mib"] == 4096 for g in groups)


def test_execute_frees_the_previous_models_before_each_group(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(run, "_query_used_mib", lambda: 4096)
    jobs = [j for j in image_jobs() if j.case == "knife" and j.seed in {11, 22}]
    client = FakeClient()
    run.execute(jobs, client, tmp_path)
    assert client.calls == ["free", "run", "run"] * len({j.model for j in jobs})


def test_a_group_without_a_vram_sample_records_null(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def no_gpu() -> int:
        raise OSError("nvidia-smi: not found")

    monkeypatch.setattr(run, "_query_used_mib", no_gpu)
    run.execute(image_jobs()[:1], FakeClient(), tmp_path)
    groups = [json.loads(line) for line in (tmp_path / "groups.jsonl").read_text().splitlines()]
    assert [g["peak_vram_mib"] for g in groups] == [None]


def test_execute_settles_vram_after_free_and_before_the_first_sample(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    client = FakeClient()

    def sample() -> int:
        client.calls.append("sample")
        return 4096

    monkeypatch.setattr(run, "settle_vram", lambda: client.calls.append("settle"))
    monkeypatch.setattr(run, "_query_used_mib", sample)
    run.execute(image_jobs()[:1], client, tmp_path)
    assert client.calls[:4] == ["free", "settle", "sample", "run"]


def test_settle_polls_every_half_second_until_two_readings_are_within_256_mib(
    capsys: pytest.CaptureFixture[str],
) -> None:
    fake = FakeClock()
    readings = iter([30000, 6000, 6257, 6001])  # unloading, 257 MiB apart, then 256: settled
    assert settle_vram(read=lambda: next(readings), sleep=fake.sleep, clock=fake.clock) is True
    assert fake.sleeps == [0.5, 0.5, 0.5]
    assert capsys.readouterr().err == ""


def test_settle_gives_up_after_30_seconds_with_one_warning(
    capsys: pytest.CaptureFixture[str],
) -> None:
    fake = FakeClock()
    readings = itertools.cycle([6000, 20000])  # never settles
    assert settle_vram(read=lambda: next(readings), sleep=fake.sleep, clock=fake.clock) is False
    assert fake.now == 30.0
    assert set(fake.sleeps) == {0.5}
    warning = capsys.readouterr().err.splitlines()
    assert len(warning) == 1
    assert "30" in warning[0]


def test_settle_does_not_wait_when_vram_cannot_be_read(
    capsys: pytest.CaptureFixture[str],
) -> None:
    fake = FakeClock()

    def no_gpu() -> int:
        raise OSError("nvidia-smi: not found")

    assert settle_vram(read=no_gpu, sleep=fake.sleep, clock=fake.clock) is False
    assert fake.sleeps == []
    assert len(capsys.readouterr().err.splitlines()) == 1


def test_settle_reads_the_same_query_as_the_sampler_by_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = FakeClock()
    readings = iter([9000, 4096, 4096])
    monkeypatch.setattr(run, "_query_used_mib", lambda: next(readings))
    assert settle_vram(sleep=fake.sleep, clock=fake.clock) is True
    assert fake.sleeps == [0.5, 0.5]
