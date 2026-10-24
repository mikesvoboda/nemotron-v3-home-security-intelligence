"""B2.2 / [r306a] (owner rulings 68, 306, 325): the seam is ``osnet_loader.extract_person_embedding``.

"Put a gateway-backed embedding behind it (``/enrich-lt/person-reid``), so
neither caller changes." The switch is ``Settings.reid_backend``; after O2.4's
parity pass (`[r312a]` Run 2, #7238 `6353368002`, ruling 325), the default is
``gateway``.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import numpy as np
import pytest
from PIL import Image

from backend.core.config import Settings
from backend.services import osnet_loader
from backend.services.osnet_loader import PersonEmbeddingResult

GW = "http://gw/enrich-lt"
REPO_ROOT = Path(__file__).resolve().parents[4]


def _settings(backend: str) -> SimpleNamespace:
    return SimpleNamespace(reid_backend=backend, enrichment_light_url=GW)


class TestSetting:
    def test_defaults_to_gateway(self) -> None:
        assert Settings.model_fields["reid_backend"].default == "gateway"

    def test_env_example_defaults_to_gateway(self) -> None:
        reid_lines = [
            line
            for line in (REPO_ROOT / ".env.example").read_text().splitlines()
            if line.startswith("REID_BACKEND=")
        ]
        assert reid_lines == ["REID_BACKEND=gateway"]

    def test_refuses_an_unknown_backend(self) -> None:
        with pytest.raises(ValueError):
            Settings(reid_backend="cuda")


class TestHandle:
    def test_gateway_backend_gives_a_gateway_handle_without_the_local_model(self) -> None:
        with (
            patch.object(
                osnet_loader, "get_settings", autospec=True, return_value=_settings("gateway")
            ),
            patch(
                "backend.services.model_zoo.get_model_manager",
                autospec=True,
                side_effect=AssertionError("the local model must not be consulted"),
            ),
        ):
            handle = osnet_loader.get_reid_handle()

        # model_id None: the belt is the gateway's per-response ID, never assumed.
        assert handle == {"kind": "gateway", "base_url": GW, "model_id": None}

    def test_local_backend_keeps_the_resident_handle(self) -> None:
        resident = {"model": object(), "transform": object(), "model_id": "local-id"}
        manager = SimpleNamespace(_loaded_models={osnet_loader.OSNET_ZOO_NAME: resident})
        with (
            patch.object(
                osnet_loader, "get_settings", autospec=True, return_value=_settings("local")
            ),
            patch(
                "backend.services.model_zoo.get_model_manager", autospec=True, return_value=manager
            ),
        ):
            assert osnet_loader.get_reid_handle() is resident


class TestExtract:
    async def test_a_gateway_handle_embeds_through_the_gateway(self) -> None:
        crop = Image.new("RGB", (64, 128))
        expected = PersonEmbeddingResult(
            embedding=np.ones(512, np.float32), detection_id="d", model_id="gw-id"
        )
        with patch(
            "backend.services.reid_gateway.embed_person_via_gateway",
            new=AsyncMock(return_value=expected),
        ) as gateway:
            result = await osnet_loader.extract_person_embedding(
                {"kind": "gateway", "base_url": GW, "model_id": None}, crop, detection_id="d"
            )

        assert result is expected
        gateway.assert_awaited_once_with(crop, base_url=GW, detection_id="d")

    async def test_gateway_failures_keep_their_type(self) -> None:
        from backend.services.reid_gateway import ReidGatewayUnavailable

        with (
            patch(
                "backend.services.reid_gateway.embed_person_via_gateway",
                new=AsyncMock(side_effect=ReidGatewayUnavailable("down")),
            ),
            pytest.raises(ReidGatewayUnavailable),
        ):
            await osnet_loader.extract_person_embedding(
                {"kind": "gateway", "base_url": GW, "model_id": None}, Image.new("RGB", (8, 8))
            )


class TestBatch:
    async def test_batch_extraction_refuses_a_gateway_handle(self) -> None:
        """Nothing calls the batch path today; it is local-only, and says so."""
        with pytest.raises(RuntimeError, match="gateway"):
            await osnet_loader.extract_person_embeddings_batch(
                {"kind": "gateway", "base_url": GW, "model_id": None}, [Image.new("RGB", (8, 8))]
            )
