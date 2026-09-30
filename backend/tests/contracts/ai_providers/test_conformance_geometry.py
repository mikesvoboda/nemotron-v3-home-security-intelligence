"""WP8.3 conformance suite — cluster GEOMETRY AND ENCODING (G1-G9).

Per-property module toward ``backend/tests/contracts/ai_providers/test_conformance.py``
(plan docs/superpowers/plans/2026-09-19-swap-readiness-72h.md §WP8.3, "Geometry
and encoding").

R8 SLICE S3 STATE (2026-09-29, five owner rulings). This cluster was drafted
against a five-adapter gateway and a Florence provider whose bbox conventions
were its reason for existing: LIST-of-FLOATS ``[x1,y1,x2,y2]`` on detect and
EIGHT flattened floats (quad corners) on OCR-with-regions, against the yolo
family's dict-of-INTS ``{x,y,width,height}``. S3 swept Florence (ruling 1) and
CLIP (ruling 5) — adapter, client, serving dirs, Triton dirs, registry rows —
so the second half of that pair is GONE and this file is retargeted around
what survives:

  * ``/yolo26`` (ai.gateway.adapters.yolo26) and ``/enrich-lt``
    (ai.gateway.adapters.enrichment_light) are the only mounted adapters
    (ai/gateway/main.py:269-273), so ``GATEWAY_MOUNTS`` is READ from that file
    instead of being hand-listed here — the hand-listed five-mount table is
    exactly what made every gateway-driven test in this file ERROR (the fixture
    imported ``ai.gateway.adapters.clip``, which no longer exists), and a table
    copied from a memory of main.py rots the next time main.py changes.
  * The round-vs-truncate split (G1a/G1b) is fully alive: the gateway yolo
    adapter still emits ``round()`` and the native server still emits ``int()``
    truncation, so the discriminating canned row survives with new numbers.
  * The list-vs-dict / arity-blindness properties (G2) retarget onto the light
    lane, whose request model accepts BOTH bbox spellings with NO arity
    constraint at all — a strictly stronger version of the same hazard than the
    committed snapshots' ``array of number`` ever was.
  * The four-coord-vs-eight-coord Florence arity lesson and the zero-validation
    / absent-score client lesson cannot retarget (no surviving op carries a
    list-of-floats bbox and no surviving module hard-codes score=1.0): they are
    TOMBSTONED here, each with its own geometry angle, its own absence
    assertions and its own non-vacuity. The arity lesson is ALREADY recorded at
    test_fake_provider.py::test_florence_list_bbox_and_ocr_quads_retired_with_the_provider
    from the GENERATOR side ("a fake emitting 4 there trains consumers on the
    wrong arity"); this file owns the CONSUMER side — a reader that takes
    ``bbox[0]`` as x mis-reads the surviving dict-of-ints as a corner pair, and
    the surviving request schema will bind a 3-, 4- or 8-length list alike.
    Neither record restates the other.

Verdict legend for the inline comments: this file used to carry PREDICTED
tags because it was drafted unrun. Every assertion below has since been RUN
against the shipped tree, so the predictions are gone; where a property is a
CHARACTERIZATION pin (it pins shipped behavior without endorsing it — G5's
false invariant, G7's unclamped confidence, G4's fourth spelling) the docstring
says so, because "pinning, not fixing" is the whole point of those tests.

No xfail / skip / importorskip anywhere (goal rule). Nothing in this file is
skipped and nothing is quarantined: a property that lost its subject is
tombstoned (states the hazard, asserts the absence, proves non-vacuity), never
suppressed.
"""

from __future__ import annotations

import ast
import io
import json
import math
import re
from contextlib import ExitStack
from importlib import import_module
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, patch

import numpy as np
import pytest
from backend.ai_contract.operations import OPERATION_IDS, OPERATIONS
from backend.ai_contract.provider import operations_for_slot
from httpx import ASGITransport, AsyncClient
from PIL import Image

REPO_ROOT = Path(__file__).resolve().parents[4]
SCHEMA_DIR = REPO_ROOT / "backend" / "ai_contract" / "schemas"
GOLDEN_DIR = REPO_ROOT / "backend/tests/contracts/ai_providers/golden/payloads"

YOLO_SERVER_SRC = REPO_ROOT / "ai" / "yolo26" / "model.py"  # SURVIVES the S3 sweep
GATEWAY_YOLO_SRC = REPO_ROOT / "ai" / "gateway" / "adapters" / "yolo26.py"
LIGHT_ADAPTER_SRC = REPO_ROOT / "ai" / "gateway" / "adapters" / "enrichment_light.py"
GATEWAY_MAIN_SRC = REPO_ROOT / "ai" / "gateway" / "main.py"

# The production mount table, READ from production main instead of hand-listed.
# The drafted form was a five-row literal (yolo26 / clip / florence /
# enrichment / enrich-lt); three of its five modules are swept, so the fixture
# that consumed it raised ModuleNotFoundError and every gateway-driven test in
# this file ERRORed — a hand-copied table's failure mode, not a coincidence.
# Reading main.py's own ``from … import router as X`` + ``include_router(X,
# prefix=…)`` pairs means a fourth adapter is picked up automatically and a
# renamed prefix cannot quietly drift out of this suite's driving shape.
# Cost: one read_text + two regex passes, ~0 ms (ai/gateway/main.py is 30 KB).
_MOUNT_RE = re.compile(r"app\.include_router\((\w+),\s*prefix=\"([^\"]+)\"")
_IMPORT_ALIAS_RE = re.compile(r"from (ai\.gateway\.adapters\.\w+) import router as (\w+)")


def _production_mounts() -> tuple[tuple[str, str], ...]:
    """``((module, prefix), …)`` exactly as production mounts them."""
    src = GATEWAY_MAIN_SRC.read_text(encoding="utf-8")
    # findall yields (module, alias); the lookup below is by alias.
    alias_to_module = {alias: module for module, alias in _IMPORT_ALIAS_RE.findall(src)}
    assert alias_to_module, f"{GATEWAY_MAIN_SRC.name} no longer imports adapter routers"
    mounts = [(alias_to_module[alias], prefix) for alias, prefix in _MOUNT_RE.findall(src)]
    assert mounts, f"{GATEWAY_MAIN_SRC.name} no longer include_router()s anything"
    return tuple(mounts)


GATEWAY_MOUNTS = _production_mounts()
# Per-module patch targets: each adapter module-level from-import is its own
# name, so patching one leaves the others on real gRPC (dossier Q2). The rule
# did not shrink because the count did — it is DERIVED from GATEWAY_MOUNTS, so
# a mount added to main.py is a patch target here without anyone remembering.
GATEWAY_PATCH_TARGETS = tuple(f"{module}.get_triton_client" for module, _ in GATEWAY_MOUNTS)


def _read(rel: str | Path) -> str:
    path = Path(rel) if isinstance(rel, Path) else REPO_ROOT / rel
    return path.read_text(encoding="utf-8")


def _source_corpus(*roots: str) -> list[Path]:
    """Non-test .py files under the given repo roots — the census used by the
    G4/G6 "who emits this spelling" pins. Deliberately NOT a whole-tree walk:
    the WP1.3 duration budget already bit this tier once for parsing the tree
    inside one test id (ledger item 49), and every claim here only needs the
    shipped AI + contract surface (~1.9k files read in ~0.5s locally, and the
    audit classifies backend/tests/contracts/* as integration anyway)."""
    files: list[Path] = []
    for root in roots:
        files += [
            p
            for p in (REPO_ROOT / root).rglob("*.py")
            if "__pycache__" not in p.parts
            and "/tests/" not in str(p.relative_to(REPO_ROOT))
            and "test" not in p.name
        ]
    return files


# ---------------------------------------------------------------------------
# Request-shape helpers (fake-driven), same contract as test_fake_provider.py
# ---------------------------------------------------------------------------


def _request_kwargs(op_id: str) -> dict[str, Any]:
    """Drive requests from the WP7.2 goldens where a request example exists.

    The multipart endpoints (the yolo family) declare an ``UploadFile``, so a
    JSON body cannot bind them; the golden's string payload stands for the
    upload. Ops with no committed request snapshot get a neutral JSON body —
    the fake ignores content and is seeded by op id."""
    if OPERATIONS[op_id].method == "GET":
        return {}
    example = GOLDEN_DIR / f"{op_id}.request.example.json"
    if example.exists():
        payload = json.loads(example.read_text(encoding="utf-8"))
        if isinstance(payload, str):
            return {"files": [("file", ("f.jpg", payload.encode(), "image/jpeg"))]}
        if payload == {}:
            return {}
        return {"json": payload}
    return {"json": {"image_base64": "ZmFrZS1pbWFnZQ=="}}


def _png_bytes(width: int = 640, height: int = 640) -> bytes:
    """A real PNG (the gateway decodes uploads with PIL). 640x640 gives
    letterbox scale=1, pad=0 (ai/gateway/utils.py:202-207), so post-NMS coords
    pass through the reverse-letterbox untouched and round() output is exactly
    predictable; a non-square frame is the OTHER arm (G8)."""
    buf = io.BytesIO()
    Image.new("RGB", (width, height), (7, 23, 41)).save(buf, format="PNG")
    return buf.getvalue()


def _png_b64(width: int = 640, height: int = 640) -> str:
    import base64

    return base64.b64encode(_png_bytes(width, height)).decode("ascii")


# ---------------------------------------------------------------------------
# Canned Triton rows
# ---------------------------------------------------------------------------
# Post-NMS row format [x1, y1, x2, y2, conf, cls] in 640-space
# (ai/gateway/adapters/yolo26.py:172). Row A is a fractional discriminator for
# round() vs int(); row B is the SAME box fed to BOTH surviving lanes (as the
# matching cxcywh threat row below) so G8's letterbox/clamp split is measured,
# not asserted from a reading of the code.
# (1, N, 6): the adapter strips the batch dim itself (preds = output[0],
# adapters/yolo26.py:152) and then iterates rows.
GATEWAY_CANNED_ROWS = np.array(
    [
        [
            [200.6, 240.4, 320.5, 300.9, 0.9, 0],  # A: person, fractional
            [100.0, 340.0, 500.0, 740.0, 0.5, 1],  # B: bicycle, overflows the frame
        ]
    ],
    dtype=np.float64,
)
# Row A through round() at scale=1/pad=0: x=round(200.6)=201, y=round(240.4)=240,
# width=round(119.9)=120, height=round(60.5)=60 (banker's nearest-even).
ROW_A_ROUNDED = {"x": 201, "y": 240, "width": 120, "height": 60}
# The same row through the SERVER's int(): x=200, y=240, width=int(119.9)=119,
# height=60. The ±1px divergence on x and width is the whole G1b point.
ROW_A_TRUNCATED = {"x": 200, "y": 240, "width": 119, "height": 60}
# Row B in 640-space on a 640x640 frame, yolo-side: bx2 = min(640, 740) clamps
# the bottom edge, so height = 640-340 = 300 while the raw box is 400 tall.
ROW_B_YOLO_SQUARE = {"x": 100, "y": 340, "width": 400, "height": 300}
# Row B on the light lane, same frame: no letterbox, no clamp, so the SAME
# tensor-space box ships 400 tall and reaches 340+400 = 740 px.
ROW_B_LIGHT_SQUARE = {"x": 100, "y": 340, "width": 400, "height": 400}
# Row B in the SAME tensor space on a 1280x720 upload, yolo-side: scale 0.5 /
# pad_y 140 doubles x and width (x2=1000 is inside 1280, so no horizontal
# clamp) and doubles y, but y2=1200 overshoots 720 so the bottom clamps and
# height is 720-400=320. Measured, not computed.
ROW_B_YOLO_WIDE = {"x": 200, "y": 400, "width": 800, "height": 320}

# Threat lane output: shape (1, 8, 20), rows = cx, cy, w, h, then one score per
# THREAT_CLASSES entry (adapters/enrichment_light.py:74-118). Column 0 carries
# fractional cxcywh so the light lane's own round() is visible; column 1 is
# row B re-expressed as cxcywh (cx=300, cy=540); column 2 sits under the 0.25
# threshold and must vanish; column 3 carries an out-of-band confidence of 1.7
# to pin the clamp asymmetry (G7).
THREAT_COLUMNS = {
    0: (300.9, 200.9, 120.6, 60.6, 1, 0.75),
    1: (300.0, 540.0, 400.0, 400.0, 0, 0.5),
    2: (500.0, 400.0, 20.0, 20.0, 3, 0.10),
    3: (200.0, 300.0, 40.0, 40.0, 2, 1.7),
}
# Column 0 on the light lane: x=round(300.9-60.3)=round(240.6)=241 where the
# server-side int() idiom would have said 240 (and where the yolo adapter's
# round() says 241 too — the light lane is a SECOND round()-side path).
LIGHT_ROW_A_ROUNDED = {"x": 241, "y": 171, "width": 121, "height": 61}
LIGHT_ROW_A_TRUNCATED = {"x": 240, "y": 170, "width": 120, "height": 60}
REID_VECTOR = np.arange(1, 513, dtype=np.float32)  # 512 dims, NOT unit-norm


def _threat_output(*, all_below_threshold: bool = False) -> np.ndarray:
    """The threat lane's (1, 8, N) matrix. ``all_below_threshold`` must drop
    EVERY score row of EVERY candidate column — the postprocessor's argmax is
    per-candidate, so zeroing a subset still lets the untouched rows survive
    (a "no threats" matrix that leaves one 1.7 column in is not an empty
    detection set; the first draft of the zero arm made exactly that mistake
    and pinned a one-row body as if it were the empty one)."""
    out = np.zeros((1, 8, 20), dtype=np.float32)
    for col, (cx, cy, w, h, cls, conf) in THREAT_COLUMNS.items():
        score = 0.05 if all_below_threshold else conf
        row = [cx, cy, w, h] + [score if i == cls else 0.0 for i in range(4)]
        out[0][:, col] = row
    return out


def _triton_mock() -> AsyncMock:
    """One mock serving BOTH surviving lanes by ``model_name``.

    The shared-mock shape is load-bearing, not lazy: the same object answers
    every patched adapter, so a route that reached the wrong Triton model name
    (or reached Triton at all, for a route that should not) raises here instead
    of returning someone else's tensor. ``reid`` returns a deliberately
    NON-unit vector so the adapter's own L2 normalization is what the unit-norm
    assertions actually test."""

    async def _infer(*, model_name: str, inputs: Any, outputs: Any) -> dict[str, Any]:
        if model_name == "yolo26":
            return {"output0": GATEWAY_CANNED_ROWS}
        if model_name == "threat":
            return {"output0": _threat_output(all_below_threshold=_below[0])}
        if model_name == "reid":
            return {"embedding": REID_VECTOR[np.newaxis, :]}
        raise AssertionError(f"unexpected Triton model_name {model_name!r}")

    _below = [False]
    triton = AsyncMock()
    triton.infer = AsyncMock(side_effect=_infer)
    triton.is_model_ready = AsyncMock(return_value=True)
    triton.get_model_metadata = AsyncMock(return_value={"outputs": [{"name": "output0"}]})
    triton.zero_threat = lambda: _below.__setitem__(0, True)  # type: ignore[attr-defined]
    triton.unzero_threat = lambda: _below.__setitem__(0, False)  # type: ignore[attr-defined]
    return triton


@pytest.fixture(scope="module")
def fake_app():
    from backend.ai_contract.fake import create_fake_app

    return create_fake_app()


@pytest.fixture
async def fake_client(fake_app):
    transport = ASGITransport(app=fake_app)
    async with AsyncClient(transport=transport, base_url="http://fake") as client:
        yield client


@pytest.fixture(scope="module")
def gateway_app():
    """Every adapter production mounts, on one app, at its production prefix —
    so registry op paths like /yolo26/detect resolve (Operation.path already
    carries the prefix)."""
    from fastapi import FastAPI

    app = FastAPI(title="WP8.3 geometry conformance gateway app")
    for module, prefix in GATEWAY_MOUNTS:
        app.include_router(import_module(module).router, prefix=prefix)
    return app


@pytest.fixture
def gateway_triton() -> AsyncMock:
    return _triton_mock()


@pytest.fixture
async def gateway_client(gateway_app, gateway_triton):
    """Patch EVERY mounted adapter's get_triton_client name. The property the
    multi-target rule protects has not shrunk with the count: patching one
    leaves the other on real gRPC."""
    with ExitStack() as stack:
        for target in GATEWAY_PATCH_TARGETS:
            stack.enter_context(patch(target, return_value=gateway_triton))
        transport = ASGITransport(app=gateway_app)
        async with AsyncClient(transport=transport, base_url="http://gateway") as client:
            yield client


# ---------------------------------------------------------------------------
# Shared geometry helpers (the pins read them, so the semantics are stated once)
# ---------------------------------------------------------------------------


def _bbox_emitter_names(src: str) -> list[tuple[int, str]]:
    """Every ``{"x": …, "y": …, "width": …, "height": …}`` literal's value call,
    as (line, function-name). AST, not text: a reformatted dict literal must not
    silently un-pin a rounding-vs-truncation characterization, and a bare
    ``src.count('"x": round(')`` is format-sensitive in exactly the way the
    drafted version of this file was."""
    out: list[tuple[int, str]] = []
    for node in ast.walk(ast.parse(src)):
        if not isinstance(node, ast.Dict):
            continue
        keys = [k.value for k in node.keys if isinstance(k, ast.Constant)]
        if not {"x", "y", "width", "height"} <= set(keys):
            continue
        value = node.values[keys.index("x")]
        if isinstance(value, ast.Call) and isinstance(value.func, ast.Name):
            name = value.func.id
        else:
            name = ast.unparse(value)
        out.append((node.lineno, name))
    return sorted(out)


def _yolo_dict_from_fake(body: dict[str, Any]) -> dict[str, int]:
    dets = body["detections"]
    assert dets, "fake must emit detections, not an empty list"
    return dets[0]["bbox"]


# ---------------------------------------------------------------------------
# G1a — yolo26 bbox: dict-of-INTS {x,y,width,height}, absolute px, int() TRUNCATION
# ---------------------------------------------------------------------------


class TestG1AYoloDictOfInts:
    async def test_g1a_fake_yolo_bbox_is_dict_of_absolute_ints(self, fake_client) -> None:
        r = await fake_client.post("/yolo26/detect", **_request_kwargs("yolo26_detect"))
        assert r.status_code == 200
        body = r.json()
        dets = body["detections"]
        assert dets, "fake must emit detections, not an empty list"
        for d in dets:
            b = d["bbox"]
            # source: backend/ai_contract/fake/generators.py:195-210
            # (_yolo_bbox_dict, dict of ints in the 640x480 fake frame,
            # _FAKE_FRAME at :141). Re-pinned provider-agnostically against the
            # conformance suite's own copy of the same contract.
            assert set(b) == {"x", "y", "width", "height"}
            assert all(type(v) is int for v in b.values()), "dict-of-INTS, not floats"
            # absolute px, top-left origin, in-frame: the discriminability
            # WITHOUT frame-size luck — an int() truncated from a normalized
            # [0,1] provider box would fail width >= 1 (see G6).
            assert b["x"] >= 0 and b["y"] >= 0
            assert b["width"] >= 1 and b["height"] >= 1
            assert b["x"] + b["width"] <= body["image_width"]
            assert b["y"] + b["height"] <= body["image_height"]

    def test_g1a_yolo_server_emit_block_is_int_truncation(self) -> None:
        """Native per-model server cannot boot in-sandbox (GPU/weights) — pin
        the shipped emission by AST + pure expression semantics."""
        src = _read(YOLO_SERVER_SRC)
        # source: ai/yolo26/model.py:1100 (x1, y1, x2, y2 = box.xyxy[0].tolist())
        # and :1106-1109 ({"x": int(x1), …, "width": int(x2 - x1), …}). The
        # WP8.3 dossier cites 1399/1406-1409: the file has since shrunk by ~300
        # lines and those cites drifted UPWARD-to-lower by ~300; the strings are
        # still exactly present, which is why the pin reads the emitter rather
        # than a remembered line number.
        assert "x1, y1, x2, y2 = box.xyxy[0].tolist()" in src
        emitters = _bbox_emitter_names(src)
        assert [fn for _, fn in emitters] == ["int"], emitters
        assert '"width": int(x2 - x1),' in src
        assert '"height": int(y2 - y1),' in src
        # Non-vacuity: the emitter walk is not reading an empty file, and the
        # server's SECURITY_CLASSES vocabulary filter survives S3 alongside it.
        assert len(src.splitlines()) > 1000
        assert "SECURITY_CLASSES" in src

    def test_g1a_truncation_and_rounding_split_on_fractional_coords(self) -> None:
        """Pure semantics, no I/O: on ANY fractional coord the two shipped paths
        disagree — which is why the suite pins each path to its own truth and
        never asserts cross-provider value-equality on fractional input."""
        # source: server int() ai/yolo26/model.py:1106-1109 vs gateway round()
        # ai/gateway/adapters/yolo26.py:204-207 (post-NMS) and :321-324 (pre-NMS).
        # fake is GREEN-by-agreement: it emits only ints (generators.py:195) so
        # it is truncation-indistinguishable.
        assert int(200.6) == 200  # truncation toward zero
        assert round(200.6) == 201  # rounding to nearest
        assert int(320.5 - 200.6) == 119  # 119.899... truncates to 119
        assert round(320.5 - 200.6) == 120  # while round() gives 120
        assert round(60.5) == 60  # banker's rounding (nearest-even) — shipped behavior
        assert int(60.5) == 60


# ---------------------------------------------------------------------------
# G1b — gateway yolo adapter uses round(): shipped-correct for the gateway path
# ---------------------------------------------------------------------------


class TestG1BGatewayRounds:
    def test_g1b_gateway_adapter_emit_block_is_round(self) -> None:
        src = _read(GATEWAY_YOLO_SRC)
        # source: ai/gateway/adapters/yolo26.py:204-207 (_postprocess_post_nms,
        # def :164) and the identical pre-NMS twin at :321-324 (def :215).
        # Characterization pinned as shipped-correct for the gateway path; the
        # divergence against the server's int() is G1a's, not a defect here.
        emitters = _bbox_emitter_names(src)
        assert [fn for _, fn in emitters] == ["round", "round"], emitters
        # Non-vacuity: BOTH post-processors are still in the file, so "round in
        # two places" is a real census and not one emitter counted twice.
        assert "_postprocess_post_nms" in src and "_postprocess_pre_nms" in src
        assert src.count("def _postprocess") == 3  # dispatcher + the two twins

    async def test_g1b_gateway_http_path_emits_rounded_dict_bbox(self, gateway_client) -> None:
        """Full gateway drive: multipart upload -> patched Triton canned rows ->
        adapter output. Pins the ADAPTER behavior as shipped-correct for the
        gateway provider path."""
        r = await gateway_client.post(
            "/yolo26/detect", files={"file": ("frame.png", _png_bytes(), "image/png")}
        )
        assert r.status_code == 200, r.text
        body = r.json()
        # Row B is below the letterbox content band only for non-square frames;
        # on a square frame BOTH canned rows survive, which is the fixture's
        # shape (and the reason len() is 2 rather than the drafted 1).
        dets = body["detections"]
        assert len(dets) == len(GATEWAY_CANNED_ROWS[0])
        d = dets[0]
        # source: canned row A [200.6, 240.4, 320.5, 300.9, 0.9, 0] through
        # _postprocess_post_nms (adapters/yolo26.py:164,204-207) on a 640x640
        # upload => scale=1, pad=0 (ai/gateway/utils.py:202-207); cls 0 = COCO
        # "person" (adapters/yolo26.py:42+).
        assert d["class"] == "person"
        assert d["bbox"] == ROW_A_ROUNDED
        assert all(type(v) is int for v in d["bbox"].values())
        assert body["image_width"] == 640 and body["image_height"] == 640

    async def test_g1b_round_vs_truncate_splits_the_two_shipped_paths(self, gateway_client) -> None:
        """Same fractional xyxy, both shipped semantics: the gateway adapter and
        the native server expression DIFFER on x and width. A cross-provider
        value-equality assertion on fractional input would be RED against
        exactly one provider — the naive-pin trap — so each side gets its own
        equality and the divergence itself is the third assertion."""
        r = await gateway_client.post(
            "/yolo26/detect", files={"file": ("frame.png", _png_bytes(), "image/png")}
        )
        assert r.status_code == 200
        gateway_bbox = r.json()["detections"][0]["bbox"]
        x1, y1, x2, y2 = (float(v) for v in GATEWAY_CANNED_ROWS[0][0][:4])
        server_semantics = {
            "x": int(x1),
            "y": int(y1),
            "width": int(x2 - x1),
            "height": int(y2 - y1),
        }  # source: ai/yolo26/model.py:1100,1106-1109 (the server's own idiom).
        assert gateway_bbox == ROW_A_ROUNDED  # gateway: the round path
        assert server_semantics == ROW_A_TRUNCATED  # pure-expression pin
        assert gateway_bbox != server_semantics  # the ±1px divergence, per-path
        assert set(gateway_bbox) == set(server_semantics)  # same keys, ±1 values

    def test_g1b_the_yolo_family_declares_a_bare_dict_so_the_shape_is_not_schema_checked(
        self,
    ) -> None:
        """The committed snapshot for every yolo-family op is a BARE-DICT
        placeholder, so nothing in the contract catches a bbox key-set or dtype
        regression on the busiest geometry surface in the repo. Characterization
        of the contract gap (the yolo-family heir of the reasoning that retired
        with the free-form /enrich snapshot): the load-bearing shape assertion
        is this suite's, not the schema's."""
        bare = [op_id for op_id in sorted(OPERATIONS) if op_id.startswith("yolo26_")]
        assert bare, "the yolo family left the registry; this pin has no subject"
        for op_id in bare:
            schema = json.loads((SCHEMA_DIR / f"{op_id}.response.json").read_text(encoding="utf-8"))
            assert schema["type"] == "object"
            assert schema["additionalProperties"] is True
            assert "properties" not in schema, f"{op_id} grew a schema; this gap closed"
        # Non-vacuity: the gap is specific to the bare-dict routes. The light
        # lane's reid op DOES have a property-bearing snapshot on disk.
        reid = json.loads(
            (SCHEMA_DIR / "enrich_lt_person_reid.response.json").read_text(encoding="utf-8")
        )
        assert "embedding" in reid["properties"]


# ---------------------------------------------------------------------------
# G2 — LIST-vs-DICT bboxes and the absence of any arity constraint (retargeted)
# ---------------------------------------------------------------------------


class TestG2BboxSpellingAndArityBlindness:
    """The drafted G2 drove Florence's list-of-floats bbox. That provider is
    gone (ruling 1); the HAZARD it pinned — a bbox whose arity nothing checks,
    read through the wrong convention — is fully alive on the light lane, whose
    request model declares ``dict[str, float] | list[float] | None`` with no
    length constraint at all (adapters/enrichment_light.py:52)."""

    def test_g2_light_lane_accepts_both_spellings_with_no_arity_constraint(self) -> None:
        """Characterization: the surviving request schema bounds bbox neither
        by length nor by key set, so a 3-length, 4-length or 8-length list all
        bind — the surviving, stronger form of the snapshot gap the drafted G2
        pinned against florence_detect.response.json."""
        from ai.gateway.adapters.enrichment_light import BBoxRequest

        schema = BBoxRequest.model_json_schema()
        bbox = schema["properties"]["bbox"]
        assert bbox["default"] is None
        assert "minItems" not in bbox and "maxItems" not in bbox
        assert "prefixItems" not in bbox
        bound = [b for b in bbox["anyOf"] if b.get("type") == "array"]
        assert len(bound) == 1, bbox
        assert bound[0]["items"] == {"type": "number"}
        # The dict alternative is key-unconstrained too: {"a": 1.0} is a valid
        # "bbox" as far as this schema is concerned.
        obj = [b for b in bbox["anyOf"] if b.get("type") == "object"]
        assert obj[0]["additionalProperties"] == {"type": "number"}
        # Non-vacuity: the same schema DOES bind the image field, so the model
        # is not simply schema-blind — the gap is bbox-specific.
        assert schema["required"] == ["image_base64"]

    async def test_g2_a_positional_reader_gets_a_different_box_from_each_provider(
        self, fake_client, gateway_client
    ) -> None:
        """THE consumer-side arity lesson, retargeted — and sharper than the
        version it replaces. A reader that indexes a bbox positionally
        (``list(bbox.values())[0]`` is x, the idiom every retired vision lane's
        ``[x1, y1, x2, y2]`` list made natural) does not merely mis-read the
        surviving dict: it gets a DIFFERENT FIELD FIRST FROM EACH PROVIDER.

        Measured, not reasoned: the fake renders every body through ONE
        ``json.dumps(sort_keys=True)`` serializer (backend/ai_contract/fake/
        generators.py:350-352 — that alphabetization IS its byte-determinism
        mechanism), so its bbox arrives as
        ``{"height":…,"width":…,"x":…,"y":…}`` and ``values()[0]`` is HEIGHT.
        The gateway adapter serializes without sort_keys, so the same logical
        box arrives in declared order ``{"x":…,"y":…,"width":…,"height":…}`` and
        ``values()[0]`` is X. Key ORDER is therefore not part of the contract at
        all, and nothing in the committed snapshots says otherwise (the yolo
        family is a bare dict — see G1b's schema-gap pin).

        The trap this pins, in its strongest form: ``len(bbox) == 4`` is GREEN on
        both providers while the positional reading is wrong on at least one,
        AND the usual "is this even a sane box" sanity check (``x2 > x1``) still
        passes on the mis-read — so a consumer can carry the bug to production
        with every guard green. This is what a ``len(bbox) == 4``-style pin
        trained the wrong way, and it is why every surviving pin in this file
        reads KEYS, never positions.
        """
        r_f = await fake_client.post("/yolo26/detect", **_request_kwargs("yolo26_detect"))
        assert r_f.status_code == 200
        fake_bbox = _yolo_dict_from_fake(r_f.json())
        r_g = await gateway_client.post(
            "/yolo26/detect", files={"file": ("frame.png", _png_bytes(), "image/png")}
        )
        assert r_g.status_code == 200
        gateway_bbox = r_g.json()["detections"][0]["bbox"]

        # The trap: the 4-length assertion is GREEN for both spellings...
        assert len(fake_bbox) == 4 and len(gateway_bbox) == 4
        # ...the keys agree, which is all the contract actually guarantees...
        assert set(fake_bbox) == set(gateway_bbox) == {"x", "y", "width", "height"}
        # ...and the ORDER does not, which is what a positional reader trusts.
        assert list(fake_bbox) == ["height", "width", "x", "y"], "fake's sort_keys changed"
        assert list(gateway_bbox) == ["x", "y", "width", "height"], "gateway sorts now too"
        assert list(fake_bbox) != list(gateway_bbox)
        # The mis-read, asserted as behavior on each side.
        assert next(iter(fake_bbox.values())) == fake_bbox["height"]
        assert next(iter(gateway_bbox.values())) == gateway_bbox["x"]
        # The second half of the trap: whether a "is this a sane box" guard
        # (x2 > x1, the cheap check a reviewer reaches for) catches the mis-read
        # is DATA-DEPENDENT, so it cannot be the backstop. Measured on the two
        # bodies this very test just fetched — the fake's first detection reads
        # as height/width/x/y = 84/172/263/54, where x2 > x1 holds (263 > 84) and
        # y2 > y1 does NOT (54 > 172 is False), i.e. the guard fires on ONE axis
        # and passes the other; the gateway's frame-fixed box reads as
        # 201/240/120/60 and fails both. Neither outcome is a reliable signal,
        # and neither is the same as "the box is correct".
        fake_read = tuple(fake_bbox.values())
        gateway_read = tuple(gateway_bbox.values())
        assert fake_bbox == {"height": 84, "width": 172, "x": 263, "y": 54}, fake_bbox
        assert (fake_read[2] > fake_read[0], fake_read[3] > fake_read[1]) == (True, False)
        assert gateway_read == (201, 240, 120, 60), gateway_read
        assert (gateway_read[2] > gateway_read[0]) is False
        # And on neither provider does the mis-read reproduce the true box.
        assert fake_read != (
            fake_bbox["x"],
            fake_bbox["y"],
            fake_bbox["x"] + fake_bbox["width"],
            fake_bbox["y"] + fake_bbox["height"],
        )
        # dtype is the only cheap tell, and only because both emit ints.
        assert all(type(v) is int for v in fake_bbox.values())
        assert all(type(v) is int for v in gateway_bbox.values())

    def test_g2_inbound_coercion_handles_both_spellings_but_reads_them_differently(self) -> None:
        """The app-boundary reader of both spellings, pinned per side: the
        inbound coercion (backend/services/detector_client.py) branches on the
        container type and treats the SAME four numbers as two different boxes —
        dict keys are (x, y, w, h), list positions are (x, y, w, h) too, i.e.
        the list branch re-reads an xyxy provider's corner pair as x/y/width/
        height. Characterization of shipped behavior (this is the ALPR-shaped
        hazard in the surviving code, and it is why G5's validator blindness
        matters)."""
        src = _read("backend/services/detector_client.py")
        assert "if isinstance(bbox, dict):" in src
        assert "elif isinstance(bbox, list | tuple) and len(bbox) == 4:" in src
        # The dict branch reads FOUR named keys; the list branch reads FOUR
        # positions and assigns them straight to x/y/width/height.
        assert 'bbox_width = int(bbox["width"])' in src
        assert "bbox_width = int(bbox[2])" in src
        assert "bbox_height = int(bbox[3])" in src
        # Non-vacuity: this is live shipped code, not a comment — the module's
        # own import proves the file is the real client.
        mod = import_module("backend.services.detector_client")
        assert hasattr(mod, "DetectorClient")

    def test_g2_list_bbox_and_ocr_quad_arity_lesson_retired_with_the_provider(self) -> None:
        """TOMBSTONE (R8 S3, owner ruling 1) — CONSUMER-side angle only.

        The drafted test drove the gateway florence adapter with a canned ``<OD>``
        result and pinned that the adapter mirrors the server's
        ``bboxes`` VERBATIM into ``list[float]`` of length 4, ordered xyxy. What
        that pinned, kept in full:

          * Florence's bbox was a LIST of FLOATS ``[x1, y1, x2, y2]`` while the
            yolo family's is a DICT of INTS — opposite conventions on one
            registry, with nothing in the wire contract distinguishing them;
          * a consumer that read ``bbox[0]`` as x got x1 from Florence and
            insertion-order noise from yolo, so the same helper could not serve
            both providers. The consumer-side half of that lesson is RETARGETED
            above
            (test_g2_a_positional_reader_gets_a_different_box_from_each_provider),
            which is why this tombstone asserts absence instead of restating it;
          * the 4-vs-8 arity SPLIT (detect = 4, ocr-with-regions = 8) is recorded
            once, from the generator side, at
            test_fake_provider.py::test_florence_list_bbox_and_ocr_quads_retired_with_the_provider
            and in the tombstone comment at the bottom of
            backend/ai_contract/fake/generators.py. Copying that record a third
            time here would be prose, not evidence, so it is not repeated: this
            file owns the reading convention, that one owns the emitted arity.

        It cannot retarget as an arity equality: no surviving op carries a
        list-of-floats bbox — the registry's remaining geometry is the yolo
        dict-of-ints and the light lane's embedding / threat-flag shapes. The
        hazard it leaves behind is the one pinned above, which the light lane's
        un-arity-bounded ``bbox`` field keeps very much alive.
        """
        # (a) the ops that carried the shape are gone from the contract...
        florence = sorted(i for i in OPERATION_IDS if i.startswith("florence_"))
        assert florence == [], f"florence ops came back: {florence}"
        # (b) ...the module that mirrored the list is gone (forced import
        # failure, not a text scan), and no surviving gateway op has a `bbox`
        # property in a committed response snapshot.
        with pytest.raises(ModuleNotFoundError):
            import_module("ai.gateway.adapters.florence")
        with pytest.raises(ModuleNotFoundError):
            import_module("backend.services.florence_client")
        for op_id in sorted(OPERATIONS):
            schema = json.loads((SCHEMA_DIR / f"{op_id}.response.json").read_text(encoding="utf-8"))
            assert "bbox" not in json.dumps(schema.get("properties", {})), op_id
        # (c) Non-vacuity: the class this tombstone sits in drives live surface
        # — the light lane's request schema above is read from the shipped
        # module, and its two ops are still in the gateway's column.
        gateway_column = set(operations_for_slot("gateway", OPERATIONS))
        assert {
            "enrich_lt_person_reid",
            "enrich_lt_threat_detect",
        } <= gateway_column
        assert "yolo26_detect" in gateway_column


# ---------------------------------------------------------------------------
# G3 — the eight-float OCR quad flatten (tombstoned)
# ---------------------------------------------------------------------------


class TestG3QuadFlattenTombstone:
    """TOMBSTONE (R8 S3, owner ruling 1).

    The drafted G3 drove a NESTED quad ``[[x, y] x 4]`` through the gateway
    Florence adapter's flatten step and pinned the emitted 8 floats in
    TL,TR,BR,BL order, plus the server's ``[x1, y1, x2, y2, x3, y3, x4, y4]``
    field description and its ``bbox = [coord for point in bbox for coord in
    point]`` flatten. What it established, kept because the hazard is general:

      * **a nested list and a flattened list are the same length-4 python
        object to a naive reader.** ``len(quad) == 4`` is GREEN for
        ``[[x,y] x 4]`` and for ``[x1,y1,x2,y2]``, and the two mean completely
        different things; the flatten is exactly the step that makes them
        indistinguishable downstream. An OCR consumer that took
        ``quad[0]``/``quad[1]`` as a corner pair silently read a 2-coordinate
        box out of an 8-coordinate one;
      * the flatten existed in TWO shipped places (server model and gateway
        adapter) and had to be pinned per path, because the pair could diverge
        without any schema noticing — the general "same transformation, two
        owners" hazard, and the reason this file reads production source for
        the surviving transformations (G1b's AST emitter census, G8's letterbox
        reprojection) rather than trusting one implementation.

    It cannot retarget: no surviving route returns a polygon, mask or quad —
    the light lane returns a 512-dim vector and a threat list, and the yolo
    family returns dict-of-ints boxes with no mask fields (segment falls back
    to detection, ai/gateway/adapters/yolo26.py:447-505). The only shipped
    flatten of that kind left in the tree is the one this docstring describes,
    and the modules holding it are swept.
    """

    def test_g3_quad_flatten_surface_retired_and_no_polygon_returns(self) -> None:
        # (a) the op that carried the quads is gone; nothing in the registry
        # even names a polygon-shaped field.
        assert "florence_ocr_with_regions" not in OPERATION_IDS
        for op_id in sorted(OPERATIONS):
            schema = json.loads((SCHEMA_DIR / f"{op_id}.response.json").read_text(encoding="utf-8"))
            text = json.dumps(schema)
            assert "quad" not in text and "polygon" not in text, op_id
        # (b) the two modules that owned the flatten are gone, by forced import
        # failure and by file absence (not by a text scan for dead spellings).
        assert not (REPO_ROOT / "ai/florence").exists()
        assert not (REPO_ROOT / "ai/gateway/adapters/florence.py").exists()
        with pytest.raises(ModuleNotFoundError):
            import_module("ai.gateway.adapters.florence")
        # The flatten text itself survives nowhere in shipped source: read the
        # LIVE trees for the LIVE form of the transformation.
        survivors = _source_corpus("ai/gateway", "backend/services", "backend/ai_contract")
        assert survivors, "the surviving source tree vanished; this absence is vacuous"
        offenders = [
            p.name for p in survivors if "for point in bbox for coord in point" in _read(p)
        ]
        assert offenders == [], offenders
        # (c) Non-vacuity: this file still drives both surviving adapters'
        # Triton paths (see G8/G9), so the cluster is not now entirely about
        # deleted surface — and the yolo family's own coordinate transformation
        # (letterbox reprojection) IS pinned, live, in this file.
        assert {m.rsplit(".", 1)[1] for m, _ in GATEWAY_MOUNTS} == {
            "yolo26",
            "enrichment_light",
        }


# ---------------------------------------------------------------------------
# G4 — FOURTH spelling: {x1,y1,x2,y2} dicts (request-side / backend-internal)
# ---------------------------------------------------------------------------


class TestG4FourthSpelling:
    def test_g4_fourth_spelling_shape_and_rarity(self) -> None:
        """The x1-dict spelling exists, is CORNERS not x/y/w/h, and lives on the
        request / DB-serialization side — never on a provider RESPONSE. After
        S3 swept the Florence client (which held the drafted representative
        site), the surviving shipped homes of the corners-dict are the ALPR
        plate schema and the smoke/fire row serializer: exactly one literal
        each, both DERIVED, both read from LIVE files."""
        from backend.api.schemas.plate_read import BoundingBox as PlateBoundingBox

        d = PlateBoundingBox(x1=10.0, y1=20.0, x2=30.0, y2=40.0).model_dump()
        # source: backend/api/schemas/plate_read.py:12-31 (BoundingBox, four
        # float corner fields) + its own json_schema_extra example at :19-25.
        assert json.dumps(d) == '{"x1": 10.0, "y1": 20.0, "x2": 30.0, "y2": 40.0}'
        assert d["x2"] - d["x1"] == 20.0  # keys are corners, not x/width
        # The corner-vs-extent distinction is enforced HERE (unlike the light
        # lane's bbox field): a dtype-blind list cannot bind this model.
        # pydantic raises ValidationError (a ValueError subclass) for a list
        # where a corners-model is declared.
        with pytest.raises(ValueError):
            PlateBoundingBox.model_validate([10.0, 20.0, 30.0, 40.0])

        # Rarity, DERIVED per file: exactly one corners-dict literal in each
        # surviving home, and the census that says "these are the only ones".
        plate_src = _read("backend/api/schemas/plate_read.py")
        smoke_src = _read("backend/models/smoke_fire_result.py")
        assert plate_src.count('"x1":') == 1
        assert smoke_src.count('"x1":') == 1
        prod = _source_corpus("ai", "backend/api", "backend/models", "backend/services", "scripts")
        assert len(prod) > 100, "the census corpus collapsed; this equality is vacuous"
        emitters = sorted(str(p.relative_to(REPO_ROOT)) for p in prod if '"x1":' in _read(p))
        assert emitters == [
            "backend/api/schemas/plate_read.py",
            "backend/models/smoke_fire_result.py",
            "scripts/dataset_converters/ccpd_converter.py",
            "scripts/dataset_converters/coco_converter.py",
            "scripts/dataset_converters/flir_converter.py",
        ], emitters
        # ai/ — the provider/serving side — carries ZERO corners-dicts: the
        # spelling never reached a wire response. Derived victim, not a count.
        ai_prod = [p for p in prod if str(p.relative_to(REPO_ROOT)).startswith("ai/")]
        assert len(ai_prod) > 20, "the ai/ census collapsed"
        assert [p.name for p in ai_prod if '"x1":' in _read(p)] == []

    def test_g4_the_fourth_spelling_never_crossed_the_provider_wire(self) -> None:
        """Positive control on the census above: not one registry op declares a
        corners-dict RESPONSE shape, so the spelling is request-side and
        storage-side only. Derived from the registry, not from a remembered
        op list — a resurrected corners-dict response would redden here."""
        hits = []
        for op_id in sorted(OPERATIONS):
            schema = json.loads((SCHEMA_DIR / f"{op_id}.response.json").read_text(encoding="utf-8"))
            if '"x1"' in json.dumps(schema):
                hits.append(op_id)
        assert hits == []
        # Non-vacuity: the sweep is not reading empty schemas.
        reid = json.loads(
            (SCHEMA_DIR / "enrich_lt_person_reid.response.json").read_text(encoding="utf-8")
        )
        assert set(reid["required"]) == {"embedding", "embedding_dimension", "inference_time_ms"}

    async def test_g4_no_provider_response_emits_fourth_spelling(
        self, fake_client, gateway_client
    ) -> None:
        """MATRIX-ONLY consequence, asserted against every drivable provider
        path that survives: no response body carries the x1-dict spelling. The
        drafted form drove fake yolo + fake/gateway florence; the florence paths
        are gone, so the drive is widened over the gateway's WHOLE served column
        (derived) plus the fake's yolo and light lanes — strictly more surface
        than the draft covered, not less."""
        for op_id in sorted(OPERATIONS):
            r = await fake_client.request(
                OPERATIONS[op_id].method, OPERATIONS[op_id].path, **_request_kwargs(op_id)
            )
            assert r.status_code == 200, op_id
            assert '"x1"' not in r.text, op_id

        gateway_column = sorted(operations_for_slot("gateway", OPERATIONS))
        assert len(gateway_column) >= 2
        for op_id in gateway_column:
            op = OPERATIONS[op_id]
            kwargs: dict[str, Any]
            if op_id.startswith("yolo26_"):
                field = "files" if op_id.endswith("batch") else "file"
                payload = _png_bytes()
                kwargs = {
                    "files": [(field, ("frame.png", payload, "image/png"))]
                    if field == "files"
                    else {"file": ("frame.png", payload, "image/png")}
                }
            else:
                kwargs = {"json": {"image_base64": _png_b64()}}
            r = await gateway_client.request(op.method, op.path, **kwargs)
            assert r.status_code == 200, (op_id, r.text[:200])
            assert '"x1"' not in r.text, op_id


# ---------------------------------------------------------------------------
# G5 — bbox_validation.py docstring asserts a FALSE invariant (characterization)
# ---------------------------------------------------------------------------


class TestG5BboxValidationFalseInvariant:
    """This class is about ``backend/services/bbox_validation.py``, which S3
    did NOT touch: the properties here are the file's own, and only the
    provider-driven arm rode along on the florence path that disappeared."""

    def test_g5_xywh_box_passes_every_validator_check(self) -> None:
        """THE characterization: feed the yolo-style xywh tuple (100,150,300,400)
        (x=100 y=150 w=300 h=400) through the validator and PIN that it PASSES
        and is silently re-read as a 200x250 xyxy box. Convention-blindness is
        proven by characterization, NOT fixed (WP6-C ruling territory — parked
        as characterization; no xfail, the test is GREEN as shipped).
        """
        from backend.services.bbox_validation import (
            clamp_bbox_to_image,
            is_valid_bbox,
            validate_bbox,
        )

        xywh = (100.0, 150.0, 300.0, 400.0)
        # source: backend/services/bbox_validation.py — is_valid_bbox :121-156
        # unpacks and tests only x2>x1, y2>y1, finiteness and sign;
        # validate_bbox :160+ adds optional strict_bounds; clamp_bbox_to_image
        # :258+ clamps an in-bounds box unchanged. All three read four positions.
        assert is_valid_bbox(xywh, allow_negative=True) is True
        validate_bbox(xywh, image_width=640, image_height=480, strict_bounds=True)  # no raise
        assert clamp_bbox_to_image(xywh, 640, 480) == xywh
        assert (xywh[2] - xywh[0], xywh[3] - xywh[1]) == (200.0, 250.0)  # silent xywh->xyxy

    def test_g5_false_invariant_docstring_is_pinned(self) -> None:
        """Pin the FALSE sentence itself, so removing/correcting it is a visible
        deliberate act (characterization of the doc, not of the claim)."""
        from backend.services import bbox_validation

        # source: backend/services/bbox_validation.py:7 — "All bounding boxes in
        # this system use the format (x1, y1, x2, y2) where:". FALSE globally:
        # yolo ships {x,y,width,height} int dicts (G1, both fake and gateway
        # drives above) and the Detection DB stores x/y/w/h ints (G6).
        assert bbox_validation.__doc__ is not None
        assert "All bounding boxes in this system use the format (x1, y1, x2, y2)" in (
            bbox_validation.__doc__
        )
        lines = _read("backend/services/bbox_validation.py").splitlines()
        assert lines[6].strip().startswith("All bounding boxes")  # the :7 cite itself

    def test_g5_cited_call_sites_exist_and_are_the_only_ones(self) -> None:
        """The plan's unprotected-caller cite holds verbatim, and the census of
        shipped callers is DERIVED (the drafted version named a second caller
        that S2b/S3 deleted; it now reads the whole shipped surface instead of
        remembering two files)."""
        # source: backend/services/reid_service.py:523
        # `if not is_valid_bbox(bbox_float, allow_negative=True):`
        reid_src = _read("backend/services/reid_service.py")
        assert "is_valid_bbox(bbox_float, allow_negative=True)" in reid_src
        assert not (REPO_ROOT / "backend/services/enrichment_client.py").exists()
        callers = sorted(
            str(p.relative_to(REPO_ROOT))
            for p in _source_corpus("backend/api", "backend/services", "backend/models")
            if "is_valid_bbox(" in _read(p)
        )
        # The module defining it, plus exactly one shipped caller. A re-added
        # enrichment caller reddens here instead of silently restoring the
        # dossier's two-caller shape.
        assert callers == [
            "backend/services/bbox_validation.py",
            "backend/services/reid_service.py",
        ]

    async def test_g5_provider_shapes_are_indistinguishable_to_the_validator(
        self, fake_client, gateway_client
    ) -> None:
        """Feed the SURVIVING shipped spellings through the validator. The
        drafted arm used florence's 4-float xyxy list against the yolo dict
        re-projected as a tuple; the florence path is gone, so the pair is now
        (a) the yolo dict re-projected as a tuple — an xywh box wearing an xyxy
        costume, which passes — and (b) the SAME dict handed over raw, which
        fails. The mechanism is unchanged and the failure mode is
        ``is_valid_bbox`` reading a str key name: a dict that arrives un-projected
        is not "invalid geometry", it is a TypeError the function swallows."""
        from backend.services.bbox_validation import is_valid_bbox

        r = await fake_client.post("/yolo26/detect", **_request_kwargs("yolo26_detect"))
        assert r.status_code == 200
        b = _yolo_dict_from_fake(r.json())
        yolo_as_tuple = (b["x"], b["y"], b["x"] + b["width"], b["y"] + b["height"])
        # source: fake shape (generators.py:195-210) fed to is_valid_bbox
        # (bbox_validation.py:121-156).
        assert is_valid_bbox(yolo_as_tuple, allow_negative=True) is True
        # The dict itself: the try/except at :156 turns "can't compare str and
        # int" into a False, so a caller that forgets the projection cannot tell
        # "wrong convention" from "wrong container".
        assert is_valid_bbox(b, allow_negative=True) is False  # type: ignore[arg-type]
        # And a gateway-emitted box behaves identically to the fake's — the
        # validator is blind to which provider produced it.
        r = await gateway_client.post(
            "/yolo26/detect", files={"file": ("frame.png", _png_bytes(), "image/png")}
        )
        assert r.status_code == 200
        g = r.json()["detections"][0]["bbox"]
        assert (
            is_valid_bbox(
                (g["x"], g["y"], g["x"] + g["width"], g["y"] + g["height"]), allow_negative=True
            )
            is True
        )


# ---------------------------------------------------------------------------
# G6 — normalized [0,1] floats truncate to 0 in the Integer DB columns, silently
# ---------------------------------------------------------------------------


class TestG6NormalizedFloatTruncation:
    def test_g6_db_bbox_columns_are_integer(self) -> None:
        from backend.models.detection import Detection

        cols = {c.name: str(c.type) for c in Detection.__table__.columns}
        # source: backend/models/detection.py:56-59 — bbox_x/bbox_y/bbox_width/
        # bbox_height Mapped[int|None] = mapped_column(Integer, nullable=True);
        # the plan's ':55' is the confidence Float column (dossier G6 correction;
        # str(type) == "INTEGER").
        for name in ("bbox_x", "bbox_y", "bbox_width", "bbox_height"):
            assert cols[name] == "INTEGER", (name, cols[name])

    def test_g6_normalized_floats_collapse_to_zero_silently(self) -> None:
        """Negative property (matrix-only per dossier G6): a hypothetical
        [0,1]-emitting provider is UNDETECTABLE at this layer — the app-boundary
        int() coercion (not the DB) does the damage, and the downstream guard
        silently DROPS the detection with no error."""
        normalized = {"x": 0.87, "y": 0.42, "width": 0.31, "height": 0.19}
        coerced = {k: int(v) for k, v in normalized.items()}
        # source: backend/services/detector_client.py:1210-1213 (`bbox_x =
        # int(bbox["x"]); …`) and the silent skip at :1256 (`if bbox_width < 1
        # or bbox_height < 1:`). The WP8.3 dossier cites :1333-1336/:1379; the
        # strings are still exactly present ~120 lines earlier, which is what
        # these pins read.
        assert coerced == {"x": 0, "y": 0, "width": 0, "height": 0}
        det_src = _read("backend/services/detector_client.py")
        assert 'bbox_x = int(bbox["x"])' in det_src
        assert "if bbox_width < 1 or bbox_height < 1:" in det_src

    def test_g6_the_lane_that_could_have_been_normalized_is_not(self) -> None:
        """The other half of "latent, not live": the surviving embedding lanes —
        the float-vector payloads left in the contract — are stored as JSONB and
        as bytes, never through an Integer column, so the class of coordinate the
        G6 hazard is about cannot reach them. Read from the shipped ORM (the
        Detection columns above are the INT side).

        RETARGETED BY R8 S4 (2026-09-30): this pin used to read the claim off
        ``ReIDEmbedding.embedding`` (the per-detection 512-dim JSONB column, whose
        comment spelled the dimensionality). That class, and the
        ``reid_embeddings`` table, were dropped by owner ruling — zero live
        readers, zero shipped writers — so the property is now stated over the
        THREE surviving embedding columns, derived from the ORM rather than
        remembered, and the claim is the same: not one of them is an Integer."""
        from backend.models.detection import Detection
        from backend.models.household import PersonEmbedding, RegisteredVehicle
        from backend.models.track import Track

        # Derived: every shipped column whose NAME says it carries an embedding
        # vector, across the three models that still have one. A fourth column
        # appearing with an Integer type reddens the loop below.
        embed_cols = {
            f"{m.__tablename__}.{c.name}": str(c.type)
            for m in (PersonEmbedding, RegisteredVehicle, Track, Detection)
            for c in m.__table__.columns
            if "embed" in c.name or c.name == "enrichment_data"
        }
        assert embed_cols, "no surviving embedding column at all — the scan is vacuous"
        for name, type_ in embed_cols.items():
            assert type_ in {"JSONB", "BLOB"}, f"{name} is {type_}; a float vector in an INT column"
        # Non-vacuity: the contrast is with a real Integer column on the same ORM
        # base — the side G6 is actually about — not with nothing.
        assert str(Detection.__table__.columns["bbox_x"].type) == "INTEGER"
        assert str(PersonEmbedding.__table__.columns["member_id"].type) == "INTEGER"

    async def test_g6_registered_provider_paths_emit_absolute_pixels(
        self, fake_client, gateway_client
    ) -> None:
        """The positive guard that keeps G6 a latent hazard rather than a live
        one: every drivable provider path emits ABSOLUTE px. The drafted arm
        drove fake florence and gateway florence; both are gone, so the guard
        now covers every op the gateway column serves (derived), the yolo
        family's dict-of-ints on the fake, and the light lane's float vector —
        whose components are the one place a sub-1 float legitimately ships,
        and are pinned as NOT being read as pixels."""
        for op_id in sorted(OPERATIONS):
            if not op_id.startswith("yolo26_"):
                continue
            r = await fake_client.request(
                OPERATIONS[op_id].method, OPERATIONS[op_id].path, **_request_kwargs(op_id)
            )
            assert r.status_code == 200, op_id
            body = r.json()
            items = body.get("results", [body])
            for item in items:
                for d in item["detections"]:
                    # source: fake _yolo_bbox_dict in-frame ints
                    # (generators.py:195-210, _FAKE_FRAME (640, 480) at :141).
                    assert d["bbox"]["width"] >= 1 and d["bbox"]["height"] >= 1
                    assert d["bbox"]["x"] >= 0 and d["bbox"]["y"] >= 0

        gateway_column = sorted(operations_for_slot("gateway", OPERATIONS))
        driven = 0
        for op_id in gateway_column:
            op = OPERATIONS[op_id]
            if op_id.startswith("yolo26_"):
                r = await gateway_client.request(
                    op.method,
                    op.path,
                    files=[("files", ("f.png", _png_bytes(), "image/png"))]
                    if op_id.endswith("batch")
                    else {"file": ("f.png", _png_bytes(), "image/png")},
                )
                assert r.status_code == 200, (op_id, r.text[:200])
                body = r.json()
                items = body.get("results", [body])
                for item in items:
                    for d in item["detections"]:
                        # gateway round() output is absolute px; the canned
                        # width is >= 1 by construction.
                        assert d["bbox"]["width"] >= 1 and d["bbox"]["height"] >= 1
                        assert all(type(v) is int for v in d["bbox"].values())
                driven += 1
            else:
                r = await gateway_client.request(
                    op.method, op.path, json={"image_base64": _png_b64()}
                )
                assert r.status_code == 200, (op_id, r.text[:200])
                body = r.json()
                if "embedding" in body:
                    # The float lane's components ARE sub-1, and the reason is
                    # structural: the adapter L2-normalizes whatever Triton
                    # returned (the mock deliberately feeds a NON-unit ramp
                    # vector, adapters/enrichment_light.py:205-213), so every
                    # component is <= 1 by construction — and int() of any of
                    # them would be 0, which is exactly the G6 collapse. That is
                    # safe here ONLY because nothing reads them as pixels: pin
                    # the norm (which is what makes sub-1 a guarantee rather
                    # than an observation about one payload), the declared
                    # dimension, and the absence of any box field.
                    assert math.isclose(
                        math.sqrt(sum(v * v for v in body["embedding"])), 1.0, abs_tol=1e-4
                    ), body["embedding_dimension"]
                    assert all(abs(v) < 1.0 for v in body["embedding"])
                    assert body["embedding_dimension"] == len(body["embedding"])
                    assert "bbox" not in body
                driven += 1
        assert driven == len(gateway_column) >= 2


# ---------------------------------------------------------------------------
# G7 — zero validation of a score, and absent score == MAXIMUM (retargeted)
# ---------------------------------------------------------------------------


class TestG7ScoreDefaultAndClampZeroValidation:
    """The drafted G7 drove ``FlorenceClient.detect`` and the gateway Florence
    OD route, both of which shipped "no validation, absent score means 1.0".
    Both are gone; the same two degeneracies survive on live surface — the ALPR
    recognize request (absent confidence defaults to the MAXIMUM 1.0 and is not
    required) and the two gateway confidence clamps (yolo clamps to [0,1], the
    light lane does not)."""

    def test_g7_absent_confidence_defaults_to_the_maximum_on_the_surviving_schema(self) -> None:
        """Omitted confidence == MAXIMUM confidence, pinned on the surviving
        request-side schema (backend/api/schemas/plate_read.py:192-197:
        ``detection_confidence: float = Field(default=1.0, ge=0.0, le=1.0)``).
        Characterization: the default is the shipped choice, and the pin exists
        so that changing it is a deliberate act — a reader that treats "no
        confidence given" as "no confidence" gets the opposite answer."""
        from backend.api.schemas.plate_read import PlateRecognizeRequest

        schema = PlateRecognizeRequest.model_json_schema()
        conf = schema["properties"]["detection_confidence"]
        assert conf["default"] == 1.0
        assert conf["minimum"] == 0.0 and conf["maximum"] == 1.0
        assert "detection_confidence" not in schema["required"]
        assert schema["required"] == ["camera_id", "image_base64"]
        # Non-vacuity: the same module's bbox field DOES carry the arity
        # constraint the light lane's lacks (G2) — the schema layer is not
        # uniformly blind, it is blind in these two places. The field is
        # Optional, so the 4/4 bounds live on the array arm of the anyOf, not on
        # the field itself; reading the top level (the first draft did) is a
        # KeyError, and the contrast with BBoxRequest is arm-for-arm.
        det_bbox = schema["properties"]["detection_bbox"]
        assert det_bbox["default"] is None
        arms = [a for a in det_bbox["anyOf"] if a.get("type") == "array"]
        assert len(arms) == 1, det_bbox
        assert arms[0]["minItems"] == 4 and arms[0]["maxItems"] == 4
        from ai.gateway.adapters.enrichment_light import BBoxRequest

        light_arms = [
            a
            for a in BBoxRequest.model_json_schema()["properties"]["bbox"]["anyOf"]
            if a.get("type") == "array"
        ]
        assert "minItems" not in light_arms[0] and "maxItems" not in light_arms[0]

    def test_g7_the_zero_validation_client_surface_is_retired(self) -> None:
        """TOMBSTONE (R8 S3, rulings 1 + 5).

        The drafted test drove a ``FlorenceClient`` whose httpx pools were
        mocks and pinned that its ``detect`` validates NOTHING: an absent
        ``bbox`` became ``[]``, an absent ``score`` became ``1.0``, string
        coordinates survived verbatim, and an out-of-band ``score: 42`` passed
        because the client-side dataclass had no validator while its sibling
        ``SecurityObjectDetection`` did (``ge=0/le=1``). Kept because the hazard
        is general: **a client mirror with no validator is where a provider's
        sloppy response becomes silently usable data**, and the one clamped
        sibling proves the omission was per-class, not a house style.

        It cannot retarget as a behavior drive: the module is deleted (ruling 1
        retires the Florence client with its provider) and no surviving client
        hard-codes ``score=1.0`` — the derived scan below is the whole point,
        so a future client that re-adds the degeneracy reddens here rather than
        silently inheriting the dossier's shape.
        """
        assert "florence_detect" not in OPERATION_IDS
        with pytest.raises(ModuleNotFoundError):
            import_module("backend.services.florence_client")
        assert not (REPO_ROOT / "backend/services/florence_client.py").exists()
        # LIVE forms only: no surviving shipped module hard-codes a maximum
        # score for every detection, and no surviving gateway adapter ships a
        # confidence without a clamp... except the light lane, which IS pinned
        # as unclamped in the test below (so this is a census, not a wish).
        survivors = _source_corpus("backend/services", "ai/gateway")
        offenders = [
            p.name for p in survivors if re.search(r"Detection\([^)]*score=1\.0", _read(p))
        ]
        assert offenders == [], offenders
        # Non-vacuity: the clamp asymmetry that G7 now pins IS live and drives
        # both adapters through the same mock in the next test.
        assert "max(0.0, min(1.0" in _read(GATEWAY_YOLO_SRC)
        assert "min(1.0" not in _read(LIGHT_ADAPTER_SRC)

    async def test_g7_light_lane_confidence_is_unclamped_where_yolo_clamps(
        self, gateway_client
    ) -> None:
        """Provider-SPLIT characterization, now measured on two SURVIVING paths
        instead of one surviving and one deleted: the same out-of-band
        confidence of 1.7 reaches the client UNCHANGED on /enrich-lt and
        CLAMPS to 1.0 on /yolo26. The drafted note said a cross-provider
        "scores are in [0,1]" assertion is RED against exactly one side and is
        therefore not written — true then, true now, and the two sides are both
        drivable, so the divergence is pinned per-path and jointly."""
        r_y = await gateway_client.post(
            "/yolo26/detect", files={"file": ("frame.png", _png_bytes(), "image/png")}
        )
        assert r_y.status_code == 200, r_y.text
        # source: adapters/yolo26.py:183 (post-NMS clamp) and :314 (pre-NMS
        # twin) — score = max(0.0, min(1.0, score)). The canned rows carry 0.9
        # and 0.5, so this arm pins passthrough; the over-1 arm is the light
        # lane below, where the identical input does NOT clamp.
        confs = [d["confidence"] for d in r_y.json()["detections"]]
        assert confs == [0.9, 0.5], confs
        assert all(0.0 <= c <= 1.0 for c in confs)

        r_l = await gateway_client.post(
            "/enrich-lt/threat-detect", json={"image_base64": _png_b64()}
        )
        assert r_l.status_code == 200, r_l.text
        body = r_l.json()
        threat_confs = [d["confidence"] for d in body["threats_detected"]]
        assert 1.7 in threat_confs, threat_confs
        assert body["max_confidence"] == 1.7  # the envelope echoes it, unclamped
        assert max(threat_confs) > 1.0
        # Non-vacuity: the light lane DID drop the sub-threshold column, so
        # "unclamped" is not just "unfiltered" — its threshold works, its range
        # check does not exist.
        assert len(body["threats_detected"]) == len(THREAT_COLUMNS) - 1
        assert min(threat_confs) >= 0.25
        assert body["is_threat"] is True
        # The light lane also rounds: column 0's fractional cxcywh shows the
        # SAME round-vs-truncate split as G1b on a second shipped path.
        col0 = body["threats_detected"][0]
        assert col0["bbox"] == LIGHT_ROW_A_ROUNDED
        cx, cy, w, h = THREAT_COLUMNS[0][:4]
        truncated = {
            "x": int(cx - w / 2),
            "y": int(cy - h / 2),
            "width": int(w),
            "height": int(h),
        }
        assert truncated == LIGHT_ROW_A_TRUNCATED
        assert col0["bbox"] != truncated

    async def test_g7_light_lane_defaults_are_shipped_when_the_model_sees_nothing(
        self, gateway_client, gateway_triton
    ) -> None:
        """The surviving form of "an absent value becomes a silent constant":
        with every threat score under the 0.25 threshold the route returns 200
        with an EMPTY list, ``is_threat`` False and ``max_confidence`` 0.0 — a
        healthy-looking response indistinguishable from "nothing in frame".
        Characterization, and the ``max_confidence`` default comes from
        adapters/enrichment_light.py:58 (``Field(default=0.0)``) / the ``default
        = 0.0`` in the route's own max()."""
        gateway_triton.zero_threat()
        r = await gateway_client.post("/enrich-lt/threat-detect", json={"image_base64": _png_b64()})
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["threats_detected"] == []
        assert body["is_threat"] is False
        assert body["max_confidence"] == 0.0
        # Non-vacuity: the SAME route, SAME app, mock un-toggled, returns a
        # populated body — so the empty one is the threshold's doing, not a
        # dead mount or a broken mock.
        gateway_triton.unzero_threat()
        r2 = await gateway_client.post(
            "/enrich-lt/threat-detect", json={"image_base64": _png_b64()}
        )
        assert r2.status_code == 200, r2.text
        assert r2.json()["threats_detected"], "the positive control came back empty too"
        assert r2.text != r.text

    def test_g7_the_dead_provider_score_shape_is_not_in_the_contract(self) -> None:
        """Absence on the contract side of the same lesson: the retired ops'
        snapshots are gone from disk (so nothing can walk a score-with-default
        generator for them), and no surviving snapshot declares a per-item
        ``score`` at all."""
        leftovers = sorted(p.name for p in SCHEMA_DIR.glob("florence_*.json"))
        assert leftovers == [], leftovers
        # Non-vacuity: the survivor check is positive and specific.
        assert any(SCHEMA_DIR.glob("yolo26_*.json")), "the sweep took survivors too"
        declared = [
            op_id
            for op_id in sorted(OPERATIONS)
            if '"score"' in (SCHEMA_DIR / f"{op_id}.response.json").read_text(encoding="utf-8")
        ]
        assert declared == []


# ---------------------------------------------------------------------------
# G8 — the two lanes disagree about whose coordinate frame a bbox is in
# ---------------------------------------------------------------------------


class TestG8CoordinateFrameSplit:
    """A retarget that only S3's surviving surface makes possible, and the
    cluster's most useful property: the same model-output box reaches the two
    surviving lanes' clients in DIFFERENT coordinate frames. /yolo26 reverses
    the letterbox and clamps to the uploaded frame; /enrich-lt never enters
    that pipeline (its postprocessor is a standalone
    cxcywh→xywh conversion with no frame argument at all,
    adapters/enrichment_light.py:74-121), so its boxes are frame-independent
    AND can extend past the frame."""

    async def test_g8_the_same_box_is_in_two_frames_on_two_routes(self, gateway_client) -> None:
        yolo = await gateway_client.post(
            "/yolo26/detect", files={"file": ("frame.png", _png_bytes(), "image/png")}
        )
        light = await gateway_client.post(
            "/enrich-lt/threat-detect", json={"image_base64": _png_b64()}
        )
        assert yolo.status_code == 200 and light.status_code == 200
        # Row B / threat column 1 are the same 640-space box on both lanes.
        y_box = next(d["bbox"] for d in yolo.json()["detections"] if d["class"] == "bicycle")
        l_box = next(d["bbox"] for d in light.json()["threats_detected"] if d["class"] == "knife")
        # yolo clamped the bottom edge into the 640x640 frame; light did not.
        assert y_box == ROW_B_YOLO_SQUARE
        assert l_box == ROW_B_LIGHT_SQUARE
        assert l_box["height"] > y_box["height"]  # 400 vs 300: the clamp, measured
        assert l_box["y"] + l_box["height"] > yolo.json()["image_height"]
        # Same top-left corner though — the split is extent, not origin, so a
        # consumer comparing anchors sees agreement while the crop differs.
        assert (l_box["x"], l_box["y"]) == (y_box["x"], y_box["y"])

    async def test_g8_a_wide_frame_moves_yolo_boxes_and_leaves_light_boxes_alone(
        self, gateway_client
    ) -> None:
        """The frame-dependence half, driven on a 1280x720 upload: yolo's box
        doubles (scale 0.5, pad_y 140) and its BOTTOM edge clamps into the
        frame, while the light lane's box does not move AT ALL. A consumer that
        crops with a light-lane bbox gets a different region for the same tensor
        than one that crops with a yolo bbox, and the only guard against mixing
        them is the caller's memory of which route answered.

        Measured, because the clamp is edge-specific and a hand-computed
        constant got it wrong the first time: at scale=0.5 row B's x2 re-projects
        to 1000, which is INSIDE a 1280-wide frame, so nothing clamps
        horizontally and the width doubles to 800; its y2 re-projects to 1200,
        which is past 720, so the bottom clamps and the height is 720-400=320
        rather than the unclamped 800. Same tensor, one axis clamped, one not."""
        wide = (1280, 720)
        yolo = await gateway_client.post(
            "/yolo26/detect", files={"file": ("frame.png", _png_bytes(*wide), "image/png")}
        )
        light = await gateway_client.post(
            "/enrich-lt/threat-detect", json={"image_base64": _png_b64(*wide)}
        )
        assert yolo.status_code == 200 and light.status_code == 200
        assert yolo.json()["image_width"] == wide[0]
        assert yolo.json()["image_height"] == wide[1]
        y_box = next(d["bbox"] for d in yolo.json()["detections"] if d["class"] == "bicycle")
        l_box = next(d["bbox"] for d in light.json()["threats_detected"] if d["class"] == "knife")
        # source: letterbox_scale_factors(1280, 720, 640) = (0.5, 0, 140)
        # (ai/gateway/utils.py:202-207), applied at adapters/yolo26.py:174,188-191
        # with bx2/by2 clamped to orig_w/orig_h.
        assert y_box == ROW_B_YOLO_WIDE, y_box
        # The light lane's answer is frame-independent — byte-identical to the
        # square-frame case pinned in the test above.
        assert l_box == ROW_B_LIGHT_SQUARE, l_box
        assert l_box["y"] + l_box["height"] > wide[1]  # reaches 740 past a 720 frame
        # Non-vacuity: the yolo route really did re-project (its box moved)
        # while the light route really served the request (200 + rows above).
        assert y_box != l_box
        # And the re-projection is not a uniform scale of the square-frame
        # answer, which is what "clamp" costs the consumer: x/width doubled,
        # y doubled, height did NOT (320, not 2x300=600 and not 2x400=800).
        square = await gateway_client.post(
            "/yolo26/detect", files={"file": ("frame.png", _png_bytes(), "image/png")}
        )
        y_square = next(d["bbox"] for d in square.json()["detections"] if d["class"] == "bicycle")
        assert y_square == ROW_B_YOLO_SQUARE, y_square
        assert (y_box["width"], y_box["height"]) != (2 * y_square["width"], 2 * y_square["height"])

    def test_g8_the_reprojection_is_one_helper_the_light_lane_does_not_call(self) -> None:
        """Source-side of the same split, so a fix that "harmonizes" the lanes
        reddens here: ``letterbox_scale_factors`` is imported and called by the
        yolo adapter's TWO post-processors and referenced nowhere in the light
        adapter."""
        yolo_src = _read(GATEWAY_YOLO_SRC)
        light_src = _read(LIGHT_ADAPTER_SRC)
        assert yolo_src.count("letterbox_scale_factors(orig_w, orig_h, TARGET_SIZE)") == 2
        assert "letterbox" not in light_src
        # Non-vacuity: the light adapter does do coordinate arithmetic — it is
        # the frame-free part that is missing.
        assert '"x": round(float(cx - w / 2))' in light_src


# ---------------------------------------------------------------------------
# G9 — the driving shape itself: mounts, patch targets, absence
# ---------------------------------------------------------------------------


class TestG9DrivingShape:
    """This cluster's failures were the driving shape's, not any property's:
    the five-mount fixture ERRORed on a swept import. Pinned so the same class
    of failure cannot recur silently — and so "the gateway answered 404" can
    never again be read as "the provider does not serve this" without the
    mount table being checked first."""

    def test_g9_the_mount_table_and_patch_targets_are_derived_from_production(self) -> None:
        modules = {m.rsplit(".", 1)[1] for m, _ in GATEWAY_MOUNTS}
        prefixes = {p for _, p in GATEWAY_MOUNTS}
        # The pair every registry path depends on: Operation.path already
        # carries the prefix, so mounting without it 404s everything.
        assert modules == {"yolo26", "enrichment_light"}, GATEWAY_MOUNTS
        assert prefixes == {"/yolo26", "/enrich-lt"}, GATEWAY_MOUNTS
        assert len(GATEWAY_PATCH_TARGETS) == len(GATEWAY_MOUNTS) >= 2
        # The retired lanes are not mounted, and the mount table proves it
        # rather than a hand-written absence list.
        assert all(not m.startswith("ai.gateway.adapters.clip") for m, _ in GATEWAY_MOUNTS)
        for gone in ("/florence", "/clip", "/enrichment"):
            assert gone not in prefixes
        # Non-vacuity: production main still mounts exactly what it says —
        # the regex found the same count as the file's own include_router lines.
        src = _read(GATEWAY_MAIN_SRC)
        assert src.count("app.include_router(") == len(GATEWAY_MOUNTS)

    def test_g9_patching_one_adapter_name_leaves_the_other_on_real_grpc(self) -> None:
        """The dossier-Q2 rule, asserted on the two surviving modules: the
        per-module from-import means each adapter holds its OWN reference, so
        patching one name cannot reach the other. This is why
        ``gateway_client`` patches all of GATEWAY_PATCH_TARGETS and why the
        target list must grow with the mount table.

        ``new=`` and not ``return_value=`` is load-bearing here: patch's
        ``return_value`` replaces the attribute with a MagicMock whose CALL
        returns the object, so an identity assertion on the attribute could
        never hold (the first draft of this pin asserted exactly that and
        failed on its own mock). ``new=`` binds the object itself."""
        import ai.gateway.adapters.enrichment_light as light
        import ai.gateway.adapters.yolo26 as yolo
        from ai.gateway import triton_client

        shipped = triton_client.get_triton_client
        # Same object before any patch: both names were bound to the same
        # function at import, so a patch of one name is invisible to the other.
        assert yolo.get_triton_client is shipped
        assert light.get_triton_client is shipped
        sentinel = AsyncMock()
        with patch("ai.gateway.adapters.yolo26.get_triton_client", new=sentinel):
            assert yolo.get_triton_client is sentinel
            assert light.get_triton_client is shipped  # still the real gRPC factory
        assert yolo.get_triton_client is shipped  # unpatched again

    async def test_g9_every_gateway_column_path_resolves_on_the_mounted_app(
        self, gateway_client
    ) -> None:
        """Absence must MATCH the matrix, and presence must too: every op in the
        gateway's column answers on this app (the availability matrix's claim
        is checkable, not decorative), while every retired lane's path is a real
        404 rather than a mounted-router-forever-503."""
        column = sorted(operations_for_slot("gateway", OPERATIONS))
        assert len(column) >= 2
        for op_id in column:
            op = OPERATIONS[op_id]
            if op_id.startswith("yolo26_"):
                r = await gateway_client.request(
                    op.method,
                    op.path,
                    files=[("files", ("f.png", _png_bytes(), "image/png"))]
                    if op_id.endswith("batch")
                    else {"file": ("f.png", _png_bytes(), "image/png")},
                )
            else:
                r = await gateway_client.request(
                    op.method, op.path, json={"image_base64": _png_b64()}
                )
            assert r.status_code == 200, (op_id, op.path, r.text[:200])
            assert r.json(), op_id

        for dead_path in (
            "/florence/detect",
            "/clip/embed",
            "/enrichment/enrich",
            "/enrich-lt/pose-analyze",  # pruned route on a SURVIVING mount
            "/yolo26/track",  # deployed-but-unreachable precedent
        ):
            r = await gateway_client.post(dead_path, json={"image_base64": _png_b64()})
            assert r.status_code == 404, (dead_path, r.status_code)
