"""Chunk-20 kill battery: enrichment_pipeline (chunk 20 of the #26 batch).

Owned shapes (120 keys, 120 distinct shape groups — every group has exactly one
key, so "twins" here means one test per key):

  A) ``EnrichmentPipeline.__init__`` (shipped 2068-2227) — 30 keys
  B) ``EnrichmentPipeline._detect_threats_via_service`` (5167-5282) — 8 keys
  C) ``EnrichmentPipeline._safe_extract_osnet_embeddings`` (3395-3449) — 31 keys
  D) ``EnrichmentPipeline._handle_enrichment_error`` (2239-2311) — 16 keys
  E) ``EnrichmentPipeline._detect_violence`` (6491-6530) — 18 keys
  F) ``EnrichmentResult.to_prompt_context`` (1575-1647) — 15 keys

Every value asserted below was MEASURED against pristine HEAD source with the
harnesses in /tmp/wp-ep/probes/c20/probe{1,2,3,4}.py (same mock topology as
these tests); shipped quirks are pinned as shipped — e.g.

* ``result.add_error(op, None)`` does NOT raise: ``EnrichmentError.from_exception``
  falls through every isinstance leg and returns
  ``category=unexpected, reason='Unexpected error: None', error_type='NoneType'``
  (probe3) — which is exactly what makes key ``_handle_enrichment_error__mutmut_3``
  observable;
* the empty-``persons`` guard in ``_safe_extract_osnet_embeddings`` returns before
  ``model_manager.load`` is ever entered (probe3: ``load called: []``);
* ``format_vehicle_damage_context({}, time_of_day=...)`` ignores the time context
  entirely when the damage dict is empty (probe3) — so the ``time_of_day`` keys are
  pinned on the CALL, not on the returned string;
* ``operation.replace('_', '_')`` in the metric name is a shipped identity
  expression, and the ``'XX_XX'`` mutant of its first argument is a proven
  no-arg substitution (see verdicts_20.json for the reachability proof).

Collaborators are patched through ``getattr(M.EnrichmentPipeline, fn).__globals__``
(the live function's own globals dict) rather than ``patch.object(M, ...)``: the
ep_plugin swap exec's a variant body in a COPY of the module dict, so a swapped
mutant's ``__globals__`` is not ``M.__dict__``; patching through the function's
own globals is exactly equivalent under pristine code and additionally observed
by the mutants.  ``to_prompt_context`` imports its formatters from
``backend.services.prompts`` *inside* the call, so patching the prompts module
attributes is observed by pristine and mutant alike.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import types
from unittest.mock import AsyncMock, MagicMock, patch

import backend.services.enrichment_pipeline as M
import backend.services.prompts as PROMPTS
import httpx
import pytest
from backend.core.config import get_settings
from backend.core.logging import sanitize_error as REAL_SANITIZE
from PIL import Image

MODLOG = "backend.services.enrichment_pipeline"
PIPE = "_handle_enrichment_error"
OSNET = "_safe_extract_osnet_embeddings"
VIOL = "_detect_violence"
DVTS = "_detect_threats_via_service"
TPC = "to_prompt_context"

IMAGE = Image.new("RGB", (32, 32), "grey")
MODEL = object()  # what model_manager.load(...) yields as model_data
CROP = object()  # what _crop_to_bbox(...) returns
BBOX = M.BoundingBox(x1=1, y1=2, x2=30, y2=30)


class _LoadCM:
    """Stand-in for ``async with model_manager.load(name) as model_data``."""

    def __init__(self, result=MODEL, exc: BaseException | None = None) -> None:
        self.result = result
        self.exc = exc

    async def __aenter__(self):
        if self.exc is not None:
            raise self.exc
        return self.result

    async def __aexit__(self, *exc_info) -> bool:
        return False


def tg(method: str, cls=M.EnrichmentPipeline) -> dict:
    """Name-resolution dict of the LIVE function object (see module docstring).

    Pristine: ``M.__dict__``. Ep_plugin swap: the variant's snapshot dict
    (freshly compiled — no ``__wrapped__``). Mutants-tree re-bank (MEASURED
    2026-09-26): mutmut 3.8 trampoline-wraps every function and the wrapper's
    ``__globals__`` is mutmut's OWN module dict — the shipped implementation
    resolves ``M.__dict__``, reachable via ``__wrapped__``; unwrap only under
    that identity check, which is false in both other worlds.
    """
    f = getattr(cls, method)
    if f.__globals__ is not M.__dict__:
        w = getattr(f, "__wrapped__", None)
        if w is not None and w.__globals__ is M.__dict__:
            return M.__dict__
    return f.__globals__


def pipeline(load_exc: BaseException | None = None) -> M.EnrichmentPipeline:
    mm = MagicMock()
    mm.load = MagicMock(return_value=_LoadCM(exc=load_exc))
    return M.EnrichmentPipeline(model_manager=mm)


def person(det_id=None, bbox=BBOX):
    return types.SimpleNamespace(id=det_id, bbox=bbox)


def payload(record, keys: tuple[str, ...]) -> dict:
    """MEASURED harness fact (ADJUDICATION-RULES rule 5): the repo conftest/log
    config injects its own record attributes; ``extra=`` payloads are plain
    record attributes — read them with getattr(rec, key, None)."""
    return {k: getattr(record, k, None) for k in keys}


def logs_at(caplog, levelno: int) -> list[logging.LogRecord]:
    return [r for r in caplog.records if r.name == MODLOG and r.levelno == levelno]


# ========================================================================== #
# A) __init__ — default-argument mutants (def-line deltas)                    #
# ========================================================================== #


def _pin_enable_flag(attr: str) -> None:
    """MEASURED: shipped default is True (probe1) and the flag is stored verbatim."""
    p = M.EnrichmentPipeline(model_manager=MagicMock())
    assert getattr(p, attr) is True, f"shipped default of {attr} is True"
    q = M.EnrichmentPipeline(model_manager=MagicMock(), **{attr: False})
    assert getattr(q, attr) is False, f"{attr} must store the caller's value"


def test_init_depth_estimation_enabled_defaults_true():
    _pin_enable_flag("depth_estimation_enabled")


def test_init_pose_estimation_enabled_defaults_true():
    _pin_enable_flag("pose_estimation_enabled")


def test_init_action_recognition_enabled_defaults_true():
    _pin_enable_flag("action_recognition_enabled")


def test_init_scene_ocr_enabled_defaults_true():
    _pin_enable_flag("scene_ocr_enabled")


def test_init_age_classification_enabled_defaults_true():
    _pin_enable_flag("age_classification_enabled")


def test_init_gender_classification_enabled_defaults_true():
    _pin_enable_flag("gender_classification_enabled")


def test_init_smoke_fire_detection_enabled_defaults_true():
    _pin_enable_flag("smoke_fire_detection_enabled")


def test_init_yolo_world_enabled_defaults_true():
    _pin_enable_flag("yolo_world_enabled")


def test_init_osnet_reid_enabled_defaults_true():
    _pin_enable_flag("osnet_reid_enabled")


def test_init_low_light_enhancement_enabled_defaults_true():
    _pin_enable_flag("low_light_enhancement_enabled")


# ========================================================================== #
# A2) __init__ — attribute-assignment mutants (stored value, not the flag)    #
# ========================================================================== #


def _pin_stored_flag(attr: str) -> None:
    """MEASURED (probe1): ``self.<attr>`` mirrors the argument — True by default,
    and False when the caller passes False (so a ``= None`` assignment is visible
    in both directions)."""
    default = M.EnrichmentPipeline(model_manager=MagicMock())
    assert getattr(default, attr) is True, f"{attr} must be True by default"
    explicit = M.EnrichmentPipeline(model_manager=MagicMock(), **{attr: False})
    assert getattr(explicit, attr) is False, f"{attr} must store False when passed"


def test_init_stores_depth_estimation_enabled():
    _pin_stored_flag("depth_estimation_enabled")


def test_init_stores_scene_ocr_enabled():
    _pin_stored_flag("scene_ocr_enabled")


def test_init_stores_age_classification_enabled():
    _pin_stored_flag("age_classification_enabled")


def test_init_stores_gender_classification_enabled():
    _pin_stored_flag("gender_classification_enabled")


def test_init_stores_smoke_fire_detection_enabled():
    _pin_stored_flag("smoke_fire_detection_enabled")


def test_init_stores_yolo_world_enabled():
    _pin_stored_flag("yolo_world_enabled")


def test_init_stores_osnet_reid_enabled():
    _pin_stored_flag("osnet_reid_enabled")


def test_init_stores_low_light_enhancement_enabled():
    _pin_stored_flag("low_light_enhancement_enabled")


def test_init_smoke_consecutive_counts_starts_as_empty_dict():
    """MEASURED: ``_smoke_consecutive_counts`` is a fresh per-instance ``{}``."""
    a = M.EnrichmentPipeline(model_manager=MagicMock())
    assert isinstance(a._smoke_consecutive_counts, dict)
    assert a._smoke_consecutive_counts == {}
    a._smoke_consecutive_counts["cam1"] = 2
    b = M.EnrichmentPipeline(model_manager=MagicMock())
    assert b._smoke_consecutive_counts == {}, "must not be shared/class state"


def test_init_skeleton_action_service_starts_none():
    """MEASURED: lazy ST-GCN++ slot is ``None`` (falsy) until first use."""
    p = M.EnrichmentPipeline(model_manager=MagicMock())
    assert p._skeleton_action_service is None
    assert not p._skeleton_action_service


def test_init_reid_service_prefers_injected_then_global():
    """MEASURED (probe1): ``reid_service if reid_service is not None else
    get_reid_service()`` — injected instance wins, else the global factory."""
    injected = object()
    created = object()
    factory = MagicMock(return_value=created)
    with patch.dict(tg("__init__"), {"get_reid_service": factory}):
        p = M.EnrichmentPipeline(model_manager=MagicMock(), reid_service=injected)
        assert p._reid_service is injected, "an injected service must be kept"
        assert factory.call_args_list == [], "global factory must not run when injected"
        q = M.EnrichmentPipeline(model_manager=MagicMock())
        assert q._reid_service is created, "absent service must fall back to the factory"
        assert len(factory.call_args_list) == 1


def test_init_scene_ocr_service_gated_on_scene_ocr_enabled():
    """MEASURED (probe1): ``get_scene_ocr_service()`` runs (once) when the flag is
    on and the service is stored; with the flag off it is ``None`` and the factory
    is never called."""
    created = object()
    factory = MagicMock(return_value=created)
    with patch.dict(tg("__init__"), {"get_scene_ocr_service": factory}):
        on = M.EnrichmentPipeline(model_manager=MagicMock())
        assert on._scene_ocr_service is created
        assert on.scene_ocr_enabled is True
        off = M.EnrichmentPipeline(model_manager=MagicMock(), scene_ocr_enabled=False)
        assert off._scene_ocr_service is None
        assert off.scene_ocr_enabled is False
    assert len(factory.call_args_list) == 1, "factory runs only for the enabled instance"


def test_init_builds_florence_semaphore_from_settings():
    """MEASURED (probe1): ``asyncio.Semaphore(settings.enrichment_florence_
    concurrency)`` — value 3 under test settings."""
    p = M.EnrichmentPipeline(model_manager=MagicMock())
    sem = p._florence_semaphore
    assert isinstance(sem, asyncio.Semaphore), "must be a real asyncio semaphore"
    assert sem._value == get_settings().enrichment_florence_concurrency


def test_init_builds_clip_semaphore_from_settings():
    """MEASURED: same shape for the CLIP concurrency semaphore."""
    p = M.EnrichmentPipeline(model_manager=MagicMock())
    sem = p._clip_semaphore
    assert isinstance(sem, asyncio.Semaphore), "must be a real asyncio semaphore"
    assert sem._value == get_settings().enrichment_clip_concurrency


def test_init_quality_level_comes_from_settings():
    """MEASURED (probe1): ``_quality_level == settings.enrichment_quality_level``
    (``'full'`` under test settings), never ``None``."""
    p = M.EnrichmentPipeline(model_manager=MagicMock())
    assert p._quality_level == get_settings().enrichment_quality_level
    assert p._quality_level is not None


def test_init_records_the_quality_level_metric():
    """MEASURED: ``set_enrichment_quality_level(self._quality_level)`` is called
    exactly once with the instance's own quality level."""
    spy = MagicMock()
    with patch.dict(tg("__init__"), {"set_enrichment_quality_level": spy}):
        p = M.EnrichmentPipeline(model_manager=MagicMock())
    assert spy.call_args_list == [((p._quality_level,), {})]
    assert p._quality_level is not None


def test_init_logs_startup_banner(caplog):
    """MEASURED (probe1): INFO line 'EnrichmentPipeline initialized: license_plate=
    ...quality_level=full, pipeline_timeout=30.0s'."""
    caplog.clear()
    with caplog.at_level(logging.INFO, logger=MODLOG):
        M.EnrichmentPipeline(model_manager=MagicMock())
    msgs = [
        r.getMessage() for r in caplog.records if r.name == MODLOG and r.levelno == logging.INFO
    ]
    banner = [m for m in msgs if m.startswith("EnrichmentPipeline initialized:")]
    assert len(banner) == 1, msgs
    assert "license_plate=" in banner[0]
    assert "quality_level=" in banner[0]


# ========================================================================== #
# B) _detect_threats_via_service — parse-error handler log payload            #
# ========================================================================== #


@contextlib.contextmanager
def dtvs_collabs():
    subs = {
        "record_enrichment_model_call": MagicMock(),
        "record_enrichment_model_error": MagicMock(),
        "observe_enrichment_model_duration": MagicMock(),
    }
    with patch.dict(tg(DVTS), subs):
        yield subs


async def _dtvs_failure(exc: BaseException):
    p = pipeline()
    client = MagicMock()
    client.detect_threats = AsyncMock(side_effect=exc)
    p._get_enrichment_client = MagicMock(return_value=client)
    with dtvs_collabs():
        out = await M.EnrichmentPipeline._detect_threats_via_service(p, IMAGE)
    return out


@pytest.mark.asyncio
async def test_dtvs_parse_error_log_payload(caplog):
    """MEASURED (probe2): the ValueError handler logs levelno 40, message
    'Threat detection parse error', extra={'service': 'threat-via-service',
    'error_type': 'ValueError'} and returns None."""
    caplog.clear()
    with caplog.at_level(logging.DEBUG, logger=MODLOG):
        out = await _dtvs_failure(ValueError("bad payload"))
    assert out is None, "shipped: every handler returns None"
    recs = logs_at(caplog, logging.ERROR)
    assert [r.getMessage() for r in recs] == ["Threat detection parse error"], caplog.records
    rec = recs[0]
    assert payload(rec, ("service", "error_type")) == {
        "service": "threat-via-service",
        "error_type": "ValueError",
    }


@pytest.mark.asyncio
async def test_dtvs_parse_error_carries_exception_context(caplog):
    """MEASURED: that record is emitted with ``exc_info=True`` and the live
    exception instance (a bare ``logger.error(msg)`` leaves exc_info None)."""
    exc = ValueError("bad payload")
    caplog.clear()
    with caplog.at_level(logging.DEBUG, logger=MODLOG):
        await _dtvs_failure(exc)
    recs = logs_at(caplog, logging.ERROR)
    assert len(recs) == 1
    assert recs[0].exc_info is not None, "shipped passes exc_info=True"
    assert recs[0].exc_info[0] is ValueError
    assert recs[0].exc_info[1] is exc


# ========================================================================== #
# C) _safe_extract_osnet_embeddings                                          #
# ========================================================================== #


@contextlib.contextmanager
def osnet_collabs(extract: AsyncMock | None = None):
    subs = {
        "record_enrichment_model_call": MagicMock(),
        "record_enrichment_model_error": MagicMock(),
        "observe_enrichment_model_duration": MagicMock(),
        "extract_person_embedding": extract or AsyncMock(return_value=emb_result()),
    }
    with patch.dict(tg(OSNET), subs):
        yield subs


def emb_result(values=(0.1, 0.2)):
    r = MagicMock()
    r.embedding = list(values)
    return r


async def run_osnet(persons, *, crop=None, extract=None, load_exc=None):
    p = pipeline(load_exc)
    p._crop_to_bbox = AsyncMock(return_value=CROP) if crop is None else crop
    with osnet_collabs(extract) as subs:
        out = await M.EnrichmentPipeline._safe_extract_osnet_embeddings(p, persons, IMAGE)
    return out, p, subs


@pytest.mark.asyncio
async def test_osnet_empty_persons_short_circuits_before_model_load():
    """MEASURED (probe3): empty ``persons`` returns ``{}`` and model_manager.load
    is never entered; no metrics, no embedding calls."""
    extract = AsyncMock(return_value=emb_result())
    out, p, subs = await run_osnet([], extract=extract)
    assert out == {}
    assert p.model_manager.load.call_args_list == [], "guard must precede the load"
    assert [c.args for c in subs["record_enrichment_model_call"].call_args_list] == []
    assert [c.args for c in subs["observe_enrichment_model_duration"].call_args_list] == []
    assert extract.await_args_list == []


@pytest.mark.asyncio
async def test_osnet_loads_the_osnet_model_key():
    """MEASURED: the model key is exactly ``'osnet-ain-x1-0'`` (loaded once)."""
    out, p, _subs = await run_osnet([person(5)])
    assert [c.args[0] for c in p.model_manager.load.call_args_list] == ["osnet-ain-x1-0"]


@pytest.mark.asyncio
async def test_osnet_crops_every_person_in_order():
    """MEASURED: the loop runs once per person (crop called per detection)."""
    p_crop = AsyncMock(return_value=None)
    out, _p, subs = await run_osnet([person(1), person(2)], crop=p_crop)
    assert out == {}
    assert p_crop.await_count == 2, "one crop attempt per person"


@pytest.mark.asyncio
async def test_osnet_det_id_uses_person_id_else_position_index():
    """MEASURED (probe2): ids [7, 0, None] -> detection ids ['7', '1', '2'].
    Truthy ids win; falsy ids fall back to ``str(enumerate_index)`` — never
    ``str(None)`` and never ``None``."""
    extract = AsyncMock(return_value=None)
    _out, _p, _subs = await run_osnet([person(7), person(0), person(None)], extract=extract)
    assert [c.kwargs["detection_id"] for c in extract.await_args_list] == ["7", "1", "2"]


@pytest.mark.asyncio
async def test_osnet_crop_receives_image_and_person_bbox():
    """MEASURED: ``self._crop_to_bbox(image, person.bbox)`` positionally, with the
    caller's image object and the person's own bbox object."""
    p_crop = AsyncMock(return_value=None)
    b1 = M.BoundingBox(x1=5, y1=6, x2=7, y2=8)
    await run_osnet([person(1, b1), person(2)], crop=p_crop)
    assert [c.args for c in p_crop.await_args_list] == [(IMAGE, b1), (IMAGE, BBOX)]


@pytest.mark.asyncio
async def test_osnet_skips_persons_whose_crop_is_none():
    """MEASURED (probe2): with crops [None, CROP] only the second person yields an
    embedding entry (key '1'), and extraction is attempted once."""
    extract = AsyncMock(return_value=emb_result())
    p_crop = AsyncMock(side_effect=[None, CROP])
    out, _p, _subs = await run_osnet([person(3), person(None)], crop=p_crop, extract=extract)
    assert out == {"1": {"embedding": [0.1, 0.2], "embedding_dim": 2, "detection_id": "1"}}
    assert [c.args for c in extract.await_args_list] == [(MODEL, CROP)]


@pytest.mark.asyncio
async def test_osnet_extract_person_embedding_call_signature():
    """MEASURED: ``extract_person_embedding(model_data, crop, detection_id=det_id)``
    where model_data is the object yielded by ``model_manager.load(...)``."""
    extract = AsyncMock(return_value=emb_result())
    out, _p, _subs = await run_osnet([person(5)], extract=extract)
    call = extract.await_args_list[0]
    assert call.args == (MODEL, CROP)
    assert call.kwargs == {"detection_id": "5"}
    assert list(out) == ["5"]


@pytest.mark.asyncio
async def test_osnet_returns_embedding_entries_keyed_by_det_id():
    """MEASURED: entry IS ``{'embedding': tolist-able list, 'embedding_dim': len,
    'detection_id': det_id}`` — and the mapping is a dict (empty-safe)."""
    extract = AsyncMock(return_value=emb_result((0.5, 0.6, 0.7)))
    out, _p, _subs = await run_osnet([person(9)], extract=extract)
    assert isinstance(out, dict)
    assert out == {"9": {"embedding": [0.5, 0.6, 0.7], "embedding_dim": 3, "detection_id": "9"}}


@pytest.mark.asyncio
async def test_osnet_success_path_metrics_use_osnet_reid_label():
    """MEASURED: duration observed under label ``'osnet_reid'`` with a real float
    (``time.monotonic() - start`` >= 0), one call metric ``('osnet_reid',)`` and
    no error metric on the success path."""
    extract = AsyncMock(return_value=emb_result())
    out, _p, subs = await run_osnet([person(5)], extract=extract)
    assert list(out) == ["5"]
    obs = subs["observe_enrichment_model_duration"].call_args_list
    assert len(obs) == 1
    assert obs[0].args[0] == "osnet_reid"
    dur = obs[0].args[1]
    assert isinstance(dur, float) and dur >= 0.0, f"duration must be a real delta, got {dur!r}"
    assert [c.args for c in subs["record_enrichment_model_call"].call_args_list] == [
        ("osnet_reid",)
    ]
    assert [c.args for c in subs["record_enrichment_model_error"].call_args_list] == []


@pytest.mark.asyncio
async def test_osnet_success_observed_duration_is_a_small_delta():
    """MEASURED (probe2): duration is ``time.monotonic() - start`` over mocked work
    — a real, small (sub-second) float.  ``None`` (dropped ``start``) and the sum
    ``time.monotonic() + start`` (≈ 2× uptime) are both excluded."""
    extract = AsyncMock(return_value=emb_result())
    _out, _p, subs = await run_osnet([person(5)], extract=extract)
    (label, duration), _kwargs = subs["observe_enrichment_model_duration"].call_args_list[0]
    assert label == "osnet_reid"
    assert isinstance(duration, (int, float)), f"duration must be numeric, got {duration!r}"
    assert 0.0 <= duration < 1.0, f"shipped duration is a small delta, got {duration!r}"


@pytest.mark.asyncio
async def test_osnet_model_load_failure_returns_empty_and_records_error():
    """MEASURED: a load failure is swallowed to ``{}`` (dict, not None) and the
    error metric is recorded under label ``'osnet_reid'``."""
    out, _p, subs = await run_osnet([person(5)], load_exc=KeyError("osnet-ain-x1-0"))
    assert out == {}
    assert [c.args for c in subs["record_enrichment_model_error"].call_args_list] == [
        ("osnet_reid",)
    ]
    assert [c.args for c in subs["record_enrichment_model_call"].call_args_list] == []


@pytest.mark.asyncio
async def test_osnet_failure_debug_line_names_the_exception(caplog):
    """MEASURED (probe2): DEBUG 'OSNet embedding extraction skipped: model boom'."""
    caplog.clear()
    with caplog.at_level(logging.DEBUG, logger=MODLOG):
        out, _p, _subs = await run_osnet([person(5)], load_exc=RuntimeError("model boom"))
    assert out == {}
    debugs = [r.getMessage() for r in logs_at(caplog, logging.DEBUG)]
    assert debugs == ["OSNet embedding extraction skipped: model boom"], debugs


# ========================================================================== #
# D) _handle_enrichment_error — per-category dispatch                        #
# ========================================================================== #


def http_status_error(code: int) -> httpx.HTTPStatusError:
    req = httpx.Request("GET", "http://svc/x")
    resp = httpx.Response(code, request=req)
    return httpx.HTTPStatusError(f"HTTP {code}", request=req, response=resp)


@contextlib.contextmanager
def herror_collabs(**extra):
    """Spies on the handler's globals.

    ``logger`` is replaced by a MagicMock with ``wraps=`` the real logger, so the
    call is recorded AND still reaches the handler chain caplog reads (the call
    site is ``logger.warning(...)``, i.e. an attribute access on the module-level
    logger object — patching a ``"logger.warning"`` module key would be inert).
    """
    spy_logger = MagicMock(wraps=M.logger)
    subs = {
        "record_pipeline_error": MagicMock(),
        "logger": spy_logger,
        "sanitize_error": MagicMock(side_effect=REAL_SANITIZE),
    }
    subs.update(extra)
    with patch.dict(tg(PIPE), subs):
        yield subs


def run_herror(operation: str, exc: BaseException):
    """Drive the live handler; returns (error, result, collaborators)."""
    p = pipeline()
    result = M.EnrichmentResult()
    with herror_collabs() as subs:
        err = M.EnrichmentPipeline._handle_enrichment_error(p, operation, exc, result)
    return err, result, subs


def metric_of(subs) -> object:
    calls = subs["record_pipeline_error"].call_args_list
    assert len(calls) == 1, calls
    return calls[0].args[0]


def logged_of(subs, fn: str):
    """The single ``logger.<fn>(...)`` call the handler made.

    MEASURED harness fact: a MagicMock spy over the module logger records the
    attribute call as ``('warning', args, kwargs)`` — the bare attribute name.
    """
    name = fn.rsplit(".", 1)[-1]
    calls = subs["logger"].method_calls
    sel = [c for c in calls if c[0] == name]
    assert len(sel) == 1, calls
    return sel[0]


@pytest.mark.asyncio
async def test_herror_metric_name_contains_no_literal_placeholder():
    """MEASURED: metric is an f-string over ``operation.replace('_', '_')`` (a
    shipped identity) -> ``'face_detection_error_transient'``. The metric argument
    is always a non-empty string, never ``None``."""
    _err, _res, subs = run_herror("face_detection", httpx.ConnectError("connect refused"))
    metric = metric_of(subs)
    assert isinstance(metric, str), f"metric must be a string, got {metric!r}"
    assert metric == "face_detection_error_transient"


@pytest.mark.asyncio
async def test_herror_metric_name_preserves_operation_text_verbatim():
    """MEASURED: ``metric_name = f"{operation.replace('_', '_')}_error"`` — the
    shipped ``replace`` is the IDENTITY (its from/to arguments are both ``'_'``),
    so the operation text reaches the metric untouched even when it contains the
    substring ``'XX_XX'`` (mutmut's mutation sentinel): ``'XX_XX'`` must yield
    ``'XX_XX_error_transient'``, not ``'_error_transient'``.
    """
    for operation, expected in (
        ("face_detection", "face_detection_error_transient"),
        ("XX_XX", "XX_XX_error_transient"),
        ("clipXX_XXthreat_matching", "clipXX_XXthreat_matching_error_transient"),
    ):
        _err, _res, subs = run_herror(operation, httpx.ConnectError("no route"))
        assert metric_of(subs) == expected, f"operation {operation!r} was rewritten"


@pytest.mark.asyncio
async def test_herror_service_unavailable_and_timeout_are_transient(caplog):
    """MEASURED (probe2/3): SERVICE_UNAVAILABLE/TIMEOUT share one branch — metric
    ``<op>_error_transient``, WARNING '<op> service unavailable or timed out',
    extra['error'] == error.to_dict(), no traceback."""
    caplog.clear()
    with caplog.at_level(logging.DEBUG, logger=MODLOG):
        err, result, subs = run_herror("face_detection", httpx.ConnectError("connect refused"))
    assert err.category is M.ErrorCategory.SERVICE_UNAVAILABLE
    assert metric_of(subs) == "face_detection_error_transient"
    assert logged_of(subs, "warning").args[0] == ("face_detection service unavailable or timed out")
    recs = logs_at(caplog, logging.WARNING)
    assert [r.getMessage() for r in recs] == ["face_detection service unavailable or timed out"]
    assert recs[0].exc_info is None
    assert payload(recs[0], ("error",)) == {
        "error": {
            "operation": "face_detection",
            "category": "service_unavailable",
            "reason": "Service connection failed: connect refused",
            "error_type": "ConnectError",
            "is_transient": True,
            "details": {},
        }
    }
    assert result.errors == ["face_detection failed: Service connection failed: connect refused"]
    assert result.structured_errors == [err]


@pytest.mark.asyncio
async def test_herror_rate_limited_branch(caplog):
    """MEASURED: HTTP 429 -> metric ``_rate_limited`` + WARNING
    '<op> rate limited - backing off'."""
    caplog.clear()
    with caplog.at_level(logging.DEBUG, logger=MODLOG):
        err, _result, subs = run_herror("face_detection", http_status_error(429))
    assert err.category is M.ErrorCategory.RATE_LIMITED
    assert metric_of(subs) == "face_detection_error_rate_limited"
    assert logged_of(subs, "warning").args[0] == "face_detection rate limited - backing off"
    assert [r.getMessage() for r in logs_at(caplog, logging.WARNING)] == [
        "face_detection rate limited - backing off"
    ]
    assert payload(logs_at(caplog, logging.WARNING)[0], ("error",))["error"]["details"] == {
        "status_code": 429
    }


@pytest.mark.asyncio
async def test_herror_server_error_branch(caplog):
    """MEASURED: HTTP 5xx -> metric ``_server_error`` + WARNING
    '<op> server error (transient)'."""
    caplog.clear()
    with caplog.at_level(logging.DEBUG, logger=MODLOG):
        err, _result, subs = run_herror("face_detection", http_status_error(503))
    assert err.category is M.ErrorCategory.SERVER_ERROR
    assert metric_of(subs) == "face_detection_error_server_error"
    assert logged_of(subs, "warning").args[0] == "face_detection server error (transient)"
    assert [r.getMessage() for r in logs_at(caplog, logging.WARNING)] == [
        "face_detection server error (transient)"
    ]


@pytest.mark.asyncio
async def test_herror_client_error_branch(caplog):
    """MEASURED: HTTP 4xx -> metric ``_client_error`` + ERROR (with traceback)
    '<op> client error (likely a bug)' and ``is_transient=False``."""
    caplog.clear()
    with caplog.at_level(logging.DEBUG, logger=MODLOG):
        err, _result, subs = run_herror("face_detection", http_status_error(404))
    assert err.category is M.ErrorCategory.CLIENT_ERROR
    assert err.is_transient is False
    assert metric_of(subs) == "face_detection_error_client_error"
    call = logged_of(subs, "error")
    assert call.args[0] == "face_detection client error (likely a bug)"
    assert call.kwargs["exc_info"] is True
    recs = logs_at(caplog, logging.ERROR)
    assert len(recs) == 1 and recs[0].exc_info is not None


@pytest.mark.asyncio
async def test_herror_parse_error_branch(caplog):
    """MEASURED: ValueError -> metric ``face_detection_error_parse_error`` +
    ERROR 'face_detection response parsing failed' with traceback."""
    caplog.clear()
    with caplog.at_level(logging.DEBUG, logger=MODLOG):
        err, _result, subs = run_herror("face_detection", ValueError("bad response"))
    assert err.category is M.ErrorCategory.PARSE_ERROR
    assert metric_of(subs) == "face_detection_error_parse_error"
    call = logged_of(subs, "error")
    assert call.args[0] == "face_detection response parsing failed"
    assert call.kwargs["exc_info"] is True
    assert [r.getMessage() for r in logs_at(caplog, logging.ERROR)] == [
        "face_detection response parsing failed"
    ]


@pytest.mark.asyncio
async def test_herror_validation_error_branch(caplog):
    """MEASURED: AttributeError -> metric ``_validation_error`` + ERROR
    '<op> validation failed'."""
    caplog.clear()
    with caplog.at_level(logging.DEBUG, logger=MODLOG):
        err, _result, subs = run_herror("face_detection", AttributeError("no attr"))
    assert err.category is M.ErrorCategory.VALIDATION_ERROR
    assert metric_of(subs) == "face_detection_error_validation_error"
    call = logged_of(subs, "error")
    assert call.args[0] == "face_detection validation failed"
    assert call.kwargs["exc_info"] is True


@pytest.mark.asyncio
async def test_herror_unexpected_branch_message_and_metric(caplog):
    """MEASURED: a RuntimeError reaches UNEXPECTED -> metric ``_unexpected`` +
    ERROR '<op> unexpected error: <sanitize_error(exc)>' whose message carries the
    exception text, and ``sanitize_error`` is called with the live exception."""
    exc = RuntimeError("boom-secret")
    caplog.clear()
    with caplog.at_level(logging.DEBUG, logger=MODLOG):
        err, _result, subs = run_herror("face_detection", exc)
    assert err.category is M.ErrorCategory.UNEXPECTED
    assert metric_of(subs) == "face_detection_error_unexpected"
    assert subs["sanitize_error"].call_args_list[0].args[0] is exc
    call = logged_of(subs, "error")
    assert call.args[0] == "face_detection unexpected error: boom-secret"
    assert "boom-secret" in call.args[0]
    assert call.kwargs["exc_info"] is True
    assert [r.getMessage() for r in logs_at(caplog, logging.ERROR)] == [
        "face_detection unexpected error: boom-secret"
    ]


@pytest.mark.asyncio
async def test_herror_passes_the_live_exception_to_add_error():
    """MEASURED (probe3): ``result.add_error(operation, exc)`` classifies the LIVE
    exception. Passing ``None`` instead does not raise — from_exception falls
    through to ``category=unexpected / error_type='NoneType' / reason='Unexpected
    error: None'`` — so the classification and the reason text below are the
    observable difference."""
    exc = ValueError("bad payload")
    err, result, _subs = run_herror("face_detection", exc)
    assert err.error_type == "ValueError"
    assert err.reason == "Response parsing failed: bad payload"
    assert err.category is M.ErrorCategory.PARSE_ERROR
    assert result.errors == ["face_detection failed: Response parsing failed: bad payload"]
    assert err is result.structured_errors[0]


# ========================================================================== #
# E) _detect_violence                                                        #
# ========================================================================== #


def violence_result(violent: bool = True, conf: float = 0.83):
    return M.ViolenceDetectionResult(
        is_violent=violent,
        confidence=conf,
        violent_score=conf,
        non_violent_score=1.0 - conf,
    )


@contextlib.contextmanager
def viol_collabs(classify: AsyncMock):
    subs = {
        "classify_violence": classify,
        "record_enrichment_model_call": MagicMock(),
        "record_enrichment_model_error": MagicMock(),
        "observe_enrichment_model_duration": MagicMock(),
    }
    with patch.dict(tg(VIOL), subs):
        yield subs


async def run_violence(*, classify=None, load_exc=None):
    p = pipeline(load_exc)
    classify = classify or AsyncMock(return_value=violence_result())
    with viol_collabs(classify) as subs:
        try:
            out = await M.EnrichmentPipeline._detect_violence(p, IMAGE)
            err: BaseException | None = None
        except BaseException as exc:  # noqa: BLE001 - re-raised by the caller
            out, err = None, exc
    return out, err, subs, p


@pytest.mark.asyncio
async def test_violence_records_both_call_labels_in_order():
    """MEASURED (probe2): ``record_enrichment_model_call('violence')`` first, then
    ``record_enrichment_model_call('violence-detection')`` — both strings pinned."""
    out, err, subs, _p = await run_violence()
    assert err is None
    assert out is not None
    assert [c.args for c in subs["record_enrichment_model_call"].call_args_list] == [
        ("violence",),
        ("violence-detection",),
    ]
    assert [c.args for c in subs["record_enrichment_model_error"].call_args_list] == []
    obs = subs["observe_enrichment_model_duration"].call_args_list
    assert len(obs) == 1 and obs[0].args[0] == "violence-detection"


@pytest.mark.asyncio
async def test_violence_classify_violence_receives_model_data_and_image():
    """MEASURED: ``classify_violence(model_data, image)`` positionally."""
    classify = AsyncMock(return_value=violence_result(violent=False, conf=0.2))
    out, err, _subs, _p = await run_violence(classify=classify)
    assert err is None
    assert [c.args for c in classify.await_args_list] == [(MODEL, IMAGE)]


@pytest.mark.asyncio
async def test_violence_returns_the_classify_violence_result():
    """MEASURED: the returned value IS the object classify_violence produced —
    feeding it a non-None model_data/image is part of the contract."""
    vr = violence_result()
    classify = AsyncMock(return_value=vr)
    out, err, _subs, _p = await run_violence(classify=classify)
    assert err is None
    assert out is vr


@pytest.mark.asyncio
async def test_violence_logs_warning_when_frame_is_violent(caplog):
    """MEASURED (probe2): WARNING 'Violence detected with 83% confidence'."""
    caplog.clear()
    classify = AsyncMock(return_value=violence_result(violent=True, conf=0.83))
    with caplog.at_level(logging.DEBUG, logger=MODLOG):
        out, _err, _subs, _p = await run_violence(classify=classify)
    assert out is classify.return_value
    warnings = [r.getMessage() for r in logs_at(caplog, logging.WARNING)]
    assert warnings == ["Violence detected with 83% confidence"], warnings


@pytest.mark.asyncio
async def test_violence_generic_failure_records_error_metric_and_reraises(caplog):
    """MEASURED: a non-KeyError failure is re-raised unchanged (shipped bare
    ``raise``) after ``record_enrichment_model_error('violence-detection')`` and an
    ERROR 'Violence detection error' with a traceback."""
    caplog.clear()
    with caplog.at_level(logging.DEBUG, logger=MODLOG):
        out, err, subs, _p = await run_violence(
            classify=AsyncMock(side_effect=RuntimeError("inference exploded"))
        )
    assert out is None
    assert isinstance(err, RuntimeError) and str(err) == "inference exploded"
    assert [c.args for c in subs["record_enrichment_model_error"].call_args_list] == [
        ("violence-detection",)
    ]
    assert [c.args for c in subs["record_enrichment_model_call"].call_args_list] == [("violence",)]
    errors = [r.getMessage() for r in logs_at(caplog, logging.ERROR)]
    assert errors == ["Violence detection error"], errors
    assert logs_at(caplog, logging.ERROR)[0].exc_info is not None


@pytest.mark.asyncio
async def test_violence_model_zoo_miss_logs_warns_records_and_raises(caplog):
    """MEASURED (probe2): KeyError -> record_enrichment_model_error
    ('violence-detection',), WARNING 'violence-detection model not available in
    MODEL_ZOO', then ``RuntimeError('violence-detection model not configured')``
    chained ``from`` the KeyError."""
    caplog.clear()
    with caplog.at_level(logging.DEBUG, logger=MODLOG):
        out, err, subs, _p = await run_violence(load_exc=KeyError("violence-detection"))
    assert out is None
    assert isinstance(err, RuntimeError)
    assert str(err) == "violence-detection model not configured"
    assert isinstance(err.__cause__, KeyError)
    assert [c.args for c in subs["record_enrichment_model_error"].call_args_list] == [
        ("violence-detection",)
    ]
    warnings = [r.getMessage() for r in logs_at(caplog, logging.WARNING)]
    assert warnings == ["violence-detection model not available in MODEL_ZOO"], warnings


# ========================================================================== #
# F) EnrichmentResult.to_prompt_context — formatter call arguments           #
# ========================================================================== #

FORMATTERS = (
    "format_violence_context",
    "format_image_quality_context",
    "format_clothing_analysis_context",
    "format_vehicle_classification_context",
    "format_vehicle_damage_context",
    "format_pet_classification_context",
)


@contextlib.contextmanager
def prompt_formatters():
    """Spies for the six formatters this chunk's keys touch.

    ``to_prompt_context`` performs a LOCAL ``from backend.services.prompts
    import ...`` on every call, so replacing the attributes on the live prompts
    module is observed by shipped code and by a swapped variant body alike.
    """
    spies: dict = {}
    for name in FORMATTERS:

        def make(nm):
            def spy(*args, **kwargs):
                spies[nm] = (args, kwargs)
                return f"<{nm}>"

            return spy

        spies[f"__factory__{name}"] = make(name)
    patchers = [patch.object(PROMPTS, n, spies[f"__factory__{n}"]) for n in FORMATTERS]
    for pt in patchers:
        pt.start()
    try:
        yield spies
    finally:
        for pt in patchers:
            pt.stop()


def populated_result() -> M.EnrichmentResult:
    result = M.EnrichmentResult()
    result.violence_detection = object()
    result.image_quality = object()
    result.quality_change_detected = True
    result.quality_change_description = "camera obstructed"
    result.clothing_classifications = object()
    result.clothing_segmentation = object()
    result.vehicle_classifications = object()
    result.vehicle_damage = object()
    result.pet_classifications = object()
    return result


def run_prompt_context(result: M.EnrichmentResult, **kw):
    with prompt_formatters() as spies:
        out = M.EnrichmentResult.to_prompt_context(result, **kw)
    clean = {k: v for k, v in spies.items() if not k.startswith("__factory__")}
    return out, clean


def test_prompt_context_violence_context_receives_the_violence_detection():
    """MEASURED (probe4): ``format_violence_context(self.violence_detection)``
    positionally — the result's own object, not ``None``."""
    result = populated_result()
    out, spies = run_prompt_context(result, time_of_day="dusk")
    assert out["violence_context"] == "<format_violence_context>"
    assert spies["format_violence_context"] == ((result.violence_detection,), {})


def test_prompt_context_image_quality_arguments():
    """MEASURED: ``format_image_quality_context(self.image_quality,
    self.quality_change_detected, self.quality_change_description)`` positionally."""
    result = populated_result()
    _out, spies = run_prompt_context(result)
    assert spies["format_image_quality_context"] == (
        (result.image_quality, True, "camera obstructed"),
        {},
    )


def test_prompt_context_image_quality_quality_change_detected_is_passed():
    """MEASURED: the middle positional is the result's own flag value (True here)."""
    result = populated_result()
    _out, spies = run_prompt_context(result)
    args, kwargs = spies["format_image_quality_context"]
    assert kwargs == {}
    assert args[1] is result.quality_change_detected
    assert args[1] is True


def test_prompt_context_image_quality_quality_change_description_is_passed():
    """MEASURED: the third positional is the result's own description string."""
    result = populated_result()
    _out, spies = run_prompt_context(result)
    args, kwargs = spies["format_image_quality_context"]
    assert kwargs == {}
    assert args[2] == result.quality_change_description == "camera obstructed"


def test_prompt_context_image_quality_quality_change_detected_position_present():
    """MEASURED: the call has exactly three positionals (default fields are
    ``None / False / ''`` — probe4)."""
    result = populated_result()
    _out, spies = run_prompt_context(result)
    args, kwargs = spies["format_image_quality_context"]
    assert len(args) == 3, f"expected 3 positional args, got {args!r}"
    assert args[1] is result.quality_change_detected


def test_prompt_context_image_quality_quality_change_description_position_present():
    """MEASURED: dropping the trailing description argument would shorten the call
    to two positionals — shipped passes it (probe4: ``(obj, True, 'camera ...')``)."""
    result = populated_result()
    _out, spies = run_prompt_context(result)
    args, kwargs = spies["format_image_quality_context"]
    assert len(args) == 3, f"expected 3 positional args, got {args!r}"
    assert args[2] == result.quality_change_description


def test_prompt_context_clothing_arguments():
    """MEASURED: ``format_clothing_analysis_context(self.clothing_classifications,
    self.clothing_segmentation)`` positionally."""
    result = populated_result()
    _out, spies = run_prompt_context(result)
    assert spies["format_clothing_analysis_context"] == (
        (result.clothing_classifications, result.clothing_segmentation),
        {},
    )


def test_prompt_context_clothing_segmentation_is_passed():
    """MEASURED: second positional is the segmentation dict, not ``None``."""
    result = populated_result()
    _out, spies = run_prompt_context(result)
    args, kwargs = spies["format_clothing_analysis_context"]
    assert kwargs == {}
    assert args[1] is result.clothing_segmentation


def test_prompt_context_clothing_classifications_position_present():
    """MEASURED: two positionals; the first is the classifications mapping."""
    result = populated_result()
    _out, spies = run_prompt_context(result)
    args, kwargs = spies["format_clothing_analysis_context"]
    assert len(args) == 2, f"expected 2 positional args, got {args!r}"
    assert args[0] is result.clothing_classifications


def test_prompt_context_clothing_segmentation_position_present():
    """MEASURED: dropping the segmentation argument shortens the call — shipped
    keeps both positions."""
    result = populated_result()
    _out, spies = run_prompt_context(result)
    args, kwargs = spies["format_clothing_analysis_context"]
    assert len(args) == 2, f"expected 2 positional args, got {args!r}"
    assert args[1] is result.clothing_segmentation


def test_prompt_context_vehicle_classification_receives_the_classifications():
    """MEASURED (probe4): the real formatter renders 'Vehicle 3: Pickup Truck
    (77% confidence) [Commercial/delivery vehicle]' from the result's own dict —
    ``None`` would render the 'No vehicles analyzed' placeholder instead."""
    vcv = M.VehicleClassificationResult(
        vehicle_type="pickup_truck",
        confidence=0.77,
        display_name="Pickup Truck",
        is_commercial=True,
        all_scores={},
    )
    result = M.EnrichmentResult(vehicle_classifications={"3": vcv})
    out = M.EnrichmentResult.to_prompt_context(result)
    assert out["vehicle_classification_context"] == (
        "Vehicle 3: Pickup Truck (77% confidence) [Commercial/delivery vehicle]"
    )
    empty = M.EnrichmentResult.to_prompt_context(M.EnrichmentResult())
    assert empty["vehicle_classification_context"] == "Vehicle classification: No vehicles analyzed"


def test_prompt_context_vehicle_classification_argument_is_the_result_dict():
    """MEASURED: the single positional is ``self.vehicle_classifications`` itself."""
    result = populated_result()
    _out, spies = run_prompt_context(result)
    assert spies["format_vehicle_classification_context"] == (
        (result.vehicle_classifications,),
        {},
    )


def test_prompt_context_vehicle_damage_arguments():
    """MEASURED: ``format_vehicle_damage_context(self.vehicle_damage,
    time_of_day=time_of_day)`` — damage positional, time context as keyword."""
    result = populated_result()
    _out, spies = run_prompt_context(result, time_of_day="dusk")
    assert spies["format_vehicle_damage_context"] == (
        (result.vehicle_damage,),
        {"time_of_day": "dusk"},
    )


def test_prompt_context_vehicle_damage_time_of_day_keyword_value():
    """MEASURED: the keyword carries the caller's ``time_of_day`` value verbatim."""
    result = populated_result()
    _out, spies = run_prompt_context(result, time_of_day="dawn")
    assert spies["format_vehicle_damage_context"][1] == {"time_of_day": "dawn"}


def test_prompt_context_vehicle_damage_time_of_day_keyword_present():
    """MEASURED: ``time_of_day`` is passed as a keyword (probe4 records
    ``kwargs={'time_of_day': 'dusk'}``)."""
    result = populated_result()
    _out, spies = run_prompt_context(result, time_of_day="dusk")
    assert "time_of_day" in spies["format_vehicle_damage_context"][1]


def test_prompt_context_pet_classification_receives_the_classifications():
    """MEASURED: single positional is ``self.pet_classifications`` (not ``None``)."""
    result = populated_result()
    out, spies = run_prompt_context(result)
    assert out["pet_classification_context"] == "<format_pet_classification_context>"
    assert spies["format_pet_classification_context"] == ((result.pet_classifications,), {})


def test_prompt_context_returns_all_eleven_sections():
    """Guard: the section set stays intact so the argument pins above stay
    reachable (probe4 measured the 10 shipped keys + violence/quality/...)."""
    result = populated_result()
    out, _spies = run_prompt_context(result)
    assert {
        "violence_context",
        "weather_context",
        "image_quality_context",
        "clothing_analysis_context",
        "vehicle_classification_context",
        "vehicle_damage_context",
        "pet_classification_context",
        "pose_analysis",
        "action_recognition",
        "depth_context",
    } <= set(out)
