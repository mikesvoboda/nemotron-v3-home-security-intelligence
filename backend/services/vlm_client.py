"""vlm_client: the `vlm_assess` engine client (Phase 1.3, spec §2:101, §3).

The ONLY thing in the backend that dials the llama.cpp VLM server: a chat
request with up to 4 base64 image parts + structured context, wrapped by
the §3 enforcement probe, guarded by the circuit breaker, and mapped to
DegradationManager health (spec §6 step 4). The analyzer (vlm_analyzer)
consumes this; nobody else should.

Wire (the op's `evidence` records it; the registered PATH `/vlm/chat/
completions` is the fake's mount point - real engines speak
`POST /v1/chat/completions`):

  * `response_format: {"type":"json_schema","json_schema":{"name":...,
    "schema":...}}` - the NESTED wrapper the S-2 probe proved ENFORCED at
    b7972 (arm B echoed the const; arm C's malformed wrapper must not be
    sent at all, so the client always ships the well-formed shape);
  * the wire schema is the GENERATED contract schema with grammar-unsafe
    constraints stripped (`minLength`/`minimum`/`maximum` support at the
    pin is unverified - S-2's decision: grammar guarantees shape,
    VlmVerdict post-validation owns bounds, the spec's own 0.25 lesson);
  * timeouts: read budget `settings.ai_vlm_read_timeout` (default 25 s -
    S4's p95 <= 30 s includes cold starts, so the §6 retry at temp 0 must
    fit; a second attempt within budget only exists if the first one
    failed FAST).

Breaker semantics (spec §6 step 4): transport failures feed
`get_circuit_breaker("ai-vlm")`; when it OPENS, DegradationManager is
told ai-vlm is unhealthy (the machinery decision is ledgered - spec names
degradation_manager, and its status endpoint/system.py reader become real
once 1.3 registers the service at startup). A successful call clears the
unhealthy flag. `wake()` is the §6 cold-start ping: ONE minimal real
request (`max_tokens: 1`), never a health probe (health probes may not
wake a sleeping llama.cpp), and it never raises - a failed wake must not
crash batch ingest; the batch just proceeds without the warm head start.
"""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import mimetypes
from pathlib import Path
from typing import Any

import httpx
from pydantic import ValidationError

from backend.core.config import Settings, get_settings
from backend.core.metrics import record_model_cold_start, record_pipeline_error
from backend.services.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerConfig,
    get_circuit_breaker,
)
from backend.services.nemotron_analyzer import (
    ConstrainedDecodingNotEnforced,
    build_probe_schema,
)
from backend.services.vlm_verdict import VlmAssessRequest, VlmVerdict

# backend/ai_contract/schemas/vlm_assess.response.json - the same generated
# file the fake serves (fake/generators.py SCHEMA_DIR) and the golden payload
# pins. Derived by relative path, the house way for that directory.
_CONTRACT_SCHEMA_PATH = (
    Path(__file__).resolve().parents[1] / "ai_contract" / "schemas" / "vlm_assess.response.json"
)

logger = logging.getLogger(__name__)

BREAKER_NAME = "ai-vlm"

# llama.cpp's OpenAI-compat endpoint (spec §3: the engine wire).
CHAT_PATH = "/v1/chat/completions"
PROPS_PATH = "/props"

# The probe's budget: same S-2 lesson as _probe_completion's 400 - a budget
# that truncates mid-object FABRICATES an IGNORED verdict (the const can
# sort last in the grammar).
_PROBE_MAX_TOKENS = 400
# Real verdict budget: the verdict object plus a criterion or two.
_ASSESS_MAX_TOKENS = 700


class VlmClientError(RuntimeError):
    """Base for every client failure the analyzer maps into the ladder."""


class VlmTransportError(VlmClientError):
    """§6 step 1 territory: connection refused / timeout / 5xx. Retried
    once at temperature 0, then raised."""


class VlmSchemaError(VlmClientError):
    """§6 step 2 territory: the reply arrived but violates VlmVerdict even
    after the grammar supposedly guaranteed it (E5-class server-side lie or
    a truncated object). Post-validation is the last line (S5)."""


class VlmUnavailableError(VlmClientError):
    """Breaker OPEN: refuse fast, no I/O (house breaker contract,
    detector_client's DetectorUnavailableError pattern). Pushes
    DegradationManager UNHEALTHY on the way out."""


class VlmImageError(VlmClientError):
    """An image path the selector offered is unreadable or outside the
    capture root. Refused BEFORE any I/O: the paths come from a database
    row, and a poisoned row must not turn the backend into a reader of
    /etc. (Privacy rule, spec §6.)"""


def _strip_grammar_unsafe(node: Any) -> Any:
    """Drop the constraint keywords whose grammar-level support at the pin
    is unverified (S-2): the wire schema guarantees SHAPE only;
    VlmVerdict.model_validate re-checks bounds/minLength afterwards. A
    server that VALIDATES unsupported keywords would 400 the request; one
    that silently ignores them makes the probe useless - stripping keeps
    both failure modes off the table."""
    if isinstance(node, dict):
        return {
            k: _strip_grammar_unsafe(v)
            for k, v in node.items()
            if k not in {"minLength", "minimum", "maximum"}
        }
    if isinstance(node, list):
        return [_strip_grammar_unsafe(v) for v in node]
    return node


def _resolve_refs(node: Any, defs: dict[str, Any]) -> Any:
    """Inline every $ref. The GENERATED contract schema is pydantic-style
    ($defs + $ref); llama.cpp's json-schema->grammar converter at the pin is
    only [V]-proven on FLAT nested objects (S-2's arm B shape), so the
    client flattens refs -> literals and drops $defs. Contract stays the
    single source; this is transport shaping, not contract editing."""
    if isinstance(node, dict):
        ref = node.get("$ref")
        if isinstance(ref, str) and ref.startswith("#/$defs/"):
            return _resolve_refs(defs[ref.removeprefix("#/$defs/")], defs)
        return {k: _resolve_refs(v, defs) for k, v in node.items() if k != "$defs"}
    if isinstance(node, list):
        return [_resolve_refs(v, defs) for v in node]
    return node


class VlmClient:
    """One client per endpoint (the enforcement proof is per-endpoint AND
    per-build, S-2 - so the cache is per instance, never global).

    Args:
        settings: config source (defaults to the app singleton).
        transport: httpx transport seam; tests inject ASGITransport over a
            fake llama-server (hermetic, and the ONLY way a unit test can
            pin the timeout path - ASGITransport never enforces timeouts,
            so that test injects a raising transport instead).
        base_url: overrides settings.ai_vlm_url (tests, multi-endpoint use).
    """

    def __init__(
        self,
        settings: Settings | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
        base_url: str | None = None,
    ) -> None:
        self._settings = settings or get_settings()
        self._base_url = (base_url or self._settings.ai_vlm_url).rstrip("/")
        self._transport = transport
        self._client: httpx.AsyncClient | None = None
        # None = never probed / probe disabled; True = ENFORCED (the ONLY
        # cached verdict, S-1: a transient INCONCLUSIVE must not ossify).
        self._enforced: bool | None = None
        self._build_info: str = ""
        self._wire: dict[str, Any] | None = None
        self._probe_lock = asyncio.Lock()
        self._breaker: CircuitBreaker = get_circuit_breaker(
            BREAKER_NAME,
            CircuitBreakerConfig(failure_threshold=5, recovery_timeout=60.0),
        )

    async def _http(self) -> httpx.AsyncClient:
        if self._client is None:
            # default= covers write/pool: httpx requires all four or a default.
            timeout = httpx.Timeout(
                self._settings.ai_vlm_read_timeout,
                connect=self._settings.ai_connect_timeout,
            )
            self._client = httpx.AsyncClient(
                timeout=timeout, transport=self._transport, base_url=self._base_url
            )
        return self._client

    async def close(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    def _app_calls(self) -> list[dict[str, Any]]:
        """Chat request bodies the injected transport recorded, in order.
        A test seam only: a production transport records nothing, so this
        returns [] and no prod code reads it (the analyzer never does)."""
        return getattr(self._transport, "calls", [])

    # ------------------------------------------------------------------
    # §3 enforcement probe (the chat-shape half of the drift doctrine)
    # ------------------------------------------------------------------

    async def _probe_enforcement(self, image_parts: list[dict[str, Any]]) -> None:
        """Prove grammar enforcement ONCE on this endpoint+build, before any
        verdict is trusted. Same nonce-const contract as the /completion
        gate (build_probe_schema, shared with the CI CLI) but on the CHAT
        shape with an image part - S-2 exists because images and grammar
        are independent variables whose INTERSECTION the pin must prove.

        Raises ConstrainedDecodingNotEnforced (verdict "ignored"/
        "inconclusive") - the analyzer maps it to step 2 (verification_
        failed + NULL), the breaker records it as a failure.
        """
        if self._enforced is True or not self._settings.vlm_enforcement_probe_enabled:
            return
        async with self._probe_lock:
            if self._enforced is True:
                return

            # Build pin first (S-2: enforcement is per-build; a stale proof
            # must not launder onto an unknown build). /props is cheap.
            try:
                http = await self._http()
                props = await http.get(PROPS_PATH)
                self._build_info = (props.json() or {}).get("build_info", "")
            except Exception as exc:
                await self._note_failure("vlm_probe_props_unreachable")
                raise ConstrainedDecodingNotEnforced(
                    f"vlm /props unreachable ({exc}); cannot verify build before "
                    "trusting constrained decoding",
                    verdict="inconclusive",
                ) from exc
            required = self._settings.vlm_required_build
            if required and required not in self._build_info:
                await self._note_failure("vlm_probe_build_mismatch")
                raise ConstrainedDecodingNotEnforced(
                    f"endpoint build_info {self._build_info!r} lacks the pinned "
                    f"{required!r} - enforcement was proven against a different "
                    "build (S-2). Fail closed.",
                    verdict="inconclusive",
                )

            schema, nonce = build_probe_schema(self._wire_schema(), nonce=None)
            body = {
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            *image_parts[:1],
                            {
                                "type": "text",
                                "text": (
                                    "Emit the verdict object for the scene in the "
                                    "image above. Output JSON only.\n"
                                ),
                            },
                        ],
                    }
                ],
                "temperature": 0.0,
                "max_tokens": _PROBE_MAX_TOKENS,
                "response_format": {
                    "type": "json_schema",
                    "json_schema": {"name": "vlm_probe", "schema": schema},
                },
            }
            http = await self._http()
            try:
                resp = await http.post(CHAT_PATH, json=body)
            except Exception as exc:
                await self._note_failure("vlm_probe_transport")
                raise ConstrainedDecodingNotEnforced(
                    f"vlm probe transport failure ({exc})", verdict="inconclusive"
                ) from exc
            content = _content_of(resp) if resp.status_code == 200 else ""
            echoed = False
            try:
                echoed = json.loads(content).get("probe_const") == nonce
            except Exception:
                echoed = False
            if echoed:
                self._enforced = True
                logger.info(
                    "vlm enforcement probe: ENFORCED",
                    extra={"base_url": self._base_url, "build_info": self._build_info},
                )
                return
            await self._note_failure("vlm_probe_not_enforced")
            if resp.status_code == 200:
                # The E5-class lie, generalized to response_format: accepted
                # the parameter, did not enforce it. NEVER a silent prose mode.
                raise ConstrainedDecodingNotEnforced(
                    f"vlm endpoint accepted response_format.json_schema but the reply "
                    f"did not echo the probe const (build {self._build_info!r}) - "
                    "constrained decoding is not enforced here. Fail closed.",
                    verdict="ignored",
                )
            raise ConstrainedDecodingNotEnforced(
                f"vlm probe got HTTP {resp.status_code}; cannot measure enforcement",
                verdict="inconclusive",
            )

    def _wire_schema(self) -> dict[str, Any]:
        """The GENERATED response contract, $refs inlined and grammar-unsafe
        constraints stripped - one source (backend/ai_contract/schemas/, the
        same file the fake serves and the golden pins read), transport-shaped
        here, never hand-copied. Built once per client."""
        if self._wire is None:
            schema = json.loads(_CONTRACT_SCHEMA_PATH.read_text(encoding="utf-8"))
            defs = schema.get("$defs") or {}
            self._wire = _strip_grammar_unsafe(_resolve_refs(schema, defs))
        return self._wire

    # ------------------------------------------------------------------
    # Images (paths in, data URIs out; bytes NEVER leave this method)
    # ------------------------------------------------------------------

    def _image_parts(self, request: VlmAssessRequest) -> list[dict[str, Any]]:
        root = Path(self._settings.foscam_base_path).resolve()
        parts: list[dict[str, Any]] = []
        for raw in request.image_paths[:4]:
            path = Path(raw)
            try:
                resolved = path.resolve() if path.is_absolute() else (root / path).resolve()
            except OSError as exc:  # pragma: no cover - exotic FS errors
                raise VlmImageError(f"cannot resolve image path {raw!r}: {exc}") from exc
            if not resolved.is_relative_to(root):
                raise VlmImageError(
                    f"image path {raw!r} resolves outside the capture root {str(root)!r}; "
                    "refused before any read (privacy + traversal guard)"
                )
            if not resolved.is_file():
                raise VlmImageError(f"image file not found: {str(resolved)!r}")
            mime = mimetypes.guess_type(resolved.name)[0] or "image/jpeg"
            b64 = base64.b64encode(resolved.read_bytes()).decode()
            parts.append({"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}})
        return parts

    # ------------------------------------------------------------------
    # The call (§6 ladder lives HERE for transport, in the analyzer for verdicts)
    # ------------------------------------------------------------------

    def prompt_text(self, request: VlmAssessRequest) -> str:
        """The text half of the assess message. PUBLIC because the
        analyzer stores it verbatim as Event.llm_prompt (spec §4 event
        detail: images referenced by path, never embedded)."""
        ctx = request.context
        # Rev 6: outputs ride the snapshot (context) — the one carrier.
        specialist = json.dumps(ctx.specialist_outputs, ensure_ascii=False)
        return (
            "You are the verification expert. The detections below were produced "
            "by an object detector on the attached frame(s). Decide whether the "
            "detected candidate is REAL and CORRECTLY IDENTIFIED (verdict), and "
            "how threatening it is (risk_score 0-100). Answer ONLY with the "
            "verdict JSON object: verdict, risk_score, summary, reasoning, "
            "description, criteria (each name/passed/evidence), provenance "
            "(engine, model_id - copy the values from the served model's own "
            "reported identity).\n\n"
            f"Camera: {ctx.camera_id}\n"
            f"Time: {ctx.timestamp}\n"
            f"Zones: {', '.join(ctx.zones) or 'none'} (crossing: {ctx.zone_crossing})\n"
            f"Detections: {json.dumps(ctx.detections, ensure_ascii=False)}\n"
            f"Household context: {json.dumps(ctx.household, ensure_ascii=False)}\n"
            f"Specialist outputs (faces/plates/re-ID; these are detector evidence, "
            f"not yours to invent): {specialist}\n"
        )

    async def assess(self, request: VlmAssessRequest) -> VlmVerdict:
        """One VLM assessment of one batch. Raises VlmTransportError /
        VlmSchemaError / VlmUnavailableError / VlmImageError /
        ConstrainedDecodingNotEnforced; the analyzer owns the mapping to
        `verification_failed` (NULL score) - the client NEVER fabricates a
        verdict (S5: nothing is silently scored)."""
        # allow_call(), not is_closed(): it is the breaker's own gate that
        # lets HALF_OPEN recovery traffic through after the recovery window
        # (is_closed() alone would strand the client - nothing ever closes
        # HALF_OPEN if no call is allowed).
        if not await self._breaker.allow_call():
            record_pipeline_error("vlm_circuit_open")
            await self._push_unhealthy("circuit open")
            raise VlmUnavailableError(
                f"vlm breaker OPEN for {BREAKER_NAME}; refusing without I/O "
                f"(recovery in {self._breaker.config.recovery_timeout:.0f}s)"
            )
        parts = self._image_parts(request)
        await self._probe_enforcement(parts)

        body = {
            "messages": [
                {
                    "role": "user",
                    "content": [*parts, {"type": "text", "text": self.prompt_text(request)}],
                }
            ],
            "temperature": 0.1,
            "max_tokens": _ASSESS_MAX_TOKENS,
            "response_format": {
                "type": "json_schema",
                "json_schema": {"name": "vlm_verdict", "schema": self._wire_schema()},
            },
        }

        last_error: VlmClientError | None = None
        for attempt, temperature in enumerate((None, 0.0)):
            if temperature is not None:
                body["temperature"] = temperature  # §6 step 1: retry at temp 0
            try:
                http = await self._http()
                resp = await http.post(CHAT_PATH, json=body)
            except Exception as exc:
                last_error = VlmTransportError(f"vlm transport failure: {exc}")
                await self._note_failure("vlm_transport_error")
                logger.warning(
                    "vlm transport error (attempt %d)", attempt + 1, extra={"error": str(exc)}
                )
                continue
            if resp.status_code != 200:
                last_error = VlmTransportError(f"vlm HTTP {resp.status_code}: {resp.text[:200]}")
                await self._note_failure("vlm_http_error")
                continue
            content = _content_of(resp)
            try:
                verdict = VlmVerdict.model_validate_json(content)
            except ValidationError as exc:
                last_error = VlmSchemaError(f"vlm verdict failed validation: {exc}")
                await self._note_failure("vlm_schema_invalid")
                logger.warning("vlm schema violation (attempt %d)", attempt + 1)
                continue
            await self._breaker.record_success_async()
            await self._push_healthy()
            return verdict

        raise last_error if last_error else VlmClientError("vlm assess failed")

    # ------------------------------------------------------------------
    # Breaker/degradation wiring (spec §6 step 4; machinery choice ledgered)
    # ------------------------------------------------------------------

    async def _note_failure(self, reason: str) -> None:
        """Feed the breaker; if this failure OPENED it, push ai-vlm UNHEALTHY
        to DegradationManager once (the open transition is the edge worth
        announcing - per-failure pushes would thrash the status endpoint).

        Uses the breaker's async recorders so the state lock is held (the
        sync `record_failure` skips it and the otel/trace side effects the
        house clients rely on)."""
        await self._breaker.record_failure_async()
        record_pipeline_error(reason)
        if self._breaker.is_open:
            await self._push_unhealthy(reason)

    async def _push_unhealthy(self, reason: str) -> None:
        from backend.core.metrics import set_ai_service_degraded
        from backend.services.degradation_manager import get_degradation_manager

        await get_degradation_manager().update_service_health(
            BREAKER_NAME, is_healthy=False, error_message=reason
        )
        # §6 step 4's Prometheus alert hook (spec: "surfaced through the
        # health endpoint AND a Prometheus alert" - the singleton covers
        # the endpoint, this gauge is the alertable projection).
        set_ai_service_degraded(BREAKER_NAME, degraded=True)

    async def _push_healthy(self) -> None:
        """Clear the unhealthy flag only once the breaker is truly CLOSED
        (a HALF_OPEN trial success must not prematurely read healthy)."""
        if not self._breaker.is_closed:
            return
        from backend.core.metrics import set_ai_service_degraded
        from backend.services.degradation_manager import get_degradation_manager

        await get_degradation_manager().update_service_health(BREAKER_NAME, is_healthy=True)
        set_ai_service_degraded(BREAKER_NAME, degraded=False)

    # ------------------------------------------------------------------
    # §6 cold start: wake-on-open (the batch aggregator's fire-and-forget)
    # ------------------------------------------------------------------

    async def wake(self) -> bool:
        """`POST /v1/chat/completions` with `max_tokens: 1` - ONE minimal
        REAL request so llama.cpp loads its weights during the 30-90 s
        window (spec §6: health probes may not wake a sleeping server; the
        M1 run repeats the through-sleep proof on the A5500 [O]). Never
        raises: the caller is a detached task inside batch ingest."""
        try:
            http = await self._http()
            resp = await http.post(
                CHAT_PATH,
                json={
                    "messages": [{"role": "user", "content": "ping"}],
                    "max_tokens": 1,
                    "temperature": 0.0,
                },
                timeout=httpx.Timeout(
                    self._settings.ai_vlm_wake_timeout_seconds,
                    connect=self._settings.ai_connect_timeout,
                ),
            )
            woke: bool = resp.status_code == 200
            if woke:
                # A 200 is the ONLY evidence a load happened (or is in flight):
                # a 503 - llama.cpp refusing while still asleep, a proxy error
                # page - reached the socket but woke nothing, and counting it
                # would skew the S4 cold-start budget. The plan names this
                # metric for the wake, and a successful wake IS a cold start.
                record_model_cold_start(BREAKER_NAME)
            logger.debug("vlm wake", extra={"base_url": self._base_url, "woke": woke})
            return woke
        except Exception as exc:
            logger.debug("vlm wake failed (ignored by design)", extra={"error": str(exc)})
            return False


async def wake_ai_vlm() -> bool:
    """The batch aggregator's fire-and-forget wake (spec §6 cold start). A
    THROWAWAY client - one request, then gone; the batch that opened may be
    analyzed by a different client instance minutes later, and a warm engine
    serves whoever asks. Never raises: its caller is a detached task inside
    batch ingest, where a traceback would be pure noise (wake() already
    swallows; this belt catches the client-construction path too)."""
    try:
        client = VlmClient()
        try:
            return await client.wake()
        finally:
            await client.close()
    except Exception as exc:
        logger.debug("ai-vlm wake task failed (ignored by design)", extra={"error": str(exc)})
        return False


def _content_of(resp: httpx.Response) -> str:
    if resp.status_code != 200:
        return ""
    try:
        return resp.json()["choices"][0]["message"]["content"] or ""
    except Exception:
        return ""
