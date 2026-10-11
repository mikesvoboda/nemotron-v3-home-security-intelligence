"""The FakeProvider FastAPI app (WP8.2).

One route per registry operation, mounted from the GENERATED registry itself
(method + path come from OPERATIONS, so a registry rename moves the fake's
surface with it - the fake cannot drift to a surface that no longer exists).
Responses come from generators.py: snapshot-walked where a WP7.2 snapshot
exists, literal-from-deployed-surface for the GEN_GAPS ops (the yolo family;
R8 S3 pruned the four enrichment-server members with their ops).

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

The ENGINE half (O2.1): the backend's VlmClient never dials the contract
path /vlm/chat/completions; it speaks llama.cpp's wire, GET /props for the
pinned build and POST /v1/chat/completions with a response_format
json_schema. A constrained chat on that path is answered the way an
enforcing grammar answers it: a verdict that validates against the schema
the request carried, every top-level `const` echoed (the startup probe's nonce,
constrained_decoding.build_probe_schema), wrapped in the chat envelope. An
unconstrained chat there (the batch-open wake call) is still the llm op.
GET /health and GET /yolo26/health answer the pollers. The verdict, and the
detector's detections, come from the scenario book (scenarios.py) when the
received image is a scenario's, else from the generators seeded by the
image's sha256 - spec §3's "deterministic verdict keyed on an image hash".

This module is imported by the contract suite; importing it never imports
ai.* (package rule) and never touches network/GPU/weights.
"""

from __future__ import annotations

import asyncio
import base64
import binascii
import hashlib
import json
import os
from collections.abc import Awaitable, Callable
from functools import lru_cache
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import Response
from starlette.exceptions import HTTPException as StarletteHTTPException

from backend.ai_contract.fake.generators import (
    GATEWAY_CLASSES,
    SCHEMA_DIR,
    SECURITY_CLASSES,
    create_response_bytes,
    generate,
    validate,
)
from backend.ai_contract.fake.scenarios import ScenarioBook
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

# The engine identity /props reports. The container takes its build from
# FAKE_VLM_BUILD_INFO (docker-compose.fake-ai.yml derives it from the same
# VLM_REQUIRED_BUILD the backend pins), so the backend's build check runs
# against the fake rather than being skipped.
BUILD_INFO_ENV = "FAKE_VLM_BUILD_INFO"
DEFAULT_BUILD_INFO = "fake-ai"
MODEL_PATH = "/models/fake-ai-vlm.gguf"


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


def _images_of(payload: dict[str, Any]) -> list[bytes]:
    """The image bytes a chat request carries as data-URI parts, in order."""
    images: list[bytes] = []
    for message in payload.get("messages") or []:
        content = message.get("content") if isinstance(message, dict) else None
        for part in content if isinstance(content, list) else []:
            url = ((part or {}).get("image_url") or {}).get("url", "")
            if isinstance(url, str) and url.startswith("data:") and ";base64," in url:
                try:
                    images.append(base64.b64decode(url.split(";base64,", 1)[1], validate=True))
                except binascii.Error, ValueError:
                    continue
    return images


def _constrained_schema(payload: Any) -> dict[str, Any] | None:
    """The json_schema a chat request constrains its reply to, if any."""
    if not isinstance(payload, dict):
        return None
    response_format = payload.get("response_format")
    if not isinstance(response_format, dict) or response_format.get("type") != "json_schema":
        return None
    schema = (response_format.get("json_schema") or {}).get("schema")
    return schema if isinstance(schema, dict) else None


def _has_const(schema: dict[str, Any]) -> bool:
    return any(
        isinstance(node, dict) and "const" in node
        for node in (schema.get("properties") or {}).values()
    )


def _fill(schema: dict[str, Any], verdict: dict[str, Any]) -> dict[str, Any]:
    """The object an enforcing grammar emits: the schema's top-level
    properties, each `const` echoed, the rest taken from the verdict. Top
    level is all the probe uses (build_probe_schema adds one property)."""
    out: dict[str, Any] = {}
    for name, node in (schema.get("properties") or {}).items():
        if isinstance(node, dict) and "const" in node:
            out[name] = node["const"]
        elif name in verdict:
            out[name] = verdict[name]
    return out


def create_fake_app(
    profile: str = "gateway",
    *,
    scenarios: ScenarioBook | None = None,
    build_info: str = DEFAULT_BUILD_INFO,
) -> FastAPI:
    """A fresh app instance. Two instances must replay identically (the
    suite asserts it) because nothing is seeded from process state.

    `scenarios` defaults to the committed book; `build_info` is what /props
    reports as the serving build."""
    app = FastAPI(title="WP8.2 FakeProvider", docs_url=None, redoc_url=None)
    book = scenarios if scenarios is not None else ScenarioBook.load()
    provenance = {"engine": build_info, "model_id": MODEL_PATH.rsplit("/", 1)[-1][: -len(".gguf")]}

    @app.get("/fake/profiles/classes")
    async def _class_profiles() -> Response:
        # Vocabulary tables as DATA so the conformance suite (WP8.3) can
        # assert the 9-vs-80 divergence without importing the fake's consts.
        return _response({"security": list(_TABLE["security"]), "gateway": list(_TABLE["gateway"])})

    # --- the engine and gateway health surface the backend polls (O2.1) ---

    @app.get("/health")
    async def _health() -> Response:
        # llama-server answers 200 {"status":"ok"} once loaded; the gateway's
        # aggregate /health answers 200 too. The backend reads the status code.
        return _response({"status": "ok"})

    @app.get("/yolo26/health")
    async def _yolo26_health() -> Response:
        # The gateway adapter's own shape (ai/gateway/adapters/yolo26.py).
        return _response({"status": "healthy", "model": "fake-ai-yolo26", "model_loaded": True})

    @app.get("/props")
    async def _props() -> Response:
        # llama-server's /props: the backend's build pin reads build_info and
        # its provenance reads the model file's stem (vlm_client.py).
        return _response({"build_info": build_info, "model_path": MODEL_PATH})

    async def _engine_chat(
        payload: dict[str, Any], schema: dict[str, Any], prof: str, fault: str | None
    ) -> Response:
        images = _images_of(payload)
        scenario = next((s for s in map(book.for_image, images) if s is not None), None)
        if scenario is not None:
            # The slow-reply mode delays the VERDICT reply. A probe (a schema
            # carrying a const nonce, constrained_decoding.build_probe_schema)
            # rides the batch's first image too and is never delayed, so the
            # gate passes and the slow leg is the assess the mode exists for.
            if scenario.reply_delay_seconds and not _has_const(schema):
                await asyncio.sleep(scenario.reply_delay_seconds)
            verdict = dict(scenario.verdict)
        else:
            # spec §3: a deterministic verdict keyed on an image hash. The
            # generator's vlm override seeds on its image keys; digests are
            # the keys the engine wire has.
            keys = [f"sha256:{hashlib.sha256(image).hexdigest()}" for image in images]
            verdict = generate("vlm_assess", {"image_paths": keys} if keys else None, prof)
        verdict["provenance"] = dict(provenance)
        content = _fill(schema, verdict)
        import jsonschema

        try:
            jsonschema.validate(content, schema)
        except jsonschema.ValidationError as exc:
            # A grammar would never emit this; the fake says so loudly.
            raise HTTPException(
                status_code=500, detail=f"fake cannot satisfy the requested schema: {exc.message}"
            ) from exc
        if fault == "schema-invalid":
            # The same ladder knob as the registry ops: a reply that still
            # parses as JSON but no longer validates (here, against the schema
            # the request carried).
            required = schema.get("required") or []
            if required:
                content[required[0]] = None
        return _response(
            {
                "id": "chatcmpl-fake-ai",
                "object": "chat.completion",
                "created": 0,
                "model": provenance["model_id"],
                "choices": [
                    {
                        "index": 0,
                        "message": {
                            "role": "assistant",
                            "content": create_response_bytes(content).decode(),
                        },
                        "finish_reason": "stop",
                    }
                ],
                "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
            }
        )

    async def _scenario_detect(request: Request, prof: str) -> dict[str, Any] | None:
        """The detector's multipart upload, answered from the book when the
        uploaded file is a scenario's image. Anything else, an upload that
        does not parse included, keeps the literal script (None)."""
        if not request.headers.get("content-type", "").startswith("multipart/form-data"):
            return None
        try:
            upload = (await request.form()).get("file")
        except StarletteHTTPException, ValueError:
            # Starlette answers a missing boundary with a 400 and
            # python-multipart's parse errors are ValueErrors; the fake
            # answered both with the literal script before scenarios existed.
            return None
        if upload is None or isinstance(upload, str):
            return None
        scenario = book.for_image(await upload.read())
        if scenario is None:
            return None
        value: dict[str, Any] = generate("yolo26_detect", None, prof)
        value.update(
            detections=list(scenario.detections),
            image_width=scenario.width,
            image_height=scenario.height,
        )
        validate("yolo26_detect", value)  # the book cannot step outside the contract
        return value

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
            if op_id == "llm_chat_completion":
                schema = _constrained_schema(payload)
                if schema is not None:
                    return await _engine_chat(payload, schema, prof, fault)
            value = await _scenario_detect(request, prof) if op_id == "yolo26_detect" else None
            if value is None:
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


def create_served_app() -> FastAPI:
    """The container's app (``uvicorn --factory``,
    docker/fake-ai/Dockerfile): the committed scenario book, and the build
    the compose overlay names in FAKE_VLM_BUILD_INFO."""
    return create_fake_app(build_info=os.environ.get(BUILD_INFO_ENV) or DEFAULT_BUILD_INFO)


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
