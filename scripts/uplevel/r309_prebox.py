#!/usr/bin/env python3
"""OWLv2 pre-box pass for [r309]'s labelled frame set.

    uv run python scripts/uplevel/r309_prebox.py \
        --selection /home/OWNERHOST/frame-set/selection.json \
        --root /export/foscam \
        --out /home/OWNERHOST/frame-set/prebox.coco.json \
        [--threshold 0.2] [--max-per-frame 10] [--device cpu]

Runs the open-vocabulary detector synthbench §4.1 requires for the
independent object/prop check - a different family than every [r303]
bake-off candidate (OWLv2 here; the YOLO threat model is what is being
scored, so it must never pre-box its own evaluation set):

    docs/superpowers/specs/2026-09-27-synthetic-benchmark-generation-design.md
    §4.1 "open-vocabulary detector from a different family than YOLO26,
    YOLOE and the YOLOv8 threat model (for example Grounding DINO or OWLv2)"

Input is deliverable 1's selection list (paths + strata only). Every
selected frame is opened, measured and passed to OWLv2 with the query
texts. All detections at or above --threshold are kept as COCO
annotations with their scores - the owner corrects, so the pass errs
toward recall, not precision.

Output is a COCO file (images, annotations, categories) with the frame
paths as file_name. It stays on the host with the frames - the repo gets
counts, never boxes tied to pixels (ops.md [r309]: "no frame, crop or
label file enters the repo, a PR, a CI artifact or any cloud service").

Classes start at the bake-off's two (person, vehicle) and grow with any
extra query the pre-box was asked (--classes), so "any other product
class the pre-box finds is kept" is a property of the file, not a
promise to re-run.

Weights are fetched on first run (HF hub) and cached locally; the model
load is one seam (`load_owlv2`) so a host with no network can point it
at a local snapshot directory with --model-dir.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Protocol

# The bake-off's classes first (fixed ids), then any extras in query order.
DEFAULT_CLASSES = ["person", "vehicle"]
# Home-security-relevant extras the pre-box proposes by default; the owner
# deletes what they don't want kept.
DEFAULT_EXTRA_QUERIES = ["dog", "cat", "package", "bicycle"]


class OwlV2Like(Protocol):
    """The slice of the OWLv2 stack the pass needs (test seam)."""

    def detect(self, image: Any, queries: list[str]) -> list[tuple[str, list[float], float]]:
        """(label, [x, y, w, h] in pixels, score) per detection."""
        ...


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--selection", required=True, help="deliverable 1's selection list (JSON)")
    ap.add_argument(
        "--root",
        required=True,
        help="Foscam upload tree root the selection paths are "
        "relative to (or absolute paths are used as-is)",
    )
    ap.add_argument("--out", required=True, help="COCO output path (JSON, host-side)")
    ap.add_argument(
        "--threshold", type=float, default=0.2, help="keep detections scoring >= this (default 0.2)"
    )
    ap.add_argument(
        "--max-per-frame",
        type=int,
        default=10,
        help="keep at most this many boxes per frame, highest score first (default 10)",
    )
    ap.add_argument(
        "--classes",
        nargs="+",
        default=DEFAULT_CLASSES,
        help=f"bake-off classes, in id order (default: {' '.join(DEFAULT_CLASSES)})",
    )
    ap.add_argument(
        "--extra-queries",
        nargs="+",
        default=DEFAULT_EXTRA_QUERIES,
        help="additional open-vocabulary queries proposed to "
        "the owner (default: "
        f"{' '.join(DEFAULT_EXTRA_QUERIES)})",
    )
    ap.add_argument(
        "--model-dir",
        default=None,
        help="local OWLv2 snapshot directory (offline hosts); "
        "default fetches google/owlv2-base-patch16-ensemble "
        "from the HF hub cache",
    )
    ap.add_argument("--device", default="cpu", help="torch device for the pass (default cpu)")
    return ap.parse_args()


def load_owlv2(model_dir: str | None, device: str) -> OwlV2Like:
    """The one seam that touches weights; tests stub this out."""
    from transformers import Owlv2ForObjectDetection, Owlv2Processor

    source = model_dir or "google/owlv2-base-patch16-ensemble"
    processor = Owlv2Processor.from_pretrained(source)
    model: Any = Owlv2ForObjectDetection.from_pretrained(source)
    model.to(device)
    model.eval()

    class _OwlV2:
        def detect(self, image: Any, queries: list[str]) -> list[tuple[str, list[float], float]]:
            import torch as t

            with t.no_grad():
                inputs = processor(text=[queries], images=image, return_tensors="pt").to(device)
                outputs = model(**inputs)
                target_sizes = t.tensor([[image.height, image.width]])
                # The open-vocabulary post-processor (the closed-vocabulary
                # `post_process_object_detection` is not on this processor).
                # Its output labels index into `text_labels`, passed here so
                # the ints resolve against OUR query order, not the encoded
                # one.
                results = processor.post_process_grounded_object_detection(
                    outputs,
                    target_sizes=target_sizes,  # type: ignore[arg-type]
                    text_labels=[queries],
                )[0]
            out: list[tuple[str, list[float], float]] = []
            for score, label, box in zip(
                results["scores"].tolist(),
                results["labels"].tolist(),
                results["boxes"].tolist(),
                strict=True,
            ):
                text = queries[label]
                x1, y1, x2, y2 = box
                out.append((text, [x1, y1, x2 - x1, y2 - y1], score))
            return out

    return _OwlV2()


def read_selection(path: Path) -> tuple[list[str], dict]:
    """The selection list's paths, plus the report header it carried."""
    report = json.loads(path.read_text())
    selected = report.get("selected")
    if not isinstance(selected, list) or not selected:
        print(f"r309_prebox: {path} carries no selected frames", file=sys.stderr)
        sys.exit(2)
    paths: list[str] = []
    for e in selected:
        p = e.get("path") if isinstance(e, dict) else None
        if not isinstance(p, str) or not p:
            print(f"r309_prebox: {path} has a selection entry without a path", file=sys.stderr)
            sys.exit(2)
        paths.append(p)
    return paths, report


def resolve_frame(root: Path, raw: str) -> Path:
    """Absolute selection paths pass through; relative ones join --root."""
    p = Path(raw)
    return p if p.is_absolute() else root / p


def main() -> int:
    args = parse_args()
    paths, selection_report = read_selection(Path(args.selection))
    root = Path(args.root)
    if not root.is_dir():
        print(f"r309_prebox: --root {root} is not a directory", file=sys.stderr)
        sys.exit(2)

    from PIL import Image

    queries = list(args.classes) + [q for q in args.extra_queries if q not in args.classes]

    detector = load_owlv2(args.model_dir, args.device)

    images: list[dict] = []
    annotations: list[dict] = []
    next_image_id = 1
    next_ann_id = 1
    unreadable = 0
    frames_with_boxes = 0
    per_class: dict[str, int] = dict.fromkeys(queries, 0)

    for i, raw in enumerate(paths, start=1):
        frame = resolve_frame(root, raw)
        try:
            with Image.open(frame) as im:
                rgb = im.convert("RGB")
                width, height = im.size
        except (OSError, ValueError) as exc:
            print(f"r309_prebox: [{i}/{len(paths)}] unreadable {frame}: {exc}", file=sys.stderr)
            unreadable += 1
            continue

        dets = detector.detect(rgb, queries)
        dets = [d for d in dets if d[2] >= args.threshold]
        dets.sort(key=lambda d: d[2], reverse=True)
        dets = dets[: args.max_per_frame]

        image_id = next_image_id
        next_image_id += 1
        images.append(
            {
                "id": image_id,
                "file_name": raw,
                "width": width,
                "height": height,
                "stratum": next(
                    (e["stratum"] for e in selection_report["selected"] if e["path"] == raw),
                    None,
                ),
            }
        )
        if dets:
            frames_with_boxes += 1
        for label, box, score in dets:
            annotations.append(
                {
                    "id": next_ann_id,
                    "image_id": image_id,
                    "_label": label,
                    "bbox": [
                        round(box[0], 2),
                        round(box[1], 2),
                        round(box[2], 2),
                        round(box[3], 2),
                    ],
                    "area": round(box[2] * box[3], 2),
                    "iscrowd": 0,
                    "score": round(score, 4),
                }
            )
            next_ann_id += 1
            per_class[label] += 1
        if i % 25 == 0 or i == len(paths):
            print(f"r309_prebox: {i}/{len(paths)} frames pre-boxed")

    # The two bake-off classes are always present (the evaluation's fixed
    # labels); extras appear only when the pass actually found them - "any
    # other product class the pre-box finds is kept", and a category with
    # zero annotations is not a finding.
    used_extras = [q for q in queries[len(args.classes) :] if per_class[q] > 0]
    kept_queries = list(args.classes) + used_extras
    categories = [{"id": i + 1, "name": name} for i, name in enumerate(kept_queries)]
    # Re-id the annotations whose labels are extras: detection labels map
    # through the FULL query list, COCO category ids through kept_queries.
    remap = {name: i + 1 for i, name in enumerate(kept_queries)}
    for ann in annotations:
        ann["category_id"] = remap[ann.pop("_label")]

    coco = {
        "info": {
            "description": "[r309] pre-box pass (OWLv2) for [r303]'s "
            "detector bake-off; owner corrections pending",
            "prebox_model": "owlv2-base-patch16-ensemble",
            "score_threshold": args.threshold,
        },
        "licenses": [],
        "categories": categories,
        "images": images,
        "annotations": annotations,
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(coco, indent=2) + "\n")

    print(f"r309_prebox: wrote {out}")
    print(
        f"  frames:            {len(images)} "
        f"(unreadable: {unreadable}, empty of boxes: "
        f"{len(images) - frames_with_boxes})"
    )
    print(f"  boxes:             {len(annotations)}")
    for name in queries:
        print(f"    {name:<12} {per_class[name]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
