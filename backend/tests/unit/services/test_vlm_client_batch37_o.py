# TARGET-MODULE: backend.services.vlm_client
"""Battery O - campaign #13 of the ladder (batch-37): kill-real coverage for
``backend/services/vlm_client.py`` (324 survivors at 62.33% entering).

Harness-compatible by design (batch-30 single-process sweep): every test is a
module-level sync ``test_*()`` with no fixtures and no parametrize; coroutines
run through ``asyncio.run`` inside. The file is also collected by normal
pytest in the repo tree, so every seam swap restores in ``finally``.

The shipped battery pins the wire at coarse level (retry COUNTS, breaker
counts, finding-A triage) with fragment asserts - fragment asserts pass
XX-wrapped and case-flipped strings (the repo's own measured trap), so the
whole exact-shape layer survived. This battery kills it: FULL rendered-prompt
string equality, exact wire-BODY dicts, exact log signatures (level, raw msg,
args tuple, every ``extra`` attr, exc class), metric/degradation call tuples
(kwargs compared as dicts - a DROPPED kwarg is absent, never ``None``),
httpx timeout extensions (client-level and per-request ride
``request.extensions``), client state after the probe, exception ``str()``
and ``.verdict``, the §6 continue->break twin via second-attempt-success
(the m55 doctrine: the survivor case must come first AND pass every filter
ahead of the mutated site), and the binary-search fit boundaries.

Honesty ledger - dispositions registered EQUIVALENT at authoring (the sweep
must show GREEN on exactly these unless the sweep proves otherwise; anything
else GREEN is a test gap):

* ``xǁVlmClientǁ__init____mutmut_24`` (drop ``failure_threshold=5``): the
  dataclass default IS 5 (circuit_breaker.py:150) - identical config.
* ``xǁVlmClientǁ_image_parts__mutmut_5`` (``[:4]`` -> ``[:5]``):
  VlmAssessRequest.image_paths carries ``max_length=4`` (vlm_verdict.py:113,
  measured) - the slice bound is unreachable above the model's own cap.
* ``xǁVlmClientǁ_image_parts__mutmut_9`` (``is_absolute() and False``): for
  an ABSOLUTE path ``root / path`` IS the path (Path-join with an absolute
  argument discards the base - measured), so the else-branch resolves
  identically for every input.
* ``xǁVlmClientǁ_wire_schema__mutmut_4`` / ``_mutmut_6`` (encoding None /
  "UTF-8"): the contract file is byte-ASCII (measured: 2927 bytes, all <128)
  - locale-default and UTF-8 decode identically.
* ``xǁVlmClientǁ_render_prompt__mutmut_4`` / ``_48`` / ``_53``
  (``ensure_ascii=False`` -> ``None``): json treats ensure_ascii falsy as
  False (measured: ``dumps(o, ensure_ascii=None) == dumps(o, ensure_ascii=
  False)`` exactly).
* ``xǁVlmClientǁ_box_guidance__mutmut_9`` (FIRST ``convention +=`` ->
  ``=``; the rendered m9 body shows the mutation on the bbox_2d arm, the
  pixel arm keeps ``+=``): ``convention`` is literally ``""`` when that
  clause runs, and ``""`` anyway when it is skipped - ``"" += x`` IS
  ``= x``. The second ``+=`` (pixel clause) is a different mutant and IS
  killed: the mixed-rows render demands both sentences in order.
* ``xǁVlmClientǁ_probe_enforcement__mutmut_3`` (outer gate ``_enforced is
  True`` -> ``is False``): ``_enforced`` is only ever ``None`` or ``True``
  (init None, the ENFORCED arm assigns True) - ``is False`` never fires,
  and the lock-held INNER double-check (unmutated here) returns every
  already-ENFORCED caller before any I/O. The only difference is WHICH
  side of the lock the early return happens on - unobservable. (The inner
  gate's own mutation ``_6`` is NOT equivalent: the concurrency test
  proves one-probe-exactly.)
* ``xǁVlmClientǁ_probe_enforcement__mutmut_42`` (drop ``nonce=None``): the
  parameter default regenerates a fresh uuid either way; the echo contract
  is carried by the SAME nonce in both shapes.
* ``xǁVlmClientǁ_probe_enforcement__mutmut_89`` (``status_code == 200``
  ``or True``): the call target ``_content_of`` self-gates on status != 200
  returning "" (source 1000-1001), so the ternary's else is dead code
  reached with the same "".
* ``xǁVlmClientǁ_probe_enforcement__mutmut_93`` (non-200 content "" ->
  "XXXX"): both values fail ``json.loads`` -> ``echoed`` False either way,
  and the raise message names the STATUS, never the content.
* ``xǁVlmClientǁ_probe_enforcement__mutmut_96`` / ``_97`` (``echoed =
  False`` pre-init -> ``None`` / ``True``): every execution path reads it
  only AFTER an assignment - the try-block assigns unconditionally on
  success (any partial-dict raise lands in the except arm, which reassigns
  False) - so the initializer is never read.
* ``xǁVlmClientǁ_probe_enforcement__mutmut_104`` (except-arm ``echoed =
  False`` -> ``None``): ``if echoed:`` is the only read - both falsy, and
  no raise message or metric ever interpolates ``echoed``.
* ``xǁVlmClientǁ_probe_enforcement__mutmut_140`` (drop ``verdict="ignored"``
  on the 200-no-echo raise): the class default IS "ignored"
  (constrained_decoding.py:52).
* ``xǁVlmClientǁ_fitted_prompt__mutmut_35`` (``omitted <= 0`` -> ``< 0``
  in the ``fitted`` helper): ``omitted == len(ranked) - kept`` with
  ``kept`` in ``0..len``, so ``omitted`` is never negative - and the only
  ``omitted == 0`` call is ``fitted(len(ranked))``, whose return value is
  ``ranked == rows`` in original order: the char length is ORDER-INDEPENDENT
  (measured), the fast path already saw that length and it exceeded the
  budget, and any binary-search probe at ``lo == len`` requires a lower
  prefix (with the strictly-longer-marker text - strictly more chars,
  because every row's json is non-empty) to have fitted first. So the
  marker-free return can never be the answer or a passing probe - the
  search and the returned pair are identical. (The sibling ``<= 1`` is a
  different mutant and IS killed: suppressing the marker at
  ``omitted == 1`` makes the n-1-row probe FIT where the marked text does
  not, so the search lands one row higher - the truncation tests' windows
  sit exactly in that margin.)
* ``xǁVlmClientǁ_fitted_prompt__mutmut_45`` (``mid`` +2): the searched
  domain is a monotone feasible prefix; ``lo`` only advances on a fitting
  probe and ``(lo+hi+2)//2 <= hi`` whenever the gap allows the old probe -
  the maximum feasible ``lo`` is identical.
* ``xǁVlmClientǁassess__mutmut_58`` (init ``last_error = ""``): every path
  that reaches the loop tail assigns a real error first (both continue sites
  assign; the overflow/truncated arms RAISE) - the falsy init is never read.
* ``xǁVlmClientǁassess__mutmut_156``/``_157``/``_158``/``_159`` (the
  ``else VlmClientError("vlm assess failed")`` arm): unreachable for the
  same reason, and an assigned error object is always truthy - the fallback
  message can never be raised or observed.
"""

import asyncio
import base64
import json
import logging
import math
import sys
import tempfile
import types
from pathlib import Path
from typing import Any

import httpx
import pytest

import backend.services.vlm_client as vc
from backend.services.circuit_breaker import (
    get_circuit_breaker,
    reset_circuit_breaker_registry,
)
from backend.services.constrained_decoding import (
    ConstrainedDecodingNotEnforced,
    build_probe_schema,
)
from backend.services.vlm_verdict import VlmAssessRequest

_MISSING = object()

_BUILD = "b7972-e06088da0"
_WIRE_TIMEOUT = {"connect": 4.0, "read": 27.0, "write": 27.0, "pool": 27.0}
_WAKE_TIMEOUT = {"connect": 4.0, "read": 45.0, "write": 45.0, "pool": 45.0}

# prompt-prose literals - copied verbatim from the shipped module; the full
# string (never a fragment) is what gets compared.
_SYSTEM = (
    "You are the verification expert. The detections below were produced "
    "by an object detector on the attached frame(s). Decide whether the "
    "detected candidate is REAL and CORRECTLY IDENTIFIED (verdict), and "
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
    "reported identity)."
)
_BOX2D = (
    "A row's bbox_2d is [x1, y1, x2, y2]: its top-left and bottom-right "
    "corners on a 0-1000 scale of its frame (your own grounding format). "
)
_BOX_TAIL = (
    "The boxes are the detector's "
    "localization aids: judge each candidate from what the frame(s) show, "
    "and never reject a detection because of its box numbers alone.\n"
)
_FRAME_NOTE = (
    "Each row's frame is the 1-based index of the attached frame it was "
    "detected on; null means its frame is not attached - such a row is "
    "the same camera's detection on another still, not a box on the "
    "frames you see.\n"
)
_PROBE_TEXT = "Emit the verdict object for the scene in the image above. Output JSON only.\n"


def _module_stub(mods):
    """Set attrs on already-imported modules; returns an exact restore."""
    undo = []
    for dotted, attrs in mods.items():
        mod = sys.modules.get(dotted)
        if mod is None:  # pragma: no cover - every seam is imported by vc
            mod = types.ModuleType(dotted)
            sys.modules[dotted] = mod
            undo.append(("module", dotted))
        for key, val in attrs.items():
            old = getattr(mod, key, _MISSING)
            setattr(mod, key, val)
            undo.append(("attr", (mod, key), old))

    def restore():
        for item in reversed(undo):
            if item[0] == "module":
                sys.modules.pop(item[1], None)
                continue
            mod, key = item[1]
            old = item[2]
            if old is _MISSING:
                if hasattr(mod, key):
                    delattr(mod, key)
            else:
                setattr(mod, key, old)

    return restore


def _logs():
    """Exact (level, raw msg, args, extra attrs, exc class) capture."""
    records = []

    class _Cap(logging.Handler):
        def emit(self, record):
            records.append(record)

    handler = _Cap()
    old_handlers = vc.logger.handlers[:]
    old_propagate = vc.logger.propagate
    old_level = vc.logger.level
    vc.logger.handlers[:] = [handler]
    vc.logger.propagate = False
    vc.logger.setLevel(logging.DEBUG)

    def restore():
        vc.logger.handlers[:] = old_handlers
        vc.logger.propagate = old_propagate
        vc.logger.setLevel(old_level)

    return records, restore


def _log_sig(records, extra_keys=()):
    out = []
    for r in records:
        extra = tuple(getattr(r, key, _MISSING) for key in extra_keys)
        exc = None if r.exc_info is None else r.exc_info[0]
        out.append((r.levelname, r.msg, r.args, extra, exc))
    return out


def _metric_stub(seen, truncated=None, cold=None):
    """Swap the metrics vlm_client imported INTO its own namespace."""

    def _err(reason):
        seen.append(("pipeline_error", reason))

    def _trunc():
        if truncated is not None:
            truncated.append("prompt_truncated")

    def _cold(model):
        if cold is not None:
            cold.append(model)

    return {
        "backend.services.vlm_client": {
            "record_pipeline_error": _err,
            "record_prompt_truncated": _trunc,
            "record_model_cold_start": _cold,
        }
    }


class _Mgr:
    def __init__(self, sink):
        self._sink = sink

    async def update_service_health(self, name, **kw):
        self._sink.append(("health", name, tuple(sorted(kw.items()))))


def _degradation_stub(sink):
    """Swap the FUNCTION-LOCAL import targets of _push_*/the gauge."""

    def _gauge(service, degraded):
        sink.append(("gauge", service, degraded))

    return {
        "backend.services.degradation_manager": {"get_degradation_manager": lambda: _Mgr(sink)},
        "backend.core.metrics": {"set_ai_service_degraded": _gauge},
    }


class _SpyBreaker:
    """Stands in for the registry breaker: records, never acts."""

    def __init__(self, allow=True, is_open=False, is_closed=True):
        self.allow = allow
        self.open_ = is_open
        self.closed_ = is_closed
        self.calls = []

    async def allow_call(self):
        self.calls.append(("allow",))
        return self.allow

    async def record_failure_async(self):
        self.calls.append(("failure",))

    async def record_success_async(self):
        self.calls.append(("success",))

    @property
    def is_open(self):
        return self.open_

    @property
    def is_closed(self):
        return self.closed_

    class _Cfg:
        recovery_timeout = 60.0

    config = _Cfg()


def _fill(schema):
    """Schema-shaped filler (the strict fake's job): enum first."""
    if "enum" in schema:
        return schema["enum"][0]
    t = schema.get("type")
    if t == "boolean":
        return True
    if t == "integer":
        return 50
    if t == "array":
        return [_fill(schema["items"])]
    if t == "object":
        return {k: _fill(v) for k, v in (schema.get("properties") or {}).items()}
    return "ok"  # string and any untyped node


class _StubTransport(httpx.AsyncBaseTransport):
    """Records (method, path, timeout-extension, json body) and answers
    from a per-path handler queue. Handlers receive the decoded body and
    return (status, payload) or raise."""

    def __init__(self, handlers):
        self.calls = []
        self._handlers = handlers
        self._used = {}

    async def handle_async_request(self, request):
        raw = bytes(await request.aread())
        body = json.loads(raw) if raw else None
        self.calls.append(
            {
                "method": request.method,
                "path": request.url.path,
                "timeout": (request.extensions or {}).get("timeout"),
                "body": body,
            }
        )
        path = request.url.path
        idx = self._used.get(path, 0)
        self._used[path] = idx + 1
        queue = self._handlers.get(path)
        if queue is None:
            raise httpx.ConnectError(f"stub refused {path}")
        handler = queue[idx] if idx < len(queue) else queue[-1]
        status, payload = handler(body)
        if isinstance(payload, str):  # a plain-text body (error pages)
            return httpx.Response(status, content=payload.encode(), request=request)
        return httpx.Response(status, json=payload, request=request)


class _PausingTransport(_StubTransport):
    """Same recording/stubbing, but the FIRST request to `pause_path`
    signals `started` and waits for `release` inside handle_async_request
    - a caller can be parked mid-flight in a GET while others run."""

    def __init__(self, handlers, *, pause_path, started, release):
        super().__init__(handlers)
        self._pause_path = pause_path
        self._started = started
        self._release = release
        self._paused = False

    async def handle_async_request(self, request):
        if request.url.path == self._pause_path and not self._paused:
            self._paused = True
            self._started.set()
            await self._release.wait()
        return await super().handle_async_request(request)


def _echo_handler(build_info=_BUILD, model_path=None, finish="stop"):
    """/props arm."""
    payload = {"build_info": build_info}
    if model_path:
        payload["model_path"] = model_path
    return lambda _body: (200, payload)


def _chat_strict(finish="stop", drop_const=False):
    """Chat arm that HONORS the grammar (echoes probe_const when present)."""

    def handler(body):
        rf = body.get("response_format") or {}
        schema = (rf.get("json_schema") or {}).get("schema") or {}
        filled = _fill(schema)
        const = (schema.get("properties") or {}).get("probe_const", {}).get("const")
        if const is not None and not drop_const:
            filled["probe_const"] = const
        return 200, {
            "choices": [{"message": {"content": json.dumps(filled)}, "finish_reason": finish}]
        }

    return handler


def _chat_prose(finish="stop"):
    """Chat arm that ignores response_format: complete reply, no grammar."""

    def handler(body):
        return 200, {
            "choices": [
                {"message": {"content": "The scene shows a driveway."}, "finish_reason": finish}
            ]
        }

    return handler


def _settings(**kw):
    base = {
        "vlm_enforcement_probe_enabled": True,
        "vlm_required_build": "",
        "camera_timezone": None,
        "ai_vlm_read_timeout": 27.0,
        "ai_connect_timeout": 4.0,
        "ai_vlm_wake_timeout_seconds": 45.0,
    }
    base.update(kw)
    return vc.get_settings().model_copy(update=base)


def _client(handlers, **settings_overrides):
    reset_circuit_breaker_registry()
    return vc.VlmClient(
        settings=_settings(**settings_overrides),
        transport=_StubTransport(handlers),
        base_url="http://fake-vlm:8098",
    )


def _stills(count=1, extra_names=()):
    """Real files under a real root: the guards read the filesystem. The
    stills come back as absolute paths; the root is files[0].parent."""
    root = Path(tempfile.mkdtemp())
    for name in extra_names:
        (root / name).write_bytes(b"\xff\xd8\xff" + b"\x00" * 20)
    files = []
    for i in range(count):
        f = root / f"s{i}.jpg"
        f.write_bytes(b"\xff\xd8\xff" + bytes([i]) * 20)
        files.append(str(f))
    return files


def _pil_open_stub(dims_by_name, raises=()):
    """Swap PIL.Image.open for _frame_dims: sizes only, never pixels."""

    class _Ctx:
        def __init__(self, w, h):
            self.width, self.height = w, h

        def __enter__(self):
            return self

        def __exit__(self, *_exc):
            return False

    def opener(path):
        name = Path(str(path)).name
        if name in raises:
            raise OSError(f"unreadable {name}")
        w, h = dims_by_name[name]
        return _Ctx(w, h)

    return _module_stub({"PIL.Image": {"open": opener}})


# ---------------------------------------------------------------------------
# module-level pure helpers
# ---------------------------------------------------------------------------


def _resp(status: int, payload: Any) -> httpx.Response:
    return httpx.Response(
        status, content=json.dumps(payload).encode(), headers={"content-type": "application/json"}
    )


def test_content_of_shapes():
    # the content line is the ONLY read of the choice message; "" and None
    # both land on "" (the `or ""` arm), never a stand-in string
    assert vc._content_of(_resp(200, {"choices": [{"message": {"content": "hi"}}]})) == "hi"
    assert vc._content_of(_resp(200, {"choices": [{"message": {"content": ""}}]})) == ""
    assert vc._content_of(_resp(200, {"choices": [{"message": {"content": None}}]})) == ""
    assert vc._content_of(_resp(503, {"choices": [{"message": {"content": "x"}}]})) == ""
    assert vc._content_of(_resp(200, {"nope": 1})) == ""


def test_context_overflow_keys_on_type_never_prose():
    # structured 400 -> the two counters; prose 400 (error a STRING) must not
    # raise and must not read (the isinstance guard's whole job)
    overflow = {
        "error": {
            "code": 400,
            "message": "request exceeds the available context size, try increasing it",
            "type": "exceed_context_size_error",
            "n_prompt_tokens": 22293,
            "n_ctx": 16384,
        }
    }
    assert vc._context_overflow_of(_resp(400, overflow)) == {
        "n_prompt_tokens": 22293,
        "n_ctx": 16384,
    }
    assert vc._context_overflow_of(_resp(400, {"error": "exceed_context_size_error"})) is None
    assert vc._context_overflow_of(_resp(400, {"error": {"type": "other"}})) is None
    assert vc._context_overflow_of(_resp(200, overflow)) is None


def test_resolve_refs_inlines_and_drops_defs():
    wire = vc.VlmClient(settings=_settings())._wire_schema()
    assert "$defs" not in wire
    assert "$ref" not in json.dumps(wire)
    assert wire["properties"]["criteria"]["items"]["properties"]["name"]["type"] == "string"
    assert "enum" in wire["properties"]["verdict"]
    # the source contract really carries the refs this flattened
    raw = json.loads(vc._CONTRACT_SCHEMA_PATH.read_text(encoding="utf-8"))
    assert "$defs" in raw
    assert "$ref" in json.dumps(raw)
    assert len(raw["$defs"]) == 2


def test_resolve_refs_synthetic_nested_refs():
    # defs whose RESOLVED member carries another ref, and refs sitting inside
    # lists: both must resolve against the SAME defs map (the recursion
    # argument is the mutation target here)
    defs = {"A": {"type": "object", "properties": {"b": {"$ref": "#/$defs/B"}}}, "B": {"type": "x"}}
    out = vc._resolve_refs(
        {"props": {"$ref": "#/$defs/A"}, "list": [{"$ref": "#/$defs/B"}, 5], "$defs": defs}, defs
    )
    assert out == {
        "props": {"type": "object", "properties": {"b": {"type": "x"}}},
        "list": [{"type": "x"}, 5],
    }
    # a $ref node IS its target - siblings ride along never
    assert vc._resolve_refs({"$ref": "#/$defs/B", "extra": 1}, defs) == {"type": "x"}


def test_stop_reason_reads_both_wires_choice_first():
    # choice-level finish_reason wins over the body copy
    both = {
        "choices": [{"finish_reason": "length"}],
        "finish_reason": "stop",
    }
    assert vc._stop_reason_of(_resp(200, both)) == "length"
    # native wire: stop_type; compat third name: stop_reason
    assert vc._stop_reason_of(_resp(200, {"choices": [{"stop_type": "length"}]})) == "length"
    assert vc._stop_reason_of(_resp(200, {"choices": [{"stop_reason": "eos"}]})) == "eos"
    # body-level fallback
    assert vc._stop_reason_of(_resp(200, {"stop_type": "limit"})) == "limit"
    # the silence shapes: all read None - "the server did not say"
    assert vc._stop_reason_of(_resp(200, {"nope": 1})) is None
    assert vc._stop_reason_of(_resp(200, {"choices": []})) is None
    assert vc._stop_reason_of(_resp(200, {"choices": [{"no reason": 1}]})) is None
    assert vc._stop_reason_of(_resp(200, {"choices": [{"finish_reason": 7}]})) is None
    assert vc._stop_reason_of(_resp(200, {"choices": [{"finish_reason": ""}]})) is None
    assert vc._stop_reason_of(_resp(200, "not a dict")) is None
    assert vc._stop_reason_of(_resp(503, {"choices": [{"finish_reason": "length"}]})) is None


def test_is_box_rejects_strings_and_bools():
    assert vc.VlmClient._is_box([1, 2.5, 0, -3]) is True
    assert vc.VlmClient._is_box([True, 1, 2, 3]) is False
    assert vc.VlmClient._is_box(["1", 2, 3, 4]) is False
    assert vc.VlmClient._is_box([1, 2, 3]) is False
    assert vc.VlmClient._is_box(None) is False


def test_rank_for_budget_total_order():
    # highest confidence first; None confidence sorts last as -1.0, never
    # laundered upward; tie broken by LOWEST id first (via negation)
    assert vc.VlmClient._rank_for_budget({"confidence": 0.9, "id": 3}) == (0.9, -3)
    assert vc.VlmClient._rank_for_budget({"confidence": None, "id": 3}) == (-1.0, -3)
    assert vc.VlmClient._rank_for_budget({"id": 3}) == (-1.0, -3)
    assert vc.VlmClient._rank_for_budget({"confidence": "hi", "id": 3}) == (-1.0, -3)
    assert vc.VlmClient._rank_for_budget({"confidence": 0.5}) == (0.5, 0)
    assert vc.VlmClient._rank_for_budget({"confidence": 0.5, "id": None}) == (0.5, 0)
    rows = [
        {"id": 1, "confidence": 0.4},
        {"id": 2, "confidence": None},
        {"id": 3, "confidence": 0.9},
        {"id": 4, "confidence": 0.9},
        {"id": 5},
    ]
    assert [r["id"] for r in sorted(rows, key=vc.VlmClient._rank_for_budget, reverse=True)] == [
        3,
        4,
        1,
        2,
        5,
    ]


def test_image_token_reservation_scales_with_stills():
    c = _client({})
    one = VlmAssessRequest(image_paths=["/x/a.jpg"], context=dict(_CTX))
    three = VlmAssessRequest(image_paths=["/x/a.jpg", "/x/b.jpg", "/x/c.jpg"], context=dict(_CTX))
    assert c._image_token_reservation(one) == 1280
    assert c._image_token_reservation(three) == 3840
    assert c._image_token_reservation(one) == 1280


def test_init_state_and_breaker_config():
    reset_circuit_breaker_registry()
    c = vc.VlmClient(base_url="http://x:9// ", settings=_settings())
    # rstrip("/") ONLY - trailing spaces are the URL, the X is data
    assert c._base_url == "http://x:9// "
    assert c._build_info == ""
    assert c._served_model_id == ""
    assert c._enforced is None
    br = get_circuit_breaker("ai-vlm")
    assert br.config.failure_threshold == 5
    assert br.config.recovery_timeout == 60.0
    reset_circuit_breaker_registry()
    c2 = vc.VlmClient(base_url="/probe/", settings=_settings())
    assert c2._base_url == "/probe"
    c3 = vc.VlmClient(base_url="http://x/X", settings=_settings())
    assert c3._base_url == "http://x/X"
    # _app_calls on a PRODUCTION transport (None) reads the [] default,
    # never None and never an AttributeError
    assert c3._app_calls() == []


def test_served_provenance_before_probe():
    c = _client({})
    p = c._served_provenance()
    assert p.engine == c._settings.nemotron_verification_engine
    assert p.model_id == c._settings.vlm_model_id


_CTX = {"camera_id": "cam 1", "timestamp": "2026-09-25T11:00:00Z"}


def _req(paths, context=None, **kw):
    return VlmAssessRequest(image_paths=list(paths), context=dict(context or _CTX), **kw)


def test_wire_schema_is_the_flattened_contract():
    c = _client({})
    wire = c._wire_schema()
    assert c._wire_schema() is wire  # built once per client
    dump = json.dumps(wire)
    assert "$ref" not in dump and "$defs" not in dump
    assert "minLength" not in dump and "minimum" not in dump and "maximum" not in dump
    # the shape the grammar must reproduce is still COMPLETE
    props = wire["properties"]
    assert set(props) == {
        "verdict",
        "risk_score",
        "summary",
        "reasoning",
        "description",
        "criteria",
        "provenance",
    }
    assert props["criteria"]["items"]["properties"]["passed"]["type"] == "boolean"
    assert props["provenance"]["properties"]["model_id"]["type"] == "string"
    assert wire["required"] == [
        "verdict",
        "risk_score",
        "summary",
        "reasoning",
        "description",
        "criteria",
        "provenance",
    ]
    assert wire["additionalProperties"] is False


# ---------------------------------------------------------------------------
# images
# ---------------------------------------------------------------------------


def test_image_parts_success_data_uri_exact():
    files = _stills(1)
    root = str(Path(files[0]).parent)
    c = _client({}, foscam_base_path=root)
    # nosemgrep: path-traversal-open - stills the test itself wrote into its own mkdtemp root
    b64 = base64.b64encode(Path(files[0]).read_bytes()).decode("ascii")
    parts = c._image_parts(_req(files))
    assert parts == [{"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}}]


def test_image_parts_four_paths_all_embedded():
    files = _stills(4)
    root = str(Path(files[0]).parent)
    c = _client({}, foscam_base_path=root)
    parts = c._image_parts(_req(files))
    assert len(parts) == 4
    assert parts[2]["image_url"]["url"] == (
        # nosemgrep: path-traversal-open - stills the test itself wrote into its own mkdtemp root
        "data:image/jpeg;base64," + base64.b64encode(Path(files[2]).read_bytes()).decode()
    )


def test_image_parts_traversal_relative_refused_before_read():
    files = _stills(1)
    root = str(Path(files[0]).parent)
    c = _client({}, foscam_base_path=root)
    # the FULL message, the ROOT INTERPOLATED: a refusal that names
    # str(None) instead of the root is still a refusal - only the exact
    # string pins the guard's own evidence
    with pytest.raises(vc.VlmImageError) as exc:
        c._image_parts(_req(["../../etc/passwd"]))
    assert str(exc.value) == (
        f"image path '../../etc/passwd' resolves outside the capture root {root!r}; "
        "refused before any read (privacy + traversal guard)"
    )
    # the guard is the raise: the same client happily embeds a real still
    assert c._image_parts(_req(files)) != []


def test_image_parts_absolute_outside_root_refused():
    files = _stills(1)
    root = str(Path(files[0]).parent)
    c = _client({}, foscam_base_path=root)
    outside = Path("/etc/hostname")
    if outside.is_file():
        with pytest.raises(vc.VlmImageError, match="resolves outside the capture root"):
            c._image_parts(_req([str(outside)]))
    # absolute INSIDE the root is the else arm of the same resolve
    assert c._image_parts(_req(files)) != []


def test_image_parts_symlink_escape_refused():
    files = _stills(1)
    root = Path(files[0]).parent
    link = root / "escape.png"
    try:
        link.symlink_to(Path("/etc/hostname"))
    except OSError:  # pragma: no cover - filesystem without symlinks
        return
    c = _client({}, foscam_base_path=str(root))
    try:
        with pytest.raises(vc.VlmImageError, match="resolves outside the capture root"):
            c._image_parts(_req(["escape.png"]))
    finally:
        link.unlink(missing_ok=True)


def test_image_parts_missing_file():
    files = _stills(1)
    root = str(Path(files[0]).parent)
    c = _client({}, foscam_base_path=root)
    # pinned DOWN TO THE RESOLVED PATH (the guard shows the caller their
    # relative name resolved INTO the root and still missed - the value
    # is the evidence)
    with pytest.raises(vc.VlmImageError) as exc:
        c._image_parts(_req(["ghost.png"]))
    assert str(exc.value) == f"image file not found: {root + '/ghost.png'!r}"
    assert c._image_parts(_req(files)) != []


def test_image_parts_suffix_allowlist_exact_messages():
    files = _stills(1)
    root = Path(files[0]).parent
    (root / "notes.txt").write_text("hi", encoding="utf-8")
    (root / "noext").write_bytes(b"x")
    (root / "clip.mp4").write_bytes(b"\x00\x00\x00\x18ftypmp42fake")
    c = _client({}, foscam_base_path=str(root))
    with pytest.raises(vc.VlmImageError, match=r"type '\.txt', not a still the vlm path"):
        c._image_parts(_req(["notes.txt"]))
    with pytest.raises(vc.VlmImageError, match=r"type '\(none\)', not a still"):
        c._image_parts(_req(["noext"]))
    # the video kinds are named by their container, never laundered image/jpeg
    with pytest.raises(vc.VlmImageError, match="a video/mp4 container, not a still"):
        c._image_parts(_req(["clip.mp4"]))
    # .jpeg rides the jpeg mime (suffix.lower() -> IMAGE_MIME_TYPES)
    jpg = root / "b.JPEG"
    jpg.write_bytes(b"\xff\xd8\xff\xe0jpeg")
    parts = c._image_parts(_req(["b.JPEG"]))
    assert parts[0]["image_url"]["url"] == (
        "data:image/jpeg;base64," + base64.b64encode(jpg.read_bytes()).decode()
    )


def test_image_parts_byte_limit_boundary():
    files = _stills(1)
    root = str(Path(files[0]).parent)
    exact = Path(files[0]).stat().st_size
    c = _client({}, foscam_base_path=root)
    # the guard is `>`: exactly the limit is accepted
    c._settings = c._settings.model_copy(update={"vlm_max_image_bytes": exact})
    assert c._image_parts(_req(files)) != []
    # one byte over refuses BEFORE the read, naming both numbers
    c._settings = c._settings.model_copy(update={"vlm_max_image_bytes": exact - 1})
    with pytest.raises(
        vc.VlmImageError,
        match=rf"is {exact} bytes, over the vlm_max_image_bytes limit of {exact - 1}",
    ):
        c._image_parts(_req(files))


# ---------------------------------------------------------------------------
# prompt rendering (§4: the whole string, never a fragment)
# ---------------------------------------------------------------------------


def _pixel_sentence(sizes):
    frame = f"its {' or '.join(sizes)} source frame" if sizes else "its source frame"
    return (
        f"A row's bbox is [x, y, width, height] in pixels of {frame}: "
        "the top-left corner, then the box size. "
    )


def _guidance(box2d=False, sizes=None, pixel=True, fdi=False):
    convention = (_BOX2D if box2d else "") + (_pixel_sentence(sizes) if pixel else "")
    return convention + _BOX_TAIL + (_FRAME_NOTE if fdi else "")


def _expected_prompt(
    rows_json,
    time_str,
    zones="none",
    crossing="False",
    guidance="",
    household="{}",
    specialist="{}",
):
    return (
        _SYSTEM
        + "\n\n"
        + "Camera: cam 1\n"
        + f"Time: {time_str}\n"
        + f"Zones: {zones} (crossing: {crossing})\n"
        + guidance
        + f"Detections: {rows_json}\n"
        + f"Household context: {household}\n"
        + "Specialist outputs (faces/plates/re-ID; these are detector evidence, "
        + f"not yours to invent): {specialist}\n"
    )


def _real_stills(specs, corrupt=()):
    """specs: (name, w, h) saved as real JPEGs; corrupt names get junk."""
    root = Path(tempfile.mkdtemp())
    files = []
    for name, w, h in specs:
        from PIL import Image

        im = Image.new("RGB", (w, h))
        im.save(root / name, format="JPEG")
        files.append(str(root / name))
    for name in corrupt:
        (root / name).write_bytes(b"not an image at all")
        files.append(str(root / name))
    return files


def test_render_prompt_minimal_exact_string():
    c = _client({})
    req = _req(["/frames/a.jpg"])
    out = c._render_prompt([], req)
    assert out == _expected_prompt("[]", "2026-09-25T11:00:00Z")
    # the no-rows case carries NO box guidance at all (the "" early return)
    assert c._box_guidance([], req) == ""


def test_render_prompt_full_context_exact_string():
    c = _client({})
    req = _req(
        ["/frames/a.jpg"],
        context={
            "camera_id": "cam 1",
            "timestamp": "2026-09-25T11:00:00Z",
            "zones": ["driveway", "gate"],
            "zone_crossing": True,
            "household": {"resident_names": ["Ana"]},
            "specialist_outputs": {"faces": "no match"},
        },
    )
    rows = [{"id": 7, "label": "person", "confidence": 0.8}]
    undo = _pil_open_stub({"a.jpg": (200, 100)})
    try:
        out = c._render_prompt(rows, req)
    finally:
        undo()
    assert out == _expected_prompt(
        json.dumps(rows, ensure_ascii=False),
        "2026-09-25T11:00:00Z",
        zones="driveway, gate",
        crossing="True",
        guidance=_guidance(sizes=["200x100"]),
        household=json.dumps({"resident_names": ["Ana"]}, ensure_ascii=False),
        specialist=json.dumps({"faces": "no match"}, ensure_ascii=False),
    )


def test_render_prompt_timezone_drops_detected_at_and_renders_local_time():
    c = _client({}, camera_timezone="America/New_York")
    req = _req(["/frames/a.jpg"])
    rows = [{"id": 7, "detected_at": "2026-09-25T11:00:01Z", "label": "person"}]
    undo = _pil_open_stub({"a.jpg": (200, 100)})
    try:
        out = c._render_prompt(rows, req)
    finally:
        undo()
    rendered_rows = [{"label": "person", "id": 7}]
    assert out == _expected_prompt(
        json.dumps([{"id": 7, "label": "person"}], ensure_ascii=False),
        "2026-09-25 07:00:00 local (America/New_York, UTC-04:00)",
        guidance=_guidance(sizes=["200x100"]),
    )
    # the drop is RENDERED-COPY only - the snapshot rows keep detected_at
    assert rows[0]["detected_at"] == "2026-09-25T11:00:01Z"
    assert rendered_rows[0]["id"] == 7


def test_render_prompt_frame_ids_map_and_null_rows():
    c = _client({})
    req = _req(
        ["/frames/a.jpg", "/frames/b.jpg"],
        frame_detection_ids=[[1], [2, 3]],
    )
    rows = [{"id": 3, "label": "car"}, {"id": 99, "label": "leaf"}]
    undo = _pil_open_stub({"a.jpg": (200, 100), "b.jpg": (200, 100)})
    try:
        out = c._render_prompt(rows, req)
    finally:
        undo()
    assert out == _expected_prompt(
        json.dumps(
            [{"id": 3, "label": "car", "frame": 2}, {"id": 99, "label": "leaf", "frame": None}],
            ensure_ascii=False,
        ),
        "2026-09-25T11:00:00Z",
        guidance=_guidance(sizes=["200x100"], fdi=True),
    )


def test_render_prompt_grounds_boxes_to_0_1000_corners():
    c = _client({})
    req = _req(["/frames/a.jpg", "/frames/b.jpg"])
    rows = [
        {"id": 1, "bbox": [20, 10, 100, 50]},
        {"id": 2, "bbox": [300, 10, 50, 200]},  # clamps at 1000
        {"id": 3, "bbox": [-10, 5, 20, 10]},  # clamps at 0
        {"id": 4, "bbox": [None, 1, 2, 3]},  # not a box: pixels ride along
        {"id": 5},  # no box at all
    ]
    undo = _pil_open_stub({"a.jpg": (200, 100), "b.jpg": (200, 100)})
    try:
        out = c._render_prompt(rows, req)
    finally:
        undo()
    assert out == _expected_prompt(
        json.dumps(
            [
                {"id": 1, "bbox_2d": [100, 100, 600, 600]},
                {"id": 2, "bbox_2d": [1000, 100, 1000, 1000]},
                {"id": 3, "bbox_2d": [0, 50, 50, 150]},
                {"id": 4, "bbox": [None, 1, 2, 3]},
                {"id": 5},
            ],
            ensure_ascii=False,
        ),
        "2026-09-25T11:00:00Z",
        guidance=_guidance(box2d=True, sizes=["200x100"]),
    )


def test_render_prompt_frame_key_selects_scale_shared_none_when_mixed():
    c = _client({})
    req = _req(["/frames/big.jpg", "/frames/small.jpg"])
    rows = [
        {"id": 1, "bbox": [10, 10, 20, 20], "frame": 2},  # small 100x50 scale
        {"id": 2, "bbox": [10, 10, 20, 20]},  # mixed sizes -> shared None
    ]
    undo = _pil_open_stub({"big.jpg": (200, 100), "small.jpg": (100, 50)})
    try:
        out = c._render_prompt(rows, req)
    finally:
        undo()
    assert out == _expected_prompt(
        json.dumps(
            [
                {"id": 1, "bbox_2d": [100, 200, 300, 600], "frame": 2},
                {"id": 2, "bbox": [10, 10, 20, 20]},
            ],
            ensure_ascii=False,
        ),
        "2026-09-25T11:00:00Z",
        guidance=_guidance(box2d=True, sizes=["200x100", "100x50"]),
    )


def test_box_guidance_unreadable_frames_says_source_frame():
    c = _client({})
    req = _req(["/frames/x.jpg"])
    rows = [{"id": 1, "bbox_2d": [1, 2, 3, 4]}, {"id": 2, "bbox": [1, 2, 3, 4]}]
    undo = _pil_open_stub({}, raises=("x.jpg",))
    try:
        guidance = c._box_guidance(c._grounded_boxes(rows, req), req)
    finally:
        undo()
    assert guidance == _guidance(box2d=True, sizes=[])
    # both clauses stand side by side, verbatim
    assert guidance == (_BOX2D + _pixel_sentence([]) + _BOX_TAIL)


def test_render_prompt_non_ascii_is_never_escaped():
    c = _client({})
    req = _req(
        ["/frames/a.jpg"],
        context={
            "camera_id": "cam 1",
            "timestamp": "2026-09-25T11:00:00Z",
            "household": {"note": "Haus §3"},
            "specialist_outputs": {"faces": "Ärger"},
        },
    )
    rows = [{"id": 1, "label": "宠物"}]
    undo = _pil_open_stub({"a.jpg": (200, 100)})
    try:
        out = c._render_prompt(rows, req)
    finally:
        undo()
    assert "\\u5ba0\\u7269" not in out and "宠物" in out
    assert out == _expected_prompt(
        json.dumps(rows, ensure_ascii=False),
        "2026-09-25T11:00:00Z",
        guidance=_guidance(sizes=["200x100"]),
        household=json.dumps({"note": "Haus §3"}, ensure_ascii=False),
        specialist=json.dumps({"faces": "Ärger"}, ensure_ascii=False),
    )


def test_frame_dims_and_sizes_real_pil():
    files = _real_stills(
        [("a.jpg", 160, 80), ("b.jpg", 160, 80), ("c.jpg", 200, 100)], corrupt=("d.jpg",)
    )
    req = _req(files)
    dims = vc.VlmClient._frame_dims(req)
    assert dims == [(160, 80), (160, 80), (200, 100), None]
    assert vc.VlmClient._frame_sizes(req) == ["160x80", "200x100"]  # distinct, in order
    # a ValueError from the opener is the OTHER caught arm
    nul = _req(["a\x00b.jpg"])
    assert vc.VlmClient._frame_dims(nul) == [None]
    assert vc.VlmClient._frame_sizes(nul) == []


def test_grounded_boxes_scale_is_one_based_frame_or_shared():
    files = _real_stills([("big.jpg", 200, 100), ("small.jpg", 100, 50)])
    c = _client({})
    req = _req(files)
    rows = [
        {"id": 1, "bbox": [10, 10, 20, 20], "frame": 2},
        {"id": 2, "bbox": [10, 10, 20, 20], "frame": 0},  # out of range low
        {"id": 3, "bbox": [10, 10, 20, 20], "frame": 9},  # out of range high
        {"id": 4, "bbox": [10, 10, 20, 20], "frame": "2"},  # not an int
    ]
    out = c._grounded_boxes(rows, req)
    assert out[0]["bbox_2d"] == [100, 200, 300, 600]
    assert out[0].get("bbox") is None
    # mixed sizes -> shared None -> unframed rows keep their pixels
    for row in out[1:]:
        assert row["bbox"] == [10, 10, 20, 20] and "bbox_2d" not in row
    # a single shared size IS the shared scale for unframed rows
    same = _real_stills([("s1.jpg", 100, 100), ("s2.jpg", 100, 100)])
    out2 = c._grounded_boxes([{"id": 9, "bbox": [5, 5, 10, 10]}], _req(same))
    assert out2[0]["bbox_2d"] == [50, 50, 150, 150]


# ---------------------------------------------------------------------------
# §5 prompt fitting (token budget)
# ---------------------------------------------------------------------------


def _counter_stub():
    """Swap the counter vlm_client imported INTO its own namespace: one
    token per four characters, so every boundary below is arithmetic the
    test computes itself, never a mirror of the module."""
    return _module_stub(
        {
            "backend.services.vlm_client": {
                "get_token_counter": lambda: type(
                    "C", (), {"count_tokens": staticmethod(lambda t: len(t) // 4)}
                )()
            }
        }
    )


def _fit_rows(n):
    # `note` padded by id so every row json is the SAME length (asserted by
    # _Fit): the Detections line then grows by exactly PW + 1 per row
    return [{"id": i, "confidence": 100 + i, "note": "x" * (96 - len(str(i)))} for i in range(n)]


def _marker(kept, omitted):
    return (
        f"[{omitted} further detections were omitted from this list to fit the "
        f"model's context budget; the {kept} listed are the "
        "highest-confidence rows and are the ones the attached frame(s) "
        "were selected around]\n"
    )


class _Fit:
    """Deterministic fit environment. L0 (the empty-rows render minus its
    ``[]``) and PW (one row's rendered width) are measured from the
    renderer's OWN output; the growth model (2 + kept*PW + kept-1 chars for
    the list) is asserted against a 3-row render here."""

    def __init__(self, c, req, rows):
        self.c = c
        self.req = req
        self.rows = rows
        assert len({len(json.dumps(r, ensure_ascii=False)) for r in rows}) == 1
        self.rj = len(json.dumps(rows[0], ensure_ascii=False))  # one row's json
        empty = c._render_prompt([], req)
        one = c._render_prompt(rows[:1], req)
        two = c._render_prompt(rows[:2], req)
        self.E = len(empty)
        # G: everything a NON-EMPTY list adds besides the rows themselves -
        # the box-guidance clause (rows without bbox_2d make it appear) and
        # the "[]" -> "[...]" bracket delta. Measured, never assumed.
        self.G = len(one) - self.E - 2 - self.rj
        assert len(two) - len(one) == self.rj + 2  # the ", " join

    def body_len(self, kept):
        # json joins list items with ", " - two chars per extra row
        return self.E + (0 if kept == 0 else self.G + 2 + kept * self.rj + 2 * (kept - 1))

    def char_len(self, kept, omitted):
        return self.body_len(kept) + (0 if omitted == 0 else len(_marker(kept, omitted)))

    def served(self, kept, omitted):
        return math.ceil((self.char_len(kept, omitted) // 4) * 1.5)

    def window(self, kept, total, frames=1, buf=0):
        # budget terms read from the module (26b900bc moved the assess cap to
        # 2048; the literals here were pinned at the old 1024 and broke)
        return self.served(kept, total - kept) + vc._ASSESS_MAX_TOKENS + vc._IMAGE_TOKENS_PER_FRAME * frames + buf

    def expected(self, kept, total):
        # survivors are the ranked top-kept (own sort - the rank function is
        # pinned in test_rank_for_budget_total_order, not reused from the
        # module here)
        ranked = sorted(self.rows, key=lambda r: (r["confidence"], -r["id"]), reverse=True)
        text = self.c._render_prompt(ranked[:kept], self.req)
        if total - kept > 0:
            text += _marker(kept, total - kept)
        return text


def _fit_env(n, frames=1, window=None):
    undo = _counter_stub()
    c = _client({}, vlm_context_window=window or 60000)
    rows = _fit_rows(n)
    paths = [f"/f/{i}.jpg" for i in range(frames)]
    req = _req(paths, context=dict(_CTX, detections=rows))
    return c, req, rows, _Fit(c, req, rows), undo


def test_fitted_prompt_all_fit_is_the_unmodified_render():
    c, req, rows, fit, undo = _fit_env(12)
    try:
        c._settings = c._settings.model_copy(update={"vlm_context_window": fit.window(12, 12)})
        text, truncated = c._fitted_prompt(req)
        assert truncated is False
        assert text == c._render_prompt(rows, req)
        assert "omitted" not in text
        assert c.prompt_text(req) == text  # the ONE path the analyzer stores
    finally:
        undo()


def test_fitted_prompt_boundary_keeps_exactly_the_fitting_prefix():
    c, req, rows, fit, undo = _fit_env(12)
    try:
        # the window sized for 10 kept: by the module's OWN arithmetic 11 is
        # richer than the budget and 10 exactly consumes it (the `<=` at the
        # fit test is what makes 10 fit here)
        cw = fit.window(10, 12)
        assert fit.served(11, 1) > cw - vc._ASSESS_MAX_TOKENS - vc._IMAGE_TOKENS_PER_FRAME >= fit.served(10, 2)
        c._settings = c._settings.model_copy(update={"vlm_context_window": cw})
        text, truncated = c._fitted_prompt(req)
        assert truncated is True
        assert text == fit.expected(10, 12)
        # survivors are the RANKED top-10 (highest confidence = highest id);
        # the two omitted rows are the low-confidence tail
        assert '"id": 1,' not in text and '"id": 0,' not in text
        assert '"id": 11,' in text and '"id": 2,' in text
    finally:
        undo()


def test_fitted_prompt_binary_search_reaches_the_last_and_first_slot():
    # kept == n-1 and kept == 1 of 2: the two ends of the search that a
    # mid-bump or a hi/lo swap lands one off
    # kept == n-1 is DOMINATED in this batch shape - the marker costs more
    # than the row it replaces - so the last reachable search slot is n-2.
    c, req, rows, fit, undo = _fit_env(13)
    try:
        cw = fit.window(11, 13)
        assert fit.served(12, 1) > cw - vc._ASSESS_MAX_TOKENS - vc._IMAGE_TOKENS_PER_FRAME >= fit.served(11, 2)
        c._settings = c._settings.model_copy(update={"vlm_context_window": cw})
        text, truncated = c._fitted_prompt(req)
        assert truncated is True
        assert text == fit.expected(11, 13)
    finally:
        undo()
    # (kept == 1 of 2 is likewise dominated - the marker alone out-costs the
    # row - so the first reachable slot is 1 of 3: dropping a row saves ~51
    # served tokens while the marker's digits barely move)
    c2, req2, rows2, fit2, undo2 = _fit_env(3)
    try:
        cw2 = fit2.window(1, 3)
        assert fit2.served(2, 1) > cw2 - vc._ASSESS_MAX_TOKENS - vc._IMAGE_TOKENS_PER_FRAME >= fit2.served(1, 2)
        c2._settings = c2._settings.model_copy(update={"vlm_context_window": cw2})
        text, truncated = c2._fitted_prompt(req2)
        assert truncated is True
        assert text == fit2.expected(1, 3)
    finally:
        undo2()


def test_fitted_prompt_marker_only_when_nothing_fits():
    # kept == 0: `if omitted <= 0` is NOT taken - the empty row list plus the
    # marker IS the prompt (the model is told, never left to infer)
    c, req, rows, fit, undo = _fit_env(3)
    try:
        cw = fit.window(0, 3)
        assert fit.served(1, 2) > cw - vc._ASSESS_MAX_TOKENS - vc._IMAGE_TOKENS_PER_FRAME >= fit.served(0, 3)
        c._settings = c._settings.model_copy(update={"vlm_context_window": cw})
        text, truncated = c._fitted_prompt(req)
        assert truncated is True
        assert text == c._render_prompt([], req) + _marker(0, 3)
        assert "Detections: []" in text
    finally:
        undo()


def test_fitted_budget_is_window_less_assess_budget_less_reservation():
    # the SAME batch under the SAME window flips on the image reservation
    # alone: one more still reserves 1280 served tokens - the rows cannot
    # pay that back
    c1, req1, rows, fit1, undo = _fit_env(12, frames=1)
    try:
        cw = fit1.window(2, 12, frames=1)  # 2 of 12 fit with one still
        assert fit1.served(3, 9) > cw - vc._ASSESS_MAX_TOKENS - vc._IMAGE_TOKENS_PER_FRAME >= fit1.served(2, 10)
        c1._settings = c1._settings.model_copy(update={"vlm_context_window": cw})
        text, truncated = c1._fitted_prompt(req1)
        assert truncated is True and text == fit1.expected(2, 12)
    finally:
        undo()
    c2, req2, _r2, _f2, undo2 = _fit_env(12, frames=2, window=cw)
    try:
        text2, truncated2 = c2._fitted_prompt(req2)
        assert truncated2 is True
        # 1280 tokens richer in reservation: nothing fits any more - the
        # marker names all 12
        assert text2.endswith(_marker(0, 12)) and "Detections: []" in text2
    finally:
        undo2()


# ---------------------------------------------------------------------------
# §3 enforcement probe
# ---------------------------------------------------------------------------


def _probe_env(handlers, **settings_over):
    """Client on one real still whose probe will run: returns
    (client, transport, still_path, undo_metrics, seen_metrics, undo_logs,
    records)."""
    files = _stills(1)
    root = str(Path(files[0]).parent)
    seen: list = []
    undo_m = _module_stub(_metric_stub(seen))
    records, undo_l = _logs()
    c = _client(handlers, foscam_base_path=root, **settings_over)
    parts = c._image_parts(_req(files))
    return c, c._transport, files[0], parts, seen, undo_m, records, undo_l


def _probe_call(transport):
    chats = [c for c in transport.calls if c["path"] == "/v1/chat/completions"]
    return chats[0]


def _data_uri(path):
    # nosemgrep: path-traversal-open - callers pass only _stills()-created paths
    return "data:image/jpeg;base64," + base64.b64encode(Path(path).read_bytes()).decode()


def test_probe_disabled_makes_no_request_at_all():
    c, t, path, parts, seen, undo_m, records, undo_l = _probe_env(
        {}, vlm_enforcement_probe_enabled=False
    )
    try:
        asyncio.run(c._probe_enforcement(parts))
        assert t.calls == []
        assert c._enforced is None and seen == []
    finally:
        undo_m()
        undo_l()


def test_probe_enforced_exact_body_state_and_log():
    c, t, path, parts, seen, undo_m, records, undo_l = _probe_env(
        {"/props": [_echo_handler()], "/v1/chat/completions": [_chat_strict()]}
    )
    try:
        asyncio.run(c._probe_enforcement(parts))
    finally:
        undo_m()
        undo_l()
    assert c._enforced is True
    assert c._build_info == _BUILD
    assert c._served_model_id == ""  # /props answered without model_path
    assert t.calls[0]["method"] == "GET" and t.calls[0]["path"] == "/props"
    call = _probe_call(t)
    assert call["method"] == "POST"
    observed_schema = call["body"]["response_format"]["json_schema"]["schema"]
    nonce = observed_schema["properties"]["probe_const"]["const"]
    assert nonce and isinstance(nonce, str)
    probe_schema, _n2 = build_probe_schema(c._wire_schema(), nonce=nonce)
    assert observed_schema == probe_schema  # the wire schema + this nonce
    assert observed_schema["required"][-1] == "probe_const"
    assert call["body"] == {
        "messages": [
            {
                "role": "user",
                "content": [*parts, {"type": "text", "text": _PROBE_TEXT}],
            }
        ],
        "temperature": 0.0,
        "max_tokens": vc._PROBE_MAX_TOKENS,
        "response_format": {
            "type": "json_schema",
            "json_schema": {"name": "vlm_probe", "schema": observed_schema},
        },
    }
    assert seen == []
    assert _log_sig(records, ("base_url", "build_info")) == [
        (
            "INFO",
            "vlm enforcement probe: ENFORCED",
            (),
            ("http://fake-vlm:8098", _BUILD),
            None,
        )
    ]


def test_probe_uses_only_the_first_still():
    files = _stills(2)
    root = str(Path(files[0]).parent)
    records, undo_l = _logs()
    c = _client(
        {"/props": [_echo_handler()], "/v1/chat/completions": [_chat_strict()]},
        foscam_base_path=root,
    )
    try:
        parts = c._image_parts(_req(files))
        assert len(parts) == 2
        asyncio.run(c._probe_enforcement(parts))
        content = _probe_call(c._transport)["body"]["messages"][0]["content"]
        assert content[0] == parts[0] and len(content) == 2
        assert content[1] == {"type": "text", "text": _PROBE_TEXT}
    finally:
        undo_l()


def test_probe_state_short_circuits_the_second_call():
    c, t, path, parts, seen, undo_m, records, undo_l = _probe_env(
        {"/props": [_echo_handler()], "/v1/chat/completions": [_chat_strict()]}
    )
    try:
        asyncio.run(c._probe_enforcement(parts))
        first = len(t.calls)
        asyncio.run(c._probe_enforcement(parts))
        assert len(t.calls) == first  # ENFORCED is the only cached verdict
    finally:
        undo_m()
        undo_l()


def test_probe_props_without_build_info_still_enforces_with_empty_build():
    # /props answered (200) but the key is ABSENT: the read-side default is
    # "" - not None, not "XXXX", not a KeyError out of the props block.
    # The default reaches the ENFORCED log line's extra and the engine
    # string, so both pin it.
    files = _stills(1)
    root = str(Path(files[0]).parent)
    records, undo_l = _logs()
    c = _client(
        {"/props": [lambda _body: (200, {})], "/v1/chat/completions": [_chat_strict()]},
        foscam_base_path=root,
    )
    try:
        asyncio.run(c._probe_enforcement(c._image_parts(_req(files))))
        assert c._enforced is True
        assert c._build_info == ""
        assert _log_sig(records, ("base_url", "build_info")) == [
            ("INFO", "vlm enforcement probe: ENFORCED", (), ("http://fake-vlm:8098", ""), None)
        ]
        assert c._served_provenance().engine == "llama.cpp"  # falsy -> bare label
    finally:
        undo_l()


def test_probe_absent_build_fails_closed_against_a_pin():
    # the polar mate: with a pinned build the SAME empty default must
    # mismatch (None or "XXXX" here could only survive a truthiness test -
    # the message shows the repr, and the probe must NOT reach ENFORCED)
    files = _stills(1)
    root = str(Path(files[0]).parent)
    seen: list = []
    undo_m = _module_stub(_metric_stub(seen))
    spy = _SpyBreaker()
    undo_b = _module_stub(
        {"backend.services.vlm_client": {"get_circuit_breaker": lambda _name, _cfg=None: spy}}
    )
    c = _client(
        {"/props": [lambda _body: (200, {})]},
        foscam_base_path=root,
        vlm_required_build="b7972",
    )
    c._breaker = spy
    try:
        try:
            asyncio.run(c._probe_enforcement(c._image_parts(_req(files))))
            raise AssertionError("must raise")
        except ConstrainedDecodingNotEnforced as exc:
            assert str(exc) == (
                "endpoint build_info '' lacks the pinned 'b7972' - "
                "enforcement was proven against a different build (S-2). Fail closed."
            )
        assert c._enforced is None
        assert [(k["method"], k["path"]) for k in c._transport.calls] == [("GET", "/props")]
        assert spy.calls == [("failure",)]
        assert seen == [("pipeline_error", "vlm_probe_build_mismatch")]
    finally:
        undo_b()
        undo_m()


def test_probe_build_pin_must_match_not_merge():
    # `required and required not in build` -> `required or ...` is only
    # distinguishable on a SATISFIED pin: the and-form enforces, the or-
    # form refuses its own match ("" is a substring of every string, so
    # `required or not-in` is True for the empty pin too - the no-pin
    # renders of this file cannot tell the two formulas apart).
    c, _t, _path, _parts, _seen, undo_m, records, undo_l = _probe_env(
        {"/props": [_echo_handler()], "/v1/chat/completions": [_chat_strict()]},
        vlm_required_build=_BUILD,
    )
    try:
        asyncio.run(c._probe_enforcement(_parts))
        assert c._enforced is True
        assert c._build_info == _BUILD
        assert _log_sig(records, ("base_url", "build_info")) == [
            ("INFO", "vlm enforcement probe: ENFORCED", (), ("http://fake-vlm:8098", _BUILD), None)
        ]
    finally:
        undo_m()
        undo_l()


def test_probe_runs_the_grammar_once_even_under_concurrency():
    # the lock-held inner double-check IS load-bearing: two callers meet a
    # never-proven client at the same time. The second arrives while the
    # first is still inside its /props GET (the transport pauses there) -
    # before _enforced is set, so the inner check is what must stop it.
    # With that check mutated away (the `is True` -> `is False` family)
    # b runs its own props+chat and the probe fires TWICE.
    started = asyncio.Event()
    release = asyncio.Event()
    transport = _PausingTransport(
        {"/props": [_echo_handler()], "/v1/chat/completions": [_chat_strict()]},
        pause_path="/props",
        started=started,
        release=release,
    )
    files = _stills(1)
    root = str(Path(files[0]).parent)
    c = _client({}, foscam_base_path=root)
    c._transport = transport
    try:

        async def _scenario():
            a = asyncio.create_task(c._probe_enforcement([]))
            # the first caller is paused INSIDE its /props GET - before
            # _enforced is set - so it cannot serve the second one
            await asyncio.wait_for(started.wait(), 5)
            b = asyncio.create_task(c._probe_enforcement([]))
            await asyncio.sleep(0.05)  # b passes the outer gate, waits on the lock
            release.set()
            await asyncio.wait_for(asyncio.gather(a, b), 5)

        asyncio.run(_scenario())
        assert c._enforced is True
        chats = [k for k in transport.calls if k["path"] == "/v1/chat/completions"]
        props = [k for k in transport.calls if k["path"] == "/props"]
        assert len(chats) == 1  # the double-check ate the second probe
        assert len(props) == 1  # b never even re-read /props
    finally:
        release.set()


def test_probe_props_unreachable_is_inconclusive_and_feeds_breaker():
    files = _stills(1)
    root = str(Path(files[0]).parent)
    seen: list = []
    undo_m = _module_stub(_metric_stub(seen))
    spy = _SpyBreaker()
    undo_b = _module_stub(
        {"backend.services.vlm_client": {"get_circuit_breaker": lambda _name, _cfg=None: spy}}
    )
    c = _client({}, foscam_base_path=root)  # no /props handler: transport refuses
    try:
        try:
            asyncio.run(c._probe_enforcement(c._image_parts(_req(files))))
            raise AssertionError("must raise")
        except ConstrainedDecodingNotEnforced as exc:
            assert exc.verdict == "inconclusive"
            assert str(exc).startswith("vlm /props unreachable (")
            assert "cannot verify build before trusting constrained decoding" in str(exc)
        assert c._enforced is None
        assert spy.calls == [("failure",)]
        assert seen == [("pipeline_error", "vlm_probe_props_unreachable")]
    finally:
        undo_b()
        undo_m()


def test_probe_build_mismatch_is_inconclusive():
    files = _stills(1)
    root = str(Path(files[0]).parent)
    seen: list = []
    undo_m = _module_stub(_metric_stub(seen))
    spy = _SpyBreaker()
    undo_b = _module_stub(
        {"backend.services.vlm_client": {"get_circuit_breaker": lambda _name, _cfg=None: spy}}
    )
    c = _client(
        {"/props": [_echo_handler(build_info="b9999-deadbeef")]},
        foscam_base_path=root,
        vlm_required_build="b7972",
    )
    c._breaker = spy
    try:
        parts = c._image_parts(_req(files))
        try:
            asyncio.run(c._probe_enforcement(parts))
            raise AssertionError("must raise")
        except ConstrainedDecodingNotEnforced as exc:
            assert exc.verdict == "inconclusive"
            assert str(exc) == (
                "endpoint build_info 'b9999-deadbeef' lacks the pinned 'b7972' - "
                "enforcement was proven against a different build (S-2). Fail closed."
            )
        # the pin check ran BEFORE any probe request: only /props was called
        assert [(k["method"], k["path"]) for k in c._transport.calls] == [("GET", "/props")]
        assert c._build_info == "b9999-deadbeef"
        assert spy.calls == [("failure",)]
        assert seen == [("pipeline_error", "vlm_probe_build_mismatch")]
    finally:
        undo_b()
        undo_m()


def test_probe_read_serves_the_model_id_into_provenance():
    files = _stills(1)
    root = str(Path(files[0]).parent)
    records, undo_l = _logs()
    c = _client(
        {
            "/props": [_echo_handler(model_path="/models/Qwen3VL-8B-Instruct.gguf")],
            "/v1/chat/completions": [_chat_strict()],
        },
        foscam_base_path=root,
    )
    try:
        asyncio.run(c._probe_enforcement(c._image_parts(_req(files))))
        assert c._served_model_id == "Qwen3VL-8B-Instruct"
        p = c._served_provenance()
        assert p.engine == f"llama.cpp@{_BUILD}"
        assert p.model_id == "Qwen3VL-8B-Instruct"
    finally:
        undo_l()


def test_probe_prose_reply_is_ignored_verdict():
    files = _stills(1)
    root = str(Path(files[0]).parent)
    seen: list = []
    undo_m = _module_stub(_metric_stub(seen))
    spy = _SpyBreaker()
    undo_b = _module_stub(
        {"backend.services.vlm_client": {"get_circuit_breaker": lambda _name, _cfg=None: spy}}
    )
    c = _client(
        {"/props": [_echo_handler()], "/v1/chat/completions": [_chat_prose()]},
        foscam_base_path=root,
    )
    c._breaker = spy
    try:
        try:
            asyncio.run(c._probe_enforcement(c._image_parts(_req(files))))
            raise AssertionError("must raise")
        except ConstrainedDecodingNotEnforced as exc:
            assert exc.verdict == "ignored"
            assert str(exc) == (
                "vlm endpoint accepted response_format.json_schema but the reply "
                f"did not echo the probe const (build {_BUILD!r}, stop='stop') - "
                "constrained decoding is not enforced here. Fail closed."
            )
        assert c._enforced is None  # never cached
        assert spy.calls == [("failure",)]
        assert seen == [("pipeline_error", "vlm_probe_not_enforced")]
    finally:
        undo_b()
        undo_m()


def test_probe_grammar_honoring_but_dropping_const_is_ignored():
    # the const is REQUIRED and first-pinned in the grammar; a server that
    # fills everything else and skips it proves nothing was enforced
    files = _stills(1)
    root = str(Path(files[0]).parent)
    c = _client(
        {
            "/props": [_echo_handler()],
            "/v1/chat/completions": [_chat_strict(drop_const=True)],
        },
        foscam_base_path=root,
    )
    records, undo_l = _logs()
    try:
        try:
            asyncio.run(c._probe_enforcement(c._image_parts(_req(files))))
            raise AssertionError("must raise")
        except ConstrainedDecodingNotEnforced as exc:
            assert exc.verdict == "ignored"
    finally:
        undo_l()


def test_probe_length_stop_is_budget_exhausted_not_a_breaker_failure():
    files = _stills(1)
    root = str(Path(files[0]).parent)
    seen: list = []
    undo_m = _module_stub(_metric_stub(seen))
    spy = _SpyBreaker()
    undo_b = _module_stub(
        {"backend.services.vlm_client": {"get_circuit_breaker": lambda _name, _cfg=None: spy}}
    )
    c = _client(
        {
            "/props": [_echo_handler()],
            "/v1/chat/completions": [_chat_prose(finish="length")],
        },
        foscam_base_path=root,
    )
    c._breaker = spy
    try:
        try:
            asyncio.run(c._probe_enforcement(c._image_parts(_req(files))))
            raise AssertionError("must raise")
        except ConstrainedDecodingNotEnforced as exc:
            assert exc.verdict == "inconclusive"
            assert str(exc) == (
                "vlm probe reply hit its token budget (stop='length', "
                f"max_tokens={vc._PROBE_MAX_TOKENS}) before the const could be "
                "read - enforcement "
                "is UNMEASURED at this budget, not absent. Fail closed."
            )
        assert seen == [("pipeline_error", "vlm_probe_truncated")]
        assert spy.calls == []  # finding A: the breaker is NOT fed a budget
        assert c._enforced is None
    finally:
        undo_b()
        undo_m()


def test_probe_non200_is_inconclusive_http():
    files = _stills(1)
    root = str(Path(files[0]).parent)
    seen: list = []
    undo_m = _module_stub(_metric_stub(seen))
    spy = _SpyBreaker()
    undo_b = _module_stub(
        {"backend.services.vlm_client": {"get_circuit_breaker": lambda _name, _cfg=None: spy}}
    )
    c = _client(
        {"/props": [_echo_handler()], "/v1/chat/completions": [lambda _b: (503, {"e": "down"})]},
        foscam_base_path=root,
    )
    c._breaker = spy
    try:
        try:
            asyncio.run(c._probe_enforcement(c._image_parts(_req(files))))
            raise AssertionError("must raise")
        except ConstrainedDecodingNotEnforced as exc:
            assert exc.verdict == "inconclusive"
            assert str(exc) == "vlm probe got HTTP 503; cannot measure enforcement"
        assert seen == [("pipeline_error", "vlm_probe_not_enforced")]
        assert spy.calls == [("failure",)]
    finally:
        undo_b()
        undo_m()


def test_probe_transport_failure_is_inconclusive():
    files = _stills(1)
    root = str(Path(files[0]).parent)
    seen: list = []
    undo_m = _module_stub(_metric_stub(seen))
    spy = _SpyBreaker()
    undo_b = _module_stub(
        {"backend.services.vlm_client": {"get_circuit_breaker": lambda _name, _cfg=None: spy}}
    )

    def refuse(body):
        raise httpx.ConnectTimeout("connect timeout")

    c = _client(
        {"/props": [_echo_handler()], "/v1/chat/completions": [refuse]},
        foscam_base_path=root,
    )
    c._breaker = spy
    try:
        try:
            asyncio.run(c._probe_enforcement(c._image_parts(_req(files))))
            raise AssertionError("must raise")
        except ConstrainedDecodingNotEnforced as exc:
            assert exc.verdict == "inconclusive"
            assert str(exc) == "vlm probe transport failure (connect timeout)"
        assert seen == [("pipeline_error", "vlm_probe_transport")]
        assert spy.calls == [("failure",)]
    finally:
        undo_b()
        undo_m()


def test_probe_chat_length_stop_still_enforced_when_const_echoed():
    # finding A's truncated_with_const arm: an echo cannot be argued with by
    # a stop reason - ENFORCED caches even on a length stop
    files = _stills(1)
    root = str(Path(files[0]).parent)
    records, undo_l = _logs()
    c = _client(
        {"/props": [_echo_handler()], "/v1/chat/completions": [_chat_strict(finish="length")]},
        foscam_base_path=root,
    )
    try:
        asyncio.run(c._probe_enforcement(c._image_parts(_req(files))))
        assert c._enforced is True
    finally:
        undo_l()


# ---------------------------------------------------------------------------
# §6 assess - the wire, the ladder, the breaker
# ---------------------------------------------------------------------------


def _assess_env(handlers, *, allow=True, is_open=False, is_closed=True, probe=False, **over):
    """Everything assess touches: real stills, spy breaker, metric/degradation
    sinks, log capture. Returns a namespace-ish tuple."""
    files = _stills(1)
    root = str(Path(files[0]).parent)
    metrics: list = []
    degraded: list = []
    truncated: list = []
    sink: list = []
    undo_m = _module_stub(_metric_stub(metrics, truncated=truncated))
    undo_d = _module_stub(_degradation_stub(degraded))
    spy = _SpyBreaker(allow=allow, is_open=is_open, is_closed=is_closed)
    undo_b = _module_stub(
        {
            "backend.services.vlm_client": {
                "get_circuit_breaker": lambda _name, _cfg=None: spy,
            }
        }
    )
    records, undo_l = _logs()
    c = _client(
        handlers,
        foscam_base_path=root,
        vlm_enforcement_probe_enabled=probe,
        **over,
    )
    c._breaker = spy
    return {
        "c": c,
        "t": c._transport,
        "path": files[0],
        "spy": spy,
        "metrics": metrics,
        "degraded": degraded,
        "truncated": truncated,
        "sink": sink,
        "records": records,
        "undo": [undo_m, undo_d, undo_b, undo_l],
    }


def _close_all(env):
    for undo in env["undo"]:
        undo()


def _chat_valid(finish="stop", content=None):
    def handler(body):
        rf = body.get("response_format") or {}
        schema = (rf.get("json_schema") or {}).get("schema") or {}
        payload = json.dumps(content if content is not None else _fill(schema))
        return 200, {"choices": [{"message": {"content": payload}, "finish_reason": finish}]}

    return handler


def test_assess_circuit_open_refuses_without_io():
    env = _assess_env({"/v1/chat/completions": [_chat_valid()]}, allow=False)
    try:
        try:
            asyncio.run(env["c"].assess(_req([env["path"]])))
            raise AssertionError("must raise")
        except vc.VlmUnavailableError as exc:
            assert str(exc) == (
                "vlm breaker OPEN for ai-vlm; refusing without I/O (recovery in 60s)"
            )
        assert env["t"].calls == []  # no I/O, not one request
        assert env["metrics"] == [("pipeline_error", "vlm_circuit_open")]
        assert env["degraded"] == [
            ("health", "ai-vlm", (("error_message", "circuit open"), ("is_healthy", False))),
            ("gauge", "ai-vlm", True),
        ]
        assert env["spy"].calls == [("allow",)]
    finally:
        _close_all(env)


def test_assess_success_body_exact_and_provenance_override():
    env = _assess_env({"/v1/chat/completions": [_chat_valid()]})
    try:
        req = _req([env["path"]])
        # nosemgrep: path-traversal-open - env["path"] is a _stills()-created file
        b64 = base64.b64encode(Path(env["path"]).read_bytes()).decode()
        verdict = asyncio.run(env["c"].assess(req))
        call = env["t"].calls[0]
        assert call["method"] == "POST" and call["path"] == "/v1/chat/completions"
        assert call["timeout"] == _WIRE_TIMEOUT  # client-level timeout rides extensions
        observed_schema = call["body"]["response_format"]["json_schema"]["schema"]
        assert call["body"] == {
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/jpeg;base64,{b64}"},
                        },
                        {"type": "text", "text": env["c"].prompt_text(req)},
                    ],
                }
            ],
            "temperature": 0.0,
            "max_tokens": vc._ASSESS_MAX_TOKENS,
            "response_format": {
                "type": "json_schema",
                "json_schema": {"name": "vlm_verdict", "schema": observed_schema},
            },
        }
        assert observed_schema == env["c"]._wire_schema()  # the probe const is NOT here
        assert verdict.provenance.engine == "llama.cpp"
        assert verdict.provenance.model_id == env["c"]._settings.vlm_model_id
        assert env["spy"].calls == [("allow",), ("success",)]
        assert env["degraded"] == [
            ("health", "ai-vlm", (("is_healthy", True),)),
            ("gauge", "ai-vlm", False),
        ]
        assert env["metrics"] == [] and env["truncated"] == []
    finally:
        _close_all(env)


def test_assess_provenance_always_the_clients_own_knowledge():
    # a model that LIES about its identity is overwritten, never trusted
    env = _assess_env({"/v1/chat/completions": [_chat_valid(content=_camera_lie())]}, probe=True)
    try:
        c = env["c"]
        c._build_info = "b1-2"
        c._served_model_id = "ServedModel"
        c._enforced = True  # probe short-circuits
        verdict = asyncio.run(c.assess(_req([env["path"]])))
        assert verdict.provenance.engine == "llama.cpp@b1-2"
        assert verdict.provenance.model_id == "ServedModel"
        assert verdict.summary == "the model wrote this"
    finally:
        _close_all(env)


def _camera_lie():
    return {
        "verdict": "confirmed",
        "risk_score": 50,
        "summary": "the model wrote this",
        "reasoning": "r",
        "description": "d",
        "criteria": [{"name": "n", "passed": True, "evidence": "e"}],
        "provenance": {"engine": "cam1", "model_id": "cam1"},
    }


def test_assess_second_attempt_at_temp_zero_is_the_success_path():
    # the §6 ladder AND the continue->break twin: the survivor case comes
    # AFTER the skipped case and passes every filter ahead of the mutated arm
    env = _assess_env({"/v1/chat/completions": [_chat_prose(), _chat_valid()]})
    try:
        verdict = asyncio.run(env["c"].assess(_req([env["path"]])))
        calls = env["t"].calls
        assert len(calls) == 2
        assert calls[0]["body"]["temperature"] == 0.0  # greedy first attempt
        assert calls[1]["body"]["temperature"] == 0.0  # step 1 of the ladder: a plain re-send
        assert verdict.verdict is not None
        assert env["spy"].calls == [("allow",), ("failure",), ("success",)]
        assert env["metrics"] == [("pipeline_error", "vlm_schema_invalid")]
        assert _log_sig(env["records"]) == [
            ("WARNING", "vlm schema violation (attempt %d)", (1,), (), None)
        ]
    finally:
        _close_all(env)


def test_assess_transport_error_twice_is_a_transport_error():
    def refuse(body):
        raise httpx.ConnectError("all connections failed")

    env = _assess_env({"/v1/chat/completions": [refuse]})
    try:
        try:
            asyncio.run(env["c"].assess(_req([env["path"]])))
            raise AssertionError("must raise")
        except vc.VlmTransportError as exc:
            assert str(exc) == "vlm transport failure: all connections failed"
        assert len(env["t"].calls) == 2
        assert env["spy"].calls == [("allow",), ("failure",), ("failure",)]
        assert env["metrics"] == [("pipeline_error", "vlm_transport_error")] * 2
        assert _log_sig(env["records"], ("error",)) == [
            (
                "WARNING",
                "vlm transport error (attempt %d)",
                (1,),
                ("all connections failed",),
                None,
            ),
            (
                "WARNING",
                "vlm transport error (attempt %d)",
                (2,),
                ("all connections failed",),
                None,
            ),
        ]
    finally:
        _close_all(env)


def test_assess_transport_then_success_reports_both_attempt_numbers():
    # the other continue->break twin on the transport arm
    calls = {"n": 0}

    def flaky(body):
        calls["n"] += 1
        if calls["n"] == 1:
            raise httpx.ReadTimeout("read timed out")
        return 200, {
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            _fill(body["response_format"]["json_schema"]["schema"])
                        )
                    },
                    "finish_reason": "stop",
                }
            ]
        }

    env = _assess_env({"/v1/chat/completions": [flaky]})
    try:
        verdict = asyncio.run(env["c"].assess(_req([env["path"]])))
        assert verdict is not None
        assert env["spy"].calls == [("allow",), ("failure",), ("success",)]
        assert _log_sig(env["records"], ("error",)) == [
            ("WARNING", "vlm transport error (attempt %d)", (1,), ("read timed out",), None)
        ]
    finally:
        _close_all(env)


def test_assess_context_overflow_raises_without_feeding_the_breaker():
    overflow = {
        "error": {
            "type": "exceed_context_size_error",
            "n_prompt_tokens": 22293,
            "n_ctx": 16384,
        }
    }
    env = _assess_env({"/v1/chat/completions": [lambda _b: (400, overflow)]})
    try:
        try:
            asyncio.run(env["c"].assess(_req([env["path"]])))
            raise AssertionError("must raise")
        except vc.VlmContextOverflowError as exc:
            assert str(exc) == (
                "vlm request (22293 tokens) exceeds the served slot (16384 tokens); "
                "the prompt fit under-estimated it - verdict UNMEASURED, the engine is fine"
            )
        assert len(env["t"].calls) == 1  # NO retry of the same bytes
        assert env["spy"].calls == [("allow",)]  # the breaker is not lied to
        assert env["metrics"] == [("pipeline_error", "vlm_context_overflow")]
        assert _log_sig(env["records"], ("n_prompt_tokens", "n_ctx")) == [
            (
                "WARNING",
                "vlm request exceeded the served slot",
                (),
                (22293, 16384),
                None,
            )
        ]
    finally:
        _close_all(env)


def test_assess_http_error_body_is_cut_at_200_chars():
    long_text = "E" * 250
    env = _assess_env({"/v1/chat/completions": [lambda _b: (500, long_text)]})
    try:
        try:
            asyncio.run(env["c"].assess(_req([env["path"]])))
            raise AssertionError("must raise")
        except vc.VlmTransportError as exc:
            assert str(exc) == f"vlm HTTP 500: {long_text[:200]}"
            assert len(str(exc)) == len("vlm HTTP 500: ") + 200
        assert len(env["t"].calls) == 2
        assert env["metrics"] == [("pipeline_error", "vlm_http_error")] * 2
        assert env["spy"].calls == [("allow",), ("failure",), ("failure",)]
    finally:
        _close_all(env)


def test_assess_truncated_reply_raises_from_and_blames_the_budget():
    # FINDING A on the assess leg: length stop -> VlmTruncatedError, ONE
    # attempt (the retry could not help), budget metric, breaker untouched
    env = _assess_env({"/v1/chat/completions": [_chat_prose(finish="length")]})
    try:
        try:
            asyncio.run(env["c"].assess(_req([env["path"]])))
            raise AssertionError("must raise")
        except vc.VlmTruncatedError as exc:
            assert str(exc) == (
                "vlm verdict reply hit its token budget before the object closed "
                f"(stop='length', max_tokens={vc._ASSESS_MAX_TOKENS}); verdict "
                "UNMEASURED at this budget, not invalid"
            )
            assert isinstance(exc.__cause__, Exception)
            assert type(exc.__cause__).__name__ == "ValidationError"
        assert len(env["t"].calls) == 1  # no §6 retry on a budget
        assert env["spy"].calls == [("allow",)]
        assert env["metrics"] == [("pipeline_error", "vlm_assess_truncated")]
        assert _log_sig(env["records"], ("stop",)) == [
            ("WARNING", "vlm verdict truncated at max_tokens=%d", (vc._ASSESS_MAX_TOKENS,), ("length",), None)
        ]
    finally:
        _close_all(env)


def test_assess_schema_violation_twice_raises_the_last_error():
    env = _assess_env({"/v1/chat/completions": [_chat_prose()]})
    try:
        try:
            asyncio.run(env["c"].assess(_req([env["path"]])))
            raise AssertionError("must raise")
        except vc.VlmSchemaError as exc:
            assert str(exc).startswith("vlm verdict failed validation: ")
            assert not isinstance(exc, vc.VlmTruncatedError)
        assert env["metrics"] == [("pipeline_error", "vlm_schema_invalid")] * 2
        assert _log_sig(env["records"]) == [
            ("WARNING", "vlm schema violation (attempt %d)", (1,), (), None),
            ("WARNING", "vlm schema violation (attempt %d)", (2,), (), None),
        ]
    finally:
        _close_all(env)


def test_assess_prompt_truncation_fires_at_the_wire_once():
    # a batch that cannot fit: the metric + warning ride the WIRE leg, not
    # the renderer (prompt_text runs again in the analyzer)
    undo_c = _counter_stub()
    env = _assess_env({"/v1/chat/completions": [_chat_valid()]})
    try:
        c = env["c"]
        req = _req([env["path"]], context=dict(_CTX, detections=_fit_rows(3)))
        c._settings = c._settings.model_copy(update={"vlm_context_window": 1400})
        verdict = asyncio.run(c.assess(req))
        assert verdict is not None
        assert env["truncated"] == ["prompt_truncated"]  # once, not twice
        assert _log_sig(env["records"], ("vlm_context_window", "detections_in_context")) == [
            (
                "WARNING",
                "vlm prompt truncated to fit the slot",
                (),
                (1400, 3),
                None,
            )
        ]
        body_text = env["t"].calls[0]["body"]["messages"][0]["content"][1]["text"]
        assert "omitted" in body_text
    finally:
        undo_c()
        _close_all(env)


def test_assess_probe_failure_stops_before_the_verdict_wire():
    env = _assess_env(
        {"/props": [_echo_handler()], "/v1/chat/completions": [_chat_prose()]}, probe=True
    )
    try:
        try:
            asyncio.run(env["c"].assess(_req([env["path"]])))
            raise AssertionError("must raise")
        except ConstrainedDecodingNotEnforced as exc:
            assert exc.verdict == "ignored"
        # exactly ONE chat call - the probe itself; the verdict was never
        # asked for (and assess never reaches its retry ladder)
        assert [(k["method"], k["path"]) for k in env["t"].calls] == [
            ("GET", "/props"),
            ("POST", "/v1/chat/completions"),
        ]
        assert env["t"].calls[1]["body"]["response_format"]["json_schema"]["name"] == "vlm_probe"
        assert env["spy"].calls == [("allow",), ("failure",)]
    finally:
        _close_all(env)


def test_assess_unreadable_image_raises_before_any_request():
    env = _assess_env({"/v1/chat/completions": [_chat_valid()]})
    try:
        try:
            asyncio.run(env["c"].assess(_req(["ghost.jpg"])))
            raise AssertionError("must raise")
        except vc.VlmImageError as exc:
            assert "image file not found" in str(exc)
        assert env["t"].calls == []
        assert env["spy"].calls == [("allow",)]
    finally:
        _close_all(env)


def test_assess_health_push_is_silent_until_the_breaker_closes():
    # HALF_OPEN trial success must not read healthy
    env = _assess_env({"/v1/chat/completions": [_chat_valid()]}, is_closed=False)
    try:
        asyncio.run(env["c"].assess(_req([env["path"]])))
        assert env["degraded"] == []
    finally:
        _close_all(env)


def test_note_failure_announces_only_the_open_transition():
    env = _assess_env({"/v1/chat/completions": [_chat_valid()]}, is_open=False)
    try:
        asyncio.run(env["c"]._note_failure("vlm_transport_error"))
        assert env["spy"].calls == [("failure",)]
        assert env["metrics"] == [("pipeline_error", "vlm_transport_error")]
        assert env["degraded"] == []
    finally:
        _close_all(env)
    env2 = _assess_env({"/v1/chat/completions": [_chat_valid()]}, is_open=True)
    try:
        asyncio.run(env2["c"]._note_failure("vlm_http_error"))
        assert env2["degraded"] == [
            ("health", "ai-vlm", (("error_message", "vlm_http_error"), ("is_healthy", False))),
            ("gauge", "ai-vlm", True),
        ]
    finally:
        _close_all(env2)


# ---------------------------------------------------------------------------
# §6 cold start: wake / wake_ai_vlm / close
# ---------------------------------------------------------------------------


def test_wake_body_timeout_and_cold_start_metric():
    files = _stills(1)
    root = str(Path(files[0]).parent)
    cold: list = []
    metrics: list = []
    undo_m = _module_stub(_metric_stub(metrics, cold=cold))
    records, undo_l = _logs()
    c = _client(
        {"/v1/chat/completions": [lambda _b: (200, {"choices": [{"message": {"content": "p"}}]})]},
        foscam_base_path=root,
    )
    try:
        assert asyncio.run(c.wake()) is True
        call = c._transport.calls[0]
        assert call["path"] == "/v1/chat/completions"
        # the PER-REQUEST wake timeout rides the extension (client 27/4 vs
        # wake 45/4: the mutation shows up in exactly one of the two dicts)
        assert call["timeout"] == _WAKE_TIMEOUT
        assert call["body"] == {
            "messages": [{"role": "user", "content": "ping"}],
            "max_tokens": 1,
            "temperature": 0.0,
        }
        assert cold == ["ai-vlm"]
        assert _log_sig(records, ("base_url", "woke")) == [
            ("DEBUG", "vlm wake", (), ("http://fake-vlm:8098", True), None)
        ]
    finally:
        undo_m()
        undo_l()


def test_wake_non200_does_not_count_a_cold_start():
    cold: list = []
    metrics: list = []
    undo_m = _module_stub(_metric_stub(metrics, cold=cold))
    records, undo_l = _logs()
    c = _client({"/v1/chat/completions": [lambda _b: (503, {"e": "sleeping"})]})
    try:
        assert asyncio.run(c.wake()) is False
        assert cold == []  # a 503 woke nothing
        assert _log_sig(records, ("base_url", "woke")) == [
            ("DEBUG", "vlm wake", (), ("http://fake-vlm:8098", False), None)
        ]
    finally:
        undo_m()
        undo_l()


def test_wake_never_raises_on_transport_failure():
    def refuse(body):
        raise httpx.ConnectError("nobody home")

    records, undo_l = _logs()
    c = _client({"/v1/chat/completions": [refuse]})
    try:
        assert asyncio.run(c.wake()) is False
        assert _log_sig(records, ("error",)) == [
            (
                "DEBUG",
                "vlm wake failed (ignored by design)",
                (),
                ("nobody home",),
                None,
            )
        ]
    finally:
        undo_l()


def test_wake_ai_vlm_uses_a_throwaway_client_and_never_raises():
    # the REAL VlmClient class is constructed by wake_ai_vlm; only its
    # transport is the stub, so the construction + wake + close lifecycle
    # runs for real and a second call proves the client was throwaway
    transport = _StubTransport({"/v1/chat/completions": [lambda _b: (200, {"choices": []})]})
    cold: list = []
    metrics: list = []
    undo_m = _module_stub(_metric_stub(metrics, cold=cold))
    built: list = []

    async def _http(self):
        if self._client is None:
            self._client = httpx.AsyncClient(transport=transport, base_url=self._base_url)
            built.append(self._client)
        return self._client

    old_http = vc.VlmClient._http
    vc.VlmClient._http = _http
    try:
        assert asyncio.run(vc.wake_ai_vlm()) is True
        assert cold == ["ai-vlm"]
        assert len(built) == 1
        assert asyncio.run(vc.wake_ai_vlm()) is True  # a FRESH throwaway
        assert len(built) == 2 and cold == ["ai-vlm", "ai-vlm"]
    finally:
        vc.VlmClient._http = old_http
        undo_m()


def test_wake_ai_vlm_swallows_construction_failure():
    boom = {"n": 0}

    class _Boom:
        def __init__(self, *_a, **_k):
            boom["n"] += 1
            raise RuntimeError("no settings")

    undo = _module_stub({"backend.services.vlm_client": {"VlmClient": _Boom}})
    records, undo_l = _logs()
    try:
        assert asyncio.run(vc.wake_ai_vlm()) is False
        assert boom["n"] == 1
        assert _log_sig(records, ("error",)) == [
            ("DEBUG", "ai-vlm wake task failed (ignored by design)", (), ("no settings",), None)
        ]
    finally:
        undo()
        undo_l()


def test_close_releases_the_client_and_lets_it_reopen():
    env = _assess_env({"/v1/chat/completions": [_chat_valid()]}, probe=True)
    try:
        c = env["c"]
        c._enforced = True
        asyncio.run(c.assess(_req([env["path"]])))
        assert c._client is not None
        first = len(env["t"].calls)
        asyncio.run(c.close())
        assert c._client is None
        asyncio.run(c.assess(_req([env["path"]])))
        assert c._client is not None  # a fresh client after close
        assert len(env["t"].calls) == first + 1
    finally:
        _close_all(env)
