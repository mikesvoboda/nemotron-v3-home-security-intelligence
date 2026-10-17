"""[r95] S4 — the `monitoring` scope's `/api/events` grant is a FIELD ceiling.

The row's clause (packages/backend.md, verbatim): the scope "admits
`GET /api/events`, which serves sparse fieldsets including `reasoning`, and
`include_deleted` … If a consumer needs `/api/events`, admit only the fields it
reads: no `reasoning`, no `include_deleted`."

Why this is a response ceiling and not a path-set edit (measured, recorded in
#7135's comment 6178568441): every one of the 11 scoped paths has a keyed
consumer, so no path is removable — and `_key_admits` is `call in scope` with
`call = (method, path)` (middleware/auth.py:217-224), with
`test_query_strings_do_not_escape_the_scope` pinning that query strings never
take part in scope naming. So `("GET", "/api/events")` admits
`?include_deleted=true` exactly as readily as the shipped panel's own query.
The narrowing has to sit where the response is built.

Two clamps, because the clause names two different leaks:

- `reasoning` is SERVED by default: `routes/events.py:407` `undefer`s the column
  and `:530` writes the value into every row. The ceiling is on the VALUE, not
  on key presence — measured here: a dict that OMITS `reasoning` still goes out
  on the wire as `"reasoning": null`, because the row dicts are re-validated
  against `EventResponse` and pydantic re-adds the schema default. That is the
  same absence-is-not-a-witness trap this file's `notes` sibling documents at
  `routes/events.py:532` (F-057). So each leg below seeds real text and asserts
  the value is null, which is the only assertion that distinguishes the states.
- `include_deleted` widens the ROWS (`events.py:420-421` is where the
  `deleted_at IS NULL` filter is applied, so skipping it widens the set). For a
  scoped caller it is not an admitted capability, so it is forced off: the
  response stays a 200 and the row set equals the default one. Deliberately not
  a 400 — "admit only the fields it reads" narrows the grant; it does not add a
  new failure mode to a path Grafana calls on every dashboard refresh.

Both clamps key on the PRESENTED KEY's scope re-derived at request time, not on
middleware-set state, because `AuthMiddleware.__call__` returns early when
`expose_lan` is off (`middleware/auth.py:661`) — in the LAN-trusted posture the
gate never runs, so state set there would leave the ceiling unarmed exactly
where S1's configuration lives.

The unscoped arms are the point as much as the scoped ones: an operator key and
a session-cookie caller keep byte-identical payloads, so this is a narrowing of
one scope, not a change to the endpoint.
"""

from __future__ import annotations

import json
import re
from collections.abc import AsyncIterator, Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest

from backend.api.middleware import auth as auth_middleware
from backend.api.routes import auth as auth_routes
from backend.api.routes.auth import SESSION_COOKIE_NAME
from backend.api.schemas.ai_audit import RecommendationItem
from backend.core.config import get_settings
from backend.core.database import get_session
from backend.models.camera import Camera
from backend.models.event import Event
from backend.models.event_audit import EventAudit
from backend.models.event_verification import EventVerification

if TYPE_CHECKING:
    from httpx import AsyncClient

    from backend.core.redis import RedisClient

pytestmark = pytest.mark.integration

# Repo root for the committed-artifact legs below (same depth idiom as
# test_dashboard_jsonpath_bindings.py's DASHBOARDS_DIR).
_REPO_ROOT = Path(__file__).resolve().parents[3]

# Grafana's panel is the only scoped consumer of this route; it reads
# id/started_at/camera_id/risk_score/summary/detection_count and no sparse
# fieldset (analytics.json:1184, measured). REASONING_TEXT is what must stop
# reaching it.
REASONING_TEXT = "the model's private chain of thought about this event"  # pragma: allowlist secret
SCOPED_KEY = "hsi-r95-s4-scoped-monitoring-key"  # pragma: allowlist secret
PLAIN_KEY = "hsi-r95-s4-plain-operator-key"  # pragma: allowlist secret
_KEY_HEADER = "X-API-Key"
# A subset proven to serve 200: three REQUIRED EventResponse fields plus one
# optional. A subset omitting a required field 500s for a reason unrelated to
# this package (pinned at test_events_api.py:407-411).
SAFE_SPARSE_WITH_REASONING = "id,camera_id,started_at,reasoning"
# S4's third leak, found by the security audit of this clamp: `verification`
# carries the VLM's own prose (`scene_description`, plus each criterion's
# `evidence`), which is the same class of text as `reasoning`, and 0 hits for
# `verification` anywhere under monitoring/ — no scoped consumer reads it.
# Seed both members, because a clamp that nulls the payload has to stop BOTH.
SCENE_TEXT = "the verifier model described a person at the front door"  # pragma: allowlist secret
EVIDENCE_TEXT = "verifier evidence: parcel visible on the porch step"  # pragma: allowlist secret
# [r244] the third VLM-prose leak, on a different route. `suggestion` is the
# audit's free-text advice about the PROMPT; the monitoring key reads this
# endpoint for `category`/`frequency`/`priority` (consolidated.json panel 277,
# relabelled in this PR precisely because it can no longer read this string).
SUGGESTION_TEXT = (
    "add time since last motion event to the analysis prompt"  # pragma: allowlist secret
)
PASSWORD = "SecurePassword123!"  # pragma: allowlist secret  # nosemgrep: hardcoded-password


def _scoped_entry() -> str:
    return json.dumps({"key": SCOPED_KEY, "scope": "monitoring"})


def _plain_entry() -> str:
    return json.dumps(PLAIN_KEY)


@pytest.fixture
def gate_armed(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """EXPOSE_LAN on, exactly the scoped + plain entries, settings cache cleared.

    Entries are raw JSON fragments because a scoped object and a plain string
    share one list (same reason as test_api_key_scopes.py's helper).
    ``integration_env`` is function-scoped and already wrote ``API_KEYS``, so
    this fixture — which runs after the client fixture has built its app —
    wins: the scope lookup happens per request at auth.py:171, not at build.
    """
    monkeypatch.setenv("EXPOSE_LAN", "true")
    monkeypatch.setenv("API_KEYS", "[" + ",".join([_scoped_entry(), _plain_entry()]) + "]")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def keyless(client: AsyncClient) -> AsyncClient:
    """The shared client with its ambient integration key removed.

    The ``client`` fixture sends ``X-API-Key: test-api-key-12345`` on every
    request (``backend/tests/integration/conftest.py:1755``) — an UNSCOPED
    entry. Leaving it on would make every "scoped" leg an unscoped one wearing a
    second header.
    """
    client.headers.pop(_KEY_HEADER, None)
    return client


async def _seed_pair(camera_id: str, *, with_verification: bool = False) -> tuple[int, int]:
    """One live event carrying REASONING_TEXT and one soft-deleted twin.

    `with_verification` also hangs an EventVerification row on the live event,
    because `verification` is a second VLM-prose member of the same response
    (its payload renders from the newest row, so seeding one is what makes the
    field non-null by default rather than null-by-absence).

    Returns (live_id, deleted_id).
    """
    async with get_session() as db:
        camera = Camera(
            id=camera_id,
            name=camera_id,
            folder_path=f"/export/foscam/{camera_id}",
            status="online",
        )
        db.add(camera)
        await db.flush()
        live = Event(
            batch_id=f"{camera_id}-live",
            camera_id=camera_id,
            started_at=datetime.now(UTC),
            risk_score=80,
            risk_level="high",
            summary="live event",
            reasoning=REASONING_TEXT,
        )
        deleted = Event(
            batch_id=f"{camera_id}-deleted",
            camera_id=camera_id,
            started_at=datetime.now(UTC),
            risk_score=80,
            risk_level="high",
            summary="deleted event",
            reasoning=REASONING_TEXT,
            deleted_at=datetime.now(UTC),
        )
        db.add_all([live, deleted])
        await db.flush()
        ids = (live.id, deleted.id)
        if with_verification:
            db.add(
                EventVerification(
                    event_id=live.id,
                    verdict="confirmed",
                    engine="llama.cpp",
                    model_id="qwen3-vl-4b",
                    scene_description=SCENE_TEXT,
                    criteria=[
                        {"name": "person_present", "passed": True, "evidence": EVIDENCE_TEXT}
                    ],
                )
            )
        await db.commit()
    return ids


def _rows(payload: dict) -> dict[int, dict]:
    return {row["id"]: row for row in payload["items"]}


async def _seed_audit(camera_id: str) -> int:
    """One Camera -> Event -> EventAudit carrying SUGGESTION_TEXT.

    The read this clamps is not a row lookup: `get_recommendations`
    (services/pipeline_quality_audit_service.py:733) selects EventAudit rows
    with `overall_quality_score IS NOT NULL` and a recent `audited_at`, then
    groups the JSON list in each category column by string. So the row needs
    all three — a null score selects nothing, and an empty category list
    aggregates to zero recommendations. Either would leave every leg below
    asserting against `[]`, which is vacuously green for a null and for prose
    alike. Returns the event id for the caller's own bookkeeping.
    """
    async with get_session() as db:
        camera = Camera(
            id=camera_id,
            name=camera_id,
            folder_path=f"/export/foscam/{camera_id}",
            status="online",
        )
        db.add(camera)
        await db.flush()
        event = Event(
            batch_id=f"{camera_id}-audited",
            camera_id=camera_id,
            started_at=datetime.now(UTC),
            risk_score=70,
            risk_level="high",
            summary="audited event",
        )
        db.add(event)
        await db.flush()
        db.add(
            EventAudit(
                event_id=event.id,
                audited_at=datetime.now(UTC),
                overall_quality_score=4.0,
                missing_context=json.dumps([SUGGESTION_TEXT]),
            )
        )
        await db.commit()
        return event.id


@pytest.fixture
def real_session_store(real_redis: RedisClient) -> Iterator[None]:
    """Point login and the gate at the worker's real Redis (test_expose_lan_auth precedent).

    The shared ``client`` fixture's lifespan Redis is a mock that cannot answer
    session reads, so a login-issued cookie would never validate without this.
    """

    async def _real_redis_optional() -> RedisClient:
        return real_redis

    with (
        patch.object(auth_routes, "get_redis_optional", _real_redis_optional),
        patch.object(auth_middleware, "get_redis_optional", _real_redis_optional),
    ):
        yield


@pytest.fixture
async def cookie(
    client: AsyncClient, real_session_store: None
) -> AsyncIterator[tuple[AsyncClient, dict[str, str]]]:
    """The shared client with its ambient key removed, plus a login session cookie.

    The point of the leg is a caller whose only credential carries no scope, so
    the ambient integration key is popped before login (same reason as
    ``keyless``) and login runs against the real session store.

    Yields the cookie as a dict to pass per request rather than relying on the
    client's cookie jar — the ``test_expose_lan_auth.py`` precedent, which
    measures that this client does NOT retain the login cookie, so a leg that
    assumed retention would send a bare request. Handing it explicitly is also
    what lets the leg assert the refusal WITHOUT it first.
    """
    client.headers.pop(_KEY_HEADER, None)
    registered = await client.post(
        "/api/auth/register",
        json={"username": "admin", "email": "admin@example.com", "password": PASSWORD},
    )
    assert registered.status_code == 201, registered.text
    login = await client.post("/api/auth/login", json={"username": "admin", "password": PASSWORD})
    assert login.status_code == 200, login.text
    yield client, {SESSION_COOKIE_NAME: login.cookies[SESSION_COOKIE_NAME]}


class TestScopedKeyFieldCeiling:
    """The scoped key's `/api/events` response is clamped; everyone else's is not."""

    async def test_scoped_key_is_admitted_and_sees_no_reasoning(
        self, keyless: AsyncClient, gate_armed: None, clean_tables: None
    ) -> None:
        """[r95] S4's literal clause: `no reasoning` for the monitoring grant.

        200 first — a 401 here would make the field assertion vacuous, since
        `("GET", "/api/events")` IS in the scope. Then the VALUE: seeded text
        must arrive null. Key presence alone proves nothing (a dropped key is
        re-added as null by revalidation), which is why this asserts the value
        and not the key.
        """
        live_id, _ = await _seed_pair("r95s4_scoped_bare")

        response = await keyless.get("/api/events", headers={_KEY_HEADER: SCOPED_KEY})
        assert response.status_code == 200, response.text
        rows = _rows(response.json())
        assert live_id in rows, "the scoped key must still see its events"
        assert rows[live_id]["reasoning"] is None, (
            "S4's ceiling: the monitoring grant serves no reasoning. Got "
            f"{rows[live_id]['reasoning']!r}"
        )

    async def test_unscoped_key_still_gets_reasoning(
        self, keyless: AsyncClient, gate_armed: None, clean_tables: None
    ) -> None:
        """Control, and the reason this is a narrowing rather than a change.

        Same route, same seed, an entry with no scope: the text must still
        arrive. If this leg goes red the clamp widened past its scope.
        """
        live_id, _ = await _seed_pair("r95s4_plain_bare")

        response = await keyless.get("/api/events", headers={_KEY_HEADER: PLAIN_KEY})
        assert response.status_code == 200, response.text
        rows = _rows(response.json())
        assert rows[live_id]["reasoning"] == REASONING_TEXT

    async def test_scoped_key_narrowed_through_sparse_fieldset_too(
        self, keyless: AsyncClient, gate_armed: None, clean_tables: None
    ) -> None:
        """`?fields=` must not be a door back around the ceiling.

        The endpoint's own sparse-fieldset feature, asked for the clamped field
        by name. Still a 200 (the name is in the allowlist) and still a null —
        the clamp is on the value, so it holds whichever way the field was
        requested.
        """
        live_id, _ = await _seed_pair("r95s4_scoped_sparse")

        response = await keyless.get(
            f"/api/events?fields={SAFE_SPARSE_WITH_REASONING}",
            headers={_KEY_HEADER: SCOPED_KEY},
        )
        assert response.status_code == 200, response.text
        rows = _rows(response.json())
        assert rows[live_id]["reasoning"] is None

    async def test_scoped_key_include_deleted_does_not_widen_rows(
        self, keyless: AsyncClient, gate_armed: None, clean_tables: None
    ) -> None:
        """S4's other named leak: `no include_deleted` for the monitoring grant."""
        live_id, deleted_id = await _seed_pair("r95s4_scoped_deleted")

        response = await keyless.get(
            "/api/events?include_deleted=true", headers={_KEY_HEADER: SCOPED_KEY}
        )
        assert response.status_code == 200, response.text
        rows = _rows(response.json())
        assert live_id in rows
        assert deleted_id not in rows, (
            "S4's ceiling: include_deleted is not an admitted capability of the "
            "monitoring grant, so it must not widen the row set"
        )

    async def test_scoped_key_sees_no_verification_prose(
        self, keyless: AsyncClient, gate_armed: None, clean_tables: None
    ) -> None:
        """`verification` is VLM prose too, so it falls under the same ceiling.

        Witnessed on the RAW BODY, deliberately. This clamp drops the payload
        rather than nulling a scalar, and `EventVerificationPayload`/
        `EventResponse` strip a None `verification` from the payload entirely —
        so key presence says nothing here either way, and the only assertion
        that survives the schema is that neither seeded string is anywhere in
        what went out. Same lesson as the module docstring's `reasoning` note,
        one layer deeper.
        """
        live_id, _ = await _seed_pair("r95s4_scoped_verify", with_verification=True)

        response = await keyless.get("/api/events", headers={_KEY_HEADER: SCOPED_KEY})
        assert response.status_code == 200, response.text
        rows = _rows(response.json())
        assert live_id in rows, "the leg must still be served, not refused"
        assert SCENE_TEXT not in response.text, "S4's ceiling: no verifier prose for the grant"
        assert EVIDENCE_TEXT not in response.text, (
            "criteria[].evidence carries the same class of text as "
            "scene_description; nulling only the scene would leak it"
        )

    async def test_unscoped_key_still_gets_verification_prose(
        self, keyless: AsyncClient, gate_armed: None, clean_tables: None
    ) -> None:
        """Control: the field is really served by default, so the leg above is not vacuous.

        Without this the scoped assertion could be green because the seed never
        produced a payload at all. This one pins the shape too — the row's
        `verification.scene_description` is the seeded text.
        """
        live_id, _ = await _seed_pair("r95s4_plain_verify", with_verification=True)

        response = await keyless.get("/api/events", headers={_KEY_HEADER: PLAIN_KEY})
        assert response.status_code == 200, response.text
        rows = _rows(response.json())
        verification = rows[live_id].get("verification")
        assert verification is not None, (
            "the seed must produce a served payload; got the row without one: "
            f"{sorted(rows[live_id])}"
        )
        assert verification["scene_description"] == SCENE_TEXT
        assert verification["criteria"][0]["evidence"] == EVIDENCE_TEXT

    async def test_unscoped_key_include_deleted_still_widens_rows(
        self, keyless: AsyncClient, gate_armed: None, clean_tables: None
    ) -> None:
        """Control for the leg above: the param still works for an unscoped key."""
        live_id, deleted_id = await _seed_pair("r95s4_plain_deleted")

        response = await keyless.get(
            "/api/events?include_deleted=true", headers={_KEY_HEADER: PLAIN_KEY}
        )
        assert response.status_code == 200, response.text
        rows = _rows(response.json())
        assert {live_id, deleted_id} <= rows.keys()


class TestRecommendationsSuggestionCeiling:
    """[r244] ruling 244: `/api/ai-audit/recommendations` clamps `suggestion` for the grant.

    Same ceiling, one route over, because the leak is the same class of text.
    This path is in MONITORING_SCOPE_PATHS (core/constants.py:323) so Grafana's
    `Backend-API` datasource calls it with the monitoring key, and each item
    carries `suggestion` — the audit's free-text advice about the PROMPT, which
    is what ruling 95's "admit only the fields it reads" withholds from a
    scoped grant. The panel reads category/frequency/priority, so nulling the
    prose costs it nothing (and its legs relabel to those fields in this PR,
    pinned at test_dashboard_jsonpath_bindings.py).

    Three postures, because the point is a narrowing rather than a change: the
    scoped key is nulled, the unscoped key and the session cookie are served
    exactly as before.
    """

    async def test_scoped_key_gets_no_suggestion(
        self, keyless: AsyncClient, gate_armed: None, clean_tables: None
    ) -> None:
        """The clamp's own leg: served 200, item present, value null.

        200 and a non-empty list FIRST. Without them the null is vacuous — an
        empty `recommendations` array would satisfy a "no prose" assertion for
        the wrong reason, which is the trap `_seed_audit` exists to close. Then
        the value, asserted twice: the field is null on the item, and the seeded
        string is nowhere in the raw body (the module docstring's
        absence-is-not-a-witness lesson, applied to the whole payload).
        """
        await _seed_audit("r244_scoped")

        response = await keyless.get(
            "/api/ai-audit/recommendations", headers={_KEY_HEADER: SCOPED_KEY}
        )
        assert response.status_code == 200, response.text
        items = response.json()["recommendations"]
        assert items, "the seed must produce a recommendation, or the null below proves nothing"
        assert all(item["suggestion"] is None for item in items), (
            "ruling 244: the monitoring grant gets no suggestion prose. Got "
            f"{[i['suggestion'] for i in items]!r}"
        )
        assert SUGGESTION_TEXT not in response.text
        # The rest of the grant still works: it is a field ceiling, not a refusal.
        assert items[0]["category"] == "missing_context"
        assert items[0]["frequency"] == 1

    async def test_unscoped_key_still_gets_the_suggestion(
        self, keyless: AsyncClient, gate_armed: None, clean_tables: None
    ) -> None:
        """Control, and the non-vacuity witness for the leg above.

        Same route, same seed, an entry with no scope: the prose must arrive.
        If this goes red the clamp widened past its grant, and if it passes
        while the scoped leg also passes, the only explanation is a clamp that
        nulls for everyone.
        """
        await _seed_audit("r244_plain")

        response = await keyless.get(
            "/api/ai-audit/recommendations", headers={_KEY_HEADER: PLAIN_KEY}
        )
        assert response.status_code == 200, response.text
        items = response.json()["recommendations"]
        assert items[0]["suggestion"] == SUGGESTION_TEXT

    async def test_session_cookie_still_gets_the_suggestion(
        self,
        cookie: tuple[AsyncClient, dict[str, str]],
        gate_armed: None,
        clean_tables: None,
    ) -> None:
        """Ruling 244's second posture: a session cookie is not a scoped key.

        `presents_scoped_api_key` answers False for a cookie (auth.py:250-254 —
        it looks for a PRESENTED key first, and there is none), and the AI Audit
        page renders this prose behind a login.

        The 401 on the same request WITHOUT the cookie is part of the leg, not
        decoration (test_expose_lan_auth's shape): it proves the gate is armed
        and that the 200 below came from the cookie rather than from a route
        that was open anyway. `gate_armed` + the real session store matter for
        the same reason — with `expose_lan` off the gate passes everything
        through, and an unarmed leg would "pass" a request the gate never read.
        """
        await _seed_audit("r244_cookie")
        client_with_cookie, session = cookie

        bare = await client_with_cookie.get("/api/ai-audit/recommendations")
        assert bare.status_code == 401, (
            "the leg needs the gate armed: a 200 here means nothing was "
            "authenticated, so the prose below would not be evidence of anything"
        )

        response = await client_with_cookie.get("/api/ai-audit/recommendations", cookies=session)
        assert response.status_code == 200, response.text
        items = response.json()["recommendations"]
        assert items[0]["suggestion"] == SUGGESTION_TEXT

    async def test_scoped_key_beside_a_cookie_is_still_clamped(
        self,
        cookie: tuple[AsyncClient, dict[str, str]],
        gate_armed: None,
        clean_tables: None,
    ) -> None:
        """A cookie does not launder a scoped key.

        The ceiling keys on the PRESENTED KEY (auth.py:250), and a request can
        carry both credentials. Admission is the wrong witness for the clamp:
        test_api_key_scopes.py:546 pins that beside a valid cookie a scoped key
        'cast[s] no vote' and the cookie serves, so admission keys on the cookie
        here. The ceiling deliberately keys on the key instead — the narrower
        reading — so a monitoring deployment that also holds a session cannot
        read the prose back through the cookie leg. This is the leg that stops the clamp being written as
        "cookie present -> serve prose".
        """
        await _seed_audit("r244_cookie_key")
        client_with_cookie, session = cookie

        response = await client_with_cookie.get(
            "/api/ai-audit/recommendations",
            cookies=session,
            headers={_KEY_HEADER: SCOPED_KEY},
        )
        assert response.status_code == 200, response.text
        items = response.json()["recommendations"]
        assert all(item["suggestion"] is None for item in items), (
            "the scoped key clamps even next to a session cookie; got "
            f"{[i['suggestion'] for i in items]!r}"
        )
        assert SUGGESTION_TEXT not in response.text


class TestSuggestionSchemaFlipIsDeclared:
    """[r244] `suggestion: str | None` in the model AND in both committed artifacts.

    Ruling 244 item 1 names the flip and BOTH generated files in the same commit;
    item 3 asks for a leg red if the flip is omitted. Each artifact gets its own
    assertion so a failure says which one drifted: the runtime schema, the
    committed `docs/openapi.json` (CI-gated by `generate-openapi.py --check`,
    ci.yml:2042), the generated `frontend/src/types/generated/api.ts` (CI-gated
    by `generate-types.sh --check`, ci.yml:2036).

    These are the schema-flip legs: with the handler clamp in place but the
    model still `suggestion: str`, the runtime leg below is red — FastAPI
    serialises the response_model, so a scoped request would raise a validation
    error rather than serve null.
    """

    def test_model_field_is_nullable_and_still_required(self) -> None:
        """`str | None`, not optional: the key is always present, the value may be null.

        Asserting the shape as the JSON Schema the model actually emits rather
        than a hand-written expectation, because "nullable" has three different
        spellings in that document (`type: ["string","null"]`, `anyOf`, and a
        `None` default with `type: string`) and only some of them mean what the
        ruling asked for. `required` is pinned too: making the field optional
        would satisfy a naive nullability check while changing the wire shape to
        an absent key — the absence the module docstring spends a page on.
        """
        schema = RecommendationItem.model_json_schema()
        prop = schema["properties"]["suggestion"]
        assert prop.get("anyOf") == [{"type": "string"}, {"type": "null"}], prop
        assert "suggestion" in schema["required"], schema.get("required")

    def test_committed_openapi_agrees_with_the_model(self) -> None:
        """docs/openapi.json is the contract CI checks; read it, don't re-derive it.

        Reads the committed file, so this goes red if the artifact is stale
        against the model even when `generate-openapi.py --check` is not run
        locally. The two spellings below are the only honest ways to say
        "string or null" in JSON Schema; `{"type": "string"}` alone is the
        pre-[r244] shape and is the failure this leg exists to catch.
        """
        doc = json.loads((_REPO_ROOT / "docs/openapi.json").read_text())
        prop = doc["components"]["schemas"]["RecommendationItem"]["properties"]["suggestion"]
        assert prop.get("anyOf") == [{"type": "string"}, {"type": "null"}] or prop.get("type") == [
            "string",
            "null",
        ], prop

    def test_generated_api_ts_declares_the_null(self) -> None:
        """The frontend's generated view of the field allows null.

        Grepping the generated file is deliberate: `generate-types.sh --check`
        already certifies the file matches the spec in CI, but that gate is
        green for a spec that still says `string`. This is the leg that asks the
        narrower question ruling 244 item 1 asks — that the null reached the
        TypeScript, so a frontend author reading `item.suggestion` is told by
        the compiler to handle null.
        """
        generated = (_REPO_ROOT / "frontend/src/types/generated/api.ts").read_text()
        block = generated.split("        RecommendationItem: {", 1)
        assert len(block) == 2, "the codegen'd RecommendationItem block vanished"
        body = block[1].split("        };", 1)[0]
        assert re.search(r"suggestion: string \| null;", body), body
