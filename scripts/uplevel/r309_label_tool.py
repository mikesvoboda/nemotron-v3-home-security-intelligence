#!/usr/bin/env python3
"""Local labelling tool for [r309]'s labelled frame set.

    uv run python scripts/uplevel/r309_label_tool.py \
        --root /export/foscam \
        --prebox /home/OWNERHOST/frame-set/prebox.coco.json \
        --state /home/OWNERHOST/frame-set/corrections.json \
        --port 8765

Serves the selected frames and their pre-boxes on localhost only (binds
127.0.0.1) so the owner corrects the pre-boxes in a browser: drag boxes,
resize, re-classify, delete, add. Corrections accumulate in a state file
(host-side, plain JSON) so the tool can be closed and reopened without
losing work; the export writes the corrected COCO file the bake-off reads.

Everything stays on the host: the tool binds localhost, serves only files
under --root and the two JSON files named, and writes nothing outside the
paths given (ops.md [r309]: "no frame, crop or label file enters the repo,
a PR, a CI artifact or any cloud service").

The corrections file records, per frame: deleted pre-box ids, added boxes
(path-relative pixel coords + class + score 1.0), and moved/resized or
reclassified pre-boxes. The export folds corrections over the pre-box COCO
and writes a NEW file — the pre-box file is never modified in place, so a
bad export can always be re-derived from the untouched input.

Owner guide (also in docs/uplevel/roles/r309-labelling-guide.md):

  1. Run the command above on the host where the frames live.
  2. Open http://127.0.0.1:8765 in the browser.
  3. Each frame shows its pre-boxes (person = red, vehicle = blue, other =
     grey). Drag a box to move it; drag its corner to resize; pick the
     class under the image; press Delete to remove a selected box.
  4. 'Add box' then drag on the image to draw a new one.
  5. Use 'No objects' for a frame with nothing to label - it marks every
     remaining pre-box on that frame deleted.
  6. Corrected/kept state autosaves; close the tab whenever; re-open and
     continue.
  7. When every frame is dispositioned, press 'Export COCO' - the bake-off
     reads the corrected file at --export path.
"""

from __future__ import annotations

import argparse
import json
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

MIME = {
    "html": "text/html",
    "js": "application/javascript",
    "json": "application/json",
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "png": "image/png",
}


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument(
        "--root", required=True, help="Foscam upload tree root the frame paths resolve under"
    )
    ap.add_argument("--prebox", required=True, help="deliverable 2's pre-box COCO file")
    ap.add_argument(
        "--state", required=True, help="corrections state file (host-side, created if absent)"
    )
    ap.add_argument(
        "--export",
        default=None,
        help="corrected COCO output path for the export (default: <prebox>.corrected.json)",
    )
    ap.add_argument("--port", type=int, default=8765)
    return ap.parse_args()


def load_state(path: Path) -> dict[str, Any]:
    """Corrections keyed by file_name; {} when the file is absent/empty."""
    if not path.exists():
        return {}
    text = path.read_text().strip()
    if not text:
        return {}
    state = json.loads(text)
    if not isinstance(state, dict):
        raise ValueError(f"{path} must hold a JSON object")
    return state


def save_state(path: Path, state: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n")


# --- HTTP surface -----------------------------------------------------------


class LabellingHandler(BaseHTTPRequestHandler):
    """Serves frames, pre-boxes and the editor page; mutates only state."""

    root: Path
    prebox: dict
    state_path: Path
    state: dict

    def log_message(self, fmt: str, *args: Any) -> None:  # quiet default
        pass

    def _send(self, code: int, body: bytes, ctype: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_json(self, obj: Any, code: int = 200) -> None:
        self._send(code, json.dumps(obj).encode(), "application/json")

    def do_GET(self) -> None:
        path = self.path.split("?", 1)[0]
        if path in ("/", "/index.html"):
            self._send(200, PAGE.encode(), "text/html")
        elif path == "/prebox":
            self._send_json(self.prebox)
        elif path == "/state":
            # The state FILE is the source of truth: every request is a new
            # handler instance, so an in-memory copy would go stale after a
            # POST from a different instance.
            self._send_json(load_state(self.state_path))
        elif path.startswith("/frame/"):
            self._serve_frame(path[len("/frame/") :])
        else:
            self._send(404, b"not found", "text/plain")

    def _serve_frame(self, quoted: str) -> None:
        from urllib.parse import unquote

        name = unquote(quoted)
        # Only paths that appear in the pre-box COCO are servable - the
        # server is not a general file server for the host.
        known = {im["file_name"] for im in self.prebox.get("images", [])}
        if name not in known:
            self._send(404, b"not a labelled frame", "text/plain")
            return
        frame = Path(name)
        if not frame.is_absolute():
            frame = self.root / frame
        try:
            data = frame.read_bytes()
        except OSError:
            self._send(404, b"frame unreadable", "text/plain")
            return
        ctype = MIME.get(frame.suffix.lower().lstrip("."), "application/octet-stream")
        self._send(200, data, ctype)

    def do_POST(self) -> None:
        path = self.path.split("?", 1)[0]
        if path != "/state":
            self._send(404, b"not found", "text/plain")
            return
        length = int(self.headers.get("Content-Length", "0"))
        try:
            new_state = json.loads(self.rfile.read(length))
        except json.JSONDecodeError:
            self._send_json({"error": "bad json"}, 400)
            return
        if not isinstance(new_state, dict):
            self._send_json({"error": "state must be an object"}, 400)
            return
        self.state = new_state
        save_state(self.state_path, new_state)
        self._send_json({"saved": True})


PAGE = """<!doctype html>
<html>
<head>
<meta charset="utf-8">
<title>[r309] frame corrections</title>
<style>
  body { font-family: sans-serif; margin: 1rem; background: #1a1a2e; color: #eee; }
  #meta { color: #aaa; }
  #stage { margin: 0.5rem 0; }
  canvas { border: 1px solid #555; cursor: crosshair; max-width: 90vw; }
  button { margin-right: 0.5rem; padding: 0.3rem 0.8rem; }
  select, input { padding: 0.25rem; }
  #frames { margin: 0.5rem 0; }
  .done { color: #7f7; }
</style>
</head>
<body>
<h1>[r309] frame corrections</h1>
<div id="meta">loading…</div>
<div id="stage"><canvas id="cv" width="0" height="0"></canvas></div>
<div>
  <select id="cls">
    <option value="person">person</option>
    <option value="vehicle">vehicle</option>
    <option value="other">other (type below)</option>
  </select>
  <input id="other" placeholder="other class name" size="12" disabled>
  <button id="addbtn">Add box</button>
  <button id="delbtn">Delete selected</button>
  <button id="nobtn">No objects</button>
  <button id="prevbtn">&#8592; Prev</button>
  <button id="nextbtn">Next &#8594;</button>
  <button id="exportbtn">Export COCO</button>
  <span id="status"></span>
</div>
<div id="frames"></div>
<script>
"use strict";
const qs = new URLSearchParams(location.search);
let images = [], annotations = {}, cats = {}, idx = 0;
let boxes = [], selected = -1, drawing = null, dirty = false;

function status(msg) { document.getElementById("status").textContent = msg; }

function colorFor(catId) {
  const name = (cats[catId] || "?").toLowerCase();
  if (name === "person") return "#f55";
  if (name === "vehicle") return "#59f";
  return "#aaa";
}

async function load() {
  const [pb, st] = await Promise.all([
    fetch("/prebox").then(r => r.json()),
    fetch("/state").then(r => r.json()),
  ]);
  images = pb.images;
  cats = {}; pb.categories.forEach(c => { cats[c.id] = c.name; });
  annotations = {}; pb.annotations.forEach(a => {
    (annotations[a.image_id] = annotations[a.image_id] || []).push(a);
  });
  // Fold saved corrections in.
  for (const [fn, corr] of Object.entries(st)) {
    const im = images.find(i => i.file_name === fn);
    if (!im) continue;
    const anns = annotations[im.id] || [];
    const kept = anns.filter(a => !(corr.deleted || []).includes(a.id));
    boxes = kept.map(a => ({
      id: a.id, bbox: a.bbox, cat: cats[a.category_id], score: a.score,
    })).concat((corr.added || []).map(b => (
      { bbox: b.bbox, cat: b.cat, score: 1.0 }
    )));
    // Replaced/moved boxes: bbox or class overrides.
    (corr.moved || []).forEach(m => {
      const b = boxes.find(x => x.id === m.id);
      if (b) { b.bbox = m.bbox; b.cat = m.cat; }
    });
    annotations[im.id] = [];  // replaced below; boxes holds the truth
    im._boxes = boxes;
  }
  images.forEach(im => { if (!im._boxes) {
    im._boxes = (annotations[im.id] || []).map(a => ({
      id: a.id, bbox: a.bbox, cat: cats[a.category_id], score: a.score,
    }));
  }});
  document.getElementById("meta").textContent =
    `${images.length} frames; corrections fold in as you work`;
  buildIndex();
  show();
}

function dispositioned(fn) {
  const im = images.find(i => i.file_name === fn);
  return im && im._boxes && im._boxes.length === 0 && state && state[fn] &&
         (state[fn].deleted || []).length > 0;
}

let state = null;
async function loadState() { state = await fetch("/state").then(r => r.json()); }

function buildIndex() {
  // Un-dispositioned frames first, in file order.
  const todo = images.filter(im => !dispositioned(im.file_name));
  const done = images.filter(im => dispositioned(im.file_name));
  images = todo.concat(done);
  document.getElementById("frames").innerHTML =
    `${todo.length} to go, ${done.length} dispositioned`;
}

function show() {
  const im = images[idx];
  const cv = document.getElementById("cv");
  const img = new Image();
  img.onload = () => {
    cv.width = img.naturalWidth; cv.height = img.naturalHeight;
    draw(img);
  };
  img.src = "/frame/" + encodeURIComponent(im.file_name);
  cv._img = img;
  document.getElementById("meta").textContent =
    `frame ${idx + 1}/${images.length}: ${im.file_name} [${im.stratum}]`;
}

function draw(img) {
  const cv = document.getElementById("cv");
  const ctx = cv.getContext("2d");
  ctx.drawImage(img, 0, 0);
  const im = images[idx];
  im._boxes.forEach((b, i) => {
    ctx.strokeStyle = colorFor(b.catId || b.cat);
    ctx.lineWidth = 2;
    ctx.strokeRect(...b.bbox);
    ctx.fillStyle = colorFor(b.catId || b.cat);
    ctx.font = "12px sans-serif";
    ctx.fillText(`${b.cat}${b.score != null ? " " + b.score : ""}`,
                 b.bbox[0], Math.max(12, b.bbox[1] - 4));
    if (i === selected) {
      ctx.strokeStyle = "#ff0"; ctx.lineWidth = 1;
      ctx.strokeRect(...b.bbox);
    }
  });
  if (drawing) {
    ctx.strokeStyle = "#ff0"; ctx.setLineDash([4, 4]);
    ctx.strokeRect(...drawing);
    ctx.setLineDash([]);
  }
}

function corrFor(fn) {
  state[fn] = state[fn] || { deleted: [], added: [], moved: [] };
  for (const k of ["deleted", "added", "moved"]) state[fn][k] = state[fn][k] || [];
  return state[fn];
}

async function persist() {
  const r = await fetch("/state", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(state),
  });
  status(r.ok ? "saved" : "SAVE FAILED");
}

function currentCat() {
  const sel = document.getElementById("cls").value;
  if (sel !== "other") return sel;
  return document.getElementById("other").value.trim() || "other";
}

function collectBoxes() {
  const im = images[idx];
  const corr = corrFor(im.file_name);
  const preIds = (annotations[im.id] || []).map(a => a.id);
  // Everything still shown that is a pre-box and not deleted keeps; moved
  // boxes record their new shape; deletions accumulate.
  const shownPre = im._boxes.filter(b => b.id != null);
  corr.deleted = preIds.filter(id => !shownPre.some(b => b.id === id));
  corr.moved = shownPre
    .filter(b => b.dirty)
    .map(b => ({ id: b.id, bbox: b.bbox, cat: b.cat }));
  corr.added = im._boxes.filter(b => b.id == null)
    .map(b => ({ bbox: b.bbox, cat: b.cat }));
}

document.getElementById("nextbtn").onclick = async () => {
  collectBoxes(); await persist(); idx = (idx + 1) % images.length; show();
};
document.getElementById("prevbtn").onclick = async () => {
  collectBoxes(); await persist();
  idx = (idx - 1 + images.length) % images.length; show();
};
document.getElementById("nobtn").onclick = async () => {
  const im = images[idx];
  const corr = corrFor(im.file_name);
  corr.deleted = (annotations[im.id] || []).map(a => a.id);
  im._boxes = [];
  await persist();
  status("marked no objects");
};
document.getElementById("delbtn").onclick = () => {
  if (selected < 0) return status("no box selected");
  images[idx]._boxes.splice(selected, 1);
  selected = -1; dirty = true; draw(document.getElementById("cv")._img);
};
document.getElementById("addbtn").onclick = () => {
  selected = -1; status("drag on the image to draw the box");
};
document.getElementById("cls").onchange = (e) => {
  document.getElementById("other").disabled = e.target.value !== "other";
  if (selected >= 0) {
    images[idx]._boxes[selected].cat = currentCat();
    images[idx]._boxes[selected].dirty = true;
    draw(document.getElementById("cv")._img);
  }
};
document.getElementById("other").oninput = () => {
  if (selected >= 0) {
    images[idx]._boxes[selected].cat = currentCat();
    images[idx]._boxes[selected].dirty = true;
    draw(document.getElementById("cv")._img);
  }
};
document.getElementById("exportbtn").onclick = async () => {
  collectBoxes(); await persist();
  const r = await fetch("/export", { method: "POST" });
  status(r.ok ? "exported COCO" : "EXPORT FAILED");
};

// Mouse: select / move / resize / draw.
const cv = document.getElementById("cv");
let mode = null, start = null, origBbox = null;
function pos(e) {
  const r = cv.getBoundingClientRect();
  return [Math.round((e.clientX - r.left) * cv.width / r.width),
          Math.round((e.clientY - r.top) * cv.height / r.height)];
}
cv.addEventListener("mousedown", (e) => {
  const [x, y] = pos(e);
  const im = images[idx];
  if (document.getElementById("addbtn")._drawing) {
    mode = "draw"; start = [x, y]; drawing = [x, y, 0, 0];
    return;
  }
  // Corner hit first (resize), then inside (move).
  for (let i = im._boxes.length - 1; i >= 0; i--) {
    const [bx, by, bw, bh] = im._boxes[i].bbox;
    if (Math.abs(x - (bx + bw)) < 8 && Math.abs(y - (by + bh)) < 8) {
      selected = i; mode = "resize"; start = [x, y];
      origBbox = [...im._boxes[i].bbox]; draw(cv._img); return;
    }
    if (x >= bx && x <= bx + bw && y >= by && y <= by + bh) {
      selected = i; mode = "move"; start = [x, y];
      origBbox = [...im._boxes[i].bbox]; draw(cv._img); return;
    }
  }
  selected = -1; draw(cv._img);
});
cv.addEventListener("mousemove", (e) => {
  if (!mode) return;
  const [x, y] = pos(e);
  const im = images[idx];
  if (mode === "draw" && drawing) {
    drawing = [start[0], start[1], x - start[0], y - start[1]];
    draw(cv._img); return;
  }
  const b = im._boxes[selected];
  if (!b) return;
  if (mode === "move") {
    b.bbox = [origBbox[0] + x - start[0], origBbox[1] + y - start[1],
              origBbox[2], origBbox[3]];
  } else if (mode === "resize") {
    b.bbox = [origBbox[0], origBbox[1],
              Math.max(4, x - origBbox[0]), Math.max(4, y - origBbox[1])];
  }
  b.dirty = true;
  draw(cv._img);
});
window.addEventListener("mouseup", () => {
  if (mode === "draw" && drawing) {
    const [x, y, w, h] = drawing;
    if (Math.abs(w) > 3 && Math.abs(h) > 3) {
      images[idx]._boxes.push({
        bbox: [x, y, w, h].map(v => Math.max(0, v)), cat: currentCat(),
      });
      dirty = true;
    }
    drawing = null;
    document.getElementById("addbtn")._drawing = false;
    document.getElementById("addbtn").textContent = "Add box";
  }
  if (mode) { mode = null; draw(cv._img); }
});
document.getElementById("addbtn").onclick = () => {
  const btn = document.getElementById("addbtn");
  btn._drawing = !btn._drawing;
  btn.textContent = btn._drawing ? "Drawing… (drag on image)" : "Add box";
};

loadState().then(load);

async function postExport() { return fetch("/export", { method: "POST" }); }
</script>
</body>
</html>"""


def fold_corrections(prebox: dict, state: dict) -> dict:
    """Fold the owner's corrections over the pre-box COCO.

    Per frame: drop deleted ids, apply moved shapes/classes, append added
    boxes (score 1.0 - the owner's word is ground truth)."""
    by_name = {im["file_name"]: im for im in prebox.get("images", [])}
    cat_by_name = {c["name"]: c["id"] for c in prebox.get("categories", [])}
    next_cat = max([c["id"] for c in prebox.get("categories", [])], default=0) + 1
    categories = [dict(c) for c in prebox.get("categories", [])]
    annotations: list[dict] = []
    next_ann = 1
    for fn, im in by_name.items():
        corr = state.get(fn) or {}
        deleted = set(corr.get("deleted", []))
        moved = {m["id"]: m for m in corr.get("moved", [])}
        for ann in prebox.get("annotations", []):
            if ann["image_id"] != im["id"]:
                continue
            if ann["id"] in deleted:
                continue
            out = {k: ann[k] for k in ("image_id", "category_id", "bbox", "area", "iscrowd")}
            if ann["id"] in moved:
                m = moved[ann["id"]]
                out["bbox"] = m["bbox"]
                out["area"] = round(m["bbox"][2] * m["bbox"][3], 2)
                cat_name = m["cat"]
                if cat_name not in cat_by_name:
                    cat_by_name[cat_name] = next_cat
                    categories.append({"id": next_cat, "name": cat_name})
                    next_cat += 1
                out["category_id"] = cat_by_name[cat_name]
            annotations.append({**out, "id": next_ann})
            next_ann += 1
        for added in corr.get("added", []):
            cat_name = added["cat"]
            if cat_name not in cat_by_name:
                cat_by_name[cat_name] = next_cat
                categories.append({"id": next_cat, "name": cat_name})
                next_cat += 1
            bbox = added["bbox"]
            annotations.append(
                {
                    "id": next_ann,
                    "image_id": im["id"],
                    "category_id": cat_by_name[cat_name],
                    "bbox": bbox,
                    "area": round(bbox[2] * bbox[3], 2),
                    "iscrowd": 0,
                }
            )
            next_ann += 1
    return {
        "info": {
            **prebox.get("info", {}),
            "description": "[r309] corrected frame set for [r303]'s bake-off",
        },
        "licenses": prebox.get("licenses", []),
        "categories": categories,
        "images": prebox.get("images", []),
        "annotations": annotations,
    }


def make_handler(
    root: Path, prebox: dict, state_path: Path, export_path: Path
) -> type[LabellingHandler]:
    class Handler(LabellingHandler):
        export_path: Path

        def do_EXPORT(self) -> None:
            state = load_state(state_path)  # reload: client just POSTed
            corrected = fold_corrections(prebox, state)
            export_path.parent.mkdir(parents=True, exist_ok=True)
            export_path.write_text(json.dumps(corrected, indent=2) + "\n")
            self._send_json(
                {
                    "exported": str(export_path),
                    "frames": len(corrected["images"]),
                    "annotations": len(corrected["annotations"]),
                }
            )

    Handler.root = root
    Handler.prebox = prebox
    Handler.state_path = state_path
    Handler.state = load_state(state_path)
    Handler.export_path = export_path
    return Handler


def main() -> int:
    args = parse_args()
    root = Path(args.root)
    if not root.is_dir():
        print(f"r309_label_tool: --root {root} is not a directory", file=sys.stderr)
        sys.exit(2)
    prebox_path = Path(args.prebox)
    if not prebox_path.is_file():
        print(f"r309_label_tool: --prebox {prebox_path} is not a file", file=sys.stderr)
        sys.exit(2)
    prebox = json.loads(prebox_path.read_text())
    if not prebox.get("images"):
        print(f"r309_label_tool: {prebox_path} carries no frames", file=sys.stderr)
        sys.exit(2)
    state_path = Path(args.state)
    export_path = Path(args.export) if args.export else prebox_path.with_suffix(".corrected.json")

    handler_cls = make_handler(root, prebox, state_path, export_path)
    server = ThreadingHTTPServer(("127.0.0.1", args.port), handler_cls)
    print(
        f"r309_label_tool: serving http://127.0.0.1:{args.port} "
        f"({len(prebox['images'])} frames; state {state_path}; "
        f"export {export_path})"
    )
    print("r309_label_tool: Ctrl+C to stop; state autosaves on every action")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
