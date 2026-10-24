"""F-297 — the household person-embedding row: the documented endpoint really
extracts a re-ID embedding from an event's person detection for a member.

Inventory row: ``docs/reference/feature-inventory.md`` §3.13, grep anchor
``POST /members/{member_id}/embeddings`` (count 1 in the doc).

Documented contract (``docs/guides/face-recognition.md`` "Add an embedding for
a member"): ``POST /api/household/members/{member_id}/embeddings`` with a JSON
body ``{"event_id": ..., "confidence": ...}`` (confidence optional, defaulting
to 1.0), implemented by ``backend/api/routes/household.py``
``add_embedding_from_event``. The ladder below walks the endpoint's documented
error contract and its 201 success rung:

* 404 for an unknown member, 404 for an unknown event, 400 for an event with
  no person detection: all three are pure-database answers reachable with
  nothing but HTTP.
* 201 storing a 512-dim person embedding: with ``REID_BACKEND=gateway``
  (`[r306a]`), the smoke event's person detection is embedded through the
  gateway's ``/enrich-lt/person-reid`` route and stored in
  ``person_embeddings`` beside the producer's ``model_id``.
"""

from __future__ import annotations

from collections.abc import Iterator

import httpx
import pytest

# Same marker hierarchy as every golden spec: these talk HTTP to a live stack
# and the ini's 5 s default (pyproject.toml) is too tight for an endpoint that
# resolves a detection image before answering.
pytestmark = [pytest.mark.network, pytest.mark.timeout(120)]

EMBEDDINGS_PATH = "/api/household/members/{member_id}/embeddings"


def _embeddings_url(member_id: int) -> str:
    return EMBEDDINGS_PATH.format(member_id=member_id)


def _create_member(client: httpx.Client) -> int:
    """Create one household member and return its id.

    Uses the smallest body the schema allows: ``name``, ``role`` and
    ``trusted_level`` are all required (``HouseholdMemberCreate``); every other
    field is optional. Values are the documented exemplar's (role ``resident``,
    trust ``full``), not arbitrary ones.
    """
    response = client.post(
        "/api/household/members",
        json={"name": "Golden F-297", "role": "resident", "trusted_level": "full"},
    )
    assert response.status_code == 201, response.text[:500]
    body = response.json()
    assert isinstance(body.get("id"), int), body
    return int(body["id"])


def _delete_member(client: httpx.Client, member_id: int) -> None:
    """Delete the member this module created; 204 or 404 are both clean-up fine."""
    response = client.delete(f"/api/household/members/{member_id}")
    assert response.status_code in (204, 404), response.text[:500]


@pytest.fixture(scope="module")
def member_id(logged_in_api: httpx.Client) -> Iterator[int]:
    """One member for the whole module, deleted in teardown (assert 204)."""
    created = _create_member(logged_in_api)
    yield created
    _delete_member(logged_in_api, created)


@pytest.fixture(scope="module")
def no_person_event_id(api: httpx.Client, cameras_by_scenario: dict[str, str]) -> int:
    """An event with zero detections, created through the public API.

    The bulk-create endpoint (``POST /api/events/bulk``, 207) makes events
    without touching the ``event_detections`` junction — its response items
    carry the id. Needs a real camera id (unknown ones fail per-item), taken
    from the harness's seeded set.
    """
    camera_id = cameras_by_scenario.get("harness-smoke")
    assert camera_id, "harness seeded no harness-smoke camera for the bulk-create leg"
    response = api.post(
        "/api/events/bulk",
        json={
            "events": [
                {
                    "batch_id": "golden-f297-no-person",
                    "camera_id": camera_id,
                    "started_at": "2026-01-01T00:00:00Z",
                    "risk_score": 10,
                    "risk_level": "low",
                    "summary": "golden F-297 event with no detections",
                }
            ]
        },
    )
    assert response.status_code == 207, response.text[:500]
    items = response.json().get("results", [])
    assert len(items) == 1, response.text[:500]
    assert items[0].get("status") == "success", response.text[:500]
    assert isinstance(items[0].get("id"), int), response.text[:500]
    return int(items[0]["id"])


@pytest.fixture(scope="module")
def smoke_event(api: httpx.Client, cameras_by_scenario: dict[str, str]) -> dict:
    """The event the harness's own smoke step produced, looked up by camera.

    ``scripts/feature_check.py`` ``smoke()`` runs before ``golden()`` and
    aborts the run if it produced no verified event, so at golden time the
    stack is guaranteed to hold exactly the event this fixture asserts on. The
    lookup therefore **asserts** rather than skips: a missing event is a
    harness contract break, not a spec precondition.
    """
    camera_id = cameras_by_scenario.get("harness-smoke")
    assert camera_id, "harness seeded no harness-smoke camera"
    response = api.get("/api/events", params={"camera_id": camera_id, "limit": 10})
    assert response.status_code == 200, response.text[:500]
    items = response.json().get("items", [])
    assert items, (
        "no event for the smoke camera at golden time — smoke() ran before golden() and must have produced one"
    )
    # This module itself bulk-creates an event on the same camera (the 400
    # leg), so the newest-first list may hold it before the smoke event; pick
    # by the property smoke() guarantees — a verification verdict — rather
    # than by position.
    event = next((e for e in items if (e.get("verification") or {}).get("verdict")), None)
    assert event is not None, (
        "no verified event for the smoke camera; smoke() asserts one exists before golden()"
    )
    return event


def test_f297_unknown_member_answers_404(logged_in_api: httpx.Client) -> None:
    """Enrolment for a member that does not exist is 404, not 500."""
    response = logged_in_api.post(
        _embeddings_url(999_999_999),
        json={"event_id": 1, "confidence": 0.9},
    )
    assert response.status_code == 404, response.text[:500]
    assert "Household member with id 999999999 not found" in response.text


def test_f297_unknown_event_answers_404(logged_in_api: httpx.Client, member_id: int) -> None:
    """Enrolment for a real member but an event id that does not exist is 404."""
    response = logged_in_api.post(
        _embeddings_url(member_id),
        json={"event_id": 987_654_321, "confidence": 0.9},
    )
    assert response.status_code == 404, response.text[:500]
    assert "Event with id 987654321 not found" in response.text


def test_f297_event_without_person_detection_answers_400(
    logged_in_api: httpx.Client,
    member_id: int,
    no_person_event_id: int,
) -> None:
    """A real event carrying zero detections answers 400, not 500.

    The bulk-created event has no detections at all, so the endpoint's
    "find the first person detection" scan comes up empty before it ever
    touches the filesystem — the database-only rung of the ladder.
    """
    response = logged_in_api.post(
        _embeddings_url(member_id),
        json={"event_id": no_person_event_id, "confidence": 0.9},
    )
    assert response.status_code == 400, response.text[:500]
    assert "Event does not contain a person detection" in response.text


def test_f297_person_event_stores_embedding_answers_201(
    logged_in_api: httpx.Client,
    member_id: int,
    smoke_event: dict,
) -> None:
    """With REID_BACKEND=gateway ([r306a]), the smoke event's person crop embeds and stores (201).

    The smoke event carries a person detection (scenario fixture: one person,
    bbox 260,120,110,300) whose image file exists in-container — so the
    endpoint reaches the Re-ID service, which extracts a 512-dim embedding
    through the gateway's ``/enrich-lt/person-reid`` route and stores the
    ``PersonEmbedding`` row beside the producer's ``model_id``.
    """
    event_id = smoke_event["id"]
    response = logged_in_api.post(
        _embeddings_url(member_id),
        json={"event_id": event_id, "confidence": 0.9},
    )
    assert response.status_code == 201, response.text[:500]
    body = response.json()
    assert isinstance(body.get("id"), int), body
    assert body.get("member_id") == member_id, body
    assert body.get("source_event_id") == event_id, body
    assert body.get("confidence") == pytest.approx(0.9), body
    assert isinstance(body.get("created_at"), str) and body["created_at"], body
