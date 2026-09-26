"""Unit tests for `vlm_client` (Phase 1.3, spec §2:101, §3, §6 ladder).

The client is the ONLY thing that talks to the llama.cpp chat wire, so each
§6 invariant that lives in transport-land gets pinned here against a tiny
FAKE llama-server (ASGITransport, in-process, hermetic):

  - wire shape: /v1/chat/completions, base64 data-URI image parts, the
    response_format NESTED wrapper arm-B-proven at G0 (json_schema.schema),
    the wire schema with grammar-unsafe constraints stripped (minLength/
    bounds are post-validated client-side - S-2's ledger note);
  - enforcement probe: once per endpoint, ONLY ENFORCED cached; an
    endpoint that ACCEPTS the schema and IGNORES it must read NOT enforced
    (E5's class of lie), never a silent success;
  - the §6 retry: transport error -> retry EXACTLY once at temperature 0;
    still bad -> raise (the analyzer maps the raise to verification_failed);
  - breaker + degradation: repeated failures open "ai-vlm"; open breaker
    pushes DegradationManager unhealthy and refuses calls without I/O.

The image-path guard (read only under settings.foscam_base_path) pins the
privacy rule: a poisoned DB row must not turn the backend into a file
reader for /etc.
"""

from __future__ import annotations

import json
from typing import Any, ClassVar

import httpx
import pytest
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from backend.services import vlm_client as vc
from backend.services.nemotron_analyzer import ConstrainedDecodingNotEnforced
from backend.services.vlm_verdict import VlmAssessRequest, VlmVerdict

# ---------------------------------------------------------------------------
# The fake llama-server. Modes mirror what the REAL server was observed to
# do (G0/S-2 [V]): strict honors a well-formed nested json_schema wrapper
# and dumps "{}" for a malformed one; ignore accepts the param and answers
# prose (E5's nvext.guided_json lesson, generalized to response_format).
# ---------------------------------------------------------------------------

_BUILD_INFO = "b7972-e06088da0"


def _fill_from_schema(schema: dict[str, Any]) -> Any:  # noqa: PLR0911 - one return per schema type
    """Type-driven filler so the strict fake answers with schema-shaped
    content without hardcoding the verdict shape here (the schema is the
    single source; if 1.x regenerates it the fake follows)."""
    if "enum" in schema:
        # `verdict` is a bare enum (a pydantic Literal emits no "type"), so
        # this branch must come BEFORE the type dispatch - a type-blind "ok"
        # for an enum field would fail VlmVerdict post-validation and make
        # the strict fake indistinguishable from a lying one.
        return schema["enum"][0]
    t = schema.get("type")
    if t == "string":
        return "ok"
    if t == "boolean":
        return True
    if t == "integer":
        return 50  # VlmVerdict post-validation bounds are client-side (50 is in [0,100])
    if t == "array":
        return [_fill_from_schema(schema["items"])]
    if t == "object":
        return {k: _fill_from_schema(v) for k, v in (schema.get("properties") or {}).items()}
    return "ok"


class RecordingTransport(httpx.AsyncBaseTransport):
    """ASGITransport, plus: parse and keep every JSON request body so
    `client._app_calls()` can inspect the WIRE (probe-then-real ordering,
    the retry's temperature, wrapper shape) without the client growing any
    prod-side recording."""

    def __init__(self, app: FastAPI) -> None:
        self._inner = httpx.ASGITransport(app=app)
        self.calls: list[dict[str, Any]] = []

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        response = await self._inner.handle_async_request(request)
        if request.url.path == "/v1/chat/completions":  # /props would skew the counts
            try:
                body = json.loads(bytes(await request.aread()))
            except Exception:  # pragma: no cover - the client always sends JSON
                body = {"__raw__": True}
            self.calls.append({"path": request.url.path, **body})
        return response


def make_fake_llama(mode: str = "strict", build_info: str = _BUILD_INFO) -> FastAPI:
    app = FastAPI()
    app.state.calls = []  # every chat request body, in order (wake tests read this directly)

    @app.get("/props")
    async def props() -> dict:
        return {"build_info": build_info}

    @app.post("/v1/chat/completions")
    async def chat(request: Request) -> JSONResponse:
        body = await request.json()
        app.state.calls.append(body)
        if mode == "down":
            return JSONResponse({"error": "gone"}, status_code=503)
        if mode == "schema-invalid":
            # 200 + content that VIOLATES VlmVerdict: the float risk_score
            # from the spec's own bad example (int ge/le fails). Post-
            # validation must catch what a lying grammar let through.
            return JSONResponse({"choices": [{"message": {"content": '{"risk_score": 0.25}'}}]})
        rf = body.get("response_format")
        content: str
        if rf is None:
            content = "the scene" if body.get("max_tokens") == 1 else "prose"
        elif mode == "ignore":
            # accepts the parameter, answers prose WITHOUT the grammar -
            # the exact E5-class lie the probe must catch.
            content = "The scene shows a driveway with a car."
        else:
            # strict: a WELL-FORMED wrapper gets grammar-shaped content;
            # a MALFORMED wrapper (schema key missing) makes llama.cpp dump
            # the EMPTY grammar - arm C's observed behavior.
            wrapper = rf.get("json_schema") or {}
            schema = wrapper.get("schema")
            if not isinstance(schema, dict):
                content = "{}"
            else:
                filled = _fill_from_schema(schema)
                const = (schema.get("properties") or {}).get("probe_const", {}).get("const")
                if const is not None:
                    filled["probe_const"] = const  # grammar ENFORCEMENT == echo
                content = json.dumps(filled)
        return JSONResponse(
            {"choices": [{"message": {"content": content}}], "usage": {"total_tokens": 7}}
        )

    return app


@pytest.fixture(autouse=True)
def _fresh_breaker_registry():
    """The "ai-vlm" breaker is a REGISTRY singleton; every client instance
    shares it. Without a per-test reset, the failures one test records (the
    ladder pins, the probe fail-closed pins) would open the breaker halfway
    through the module and every later assess() would read UNAVAILABLE -
    tests must not depend on file order."""
    from backend.services.circuit_breaker import reset_circuit_breaker_registry

    reset_circuit_breaker_registry()
    yield
    reset_circuit_breaker_registry()


@pytest.fixture
def image_dir(tmp_path, monkeypatch):
    """Two tiny 'stills' under a foscam-root the settings override points at.
    Synthetic bytes only - the privacy rule applies to test fixtures too."""
    root = tmp_path / "foscam"
    (root / "front_door").mkdir(parents=True)
    for name in ("a.jpg", "b.jpg"):
        (root / "front_door" / name).write_bytes(b"\xff\xd8\xff" + b"\x00" * 32)
    monkeypatch.setattr(
        vc.get_settings(), "foscam_base_path", str(root), raising=False
    )  # settings is a cached singleton; setattr on the instance is the house override
    return root


def _request(paths: list[str], **context_overrides: Any) -> VlmAssessRequest:
    context: dict[str, Any] = {
        "camera_id": "front_door",
        "detections": [{"object_type": "person", "confidence": 0.9}],
        "zones": ["porch"],
        "timestamp": "2026-09-25T12:00:00+00:00",
    }
    context.update(context_overrides)
    return VlmAssessRequest(image_paths=paths, context=context)


def make_client(mode: str = "strict", **settings_overrides: Any) -> vc.VlmClient:
    """A client dialed at the fake via a recording ASGITransport (no socket)."""
    settings = vc.get_settings().model_copy(
        update={"vlm_enforcement_probe_enabled": True, **settings_overrides}
    )
    return vc.VlmClient(
        base_url="http://fake-vlm:8098",
        transport=RecordingTransport(make_fake_llama(mode)),
        settings=settings,
    )


class TestWireShape:
    async def test_assess_posts_the_chat_shape(self, image_dir) -> None:
        client = make_client()
        verdict = await client.assess(
            _request([str(image_dir / "front_door/a.jpg"), str(image_dir / "front_door/b.jpg")])
        )
        assert isinstance(verdict, VlmVerdict)
        # Real call is the LAST chat call (the probe ran first).
        body = client._app_calls()[-1]
        assert body["max_tokens"] >= 200, "grammar cannot close past the budget (S-2)"
        content = body["messages"][0]["content"]
        uris = [p["image_url"]["url"] for p in content if p["type"] == "image_url"]
        texts = [p["text"] for p in content if p["type"] == "text"]
        assert len(uris) == 2 and all(u.startswith("data:image/") for u in uris)
        assert any("person" in t for t in texts), "the AssessInput context reaches the prompt"
        # Arm-B nested wrapper - NOT a flattened top-level schema.
        wrapper = body["response_format"]["json_schema"]
        assert wrapper["name"] and isinstance(wrapper["schema"], dict)
        props = wrapper["schema"]["properties"]
        assert {"verdict", "risk_score", "summary", "criteria", "provenance"} <= set(props)
        await client.close()

    async def test_wire_schema_carries_no_grammar_unsafe_constraints(self, image_dir) -> None:
        """S-2 [V]: minLength/bounds support at the pin is UNVERIFIED - the
        wire schema strips them; VlmVerdict post-validation enforces them
        client-side. Sending them would risk an INCONCLUSIVE probe on a
        server that validates what it cannot enforce."""
        client = make_client()
        await client.assess(_request([str(image_dir / "front_door/a.jpg")]))
        schema = client._app_calls()[-1]["response_format"]["json_schema"]["schema"]
        blob = json.dumps(schema)
        assert "minLength" not in blob and "minimum" not in blob and "maximum" not in blob
        await client.close()

    async def test_paths_never_bytes_and_never_leave_the_root(self, image_dir) -> None:
        client = make_client()
        with pytest.raises(vc.VlmImageError):
            await client.assess(_request(["/etc/passwd"]))
        with pytest.raises(vc.VlmImageError):
            await client.assess(_request([str(image_dir / ".." / "escape.jpg")]))
        assert client._app_calls() == [], "refused BEFORE any I/O"
        await client.close()

    async def test_missing_file_raises_image_error_not_silently_skipped(self, image_dir) -> None:
        client = make_client()
        with pytest.raises(vc.VlmImageError):
            await client.assess(_request([str(image_dir / "front_door" / "nope.jpg")]))
        await client.close()


class TestEnforcementProbe:
    async def test_enforced_echoes_const_then_caches(self, image_dir) -> None:
        client = make_client("strict")
        req = _request([str(image_dir / "front_door/a.jpg")])
        await client.assess(req)
        first_round = len(client._app_calls())
        assert first_round == 2, "probe + real call"
        probe_body = client._app_calls()[0]
        schema = probe_body["response_format"]["json_schema"]["schema"]
        assert "probe_const" in schema["properties"], (
            "the nonce const rides the REAL verdict schema"
        )
        await client.assess(req)
        # Second assess: NO new probe - only one more call (the real one).
        assert len(client._app_calls()) == first_round + 1
        await client.close()

    async def test_ignoring_endpoint_reads_not_enforced_and_raises(self, image_dir) -> None:
        """The E5-class regression the plan names: accepts-but-ignores must
        NOT be a silent prose mode. First assess RAISES, nothing cached -
        the next call re-probes (S-1: a bad result must not ossify)."""
        client = make_client("ignore")
        with pytest.raises(ConstrainedDecodingNotEnforced) as exc:
            await client.assess(_request([str(image_dir / "front_door/a.jpg")]))
        assert exc.value.verdict in {"ignored", "inconclusive"}
        with pytest.raises(ConstrainedDecodingNotEnforced):
            await client.assess(_request([str(image_dir / "front_door/a.jpg")]))
        await client.close()

    async def test_only_enforced_is_cached(self, image_dir) -> None:
        """An unreachable endpoint must not cache INCONCLUSIVE either - each
        call re-probes until ENFORCED."""
        client = make_client("down")
        for _ in range(2):
            with pytest.raises(ConstrainedDecodingNotEnforced):
                await client.assess(_request([str(image_dir / "front_door/a.jpg")]))
        await client.close()

    async def test_build_info_pin_fail_closed(self, image_dir) -> None:
        """S-2: enforcement is per-build. A server whose build_info lacks
        the pinned build must not launder an old proof onto it."""
        client = make_client("strict", vlm_required_build="b99999")
        with pytest.raises(ConstrainedDecodingNotEnforced) as exc:
            await client.assess(_request([str(image_dir / "front_door/a.jpg")]))
        assert exc.value.verdict == "inconclusive"
        await client.close()

    async def test_probe_disabled_skips_probe_traffic(self, image_dir) -> None:
        client = make_client("strict", vlm_enforcement_probe_enabled=False)
        await client.assess(_request([str(image_dir / "front_door/a.jpg")]))
        assert len(client._app_calls()) == 1, "flag-off installs see zero probe traffic"
        await client.close()


class TestFailureLadder:
    async def test_transport_error_retries_once_at_temperature_zero(self, image_dir) -> None:
        """§6 step 1: transport error -> retry EXACTLY once at temp 0. A
        second failure raises - the analyzer turns that into
        verification_failed (its tests pin the mapping)."""
        # Enforcement probe disabled: this isolates the RETRY of the real
        # call, not the probe's fail-closed path (pinned in TestEnforcementProbe).
        client = make_client("down", vlm_enforcement_probe_enabled=False)
        with pytest.raises(vc.VlmTransportError):
            await client.assess(_request([str(image_dir / "front_door/a.jpg")]))
        calls = client._app_calls()
        assert len(calls) == 2, "exactly one retry, no hammering"
        assert calls[1]["temperature"] == 0.0, "the retry is at temp 0"
        assert calls[0]["temperature"] != 0.0, "the first attempt is not"
        await client.close()

    async def test_read_timeout_raises_transport_error(self, image_dir) -> None:
        """ASGITransport NEVER enforces client timeouts (the 1.1 lesson), so
        the timeout is pinned at the transport layer itself: a transport
        that raises httpx.ReadTimeout exactly as a socket timeout would."""

        class TimingOutTransport(httpx.AsyncBaseTransport):
            async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
                raise httpx.ReadTimeout("read timeout", request=request)

        settings = vc.get_settings().model_copy(update={"vlm_enforcement_probe_enabled": False})
        client = vc.VlmClient(
            base_url="http://fake-vlm:8098",
            transport=TimingOutTransport(),
            settings=settings,
        )
        with pytest.raises(vc.VlmTransportError):
            await client.assess(_request([str(image_dir / "front_door/a.jpg")]))
        await client.close()

    async def test_schema_invalid_completion_raises_schema_error(self, image_dir) -> None:
        """Server answers 200 with content that violates VlmVerdict (the
        schema-invalid fault class). Post-validation catches what the
        grammar supposedly guaranteed - raise, do not coerce (S5: nothing
        silently scored)."""
        client = make_client("schema-invalid", vlm_enforcement_probe_enabled=False)
        with pytest.raises(vc.VlmSchemaError):
            await client.assess(_request([str(image_dir / "front_door/a.jpg")]))
        assert len(client._app_calls()) == 2, "answered once + one retry, then raised"
        await client.close()


class TestBreakerAndDegradation:
    BREAKER: ClassVar = "ai-vlm"

    @pytest.fixture(autouse=True)
    def _clean_registries(self):
        from backend.services.circuit_breaker import reset_circuit_breaker_registry
        from backend.services.degradation_manager import reset_degradation_manager

        reset_circuit_breaker_registry()
        reset_degradation_manager()
        yield
        reset_circuit_breaker_registry()
        reset_degradation_manager()

    async def test_repeated_failures_open_the_breaker_and_push_degradation(self, image_dir) -> None:
        from backend.services.circuit_breaker import get_circuit_breaker
        from backend.services.degradation_manager import get_degradation_manager

        manager = get_degradation_manager()
        # register_service is SYNC and health_check is required (the breaker,
        # not a probe, carries ai-vlm health - spec §6 forbids health-probe-
        # as-wake on a sleeping llama.cpp, so this stub is never consulted
        # for truth; main.py's startup registration passes the same shape).
        manager.register_service(self.BREAKER, health_check=lambda: True)
        client = make_client("down", vlm_enforcement_probe_enabled=False)
        threshold = client._breaker.config.failure_threshold
        path = str(image_dir / "front_door/a.jpg")
        # One assess consumes TWO failures (the §6 retry is a second failed
        # request), so the breaker can OPEN mid-assess - later assessments
        # then raise VlmUnavailableError, and the loop stops at the edge.
        opened = False
        for _ in range(threshold):
            with pytest.raises((vc.VlmTransportError, vc.VlmUnavailableError)):
                await client.assess(_request([path]))
            if get_circuit_breaker(self.BREAKER).is_open:
                opened = True
                break
        assert opened, f"{threshold} threshold never tripped open"
        health = manager.get_service_health(self.BREAKER)
        assert health is not None and not health.is_healthy, "ai-vlm marked unhealthy"

        calls_before = len(client._app_calls())
        with pytest.raises(vc.VlmUnavailableError):
            await client.assess(_request([path]))
        assert len(client._app_calls()) == calls_before, "open breaker refuses WITHOUT I/O"
        await client.close()


class TestWake:
    async def test_wake_is_one_minimal_request_and_never_raises(self) -> None:
        app = make_fake_llama("strict")
        client = vc.VlmClient(
            base_url="http://fake-vlm:8098",
            transport=httpx.ASGITransport(app=app),
            settings=vc.get_settings(),
        )
        woke = await client.wake()
        assert woke is True
        body = app.state.calls[-1]
        assert body["max_tokens"] == 1, "spec §6: minimal REAL request, not a health probe"
        assert "response_format" not in body, "a wake must not pay grammar cost"
        await client.close()

    async def test_wake_records_the_cold_start(self, monkeypatch) -> None:
        """The plan names the metric: a wake IS a cold start, so it counts
        as one (the S4 latency budget is measured including cold starts -
        this counter is how the wake's effect on p95 becomes visible)."""
        recorded: list[str] = []
        monkeypatch.setattr(vc, "record_model_cold_start", lambda model: recorded.append(model))
        app = make_fake_llama("strict")
        client = vc.VlmClient(
            base_url="http://fake-vlm:8098",
            transport=httpx.ASGITransport(app=app),
            settings=vc.get_settings(),
        )
        assert await client.wake() is True
        await client.close()
        assert recorded == ["ai-vlm"]

    async def test_failed_wake_counts_no_cold_start(self, monkeypatch) -> None:
        """ "down" answers 503 - the request reached the socket, yet nothing
        loaded (llama.cpp refuses while still asleep; a proxy error page
        looks the same). A 200 is the only evidence of a load, so a wake
        that woke NOTHING counts NOTHING - honest accounting in both
        directions. A transport-level failure (server unreachable) takes
        the except path and records nothing by construction."""
        recorded: list[str] = []
        monkeypatch.setattr(vc, "record_model_cold_start", lambda model: recorded.append(model))
        client = make_client("down")
        assert await client.wake() is False
        await client.close()
        assert recorded == []

    async def test_wake_failure_swallowed(self) -> None:
        client = make_client("down")
        assert await client.wake() is False, "a failed wake must never crash batch ingest"
        await client.close()

    async def test_wake_ai_vlm_helper_is_throwaway_and_never_raises(self, monkeypatch) -> None:
        """The aggregator's fire-and-forget entry: a THROWAWAY client (its
        own instance, closed after the one request - the batch may be
        analyzed later by a different client), and a client whose
        CONSTRUCTION raises still cannot escape into the detached task."""
        made: list = []

        class _OkClient:
            def __init__(self) -> None:
                made.append(self)
                self.closed = False

            async def wake(self) -> bool:
                return True

            async def close(self) -> None:
                self.closed = True

        monkeypatch.setattr(vc, "VlmClient", _OkClient)
        assert await vc.wake_ai_vlm() is True
        assert made[0].closed is True, "the throwaway client was closed"

        class _BoomClient:
            def __init__(self) -> None:
                raise RuntimeError("settings exploded")

        monkeypatch.setattr(vc, "VlmClient", _BoomClient)
        assert await vc.wake_ai_vlm() is False, "construction failure swallowed too"

    def test_main_registers_ai_vlm_on_the_degradation_manager(self) -> None:
        """§6 step 4's health-endpoint half needs a REGISTERED name -
        update_service_health warns-and-drops an unregistered one, so the
        vlm_client's pushes would evaporate. Source pin (house precedent):
        main.py's lifespan registers ai-vlm on the singleton, and it is
        breaker-PUSH health, deliberately NOT a ServiceHealthMonitor probe
        (§6: a health probe may not wake a sleeping llama.cpp - polling
        would conflate sleep with failure)."""
        import inspect

        import backend.main

        src = inspect.getsource(backend.main)
        assert 'register_service(\n        "ai-vlm"' in src or 'register_service("ai-vlm"' in src
        # and NOT wired into the probe-poll monitor's config list:
        assert 'ServiceConfig(\n                name="ai-vlm"' not in src

    async def test_provider_registration_binds_the_real_callable_not_the_sentinel(self) -> None:
        """1.3's registry flip: OPENAI_VLM/RTVI_VLM carry the LIVE callable
        (the _not_wired sentinel said 'until vlm_client lands - 1.3')."""
        from backend.ai_contract.provider import registered_providers
        from backend.ai_contract.providers import ProviderId

        for pid in (ProviderId.OPENAI_VLM, ProviderId.RTVI_VLM):
            ops = registered_providers()[pid.value].operations()
            fn = ops["vlm_assess"]
            assert "_not_wired" not in fn.__qualname__, fn.__qualname__
            assert fn.__qualname__ == "VlmClient.assess"
            assert callable(fn)


class TestVerdictPostValidation:
    async def test_out_of_bounds_score_rejected_not_clamped(self, image_dir) -> None:
        """The client's contract is VlmVerdict (int 0-100, ge/le at the
        model). A grammar-bypassing answer is a schema error, NOT something
        to quietly fix - clamping is the analyzer's §6 invariant job, and
        it only applies to `rejected`."""
        garbage = FastAPI()

        @garbage.get("/props")
        async def props() -> dict:
            return {"build_info": _BUILD_INFO}

        @garbage.post("/v1/chat/completions")
        async def chat(request: Request) -> JSONResponse:
            await request.json()
            return JSONResponse(
                {"choices": [{"message": {"content": json.dumps(_full_verdict(risk_score=101))}}]}
            )

        settings = vc.get_settings().model_copy(update={"vlm_enforcement_probe_enabled": False})
        client = vc.VlmClient(
            base_url="http://fake-vlm:8098",
            transport=httpx.ASGITransport(app=garbage),
            settings=settings,
        )
        with pytest.raises((vc.VlmSchemaError, ValidationError)):
            await client.assess(_request([str(image_dir / "front_door/a.jpg")]))
        await client.close()


def _full_verdict(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "verdict": "confirmed",
        "risk_score": 50,
        "summary": "A person stands at the porch.",
        "reasoning": "Delivery posture, no tools, no concealment.",
        "description": "Porch, daytime, one adult with a box.",
        "criteria": [{"name": "coherent", "passed": True, "evidence": "box in hands"}],
        "provenance": {"engine": "llama.cpp " + _BUILD_INFO, "model_id": "Qwen3VL-4B"},
    }
    base.update(overrides)
    return base


class TestAssessHappyPathReturnsRealVerdict:
    async def test_valid_verdict_round_trips(self, image_dir) -> None:
        good = FastAPI()

        @good.get("/props")
        async def props() -> dict:
            return {"build_info": _BUILD_INFO}

        @good.post("/v1/chat/completions")
        async def chat(request: Request) -> JSONResponse:
            await request.json()
            return JSONResponse(
                {"choices": [{"message": {"content": json.dumps(_full_verdict())}}]}
            )

        settings = vc.get_settings().model_copy(update={"vlm_enforcement_probe_enabled": False})
        client = vc.VlmClient(
            base_url="http://fake-vlm:8098",
            transport=httpx.ASGITransport(app=good),
            settings=settings,
        )
        verdict = await client.assess(_request([str(image_dir / "front_door/a.jpg")]))
        assert verdict.verdict == "confirmed" and verdict.risk_score == 50
        await client.close()
