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
    Triage,
    attempt_seed,
    render_name,
)
from synthbench.contract.spec import Spec
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

    def __call__(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path == "/system_stats":
            return httpx.Response(200, json={"system": {}})
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
    assert "nothing to render" in capsys.readouterr().out


def test_render_waits_while_the_flagship_has_requests_waiting(tmp_path: Path) -> None:
    _specs, clock = _ready(tmp_path, 1)
    h.flagship(tmp_path, waiting=2)
    comfy = FakeComfy(clock)
    deps = _deps(clock, comfy, on_sleep=lambda: h.flagship(tmp_path, waiting=0))
    assert _render(tmp_path, deps) == cli.EXIT_OK
    assert clock.sleeps == [5.0]
    assert len(comfy.graphs) == 1


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


def test_a_failed_job_is_recorded_and_retried_next_run(tmp_path: Path) -> None:
    specs, clock = _ready(tmp_path, 2)
    assert _render(tmp_path, _deps(clock, FakeComfy(clock, fail=frozenset({1})))) == cli.EXIT_OK
    first = _attempt(tmp_path, specs[0])
    assert first.render is None
    assert "OutOfMemoryError" in first.render_failures[0].error
    assert _attempt(tmp_path, specs[1]).render is not None
    assert _render(tmp_path, _deps(clock, FakeComfy(clock))) == cli.EXIT_OK
    assert _attempt(tmp_path, specs[0]).render is not None


def test_three_failed_jobs_stop_and_ask(tmp_path: Path) -> None:
    _specs, clock = _ready(tmp_path, 1)
    for _ in range(2):
        assert _render(tmp_path, _deps(clock, FakeComfy(clock, fail=frozenset({1})))) == 0
    with pytest.raises(AskOwner, match="failed to render 3 times"):
        _render(tmp_path, _deps(clock, FakeComfy(clock, fail=frozenset({1}))))


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
