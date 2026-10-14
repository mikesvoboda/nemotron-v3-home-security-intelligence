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

- `reasoning` is SERVED by default: routes/events.py:405 `undefer`s the column
  and :509 writes the value into every row. The ceiling is on the VALUE, not on
  key presence — measured here: a dict that OMITS `reasoning` still goes out on
  the wire as `"reasoning": null`, because the row dicts are re-validated
  against `EventResponse` and pydantic re-adds the schema default. That is the
  same absence-is-not-a-witness trap this file's `notes` sibling documents at
  routes/events.py:511 (F-057). So each leg below seeds real text and asserts
  the value is null, which is the only assertion that distinguishes the states.
- `include_deleted` widens the ROWS (events.py:409-410 skips the
  `deleted_at IS NULL` filter). For a scoped caller it is not an admitted
  capability, so it is forced off: the response stays a 200 and the row set
  equals the default one. Deliberately not a 400 — "admit only the fields it
  reads" narrows the grant; it does not add a new failure mode to a path
  Grafana calls on every dashboard refresh.

Both clamps key on the PRESENTED KEY's scope re-derived at request time, not on
middleware-set state, because `AuthMiddleware.__call__` returns early when
`expose_lan` is off (auth.py:613) — in the LAN-trusted posture the gate never
runs, so state set there would leave the ceiling unarmed exactly where S1's
configuration lives.

The unscoped arms are the point as much as the scoped ones: an operator key and
a session-cookie caller keep byte-identical payloads, so this is a narrowing of
one scope, not a change to the endpoint.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from datetime import UTC, datetime
from typing import TYPE_CHECKING

import pytest

from backend.core.config import get_settings
from backend.core.database import get_session
from backend.models.camera import Camera
from backend.models.event import Event
from backend.models.event_verification import EventVerification

if TYPE_CHECKING:
    from httpx import AsyncClient

pytestmark = pytest.mark.integration

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
    request (conftest.py:1755) — an UNSCOPED entry. Leaving it on would make
    every "scoped" leg an unscoped one wearing a second header.
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
