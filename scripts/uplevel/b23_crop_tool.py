#!/usr/bin/env python3
"""B2.3 neutral person-crop sampler, event/track pre-grouper, and localhost review tool.

Ruling 333 item 1:
- About 150-200 person crops across several of the owner's cameras and days,
  the 36 crops from `[r312a]` included.
- Pre-grouped by event and track (one detection track inside one event is one
  identity), never by OSNet or a challenger model, so the labels do not favour
  any candidate.
- The owner merges or splits groups across events and cameras in a local review
  tool (`127.0.0.1` only), as ruling 309 set for `[r309]`.
- Crops and labels stay on the host and are never committed or uploaded; PRs
  post only aggregate counts and metrics.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import re
import shutil
import sys
from dataclasses import dataclass, field
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import unquote

from PIL import Image

IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
# Matches e.g. real-018-beach_front_left-048.png -> camera=beach_front_left, burst=048
_O24_FILENAME_RE = re.compile(r"^real-\d+-(?P<camera>[a-zA-Z0-9_]+)-(?P<burst>\d+)\.[a-zA-Z0-9]+$")


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _parse_existing_crop_metadata(path: Path) -> tuple[str, str, str]:
    """Infer `(camera_id, event_id, track_id)` from an existing crop filename without any model."""
    m = _O24_FILENAME_RE.match(path.name)
    if m:
        cam = m.group("camera")
        burst = m.group("burst")
        return cam, f"o24_{cam}_{burst}", f"burst_{burst}"
    stem = path.stem
    return "unknown_camera", f"singleton_{stem}", f"trk_{stem}"


def _neutral_group_id(camera_id: str, event_id: str, track_id: str) -> str:
    """Deterministic group ID from event and track only (never from model embeddings)."""
    safe_evt = re.sub(r"[^a-zA-Z0-9_-]", "_", str(event_id or "evt"))
    safe_trk = re.sub(r"[^a-zA-Z0-9_-]", "_", str(track_id or "trk"))
    safe_cam = re.sub(r"[^a-zA-Z0-9_-]", "_", str(camera_id or "cam"))
    return f"grp_{safe_cam}_{safe_evt}_{safe_trk}"


def build_pregrouped_set(
    *,
    existing_crops_dir: Path | None,
    detections_manifest: Path | None,
    output_dir: Path,
    target_count: int = 180,
    seed: int = 42,
) -> dict[str, Any]:
    """Build `<output_dir>/crops/` and `<output_dir>/pregrouped.json` using only
    event and track metadata (never OSNet or any challenger embedding).
    """
    crops_out = output_dir / "crops"
    crops_out.mkdir(parents=True, exist_ok=True)

    items: list[dict[str, Any]] = []
    seen_ids: set[str] = set()

    # 1. Always include the existing [r312a] crops first when supplied (ruling 333 item 1)
    if existing_crops_dir is not None and existing_crops_dir.is_dir():
        for src in sorted(existing_crops_dir.iterdir()):
            if not src.is_file() or src.suffix.lower() not in IMAGE_SUFFIXES:
                continue
            crop_id = src.name
            if crop_id in seen_ids:
                continue
            seen_ids.add(crop_id)
            dst = crops_out / crop_id
            if src.resolve() != dst.resolve():
                shutil.copy2(src, dst)
            cam_id, evt_id, trk_id = _parse_existing_crop_metadata(src)
            items.append(
                {
                    "crop_id": crop_id,
                    "camera_id": cam_id,
                    "event_id": evt_id,
                    "track_id": trk_id,
                    "captured_at": "",
                    "source": "r312a_crops",
                    "group_id": _neutral_group_id(cam_id, evt_id, trk_id),
                }
            )

    # 2. Sample additional person crops from detections_manifest across cameras/days
    if detections_manifest is not None and detections_manifest.is_file():
        raw_manifest = json.loads(detections_manifest.read_text(encoding="utf-8"))
        entries = (
            raw_manifest if isinstance(raw_manifest, list) else raw_manifest.get("detections", [])
        )
        rng = random.Random(seed)  # noqa: S311 - deterministic sampling seed
        candidates = list(entries)
        rng.shuffle(candidates)
        candidates.sort(key=lambda e: (str(e.get("camera_id", "")), str(e.get("event_id", ""))))

        for idx, entry in enumerate(candidates):
            if len(items) >= target_count:
                break
            cam_id = str(entry.get("camera_id") or "camera")
            evt_id = str(entry.get("event_id") or f"evt_{idx}")
            trk_id = str(entry.get("track_id") or "trk_0")
            captured_at = str(entry.get("captured_at") or "")

            if entry.get("crop_path"):
                src_crop = Path(str(entry["crop_path"]))
                if not src_crop.is_file():
                    continue
                crop_id = src_crop.name
                if crop_id in seen_ids:
                    crop_id = f"crop_{idx:04d}_{src_crop.name}"
                seen_ids.add(crop_id)
                dst = crops_out / crop_id
                if src_crop.resolve() != dst.resolve():
                    shutil.copy2(src_crop, dst)
            elif entry.get("frame_path") and entry.get("bbox"):
                frame_p = Path(str(entry["frame_path"]))
                if not frame_p.is_file():
                    continue
                x1, y1, x2, y2 = [round(float(v)) for v in entry["bbox"][:4]]
                with Image.open(frame_p) as im:
                    rgb = im.convert("RGB")
                    w, h = rgb.size
                    cx1, cy1 = max(0, min(x1, w - 1)), max(0, min(y1, h - 1))
                    cx2, cy2 = max(cx1 + 1, min(x2, w)), max(cy1 + 1, min(y2, h))
                    crop_im = rgb.crop((cx1, cy1, cx2, cy2))
                    crop_id = f"det_{cam_id}_{evt_id}_{trk_id}_{idx:04d}.png"
                    seen_ids.add(crop_id)
                    crop_im.save(crops_out / crop_id, format="PNG")
            else:
                continue

            items.append(
                {
                    "crop_id": crop_id,
                    "camera_id": cam_id,
                    "event_id": evt_id,
                    "track_id": trk_id,
                    "captured_at": captured_at,
                    "source": "detections_manifest",
                    "group_id": _neutral_group_id(cam_id, evt_id, trk_id),
                }
            )

    payload: dict[str, Any] = {
        "seed": seed,
        "target_count": target_count,
        "grouping_rule": "event_and_track_only (never model embeddings, ruling 333 item 1)",
        "total_crops": len(items),
        "initial_groups": len({it["group_id"] for it in items}),
        "items": items,
    }
    (output_dir / "pregrouped.json").write_text(
        json.dumps(payload, indent=2) + "\n", encoding="utf-8"
    )
    return payload


@dataclass
class ReviewState:
    """Mutable owner review state over pre-grouped person crops."""

    items: dict[str, dict[str, Any]] = field(default_factory=dict)
    next_split_index: int = 1

    @classmethod
    def from_pregrouped(cls, pregrouped: dict[str, Any]) -> ReviewState:
        items: dict[str, dict[str, Any]] = {}
        for row in pregrouped.get("items", []):
            cid = str(row["crop_id"])
            gid = str(row["group_id"])
            items[cid] = {
                "crop_id": cid,
                "camera_id": str(row.get("camera_id", "")),
                "event_id": str(row.get("event_id", "")),
                "track_id": str(row.get("track_id", "")),
                "captured_at": str(row.get("captured_at", "")),
                "group_id": gid,
                "person_id": gid,
                "excluded": False,
            }
        return cls(items=items)

    def merge_groups(self, group_ids: list[str], *, target_person_id: str) -> None:
        target = target_person_id.strip()
        if not target:
            raise ValueError("target_person_id must be non-empty")
        gset = set(group_ids)
        for item in self.items.values():
            if item["person_id"] in gset or item["group_id"] in gset:
                item["person_id"] = target

    def split_crop(self, crop_id: str, *, new_person_id: str | None = None) -> str:
        if crop_id not in self.items:
            raise KeyError(f"Unknown crop_id: {crop_id}")
        assigned = (
            new_person_id.strip()
            if new_person_id and new_person_id.strip()
            else f"split_person_{self.next_split_index:03d}"
        )
        self.next_split_index += 1
        self.items[crop_id]["person_id"] = assigned
        return assigned

    def set_crop_status(self, crop_id: str, *, excluded: bool) -> None:
        if crop_id not in self.items:
            raise KeyError(f"Unknown crop_id: {crop_id}")
        self.items[crop_id]["excluded"] = bool(excluded)

    def to_dict(self) -> dict[str, Any]:
        return {
            "next_split_index": self.next_split_index,
            "items": list(self.items.values()),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ReviewState:
        items = {str(it["crop_id"]): dict(it) for it in data.get("items", [])}
        return cls(items=items, next_split_index=int(data.get("next_split_index", 1)))


def export_labels(work_dir: Path, state: ReviewState) -> dict[str, Any]:
    """Write `<work_dir>/labels.json` and return privacy-safe aggregate counts + SHA-256."""
    kept = [it for it in state.items.values() if not it.get("excluded", False)]
    excluded = [it for it in state.items.values() if it.get("excluded", False)]

    by_person: dict[str, list[dict[str, Any]]] = {}
    for it in kept:
        by_person.setdefault(str(it["person_id"]), []).append(it)

    multi_crop_identities = sum(1 for crops in by_person.values() if len(crops) >= 2)
    cameras = sorted({str(it["camera_id"]) for it in kept if it.get("camera_id")})

    summary = {
        "total_crops": len(state.items),
        "total_kept_crops": len(kept),
        "excluded_crops": len(excluded),
        "identities_count": len(by_person),
        "multi_crop_identities_count": multi_crop_identities,
        "cameras_count": len(cameras),
        "grouping_rule": "event_and_track_pregrouped_owner_reviewed",
    }
    labels_doc = {
        "summary": summary,
        "crops": sorted(kept, key=lambda x: str(x["crop_id"])),
    }
    raw_bytes = (json.dumps(labels_doc, indent=2) + "\n").encode("utf-8")
    labels_path = work_dir / "labels.json"
    labels_path.write_bytes(raw_bytes)
    sha = _sha256_bytes(raw_bytes)
    return {
        "labels_path": str(labels_path),
        "labels_sha256": sha,
        "summary": summary,
    }


_INDEX_HTML = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>B2.3 Person-Crop Identity Review Tool</title>
<style>
  body { font-family: system-ui, sans-serif; margin: 20px; background: #111827; color: #f3f4f6; }
  .toolbar { position: sticky; top: 0; background: #1f2937; padding: 12px; border-radius: 8px; margin-bottom: 16px; display: flex; gap: 12px; align-items: center; z-index: 10; }
  input, button { padding: 6px 12px; border-radius: 4px; border: 1px solid #374151; background: #374151; color: #fff; cursor: pointer; }
  button.primary { background: #2563eb; border-color: #1d4ed8; }
  .group { background: #1f2937; border: 1px solid #374151; border-radius: 8px; padding: 12px; margin-bottom: 14px; }
  .crops { display: flex; flex-wrap: wrap; gap: 10px; margin-top: 8px; }
  .crop-card { background: #111827; border: 1px solid #4b5563; border-radius: 6px; padding: 6px; width: 150px; font-size: 12px; }
  .crop-card.excluded { opacity: 0.35; }
  .crop-card img { width: 128px; height: 256px; object-fit: contain; display: block; margin: 0 auto 6px; background: #000; }
</style>
</head>
<body>
<div class="toolbar">
  <strong>B2.3 Neutral Event/Track Crop Review</strong>
  <input id="mergeTarget" placeholder="Target person_id (e.g. person_01)" />
  <button class="primary" onclick="mergeSelected()">Merge Checked Groups</button>
  <button class="primary" onclick="exportLabels()">Export labels.json</button>
  <span id="status"></span>
</div>
<div id="groups"></div>
<script>
let state = { items: [] };
async function load() {
  const res = await fetch('/api/state');
  state = await res.json();
  render();
}
function render() {
  const byPerson = {};
  for (const it of state.items) {
    (byPerson[it.person_id] = byPerson[it.person_id] || []).push(it);
  }
  const container = document.getElementById('groups');
  container.innerHTML = '';
  for (const [pid, list] of Object.entries(byPerson)) {
    const div = document.createElement('div');
    div.className = 'group';
    div.innerHTML = `<label><input type="checkbox" class="grp-check" value="${pid}"> <strong>${pid}</strong> (${list.length} crops)</label>`;
    const row = document.createElement('div');
    row.className = 'crops';
    for (const it of list) {
      const card = document.createElement('div');
      card.className = 'crop-card' + (it.excluded ? ' excluded' : '');
      card.innerHTML = `
        <img src="/crops/${encodeURIComponent(it.crop_id)}" loading="lazy" />
        <div>${it.camera_id}<br>${it.event_id} / ${it.track_id}</div>
        <button onclick="splitCrop('${it.crop_id}')">Split</button>
        <button onclick="toggleExclude('${it.crop_id}', ${!it.excluded})">${it.excluded ? 'Include' : 'Exclude'}</button>
      `;
      row.appendChild(card);
    }
    div.appendChild(row);
    container.appendChild(div);
  }
}
async function mergeSelected() {
  const checked = [...document.querySelectorAll('.grp-check:checked')].map(el => el.value);
  const target = document.getElementById('mergeTarget').value.trim() || checked[0];
  if (!checked.length || !target) return;
  await fetch('/api/merge', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({group_ids: checked, target_person_id: target}) });
  await load();
}
async function splitCrop(crop_id) {
  const name = prompt('New person_id for split crop (leave blank for auto):', '');
  if (name === null) return;
  await fetch('/api/split', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({crop_id, new_person_id: name}) });
  await load();
}
async function toggleExclude(crop_id, excluded) {
  await fetch('/api/exclude', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({crop_id, excluded}) });
  await load();
}
async function exportLabels() {
  const res = await fetch('/api/export', { method: 'POST' });
  const out = await res.json();
  document.getElementById('status').textContent = `Exported: ${out.summary.total_kept_crops} crops, ${out.summary.identities_count} identities, sha256=${out.labels_sha256.slice(0, 16)}...`;
}
load();
</script>
</body>
</html>
"""


def run_server(work_dir: Path, host: str = "127.0.0.1", port: int = 8766) -> None:
    if host != "127.0.0.1":
        raise SystemExit("Refusing to bind non-loopback address; use 127.0.0.1 (UR-133)")
    pre_path = work_dir / "pregrouped.json"
    if not pre_path.is_file():
        raise SystemExit(f"pregrouped.json not found in {work_dir}; run 'sample' first")
    state_path = work_dir / "review_state.json"
    if state_path.is_file():
        state = ReviewState.from_dict(json.loads(state_path.read_text(encoding="utf-8")))
    else:
        state = ReviewState.from_pregrouped(json.loads(pre_path.read_text(encoding="utf-8")))

    crops_dir = (work_dir / "crops").resolve()

    def save_state() -> None:
        state_path.write_text(json.dumps(state.to_dict(), indent=2) + "\n", encoding="utf-8")

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, _fmt: str, *_args: object) -> None:
            return

        def _send_json(self, obj: Any, status: int = HTTPStatus.OK) -> None:
            body = json.dumps(obj).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self) -> None:
            if self.path in ("/", "/index.html"):
                body = _INDEX_HTML.encode("utf-8")
                self.send_response(HTTPStatus.OK)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            if self.path == "/api/state":
                self._send_json(state.to_dict())
                return
            if self.path.startswith("/crops/"):
                crop_name = unquote(self.path[len("/crops/") :])
                if crop_name not in state.items:
                    self.send_error(HTTPStatus.NOT_FOUND)
                    return
                candidate = (crops_dir / crop_name).resolve()
                if candidate.parent != crops_dir or not candidate.is_file():
                    self.send_error(HTTPStatus.FORBIDDEN)
                    return
                data = candidate.read_bytes()
                self.send_response(HTTPStatus.OK)
                self.send_header("Content-Type", "image/png")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
                return
            self.send_error(HTTPStatus.NOT_FOUND)

        def do_POST(self) -> None:
            length = int(self.headers.get("Content-Length", "0"))
            raw = self.rfile.read(length) if length > 0 else b"{}"
            payload = json.loads(raw.decode("utf-8"))
            if self.path == "/api/merge":
                state.merge_groups(
                    list(payload.get("group_ids", [])),
                    target_person_id=str(payload.get("target_person_id", "")),
                )
                save_state()
                self._send_json({"ok": True})
                return
            if self.path == "/api/split":
                assigned = state.split_crop(
                    str(payload["crop_id"]),
                    new_person_id=payload.get("new_person_id"),
                )
                save_state()
                self._send_json({"ok": True, "person_id": assigned})
                return
            if self.path == "/api/exclude":
                state.set_crop_status(
                    str(payload["crop_id"]),
                    excluded=bool(payload["excluded"]),
                )
                save_state()
                self._send_json({"ok": True})
                return
            if self.path == "/api/export":
                save_state()
                res = export_labels(work_dir, state)
                self._send_json(res)
                return
            self.send_error(HTTPStatus.NOT_FOUND)

    server = ThreadingHTTPServer((host, port), Handler)
    print(f"B2.3 review tool listening on http://{host}:{port} (Ctrl+C to stop)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="B2.3 neutral person-crop sampler and review tool")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_sample = sub.add_parser(
        "sample", help="Sample ~150-200 person crops and pre-group by event/track"
    )
    p_sample.add_argument("--existing-crops-dir", type=Path, default=None)
    p_sample.add_argument("--detections-manifest", type=Path, default=None)
    p_sample.add_argument("--output-dir", type=Path, required=True)
    p_sample.add_argument("--target-count", type=int, default=180)
    p_sample.add_argument("--seed", type=int, default=42)

    p_serve = sub.add_parser("serve", help="Run localhost review tool (127.0.0.1 only)")
    p_serve.add_argument("--work-dir", type=Path, required=True)
    p_serve.add_argument("--host", default="127.0.0.1")
    p_serve.add_argument("--port", type=int, default=8766)

    p_export = sub.add_parser(
        "export", help="Export labels.json from saved review_state.json or pregrouped.json"
    )
    p_export.add_argument("--work-dir", type=Path, required=True)

    args = parser.parse_args(argv)
    if args.cmd == "sample":
        res = build_pregrouped_set(
            existing_crops_dir=args.existing_crops_dir,
            detections_manifest=args.detections_manifest,
            output_dir=args.output_dir,
            target_count=args.target_count,
            seed=args.seed,
        )
        print(
            json.dumps(
                {
                    "total_crops": res["total_crops"],
                    "initial_groups": res["initial_groups"],
                    "grouping_rule": res["grouping_rule"],
                },
                indent=2,
            )
        )
        return 0
    if args.cmd == "serve":
        run_server(args.work_dir, host=args.host, port=args.port)
        return 0
    if args.cmd == "export":
        state_path = args.work_dir / "review_state.json"
        pre_path = args.work_dir / "pregrouped.json"
        if state_path.is_file():
            state = ReviewState.from_dict(json.loads(state_path.read_text(encoding="utf-8")))
        else:
            state = ReviewState.from_pregrouped(json.loads(pre_path.read_text(encoding="utf-8")))
        out = export_labels(args.work_dir, state)
        print(json.dumps(out, indent=2))
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
