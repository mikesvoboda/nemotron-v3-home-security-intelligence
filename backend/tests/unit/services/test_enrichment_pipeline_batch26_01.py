"""Chunk-01 kill battery — enrichment_pipeline structured-log payload survivors.

Every mutmut survivor in chunk 01 mutates ONE entry of the ``extra={...}``
structured-logging payload inside one of the seven exception handlers of
``EnrichmentPipeline._classify_person_clothing`` (shipped L6576-6726),
``_classify_pets`` (L7112-7267) or ``_classify_vehicle_types`` (L6790-6945).

Shipped behaviour (every value asserted below was MEASURED against pristine HEAD
source — see probes/c01/dump2.jsonl): on failure each method returns ``{}`` and
emits EXACTLY one record on the ``backend.services.enrichment_pipeline`` logger
carrying exactly the shipped payload keys at the shipped severity:

* KeyError         -> WARNING {detection_type, operation, error_category="parse_error"}
                    (NO error_type, NO is_transient, NO status_code)
* unavailable tuple-> WARNING + error_type=<exc class> + "service_unavailable" + is_transient=True
* ConnectError     -> WARNING + "service_unavailable" + is_transient=True
* TimeoutException -> WARNING + "timeout" + is_transient=True
* HTTPStatusError  -> 500<=code<600: WARNING + "server_error" + status_code + is_transient=True
                     else (4xx):    ERROR   + "client_error"  + status_code + is_transient=False
* ValueError/TypeError -> ERROR + "parse_error" + error_type=<exc class> + is_transient=False
* Exception (catch)-> ERROR + "unexpected" + is_transient=True (NO error_type)

The payload is asserted as a COMPLETE dict over the six keys the three methods
ever emit, so a key-renaming mutant ("is_transient" -> "IS_TRANSIENT") fails on
the missing attribute and a value mutant ("person" -> "PERSON") fails on value.

Handlers are reached through the live class attr (``M.EnrichmentPipeline``) so the
ep_plugin swap is observed; a ``from ... import`` would freeze shipped code.
"""

from __future__ import annotations

import logging
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
from PIL import Image

import backend.services.enrichment_pipeline as M
from backend.core.exceptions import EnrichmentUnavailableError
from backend.services.enrichment_pipeline import BoundingBox, DetectionInput

MODLOG = "backend.services.enrichment_pipeline"
# the six payload keys any of the three methods ever emits (measured)
PAYLOAD_KEYS = (
    "detection_type",
    "operation",
    "error_type",
    "error_category",
    "status_code",
    "is_transient",
)


def _request() -> httpx.Request:
    return httpx.Request("GET", "http://svc/enrich")


def _exc_for(method: str, scenario: str) -> Exception:
    """One exception per handler branch of the three classification methods."""
    if scenario == "keyerror":
        # The KeyError identity is irrelevant: the handler is selected by type and
        # its payload carries no error_type, so all candidates are equivalent.
        return KeyError(
            {
                "clothing": "fashion-clip",
                "pets": "pet-classifier",
                "vehicles": "vehicle-segment-classification",
            }[method]
        )
    if scenario == "unavail":
        return EnrichmentUnavailableError("svc down")
    if scenario == "connect":
        return httpx.ConnectError("connection refused")
    if scenario == "timeout":
        return httpx.TimeoutException("too slow")
    if scenario.startswith("http"):
        code = int(scenario[4:])
        return httpx.HTTPStatusError(
            "status", request=_request(), response=httpx.Response(code, request=_request())
        )
    if scenario == "valueerror":
        return ValueError("bad payload")
    if scenario == "typeerror":
        return TypeError("bad type")
    if scenario == "catchall":
        return RuntimeError("unexpected")
    raise AssertionError(f"unknown scenario {scenario}")


def _pipeline_raising(exc: Exception) -> "M.EnrichmentPipeline":
    manager = MagicMock()

    async def _boom(*_args, **_kwargs):
        raise exc

    manager.load = MagicMock(return_value=AsyncMock(__aenter__=_boom, __aexit__=AsyncMock()))
    return M.EnrichmentPipeline(model_manager=manager)


_METHOD = {
    "clothing": "_classify_person_clothing",
    "pets": "_classify_pets",
    "vehicles": "_classify_vehicle_types",
}
_DET_CLASS = {"clothing": "person", "pets": "animal", "vehicles": "vehicle"}


async def _run(caplog: pytest.LogCaptureFixture, method: str, scenario: str):
    """Drive one handler branch; return the single record it emitted."""
    pipeline = _pipeline_raising(_exc_for(method, scenario))
    det = DetectionInput(
        id=7,
        class_name=_DET_CLASS[method],
        confidence=0.9,
        bbox=BoundingBox(x1=1, y1=2, x2=20, y2=22),
    )
    caplog.clear()
    with caplog.at_level(logging.DEBUG, logger=MODLOG):
        results = await getattr(M.EnrichmentPipeline, _METHOD[method])(
            pipeline, [det], Image.new("RGB", (32, 32), "red")
        )
    assert results == {}, "shipped: every failure branch returns the empty dict"
    records = [r for r in caplog.records if r.name == MODLOG]
    assert len(records) == 1, [(r.levelno, r.getMessage()) for r in caplog.records]
    return records[0]


def _payload(record) -> dict:
    """The record's payload restricted to the six ever-emitted keys (measured)."""
    return {k: getattr(record, k) for k in PAYLOAD_KEYS if hasattr(record, k)}


async def _expect(caplog, method, scenario, level, payload):
    """Pin severity + the complete measured payload of one handler branch."""
    record = await _run(caplog, method, scenario)
    assert record.levelno == level, (record.levelno, record.getMessage())
    assert _payload(record) == payload, _payload(record)


# --------------------------------------------------------------------- #
# SHIPPED PINS — one per (method, handler branch); every value measured. #
# --------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_clothing_keyerror_payload(caplog):
    """MEASURED shipped warning payload: clothing/keyerror."""
    await _expect(
        caplog,
        "clothing",
        "keyerror",
        logging.WARNING,
        {
            "detection_type": "person",
            "error_category": "parse_error",
            "operation": "clothing_classification",
        },
    )


@pytest.mark.asyncio
async def test_clothing_unavailable_payload(caplog):
    """MEASURED shipped warning payload: clothing/unavail."""
    await _expect(
        caplog,
        "clothing",
        "unavail",
        logging.WARNING,
        {
            "detection_type": "person",
            "error_category": "service_unavailable",
            "error_type": "EnrichmentUnavailableError",
            "is_transient": True,
            "operation": "clothing_classification",
        },
    )


@pytest.mark.asyncio
async def test_clothing_connect_payload(caplog):
    """MEASURED shipped warning payload: clothing/connect."""
    await _expect(
        caplog,
        "clothing",
        "connect",
        logging.WARNING,
        {
            "detection_type": "person",
            "error_category": "service_unavailable",
            "error_type": "ConnectError",
            "is_transient": True,
            "operation": "clothing_classification",
        },
    )


@pytest.mark.asyncio
async def test_clothing_timeout_payload(caplog):
    """MEASURED shipped warning payload: clothing/timeout."""
    await _expect(
        caplog,
        "clothing",
        "timeout",
        logging.WARNING,
        {
            "detection_type": "person",
            "error_category": "timeout",
            "error_type": "TimeoutException",
            "is_transient": True,
            "operation": "clothing_classification",
        },
    )


@pytest.mark.asyncio
async def test_clothing_server_error_503_payload(caplog):
    """MEASURED shipped warning payload: clothing/http5xx."""
    await _expect(
        caplog,
        "clothing",
        "http503",
        logging.WARNING,
        {
            "detection_type": "person",
            "error_category": "server_error",
            "error_type": "HTTPStatusError",
            "is_transient": True,
            "operation": "clothing_classification",
            "status_code": 503,
        },
    )


@pytest.mark.asyncio
async def test_clothing_server_error_599_payload(caplog):
    """MEASURED shipped warning payload: clothing/http599."""
    await _expect(
        caplog,
        "clothing",
        "http599",
        logging.WARNING,
        {
            "detection_type": "person",
            "error_category": "server_error",
            "error_type": "HTTPStatusError",
            "is_transient": True,
            "operation": "clothing_classification",
            "status_code": 599,
        },
    )


@pytest.mark.asyncio
async def test_clothing_client_error_400_payload(caplog):
    """MEASURED shipped error payload: clothing/http400."""
    await _expect(
        caplog,
        "clothing",
        "http400",
        logging.ERROR,
        {
            "detection_type": "person",
            "error_category": "client_error",
            "error_type": "HTTPStatusError",
            "is_transient": False,
            "operation": "clothing_classification",
            "status_code": 400,
        },
    )


@pytest.mark.asyncio
async def test_clothing_client_error_404_payload(caplog):
    """MEASURED shipped error payload: clothing/http404."""
    await _expect(
        caplog,
        "clothing",
        "http404",
        logging.ERROR,
        {
            "detection_type": "person",
            "error_category": "client_error",
            "error_type": "HTTPStatusError",
            "is_transient": False,
            "operation": "clothing_classification",
            "status_code": 404,
        },
    )


@pytest.mark.asyncio
async def test_clothing_parse_error_value_payload(caplog):
    """MEASURED shipped error payload: clothing/valueerror."""
    await _expect(
        caplog,
        "clothing",
        "valueerror",
        logging.ERROR,
        {
            "detection_type": "person",
            "error_category": "parse_error",
            "error_type": "ValueError",
            "is_transient": False,
            "operation": "clothing_classification",
        },
    )


@pytest.mark.asyncio
async def test_clothing_parse_error_type_payload(caplog):
    """MEASURED shipped error payload: clothing/typeerror."""
    await _expect(
        caplog,
        "clothing",
        "typeerror",
        logging.ERROR,
        {
            "detection_type": "person",
            "error_category": "parse_error",
            "error_type": "TypeError",
            "is_transient": False,
            "operation": "clothing_classification",
        },
    )


@pytest.mark.asyncio
async def test_clothing_unexpected_payload(caplog):
    """MEASURED shipped error payload: clothing/catchall."""
    await _expect(
        caplog,
        "clothing",
        "catchall",
        logging.ERROR,
        {
            "detection_type": "person",
            "error_category": "unexpected",
            "is_transient": True,
            "operation": "clothing_classification",
        },
    )


@pytest.mark.asyncio
async def test_pets_keyerror_payload(caplog):
    """MEASURED shipped warning payload: pets/keyerror."""
    await _expect(
        caplog,
        "pets",
        "keyerror",
        logging.WARNING,
        {
            "detection_type": "animal",
            "error_category": "parse_error",
            "operation": "pet_classification",
        },
    )


@pytest.mark.asyncio
async def test_pets_unavailable_payload(caplog):
    """MEASURED shipped warning payload: pets/unavail."""
    await _expect(
        caplog,
        "pets",
        "unavail",
        logging.WARNING,
        {
            "detection_type": "animal",
            "error_category": "service_unavailable",
            "error_type": "EnrichmentUnavailableError",
            "is_transient": True,
            "operation": "pet_classification",
        },
    )


@pytest.mark.asyncio
async def test_pets_connect_payload(caplog):
    """MEASURED shipped warning payload: pets/connect."""
    await _expect(
        caplog,
        "pets",
        "connect",
        logging.WARNING,
        {
            "detection_type": "animal",
            "error_category": "service_unavailable",
            "error_type": "ConnectError",
            "is_transient": True,
            "operation": "pet_classification",
        },
    )


@pytest.mark.asyncio
async def test_pets_timeout_payload(caplog):
    """MEASURED shipped warning payload: pets/timeout."""
    await _expect(
        caplog,
        "pets",
        "timeout",
        logging.WARNING,
        {
            "detection_type": "animal",
            "error_category": "timeout",
            "error_type": "TimeoutException",
            "is_transient": True,
            "operation": "pet_classification",
        },
    )


@pytest.mark.asyncio
async def test_pets_server_error_503_payload(caplog):
    """MEASURED shipped warning payload: pets/http5xx."""
    await _expect(
        caplog,
        "pets",
        "http503",
        logging.WARNING,
        {
            "detection_type": "animal",
            "error_category": "server_error",
            "error_type": "HTTPStatusError",
            "is_transient": True,
            "operation": "pet_classification",
            "status_code": 503,
        },
    )


@pytest.mark.asyncio
async def test_pets_server_error_599_payload(caplog):
    """MEASURED shipped warning payload: pets/http599."""
    await _expect(
        caplog,
        "pets",
        "http599",
        logging.WARNING,
        {
            "detection_type": "animal",
            "error_category": "server_error",
            "error_type": "HTTPStatusError",
            "is_transient": True,
            "operation": "pet_classification",
            "status_code": 599,
        },
    )


@pytest.mark.asyncio
async def test_pets_client_error_400_payload(caplog):
    """MEASURED shipped error payload: pets/http400."""
    await _expect(
        caplog,
        "pets",
        "http400",
        logging.ERROR,
        {
            "detection_type": "animal",
            "error_category": "client_error",
            "error_type": "HTTPStatusError",
            "is_transient": False,
            "operation": "pet_classification",
            "status_code": 400,
        },
    )


@pytest.mark.asyncio
async def test_pets_client_error_404_payload(caplog):
    """MEASURED shipped error payload: pets/http404."""
    await _expect(
        caplog,
        "pets",
        "http404",
        logging.ERROR,
        {
            "detection_type": "animal",
            "error_category": "client_error",
            "error_type": "HTTPStatusError",
            "is_transient": False,
            "operation": "pet_classification",
            "status_code": 404,
        },
    )


@pytest.mark.asyncio
async def test_pets_parse_error_value_payload(caplog):
    """MEASURED shipped error payload: pets/valueerror."""
    await _expect(
        caplog,
        "pets",
        "valueerror",
        logging.ERROR,
        {
            "detection_type": "animal",
            "error_category": "parse_error",
            "error_type": "ValueError",
            "is_transient": False,
            "operation": "pet_classification",
        },
    )


@pytest.mark.asyncio
async def test_pets_parse_error_type_payload(caplog):
    """MEASURED shipped error payload: pets/typeerror."""
    await _expect(
        caplog,
        "pets",
        "typeerror",
        logging.ERROR,
        {
            "detection_type": "animal",
            "error_category": "parse_error",
            "error_type": "TypeError",
            "is_transient": False,
            "operation": "pet_classification",
        },
    )


@pytest.mark.asyncio
async def test_pets_unexpected_payload(caplog):
    """MEASURED shipped error payload: pets/catchall."""
    await _expect(
        caplog,
        "pets",
        "catchall",
        logging.ERROR,
        {
            "detection_type": "animal",
            "error_category": "unexpected",
            "is_transient": True,
            "operation": "pet_classification",
        },
    )


@pytest.mark.asyncio
async def test_vehicles_keyerror_payload(caplog):
    """MEASURED shipped warning payload: vehicles/keyerror."""
    await _expect(
        caplog,
        "vehicles",
        "keyerror",
        logging.WARNING,
        {
            "detection_type": "vehicle",
            "error_category": "parse_error",
            "operation": "vehicle_classification",
        },
    )


@pytest.mark.asyncio
async def test_vehicles_unavailable_payload(caplog):
    """MEASURED shipped warning payload: vehicles/unavail."""
    await _expect(
        caplog,
        "vehicles",
        "unavail",
        logging.WARNING,
        {
            "detection_type": "vehicle",
            "error_category": "service_unavailable",
            "error_type": "EnrichmentUnavailableError",
            "is_transient": True,
            "operation": "vehicle_classification",
        },
    )


@pytest.mark.asyncio
async def test_vehicles_connect_payload(caplog):
    """MEASURED shipped warning payload: vehicles/connect."""
    await _expect(
        caplog,
        "vehicles",
        "connect",
        logging.WARNING,
        {
            "detection_type": "vehicle",
            "error_category": "service_unavailable",
            "error_type": "ConnectError",
            "is_transient": True,
            "operation": "vehicle_classification",
        },
    )


@pytest.mark.asyncio
async def test_vehicles_timeout_payload(caplog):
    """MEASURED shipped warning payload: vehicles/timeout."""
    await _expect(
        caplog,
        "vehicles",
        "timeout",
        logging.WARNING,
        {
            "detection_type": "vehicle",
            "error_category": "timeout",
            "error_type": "TimeoutException",
            "is_transient": True,
            "operation": "vehicle_classification",
        },
    )


@pytest.mark.asyncio
async def test_vehicles_server_error_503_payload(caplog):
    """MEASURED shipped warning payload: vehicles/http5xx."""
    await _expect(
        caplog,
        "vehicles",
        "http503",
        logging.WARNING,
        {
            "detection_type": "vehicle",
            "error_category": "server_error",
            "error_type": "HTTPStatusError",
            "is_transient": True,
            "operation": "vehicle_classification",
            "status_code": 503,
        },
    )


@pytest.mark.asyncio
async def test_vehicles_server_error_599_payload(caplog):
    """MEASURED shipped warning payload: vehicles/http599."""
    await _expect(
        caplog,
        "vehicles",
        "http599",
        logging.WARNING,
        {
            "detection_type": "vehicle",
            "error_category": "server_error",
            "error_type": "HTTPStatusError",
            "is_transient": True,
            "operation": "vehicle_classification",
            "status_code": 599,
        },
    )


@pytest.mark.asyncio
async def test_vehicles_client_error_400_payload(caplog):
    """MEASURED shipped error payload: vehicles/http400."""
    await _expect(
        caplog,
        "vehicles",
        "http400",
        logging.ERROR,
        {
            "detection_type": "vehicle",
            "error_category": "client_error",
            "error_type": "HTTPStatusError",
            "is_transient": False,
            "operation": "vehicle_classification",
            "status_code": 400,
        },
    )


@pytest.mark.asyncio
async def test_vehicles_client_error_404_payload(caplog):
    """MEASURED shipped error payload: vehicles/http404."""
    await _expect(
        caplog,
        "vehicles",
        "http404",
        logging.ERROR,
        {
            "detection_type": "vehicle",
            "error_category": "client_error",
            "error_type": "HTTPStatusError",
            "is_transient": False,
            "operation": "vehicle_classification",
            "status_code": 404,
        },
    )


@pytest.mark.asyncio
async def test_vehicles_parse_error_value_payload(caplog):
    """MEASURED shipped error payload: vehicles/valueerror."""
    await _expect(
        caplog,
        "vehicles",
        "valueerror",
        logging.ERROR,
        {
            "detection_type": "vehicle",
            "error_category": "parse_error",
            "error_type": "ValueError",
            "is_transient": False,
            "operation": "vehicle_classification",
        },
    )


@pytest.mark.asyncio
async def test_vehicles_parse_error_type_payload(caplog):
    """MEASURED shipped error payload: vehicles/typeerror."""
    await _expect(
        caplog,
        "vehicles",
        "typeerror",
        logging.ERROR,
        {
            "detection_type": "vehicle",
            "error_category": "parse_error",
            "error_type": "TypeError",
            "is_transient": False,
            "operation": "vehicle_classification",
        },
    )


@pytest.mark.asyncio
async def test_vehicles_unexpected_payload(caplog):
    """MEASURED shipped error payload: vehicles/catchall."""
    await _expect(
        caplog,
        "vehicles",
        "catchall",
        logging.ERROR,
        {
            "detection_type": "vehicle",
            "error_category": "unexpected",
            "is_transient": True,
            "operation": "vehicle_classification",
        },
    )


@pytest.mark.asyncio
async def test_payload_key_set_is_exact(caplog):
    """MEASURED shipped key set; renamed-key twins must not appear on the record.

    A key-rename mutant would drop "is_transient" and add e.g. "IS_TRANSIENT".
    The dict equality fails on the missing key; the twin scan fails on the extra
    one, so both halves of the delta are pinned.
    """
    record = await _run(caplog, "clothing", "unavail")
    assert _payload(record) == {
        "detection_type": "person",
        "operation": "clothing_classification",
        "error_type": "EnrichmentUnavailableError",
        "error_category": "service_unavailable",
        "is_transient": True,
    }, _payload(record)
    up = {k.upper() for k in PAYLOAD_KEYS}
    twins = sorted(
        a
        for a in record.__dict__
        if a.upper() in up and a not in PAYLOAD_KEYS and not a.startswith("_")
    )
    assert twins == [], twins


# --------------------------------------------------------------------- #
# BATTERY — one test per shape group. Each sweeps EVERY handler branch of #
# that method which carries an occurrence of the mutated literal, so one  #
# splice disposes the whole twin group (rule 4).                          #
# --------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_clothing_detection_type_sentinel_value_all_branches(caplog):
    """Shape group 1: "detection_type": "person" -> "detection_type": "XXpersonXX" (all twin mutants).

    Mutates the detection_type entry of the structured-log payload in every clothing
    handler branch listed below; each branch's complete shipped payload is
    pinned, so the mutant fails whichever branch the harness drives.
    """
    # mutmut_42: shipped L6627 — keyerror branch
    await _expect(
        caplog,
        "clothing",
        "keyerror",
        logging.WARNING,
        {
            "detection_type": "person",
            "error_category": "parse_error",
            "operation": "clothing_classification",
        },
    )
    # mutmut_57: shipped L6642 — unavail branch
    await _expect(
        caplog,
        "clothing",
        "unavail",
        logging.WARNING,
        {
            "detection_type": "person",
            "error_category": "service_unavailable",
            "error_type": "EnrichmentUnavailableError",
            "is_transient": True,
            "operation": "clothing_classification",
        },
    )
    # mutmut_99: shipped L6666 — timeout branch
    await _expect(
        caplog,
        "clothing",
        "timeout",
        logging.WARNING,
        {
            "detection_type": "person",
            "error_category": "timeout",
            "error_type": "TimeoutException",
            "is_transient": True,
            "operation": "clothing_classification",
        },
    )
    # mutmut_124: shipped L6680 — http5xx branch
    await _expect(
        caplog,
        "clothing",
        "http503",
        logging.WARNING,
        {
            "detection_type": "person",
            "error_category": "server_error",
            "error_type": "HTTPStatusError",
            "is_transient": True,
            "operation": "clothing_classification",
            "status_code": 503,
        },
    )
    # mutmut_147: shipped L6706 — valueerror branch
    await _expect(
        caplog,
        "clothing",
        "valueerror",
        logging.ERROR,
        {
            "detection_type": "person",
            "error_category": "parse_error",
            "error_type": "ValueError",
            "is_transient": False,
            "operation": "clothing_classification",
        },
    )
    # mutmut_173: shipped L6719 — catchall branch
    await _expect(
        caplog,
        "clothing",
        "catchall",
        logging.ERROR,
        {
            "detection_type": "person",
            "error_category": "unexpected",
            "is_transient": True,
            "operation": "clothing_classification",
        },
    )


@pytest.mark.asyncio
async def test_clothing_detection_type_uppercase_value_all_branches(caplog):
    """Shape group 2: "detection_type": "person" -> "detection_type": "PERSON" (all twin mutants).

    Mutates the detection_type entry of the structured-log payload in every clothing
    handler branch listed below; each branch's complete shipped payload is
    pinned, so the mutant fails whichever branch the harness drives.
    """
    # mutmut_43: shipped L6627 — keyerror branch
    await _expect(
        caplog,
        "clothing",
        "keyerror",
        logging.WARNING,
        {
            "detection_type": "person",
            "error_category": "parse_error",
            "operation": "clothing_classification",
        },
    )
    # mutmut_58: shipped L6642 — unavail branch
    await _expect(
        caplog,
        "clothing",
        "unavail",
        logging.WARNING,
        {
            "detection_type": "person",
            "error_category": "service_unavailable",
            "error_type": "EnrichmentUnavailableError",
            "is_transient": True,
            "operation": "clothing_classification",
        },
    )
    # mutmut_100: shipped L6666 — timeout branch
    await _expect(
        caplog,
        "clothing",
        "timeout",
        logging.WARNING,
        {
            "detection_type": "person",
            "error_category": "timeout",
            "error_type": "TimeoutException",
            "is_transient": True,
            "operation": "clothing_classification",
        },
    )
    # mutmut_125: shipped L6680 — http5xx branch
    await _expect(
        caplog,
        "clothing",
        "http503",
        logging.WARNING,
        {
            "detection_type": "person",
            "error_category": "server_error",
            "error_type": "HTTPStatusError",
            "is_transient": True,
            "operation": "clothing_classification",
            "status_code": 503,
        },
    )
    # mutmut_148: shipped L6706 — valueerror branch
    await _expect(
        caplog,
        "clothing",
        "valueerror",
        logging.ERROR,
        {
            "detection_type": "person",
            "error_category": "parse_error",
            "error_type": "ValueError",
            "is_transient": False,
            "operation": "clothing_classification",
        },
    )
    # mutmut_174: shipped L6719 — catchall branch
    await _expect(
        caplog,
        "clothing",
        "catchall",
        logging.ERROR,
        {
            "detection_type": "person",
            "error_category": "unexpected",
            "is_transient": True,
            "operation": "clothing_classification",
        },
    )


@pytest.mark.asyncio
async def test_clothing_error_type_key_sentinel_all_branches(caplog):
    """Shape group 3: "error_type": type(e).__name__ -> "XXerror_typeXX": type(e).__name__ (all twin mutants).

    Mutates the error_type entry of the structured-log payload in every clothing
    handler branch listed below; each branch's complete shipped payload is
    pinned, so the mutant fails whichever branch the harness drives.
    """
    # mutmut_63: shipped L6644 — unavail branch
    await _expect(
        caplog,
        "clothing",
        "unavail",
        logging.WARNING,
        {
            "detection_type": "person",
            "error_category": "service_unavailable",
            "error_type": "EnrichmentUnavailableError",
            "is_transient": True,
            "operation": "clothing_classification",
        },
    )
    # mutmut_84: shipped L6656 — connect branch
    await _expect(
        caplog,
        "clothing",
        "connect",
        logging.WARNING,
        {
            "detection_type": "person",
            "error_category": "service_unavailable",
            "error_type": "ConnectError",
            "is_transient": True,
            "operation": "clothing_classification",
        },
    )
    # mutmut_105: shipped L6668 — timeout branch
    await _expect(
        caplog,
        "clothing",
        "timeout",
        logging.WARNING,
        {
            "detection_type": "person",
            "error_category": "timeout",
            "error_type": "TimeoutException",
            "is_transient": True,
            "operation": "clothing_classification",
        },
    )
    # mutmut_130: shipped L6682 — http5xx branch
    await _expect(
        caplog,
        "clothing",
        "http503",
        logging.WARNING,
        {
            "detection_type": "person",
            "error_category": "server_error",
            "error_type": "HTTPStatusError",
            "is_transient": True,
            "operation": "clothing_classification",
            "status_code": 503,
        },
    )
    # mutmut_153: shipped L6708 — valueerror branch
    await _expect(
        caplog,
        "clothing",
        "valueerror",
        logging.ERROR,
        {
            "detection_type": "person",
            "error_category": "parse_error",
            "error_type": "ValueError",
            "is_transient": False,
            "operation": "clothing_classification",
        },
    )


@pytest.mark.asyncio
async def test_clothing_error_type_key_uppercase_all_branches(caplog):
    """Shape group 4: "error_type": type(e).__name__ -> "ERROR_TYPE": type(e).__name__ (all twin mutants).

    Mutates the error_type entry of the structured-log payload in every clothing
    handler branch listed below; each branch's complete shipped payload is
    pinned, so the mutant fails whichever branch the harness drives.
    """
    # mutmut_64: shipped L6644 — unavail branch
    await _expect(
        caplog,
        "clothing",
        "unavail",
        logging.WARNING,
        {
            "detection_type": "person",
            "error_category": "service_unavailable",
            "error_type": "EnrichmentUnavailableError",
            "is_transient": True,
            "operation": "clothing_classification",
        },
    )
    # mutmut_85: shipped L6656 — connect branch
    await _expect(
        caplog,
        "clothing",
        "connect",
        logging.WARNING,
        {
            "detection_type": "person",
            "error_category": "service_unavailable",
            "error_type": "ConnectError",
            "is_transient": True,
            "operation": "clothing_classification",
        },
    )
    # mutmut_106: shipped L6668 — timeout branch
    await _expect(
        caplog,
        "clothing",
        "timeout",
        logging.WARNING,
        {
            "detection_type": "person",
            "error_category": "timeout",
            "error_type": "TimeoutException",
            "is_transient": True,
            "operation": "clothing_classification",
        },
    )
    # mutmut_131: shipped L6682 — http5xx branch
    await _expect(
        caplog,
        "clothing",
        "http503",
        logging.WARNING,
        {
            "detection_type": "person",
            "error_category": "server_error",
            "error_type": "HTTPStatusError",
            "is_transient": True,
            "operation": "clothing_classification",
            "status_code": 503,
        },
    )
    # mutmut_154: shipped L6708 — valueerror branch
    await _expect(
        caplog,
        "clothing",
        "valueerror",
        logging.ERROR,
        {
            "detection_type": "person",
            "error_category": "parse_error",
            "error_type": "ValueError",
            "is_transient": False,
            "operation": "clothing_classification",
        },
    )


@pytest.mark.asyncio
async def test_clothing_error_type_typenone_value_all_branches(caplog):
    """Shape group 5: "error_type": type(e).__name__ -> "error_type": type(None).__name__ (all twin mutants).

    Mutates the error_type entry of the structured-log payload in every clothing
    handler branch listed below; each branch's complete shipped payload is
    pinned, so the mutant fails whichever branch the harness drives.
    """
    # mutmut_65: shipped L6644 — unavail branch
    await _expect(
        caplog,
        "clothing",
        "unavail",
        logging.WARNING,
        {
            "detection_type": "person",
            "error_category": "service_unavailable",
            "error_type": "EnrichmentUnavailableError",
            "is_transient": True,
            "operation": "clothing_classification",
        },
    )
    # mutmut_86: shipped L6656 — connect branch
    await _expect(
        caplog,
        "clothing",
        "connect",
        logging.WARNING,
        {
            "detection_type": "person",
            "error_category": "service_unavailable",
            "error_type": "ConnectError",
            "is_transient": True,
            "operation": "clothing_classification",
        },
    )
    # mutmut_107: shipped L6668 — timeout branch
    await _expect(
        caplog,
        "clothing",
        "timeout",
        logging.WARNING,
        {
            "detection_type": "person",
            "error_category": "timeout",
            "error_type": "TimeoutException",
            "is_transient": True,
            "operation": "clothing_classification",
        },
    )
    # mutmut_132: shipped L6682 — http5xx branch
    await _expect(
        caplog,
        "clothing",
        "http503",
        logging.WARNING,
        {
            "detection_type": "person",
            "error_category": "server_error",
            "error_type": "HTTPStatusError",
            "is_transient": True,
            "operation": "clothing_classification",
            "status_code": 503,
        },
    )
    # mutmut_155: shipped L6708 — valueerror branch
    await _expect(
        caplog,
        "clothing",
        "valueerror",
        logging.ERROR,
        {
            "detection_type": "person",
            "error_category": "parse_error",
            "error_type": "ValueError",
            "is_transient": False,
            "operation": "clothing_classification",
        },
    )


@pytest.mark.asyncio
async def test_clothing_is_transient_key_sentinel_all_branches(caplog):
    """Shape group 6: "is_transient": True -> "XXis_transientXX": True (all twin mutants).

    Mutates the is_transient entry of the structured-log payload in every clothing
    handler branch listed below; each branch's complete shipped payload is
    pinned, so the mutant fails whichever branch the harness drives.
    """
    # mutmut_68: shipped L6646 — unavail branch
    await _expect(
        caplog,
        "clothing",
        "unavail",
        logging.WARNING,
        {
            "detection_type": "person",
            "error_category": "service_unavailable",
            "error_type": "EnrichmentUnavailableError",
            "is_transient": True,
            "operation": "clothing_classification",
        },
    )
    # mutmut_89: shipped L6658 — connect branch
    await _expect(
        caplog,
        "clothing",
        "connect",
        logging.WARNING,
        {
            "detection_type": "person",
            "error_category": "service_unavailable",
            "error_type": "ConnectError",
            "is_transient": True,
            "operation": "clothing_classification",
        },
    )
    # mutmut_110: shipped L6670 — timeout branch
    await _expect(
        caplog,
        "clothing",
        "timeout",
        logging.WARNING,
        {
            "detection_type": "person",
            "error_category": "timeout",
            "error_type": "TimeoutException",
            "is_transient": True,
            "operation": "clothing_classification",
        },
    )
    # mutmut_137: shipped L6685 — http5xx branch
    await _expect(
        caplog,
        "clothing",
        "http503",
        logging.WARNING,
        {
            "detection_type": "person",
            "error_category": "server_error",
            "error_type": "HTTPStatusError",
            "is_transient": True,
            "operation": "clothing_classification",
            "status_code": 503,
        },
    )
    # mutmut_181: shipped L6722 — catchall branch
    await _expect(
        caplog,
        "clothing",
        "catchall",
        logging.ERROR,
        {
            "detection_type": "person",
            "error_category": "unexpected",
            "is_transient": True,
            "operation": "clothing_classification",
        },
    )


@pytest.mark.asyncio
async def test_clothing_is_transient_key_uppercase_all_branches(caplog):
    """Shape group 7: "is_transient": True -> "IS_TRANSIENT": True (all twin mutants).

    Mutates the is_transient entry of the structured-log payload in every clothing
    handler branch listed below; each branch's complete shipped payload is
    pinned, so the mutant fails whichever branch the harness drives.
    """
    # mutmut_69: shipped L6646 — unavail branch
    await _expect(
        caplog,
        "clothing",
        "unavail",
        logging.WARNING,
        {
            "detection_type": "person",
            "error_category": "service_unavailable",
            "error_type": "EnrichmentUnavailableError",
            "is_transient": True,
            "operation": "clothing_classification",
        },
    )
    # mutmut_90: shipped L6658 — connect branch
    await _expect(
        caplog,
        "clothing",
        "connect",
        logging.WARNING,
        {
            "detection_type": "person",
            "error_category": "service_unavailable",
            "error_type": "ConnectError",
            "is_transient": True,
            "operation": "clothing_classification",
        },
    )
    # mutmut_111: shipped L6670 — timeout branch
    await _expect(
        caplog,
        "clothing",
        "timeout",
        logging.WARNING,
        {
            "detection_type": "person",
            "error_category": "timeout",
            "error_type": "TimeoutException",
            "is_transient": True,
            "operation": "clothing_classification",
        },
    )
    # mutmut_138: shipped L6685 — http5xx branch
    await _expect(
        caplog,
        "clothing",
        "http503",
        logging.WARNING,
        {
            "detection_type": "person",
            "error_category": "server_error",
            "error_type": "HTTPStatusError",
            "is_transient": True,
            "operation": "clothing_classification",
            "status_code": 503,
        },
    )
    # mutmut_182: shipped L6722 — catchall branch
    await _expect(
        caplog,
        "clothing",
        "catchall",
        logging.ERROR,
        {
            "detection_type": "person",
            "error_category": "unexpected",
            "is_transient": True,
            "operation": "clothing_classification",
        },
    )


@pytest.mark.asyncio
async def test_clothing_is_transient_true_to_false_all_branches(caplog):
    """Shape group 8: "is_transient": True -> "is_transient": False (all twin mutants).

    Mutates the is_transient entry of the structured-log payload in every clothing
    handler branch listed below; each branch's complete shipped payload is
    pinned, so the mutant fails whichever branch the harness drives.
    """
    # mutmut_70: shipped L6646 — unavail branch
    await _expect(
        caplog,
        "clothing",
        "unavail",
        logging.WARNING,
        {
            "detection_type": "person",
            "error_category": "service_unavailable",
            "error_type": "EnrichmentUnavailableError",
            "is_transient": True,
            "operation": "clothing_classification",
        },
    )
    # mutmut_91: shipped L6658 — connect branch
    await _expect(
        caplog,
        "clothing",
        "connect",
        logging.WARNING,
        {
            "detection_type": "person",
            "error_category": "service_unavailable",
            "error_type": "ConnectError",
            "is_transient": True,
            "operation": "clothing_classification",
        },
    )
    # mutmut_112: shipped L6670 — timeout branch
    await _expect(
        caplog,
        "clothing",
        "timeout",
        logging.WARNING,
        {
            "detection_type": "person",
            "error_category": "timeout",
            "error_type": "TimeoutException",
            "is_transient": True,
            "operation": "clothing_classification",
        },
    )
    # mutmut_139: shipped L6685 — http5xx branch
    await _expect(
        caplog,
        "clothing",
        "http503",
        logging.WARNING,
        {
            "detection_type": "person",
            "error_category": "server_error",
            "error_type": "HTTPStatusError",
            "is_transient": True,
            "operation": "clothing_classification",
            "status_code": 503,
        },
    )
    # mutmut_183: shipped L6722 — catchall branch
    await _expect(
        caplog,
        "clothing",
        "catchall",
        logging.ERROR,
        {
            "detection_type": "person",
            "error_category": "unexpected",
            "is_transient": True,
            "operation": "clothing_classification",
        },
    )


@pytest.mark.asyncio
async def test_pets_detection_type_key_sentinel_all_branches(caplog):
    """Shape group 9: "detection_type": "animal" -> "XXdetection_typeXX": "animal" (all twin mutants).

    Mutates the detection_type entry of the structured-log payload in every pets
    handler branch listed below; each branch's complete shipped payload is
    pinned, so the mutant fails whichever branch the harness drives.
    """
    # mutmut_40: shipped L7168 — keyerror branch
    await _expect(
        caplog,
        "pets",
        "keyerror",
        logging.WARNING,
        {
            "detection_type": "animal",
            "error_category": "parse_error",
            "operation": "pet_classification",
        },
    )
    # mutmut_55: shipped L7183 — unavail branch
    await _expect(
        caplog,
        "pets",
        "unavail",
        logging.WARNING,
        {
            "detection_type": "animal",
            "error_category": "service_unavailable",
            "error_type": "EnrichmentUnavailableError",
            "is_transient": True,
            "operation": "pet_classification",
        },
    )
    # mutmut_76: shipped L7195 — connect branch
    await _expect(
        caplog,
        "pets",
        "connect",
        logging.WARNING,
        {
            "detection_type": "animal",
            "error_category": "service_unavailable",
            "error_type": "ConnectError",
            "is_transient": True,
            "operation": "pet_classification",
        },
    )
    # mutmut_97: shipped L7207 — timeout branch
    await _expect(
        caplog,
        "pets",
        "timeout",
        logging.WARNING,
        {
            "detection_type": "animal",
            "error_category": "timeout",
            "error_type": "TimeoutException",
            "is_transient": True,
            "operation": "pet_classification",
        },
    )
    # mutmut_145: shipped L7247 — valueerror branch
    await _expect(
        caplog,
        "pets",
        "valueerror",
        logging.ERROR,
        {
            "detection_type": "animal",
            "error_category": "parse_error",
            "error_type": "ValueError",
            "is_transient": False,
            "operation": "pet_classification",
        },
    )
    # mutmut_171: shipped L7260 — catchall branch
    await _expect(
        caplog,
        "pets",
        "catchall",
        logging.ERROR,
        {
            "detection_type": "animal",
            "error_category": "unexpected",
            "is_transient": True,
            "operation": "pet_classification",
        },
    )


@pytest.mark.asyncio
async def test_pets_detection_type_key_uppercase_all_branches(caplog):
    """Shape group 10: "detection_type": "animal" -> "DETECTION_TYPE": "animal" (all twin mutants).

    Mutates the detection_type entry of the structured-log payload in every pets
    handler branch listed below; each branch's complete shipped payload is
    pinned, so the mutant fails whichever branch the harness drives.
    """
    # mutmut_41: shipped L7168 — keyerror branch
    await _expect(
        caplog,
        "pets",
        "keyerror",
        logging.WARNING,
        {
            "detection_type": "animal",
            "error_category": "parse_error",
            "operation": "pet_classification",
        },
    )
    # mutmut_56: shipped L7183 — unavail branch
    await _expect(
        caplog,
        "pets",
        "unavail",
        logging.WARNING,
        {
            "detection_type": "animal",
            "error_category": "service_unavailable",
            "error_type": "EnrichmentUnavailableError",
            "is_transient": True,
            "operation": "pet_classification",
        },
    )
    # mutmut_77: shipped L7195 — connect branch
    await _expect(
        caplog,
        "pets",
        "connect",
        logging.WARNING,
        {
            "detection_type": "animal",
            "error_category": "service_unavailable",
            "error_type": "ConnectError",
            "is_transient": True,
            "operation": "pet_classification",
        },
    )
    # mutmut_98: shipped L7207 — timeout branch
    await _expect(
        caplog,
        "pets",
        "timeout",
        logging.WARNING,
        {
            "detection_type": "animal",
            "error_category": "timeout",
            "error_type": "TimeoutException",
            "is_transient": True,
            "operation": "pet_classification",
        },
    )
    # mutmut_146: shipped L7247 — valueerror branch
    await _expect(
        caplog,
        "pets",
        "valueerror",
        logging.ERROR,
        {
            "detection_type": "animal",
            "error_category": "parse_error",
            "error_type": "ValueError",
            "is_transient": False,
            "operation": "pet_classification",
        },
    )
    # mutmut_172: shipped L7260 — catchall branch
    await _expect(
        caplog,
        "pets",
        "catchall",
        logging.ERROR,
        {
            "detection_type": "animal",
            "error_category": "unexpected",
            "is_transient": True,
            "operation": "pet_classification",
        },
    )


@pytest.mark.asyncio
async def test_pets_detection_type_sentinel_value_all_branches(caplog):
    """Shape group 11: "detection_type": "animal" -> "detection_type": "XXanimalXX" (all twin mutants).

    Mutates the detection_type entry of the structured-log payload in every pets
    handler branch listed below; each branch's complete shipped payload is
    pinned, so the mutant fails whichever branch the harness drives.
    """
    # mutmut_42: shipped L7168 — keyerror branch
    await _expect(
        caplog,
        "pets",
        "keyerror",
        logging.WARNING,
        {
            "detection_type": "animal",
            "error_category": "parse_error",
            "operation": "pet_classification",
        },
    )
    # mutmut_57: shipped L7183 — unavail branch
    await _expect(
        caplog,
        "pets",
        "unavail",
        logging.WARNING,
        {
            "detection_type": "animal",
            "error_category": "service_unavailable",
            "error_type": "EnrichmentUnavailableError",
            "is_transient": True,
            "operation": "pet_classification",
        },
    )
    # mutmut_78: shipped L7195 — connect branch
    await _expect(
        caplog,
        "pets",
        "connect",
        logging.WARNING,
        {
            "detection_type": "animal",
            "error_category": "service_unavailable",
            "error_type": "ConnectError",
            "is_transient": True,
            "operation": "pet_classification",
        },
    )
    # mutmut_99: shipped L7207 — timeout branch
    await _expect(
        caplog,
        "pets",
        "timeout",
        logging.WARNING,
        {
            "detection_type": "animal",
            "error_category": "timeout",
            "error_type": "TimeoutException",
            "is_transient": True,
            "operation": "pet_classification",
        },
    )
    # mutmut_147: shipped L7247 — valueerror branch
    await _expect(
        caplog,
        "pets",
        "valueerror",
        logging.ERROR,
        {
            "detection_type": "animal",
            "error_category": "parse_error",
            "error_type": "ValueError",
            "is_transient": False,
            "operation": "pet_classification",
        },
    )
    # mutmut_173: shipped L7260 — catchall branch
    await _expect(
        caplog,
        "pets",
        "catchall",
        logging.ERROR,
        {
            "detection_type": "animal",
            "error_category": "unexpected",
            "is_transient": True,
            "operation": "pet_classification",
        },
    )


@pytest.mark.asyncio
async def test_pets_detection_type_uppercase_value_all_branches(caplog):
    """Shape group 12: "detection_type": "animal" -> "detection_type": "ANIMAL" (all twin mutants).

    Mutates the detection_type entry of the structured-log payload in every pets
    handler branch listed below; each branch's complete shipped payload is
    pinned, so the mutant fails whichever branch the harness drives.
    """
    # mutmut_43: shipped L7168 — keyerror branch
    await _expect(
        caplog,
        "pets",
        "keyerror",
        logging.WARNING,
        {
            "detection_type": "animal",
            "error_category": "parse_error",
            "operation": "pet_classification",
        },
    )
    # mutmut_58: shipped L7183 — unavail branch
    await _expect(
        caplog,
        "pets",
        "unavail",
        logging.WARNING,
        {
            "detection_type": "animal",
            "error_category": "service_unavailable",
            "error_type": "EnrichmentUnavailableError",
            "is_transient": True,
            "operation": "pet_classification",
        },
    )
    # mutmut_79: shipped L7195 — connect branch
    await _expect(
        caplog,
        "pets",
        "connect",
        logging.WARNING,
        {
            "detection_type": "animal",
            "error_category": "service_unavailable",
            "error_type": "ConnectError",
            "is_transient": True,
            "operation": "pet_classification",
        },
    )
    # mutmut_100: shipped L7207 — timeout branch
    await _expect(
        caplog,
        "pets",
        "timeout",
        logging.WARNING,
        {
            "detection_type": "animal",
            "error_category": "timeout",
            "error_type": "TimeoutException",
            "is_transient": True,
            "operation": "pet_classification",
        },
    )
    # mutmut_148: shipped L7247 — valueerror branch
    await _expect(
        caplog,
        "pets",
        "valueerror",
        logging.ERROR,
        {
            "detection_type": "animal",
            "error_category": "parse_error",
            "error_type": "ValueError",
            "is_transient": False,
            "operation": "pet_classification",
        },
    )
    # mutmut_174: shipped L7260 — catchall branch
    await _expect(
        caplog,
        "pets",
        "catchall",
        logging.ERROR,
        {
            "detection_type": "animal",
            "error_category": "unexpected",
            "is_transient": True,
            "operation": "pet_classification",
        },
    )


@pytest.mark.asyncio
async def test_pets_error_type_key_sentinel_all_branches(caplog):
    """Shape group 13: "error_type": type(e).__name__ -> "XXerror_typeXX": type(e).__name__ (all twin mutants).

    Mutates the error_type entry of the structured-log payload in every pets
    handler branch listed below; each branch's complete shipped payload is
    pinned, so the mutant fails whichever branch the harness drives.
    """
    # mutmut_63: shipped L7185 — unavail branch
    await _expect(
        caplog,
        "pets",
        "unavail",
        logging.WARNING,
        {
            "detection_type": "animal",
            "error_category": "service_unavailable",
            "error_type": "EnrichmentUnavailableError",
            "is_transient": True,
            "operation": "pet_classification",
        },
    )
    # mutmut_84: shipped L7197 — connect branch
    await _expect(
        caplog,
        "pets",
        "connect",
        logging.WARNING,
        {
            "detection_type": "animal",
            "error_category": "service_unavailable",
            "error_type": "ConnectError",
            "is_transient": True,
            "operation": "pet_classification",
        },
    )
    # mutmut_105: shipped L7209 — timeout branch
    await _expect(
        caplog,
        "pets",
        "timeout",
        logging.WARNING,
        {
            "detection_type": "animal",
            "error_category": "timeout",
            "error_type": "TimeoutException",
            "is_transient": True,
            "operation": "pet_classification",
        },
    )
    # mutmut_130: shipped L7223 — http5xx branch
    await _expect(
        caplog,
        "pets",
        "http503",
        logging.WARNING,
        {
            "detection_type": "animal",
            "error_category": "server_error",
            "error_type": "HTTPStatusError",
            "is_transient": True,
            "operation": "pet_classification",
            "status_code": 503,
        },
    )
    # mutmut_153: shipped L7249 — valueerror branch
    await _expect(
        caplog,
        "pets",
        "valueerror",
        logging.ERROR,
        {
            "detection_type": "animal",
            "error_category": "parse_error",
            "error_type": "ValueError",
            "is_transient": False,
            "operation": "pet_classification",
        },
    )


@pytest.mark.asyncio
async def test_pets_error_type_key_uppercase_all_branches(caplog):
    """Shape group 14: "error_type": type(e).__name__ -> "ERROR_TYPE": type(e).__name__ (all twin mutants).

    Mutates the error_type entry of the structured-log payload in every pets
    handler branch listed below; each branch's complete shipped payload is
    pinned, so the mutant fails whichever branch the harness drives.
    """
    # mutmut_64: shipped L7185 — unavail branch
    await _expect(
        caplog,
        "pets",
        "unavail",
        logging.WARNING,
        {
            "detection_type": "animal",
            "error_category": "service_unavailable",
            "error_type": "EnrichmentUnavailableError",
            "is_transient": True,
            "operation": "pet_classification",
        },
    )
    # mutmut_85: shipped L7197 — connect branch
    await _expect(
        caplog,
        "pets",
        "connect",
        logging.WARNING,
        {
            "detection_type": "animal",
            "error_category": "service_unavailable",
            "error_type": "ConnectError",
            "is_transient": True,
            "operation": "pet_classification",
        },
    )
    # mutmut_106: shipped L7209 — timeout branch
    await _expect(
        caplog,
        "pets",
        "timeout",
        logging.WARNING,
        {
            "detection_type": "animal",
            "error_category": "timeout",
            "error_type": "TimeoutException",
            "is_transient": True,
            "operation": "pet_classification",
        },
    )
    # mutmut_131: shipped L7223 — http5xx branch
    await _expect(
        caplog,
        "pets",
        "http503",
        logging.WARNING,
        {
            "detection_type": "animal",
            "error_category": "server_error",
            "error_type": "HTTPStatusError",
            "is_transient": True,
            "operation": "pet_classification",
            "status_code": 503,
        },
    )
    # mutmut_154: shipped L7249 — valueerror branch
    await _expect(
        caplog,
        "pets",
        "valueerror",
        logging.ERROR,
        {
            "detection_type": "animal",
            "error_category": "parse_error",
            "error_type": "ValueError",
            "is_transient": False,
            "operation": "pet_classification",
        },
    )


@pytest.mark.asyncio
async def test_pets_error_type_typenone_value_all_branches(caplog):
    """Shape group 15: "error_type": type(e).__name__ -> "error_type": type(None).__name__ (all twin mutants).

    Mutates the error_type entry of the structured-log payload in every pets
    handler branch listed below; each branch's complete shipped payload is
    pinned, so the mutant fails whichever branch the harness drives.
    """
    # mutmut_65: shipped L7185 — unavail branch
    await _expect(
        caplog,
        "pets",
        "unavail",
        logging.WARNING,
        {
            "detection_type": "animal",
            "error_category": "service_unavailable",
            "error_type": "EnrichmentUnavailableError",
            "is_transient": True,
            "operation": "pet_classification",
        },
    )
    # mutmut_86: shipped L7197 — connect branch
    await _expect(
        caplog,
        "pets",
        "connect",
        logging.WARNING,
        {
            "detection_type": "animal",
            "error_category": "service_unavailable",
            "error_type": "ConnectError",
            "is_transient": True,
            "operation": "pet_classification",
        },
    )
    # mutmut_107: shipped L7209 — timeout branch
    await _expect(
        caplog,
        "pets",
        "timeout",
        logging.WARNING,
        {
            "detection_type": "animal",
            "error_category": "timeout",
            "error_type": "TimeoutException",
            "is_transient": True,
            "operation": "pet_classification",
        },
    )
    # mutmut_132: shipped L7223 — http5xx branch
    await _expect(
        caplog,
        "pets",
        "http503",
        logging.WARNING,
        {
            "detection_type": "animal",
            "error_category": "server_error",
            "error_type": "HTTPStatusError",
            "is_transient": True,
            "operation": "pet_classification",
            "status_code": 503,
        },
    )
    # mutmut_155: shipped L7249 — valueerror branch
    await _expect(
        caplog,
        "pets",
        "valueerror",
        logging.ERROR,
        {
            "detection_type": "animal",
            "error_category": "parse_error",
            "error_type": "ValueError",
            "is_transient": False,
            "operation": "pet_classification",
        },
    )


@pytest.mark.asyncio
async def test_pets_is_transient_key_sentinel_all_branches(caplog):
    """Shape group 16: "is_transient": True -> "XXis_transientXX": True (all twin mutants).

    Mutates the is_transient entry of the structured-log payload in every pets
    handler branch listed below; each branch's complete shipped payload is
    pinned, so the mutant fails whichever branch the harness drives.
    """
    # mutmut_68: shipped L7187 — unavail branch
    await _expect(
        caplog,
        "pets",
        "unavail",
        logging.WARNING,
        {
            "detection_type": "animal",
            "error_category": "service_unavailable",
            "error_type": "EnrichmentUnavailableError",
            "is_transient": True,
            "operation": "pet_classification",
        },
    )
    # mutmut_89: shipped L7199 — connect branch
    await _expect(
        caplog,
        "pets",
        "connect",
        logging.WARNING,
        {
            "detection_type": "animal",
            "error_category": "service_unavailable",
            "error_type": "ConnectError",
            "is_transient": True,
            "operation": "pet_classification",
        },
    )
    # mutmut_110: shipped L7211 — timeout branch
    await _expect(
        caplog,
        "pets",
        "timeout",
        logging.WARNING,
        {
            "detection_type": "animal",
            "error_category": "timeout",
            "error_type": "TimeoutException",
            "is_transient": True,
            "operation": "pet_classification",
        },
    )
    # mutmut_137: shipped L7226 — http5xx branch
    await _expect(
        caplog,
        "pets",
        "http503",
        logging.WARNING,
        {
            "detection_type": "animal",
            "error_category": "server_error",
            "error_type": "HTTPStatusError",
            "is_transient": True,
            "operation": "pet_classification",
            "status_code": 503,
        },
    )
    # mutmut_181: shipped L7263 — catchall branch
    await _expect(
        caplog,
        "pets",
        "catchall",
        logging.ERROR,
        {
            "detection_type": "animal",
            "error_category": "unexpected",
            "is_transient": True,
            "operation": "pet_classification",
        },
    )


@pytest.mark.asyncio
async def test_pets_is_transient_key_uppercase_all_branches(caplog):
    """Shape group 17: "is_transient": True -> "IS_TRANSIENT": True (all twin mutants).

    Mutates the is_transient entry of the structured-log payload in every pets
    handler branch listed below; each branch's complete shipped payload is
    pinned, so the mutant fails whichever branch the harness drives.
    """
    # mutmut_69: shipped L7187 — unavail branch
    await _expect(
        caplog,
        "pets",
        "unavail",
        logging.WARNING,
        {
            "detection_type": "animal",
            "error_category": "service_unavailable",
            "error_type": "EnrichmentUnavailableError",
            "is_transient": True,
            "operation": "pet_classification",
        },
    )
    # mutmut_90: shipped L7199 — connect branch
    await _expect(
        caplog,
        "pets",
        "connect",
        logging.WARNING,
        {
            "detection_type": "animal",
            "error_category": "service_unavailable",
            "error_type": "ConnectError",
            "is_transient": True,
            "operation": "pet_classification",
        },
    )
    # mutmut_111: shipped L7211 — timeout branch
    await _expect(
        caplog,
        "pets",
        "timeout",
        logging.WARNING,
        {
            "detection_type": "animal",
            "error_category": "timeout",
            "error_type": "TimeoutException",
            "is_transient": True,
            "operation": "pet_classification",
        },
    )
    # mutmut_138: shipped L7226 — http5xx branch
    await _expect(
        caplog,
        "pets",
        "http503",
        logging.WARNING,
        {
            "detection_type": "animal",
            "error_category": "server_error",
            "error_type": "HTTPStatusError",
            "is_transient": True,
            "operation": "pet_classification",
            "status_code": 503,
        },
    )
    # mutmut_182: shipped L7263 — catchall branch
    await _expect(
        caplog,
        "pets",
        "catchall",
        logging.ERROR,
        {
            "detection_type": "animal",
            "error_category": "unexpected",
            "is_transient": True,
            "operation": "pet_classification",
        },
    )


@pytest.mark.asyncio
async def test_pets_is_transient_true_to_false_all_branches(caplog):
    """Shape group 18: "is_transient": True -> "is_transient": False (all twin mutants).

    Mutates the is_transient entry of the structured-log payload in every pets
    handler branch listed below; each branch's complete shipped payload is
    pinned, so the mutant fails whichever branch the harness drives.
    """
    # mutmut_70: shipped L7187 — unavail branch
    await _expect(
        caplog,
        "pets",
        "unavail",
        logging.WARNING,
        {
            "detection_type": "animal",
            "error_category": "service_unavailable",
            "error_type": "EnrichmentUnavailableError",
            "is_transient": True,
            "operation": "pet_classification",
        },
    )
    # mutmut_91: shipped L7199 — connect branch
    await _expect(
        caplog,
        "pets",
        "connect",
        logging.WARNING,
        {
            "detection_type": "animal",
            "error_category": "service_unavailable",
            "error_type": "ConnectError",
            "is_transient": True,
            "operation": "pet_classification",
        },
    )
    # mutmut_112: shipped L7211 — timeout branch
    await _expect(
        caplog,
        "pets",
        "timeout",
        logging.WARNING,
        {
            "detection_type": "animal",
            "error_category": "timeout",
            "error_type": "TimeoutException",
            "is_transient": True,
            "operation": "pet_classification",
        },
    )
    # mutmut_139: shipped L7226 — http5xx branch
    await _expect(
        caplog,
        "pets",
        "http503",
        logging.WARNING,
        {
            "detection_type": "animal",
            "error_category": "server_error",
            "error_type": "HTTPStatusError",
            "is_transient": True,
            "operation": "pet_classification",
            "status_code": 503,
        },
    )
    # mutmut_183: shipped L7263 — catchall branch
    await _expect(
        caplog,
        "pets",
        "catchall",
        logging.ERROR,
        {
            "detection_type": "animal",
            "error_category": "unexpected",
            "is_transient": True,
            "operation": "pet_classification",
        },
    )


@pytest.mark.asyncio
async def test_vehicles_operation_key_sentinel_all_branches(caplog):
    """Shape group 19: "operation": "vehicle_classification" -> "XXoperationXX": "vehicle_classification" (all twin mutants).

    Mutates the operation entry of the structured-log payload in every vehicles
    handler branch listed below; each branch's complete shipped payload is
    pinned, so the mutant fails whichever branch the harness drives.
    """
    # mutmut_42: shipped L6845 — keyerror branch
    await _expect(
        caplog,
        "vehicles",
        "keyerror",
        logging.WARNING,
        {
            "detection_type": "vehicle",
            "error_category": "parse_error",
            "operation": "vehicle_classification",
        },
    )
    # mutmut_57: shipped L6860 — unavail branch
    await _expect(
        caplog,
        "vehicles",
        "unavail",
        logging.WARNING,
        {
            "detection_type": "vehicle",
            "error_category": "service_unavailable",
            "error_type": "EnrichmentUnavailableError",
            "is_transient": True,
            "operation": "vehicle_classification",
        },
    )
    # mutmut_78: shipped L6872 — connect branch
    await _expect(
        caplog,
        "vehicles",
        "connect",
        logging.WARNING,
        {
            "detection_type": "vehicle",
            "error_category": "service_unavailable",
            "error_type": "ConnectError",
            "is_transient": True,
            "operation": "vehicle_classification",
        },
    )
    # mutmut_99: shipped L6884 — timeout branch
    await _expect(
        caplog,
        "vehicles",
        "timeout",
        logging.WARNING,
        {
            "detection_type": "vehicle",
            "error_category": "timeout",
            "error_type": "TimeoutException",
            "is_transient": True,
            "operation": "vehicle_classification",
        },
    )
    # mutmut_120: shipped L6924 — valueerror branch
    await _expect(
        caplog,
        "vehicles",
        "valueerror",
        logging.ERROR,
        {
            "detection_type": "vehicle",
            "error_category": "parse_error",
            "error_type": "ValueError",
            "is_transient": False,
            "operation": "vehicle_classification",
        },
    )
    # mutmut_146: shipped L6937 — catchall branch
    await _expect(
        caplog,
        "vehicles",
        "catchall",
        logging.ERROR,
        {
            "detection_type": "vehicle",
            "error_category": "unexpected",
            "is_transient": True,
            "operation": "vehicle_classification",
        },
    )


@pytest.mark.asyncio
async def test_vehicles_operation_key_uppercase_all_branches(caplog):
    """Shape group 20: "operation": "vehicle_classification" -> "OPERATION": "vehicle_classification" (all twin mutants).

    Mutates the operation entry of the structured-log payload in every vehicles
    handler branch listed below; each branch's complete shipped payload is
    pinned, so the mutant fails whichever branch the harness drives.
    """
    # mutmut_43: shipped L6845 — keyerror branch
    await _expect(
        caplog,
        "vehicles",
        "keyerror",
        logging.WARNING,
        {
            "detection_type": "vehicle",
            "error_category": "parse_error",
            "operation": "vehicle_classification",
        },
    )
    # mutmut_58: shipped L6860 — unavail branch
    await _expect(
        caplog,
        "vehicles",
        "unavail",
        logging.WARNING,
        {
            "detection_type": "vehicle",
            "error_category": "service_unavailable",
            "error_type": "EnrichmentUnavailableError",
            "is_transient": True,
            "operation": "vehicle_classification",
        },
    )
    # mutmut_79: shipped L6872 — connect branch
    await _expect(
        caplog,
        "vehicles",
        "connect",
        logging.WARNING,
        {
            "detection_type": "vehicle",
            "error_category": "service_unavailable",
            "error_type": "ConnectError",
            "is_transient": True,
            "operation": "vehicle_classification",
        },
    )
    # mutmut_100: shipped L6884 — timeout branch
    await _expect(
        caplog,
        "vehicles",
        "timeout",
        logging.WARNING,
        {
            "detection_type": "vehicle",
            "error_category": "timeout",
            "error_type": "TimeoutException",
            "is_transient": True,
            "operation": "vehicle_classification",
        },
    )
    # mutmut_121: shipped L6924 — valueerror branch
    await _expect(
        caplog,
        "vehicles",
        "valueerror",
        logging.ERROR,
        {
            "detection_type": "vehicle",
            "error_category": "parse_error",
            "error_type": "ValueError",
            "is_transient": False,
            "operation": "vehicle_classification",
        },
    )
    # mutmut_147: shipped L6937 — catchall branch
    await _expect(
        caplog,
        "vehicles",
        "catchall",
        logging.ERROR,
        {
            "detection_type": "vehicle",
            "error_category": "unexpected",
            "is_transient": True,
            "operation": "vehicle_classification",
        },
    )


@pytest.mark.asyncio
async def test_vehicles_operation_sentinel_value_all_branches(caplog):
    """Shape group 21: "operation": "vehicle_classification" -> "operation": "XXvehicle_classificationXX" (all twin mutants).

    Mutates the operation entry of the structured-log payload in every vehicles
    handler branch listed below; each branch's complete shipped payload is
    pinned, so the mutant fails whichever branch the harness drives.
    """
    # mutmut_44: shipped L6845 — keyerror branch
    await _expect(
        caplog,
        "vehicles",
        "keyerror",
        logging.WARNING,
        {
            "detection_type": "vehicle",
            "error_category": "parse_error",
            "operation": "vehicle_classification",
        },
    )
    # mutmut_59: shipped L6860 — unavail branch
    await _expect(
        caplog,
        "vehicles",
        "unavail",
        logging.WARNING,
        {
            "detection_type": "vehicle",
            "error_category": "service_unavailable",
            "error_type": "EnrichmentUnavailableError",
            "is_transient": True,
            "operation": "vehicle_classification",
        },
    )
    # mutmut_80: shipped L6872 — connect branch
    await _expect(
        caplog,
        "vehicles",
        "connect",
        logging.WARNING,
        {
            "detection_type": "vehicle",
            "error_category": "service_unavailable",
            "error_type": "ConnectError",
            "is_transient": True,
            "operation": "vehicle_classification",
        },
    )
    # mutmut_101: shipped L6884 — timeout branch
    await _expect(
        caplog,
        "vehicles",
        "timeout",
        logging.WARNING,
        {
            "detection_type": "vehicle",
            "error_category": "timeout",
            "error_type": "TimeoutException",
            "is_transient": True,
            "operation": "vehicle_classification",
        },
    )
    # mutmut_122: shipped L6924 — valueerror branch
    await _expect(
        caplog,
        "vehicles",
        "valueerror",
        logging.ERROR,
        {
            "detection_type": "vehicle",
            "error_category": "parse_error",
            "error_type": "ValueError",
            "is_transient": False,
            "operation": "vehicle_classification",
        },
    )
    # mutmut_148: shipped L6937 — catchall branch
    await _expect(
        caplog,
        "vehicles",
        "catchall",
        logging.ERROR,
        {
            "detection_type": "vehicle",
            "error_category": "unexpected",
            "is_transient": True,
            "operation": "vehicle_classification",
        },
    )


@pytest.mark.asyncio
async def test_vehicles_operation_uppercase_value_all_branches(caplog):
    """Shape group 22: "operation": "vehicle_classification" -> "operation": "VEHICLE_CLASSIFICATION" (all twin mutants).

    Mutates the operation entry of the structured-log payload in every vehicles
    handler branch listed below; each branch's complete shipped payload is
    pinned, so the mutant fails whichever branch the harness drives.
    """
    # mutmut_45: shipped L6845 — keyerror branch
    await _expect(
        caplog,
        "vehicles",
        "keyerror",
        logging.WARNING,
        {
            "detection_type": "vehicle",
            "error_category": "parse_error",
            "operation": "vehicle_classification",
        },
    )
    # mutmut_60: shipped L6860 — unavail branch
    await _expect(
        caplog,
        "vehicles",
        "unavail",
        logging.WARNING,
        {
            "detection_type": "vehicle",
            "error_category": "service_unavailable",
            "error_type": "EnrichmentUnavailableError",
            "is_transient": True,
            "operation": "vehicle_classification",
        },
    )
    # mutmut_81: shipped L6872 — connect branch
    await _expect(
        caplog,
        "vehicles",
        "connect",
        logging.WARNING,
        {
            "detection_type": "vehicle",
            "error_category": "service_unavailable",
            "error_type": "ConnectError",
            "is_transient": True,
            "operation": "vehicle_classification",
        },
    )
    # mutmut_102: shipped L6884 — timeout branch
    await _expect(
        caplog,
        "vehicles",
        "timeout",
        logging.WARNING,
        {
            "detection_type": "vehicle",
            "error_category": "timeout",
            "error_type": "TimeoutException",
            "is_transient": True,
            "operation": "vehicle_classification",
        },
    )
    # mutmut_123: shipped L6924 — valueerror branch
    await _expect(
        caplog,
        "vehicles",
        "valueerror",
        logging.ERROR,
        {
            "detection_type": "vehicle",
            "error_category": "parse_error",
            "error_type": "ValueError",
            "is_transient": False,
            "operation": "vehicle_classification",
        },
    )
    # mutmut_149: shipped L6937 — catchall branch
    await _expect(
        caplog,
        "vehicles",
        "catchall",
        logging.ERROR,
        {
            "detection_type": "vehicle",
            "error_category": "unexpected",
            "is_transient": True,
            "operation": "vehicle_classification",
        },
    )
