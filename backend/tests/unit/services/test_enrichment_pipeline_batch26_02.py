"""Chunk-02 kill-battery for enrichment_pipeline mutation survivors (119 keys).

Every assertion pins behaviour MEASURED against the pristine shipped module
``backend/services/enrichment_pipeline.py`` (HEAD, 7591 lines).  33 shape groups
across 5 defs:

A) ``EnrichmentError.from_exception`` (L390-520) — kwargs of the ``cls(...)``
   return sites:
     shape#0  ``operation=operation``   -> ``operation=None``   (L415,442,464,481,503)
     shape#1  ``details=error_details`` -> ``details=None``     (L420,486,508,518)
     shape#2  ``is_transient=True``     -> kwarg deleted        (L419,430,446,457,485)
     shape#3  ``details=error_details`` -> kwarg deleted        (L420,486,508,518)
   ``EnrichmentError`` is ``@dataclass(slots=True)`` (L355-372): ``operation``
   has NO default, while ``is_transient=True`` and
   ``details=field(default_factory=dict)`` do.  shape#0 stores ``None`` instead
   of the caller's operation string; shape#1 stores ``None`` instead of the
   caller's dict; both are killed by value/identity pins.  Only shape#2
   (``is_transient=True`` deleted) lands on a value identical to shipped — the
   dataclass default IS True — and is the chunk's one equivalent group.

B) ``EnrichmentPipeline._classify_vehicle_types`` (L6790-6941) — the ``extra={``
   dicts of the OUTER except-branch log calls:
     shapes#20-23  key ``detection_type`` / value ``"vehicle"``
     shapes#34-36  key ``error_type``     / value ``type(e).__name__``
     shapes#39-41  key ``is_transient``   / value ``True``

C) ``_classify_clothing_via_service`` (L4757), ``_classify_pets_via_service``
   (L4345), ``_classify_vehicle_via_service`` (L4212) — the ``extra={`` dicts at
   BOTH the ``if remote_result:`` DEBUG site (L4806/L4393/L4265) and the
   ``(ConnectError, TimeoutException, EnrichmentUnavailableError)`` WARNING site
   (L4820/L4407/L4283): key ``service`` and its name value, key ``detection_id``.

D) ``EnrichmentPipeline._run_parallel_enrichment`` (L2345-2872):
     shapes#44/#100  ``A and B and self._should_run_for_quality("standard")``
                     -> ``A and B or self._should_run_for_quality("standard")``
       at L2437 (unified vehicle), L2495 (local vehicle types), L2551 (vehicle
       damage), L2530 (YOLO-World), L2542 (local depth), L2794 (scene-OCR crops).
       Under ``or`` the first truthy conjunct alone decides, so a gate with a
       False enable flag but a truthy detection list still schedules its task.
     shapes#209/#211  ``limit=5`` -> deleted (the shipped ``bounded_gather``
                      default is 10) -> ``limit=6``, at L2690 (CPU group),
       L2810 (phase 2), L2848 (phase 3).  Measured as peak in-flight concurrency
       for the same 6-task workload: 5 shipped vs 6 under both mutants.
"""

from __future__ import annotations

import asyncio
import contextlib
import dataclasses
import inspect
import logging
from typing import Any
from unittest.mock import MagicMock, patch

import httpx
from PIL import Image

import backend.services.enrichment_pipeline as M

MODULE = "backend.services.enrichment_pipeline"
LOG_NAME = "backend.services.enrichment_pipeline"


# ---------------------------------------------------------------------------
# log capture: ``logger.<lvl>(msg, extra={...})`` copies the extra mapping onto
# the LogRecord, so a Handler on the module logger sees the extras verbatim.
# ---------------------------------------------------------------------------
class _Capture(logging.Handler):
    def __init__(self) -> None:
        super().__init__()
        self.records: list[logging.LogRecord] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.records.append(record)


@contextlib.contextmanager
def capture_extra() -> Any:
    handler = _Capture()
    logger = logging.getLogger(LOG_NAME)
    previous_level = logger.level
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG)
    try:
        yield handler
    finally:
        logger.setLevel(previous_level)
        logger.removeHandler(handler)


def extras_with(handler: _Capture, keys: tuple[str, ...]) -> list[dict[str, Any]]:
    """Captured records carrying *all* of ``keys`` -> those extras as dicts."""
    out: list[dict[str, Any]] = []
    for rec in handler.records:
        if all(hasattr(rec, k) for k in keys):
            out.append({k: getattr(rec, k) for k in keys})
    return out


def run(coro: Any) -> Any:
    return asyncio.run(coro)


async def _done(value: Any = None) -> Any:
    return value


# ---------------------------------------------------------------------------
# pipeline instance / detection builders
# ---------------------------------------------------------------------------
def make_pipeline(**kw: Any) -> Any:
    """EnrichmentPipeline with every global service getter patched at the IMPORT
    site (same topology as the repo suite's ``mock_enrichment_services``)."""
    with (
        patch(f"{MODULE}.get_vision_extractor", autospec=True) as vision,
        patch(f"{MODULE}.get_reid_service", autospec=True) as reid,
        patch(f"{MODULE}.get_scene_change_detector", autospec=True) as scene,
        patch(f"{MODULE}.get_scene_ocr_service", autospec=True) as ocr,
    ):
        vision.return_value = MagicMock()
        reid.return_value = MagicMock()
        scene.return_value = MagicMock()
        ocr.return_value = MagicMock()
        return M.EnrichmentPipeline(model_manager=MagicMock(), **kw)


ALL_OFF = dict(
    license_plate_enabled=False,
    face_detection_enabled=False,
    image_quality_enabled=False,
    ocr_enabled=False,
    vision_extraction_enabled=False,
    reid_enabled=False,
    scene_change_enabled=False,
    violence_detection_enabled=False,
    weather_classification_enabled=False,
    clothing_classification_enabled=False,
    clothing_segmentation_enabled=False,
    vehicle_damage_detection_enabled=False,
    vehicle_classification_enabled=False,
    pet_classification_enabled=False,
    depth_estimation_enabled=False,
    pose_estimation_enabled=False,
    action_recognition_enabled=False,
    scene_ocr_enabled=False,
    household_matching_enabled=False,
    age_classification_enabled=False,
    gender_classification_enabled=False,
    smoke_fire_detection_enabled=False,
    yolo_world_enabled=False,
    osnet_reid_enabled=False,
    low_light_enhancement_enabled=False,
)


def minimal_pipeline(**kw: Any) -> Any:
    """Every model family off; the caller re-enables exactly what it needs."""
    base = dict(ALL_OFF)
    base.update(kw)
    return make_pipeline(**base)


def det(cls: str, det_id: int | None = 1, conf: float = 0.9) -> Any:
    return M.DetectionInput(
        class_name=cls,
        confidence=conf,
        bbox=M.BoundingBox(x1=4, y1=4, x2=30, y2=30),
        id=det_id,
    )


def image() -> Image.Image:
    return Image.new("RGB", (64, 64), color=(9, 9, 9))


# ===========================================================================
# A) EnrichmentError.from_exception
# ===========================================================================
def fe(exc: BaseException, operation: str = "plate_detection", details: Any = None) -> Any:
    """Call ``EnrichmentError.from_exception`` in a form that works BOTH for the
    shipped classmethod object and for a mutant body, which ep_plugin binds as a
    plain function (``setattr(cls, name, variant)`` does not re-wrap it in
    ``classmethod``).  Passing the class explicitly keeps the arity identical in
    both cases, so a mutant can never "fail" merely because of the binding."""
    fn = M.EnrichmentError.__dict__["from_exception"]
    fn = fn.__func__ if isinstance(fn, classmethod) else fn
    return fn(M.EnrichmentError, operation, exc, details=details)


def http_status(status_code: int) -> httpx.HTTPStatusError:
    response = MagicMock()
    response.status_code = status_code
    return httpx.HTTPStatusError(f"status {status_code}", request=MagicMock(), response=response)


ALL_EXCS: tuple[BaseException, ...] = (
    httpx.ConnectError("refused"),
    httpx.TimeoutException("slow"),
    TimeoutError("t"),
    http_status(429),
    http_status(503),
    http_status(404),
    M.EnrichmentUnavailableError("down"),
    ValueError("bad"),
    AttributeError("nope"),
    RuntimeError("unknown"),
)


def test_from_exception_operation_is_the_argument() -> None:
    """Shipped (L415/442/464/481/503 and the 4 non-mutated sites): ``operation``
    is echoed verbatim.  shape#0 replaces the argument with the literal ``None``
    at each of the five mutated return sites, so the structured error loses the
    identity of the failed operation for every exception class handled there."""
    for exc in ALL_EXCS:
        assert fe(exc, operation="op-under-test").operation == "op-under-test", exc
    # shipped is a pure passthrough: a None argument stays None
    assert fe(RuntimeError("x"), operation=None).operation is None


def test_enrichment_error_field_defaults() -> None:
    """Field contract of the dataclass these shapes write into (L355-372):
    ``operation`` is a required field (so a shipped-None mutant is a real value
    change, not a fallback), ``is_transient`` defaults to True — which is what
    makes shape#2 value-identical to shipped — and ``details`` defaults to a
    FRESH dict, i.e. NOT the caller's object."""
    fld = {f.name: f for f in dataclasses.fields(M.EnrichmentError)}
    assert fld["operation"].default is dataclasses.MISSING
    assert fld["operation"].default_factory is dataclasses.MISSING
    assert fld["is_transient"].default is True
    assert fld["details"].default_factory is dict


def test_from_exception_details_is_the_caller_dict() -> None:
    """Shipped (L420/431/447/458/469/486/497/508/518): ``details`` IS the dict
    the caller passed — same object, so later mutations are visible.  Kills
    shape#1 (``details=None``)."""
    for exc in ALL_EXCS:
        d: dict[str, Any] = {"camera": "cam-1", "det": 3}
        err = fe(exc, details=d)
        assert err.details is d, exc
        assert err.details["camera"] == "cam-1", exc


def test_from_exception_status_code_injected_into_caller_dict() -> None:
    """Shipped L436 writes ``status_code`` into the SAME dict the caller passed,
    observable through ``err.details`` (second angle on shape#1)."""
    d: dict[str, Any] = {"camera": "cam-1"}
    assert fe(http_status(429), details=d).details is d and d["status_code"] == 429
    d2: dict[str, Any] = {"det": 9}
    assert fe(http_status(404), details=d2).details is d2 and d2["status_code"] == 404
    # shipped L406 ``details or {}``: a FALSY dict is replaced by a fresh dict,
    # into which status_code is then injected
    d3: dict[str, Any] = {}
    err = fe(http_status(404), details=d3)
    assert err.details == {"status_code": 404} and err.details is not d3


def test_from_exception_details_identity_holds_for_every_input() -> None:
    """Kills shape#3 (the ``details`` kwarg is deleted from the call): shipped
    always yields the caller's object for a truthy dict, whatever it is, and a
    fresh {} for the falsy/None cases (L406 ``details or {}``)."""

    class _D(dict):  # a dict SUBCLASS — shipped hands it back untouched
        pass

    for exc in ALL_EXCS:
        for passed in (None, {}, {"k": "v"}, _D({"sub": 1})):
            err = fe(exc, details=passed)
            assert isinstance(err.details, dict), (exc, passed)
            if passed:
                assert type(err.details) is type(passed), (exc, passed)
                assert err.details is passed, (exc, passed)
                assert err.details["k" if "k" in passed else "sub"] in ("v", 1), (exc, passed)


def test_from_exception_transient_table() -> None:
    """Shipped ``is_transient`` at every branch.  This table is also the
    equivalence witness for shape#2: the five mutated sites all pass True, which
    is exactly the dataclass default, so deleting that kwarg cannot be observed."""
    table = (
        (httpx.ConnectError("r"), True),
        (httpx.TimeoutException("t"), True),
        (TimeoutError("t"), True),
        (http_status(429), True),
        (http_status(503), True),
        (http_status(404), False),
        (M.EnrichmentUnavailableError("d"), True),
        (ValueError("v"), False),
        (AttributeError("a"), False),
        (RuntimeError("r"), True),
    )
    for exc, want in table:
        err = fe(exc)
        assert err.is_transient is want, exc
        assert err.to_dict()["is_transient"] is want, exc


def test_from_exception_category_reason_error_type_table() -> None:
    """Full shipped classification pin (category / error_type / reason prefix).
    Shapes#2 and #3 leave these untouched, so this is their second witness."""
    cases = (
        (
            httpx.ConnectError("r"),
            M.ErrorCategory.SERVICE_UNAVAILABLE,
            "ConnectError",
            "Service connection failed",
        ),
        (
            httpx.TimeoutException("t"),
            M.ErrorCategory.TIMEOUT,
            "TimeoutException",
            "Request timed out",
        ),
        (
            http_status(429),
            M.ErrorCategory.RATE_LIMITED,
            "HTTPStatusError",
            "Rate limited (HTTP 429)",
        ),
        (
            http_status(503),
            M.ErrorCategory.SERVER_ERROR,
            "HTTPStatusError",
            "Server error (HTTP 503)",
        ),
        (
            http_status(404),
            M.ErrorCategory.CLIENT_ERROR,
            "HTTPStatusError",
            "Client error (HTTP 404)",
        ),
        (
            M.EnrichmentUnavailableError("d"),
            M.ErrorCategory.SERVICE_UNAVAILABLE,
            "EnrichmentUnavailableError",
            "d",
        ),
        (ValueError("v"), M.ErrorCategory.PARSE_ERROR, "ValueError", "Response parsing failed"),
        (
            AttributeError("a"),
            M.ErrorCategory.VALIDATION_ERROR,
            "AttributeError",
            "Validation failed",
        ),
        (RuntimeError("r"), M.ErrorCategory.UNEXPECTED, "RuntimeError", "Unexpected error"),
    )
    for exc, cat, etype, reason_prefix in cases:
        err = fe(exc, operation="op")
        assert err.category is cat, exc
        assert err.error_type == etype, exc
        assert err.reason.startswith(reason_prefix), exc
        d = err.to_dict()
        assert d["operation"] == "op" and d["category"] == cat.value, exc


# ===========================================================================
# B) _classify_vehicle_types — outer except-branch log extras
# ===========================================================================
VT_KEYS = ("detection_type", "operation", "error_type", "error_category", "is_transient")
VT_FULL = VT_KEYS + ("status_code",)


class _RaiseOnEnter:
    """``async with model_manager.load(...)`` raising in ``__aenter__`` drives
    the method's OUTER try/except handlers (L6813-6941)."""

    def __init__(self, exc: BaseException) -> None:
        self.exc = exc

    async def __aenter__(self) -> Any:
        raise self.exc

    async def __aexit__(self, *a: Any) -> bool:
        return False


def vt_extra(exc: BaseException) -> dict[str, Any]:
    """The structured extras of the single log call the handler for ``exc``
    makes (L6840-6941)."""
    p = make_pipeline()
    p.model_manager = MagicMock(load=MagicMock(return_value=_RaiseOnEnter(exc)))
    with capture_extra() as h:
        out = run(p._classify_vehicle_types([det("car", 7)], image()))
    assert out == {}, exc  # shipped: every handler swallows and returns {}
    recs = [r for r in h.records if getattr(r, "operation", None) == "vehicle_classification"]
    assert len(recs) == 1, [(r.levelname, r.getMessage()) for r in h.records]
    rec = recs[0]
    return {k: getattr(rec, k) for k in VT_FULL if hasattr(rec, k)}


# Shipped extra dicts, verbatim (line of the ``extra={`` is in the comment).
VT_EXPECTED: tuple[tuple[BaseException, dict[str, Any]], ...] = (
    # L6843 except KeyError
    (
        KeyError("vehicle-segment-classification"),
        {
            "detection_type": "vehicle",
            "operation": "vehicle_classification",
            "error_category": "parse_error",
        },
    ),
    # L6858 except (EnrichmentUnavailableError, AIServiceError, ...)
    (
        M.EnrichmentUnavailableError("unavailable"),
        {
            "detection_type": "vehicle",
            "operation": "vehicle_classification",
            "error_type": "EnrichmentUnavailableError",
            "error_category": "service_unavailable",
            "is_transient": True,
        },
    ),
    # L6870 except httpx.ConnectError
    (
        httpx.ConnectError("refused"),
        {
            "detection_type": "vehicle",
            "operation": "vehicle_classification",
            "error_type": "ConnectError",
            "error_category": "service_unavailable",
            "is_transient": True,
        },
    ),
    # L6882 except httpx.TimeoutException
    (
        httpx.TimeoutException("slow"),
        {
            "detection_type": "vehicle",
            "operation": "vehicle_classification",
            "error_type": "TimeoutException",
            "error_category": "timeout",
            "is_transient": True,
        },
    ),
    # L6896 5xx
    (
        http_status(503),
        {
            "detection_type": "vehicle",
            "operation": "vehicle_classification",
            "error_type": "HTTPStatusError",
            "error_category": "server_error",
            "status_code": 503,
            "is_transient": True,
        },
    ),
    # L6909 4xx
    (
        http_status(404),
        {
            "detection_type": "vehicle",
            "operation": "vehicle_classification",
            "error_type": "HTTPStatusError",
            "error_category": "client_error",
            "status_code": 404,
            "is_transient": False,
        },
    ),
    # L6922 except (ValueError, TypeError)
    (
        ValueError("bad payload"),
        {
            "detection_type": "vehicle",
            "operation": "vehicle_classification",
            "error_type": "ValueError",
            "error_category": "parse_error",
            "is_transient": False,
        },
    ),
    (
        TypeError("bad type"),
        {
            "detection_type": "vehicle",
            "operation": "vehicle_classification",
            "error_type": "TypeError",
            "error_category": "parse_error",
            "is_transient": False,
        },
    ),
    # L6935 except Exception (no error_type key shipped here)
    (
        RuntimeError("unexpected"),
        {
            "detection_type": "vehicle",
            "operation": "vehicle_classification",
            "error_category": "unexpected",
            "is_transient": True,
        },
    ),
)


def test_vehicle_types_handler_extra_contract() -> None:
    """ONE contract for all ten _classify_vehicle_types shape groups: each of the
    eight outer handlers logs EXACTLY the shipped extra dict (keys and values).

    A key rename (shapes #20/#21 detection_type, #34/#35 error_type,
    #39/#40 is_transient) removes a key the contract demands; a value mutation
    (#22/#23 "vehicle" -> sentinel/upper, #36 ``type(None).__name__`` ->
    "NoneType", #41 True -> False) changes one — either way this test fails."""
    for exc, expected in VT_EXPECTED:
        assert vt_extra(exc) == expected, exc


# ===========================================================================
# C) *_via_service — DEBUG (remote_result) + WARNING (transient except) extras
# ===========================================================================
VIA: dict[str, dict[str, Any]] = {
    "clothing": {
        "meth": "_classify_clothing_via_service",
        "cls": "person",
        "service": "clothing-via-service",
        "client": "classify_clothing",
    },
    "pets": {
        "meth": "_classify_pets_via_service",
        "cls": "dog",
        "service": "pet-via-service",
        "client": "classify_pet",
    },
    "vehicle": {
        "meth": "_classify_vehicle_via_service",
        "cls": "car",
        "service": "vehicle-via-service",
        "client": "classify_vehicle",
    },
}


def remote(kind: str) -> Any:
    """Truthy stand-in for the remote payload exposing every attribute the
    shipped conversion reads (L4253-4259 / L4383-4390 / L4795-4802)."""
    r = MagicMock(name=f"remote-{kind}")
    r.confidence = 0.75
    if kind == "vehicle":
        r.vehicle_type = "sedan"
        r.display_name = "Sedan"
        r.is_commercial = False
        r.all_scores = {"sedan": 0.75}
    elif kind == "pets":
        r.pet_type = "dog"
        r.is_household_pet = True
    else:
        r.top_category = "jacket"
        r.is_suspicious = False
        r.is_service_uniform = False
        r.description = "dark jacket"
    return r


def via_extras(kind: str, behaviour: Any) -> list[dict[str, Any]]:
    """Run the shipped *_via_service method over one detection and return every
    structured-extra dict it logged that carries a ``service`` key."""
    p = make_pipeline()
    client = MagicMock()
    setattr(client, VIA[kind]["client"], behaviour)
    p._enrichment_client = client
    with capture_extra() as h:
        run(getattr(p, VIA[kind]["meth"])([det(VIA[kind]["cls"], 42)], image()))
    out = []
    for rec in h.records:
        if hasattr(rec, "service"):
            out.append(
                {
                    k: getattr(rec, k)
                    for k in ("service", "detection_id", "duration_ms", "error_type")
                    if hasattr(rec, k)
                }
            )
    return out


def via_contract(kind: str) -> None:
    """Assert the shipped extras at all three mutated sites of one
    ``*_via_service`` method: the ``if remote_result`` DEBUG log, the
    (ConnectError, TimeoutException, EnrichmentUnavailableError) WARNING and the
    catch-all ``except Exception`` ERROR."""
    name = VIA[kind]["service"]

    async def ok(*args: Any, **kwargs: Any) -> Any:
        return remote(kind)

    rows_ok = via_extras(kind, ok)
    assert len(rows_ok) == 1, rows_ok
    assert rows_ok[0] == {
        "service": name,
        "detection_id": "42",
        "duration_ms": rows_ok[0]["duration_ms"],
    }
    assert isinstance(rows_ok[0]["duration_ms"], int)

    async def transient(*args: Any, **kwargs: Any) -> Any:
        raise httpx.TimeoutException("slow")

    rows_warn = via_extras(kind, transient)
    assert len(rows_warn) == 1, rows_warn
    assert rows_warn[0] == {
        "service": name,
        "detection_id": "42",
        "error_type": "TimeoutException",
    }

    async def boom(*args: Any, **kwargs: Any) -> Any:
        raise RuntimeError("service blew up")

    rows_err = via_extras(kind, boom)
    assert len(rows_err) == 1, rows_err
    assert rows_err[0] == {
        "service": name,
        "detection_id": "42",
        "error_type": "RuntimeError",
    }


def test_clothing_via_service_extra_contract() -> None:
    """Shapes 27-32 of _classify_clothing_via_service: key ``service`` + value
    "clothing-via-service" and key ``detection_id`` at L4807/4808 (DEBUG),
    L4821/4823 (transient WARNING) and L4873/4875 (unexpected ERROR)."""
    via_contract("clothing")


def test_pets_via_service_extra_contract() -> None:
    """Shapes 26-31 of _classify_pets_via_service: the same contract at
    L4394/4395, L4408/4410 and L4460/4462 with value "pet-via-service"."""
    via_contract("pets")


def test_vehicle_via_service_extra_contract() -> None:
    """Shapes 24-26 of _classify_vehicle_via_service: the same contract at
    L4266/4267, L4284/4286 and L4336/4338 with value "vehicle-via-service"."""
    via_contract("vehicle")


# ===========================================================================
# D) _run_parallel_enrichment — gate `and`->`or`, and bounded_gather limit
# ===========================================================================
# Scheduling is observed by replacing each Phase-1 task FACTORY with a closure
# that records its tag and returns an already-resolved awaitable.  The closures
# are INSTANCE attributes (never class attributes), so the pristine class shared
# with the ep_plugin mutant swap is left untouched.
SENTINELS: dict[str, str] = {
    "_enrich_persons_via_unified_service": "up",
    "_enrich_vehicles_via_unified_service": "uv",
    "_enrich_animals_via_unified_service": "ua",
    "_safe_classify_person_clothing": "cl",
    "_safe_classify_vehicle_types": "vt",
    "_safe_classify_pets": "pe",
    "_safe_classify_demographics": "de",
    "_safe_extract_osnet_embeddings": "os",
    "_safe_detect_yolo_world": "yw",
    "_safe_analyze_depth": "dp",
    "_safe_detect_vehicle_damage": "vd",
    "_safe_segment_person_clothing": "cs",
    "_safe_assess_image_quality": "iq",
    "_safe_classify_weather": "wx",
    "_safe_estimate_poses": "pl",
    "_safe_run_scene_ocr_frame": "of",
    "_safe_detect_smoke_fire": "sf",
    "_safe_detect_faces": "fd",
    "_safe_detect_license_plates": "lp",
    "_safe_detect_plates_fast_alpr": "lp",
    "_safe_detect_violence": "vi",
    "_estimate_poses_via_service": "ps",
    "_detect_threats_via_service": "th",
    "_compute_reid_via_service": "ri",
    "_safe_clip_scene_classify": "cc",
    "_safe_clip_threat_match": "ct",
}


def _tagged(p: Any, tag: str) -> Any:
    def call(*args: Any, **kwargs: Any) -> Any:
        p._fired[tag] = len(args)
        return _done(None)

    return call


def arm(p: Any) -> Any:
    """Cover every Phase-1 factory plus the Phase-2/3 workers and the Florence
    extractor, so no real model code can run."""
    if not hasattr(p, "_fired"):
        p._fired = {}
    for name, tag in SENTINELS.items():
        setattr(p, name, _tagged(p, tag))
    p._safe_run_scene_ocr_crops = _tagged(p, "sc")
    p._read_plates = lambda *a, **k: _done(None)
    p._run_reid = lambda *a, **k: _done(None)
    p._run_clip_anomaly_detection = lambda *a, **k: _done(None)
    p._run_household_matching = lambda *a, **k: _done(None)
    p._recognize_actions_from_skeleton = lambda *a, **k: _done(None)
    p._is_fast_alpr_available = lambda: False
    extractor = MagicMock()
    extractor.extract_batch_attributes = MagicMock(return_value=_done(None))
    p._vision_extractor = extractor
    return p


def fire_tags(p: Any, hcd: list[Any], use_service: bool = False) -> dict[str, Any]:
    """Run the shipped orchestrator at the pipeline's current ``_quality_level``
    and report which task factories were CALLED (i.e. scheduled)."""
    p._fired = {}
    p.use_enrichment_service = use_service
    run(p._run_parallel_enrichment(M.EnrichmentResult(), image(), hcd, {42: image()}, "cam-1"))
    return dict(p._fired)


# gate tag -> detection class that makes that gate's detection term truthy
GATE_CLASS = {
    "uv": "car",  # L2437 unified vehicle
    "vt": "car",  # L2495 local vehicle-type classification
    "vd": "car",  # L2551 vehicle damage
    "yw": "car",  # L2530 YOLO-World zero-shot
    "dp": "car",  # L2542 local depth estimation
    "sc": "car",  # L2794 scene-OCR per-crop pass (phase 2)
}


def gate_fired(gate: str, quality: str, use_service: bool) -> bool:
    """Shipped schedule decision for a gate whose ENABLE FLAG is False while its
    detection term is truthy.  Shipped: never (``False and ...`` is False)."""
    p = arm(minimal_pipeline(use_enrichment_service=use_service))
    p._quality_level = quality
    return gate in fire_tags(p, [det(GATE_CLASS[gate], 42, conf=0.5)], use_service)


def test_gate_or_cascade_never_schedules_a_disabled_model() -> None:
    """Shapes #44/#100 (``and`` -> ``or`` at L2437 unified vehicle, L2495 local
    vehicle-type classification, L2551 vehicle damage, L2530 YOLO-World, L2542
    local depth, L2794 scene-OCR crops): shipped requires EVERY conjunct, so a gate whose
    enable flag is False never schedules its task.  Under ``or`` the first truthy
    conjunct alone decides — a non-empty detection list makes the gate True and
    the disabled model's coroutine is scheduled (at standard/full, where
    ``_should_run_for_quality("standard")`` is True).  That flip in the shipped
    schedule is the kill."""
    for use_service in (False, True):
        for gate in ("uv", "vt", "vd", "yw", "dp", "sc"):
            for quality in ("minimal", "standard", "full"):
                assert gate_fired(gate, quality, use_service) is False, (
                    gate,
                    quality,
                    use_service,
                )


def test_gate_schedule_is_exactly_the_enabled_models() -> None:
    """Second angle on shapes #44/#100: with ONLY ``vehicle_classification``
    enabled, shipped schedules exactly one Phase-1 task; under ``or`` every
    gate whose detection list is non-empty fires, so the scheduled set grows."""
    for quality, expected in (("full", {"vt"}), ("standard", {"vt"}), ("minimal", set())):
        p = arm(minimal_pipeline(vehicle_classification_enabled=True))
        p._quality_level = quality
        fired = fire_tags(p, [det("car", 42)], use_service=False)
        assert set(fired) == expected, (quality, fired)
    for quality, expected in (("full", {"uv"}), ("standard", {"uv"}), ("minimal", set())):
        p = arm(minimal_pipeline(vehicle_classification_enabled=True, use_enrichment_service=True))
        p._quality_level = quality
        fired = fire_tags(p, [det("car", 42)], use_service=True)
        assert set(fired) == expected, (quality, fired)


def test_gate_reference_shipped_quality_arithmetic() -> None:
    """Anchors both tests above to measured values of shipped
    ``_should_run_for_quality`` (L2331-2343) — ``level_order`` thresholds plus
    BOTH ``level_order.get(..., 2)`` fallbacks (unknown level and unknown tier
    both resolve to "full")."""
    p = minimal_pipeline()
    table = (
        ("minimal", {"minimal": True, "standard": False, "full": False}),
        ("standard", {"minimal": True, "standard": True, "full": False}),
        ("full", {"minimal": True, "standard": True, "full": True}),
        # unknown LEVEL -> get(level, 2) == 2, so only a "full" tier passes
        ("bogus", {"minimal": True, "standard": True, "full": True}),
    )
    for level, expects in table:
        p._quality_level = level
        for tier, want in expects.items():
            assert p._should_run_for_quality(tier) is want, (level, tier)
    # unknown TIER -> get(tier, 2) == 2 == requires current >= full
    p._quality_level = "full"
    assert p._should_run_for_quality("XXstandardXX") is True
    p._quality_level = "standard"
    assert p._should_run_for_quality("XXstandardXX") is False


# ---- bounded_gather ``limit=5`` (shapes #209 / #211) ----
# The three mutated call sites (L2690 CPU group, L2810 phase 2, L2848 phase 3)
# pass their limit as a KEYWORD argument, and the shipped default of the callee
# is 10 — so "kwarg deleted" and "limit=6" are only observable at the call site.
# A recording proxy is installed over the IMPORT-SITE binding at module import
# (before the plugin snapshots the module dict, so mutant bodies see it too) and
# forwards every argument unchanged: shipped behaviour is untouched, but the
# ``limit`` each site actually passes is now measurable.
_UNSET = object()
_ORIGINAL_BOUNDED_GATHER = M.bounded_gather
GATHER_CALLS: list[Any] = []


async def _spy_bounded_gather(
    coros: Any,
    *,
    limit: Any = _UNSET,
    task_timeout: Any = None,
    return_exceptions: bool = False,
) -> Any:
    GATHER_CALLS.append("<no limit kwarg>" if limit is _UNSET else limit)
    kw: dict[str, Any] = {} if limit is _UNSET else {"limit": limit}
    return await _ORIGINAL_BOUNDED_GATHER(
        list(coros), task_timeout=task_timeout, return_exceptions=return_exceptions, **kw
    )


M.bounded_gather = _spy_bounded_gather


async def _peak(n: int, **gather_kw: Any) -> int:
    """Peak in-flight awaitables for an n-task workload through the same
    ``bounded_gather`` the mutated sites call: with a limit of 5 six awaiting
    tasks run 5-at-a-time."""
    st = {"now": 0, "peak": 0}

    async def one() -> None:
        st["now"] += 1
        st["peak"] = max(st["peak"], st["now"])
        try:
            await asyncio.sleep(0.02)
        finally:
            st["now"] -= 1

    await M.bounded_gather([one() for _ in range(n)], return_exceptions=True, **gather_kw)
    return st["peak"]


def _sampled(st: dict[str, int], mark: Any = None) -> Any:
    """Factory for a stub task that samples in-flight concurrency."""

    async def body(*args: Any, **kwargs: Any) -> None:
        if mark is not None:
            mark()
        st["now"] += 1
        st["peak"] = max(st["peak"], st["now"])
        try:
            await asyncio.sleep(0.02)
        finally:
            st["now"] -= 1

    return lambda *a, **k: body()


def service_six_task_pipeline() -> Any:
    """Pipeline whose shipped scheduling produces exactly 6 Phase-1 tasks (all
    CPU-grouped on the service path), 1 Phase-2 task and 1 Phase-3 task."""
    p = arm(
        minimal_pipeline(
            use_enrichment_service=True,
            vehicle_classification_enabled=True,
            pet_classification_enabled=True,
            pose_estimation_enabled=True,
            reid_enabled=True,
            scene_change_enabled=True,
            household_matching_enabled=True,
            redis_client=MagicMock(),
        )
    )
    p._quality_level = "standard"
    st = {"now": 0, "peak": 0}
    p._ep02_st = st
    for name, tag in (
        ("_enrich_persons_via_unified_service", "up"),
        ("_enrich_vehicles_via_unified_service", "uv"),
        ("_enrich_animals_via_unified_service", "ua"),
        ("_estimate_poses_via_service", "ps"),
        ("_detect_threats_via_service", "th"),
        ("_compute_reid_via_service", "ri"),
    ):
        setattr(p, name, _sampled(st, lambda t=tag: p._fired.setdefault(t, True)))
    p._safe_run_scene_ocr_crops = lambda *a, **k: _sampled(st)()
    p._scene_detector = MagicMock()
    p._scene_detector.detect_changes = MagicMock(return_value=None)
    p._run_household_matching = _sampled(st)
    p.use_enrichment_service = True
    return p


def test_all_three_pipeline_gather_sites_pass_limit_five() -> None:
    """Shapes #209 (``limit=5`` kwarg deleted -> callee default 10) and #211
    (``limit=6``) mutate the limit at L2690 (CPU group), L2810 (phase 2) and
    L2848 (phase 3).  This run drives all three gathers: shipped calls each one
    with ``limit=5``, so the recorded argument list is EXACTLY [5, 5, 5]; a
    deleted kwarg records "<no limit kwarg>" and a 6 records 6."""
    GATHER_CALLS.clear()
    p = service_six_task_pipeline()
    run(
        p._run_parallel_enrichment(
            M.EnrichmentResult(),
            image(),
            [det("person", 1), det("car", 2), det("dog", 3)],
            {1: image()},
            "cam-1",
        )
    )
    assert len(p._fired) == 6, p._fired  # 6 Phase-1 tasks really scheduled
    assert GATHER_CALLS == [5, 5, 5], GATHER_CALLS


def test_cpu_group_gather_peaks_at_five_inflight() -> None:
    """Shape #209/#211 at L2690, measured as concurrency instead of as an
    argument: the same 6 Phase-1 tasks peak at 5 in flight under the shipped
    ``limit=5``; deleting the kwarg (default 10) or passing 6 lets all 6 run at
    once."""
    GATHER_CALLS.clear()
    p = service_six_task_pipeline()
    run(
        p._run_parallel_enrichment(
            M.EnrichmentResult(),
            image(),
            [det("person", 1), det("car", 2), det("dog", 3)],
            {1: image()},
            "cam-1",
        )
    )
    assert p._ep02_st["peak"] == 5, p._ep02_st


def test_limit_five_is_discriminating_and_default_is_ten() -> None:
    """Companion calibration for the same workload shape: 4->4, 5->5, 6->6, and
    11 tasks with no kwarg->10, i.e. the callee default that a deleted
    ``limit=5`` silently promotes the site to.  The callee itself is unchanged by
    shapes #209/#211 (they mutate the CALL sites), so its default is pinned here
    as the shipped value 10."""
    assert run(_peak(6, limit=4)) == 4
    assert run(_peak(6, limit=5)) == 5
    assert run(_peak(6, limit=6)) == 6
    assert run(_peak(11)) == 10
    assert inspect.signature(_ORIGINAL_BOUNDED_GATHER).parameters["limit"].default == 10


def test_parallel_enrichment_really_reaches_the_mutated_gathers() -> None:
    """End-to-end witness that a gated task flows through the CPU-group gather
    at L2690 and into ``_process_phase1_results`` — the path shapes #209/#211
    mutate."""
    p = arm(minimal_pipeline(vehicle_classification_enabled=True))
    p._quality_level = "full"
    p._fired = {}
    seen: list[list[str]] = []
    p._process_phase1_results = lambda res, d: seen.append(sorted(d))
    run(
        p._run_parallel_enrichment(
            M.EnrichmentResult(), image(), [det("car", 42)], {42: image()}, "cam-1"
        )
    )
    assert {"vt"} <= set(p._fired), p._fired
    assert seen == [["vehicle_classification"]], seen


# ===========================================================================
# E) EnrichmentError.to_dict round trip — the carrier that surfaces any value
#    change at the from_exception return sites
# ===========================================================================
def test_to_dict_round_trip_carries_all_mutated_fields() -> None:
    err = fe(httpx.ConnectError("refused"), operation="op", details={"a": 1})
    assert err.to_dict() == {
        "operation": "op",
        "category": M.ErrorCategory.SERVICE_UNAVAILABLE.value,
        "reason": err.reason,
        "error_type": "ConnectError",
        "is_transient": True,
        "details": {"a": 1},
    }
