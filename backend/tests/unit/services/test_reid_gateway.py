"""B2.2: the backend's client for the gateway's ``/enrich-lt/person-reid``.

Owner ruling 68 pins what this client must do: send the crop with no lossy
round-trip, return the final L2-normalised vector, carry the model ID the
gateway reports (or the sentinel when it reports none, never a relabel), and
fail with its own error so the leg can degrade with its own reason code.
"""

from __future__ import annotations

import base64
import io
import json

import httpx
import numpy as np
import pytest
from PIL import Image

from backend.core.vector_provenance import LEGACY_MODEL_ID
from backend.services.reid_gateway import ReidGatewayUnavailable, embed_person_via_gateway

BASE_URL = "http://gw/enrich-lt"
GATEWAY_MODEL_ID = "osnet-ain-x1-0@osnet_ain_x1_0_msmt17@0123456789ab"


def _crop(width: int = 64, height: int = 128, seed: int = 0) -> Image.Image:
    rng = np.random.default_rng(seed)
    return Image.fromarray(rng.integers(0, 256, (height, width, 3), dtype=np.uint8))


def _client(handler) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


def _ok(embedding: list[float], model_id: str | None = GATEWAY_MODEL_ID):
    body: dict[str, object] = {
        "embedding": embedding,
        "embedding_dimension": len(embedding),
        "inference_time_ms": 1.0,
    }
    if model_id is not None:
        body["model_id"] = model_id
    return httpx.Response(200, json=body)


class TestRequest:
    async def test_posts_the_crop_losslessly_to_person_reid(self) -> None:
        crop = _crop()
        seen: dict[str, object] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            seen["url"] = str(request.url)
            seen["body"] = json.loads(request.content)
            return _ok([1.0] * 512)

        async with _client(handler) as client:
            await embed_person_via_gateway(crop, base_url=BASE_URL, client=client)

        assert seen["url"] == f"{BASE_URL}/person-reid"
        sent = Image.open(io.BytesIO(base64.b64decode(seen["body"]["image"])))  # type: ignore[index]
        assert np.array_equal(np.asarray(sent.convert("RGB")), np.asarray(crop))

    async def test_non_rgb_crops_are_sent_as_rgb(self) -> None:
        crop = _crop().convert("RGBA")
        seen: dict[str, Image.Image] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            raw = base64.b64decode(json.loads(request.content)["image"])
            seen["img"] = Image.open(io.BytesIO(raw))
            return _ok([1.0] * 512)

        async with _client(handler) as client:
            await embed_person_via_gateway(crop, base_url=BASE_URL, client=client)

        assert seen["img"].mode == "RGB"


class TestResult:
    async def test_vector_is_l2_normalised_and_carries_the_gateway_model_id(self) -> None:
        raw = [3.0] + [4.0] + [0.0] * 510

        async with _client(lambda _r: _ok(raw)) as client:
            result = await embed_person_via_gateway(
                _crop(), base_url=BASE_URL, client=client, detection_id="d1"
            )

        assert result.embedding.shape == (512,)
        assert np.isclose(np.linalg.norm(result.embedding), 1.0)
        assert np.allclose(result.embedding[:2], [0.6, 0.8])
        assert result.model_id == GATEWAY_MODEL_ID
        assert result.detection_id == "d1"

    async def test_missing_model_id_is_the_sentinel_never_a_relabel(self) -> None:
        async with _client(lambda _r: _ok([1.0] * 512, model_id=None)) as client:
            result = await embed_person_via_gateway(_crop(), base_url=BASE_URL, client=client)

        assert result.model_id == LEGACY_MODEL_ID

    @pytest.mark.parametrize(
        ("size", "confidence"),
        [((20, 40), 0.5), ((48, 100), 0.8), ((64, 128), 1.0)],
    )
    async def test_confidence_follows_the_local_paths_crop_size_rule(
        self, size: tuple[int, int], confidence: float
    ) -> None:
        async with _client(lambda _r: _ok([1.0] * 512)) as client:
            result = await embed_person_via_gateway(_crop(*size), base_url=BASE_URL, client=client)

        assert result.confidence == confidence

    async def test_wrong_dimension_is_refused(self) -> None:
        async with _client(lambda _r: _ok([1.0] * 256)) as client:
            with pytest.raises(RuntimeError):
                await embed_person_via_gateway(_crop(), base_url=BASE_URL, client=client)


class TestFailure:
    @pytest.mark.parametrize("status", [500, 503])
    async def test_server_errors_raise_gateway_unavailable(self, status: int) -> None:
        async with _client(lambda _r: httpx.Response(status, json={"detail": "x"})) as client:
            with pytest.raises(ReidGatewayUnavailable):
                await embed_person_via_gateway(_crop(), base_url=BASE_URL, client=client)

    async def test_connection_errors_raise_gateway_unavailable(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("refused", request=request)

        async with _client(handler) as client:
            with pytest.raises(ReidGatewayUnavailable):
                await embed_person_via_gateway(_crop(), base_url=BASE_URL, client=client)

    def test_gateway_unavailable_is_a_runtime_error(self) -> None:
        # extract_person_embedding's contract is RuntimeError on failure;
        # both callers catch on that.
        assert issubclass(ReidGatewayUnavailable, RuntimeError)
