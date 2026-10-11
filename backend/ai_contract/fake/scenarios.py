"""The fake AI stack's scenario book (O2.1).

The fixture image chooses the outcome. Each scenario names an image under
``scenario_fixtures/`` and the detections and verdict the fake answers for it;
the fake hashes the bytes it RECEIVES and looks the digest up here. Both hops
carry the file the camera wrote, unchanged: the detector uploads it as a
multipart file (``detector_client.py``, ``image_file.read_bytes()``) and the
VLM client embeds it as a data URI (``vlm_client.py``, ``_image_parts``). So a
golden path drops a scenario image into a camera folder and asserts the event
carries that scenario's verdict, exactly.

Digests are computed from the committed files at load time, never written
down: re-encoding an image changes its scenario key and nothing else.

``reply_delay_seconds`` delays the VLM's verdict reply: the slow-reply failure
mode, chosen per image so the fake keeps no runtime state and a slow scenario
never slows another request. The enforcement probe the client sends first,
with the same image, is never delayed (``app.py``), so the slow leg is the
verdict request itself.

An image no scenario names gets the deterministic generator answers the
contract suite pins (``generators.py``).
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

SCENARIO_DIR = Path(__file__).resolve().parent / "scenario_fixtures"
BOOK_FILE = "scenarios.json"


@dataclass(frozen=True)
class Scenario:
    """One fixture image and the outcome it chooses."""

    name: str
    image: Path
    digest: str
    width: int
    height: int
    detections: tuple[dict[str, Any], ...]
    verdict: dict[str, Any]
    reply_delay_seconds: float


class ScenarioBook:
    """Scenarios by the sha256 of their image bytes."""

    def __init__(self, scenarios: Iterable[Scenario] = ()) -> None:
        self._by_digest: dict[str, Scenario] = {}
        for scenario in scenarios:
            if scenario.digest in self._by_digest:
                other = self._by_digest[scenario.digest].name
                raise ValueError(f"scenarios {other!r} and {scenario.name!r} share an image")
            self._by_digest[scenario.digest] = scenario

    @classmethod
    def load(cls, directory: Path = SCENARIO_DIR) -> ScenarioBook:
        return _load(directory.resolve())

    def for_image(self, data: bytes) -> Scenario | None:
        return self._by_digest.get(hashlib.sha256(data).hexdigest())

    def __iter__(self) -> Iterator[Scenario]:
        return iter(self._by_digest.values())

    def __len__(self) -> int:
        return len(self._by_digest)


@lru_cache(maxsize=4)
def _load(directory: Path) -> ScenarioBook:
    from PIL import Image

    entries = json.loads((directory / BOOK_FILE).read_text(encoding="utf-8"))["scenarios"]
    scenarios = []
    for entry in entries:
        image = directory / entry["image"]
        data = image.read_bytes()
        with Image.open(image) as decoded:
            width, height = decoded.size
        scenarios.append(
            Scenario(
                name=entry["name"],
                image=image,
                digest=hashlib.sha256(data).hexdigest(),
                width=width,
                height=height,
                detections=tuple(entry["detections"]),
                verdict=entry["verdict"],
                reply_delay_seconds=float(entry.get("reply_delay_seconds", 0)),
            )
        )
    return ScenarioBook(scenarios)
