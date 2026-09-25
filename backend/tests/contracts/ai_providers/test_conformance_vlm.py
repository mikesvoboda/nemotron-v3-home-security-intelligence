"""FakeProvider coverage for vlm_assess (spec §3 Slots, §7 conformance row).

The registry-derived tables already know the op (vlm_assess is declared in
VLM_OPS with fake:True), but derived tables prove DECLARATION, not SERVICE:
nobody had sent a request to the fake's vlm route yet. This file is that
request. No xfail/skip: the tier bans them (AGENTS.md here;
test_conformance_semantics.py's meta-guard).

The fault-injection class is spec §7's "FakeProvider fault injection
(timeout, schema-invalid, 5xx) -> circuit -> DEGRADED" — the ladder in 1.3
drives these knobs; 1.1 ships the knobs so the ladder tests a mechanism,
not a mock of a mechanism.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import jsonschema
import pytest
from backend.ai_contract.fake.app import create_fake_app
from backend.ai_contract.provider import registered_providers
from httpx import ASGITransport, AsyncClient

REPO_ROOT = Path(__file__).resolve().parents[4]
SCHEMA_DIR = REPO_ROOT / "backend/ai_contract/schemas"
GOLDEN_DIR = REPO_ROOT / "backend/tests/contracts/ai_providers/golden/payloads"


async def _post_vlm(app, body: dict, headers: dict[str, str] | None = None) -> tuple[int, dict]:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://fake") as client:
        r = await client.post("/vlm/chat/completions", json=body, headers=headers or {})
    return r.status_code, r.json()


def _golden_request() -> dict:
    return json.loads((GOLDEN_DIR / "vlm_assess.request.example.json").read_text())


class TestFakeVlmAssess:
    async def test_fake_answers_valid_verdict(self):
        """The golden request payload gets a 200 whose body validates against
        the GENERATED response schema - the E5 class of bug is a fake (or
        engine) answering 'a JSON-looking thing' that the parser then has to
        forgive. It may not."""
        app = create_fake_app()
        status, body = await _post_vlm(app, _golden_request())
        assert status == 200
        schema = json.loads((SCHEMA_DIR / "vlm_assess.response.json").read_text())
        jsonschema.validate(body, schema)  # raises on any shape violation

    async def test_verdict_is_keyed_on_the_image_paths(self):
        """spec §3: 'The FakeProvider returns a deterministic verdict keyed
        on an image hash.' Determinism is two-sided: the same image paths
        replay byte-identically, and different paths can surface a different
        verdict (a fake that ignores the images cannot pin ladder tests on
        verdict variety)."""
        app = create_fake_app()
        base = _golden_request()
        same_a = json.loads(json.dumps(base))
        flipped = json.loads(json.dumps(base))
        flipped["image_paths"] = ["/export/foscam/other/cam9/000001.jpg"]

        _, body_a1 = await _post_vlm(app, same_a)
        _, body_a2 = await _post_vlm(app, json.loads(json.dumps(base)))
        assert body_a1 == body_a2, "same images must replay identically"

        verdicts = {(await _post_vlm(app, flipped))[1]["verdict"] for _ in range(2)}
        assert len(verdicts) == 1, "flipped input must still be deterministic"
        # two distinct image sets must not be frozen to one verdict forever:
        # scan a small sweep and require at least one difference somewhere in
        # (verdict, risk_score) across varied paths
        seen = set()
        for i in range(12):
            variant = json.loads(json.dumps(base))
            variant["image_paths"] = [f"/export/foscam/cam{i % 3}/{i:06d}.jpg"]
            _, body = await _post_vlm(app, variant)
            seen.add((body["verdict"], body["risk_score"]))
        assert len(seen) > 1, "fake verdicts are constant across images - not keyed on them"

    @pytest.mark.parametrize("side", ["request", "response"])
    async def test_sides_have_object_roots(self, side: str):
        """Goldens emit only for object-rooted schemas (gen-ai-contract.py
        refuses array roots with empty/mixed shapes); §3 asks for BOTH sides
        to be golden'd, so both roots must be objects."""
        schema = json.loads((SCHEMA_DIR / f"vlm_assess.{side}.json").read_text())
        assert schema["type"] == "object"


class TestFakeVlmFaultInjection:
    """§7 ladder knobs: 1.3's failure-ladder unit tests need a fake that can
    FAIL three specific ways, not just succeed. Header-scoped and hermetic —
    the fault arrives per request, so it cannot pollute the byte-identity
    determinism the class above pins (same request WITHOUT the header is
    unchanged; asserted)."""

    async def test_fault_5xx(self):
        app = create_fake_app()
        status, body = await _post_vlm(app, _golden_request(), headers={"x-fake-fault": "5xx"})
        assert status == 503
        assert body["detail"] == "injected fault: 5xx"

    async def test_fault_schema_invalid_still_200_but_breaks_the_schema(self):
        """The schema-invalid fault MUST ride a 200: a 4xx would be the
        server refusing, which is a different ladder branch than a 2xx whose
        body the parser must reject (spec S5's unparseable-verdict case)."""
        app = create_fake_app()
        status, body = await _post_vlm(
            app, _golden_request(), headers={"x-fake-fault": "schema-invalid"}
        )
        assert status == 200
        schema = json.loads((SCHEMA_DIR / "vlm_assess.response.json").read_text())
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(body, schema)

    async def test_fault_timeout_stalls_the_response(self):
        """ASGITransport does not enforce httpx timeouts, so the timeout
        knob is an honest STALL (asyncio.sleep, caller-settable via a
        ':SECONDS' suffix) rather than a pretend ReadTimeout. Against a real
        socket, a stalled llama.cpp slot is precisely what trips
        vlm_client's own read timeout — the stall is the server-side half
        of that failure; the client-side half is 1.3's timeout wiring."""
        app = create_fake_app()
        body = _golden_request()
        start = time.perf_counter()
        status, _ = await _post_vlm(app, body, headers={"x-fake-fault": "timeout:0.15"})
        elapsed = time.perf_counter() - start
        assert status == 200  # the stall completes; the FAKE never dies
        assert elapsed >= 0.15, f"timeout fault did not stall: {elapsed:.3f}s"

    async def test_no_fault_header_is_unchanged(self):
        """The knobs are opt-in per request: the no-header path must still
        answer a schema-valid verdict (the determinism contract above
        extends to "a fault mechanism exists" being invisible when unused)."""
        app = create_fake_app()
        status, body = await _post_vlm(app, _golden_request())
        assert status == 200
        schema = json.loads((SCHEMA_DIR / "vlm_assess.response.json").read_text())
        jsonschema.validate(body, schema)

    async def test_unknown_fault_header_is_ignored(self):
        """Same doctrine as the profile header (app.py:82): an unknown value
        falls back to the healthy path rather than inventing behavior no
        ladder row asked for."""
        app = create_fake_app()
        status, _ = await _post_vlm(app, _golden_request(), headers={"x-fake-fault": "nonsense"})
        assert status == 200


class TestVlmProviderIds:
    """spec §3 Slots: OPENAI_VLM and RTVI_VLM minted, each registering with
    required={"vlm_assess"} - the subset pattern llamacpp-serve uses inside
    the union per_model_server column (MATRIX_SLOTS stays 4 keys; multiple
    ProviderIds share one column, exactly as LLAMACPP_LLM already does)."""

    @pytest.mark.parametrize("pid_name", ["OPENAI_VLM", "RTVI_VLM"])
    def test_registered_with_vlm_assess_subset(self, pid_name: str):
        from backend.ai_contract.provider import PROVIDER_SLOT, ProviderId

        pid = ProviderId[pid_name]
        assert PROVIDER_SLOT[pid] == "per_model_server"
        rec = registered_providers()[pid.value]
        assert set(rec.operations()) == {"vlm_assess"}
        # honest deployment state for 1.1: the compose service is 1.2 and
        # vlm_client is 1.3 - declared, not yet deployed.
        assert rec.deployed is False

    @pytest.mark.parametrize("pid_name", ["OPENAI_VLM", "RTVI_VLM"])
    async def test_not_wired_until_vlm_client_names_the_fake(self, pid_name: str):
        """1.1 registers these providers with the not-wired sentinel (no
        client bound yet); calling it must raise naming the FakeProvider -
        same device _bound_or_reject uses for kept-deployed ops. 1.3's
        vlm_client replaces this path."""
        from backend.ai_contract.provider import ProviderId

        rec = registered_providers()[ProviderId[pid_name].value]
        with pytest.raises(NotImplementedError, match="FakeProvider"):
            await rec.operations()["vlm_assess"]({})
