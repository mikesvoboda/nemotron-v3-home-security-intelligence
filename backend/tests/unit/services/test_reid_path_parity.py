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
