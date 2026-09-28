"""P1 measurement (spec §3.7): OWLv2 prop adherence, facenet identity drift,
EasyOCR plate reading. All three are independent of the pipeline's models.

Every image (and clip frame) is first resized, aspect kept, to MEASURE_SIZE's
area (~1.03 MP, the smallest native render size), so no model's legibility or
face size gains from rendering more pixels. Plates are scored on their
alphanumerics only (ALPR-style); `plate_text` keeps what OCR read.

Every image is also read once by OCR for a refusal: Ideogram 4's weights paint
"Image blocked by safety filter" (a gray card, or the text over a partial scene)
for prompts they refuse. `refused` comes from that text; `card_like` (a nearly
uniform image) is a diagnostic beside it. Clips are never refused.

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
from collections.abc import Iterator
from pathlib import Path
from typing import Any, Protocol

from synthbench.spikes.p1_bakeoff.cases import CASES

_CASES = {case.id: case for case in CASES}
OWL_MODEL = "google/owlv2-base-patch16-ensemble"
# The pixel budget every image is measured at: the smallest native size (flux2-klein-4b).
MEASURE_SIZE = (1344, 768)
# A uniform gray card: its grayscale standard deviation at MEASURE_SIZE is under this.
# Calibrated on the 312 P1 images: Ideogram 4's 25 uniform cards measure 9.54-12.01 (the
# 12.01 one carries IR-style noise), every real render 23.31 or more. Its refusals painted
# over a partial scene measure 27-64: `refused` comes from the OCR text, and `card_like`
# is only a diagnostic.
CARD_GRAY_STD_MAX = 16.0

# One OCR text fragment: (text, (left, top, right, bottom)) in image pixels.
Fragment = tuple[str, tuple[float, float, float, float]]


def normalize_plate(text: str) -> str:
    """What plate scoring compares: the uppercase alphanumerics. A hyphen, dot or gap the
    model drew (or OCR dropped at a fragment split) never decides exact vs not."""
    return re.sub(r"[^A-Z0-9]", "", text.upper())


def measure_size(width: int, height: int) -> tuple[int, int]:
    """(width, height) scaled, aspect kept, to MEASURE_SIZE's area."""
    scale = math.sqrt(MEASURE_SIZE[0] * MEASURE_SIZE[1] / (width * height))
    return max(round(width * scale), 1), max(round(height * scale), 1)


def at_measure_size(image: Any) -> Any:
    """A PIL image at measure_size() (Lanczos); the same image when it is already there."""
    from PIL import Image

    size = measure_size(*image.size)
    return image if size == image.size else image.resize(size, Image.Resampling.LANCZOS)


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


def reading_order(fragments: list[Fragment]) -> list[list[Fragment]]:
    """Text lines top to bottom, each left to right. A fragment joins the first line whose
    first fragment's vertical span holds the fragment's vertical centre."""
    lines: list[list[Fragment]] = []
    for fragment in sorted(fragments, key=lambda f: f[1][1] + f[1][3]):
        centre = (fragment[1][1] + fragment[1][3]) / 2
        for line in lines:
            if line[0][1][1] <= centre <= line[0][1][3]:
                line.append(fragment)
                break
        else:
            lines.append([fragment])
    return [sorted(line, key=lambda f: f[1][0]) for line in lines]


def plate_candidates(fragments: list[Fragment]) -> list[str]:
    """Every fragment and every run of horizontally adjacent fragments (one line, left to
    right), joined as read: a plate read in pieces, beside other text in the scene."""
    candidates: list[str] = []
    for line in reading_order(fragments):
        for start in range(len(line)):
            for end in range(start + 1, len(line) + 1):
                candidates.append("".join(text for text, _ in line[start:end]))
    return candidates


def is_refusal_text(fragments: list[Fragment]) -> bool:
    """Whether OCR read the refusal card ("Image blocked by safety filter"): the text, in
    reading order, lowercased and stripped of punctuation and spaces, holds "blocked" and
    also "safety" or "filter", or holds "image blocked" (the model garbles the last words:
    "saficy filke!"). Scene text ("safety glass", "blocked driveway") is not one."""
    read = "".join(text for line in reading_order(fragments) for text, _ in line)
    text = re.sub(r"[^a-z0-9]", "", read.lower())
    return "imageblocked" in text or ("blocked" in text and ("safety" in text or "filter" in text))


def looks_like_card(gray_std: float) -> bool:
    """Whether an image's grayscale standard deviation at MEASURE_SIZE is a uniform card's."""
    return gray_std < CARD_GRAY_STD_MAX


def grayscale_std(image: Any) -> float:
    """A PIL image's grayscale standard deviation, measured at measure_size()."""
    from PIL import ImageStat

    return float(ImageStat.Stat(at_measure_size(image.convert("RGB")).convert("L")).stddev[0])


class Tools(Protocol):
    def owl(self, image: Path, queries: tuple[str, ...]) -> dict[str, float]: ...

    def ocr(self, image: Path) -> list[Fragment]: ...

    def face(self, image: Path) -> list[float] | None: ...

    def clip_faces(self, clip: Path) -> list[list[float]]: ...

    def gray_std(self, image: Path) -> float: ...


def measure_record(record: dict[str, Any], root: Path, tools: Tools) -> dict[str, Any]:
    path = root / record["output"]
    out: dict[str, Any] = {"output": record["output"]}
    if record["kind"] == "i2v":
        faces = tools.clip_faces(path)
        out["frames_with_face"] = len(faces)
        out["frame_drift_max"] = max(
            (cosine_distance(faces[0], f) for f in faces[1:]), default=None
        )
        out["refused"] = False  # frames are never OCR-read: refusal is an image finding
        return out
    fragments = tools.ocr(path)  # every image, once: the refusal check; the plate reuses it
    out["ocr_fragments"] = [t for line in reading_order(fragments) for t, _ in line]
    out["refused"] = is_refusal_text(fragments)
    out["card_like"] = looks_like_card(tools.gray_std(path))
    case = _CASES.get(record["case"])
    if case is not None:
        out["owl"] = tools.owl(path, case.owl_queries)
        if case.ocr_target:
            target = normalize_plate(case.ocr_target)
            # the closest candidate on alphanumerics; CER 0 (exact) whenever any one matches
            text = min(
                plate_candidates(fragments) or [""],
                key=lambda c: cer(normalize_plate(c), target),
            )
            out["plate_text"] = text  # as read, for the sheet
            out["plate_exact"] = normalize_plate(text) == target
            out["plate_cer"] = cer(normalize_plate(text), target)
    if record["case"] in {"identity", "identity_reference"}:
        out["face"] = tools.face(path)
    return out


def clip_frames(clip: Path, count: int = 8) -> list[Any]:
    """Up to `count` evenly spaced frames (PIL images) of the clip's first video stream.
    Decoding only that stream skips the audio track LTX-2.5 and MiniMax-H3 clips carry."""
    import av

    with av.open(str(clip)) as container:
        frames = [f.to_image() for f in container.decode(video=0)]
    step = max(len(frames) // count, 1)
    return frames[::step][:count]


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
        img = at_measure_size(Image.open(image).convert("RGB"))
        inputs = processor(text=[list(queries)], images=img, return_tensors="pt").to(self._device)
        with torch.no_grad():
            logits = model(**inputs).logits[0].sigmoid()  # (boxes, queries)
        return {q: round(float(logits[:, i].max()), 4) for i, q in enumerate(queries)}

    def ocr(self, image: Path) -> list[Fragment]:
        import easyocr
        import numpy as np
        from PIL import Image

        if self._ocr is None:
            self._ocr = easyocr.Reader(["en"], gpu=self._device == "cuda")
        # An RGB array reaches EasyOCR's detector as a file path's pixels would; its grey
        # copy for the recognizer swaps the R/B weights, the same for every model.
        pixels = np.asarray(at_measure_size(Image.open(image).convert("RGB")))
        fragments: list[Fragment] = []
        for corners, text, _conf in self._ocr.readtext(pixels):  # corners: 4 (x, y) points
            xs = [float(x) for x, _y in corners]
            ys = [float(y) for _x, y in corners]
            fragments.append((text, (min(xs), min(ys), max(xs), max(ys))))
        return fragments

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

        return self._embed(at_measure_size(Image.open(image).convert("RGB")))

    def clip_faces(self, clip: Path) -> list[list[float]]:
        faces = [self._embed(at_measure_size(frame)) for frame in clip_frames(clip)]
        return [f for f in faces if f is not None]

    def gray_std(self, image: Path) -> float:
        from PIL import Image

        return grayscale_std(Image.open(image).convert("RGB"))


def measure_all(
    records: list[dict[str, Any]], root: Path, tools: Tools
) -> Iterator[dict[str, Any]]:
    """One row per ok output (a resumed job's last row wins). A record that raises yields
    {"output", "error"} and measuring goes on: one unreadable file must not stop the rest."""
    latest = {r["output"]: r for r in records}
    for record in latest.values():
        if not record["ok"]:
            continue
        try:
            yield measure_record(record, root, tools)
        except Exception as exc:
            yield {"output": record["output"], "error": f"{type(exc).__name__}: {exc}"[:500]}


def main(argv: list[str] | None = None) -> int:  # pragma: no cover - renderer image only
    parser = argparse.ArgumentParser(prog="python -m synthbench.spikes.p1_bakeoff.measure")
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(os.environ.get("SYNTHBENCH_ROOT", "/export/synthbench")) / "p1",
    )
    root: Path = parser.parse_args(argv).root
    records = [json.loads(line) for line in (root / "records.jsonl").read_text().splitlines()]
    rows = errors = 0
    with (root / "measures.jsonl").open("w") as fh:  # a full re-measure every run
        for row in measure_all(records, root, RealTools()):
            fh.write(json.dumps(row) + "\n")
            fh.flush()
            rows += 1
            if "error" in row:
                errors += 1
                sys.stderr.write(f"[p1-measure] {row['output']}: {row['error']}\n")
    sys.stderr.write(f"[p1-measure] {rows} rows, {errors} errors -> {root / 'measures.jsonl'}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
