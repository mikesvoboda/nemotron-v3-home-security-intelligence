"""P1 runner: records failures without stopping, writes outputs, samples VRAM."""

from __future__ import annotations

import contextlib
import errno
import itertools
import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from synthbench.spikes.p1_bakeoff import run
from synthbench.spikes.p1_bakeoff.plan import image_jobs, pending

# The real settle_vram, bound before the autouse fixture below replaces run.settle_vram.
from synthbench.spikes.p1_bakeoff.run import Settle, settle_vram


class FakeClient:
    def __init__(self, fail: bool = False) -> None:
        self.fail = fail
        self.graphs: list[dict[str, Any]] = []
        self.calls: list[str] = []
        self.polls: list[float] = []

    def free(self) -> None:
        self.calls.append("free")

    def upload_image(self, path: Path) -> str:
        return path.name

    def run(self, graph: dict[str, Any], *, timeout_s: float, poll_s: float) -> list[bytes]:
        self.calls.append("run")
        self.graphs.append(graph)
        self.polls.append(poll_s)
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
    """execute() waits for /free's asynchronous unload (PF19b), which really sleeps.

    Here it returns at once; settle_vram's own tests below drive it with a fake clock.
    """
    monkeypatch.setattr(run, "settle_vram", lambda before_mib: Settle("no_drop", before_mib))


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


def test_only_the_first_job_of_each_model_group_is_cold(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(run, "_query_used_mib", lambda: 4096)
    jobs = [j for j in image_jobs() if j.case == "knife" and j.seed in {11, 22}]
    run.execute(jobs, FakeClient(), tmp_path)
    rows = [json.loads(line) for line in (tmp_path / "records.jsonl").read_text().splitlines()]
    assert [r["cold"] for r in rows] == [True, False] * len({j.model for j in jobs})


def test_jobs_poll_comfyui_every_100_ms(tmp_path: Path) -> None:
    client = FakeClient()
    run.run_job(image_jobs()[0], client, tmp_path)
    assert client.polls == [0.1]


@pytest.mark.parametrize(
    "error", [OSError(errno.ENOSPC, "No space left on device"), SystemExit(143)]
)
def test_an_interrupted_write_leaves_nothing_at_the_final_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, error: BaseException
) -> None:
    real_write_bytes = Path.write_bytes

    def half_then_fail(self: Path, data: bytes) -> int:
        real_write_bytes(self, data[: len(data) // 2])
        raise error

    monkeypatch.setattr(Path, "write_bytes", half_then_fail)
    job = image_jobs()[0]
    with contextlib.suppress(SystemExit):  # SIGTERM leaves run_job by design
        run.run_job(job, FakeClient(), tmp_path)
    out = tmp_path / job.output
    assert list(out.parent.iterdir()) == []  # no truncated file, no leftover temp file
    assert pending([job], tmp_path) == [job]  # so a resume renders it again


def test_execute_reads_vram_before_free_then_settles_and_records_the_outcome(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    client = FakeClient()

    def read() -> int:
        client.calls.append("read")
        return 30000

    def settle(before_mib: int | None) -> Settle:
        client.calls.append(f"settle from {before_mib}")
        return Settle("timeout", 7900)

    monkeypatch.setattr(run, "_query_used_mib", read)
    monkeypatch.setattr(run, "settle_vram", settle)
    run.execute(image_jobs()[:1], client, tmp_path)
    # the pre-free level, /free, the settle, then the sampler's first sample and the job
    assert client.calls[:5] == ["read", "free", "settle from 30000", "read", "run"]
    group = json.loads((tmp_path / "groups.jsonl").read_text())
    assert group["settle"] == "timeout"
    assert group["baseline_vram_mib"] == 7900


def _reader(values: list[int]) -> Callable[[], int]:
    remaining = iter(values)
    return lambda: next(remaining)


def test_settle_waits_out_the_pre_unload_plateau_until_the_drop_holds(
    capsys: pytest.CaptureFixture[str],
) -> None:
    fake = FakeClock()
    # From 30000: 256 below is not yet a drop; after it, 257 apart is not yet stable, 256 is.
    read = _reader([30000, 29744, 29744, 9000, 8743, 8487])
    result = settle_vram(30000, read=read, sleep=fake.sleep, clock=fake.clock)
    assert result == Settle("dropped", 8487)
    assert fake.sleeps == [0.5] * 6
    assert capsys.readouterr().err == ""


def test_settle_proceeds_after_a_15_second_grace_when_nothing_drops(
    capsys: pytest.CaptureFixture[str],
) -> None:
    fake = FakeClock()
    steady = itertools.cycle([6000, 6100])  # steady, but nothing was freed (first group)
    result = settle_vram(6000, read=lambda: next(steady), sleep=fake.sleep, clock=fake.clock)
    assert result == Settle("no_drop", 6100)
    assert fake.now == 15.0
    assert set(fake.sleeps) == {0.5}
    assert capsys.readouterr().err == ""


def test_settle_times_out_at_60_seconds_with_one_warning_when_the_drop_never_holds(
    capsys: pytest.CaptureFixture[str],
) -> None:
    fake = FakeClock()
    falling = itertools.cycle([8000, 12000])  # below the pre-free level, never stable
    result = settle_vram(30000, read=lambda: next(falling), sleep=fake.sleep, clock=fake.clock)
    assert result == Settle("timeout", 12000)
    assert fake.now == 60.0
    warning = capsys.readouterr().err.splitlines()
    assert len(warning) == 1
    assert "60" in warning[0]


def _no_gpu() -> int:
    raise OSError("nvidia-smi: not found")


@pytest.mark.parametrize(
    ("before_mib", "read", "sleeps"),
    [(None, lambda: 4096, []), (30000, _no_gpu, [0.5])],
    ids=["no pre-free reading", "no reading after free"],
)
def test_settle_does_not_wait_when_vram_cannot_be_read(
    capsys: pytest.CaptureFixture[str],
    before_mib: int | None,
    read: Callable[[], int],
    sleeps: list[float],
) -> None:
    fake = FakeClock()
    result = settle_vram(before_mib, read=read, sleep=fake.sleep, clock=fake.clock)
    assert result == Settle("unreadable", None)
    assert fake.sleeps == sleeps
    assert len(capsys.readouterr().err.splitlines()) == 1


def test_settle_reads_the_same_query_as_the_sampler_by_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = FakeClock()
    monkeypatch.setattr(run, "_query_used_mib", _reader([9000, 8900]))
    assert settle_vram(30000, sleep=fake.sleep, clock=fake.clock) == Settle("dropped", 8900)
