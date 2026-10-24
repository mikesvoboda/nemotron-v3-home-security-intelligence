"""Tests for scripts/uplevel/r309_label_tool.py — the [r309] labelling tool.

The tool must:
* serve the editor page, the pre-box COCO, the state, and ONLY frames the
  pre-box names (it is not a general file server for the host);
* persist POSTed corrections state;
* fold corrections over the pre-box COCO into a corrected export: deleted
  ids dropped, moved shapes/classes applied, added boxes appended with
  score 1.0, new classes appended to categories;
* never modify the pre-box file in place;
* refuse a missing root/prebox or a frame-less prebox (exit 2).

HTTP handlers are driven in-process by constructing the handler class and
calling its do_GET/do_POST/do_EXPORT with a fake request object, per
UR-69 spirit — the tests exercise the real handler code, not a mock.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from urllib.parse import quote

import pytest
from PIL import Image

# Add project root to path for imports - must be before script imports
PROJECT_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.uplevel import r309_label_tool as tool  # noqa: E402

# --- fixtures ---------------------------------------------------------------


def write_frame(path: Path, width: int = 64, height: int = 48) -> None:
    Image.new("RGB", (width, height), color=(64, 96, 64)).save(path)


@pytest.fixture()
def env(tmp_path: Path):
    """A pre-box COCO over two real frames, plus the tool's handler."""
    root = tmp_path / "foscam"
    snap = root / "Front Yard" / "snap"
    snap.mkdir(parents=True)
    day = "Front Yard/snap/MDAlarm_20260911-120000.jpg"
    night = "Front Yard/snap/MDAlarm_20260911-020000.jpg"
    write_frame(root / day)
    write_frame(root / night)
    prebox = {
        "info": {"description": "prebox"},
        "licenses": [],
        "categories": [{"id": 1, "name": "person"}, {"id": 2, "name": "vehicle"}],
        "images": [
            {"id": 1, "file_name": day, "width": 64, "height": 48, "stratum": "day"},
            {"id": 2, "file_name": night, "width": 64, "height": 48, "stratum": "night_ir"},
        ],
        "annotations": [
            {
                "id": 11,
                "image_id": 1,
                "category_id": 1,
                "bbox": [10, 10, 30, 30],
                "area": 900,
                "iscrowd": 0,
            },
            {
                "id": 12,
                "image_id": 1,
                "category_id": 2,
                "bbox": [40, 10, 20, 20],
                "area": 400,
                "iscrowd": 0,
            },
            {
                "id": 13,
                "image_id": 2,
                "category_id": 1,
                "bbox": [5, 5, 10, 10],
                "area": 100,
                "iscrowd": 0,
            },
        ],
    }
    pb_path = tmp_path / "prebox.coco.json"
    pb_path.write_text(json.dumps(prebox))
    state_path = tmp_path / "corrections.json"
    export_path = tmp_path / "corrected.coco.json"

    handler_cls = tool.make_handler(root, prebox, state_path, export_path)
    return type(
        "Env",
        (),
        {
            "root": root,
            "prebox": prebox,
            "pb_path": pb_path,
            "state_path": state_path,
            "export_path": export_path,
            "handler_cls": handler_cls,
            "tmp": tmp_path,
        },
    )


class FakeRequest:
    """The slice of BaseHTTPRequestHandler's self the handlers touch."""

    def __init__(self, path: str, body: bytes | None = None, headers: dict | None = None) -> None:
        self.path = path
        self.rfile = (body and __import__("io").BytesIO(body)) or None
        self.headers = headers or {}
        self.sent: list[tuple[int, bytes, str]] = []

    def send_response(self, code: int) -> None:
        self._code = code

    def send_header(self, name: str, value: str) -> None:
        pass

    def end_headers(self) -> None:
        pass

    def wfile_write(self, body: bytes) -> None:
        pass


def call(handler_cls, req: FakeRequest) -> FakeRequest:
    """Run a request through a real handler instance (no socket)."""
    h = handler_cls.__new__(handler_cls)
    h.path = req.path
    h.rfile = req.rfile
    h.headers = req.headers
    h.sent = []

    def _send(code: int, body: bytes, ctype: str) -> None:
        h.sent.append((code, body, ctype))

    h._send = _send
    h._send_json = lambda obj, code=200: _send(code, json.dumps(obj).encode(), "application/json")
    return h


def get(handler_cls, path: str) -> FakeRequest:
    req = FakeRequest(path)
    h = call(handler_cls, req)
    h.do_GET()
    req.result = h.sent
    return req


def post(handler_cls, path: str, body: dict) -> FakeRequest:
    payload = json.dumps(body).encode()
    req = FakeRequest(path, body=payload, headers={"Content-Length": str(len(payload))})
    h = call(handler_cls, req)
    h.do_POST()
    req.result = h.sent
    return req


def do_export(handler_cls) -> FakeRequest:
    req = FakeRequest("/export")
    h = call(handler_cls, req)
    h.do_EXPORT()
    req.result = h.sent
    return req


# --- tests ------------------------------------------------------------------


def test_serves_page_prebox_state_and_named_frames_only(env) -> None:
    """The four GET surfaces work; an unlisted frame path is refused."""
    page = get(env.handler_cls, "/")
    assert page.result[0][0] == 200
    assert b"frame corrections" in page.result[0][1]

    pb = get(env.handler_cls, "/prebox")
    assert json.loads(pb.result[0][1])["images"][0]["stratum"] == "day"

    st = get(env.handler_cls, "/state")
    assert json.loads(st.result[0][1]) == {}

    frame = get(env.handler_cls, "/frame/" + quote("Front Yard/snap/MDAlarm_20260911-120000.jpg"))
    assert frame.result[0][2].startswith("image/")

    # A real file on disk that the pre-box does NOT name is refused.
    sneaky = env.root / "Front Yard" / "snap" / "MDAlarm_20260911-999999.jpg"
    write_frame(sneaky)
    refused = get(env.handler_cls, "/frame/" + quote("Front Yard/snap/MDAlarm_20260911-999999.jpg"))
    assert refused.result[0][0] == 404


def test_post_persists_state(env) -> None:
    """POSTed corrections land in the state file and are served back."""
    state = {
        "Front Yard/snap/MDAlarm_20260911-120000.jpg": {"deleted": [12], "added": [], "moved": []}
    }
    resp = post(env.handler_cls, "/state", state)
    assert json.loads(resp.result[0][1]) == {"saved": True}
    assert json.loads(env.state_path.read_text()) == state
    served = json.loads(get(env.handler_cls, "/state").result[0][1])
    assert served == state


def test_export_folds_deletions_moved_and_added(env) -> None:
    """Deleted ids vanish; moved boxes take the new shape/class; added
    boxes land with score 1.0 and a new category; untouched frames pass
    through untouched."""
    day = "Front Yard/snap/MDAlarm_20260911-120000.jpg"
    night = "Front Yard/snap/MDAlarm_20260911-020000.jpg"
    post(
        env.handler_cls,
        "/state",
        {
            day: {
                "deleted": [12],
                "moved": [{"id": 11, "bbox": [8, 8, 32, 34], "cat": "person"}],
                "added": [{"bbox": [0, 0, 5, 5], "cat": "dog"}],
            },
        },
    )
    do_export(env.handler_cls)
    coco = json.loads(env.export_path.read_text())
    names = [c["name"] for c in coco["categories"]]
    assert names == ["person", "vehicle", "dog"]  # dog appended
    dog = next(c for c in coco["categories"] if c["name"] == "dog")
    anns = [a for a in coco["annotations"] if a["image_id"] == 1]
    assert [a["id"] for a in anns] == [1, 2]  # old 12 gone; ids renumbered
    assert anns[0]["bbox"] == [8, 8, 32, 34]  # moved shape applied
    assert anns[0]["category_id"] == 1
    assert anns[1]["category_id"] == dog["id"]  # added box
    assert anns[1]["area"] == 25
    night_anns = [a for a in coco["annotations"] if a["image_id"] == 2]
    assert len(night_anns) == 1 and night_anns[0]["bbox"] == [5, 5, 10, 10]
    # The pre-box file itself is untouched.
    assert json.loads(env.pb_path.read_text())["annotations"][0]["id"] == 11


def test_export_with_empty_state_is_the_prebox(env) -> None:
    """No corrections -> the corrected file mirrors the pre-box content
    (ids renumbered, description updated)."""
    do_export(env.handler_cls)
    coco = json.loads(env.export_path.read_text())
    assert len(coco["images"]) == 2
    assert len(coco["annotations"]) == 3
    assert "corrected" in coco["info"]["description"]


def test_refusals(env, capsys) -> None:
    """Missing root, missing prebox, frame-less prebox: exit 2 each."""
    for argv in (
        [
            "--root",
            str(env.tmp / "nope"),
            "--prebox",
            str(env.pb_path),
            "--state",
            str(env.tmp / "s.json"),
        ],
        [
            "--root",
            str(env.root),
            "--prebox",
            str(env.tmp / "nope.json"),
            "--state",
            str(env.tmp / "s.json"),
        ],
    ):
        with pytest.raises(SystemExit) as excinfo:
            sys.argv = ["r309_label_tool", *argv]
            tool.main()
        assert excinfo.value.code == 2
    empty = env.tmp / "empty.json"
    empty.write_text(json.dumps({"images": [], "categories": [], "annotations": []}))
    with pytest.raises(SystemExit) as excinfo:
        sys.argv = [
            "r309_label_tool",
            "--root",
            str(env.root),
            "--prebox",
            str(empty),
            "--state",
            str(env.tmp / "s.json"),
        ]
        tool.main()
    assert excinfo.value.code == 2
