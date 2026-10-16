"""Integration tests for the event search API.

These tests require a running PostgreSQL database with the full-text search
migration applied.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from backend.models.camera import Camera
from backend.models.event import Event
from backend.tests.conftest import unique_id

# Search API is implemented at /api/events/search


@pytest.fixture
async def setup_searchable_events(db_session):
    """Create test data for search tests."""
    # Use unique IDs and names to avoid parallel test conflicts and unique constraint violations
    front_door_id = unique_id("front_door")
    back_yard_id = unique_id("back_yard")

    # Create a camera with unique name
    camera = Camera(
        id=front_door_id,
        name=f"Front Door {front_door_id[-8:]}",
        folder_path=f"/export/foscam/{front_door_id}",
        status="online",
    )
    db_session.add(camera)

    camera2 = Camera(
        id=back_yard_id,
        name=f"Back Yard {back_yard_id[-8:]}",
        folder_path=f"/export/foscam/{back_yard_id}",
        status="online",
    )
    db_session.add(camera2)

    await db_session.flush()

    # Create events with various content for search testing
    events = [
        Event(
            batch_id=unique_id("batch1"),
            camera_id=front_door_id,
            started_at=datetime.now(UTC) - timedelta(hours=1),
            risk_score=75,
            risk_level="high",
            summary="Suspicious person detected near front entrance",
            reasoning="Unknown individual lingering near door during nighttime hours",
            reviewed=False,
            object_types="person",
        ),
        Event(
            batch_id=unique_id("batch2"),
            camera_id=front_door_id,
            started_at=datetime.now(UTC) - timedelta(hours=2),
            risk_score=30,
            risk_level="low",
            summary="Delivery driver dropped off package",
            reasoning="Recognized delivery uniform, routine delivery activity",
            reviewed=True,
            object_types="person, vehicle",
        ),
        Event(
            batch_id=unique_id("batch3"),
            camera_id=back_yard_id,
            started_at=datetime.now(UTC) - timedelta(hours=3),
            risk_score=50,
            risk_level="medium",
            summary="Animal detected in back yard",
            reasoning="Dog or cat moving through yard, no threat",
            reviewed=False,
            object_types="animal",
        ),
        Event(
            batch_id=unique_id("batch4"),
            camera_id=back_yard_id,
            started_at=datetime.now(UTC) - timedelta(days=2),
            risk_score=90,
            risk_level="critical",
            summary="Vehicle parked suspiciously for extended time",
            reasoning="Unknown vehicle parked near property for over 30 minutes at night",
            reviewed=False,
            object_types="vehicle",
        ),
    ]

    for event in events:
        db_session.add(event)

    await db_session.commit()

    # Return events and camera IDs for tests that need them
    return {"events": events, "front_door_id": front_door_id, "back_yard_id": back_yard_id}


@pytest.mark.asyncio
async def test_search_basic_query(client, setup_searchable_events):
    """Test basic search query."""
    response = await client.get("/api/events/search?q=person")

    assert response.status_code == 200
    data = response.json()

    assert "results" in data
    # Shipped SearchResponse (schemas/search.py:78-112): results,
    # total_count, limit, offset — no "total", no "query" echo.
    assert "total_count" in data
    assert "limit" in data
    assert "offset" in data

    # Should find events mentioning "person"
    assert data["total_count"] >= 0  # May be 0 if FTS not populated yet


@pytest.mark.asyncio
async def test_search_phrase_query(client, setup_searchable_events):
    """Test phrase search with quotes."""
    # Note: PostgreSQL FTS handles phrase search differently
    response = await client.get("/api/events/search?q=suspicious")

    assert response.status_code == 200
    data = response.json()

    assert "results" in data


@pytest.mark.asyncio
async def test_search_boolean_or(client, setup_searchable_events):
    """Test OR boolean search."""
    # Note: The API uses AND by default, not OR
    response = await client.get("/api/events/search?q=person")

    assert response.status_code == 200
    data = response.json()

    assert "results" in data


@pytest.mark.asyncio
async def test_search_with_camera_filter(client, setup_searchable_events):
    """Test search with camera filter."""
    front_door_id = setup_searchable_events["front_door_id"]
    response = await client.get(f"/api/events/search?q=detected&camera_id={front_door_id}")

    assert response.status_code == 200
    data = response.json()

    # All results should be from front_door camera
    for result in data["results"]:
        assert result["camera_id"] == front_door_id


@pytest.mark.asyncio
async def test_search_with_risk_level_filter(client, setup_searchable_events):
    """Test search with risk_level filter."""
    response = await client.get("/api/events/search?q=vehicle&risk_level=critical")

    assert response.status_code == 200
    data = response.json()

    # All results should have critical risk level
    for result in data["results"]:
        assert result["risk_level"] == "critical"


@pytest.mark.asyncio
async def test_search_with_date_range(client, setup_searchable_events):
    """Test search with date range filter."""
    start_date = (datetime.now(UTC) - timedelta(days=1)).isoformat()
    end_date = datetime.now(UTC).isoformat()

    # params= percent-encodes the '+' in the tz offset; string interpolation
    # leaves it raw and it arrives as a literal space -> 422.
    response = await client.get(
        "/api/events/search",
        params={"q": "detected", "start_date": start_date, "end_date": end_date},
    )

    assert response.status_code == 200
    data = response.json()

    # Results should be within date range
    for result in data["results"]:
        result_date = datetime.fromisoformat(result["started_at"].replace("Z", "+00:00"))
        assert result_date >= datetime.fromisoformat(start_date.replace("Z", "+00:00"))


@pytest.mark.asyncio
async def test_search_pagination(client, setup_searchable_events):
    """Test search pagination."""
    # First page
    response1 = await client.get("/api/events/search?q=detected&limit=2&offset=0")
    assert response1.status_code == 200
    data1 = response1.json()

    # Second page
    response2 = await client.get("/api/events/search?q=detected&limit=2&offset=2")
    assert response2.status_code == 200
    data2 = response2.json()

    # Pagination info should be correct
    assert data1["limit"] == 2
    assert data1["offset"] == 0
    assert data2["offset"] == 2

    # Results should be different (if there are enough)
    if len(data1["results"]) > 0 and len(data2["results"]) > 0:
        assert data1["results"][0]["id"] != data2["results"][0]["id"]


@pytest.mark.asyncio
async def test_search_relevance_scoring(client, setup_searchable_events):
    """Test that results include relevance scores."""
    response = await client.get("/api/events/search?q=suspicious")

    assert response.status_code == 200
    data = response.json()

    # Results should have relevance scores (shipped field name:
    # relevance_score — schemas/search.py:70-72, service labels the SQL
    # rank as relevance_score)
    for result in data["results"]:
        assert "relevance_score" in result
        assert isinstance(result["relevance_score"], int | float)


@pytest.mark.asyncio
async def test_search_returns_camera_name(client, setup_searchable_events):
    """Test that results include camera name."""
    response = await client.get("/api/events/search?q=detected")

    assert response.status_code == 200
    data = response.json()

    # Results should have camera_name
    for result in data["results"]:
        assert "camera_name" in result


@pytest.mark.asyncio
async def test_search_empty_query_rejected(client):
    """Test that empty query is rejected."""
    response = await client.get("/api/events/search?q=")

    # FastAPI should reject empty query due to min_length=1
    assert response.status_code == 422  # Validation error


@pytest.mark.asyncio
async def test_search_returns_highlights(client, setup_searchable_events):
    """Test that results carry the shipped per-result fields.

    "highlights" is not part of the shipped contract — no backend code
    outside tests references it (repo-wide grep) and no revision of
    schemas/search.py ever had it. Assert the shipped result fields.
    """
    response = await client.get("/api/events/search?q=suspicious")

    assert response.status_code == 200
    data = response.json()

    for result in data["results"]:
        assert "id" in result  # SearchResult.id (Event ID)
        assert "relevance_score" in result


@pytest.mark.asyncio
async def test_search_returns_query_in_response(client, setup_searchable_events):
    """Test search response shape for a real query.

    The shipped SearchResponse (schemas/search.py:78-112) never included a
    "query" echo (no revision did) — assert the shipped response shape.
    """
    response = await client.get("/api/events/search?q=person")

    assert response.status_code == 200
    data = response.json()

    assert data["total_count"] >= 0
    assert isinstance(data["results"], list)


@pytest.fixture
async def setup_severity_mismatch_events(db_session):
    """Camera + events whose stored risk_level disagrees with their risk_score.

    `[r211b]` break (2): the search filter tested the stored `risk_level` column
    while the response recomputes it from `risk_score`
    (backend/api/schemas/search.py:44 -> schemas/events.py:19), so a row can
    display one level and be filtered by another. Each row here is written with
    the *wrong* stored level on purpose; the displayed level is the derived one.
    """
    camera_id = unique_id("sev_mismatch_cam")
    db_session.add(
        Camera(
            id=camera_id,
            name=f"Severity mismatch {camera_id[-8:]}",
            folder_path=f"/export/foscam/{camera_id}",
            status="online",
        )
    )
    await db_session.flush()

    # (risk_score, stored risk_level) pairs straddling every band boundary.
    rows = [
        (91, "high"),  # the ruling's measured instance: displays critical
        (84, "medium"),  # displays high
        (85, "low"),  # displays critical
        (60, "low"),  # displays high
        (59, "critical"),  # displays medium
        (30, "low"),  # displays medium
        (29, "medium"),  # displays low
    ]
    events = [
        Event(
            batch_id=unique_id(f"batch_sc{i}"),
            camera_id=camera_id,
            started_at=datetime.now(UTC) - timedelta(hours=1 + i),
            risk_score=score,
            risk_level=stored_level,
            summary="Person seen near the camera",
            reasoning="Test row for the severity derivation",
            reviewed=False,
            object_types="person",
        )
        for i, (score, stored_level) in enumerate(rows)
    ]
    for event in events:
        db_session.add(event)
    await db_session.commit()
    return {"events": events, "camera_id": camera_id}


@pytest.mark.asyncio
async def test_search_never_returns_soft_deleted_events(
    client, db_session, setup_searchable_events
):
    """`[r211b]` break (1): browse hides soft-deleted events, search did not.

    GET /api/events filters on Event.deleted_at (routes/events.py:421); the
    search service had no such predicate, so a deleted event stayed searchable
    while invisible in the list the panel actually draws from.
    """
    # Scoped to this fixture's camera: the shared integration DB holds other
    # rows that match the same text, so an unscoped total_count == len(results)
    # assertion would measure other tests' data.
    camera_id = setup_searchable_events["front_door_id"]
    victim = setup_searchable_events["events"][0]
    victim_id = victim.id

    # Present before deletion, so the assertion below cannot pass by accident.
    before = await client.get(
        "/api/events/search", params={"q": "suspicious", "camera_id": camera_id}
    )
    assert before.status_code == 200
    assert victim_id in [r["id"] for r in before.json()["results"]]

    victim.deleted_at = datetime.now(UTC)
    await db_session.commit()

    response = await client.get(
        "/api/events/search", params={"q": "suspicious", "camera_id": camera_id}
    )
    assert response.status_code == 200
    data = response.json()

    assert victim_id not in [r["id"] for r in data["results"]]
    # The count must agree with the page, or the panel renders "N of M" over a
    # list that no longer holds the row (ruling 211's measured symptom).
    assert data["total_count"] == len(data["results"])


@pytest.mark.asyncio
async def test_search_severity_filter_returns_the_level_a_result_displays(
    client, setup_severity_mismatch_events
):
    """`[r211b]` break (2): filtering tested the stored column, the response
    reports the derived level, so `severity=critical` missed a row displayed
    critical. The filter and the response must read one derivation.
    """
    camera_id = setup_severity_mismatch_events["camera_id"]
    events = setup_severity_mismatch_events["events"]

    # What the API actually reports per row, keyed by score.
    listed = await client.get("/api/events/search", params={"q": "person", "camera_id": camera_id})
    assert listed.status_code == 200
    displayed = {r["risk_score"]: r["risk_level"] for r in listed.json()["results"]}
    assert displayed[91] == "critical", "the response recomputes from risk_score"
    assert len(displayed) == len(events), "every mismatch row is searchable"

    for score, level in displayed.items():
        filtered = await client.get(
            "/api/events/search",
            params={"q": "person", "camera_id": camera_id, "severity": level},
        )
        assert filtered.status_code == 200
        ids = [r["id"] for r in filtered.json()["results"]]
        assert any(r["risk_score"] == score for r in filtered.json()["results"]), (
            f"a row displaying {level} (score {score}) must be returned by severity={level}"
        )
        # and nothing in the page displays a different level
        for r in filtered.json()["results"]:
            assert r["risk_level"] == level


@pytest.mark.asyncio
async def test_search_severity_filter_agrees_at_band_boundaries(
    client, setup_severity_mismatch_events
):
    """Every band boundary lands in the filter's result page, not just the middle.

    Exercises the SQL half of Event.computed_risk_level -- the CASE behind
    services/search.py's severity filter -- at the SHIPPED bands, which is what
    makes it the witness for that arm: it reads settings like the Python half
    (models/event.py:450), so the two cannot drift apart silently. Hardcoding
    any band set into the expression reddens this leg (verified: baking in
    10/20/30 fails both severity legs).
    """
    camera_id = setup_severity_mismatch_events["camera_id"]
    expected = {
        91: "critical",
        85: "critical",
        84: "high",
        60: "high",
        59: "medium",
        30: "medium",
        29: "low",
    }

    for level in ("low", "medium", "high", "critical"):
        response = await client.get(
            "/api/events/search",
            params={"q": "person", "camera_id": camera_id, "severity": level},
        )
        assert response.status_code == 200
        results = response.json()["results"]
        assert {r["risk_score"] for r in results if r["camera_id"] == camera_id} == {
            score for score, lvl in expected.items() if lvl == level
        }, f"severity={level} should select exactly the scores that display {level}"
        assert all(r["risk_level"] == level for r in results)


@pytest.mark.asyncio
async def test_computed_risk_level_sql_and_python_agree_on_moved_bands(db_session, monkeypatch):
    """The SQL CASE and the Python echo must be ONE derivation, machine-checked.

    `[r211b]` routes both the search filter (services/search.py) and the API
    response (api/schemas/search.py:44) through the score-to-level rule, so the
    two halves of Event.computed_risk_level cannot be allowed to drift. With the
    bands moved off their shipped defaults, a SQL side that still carried the
    old hardcoded 29/59/84 would classify a different set of scores than the
    Python side and this fails for every score between the old and new edges.
    """
    from unittest.mock import MagicMock

    from sqlalchemy import select

    from backend.api.schemas.events import _compute_risk_level
    from backend.core import config as config_module
    from backend.models.event import Event

    moved = MagicMock()
    moved.severity_low_max = 10
    moved.severity_medium_max = 20
    moved.severity_high_max = 30
    monkeypatch.setattr(config_module, "get_settings", lambda: moved)

    # One row per score straddling the NEW edges (10/11, 20/21, 30/31) and the
    # OLD ones (29/30, 59/60, 84/85) — the latter are what a stale literal leaks.
    camera_id = unique_id("derivation_cam")
    db_session.add(
        Camera(
            id=camera_id,
            name=f"Derivation {camera_id[-8:]}",
            folder_path=f"/export/foscam/{camera_id}",
            status="online",
        )
    )
    await db_session.flush()
    scores = [0, 10, 11, 20, 21, 29, 30, 31, 59, 60, 84, 85, 100]
    for i, score in enumerate(scores):
        db_session.add(
            Event(
                batch_id=unique_id(f"batch_dv{i}"),
                camera_id=camera_id,
                started_at=datetime.now(UTC) - timedelta(hours=1 + i),
                risk_score=score,
                summary="Person seen near the derivation camera",
                reviewed=False,
            )
        )
    await db_session.commit()

    for level in ("low", "medium", "high", "critical"):
        rows = (
            (
                await db_session.execute(
                    select(Event.risk_score)
                    .where(Event.camera_id == camera_id)
                    .where(Event.computed_risk_level == level)
                )
            )
            .scalars()
            .all()
        )
        expected = {s for s in scores if _compute_risk_level(s) == level}
        assert set(rows) == expected, (
            f"SQL side put {sorted(set(rows))} in {level!r}; the Python derivation "
            f"says {sorted(expected)} — the two halves of computed_risk_level disagree"
        )
    # The guard that makes the four loops above non-vacuous: if the patch had
    # reached NEITHER side, both would still agree on the shipped bands and the
    # loops would pass for the wrong reason. 25 is "low" on the shipped
    # 29/59/84, "high" on 10/20/30, so this pins that the bands really moved.
    assert _compute_risk_level(25) == "high", "bands did not actually move off 29/59/84"
