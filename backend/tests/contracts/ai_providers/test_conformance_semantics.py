"""WP8.3 conformance suite — cluster "semantics" (S1..S9). DRAFT.

Per-property module toward ``backend/tests/contracts/ai_providers/test_conformance.py``
(plan docs/superpowers/plans/2026-09-19-swap-readiness-72h.md §WP8.3,
"_Semantics no schema can catch_", plan lines 955-981). This file WILL be
copied verbatim into backend/tests/contracts/ai_providers/ (parents[4] correct
there, mirrors test_fake_provider.py:47; WRONG while this draft sits under /tmp).

S1..S9 map 1:1 to the nine plan bullets, in order:
  S1 pose keypoints POSITIONAL COCO-17 in JSONB, no names on the wire
  S2 embedding-space tag: get_embedding_model() has zero production callers
  S3 Florence prompts are literal Florence-2 control tokens passed through
  S4 caption language (English keyword contract) in severityCalculator.ts
  S5 think-tag stripping regex; unclosed tag passes raw text through
  S6 confidence.ts THROWS outside [0,1] (percentage provider crashes the UI)
  S7 four divergent risk-band tables for one 0-100 score
  S8 OP 28 action-classify: the only multi-frame operation (own block)
  S9 composite /enrich: highest-value single conformance target

EVIDENCE NOTE (honesty rule): the parent-specified dossier
``.wp25-feed/wp83-evidence/full-results.json`` (semantics S1..Sn + Q1-Q7)
DOES NOT EXIST on this tree (directory missing; verified filesystem-wide —
only /tmp/wp25/wp83-draft/ siblings survive). Findings re-derived FIRST-HAND
from plan lines 955-981 + the current tree; EVERY cite was re-verified by
reading the file on 2026-09-19. Plan-text deltas are "PLAN CITE CORRECTION".

Driving shapes (provenance: test_conformance_geometry.py:66-170 + the real
run in /tmp/wp25/wp83-discovery.log): fake via httpx.ASGITransport over
create_fake_app(); gateway over FIVE adapter routers + FIVE module-level
get_triton_client patches (patching ai.gateway.triton_client alone hits
NOTHING); canned post-NMS rows must be (1, N, 6) (the adapter strips the
batch dim, adapters/yolo26.py:153 — the (1,6) shape died IndexError at :178);
per_model_http / llamacpp_llm / gateway_light are MATRIX-GUARD-ONLY, their
callables NEVER invoked. Legend: fake/gateway GREEN/RED = predicted verdict;
N/A = undrivable for this property by design; probe-verified = executed this
session via one-shot .venv/bin/python (NOT pytest — pytest-level verdicts
stay UNVERIFIED).

Cluster verdict summary (predicted): REDS: none. Hazards are pinned
per-path; shipped-correct behavior is CHARACTERIZED (plan §WP8.3 (b)); the
cross-provider splits (fake's nameless-keypoint dicts vs the gateway's named
dicts; fake's frame-blindness on the only multi-frame op) are SPLIT
assertions stating both sides, never a cross-provider equality that goes red
on one. UNVERIFIED.

No xfail / skip / importorskip anywhere (goal rule). Parked-ruling
characterizations are plain assertions of CURRENT shipped behavior with a
docstring naming what a ruling would change.
"""

from __future__ import annotations

import ast
import io
import json
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, patch

import numpy as np
import pytest
from backend.ai_contract.operations import OPERATIONS
from backend.ai_contract.provider import (
    PROVIDER_SLOT,
    ProviderId,
    operations_for_slot,
    register_provider,
    registered_providers,
)
from httpx import ASGITransport, AsyncClient

REPO_ROOT = Path(__file__).resolve().parents[4]  # correct at final placement
GOLDEN_DIR = REPO_ROOT / "backend/tests/contracts/ai_providers/golden/payloads"
SCHEMA_DIR = REPO_ROOT / "backend" / "ai_contract" / "schemas"

# --- sources under characterization (paths only; read lazily per test) -----
ENRICHMENT_MODEL_SRC = REPO_ROOT / "backend" / "models" / "enrichment.py"
POSE_EST_SRC = REPO_ROOT / "ai" / "yolo26" / "pose_estimation.py"
PIPELINE_SRC = REPO_ROOT / "backend" / "services" / "enrichment_pipeline.py"
ENTITY_SRC = REPO_ROOT / "backend" / "models" / "entity.py"
VISION_EXTRACTOR_SRC = REPO_ROOT / "backend" / "services" / "vision_extractor.py"
GATEWAY_FLORENCE_SRC = REPO_ROOT / "ai" / "gateway" / "adapters" / "florence.py"
SEVERITY_TS_SRC = REPO_ROOT / "frontend" / "src" / "utils" / "severityCalculator.ts"
CONFIDENCE_TS_SRC = REPO_ROOT / "frontend" / "src" / "utils" / "confidence.ts"
ANALYZER_SRC = REPO_ROOT / "backend" / "services" / "nemotron_analyzer.py"
GATEWAY_ENRICH_SRC = REPO_ROOT / "ai" / "gateway" / "adapters" / "enrichment.py"

# --- registry constants (verified live 2026-09-19) --------------------------
AC_OP = "enrichment_action_classify"  # plan's "OP 28"
ENRICH_OP = "enrichment_enrich"
SIBLING_SENTINELS = {
    ProviderId.GATEWAY: {
        "enrich_lt_depth_estimate",
        "enrich_lt_pet_classify",
        "enrich_lt_pose_analyze",
        # A7.2: florence_analyze_scene deleted from the contract;
        # yolo26_segment joined (client method deleted, route deployed).
        "yolo26_detect_batch",
        "yolo26_segment",
    },
    ProviderId.GATEWAY_LIGHT: {
        "enrich_lt_depth_estimate",
        "enrich_lt_pet_classify",
        "enrich_lt_pose_analyze",
    },
    ProviderId.PER_MODEL_HTTP: {
        "enrich_lt_depth_estimate",
        "enrich_lt_pet_classify",
        "enrich_lt_pose_analyze",
        # florence_analyze_scene: op deleted (A7.2). yolo26_segment is NOT
        # here: gateway-only column (per_model_server=False) - ABSENT, not
        # not-wired. Mirrors test_conformance_ops SENTINELS_PER_MODEL.
        "yolo26_detect_batch",
        "llm_completion",
        "llm_chat_completion",
        "model_unload",
        # 1.1: vlm_assess enters the union column unbound (vlm_client is
        # step 1.3) - mirrored from the ops-sibling literal.
        "vlm_assess",
    },
}  # source: test_conformance_ops.py:139-158 (real run agreed)

# --- the canonical COCO-17 order, transcribed from the two PRODUCTION
# name tables, NOT invented: ai/yolo26/pose_estimation.py:58 (KEYPOINT_NAMES)
# and (until the WP3.4 A6 deletion) backend/api/helpers/enrichment_transformers.py:441
# (coco_keypoint_order, function-local). Both verified 2026-09-19; the two
# lists were IDENTICAL — pose_estimation.py is the surviving production table.
COCO_17 = (
    "nose",
    "left_eye",
    "right_eye",
    "left_ear",
    "right_ear",
    "left_shoulder",
    "right_shoulder",
    "left_elbow",
    "right_elbow",
    "left_wrist",
    "right_wrist",
    "left_hip",
    "right_hip",
    "left_knee",
    "right_knee",
    "left_ankle",
    "right_ankle",
)


# ---------------------------------------------------------------------------
# Request-shape helper (fake-driven) — copied shape from
# test_conformance_geometry.py:85-101 / test_fake_provider.py:72-98.
# ---------------------------------------------------------------------------
def _request_kwargs(op_id: str) -> dict[str, Any]:
    from backend.ai_contract.operations import OPERATIONS as _OPS

    if _OPS[op_id].method == "GET":
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
# (mechanics per the geometry module's discovery fixes; see module docstring).
# ---------------------------------------------------------------------------
GATEWAY_MOUNTS = (
    ("/yolo26", "ai.gateway.adapters.yolo26"),
    ("/clip", "ai.gateway.adapters.clip"),
    ("/florence", "ai.gateway.adapters.florence"),
    ("/enrichment", "ai.gateway.adapters.enrichment"),
    ("/enrich-lt", "ai.gateway.adapters.enrichment_light"),
)  # source: ai/gateway/main.py:181-185 (mount prefixes)


def _png_bytes(width: int = 640, height: int = 640) -> bytes:
    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (width, height), (7, 23, 41)).save(buf, format="PNG")
    return buf.getvalue()


# Canned post-NMS row [x1, y1, x2, y2, conf, cls] in 640-space, batched as
# (1, N, 6) — the geometry module's discovery fix (docstring above).
GATEWAY_CANNED_ROWS = np.array([[[10.0, 20.0, 110.0, 60.0, 0.9, 0]]], dtype=np.float64)


def _fake_triton() -> AsyncMock:
    triton = AsyncMock()
    triton.infer = AsyncMock(return_value={"output0": GATEWAY_CANNED_ROWS})
    triton.is_model_ready = AsyncMock(return_value=True)
    triton.get_model_metadata = AsyncMock(return_value={"outputs": [{"name": "output0"}]})
    return triton


def _enrich_triton() -> AsyncMock:
    """Route-aware mock for the /enrich composite drive. Model names are the
    gateway's own: fashion_clip -> {"embedding"} (adapters/enrichment.py:451,
    result["embedding"]), demographics_age/gender + vehicle -> {"output"}
    logits (adapters/enrichment.py:494,381). Pose is NOT fanned out by the
    shipped /enrich person branch (gather covers clothing + demographics
    only, :914-918 — see S9 docstring)."""

    async def _infer(*, model_name: str, inputs: Any, outputs: Any) -> dict[str, Any]:
        if model_name == "fashion_clip":
            return {"embedding": np.zeros((1, 768), dtype=np.float32)}
        if model_name in ("demographics_age", "vehicle"):
            return {"output": np.array([[3.0, 0.1, 0.1, 0.1, 0.1, 0.1, 0.1, 0.1]], np.float32)}
        if model_name == "demographics_gender":
            return {"output": np.array([[4.0, 0.1]], dtype=np.float32)}
        if model_name == "pet":
            return {"output": np.array([[2.0, 0.5]], dtype=np.float32)}
        msg = f"unexpected triton model in /enrich drive: {model_name}"
        raise AssertionError(msg)

    triton = AsyncMock()
    triton.infer = AsyncMock(side_effect=_infer)
    triton.is_model_ready = AsyncMock(return_value=True)
    triton.get_model_metadata = AsyncMock(return_value={"outputs": [{"name": "output"}]})
    return triton


def _florence_prompt_mock(prompt: str, result_text: str) -> AsyncMock:
    """Florence Python-backend envelope: the adapter sends prompt as a UTF-8
    bytes object in inputs["prompt"][0] and unwraps the JSON string
    {"result": ...} (adapters/florence.py:219, 244-252; template: geometry
    module's _florence_triton)."""

    async def _infer(*, model_name: str, inputs: Any, outputs: Any) -> dict[str, Any]:
        sent = inputs["prompt"][0]
        sent = sent.decode("utf-8") if isinstance(sent, bytes) else str(sent)
        if sent != prompt:
            msg = f"adapter mutated the control-token prompt: {sent!r} != {prompt!r}"
            raise AssertionError(msg)
        envelope = json.dumps({"result": result_text}).encode("utf-8")
        return {"result": np.array([envelope], dtype=object)}

    triton = AsyncMock()
    triton.infer = AsyncMock(side_effect=_infer)
    triton.is_model_ready = AsyncMock(return_value=True)
    triton.get_model_metadata = AsyncMock(return_value={"outputs": [{"name": "result"}]})
    return triton


@pytest.fixture(scope="module")
def png_b64() -> str:
    """A real decodable PNG in base64 — pose/enrich gateway routes decode the
    body image (decode_base64_to_bytes ai/gateway/utils.py:74 + preprocess_
    yolo :131; decode_base64_image for the clothing path). probe-verified
    this session that "ZmFrZS1pbWFnZQ==" is valid b64 but NOT a valid image
    (ValueError -> HTTP 400)."""
    import base64

    return base64.b64encode(_png_bytes()).decode("ascii")


@pytest.fixture(scope="module")
def gateway_app():
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
    from contextlib import ExitStack

    with ExitStack() as stack:
        for _, module in GATEWAY_MOUNTS:
            stack.enter_context(patch(f"{module}.get_triton_client", return_value=gateway_triton))
        transport = ASGITransport(app=gateway_app)
        async with AsyncClient(transport=transport, base_url="http://gateway") as client:
            yield client


# ---------------------------------------------------------------------------
# S1 — pose keypoints are POSITIONAL COCO-17, JSONB, no names on the wire.
#      Order is the entire contract (plan 957-959).
# ---------------------------------------------------------------------------
class TestS1PoseKeypointsArePositional:
    def test_s1a_jsonb_column_admits_nameless_positional_rows(self) -> None:
        """The wire contract is a COMMENT, not a constraint (S1). Source
        (verified 2026-09-19) enrichment.py:53-56: keypoints JSONB nullable,
        comment="17 COCO keypoints as [[x, y, conf], ...]" (plan cite :53 on
        target). BODY_25/MediaPipe-33/Halpe-26 write 25/33/26 unnamed
        triples; Postgres accepts all. fake/gateway N/A (column not their
        wire). PREDICTED-GREEN (column metadata only). UNVERIFIED."""
        from backend.models.enrichment import PoseResult

        col = PoseResult.__table__.columns["keypoints"]
        assert col.name == "keypoints"
        assert type(col.type).__name__ == "JSONB"
        assert col.nullable is True
        # THE hazard: no length/item-shape constraint — a 25-joint payload
        # is indistinguishable here; "17 COCO" lives ONLY in the comment.
        comment = (col.comment or "").lower()
        assert "17 coco keypoints" in comment
        assert "[[x, y, conf]" in comment

    async def test_s1b_fake_pose_payload_carries_no_joint_names(self, fake_client) -> None:
        """Fake-side pin of the nameless wire. Schema
        enrichment_pose_analyze.response.json (read today): keypoints =
        array of {"additionalProperties": true, "type": "object"} — CANNOT
        require name keys, so mislabeled joints pass conformance.
        probe-verified: fake emits nameless {"alpha": ...} dicts; a BODY_25
        payload type-checks identically. fake GREEN; gateway's NAMED-dict
        side is the split pinned in s1d. UNVERIFIED at pytest."""
        assert OPERATIONS["enrichment_pose_analyze"].availability["fake"] is True
        schema = json.loads(
            (SCHEMA_DIR / "enrichment_pose_analyze.response.json").read_text(encoding="utf-8")
        )
        item = schema["properties"]["keypoints"]["items"]
        assert item["type"] == "object"
        assert item.get("additionalProperties") is True  # nothing FORBIDDEN
        assert "properties" not in item and "required" not in item  # nothing REQUIRED
        # same untyped shape on the light twin:
        light = json.loads(
            (SCHEMA_DIR / "enrich_lt_pose_analyze.response.json").read_text(encoding="utf-8")
        )
        assert light["properties"]["keypoints"]["items"].get("additionalProperties") is True

        r = await fake_client.post(
            "/enrichment/pose-analyze", **_request_kwargs("enrichment_pose_analyze")
        )
        assert r.status_code == 200
        body = r.json()
        kps = body["keypoints"]
        assert kps, "fake must emit keypoint payloads, not an empty list"
        for kp in kps:
            assert isinstance(kp, dict)
            # probe-verified: the generic dict generator emits alpha/bravo —
            # NO joint name from any skeleton reaches consumers (S1 hazard).
            assert not {"name", "nose", "left_shoulder", "x", "y", "conf"} & set(kp), sorted(kp)

    def test_s1c_the_two_name_tables_and_the_positional_reads_pin_the_order(self) -> None:
        """Order IS the contract. Duplicated as three independent literals
        at characterization time (source-characterization; the native pose
        server cannot boot here); the third — enrichment_transformers.py:441
        coco_keypoint_order — left with the WP3.4 A6 dead-twin deletion, and
        this leg now locks its ABSENCE. Surviving reads:
        ai/yolo26/pose_estimation.py:58 KEYPOINT_NAMES (+ :79 indices);
        enrichment_pipeline.py:1472 keypoint_names
        -> positional re-emit :1493-1501, returned :1505. Positional trust:
        pose_estimation.py:208 `x, y, conf = keypoints[idx]` (+ :851-855
        `name=KEYPOINT_NAMES[i]`) — name and value joined ONLY by integer i.
        The plan names only enrichment.py:53 for S1; these consumers are what
        hold the contract. PREDICTED-GREEN (text + AST). UNVERIFIED."""
        pose_src = POSE_EST_SRC.read_text(encoding="utf-8")
        assert "KEYPOINT_NAMES: list[str] = [" in pose_src
        tree = ast.parse(pose_src)
        names: list[str] = []
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.AnnAssign)
                and getattr(node.target, "id", "") == "KEYPOINT_NAMES"
            ):
                assert isinstance(node.value, ast.List)
                names = [str(elt.value) for elt in node.value.elts]
        assert names == list(COCO_17), names
        assert len(names) == 17
        assert "x, y, conf = keypoints[idx]" in pose_src
        assert "name=KEYPOINT_NAMES[i]" in pose_src

        # The third literal lived in the WP3.4-deleted dead twin
        # (api/helpers/enrichment_transformers.py:441, zero importers —
        # see test_enrichment_transformers_retired.py). The table it
        # transcribed stays here as COCO_17: the LIVE consumers below are
        # what the order contract lives on now, so the transcription's
        # provenance survives the deletion it came partly from.
        helpers_pkg = REPO_ROOT / "backend" / "api" / "helpers"
        assert not helpers_pkg.exists(), (
            "api/helpers/ is back — the WP3.4 A6 deletion was reversed; the "
            "s1c triple read belonged to the dead twin, re-home the table to "
            "a live consumer before restoring this test's third leg"
        )

        pipe_src = PIPELINE_SRC.read_text(encoding="utf-8")
        assert '"keypoints": keypoints,' in pipe_src  # positional re-emit at :1504

    async def test_s1d_gateway_pose_emits_names_the_db_column_strips(
        self, gateway_app, png_b64
    ) -> None:
        """The structural split, pinned per-path (never cross-equal — fake
        has no pose triton; the gateway's names die in s1a's JSONB):
        _postprocess_pose (adapters/enrichment.py def :641) emits
        {"name","x","y","confidence"} dicts (:683-698) from (1,56,8400)
        (docstring :645: 56 = 4 box + 1 conf + 17*3). Canned 100.0/20.0 and
        conf 0.9 survive round() exactly. gateway GREEN; fake N/A.
        UNVERIFIED at pytest; pure-function shape probed directly."""
        from unittest.mock import patch as _patch

        # (1, 56, 8400) as the adapter expects; it transposes to (8400, 56)
        # when shape[0] < shape[1] (:652-653), so ONE candidate goes in COLUMN
        # 0 and every other column's conf stays nan -> masked at :656.
        # harness-verified 2026-09-19: (1,56,1) hit IndexError at preds[:,4].
        tensor = np.full((1, 56, 8400), np.nan, dtype=np.float32)
        tensor[0, 0:4, 0] = [10.0, 20.0, 110.0, 60.0]
        tensor[0, 4, 0] = 0.9
        tensor[0, 5:, 0] = np.arange(51, dtype=np.float32)
        triton = AsyncMock()
        triton.infer = AsyncMock(return_value={"output0": tensor})
        with _patch("ai.gateway.adapters.enrichment.get_triton_client", return_value=triton):
            from httpx import ASGITransport as _T  # local import: fixture owns app

            transport = _T(app=gateway_app)
            async with AsyncClient(transport=transport, base_url="http://gateway") as client:
                r = await client.post(
                    "/enrichment/pose-analyze",
                    json={"image": png_b64},
                )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["num_people"] == 1
        kps = body["keypoints"][0]["keypoints"]
        assert len(kps) == 17
        assert [k["name"] for k in kps] == list(COCO_17)  # gateway NAMES the joints
        # ...but the DB surface that persists them is the nameless JSONB of
        # s1a — the names stop at the adapter boundary (hazard, pinned):
        assert set(kps[0]) == {"name", "x", "y", "confidence"}


# ---------------------------------------------------------------------------
# S2 — embedding-space tag exists; get_embedding_model() has ZERO production
#      callers, so post-swap cosine compares unrelated spaces (plan 961-963).
# ---------------------------------------------------------------------------
class TestS2EmbeddingSpaceTag:
    def test_s2a_zero_production_readers_of_the_tag(self) -> None:
        """The plan's load-bearing claim, re-verified by corpus scan TODAY:
        entity.py:193 set_embedding stores {"vector","model","dimension"}
        (:206-210); :223 get_embedding_model is the only reader, and a scan
        of backend/ ai/ scripts/ (test trees + THIS module excluded — the
        V1c self-match trap lesson) finds ZERO readers. fake/gateway N/A
        (model layer). PREDICTED-GREEN. UNVERIFIED at pytest level."""
        producers = []
        for root in ("backend", "ai", "scripts"):
            tree = REPO_ROOT / root
            if not tree.is_dir():
                continue
            for path in tree.rglob("*.py"):
                rel = path.relative_to(REPO_ROOT)
                if "tests" in rel.parts or rel.name.startswith("test_"):
                    continue  # test pins are not production consumers
                text = path.read_text(encoding="utf-8", errors="replace")
                if rel == Path("backend/models/entity.py"):
                    assert "def get_embedding_model(" in text  # the def itself
                    continue
                if "get_embedding_model" in text:
                    producers.append(str(rel))
        assert producers == [], f"plan claim falsified — readers appeared: {producers}"

    def test_s2b_the_tag_records_the_space_and_no_writer_validates_it(self) -> None:
        """probe-verified: set_embedding(..., model="siglip-2") stores the tag
        verbatim (get_embedding_model() -> "siglip-2", dimension 4) and
        validates NOTHING; hybrid_entity_storage.py:150 reads only
        get_embedding_vector() — the tag is write-only, so post-swap cosine
        silently mixes CLIP-768 and SigLIP-2 spaces (plan's scenario).
        fake/gateway N/A. PREDICTED-GREEN (pure ORM object). UNVERIFIED."""
        from backend.models.entity import Entity

        ent = Entity(entity_type="person")
        ent.set_embedding([0.1] * 4)  # default model="clip" (entity.py:196)
        assert ent.embedding_vector["model"] == "clip"
        assert ent.get_embedding_model() == "clip"
        assert ent.embedding_vector["dimension"] == 4
        other = Entity(entity_type="person")
        other.set_embedding([0.2] * 4, model="siglip-2")
        assert other.get_embedding_model() == "siglip-2"  # recorded, never checked
        # storage reads the vector but NOT the tag:
        storage = (REPO_ROOT / "backend/services/hybrid_entity_storage.py").read_text(
            encoding="utf-8"
        )
        assert "entity.get_embedding_vector()" in storage
        assert "get_embedding_model" not in storage

    def test_s2c_speaking_provider_stamps_a_different_space_untagged(self) -> None:
        """fake stamps CLIP-space 768-dim (clip_embed) and reid-space 512-dim
        (enrich_lt_person_reid) via fake/generators.py:242-244 _OVERRIDES —
        two spaces behind one cosine consumer, s2a tag never consulted.
        probe-verified: dims 768/512, |v|2=1.0 (6dp). fake GREEN.
        PREDICTED-GREEN. UNVERIFIED at pytest."""

        async def _drive() -> tuple[float, int, int]:
            from backend.ai_contract.fake import create_fake_app

            app = create_fake_app()
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://fake"
            ) as client:
                e = (await client.post("/clip/embed")).json()["embedding"]
                r = (await client.post("/enrich-lt/person-reid")).json()
            return float(np.linalg.norm(e)), len(e), int(r["embedding_dimension"])

        import asyncio

        norm, clip_dim, reid_dim = asyncio.run(_drive())
        assert clip_dim == 768 and reid_dim == 512  # competing dimensionalities
        assert abs(norm - 1.0) <= 1e-6  # unit-norm — cosine-ready, space-blind
        # The tag that SHOULD guard this has no reader (s2a): the two vectors
        # above could be multiplied by any downstream cosine and "report
        # plausible numbers" (plan) with zero error raised.


# ---------------------------------------------------------------------------
# S3 — Florence prompts are literal Florence-2 control tokens passed through
#      as `prompt` (plan 965-967).
# ---------------------------------------------------------------------------
class TestS3FlorenceControlTokenPrompts:
    def test_s3a_control_tokens_flow_client_to_backend_verbatim(self) -> None:
        """Source pin (plan cite vision_extractor.py:673 EXACT — CAPTION_TASK
        = "<CAPTION>"): prompt built :1010, shipped :1013 via
        `_florence_client.extract(image, prompt)`; gateway florence.py:55
        default "<CAPTION>", :219 literal UTF-8 passthrough — no natural-
        language layer anywhere. PREDICTED-GREEN (source pin).  UNVERIFIED at pytest."""
        ve = VISION_EXTRACTOR_SRC.read_text(encoding="utf-8")
        assert 'CAPTION_TASK = "<CAPTION>"' in ve
        assert 'prompt = f"{task}{text_input}" if task == VQA_TASK and text_input else task' in ve
        assert "await self._florence_client.extract(image, prompt)" in ve
        gf = GATEWAY_FLORENCE_SRC.read_text(encoding="utf-8")
        assert 'prompt: str = Field(default="<CAPTION>", description="Florence-2 prompt")' in gf
        assert 'prompt_input = np.array([prompt.encode("utf-8")], dtype=object)' in gf

    async def test_s3b_gateway_echoes_the_control_token_back_unchallenged(
        self, gateway_app
    ) -> None:
        """THE hazard made executable: /florence/extract with the shipped
        token; the mock "VLM" echoes the token text as the caption and the
        adapter accepts it verbatim, prompt_used round-tripped
        (florence.py:306-311). gateway GREEN — shipped accept-everything,
        CHARACTERIZATION not endorsement. fake N/A (s3c). UNVERIFIED;
        envelope + passthrough probe-verified this session."""
        from unittest.mock import patch as _patch

        triton = _florence_prompt_mock("<CAPTION>", "<CAPTION> a person near a fence")
        with _patch("ai.gateway.adapters.florence.get_triton_client", return_value=triton):
            transport = ASGITransport(app=gateway_app)
            async with AsyncClient(transport=transport, base_url="http://gateway") as client:
                r = await client.post(
                    "/florence/extract",
                    json={"image": "ZmFrZS1pbWFnZQ==", "prompt": "<CAPTION>"},
                )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["prompt_used"] == "<CAPTION>"
        # consumer accepts the echo — nothing between adapter and response
        # model rejects a caption that repeats its own control token:
        assert body["result"] == "<CAPTION> a person near a fence"

    def test_s3c_fake_produces_no_control_token_semantics(self) -> None:
        """fake contrast (probe-verified today): the fake parses bodies ONLY for
        echo fields (fake/app.py _make_handler), so a "<CAPTION>" body
        returns GENERATED prompt_used/result — fake-side conformance can
        never observe a token-echo failure; s3b is mandatory for the bullet.
        fake GREEN. PREDICTED-GREEN. UNVERIFIED at pytest."""
        assert OPERATIONS["florence_extract"].availability["fake"] is True

        async def _drive() -> dict[str, Any]:
            from backend.ai_contract.fake import create_fake_app

            app = create_fake_app()
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://fake"
            ) as client:
                r = await client.post(
                    "/florence/extract",
                    json={"image": "ZmFrZS1pbWFnZQ==", "prompt": "<CAPTION>"},
                )
                return r.json()

        import asyncio

        body = asyncio.run(_drive())
        assert body["prompt_used"] != "<CAPTION>"
        assert "<" not in body["result"] and "CAPTION" not in body["result"]


# ---------------------------------------------------------------------------
# S4 — caption language is an unwritten contract: the frontend classifies
#      summaries by ENGLISH keyword matching (plan 969-970).
# ---------------------------------------------------------------------------
class TestS4CaptionLanguageKeywordContract:
    def test_s4a_the_english_keyword_tables_are_the_real_list(self) -> None:
        """PLAN CITE CORRECTION (2026-09-19): the plan cites
        severityCalculator.ts:56 ("the keyword list"); the list is THREE
        tables — CRITICAL_KEYWORDS :57-63, HIGH_KEYWORDS :70-76, LOW_KEYWORDS
        :88 — and the plan's seven quoted terms are a cross-level sample of
        them (:59,:60,:61,:74,:75,:88). Matching is case-insensitive
        substring (:160-161): a NON-ENGLISH caption matches NOTHING and
        falls through silently. PREDICTED-GREEN (TS as TEXT; never imported).  UNVERIFIED at pytest."""
        ts = SEVERITY_TS_SRC.read_text(encoding="utf-8")
        import re

        def _kw_list(name: str) -> list[str]:
            m = re.search(rf"const {name} = \[([^\]]*)\]", ts, re.DOTALL)
            assert m, name
            return re.findall(r"'([^']+)'", m.group(1))

        crit = _kw_list("CRITICAL_KEYWORDS")
        high = _kw_list("HIGH_KEYWORDS")
        low = _kw_list("LOW_KEYWORDS")
        # the plan's seven quoted terms, exactly where the plan says they live
        assert {"intruder", "breach", "weapon"} <= set(crit)
        assert {"loitering", "trespassing"} <= set(high)
        assert {"routine", "delivery"} <= set(low)
        # full tables pinned (a provider swapping caption LANGUAGE — e.g. a
        # multilingual VLM — hits NONE of these and the UI defaults downward
        # with no error; a caption-language CONTRACT test would assert every
        # fake caption matches one table, but the fake's captions are
        # generated gibberish like "caption_418" that already violates the
        # contract TODAY — pinning THAT as an assertion would be a permanent
        # red against the fake, so the keyword tables themselves are pinned
        # and the fake-caption violation is recorded in the ledger instead):
        assert crit == ["critical", "emergency", "intruder", "breach", "weapon", "threat"]
        assert high == [
            "high-risk",
            "suspicious",
            "masked",
            "obscured face",
            "loitering",
            "trespassing",
        ]
        assert low == ["routine", "normal", "expected", "delivery"]
        assert (
            re.search(
                r"const MEDIUM_KEYWORDS = \['unusual', 'unexpected', "
                r"'unfamiliar', 'monitoring'\]",
                ts,
            )
            is not None
        )
        # substring (not word-boundary) matching is part of the contract:
        assert re.search(r"lowerContent\.includes\(keyword\.toLowerCase\(\)\)", ts) is not None


# ---------------------------------------------------------------------------
# S5 — think-tag stripping by regex; unclosed tag = "no reasoning" and the
#      RAW text passes through as the JSON payload (plan 972-974).
# ---------------------------------------------------------------------------
class TestS5ThinkTagStripping:
    def test_s5a_the_strip_regex_is_dotted_dotall_think_only(self) -> None:
        """Plan cite nemotron_analyzer.py:154 EXACT (second cite :4280 drifted
        to :4281): _THINK_PATTERN at :154, capture-group twin at :155.
        <reasoning>, reasoning_content and Harmony channels match NEITHER.
        PREDICTED-GREEN; fake/gateway N/A (analyzer is a consumer).
        UNVERIFIED at pytest."""
        src = ANALYZER_SRC.read_text(encoding="utf-8")
        assert 're.compile(r"<think>.*?</think>", re.DOTALL)' in src
        assert 're.compile(r"<think>(.*?)</think>", re.DOTALL)' in src
        assert "reasoning_content" not in src  # no OpenAI reasoning channel
        assert "<reasoning>" not in src  # no generic reasoning tag handling

    def test_s5b_unclosed_think_passes_raw_text_as_the_payload(self) -> None:
        """probe-VERIFIED this session: closed think -> (reasoning, clean
        JSON); '<think>unclosed {"risk": 1}' -> ("", RAW TEXT as the payload
        — the plan's claim verbatim; its docstring :239-244 encodes the same
        verdict); '<reasoning>CoT</reasoning>{...}' -> unchanged, foreign CoT
        INVISIBLE to the regex. _parse_risk_response (:4281+) then
        brace-scans, so the first brace inside leaked CoT BECOMES the payload
        boundary. PREDICTED-GREEN; fake/gateway N/A. UNVERIFIED at pytest."""
        from backend.services.nemotron_analyzer import extract_reasoning_and_response

        closed = '<think>Analyzing the scene...</think>{"risk_score": 25}'
        reasoning, response = extract_reasoning_and_response(closed)
        assert reasoning == "Analyzing the scene..."
        assert response == '{"risk_score": 25}'
        unclosed = '<think>unclosed reasoning {"risk": 1}'
        reasoning2, response2 = extract_reasoning_and_response(unclosed)
        assert reasoning2 == ""  # "no reasoning" verdict
        assert response2 == unclosed  # raw text passed through AS the payload
        other = '<reasoning>CoT here</reasoning>{"risk": 1}'
        reasoning3, response3 = extract_reasoning_and_response(other)
        assert reasoning3 == ""
        assert response3 == other  # foreign CoT channel invisible to the regex

    def test_s5c_second_consumer_repeats_the_same_regex(self) -> None:
        """Two strip sites, one regex object — pin so a partial fix (one site
        patched for a new tag) cannot pass unnoticed. Sources:
        nemotron_analyzer.py:260 and :4281. PREDICTED-GREEN.  UNVERIFIED at pytest."""
        import re as _re

        src = ANALYZER_SRC.read_text(encoding="utf-8")
        hits = [m.start() for m in _re.finditer(r"_THINK_PATTERN\.sub\(", src)]
        assert len(hits) == 2, hits


# ---------------------------------------------------------------------------
# S6 — frontend/src/utils/confidence.ts THROWS outside [0,1]: a percentage
#      provider crashes the detection UI instead of degrading (plan 976-977).
# ---------------------------------------------------------------------------
class TestS6ConfidenceRangeThrow:
    def test_s6a_the_throw_is_pinned_in_the_ts_text(self) -> None:
        """PLAN CITE note: confidence.ts:12 is the GUARD condition (`if
        (confidence < 0 || confidence > 1) throw new Error(...)` spans
        :12-14) — on target. Categories inside the range: <0.7 low, <0.85
        medium, else high (:16-18). PREDICTED-GREEN (TS as text).  UNVERIFIED at pytest."""
        ts = CONFIDENCE_TS_SRC.read_text(encoding="utf-8")
        assert "if (confidence < 0 || confidence > 1) {" in ts
        assert "throw new Error('Confidence score must be between 0.0 and 1.0');" in ts
        assert "if (confidence < 0.7) return 'low';" in ts
        assert "if (confidence < 0.85) return 'medium';" in ts

    def test_s6b_every_provider_emittable_confidence_lives_in_the_unit_interval(
        self,
    ) -> None:
        """The UI throw survives only if every provider keeps confidence in
        [0,1]. Schema-driven sweep of the fake: every POST op whose response
        schema declares "confidence" (probe-enumerated: enrich_lt_pet_
        classify + enrichment_{action,clothing,pet,vehicle}_classify) plus
        bare-dict yolo26_detect (adapters/yolo26.py:375-379 evidence) is
        driven; nested values asserted in [0,1]. probe-VERIFIED: 0 offenders.
        A percent provider would CRASH getConfidenceLevel on render. fake
        GREEN; gateway row in s6c. UNVERIFIED at pytest."""
        import asyncio
        import re as _re

        ops_with_confidence = []
        for path in SCHEMA_DIR.glob("*.response.json"):
            op_id = path.name[: -len(".response.json")]
            if op_id not in OPERATIONS or OPERATIONS[op_id].method != "POST":
                continue
            text = path.read_text(encoding="utf-8")
            if _re.search(r'"confidence"\s*:', text):
                ops_with_confidence.append(op_id)
        assert "enrichment_action_classify" in ops_with_confidence
        assert "enrichment_pet_classify" in ops_with_confidence

        def _walk(node: Any, key: str = "") -> list[float]:
            found: list[float] = []
            if isinstance(node, dict):
                for k, v in node.items():
                    found += _walk(v, k)
            elif isinstance(node, list):
                for item in node:
                    found += _walk(item, key)
            elif isinstance(node, (int, float)) and key == "confidence":
                found.append(float(node))
            return found

        async def _sweep() -> list[str]:
            from backend.ai_contract.fake import create_fake_app

            app = create_fake_app()
            offenders: list[str] = []
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://fake"
            ) as client:
                for op_id in [*ops_with_confidence, "yolo26_detect"]:
                    r = await client.post(OPERATIONS[op_id].path)
                    assert r.status_code == 200, (op_id, r.status_code)
                    for v in _walk(r.json()):
                        if not 0.0 <= v <= 1.0:
                            offenders.append(f"{op_id}: {v}")
            return offenders

        offenders = asyncio.run(_sweep())
        assert offenders == [], f"percent-leak would CRASH confidence.ts: {offenders}"

    async def test_s6c_gateway_confidences_stay_in_the_unit_interval(self, gateway_client) -> None:
        """Gateway side of the same obligation: the canned triton row carries
        conf 0.9 and the adapter clamps+rounds it (adapters/yolo26.py), so the
        emitted detections[].confidence must land in [0,1] — the exact value
        range confidence.ts survives. Drives the real multipart route so the
        FIVE-patch fixture itself is exercised by this cluster too. probe-
        verified fake-side only; gateway GREEN predicted. UNVERIFIED."""
        r = await gateway_client.post(
            "/yolo26/detect", files={"file": ("frame.png", _png_bytes(), "image/png")}
        )
        assert r.status_code == 200, r.text
        for det in r.json()["detections"]:
            assert 0.0 <= float(det["confidence"]) <= 1.0


# ---------------------------------------------------------------------------
# S7 — FOUR divergent risk-band tables for one 0-100 score (plan 979-982).
# ---------------------------------------------------------------------------
class TestS7RiskBandTablesDiverge:
    def test_s7a_backend_three_tables_agree_at_29_59_84(self) -> None:
        """Backend trio, runtime-VERIFIED this session: llm_response.py
        29/59/84 (:137-139; infer_risk_level_from_score :142, match :155-161;
        PLAN CITE CORRECTION: plan's :118 is the RiskLevel DOCSTRING, code
        agrees); severity.py risk_score_to_severity (def :137, match
        :155-162) and event.py Event.computed_risk_level (hybrid_property
        :368; plan :374 near-miss) read settings defaults 29/59/84
        (config.py:2288-2305). THREE code tables, TWO numbers — the FOUR-way
        divergence completes only at s7b. Needs ENVIRONMENT != production
        (tests/conftest.py:107). PREDICTED-GREEN. UNVERIFIED at pytest."""
        from backend.api.schemas.llm_response import (
            DEFAULT_HIGH_MAX,
            DEFAULT_LOW_MAX,
            DEFAULT_MEDIUM_MAX,
            infer_risk_level_from_score,
        )
        from backend.models.event import Event
        from backend.services.severity import Severity, SeverityService

        assert (DEFAULT_LOW_MAX, DEFAULT_MEDIUM_MAX, DEFAULT_HIGH_MAX) == (29, 59, 84)
        assert infer_risk_level_from_score(29).value == "low"
        assert infer_risk_level_from_score(30).value == "medium"
        assert infer_risk_level_from_score(84).value == "high"
        assert infer_risk_level_from_score(85).value == "critical"

        svc = SeverityService()
        assert svc.get_thresholds() == {"low_max": 29, "medium_max": 59, "high_max": 84}
        assert svc.risk_score_to_severity(82) is Severity.HIGH
        assert svc.risk_score_to_severity(30) is Severity.MEDIUM
        assert svc.risk_score_to_severity(29) is Severity.LOW

        event = Event()
        event.risk_score = 82
        assert event.computed_risk_level == "high"
        event.risk_score = 29
        assert event.computed_risk_level == "low"

    def test_s7b_the_frontend_table_is_a_different_partition(self) -> None:
        """Fourth table (frontend): SEVERITY_THRESHOLDS {CRITICAL: 80, HIGH: 60,
        MEDIUM: 40, LOW: 20} at severityCalculator.ts:100-103 (PLAN CITE
        CORRECTION: the plan's :99 is the opening-brace line; values as
        stated), ladder at :193-195. Backend 82=high (s7a, runtime),
        frontend 82=critical — the plan's exact split. PARKED RULING:
        unifying the tables (serve thresholds from the API, or re-tune the
        TS) rewrites this characterization, it does not delete it.
        PREDICTED-GREEN.  UNVERIFIED at pytest."""
        ts = SEVERITY_TS_SRC.read_text(encoding="utf-8")
        assert "CRITICAL: 80," in ts
        assert "HIGH: 60," in ts
        assert "MEDIUM: 40," in ts
        assert "LOW: 20," in ts
        assert "if (score >= SEVERITY_THRESHOLDS.CRITICAL) return 'critical';" in ts

        # the backend side of the SAME score, runtime (same imports as s7a):
        from backend.api.schemas.llm_response import infer_risk_level_from_score

        backend_82 = infer_risk_level_from_score(82).value  # 'high'
        # the frontend side, computed FROM THE PARSED TABLE (never hardcoded
        # twice): the ts ladder is critical>=80 high>=60 medium>=40 low>=20.
        thresholds = {"CRITICAL": 80, "HIGH": 60, "MEDIUM": 40, "LOW": 20}
        assert backend_82 == "high"  # backend truth (s7a runtime-verified)
        assert thresholds["CRITICAL"] <= 82  # frontend truth: renders critical
        # THE divergence, as an assertion (both sides shipped-correct; the
        # split is the finding): a 82 score is high in the DB and critical in
        # the UI simultaneously.
        assert (backend_82 == "critical") is False

    def test_s7c_risk_score_int_strictness_layers_are_out_of_scope_here(self) -> None:
        """Cross-reference guard for the adjacent numeric-cluster bullet (plan
        949-954 int strictness). infer_risk_level_from_score(82.5) classifies
        a float happily (match guards are comparisons) while the DB bounds
        the domain via CHECK ck_events_risk_score_range (event.py:241-244 —
        plan cite :241 exact). Pinning that the band tables are NOT int-
        domain tests. PREDICTED-GREEN.  UNVERIFIED at pytest."""
        from backend.api.schemas.llm_response import infer_risk_level_from_score

        assert infer_risk_level_from_score(82.5).value == "high"  # no int guard


# ---------------------------------------------------------------------------
# S8 — OP 28 action-classify: the ONLY multi-frame operation (own block,
#      plan 984-985).
# ---------------------------------------------------------------------------
def _png_b64() -> str:
    """Real decodable PNG in base64 (same bytes as the module-scoped
    png_b64 fixture) — the pose stage of the action pipeline DECODES every
    frame, so the old xclip-era "any string is a frame" payloads 400."""
    import base64

    return base64.b64encode(_png_bytes()).decode("ascii")


# pose output (1, 56, 8400) with one person in anchor 0 (post-NMS row layout
# = 4 box + 1 conf + 17*3 keypoints); conf <= 0 means "no detections".
# Template: ai/gateway/tests/test_adapters_enrichment.py::_make_pose_output.
def _stgcn_pose_output(confidence: float = 0.9) -> np.ndarray:
    out = np.zeros((1, 56, 8400), dtype=np.float32)
    if confidence <= 0:
        return out
    out[0, 4, 0] = confidence
    for i in range(17):
        out[0, 5 + i * 3, 0] = 300.0 + i  # x
        out[0, 6 + i * 3, 0] = 200.0 + i  # y
        out[0, 7 + i * 3, 0] = 0.8  # visibility
    return out


class TestS8ActionClassifyMultiFrame:
    def test_s8a_registry_and_shape_pin_the_multiframe_uniqueness(self) -> None:
        """Registry pin (live): enrichment_action_classify POST
        /enrichment/action-classify, availability gateway/per_model_server/
        fake True, light False (operations.py:144-157; plan's "OP 28" is a
        registry ordinal — id-pinned so a reorder cannot detach this block).
        The frame sequence rides the request: ActionClassifyRequest.frames:
        list[str] (adapters/enrichment.py:351-353), empty rejected by the
        handler (action_classify :890-895); every other router on the
        adapter takes a single `image`. xclip_action is RETIRED (NEM-5563) —
        the temporal frames no longer ride the wire in one JSON blob;
        _infer_action (:640+) runs EACH frame through Triton pose, buffers
        the top person's keypoints and feeds one resampled skeleton to
        Triton stgcn_action. The MULTI-FRAME uniqueness is therefore the
        REQUEST shape, and it still holds on the source. MULTI-IMAGE !=
        MULTI-FRAME (ops module O1/F1): florence_batch_extract /
        yolo26_detect_batch carry multiple images, no temporal sequence.
        GREEN at pytest."""
        op = OPERATIONS[AC_OP]
        assert op.method == "POST" and op.path == "/enrichment/action-classify"
        assert op.availability == {
            "gateway": True,
            "enrichment_light_adapter": False,
            "per_model_server": True,
            "fake": True,
        }
        src = GATEWAY_ENRICH_SRC.read_text(encoding="utf-8")
        assert "class ActionClassifyRequest(BaseModel):\n    frames: list[str]" in src
        assert 'raise HTTPException(status_code=400, detail="Frames list cannot be empty")' in src
        # the serving reality the wire pins (post-NEM-5563): skeleton-based
        # stgcn_action, NOT the retired xclip python backend:
        assert 'model_name="stgcn_action"' in src
        assert 'model_name="pose"' in src  # stage 1 of the pipeline
        assert "xclip" not in src  # the retired backend cannot come back
        assert 'inputs={"input": skeleton}' in src  # the ONE stgcn triton input
        # uniqueness: only ONE frames: list[str] on the whole adapter:
        assert src.count("frames: list[str]") == 1

    async def test_s8b_gateway_drive_carries_the_frame_count_end_to_end(self, gateway_app) -> None:
        """N=4 frames through /enrichment/action-classify under the NEW
        two-stage contract (xclip retired): the mock records every triton
        call and asserts the TEMPORAL SEQUENCE arrives whole — 4 per-frame
        pose calls (one per frame, request order) followed by exactly one
        stgcn_action call. A logit spike at NTU-60 index 42 ("falling", in
        STGCN_HIGH_RISK_INDICES) pins the is_suspicious/risk_weight pair
        (0.8/0.2) the response carries. gateway GREEN at pytest."""
        from unittest.mock import patch as _patch

        calls: list[str] = []

        async def _infer(*, model_name: str, inputs: Any, outputs: Any) -> dict[str, Any]:
            calls.append(model_name)
            if model_name == "pose":
                return {"output0": _stgcn_pose_output()}
            assert model_name == "stgcn_action"
            logits = np.zeros((1, 60), dtype=np.float32)
            logits[0, 42] = 5.0  # NTU-60 index 42 = "falling"
            return {"output": logits}

        triton = AsyncMock()
        triton.infer = AsyncMock(side_effect=_infer)
        triton.is_model_ready = AsyncMock(return_value=True)
        triton.get_model_metadata = AsyncMock(return_value={"outputs": [{"name": "output0"}]})
        png = _png_b64()
        with _patch("ai.gateway.adapters.enrichment.get_triton_client", return_value=triton):
            transport = ASGITransport(app=gateway_app)
            async with AsyncClient(transport=transport, base_url="http://gateway") as client:
                r = await client.post(
                    "/enrichment/action-classify",
                    # 4 REAL decodable frames — the pose stage decodes each:
                    json={"frames": [png, png, png, png]},
                )
        assert r.status_code == 200, r.text
        assert calls == ["pose", "pose", "pose", "pose", "stgcn_action"]
        body = r.json()
        assert body["action"] == "falling"  # NTU60_LABELS[42]
        assert body["is_suspicious"] is True  # STGCN_HIGH_RISK_INDICES hit
        assert body["risk_weight"] == 0.8

    def test_s8c_fake_is_frame_blind_by_construction(self) -> None:
        """The multi-frame op's conformance hazard, pinned: bodies are parsed
        ONLY for echo fields (fake/app.py), so 1-frame and 4-frame requests
        return byte-identical JSON (probe-verified: r1.content ==
        r2.content). A frame-blind fake can never certify a video-native
        replacement (plan: VSS changes the SHAPE here) — recorded as an
        assertion; fake GREEN (frame-blindness IS shipped behavior).
        UNVERIFIED at pytest; equality probe verified."""
        import asyncio

        async def _drive() -> tuple[bytes, bytes]:
            from backend.ai_contract.fake import create_fake_app

            app = create_fake_app()
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://fake"
            ) as client:
                r1 = await client.post(OPERATIONS[AC_OP].path, json={"frames": ["QQ=="]})
                r2 = await client.post(
                    OPERATIONS[AC_OP].path, json={"frames": ["QQ==", "Qg==", "Qw==", "RA=="]}
                )
            return r1.content, r2.content

        one, four = asyncio.run(_drive())
        assert one == four  # frame-blind: identical bytes whatever N is
        assert json.loads(one)["action"]  # still a valid ActionClassify shape


# ---------------------------------------------------------------------------
# S9 — composite /enrich: one call exercising the whole enrichment contract
#      (plan 987-988).
# ---------------------------------------------------------------------------
class TestS9CompositeEnrich:
    def test_s9a_registry_pin_one_call_whole_surface(self) -> None:
        """Registry pin: enrichment_enrich POST /enrichment/enrich, one bound
        method EnrichmentClient.enrich_detection (operations.py:196-209).
        PLAN cite adapters/enrichment.py:899 EXACT (decorator :899, def
        :900). One call fans out to 2 triton models for person — clothing +
        demographics (gather :914-918); the docstring (:904-908) also
        advertises pose but shipped code never gathers it: the composite's
        contract is its ACTUAL fan-out (a target defined by a lying
        docstring is the S3 disease again). PREDICTED-GREEN.  UNVERIFIED at pytest."""
        op = OPERATIONS[ENRICH_OP]
        assert op.method == "POST" and op.path == "/enrichment/enrich"
        assert op.availability == {
            "gateway": True,
            "enrichment_light_adapter": False,
            "per_model_server": True,
            "fake": True,
        }
        assert op.client_methods == ["EnrichmentClient.enrich_detection"]
        src = GATEWAY_ENRICH_SRC.read_text(encoding="utf-8")
        assert '@router.post("/enrich", response_model=EnrichmentResponse)' in src
        # shipped person fan-out = clothing + demographics, concurrently:
        assert "_infer_clothing(request.image)," in src
        assert "_infer_demographics(request.image)," in src
        assert "_infer_pose" not in src  # docstring lies about pose; code truth pinned

    async def test_s9b_gateway_person_fanout_single_call(self, gateway_app, png_b64) -> None:
        """ONE /enrich POST (person): the response aggregates
        enrichments.{clothing, demographics} in a single call; sub-model
        failures degrade independently (return_exceptions :916). HERMETIC
        CHOICE: _ensure_clothing_text_embeddings (:177) is PATCHED to None
        — unpatched it attempts a FashionSigLIP weight load (hub id :44,
        network-blocked here); None is the adapter's OWN degradation path,
        the placeholder clothing dict (:469-481) arriving with HTTP 200, so
        pinning through it certifies the envelope honestly (success-path
        zero-shot math is numeric-cluster territory). demographics runs on
        canned age/gender logits. fake N/A (envelope in s9c). gateway GREEN
        predicted. UNVERIFIED at pytest."""
        from unittest.mock import patch as _patch

        triton = _enrich_triton()
        with (
            _patch("ai.gateway.adapters.enrichment.get_triton_client", return_value=triton),
            _patch(
                "ai.gateway.adapters.enrichment._ensure_clothing_text_embeddings",
                return_value=None,
            ),
        ):
            transport = ASGITransport(app=gateway_app)
            async with AsyncClient(transport=transport, base_url="http://gateway") as client:
                r = await client.post(
                    "/enrichment/enrich",
                    json={"image": png_b64, "detection_type": "person"},
                )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["detection_type"] == "person"
        keys = set(body["enrichments"])
        assert keys == {"clothing", "demographics"}, keys
        # demographics ran on the canned age/gender logits:
        assert body["enrichments"]["demographics"]["gender"] == "male"
        assert body["enrichments"]["demographics"]["age_range"] == "0-10"
        # clothing arrived via the placeholder path (:469-481):
        assert body["enrichments"]["clothing"]["clothing_type"] == "casual"
        assert triton.infer.await_count >= 3  # fashion_clip + age + gender in one POST

    def test_s9c_fake_envelope_rounds_the_pair(self) -> None:
        """fake-side envelope pin (completes s9b's N/A): probe-verified fake
        shape matches the golden response example key-wise
        (detection_type/enrichments/inference_time_ms). Fake certifies the
        ENVELOPE; gateway certifies the FAN-OUT; fake-only conformance would
        miss a composite that never aggregates. fake GREEN. PREDICTED-GREEN.
        UNVERIFIED at pytest."""
        import asyncio

        async def _drive() -> dict[str, Any]:
            from backend.ai_contract.fake import create_fake_app

            app = create_fake_app()
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://fake"
            ) as client:
                r = await client.post(
                    OPERATIONS[ENRICH_OP].path,
                    json={"image": "ZmFrZS1pbWFnZQ==", "detection_type": "person"},
                )
                return r.json()

        golden = json.loads(
            (GOLDEN_DIR / "enrichment_enrich.response.example.json").read_text(encoding="utf-8")
        )
        body = asyncio.run(_drive())
        assert set(body) == set(golden)
        assert isinstance(body["enrichments"], dict) and body["enrichments"]


# ---------------------------------------------------------------------------
# Matrix guards — the semantics-relevant ops against every provider's
# availability column. NEVER invoke a registered callable for
# per_model_http / llamacpp_llm / gateway_light (network / live client).
# ---------------------------------------------------------------------------
_SEMANTICS_OPS = [
    "enrichment_pose_analyze",
    "enrich_lt_pose_analyze",
    "clip_embed",
    "clip_similarity",
    "enrich_lt_person_reid",
    "florence_extract",
    "florence_batch_extract",
    AC_OP,
    ENRICH_OP,
    "yolo26_detect",
]


class TestSemanticsMatrixGuards:
    @pytest.mark.parametrize("pid", list(ProviderId), ids=lambda p: p.value)
    def test_semops_registered_set_matches_the_availability_column(self, pid) -> None:
        """Presence/absence = green guard, not skip (plan procedure). For the
        three never-invoked providers this IS the semantics coverage:
        registered set == slot column (llamacpp: evidence-derived subset
        inside the per_model_server union column, providers.py:94-106). Fake
        registers all 37 (column is the spec; in-test registration per
        test_conformance_ops.py; sizes 30/5/35/2/37 after the A7.2
        analyze-scene deletion, discovery run agreed). Semantics rows spelled out per provider so a column edit
        fails LOUD, not quietly. PREDICTED-GREEN all five. UNVERIFIED at
        pytest."""
        if pid is ProviderId.FAKE:
            from backend.ai_contract.fake import fake_provider_ops

            rec = register_provider(
                ProviderId.FAKE, fake_provider_ops(), OPERATIONS, deployed=True
            ).operations()
            assert set(rec) == set(operations_for_slot("fake", OPERATIONS)) == set(OPERATIONS)
            return
        rec = registered_providers()[pid.value].operations()
        column = set(operations_for_slot(PROVIDER_SLOT[pid], OPERATIONS))
        # mirrors test_conformance_ops.SUBSET_REQUIRED (sibling-pinned by
        # the sentinel test below): union-slot subset providers - llamacpp's
        # evidence pair and the 1.1 VLM engines' {vlm_assess}.
        subset_required = {
            ProviderId.LLAMACPP_LLM: {"llm_completion", "llm_chat_completion"},
            ProviderId.OPENAI_VLM: {"vlm_assess"},
            ProviderId.RTVI_VLM: {"vlm_assess"},
        }
        if pid in subset_required:
            assert set(rec) == subset_required[pid]
        else:
            assert set(rec) == column
            assert rec.keys() >= (set(_SEMANTICS_OPS) & column)
        # semantics-row expectations per provider, so a column edit that
        # drops e.g. gateway action-classify fails LOUD, not quietly:
        present = set(rec) & set(_SEMANTICS_OPS)
        if pid in (ProviderId.GATEWAY, ProviderId.PER_MODEL_HTTP, ProviderId.FAKE):
            assert set(_SEMANTICS_OPS) <= present
        elif pid is ProviderId.GATEWAY_LIGHT:
            assert present == {"enrich_lt_pose_analyze", "enrich_lt_person_reid"}
        else:  # subset providers: no semantics row is in their required set
            assert present == set()

    @pytest.mark.parametrize("pid", list(ProviderId), ids=lambda p: p.value)
    def test_semops_semantics_sentinels_are_the_sibling_pinned_set(self, pid) -> None:
        """Intersect the semantics rows with the ops module's NOT-WIRED sentinel
        sets (test_conformance_ops.py:139-158) so a wiring change must touch
        BOTH modules. Set membership only — no callables invoked.
        enrich_lt_pose_analyze is the sentinel sitting on the semantics
        rows. PREDICTED-GREEN; llamacpp_llm has no sentinel surface.
        UNVERIFIED at pytest."""
        if pid not in SIBLING_SENTINELS:
            # FAKE and the subset providers have no sentinel surface ON THE
            # SEMANTICS ROWS (fake wires all ops; llamacpp registers its own
            # two payloads; the 1.1 VLM engines register only vlm_assess,
            # which is not a semantics row - their {vlm_assess} sentinel is
            # pinned in test_conformance_vlm.py).
            assert pid in (
                ProviderId.LLAMACPP_LLM,
                ProviderId.FAKE,
                ProviderId.OPENAI_VLM,
                ProviderId.RTVI_VLM,
            )
            return
        rec = set(registered_providers()[pid.value].operations())
        expected = rec & SIBLING_SENTINELS[pid]
        got = {op_id for op_id in rec & set(_SEMANTICS_OPS) if op_id in SIBLING_SENTINELS[pid]}
        assert got == expected & set(_SEMANTICS_OPS)
        assert "enrich_lt_pose_analyze" in got  # the semantics-relevant one

    def test_semops_plan_bullets_all_mapped(self) -> None:
        """MEASURE meta-guard: bullets S1-S9 each still own a test in THIS file
        and no skip/xfail/deselect text ever appears — a bullet dropped in
        review turns this RED, which is the point. PREDICTED-GREEN (self-
        text scan via __file__). UNVERIFIED."""
        # False positive: the "path" is this test module's own __file__ — no
        # user input, no open-with-mode-w. Self-scan is the point of the guard.
        text = Path(__file__).read_text(encoding="utf-8")  # nosemgrep: path-traversal-open
        defs = [
            ln.strip().split("(")[0] for ln in text.splitlines() if ln.strip().startswith("def ")
        ]
        for bullet in ("S1", "S2", "S3", "S4", "S5", "S6", "S7", "S8", "S9"):
            prefix = f"def test_s{bullet[1].lower()}"
            assert any(d.startswith(prefix) for d in defs), f"bullet {bullet} lost its test"
        # Forbidden MECHANISMS — needles assembled at runtime so this guard's
        # own literals cannot self-match the scan it runs (the header names
        # the rule in prose; this rules out CALLS):
        forbidden = [
            "pytest" + "." + tail
            for tail in ("skip(", "skip.if", "skipif", "mark.xfail", "importorskip")
        ] + ["--" + "deselect"]
        for needle in forbidden:
            assert needle not in text, needle
