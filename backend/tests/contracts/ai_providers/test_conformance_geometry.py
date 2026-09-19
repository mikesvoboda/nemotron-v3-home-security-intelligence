"""WP8.3 conformance suite — cluster GEOMETRY AND ENCODING (G1a-G7).

Per-property module toward ``backend/tests/contracts/ai_providers/test_conformance.py``
(plan docs/superpowers/plans/2026-09-19-swap-readiness-72h.md §WP8.3, "Geometry
and encoding"). Every assertion carries: its source cite (file:line from the
WP8.3 evidence dossier, corrected-line form), its predicted verdict against the
FakeProvider, its predicted gateway behavior, and UNVERIFIED (this is a DRAFT —
nothing here has been run; a full validate.sh pytest tier was running while it
was written).

Predicted-verdict legend used in the inline comments:
  fake GREEN/RED    — verdict predicted for the FakeProvider-driven form
  gateway GREEN/RED — verdict predicted for the gateway-adapter-driven form
  (per_model_http / llamacpp_llm are MATRIX-GUARD-only providers: this module
  never invokes their registered callables, which are unbound client methods
  that would hit the real network; their geometry is exercised only through
  the gateway/fake paths plus source-pins.)

Cluster verdict summary (predicted, UNVERIFIED):
  * REDS AGAINST FAKE: none. The fake was BUILT to encode every shipped-correct
    geometry bullet (_yolo_bbox_dict dict-of-ints in-frame 640x480,
    generators.py:215-229; _florence_bbox arity 4/8, generators.py:178-201;
    _OVERRIDES at :247-266), so every shape assertion here is predicted GREEN
    against fake. REDS AGAINST GATEWAY (driven form): none either — both
    shipped paths are "shipped-correct" per the WP6-C-style rulings the plan
    cites, so each divergence (trunc-vs-round, 4-vs-8 arity, score-1.0) is
    pinned per-path rather than asserted cross-provider-equal. The genuine
    provider-SPLIT lives inside two tests (G1b round-vs-truncate and G7
    score-constant) where fake and gateway are each pinned to their OWN
    shipped truth: a naive single equality between them would be RED against
    exactly one provider on a fractional fixture, which is why none is written.
  * The native per-model server path (ai/yolo26/model.py int() truncation,
    ai/florence/model.py flatten/score=1.0) cannot be booted in-sandbox, so it
    is pinned by source-text characterization + pure-expression semantics —
    each such test notes that its source-pin is predicted GREEN against today's
    source (it pins, not fixes).

No xfail / skip / importorskip anywhere (goal rule). Properties that a ruling
parks (G5 false invariant, G7 zero-validation) are plain CHARACTERIZATION
assertions: they pin current behavior as shipped, they do not assert the
docstring's claim is true, and they do not fix it.
"""

from __future__ import annotations

import io
import json
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pytest
from httpx import ASGITransport, AsyncClient

REPO_ROOT = Path(__file__).resolve().parents[4]  # UNVERIFIED: parents[4] is correct for the
# final placement at backend/tests/contracts/ai_providers/test_conformance_geometry.py
# (mirrors test_fake_provider.py:47); it is WRONG while this draft sits under /tmp.
SCHEMA_DIR = REPO_ROOT / "backend" / "ai_contract" / "schemas"
GOLDEN_DIR = REPO_ROOT / "backend/tests/contracts/ai_providers/golden/payloads"

YOLO_SERVER_SRC = REPO_ROOT / "ai" / "yolo26" / "model.py"
GATEWAY_YOLO_SRC = REPO_ROOT / "ai" / "gateway" / "adapters" / "yolo26.py"
FLORENCE_SERVER_SRC = REPO_ROOT / "ai" / "florence" / "model.py"

# The five production adapter mount prefixes (ai/gateway/main.py:181-185) and
# the five per-module patch targets (dossier Q2: each adapter module-level
# from-import — patching ai.gateway.triton_client.get_triton_client hits NONE;
# patching one leaves the other four calling real gRPC).
# source: ai/gateway/main.py:181-185; patch targets at adapters/
# {yolo26.py:28, enrichment.py:31, enrichment_light.py:30, florence.py:39,
#  clip.py:40}. UNVERIFIED.
GATEWAY_MOUNTS = (
    ("/yolo26", "ai.gateway.adapters.yolo26"),
    ("/clip", "ai.gateway.adapters.clip"),
    ("/florence", "ai.gateway.adapters.florence"),
    ("/enrichment", "ai.gateway.adapters.enrichment"),
    ("/enrich-lt", "ai.gateway.adapters.enrichment_light"),
)


# ---------------------------------------------------------------------------
# Request-shape helpers (fake-driven), copied shape from test_fake_provider.py:72-98
# ---------------------------------------------------------------------------


def _request_kwargs(op_id: str) -> dict[str, Any]:
    """Drive requests from the WP7.2 goldens where a request example exists
    (source: test_fake_provider.py:72-98 — same contract, same fake app).
    UNVERIFIED here (not run)."""
    from backend.ai_contract.operations import OPERATIONS

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


@pytest.fixture(scope="module")
def fake_app():
    from backend.ai_contract.fake import create_fake_app

    return create_fake_app()


@pytest.fixture
async def fake_client(fake_app):
    transport = ASGITransport(app=fake_app)
    async with AsyncClient(transport=transport, base_url="http://fake") as client:
        yield client


# ---------------------------------------------------------------------------
# Gateway-driven helpers: five routers + five patched get_triton_client names
# ---------------------------------------------------------------------------


def _png_bytes(width: int = 640, height: int = 640) -> bytes:
    """640x640 PNG so letterbox scale=1, pad=0 (ai/gateway/utils.py:202-207) —
    post-NMS coords pass through the reverse-letterbox untouched, making the
    round() output exactly predictable. UNVERIFIED."""
    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (width, height), (7, 23, 41)).save(buf, format="PNG")
    return buf.getvalue()


# Canned post-NMS Triton row [x1, y1, x2, y2, conf, cls] in 640-space
# (row format: ai/gateway/adapters/yolo26.py:136-137 docstring). The coords
# DISCRIMINATE truncation from rounding:
#   gateway round():  x=round(10.6)=11        width=round(99.9)=100  height=round(40.5)=40 (banker's)
#   server  int():    x=int(10.6)=10          width=int(99.9)=99     height=int(40.5)=40
# source: gateway round at adapters/yolo26.py:204-207 (def _postprocess_post_nms :164;
# pre_nms twin :321-324); server int at ai/yolo26/model.py:1406-1409 (xyxy unpack :1399).
# UNVERIFIED pending the first real run.
# (1, N, 6): the adapter strips the batch dim itself (preds = output[0],
# ai/gateway/adapters/yolo26.py:153) then iterates rows — discovery fix, the
# drafted (1, 6) shape made row[4] a scalar access (IndexError).
GATEWAY_CANNED_ROWS = np.array([[[10.6, 20.4, 110.5, 60.9, 0.9, 0]]], dtype=np.float64)
GATEWAY_CANNED_ROUNDED = {"x": 11, "y": 20, "width": 100, "height": 40}  # predicted gateway output
GATEWAY_CANNED_TRUNCATED = {"x": 10, "y": 20, "width": 99, "height": 40}  # server-side semantics


def _florence_triton(prompt_payloads: dict[str, dict[str, Any]]) -> AsyncMock:
    """Triton mock for the florence adapter: inspects the prompt the adapter
    sends (ai/gateway/adapters/florence.py:219,222-229) and returns the canned
    Python-backend envelope {"result": <task JSON string>} the adapter unwraps
    at :244-252. UNVERIFIED."""
    import base64 as _b64  # noqa: F401  (adapter validates b64; our payload must be valid)

    async def _infer(*, model_name: str, inputs: Any, outputs: Any) -> dict[str, Any]:
        prompt = inputs["prompt"][0]
        prompt = prompt.decode("utf-8") if isinstance(prompt, bytes) else str(prompt)
        envelope = json.dumps({"result": json.dumps(prompt_payloads[prompt])}).encode("utf-8")
        return {"result": np.array([envelope], dtype=object)}

    triton = AsyncMock()
    triton.infer = AsyncMock(side_effect=_infer)
    triton.is_model_ready = AsyncMock(return_value=True)
    triton.get_model_metadata = AsyncMock(return_value={"outputs": [{"name": "result"}]})
    return triton


def _fake_triton() -> AsyncMock:
    """Base mock: AsyncMock(.infer, .is_model_ready, .get_model_metadata) with
    the yolo post-NMS canned output as the default (template:
    ai/gateway/tests/test_adapters_yolo26.py:76-87,101). UNVERIFIED."""
    triton = AsyncMock()
    triton.infer = AsyncMock(return_value={"output0": GATEWAY_CANNED_ROWS})
    triton.is_model_ready = AsyncMock(return_value=True)
    triton.get_model_metadata = AsyncMock(return_value={"outputs": [{"name": "output0"}]})
    return triton


@pytest.fixture(scope="module")
def gateway_app():
    """One FastAPI app mounting the FIVE adapter routers with their production
    prefixes (ai/gateway/main.py:181-185) so registry op paths like
    /yolo26/detect resolve. Template: ai/gateway/tests/test_adapters_yolo26.py:90-95
    extended to all five mounts per dossier Q1b/Q5. UNVERIFIED."""
    from importlib import import_module

    from fastapi import FastAPI

    app = FastAPI()
    for prefix, module in GATEWAY_MOUNTS:
        app.include_router(import_module(module).router, prefix=prefix)
    return app


@pytest.fixture
def gateway_triton() -> AsyncMock:
    return _fake_triton()


@pytest.fixture
async def gateway_client(gateway_app, gateway_triton):
    """Patch ALL FIVE module-level get_triton_client names (dossier Q2: five
    distinct targets — a suite patching one silently exercises real gRPC for
    four of five). Template: ai/gateway/tests/test_adapters_yolo26.py:98-104.
    UNVERIFIED."""
    from contextlib import ExitStack

    with ExitStack() as stack:
        for _, module in GATEWAY_MOUNTS:
            stack.enter_context(patch(f"{module}.get_triton_client", return_value=gateway_triton))
        transport = ASGITransport(app=gateway_app)
        async with AsyncClient(transport=transport, base_url="http://gateway") as client:
            yield client


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
            # source: backend/ai_contract/fake/generators.py:215-229 (_yolo_bbox_dict,
            # dict of ints in the 640x480 fake frame, _FAKE_FRAME at :137).
            # fake GREEN (shape already pinned by test_fake_provider.py:194-205; the
            # conformance suite re-pins it provider-agnostically). UNVERIFIED.
            assert set(b) == {"x", "y", "width", "height"}
            assert all(type(v) is int for v in b.values()), "dict-of-INTS, not floats"
            # absolute px, top-left origin, in-frame: the discriminability WITHOUT
            # frame-size luck — an int() truncated from a normalized [0,1] provider
            # box would fail width >= 1 (see G6). UNVERIFIED.
            assert b["x"] >= 0 and b["y"] >= 0
            assert b["width"] >= 1 and b["height"] >= 1
            assert b["x"] + b["width"] <= body["image_width"]
            assert b["y"] + b["height"] <= body["image_height"]

    def test_g1a_yolo_server_emit_block_is_int_truncation(self) -> None:
        """Native per-model server cannot boot in-sandbox (GPU/weights) — pin
        the shipped emission by SOURCE TEXT + pure expression semantics."""
        src = YOLO_SERVER_SRC.read_text(encoding="utf-8")
        # source: ai/yolo26/model.py:1399 (x1,y1,x2,y2 = box.xyxy[0].tolist()) and
        # :1406-1409 ({"x": int(x1), ..., "width": int(x2 - x1), ...}; plan's :1413
        # cite drifted ~4-7 lines, dict literal spans 1403-1411 — dossier G1a).
        # fake N/A (this pins the server column, not the fake).
        # gateway N/A (adapters use round(), pinned in G1b).
        # Predicted GREEN against today's source; a change here is a deliberate act.
        # UNVERIFIED (text pins are format-sensitive — first run confirms).
        assert "x1, y1, x2, y2 = box.xyxy[0].tolist()" in src
        assert '"x": int(x1),' in src
        assert '"width": int(x2 - x1),' in src
        assert '"height": int(y2 - y1),' in src

    def test_g1a_truncation_and_rounding_split_on_fractional_coords(self) -> None:
        """Pure semantics, no I/O: on ANY fractional coord the two shipped paths
        disagree — which is why the suite pins each path to its own truth and
        never asserts cross-provider value-equality on fractional input."""
        # source: server int() ai/yolo26/model.py:1406-1409 vs gateway round()
        # ai/gateway/adapters/yolo26.py:204-207 (dossier G1a/G1b divergence note).
        # fake GREEN-by-agreement: fake emits only ints (generators.py:215) so it is
        # truncation-indistinguishable; a fractional cross-equality pin would be
        # predicted RED against exactly one of {fake-on-server-semantics, gateway}.
        # UNVERIFIED.
        assert int(10.6) == 10  # truncation toward zero
        assert round(10.6) == 11  # rounding to nearest
        assert int(110.5 - 10.6) == 99  # 99.899... truncates to 99
        assert round(110.5 - 10.6) == 100  # while round() gives 100
        assert round(40.5) == 40  # banker's rounding (nearest-even) — shipped behavior
        assert int(40.5) == 40


# ---------------------------------------------------------------------------
# G1b — gateway yolo adapter uses round(): shipped-correct for the gateway path
# ---------------------------------------------------------------------------


class TestG1BGatewayRounds:
    def test_g1b_gateway_adapter_emit_block_is_round(self) -> None:
        src = GATEWAY_YOLO_SRC.read_text(encoding="utf-8")
        # source: ai/gateway/adapters/yolo26.py:204-207 (_postprocess_post_nms,
        # def at :164) and the identical pre_nms twin at :321-324 (def at :215);
        # plan's :199 cite is the confidence-clamp block (dossier correction).
        # fake N/A (fake never runs this module). gateway GREEN — this is the
        # shipped gateway truth the suite pins as correct (WP6-C-style ruling
        # territory: divergence parked, adapter is shipped-correct for its path).
        # UNVERIFIED.
        assert src.count('"x": round(bx1),') == 2
        assert src.count('"width": round(box_w),') == 2

    async def test_g1b_gateway_http_path_emits_rounded_dict_bbox(self, gateway_client) -> None:
        """Full gateway drive: multipart upload -> patched Triton canned rows ->
        adapter output. Pins the ADAPTER behavior as shipped-correct for the
        gateway provider path."""
        r = await gateway_client.post(
            "/yolo26/detect", files={"file": ("frame.png", _png_bytes(), "image/png")}
        )
        assert r.status_code == 200, r.text
        body = r.json()
        dets = body["detections"]
        assert len(dets) == 1
        d = dets[0]
        # source: canned row [10.6, 20.4, 110.5, 60.9, 0.9, 0] through
        # _postprocess_post_nms (ai/gateway/adapters/yolo26.py:164,204-207) with
        # 640x640 input => scale=1, pad=0 (ai/gateway/utils.py:202-207); cls 0 =
        # COCO "person" (adapters/yolo26.py:41+). gateway GREEN predicted;
        # fake N/A (fake has no triton). UNVERIFIED (a one-shot import-level probe
        # of _postprocess_post_nms agreed: {'x':11,'y':20,'width':100,'height':40}).
        assert d["class"] == "person"
        assert d["bbox"] == GATEWAY_CANNED_ROUNDED
        assert all(type(v) is int for v in d["bbox"].values())
        assert body["image_width"] == 640 and body["image_height"] == 640

    async def test_g1b_round_vs_truncate_splits_the_two_shipped_paths(self, gateway_client) -> None:
        """Same fractional xyxy, both shipped semantics: the gateway adapter and
        the native server expression DIFFER on x and width. Predicted:
        gateway GREEN on its own equality; the server-semantic equality is
        N/A-in-sandbox (characterization only) — a cross-provider value-equality
        assertion on fractional input would be predicted RED against exactly one
        provider, which the dossier flags as the naive-pin trap. UNVERIFIED."""
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
        }  # source: ai/yolo26/model.py:1399,1406-1409. UNVERIFIED.
        assert gateway_bbox == GATEWAY_CANNED_ROUNDED  # gateway GREEN (round path)
        assert server_semantics == GATEWAY_CANNED_TRUNCATED  # pure-expression pin
        assert gateway_bbox != server_semantics  # the ±1px divergence, proven per-path


# ---------------------------------------------------------------------------
# G2 — Florence bbox: LIST [x1,y1,x2,y2] of floats (opposite convention to G1)
# ---------------------------------------------------------------------------


class TestG2FlorenceListBbox:
    async def test_g2_fake_florence_bbox_is_list_of_four_floats(self, fake_client) -> None:
        r = await fake_client.post("/florence/detect", **_request_kwargs("florence_detect"))
        assert r.status_code == 200
        dets = r.json()["detections"]
        assert dets
        for d in dets:
            b = d["bbox"]
            # source: fake _florence_bbox arity-4 (generators.py:178-201) +
            # _OVERRIDES[("florence_detect","bbox")] = ("florence_bbox", 4)
            # (generators.py:249-257); server mirror ai/florence/model.py:207
            # (bbox: list[float], "[x1, y1, x2, y2]"). fake GREEN. UNVERIFIED.
            assert isinstance(b, list) and len(b) == 4
            assert all(isinstance(v, float) for v in b), "list-of-FLOATS (G1 ships ints)"
            assert b[0] < b[2] and b[1] < b[3]  # xyxy top-left -> bottom-right

    async def test_g2_gateway_florence_bbox_is_list_of_four_floats(
        self, gateway_client, gateway_triton
    ) -> None:
        """Gateway florence adapter driven with a canned <OD> backend result:
        the adapter mirrors the server's bboxes verbatim into list[float]."""
        gateway_triton.infer = _florence_triton(
            {
                "<OD>": {
                    "labels": ["person", "car"],
                    "bboxes": [[10.5, 20.25, 110.75, 60.5], [200.0, 50.0, 400.0, 300.0]],
                }
            }
        ).infer
        r = await gateway_client.post("/florence/detect", json={"image": "ZmFrZS1pbWFnZQ=="})
        assert r.status_code == 200, r.text
        dets = r.json()["detections"]
        # source: ai/gateway/adapters/florence.py:393-409 (detect route; Detection
        # response model :83-86 bbox: list[float]); canned pass-through means the
        # emitted bboxes are the canned ones. gateway GREEN predicted. fake GREEN
        # (same shape, driven in the test above). UNVERIFIED.
        assert len(dets) == 2
        for d in dets:
            b = d["bbox"]
            assert isinstance(b, list) and len(b) == 4
            assert all(isinstance(v, float) for v in b)
        assert dets[0]["bbox"] == [10.5, 20.25, 110.75, 60.5]

    def test_g2_contract_schema_carries_no_arity_constraint(self) -> None:
        """The 4-vs-8 swap and xyxy-vs-xywh swap are NOT schema-catchable: the
        committed snapshots bound bbox only as array-of-number (dossier G2/G3
        structural finding). Characterization — pins the CONTRACT GAP so a
        future schema tightening is a visible, deliberate act."""
        for name in ("florence_detect", "florence_ocr_with_regions"):
            schema = json.loads((SCHEMA_DIR / f"{name}.response.json").read_text(encoding="utf-8"))
            defs = schema["$defs"]
            bbox = next(
                defs[k]["properties"]["bbox"]
                for k in defs
                if k.endswith(("Detection", "OCRRegion"))
            )
            # source: backend/ai_contract/schemas/florence_detect.response.json
            # ($defs.Detection.properties.bbox = {items:{type:number}, type:array},
            # verified) and florence_ocr_with_regions.response.json ($defs.OCRRegion).
            # fake N/A (contract artifact, not provider behavior). gateway N/A.
            # Predicted GREEN against the committed snapshots. UNVERIFIED.
            assert bbox["type"] == "array"
            assert bbox["items"]["type"] == "number"
            assert "minItems" not in bbox and "maxItems" not in bbox
            assert "prefixItems" not in bbox


# ---------------------------------------------------------------------------
# G3 — Florence OCR regions carry EIGHT floats (quad corners flattened)
# ---------------------------------------------------------------------------


class TestG3FlorenceOcrQuads:
    async def test_g3_fake_ocr_regions_are_eight_floats(self, fake_client) -> None:
        r = await fake_client.post(
            "/florence/ocr-with-regions", **_request_kwargs("florence_ocr_with_regions")
        )
        assert r.status_code == 200
        regions = r.json()["regions"]
        assert regions
        for reg in regions:
            b = reg["bbox"]
            # source: fake _OVERRIDES[("florence_ocr_with_regions","bbox")] =
            # ("florence_bbox", 8) at generators.py:261; quad layout (x1,y1)
            # (x2,y1) (x2,y2) (x1,y2) at generators.py:187-196. fake GREEN. UNVERIFIED.
            assert isinstance(b, list) and len(b) == 8, "OCR quads are EIGHT floats, not 4"
            assert all(isinstance(v, float) for v in b)
            # axis-aligned quad TL,TR,BR,TL-order (x1,y1)(x2,y1)(x2,y2)(x1,y2):
            # corner REPEATS, not collapsed sets. Discovery fix: the drafted
            # set-collapse assertion was wrong (the x set is {x1,x2}, two
            # distinct values). First-run red → assertion bug, fake behavior
            # is correct quad semantics (generators.py:187-196).
            assert b[0] == b[6] and b[2] == b[4], "x repeats TL/TR/TR/TL"
            assert b[1] == b[3] and b[5] == b[7], "y repeats TL/TL/BR/BR"
            assert b[0] != b[2] and b[1] != b[5], "a real box, not a duplicated 4"

    async def test_g3_gateway_ocr_quad_flattens_to_eight_floats(
        self, gateway_client, gateway_triton
    ) -> None:
        """Canned NESTED quad ([[x,y]x4]) through the adapter's flatten step —
        the same flatten the server ships (ai/florence/model.py:1101-1105)."""
        gateway_triton.infer = _florence_triton(
            {
                "<OCR_WITH_REGION>": {
                    "quad_boxes": [[[10.0, 20.0], [110.0, 20.0], [110.0, 70.0], [10.0, 70.0]]],
                    "labels": ["HELLO WORLD"],
                }
            }
        ).infer
        r = await gateway_client.post(
            "/florence/ocr-with-regions", json={"image": "ZmFrZS1pbWFnZQ=="}
        )
        assert r.status_code == 200, r.text
        regions = r.json()["regions"]
        assert len(regions) == 1
        # source: ai/gateway/adapters/florence.py:381-385 — `if bbox and
        # isinstance(bbox[0], list): bbox = [coord for point in bbox for coord in
        # point]` then OCRRegion(text=label, bbox=bbox). gateway GREEN predicted.
        # fake GREEN (same 8-arity, own generator). UNVERIFIED.
        assert regions[0]["bbox"] == [10.0, 20.0, 110.0, 20.0, 110.0, 70.0, 10.0, 70.0]
        assert len(regions[0]["bbox"]) == 8

    def test_g3_server_flatten_and_quad_description_characterization(self) -> None:
        """Native florence server can't boot here (transformers/GPU import) —
        pin the shipped flatten + the EIGHT-float field description by source."""
        src = FLORENCE_SERVER_SRC.read_text(encoding="utf-8")
        # source: ai/florence/model.py:189-192 (OCRRegion.bbox Field description
        # "[x1, y1, x2, y2, x3, y3, x4, y4] (quadrilateral corners)"; plan cite
        # :190 lands inside the Field call) and the flatten at :1101-1105
        # (second site :1263-1267). fake N/A (server column pin).
        # gateway GREEN-equivalent: the adapter carries the identical flatten
        # (adapters/florence.py:383-384, pinned behaviorally in the test above).
        # Predicted GREEN against today's source. UNVERIFIED.
        assert "[x1, y1, x2, y2, x3, y3, x4, y4]" in src
        assert "if bbox and isinstance(bbox[0], list):" in src
        assert "bbox = [coord for point in bbox for coord in point]" in src


# ---------------------------------------------------------------------------
# G4 — FOURTH spelling: {x1,y1,x2,y2} dicts (request-side / backend-internal)
# ---------------------------------------------------------------------------


class TestG4FourthSpelling:
    def test_g4_fourth_spelling_shape_and_rarity(self) -> None:
        """The x1-dict spelling exists, is CORNERS not x/y/w/h, and lives on the
        request/backend-internal side — with the dossier's corrected counts
        (the plan's '~30 enrichment literals' was ~4x overstated: enrichment_client
        has exactly ONE; ai/ has ZERO)."""
        from backend.services.florence_client import BoundingBox as FlorenceBoundingBox

        d = FlorenceBoundingBox(x1=10.0, y1=20.0, x2=30.0, y2=40.0).as_dict()
        # source: backend/services/florence_client.py:84-88 (as_dict) + :87 order
        # x1,y1,x2,y2 (class at :85 region; dossier G4 representative-site list).
        # fake N/A / gateway N/A — matrix-only property (no provider RESPONSE
        # returns an x1 dict; pinned by the next test). UNVERIFIED.
        assert json.dumps(d) == '{"x1": 10.0, "y1": 20.0, "x2": 30.0, "y2": 40.0}'
        assert d["x2"] - d["x1"] == 20.0  # keys are corners, not x/width

        enrich_src = (REPO_ROOT / "backend/services/enrichment_client.py").read_text(
            encoding="utf-8"
        )
        assert enrich_src.count('"x1":') == 1
        # source: backend/services/enrichment_client.py:3161-3166 (unified-enrichment
        # request payload `"bbox": {"x1": bbox[0], ...}`; the ONLY such literal in
        # the file — dossier G4 corrected count). Predicted GREEN. UNVERIFIED.
        ai_tree = REPO_ROOT / "ai"
        x1_in_ai = sum(
            p.read_text(encoding="utf-8").count('"x1":')
            for p in ai_tree.rglob("*.py")
            if "__pycache__" not in p.parts and "/tests/" not in str(p.relative_to(REPO_ROOT))
        )
        assert x1_in_ai == 0
        # source: dossier G4 — "ai/ (incl. ai/enrichment) has ZERO `\"x1\":`
        # literals" — TRUE ON THE PRODUCTION SURFACE. First-run discovery: ai/
        # carries exactly 12 hits and ALL live under ai/*/tests/ canned fixtures
        # (test_adapters_florence.py:364,385,386; test_region_endpoints.py x9) —
        # server-side TEST payloads, never a provider response shape. Scoped to
        # non-test files, matching the G6 finding "no provider RESPONSE emits
        # the x1-dict". The repo-wide totals (57 incl. tests / 7 outside tests)
        # are deliberately NOT pinned — drift-hostile (see module notes).

    async def test_g4_no_provider_response_emits_fourth_spelling(
        self, fake_client, gateway_client, gateway_triton
    ) -> None:
        """MATRIX-ONLY consequence, asserted: no provider RESPONSE shape carries
        the x1-dict spelling — fake yolo emits x/y/width/height dicts and fake +
        gateway florence emit lists. A naive 'all bboxes are dict-or-list of 4'
        provider assertion cannot catch fourth-spelling rot."""
        # source: fake generators _yolo_bbox_dict (generators.py:215-229) +
        # _florence_bbox (:178-201); gateway florence detect route
        # (adapters/florence.py:393-409). fake GREEN; gateway GREEN (canned drive).
        # UNVERIFIED.
        for client, path, kwargs in (
            (fake_client, "/yolo26/detect", _request_kwargs("yolo26_detect")),
            (fake_client, "/florence/detect", _request_kwargs("florence_detect")),
        ):
            r = await client.post(path, **kwargs)
            assert r.status_code == 200
            assert '"x1"' not in r.text, path

        gateway_triton.infer = _florence_triton(
            {"<OD>": {"labels": ["person"], "bboxes": [[1.0, 2.0, 3.0, 4.0]]}}
        ).infer
        r = await gateway_client.post("/florence/detect", json={"image": "ZmFrZS1pbWFnZQ=="})
        assert r.status_code == 200
        assert '"x1"' not in r.text


# ---------------------------------------------------------------------------
# G5 — bbox_validation.py docstring asserts a FALSE invariant (characterization)
# ---------------------------------------------------------------------------


class TestG5BboxValidationFalseInvariant:
    def test_g5_xywh_box_passes_every_validator_check(self) -> None:
        """THE characterization: feed the yolo-style xywh tuple (100,150,300,400)
        (x=100 y=150 w=300 h=400) through the validator and PIN that it PASSES
        and is silently re-read as a 200x250 xyxy box. Convention-blindness is
        proven by characterization, NOT fixed (WP6-C ruling territory — parked
        as characterization; no xfail, the test is predicted GREEN as shipped).
        """
        from backend.services.bbox_validation import (
            clamp_bbox_to_image,
            is_valid_bbox,
            validate_bbox,
        )

        xywh = (100.0, 150.0, 300.0, 400.0)
        # source: backend/services/bbox_validation.py — is_valid_bbox :121-157
        # tests only x2>x1, y2>y1, finite, sign; validate_bbox :160+ adds optional
        # strict_bounds (640x480 passes); clamp_bbox_to_image :258+ returns an
        # in-bounds box unchanged. Dossier G5 (all verified). fake N/A (backend
        # infra, not provider behavior) — driven with provider outputs below.
        # gateway N/A — same. UNVERIFIED.
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
        # yolo ships {x,y,width,height} int dicts (G1) and the Detection DB
        # stores x/y/w/h ints (G6). Predicted GREEN (the sentence is present).
        # UNVERIFIED.
        assert bbox_validation.__doc__ is not None
        assert "All bounding boxes in this system use the format (x1, y1, x2, y2)" in (
            bbox_validation.__doc__
        )
        lines = (
            (REPO_ROOT / "backend/services/bbox_validation.py")
            .read_text(encoding="utf-8")
            .splitlines()
        )
        assert lines[6].strip().startswith("All bounding boxes")  # the :7 cite itself

    def test_g5_cited_call_sites_exist(self) -> None:
        """The plan's unprotected-callers cite holds verbatim (dossier G5: call
        sites exist; current direct callers feed xyxy, but the validator cannot
        ENFORCE the convention either way)."""
        # source: backend/services/reid_service.py:482
        # `if not is_valid_bbox(bbox_float, allow_negative=True):` and
        # backend/services/enrichment_client.py:1965
        # `if not is_valid_bbox(bbox, allow_negative=True):` — both grepped
        # present. Predicted GREEN. UNVERIFIED.
        reid_src = (REPO_ROOT / "backend/services/reid_service.py").read_text(encoding="utf-8")
        assert "is_valid_bbox(bbox_float, allow_negative=True)" in reid_src
        enrich_src = (REPO_ROOT / "backend/services/enrichment_client.py").read_text(
            encoding="utf-8"
        )
        assert "is_valid_bbox(bbox, allow_negative=True)" in enrich_src

    async def test_g5_provider_shapes_are_indistinguishable_to_the_validator(
        self, fake_client
    ) -> None:
        """Feed the fake's own two shipped spellings through the validator:
        florence's 4-float xyxy list and the yolo dict re-projected as a tuple
        are accepted IDENTICALLY — the validator cannot tell a real xyxy box
        from an xywh box, which is the mechanism behind G5."""
        from backend.services.bbox_validation import is_valid_bbox

        r = await fake_client.post("/florence/detect", **_request_kwargs("florence_detect"))
        flo = tuple(r.json()["detections"][0]["bbox"])
        r2 = await fake_client.post("/yolo26/detect", **_request_kwargs("yolo26_detect"))
        b = r2.json()["detections"][0]["bbox"]
        yolo_as_tuple = (b["x"], b["y"], b["x"] + b["width"], b["y"] + b["height"])
        # source: fake shapes generators.py:178-201,215-229 fed to
        # is_valid_bbox (bbox_validation.py:121-157). fake GREEN (both accept);
        # the PAIR is the point: an xywh box and an xyxy box are the same
        # 4-tuple to this validator. UNVERIFIED.
        assert is_valid_bbox(flo, allow_negative=True) is True
        assert is_valid_bbox(yolo_as_tuple, allow_negative=True) is True


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
        # verified str(type) == "INTEGER"). fake/gateway N/A (DB layer). UNVERIFIED.
        assert cols["bbox_x"] == "INTEGER"
        assert cols["bbox_width"] == "INTEGER"
        assert cols["bbox_y"] == "INTEGER"
        assert cols["bbox_height"] == "INTEGER"

    def test_g6_normalized_floats_collapse_to_zero_silently(self) -> None:
        """Negative property (matrix-only per dossier G6): a hypothetical
        [0,1]-emitting provider is UNDETECTABLE at this layer — the app-boundary
        int() coercion (not the DB) does the damage, and the downstream guard
        silently DROPS the detection with no error."""
        normalized = {"x": 0.87, "y": 0.42, "width": 0.31, "height": 0.19}
        coerced = {k: int(v) for k, v in normalized.items()}
        # source: backend/services/detector_client.py:1333-1336
        # (`bbox_x = int(bbox["x"]); ...` — verified at :1333) and the silent
        # record-and-continue skip at :1379 (`if bbox_width < 1 or
        # bbox_height < 1:` — dossier's :1380-1388 cite drifted one line).
        # fake GREEN-as-negative (fake never emits normalized — pinned below);
        # gateway same (adapter clamps+rounds to absolute px). UNVERIFIED.
        assert coerced == {"x": 0, "y": 0, "width": 0, "height": 0}
        det_src = (REPO_ROOT / "backend/services/detector_client.py").read_text(encoding="utf-8")
        assert 'bbox_x = int(bbox["x"])' in det_src
        assert "if bbox_width < 1 or bbox_height < 1:" in det_src

    async def test_g6_registered_provider_paths_emit_absolute_pixels(
        self, fake_client, gateway_client, gateway_triton
    ) -> None:
        """The positive guard that keeps G6 a latent hazard rather than a live
        one: every drivable provider path emits ABSOLUTE px — yolo int coords
        with width >= 1, florence floats > 1 (a normalized frame-relative box
        would truncate to 0 / compare <= 1 on realistic frames)."""
        r = await fake_client.post("/yolo26/detect", **_request_kwargs("yolo26_detect"))
        for d in r.json()["detections"]:
            # source: fake _yolo_bbox_dict in-frame ints (generators.py:215-229,
            # _FAKE_FRAME (640, 480) at :137). fake GREEN. UNVERIFIED.
            assert d["bbox"]["width"] >= 1 and d["bbox"]["height"] >= 1
            assert d["bbox"]["x"] >= 0 and d["bbox"]["y"] >= 0
        r = await fake_client.post("/florence/detect", **_request_kwargs("florence_detect"))
        for d in r.json()["detections"]:
            # fake florence coords are drawn from [8, 368]/[8, 276] ranges
            # (generators.py:181-183) => every coord > 1.0, i.e. NOT normalized.
            # fake GREEN. UNVERIFIED.
            assert all(v > 1.0 for v in d["bbox"])

        gateway_triton.infer = _florence_triton(
            {"<OD>": {"labels": ["person"], "bboxes": [[10.5, 20.25, 110.75, 60.5]]}}
        ).infer
        r = await gateway_client.post("/florence/detect", json={"image": "ZmFrZS1pbWFnZQ=="})
        assert r.status_code == 200
        for d in r.json()["detections"]:
            assert all(v > 1.0 for v in d["bbox"])
        # Restore the yolo canned output: the shared fixture mock is the SAME
        # object for all five adapters, and the florence _infer side-effect
        # reads inputs["prompt"] — a yolo request (inputs={"images": …})
        # KeyErrors there. Discovery fix (first-run KeyError: 'prompt').
        gateway_triton.infer = AsyncMock(return_value={"output0": GATEWAY_CANNED_ROWS})
        r = await gateway_client.post(
            "/yolo26/detect", files={"file": ("frame.png", _png_bytes(), "image/png")}
        )
        assert r.status_code == 200
        for d in r.json()["detections"]:
            # gateway GREEN predicted: round() output is absolute px with
            # width >= 1 (the canned width is 100). UNVERIFIED.
            assert d["bbox"]["width"] >= 1 and d["bbox"]["height"] >= 1


# ---------------------------------------------------------------------------
# G7 — FlorenceClient.detect validates NOTHING; absent score becomes MAX (1.0)
# ---------------------------------------------------------------------------


class TestG7FlorenceZeroValidationAndScoreDefault:
    @pytest.fixture
    def florence_client_no_net(self):
        """FlorenceClient whose persistent httpx pools are mocks — the repo's
        own idiom (backend/tests/unit/services/test_florence_client.py:85-95).
        NO network: base_url is never dialed; post is replaced per-test.
        UNVERIFIED."""
        from backend.services.florence_client import FlorenceClient

        main_client = AsyncMock()
        health_client = AsyncMock()
        with patch(
            "backend.services.florence_client.httpx.AsyncClient",
            side_effect=[main_client, health_client],
            autospec=True,
        ):
            return FlorenceClient(base_url="http://florence.invalid")

    def test_g7_score_defaults_to_1_0_when_absent(self) -> None:
        """Omitted confidence == MAXIMUM confidence, on both the client mirror
        and the server model, plus the committed schema's default."""
        from backend.services.florence_client import Detection as ClientDetection

        assert ClientDetection(label="x", bbox=[]).score == 1.0
        # source: backend/services/florence_client.py:59-64 (dataclass Detection,
        # slots, `score: float = 1.0` at :63). fake N/A (client-side mirror);
        # gateway ships the same degeneracy (pinned by the drive below).
        # UNVERIFIED.

        schema = json.loads(
            (SCHEMA_DIR / "florence_detect.response.json").read_text(encoding="utf-8")
        )
        det = schema["$defs"]["Detection"]
        # source: florence_detect.response.json score {default: 1.0} and
        # required == ["label", "bbox"] (score NOT required — verified).
        # Predicted GREEN. UNVERIFIED.
        assert det["properties"]["score"]["default"] == 1.0
        assert "score" not in det["required"]

        srv_src = FLORENCE_SERVER_SRC.read_text(encoding="utf-8")
        # source: ai/florence/model.py:208 (score: float = Field(default=1.0))
        # and the /detect route hard-coding score=1.0 at :1150 because
        # "Florence-2 OD doesn't return scores". Predicted GREEN (source pin).
        # UNVERIFIED.
        assert "score: float = Field(default=1.0" in srv_src
        assert "Detection(label=label, bbox=bbox, score=1.0)" in srv_src

    async def test_g7_client_detect_zero_validation(self, florence_client_no_net) -> None:
        """Zero validation of bbox arity/dtype/convention: string coords survive,
        absent bbox becomes [], absent score becomes 1.0, out-of-band score 42
        survives (no [0,1] clamp on this dataclass). CHARACTERIZATION of shipped
        client behavior; the fix lives under a ruling, not here."""
        from backend.services.florence_client import FlorenceClient  # noqa: F401  (fixture type)
        from PIL import Image

        resp = MagicMock()
        resp.status_code = 200
        resp.raise_for_status = MagicMock()
        resp.json.return_value = {
            "detections": [
                {"label": "person"},  # NO bbox, NO score
                {"label": "car", "bbox": ["a", "b"], "score": 42},  # string coords
            ],
            "inference_time_ms": 1.0,
        }
        florence_client_no_net._http_client.post = AsyncMock(return_value=resp)

        dets = await florence_client_no_net.detect(Image.new("RGB", (8, 8)))
        # source: backend/services/florence_client.py:1054 (async def detect),
        # parse at :1100-1106 `Detection(label=d.get("label",""),
        # bbox=d.get("bbox",[]), score=d.get("score",1.0))` — plan's :1101 cite
        # lands in the comprehension. Dataclass is plain slots (:59-64), no
        # validator. fake N/A (client wrapper, not provider shape).
        # gateway-adapter comparison: the adapter route (adapters/florence.py:
        # 406) ALSO hard-codes score=1.0 — pinned in the test below. UNVERIFIED.
        assert dets[0].bbox == [] and dets[0].score == 1.0  # absent bbox/score: silent
        assert dets[1].bbox == ["a", "b"]  # dtype NEVER validated — strings survive
        assert dets[1].score == 42  # no [0,1] clamp (contrast SecurityObjectDetection
        # ge=0/le=1 at ai/florence/model.py:237-239 — the ONLY clamped sibling)

    async def test_g7_gateway_od_ships_max_score_for_every_detection(
        self, gateway_client, gateway_triton
    ) -> None:
        """Provider-SPLIT characterization (dossier G7 divergence): the real
        Florence OD path ships score == 1.0 for EVERY detection (omitted
        confidence == max), while the fake's schema walker emits varied floats —
        so a cross-provider "scores reflect model confidence / not constant"
        assertion is predicted RED against the gateway path and is NOT written;
        each side gets its own pinned truth instead."""
        gateway_triton.infer = _florence_triton(
            {
                "<OD>": {
                    "labels": ["person", "car"],
                    "bboxes": [[10.0, 20.0, 110.0, 60.0], [200.0, 50.0, 400.0, 300.0]],
                    # NOTE: even a score-bearing task payload is IGNORED by the
                    # route — the adapter hard-codes score=1.0.
                    "scores": [0.11, 0.9],
                }
            }
        ).infer
        r = await gateway_client.post("/florence/detect", json={"image": "ZmFrZS1pbWFnZQ=="})
        assert r.status_code == 200, r.text
        dets = r.json()["detections"]
        # source: ai/gateway/adapters/florence.py:406 `detections.append(
        # Detection(label=label, bbox=bbox, score=1.0))` — canned payload scores
        # deliberately absent from the response. gateway GREEN (constant 1.0 is
        # the shipped truth). fake GREEN on its own (schema-valid ∈ [0,1] below).
        # UNVERIFIED.
        assert len(dets) == 2
        assert all(d["score"] == 1.0 for d in dets)

    async def test_g7_fake_scores_stay_in_unit_interval(self, fake_client) -> None:
        """Fake-side complement to the split above: FakeProvider's emitted
        florence scores stay schema-valid floats in [0,1] (they VARY from the
        gateway's constant 1.0 — the divergence the test above pins per-path)."""
        r = await fake_client.post("/florence/detect", **_request_kwargs("florence_detect"))
        assert r.status_code == 200
        scores = [d.get("score") for d in r.json()["detections"]]
        # source: fake schema-walker generation (generators.py; florence_detect
        # snapshot score {type:number, default:1.0}). fake GREEN predicted
        # (score may be ABSENT — the snapshot does not require it — hence .get
        # and the None branch). UNVERIFIED: whether the walker emits the optional
        # score at all is the one shape fact in this module not settled by the
        # dossier; if it emits >1 values this prediction flips RED — flag for
        # first run.
        for s in scores:
            assert s is None or 0.0 <= s <= 1.0
