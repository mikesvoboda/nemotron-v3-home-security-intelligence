"""`render` (agent-driven design §3 step 4, §5.2) against a fake ComfyUI (httpx.MockTransport)."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from datetime import timedelta
from pathlib import Path
from typing import Any

import httpx
import pytest
from synthbench import cli
from synthbench.commands import render
from synthbench.commands.common import AskOwner, RequestError
from synthbench.contract.provenance import (
    Attempt,
    OutputFile,
    Provenance,
    RenderFailure,
    Triage,
    attempt_seed,
    render_name,
)
from synthbench.contract.spec import Spec
from synthbench.generate.comfy import graphs
from synthbench.generate.render import (
    RendererUnreachable,
    check_png,
    comfy_url,
    model_hashes,
)
from synthbench.prompt import rules
from synthbench.status import flagship_file

from backend.tests.unit.synthbench import helpers as h

Handler = Callable[[httpx.Request], httpx.Response]
OOM = [
    "execution_error",
    {
        "node_id": "11",
        "node_type": "SamplerCustomAdvanced",
        "exception_type": "torch.OutOfMemoryError",
        "exception_message": "out of memory",
    },
]


class FakeComfy:
    """ComfyUI's /system_stats, /prompt, /history and /view; one image per queued prompt.

    Each queued prompt moves the fake clock by `seconds`, like a render. Prompt numbers in
    `fail` end in an out-of-memory error.
    """

    def __init__(
        self, clock: h.FakeClock, *, seconds: float = 8.0, fail: frozenset[int] = frozenset()
    ) -> None:
        self.clock = clock
        self.seconds = seconds
        self.fail = fail
        self.image = h.png()
        self.graphs: list[dict[str, Any]] = []
        self.history: dict[str, Any] = {}
        self.freed = 0
        self.free_gib = 200.0

    def __call__(self, request: httpx.Request) -> httpx.Response:  # noqa: PLR0911
        path = request.url.path
        if path == "/system_stats":
            devices = [{"vram_free": int(self.free_gib * 2**30)}]
            return httpx.Response(200, json={"system": {}, "devices": devices})
        if path == "/history":
            return httpx.Response(200, json=self.history)
        if path == "/free":
            self.freed += 1
            return httpx.Response(200, json={})
        if path == "/prompt":
            self.graphs.append(json.loads(request.content)["prompt"])
            self.clock.now += self.seconds
            return httpx.Response(
                200, json={"prompt_id": f"p{len(self.graphs)}", "node_errors": {}}
            )
        if path.startswith("/history/p"):
            number = int(path.rsplit("p", 1)[1])
            if number in self.fail:
                entry = {"status": {"status_str": "error", "messages": [OOM]}, "outputs": {}}
            else:
                image = {"filename": "x.png", "subfolder": "", "type": "output"}
                entry = {
                    "status": {"status_str": "success"},
                    "outputs": {"13": {"images": [image]}},
                }
            return httpx.Response(200, json={f"p{number}": entry})
        if path == "/view":
            return httpx.Response(200, content=self.image)
        return httpx.Response(404)


def _deps(
    clock: h.FakeClock, handler: Handler, *, on_sleep: Callable[[], None] | None = None
) -> render.Deps:
    transport = httpx.MockTransport(handler)

    def get(url: str, timeout: float) -> httpx.Response:
        with httpx.Client(transport=transport) as client:
            return client.get(url, timeout=timeout)

    def sleep(seconds: float) -> None:
        clock.sleep(seconds)
        if on_sleep is not None:
            on_sleep()

    return render.Deps(transport=transport, get=get, sleep=sleep, clock=clock, now=lambda: h.NOW)


def _render(root: Path, deps: render.Deps, budget: float = 480) -> int:
    return render.execute("pilot-1", budget, h.env(root), deps)


def _attempt(root: Path, spec: Spec) -> Any:
    store = h.store(root)
    return store.read(store.provenance_file(spec.event_id), Provenance).attempts[-1]


def _ready(root: Path, n: int) -> tuple[list[Spec], h.FakeClock]:
    specs = h.frozen_batch(root, n=n)
    h.flagship(root)
    return specs, h.FakeClock()


def test_render_stores_each_pending_attempt(tmp_path: Path) -> None:
    specs, clock = _ready(tmp_path, 3)
    comfy = FakeComfy(clock)
    assert _render(tmp_path, _deps(clock, comfy)) == cli.EXIT_OK
    store = h.store(tmp_path)
    for spec, graph in zip(specs, comfy.graphs, strict=True):
        attempt = _attempt(tmp_path, spec)
        name = render_name(1, attempt_seed(spec.event_id, 1))
        assert attempt.render == OutputFile(
            path=name, sha256=hashlib.sha256(comfy.image).hexdigest()
        )
        assert attempt.render_seconds == 8.0
        assert attempt.models == model_hashes()
        assert (store.event_dir(spec.event_id) / name).read_bytes() == comfy.image
        assert graph["4"]["inputs"]["text"] == rules.render_text(spec)
        assert graph["10"]["inputs"]["noise_seed"] == attempt.seed
        assert (graph["7"]["inputs"]["width"], graph["7"]["inputs"]["height"]) == (1280, 720)
        prefix = f"synthbench/{h.VERSION}/{spec.event_id}/a1-s{attempt.seed}"
        assert graph["13"]["inputs"]["filename_prefix"] == prefix
    assert {row.status for row in store.latest_index().values()} == {"rendered"}


def test_a_second_run_renders_nothing(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    _specs, clock = _ready(tmp_path, 2)
    assert _render(tmp_path, _deps(clock, FakeComfy(clock))) == cli.EXIT_OK
    again = FakeComfy(clock)
    assert _render(tmp_path, _deps(clock, again)) == cli.EXIT_OK
    assert again.graphs == []
    assert "0 still to render. Next: camera --batch pilot-1" in capsys.readouterr().out


def test_render_waits_while_the_flagship_has_requests_waiting(tmp_path: Path) -> None:
    _specs, clock = _ready(tmp_path, 1)
    h.flagship(tmp_path, waiting=2)
    comfy = FakeComfy(clock)
    deps = _deps(clock, comfy, on_sleep=lambda: h.flagship(tmp_path, waiting=0))
    assert _render(tmp_path, deps) == cli.EXIT_OK
    assert clock.sleeps == [5.0]
    assert len(comfy.graphs) == 1


def test_render_yields_before_every_image_not_only_the_first(tmp_path: Path) -> None:
    """§5.2: the yield check runs before EACH image. A flagship that goes busy only after
    image 1 must still stall image 2 - a yield hoisted above the per-image loop would miss it."""
    specs, clock = _ready(tmp_path, 2)
    comfy = FakeComfy(clock)
    order: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/prompt":
            order.append(f"prompt-{len(comfy.graphs) + 1}")
        response = comfy(request)
        if request.url.path == "/prompt" and len(comfy.graphs) == 1:
            h.flagship(tmp_path, waiting=3)  # busy only once image 1's job is queued
        return response

    def on_sleep() -> None:
        order.append("sleep")
        h.flagship(tmp_path, waiting=0)

    deps = _deps(clock, handler, on_sleep=on_sleep)
    assert _render(tmp_path, deps) == cli.EXIT_OK
    assert order == ["prompt-1", "sleep", "prompt-2"]
    assert len(comfy.graphs) == 2
    assert _attempt(tmp_path, specs[0]).render is not None
    assert _attempt(tmp_path, specs[1]).render is not None


def test_an_unhealthy_flagship_holds_every_image_until_the_budget_ends(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _specs, clock = _ready(tmp_path, 1)
    h.flagship(tmp_path, healthy=False)
    comfy = FakeComfy(clock)
    assert _render(tmp_path, _deps(clock, comfy), budget=30) == cli.EXIT_OK
    assert comfy.graphs == []
    assert clock.sleeps == [5.0] * 6
    assert "1 still to render" in capsys.readouterr().out


@pytest.mark.parametrize("state", ["stale", "missing"])
def test_an_unknown_flagship_stops_render(tmp_path: Path, state: str) -> None:
    _specs, clock = _ready(tmp_path, 1)
    if state == "stale":
        h.flagship(tmp_path, time=h.NOW - timedelta(seconds=31))
    else:
        flagship_file(h.env(tmp_path)).unlink()
    comfy = FakeComfy(clock)
    with pytest.raises(AskOwner, match="guard"):
        _render(tmp_path, _deps(clock, comfy))
    assert comfy.graphs == []


def test_render_starts_no_image_after_its_budget(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _specs, clock = _ready(tmp_path, 3)
    comfy = FakeComfy(clock, seconds=200.0)
    assert _render(tmp_path, _deps(clock, comfy), budget=300) == cli.EXIT_OK
    assert len(comfy.graphs) == 2
    assert "1 still to render" in capsys.readouterr().out
    rest = FakeComfy(clock)
    assert _render(tmp_path, _deps(clock, rest), budget=300) == cli.EXIT_OK
    assert len(rest.graphs) == 1


def test_a_budget_over_the_max_exits_1(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """render.MAX_BUDGET_S (480, the default) plus RENDER_TIMEOUT_S (90) is 570 s, under the Bash
    tool's 600 s per-call cap (P3-R10): a longer budget could let a hung image outlive the call."""
    assert render.MAX_BUDGET_S == render.DEFAULT_BUDGET_S == 480
    try:  # argparse raises SystemExit for usage errors; the command returns its code
        code = cli.main(
            ["render", "--batch", "pilot-1", "--budget-seconds", "481"], env=h.env(tmp_path)
        )
    except SystemExit as stop:
        code = int(stop.code or 0)
    assert code == cli.EXIT_ERROR
    assert f"30..{render.MAX_BUDGET_S} seconds, got 481" in capsys.readouterr().err


def test_a_failed_job_is_recorded_and_retried_next_run(tmp_path: Path) -> None:
    specs, clock = _ready(tmp_path, 2)
    assert _render(tmp_path, _deps(clock, FakeComfy(clock, fail=frozenset({1})))) == cli.EXIT_OK
    first = _attempt(tmp_path, specs[0])
    assert first.render is None
    assert "OutOfMemoryError" in first.render_failures[0].error
    assert _attempt(tmp_path, specs[1]).render is not None
    assert _render(tmp_path, _deps(clock, FakeComfy(clock))) == cli.EXIT_OK
    assert _attempt(tmp_path, specs[0]).render is not None


def _failed_rows(root: Path, spec: Spec) -> int:
    lines = h.store(root).index_file.read_text(encoding="utf-8").splitlines()
    return sum(spec.event_id in line and '"failed"' in line for line in lines)


def _fail_three_jobs(root: Path) -> tuple[Spec, h.FakeClock]:
    """A 1-event batch whose attempt 1 fails its job on three runs: the third run stops."""
    (spec,), clock = _ready(root, 1)
    for _ in range(2):
        assert _render(root, _deps(clock, FakeComfy(clock, fail=frozenset({1})))) == 0
    with pytest.raises(AskOwner, match="failed to render 3 times"):
        _render(root, _deps(clock, FakeComfy(clock, fail=frozenset({1}))))
    return spec, clock


def test_a_third_failed_job_fails_the_event_and_stops_once(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """I2: the third failed job appends a `failed` index row the moment it happens, render still
    renders the rest of the batch, and only then exits 2."""
    specs, clock = _ready(tmp_path, 2)
    for _ in range(2):  # both events fail twice
        both = FakeComfy(clock, fail=frozenset({1, 2}))
        assert _render(tmp_path, _deps(clock, both)) == cli.EXIT_OK
    comfy = FakeComfy(clock, fail=frozenset({1}))  # specs[0] fails a third time
    stuck = rf"failed to render 3 times: {specs[0].event_id}\. This event is now failed"
    with pytest.raises(AskOwner, match=stuck) as stop:
        _render(tmp_path, _deps(clock, comfy))
    assert "sample replacements" in str(stop.value)
    assert len(comfy.graphs) == 2
    assert _attempt(tmp_path, specs[1]).render is not None
    assert h.store(tmp_path).latest_index()[specs[0].event_id].status == "failed"
    assert _failed_rows(tmp_path, specs[0]) == 1
    assert "0 still to render" in capsys.readouterr().out


def test_a_later_stop_keeps_the_failed_events_in_its_message(tmp_path: Path) -> None:
    """An event failed this run must still be named when another stop ends the run: here the
    renderer stops answering on the next event, after specs[0] failed its third job."""
    specs, clock = _ready(tmp_path, 2)
    for _ in range(2):  # both events fail twice
        both = FakeComfy(clock, fail=frozenset({1, 2}))
        assert _render(tmp_path, _deps(clock, both)) == cli.EXIT_OK
    comfy = FakeComfy(clock, fail=frozenset({1}))  # specs[0] fails a third time

    def then_refused(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/prompt" and len(comfy.graphs) == 1:
            raise httpx.ConnectError("connection refused", request=request)
        return comfy(request)

    with pytest.raises(AskOwner) as stop:
        _render(tmp_path, _deps(clock, then_refused))
    assert "stopped answering" in str(stop.value)
    assert f"failed to render 3 times: {specs[0].event_id}" in str(stop.value)
    assert h.store(tmp_path).latest_index()[specs[0].event_id].status == "failed"


def test_a_failed_event_is_skipped_by_the_next_run(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    spec, clock = _fail_three_jobs(tmp_path)
    capsys.readouterr()
    again = FakeComfy(clock)
    assert _render(tmp_path, _deps(clock, again)) == cli.EXIT_OK
    assert again.graphs == []
    assert "0 still to render" in capsys.readouterr().out
    assert _failed_rows(tmp_path, spec) == 1
    assert _attempt(tmp_path, spec).render is None


def test_the_report_shows_a_render_failed_event_as_failed(tmp_path: Path) -> None:
    _fail_three_jobs(tmp_path)
    assert h.run(tmp_path, "report", "--batch", "pilot-1") == cli.EXIT_OK
    text = (h.store(tmp_path).batch_dir("pilot-1") / "report.md").read_text(encoding="utf-8")
    assert "| failed | 1 |" in text
    assert "| awaiting render | 0 |" in text


def test_an_attempt_already_over_the_limit_is_marked_failed_at_the_start(tmp_path: Path) -> None:
    """An attempt with three failed jobs but no `failed` row (a crash between the provenance
    write and the index append) is marked failed when the next run starts; the rest renders."""
    specs, clock = _ready(tmp_path, 2)
    store = h.store(tmp_path)
    path = store.provenance_file(specs[0].event_id)
    prov = store.read(path, Provenance)
    job = RenderFailure(time="2026-09-28T00:00:00+00:00", error="ComfyError: out of memory")
    store.replace_json(
        path, prov.updated(attempts=(prov.attempts[0].updated(render_failures=(job,) * 3),))
    )
    comfy = FakeComfy(clock)
    with pytest.raises(AskOwner, match=rf"{specs[0].event_id}\. This event is now failed"):
        _render(tmp_path, _deps(clock, comfy))
    assert len(comfy.graphs) == 1
    assert _attempt(tmp_path, specs[1]).render is not None
    assert store.latest_index()[specs[0].event_id].status == "failed"
    assert _failed_rows(tmp_path, specs[0]) == 1


def test_a_renderer_that_stops_answering_stops_render(tmp_path: Path) -> None:
    specs, clock = _ready(tmp_path, 2)
    comfy = FakeComfy(clock)

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/prompt":
            raise httpx.ConnectError("connection refused", request=request)
        return comfy(request)

    with pytest.raises(AskOwner, match="stopped answering"):
        _render(tmp_path, _deps(clock, handler))
    attempt = _attempt(tmp_path, specs[0])
    assert attempt.render is None
    assert len(attempt.render_failures) == 1


def test_an_unreachable_renderer_is_recorded_but_does_not_count(tmp_path: Path) -> None:
    """I2: a renderer that stops answering already stops the run for the owner (the guard may
    have stopped it), so its failure is `unreachable` and does not count toward the three."""
    (spec,), clock = _ready(tmp_path, 1)
    for _ in range(2):
        assert _render(tmp_path, _deps(clock, FakeComfy(clock, fail=frozenset({1})))) == 0
    comfy = FakeComfy(clock)

    def refused(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/prompt":
            raise httpx.ConnectError("connection refused", request=request)
        return comfy(request)

    with pytest.raises(AskOwner, match="stopped answering"):
        _render(tmp_path, _deps(clock, refused))
    kinds = [failure.kind for failure in _attempt(tmp_path, spec).render_failures]
    assert kinds == ["job", "job", "unreachable"]
    assert _render(tmp_path, _deps(clock, FakeComfy(clock))) == cli.EXIT_OK
    assert _attempt(tmp_path, spec).render is not None


def test_no_renderer_is_a_stop(tmp_path: Path) -> None:
    _specs, clock = _ready(tmp_path, 1)

    def down(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    with pytest.raises(AskOwner, match="renderer is down"):
        _render(tmp_path, _deps(clock, down))


def test_render_needs_frozen_prompts(tmp_path: Path) -> None:
    h.sample(tmp_path, n=2)
    h.flagship(tmp_path)
    clock = h.FakeClock()
    with pytest.raises(RequestError, match="run check"):
        _render(tmp_path, _deps(clock, FakeComfy(clock)))


def test_an_unrecorded_render_is_adopted(tmp_path: Path) -> None:
    (spec,), clock = _ready(tmp_path, 1)
    image = h.png(color=(1, 2, 3))
    name = render_name(1, attempt_seed(spec.event_id, 1))
    h.store(tmp_path).write_new_bytes(h.store(tmp_path).event_dir(spec.event_id) / name, image)
    comfy = FakeComfy(clock)
    assert _render(tmp_path, _deps(clock, comfy)) == cli.EXIT_OK
    assert comfy.graphs == []
    attempt = _attempt(tmp_path, spec)
    assert attempt.render.sha256 == hashlib.sha256(image).hexdigest()
    assert attempt.render_seconds is None


def test_a_reroll_renders_a_new_file_and_leaves_the_old_one(tmp_path: Path) -> None:
    (spec,), clock = _ready(tmp_path, 1)
    assert _render(tmp_path, _deps(clock, FakeComfy(clock))) == cli.EXIT_OK
    store = h.store(tmp_path)
    old = store.event_dir(spec.event_id) / render_name(1, attempt_seed(spec.event_id, 1))
    before = old.read_bytes()
    h.record_output(tmp_path, spec, still=b"jpeg")
    path = store.provenance_file(spec.event_id)
    prov = store.read(path, Provenance)
    first = prov.attempts[0].updated(triage=Triage(verdict="reroll", reason="blank"))
    second = Attempt(k=2, seed=attempt_seed(spec.event_id, 2), prompt_sha256=first.prompt_sha256)
    store.replace_json(path, prov.updated(attempts=(first, second)))
    comfy = FakeComfy(clock)
    comfy.image = h.png(color=(9, 9, 9))
    assert _render(tmp_path, _deps(clock, comfy)) == cli.EXIT_OK
    assert old.read_bytes() == before
    new = store.event_dir(spec.event_id) / render_name(2, attempt_seed(spec.event_id, 2))
    assert new.read_bytes() == comfy.image
    assert comfy.graphs[0]["10"]["inputs"]["noise_seed"] == attempt_seed(spec.event_id, 2)


def test_comfy_url_prefers_the_environment_then_the_first_default_that_answers() -> None:
    seen: list[str] = []

    def get(url: str, timeout: float) -> httpx.Response:
        seen.append(url)
        if url.startswith("http://127.0.0.1"):
            raise httpx.ConnectError("connection refused")
        return httpx.Response(200)

    assert comfy_url({}, get) == "http://host.docker.internal:8188"
    assert seen == [
        "http://127.0.0.1:8188/system_stats",
        "http://host.docker.internal:8188/system_stats",
    ]
    configured = {"SYNTHBENCH_COMFYUI_URL": "http://renderer:9000"}
    assert comfy_url(configured, lambda _url, **_kw: httpx.Response(200)) == "http://renderer:9000"
    with pytest.raises(RendererUnreachable):
        comfy_url({}, lambda _url, **_kw: httpx.Response(503))


def test_check_png_wants_a_1280x720_png() -> None:
    check_png(h.png())
    with pytest.raises(ValueError, match="1280x720 PNG"):
        check_png(h.png(640, 360))
    with pytest.raises(ValueError, match="not an image"):
        check_png(b"<html>error</html>")


def _last(graph: dict[str, Any]) -> dict[str, Any]:
    return {"p0": {"prompt": [0, "p0", graph, {}, []]}}


def test_render_frees_a_renderer_that_last_ran_h3(tmp_path: Path) -> None:
    _, clock = _ready(tmp_path, 1)
    fake = FakeComfy(clock)
    fake.history = _last(
        graphs.minimax_h3_turbo_i2v("x", image="i", seed=0, width=1344, height=768, frames=22)
    )
    assert _render(tmp_path, _deps(clock, fake)) == cli.EXIT_OK
    assert fake.freed == 1


def test_render_leaves_a_flux_renderer_alone(tmp_path: Path) -> None:
    _, clock = _ready(tmp_path, 1)
    fake = FakeComfy(clock)
    fake.history = _last(graphs.flux2_dev_t2i("x", seed=0, width=1280, height=720))
    assert _render(tmp_path, _deps(clock, fake)) == cli.EXIT_OK
    assert fake.freed == 0


def test_a_freed_renderer_without_room_for_flux_stops_render(tmp_path: Path) -> None:
    """Deviation from the brief: every other stop in this file is asserted with
    pytest.raises(AskOwner, ...), since `_render` here calls `render.execute` directly rather
    than through `cli.main` (which is what maps AskOwner to EXIT_ASK and writes stderr). The
    brief's draft compared `_render(...)` to `cli.EXIT_ASK` and checked capsys stderr, which
    cannot pass: `execute()` raises, it never returns, and nothing in this path writes to
    stderr."""
    _, clock = _ready(tmp_path, 1)
    fake = FakeComfy(clock)
    fake.history = _last(
        graphs.minimax_h3_turbo_i2v("x", image="i", seed=0, width=1344, height=768, frames=22)
    )
    fake.free_gib = 10.0
    with pytest.raises(AskOwner, match=r"FLUX\.2 needs 60 GiB"):
        _render(tmp_path, _deps(clock, fake))
    assert fake.graphs == []
