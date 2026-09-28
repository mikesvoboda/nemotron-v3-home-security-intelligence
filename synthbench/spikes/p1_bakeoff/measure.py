"""P1 measurement (spec §3.7): OWLv2 prop adherence, facenet identity drift,
EasyOCR plate reading. All three are independent of the pipeline's models.

Run inside the renderer image (GPU; the flagship may stay up):
    $(uv run python -m synthbench.generate.podman) run --rm --device nvidia.com/gpu=all \
      -v "$PWD":/work:ro -w /work \
      -v /export/synthbench:/export/synthbench -v /export/synthbench/cache:/root/.cache \
      -e SYNTHBENCH_ROOT=/export/synthbench -e EASYOCR_MODULE_PATH=/root/.cache/easyocr \
      --entrypoint python localhost/synthbench-comfyui:v0.37.0 \
      -m synthbench.spikes.p1_bakeoff.measure

This module and cases.py run on the image's Python 3.12: ruff targets py312
for them (pyproject.toml), and test_p1_py312.py checks that they parse.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import sys
from pathlib import Path
from typing import Any, Protocol

from synthbench.spikes.p1_bakeoff.cases import CASES

_CASES = {case.id: case for case in CASES}
OWL_MODEL = "google/owlv2-base-patch16-ensemble"


def normalize_plate(text: str) -> str:
    return re.sub(r"[^A-Z0-9-]", "", text.upper())


def cer(pred: str, target: str) -> float:
    """Character error rate: Levenshtein distance / len(target)."""
    prev = list(range(len(target) + 1))
    for i, pc in enumerate(pred, start=1):
        cur = [i]
        for j, tc in enumerate(target, start=1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (pc != tc)))
        prev = cur
    return prev[-1] / max(len(target), 1)


def cosine_distance(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    norm = math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b))
    return 1.0 - dot / norm if norm else 1.0


class Tools(Protocol):
    def owl(self, image: Path, queries: tuple[str, ...]) -> dict[str, float]: ...

    def ocr(self, image: Path) -> str: ...

    def face(self, image: Path) -> list[float] | None: ...

    def clip_faces(self, clip: Path) -> list[list[float]]: ...


def measure_record(record: dict[str, Any], root: Path, tools: Tools) -> dict[str, Any]:
    path = root / record["output"]
    out: dict[str, Any] = {"output": record["output"]}
    if record["kind"] == "i2v":
        faces = tools.clip_faces(path)
        out["frames_with_face"] = len(faces)
        out["frame_drift_max"] = max(
            (cosine_distance(faces[0], f) for f in faces[1:]), default=None
        )
        return out
    case = _CASES.get(record["case"])
    if case is not None:
        out["owl"] = tools.owl(path, case.owl_queries)
        if case.ocr_target:
            text = normalize_plate(tools.ocr(path))
            out["plate_text"] = text
            out["plate_exact"] = text == case.ocr_target
            out["plate_cer"] = cer(text, case.ocr_target)
    if record["case"] in {"identity", "identity_reference"}:
        out["face"] = tools.face(path)
    return out


class RealTools:  # pragma: no cover - runs in the renderer image only
    def __init__(self) -> None:
        import torch

        self._device = "cuda" if torch.cuda.is_available() else "cpu"
        self._owl: Any = None
        self._ocr: Any = None
        self._faces: Any = None

    def owl(self, image: Path, queries: tuple[str, ...]) -> dict[str, float]:
        import torch
        from PIL import Image
        from transformers import Owlv2ForObjectDetection, Owlv2Processor

        if self._owl is None:
            # Bound as Any: mypy rejects the .to() chain on the transformers stub.
            owl_cls: Any = Owlv2ForObjectDetection
            self._owl = (
                Owlv2Processor.from_pretrained(OWL_MODEL),
                owl_cls.from_pretrained(OWL_MODEL).to(self._device).eval(),
            )
        processor, model = self._owl
        img = Image.open(image).convert("RGB")
        inputs = processor(text=[list(queries)], images=img, return_tensors="pt").to(self._device)
        with torch.no_grad():
            logits = model(**inputs).logits[0].sigmoid()  # (boxes, queries)
        return {q: round(float(logits[:, i].max()), 4) for i, q in enumerate(queries)}

    def ocr(self, image: Path) -> str:
        import easyocr

        if self._ocr is None:
            self._ocr = easyocr.Reader(["en"], gpu=self._device == "cuda")
        results = self._ocr.readtext(str(image))
        return " ".join(text for _box, text, _conf in sorted(results, key=lambda r: -r[2]))

    def _face_models(self) -> Any:
        from facenet_pytorch import MTCNN, InceptionResnetV1

        if self._faces is None:
            self._faces = (
                MTCNN(image_size=160, device=self._device),
                InceptionResnetV1(pretrained="vggface2").eval().to(self._device),
            )
        return self._faces

    def _embed(self, pil_image: Any) -> list[float] | None:
        import torch

        detector, embedder = self._face_models()
        crop = detector(pil_image)
        if crop is None:
            return None
        with torch.no_grad():
            vector = embedder(crop.unsqueeze(0).to(self._device))[0]
        return [round(float(x), 6) for x in vector]

    def face(self, image: Path) -> list[float] | None:
        from PIL import Image

        return self._embed(Image.open(image).convert("RGB"))

    def clip_faces(self, clip: Path) -> list[list[float]]:
        import av

        with av.open(str(clip)) as container:
            frames = [f.to_image() for f in container.decode(video=0)]
        step = max(len(frames) // 8, 1)
        faces = [self._embed(frame) for frame in frames[::step][:8]]
        return [f for f in faces if f is not None]


def main(argv: list[str] | None = None) -> int:  # pragma: no cover - renderer image only
    parser = argparse.ArgumentParser(prog="python -m synthbench.spikes.p1_bakeoff.measure")
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(os.environ.get("SYNTHBENCH_ROOT", "/export/synthbench")) / "p1",
    )
    root: Path = parser.parse_args(argv).root
    records = [json.loads(line) for line in (root / "records.jsonl").read_text().splitlines()]
    latest = {r["output"]: r for r in records}  # a resumed job's last row wins
    tools = RealTools()
    with (root / "measures.jsonl").open("w") as fh:
        for record in latest.values():
            if record["ok"]:
                fh.write(json.dumps(measure_record(record, root, tools)) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
