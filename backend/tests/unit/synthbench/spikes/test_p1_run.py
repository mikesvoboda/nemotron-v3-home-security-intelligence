"""P1 runner: records failures without stopping, writes outputs, samples VRAM."""

from __future__ import annotations

import contextlib
import errno
import inspect
import itertools
import json
import signal
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import httpx
import pytest
from synthbench.generate.comfy import serve
from synthbench.spikes.p1_bakeoff import run
from synthbench.spikes.p1_bakeoff.plan import clip_jobs, image_jobs, pending

# The real settle_vram, bound before the autouse fixture below replaces run.settle_vram.
from synthbench.spikes.p1_bakeoff.run import Settle, settle_vram


class FakeClient:
    """`errors`: what each run() raises in turn (None: it renders); then `fail` decides."""

    def __init__(self, fail: bool = False, errors: list[Exception | None] | None = None) -> None:
        self.fail = fail
        self.graphs: list[dict[str, Any]] = []
        self.calls: list[str] = []
        self.polls: list[float] = []
        self._errors = iter(errors or [])

    def free(self) -> None:
        self.calls.append("free")

    def upload_image(self, path: Path) -> str:
        return path.name

    def run(self, graph: dict[str, Any], *, timeout_s: float, poll_s: float) -> list[bytes]:
        self.calls.append("run")
        self.graphs.append(graph)
        self.polls.append(poll_s)
        error = next(self._errors, None)
        if error is not None:
            raise error
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


def _rows(root: Path) -> list[dict[str, Any]]:
    path = root / "records.jsonl"
    return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []


def _knife_jobs(seeds: set[int]) -> list[Any]:
    return [j for j in image_jobs() if j.case == "knife" and j.seed in seeds]


@pytest.mark.parametrize(
    "lost",
    [httpx.ConnectError("connection refused"), httpx.ReadTimeout("no answer")],
    ids=["refused", "read timeout"],
)
def test_a_lost_renderer_stops_the_run_instead_of_recording_a_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, lost: Exception
) -> None:
    # A dead renderer is not the model's failure: nothing is recorded, a resume retries.
    monkeypatch.setattr(run, "_query_used_mib", lambda: 4096)
    with pytest.raises(type(lost)):
        run.execute(_knife_jobs({11, 22}), FakeClient(errors=[lost]), tmp_path)
    assert _rows(tmp_path) == []


def test_two_timeouts_in_a_row_abort_the_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(run, "_query_used_mib", lambda: 4096)
    client = FakeClient(errors=[TimeoutError("p1 not finished after 600s")] * 3)
    with pytest.raises(run.RunAborted, match=r"2 jobs of flux2-dev in a row timed out"):
        run.execute(_knife_jobs({11, 22, 33}), client, tmp_path)
    assert client.calls == ["free", "run", "run"]  # the third job never started
    assert [r["error"].split(":")[0] for r in _rows(tmp_path)] == ["TimeoutError"] * 2


def test_a_timeout_between_renders_is_a_job_failure_and_the_count_resets(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(run, "_query_used_mib", lambda: 4096)
    timeout = TimeoutError("p1 not finished after 600s")
    client = FakeClient(errors=[timeout, None, timeout, None])
    run.execute(_knife_jobs({11, 22, 33, 44})[:4], client, tmp_path)
    assert [r["ok"] for r in _rows(tmp_path)] == [False, True, False, True]


def test_timeouts_are_counted_per_model_group(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(run, "_query_used_mib", lambda: 4096)
    jobs = _knife_jobs({11, 22})[:4]  # two models, two jobs each
    assert len({j.model for j in jobs}) == 2
    timeout = TimeoutError("p1 not finished after 600s")
    run.execute(jobs, FakeClient(errors=[None, timeout, timeout, None]), tmp_path)
    assert [r["ok"] for r in _rows(tmp_path)] == [True, False, False, True]


def test_vram_is_sampled_every_quarter_second() -> None:
    # A 1 s interval misses sub-second VAE-decode spikes and understates the peak.
    assert inspect.signature(run.VramSampler).parameters["interval_s"].default == 0.25


@pytest.fixture
def no_comfyui(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """main() must decide before it starts anything: starting ComfyUI fails the test.

    main() installs its SIGTERM handler just before it starts ComfyUI; a regression that
    gets that far must not leave the handler behind for the rest of the session.
    """

    def never(*_args: Any, **_kw: Any) -> None:
        raise AssertionError("main() started ComfyUI")

    monkeypatch.setattr(serve, "start", never)
    monkeypatch.setattr(serve, "wait_ready", never)
    sigterm = signal.getsignal(signal.SIGTERM)
    yield
    signal.signal(signal.SIGTERM, sigterm)


@pytest.mark.usefixtures("no_comfyui")
def test_dry_run_prints_the_pending_jobs_per_model_and_kind(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    before = signal.getsignal(signal.SIGTERM)
    assert run.main(["all", "--root", str(tmp_path / "p1"), "--dry-run"]) == 0
    lines = capsys.readouterr().out.splitlines()
    assert lines[:3] == ["flux2-dev t2i 37", "flux2-dev edit 15", "flux2-klein-4b t2i 37"]
    assert "hidream-i1-full t2i 52" in lines and "wan2.2-i2v i2v 8" in lines
    assert lines[-5:] == [
        "ltx-2.5 i2v 8",
        "wan2.2-i2v i2v 8",
        "minimax-h3 i2v 8",
        "minimax-h3-turbo i2v 8",
        "total 344",
    ]
    assert signal.getsignal(signal.SIGTERM) == before


@pytest.mark.usefixtures("no_comfyui")
def test_unknown_models_are_a_usage_error(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    with pytest.raises(SystemExit) as exc:
        run.main(["all", "--root", str(tmp_path), "--models", "flux2-dev,flux2-devv"])
    assert exc.value.code == 2
    assert "flux2-devv" in capsys.readouterr().err


@pytest.mark.usefixtures("no_comfyui")
def test_nothing_pending_returns_before_starting_comfyui(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    for job in clip_jobs():
        (tmp_path / job.output).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / job.output).write_bytes(b"mp4")
        run._append(tmp_path / "records.jsonl", {"output": job.output, "ok": True})
    assert run.main(["clips", "--root", str(tmp_path)]) == 0
    assert "nothing pending" in capsys.readouterr().err


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
