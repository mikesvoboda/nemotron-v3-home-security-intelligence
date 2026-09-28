"""S2 batch-28 lane L1 / group dc01 — module-level helpers + client plumbing.

Family probed (all pinned at the CURRENT source of
``backend/services/detector_client.py`` md5 ``294c938abe9e37cd0f979f9357982753``;
production never bends to these tests — every expected value below is transcribed
from the shipped line it defends):

``L120-133``   ``_is_free_threaded()`` — the GIL probe
               (``hasattr(sys, "_is_gil_enabled")`` / ``return not sys._is_gil_enabled()``).
``L150-161``   ``_get_preprocess_worker_count()`` — 8 free-threaded / 2 with the GIL.
``L203-223``   ``DetectorClient._get_semaphore()`` — create-or-recreate on limit
               change + the ``logger.debug`` line only the create path emits.
``L393-413``   ``DetectorClient._get_auth_headers()`` — SecretStr vs plain-str key.
``L298-309``   the two ``httpx.Timeout`` constructions (``_timeout`` / ``_health_timeout``).
``L321-328``   the two persistent ``httpx.AsyncClient`` constructions (timeout + Limits).

Discrimination notes for the timeout / pool groups, MEASURED on the shipped
httpx 0.28.1 rather than assumed:

``httpx.Timeout(connect=None, ...)`` is NOT the same as passing the real number —
``Timeout.__init__`` only substitutes for a leg that is ``None`` when a positional
``default`` was supplied, so a mutated leg reads back as ``{'connect': None, ...}``
which ``!=`` the shipped ``{'connect': 3.5, ...}``. That is what makes ``arg->None``
on a leg killable at all.
``httpx.AsyncClient`` does NOT preserve ``Timeout`` identity (it rebuilds one) and
its own client default is ``Timeout(5.0)``. So the health client is built against a
settings value of 7.0 — deliberately DIFFERENT from httpx's 5.0 default — which is
what separates "the ``timeout=`` kwarg is present" (7.0 legs) from "the kwarg was
dropped or set to ``None``" (5.0 legs / all-``None`` legs).
``Limits(max_connections=None)`` renders as ``9223372036854775807`` (int max) and
``Limits(max_keepalive_connections=None)`` renders as keepalive 10, so a ``->None``
mutation is observable; ``Limits(max_connections=10)`` alone yields ``(10, 10)``
while the shipped pair yields ``(10, 5)``. The two numbers read off
``client._transport._pool`` therefore separate all six value-level mutations and
both ``arg_drop`` variants.

Occurrence twins: the two ``httpx.AsyncClient(...)`` calls in ``__init__`` are
textually identical apart from the ``timeout`` argument, so BOTH clients get the
same four reads — whichever twin the bank's mutant sits on, a named test reddens.

Windows: ``caplog.set_level`` does NOT clear the buffer (the historical CI-flake
family), so the log-reading tests open their window with ``set_level`` + ``clear()``
and filter to this module's logger name.
"""

from __future__ import annotations

import asyncio
import logging
import sys
from collections.abc import Iterator
from typing import Any
from unittest.mock import MagicMock

import pytest

from backend.services import detector_client as M

LOG_NAME = M.logger.name
pytestmark = [pytest.mark.unit]

# --- shipped settings values used to build every client in this file ---------
YOLO26_URL = "http://yolo26-test:8000"
API_KEY = "sk-dc01-test-key"  # pragma: allowlist secret  # nosemgrep: hardcoded-password
READ_TIMEOUT = 42.0
CONNECT_TIMEOUT = 3.5
# Deliberately distinct from httpx's own 5.0 client default (see module docstring).
HEALTH_TIMEOUT = 7.0
# Read off the shipped Limits(max_connections=10, max_keepalive_connections=5).
MAX_CONNECTIONS = 10
MAX_KEEPALIVE = 5
# httpx's own AsyncClient default, measured: Timeout(5.0) on all four legs.
CLIENT_DEFAULT_LEGS = {"connect": 5.0, "read": 5.0, "write": 5.0, "pool": 5.0}
# httpx.Limits renders an unspecified slot as int max (measured).
UNLIMITED = 9223372036854775807

INFERENCE_LIMIT = 3
# The attribute L131/L132 probe on sys; named once so the probe tests stay honest.
GIL_ATTR = "_is_gil_enabled"

CORRELATION_HEADERS = {"X-Correlation-ID": "corr-dc01", "traceparent": "00-dc01-trace-01"}


# =============================================================================
# Fixtures / builders
# =============================================================================


@pytest.fixture(autouse=True)
def reset_semaphore_global() -> Iterator[None]:
    """Reset the class-level semaphore globals around every test.

    ``DetectorClient._request_semaphore`` / ``_semaphore_limit`` are CLASS state
    (L195-196) and outlive an instance, so the create path at L218 is only
    reachable from a known state. The pre-existing detector suite resets them the
    same way (test_detector_client.py:1350-1351).
    """
    M.DetectorClient._request_semaphore = None
    M.DetectorClient._semaphore_limit = 0
    yield
    M.DetectorClient._request_semaphore = None
    M.DetectorClient._semaphore_limit = 0


def make_settings(**overrides: Any) -> MagicMock:
    """The knobs ``__init__`` reads at L280-330, with two sentinels: the gateway
    flags are delivered as REAL values so a mutation that reaches for an
    attribute the shipped line does not read fails loudly instead of quietly
    returning a ``MagicMock``."""
    settings = MagicMock()
    settings.yolo26_url = YOLO26_URL
    settings.yolo26_api_key = API_KEY
    settings.yolo26_read_timeout = READ_TIMEOUT
    settings.ai_connect_timeout = CONNECT_TIMEOUT
    settings.ai_health_timeout = HEALTH_TIMEOUT
    settings.ai_max_concurrent_inferences = INFERENCE_LIMIT
    settings.__dict__["use_ai_gateway"] = False
    settings.__dict__["ai_gateway_url"] = None
    for name, value in overrides.items():
        if name == "api_key":
            settings.yolo26_api_key = value
        else:
            setattr(settings, name, value)
    return settings


class PlainKey:
    """Stand-in for the plain-``str`` branch of ``_get_auth_headers`` (L411-412):
    an object with NO ``get_secret_value`` attribute."""

    def __str__(self) -> str:
        return "sk-str-branch"


class SecretKey:
    """Stand-in for the pydantic ``SecretStr`` branch (L407-410)."""

    def __init__(self, value: str) -> None:
        self._value = value

    def get_secret_value(self) -> str:
        return self._value


def build_client(
    monkeypatch: pytest.MonkeyPatch,
    *,
    free_threaded: bool = False,
    limit: int = INFERENCE_LIMIT,
    api_key: Any = API_KEY,
    **setting_overrides: Any,
) -> Any:
    """A pristine-shaped ``DetectorClient``: the two module helpers are scripted,
    settings are mocked at the module attribute the shipped code resolves
    (``get_settings``), and the API key arrives through settings the way it does
    in production (``settings.yolo26_api_key``)."""
    monkeypatch.setattr(M, "_is_free_threaded", lambda: free_threaded)
    settings = make_settings(
        ai_max_concurrent_inferences=limit, api_key=api_key, **setting_overrides
    )
    monkeypatch.setattr(M, "get_settings", lambda: settings)
    return M.DetectorClient(max_retries=1)


def legs(client: Any, attribute: str) -> dict[str, float | None]:
    """The four timeout legs of one persistent client's OWN resolved config."""
    return getattr(client, attribute).timeout.as_dict()


def pool(client: Any, attribute: str) -> tuple[int, int]:
    """(max_connections, max_keepalive_connections) of one persistent pool."""
    transport_pool = getattr(client, attribute)._transport._pool
    return transport_pool._max_connections, transport_pool._max_keepalive_connections


def creates(caplog: pytest.LogCaptureFixture) -> list[logging.LogRecord]:
    """Create-path debug records from THIS module's logger inside the window."""
    return [
        r
        for r in caplog.records
        if r.name == LOG_NAME and r.levelno == logging.DEBUG and str(r.msg).startswith("Created ")
    ]


# =============================================================================
# L120-133 — _is_free_threaded()
# =============================================================================


def test_is_free_threaded_is_false_when_the_gil_probe_is_absent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """L131-133: no ``sys._is_gil_enabled`` -> the guard is False and we fall
    through to ``return False``. Kills ``hasattr(None, ...)`` (L131 m4-family),
    which answers True for ANY name and so skips the fall-through and then blows
    up calling a missing attribute."""
    monkeypatch.delattr(sys, GIL_ATTR, raising=False)
    assert M._is_free_threaded() is False


def test_is_free_threaded_inverts_an_enabled_gil(monkeypatch: pytest.MonkeyPatch) -> None:
    """L132: GIL enabled -> False. Kills the dropped ``not``."""
    monkeypatch.setattr(sys, GIL_ATTR, lambda: True, raising=False)
    assert M._is_free_threaded() is False


def test_is_free_threaded_inverts_a_disabled_gil(monkeypatch: pytest.MonkeyPatch) -> None:
    """L132: GIL disabled -> True. Kills the dropped ``not`` the other way, and
    the two attribute renames, which find no such attribute and return False."""
    monkeypatch.setattr(sys, GIL_ATTR, lambda: False, raising=False)
    assert M._is_free_threaded() is True


# =============================================================================
# L150-161 — _get_preprocess_worker_count()
# =============================================================================


def test_preprocess_worker_count_with_gil_is_two(monkeypatch: pytest.MonkeyPatch) -> None:
    """L161: ``return 2`` on GIL-bound Python."""
    monkeypatch.setattr(M, "_is_free_threaded", lambda: False)
    assert M._get_preprocess_worker_count() == 2


def test_preprocess_worker_count_free_threaded_is_eight(monkeypatch: pytest.MonkeyPatch) -> None:
    """L159: ``return 8`` on free-threaded Python."""
    monkeypatch.setattr(M, "_is_free_threaded", lambda: True)
    assert M._get_preprocess_worker_count() == 8


# =============================================================================
# L203-223 — _get_semaphore(): create / reuse / recreate + the debug line
# =============================================================================


def test_semaphore_is_created_at_the_settings_limit(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """From the reset state the first call builds ``asyncio.Semaphore(limit)`` at
    the settings value, records the limit on the class, and emits the create-path
    debug line verbatim. Kills ``arg->None`` on the ``logger.debug`` message."""
    caplog.set_level(logging.DEBUG, logger=LOG_NAME)
    caplog.clear()
    build_client(monkeypatch, limit=3)

    semaphore = M.DetectorClient._get_semaphore()

    assert isinstance(semaphore, asyncio.Semaphore)
    assert semaphore._value == 3
    assert M.DetectorClient._semaphore_limit == 3

    records = creates(caplog)
    assert len(records) == 1, f"expected exactly one create line, got {caplog.records!r}"
    record = records[0]
    assert record.msg == "Created DetectorClient semaphore with limit=3"
    assert record.levelno == logging.DEBUG
    assert tuple(record.args or ()) == ()
    assert record.exc_info is None


def test_semaphore_is_reused_while_the_limit_is_unchanged(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """L218: same limit -> the SAME object and NO second create line. Kills
    ``NotEqual->Equal`` (which recreates on every call) and ``Is->IsNot`` on
    ``_request_semaphore`` (which recreates whenever one already exists)."""
    build_client(monkeypatch, limit=3)
    first = M.DetectorClient._get_semaphore()

    caplog.set_level(logging.DEBUG, logger=LOG_NAME)
    caplog.clear()
    second = M.DetectorClient._get_semaphore()

    assert second is first
    assert M.DetectorClient._semaphore_limit == 3
    assert creates(caplog) == []


def test_semaphore_is_recreated_when_the_settings_limit_changes(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """L218-221: a changed settings limit rebuilds the semaphore at the new value.
    Kills ``Or->And``, which short-circuits the rebuild once a semaphore exists."""
    build_client(monkeypatch, limit=3)
    first = M.DetectorClient._get_semaphore()

    monkeypatch.setattr(M, "get_settings", lambda: make_settings(ai_max_concurrent_inferences=5))
    caplog.set_level(logging.DEBUG, logger=LOG_NAME)
    caplog.clear()
    second = M.DetectorClient._get_semaphore()

    assert second is not first
    assert second._value == 5
    assert M.DetectorClient._semaphore_limit == 5
    records = creates(caplog)
    assert len(records) == 1
    assert records[0].msg == "Created DetectorClient semaphore with limit=5"


# =============================================================================
# L393-413 — _get_auth_headers()
# =============================================================================


def auth_headers(monkeypatch: pytest.MonkeyPatch, client: Any) -> dict[str, str]:
    """Call the shipped method over a KNOWN correlation payload and assert the
    correlation half survived intact (NEM-1729) before the caller checks auth."""
    monkeypatch.setattr(M, "get_correlation_headers", lambda: dict(CORRELATION_HEADERS))
    headers = client._get_auth_headers()
    for name, value in CORRELATION_HEADERS.items():
        assert headers[name] == value, "correlation headers must pass through"
    return headers


def test_auth_headers_without_an_api_key_carry_only_correlation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """L406: a falsy key never reaches the X-API-Key line."""
    client = build_client(monkeypatch, api_key=None)

    headers = auth_headers(monkeypatch, client)

    assert "X-API-Key" not in headers
    assert headers == dict(CORRELATION_HEADERS)


def test_auth_headers_reads_a_secret_value_through_get_secret_value(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """L407-410: a key exposing ``get_secret_value()`` yields THAT value. Kills a
    renamed ``hasattr`` attribute, which would answer False here and log the
    object's ``str()`` (a repr) instead of the key."""
    client = build_client(monkeypatch, api_key=SecretKey("sk-secret-branch"))

    headers = auth_headers(monkeypatch, client)

    assert headers["X-API-Key"] == "sk-secret-branch"


def test_auth_headers_stringifies_a_key_without_a_secret_value(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """L411-412: with no ``get_secret_value`` attribute the shipped code falls to
    ``str(self._api_key)``. Kills ``hasattr(None, ...)``, which answers True for
    any object and would then call a method this key does not have."""
    client = build_client(monkeypatch, api_key=PlainKey())

    headers = auth_headers(monkeypatch, client)

    assert headers["X-API-Key"] == "sk-str-branch"


# =============================================================================
# L298-309 + L321-328 — the two timeouts and the two connection pools
#
# One test per value the mutations move; every reading is taken from the shipped
# client's OWN resolved config (httpx rebuilds the Timeout, so the attribute
# alone is not enough — see the module docstring).
# =============================================================================

DEFAULT_LEGS = {
    "connect": CONNECT_TIMEOUT,
    "read": READ_TIMEOUT,
    "write": READ_TIMEOUT,
    "pool": CONNECT_TIMEOUT,
}
HEALTH_LEGS = {
    "connect": HEALTH_TIMEOUT,
    "read": HEALTH_TIMEOUT,
    "write": HEALTH_TIMEOUT,
    "pool": HEALTH_TIMEOUT,
}


@pytest.mark.parametrize("leg", sorted(DEFAULT_LEGS))
def test_inference_timeout_leg_carries_the_settings_number(
    monkeypatch: pytest.MonkeyPatch, leg: str
) -> None:
    """L298-303: the leg the shipped call passes survives to the persistent
    inference client, so a leg set to ``None`` (or dropped) cannot hide."""
    client = build_client(monkeypatch)

    assert legs(client, "_http_client")[leg] == DEFAULT_LEGS[leg]


@pytest.mark.parametrize("leg", sorted(HEALTH_LEGS))
def test_health_timeout_leg_carries_the_health_settings_number(
    monkeypatch: pytest.MonkeyPatch, leg: str
) -> None:
    """L304-309: the ``_health_timeout`` attribute AND the health client's own
    config both carry the health number on every leg. A mutated leg reads back as
    ``None``, and a client that lost the ``timeout=`` kwarg reads back as httpx's
    5.0 default — never as 7.0."""
    client = build_client(monkeypatch)

    assert client._health_timeout.as_dict() == HEALTH_LEGS
    assert legs(client, "_health_http_client")[leg] == HEALTH_LEGS[leg]


def test_inference_timeout_carries_no_defaulted_leg(monkeypatch: pytest.MonkeyPatch) -> None:
    """Whole-dict pin of the inference timeout (both timeouts are built from
    settings values that no httpx default can imitate)."""
    client = build_client(monkeypatch)

    assert client._timeout.as_dict() == DEFAULT_LEGS
    assert legs(client, "_http_client") == DEFAULT_LEGS
    assert DEFAULT_LEGS != CLIENT_DEFAULT_LEGS


def test_health_timeout_carries_no_defaulted_leg(monkeypatch: pytest.MonkeyPatch) -> None:
    """Whole-dict pin of the health timeout across attribute + client."""
    client = build_client(monkeypatch)

    assert legs(client, "_health_http_client") == HEALTH_LEGS
    assert HEALTH_LEGS != CLIENT_DEFAULT_LEGS


@pytest.mark.parametrize("leg", sorted(HEALTH_LEGS))
def test_health_timeout_leg_is_not_the_httpx_client_default(
    monkeypatch: pytest.MonkeyPatch, leg: str
) -> None:
    """Per-leg negative twin for the health client's ``timeout=`` kwarg: both
    ``timeout=None`` and a dropped kwarg yield 5.0 for THAT leg, which the 7.0
    settings value contradicts."""
    client = build_client(monkeypatch)

    assert legs(client, "_health_http_client")[leg] != CLIENT_DEFAULT_LEGS[leg]


def test_inference_pool_carries_the_shipped_pair(monkeypatch: pytest.MonkeyPatch) -> None:
    """L321-326: ``Limits(max_connections=10, max_keepalive_connections=5)`` on
    the inference client (also pins the ``_http_client`` twin of the dropped
    ``limits=`` / dropped-``limits``-argument mutants)."""
    client = build_client(monkeypatch)

    assert pool(client, "_http_client") == (MAX_CONNECTIONS, MAX_KEEPALIVE)


def test_health_pool_carries_the_shipped_pair(monkeypatch: pytest.MonkeyPatch) -> None:
    """L327: the same pair on the health client."""
    client = build_client(monkeypatch)

    assert pool(client, "_health_http_client") == (MAX_CONNECTIONS, MAX_KEEPALIVE)


@pytest.mark.parametrize("slot", ["max_connections", "max_keepalive_connections"])
def test_both_pool_slots_are_finite(monkeypatch: pytest.MonkeyPatch, slot: str) -> None:
    """An absent or ``None`` slot renders as int max, so finiteness is what kills
    the ``->None`` and ``arg_drop`` variants on either client."""
    client = build_client(monkeypatch)

    for attribute in ("_http_client", "_health_http_client"):
        assert UNLIMITED not in pool(client, attribute), f"{slot} mutated on {attribute}"


@pytest.mark.parametrize(
    ("slot", "shipped", "neighbour"),
    [
        ("max_connections", MAX_CONNECTIONS, MAX_KEEPALIVE),
        ("max_keepalive_connections", MAX_KEEPALIVE, MAX_CONNECTIONS),
    ],
)
def test_both_pool_slots_hold_their_own_number(
    monkeypatch: pytest.MonkeyPatch, slot: str, shipped: int, neighbour: int
) -> None:
    """The two slots hold DIFFERENT shipped numbers, so neither a ``+1`` bump nor
    a slot swap can satisfy both readings at once."""
    client = build_client(monkeypatch)

    for attribute in ("_http_client", "_health_http_client"):
        max_connections, max_keepalive = pool(client, attribute)
        actual = max_connections if slot == "max_connections" else max_keepalive
        assert actual == shipped, f"{slot} on {attribute}: {actual} != {shipped}"
        assert actual != neighbour
