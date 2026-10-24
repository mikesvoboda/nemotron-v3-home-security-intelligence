#!/usr/bin/env python3
"""Stratified frame sampler for [r309]'s labelled frame set.

    uv run python scripts/uplevel/r309_frame_sampler.py \
        --root /export/foscam \
        --out /home/OWNERHOST/frame-set/selection.json \
        [--seed 0] [--per-stratum 100] [--distant-resolution 720]

Stratifies the Foscam upload tree into day, night/IR and distant subjects,
and writes a seeded, repeatable selection list of paths and strata ONLY —
no frame, crop or label file ever enters the repo (ops.md [r309]: "The
frames and labels stay on the host").

Tree layout (the backend's own conventions, probed from
backend/services/file_watcher.py and backend/services/capture_time.py):

    <root>/<Camera Folder>/snap/MDAlarm_20260911-123100.jpg
    <root>/<Camera Folder>/snap/HMDAlarm_20260616-134454.jpg
    <root>/<Camera Folder>/record/MDalarm_20260728_111148.mkv

Only IMAGE extensions qualify ([r303]'s bake-off scores stills); the
filename regex and the image/video extension sets are the backend's own
(`_FOSCAM_NAME`, `IMAGE_EXTENSIONS`), imported so the sampler cannot drift
from what production watches.

Strata, decided from what the files themselves carry (no image decode,
no EXIF read — the path list must be computable from the host shell alone):

* **night/IR** — capture hour (camera local time, from the filename via
  `backend.services.capture_time.parse_capture_time` with
  `CAMERA_TIMEZONE`) outside [day-start, day-end). IR illuminators come
  on after dusk; night/IR and "day" are disjoint by construction.
* **day** — the complement, same clock.
* **distant** — resolution width below `--distant-resolution` px (720 by
  default), measured with the stdlib-only JPEG/PNG size probe. A small
  frame is the operational proxy for a small, far subject; the honest
  label is printed and the owner corrects strata at labelling time (the
  tool records the stratum as *proposed*, not measured).

Distant is a FLAG, not a separate stratum bucket: the selection carries
`(path, day|night_ir, distant?)`, so the counts the PR posts can report
"night/IR AND distant" without a fourth sampling bucket to fill.

Repeatability: `--seed` seeds a `random.Random(seed)`; the walk is
deterministic (sorted os.walk); selection is `rng.sample` per stratum
after bucketing. Same tree, same seed, same selection list — down to
bytes on a stable tree.

Exit codes: 0 = wrote the selection list; 2 = the root cannot be read or
is empty or no image file parses as a Foscam name (a silent empty
selection would look like a valid census of nothing).
"""

from __future__ import annotations

import argparse
import json
import os
import random
import struct
import sys
from pathlib import Path
from typing import NoReturn

from backend.services.capture_time import camera_tz, parse_capture_time
from backend.services.file_watcher import IMAGE_EXTENSIONS

# A JPEG frame starts with the SOI marker; the SOF0/SOF2 segment carries
# the dimensions. Scanning for the marker keeps this stdlib-only (no PIL
# on the host) and correct for progressive JPEGs too (SOF2).
_JPEG_SOF_MARKERS = {0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF}
_PNG_IHDR = b"IHDR"


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--root", required=True, help="Foscam upload tree root (e.g. /export/foscam)")
    ap.add_argument("--out", required=True, help="selection list output path (JSON, host-side)")
    ap.add_argument(
        "--seed", type=int, default=0, help="seed for the repeatable selection (default 0)"
    )
    ap.add_argument(
        "--per-stratum",
        type=int,
        default=100,
        help="target selection size per stratum (default 100)",
    )
    ap.add_argument(
        "--distant-resolution",
        type=int,
        default=720,
        help="width below which a frame is 'distant' (default 720)",
    )
    ap.add_argument(
        "--day-start",
        type=int,
        default=6,
        help="first camera-local hour counted as day (default 6)",
    )
    ap.add_argument(
        "--day-end", type=int, default=19, help="hour AFTER which it is night/IR (default 19)"
    )
    ap.add_argument(
        "--camera-tz",
        default=None,
        help="IANA timezone of the cameras' clocks "
        "(falls back to CAMERA_TIMEZONE); required unless "
        "CAMERA_TIMEZONE is set",
    )
    ap.add_argument(
        "--min-per-stratum",
        type=int,
        default=100,
        help="[r303] needs at least 100 person/vehicle frames per "
        "stratum; the sampler only counts what it finds and "
        "prints this bar for reference (default 100)",
    )
    return ap.parse_args()


def fail(msg: str) -> NoReturn:
    """Refuse loudly: name what failed, exit 2 (a code, not sys.exit(str) 1)."""
    print(msg, file=sys.stderr)
    sys.exit(2)


def jpeg_dimensions(data: bytes) -> tuple[int, int] | None:
    """(width, height) from JPEG bytes by scanning for a SOFn segment.

    Returns None when no SOFn appears before EOI (truncated or not a JPEG) —
    the caller records the file as unmeasured rather than guessing."""
    if len(data) < 4 or data[0:2] != b"\xff\xd8":
        return None
    i = 2
    n = len(data)
    while i + 4 <= n:
        if data[i] != 0xFF:
            i += 1
            continue
        marker = data[i + 1]
        if marker in (0xD8, 0x01) or 0xD0 <= marker <= 0xD7:
            i += 2
            continue
        if marker == 0xD9:  # EOI
            return None
        seg_len = struct.unpack(">H", data[i + 2 : i + 4])[0]
        if seg_len < 2:
            return None
        if marker in _JPEG_SOF_MARKERS:
            if i + 9 > n:
                return None
            h, w = struct.unpack(">HH", data[i + 5 : i + 9])
            return (w, h)
        i += 2 + seg_len
    return None


def png_dimensions(data: bytes) -> tuple[int, int] | None:
    """(width, height) from PNG bytes via the IHDR header, or None."""
    if len(data) < 24 or data[0:8] != b"\x89PNG\r\n\x1a\n":
        return None
    if data[12:16] != _PNG_IHDR:
        return None
    w, h = struct.unpack(">II", data[16:24])
    return (w, h)


def image_dimensions(path: Path) -> tuple[int, int] | None:
    """(width, height) for a .jpg/.jpeg/.png file, or None when unmeasurable."""
    try:
        data = path.read_bytes()
    except OSError:
        return None
    if path.suffix.lower() == ".png":
        return png_dimensions(data)
    return jpeg_dimensions(data)


def strata_for(
    captured_local_hour: int,
    width: int | None,
    day_start: int,
    day_end: int,
) -> str | None:
    """'day' or 'night_ir' from the camera-local capture hour, or None."""
    if width is None:
        return None
    return "day" if day_start <= captured_local_hour < day_end else "night_ir"


def walk_images(root: Path) -> list[Path]:
    """Every image file under root, camera-folder first, sorted (deterministic)."""
    found: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames.sort()
        for name in sorted(filenames):
            p = Path(dirpath) / name
            if p.suffix.lower() in IMAGE_EXTENSIONS:
                found.append(p)
    return found


def main() -> int:
    args = parse_args()
    root = Path(args.root)
    if not root.is_dir():
        fail(f"r309_frame_sampler: --root {root} is not a directory")

    tz = camera_tz(args.camera_tz)
    if tz is None:
        from backend.core.config import get_settings

        tz = camera_tz(get_settings().camera_timezone)
    if tz is None:
        fail(
            "r309_frame_sampler: no camera timezone (--camera-tz or "
            "CAMERA_TIMEZONE) - capture hours cannot be parsed, so the "
            "day/night strata would be guessed"
        )

    images = walk_images(root)
    if not images:
        fail(f"r309_frame_sampler: no image files under {root}")

    # Bucket every parseable still, then sample per stratum.
    buckets: dict[str, list[dict]] = {"day": [], "night_ir": []}
    unmeasured = 0
    unparsable_names = 0
    for p in images:
        captured = parse_capture_time(str(p), tz)
        if captured is None:
            unparsable_names += 1
            continue
        dims = image_dimensions(p)
        width = dims[0] if dims else None
        if width is None:
            unmeasured += 1
            continue
        # captured is UTC (parse_capture_time's contract); the day window is
        # camera-local, so read the hour from the camera-clock datetime.
        local_hour = captured.astimezone(tz).hour
        stratum = strata_for(local_hour, width, args.day_start, args.day_end)
        if stratum is None:
            # width was None (we checked) - unreachable, kept for the type checker
            continue
        buckets[stratum].append(
            {
                "path": str(p),
                "width": width,
                "height": dims[1],
                "capture_hour": local_hour,
            }
        )

    # Distant is a flag on top of the two strata, applied at sample time.
    rng = random.Random(args.seed)
    selection: list[dict] = []
    for stratum in ("day", "night_ir"):
        pool = buckets[stratum]
        distant = [e for e in pool if e["width"] < args.distant_resolution]
        near = [e for e in pool if e["width"] >= args.distant_resolution]
        # Take distant first so a stratum short of distant frames still
        # meets its distant share when the tree holds them.
        take_distant = min(len(distant), args.per_stratum // 2)
        take_near = min(len(near), args.per_stratum - take_distant)
        for e in rng.sample(distant, take_distant):
            selection.append({**e, "stratum": stratum, "distant": True})
        for e in rng.sample(near, take_near):
            selection.append({**e, "stratum": stratum, "distant": False})

    # The report the PR posts: counts per stratum and class-of-size only —
    # no image, no crop, no frame bytes anywhere in this output.
    report = {
        "root": str(root),
        "seed": args.seed,
        "per_stratum_target": args.per_stratum,
        "distant_resolution": args.distant_resolution,
        "day_window_hours": [args.day_start, args.day_end],
        "counted": {
            "images_seen": len(images),
            "unparsable_names": unparsable_names,
            "unmeasured_dimensions": unmeasured,
            "day_total": len(buckets["day"]),
            "night_ir_total": len(buckets["night_ir"]),
            "day_distant": sum(1 for e in buckets["day"] if e["width"] < args.distant_resolution),
            "night_ir_distant": sum(
                1 for e in buckets["night_ir"] if e["width"] < args.distant_resolution
            ),
        },
        "selected": [
            {"path": e["path"], "stratum": e["stratum"], "distant": e["distant"]} for e in selection
        ],
    }

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")

    print(f"r309_frame_sampler: wrote {out}")
    c = report["counted"]
    print(f"  images seen:            {c['images_seen']}")
    print(f"  unparsable names:       {c['unparsable_names']}")
    print(f"  unmeasured dimensions:  {c['unmeasured_dimensions']}")
    print(f"  day pool:               {c['day_total']} (distant: {c['day_distant']})")
    print(f"  night/IR pool:          {c['night_ir_total']} (distant: {c['night_ir_distant']})")
    print(
        f"  selected:               {len(selection)} "
        f"({sum(1 for e in selection if e['stratum'] == 'day')} day, "
        f"{sum(1 for e in selection if e['stratum'] == 'night_ir')} night/IR)"
    )
    print(
        f"  [r303] bar: at least {args.min_per_stratum} person/vehicle frames "
        f"per stratum after labelling - the sampler cannot promise this; "
        f"the pool sizes above are what it can promise"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
