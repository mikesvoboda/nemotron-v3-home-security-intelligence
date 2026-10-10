"""Unit tests for the enrichment-light gateway adapter.

Tests the enrichment-light adapter's shipped endpoints — ``POST /threat-detect``,
``POST /person-reid`` and ``GET /health`` — with a mocked Triton client, plus the
pure post-processing helper the threat route derives its confidences with.

R8 S3 (2026-09-29, owner rulings 3/4/5) pruned ``pose``, ``pet`` and ``depth``
from the Triton repository and hard-raised ``GATEWAY_MODEL_SET``, so
``/pose-analyze``, ``/pet-classify`` and ``/depth-estimate`` left the adapter
with their models and the ``_softmax`` helper left with them. The suites for
those three routes are DELETED here, not tombstoned: the historical record is
owned by the S3 guard, which pins each of those properties by name —
``TestTritonRepositoryPruned.test_enrichment_light_adapter_survives_and_serves_the_kept_models``
asserts the three route strings are absent from this adapter's source and that
the two KEPT-model ops stay registered, and
``test_adapters_whose_models_are_all_pruned_retire_with_them``
asserts ``enrich_lt_pose_analyze`` / ``enrich_lt_pet_classify`` /
``enrich_lt_depth_estimate`` are out of ``OPERATION_IDS``. A second copy of
"that route is gone" in the tier that hosted it would be a pin with no owner.

What transfers is retargeted rather than dropped: the deleted ``_softmax`` suite
pinned the adapter's confidence derivation (scores in, one probability per class,
numerically stable). The surviving carrier of that property is
``_postprocess_threat`` — argmax over the class-score block, then a threshold —
so it is tested as the mechanism it is (``TestConfidenceDerivation``), on the
tensor layouts and the boundary the deleted tests never reached.
"""

from __future__ import annotations

import base64
import io
import math
from unittest.mock import AsyncMock, patch

import numpy as np
import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from PIL import Image

from ai.gateway.adapters.enrichment_light import (
    _postprocess_threat,
    router,
)
from ai.gateway.triton_client import TritonClientError

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_b64_image(width: int = 224, height: int = 224) -> str:
    """Create a small test image encoded as base64."""
    img = Image.new("RGB", (width, height), color=(100, 150, 200))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode("utf-8")


def _threat_output(
    n_classes: int = 4,
    rows: int = 8400,
    layout: str = "channels_first",
) -> np.ndarray:
    """An all-zero YOLO threat tensor in the shipped (1, 4+n_classes, rows) family.

    ``layout`` covers both orientations _postprocess_threat accepts: the model's
    own ``(1, 8, 8400)`` and the ``(1, 8400, 8)`` transposed form it normalises.
    """
    depth = 4 + n_classes
    shape = (1, depth, rows) if layout == "channels_first" else (1, rows, depth)
    return np.zeros(shape, dtype=np.float32)


def _plant(
    out: np.ndarray,
    det: int,
    *,
    box: tuple[float, float, float, float] = (55.0, 110.0, 90.0, 180.0),
    class_index: int = 0,
    score: float = 0.92,
    layout: str = "channels_first",
) -> None:
    """Write one detection into ``out`` (cxcywh box + one class score)."""
    cx, cy, w, h = box
    channel = 4 + class_index
    if layout == "channels_first":
        out[0, 0:4, det] = (cx, cy, w, h)
        out[0, channel, det] = score
    else:
        out[0, det, 0:4] = (cx, cy, w, h)
        out[0, det, channel] = score


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_triton():
    """Create a mock Triton client."""
    client = AsyncMock()
    client.infer = AsyncMock()
    client.is_model_ready = AsyncMock(return_value=True)
    return client


@pytest.fixture
def app():
    """Create a test FastAPI app with the enrichment-light router."""
    app = FastAPI()
    app.include_router(router)
    return app


@pytest.fixture
async def client(app, mock_triton):
    """Create an async test client with mocked Triton."""
    with patch(
        "ai.gateway.adapters.enrichment_light.get_triton_client",
        return_value=mock_triton,
    ):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            yield c


def _light_probe_set() -> set[str]:
    """The models this adapter's /health probes, DERIVED.

    The adapter's own docstring states the rule: its models are exactly the
    residency set's non-yolo26 members. Deriving from ``FULL_MODEL_SET`` is the
    point — a health payload that remembered ``pose``/``pet``/``depth`` would
    report ``degraded`` on every healthy boot, and a hand-list here rots the same
    way (WP4.2).
    """
    from ai.gateway.residency import FULL_MODEL_SET

    probes = {m for m in FULL_MODEL_SET if m != "yolo26"}
    # Non-vacuity: an empty derivation would make every equality below vacuous.
    assert len(probes) >= 2, probes
    return probes


# =============================================================================
# Confidence derivation (_postprocess_threat)
# =============================================================================


class TestConfidenceDerivation:
    """The adapter's scores-to-confidence mechanism.

    Retargeted from the deleted ``_softmax`` suite, which pinned "class scores
    become one confidence per class, without overflowing". The heir is not a
    softmax — ``_postprocess_threat`` takes the argmax of the class-score block
    and keeps a detection only when that winning score clears the threshold —
    so the pin is about the surviving mechanism, not a pretend probability
    distribution: which class wins, what number becomes the confidence, where
    the threshold bites, and how the box is converted.
    """

    def test_winning_class_is_the_argmax_of_the_class_block(self) -> None:
        """Each anchor's class comes from argmax over its own score vector."""
        out = _threat_output()
        # Three anchors, each with a different class-score winner, plus a
        # distractor in slot 0 that must not win the argmax.
        for det, class_index in enumerate((0, 1, 3)):
            _plant(out, det, class_index=class_index, score=0.8)
            distractor = 4 if class_index != 0 else 5
            out[0, distractor, det] = 0.2

        detections = _postprocess_threat(out)
        assert len(detections) == 3
        names = [d["class"] for d in detections]
        # The vocabulary is derived from the shipped adapter, one name per class
        # slot, and stays distinct per slot (an aliasing bug would collapse two
        # weapon classes into one label).
        vocabulary = _probe_vocabulary()
        assert len(vocabulary) >= 4, vocabulary
        assert names == [vocabulary[i] for i in (0, 1, 3)], names

    def test_confidence_is_the_winning_score_not_an_aggregate(self) -> None:
        """confidence == the max class score for that anchor (the shipped
        contract the backend reads as max_confidence)."""
        out = _threat_output()
        _plant(out, 0, class_index=2, score=0.62)
        out[0, 4, 0] = 0.40  # a second, lower class score on the same anchor

        detections = _postprocess_threat(out)
        assert len(detections) == 1
        assert detections[0]["confidence"] == 0.62
        # Not the sum (1.02) and not the mean — the argmax value only.
        assert detections[0]["confidence"] < 1.0

    def test_threshold_is_inclusive_at_the_boundary_and_exclusive_below_it(self) -> None:
        """The 0.25 default keeps ==0.25 and drops the next float below it."""
        kept = _threat_output()
        _plant(kept, 0, score=0.25)
        assert len(_postprocess_threat(kept)) == 1

        dropped = _threat_output()
        _plant(dropped, 0, score=0.2499)
        assert _postprocess_threat(dropped) == []

        # Non-vacuity: the same tensor with an above-threshold score keeps, so
        # the empty result above is the threshold's doing, not a broken probe.
        _plant(dropped, 0, score=0.26)
        assert len(_postprocess_threat(dropped)) == 1

    def test_transposed_tensor_layout_is_normalised(self) -> None:
        """(1, 8400, 8) yields the same detection as the model's (1, 8, 8400)."""
        firsts = _threat_output()
        _plant(firsts, 0, box=(55.0, 110.0, 90.0, 180.0), class_index=1, score=0.9)
        transposed = _threat_output(layout="channels_last")
        _plant(
            transposed, 0, box=(55.0, 110.0, 90.0, 180.0), class_index=1, score=0.9, layout="channels_last"
        )

        a = _postprocess_threat(firsts)
        b = _postprocess_threat(transposed)
        assert len(a) == 1 and len(b) == 1
        assert a == b, "orientation normalisation diverged between layouts"

    def test_box_is_converted_from_cxcywh_to_corner_xywh(self) -> None:
        """cxcywh in, integer corner box out — the shape the backend crops with."""
        out = _threat_output()
        _plant(out, 0, box=(100.0, 200.0, 40.0, 60.0), class_index=0, score=0.9)

        (detection,) = _postprocess_threat(out)
        assert detection["bbox"] == {"x": 80, "y": 170, "width": 40, "height": 60}
        assert all(isinstance(v, int) for v in detection["bbox"].values())

    def test_class_index_beyond_the_vocabulary_degrades_instead_of_raising(self) -> None:
        """A model emitting more classes than the adapter knows yields a
        synthetic ``threat_<id>`` label rather than an IndexError 500."""
        out = _threat_output(n_classes=8)  # 4 box + 8 class scores
        _plant(out, 0, class_index=7, score=0.9)

        (detection,) = _postprocess_threat(out)
        vocabulary = _probe_vocabulary()
        assert detection["class"] not in vocabulary
        assert detection["class"].startswith("threat_")

    def test_all_zero_tensor_is_empty_not_a_phantom_detection(self) -> None:
        """The all-zero output is the no-detections case, not a 0-confidence hit."""
        assert _postprocess_threat(_threat_output()) == []


def _probe_vocabulary() -> list[str]:
    """The adapter's class vocabulary, probed through the function.

    ``THREAT_CLASSES`` is a local of ``_postprocess_threat`` (adapter :84), so it
    cannot be imported; planting a winner in each class slot and reading the
    label is the derivation that stays true when the tuple changes.
    """
    names: list[str] = []
    for index in range(4):
        out = _threat_output()
        _plant(out, 0, class_index=index, score=0.9)
        (detection,) = _postprocess_threat(out)
        names.append(detection["class"])
    assert len(set(names)) == len(names), f"class slots alias: {names}"
    return names


# =============================================================================
# /threat-detect endpoint tests
# =============================================================================


class TestThreatDetectEndpoint:
    """Tests for the POST /threat-detect endpoint."""

    async def test_threat_detected(self, client, mock_triton):
        """Threat detected returns correct fields."""
        output = _threat_output()
        _plant(output, 0, class_index=0, score=0.92)
        mock_triton.infer.return_value = {"output0": output}

        response = await client.post(
            "/threat-detect",
            json={"image": _make_b64_image()},
        )

        assert response.status_code == 200
        data = response.json()
        # Shipped contract (WP6.4 triage): ThreatResponse =
        # threats_detected/is_threat/max_confidence (adapters/
        # enrichment_light.py ThreatResponse; consumed by backend
        # EnrichmentClient.ThreatDetectionClientResult). The old field names
        # (threat_detected/threat_type/confidence/detections) exist in no
        # product layer.
        assert data["is_threat"] is True
        assert data["threats_detected"][0]["class"] == "knife"
        assert data["max_confidence"] == 0.92
        assert len(data["threats_detected"]) == 1

    async def test_requests_the_resident_threat_model_only(
        self, client, mock_triton
    ) -> None:
        """The wire call names the KEPT Triton model and its output.

        Residency is by repository contents, so a stale ``model_name`` here is a
        503 on every request that a mocked-infer test would sail past.
        """
        mock_triton.infer.return_value = {"output0": _threat_output()}

        await client.post("/threat-detect", json={"image": _make_b64_image()})

        call = mock_triton.infer.await_args
        assert call.kwargs["model_name"] == "threat"
        assert call.kwargs["outputs"] == ["output0"]
        assert call.kwargs["inputs"]["images"].shape == (1, 3, 640, 640)

    async def test_no_threat(self, client, mock_triton):
        """No threat returns threat_detected=False."""
        mock_triton.infer.return_value = {"output0": _threat_output()}

        response = await client.post(
            "/threat-detect",
            json={"image": _make_b64_image()},
        )

        assert response.status_code == 200
        data = response.json()
        # Shipped contract (WP6.4 triage): see test_threat_detected — the
        # shipped response has no per-response threat_type (class lives
        # inside each threats_detected entry).
        assert data["is_threat"] is False
        assert data["max_confidence"] == 0.0
        assert data["threats_detected"] == []

    async def test_max_confidence_is_the_worst_detection(self, client, mock_triton) -> None:
        """max_confidence is the max over detections, not the last one."""
        output = _threat_output()
        _plant(output, 0, class_index=0, score=0.9)
        _plant(output, 1, class_index=1, score=0.31)
        mock_triton.infer.return_value = {"output0": output}

        response = await client.post("/threat-detect", json={"image": _make_b64_image()})

        data = response.json()
        assert len(data["threats_detected"]) == 2
        assert data["max_confidence"] == 0.9

    async def test_threat_detect_triton_error(self, client, mock_triton):
        """Triton failure returns 503."""
        mock_triton.infer.side_effect = TritonClientError("Model not loaded")

        response = await client.post(
            "/threat-detect",
            json={"image": _make_b64_image()},
        )
        assert response.status_code == 503

    async def test_threat_detect_invalid_image(self, client, mock_triton):
        """Un-decodable base64 returns 400, and Triton is never called."""
        response = await client.post("/threat-detect", json={"image": "not-valid-base64!@#$"})

        assert response.status_code == 400
        mock_triton.infer.assert_not_awaited()


# =============================================================================
# /person-reid endpoint tests
# =============================================================================


class TestPersonReIDEndpoint:
    """Tests for the POST /person-reid endpoint."""

    async def test_person_reid_success(self, client, mock_triton):
        """Person ReID returns a normalized embedding."""
        raw_emb = np.random.default_rng(1).standard_normal((1, 512)).astype(np.float32)
        mock_triton.infer.return_value = {"embedding": raw_emb}

        response = await client.post(
            "/person-reid",
            json={"image": _make_b64_image()},
        )

        assert response.status_code == 200
        data = response.json()
        assert "embedding" in data
        assert data["embedding_dimension"] == len(data["embedding"])
        # Check L2 normalization
        norm = math.sqrt(sum(x * x for x in data["embedding"]))
        assert abs(norm - 1.0) < 0.01

    async def test_requests_the_resident_reid_model_in_osnet_shape(
        self, client, mock_triton
    ) -> None:
        """model_name/outputs/input geometry are the ONNX contract for `reid`."""
        mock_triton.infer.return_value = {"embedding": np.zeros((1, 512), np.float32)}

        await client.post("/person-reid", json={"image": _make_b64_image()})

        call = mock_triton.infer.await_args
        assert call.kwargs["model_name"] == "reid"
        assert call.kwargs["outputs"] == ["embedding"]
        # OSNet input: 3 x 256(h) x 128(w), batch 1, ImageNet-normalised.
        assert call.kwargs["inputs"]["input"].shape == (1, 3, 256, 128)

    async def test_person_reid_embedding_dimension(self, client, mock_triton):
        """Embedding dimension field matches actual embedding length."""
        raw_emb = np.random.default_rng(2).standard_normal((1, 256)).astype(np.float32)
        mock_triton.infer.return_value = {"embedding": raw_emb}

        response = await client.post(
            "/person-reid",
            json={"image": _make_b64_image()},
        )

        data = response.json()
        assert data["embedding_dimension"] == 256

    async def test_zero_embedding_is_returned_unscaled(self, client, mock_triton) -> None:
        """The norm guard: a zero vector is passed through, not divided by ~0."""
        mock_triton.infer.return_value = {"embedding": np.zeros((1, 512), np.float32)}

        response = await client.post("/person-reid", json={"image": _make_b64_image()})

        data = response.json()
        assert data["embedding_dimension"] == 512
        assert all(x == 0.0 for x in data["embedding"])
        assert data["inference_time_ms"] >= 0.0

    async def test_person_reid_triton_error(self, client, mock_triton):
        """Triton failure returns 503."""
        mock_triton.infer.side_effect = TritonClientError("Error")

        response = await client.post(
            "/person-reid",
            json={"image": _make_b64_image()},
        )
        assert response.status_code == 503

    async def test_person_reid_invalid_image(self, client, mock_triton):
        """Invalid base64 returns 400."""
        response = await client.post(
            "/person-reid",
            json={"image": "bad!@#$"},
        )
        assert response.status_code == 400


# =============================================================================
# /health endpoint tests
# =============================================================================


class TestHealthEndpoint:
    """Tests for the GET /health endpoint.

    The probe set is derived (``_light_probe_set``) rather than remembered: this
    adapter's models are the residency set's non-yolo26 members, and the pre-S3
    expectation ``{"pose","threat","reid","pet","depth"}`` is exactly the kind of
    remembered list that makes a healthy boot report ``degraded`` forever.
    """

    async def test_health_all_ready(self, client, mock_triton):
        """Returns healthy when all models are ready."""
        mock_triton.is_model_ready.return_value = True
        expected_models = _light_probe_set()

        response = await client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert set(data["models"].keys()) == expected_models
        assert all(v is True for v in data["models"].values())

    async def test_health_probes_exactly_the_derived_set(self, client, mock_triton):
        """The readiness RPCs name the derived set — not a superset of it.

        The response's key list is the adapter's own loop output, so a stale name
        would show up there too; asserting the CALLS is the independent check that
        no retired model is being probed.
        """
        mock_triton.is_model_ready.return_value = True
        expected_models = _light_probe_set()

        await client.get("/health")

        probed = {c.args[0] for c in mock_triton.is_model_ready.await_args_list}
        assert probed == expected_models, sorted(probed)

    async def test_health_some_degraded(self, client, mock_triton):
        """Returns degraded when some models are not ready."""
        expected_models = _light_probe_set()
        sick = sorted(expected_models)[0]  # derived victim, not a hand-picked name

        async def model_ready(name):
            return name != sick

        mock_triton.is_model_ready.side_effect = model_ready

        response = await client.get("/health")

        data = response.json()
        assert data["status"] == "degraded"
        assert data["models"][sick] is False
        survivors = expected_models - {sick}
        assert survivors and all(data["models"][m] is True for m in survivors)

    async def test_health_all_down(self, client, mock_triton):
        """Returns degraded when all models are down."""
        mock_triton.is_model_ready.return_value = False

        response = await client.get("/health")

        data = response.json()
        assert data["status"] == "degraded"
        assert set(data["models"]) == _light_probe_set()
        assert all(v is False for v in data["models"].values())


class TestPersonReIDModelId:
    """B2.2 (owner ruling 68): the gateway reports the model ID recorded at
    export, and reports none rather than a guess when the record is missing."""

    @staticmethod
    def _repo(tmp_path, record) -> None:
        import json

        version = tmp_path / "reid" / "1"
        version.mkdir(parents=True)
        if record is not None:
            (version / "provenance.json").write_text(
                record if isinstance(record, str) else json.dumps(record)
            )

    async def test_reports_the_exported_checkpoints_id(
        self, client, mock_triton, tmp_path, monkeypatch
    ) -> None:
        sha = "ab" * 32
        self._repo(
            tmp_path,
            {"zoo_name": "osnet-ain-x1-0", "source_file": "osnet_ain_x1_0_msmt17.pth",
             "source_sha256": sha},
        )
        monkeypatch.setenv("TRITON_MODEL_REPOSITORY", str(tmp_path))
        mock_triton.infer.return_value = {"embedding": np.ones((1, 512), np.float32)}

        response = await client.post("/person-reid", json={"image": _make_b64_image()})

        assert response.json()["model_id"] == f"osnet-ain-x1-0@osnet_ain_x1_0_msmt17@{sha[:12]}"

    @pytest.mark.parametrize(
        "record",
        [
            None,
            "{not json",
            {"zoo_name": "osnet-ain-x1-0", "source_file": "x.pth", "source_sha256": "short"},
            {"zoo_name": "osnet-ain-x1-0", "source_file": "x.pth"},
        ],
        ids=["absent", "unparseable", "bad-sha", "no-sha"],
    )
    async def test_no_usable_record_reports_no_id(
        self, client, mock_triton, tmp_path, monkeypatch, record
    ) -> None:
        self._repo(tmp_path, record)
        monkeypatch.setenv("TRITON_MODEL_REPOSITORY", str(tmp_path))
        mock_triton.infer.return_value = {"embedding": np.ones((1, 512), np.float32)}

        response = await client.post("/person-reid", json={"image": _make_b64_image()})

        assert response.status_code == 200
        assert response.json()["model_id"] is None
