"""R60 (ruling 60): scoped API keys, end to end — the done-when suite.

Pre-R60, any hash match in ``API_KEYS`` opened every gated path, and setup.py
mirrors the monitoring key into that list — the monitoring credential was an
operator credential. An entry may now be an object ``{"key": ..., "scope":
"monitoring"}`` whose access is exactly the ``(method, path)`` set its scope
names in ``backend/core/constants.py``. This file pins the ruling's done-when
list:

1. the monitoring key reads exactly its endpoints — every pair in
   ``MONITORING_SCOPE_PATHS`` served, through a catchall gate app AND through
   the real route table with stub handlers;
2. it is refused (401 / ws 4001) on every OTHER gated path, exhaustively
   walked over the mounted app, and on every ``/api/admin/*`` route with
   ``ADMIN_ENABLED`` both true and false — the gate's answer is the same
   either way, so a scoped key never learns whether admin is on;
3. the set cannot drift from the monitoring configs:
   ``TestDerivationPin`` re-derives it from prometheus.yml,
   json-exporter-config.yml, docker-entrypoint.sh and the Grafana dashboards
   (edit a config, this goes red) and cross-checks each pair against the real
   route table.

Plus the amendments only tests can hold: absorption (10: a value listed both
plain and scoped is unscoped whatever the order), the cookie no-vote (7: a
scoped key casts no vote, so a valid cookie beside it still serves),
``require_api_key``'s required ``request`` and scope arm (6), entry-scoped
fail-closed parsing (4), and the legacy route-copy flag-off returns and
stayed-unscoped stance (2).

Harness reuse note: the gate-shaped fixtures are imported from
``backend/tests/unit/api/middleware/test_auth.py`` and the route walk from
``backend/tests/unit/api/test_expose_lan_routes.py`` — the same cross-module
idiom backend/tests/integration already uses with backend/tests/mock_utils.py
— so the tree holds exactly one copy of each.
"""

from __future__ import annotations

import json
import re
import warnings
from collections.abc import Iterator
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock
from urllib.parse import urlsplit

import pytest
import yaml
from fastapi import HTTPException
from pydantic_settings import SettingsError
from starlette.requests import Request
from starlette.testclient import TestClient
from starlette.websockets import WebSocket, WebSocketDisconnect

from backend.api.middleware.auth import (
    OPEN_PATHS,
    require_api_key,
    validate_websocket_api_key,
)
from backend.api.middleware.setup_guard import SetupGuardMiddleware
from backend.api.routes import dlq as dlq_routes
from backend.api.routes import system as system_routes
from backend.core.config import ScopedApiKey, get_settings
from backend.core.constants import MONITORING_SCOPE_PATHS
from backend.services.session_service import SESSION_COOKIE_NAME
from backend.tests.unit.api.middleware.test_auth import (
    _client,
    _login,
    _SessionStore,
    _use_store,
    _ws,
)
from backend.tests.unit.api.test_expose_lan_routes import (
    _BODY_METHODS,
    MOUNTED,
    REACHED,
    REFUSAL_BODY,
    REFUSED,
    WS_REFUSAL_CODE,
    _app_middleware_around_stub,
)

pytestmark = pytest.mark.unit

# Fake, low-entropy, per-file keys (the sibling suite's naming doctrine).
SCOPED_KEY = "scope-test-monitoring-key"  # pragma: allowlist secret
PLAIN_KEY = "scope-test-operator-key"  # pragma: allowlist secret
TYPO_KEY = "scope-test-typo-scope-key"  # pragma: allowlist secret
KEYED_OTHER = "scope-test-second-key"  # pragma: allowlist secret
# Not a credential: the flag-off route copies return None before looking at
# the value. A named constant rather than an inline literal because the
# inline form + its detect-secrets pragma exceeds the line length, ruff
# format then wraps the assert, and detect-secrets matches pragmas
# line-for-line — the wrap silently un-silences it.
ANY_PRESENTED_KEY = "anything"  # pragma: allowlist secret

_REPO_ROOT = Path(__file__).resolve().parents[4]  # workspace/ = repo root
_KEY_HEADER = "X-API-Key"


def _object_entry(key: str, scope: str = "monitoring") -> str:
    """One raw JSON fragment for the scoped object entry form."""
    return json.dumps({"key": key, "scope": scope})


def _arm_gate(monkeypatch: pytest.MonkeyPatch, *entries: str, **extra: str) -> None:
    """EXPOSE_LAN on, ``API_KEYS`` exactly these raw JSON entries, cache cleared.

    Entries are passed as raw fragments (not Python values) because a scoped
    object and a plain string sit in the SAME list — ``json.dumps`` of a mixed
    list would escape the object into a string entry, which is the pre-R60
    corruption this suite exists to be impossible about.
    """
    monkeypatch.setenv("EXPOSE_LAN", "true")
    monkeypatch.setenv("API_KEYS", "[" + ",".join(entries) + "]")
    for name, value in extra.items():
        monkeypatch.setenv(name, value)
    get_settings.cache_clear()


@pytest.fixture(autouse=True)
def clear_settings_cache() -> Iterator[None]:
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def scoped_only(monkeypatch: pytest.MonkeyPatch) -> None:
    """Gate armed with ONLY a scoped monitoring key — the R60 default install."""
    _arm_gate(monkeypatch, _object_entry(SCOPED_KEY))


@pytest.fixture
def plain_only(monkeypatch: pytest.MonkeyPatch) -> None:
    """Gate armed with ONLY a plain string key — today's behavior, unchanged."""
    _arm_gate(monkeypatch, json.dumps(PLAIN_KEY))


@pytest.fixture
def setup_complete(monkeypatch: pytest.MonkeyPatch) -> None:
    """The first admin exists — SetupGuardMiddleware must not answer 4xx.

    Same body as the sibling suite's fixture of the same name, deliberately
    DEFINED not imported: a fixture imported into a test module resolves by
    namespace, which ruff's F401 reads as an unused import and (with the
    parameter shadowing) F811 reads as a redefinition — the two rules fight
    over the import line. Four self-contained lines end the argument.
    """

    async def _complete(_self: SetupGuardMiddleware) -> bool:
        return True

    monkeypatch.setattr(SetupGuardMiddleware, "_check_setup_complete", _complete)


@pytest.fixture
def stub_app_client() -> TestClient:
    """The real app's middleware stack (gate included) around a stub endpoint.

    The gate answers before routing, so the whole mounted route table is
    reachable without any handler touching a database — exactly the harness
    ``test_expose_lan_routes.py`` builds, imported rather than copied.
    """
    return TestClient(_app_middleware_around_stub())


def _key_headers(key: str) -> dict[str, str]:
    return {_KEY_HEADER: key}


def _send_as(client: TestClient, method: str, path: str, key: str) -> str:
    """One credentialled call through the real stack, named like the sibling's.

    ``refused`` means exactly the gate's answer (HTTP 401 + its body, or ws
    closed 4001); ``reached`` is the stub endpoint's; anything else is
    described so a failure says which door answered.
    """
    if method == "WS":
        try:
            with client.websocket_connect(path, subprotocols=[f"api-key.{key}"]) as websocket:
                return websocket.receive_text()
        except WebSocketDisconnect as exc:
            return REFUSED if exc.code == WS_REFUSAL_CODE else f"closed {exc.code}"
    response = client.request(
        method,
        path,
        json={} if method in _BODY_METHODS else None,
        headers=_key_headers(key),
    )
    bodiless = method == "HEAD"
    body = response.json() if response.text.startswith("{") else response.text
    if response.status_code == 401 and (bodiless or body == REFUSAL_BODY):
        return REFUSED
    if response.status_code == 200 and (bodiless or body == REACHED):
        return REACHED
    return f"{response.status_code} {response.text[:80]}"


# =============================================================================
# Done-when 1: the scoped key serves exactly its endpoints
# =============================================================================


class TestScopedKeyServesItsScope:
    @pytest.mark.parametrize(("method", "path"), sorted(MONITORING_SCOPE_PATHS))
    def test_every_scope_pair_served(self, scoped_only: None, method: str, path: str) -> None:
        response = _client().request(
            method,
            path,
            json={} if method in _BODY_METHODS else None,
            headers=_key_headers(SCOPED_KEY),
        )
        assert response.status_code == 200
        assert response.text == "reached"

    @pytest.mark.parametrize(
        "path",
        [
            # The shipped Grafana panel queries verbatim (query strings never
            # take part in scope naming — ASGI splits them from the path).
            "/api/events?risk_level=high&risk_level=critical&limit=20",
            "/api/ai-audit/stats?days=7",
            "/api/events/stats?window=24h",
        ],
    )
    def test_query_strings_do_not_escape_the_scope(self, scoped_only: None, path: str) -> None:
        response = _client().get(path, headers=_key_headers(SCOPED_KEY))
        assert response.status_code == 200
        assert response.text == "reached"

    def test_wrong_method_is_refused(self, scoped_only: None) -> None:
        """Scopes are (method, path) PAIRS — the GET grant is not a path grant."""
        response = _client().post("/api/events", json={}, headers=_key_headers(SCOPED_KEY))
        assert response.status_code == 401
        assert response.json() == REFUSAL_BODY

    def test_wrong_method_serves_for_a_plain_key(self, plain_only: None) -> None:
        """Control: the refusal above is the scope, not the catchall's verbs."""
        response = _client().post("/api/events", json={}, headers=_key_headers(PLAIN_KEY))
        assert response.status_code == 200


# =============================================================================
# Done-when 2: refused everywhere else — exhaustively, over the real table
# =============================================================================

_ADMIN_PAIRS = sorted({(m, p) for m, p in MOUNTED if p.startswith("/api/admin")})


class TestExhaustiveGateWalk:
    def test_serves_scope_refuses_everything_else(
        self,
        scoped_only: None,
        setup_complete: None,
        stub_app_client: TestClient,
    ) -> None:
        """Every mounted (method, path): served iff in scope or an open path.

        One loop, not a parametrized test per route, because the interesting
        failure is a LIST (which route leaked), and the route set grows on its
        own via ``MOUNTED`` — a route added later is covered without editing
        this file.
        """
        offenders: list[str] = []
        for method, path in MOUNTED:
            want = (
                REACHED
                if (method, path) in MONITORING_SCOPE_PATHS or path in OPEN_PATHS
                else REFUSED
            )
            got = _send_as(stub_app_client, method, path, SCOPED_KEY)
            if got != want:
                offenders.append(f"{method} {path}: got {got!r}, want {want!r}")
        assert offenders == []

    @pytest.mark.parametrize("path", ["/api/events/123", "/api/system/health/live"])
    def test_near_miss_paths_refuse(self, scoped_only: None, path: str) -> None:
        """/api/events/123 is events.py's by-id route, NOT the scoped list grant.

        Exact pairs, no prefixes — a prefix on /api/events would have admitted
        it (constants.py records why that is the ruling's whole point).
        """
        response = _client().get(path, headers=_key_headers(SCOPED_KEY))
        assert response.status_code == 401
        assert response.json() == REFUSAL_BODY


class TestAdminLeg:
    """``/api/admin/*`` for the monitoring key, ADMIN_ENABLED both ways.

    Ruling 60's done-when names ADMIN_ENABLED=true explicitly: with the flag
    ON the admin router's own gate (require_admin_access) would 403 — the
    monitoring key never reaches it, because AuthMiddleware refuses first,
    and the answer must be identical with the flag OFF (where reached routes
    would 503). Either way: 401. A scoped key must not be able to tell admin
    on from admin off.
    """

    @pytest.mark.parametrize("admin_enabled", ["true", "false"])
    def test_every_admin_route_refuses_the_monitoring_key(
        self,
        scoped_only: None,
        setup_complete: None,
        stub_app_client: TestClient,
        monkeypatch: pytest.MonkeyPatch,
        admin_enabled: str,
    ) -> None:
        monkeypatch.setenv("ADMIN_ENABLED", admin_enabled)  # outranks any .env
        get_settings.cache_clear()
        offenders = [
            f"{method} {path}: {_send_as(stub_app_client, method, path, SCOPED_KEY)!r}"
            for method, path in _ADMIN_PAIRS
            if _send_as(stub_app_client, method, path, SCOPED_KEY) != REFUSED
        ]
        assert offenders == []

    def test_plain_key_still_reaches_admin(
        self,
        plain_only: None,
        setup_complete: None,
        stub_app_client: TestClient,
    ) -> None:
        """The refusal above is scope-derived, not admin-path-specific."""
        assert _send_as(stub_app_client, "GET", "/api/admin/users", PLAIN_KEY) == REACHED


class TestAbsorption:
    """Amendment 10: a value listed BOTH plain and scoped is unscoped, order-free.

    Reachable by hand-edit (setup.py's merge dedupes cross-form precisely so
    it cannot happen on its own output); the gate takes the PLAIN entry either
    way. An earlier first-match-wins draft made the rule depend on list order,
    which would have made merge_api_keys' docstring lie half the time.
    """

    @pytest.mark.parametrize("object_first", [True, False], ids=["object-first", "plain-first"])
    def test_plain_entry_absorbs_scoped_twin(
        self, monkeypatch: pytest.MonkeyPatch, object_first: bool
    ) -> None:
        entries = [_object_entry(SCOPED_KEY), json.dumps(SCOPED_KEY)]
        if not object_first:
            entries.reverse()
        _arm_gate(monkeypatch, *entries)
        # Unscoped means EVERYWHERE: the scoped pair serves ...
        assert _client().get("/api/metrics", headers=_key_headers(SCOPED_KEY)).status_code == 200
        # ... and so does a path the scoped twin alone could never serve.
        assert _client().get("/api/events/123", headers=_key_headers(SCOPED_KEY)).status_code == 200

    def test_scoped_entry_alone_refuses_the_non_scope_path(self, scoped_only: None) -> None:
        """Control: without the plain twin the SAME key is refused there."""
        assert _client().get("/api/metrics", headers=_key_headers(SCOPED_KEY)).status_code == 200
        assert _client().get("/api/events/123", headers=_key_headers(SCOPED_KEY)).status_code == 401


class TestNoVoteCookie:
    """Amendment 7 (owner DECIDE, no vote): a scoped refusal is not a refusal.

    ``_api_key_principal`` returns None when scope refuses, so the cookie leg
    still runs — a valid login cookie beside a scoped key serves. One
    auth_required event from the gate on the refusal, no new status code.
    """

    @pytest.mark.asyncio
    async def test_valid_cookie_beside_scoped_key_serves(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        store = _SessionStore()
        _use_store(monkeypatch, store)
        cookie = await _login(store)
        _arm_gate(monkeypatch, _object_entry(SCOPED_KEY))
        client = _client()
        headers = {"Cookie": f"{SESSION_COOKIE_NAME}={cookie}"}
        # Key alone: refused (this is the R60 behavior, not the cookie's).
        assert client.get("/api/events/123", headers=_key_headers(SCOPED_KEY)).status_code == 401
        # Key + valid cookie: served — BY THE COOKIE. The key cast no vote.
        both = dict(headers, **_key_headers(SCOPED_KEY))
        response = client.get("/api/events/123", headers=both)
        assert response.status_code == 200
        assert response.text == "reached"
        # Key + garbage cookie: refused again (an invalid cookie casts no vote
        # either — R55 round 2's hierarchy, unchanged by R60).
        bogus = dict(headers, **{"Cookie": f"{SESSION_COOKIE_NAME}=stale-session"})
        assert client.get("/api/events/123", headers=bogus).status_code == 401

    @pytest.mark.asyncio
    async def test_cookie_serves_in_scope_too(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A scoped path is not scoped TO COOKIES: a login is unscoped."""
        store = _SessionStore()
        _use_store(monkeypatch, store)
        cookie = await _login(store)
        _arm_gate(monkeypatch, _object_entry(SCOPED_KEY))
        response = _client().get(
            "/api/metrics", headers={"Cookie": f"{SESSION_COOKIE_NAME}={cookie}"}
        )
        assert response.status_code == 200


class TestWebSockets:
    """No ``/ws/*`` path is in any scope — a monitoring key cannot stream."""

    def test_gate_closes_ws_for_scoped_key(self, scoped_only: None) -> None:
        client = _client()
        assert _ws(client, f"/ws/events?api_key={SCOPED_KEY}") == 4001
        assert _ws(client, "/ws/events", subprotocols=[f"api-key.{SCOPED_KEY}"]) == 4001

    def test_plain_key_streams_unchanged(self, plain_only: None) -> None:
        client = _client()
        assert _ws(client, f"/ws/events?api_key={PLAIN_KEY}") == "reached"
        assert _ws(client, "/ws/events", subprotocols=[f"api-key.{PLAIN_KEY}"]) == "reached"


# =============================================================================
# Amendment 6: require_api_key (the inbound-webhook dependency)
# =============================================================================


def _request(method: str = "GET", path: str = "/api/events") -> Request:
    return Request(
        {"type": "http", "method": method, "path": path, "headers": [], "query_string": b""}
    )


class TestRequireApiKey:
    def test_scoped_key_in_scope_returns_key(self, scoped_only: None) -> None:
        assert require_api_key(_request("GET", "/api/events"), SCOPED_KEY) == SCOPED_KEY

    def test_scoped_key_outside_scope_refuses_401(self, scoped_only: None) -> None:
        """Never 501/200 — and the detail is byte-identical to an unknown key,
        so a 401 can never reveal that the key was real and merely unentitled."""
        with pytest.raises(HTTPException) as excinfo:
            require_api_key(_request("GET", "/api/webhooks/anything"), SCOPED_KEY)
        assert excinfo.value.status_code == 401
        assert excinfo.value.detail == "Invalid API key"

    def test_scoped_key_wrong_method_refuses(self, scoped_only: None) -> None:
        with pytest.raises(HTTPException) as excinfo:
            require_api_key(_request("POST", "/api/events"), SCOPED_KEY)
        assert excinfo.value.status_code == 401

    def test_plain_key_serves_anywhere(self, plain_only: None) -> None:
        assert require_api_key(_request("POST", "/api/anything/at/all"), PLAIN_KEY) == PLAIN_KEY

    def test_unknown_key_refuses(self, scoped_only: None) -> None:
        with pytest.raises(HTTPException) as excinfo:
            require_api_key(_request("GET", "/api/events"), "not-a-configured-key")
        assert excinfo.value.status_code == 401
        assert excinfo.value.detail == "Invalid API key"

    def test_missing_header_refuses(self, scoped_only: None) -> None:
        with pytest.raises(HTTPException) as excinfo:
            require_api_key(_request("GET", "/api/events"), None)
        assert excinfo.value.status_code == 401
        assert excinfo.value.detail == "Missing X-API-Key header"


# =============================================================================
# Amendment 4: entry-scoped fail-closed parse policy (the Settings leg)
# =============================================================================


class TestParsePolicy:
    def test_monitoring_object_resolves_to_the_registry_set(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _arm_gate(monkeypatch, _object_entry(SCOPED_KEY), json.dumps(PLAIN_KEY))
        entries = get_settings().api_keys
        scoped = [e for e in entries if getattr(e, "scoped_paths", None) is not None]
        assert [e.get_secret_value() for e in scoped] == [SCOPED_KEY]
        assert scoped[0].scoped_paths == MONITORING_SCOPE_PATHS
        # The plain entry passed through unscoped (no frozenset attribute).
        plain = [e for e in entries if getattr(e, "scoped_paths", None) is None]
        assert [e.get_secret_value() for e in plain] == [PLAIN_KEY]

    def test_unrecognized_scope_warns_index_only_and_fails_closed(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _arm_gate(monkeypatch, _object_entry(TYPO_KEY, "montitoring"))
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            get_settings.cache_clear()
            entries = get_settings().api_keys
        assert entries[0].scoped_paths == frozenset()  # refuse, never unscope
        messages = [str(w.message) for w in caught if "API_KEYS entry" in str(w.message)]
        assert any("entry 0" in message for message in messages)
        # SecretStr doctrine: warnings name indices ONLY, never key material
        # (pydantic's own error echo already leaks input values; ours must not).
        assert all(TYPO_KEY not in message for message in messages)
        # And the empty set means 401 on ITS OWN nominal scope's endpoint:
        response = _client().get("/api/metrics", headers=_key_headers(TYPO_KEY))
        assert response.status_code == 401

    def test_keyless_object_is_dropped_with_warning(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _arm_gate(monkeypatch, '{"bad": 1}', json.dumps(KEYED_OTHER))
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            get_settings.cache_clear()
            entries = get_settings().api_keys
        assert [e.get_secret_value() for e in entries] == [KEYED_OTHER]
        assert any(
            "entry 0" in str(w.message) and "without a usable" in str(w.message) for w in caught
        )
        # The surviving plain entry still authenticates:
        assert (
            _client().get("/api/events/123", headers=_key_headers(KEYED_OTHER)).status_code == 200
        )

    def test_plain_list_produces_no_warnings(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Pre-R60 deployments see ZERO change: no parse pass at all."""
        monkeypatch.setenv("API_KEYS", json.dumps([PLAIN_KEY, SCOPED_KEY]))
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            get_settings.cache_clear()
            entries = get_settings().api_keys
        assert not [w for w in caught if "API_KEYS" in str(w.message)]
        assert [e.get_secret_value() for e in entries] == [PLAIN_KEY, SCOPED_KEY]

    def test_corrupt_whole_value_raises_before_validators(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """pydantic-settings JSON-decodes first and raises SettingsError — the
        documented whole-value arm (a corrupt value is NOT entry-scoped; there
        is no "rest of the list still works" for a value that never parsed).
        """
        monkeypatch.setenv("API_KEYS", '[{"key": broken')
        get_settings.cache_clear()
        with pytest.raises(SettingsError):
            get_settings()


# =============================================================================
# Amendment 2: the two legacy verify_api_key copies (flag-off returns, unscoped)
# =============================================================================


def _fake_ws(key: str) -> MagicMock:
    ws = MagicMock(spec=WebSocket)
    ws.url = MagicMock()
    ws.url.path = "/ws/events"
    ws.query_params = {"api_key": key}
    ws.headers = {}
    ws.client = None
    return ws


class TestValidateWebsocketApiKey:
    @pytest.mark.asyncio
    async def test_scoped_key_fails_a_ws_handshake_when_enabled(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("API_KEY_ENABLED", "true")
        _arm_gate(monkeypatch, _object_entry(SCOPED_KEY))
        assert await validate_websocket_api_key(_fake_ws(SCOPED_KEY)) is False

    @pytest.mark.asyncio
    async def test_plain_key_passes_a_ws_handshake_when_enabled(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("API_KEY_ENABLED", "true")
        _arm_gate(monkeypatch, json.dumps(PLAIN_KEY))
        assert await validate_websocket_api_key(_fake_ws(PLAIN_KEY)) is True

    @pytest.mark.asyncio
    async def test_flag_off_return_is_untouched(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """R60's arm sits AFTER the flag-off return by design — off is off.

        ``setenv false`` not ``delenv``: backend/tests/unit/conftest.py arms
        API_KEY_ENABLED=true session-wide, so "unset" is never off in this
        tier — a delenv here would pin the ON behavior while reading as off.
        """
        monkeypatch.setenv("API_KEY_ENABLED", "false")
        _arm_gate(monkeypatch, _object_entry(SCOPED_KEY))
        assert await validate_websocket_api_key(_fake_ws(SCOPED_KEY)) is True


class TestLegacyRouteCopies:
    """routes/system.py + routes/dlq.py: TIMING FIX ONLY (amendment 2).

    These copies stay unscoped by design — the gate is the outermost door —
    and their flag-off early returns are untouched. Pinning THAT is what
    stops a later "consistency" sweep from scoping them into a boot-order
    dependency on constants.py, or from deleting a return three tests depend
    on. (A mutation pin must patch THIS module's get_settings binding — the
    from-import in the routes copied it at import time.)
    """

    @pytest.mark.asyncio
    async def test_flag_off_short_circuits_both_copies(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        off = SimpleNamespace(api_key_enabled=False, api_keys=[])
        monkeypatch.setattr("backend.api.routes.system.get_settings", lambda: off)
        monkeypatch.setattr("backend.api.routes.dlq.get_settings", lambda: off)
        # Flag off: both copies return None before looking at the key at all
        # (amendment 2 — their early returns are untouched by R60).
        assert await system_routes.verify_api_key(x_api_key=ANY_PRESENTED_KEY) is None
        assert await dlq_routes.verify_api_key(x_api_key=ANY_PRESENTED_KEY) is None

    @pytest.mark.asyncio
    async def test_flag_on_valid_and_invalid(self, monkeypatch: pytest.MonkeyPatch) -> None:
        on = SimpleNamespace(api_key_enabled=True, api_keys=[PLAIN_KEY])
        monkeypatch.setattr("backend.api.routes.system.get_settings", lambda: on)
        monkeypatch.setattr("backend.api.routes.dlq.get_settings", lambda: on)
        assert await system_routes.verify_api_key(x_api_key=PLAIN_KEY) is None
        with pytest.raises(HTTPException) as excinfo:
            await dlq_routes.verify_api_key(x_api_key="bogus-key")  # pragma: allowlist secret
        assert excinfo.value.status_code == 401

    @pytest.mark.asyncio
    async def test_copies_stay_unscoped_by_amendment(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A ScopedApiKey with an EMPTY scope still passes these copies.

        That is amendment 2, stated as a test: scope lives at the gate, not
        in the route-local dependencies. (The gate refuses the same key on
        the same route whenever EXPOSE_LAN=true — TestExhaustiveGateWalk —
        so this is not an open door; it is the flag-independent layering.)
        """
        on = SimpleNamespace(api_key_enabled=True, api_keys=[ScopedApiKey(SCOPED_KEY, frozenset())])
        monkeypatch.setattr("backend.api.routes.system.get_settings", lambda: on)
        assert await system_routes.verify_api_key(x_api_key=SCOPED_KEY) is None


# =============================================================================
# Amendment 9: the derivation pin — the registry cannot drift from the files
# =============================================================================

# The credential these configs attach the key to (case-folded; nginx spells
# it proxy_set_header X-API-Key, Prometheus a header name, json-exporter a
# module header, Grafana a httpHeaderName1 VALUE).
_KEY_NAME = "x-api-key"


def _has_key_header(mapping: dict | None) -> bool:
    return any(str(name).lower() == _KEY_NAME for name in (mapping or {}))


def _panel_panels(doc: dict) -> list[dict]:
    """Every panel incl. nested rows/collapsed rows."""
    out: list[dict] = []
    for panel in doc.get("panels", []):
        out.append(panel)
        out.extend(_panel_panels(panel))
    return out


def _derived_monitoring_calls() -> set[tuple[str, str]]:
    """Re-derive the monitoring call set from what monitoring/ actually calls
    WITH THE KEY — the same reading constants.py cites, but measured:

    - Prometheus's own scrape carries ``http_headers: {X-API-Key: …}`` → its
      ``metrics_path`` (GET);
    - ``/probe`` jobs whose json-exporter MODULE carries the header key the
      backend target URL's path (GET). The module-header condition is what
      keeps the hsi-health job out honestly: /api/system/health is OPEN_PATHS
      and its module deliberately ships no header — the natural control arm;
    - the frontend machine listener's path-exact ``location =`` blocks that
      ``proxy_set_header X-API-Key`` (POST — Alertmanager's sink; Alertmanager
      itself cannot attach a key in any version, O1.11 probed);
    - Grafana panels whose datasource provisions the key (``httpHeaderName1``)
      — the marcusolsson-json-datasource ``urlPath``, query stripped.

    Then: exclude OPEN_PATHS (the gate answers those without a credential; a
    key-carrying leg to one would be misconfiguration, not scope).
    """
    derived: set[tuple[str, str]] = set()
    prom = yaml.safe_load((_REPO_ROOT / "monitoring/prometheus.yml").read_text())
    jobs = prom.get("scrape_configs", [])

    for job in jobs:
        if _has_key_header(job.get("http_headers")):
            derived.add(("GET", job.get("metrics_path", "/metrics")))

    exporter = yaml.safe_load((_REPO_ROOT / "monitoring/json-exporter-config.yml").read_text())
    header_modules = {
        name
        for name, module in (exporter.get("modules") or {}).items()
        if _has_key_header(module.get("headers"))
    }
    for job in jobs:
        if job.get("metrics_path") != "/probe":
            continue
        if not set((job.get("params") or {}).get("module") or []) & header_modules:
            continue
        for static in job.get("static_configs") or []:
            for target in static.get("targets") or []:
                derived.add(("GET", urlsplit(str(target)).path))

    nginx = (_REPO_ROOT / "frontend/docker-entrypoint.sh").read_text()
    for block in re.finditer(r"location\s*=\s*(\S+)\s*\{(.*?)\n\s*\}", nginx, re.S):
        if re.search(r"proxy_set_header\s+X-API-Key\b", block.group(2)):
            derived.add(("POST", block.group(1)))

    key_uids = set()
    for ds in yaml.safe_load(
        (_REPO_ROOT / "monitoring/grafana/provisioning/datasources/prometheus.yml").read_text()
    )["datasources"]:
        json_data = ds.get("jsonData") or {}
        if any(
            str(value).lower() == _KEY_NAME
            for name, value in json_data.items()
            if str(name).lower().startswith("httpheadername")
        ):
            key_uids.add(ds.get("uid"))
    for dashboard in sorted((_REPO_ROOT / "monitoring/grafana/dashboards").glob("*.json")):
        doc = json.loads(dashboard.read_text())
        for panel in _panel_panels(doc):
            for target in [panel, *(panel.get("targets") or [])]:
                if (target.get("datasource") or {}).get("uid") not in key_uids:
                    continue
                if "urlPath" not in target:
                    continue
                derived.add(
                    (str(target.get("method", "GET")).upper(), str(target["urlPath"]).split("?")[0])
                )

    return {pair for pair in derived if pair[1] not in OPEN_PATHS}


class TestDerivationPin:
    def test_registry_equals_the_monitoring_configs(self) -> None:
        """Edit a monitoring config and this fails with the exact delta.

        The constants.py block says the set is cited from grep at this commit;
        this is that citation, executable. A drift between the registry and
        what the stack actually calls is how a scope silently under-grants
        (monitoring breaks at 401, the boring direction) or over-grants
        (a path nobody calls stays in scope forever, the quietly bad one).
        """
        derived = _derived_monitoring_calls()
        extra = sorted(derived - MONITORING_SCOPE_PATHS)
        missing = sorted(MONITORING_SCOPE_PATHS - derived)
        assert (derived == MONITORING_SCOPE_PATHS, (extra, missing)) == (True, ([], []))

    def test_every_registry_pair_is_a_real_route(self) -> None:
        """A pair nobody routes is a dead grant pretending to be alive."""
        table = {(method, path) for method, path in MOUNTED if method != "WS"}
        missing = sorted(MONITORING_SCOPE_PATHS - table)
        assert missing == []
