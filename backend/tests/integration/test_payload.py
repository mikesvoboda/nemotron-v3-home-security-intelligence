"""Integration tests for the alert delivery payload builder (B4.2).

The payload is what every channel adapter receives, so the DB-backed half of
its contract lives here: a real Alert row (FKs to cameras/events enforced)
flows through ``build_payload`` unchanged in shape, the VLM summary comes off
the alert's ``metadata`` JSONB column (mapped as ``alert_metadata``), and the
F13 redaction decision (include_names off) lands on the summary that goes out.
"""

from __future__ import annotations

import json
from typing import Any
from uuid import uuid7

import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend.models.alert import Alert
from backend.services.alerting.payload import build_payload

# asyncio_mode=auto (pyproject) makes async tests run under pytest-asyncio.


@pytest_asyncio.fixture
async def db_engine(worker_db_url: str):
    engine = create_async_engine(worker_db_url)  # default isolation: transactions work
    # create_all the tables this suite needs (idempotent)
    from backend.models.camera import Base

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all, tables=None)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def session_factory(db_engine):
    return async_sessionmaker(db_engine, expire_on_commit=False)


async def _seed_alert(
    session_factory: Any,
    *,
    metadata: dict[str, Any] | None,
) -> dict[str, str]:
    """One camera -> event -> alert chain; the metadata column carries the VLM text."""
    alert_id = str(uuid7())
    event_id = 730000 + int(uuid7().hex[-5:], 16) % 100000
    async with session_factory() as session:
        await session.execute(
            text(
                "INSERT INTO cameras (id, name, folder_path, status, created_at,"
                " ingestion_mode, motion_sensitivity)"
                " VALUES ('front_door', 'Front door', '/media/front_door', 'online',"
                " timezone('utc', now()), 'rtsp', 0.5)"
                " ON CONFLICT (id) DO NOTHING"
            ),
        )
        await session.execute(
            text(
                "INSERT INTO events (id, batch_id, camera_id, started_at, version, reviewed,"
                " flagged, is_fast_path)"
                " VALUES (:eid, :batch, 'front_door', timezone('utc', now()), 1, FALSE,"
                " FALSE, FALSE)"
                " ON CONFLICT (id) DO NOTHING"
            ),
            {"eid": event_id, "batch": f"b-{event_id}"},
        )
        await session.execute(
            text(
                "INSERT INTO alerts (id, event_id, severity, status, created_at, updated_at,"
                " dedup_key, version_id, is_high_priority, match_count, metadata)"
                " VALUES (:aid, :eid, 'high', 'open', timezone('utc', now()),"
                " timezone('utc', now()), :dk, 1, FALSE, 1, CAST(:meta AS jsonb))"
            ),
            {
                "aid": alert_id,
                "eid": event_id,
                "dk": f"dk-{alert_id[:12]}",
                "meta": json.dumps(metadata) if metadata is not None else None,
            },
        )
        await session.commit()
    return {"alert_id": alert_id, "event_id": str(event_id)}


class TestBuildPayloadFromRealAlert:
    async def test_payload_reads_metadata_title_and_summary_and_redacts(
        self, session_factory
    ) -> None:
        ids = await _seed_alert(
            session_factory,
            metadata={
                "rule_name": "person at the door",
                "summary": "Known person Jane walks toward the door.",
            },
        )
        async with session_factory() as session:
            alert = await session.get(Alert, ids["alert_id"])
            payload = build_payload(
                alert,
                idempotency_key="idem-1",
                include_names=False,
                known_names={"Jane"},
            )
        assert payload["alert_id"] == ids["alert_id"]
        assert payload["title"] == "person at the door"
        # F13, pass 1: the label stays, the NAME after it becomes the token
        # ("Known person Jane" -> "Known person a known person"). Pass 2 then
        # finds no bare "Jane" left. The channel adapter tests pin the looser
        # "names never survive" invariant; this pins the exact wire text.
        assert payload["summary"] == "Known person a known person walks toward the door."
        assert payload["event_id"] == int(ids["event_id"])
        assert payload["idempotency_key"] == "idem-1"
        assert payload["severity"] == "high"
        assert payload["occurred_at"]  # iso timestamp off the row

    async def test_payload_without_metadata_sends_an_empty_summary(self, session_factory) -> None:
        """Real Alert rows have no description column: with no VLM text the
        summary ships empty rather than inventing content."""
        ids = await _seed_alert(session_factory, metadata=None)
        async with session_factory() as session:
            alert = await session.get(Alert, ids["alert_id"])
            payload = build_payload(
                alert,
                idempotency_key="idem-2",
                include_names=True,
            )
        assert payload["summary"] == ""
        assert payload["title"] == "Security alert"

    async def test_payload_redacts_reasoning_fallback_too(self, session_factory) -> None:
        """The summary key is preferred, reasoning is the second fallback, and
        the redaction pass covers whichever produced the text."""
        ids = await _seed_alert(
            session_factory,
            metadata={"reasoning": "known person Bob near the gate"},
        )
        async with session_factory() as session:
            alert = await session.get(Alert, ids["alert_id"])
            payload = build_payload(
                alert,
                idempotency_key="idem-3",
                include_names=False,
                known_names={"Bob"},
            )
        assert payload["summary"] == "known person a known person near the gate"
