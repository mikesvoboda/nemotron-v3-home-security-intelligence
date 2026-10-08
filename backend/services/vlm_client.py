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
  * timeouts: read budget `settings.ai_vlm_read_timeout` (default 25 s,
    applied PER ATTEMPT against S4's p95 <= 30 s including cold starts). Two
    full attempts would blow the spec, so a read timeout is NOT retried - see
    `VlmSlowReplyError` - and the §6 retry at temp 0 only ever follows a FAST
    failure (a connection refused, a 5xx). Worst case on the timeout path is
    therefore ONE 25 s wait and no retry, inside the 30 s; the budget is
    counted as a cause and never charged to the breaker).

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
import math
from pathlib import Path
from typing import Any, TypeGuard

import httpx
from PIL import Image
from pydantic import ValidationError

from backend.core.config import Settings, get_settings
from backend.core.metrics import (
    record_model_cold_start,
    record_pipeline_error,
    record_prompt_truncated,
)
from backend.core.mime_types import IMAGE_MIME_TYPES, VIDEO_MIME_TYPES
from backend.services.capture_time import render_prompt_time
from backend.services.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerConfig,
    get_circuit_breaker,
)
from backend.services.constrained_decoding import (  # R8 S2a: hoisted home
    ConstrainedDecodingNotEnforced,
    _is_length_truncated,
    build_probe_schema,
)
from backend.services.key_frame_selector import MAX_KEY_FRAMES
from backend.services.token_counter import get_token_counter
from backend.services.vlm_verdict import VlmAssessRequest, VlmProvenance, VlmVerdict

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

# Real verdict budget: the verdict object plus a criterion per row and frame.
# 700 cut off the shipped 8B's longest verdict (852 tokens, a two-image item;
# A5500 2026-09-28) - a truncated reply is S5-unparseable, and S5's bar is 0.
# Raised 1024 -> 2048 on 2026-10-04: across the 15-arm sweep's 9,462 stored replies
# (eval store, tierb-v0) p99 was ~917 tokens but 0.47% exceeded 1024 - those events
# degraded to verification_failed silently, and prompt work that invites longer
# justification (a risk rubric) widened the tail until truncation became the
# dominant failure in probes. 2048 keeps >=1.2x headroom over the measured 852; the
# slot (16,384) fits 4 images + prompt + reply at this cap (see _fitted_prompt's
# reservation).
#
# What this cap costs in TIME (D1 - the note here before B1.1 claimed "worst-case
# ~70s ... inside the 180s read timeout", and neither figure described this path):
#   * throughput ~57 tok/s. No throughput is committed anywhere: the sweep that the
#     figure is credited to ran at max_tokens 1024 and overrode the read timeout to
#     180 s (`docs/benchmarks/synthbench/sweep-2026-10-03/driver/replay_arm.py:18`),
#     so it measured neither this cap nor this timeout. 57 comes from 00-audit D1
#     and from the commit that raised this cap (26b900bc). The tool that turns it
#     into a measured number is committed: `scripts/vlm_probes/latency_tail.py`
#     drives THIS client at $VLM_URL and reports the engine's own tok/s, the
#     latency p95 and the reply tail (its header carries the operator commands).
#   * 2048 tok / 57 tok/s ~= 36 s for ONE attempt. The old 70 s is 2 x 36 - the
#     whole §6 ladder - set against a timeout that applies per attempt.
#   * the shipped timeout is 25 s (`config.py:1130`, compose `:551`, `.env.example:241`),
#     so a reply longer than 25 s * 57 tok/s ~= 1,425 tokens does not finish: THAT is
#     the ~1,400-token wall 00-audit D1 measured, and it is a BUDGET, handled as one
#     (see `VlmSlowReplyError`), not as a broken engine.
#   * the budget S4 asks us to protect is p95 <= 30 s including cold starts. The
#     shipped model's committed latency is far inside it - median 2.0 s, p95 2.7 s,
#     max 7.4 s (`sweep-2026-10-03/arms.csv`, control-q4km, at 1,024 tokens, GB300,
#     indicative only and not an S4 reading, per report.md) - so 25 s is ~9x the
#     measured p95 and nothing in the sweep came near timing out. The timeout is
#     therefore NOT the thing that keeps S4; it is the guard against an engine that
#     has stopped answering at all, and it must not be paid for with a breaker.
# So the cap is not reduced for arithmetic's sake: cutting it under ~1,425 to make
# the old claim true would re-create the truncation this cap exists to prevent, and
# a truncated reply is worse than a slow one - it FABRICATES a verdict field.
_ASSESS_MAX_TOKENS = 2048
# The probe's budget: a budget that truncates mid-object FABRICATES an IGNORED
# verdict (the const can sort last in the grammar), so the probe object - the
# verdict object plus one const - must get MORE room than a verdict does. The
# old fixed 400 was below the shipped 8B's 427-429-token probe reply (A5500,
# 2026-09-28): every probe went INCONCLUSIVE and every verdict failed closed.
_PROBE_MAX_TOKENS = _ASSESS_MAX_TOKENS + 64
# Sampling temperature of the assess call: greedy. At the former 0.1 (unseeded) only
# 278/450 corpus items returned the same verdict and score across two identical runs
# (36% changed score, 52 changed risk level), so an event near the medium threshold could
# alert on one pass and not on the next. At 0 two identical runs agreed on 450/450 with the
# same S2/S3 (GB300 replays, 2026-10-03), so the temperature added noise, not accuracy.
_ASSESS_TEMPERATURE = 0.0

# Upper bound for the IMAGE half of one slot, from the same arithmetic that
# sized the slot (spec §2, echoed in the ai-vlm compose block's comment):
# Qwen3-VL encodes one still at <= ~1280 vision tokens, and the selector
# never offers more than MAX_KEY_FRAMES of them. It is a reservation, not a
# measurement - the client never decodes a JPEG to count its tokens - so it
# is deliberately the ceiling of the range, and it makes the budget check
# conservative in the direction that matters (a prompt approved here cannot
# overflow the slot on account of its images).
_IMAGE_TOKENS_PER_FRAME = 1280

# The fit counts text with the repo's counter, but the SLOT is filled by the
# served tokenizer - and Qwen splits every digit, while detection rows are
# mostly digits. Measured on one fitted prompt (A5500, 2026-09-28): 10,237 by
# the counter, 13,785 by the engine's /tokenize (1.35x). The fit budgets each
# counted token at this many served ones; deterministic, so the stored prompt
# is still the sent prompt (a /tokenize call could not promise that).
_SERVED_TOKENS_PER_COUNTED = 1.5


class VlmClientError(RuntimeError):
    """Base for every client failure the analyzer maps into the ladder."""


class VlmTransportError(VlmClientError):
    """§6 step 1 territory: connection refused / timeout / 5xx. Retried
    once at temperature 0, then raised."""


class VlmSchemaError(VlmClientError):
    """§6 step 2 territory: the reply arrived COMPLETE but violates
    VlmVerdict even after the grammar supposedly guaranteed it (the E5-class
    server-side lie). Post-validation is the last line (S5). A reply cut off
    by its token budget is NOT this class - see VlmTruncatedError."""


class VlmTruncatedError(VlmSchemaError):
    """Finding A's sibling on the assess leg: the engine stopped with a
    length signal mid-object, so the JSON never closed. Subclassed under
    VlmSchemaError so every existing `except VlmSchemaError` keeps mapping to
    verification_failed (the ladder is neutral - a truncation has never
    scored), but named apart because the CAUSE and the retry calculus differ:
    a budget is not a model that emits invalid JSON, and the §6 retry asks
    again at the SAME max_tokens, so re-asking cannot close the object."""


class VlmContextOverflowError(VlmClientError):
    """The served slot refused the request as larger than its context (HTTP
    400 `exceed_context_size_error`): OUR fit under-estimated it, the engine
    is fine. Named apart from VlmTransportError because the retry calculus
    differs - the §6 retry would re-send the same bytes for the same 400 -
    and because a budget must not feed the service breaker. Still a
    VlmClientError, so the analyzer still answers verification_failed."""


class VlmSlowReplyError(VlmClientError):
    """D1: the engine took longer than `ai_vlm_read_timeout` to answer
    (httpx.ReadTimeout - the connection was accepted, the request written;
    a refusal would have been ConnectTimeout and stays a transport error).
    OUR read budget cut a live request, so this is a budget outcome like
    VlmContextOverflowError: named apart from VlmTransportError because the
    retry calculus differs (the request leaves unchanged, so the §6 retry
    re-asks the identical question at the identical speed and times out
    identically, charging the breaker a second time for nothing) and because
    a budget must not feed the service breaker. Still a VlmClientError, so
    the analyzer still answers verification_failed with a NULL score."""


class VlmUnavailableError(VlmClientError):
    """Breaker OPEN: refuse fast, no I/O (house breaker contract,
    detector_client's DetectorUnavailableError pattern). Pushes
    DegradationManager UNHEALTHY on the way out."""


class VlmImageError(VlmClientError):
    """An image path the selector offered is unreadable or outside the
    capture root. Refused BEFORE any I/O: the paths come from a database
    row, and a poisoned row must not turn the backend into a reader of
    /etc. (Privacy rule, spec §6.)"""


def _context_overflow_of(resp: httpx.Response) -> dict[str, Any] | None:
    """llama-server's own over-context refusal (HTTP 400, error.type
    `exceed_context_size_error`, with n_prompt_tokens / n_ctx), else None.
    Keyed on the structured type, never the message prose."""
    if resp.status_code != 400:
        return None
    try:
        error = resp.json().get("error")
    except ValueError:
        return None
    if isinstance(error, dict) and error.get("type") == "exceed_context_size_error":
        return {k: error.get(k) for k in ("n_prompt_tokens", "n_ctx")}
    return None


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
        # The served model's own identity (/props model_path stem), read with
        # the build pin; "" until the probe has read /props.
        self._served_model_id: str = ""
        self._wire: dict[str, Any] | None = None
        self._probe_lock = asyncio.Lock()
        self._breaker: CircuitBreaker = get_circuit_breaker(
            BREAKER_NAME,
            CircuitBreakerConfig(failure_threshold=5, recovery_timeout=60.0),
        )

    def _served_provenance(self) -> VlmProvenance:
        """Who answered, as the CLIENT knows it - never the model's copy. The
        verdict schema makes the model emit provenance, but it cannot know its
        own identity and the grammar forces it to write something (the A5500
        M1 chain stored the camera id as engine and model_id). The engine is
        the configured label plus the /props build string when read; the
        model id is the served file's stem, else the configured VLM_MODEL_ID."""
        label = self._settings.nemotron_verification_engine
        return VlmProvenance(
            engine=f"{label}@{self._build_info}" if self._build_info else label,
            model_id=self._served_model_id or self._settings.vlm_model_id,
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
                payload = props.json() or {}
                self._build_info = payload.get("build_info", "")
                self._served_model_id = Path(payload.get("model_path") or "").stem
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
            except httpx.ReadTimeout as exc:
                # D1 on the probe leg, which is the leg that actually bites in
                # production: the probe is enabled by default and its result
                # is cached once per endpoint+build, so a slow engine that has
                # already proven ENFORCED never reaches this branch - but an
                # engine that has NOT yet proven it does, once per item, and
                # the branch below charged the breaker for each. A timeout here
                # is the same budget outcome as the assess leg's: raise
                # INCONCLUSIVE (fail closed, nothing cached, no verdict
                # trusted), count it under its own cause, and do NOT feed the
                # service breaker for a number we chose.
                await self._note_budget_exhausted("vlm_probe_timeout")
                logger.warning(
                    "vlm probe reply exceeded the read budget",
                    extra={
                        "ai_vlm_read_timeout": self._settings.ai_vlm_read_timeout,
                        "max_tokens": _PROBE_MAX_TOKENS,
                    },
                )
                raise ConstrainedDecodingNotEnforced(
                    f"vlm probe reply exceeded the "
                    f"{self._settings.ai_vlm_read_timeout:.0f}s read budget at "
                    f"max_tokens={_PROBE_MAX_TOKENS} - enforcement is UNMEASURED "
                    "at this timeout, not absent. Fail closed.",
                    verdict="inconclusive",
                ) from exc
            except Exception as exc:
                await self._note_failure("vlm_probe_transport")
                raise ConstrainedDecodingNotEnforced(
                    f"vlm probe transport failure ({exc})", verdict="inconclusive"
                ) from exc
            content = _content_of(resp) if resp.status_code == 200 else ""
            stop = _stop_reason_of(resp)
            echoed = False
            try:
                echoed = json.loads(content).get("probe_const") == nonce
            except Exception:
                echoed = False
            if echoed:
                # The grammar produced a value the prompt never contained - a
                # stop reason cannot argue with that. Finding A's
                # `truncated_with_const` case must not lose a real ENFORCED.
                self._enforced = True
                logger.info(
                    "vlm enforcement probe: ENFORCED",
                    extra={"base_url": self._base_url, "build_info": self._build_info},
                )
                return
            if resp.status_code == 200 and _is_length_truncated(stop):
                # FINDING A. The reply hit its token budget, so the const may
                # simply never have been emitted - and `probe_const` can
                # legally sort LAST in the grammar. That is "could not
                # measure", NOT "measured: the server ignores the grammar",
                # and the difference decides an M2 pick. Measured on this
                # shipped shape (wire schema + const, candidate A): at 400
                # `loitering`/`pet_activity`/`prowling` never echo, `break_in_
                # attempt` echoes 3/4 - the SAME request, temp 0 - and the two
                # stable scenes clear at 400 (ledger findings A and G [V]).
                # Fail-closed is unchanged - still a raise, still nothing
                # cached, still no score. Only the WORD changes, and it changes
                # toward honesty.
                await self._note_budget_exhausted("vlm_probe_truncated")
                raise ConstrainedDecodingNotEnforced(
                    f"vlm probe reply hit its token budget (stop={stop!r}, "
                    f"max_tokens={_PROBE_MAX_TOKENS}) before the const could "
                    "be read - enforcement is UNMEASURED at this budget, not "
                    "absent. Fail closed.",
                    verdict="inconclusive",
                )
            await self._note_failure("vlm_probe_not_enforced")
            if resp.status_code == 200:
                # The E5-class lie, generalized to response_format: accepted
                # the parameter, answered completely, and did not enforce it.
                # A COMPLETE reply without the const is the evidence itself -
                # never forgiven by finding A's triage.
                raise ConstrainedDecodingNotEnforced(
                    f"vlm endpoint accepted response_format.json_schema but the reply "
                    f"did not echo the probe const (build {self._build_info!r}, "
                    f"stop={stop!r}) - constrained decoding is not enforced "
                    "here. Fail closed.",
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
        """The request's stills as data-URI parts (read AFTER three guards).

        Every path here came from a database row, so each one is checked
        before it is opened: inside the capture root (privacy/traversal),
        a still by TYPE, and small enough by BYTES. All three refuse by
        raising `VlmImageError`, which the analyzer already maps to
        `verification_failed` with a NULL score - the honest degradation,
        never a score computed from something the model could not see.
        """
        root = Path(self._settings.foscam_base_path).resolve()
        limit = self._settings.vlm_max_image_bytes
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
            # BY TYPE, an allowlist (the repo's own IMAGE_MIME_TYPES - the set
            # the capture path writes and the rest of the service accepts). An
            # extension IS the type here: `_video` below.
            suffix = resolved.suffix.lower()
            if suffix not in IMAGE_MIME_TYPES:
                # `guess_type(...) or "image/jpeg"` used to sit here, which
                # called a .mp4 "image/jpeg" and embedded it. A video batch
                # reaches this path by design - detector_client:1174 stores the
                # CLIP as `file_path` on every row of a video frame - so this
                # is the shipped path's known gap: the vlm route has no frame
                # extractor (ffmpeg is not in the backend image, and the
                # detector's extracted JPEGs are deleted at
                # pipeline_workers:746). Refusing loudly beats the two silent
                # losses: a container-base64 that overflows the llama.cpp slot
                # (which the breaker then reports as a MODEL outage, exactly
                # the 1.2 misdiagnosis shape) or an engine "verifying" bytes no
                # image decoder ever read. Naming the file and the cause keeps
                # it findable instead of looking like a VLM that is down.
                kind = VIDEO_MIME_TYPES.get(suffix)
                what = f"a {kind} container" if kind else f"type {suffix or '(none)'!r}"
                raise VlmImageError(
                    f"key frame {resolved.name!r} is {what}, not a still the vlm "
                    "path can embed; a video batch needs frame extraction before "
                    "vlm_assess (see _image_parts in this module)"
                )
            # BY BYTES, before the read (base64 inflates ~4/3 and the prompt
            # shares one slot with the verdict's output).
            size = resolved.stat().st_size
            if size > limit:
                raise VlmImageError(
                    f"key frame {resolved.name!r} is {size} bytes, over the "
                    f"vlm_max_image_bytes limit of {limit}; refused rather than "
                    "risking a context-slot overflow"
                )
            b64 = base64.b64encode(resolved.read_bytes()).decode()
            mime = IMAGE_MIME_TYPES[suffix]
            parts.append({"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}})
        return parts

    # ------------------------------------------------------------------
    # The call (§6 ladder lives HERE for transport, in the analyzer for verdicts)
    # ------------------------------------------------------------------

    def _image_token_reservation(self, request: VlmAssessRequest) -> int:
        """Tokens the attached stills will occupy - the ceiling, not a guess.

        The client never decodes a JPEG to count its vision tokens (and
        cannot: the encoder runs server-side), so the budget reserves the
        documented per-frame maximum for however many stills the selector
        offered. Sized from the same arithmetic that sized the slot
        (spec §2: Qwen3-VL encodes a still at <= ~1280 tokens). The cap is
        the SELECTOR's own constant, not a restated number: if the shipped
        budget ever allows 6 stills, the reservation has to grow with it."""
        return _IMAGE_TOKENS_PER_FRAME * min(len(request.image_paths), MAX_KEY_FRAMES)

    def _render_prompt(self, rows: list[dict[str, Any]], request: VlmAssessRequest) -> str:
        ctx = request.context
        # Rev 6: outputs ride the snapshot (context) — the one carrier.
        specialist = json.dumps(ctx.specialist_outputs, ensure_ascii=False)
        if self._settings.camera_timezone:
            # The Time: line carries the capture moment; a row's detected_at is
            # its arrival and would contradict it. Drop it from the rendered
            # copy only - the snapshot rows keep it.
            rows = [{k: v for k, v in row.items() if k != "detected_at"} for row in rows]
        if request.frame_detection_ids is not None:
            # Rendered copy only: each row names the attached frame it is on
            # (1-based), null when its still is not attached (A5500 M1).
            frame_of: dict[Any, int] = {
                det_id: i
                for i, ids in enumerate(request.frame_detection_ids, start=1)
                for det_id in ids
            }
            rows = [{**row, "frame": frame_of.get(row.get("id"))} for row in rows]
        rows = self._grounded_boxes(rows, request)
        chronology = self._chronology_lines(request)
        return (
            "You are the verification expert. The detections below were produced "
            "by an object detector on the attached frame(s). Decide whether the "
            "detected candidate is REAL and CORRECTLY IDENTIFIED (verdict), and "
            # OD-29 (owner ruling 2026-10-05): the severity-rubric scoring clause
            # from the 2026-10-03 arm B replay ships as the paired operating
            # point with the per-camera numeric alert floor 60 - the two are one
            # change (arm B text alone at the old floor is FP-WORSE than shipped:
            # 16.3% vs 6.7% benign alerts; with floor 60: 4.3%). Text shipped
            # byte-identical to the measured arm (rubric_text in run.json of
            # eval run 696c71687e264577b4deb6bd5c99af26, sha256 of the clause
            # 75564981ca9d22cdaab967e83052b55061abf770b8fcb20e2cfe69babc929811);
            # evidence: docs/vss-integration/23-*.md and stage35/
            # results-operating-point-ship.py there.
            "how much risk the scene poses (risk_score 0-100): the potential "
            "for harm to people or property if the scene is as it appears, "
            "whether or not any aggression is visible yet. Score by these "
            "bands: 0-29 low = routine, expected or harmless activity; "
            "30-59 medium = unusual or ambiguous activity that warrants "
            "attention, or an unfamiliar person or vehicle whose purpose is "
            "unclear; 60-84 high = clear signs of a likely crime, hazard or "
            "person in danger (for example someone entering or tampering with "
            "a closed space or vehicle, taking items, holding a weapon or tool "
            "in a threatening way, a child or injured person without "
            "supervision near a hazard, fire or smoke); 85-100 critical = an "
            "immediate, serious threat to life or property. A person who looks "
            "calm can still be a high risk, so do not lower the score because "
            "a person is calm or stationary; do not raise it for ordinary "
            "visitors, residents, workers or animals. Answer ONLY with the "
            "verdict JSON object: verdict, risk_score, summary, reasoning, "
            "description, criteria (each name/passed/evidence), provenance "
            "(engine, model_id - copy the values from the served model's own "
            "reported identity).\n\n"
            f"Camera: {ctx.camera_id}\n"
            f"Time: {render_prompt_time(ctx.timestamp, self._settings.camera_timezone)}\n"
            f"Zones: {', '.join(ctx.zones) or 'none'} (crossing: {ctx.zone_crossing})\n"
            f"{chronology}"
            f"{self._box_guidance(rows, request)}"
            f"Detections: {json.dumps(rows, ensure_ascii=False)}\n"
            f"Household context: {json.dumps(ctx.household, ensure_ascii=False)}\n"
            f"Specialist outputs (faces/plates/re-ID; these are detector evidence, "
            f"not yours to invent): {specialist}\n"
        )

    def _chronology_lines(self, request: VlmAssessRequest) -> str:
        """The ISS-033 timeline: when the request carries per-frame capture
        times, say the frames are in chronological order and label each one.

        The label is `render_prompt_time` — the same rendering as the `Time:`
        line (local wall time with zone when the camera timezone is set, the
        stored UTC ISO string when it is not), so a frame label and the batch
        time are the same shape. An unknown time renders `unknown`: the
        arrival time of a row is NOT a capture time and never appears here
        (the register's acceptance, verbatim). An absent field (None) renders
        nothing at all — the prompt of every store built before ISS-033, and
        of every replay, stays byte-identical.
        """
        if not request.frame_capture_times:
            return ""
        tz_name = self._settings.camera_timezone
        labels = "\n".join(
            f"Frame {index}: "
            + ("unknown" if moment is None else render_prompt_time(moment, tz_name))
            for index, moment in enumerate(request.frame_capture_times, start=1)
        )
        return (
            "Frames are in chronological order (oldest first), one image per frame "
            "in the order they are attached. Frame times:\n"
            f"{labels}\n"
        )

    @staticmethod
    def _frame_dims(request: VlmAssessRequest) -> list[tuple[int, int] | None]:
        """(width, height) of each attached frame, in order, read from the
        image header only; None for a frame that cannot be read - never
        guessed."""
        dims: list[tuple[int, int] | None] = []
        for path in request.image_paths:
            try:
                with Image.open(path) as im:
                    dims.append((im.width, im.height))
            except OSError, ValueError:
                dims.append(None)
        return dims

    @classmethod
    def _frame_sizes(cls, request: VlmAssessRequest) -> list[str]:
        """Pixel sizes of the readable attached frames ("WxH", distinct, in
        order)."""
        sizes: list[str] = []
        for dim in cls._frame_dims(request):
            if dim is not None and (size := f"{dim[0]}x{dim[1]}") not in sizes:
                sizes.append(size)
        return sizes

    def _grounded_boxes(
        self, rows: list[dict[str, Any]], request: VlmAssessRequest
    ) -> list[dict[str, Any]]:
        """Rendered copy only: a row whose frame size is known carries
        bbox_2d = [x1, y1, x2, y2] on a 0-1000 scale of that frame - Qwen3-VL's
        own grounding format - in place of the snapshot's pixel [x, y, w, h].
        With the pixel convention stated and the frame size named, the 8B
        still read [369, 183, 419, 513] its own way (a sliver) and rejected a
        correct person box as "too small" (A5500 M1, event 617). The scale is
        the row's linked frame, else the one size every attached frame
        shares; with neither, the row keeps its pixels (never a guessed
        scale)."""
        dims = self._frame_dims(request)
        known = set(dims)
        shared = dims[0] if len(known) == 1 else None  # None when unreadable too
        grounded: list[dict[str, Any]] = []
        for row in rows:
            bbox = row.get("bbox")
            k = row.get("frame")
            wh = dims[k - 1] if isinstance(k, int) and 1 <= k <= len(dims) else shared
            if wh is None or not self._is_box(bbox):
                grounded.append(row)
                continue
            x, y, w, h = bbox
            fw, fh = wh
            corners = [
                min(1000, max(0, round(v * 1000 / f)))
                for v, f in ((x, fw), (y, fh), (x + w, fw), (y + h, fh))
            ]
            grounded.append(
                {
                    ("bbox_2d" if key == "bbox" else key): (corners if key == "bbox" else value)
                    for key, value in row.items()
                }
            )
        return grounded

    @staticmethod
    def _is_box(bbox: Any) -> TypeGuard[list[float]]:
        """Four real numbers (the analyzer can hand over [None]*4 for a row
        stored without a box)."""
        return (
            isinstance(bbox, (list, tuple))
            and len(bbox) == 4
            and all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in bbox)
        )

    def _box_guidance(self, rows: list[dict[str, Any]], request: VlmAssessRequest) -> str:
        """How to read the rows' boxes - only when there are rows. The A5500
        M1 chain showed the 8B reading bare [x, y, w, h] numbers as corners,
        then (with the convention stated but no frame size) rejecting a
        correct person box as "positioned incorrectly": it cannot place pixel
        numbers without the frame, and it treated box arithmetic as evidence
        of a false detection. Rows are grounded in the model's own bbox_2d
        format where the frame size is known (_grounded_boxes); the pixel
        sentence covers the rows that are not. With no rows the prompt is
        unchanged."""
        if not rows:
            return ""
        convention = ""
        if any("bbox_2d" in row for row in rows):
            convention += (
                "A row's bbox_2d is [x1, y1, x2, y2]: its top-left and bottom-right "
                "corners on a 0-1000 scale of its frame (your own grounding format). "
            )
        if any("bbox_2d" not in row for row in rows):
            sizes = self._frame_sizes(request)
            frame = f"its {' or '.join(sizes)} source frame" if sizes else "its source frame"
            convention += (
                f"A row's bbox is [x, y, width, height] in pixels of {frame}: "
                "the top-left corner, then the box size. "
            )
        return (
            f"{convention}The boxes are the detector's "
            "localization aids: judge each candidate from what the frame(s) show, "
            "and never reject a detection because of its box numbers alone.\n"
            + (
                "Each row's frame is the 1-based index of the attached frame it was "
                "detected on; null means its frame is not attached - such a row is "
                "the same camera's detection on another still, not a box on the "
                "frames you see.\n"
                if request.frame_detection_ids is not None
                else ""
            )
        )

    @staticmethod
    def _rank_for_budget(row: dict[str, Any]) -> tuple[float, int]:
        """Which detections survive a truncated prompt: strongest confidence
        first, then lowest id (a TOTAL order, so the survivors never depend
        on arrival order - replay equality, same rule as the key-frame
        selector). A None confidence is honest-absent and sorts last, never
        laundered to 0.0."""
        conf = row.get("confidence")
        return (conf if isinstance(conf, int | float) else -1.0, -int(row.get("id") or 0))

    def _fitted_prompt(self, request: VlmAssessRequest) -> tuple[str, bool]:
        """The prompt text, and whether it had to be shortened to fit.

        The budget is `settings.vlm_context_window` (VLM_CTX_SIZE /
        VLM_PARALLEL - the slot a vlm_assess actually occupies), less the
        image reservation, less the verdict's own output budget. NOT
        `nemotron_context_window`: the backend container mirrors the legacy
        ai-llm service's CTX_SIZE/PARALLEL, whose slot is larger, so grading
        a vlm prompt against it waves through prompts the real slot cannot
        hold.

        Truncation is VISIBLE and deterministic (the "log the clamp" doctrine
        `apply_verdict_invariants` follows for scores): the strongest
        detections survive - the same ranking the key-frame selector stands
        behind, so what remains is the evidence the stills can corroborate -
        and the prompt says how many rows were omitted. A model shown 60 of
        500 rows and told nothing would read the gap as "no further
        activity", which is a lie by omission on the one channel spec §6
        reserves for detector evidence.

        Returns the flag rather than exposing it as a metric because this is
        a pure renderer called twice per batch (once here for the wire, once
        by the analyzer for the stored `llm_prompt`): a counter bumped in
        here would record the same event twice, so `assess` owns the effect.
        """
        ctx = request.context
        budget = (
            self._settings.vlm_context_window
            - _ASSESS_MAX_TOKENS
            - self._image_token_reservation(request)
        )
        counter = get_token_counter()

        def served(prompt: str) -> int:
            return math.ceil(counter.count_tokens(prompt) * _SERVED_TOKENS_PER_COUNTED)

        rows = list(ctx.detections)
        text = self._render_prompt(rows, request)
        if served(text) <= budget:
            return text, False

        # Strongest-first, then binary-search the largest list that fits.
        # The marker itself costs tokens and its length changes with the
        # count, so the fit test renders the FINAL text, never a proxy.
        ranked = sorted(rows, key=self._rank_for_budget, reverse=True)

        def fitted(kept: int) -> str:
            body = self._render_prompt(ranked[:kept], request)
            omitted = len(ranked) - kept
            if omitted <= 0:
                return body
            return body + (
                f"[{omitted} further detections were omitted from this list to fit "
                f"the model's context budget; the {kept} listed are the "
                f"highest-confidence rows and are the ones the attached frame(s) "
                "were selected around]\n"
            )

        lo, hi = 0, len(ranked)
        while lo < hi:
            mid = (lo + hi + 1) // 2
            if served(fitted(mid)) <= budget:
                lo = mid
            else:
                hi = mid - 1
        return fitted(lo), True

    def prompt_text(self, request: VlmAssessRequest) -> str:
        """The text half of the assess message, FITTED to the vlm slot.

        PUBLIC because the analyzer stores it verbatim as Event.llm_prompt
        (spec §4 event detail: images referenced by path, never embedded) -
        which is precisely why the stored text must BE the text the model was
        given: `assess` renders through this same method, so the row records
        the question that was actually asked, truncation marker included.
        Same input, same string, one code path (the "ONE path" rule the
        builders follow)."""
        return self._fitted_prompt(request)[0]

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
        text, truncated = self._fitted_prompt(request)
        if truncated:
            # The arm's only non-textual footprint. Firing HERE, at the wire,
            # not inside the renderer: prompt_text runs a second time in the
            # analyzer (the stored llm_prompt), and one oversized batch is
            # one event, not two.
            record_prompt_truncated()
            logger.warning(
                "vlm prompt truncated to fit the slot",
                extra={
                    "vlm_context_window": self._settings.vlm_context_window,
                    "detections_in_context": len(request.context.detections),
                },
            )

        body = {
            "messages": [
                {
                    "role": "user",
                    "content": [*parts, {"type": "text", "text": text}],
                }
            ],
            "temperature": _ASSESS_TEMPERATURE,
            "max_tokens": _ASSESS_MAX_TOKENS,
            "response_format": {
                "type": "json_schema",
                "json_schema": {"name": "vlm_verdict", "schema": self._wire_schema()},
            },
        }

        last_error: VlmClientError | None = None
        for attempt, temperature in enumerate((None, 0.0)):
            if temperature is not None:
                # §6 step 1: retry at temp 0. The first attempt is greedy too
                # (_ASSESS_TEMPERATURE), so the retry is a plain re-send; it stays
                # explicit so changing the first-attempt temperature cannot
                # silently change the retry.
                body["temperature"] = temperature
            try:
                http = await self._http()
                resp = await http.post(CHAT_PATH, json=body)
            except httpx.ReadTimeout as exc:
                # D1. A reply that outruns `ai_vlm_read_timeout` is a BUDGET,
                # not an outage, and it is OUR budget: the connection was
                # accepted (httpx raises a plain ReadTimeout, never
                # ConnectTimeout, only once the socket is open and the request
                # is written), the grammar applied, the engine is working. The
                # request leaves unchanged, so the §6 retry re-asks the
                # identical question at the identical speed and times out
                # identically - and used to charge the breaker a second time
                # for doing so. Five slow items opened `ai-vlm` for every
                # camera over a number we chose, after which every later item
                # answered VlmUnavailableError WITHOUT I/O and the report
                # described a breaker instead of a model. Same ruling as
                # `_context_overflow_of` and the truncation leg above: the
                # breaker asks "stop calling this engine?" and a slow reply
                # answers NO. The item still refuses to score.
                await self._note_budget_exhausted("vlm_assess_timeout")
                logger.warning(
                    "vlm reply exceeded the read budget",
                    extra={
                        "ai_vlm_read_timeout": self._settings.ai_vlm_read_timeout,
                        "max_tokens": _ASSESS_MAX_TOKENS,
                    },
                )
                raise VlmSlowReplyError(
                    f"vlm reply exceeded the {self._settings.ai_vlm_read_timeout:.0f}s "
                    f"read budget at max_tokens={_ASSESS_MAX_TOKENS}; verdict UNMEASURED "
                    "at this budget, the engine is fine"
                ) from exc
            except Exception as exc:
                last_error = VlmTransportError(f"vlm transport failure: {exc}")
                await self._note_failure("vlm_transport_error")
                logger.warning(
                    "vlm transport error (attempt %d)", attempt + 1, extra={"error": str(exc)}
                )
                continue
            if overflow := _context_overflow_of(resp):
                # A5500 2026-09-28: filed as transport, this cost two breaker
                # failures per batch (the retry re-sent the same bytes).
                await self._note_budget_exhausted("vlm_context_overflow")
                logger.warning("vlm request exceeded the served slot", extra=overflow)
                raise VlmContextOverflowError(
                    f"vlm request ({overflow.get('n_prompt_tokens')} tokens) exceeds the "
                    f"served slot ({overflow.get('n_ctx')} tokens); the prompt fit "
                    "under-estimated it - verdict UNMEASURED, the engine is fine"
                )
            if resp.status_code != 200:
                last_error = VlmTransportError(f"vlm HTTP {resp.status_code}: {resp.text[:200]}")
                await self._note_failure("vlm_http_error")
                continue
            content = _content_of(resp)
            try:
                verdict = VlmVerdict.model_validate_json(content)
            except ValidationError as exc:
                stop = _stop_reason_of(resp)
                if _is_length_truncated(stop):
                    # FINDING A on the assess leg. The object was cut off by
                    # its own budget, so it was never a candidate for being
                    # valid JSON - calling this `vlm_schema_invalid` blames the
                    # model for a number we chose. And the §6 retry cannot
                    # help: it re-asks the SAME body at the SAME
                    # _ASSESS_MAX_TOKENS (and, now, the SAME temperature), so it
                    # would produce the same length-capped object while
                    # recording one more breaker failure toward opening
                    # ai-vlm over a budget. Raise once, with the cause named.
                    # The ladder's OUTCOME is unchanged - this is still a
                    # VlmClientError, so the analyzer still answers
                    # verification_failed with a NULL score.
                    last_error = VlmTruncatedError(
                        f"vlm verdict reply hit its token budget before the "
                        f"object closed (stop={stop!r}, "
                        f"max_tokens={_ASSESS_MAX_TOKENS}); verdict UNMEASURED "
                        "at this budget, not invalid"
                    )
                    await self._note_budget_exhausted("vlm_assess_truncated")
                    logger.warning(
                        "vlm verdict truncated at max_tokens=%d",
                        _ASSESS_MAX_TOKENS,
                        # string data rides `extra`, per this module's own
                        # convention (the transport-error warning above) - the
                        # repo's semgrep rule flags a %s in the message.
                        extra={"stop": stop},
                    )
                    # `from exc` keeps the failed parse as the underlying
                    # cause: the ValidationError is the SYMPTOM (the JSON never
                    # closed), the budget is the CAUSE, and the traceback
                    # should read in that order.
                    raise last_error from exc
                last_error = VlmSchemaError(f"vlm verdict failed validation: {exc}")
                await self._note_failure("vlm_schema_invalid")
                logger.warning("vlm schema violation (attempt %d)", attempt + 1)
                continue
            await self._breaker.record_success_async()
            await self._push_healthy()
            return verdict.model_copy(update={"provenance": self._served_provenance()})

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

    async def _note_budget_exhausted(self, reason: str) -> None:
        """Count it, but do NOT feed the breaker.

        The breaker answers one question - "should we stop calling this
        service?" - and a reply cut off by OUR max_tokens answers it NO: the
        transport worked, the grammar applied, the endpoint returned 200 and
        did real work. Feeding it means a verbose corpus OPENS `ai-vlm` over a
        number we chose, after which every later item raises
        VlmUnavailableError WITHOUT I/O and the replay reports a breaker, not
        a model - the exact contamination finding B found for a per-item
        client, reached instead through a budget.

        Nothing is silenced: the metric still counts (that is the aggregate
        the M2 read uses, under its own cause), the item still refuses to
        score, and the analyzer still answers verification_failed with a NULL
        score. The diagnosis stays loud; the breaker is just not lied to.

        Deliberately NOT used for the service-level probe refusals (props
        unreachable, transport, build mismatch) - those genuinely do mean
        "stop calling this endpoint", and their breaker behavior is unchanged."""
        record_pipeline_error(reason)

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


def _stop_reason_of(resp: httpx.Response) -> str | None:
    """The engine's own account of why generation STOPPED.

    Both wires, because the repo probes both: llama.cpp's native
    ``/completion`` reports ``stop_type``, its OpenAI-compat
    ``/v1/chat/completions`` reports ``finish_reason``. Choice-level first,
    then body-level. ``None`` means the server did not say - which is NOT
    evidence of truncation; judging that goes through
    ``nemotron_analyzer._is_length_truncated``, the one vocabulary both probe
    surfaces share.
    """
    if resp.status_code != 200:
        return None
    try:
        body = resp.json()
    except Exception:
        return None
    if not isinstance(body, dict):
        return None
    choices = body.get("choices")
    choice = choices[0] if isinstance(choices, list) and choices else None
    for source in (choice if isinstance(choice, dict) else {}, body):
        for key in ("finish_reason", "stop_type", "stop_reason"):
            value = source.get(key)
            if isinstance(value, str) and value:
                return value
    return None
