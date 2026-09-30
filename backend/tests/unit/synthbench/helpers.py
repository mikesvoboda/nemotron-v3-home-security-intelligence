"""Builders shared by the synthbench command tests: batches, prompts, outputs and images."""

from __future__ import annotations

import hashlib
import io
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from PIL import Image
from synthbench import cli
from synthbench.contract.clip import ClipSpec, RoundRecord
from synthbench.contract.corpus import BatchRecord
from synthbench.contract.provenance import OutputFile, Provenance, Triage, render_name, still_name
from synthbench.contract.spec import Spec
from synthbench.contract.store import CorpusStore
from synthbench.status import FlagshipStatus, flagship_file, write_status
from synthbench.taxonomy.model import load_taxonomy

TAX = load_taxonomy()  # at import: collection pays for the load, not a timed test
VERSION = TAX.version


def env(root: Path) -> dict[str, str]:
    return {"SYNTHBENCH_ROOT": str(root)}


def store(root: Path) -> CorpusStore:
    return CorpusStore(root / "corpus", VERSION)


def run(root: Path, *argv: str) -> int:
    return cli.main(list(argv), env=env(root))


def sample(root: Path, batch: str = "pilot-1", n: int = 4) -> list[Spec]:
    assert run(root, "sample", "--batch", batch, "--n", str(n)) == cli.EXIT_OK
    s = store(root)
    record = s.read(s.batch_file(batch), BatchRecord)
    return [s.read(s.spec_file(event), Spec) for event in record.event_ids]


def good_prompt(spec: Spec) -> str:
    """A prompt that passes every rule: the first term of each subject's and prop's class."""
    nouns = [TAX.terms[item.cls][0] for item in (*spec.subjects, *spec.props)]
    place = spec.cell.zone.replace("_", " ")
    return f"At the {place}: {', '.join(nouns) if nouns else 'an empty scene'}."


def write_prompts(root: Path, batch: str, prompts: dict[str, str]) -> None:
    path = store(root).batch_dir(batch) / "prompts.jsonl"
    rows = [json.dumps({"event_id": event, "prompt": text}) for event, text in prompts.items()]
    path.write_text("".join(f"{row}\n" for row in rows), encoding="utf-8")


def frozen_batch(root: Path, batch: str = "pilot-1", n: int = 4) -> list[Spec]:
    """A sampled batch whose prompts `check` has frozen; returns the frozen specs."""
    specs = sample(root, batch, n)
    write_prompts(root, batch, {spec.event_id: good_prompt(spec) for spec in specs})
    assert run(root, "check", "--batch", batch) == cli.EXIT_OK
    s = store(root)
    return [s.read(s.spec_file(spec.event_id), Spec) for spec in specs]


def record_output(
    root: Path, spec: Spec, *, render: bytes | None = None, still: bytes | None = None
) -> None:
    """Store and record the current attempt's render and still, as render and camera do."""
    s = store(root)
    path = s.provenance_file(spec.event_id)
    prov = s.read(path, Provenance)
    attempt = prov.attempts[-1]
    event_dir = s.event_dir(spec.event_id)
    changes: dict[str, Any] = {}
    if render is not None:
        name = render_name(attempt.k, attempt.seed)
        s.write_new_bytes(event_dir / name, render)
        changes["render"] = OutputFile(path=name, sha256=hashlib.sha256(render).hexdigest())
        changes["render_seconds"] = 8.0
    if still is not None:
        name = still_name(attempt.k, attempt.seed)
        s.write_new_bytes(event_dir / name, still)
        changes["still"] = OutputFile(path=name, sha256=hashlib.sha256(still).hexdigest())
        changes["camera_params"] = "default-v1"
        changes["overlay_time"] = "2026-03-04 10:15:09"
    s.replace_json(path, prov.updated(attempts=(*prov.attempts[:-1], attempt.updated(**changes))))


def png(
    width: int = 1280, height: int = 720, color: tuple[int, int, int] = (90, 110, 130)
) -> bytes:
    out = io.BytesIO()
    Image.new("RGB", (width, height), color).save(out, "PNG")
    return out.getvalue()


def rendered_batch(root: Path, batch: str = "pilot-1", n: int = 4) -> list[Spec]:
    """A frozen batch whose attempt 1 has a real 1280x720 PNG render recorded."""
    specs = frozen_batch(root, batch, n)
    for spec in specs:
        record_output(root, spec, render=png())
    return specs


NOW = datetime(2026, 9, 28, 12, 0, tzinfo=UTC)


def flagship(root: Path, *, healthy: bool = True, waiting: int = 0, time: datetime = NOW) -> None:
    """Write status/flagship.json as the guard does."""
    status = FlagshipStatus(time=time, healthy=healthy, running=1, waiting=waiting)
    write_status(flagship_file(env(root)), status)


class FakeClock:
    """A monotonic clock that only fake sleeps and fake work move."""

    def __init__(self) -> None:
        self.now = 0.0
        self.sleeps: list[float] = []

    def __call__(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.now += seconds


def stilled_batch(root: Path, batch: str = "pilot-1", n: int = 4) -> list[Spec]:
    """A frozen batch whose attempt 1 has a render and a still recorded (stand-in bytes: fast)."""
    specs = frozen_batch(root, batch, n)
    for spec in specs:
        tag = spec.event_id.encode()
        record_output(root, spec, render=b"png " + tag, still=b"jpeg " + tag)
    return specs


def ready_batch(root: Path, batch: str = "pilot-1", n: int = 4) -> list[Spec]:
    """A batch whose every event is ready, as triage leaves it: a real 1280x720 PNG render, a
    stand-in still and an ok verdict on attempt 1."""
    specs = frozen_batch(root, batch, n)
    s = store(root)
    for spec in specs:
        record_output(root, spec, render=png(), still=b"jpeg " + spec.event_id.encode())
        path = s.provenance_file(spec.event_id)
        prov = s.read(path, Provenance)
        last = prov.attempts[-1].updated(triage=Triage(verdict="ok"))
        s.replace_json(path, prov.updated(attempts=(*prov.attempts[:-1], last)))
        row = s.latest_index()[spec.event_id]
        s.append_index([row.model_copy(update={"status": "ready", "time": NOW.isoformat()})])
    return specs


def clip_round(root: Path, n: int = 4, name: str = "clips-pilot-1") -> list[ClipSpec]:
    """A ready batch of n stills, sampled whole into clip round `name`."""
    ready_batch(root, n=n)
    assert run(root, "clip", "sample", "--round", name, "--n", str(n)) == cli.EXIT_OK
    s = store(root)
    record = s.read(s.round_file(name), RoundRecord)
    return [s.read(s.spec_file(event), ClipSpec) for event in record.event_ids]


def good_motion(spec: ClipSpec) -> str:
    """A motion that passes every rule: each subject's and prop's first term, no camera words."""
    nouns = [TAX.terms[item.cls][0] for item in (*spec.subjects, *spec.props)]
    if not nouns:
        return "Leaves move a little in the wind."
    return f"The {', '.join(nouns)} stay in place and move a little."


def write_motions(root: Path, name: str, motions: dict[str, str]) -> None:
    path = store(root).round_dir(name) / "motions.jsonl"
    rows = [json.dumps({"event_id": event, "prompt": text}) for event, text in motions.items()]
    path.write_text("".join(f"{row}\n" for row in rows), encoding="utf-8")


def frozen_round(root: Path, n: int = 4, name: str = "clips-pilot-1") -> list[ClipSpec]:
    """A clip round whose motions `clip check` has frozen; returns the frozen specs."""
    specs = clip_round(root, n, name)
    write_motions(root, name, {spec.event_id: good_motion(spec) for spec in specs})
    assert run(root, "clip", "check", "--round", name) == cli.EXIT_OK
    s = store(root)
    return [s.read(s.spec_file(spec.event_id), ClipSpec) for spec in specs]


def mp4(width: int = 1344, height: int = 768, frames: int = 243, value: int = 90) -> bytes:
    """A real H.264 mp4 of flat frames at 24 fps. 1344x768x243 encodes in about 0.3 s, so tests
    build theirs at import."""
    import av
    import numpy as np

    out = io.BytesIO()
    with av.open(out, "w", format="mp4") as container:
        stream = container.add_stream("libx264", rate=24, options={"preset": "ultrafast"})
        stream.width = width
        stream.height = height
        stream.pix_fmt = "yuv420p"
        pixels = np.full((height, width, 3), value, np.uint8)
        for _ in range(frames):
            frame = av.VideoFrame.from_ndarray(pixels, format="rgb24")
            for packet in stream.encode(frame):
                container.mux(packet)
        for packet in stream.encode():
            container.mux(packet)
    return out.getvalue()
