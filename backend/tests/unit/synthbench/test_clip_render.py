"""`clip render` (clips design §4) against a fake ComfyUI (httpx.MockTransport)."""

from __future__ import annotations

import hashlib
import io
import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import httpx
import pytest
from PIL import Image
from synthbench import cli
from synthbench.clips import settings as clip_settings
from synthbench.clips.render import (
    WARMUP_FRAMES,
    check_clip,
    clip_graph,
    fit_input,
    strip,
    warmup_graph,
)
from synthbench.clips.rules import motion_text
from synthbench.commands import clip_render, render
from synthbench.commands.common import AskOwner, RequestError
from synthbench.contract.clip import ClipProvenance, ClipSpec, SwitchRow, clip_name, strip_name
from synthbench.contract.provenance import Provenance
from synthbench.generate.comfy import graphs
from synthbench.generate.render import family

from backend.tests.unit.synthbench import helpers as h

PILOT = "clips-pilot-1"
CLIP = h.mp4()  # at import: collection pays for the encode, not a timed test
OOM = [
    "execution_error",
    {
        "node_id": "11",
        "node_type": "SamplerCustomAdvanced",
        "exception_type": "torch.OutOfMemoryError",
        "exception_message": "out of memory",
    },
]
Graph = dict[str, Any]


def _length(graph: Graph) -> int:
    return next(
        int(node["inputs"]["length"])
        for node in graph.values()
        if node["class_type"] == "MiniMaxH3ImageToVideo"
    )


def _h3() -> Graph:
    return graphs.minimax_h3_turbo_i2v("x", image="i", seed=0, width=1344, height=768, frames=22)


def _flux() -> Graph:
    return graphs.flux2_dev_t2i("x", seed=0, width=1280, height=720)


class FakeComfy:
    """ComfyUI for clips. A queued prompt moves the fake clock like a render: `seconds` for a
    clip, 30 s for the warm-up; it then becomes the history's newest entry."""

    def __init__(
        self,
        clock: h.FakeClock,
        *,
        last: Graph | None = None,
        seconds: float = 150.0,
        free_gib: float = 200.0,
        clip: bytes = CLIP,
        fail: frozenset[int] = frozenset(),
        release_polls: int = 0,
    ) -> None:
        self.clock = clock
        self.seconds = seconds
        self.free_gib = free_gib
        # Like ComfyUI (clips probe): after /free, the first `release_polls` readings still
        # show the old models' memory.
        self.release_polls = release_polls
        self.polls_since_free: int | None = None
        self.clip = clip
        self.fail = fail
        self.graphs: list[Graph] = []
        self.freed = 0
        self.uploads = 0
        self.history: dict[str, Any] = (
            {} if last is None else {"p0": {"prompt": [0, "p0", last, {}, []]}}
        )

    def __call__(self, request: httpx.Request) -> httpx.Response:  # noqa: PLR0911
        path = request.url.path
        if path == "/system_stats":
            free = self.free_gib
            if self.polls_since_free is not None:
                self.polls_since_free += 1
                if self.polls_since_free <= self.release_polls:
                    free = 5.0
            devices = [{"vram_free": int(free * 2**30)}]
            return httpx.Response(200, json={"system": {}, "devices": devices})
        if path == "/history":
            return httpx.Response(200, json=self.history)
        if path == "/free":
            self.freed += 1
            self.polls_since_free = 0
            return httpx.Response(200, json={})
        if path == "/upload/image":
            self.uploads += 1
            return httpx.Response(200, json={"name": f"up{self.uploads}.png"})
        if path == "/prompt":
            graph = json.loads(request.content)["prompt"]
            self.graphs.append(graph)
            self.clock.now += 30.0 if _length(graph) == WARMUP_FRAMES else self.seconds
            number = len(self.graphs)
            self.history = {f"p{number}": {"prompt": [number, f"p{number}", graph, {}, []]}}
            return httpx.Response(200, json={"prompt_id": f"p{number}", "node_errors": {}})
        if path.startswith("/history/p"):
            number = int(path.rsplit("p", 1)[1])
            if number in self.fail:
                entry: dict[str, Any] = {
                    "status": {"status_str": "error", "messages": [OOM]},
                    "outputs": {},
                }
            else:
                video = {"filename": "x.mp4", "subfolder": "", "type": "output"}
                entry = {
                    "status": {"status_str": "success"},
                    "outputs": {"15": {"images": [video], "animated": [True]}},
                }
            return httpx.Response(200, json={f"p{number}": entry})
        if path == "/view":
            return httpx.Response(200, content=self.clip)
        return httpx.Response(404)


def _deps(clock: h.FakeClock, handler: Callable[[httpx.Request], httpx.Response]) -> render.Deps:
    transport = httpx.MockTransport(handler)

    def get(url: str, timeout: float) -> httpx.Response:
        with httpx.Client(transport=transport) as client:
            return client.get(url, timeout=timeout)

    return render.Deps(
        transport=transport, get=get, sleep=clock.sleep, clock=clock, now=lambda: h.NOW
    )


def _render(root: Path, deps: render.Deps) -> int:
    return clip_render.execute(PILOT, h.env(root), deps)


def _ready(root: Path, n: int) -> tuple[list[ClipSpec], h.FakeClock]:
    specs = h.frozen_round(root, n=n)
    h.flagship(root)
    return specs, h.FakeClock()


def _prov(root: Path, spec: ClipSpec) -> ClipProvenance:
    store = h.store(root)
    return store.read(store.provenance_file(spec.event_id), ClipProvenance)


@pytest.fixture(autouse=True)
def _timeouts(monkeypatch: pytest.MonkeyPatch) -> None:
    """The tests' arithmetic uses these; Task 1 sets the shipped values (ruling H3-R7)."""
    monkeypatch.setattr(clip_render, "CLIP_TIMEOUT_S", 360.0)
    monkeypatch.setattr(clip_render, "WARMUP_TIMEOUT_S", 300.0)
    monkeypatch.setattr(clip_render, "H3_PEAK_GIB", 52.0)


def test_a_flux_renderer_is_freed_warmed_to_h3_once_then_renders(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    specs, clock = _ready(tmp_path, 3)
    fake = FakeComfy(clock, last=_flux())
    assert _render(tmp_path, _deps(clock, fake)) == cli.EXIT_OK
    # warm-up at 0-30 s; clips start at 30 and 180; the next would start at 330 > 570 - 360
    assert fake.freed == 1
    assert [_length(g) for g in fake.graphs] == [WARMUP_FRAMES, 243, 243]
    out = capsys.readouterr().out
    assert "2 rendered now, 1 still to render" in out
    store = h.store(tmp_path)
    (switch,) = [
        SwitchRow.model_validate_json(line)
        for line in (store.round_dir(PILOT) / "switches.jsonl").read_text().splitlines()
    ]
    assert (switch.previous, switch.warmup_seconds) == ("flux2", 30.0)
    # a second call: H3 is resident, so no switch
    assert _render(tmp_path, _deps(clock, fake)) == cli.EXIT_OK
    assert fake.freed == 1
    assert [_length(g) for g in fake.graphs[3:]] == [243]
    assert {row.status for row in store.latest_clip_index().values()} == {"rendered"}
    for spec in specs:
        attempt = _prov(tmp_path, spec).attempts[-1]
        assert attempt.clip is not None and attempt.strip is not None
        assert attempt.clip.path == clip_name(attempt.k, attempt.seed)
        assert attempt.strip.path == strip_name(attempt.k, attempt.seed)
        event_dir = store.event_dir(spec.event_id)
        assert (event_dir / attempt.clip.path).read_bytes() == CLIP
        assert attempt.models == clip_settings.model_hashes()


def test_the_input_is_the_fitted_source_render(tmp_path: Path) -> None:
    specs, clock = _ready(tmp_path, 1)
    assert _render(tmp_path, _deps(clock, FakeComfy(clock, last=_h3()))) == cli.EXIT_OK
    store = h.store(tmp_path)
    source = specs[0].source.event_id
    render_file = store.read(store.provenance_file(source), Provenance).attempts[-1].render
    assert render_file is not None
    fitted = fit_input((store.event_dir(source) / render_file.path).read_bytes())
    attempt = _prov(tmp_path, specs[0]).attempts[-1]
    assert attempt.input_sha256 == hashlib.sha256(fitted).hexdigest()


def test_an_h3_renderer_renders_without_a_switch(tmp_path: Path) -> None:
    _, clock = _ready(tmp_path, 1)
    fake = FakeComfy(clock, last=_h3())
    assert _render(tmp_path, _deps(clock, fake)) == cli.EXIT_OK
    assert fake.freed == 0
    assert [_length(g) for g in fake.graphs] == [243]
    assert not (h.store(tmp_path).round_dir(PILOT) / "switches.jsonl").exists()


def test_an_empty_history_warms_up_without_freeing(tmp_path: Path) -> None:
    _, clock = _ready(tmp_path, 1)
    fake = FakeComfy(clock)
    assert _render(tmp_path, _deps(clock, fake)) == cli.EXIT_OK
    assert fake.freed == 0
    assert _length(fake.graphs[0]) == WARMUP_FRAMES


def test_the_switch_waits_for_the_freed_memory(tmp_path: Path) -> None:
    _, clock = _ready(tmp_path, 1)
    fake = FakeComfy(clock, last=_flux(), release_polls=3)
    assert _render(tmp_path, _deps(clock, fake)) == cli.EXIT_OK
    assert clock.sleeps[:3] == [1.0, 1.0, 1.0]
    assert _length(fake.graphs[0]) == WARMUP_FRAMES


def test_too_little_free_memory_stops_before_the_warmup(tmp_path: Path) -> None:
    """Deviation from the brief: `_render` calls `clip_render.execute` directly (as it does
    throughout this file, mirroring test_render.py), so a stop is a raised AskOwner, not a
    returned exit code - the same correction test_render.py needed."""
    _, clock = _ready(tmp_path, 1)
    fake = FakeComfy(clock, last=_flux(), free_gib=1.0)
    with pytest.raises(AskOwner, match="GiB free"):
        _render(tmp_path, _deps(clock, fake))
    assert fake.graphs == []


def test_a_third_failed_job_fails_the_clip(tmp_path: Path) -> None:
    specs, clock = _ready(tmp_path, 1)
    fake = FakeComfy(clock, last=_h3(), fail=frozenset({1, 2, 3}))
    assert _render(tmp_path, _deps(clock, fake)) == cli.EXIT_OK
    assert _render(tmp_path, _deps(clock, fake)) == cli.EXIT_OK
    with pytest.raises(AskOwner, match="failed to render 3 times"):
        _render(tmp_path, _deps(clock, fake))
    assert h.store(tmp_path).latest_clip_index()[specs[0].event_id].status == "failed"
    assert _render(tmp_path, _deps(clock, fake)) == cli.EXIT_OK  # later runs skip it


def test_a_wrong_shaped_clip_is_a_failed_job(tmp_path: Path) -> None:
    specs, clock = _ready(tmp_path, 1)
    fake = FakeComfy(clock, last=_h3(), clip=h.mp4(64, 48, 10))
    assert _render(tmp_path, _deps(clock, fake)) == cli.EXIT_OK
    (failure,) = _prov(tmp_path, specs[0]).attempts[-1].render_failures
    assert "expected a 1344x768 clip" in failure.error


def test_an_unrecorded_clip_is_adopted(tmp_path: Path) -> None:
    specs, clock = _ready(tmp_path, 1)
    store = h.store(tmp_path)
    attempt = _prov(tmp_path, specs[0]).attempts[-1]
    store.write_new_bytes(
        store.event_dir(specs[0].event_id) / clip_name(attempt.k, attempt.seed), CLIP
    )
    fake = FakeComfy(clock, last=_h3())
    assert _render(tmp_path, _deps(clock, fake)) == cli.EXIT_OK
    assert fake.graphs == []
    assert _prov(tmp_path, specs[0]).attempts[-1].clip is not None


def test_clip_render_needs_frozen_motions(tmp_path: Path) -> None:
    h.clip_round(tmp_path, n=1)
    clock = h.FakeClock()
    with pytest.raises(RequestError, match="run clip check"):
        _render(tmp_path, _deps(clock, FakeComfy(clock)))


def test_an_unknown_flagship_stops_clip_render(tmp_path: Path) -> None:
    h.frozen_round(tmp_path, n=1)  # no status/flagship.json
    clock = h.FakeClock()
    with pytest.raises(AskOwner):
        _render(tmp_path, _deps(clock, FakeComfy(clock, last=_h3())))


def test_no_renderer_is_a_stop(tmp_path: Path) -> None:
    _, clock = _ready(tmp_path, 1)
    down = _deps(clock, lambda _request: httpx.Response(503))
    with pytest.raises(AskOwner, match="renderer is down"):
        _render(tmp_path, down)


def test_fit_input_covers_and_centre_crops_to_1344x768() -> None:
    for width, height in ((1280, 720), (512, 288)):
        with Image.open(io.BytesIO(fit_input(h.png(width, height)))) as image:
            assert (image.format, image.size) == ("PNG", (1344, 768))


def test_check_clip_wants_1344x768_and_240_frames() -> None:
    assert check_clip(CLIP) == 243
    with pytest.raises(ValueError, match="expected a 1344x768 clip"):
        check_clip(h.mp4(1344, 768, 100))
    with pytest.raises(ValueError, match="not a video"):
        check_clip(b"not a video")


def test_the_strip_tiles_six_frames() -> None:
    with Image.open(io.BytesIO(strip(CLIP, 243))) as image:
        assert (image.format, image.size) == ("JPEG", (1344, 512))


def test_families_come_from_the_unet() -> None:
    assert family(_flux()) == "flux2"
    assert family(_h3()) == "h3"
    wan = graphs.wan22_i2v("x", image="i", seed=0, width=832, height=480, frames=81)
    assert family(wan) == "other"


def test_the_clip_graph_carries_the_motion_the_seed_and_243_frames(tmp_path: Path) -> None:
    spec = h.frozen_round(tmp_path, n=1)[0]
    attempt = _prov(tmp_path, spec).attempts[0]
    graph = clip_graph(spec, attempt, "up.png")
    node = next(n for n in graph.values() if n["class_type"] == "MiniMaxH3ImageToVideo")
    assert node["inputs"]["prompt"] == motion_text(spec)
    assert (node["inputs"]["width"], node["inputs"]["height"], node["inputs"]["length"]) == (
        1344,
        768,
        243,
    )
    assert (
        next(n for n in graph.values() if n["class_type"] == "RandomNoise")["inputs"]["noise_seed"]
        == attempt.seed
    )
    save = next(n for n in graph.values() if n["class_type"] == "SaveVideo")
    assert save["inputs"]["filename_prefix"].endswith(f"{spec.event_id}/a1-s{attempt.seed}")
    assert _length(warmup_graph("w.png")) == WARMUP_FRAMES
