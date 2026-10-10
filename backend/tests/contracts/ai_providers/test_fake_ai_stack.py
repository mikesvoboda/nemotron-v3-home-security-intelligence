"""The fake answers the backend's own startup gates and pipeline hops (O2.1).

The FakeProvider served the CONTRACT surface: one route per registry op, the
vlm verdict at the contract-only path ``/vlm/chat/completions``. The backend
never dials that path. Its ``VlmClient`` speaks the llama.cpp engine wire:
``GET /props`` for the pinned build, then ``POST /v1/chat/completions`` with a
``response_format`` json_schema whose ``probe_const`` nonce only an enforcing
grammar can echo (``constrained_decoding.build_probe_schema``). The fake
answered that path with the llm op's fixed prose, so a backend booted against
it logged its startup probe INCONCLUSIVE and scored nothing.

These pins hold the engine half of the fake and its scenario book:

* the backend's own startup gate, run through the real client, comes back
  ``enforced`` against the fake, with the build pin checked rather than
  skipped;
* the fixture image chooses the outcome: the sha256 of the bytes the detector
  uploads (and the VLM receives as a data URI) selects the scenario's
  detections and verdict, so a golden path can assert exact results;
* a scenario can make the verdict reply slow (the slow-reply failure mode),
  slower than the timeout the backend ships with;
* an image no scenario names keeps the deterministic, payload-seeded answers
  the rest of this tier pins byte for byte.

No skip or xfail (this tier's rule, ``AGENTS.md``).
"""

from __future__ import annotations

import base64
import hashlib
import json
import time
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import jsonschema
import pytest
from backend.ai_contract.fake.app import create_fake_app
from backend.ai_contract.fake.generators import create_response_bytes, generate
from httpx import ASGITransport, AsyncClient

FAKE = "http://fake"
PIN = "b7972"
SCHEMA_DIR = Path(__file__).resolve().parents[4] / "backend/ai_contract/schemas"


def _settings(tmp_path: Path, **overrides: Any) -> Any:
    from backend.core.config import Settings

    root = tmp_path / "foscam"
    root.mkdir(exist_ok=True)
    base: dict[str, Any] = {
        "ai_vlm_url": FAKE,
        "foscam_base_path": str(root),
        "vlm_enforcement_probe_enabled": True,
        "vlm_required_build": "",
    }
    base.update(overrides)
    return Settings(_env_file=None, **base)


@pytest.fixture(autouse=True)
def _fresh_breakers() -> Any:
    """The ai-vlm breaker is a registry singleton; a leg that opens it must
    not make a later one refuse without I/O."""
    from backend.services.circuit_breaker import reset_circuit_breaker_registry

    reset_circuit_breaker_registry()
    yield
    reset_circuit_breaker_registry()


async def _startup_check(app: Any, settings: Any) -> tuple[str, Any]:
    """The backend's own P0.3 startup gate (`main.run_constrained_startup_check`),
    fed the real VlmClient pointed at `app`."""
    from backend.main import run_constrained_startup_check
    from backend.services.vlm_client import VlmClient

    client = VlmClient(settings=settings, transport=ASGITransport(app=app), base_url=FAKE)
    analyzer = MagicMock()
    analyzer._get_client = MagicMock(return_value=client)
    container = MagicMock()
    container.get_async = AsyncMock(return_value=analyzer)
    try:
        return await run_constrained_startup_check(container), client
    finally:
        await client.close()


async def _post(app: Any, path: str, **kwargs: Any) -> Any:
    async with AsyncClient(transport=ASGITransport(app=app), base_url=FAKE) as client:
        return await client.post(path, **kwargs)


async def _get(app: Any, path: str) -> Any:
    async with AsyncClient(transport=ASGITransport(app=app), base_url=FAKE) as client:
        return await client.get(path)


def _chat(image: bytes | None, schema: dict[str, Any]) -> dict[str, Any]:
    """The engine-wire body VlmClient sends (vlm_client.py: assess)."""
    content: list[dict[str, Any]] = []
    if image is not None:
        b64 = base64.b64encode(image).decode()
        content.append({"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}})
    content.append({"type": "text", "text": "Emit the verdict object."})
    return {
        "messages": [{"role": "user", "content": content}],
        "temperature": 0.0,
        "max_tokens": 2048,
        "response_format": {
            "type": "json_schema",
            "json_schema": {"name": "vlm_verdict", "schema": schema},
        },
    }


def _wire_schema(tmp_path: Path) -> dict[str, Any]:
    from backend.services.vlm_client import VlmClient

    return VlmClient(settings=_settings(tmp_path), base_url=FAKE)._wire_schema()


class TestTheBackendsStartupGatesPass:
    async def test_the_constrained_decoding_probe_is_enforced(self, tmp_path: Path) -> None:
        """The package's first test. The backend's startup gate, run through
        its own client against the fake, answers `enforced`: the fake echoes
        the probe's nonce const, as an enforcing grammar does."""
        verdict, client = await _startup_check(create_fake_app(), _settings(tmp_path))

        assert verdict == "enforced"
        assert client._enforced is True

    async def test_the_build_pin_is_checked_and_holds(self, tmp_path: Path) -> None:
        """With VLM_REQUIRED_BUILD set the gate reads /props and refuses a build
        that lacks the pin; the fake reports the build it is told to."""
        settings = _settings(tmp_path, vlm_required_build=PIN)

        pinned, client = await _startup_check(
            create_fake_app(build_info=f"{PIN}-fake-ai"), settings
        )
        unpinned, _ = await _startup_check(create_fake_app(build_info="b0000-fake-ai"), settings)

        assert pinned == "enforced"
        assert PIN in client._build_info
        assert unpinned == "inconclusive"  # the pin is enforced, not skipped

    async def test_props_names_a_model_file(self) -> None:
        props = (await _get(create_fake_app(build_info=f"{PIN}-fake-ai"), "/props")).json()

        assert props["build_info"] == f"{PIN}-fake-ai"
        assert Path(props["model_path"]).suffix == ".gguf"

    @pytest.mark.parametrize("path", ["/health", "/yolo26/health"])
    async def test_the_health_routes_the_backend_polls_answer_200(self, path: str) -> None:
        """`/health` is llama-server's and the gateway's; `/yolo26/health` is the
        detector's (system.py's readiness probe and the broadcaster read the
        status code)."""
        assert (await _get(create_fake_app(), path)).status_code == 200


class TestTheEngineWire:
    async def test_a_constrained_reply_validates_against_the_requested_schema(
        self, tmp_path: Path
    ) -> None:
        schema = _wire_schema(tmp_path)

        resp = await _post(create_fake_app(), "/v1/chat/completions", json=_chat(None, schema))

        assert resp.status_code == 200
        choice = resp.json()["choices"][0]
        assert choice["finish_reason"] == "stop"
        jsonschema.validate(json.loads(choice["message"]["content"]), schema)

    async def test_an_unconstrained_chat_keeps_the_llm_ops_bytes(self) -> None:
        """No response_format (the batch-open wake call, the llm op's golden
        request): the registry op's answer, byte for byte."""
        golden = json.loads(
            (
                Path(__file__).parent / "golden/payloads/llm_chat_completion.request.example.json"
            ).read_text()
        )

        resp = await _post(create_fake_app(), "/v1/chat/completions", json=golden)

        assert resp.content == create_response_bytes(generate("llm_chat_completion", golden))


class TestTheFixtureImageChoosesTheOutcome:
    def test_the_book_has_the_scenarios_the_golden_paths_need(self) -> None:
        from backend.ai_contract.fake.scenarios import ScenarioBook

        book = ScenarioBook.load()
        verdicts = {s.verdict["verdict"] for s in book if not s.reply_delay_seconds}

        assert verdicts == {"confirmed", "rejected", "uncertain"}
        assert any(s.reply_delay_seconds for s in book), "no slow-reply scenario"
        assert len({s.digest for s in book}) == len(book), "two scenarios share an image"

    async def test_the_detector_returns_the_scenarios_detections(self) -> None:
        from backend.ai_contract.fake.scenarios import ScenarioBook

        app = create_fake_app()
        for scenario in ScenarioBook.load():
            data = scenario.image.read_bytes()

            resp = await _post(
                app, "/yolo26/detect", files={"file": (scenario.image.name, data, "image/jpeg")}
            )

            body = resp.json()
            assert resp.status_code == 200
            assert body["detections"] == list(scenario.detections), scenario.name
            assert (body["image_width"], body["image_height"]) == (
                scenario.width,
                scenario.height,
            )

    async def test_the_vlm_client_parses_the_scenarios_verdict(self, tmp_path: Path) -> None:
        """Through the real VlmClient: the image the pipeline stored is read,
        sent as a data URI, and the scenario's verdict comes back."""
        from backend.ai_contract.fake.scenarios import ScenarioBook
        from backend.services.vlm_client import VlmClient
        from backend.services.vlm_verdict import VlmAssessRequest

        settings = _settings(tmp_path)
        camera = Path(settings.foscam_base_path) / "front"
        camera.mkdir()
        for scenario in (s for s in ScenarioBook.load() if not s.reply_delay_seconds):
            (camera / scenario.image.name).write_bytes(scenario.image.read_bytes())
            client = VlmClient(
                settings=settings, transport=ASGITransport(app=create_fake_app()), base_url=FAKE
            )
            try:
                verdict = await client.assess(
                    VlmAssessRequest(
                        image_paths=[f"front/{scenario.image.name}"],
                        context={"camera_id": "front", "timestamp": "2026-10-10T00:00:00+00:00"},
                    )
                )
            finally:
                await client.close()

            served = verdict.model_dump()
            served.pop("provenance")  # stamped by the client, never parsed
            expected = {k: v for k, v in scenario.verdict.items() if k != "provenance"}
            assert served == expected, scenario.name

    async def test_a_slow_scenario_delays_the_verdict_reply(self, tmp_path: Path) -> None:
        from backend.ai_contract.fake.scenarios import Scenario, ScenarioBook

        base = next(s for s in ScenarioBook.load() if not s.reply_delay_seconds)
        slow = ScenarioBook([Scenario(**{**base.__dict__, "reply_delay_seconds": 0.3})])
        body = _chat(base.image.read_bytes(), _wire_schema(tmp_path))

        started = time.monotonic()
        resp = await _post(create_fake_app(scenarios=slow), "/v1/chat/completions", json=body)

        assert resp.status_code == 200
        assert time.monotonic() - started >= 0.3

    async def test_a_probe_carrying_the_slow_image_is_not_delayed(self, tmp_path: Path) -> None:
        """The client probes with the batch's first image before it trusts a
        verdict (vlm_client.py: assess -> _probe_enforcement(parts)). Delaying
        that probe would fail the gate, not exercise the slow verdict reply
        the mode exists for (B1.1's leg). A probe is the schema with a const."""
        from backend.ai_contract.fake.scenarios import Scenario, ScenarioBook
        from backend.services.constrained_decoding import build_probe_schema

        base = next(s for s in ScenarioBook.load() if not s.reply_delay_seconds)
        slow = ScenarioBook([Scenario(**{**base.__dict__, "reply_delay_seconds": 5.0})])
        schema, nonce = build_probe_schema(_wire_schema(tmp_path))

        started = time.monotonic()
        resp = await _post(
            create_fake_app(scenarios=slow),
            "/v1/chat/completions",
            json=_chat(base.image.read_bytes(), schema),
        )

        assert time.monotonic() - started < 1.0
        assert json.loads(resp.json()["choices"][0]["message"]["content"])["probe_const"] == nonce

    def test_the_shipped_slow_scenario_outlasts_the_shipped_read_timeout(
        self, tmp_path: Path
    ) -> None:
        """The slow-reply mode must trip the backend's D1 budget as shipped
        (config.py ai_vlm_read_timeout), or it would test nothing."""
        from backend.ai_contract.fake.scenarios import ScenarioBook

        timeout = _settings(tmp_path).ai_vlm_read_timeout
        slow = [s.reply_delay_seconds for s in ScenarioBook.load() if s.reply_delay_seconds]

        assert slow and all(delay > timeout for delay in slow)

    def test_every_scenario_image_passes_the_file_watchers_checks(self) -> None:
        """A fixture the watcher drops never reaches the detector."""
        from backend.ai_contract.fake.scenarios import ScenarioBook
        from backend.services.file_watcher import is_valid_image

        for scenario in ScenarioBook.load():
            assert is_valid_image(str(scenario.image)), scenario.name

    async def test_every_scenario_detect_reply_is_a_valid_wire_reply(self) -> None:
        from backend.ai_contract.fake.scenarios import ScenarioBook

        schema = json.loads((SCHEMA_DIR / "yolo26_detect.response.json").read_text())
        app = create_fake_app()
        for scenario in ScenarioBook.load():
            resp = await _post(
                app,
                "/yolo26/detect",
                files={"file": (scenario.image.name, scenario.image.read_bytes())},
            )
            jsonschema.validate(resp.json(), schema)

    def test_every_scenario_verdict_is_a_valid_wire_verdict(self) -> None:
        from backend.ai_contract.fake.scenarios import ScenarioBook

        schema = json.loads((SCHEMA_DIR / "vlm_assess.response.json").read_text())
        for scenario in ScenarioBook.load():
            jsonschema.validate(scenario.verdict, schema)


class TestAnUnknownImageStaysDeterministic:
    @pytest.mark.parametrize(
        ("body", "content_type"),
        [
            (b"abc", "multipart/form-data"),  # no boundary: Starlette's 400
            (b"--x\r\nNoColonHere\r\n\r\nabc\r\n--x--\r\n", "multipart/form-data; boundary=x"),
        ],
        ids=["no-boundary", "bad-part-header"],
    )
    async def test_an_upload_that_does_not_parse_keeps_the_literal_script(
        self, body: bytes, content_type: str
    ) -> None:
        """Before scenarios the detect route never parsed the upload, so a
        broken one still got the literal script; parsing it must not turn
        that into a 400 or a 500."""
        resp = await _post(
            create_fake_app(),
            "/yolo26/detect",
            content=body,
            headers={"content-type": content_type},
        )

        assert resp.status_code == 200
        assert resp.content == create_response_bytes(generate("yolo26_detect"))

    async def test_detections_for_an_unknown_image_are_the_literal_script(self) -> None:
        resp = await _post(
            create_fake_app(), "/yolo26/detect", files={"file": ("x.jpg", b"not-a-scenario")}
        )

        assert resp.content == create_response_bytes(generate("yolo26_detect"))

    async def test_the_verdict_is_keyed_on_the_image_bytes(self, tmp_path: Path) -> None:
        """spec §3: a deterministic verdict keyed on an image hash. Same bytes
        replay identically; a sweep of different bytes is not frozen to one."""
        schema = _wire_schema(tmp_path)
        app = create_fake_app()

        async def verdict_for(image: bytes) -> tuple[str, int]:
            resp = await _post(app, "/v1/chat/completions", json=_chat(image, schema))
            content = json.loads(resp.json()["choices"][0]["message"]["content"])
            return content["verdict"], content["risk_score"]

        same = [await verdict_for(b"image-a") for _ in range(2)]
        sweep = {await verdict_for(hashlib.sha256(str(i).encode()).digest()) for i in range(12)}

        assert same[0] == same[1]
        assert len(sweep) > 1


class TestTheFaultKnobReachesTheNewPaths:
    async def test_a_scenario_detect_reply_takes_the_fault_like_the_literal_one(self) -> None:
        """The scenario path runs the registry ops' own schema-invalid code. For
        yolo26_detect that breaks nothing on either path: its snapshot is a
        bare dict naming no required key (generators.py GEN_GAPS)."""
        from backend.ai_contract.fake.scenarios import ScenarioBook

        app = create_fake_app()
        changed = []
        for data in (b"not-a-scenario", next(iter(ScenarioBook.load())).image.read_bytes()):
            replies = [
                await _post(app, "/yolo26/detect", files={"file": ("x.jpg", data)}, headers=h)
                for h in ({}, {"x-fake-fault": "schema-invalid"})
            ]
            changed.append(replies[0].content != replies[1].content)

        assert changed[0] == changed[1]

    async def test_schema_invalid_breaks_a_constrained_reply(self, tmp_path: Path) -> None:
        schema = _wire_schema(tmp_path)

        resp = await _post(
            create_fake_app(),
            "/v1/chat/completions",
            json=_chat(None, schema),
            headers={"x-fake-fault": "schema-invalid"},
        )

        content = json.loads(resp.json()["choices"][0]["message"]["content"])
        assert resp.status_code == 200
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(content, schema)


class TestTheContainerSeam:
    async def test_remote_app_relays_the_fakes_answers_unchanged(self) -> None:
        """`remote_app` is what this tier's conftest swaps in for the factory
        when FAKE_AI_URL names a running fake; it must relay status and bytes
        exactly, multipart uploads included, and report every forward."""
        from backend.ai_contract.fake.app import DEFAULT_BUILD_INFO
        from backend.ai_contract.fake.remote import remote_app
        from backend.ai_contract.fake.scenarios import ScenarioBook

        local = create_fake_app(build_info=DEFAULT_BUILD_INFO)  # arguments: always in-process
        forwarded: list[tuple[str, str]] = []
        relay = remote_app(
            FAKE,
            transport=ASGITransport(app=local),
            on_request=lambda method, path: forwarded.append((method, path)),
        )
        image = next(iter(ScenarioBook.load())).image
        golden = json.loads(
            (
                Path(__file__).parent / "golden/payloads/llm_completion.request.example.json"
            ).read_text()
        )
        calls: list[tuple[str, str, dict[str, Any]]] = [
            ("GET", "/props", {}),
            ("GET", "/no-such-route", {}),
            ("POST", "/completion", {"json": golden}),
            ("POST", "/yolo26/detect", {"files": {"file": (image.name, image.read_bytes())}}),
        ]

        for method, path, kwargs in calls:
            async with AsyncClient(transport=ASGITransport(app=local), base_url=FAKE) as c:
                direct = await c.request(method, path, **kwargs)
            async with AsyncClient(transport=ASGITransport(app=relay), base_url=FAKE) as c:
                relayed = await c.request(method, path, **kwargs)

            assert (relayed.status_code, relayed.content) == (direct.status_code, direct.content)
        assert forwarded == [(method, path) for method, path, _ in calls]
