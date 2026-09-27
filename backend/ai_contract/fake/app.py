"""The FakeProvider FastAPI app (WP8.2).

One route per registry operation, mounted from the GENERATED registry itself
(method + path come from OPERATIONS, so a registry rename moves the fake's
surface with it - the fake cannot drift to a surface that no longer exists).
Responses come from generators.py: snapshot-walked where a WP7.2 snapshot
exists, literal-from-deployed-surface for the seven GEN_GAPS ops.

THE determinism mechanism, in one line: every response is
create_response_bytes(value generated from sha256(op_id | path | profile)) -
no wall-clock, no id(), no set iteration, no global counter. Two identical
requests are byte-identical because there is no channel for a difference to
enter.

Profiles (plan: "the divergence is the point; the fake must express both"):
the yolo-family vocabulary defaults to "gateway" - the DEPLOYED provider,
which is UNFILTERED (WP7.3 Tier A: adapters/yolo26.py returns all 80 COCO
names) - and a per-request X-Fake-Profile: security header switches to the
9 SECURITY_CLASSES the native server filters to. /fake/profiles/classes
exposes both tables as data (test fake-side vocabulary assertions need no
import of the fake's consts). The plan text's "81" is the 80-name table
plus the adapter's synthetic class_{id} fallback (adapters/yolo26.py:186) -
the fake mirrors the adapter exactly; recorded in the ledger.

This module is imported by the contract suite; importing it never imports
ai.* (package rule) and never touches network/GPU/weights.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import Awaitable, Callable
from functools import lru_cache
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import Response

from backend.ai_contract.fake.generators import (
    GATEWAY_CLASSES,
    SCHEMA_DIR,
    SECURITY_CLASSES,
    create_response_bytes,
    generate,
)
from backend.ai_contract.operations import OPERATIONS
from backend.ai_contract.provider import operations_for_slot

PROFILE_HEADER = "x-fake-profile"
# spec §7 ladder knobs (Phase 1.1): the failure-ladder tests (1.3) need the
# fake to FAIL three specific ways - timeout / schema-invalid / 5xx - not
# just succeed. Header-scoped per request, so the healthy path's byte-
# identity (module docstring) is untouched; an unknown value falls back to
# healthy, same doctrine as the profile header below.
FAULT_HEADER = "x-fake-fault"

_TABLE = {"security": tuple(sorted(SECURITY_CLASSES)), "gateway": GATEWAY_CLASSES}


def _response(obj: Any) -> Response:
    return Response(content=create_response_bytes(obj), media_type="application/json")


@lru_cache(maxsize=64)
def _response_property(op_id: str, kind: str) -> str | None:
    """The response schema's first required property - the schema-invalid
    fault mutates exactly one key so the body STILL parses as JSON but no
    longer validates (spec S5's unparseable-verdict branch; a 4xx would be
    a different ladder case, server refusal, not a 2xx the parser rejects)."""
    schema = json.loads((SCHEMA_DIR / f"{op_id}.{kind}.json").read_text(encoding="utf-8"))
    req = schema.get("required") or []
    return req[0] if req else None


def create_fake_app(profile: str = "gateway") -> FastAPI:
    """A fresh app instance. Two instances must replay identically (the
    suite asserts it) because nothing is seeded from process state."""
    app = FastAPI(title="WP8.2 FakeProvider", docs_url=None, redoc_url=None)

    @app.get("/fake/profiles/classes")
    async def _class_profiles() -> Response:
        # Vocabulary tables as DATA so the conformance suite (WP8.3) can
        # assert the 9-vs-80 divergence without importing the fake's consts.
        return _response({"security": list(_TABLE["security"]), "gateway": list(_TABLE["gateway"])})

    def _make_handler(op_id: str) -> Callable[[Request], Awaitable[Response]]:
        async def _handler(request: Request) -> Response:
            raw = await request.body()
            payload: Any = None
            if raw:
                # Body parsed ONLY for echo fields (model_name). The
                # deterministic core is seeded by op id, so ignoring upload
                # bytes cannot break byte-identity: same request in, same
                # bytes out, either way.
                try:
                    payload = json.loads(raw)
                except json.JSONDecodeError, UnicodeDecodeError:
                    payload = None
            prof = request.headers.get(PROFILE_HEADER, profile)
            prof = prof if prof in _TABLE else profile
            fault = request.headers.get(FAULT_HEADER)
            if fault == "5xx":
                raise HTTPException(status_code=503, detail="injected fault: 5xx")
            if fault is not None and fault.startswith("timeout"):
                # ':SECONDS' suffix keeps ladder tests fast; the DEFAULT
                # stall (2.0s) is well past any read timeout a client
                # plausibly sets on this route (ai_vlm read timeout is
                # 1.3's setting, ~0.5-2s class), so a bare header still
                # reproduces the timeout against a real socket. ASGITrans-
                # port never enforces client timeouts, so the in-process
                # observable is the stall itself, never a ReadTimeout.
                _, _, secs = fault.partition(":")
                try:
                    delay = float(secs) if secs else 2.0
                except ValueError:
                    delay = 2.0
                await asyncio.sleep(delay)
            value = generate(op_id, payload, prof)
            if fault == "schema-invalid":
                key = _response_property(op_id, "response")
                if key:
                    value[key] = None  # violates every root key (all minLength/enum/obj)
            return _response(value)

        _handler.__name__ = f"fake_{op_id}"
        return _handler

    for op_id, op in OPERATIONS.items():
        app.add_route(op.path, _make_handler(op_id), methods=[op.method])
    return app


# --- provider-contract callables (the WP8.1 Protocol side) ---------------
#
# fake_provider_ops() builds the uniform fn(payload) callables the plan
# assigns to the FakeProvider: each drives its own route through
# httpx.ASGITransport (in-process; no socket, no port, no respx - the fake
# IS the app). register_provider(ProviderId.FAKE, ...) runs the SAME
# signature conformance every live provider passes.


@lru_cache(maxsize=1)
def _get_shared_app() -> FastAPI:
    """One app for all provider callables (deterministic anyway — see
    create_fake_app; the cache is a speed affordance, not state)."""
    return create_fake_app()


def fake_provider_ops() -> dict[str, Any]:
    from httpx import ASGITransport, AsyncClient

    def _make(op_id: str) -> Callable[[Any], Awaitable[Any]]:
        async def _call(payload: Any = None) -> Any:
            op = OPERATIONS[op_id]
            transport = ASGITransport(app=_get_shared_app())
            async with AsyncClient(transport=transport, base_url="http://fake") as client:
                kwargs: dict[str, Any] = {}
                if op.method != "GET" and payload is not None:
                    kwargs["json"] = payload
                r = await client.request(op.method, op.path, **kwargs)
                r.raise_for_status()
                return r.json()

        _call.__name__ = f"fake_{op_id}"
        return _call

    return {op_id: _make(op_id) for op_id in operations_for_slot("fake", OPERATIONS)}
