"""Multi-still sequence sets: declared-truth temporal triplets sampled from rendered clips.

ISS-037's corpus half. `export vss` writes one still per event; this writes 3 or 4 JPEG
frames sampled at fixed fractions of each READY clip's triaged mp4 — early, middle, late —
into a set the same `import_generated_items` reads, one level deeper:

    <export>/sequences/<category>/<event-id>__seq<k>/
        expected_labels.json      the importer's label document, plus the export's facts
        frame1.jpg … frame<k>.jpg  the sampled frames, oldest first
        frame1.json … frame<k>.json the attribution sidecars the importer demands

The truth is H3's declared truth (the clip spec's cell, label, risk band, subjects) —
undistributed and unaudited exactly as the clips are (ISS-038). What the sampling adds is
CHRONOLOGY the stills never had: frame k's capture time is the event's scene timestamp plus
its millisecond offset into the clip, so a replay can hand the production builders a batch
with a real timeline. The timeline is synthetic in one honest sense only: the clip's internal
clock starts at the declared scene time; the offsets themselves are the mp4's own frame times.

This module never imports `backend` (spec §7.1 — the export package rule). Frame decode is
PyAV, the declared dependency the clip checks already use (`pyproject.toml`: "synthbench clip
checks and frame strips"). JPEG encoding is Pillow, already a backend dependency and the
test suite's image tool; the bytes never leave this process.
"""

from __future__ import annotations

import hashlib
import io
import json
from collections.abc import Sequence
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from synthbench.export.vss import (
    CATEGORY_LABEL,
    LABELS_FILE,
    LICENSE,
    ExportedSet,
    scene_timestamp,
    write_set,
)

# Fixed sampling fractions of the clip's frame count: early, middle, late (and a fourth at
# 0.36 when asked). Fixed, not random: a corpus member's frames are re-derivable from the
# mp4 and these constants, which is what makes a create-once export checkable.
FRAME_FRACTIONS: dict[int, tuple[float, ...]] = {
    3: (0.10, 0.50, 0.90),
    4: (0.10, 0.36, 0.62, 0.90),
}
SEQUENCE_DIR = "sequences"
FRAME_FILE_STEM = "frame"
SIDECAR_ARTIST = "synthbench (frame sample of an H3-rendered clip)"


def sequence_name(event_id: str, frames: int) -> str:
    """The set directory's name: the clip event plus the frame count it carries."""
    return f"{event_id}__seq{frames}"


def sample_indices(frame_count: int, frames: int) -> list[int]:
    """The mp4 frame index behind each sampled still, oldest first.

    Index `int(count * fraction)`, clamped so the last frame never overruns the stream;
    strictly increasing (bumped by one if a tiny clip collapses two fractions). N distinct
    frames need at least N frames to sit in: below that the clamp cannot bump past the
    stream's end, and a silently duplicated frame would put the same moment on the wire
    twice under two capture times."""
    if frames not in FRAME_FRACTIONS:
        raise ValueError(f"frames must be one of {sorted(FRAME_FRACTIONS)}, got {frames}")
    if frame_count < frames:
        raise ValueError(f"a {frame_count}-frame clip has no {frames} distinct frames to sample")
    indices = [
        min(frame_count - 1, int(frame_count * fraction)) for fraction in FRAME_FRACTIONS[frames]
    ]
    for i in range(1, len(indices)):
        if indices[i] <= indices[i - 1]:
            indices[i] = min(frame_count - 1, indices[i - 1] + 1)
    return indices


def clip_frame_count(data: bytes) -> int:
    """How many frames the mp4 holds — the denominator `sample_indices` needs up front.

    The H.264 streams the renderer writes (and the test fixtures) carry the count in their
    metadata; a stream that does not report one is counted by decoding it once, because a
    silent wrong count would silently wrong indices."""
    import av

    with av.open(io.BytesIO(data), "r") as container:
        reported = container.streams.video[0].frames
        if reported:
            return int(reported)
        return sum(1 for _ in container.decode(video=0))


def offsets_ms(indices: list[int], fps: float) -> list[int]:
    """Each sampled frame's millisecond offset into the clip, from the stream's own rate."""
    return [round(1000 * index / fps) for index in indices]


def sample_frames(data: bytes, indices: list[int]) -> tuple[list[bytes], float]:
    """Decode the mp4 once; return (JPEG bytes per requested index in `indices` order, fps).

    `fps` is the stream's own average rate, float because a 29.97 stream is real; `offsets_ms`
    reads it as a float, and it is recorded in the sidecar for re-derivation.

    PyAV decodes the H.264 stream the renderer wrote; Pillow encodes JPEG (quality 95, the
    H3 stills' own neighborhood). An unreadable stream is a ValueError naming the failure —
    the command turns it into its exit-2 path, because a corpus member whose frames cannot be
    read must not export half a timeline."""
    import av  # declared dependency; imported here so the module stays import-cheap
    from PIL import Image

    targets = set(indices)
    picked: dict[int, bytes] = {}
    position = 0
    with av.open(io.BytesIO(data), "r") as container:
        stream = container.streams.video[0]
        fps = float(stream.average_rate or 24)
        for frame in container.decode(video=0):
            if position in targets:
                buffer = io.BytesIO()
                Image.fromarray(frame.to_ndarray(format="rgb24")).save(buffer, "JPEG", quality=95)
                picked[position] = buffer.getvalue()
            position += 1
            if len(picked) == len(targets):
                break
    missing = sorted(targets - picked.keys())
    if missing:
        raise ValueError(
            f"the clip holds {position} frames but requested index {missing[0]}; "
            "the index list is stale against this render"
        )
    return [picked[index] for index in indices], fps


def sequence_timestamps(scene_time: str, weather: str, offsets_ms: list[int]) -> list[str]:
    """Frame k's capture time: the scene timestamp plus its millisecond offset into the clip.

    Same date rule as the stills (snow scenes in January, the rest in April), same camera
    timezone; the offsets come from the mp4's own frame times, so the SPACING is the
    render's, not an invention."""
    moment = datetime.fromisoformat(scene_timestamp(scene_time, weather))
    return [(moment + timedelta(milliseconds=offset)).isoformat() for offset in offsets_ms]


def frame_detections(
    specs: Sequence[Any],
    frame_files: list[str],
    times: list[str],
) -> list[dict[str, Any]]:
    """One ideal-detector row per declared object per frame — the batch a replay hands the
    production builders.

    `specs` are the clip spec's declared SubjectSpec/PropSpec objects — the same input the
    stills' `declared_detections` takes, and read the same way (`obj.cls`). A SEQUENCE's
    rows must additionally say WHICH frame each object was on and WHEN, because that is the
    whole content of a batch: `build_assess_request` groups detections by `file_path` to
    populate `frame_detection_ids`, and `build_assess_context` takes the EARLIEST
    `detected_at` as the batch timestamp. `id` is a batch-global sequence (the wire treats
    detection ids as batch-scoped), file_path the frame file's name inside the set."""
    objects = [{"object_type": obj.cls} for obj in specs] or [{"object_type": "scene"}]
    rows: list[dict[str, Any]] = []
    next_id = 1
    for file_name, moment in zip(frame_files, times, strict=True):
        for obj in objects:
            rows.append(
                {
                    "id": next_id,
                    "object_type": obj["object_type"],
                    "confidence": 1.0,
                    "file_path": file_name,
                    "detected_at": moment,
                }
            )
            next_id += 1
    return rows


def sequence_labels_document(
    facts: dict[str, Any],
    *,
    category: str,
    frames: int,
    times: list[str],
    offsets_ms: list[int],
    detections: list[dict[str, Any]],
    frame_sha256s: list[str],
) -> dict[str, Any]:
    """The sequence set's `expected_labels.json`: the importer's keys plus this export's facts.

    `facts` is the clip event's synthbench block (cell, label, risk band, scene time,
    subjects, props — the declared truth), which the caller assembled; this function adds
    the sequence half: the frame count, the per-frame capture times and clip offsets, the
    per-frame digests, and a note that says WHERE the timeline came from. The importer reads
    category/risk/timestamp/detections; everything under `synthbench` is the scorer's."""
    lo, hi = facts["risk_band"]
    document = {
        "category": category,
        "risk": {"min_score": lo, "max_score": hi},
        "timestamp": times[0],  # production's rule: a batch is stamped by its earliest frame
        "detections": detections,
        "synthbench": {
            **facts,
            "kind": "sequence",
            "frames": frames,
            "frame_files": [f"{FRAME_FILE_STEM}{i + 1}.jpg" for i in range(frames)],
            "frame_times": times,
            "frame_offsets_ms": offsets_ms,
            "frame_sha256s": frame_sha256s,
            "timeline": "declared scene_time + the clip's own frame times",
        },
    }
    return document


def sequence_files(
    facts: dict[str, Any],
    *,
    category: str,
    jpeg_frames: list[bytes],
    offsets_ms: list[int],
    times: list[str],
    detections: list[dict[str, Any]],
    corpus_version: str,
) -> dict[str, bytes]:
    """Every file of one sequence set, by name (the shape `write_set` stages and renames)."""
    frame_files = [f"{FRAME_FILE_STEM}{i + 1}.jpg" for i in range(len(jpeg_frames))]
    digests = [hashlib.sha256(data).hexdigest() for data in jpeg_frames]
    labels = sequence_labels_document(
        facts,
        category=category,
        frames=len(jpeg_frames),
        times=times,
        offsets_ms=offsets_ms,
        detections=detections,
        frame_sha256s=digests,
    )
    files = {
        LABELS_FILE: (json.dumps(labels, indent=2, sort_keys=True) + "\n").encode(),
    }
    sidecar = {
        "license": LICENSE,
        "artist": SIDECAR_ARTIST,
        "corpus_version": corpus_version,
    }
    for name, data in zip(frame_files, jpeg_frames, strict=True):
        files[name] = data
        files[name.replace(".jpg", ".json")] = (
            json.dumps(
                {**sidecar, "frame_sha256": hashlib.sha256(data).hexdigest()},
                indent=2,
                sort_keys=True,
            )
            + "\n"
        ).encode()
    return files


def write_sequence_set(
    sequences_dir: Path, category: str, name: str, files: dict[str, bytes]
) -> bool:
    """One sequence set, create-once, under <sequences_dir>/<category>/<name>.

    `vss.write_set` does the staging-and-rename; its staging directory lands beside
    `sequences_dir` — INSIDE the export root, unlike the stills' — but dot-prefixed, and
    pathlib's wildcards never match a leading dot, so the stills' importer (depth-2 glob)
    and the sequences' importer (depth-2 below `sequences_dir`) both stay blind to it."""
    return write_set(sequences_dir, category, name, files)


def read_sequence_sets(export_dir: Path) -> list[Any]:
    """Every sequence set under an export, reusing the stills' reader one level deeper."""

    root = export_dir / SEQUENCE_DIR
    sets = [
        ExportedSet(
            category=path.parent.parent.name,
            set_dir=path.parent,
            labels=json.loads(path.read_text(encoding="utf-8")),
        )
        for path in root.glob(f"*/*/{LABELS_FILE}")
        if path.parent.parent.name in CATEGORY_LABEL
    ]
    return sorted(sets, key=lambda s: s.item_id)
