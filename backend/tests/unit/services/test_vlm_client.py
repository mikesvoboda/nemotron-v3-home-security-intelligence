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

import ast
import importlib.util
import inspect
import json
import math
import re
import sys
import types
from pathlib import Path
from typing import Any, ClassVar

import httpx
import pytest
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from backend.services import vlm_client as vc
from backend.services.constrained_decoding import ConstrainedDecodingNotEnforced
from backend.services.vlm_verdict import VlmAssessRequest, VlmVerdict


# CI-parity shim, file-local: this module's fixtures write synthetic JPEG
# bytes that plain PIL rejects with UnidentifiedImageError (production
# catches that -- the green path). But when ANY earlier test in the same
# serial process has imported ultralytics, PIL.Image.open is globally
# replaced (ultralytics.utils.patches.image_open, an import-time
# side-effect), and its HEIC fallback lazily does `from pi_heif import
# register_heif_opener` -- pi_heif is in no dependency set; on networked CI
# ultralytics pip-installs it on demand, offline (mutant-home bank runs: uv
# venvs carry no pip) the import itself becomes an uncaught error and the
# clean-test gate dies here (measured 2026-09-29: fill2 repros, both trees).
# Registering a no-op module ONLY when the real package is absent restores
# CI's exact state: the fallback retries, plain PIL still rejects the fake
# bytes, UnidentifiedImageError propagates, production handles it. If the
# real pi_heif is installed, setdefault() is a no-op and nothing changes.
def _noop_register_heif_opener() -> None:
    """Stand-in for pi_heif's real opener: registers nothing."""


if importlib.util.find_spec("pi_heif") is None:
    _pi_heif_stub = types.ModuleType("pi_heif")
    _pi_heif_stub.register_heif_opener = _noop_register_heif_opener
    sys.modules.setdefault("pi_heif", _pi_heif_stub)

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


def make_fake_llama(
    mode: str = "strict", build_info: str = _BUILD_INFO, model_path: str | None = None
) -> FastAPI:
    app = FastAPI()
    app.state.calls = []  # every chat request body, in order (wake tests read this directly)

    @app.get("/props")
    async def props() -> dict:
        return {"build_info": build_info, **({"model_path": model_path} if model_path else {})}

    @app.post("/v1/chat/completions")
    async def chat(request: Request) -> JSONResponse:
        body = await request.json()
        app.state.calls.append(body)
        if mode == "down":
            return JSONResponse({"error": "gone"}, status_code=503)
        if mode == "context_overflow":
            # llama-server b7972's own body, captured on the A5500 (2026-09-28)
            # for a fitted prompt the slot could not hold.
            return JSONResponse(
                {
                    "error": {
                        "code": 400,
                        "message": "request (22293 tokens) exceeds the available context "
                        "size (16384 tokens), try increasing it",
                        "type": "exceed_context_size_error",
                        "n_prompt_tokens": 22293,
                        "n_ctx": 16384,
                    }
                },
                status_code=400,
            )
        if mode == "schema-invalid":
            # 200 + content that VIOLATES VlmVerdict: the float risk_score
            # from the spec's own bad example (int ge/le fails). Post-
            # validation must catch what a lying grammar let through.
            return JSONResponse({"choices": [{"message": {"content": '{"risk_score": 0.25}'}}]})
        rf = body.get("response_format")
        content: str
        finish: str | None = "stop"
        if rf is None:
            content = "the scene" if body.get("max_tokens") == 1 else "prose"
        elif mode == "ignore":
            # accepts the parameter, answers prose WITHOUT the grammar -
            # the exact E5-class lie the probe must catch. It stopped
            # NATURALLY, so the missing const is real evidence.
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
        # The truncated arms describe the PROBE request only - the assess leg
        # sends response_format too, so "is this the probe?" is whether the
        # schema carries the nonce const. Deciding the arm on anything else
        # would reshape the assess leg and pin nothing.
        _sch = (((rf or {}).get("json_schema") or {}).get("schema")) or {}
        _const = (_sch.get("properties") or {}).get("probe_const", {}).get("const")
        if rf is not None and isinstance(_const, str):
            if mode == "truncated":
                # finding A's shape: the budget ran out mid-object, so the
                # const (which may legally sort last) was never emitted.
                content, finish = '{"risk_level": "me', "length"
            elif mode == "truncated_with_const":
                # out of budget, but the const arrived FIRST - the grammar
                # already proved itself; a stop reason cannot un-prove that.
                content, finish = json.dumps({"probe_const": _const}), "length"
        elif rf is not None and mode == "assess_truncated":
            # The ASSESS leg's finding A (the verdict schema, no const): 700
            # tokens run out mid-`description`, so the object never closes.
            # The reply is the SAME at any temperature - the retry's whole
            # premise is broken here.
            content, finish = '{"risk_score": 80, "risk_level": "high", "descr', "length"
        choice: dict = {"message": {"content": content}}
        # The compat wire's stop signal. Emitted only when the fake has one to
        # report: finding A's triage must not infer truncation from a field
        # the server never sent.
        if finish is not None:
            choice["finish_reason"] = finish
        return JSONResponse({"choices": [choice], "usage": {"total_tokens": 7}})

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

    async def test_assess_samples_greedily(self, image_dir) -> None:
        """The assess call is greedy (temperature 0). At the former unseeded 0.1 only
        278/450 corpus items reproduced across two identical replays (36% changed score,
        52 changed risk level), so a borderline event could alert on one pass and not the
        next; at 0 two replays agreed on 450/450 with the same S2/S3 (GB300, 2026-10-03).
        Pinned on the wire AND on the constant, with no sampling knob that would reintroduce
        run-to-run variance."""
        assert vc._ASSESS_TEMPERATURE == 0.0
        client = make_client()
        await client.assess(_request([str(image_dir / "front_door/a.jpg")]))
        body = client._app_calls()[-1]  # the real call; the probe ran first
        assert body["temperature"] == 0.0
        assert not {"top_p", "top_k", "min_p", "seed"} & set(body), (
            "greedy decoding needs no sampler knobs; adding one reopens run-to-run variance"
        )
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


class TestRefusesNonStills:
    """A clip is not a still, and `_image_parts` has no business embedding one.

    How a video reaches here is not hypothetical: for a video batch
    `detector_client` sets `detection_file_path = video_path` (:1174), so
    EVERY row of a video frame carries the `.mp4` as its `file_path`, the
    selector hands that path to the request as the batch's one still, and
    `_image_parts` base64'd the whole container into the prompt as
    `data:video/mp4;base64,...`. Two ways to lose, both silent: a big enough
    clip blows llama-server's slot (and the breaker then reports a MODEL
    outage for a data bug), or the engine tolerates it and "verifies" an event
    from bytes no image decoder ever read.

    The legacy path solved this by extracting a frame
    (`enrichment_pipeline._load_image` -> `_extract_frame_from_video`). The
    vlm path cannot copy it yet: the detector's extracted JPEGs are DELETED
    after detection (`pipeline_workers:746`), `thumbnail_path` is never
    populated for these rows, and `ffmpeg` is not in the backend image - so
    the honest move is a refusal that names the cause, which lands as
    `verification_failed` with a NULL score (D11/S5: never a silent
    substitute), never a score computed from a container.
    """

    def _clip(self, image_dir, name: str = "clip.mp4", payload: bytes = b"") -> Path:
        clip = image_dir / "front_door" / name
        # synthetic bytes only (the privacy rule covers fixtures)
        clip.write_bytes(payload or (b"\x00\x00\x00\x18ftypmp42" + b"\x00" * 4096))
        return clip

    async def test_a_clip_is_refused_before_any_read(self, image_dir) -> None:
        """The type guard wins over the size guard: even a TINY clip - one
        that would sail past any byte limit - is refused by what it IS."""
        client = make_client()
        clip = self._clip(image_dir, payload=b"tiny")
        with pytest.raises(vc.VlmImageError) as exc:
            await client.assess(_request([str(clip)]))
        assert "video" in str(exc.value).lower()
        assert client._app_calls() == [], "refused BEFORE any I/O"
        await client.close()

    async def test_the_refusal_names_the_batch_so_the_cause_is_findable(self, image_dir) -> None:
        """An operator reading the incident must be able to tell "the vlm
        path has no frame extractor" apart from "the VLM is down" - the two
        looked identical when 1.2's client wire was missing, and a clip
        landing as a bare `image file not found` would do it again."""
        client = make_client()
        clip = self._clip(image_dir)
        with pytest.raises(vc.VlmImageError) as exc:
            await client.assess(_request([str(clip)]))
        msg = str(exc.value).lower()
        assert "frame extraction" in msg or "extract" in msg
        assert str(clip.name) in str(exc.value)
        await client.close()

    async def test_an_oversized_still_is_refused_not_embedded(self, image_dir) -> None:
        """The byte backstop, for a STILL (a corrupt capture, or a filesystem
        that handed us something enormous): base64 of the payload is what
        kills the slot, so the guard sits BEFORE `read_bytes`."""
        client = make_client(vlm_max_image_bytes=1024)
        big = image_dir / "front_door" / "huge.jpg"
        big.write_bytes(b"\xff\xd8\xff" + b"\x00" * 4096)
        with pytest.raises(vc.VlmImageError) as exc:
            await client.assess(_request([str(big)]))
        assert "1024" in str(exc.value), "the limit belongs in the message"
        assert client._app_calls() == []
        await client.close()

    async def test_an_ordinary_still_still_passes_both_guards(self, image_dir) -> None:
        """No-regression half: the fixture stills (35 bytes) are unaffected -
        the guards refuse a class of input, not the working path."""
        client = make_client()
        verdict = await client.assess(_request([str(image_dir / "front_door/a.jpg")]))
        assert isinstance(verdict, VlmVerdict)
        await client.close()

    def test_the_default_byte_limit_is_not_a_still_squeezing_one(self) -> None:
        """The shipped default has to clear a real camera still with room to
        spare, or the guard becomes an outage with a name. A 2160p MJPEG
        still runs ~2-3 MB, so the floor is set in MB, not hundreds of KB -
        and the client must READ the setting, not carry its own copy."""
        default = vc.get_settings().vlm_max_image_bytes
        assert default >= 4 * 1024 * 1024, f"shipped limit {default} cannot hold a 4K still"
        client = vc.VlmClient(base_url="http://fake-vlm:8098")
        assert client._settings.vlm_max_image_bytes == default


class TestPromptBudget:
    """The text half of the prompt must FIT the slot the request actually
    lands in - measured, not assumed.

    spec §2 sized the ai-vlm slot around "4 images x <=1280 tokens + ~6K
    prompt + ~1K verdict" per slot (the same arithmetic the compose block
    comments). The ~6K was never enforced anywhere on the vlm path, and a
    legal batch walks straight past it: `batch_max_detections` defaults 500
    (config.py:977-978) and `prompt_text` renders EVERY row as JSON - measured
    with the repo's own counter, 200 detections -> 12,033 text tokens, 500
    -> 29,733, against a 16,384-token slot (VLM_CTX_SIZE 32768 /
    VLM_PARALLEL 2). The legacy path has this arm (nemotron's
    `_validate_and_truncate_prompt` + `record_prompt_truncated`); the vlm
    path shipped without it.

    The second, quieter half: the natural counter to reach for,
    `settings.nemotron_context_window`, reads the LEGACY ai-llm service's
    CTX_SIZE/PARALLEL (the backend container mirrors 262144/8 = 32768 -
    verified: the backend's environment: block never carries VLM_CTX_SIZE),
    so counting a vlm prompt against it grades against a slot twice the
    size of the one the request gets. `settings.vlm_context_window` is the
    vlm-scoped derivation (same CTX/PARALLEL rule, the ai-vlm pair); the
    client budgets against THAT.

    Truncation is VISIBLE (the `apply_verdict_invariants` "log the clamp"
    doctrine): dropped rows are counted in the prompt itself, and the
    survivors are the HIGH-confidence rows - the same ranking that chose the
    key frames, so what survives is the evidence the model can actually
    corroborate against the attached stills. Never a silent shortlist.
    """

    # Default lives OUTSIDE the capture root on purpose: the pure-renderer
    # pins never touch the filesystem, and a path the guard would refuse is
    # the honest default for a test that must not depend on file IO.
    OUTSIDE_ROOT = "/export/foscam/front_door"

    @staticmethod
    def _rows(count: int, base: str | Path = OUTSIDE_ROOT) -> list[dict[str, Any]]:
        from datetime import UTC, datetime

        return [
            {
                "id": i,
                "camera_id": "front_door",
                "object_type": "person" if i % 2 else "car",
                "confidence": 0.5 + (i % 50) / 100,
                "detected_at": datetime(2026, 9, 27, 12, 0, tzinfo=UTC),
                "file_path": f"{base}/det_{i}.jpg",
                "thumbnail_path": None,
                "track_id": None,
                "bbox": [10, 10, 100, 200],
            }
            for i in range(1, count + 1)
        ]

    def _big_request(self, count: int = 500, base: str | Path = OUTSIDE_ROOT) -> Any:
        from backend.services.vlm_analyzer import build_assess_context, build_assess_request

        rows = self._rows(count, base)
        ctx = build_assess_context(
            camera_id="front_door",
            detections=rows,
            zones=["porch"],
            specialist_outputs={"faces": "2 unknown faces", "plates": "no plates"},
        )
        return build_assess_request(context=ctx, detections=rows)

    def test_a_max_size_batch_fits_the_vlm_slot(self) -> None:
        """THE acceptance pin: a 500-detection batch (the shipped
        batch_max_detections ceiling) renders a prompt whose TEXT tokens +
        image reservation + verdict budget fit ONE vlm slot. Before the arm
        existed this measured 29,733 + 5,120 + 700 against a 16,384 slot."""
        from backend.services.token_counter import get_token_counter

        settings = vc.get_settings()
        client = make_client()
        text = client.prompt_text(self._big_request())
        counter = get_token_counter()
        reserved = client._image_token_reservation(self._big_request())
        served_text = math.ceil(counter.count_tokens(text) * vc._SERVED_TOKENS_PER_COUNTED)
        used = served_text + reserved + vc._ASSESS_MAX_TOKENS
        assert used <= settings.vlm_context_window, (
            f"{used} tokens into a {settings.vlm_context_window}-token slot"
        )

    # A5500, 2026-09-28: the same fitted prompt, counted twice - 10,237 by the
    # repo's counter, 13,785 by the served engine's /tokenize (Qwen splits
    # every digit, and detection rows are mostly digits). The fit passed a
    # prompt that, with its stills, was 22,293 tokens for a 16,384 slot.
    _MEASURED_SERVED_RATIO = 13_785 / 10_237

    def test_the_fit_counts_text_the_way_the_served_tokenizer_does(self) -> None:
        assert vc._SERVED_TOKENS_PER_COUNTED >= self._MEASURED_SERVED_RATIO * 1.1, (
            f"margin {vc._SERVED_TOKENS_PER_COUNTED} leaves under 10% over the "
            f"measured {self._MEASURED_SERVED_RATIO:.2f}x tokenizer gap"
        )

    def test_truncation_is_visible_and_counted(self) -> None:
        """A dropped tail says so, with the count: a model told nothing
        would read 12 shown rows as the whole scene ("no further activity")
        - a silent lie by omission on the one channel D10 says is evidence."""
        client = make_client()
        text = client.prompt_text(self._big_request())
        assert "omitted" in text.lower(), "the prompt admits the truncation"
        # the marker carries a real number out of 500
        m = re.search(r"(\d+) further detection", text)
        assert m and 0 < int(m.group(1)) < 500

    def test_survivors_are_the_strongest_rows(self) -> None:
        """Which rows survive is not arrival order: the highest-confidence
        detections win, because those are the rows the key-frame selector
        stands behind - the model can corroborate them against the stills."""
        client = make_client()
        text = client.prompt_text(self._big_request())
        ids_kept = [int(m) for m in re.findall(r'"id": (\d+)', text)]
        rows = self._rows(500)
        conf = {r["id"]: r["confidence"] for r in rows}
        best = max(conf.values())
        assert any(conf[i] >= best - 1e-9 for i in ids_kept), (
            "the single most confident detection survives truncation"
        )

    def test_a_small_prompt_is_untouched_byte_for_byte(self) -> None:
        """No-regression half: an ordinary batch never sees the arm - the
        stored llm_prompt stays exactly what the builders render."""
        from backend.services.vlm_analyzer import build_assess_context, build_assess_request

        rows = self._rows(6)
        ctx = build_assess_context(camera_id="front_door", detections=rows, zones=["porch"])
        request = build_assess_request(context=ctx, detections=rows)
        client = make_client()
        text = client.prompt_text(request)
        assert "omitted" not in text.lower()
        for row in rows:
            assert f'"id": {row["id"]}' in text, "every row of a fitting batch is rendered"

    def test_the_budget_is_the_vlm_slot_not_the_legacy_llms(self) -> None:
        """The two derivations are DIFFERENT numbers and the arm reads the
        vlm one. Measured slope: ~61 tokens per detection row, so a 300-row
        batch renders ~18.4K text tokens - used ~24.2K with images+output.
        That is LEGAL for the legacy slot (32768) and ILLEGAL for the vlm
        slot (16384), which makes the batch itself the discriminator: a
        300-row prompt truncates if and only if the budget is the vlm
        figure. Counting against `nemotron_context_window` - what the
        backend container actually carries, the ai-llm pair it mirrors -
        would wave this batch through into a slot half its size.
        """
        s = vc.get_settings()
        assert s.vlm_context_window < s.nemotron_context_window, (
            "shipped defaults: the vlm slot is HALF the legacy slot - if this "
            "ever reads False the two derivations collapsed into one number"
        )
        client = make_client()
        text = client.prompt_text(self._big_request(300))
        assert "omitted" in text.lower(), (
            "a batch legal for the LEGACY slot but illegal for the vlm slot "
            "must truncate - proof the guard counts against vlm_context_window"
        )

    def _wire_request(self, count: int, image_dir: Path) -> Any:
        """A request whose stills live UNDER the capture root and exist as real
        synthetic files, for the pins that drive `assess` (the pure-renderer
        pins never touch the filesystem).

        The rows are built FROM the root rather than rewritten onto it: the
        guard resolves `row["file_path"]` itself, so a request whose rows still
        point at /export/... is refused before the bytes on disk matter at all.
        Synthetic bytes only, and at most MAX_KEY_FRAMES files get embedded.
        """
        request = self._big_request(count, base=image_dir / "front_door")
        for raw in request.image_paths:
            path = Path(raw)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"\xff\xd8\xff" + b"\x00" * 32)
        return request

    async def test_the_truncation_hits_the_metric_once(self, image_dir, monkeypatch) -> None:
        """`record_prompt_truncated` is how an operator SEES the arm firing
        (legacy's NEM-1666 telemetry) - an uncounted clamp is a silent one.

        Exactly ONCE per oversized batch, and the count is the interesting
        part: `prompt_text` is called twice per assess (once for the wire,
        once by the analyzer for the stored `llm_prompt`), so a metric inside
        the renderer would double every event. The renderer returns a flag;
        the wire call owns the effect."""
        calls: list[int] = []
        monkeypatch.setattr(vc, "record_prompt_truncated", lambda: calls.append(1))
        client = make_client()
        await client.assess(self._wire_request(500, image_dir))
        assert calls == [1], f"expected one record, got {calls}"
        await client.close()

    async def test_a_fitting_prompt_records_no_truncation(self, image_dir, monkeypatch) -> None:
        calls: list[int] = []
        monkeypatch.setattr(vc, "record_prompt_truncated", lambda: calls.append(1))
        client = make_client()
        await client.assess(self._wire_request(6, image_dir))
        assert calls == [], "a prompt that fit recorded nothing"
        await client.close()

    async def test_the_stored_prompt_is_the_truncated_one(self) -> None:
        """The analyzer stores `prompt_text(request)` verbatim as
        Event.llm_prompt, so what an operator reads back must be the question
        the model was actually asked - marker and surviving rows, not the
        pre-truncation original. One code path guarantees it; this pins that
        the two call sites agree."""
        client = make_client()
        request = self._big_request()
        wire, truncated = client._fitted_prompt(request)
        assert truncated
        assert client.prompt_text(request) == wire, "renderer is deterministic"
        assert "omitted" in wire


class TestEnforcementProbe:
    def test_the_probe_budget_never_binds_before_the_verdict_budget(self) -> None:
        """A5500, 2026-09-28: the shipped 8B needs 427-429 tokens for the probe
        object (verdict + const, no image, finish=stop) and the budget was 400,
        so every in-client probe came back INCONCLUSIVE and every verdict failed
        closed - on a server the CLI gate measured ENFORCED 8/8. `probe_const`
        can sort last, so the probe object is the verdict object plus one const:
        a verdict that fits its own call must never be unmeasurable here."""
        assert vc._PROBE_MAX_TOKENS > vc._ASSESS_MAX_TOKENS, (
            f"probe budget {vc._PROBE_MAX_TOKENS} <= verdict budget {vc._ASSESS_MAX_TOKENS}"
        )

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
        the next call re-probes (S-1: a bad result must not ossify).

        Finding A's repair is what lets this pin be SHARP rather than
        two-word: the old `verdict in {"ignored", "inconclusive"}` accepted
        either, which is precisely how a fabricated `ignored` and an honest
        `inconclusive` shared a file. A complete prose reply at a natural
        stop is now pinned to `ignored`, and only the truncated shape earns
        `inconclusive` (see the pair below)."""
        client = make_client("ignore")
        with pytest.raises(ConstrainedDecodingNotEnforced) as exc:
            await client.assess(_request([str(image_dir / "front_door/a.jpg")]))
        assert exc.value.verdict == "ignored"
        with pytest.raises(ConstrainedDecodingNotEnforced):
            await client.assess(_request([str(image_dir / "front_door/a.jpg")]))
        await client.close()

    async def test_a_truncated_probe_reply_is_inconclusive_not_ignored(self, image_dir) -> None:
        """FINDING A, the shipped path. The probe's own comment names the
        hazard - "a budget that truncates mid-object FABRICATES an IGNORED
        verdict (the const can sort last in the grammar)" - and the ledger
        measured it: six scenes return `finish_reason: length` at 400 tokens,
        three of the same four echo the const at 1200. So a cut-off reply
        licenses NO claim about the server's grammar. It is unmeasured, and
        the word must be the one that says so."""
        client = make_client("truncated")
        with pytest.raises(ConstrainedDecodingNotEnforced) as exc:
            await client.assess(_request([str(image_dir / "front_door/a.jpg")]))
        assert exc.value.verdict == "inconclusive"
        assert "budget" in str(exc.value).lower() or "truncat" in str(exc.value).lower()
        await client.close()

    async def test_truncation_still_fails_closed_and_caches_nothing(self, image_dir) -> None:
        """The half that keeps this a REPAIR and not a loosening: renaming the
        verdict must not soften a single consequence. Still a raise, still no
        score, still nothing cached - the next call re-probes (S-1)."""
        client = make_client("truncated")
        for _ in range(2):
            with pytest.raises(ConstrainedDecodingNotEnforced):
                await client.assess(_request([str(image_dir / "front_door/a.jpg")]))
        assert client._enforced is None, "an unmeasured probe must never cache a verdict"
        await client.close()

    async def test_a_truncated_probe_never_opens_the_breaker(self, image_dir) -> None:
        """Finding G's measured consequence, pinned on the probe leg. The
        enforcement gate runs on the FIRST item, so a probe budget that
        truncates on a verbose scene used to record a breaker failure before
        refusing - five such scenes and `ai-vlm` opens for the whole replay,
        with every later item refused WITHOUT I/O. That is finding B's
        contamination reached through a budget rather than a per-item client,
        and it was OBSERVED, not imagined: the real-pixels run refused 6/6
        scenes this way (ledger finding G). The endpoint answered 200; the
        breaker's question is 'stop calling it?', and the answer is no."""
        from backend.services.circuit_breaker import get_circuit_breaker

        client = make_client("truncated")
        path = str(image_dir / "front_door/a.jpg")
        for _ in range(10):  # past the 5-failure threshold
            with pytest.raises(ConstrainedDecodingNotEnforced) as caught:
                await client.assess(_request([path]))
            assert caught.value.verdict == "inconclusive", (
                "every item must carry its OWN unmeasured verdict, not a breaker's blanket refusal"
            )
        await client.close()
        assert not get_circuit_breaker("ai-vlm").is_open, (
            "a probe budget must not open a service breaker"
        )

    async def test_a_slow_probe_reply_fails_closed_without_the_breaker(
        self, image_dir, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """B1.1 on the probe leg, the leg that actually bites: the probe is on
        by default and cached only once an endpoint has PROVEN enforcement, so
        an engine that has not yet proven it re-probes per item — and a slow
        re-probe used to charge the breaker each time (via `vlm_probe_transport`
        below the branch). Same budget ruling as the truncated-probe test right
        above: fail closed with INCONCLUSIVE, nothing cached, counted under its
        own cause, and never fed to the service breaker."""
        from backend.services.circuit_breaker import get_circuit_breaker

        recorded: list[str] = []
        monkeypatch.setattr(vc, "record_pipeline_error", lambda reason: recorded.append(reason))
        transport = _TimingOutTransport()
        settings = vc.get_settings().model_copy(update={"vlm_enforcement_probe_enabled": True})
        client = vc.VlmClient(
            base_url="http://fake-vlm:8098", transport=transport, settings=settings
        )
        for _ in range(10):  # well past the breaker's 5-failure threshold
            with pytest.raises(ConstrainedDecodingNotEnforced) as caught:
                await client.assess(_request([str(image_dir / "front_door/a.jpg")]))
            assert caught.value.verdict == "inconclusive", "fail closed, no verdict trusted"
        await client.close()
        assert client._enforced is None, "an unmeasured probe must never cache a verdict"
        assert transport.chat_calls == 10, "each item re-probes (nothing cached)"
        assert recorded == ["vlm_probe_timeout"] * 10, recorded
        assert not get_circuit_breaker("ai-vlm").is_open, (
            "a slow probe is OUR read budget, not a broken engine"
        )

    async def test_a_truncated_reply_that_carried_the_const_is_enforced(self, image_dir) -> None:
        """The mirror pin, guarding the other direction. If the const arrived,
        the grammar produced a value the prompt never mentioned - which is the
        probe's ENTIRE question - so running out of budget afterwards proves
        nothing against enforcement. A triage that demoted this would quietly
        lose real ENFORCED results."""
        client = make_client("truncated_with_const")
        await client.assess(_request([str(image_dir / "front_door/a.jpg")]))
        assert client._enforced is True
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
        assert calls[0]["temperature"] == 0.0, "the first attempt is greedy too"
        await client.close()

    async def test_read_timeout_raises_slow_reply_error_not_transport(self, image_dir) -> None:
        """ASGITransport NEVER enforces client timeouts (the 1.1 lesson), so
        the timeout is pinned at the transport layer itself: a transport
        that raises httpx.ReadTimeout exactly as a socket timeout would.

        B1.1 re-pins this. It used to assert VlmTransportError, which is the
        defect: a transport error is what charges the ai-vlm breaker, and a
        reply that simply took longer than OUR read budget is not a broken
        engine (D1). Same transport, same exception from httpx, now a budget
        outcome. TestSlowReplyIsNotABrokenEngine pins the breaker half."""

        class TimingOutTransport(httpx.AsyncBaseTransport):
            async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
                raise httpx.ReadTimeout("read timeout", request=request)

        settings = vc.get_settings().model_copy(update={"vlm_enforcement_probe_enabled": False})
        client = vc.VlmClient(
            base_url="http://fake-vlm:8098",
            transport=TimingOutTransport(),
            settings=settings,
        )
        with pytest.raises(vc.VlmSlowReplyError) as raised:
            await client.assess(_request([str(image_dir / "front_door/a.jpg")]))
        # still a client error, so the analyzer's mapping is unchanged
        assert isinstance(raised.value, vc.VlmClientError)
        assert not isinstance(raised.value, vc.VlmTransportError)
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


class TestAssessTruncation:
    """Ledger finding A's sibling on the ASSESS leg (see TestEnforcementProbe
    for the probe leg). The assess call sends the verdict schema at
    _ASSESS_MAX_TOKENS; the schema's required prose fields mean a rich
    scene can run out of budget before the object closes - the SAME truncation
    hazard finding A named for the probe. The shape's meaning is different
    though: a truncated verdict is a BUDGET artifact, not a model that emits
    invalid JSON (vlm_schema_invalid), and it is the SAME artifact on every
    attempt - the retry is at the same _ASSESS_MAX_TOKENS and, now that the
    first attempt is greedy too, the same temperature. The §6 transport retry
    re-runs an identical request because a transport failure is transient; a length-capped object
    is deterministic, so the retry (1) cannot change the outcome, (2) burns one
    breaker failure toward opening ai-vlm for a budget, and (3) labels the
    cause as a model defect. A budget must not read as a schema violation or a
    model outage.

    Deliberately narrower than the probe's triage: this changes the CAUSE label
    and spares the wasted breaker failures, NOT the ladder's OUTCOME - a
    truncated verdict still raises a VlmClientError subclass, so the analyzer
    still maps it to verification_failed with a NULL score. The ladder is
    neutral; only the diagnosis sharpens."""

    # A5500, 2026-09-28: the shipped 8B's longest verdict on the 38-item
    # detections set, from llama-server's own eval-token count (run 2ea4b96f,
    # a two-image item). At 700 that reply and two others were cut off - S5
    # counts a truncated reply as unparseable, and its bar is 0.
    _MEASURED_8B_LONGEST_VERDICT = 852

    def test_the_verdict_budget_covers_the_8bs_longest_measured_reply(self) -> None:
        headroom = vc._ASSESS_MAX_TOKENS / self._MEASURED_8B_LONGEST_VERDICT
        assert headroom >= 1.2, (
            f"_ASSESS_MAX_TOKENS={vc._ASSESS_MAX_TOKENS} leaves {headroom:.2f}x the "
            f"8B's measured {self._MEASURED_8B_LONGEST_VERDICT}-token verdict"
        )

    async def test_truncated_assess_reply_raises_truncated_not_schema_error(
        self, image_dir
    ) -> None:
        """`finish_reason: length` + a body cut off mid-object: the honest
        label is VlmTruncatedError (a budget), never VlmSchemaError (which the
        fake's schema-invalid mode reserves for well-formed-but-invalid JSON
        that stopped NATURALLY - that one still retries, correctly)."""
        client = make_client("assess_truncated", vlm_enforcement_probe_enabled=False)
        with pytest.raises(vc.VlmTruncatedError):
            await client.assess(_request([str(image_dir / "front_door/a.jpg")]))
        await client.close()

    async def test_truncated_assess_reply_does_not_retry(self, image_dir) -> None:
        """The retry is at the same max_tokens, so it re-asks the identical
        question and gets the identical length-capped object. Re-asking cannot
        help and records a second breaker failure for a budget; one measured
        truncation is decisive, so the leg asks ONCE."""
        client = make_client("assess_truncated", vlm_enforcement_probe_enabled=False)
        with pytest.raises(vc.VlmTruncatedError):
            await client.assess(_request([str(image_dir / "front_door/a.jpg")]))
        assert len(client._app_calls()) == 1, "a deterministic budget is not retried"
        await client.close()

    async def test_truncated_assess_records_the_truncated_cause(
        self, image_dir, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The metric label is the point of the change: `vlm_assess_truncated`,
        distinct from `vlm_schema_invalid`, so a budget never inflates the
        model-defect counter (the aggregate the M2 read uses). Patched in
        vlm_client's own namespace - that is where `_note_failure` looks it up."""
        recorded: list[str] = []
        monkeypatch.setattr(vc, "record_pipeline_error", lambda reason: recorded.append(reason))
        client = make_client("assess_truncated", vlm_enforcement_probe_enabled=False)
        with pytest.raises(vc.VlmTruncatedError):
            await client.assess(_request([str(image_dir / "front_door/a.jpg")]))
        await client.close()
        assert "vlm_assess_truncated" in recorded, recorded

    async def test_truncation_never_opens_the_breaker(self, image_dir) -> None:
        """The breaker asks "should we stop calling this service?" A truncated
        reply answers that question NO: the transport worked, the grammar
        applied, the endpoint returned 200 and did real work - OUR max_tokens
        was too small for the scene. Feeding it the breaker means a verbose
        corpus opens `ai-vlm` over a number we chose, and every later item
        then answers VlmUnavailableError WITHOUT I/O, so the report describes a
        breaker instead of a model (finding B's exact contamination, reached
        from a budget). The item still refuses to score - verification_failed
        with a NULL score - and the metric still counts, so nothing is
        silenced: the diagnosis is loud, the breaker just isn't lied to."""
        from backend.services.circuit_breaker import get_circuit_breaker

        client = make_client("assess_truncated", vlm_enforcement_probe_enabled=False)
        for _ in range(10):  # well past the breaker's 5-failure threshold
            with pytest.raises(vc.VlmClientError) as caught:
                await client.assess(_request([str(image_dir / "front_door/a.jpg")]))
            assert isinstance(caught.value, vc.VlmTruncatedError), (
                f"every item must answer with ITS OWN cause, item answered "
                f"{type(caught.value).__name__} - the breaker opened, so later "
                "items were refused without I/O"
            )
        await client.close()
        assert not get_circuit_breaker("ai-vlm").is_open, "a budget must not open a service breaker"

    async def test_a_natural_stop_invalid_reply_still_retries_as_schema_error(
        self, image_dir
    ) -> None:
        """The triage must not forgive real model defects: a well-formed reply
        that STOPS NATURALLY and violates the schema is still VlmSchemaError
        and still gets its temp-0 retry (finding A's discipline, mirrored:
        don't downgrade a schema violation just because some other field looks
        like truncation)."""
        client = make_client("schema-invalid", vlm_enforcement_probe_enabled=False)
        with pytest.raises(vc.VlmSchemaError):
            await client.assess(_request([str(image_dir / "front_door/a.jpg")]))
        assert len(client._app_calls()) == 2, "a genuine schema defect keeps its retry"
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


class TestPromptTime:
    """The Time line: UTC ISO when CAMERA_TIMEZONE is unset, local time when set."""

    def test_time_line_is_the_iso_string_when_camera_timezone_unset(self) -> None:
        client = make_client(camera_timezone=None)
        prompt = client._render_prompt([], _request(["/x/a.jpg"]))
        assert "Time: 2026-09-25T12:00:00+00:00\n" in prompt

    def test_time_line_is_local_with_zone_when_camera_timezone_set(self) -> None:
        client = make_client(camera_timezone="America/New_York")
        prompt = client._render_prompt([], _request(["/x/a.jpg"]))
        assert "Time: 2026-09-25 08:00:00 local (America/New_York, UTC-04:00)\n" in prompt

    # A 02:14 scene uploaded at 15:00: the row's detected_at is the arrival.
    _ARRIVAL = "2026-09-25T15:00:03.412000+00:00"

    def _row(self) -> dict[str, Any]:
        return {"id": 7, "object_type": "person", "confidence": 0.9, "detected_at": self._ARRIVAL}

    @staticmethod
    def _detections_line(prompt: str) -> str:
        return next(ln for ln in prompt.splitlines() if ln.startswith("Detections: "))

    def test_rows_omit_detected_at_when_camera_timezone_set(self) -> None:
        """The Time: line carries the capture moment; a row's arrival
        detected_at would contradict it, so the prompt shows one moment."""
        client = make_client(camera_timezone="America/New_York")
        prompt = client.prompt_text(_request(["/x/a.jpg"], detections=[self._row()]))
        line = self._detections_line(prompt)
        assert "detected_at" not in line
        assert '"id": 7' in line, "the rest of the row still renders"

    def test_rows_keep_detected_at_when_camera_timezone_unset(self) -> None:
        client = make_client(camera_timezone=None)
        prompt = client.prompt_text(_request(["/x/a.jpg"], detections=[self._row()]))
        assert self._detections_line(prompt) == (
            f"Detections: {json.dumps([self._row()], ensure_ascii=False)}"
        ), "unset CAMERA_TIMEZONE renders the rows byte for byte"

    def test_the_request_rows_keep_detected_at_after_rendering(self) -> None:
        client = make_client(camera_timezone="America/New_York")
        request = _request(["/x/a.jpg"], detections=[self._row()])
        client.prompt_text(request)
        assert request.context.detections == [self._row()], (
            "only the rendered copy drops detected_at; the snapshot is untouched"
        )


class TestChronologicalFrameLabels:
    """ISS-033: when the request carries per-frame capture times, the prompt
    says the frames are in chronological order and labels each one — unknown
    renders as unknown, never as arrival time. When the field is absent
    (CAMERA_TIMEZONE unset, replay of an old store) the prompt is byte-identical
    to today's, which is the S5 regression guarantee."""

    _TIMES: ClassVar[list[str]] = ["2026-09-25T10:00:00+00:00", "2026-09-25T11:00:00+00:00"]

    @staticmethod
    def _chrono_request(paths: list[str], times: list[str | None] | None) -> VlmAssessRequest:
        request = _request(paths)
        if times is not None:
            request = request.model_copy(update={"frame_capture_times": times})
        return request

    def test_the_prompt_states_the_order_and_labels_each_frame(self) -> None:
        client = make_client(camera_timezone="America/New_York")
        prompt = client._render_prompt(
            [], self._chrono_request(["/x/a.jpg", "/x/b.jpg"], self._TIMES)
        )
        assert "Frames are in chronological order" in prompt
        # Local wall time with zone, the render_prompt_time shape.
        assert "Frame 1: 2026-09-25 06:00:00 local (America/New_York, UTC-04:00)" in prompt
        assert "Frame 2: 2026-09-25 07:00:00 local (America/New_York, UTC-04:00)" in prompt

    def test_an_unknown_time_renders_unknown_not_arrival(self) -> None:
        """The row's arrival would be 15:00 UTC; "unknown" must not become
        that number by way of a fallback."""
        client = make_client(camera_timezone="America/New_York")
        prompt = client._render_prompt(
            [], self._chrono_request(["/x/a.jpg", "/x/b.jpg"], [self._TIMES[0], None])
        )
        assert "Frame 2: unknown" in prompt
        assert "15:00" not in prompt

    def test_labels_render_without_a_camera_timezone_too(self) -> None:
        """A hand-built request (replay, or any caller that knows capture
        times) gets honest UTC labels even when the camera zone is unset —
        the labels come from the request, not from settings."""
        client = make_client(camera_timezone=None)
        prompt = client._render_prompt([], self._chrono_request(["/x/a.jpg"], self._TIMES[:1]))
        assert "Frames are in chronological order" in prompt
        assert "Frame 1: 2026-09-25T10:00:00+00:00" in prompt

    def test_an_absent_field_leaves_the_prompt_byte_identical(self) -> None:
        """The field defaults to None, so every existing prompt (S5 parity,
        every store built before this change) renders exactly as before."""
        for tz in (None, "America/New_York"):
            client = make_client(camera_timezone=tz)
            without = client._render_prompt([], _request(["/x/a.jpg", "/x/b.jpg"]))
            nulled = client._render_prompt([], self._chrono_request(["/x/a.jpg", "/x/b.jpg"], None))
            assert without == nulled
            assert "chronological" not in without


class TestProvenanceIsStampedNotTrusted:
    """A5500 M1 chain, 2026-09-28: the verdict schema asked the MODEL for its
    own provenance ("copy the values from the served model's own reported
    identity") - which it cannot know, and the grammar forces it to write
    something: event 613's row stored engine = model_id = the camera id.
    Provenance is who answered; the client knows that from /props and its own
    settings, so it stamps it and never trusts the model's copy (here the
    strict fake writes "ok" into every string)."""

    @staticmethod
    def _client(model_path: str | None) -> vc.VlmClient:
        settings = vc.get_settings().model_copy(update={"vlm_enforcement_probe_enabled": True})
        return vc.VlmClient(
            base_url="http://fake-vlm:8098",
            transport=RecordingTransport(make_fake_llama("strict", model_path=model_path)),
            settings=settings,
        )

    async def test_the_served_identity_replaces_the_models_copy(self, image_dir) -> None:
        client = self._client("/models/Qwen3VL-8B-Instruct-Q4_K_M.gguf")
        verdict = await client.assess(_request([str(image_dir / "front_door/a.jpg")]))
        label = client._settings.nemotron_verification_engine
        assert verdict.provenance.engine == f"{label}@{_BUILD_INFO}"
        assert verdict.provenance.model_id == "Qwen3VL-8B-Instruct-Q4_K_M"

    async def test_the_configured_identity_when_the_server_does_not_say(self, image_dir) -> None:
        client = self._client(None)
        verdict = await client.assess(_request([str(image_dir / "front_door/a.jpg")]))
        assert verdict.provenance.model_id == client._settings.vlm_model_id
        assert verdict.provenance.engine.endswith(f"@{_BUILD_INFO}")


class TestBboxConventionIsStated:
    """A5500 M1 chain, 2026-09-28: detection rows carry bbox as the store's
    [x, y, width, height], rendered as a bare list. The 8B read it as corners
    ("width of 272 - 511 = -239, which is impossible"), called three 0.94
    person detections erroneous and scored the event 0/low. The prompt must
    say what the four numbers are. Since the native-grounding fix (below) this
    is the FALLBACK: a frame whose size cannot be read (these fixture stills
    are not decodable) keeps the snapshot's pixel numbers, and says so."""

    def test_the_prompt_names_the_bbox_convention(self, image_dir) -> None:
        det = {"id": 1, "object_type": "person", "confidence": 0.94, "bbox": [511, 242, 272, 456]}
        text = make_client().prompt_text(
            _request([str(image_dir / "front_door/a.jpg")], detections=[det])
        )
        assert "[x, y, width, height]" in text
        assert "[511, 242, 272, 456]" in text, "the rendered numbers stay the snapshot's"


class TestBoxesAreGroundedInTheFrame:
    """A5500 M1 re-run, 2026-09-28: with the [x, y, width, height] convention
    stated, the 8B still called a tight, correct person box on a 1280x704
    still "too small or positioned incorrectly" and scored a hooded figure
    at the door at night uncertain/0 - it cannot place pixel numbers without
    the frame size, and it treated box arithmetic as evidence of a false
    detection. The prompt now names the frame size and says the boxes are
    localization aids, not a verdict input. Owner ruling 2026-09-28."""

    @staticmethod
    def _still(root: Path, name: str, size: tuple[int, int]) -> str:
        from PIL import Image

        path = root / "front_door" / name
        Image.new("RGB", size, (40, 40, 40)).save(path, "JPEG")
        return str(path)

    _DET: ClassVar = {
        "id": 1,
        "object_type": "person",
        "confidence": 0.93,
        "bbox": [551, 217, 180, 477],
    }

    def test_pixel_boxes_name_their_frame_sizes(self, image_dir) -> None:
        # Two sizes and no row-to-frame link: no single frame to scale by, so
        # the rows keep pixels and the prompt names the sizes they are in.
        big = self._still(image_dir, "big.jpg", (1280, 704))
        small = self._still(image_dir, "small.jpg", (640, 480))
        text = make_client().prompt_text(_request([big, small], detections=[self._DET]))
        assert "[x, y, width, height]" in text
        assert "1280x704 or 640x480" in text

    def test_boxes_are_localization_aids_not_verdict_evidence(self, image_dir) -> None:
        still = self._still(image_dir, "sized.jpg", (1280, 704))
        text = make_client().prompt_text(_request([still], detections=[self._DET]))
        assert "never reject a detection because of its box numbers" in text

    def test_no_detections_means_no_box_guidance(self, image_dir) -> None:
        text = make_client().prompt_text(
            _request([str(image_dir / "front_door/a.jpg")], detections=[])
        )
        assert "bbox" not in text, "an item with no boxes keeps the pre-fix prompt"


class TestRowsNameTheirFrame:
    """A5500 M1 re-run, 2026-09-28: three person detections from three stills,
    one still attached. The model: "a single individual ... no evidence of
    multiple people ... the bounding boxes appear to be misaligned" - it read
    all three boxes as boxes on the one frame it could see. When the request
    links rows to attached frames, each rendered row says which frame it is
    on (null = a frame not attached); without the link, rows render exactly
    as before (replays of the existing corpus stay byte-identical)."""

    @staticmethod
    def _rows() -> list[dict[str, Any]]:
        return [
            {"id": i, "object_type": "person", "confidence": 0.9, "bbox": [10, 20, 30, 40]}
            for i in (1, 2, 3)
        ]

    @staticmethod
    def _rendered_rows(text: str) -> list[dict[str, Any]]:
        line = next(ln for ln in text.splitlines() if ln.startswith("Detections: "))
        return json.loads(line.removeprefix("Detections: "))

    def test_each_row_names_its_attached_frame(self, image_dir) -> None:
        base = _request([str(image_dir / "front_door/a.jpg")], detections=self._rows())
        request = VlmAssessRequest(
            image_paths=base.image_paths, context=base.context, frame_detection_ids=[[2]]
        )
        text = make_client().prompt_text(request)
        assert {r["id"]: r["frame"] for r in self._rendered_rows(text)} == {1: None, 2: 1, 3: None}
        assert "not attached" in text

    def test_without_frame_links_rows_render_unchanged(self, image_dir) -> None:
        request = _request([str(image_dir / "front_door/a.jpg")], detections=self._rows())
        assert all(
            "frame" not in r for r in self._rendered_rows(make_client().prompt_text(request))
        )


class TestBoxesUseTheModelsOwnGrounding:
    """A5500, 2026-09-28: with the pixel convention stated, the frame size
    named and each row's frame linked, the 8B still rejected a correct
    419x513 person box on a 1280x704 still as "too small" (M1 event 617).
    Qwen3-VL's own grounding format is bbox_2d = [x1, y1, x2, y2] on a 0-1000
    scale of the frame - read that way, [369, 183, 419, 513] IS a sliver. On
    the 38-item detections set (run a4e42603 vs d7d1e7fb) sending the model
    its own format moved the verdict mix from 9 confirmed / 21 uncertain to
    33 / 2. The rendered copy only: the snapshot keeps its pixels (the eval
    corpus and the stored rows stay comparable). Owner ruling 2026-09-28."""

    @staticmethod
    def _still(root: Path, name: str, size: tuple[int, int]) -> str:
        from PIL import Image

        path = root / "front_door" / name
        Image.new("RGB", size, (40, 40, 40)).save(path, "JPEG")
        return str(path)

    @staticmethod
    def _rendered_rows(text: str) -> list[dict[str, Any]]:
        line = next(ln for ln in text.splitlines() if ln.startswith("Detections: "))
        return json.loads(line.removeprefix("Detections: "))

    @staticmethod
    def _det(det_id: int, bbox: list[int]) -> dict[str, Any]:
        return {"id": det_id, "object_type": "person", "confidence": 0.95, "bbox": bbox}

    def test_a_sized_frame_sends_corners_on_the_0_1000_scale(self, image_dir) -> None:
        still = self._still(image_dir, "m1.jpg", (1280, 704))
        text = make_client().prompt_text(
            _request([still], detections=[self._det(1, [369, 183, 419, 513])])
        )
        (row,) = self._rendered_rows(text)
        # x1 = 369/1280, y1 = 183/704, x2 = (369+419)/1280, y2 = (183+513)/704
        assert row["bbox_2d"] == [288, 260, 616, 989]
        assert "bbox" not in row, "one box per row - never both conventions at once"
        assert "[x1, y1, x2, y2]" in text
        assert "0-1000" in text
        assert "[x, y, width, height]" not in text

    def test_the_snapshot_keeps_its_pixels(self, image_dir) -> None:
        still = self._still(image_dir, "m1.jpg", (1280, 704))
        request = _request([still], detections=[self._det(1, [369, 183, 419, 513])])
        make_client().prompt_text(request)
        assert request.context.detections[0]["bbox"] == [369, 183, 419, 513]

    def test_each_linked_row_scales_by_its_own_frame(self, image_dir) -> None:
        big = self._still(image_dir, "big.jpg", (1000, 500))
        small = self._still(image_dir, "small.jpg", (500, 250))
        base = _request(
            [big, small],
            detections=[self._det(1, [100, 100, 100, 100]), self._det(2, [100, 100, 100, 100])],
        )
        request = VlmAssessRequest(
            image_paths=base.image_paths, context=base.context, frame_detection_ids=[[1], [2]]
        )
        rows = {r["id"]: r for r in self._rendered_rows(make_client().prompt_text(request))}
        assert rows[1]["bbox_2d"] == [100, 200, 200, 400]
        assert rows[2]["bbox_2d"] == [200, 400, 400, 800]

    def test_a_box_past_the_edge_is_clamped_to_the_frame(self, image_dir) -> None:
        still = self._still(image_dir, "edge.jpg", (1000, 1000))
        text = make_client().prompt_text(
            _request([still], detections=[self._det(1, [900, 950, 300, 300])])
        )
        (row,) = self._rendered_rows(text)
        assert row["bbox_2d"] == [900, 950, 1000, 1000]

    def test_a_row_without_a_box_renders_unchanged(self, image_dir) -> None:
        still = self._still(image_dir, "m1.jpg", (1280, 704))
        det = {"id": 1, "object_type": "person", "confidence": 0.9}
        (row,) = self._rendered_rows(make_client().prompt_text(_request([still], detections=[det])))
        assert "bbox_2d" not in row


class TestContextOverflowIsABudget:
    """A5500, 2026-09-28: a fitted prompt the slot could not hold came back
    HTTP 400 `exceed_context_size_error` - and the client filed it as a
    TRANSPORT error: one breaker failure, then the §6 retry re-sent the same
    bytes for a second 400 and a second failure. Five such batches open
    `ai-vlm` for every camera over a number WE mis-estimated. Like a
    truncated verdict, it is a budget: raised once, named, counted under its
    own cause, never fed to the breaker - and still verification_failed."""

    async def test_it_raises_its_own_cause_once(self, image_dir) -> None:
        client = make_client("context_overflow", vlm_enforcement_probe_enabled=False)
        with pytest.raises(vc.VlmContextOverflowError) as caught:
            await client.assess(_request([str(image_dir / "front_door/a.jpg")]))
        assert len(client._app_calls()) == 1, "the same bytes cannot fit on a retry"
        assert "22293" in str(caught.value) and "16384" in str(caught.value)
        assert not isinstance(caught.value, vc.VlmTransportError)
        await client.close()

    async def test_it_is_counted_under_its_own_cause(
        self, image_dir, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        recorded: list[str] = []
        monkeypatch.setattr(vc, "record_pipeline_error", lambda reason: recorded.append(reason))
        client = make_client("context_overflow", vlm_enforcement_probe_enabled=False)
        with pytest.raises(vc.VlmContextOverflowError):
            await client.assess(_request([str(image_dir / "front_door/a.jpg")]))
        await client.close()
        assert recorded == ["vlm_context_overflow"], recorded

    async def test_it_never_opens_the_breaker(self, image_dir) -> None:
        from backend.services.circuit_breaker import get_circuit_breaker

        client = make_client("context_overflow", vlm_enforcement_probe_enabled=False)
        for _ in range(10):  # well past the breaker's 5-failure threshold
            with pytest.raises(vc.VlmContextOverflowError):
                await client.assess(_request([str(image_dir / "front_door/a.jpg")]))
        await client.close()
        assert not get_circuit_breaker("ai-vlm").is_open, "a budget must not open a service breaker"

    async def test_any_other_400_is_still_a_transport_error(self, image_dir) -> None:
        client = make_client("down", vlm_enforcement_probe_enabled=False)
        with pytest.raises(vc.VlmTransportError):
            await client.assess(_request([str(image_dir / "front_door/a.jpg")]))
        await client.close()


class TestSlowReplyIsNotABrokenEngine:
    """`00 §3` D1. A reply that outruns `ai_vlm_read_timeout` (25 s) came back
    as a TRANSPORT error: one breaker failure, then the §6 retry re-sent the
    SAME bytes for a second timeout and a second failure - five slow items
    open `ai-vlm` for every camera over a budget WE chose. This is
    `TestContextOverflowIsABudget` on the timeout leg: the request leaves
    unchanged, so a retry re-asks the identical question and, at the same
    speed, times out identically. The breaker's question is "stop calling
    this engine?" and a slow reply answers NO - the connection held, the
    grammar applied, the engine was doing real work. One charge, no identical
    retry, and the item still answers verification_failed with a NULL score.
    """

    @staticmethod
    def _timing_out_transport() -> _TimingOutTransport:
        return _TimingOutTransport()

    async def test_a_slow_reply_is_asked_once(self, image_dir) -> None:
        """No identical retry: the bytes that timed out are the bytes that
        would time out again."""
        transport = self._timing_out_transport()
        client = self._client(transport)
        with pytest.raises(vc.VlmClientError):
            await client.assess(_request([str(image_dir / "front_door/a.jpg")]))
        assert transport.chat_calls == 1, (
            f"a slow reply was re-asked {transport.chat_calls} times; the request is "
            "unchanged, so a second attempt times out identically"
        )
        await client.close()

    async def test_a_slow_reply_charges_the_breaker_at_most_once(self, image_dir) -> None:
        from backend.services.circuit_breaker import get_circuit_breaker

        transport = self._timing_out_transport()
        client = self._client(transport)
        with pytest.raises(vc.VlmClientError):
            await client.assess(_request([str(image_dir / "front_door/a.jpg")]))
        await client.close()
        assert get_circuit_breaker("ai-vlm").failure_count <= 1, (
            f"one slow reply charged the breaker "
            f"{get_circuit_breaker('ai-vlm').failure_count} times"
        )

    async def test_slow_replies_never_open_the_breaker(self, image_dir) -> None:
        """Ten slow items is ten UNMEASURED verdicts, not a service outage: an
        opened breaker answers every later camera WITHOUT I/O, so the report
        describes a breaker instead of a model."""
        from backend.services.circuit_breaker import get_circuit_breaker

        client = self._client(self._timing_out_transport())
        for _ in range(10):  # well past the breaker's 5-failure threshold
            with pytest.raises(vc.VlmClientError):
                await client.assess(_request([str(image_dir / "front_door/a.jpg")]))
        await client.close()
        assert not get_circuit_breaker("ai-vlm").is_open, "a budget must not open a service breaker"

    async def test_a_refused_connection_still_charges_the_breaker(self, image_dir) -> None:
        """The triage must not forgive a broken engine: a server that refuses
        the connection is still a transport failure, still retried, and still
        fed to the breaker - the one signal that the engine is down."""
        from backend.services.circuit_breaker import get_circuit_breaker

        client = make_client("down", vlm_enforcement_probe_enabled=False)
        with pytest.raises(vc.VlmTransportError):
            await client.assess(_request([str(image_dir / "front_door/a.jpg")]))
        assert len(client._app_calls()) == 2, "a real fault keeps its §6 retry"
        assert get_circuit_breaker("ai-vlm").failure_count >= 1
        await client.close()

    async def test_a_stalled_write_is_a_budget_too(self, image_dir) -> None:
        """The assess body carries base64 images (up to `vlm_max_image_bytes`
        per item), so the WRITE phase can stall and httpx raises
        `httpx.WriteTimeout` - which is NOT a subclass of `ReadTimeout`
        (measured at head: `issubclass(httpx.WriteTimeout, httpx.ReadTimeout)
        is False`). Before the classification widened, that landed in the
        `except Exception` transport arm: breaker charged, then the §6 retry
        re-sent the BYTE-IDENTICAL multi-megabyte body (`_ASSESS_TEMPERATURE`
        is already 0.0) and charged a second time - two charges and a second
        full write for a stall under a budget we chose. The same socket, the
        same our-side budget, the same identical-retry futility as the read
        leg: a budget, not an outage. One ask, no charge."""
        from backend.services.circuit_breaker import get_circuit_breaker

        transport = _StalledWriteTransport()
        client = self._client(transport)
        with pytest.raises(vc.VlmSlowReplyError):
            await client.assess(_request([str(image_dir / "front_door/a.jpg")]))
        assert transport.chat_calls == 1, "the identical body must not be re-sent"
        assert get_circuit_breaker("ai-vlm").failure_count == 0, (
            "a stalled write is OUR budget; it must not charge the breaker"
        )
        await client.close()

    async def test_a_connect_timeout_stays_a_transport_error(self, image_dir) -> None:
        """The triage must not widen the budget past its own definition: a
        server that never completes the TCP connect never had our bytes at
        all - no request was sent, so there is no identical-retry futility
        and no budget that was spent. `httpx.ConnectTimeout` stays a
        transport error, keeps its §6 retry, and stays breaker-fed. This is
        the guard against widening the timeout clause to all of
        `httpx.TimeoutException`, which would silently de-breaker real
        outages."""
        from backend.services.circuit_breaker import get_circuit_breaker

        class RefusingTransport(httpx.AsyncBaseTransport):
            async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
                raise httpx.ConnectTimeout("connection timed out", request=request)

        client = self._client(RefusingTransport())
        with pytest.raises(vc.VlmTransportError):
            await client.assess(_request([str(image_dir / "front_door/a.jpg")]))
        assert get_circuit_breaker("ai-vlm").failure_count >= 1, (
            "a connect timeout is the engine being down, not our budget"
        )
        await client.close()

    async def test_a_stalled_write_on_the_probe_leg_is_a_budget_too(self, image_dir) -> None:
        """The enforcement probe ships the same image-bearing body shape, so
        it can stall in the write phase too. It must fail closed the same
        way its read-timeout arm does (inconclusive, nothing cached) WITHOUT
        feeding the breaker - the probe leg's own D1 ruling, extended to the
        phase its clause forgot."""
        from backend.services.circuit_breaker import get_circuit_breaker

        settings = vc.get_settings().model_copy(update={"vlm_enforcement_probe_enabled": True})
        client = vc.VlmClient(
            base_url="http://fake-vlm:8098",
            transport=_StalledWriteTransport(),
            settings=settings,
        )
        with pytest.raises(vc.ConstrainedDecodingNotEnforced):
            await client.assess(_request([str(image_dir / "front_door/a.jpg")]))
        assert get_circuit_breaker("ai-vlm").failure_count == 0, (
            "the probe's write stall is the same budget the read stall is"
        )
        await client.close()

    async def test_a_connect_timeout_on_the_probe_leg_is_a_fault_not_a_budget(
        self, image_dir, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The probe-leg mirror of test_a_connect_timeout_stays_a_transport_error.
        The reviewer's mutation run showed that widening the probe clause at
        `vlm_client.py:437` to all of `httpx.TimeoutException` - the maximal
        "everything is a budget" form the module header rules out - left this
        file's timeout suite green: only `test_vlm_client_batch37_o.py` noticed,
        and only via message prose. Pinned here on the two assertions a
        widening genuinely breaks: the CAUSE is `vlm_probe_transport` (not the
        budget's own cause) and the fault FEEDS the breaker. A socket that
        never connected spent none of our budget - the engine is unreachable,
        which is exactly the outage the breaker exists to report."""
        from backend.services.circuit_breaker import get_circuit_breaker

        recorded: list[str] = []
        monkeypatch.setattr(vc, "record_pipeline_error", lambda reason: recorded.append(reason))

        class ConnectTimeoutTransport(httpx.AsyncBaseTransport):
            """/props answers (the build pin passes) so the CHAT leg is what
            refuses to connect - the props leg's own refusal is pinned in
            TestEnforcementProbe."""

            async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
                if request.url.path == vc.CHAT_PATH:
                    raise httpx.ConnectTimeout("connection timed out", request=request)
                return httpx.Response(200, json={"build_info": "b7972-e06088da0"}, request=request)

        settings = vc.get_settings().model_copy(update={"vlm_enforcement_probe_enabled": True})
        client = vc.VlmClient(
            base_url="http://fake-vlm:8098",
            transport=ConnectTimeoutTransport(),
            settings=settings,
        )
        with pytest.raises(vc.ConstrainedDecodingNotEnforced) as caught:
            await client.assess(_request([str(image_dir / "front_door/a.jpg")]))
        await client.close()
        assert caught.value.verdict == "inconclusive", "fail closed, nothing cached"
        assert recorded == ["vlm_probe_transport"], (
            "a connect timeout is the engine being unreachable, not our read budget"
        )
        assert get_circuit_breaker("ai-vlm").failure_count >= 1, (
            "the probe leg feeds the breaker for a connect fault - the symmetric "
            "budget arm must not swallow it"
        )

    async def test_the_timeout_phase_is_pinned_in_message_and_log(
        self, image_dir, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """`timeout_phase` was produced at `vlm_client.py:457`/`:1001` and
        asserted zero times; the raised message interpolates
        `ai_vlm_read_timeout` even when the stalled phase is WRITE (write
        inherits 25.0 only because `_http()` passes the read value as
        `Timeout()`'s positional default). A write-stall log that names the
        read knob sends an operator to the wrong setting, so the phase is
        pinned here in BOTH the raised message and the log extra, both
        phases. Transport-layer pinning as everywhere in this class: ASGI
        and custom transports never enforce timeouts, so the exception is
        raised, not aged into."""
        logged: list[dict] = []

        class _RecordingLogger:
            def warning(self, msg: str, **kw: Any) -> None:
                logged.append({"msg": msg, **kw})

            def __getattr__(self, _name: str):
                return lambda *_a, **_k: None

        monkeypatch.setattr(vc, "logger", _RecordingLogger())

        for transport, phase in (
            (_TimingOutTransport(), "read"),
            (_StalledWriteTransport(), "write"),
        ):
            logged.clear()
            client = self._client(transport)
            with pytest.raises(vc.VlmSlowReplyError) as raised:
                await client.assess(_request([str(image_dir / "front_door/a.jpg")]))
            await client.close()
            assert f"{phase} budget" in str(raised.value), (
                f"a {phase} stall must name the {phase} phase, not inherit the other's wording"
            )
            phases = [
                r.get("extra", {}).get("timeout_phase")
                for r in logged
                if "extra" in r and "timeout_phase" in r["extra"]
            ]
            assert phases == [phase], (
                f"exactly one timeout_phase={phase!r} log record expected, got {phases!r}"
            )

    def _client(self, transport: httpx.AsyncBaseTransport) -> vc.VlmClient:
        settings = vc.get_settings().model_copy(update={"vlm_enforcement_probe_enabled": False})
        return vc.VlmClient(base_url="http://fake-vlm:8098", transport=transport, settings=settings)


class _TimingOutTransport(httpx.AsyncBaseTransport):
    """Raises `httpx.ReadTimeout` on the chat leg exactly as a socket timeout
    would, and counts the chat requests so a test can see an identical retry.
    ASGITransport never enforces timeouts (the 1.1 lesson), so "slower than
    the read timeout" can only be pinned at the transport layer - and httpx
    does not apply a read timeout to a custom transport either (measured: a 3
    s handler under a 0.2 s timeout returns 200), which is why this raises the
    exception rather than being slow."""

    def __init__(self) -> None:
        self.chat_calls = 0

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        if request.url.path == vc.CHAT_PATH:
            self.chat_calls += 1
            raise httpx.ReadTimeout("read timeout", request=request)
        return httpx.Response(200, json={"build_info": "b7972-e06088da0"}, request=request)


class _StalledWriteTransport(httpx.AsyncBaseTransport):
    """Raises `httpx.WriteTimeout` on the chat leg exactly as a server that
    stops reading the request body would (the assess/probe bodies carry
    base64 images, so the write phase is real and can stall). Same
    transport-layer pinning rationale as `_TimingOutTransport`: a custom
    transport never enforces timeouts, so the exception is raised, not
    aged into. Counts chat requests for the identical-retry assertion."""

    def __init__(self) -> None:
        self.chat_calls = 0

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        if request.url.path == vc.CHAT_PATH:
            self.chat_calls += 1
            raise httpx.WriteTimeout("write timeout", request=request)
        return httpx.Response(200, json={"build_info": "b7972-e06088da0"}, request=request)


class TestEveryCauseIsListed:
    """B1.1 found the allowlist drifting: `KNOWN_ERROR_TYPES` guards the
    `error_type` Prometheus label against cardinality explosion by collapsing
    anything unlisted to "other", and the block that claims to cover "the VLM
    path's ladder labels" was missing five of them - so five causes, including
    both budget causes whose entire value is a DISTINGUISHABLE cause, recorded
    as "other" and the S4/S5 dashboards read a blank where the diagnosis is.
    A comment cannot keep a list and a call site in sync; this parses the call
    site."""

    _CAUSE_CALLERS: ClassVar = ("_note_failure", "_note_budget_exhausted", "record_pipeline_error")

    @staticmethod
    def _emitted_causes() -> set[str]:
        """Every string literal this module passes to a cause-recording call.

        Scope note: constant first args of the CAUSE-RECORDING calls only.
        Raised MESSAGES are not in its domain - some are assembled at runtime
        (the `VlmSlowReplyError(f"...")` at the read-budget raise is invisible
        to this walk, by design): a raise message never becomes an
        `error_type` label; only the `cause` argument of a recording call does."""
        tree = ast.parse(inspect.getsource(vc))
        causes: set[str] = set()
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or not node.args:
                continue
            func = node.func
            name = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", None)
            first = node.args[0]
            if name in TestEveryCauseIsListed._CAUSE_CALLERS and isinstance(first, ast.Constant):
                if isinstance(first.value, str):
                    causes.add(first.value)
        return causes

    def test_every_emitted_cause_survives_sanitization(self) -> None:
        from backend.core.sanitization import KNOWN_ERROR_TYPES, sanitize_error_type

        emitted = self._emitted_causes()
        assert emitted, "the AST walk found no causes - did the recording helpers get renamed?"
        collapsed = sorted(c for c in emitted if sanitize_error_type(c) != c)
        assert not collapsed, (
            f"{collapsed} are recorded by vlm_client but absent from KNOWN_ERROR_TYPES, "
            "so the metric labels them 'other' (the drift B1.1 found)"
        )
        assert emitted <= KNOWN_ERROR_TYPES

    def test_the_two_new_budget_causes_are_listed(self) -> None:
        """The specific regression B1.1 ships: named causes, not "other"."""
        from backend.core.sanitization import KNOWN_ERROR_TYPES, sanitize_error_type

        for cause in ("vlm_assess_timeout", "vlm_probe_timeout"):
            assert cause in KNOWN_ERROR_TYPES, cause
            assert cause in self._emitted_causes(), cause
            assert sanitize_error_type(cause) == cause
