"""B2.2 parity gate (owner ruling 68): the backend's CPU OSNet path and the
gateway's ``/enrich-lt/person-reid`` path must see the same crop pixels the
same way.

Ruling 68: "the same crop pixels through both paths, with the same weights in
each, give cosine similarity of at least 0.999 on the final vector. That covers
resize, normalisation, the wire encoding (no lossy round-trip) and L2
normalisation ... If the gate fails, stop and report; do not loosen it."

This module starts with the preprocessing half: the tensor the gateway hands to
Triton must equal the backend transform's tensor for the same pixels.
"""

from __future__ import annotations

import base64
import io
from typing import Any
from unittest.mock import AsyncMock, patch

import numpy as np
import pytest
from ai.gateway.adapters.enrichment_light import router
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from PIL import Image

from backend.services.osnet_loader import build_reid_transform


def _crop(seed: int = 0, width: int = 147, height: int = 311) -> Image.Image:
    """A non-uniform crop at an odd size, so any resampling difference shows."""
    rng = np.random.default_rng(seed)
    return Image.fromarray(rng.integers(0, 256, (height, width, 3), dtype=np.uint8))


def _png_b64(image: Image.Image) -> str:
    buf = io.BytesIO()
    image.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode("ascii")


@pytest.fixture
def triton() -> AsyncMock:
    client = AsyncMock()
    client.infer = AsyncMock(return_value={"embedding": np.ones((1, 512), np.float32)})
    return client


@pytest.fixture
async def gateway(triton: AsyncMock):
    app = FastAPI()
    app.include_router(router)
    with patch(
        "ai.gateway.adapters.enrichment_light.get_triton_client", autospec=True, return_value=triton
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://gw") as client:
            yield client


class TestPreprocessingParity:
    @pytest.mark.parametrize("seed", [0, 1, 2])
    async def test_gateway_tensor_equals_backend_transform(
        self, gateway: AsyncClient, triton: AsyncMock, seed: int
    ) -> None:
        crop = _crop(seed)

        response = await gateway.post("/person-reid", json={"image": _png_b64(crop)})

        assert response.status_code == 200
        sent = triton.infer.await_args.kwargs["inputs"]["input"]
        expected = build_reid_transform()(crop).unsqueeze(0).numpy()
        assert sent.shape == expected.shape
        np.testing.assert_allclose(sent, expected, rtol=0, atol=1e-5)


#: Ruling 68's gate. Never loosened: a failure here is a stop-and-report.
PARITY_GATE = 0.999


@pytest.fixture(scope="module")
def osnet() -> Any:
    """torchreid's osnet_ain_x1_0, as the backend loader builds it, seeded weights."""
    import torch

    from backend.services import osnet_loader

    osnet_loader._ensure_tensorboard_importable()
    torch.manual_seed(68)
    model = osnet_loader._import_build_model()(
        name="osnet_ain_x1_0", num_classes=1, pretrained=False
    )
    return model.eval()


@pytest.fixture
def triton_running(osnet: Any) -> AsyncMock:
    """Triton's ``reid`` answered by the same module the backend path runs."""
    import torch

    async def infer(model_name: str, inputs: dict[str, Any], outputs: list[str]) -> dict:
        assert model_name == "reid"
        with torch.inference_mode():
            out = osnet(torch.from_numpy(inputs["input"]))
        return {"embedding": out.numpy()}

    client = AsyncMock()
    client.infer = AsyncMock(side_effect=infer)
    return client


class TestParityGate:
    """The same crop pixels through both paths, the same weights in each."""

    @pytest.mark.parametrize(
        ("seed", "width", "height"),
        [(0, 147, 311), (1, 64, 128), (2, 40, 90), (3, 220, 480)],
    )
    async def test_final_vectors_agree_to_the_gate(
        self, osnet: Any, triton_running: AsyncMock, seed: int, width: int, height: int
    ) -> None:
        from backend.services.osnet_loader import extract_person_embedding
        from backend.services.reid_gateway import embed_person_via_gateway

        crop = _crop(seed, width, height)
        handle = {"model": osnet, "transform": build_reid_transform(), "model_id": "local"}
        local = await extract_person_embedding(handle, crop)

        app = FastAPI()
        app.include_router(router)
        with patch(
            "ai.gateway.adapters.enrichment_light.get_triton_client",
            autospec=True,
            return_value=triton_running,
        ):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://gw") as c:
                remote = await embed_person_via_gateway(crop, base_url="http://gw", client=c)

        cosine = float(np.dot(local.embedding, remote.embedding))
        assert cosine >= PARITY_GATE, f"parity {cosine:.6f} below the gate {PARITY_GATE}"


class TestModelIdSpace:
    """The gateway's ID for the pinned weights is the backend's ID for them, so
    vectors from either path land in one space (and anything else in none)."""

    def test_gateway_id_for_the_pinned_checkpoint_equals_osnet_model_id(
        self, tmp_path: Any, monkeypatch: Any
    ) -> None:
        import json

        from ai.gateway.adapters.enrichment_light import reid_model_id

        from backend.services.osnet_loader import _osnet_zoo_row, osnet_model_id

        row = _osnet_zoo_row()
        version = tmp_path / "reid" / "1"
        version.mkdir(parents=True)
        (version / "provenance.json").write_text(
            json.dumps(
                {
                    "zoo_name": row["name"],
                    "source_file": row["runtime_file"],
                    "source_sha256": row["sha256"],
                }
            )
        )
        monkeypatch.setenv("TRITON_MODEL_REPOSITORY", str(tmp_path))
        reid_model_id.cache_clear()

        try:
            assert reid_model_id() == osnet_model_id()
        finally:
            reid_model_id.cache_clear()
