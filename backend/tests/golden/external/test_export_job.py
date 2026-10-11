"""F-097 — the data-management export-events row: an export job writes
a real row and a real file, and both are readable back over HTTP.

Inventory row: ``docs/reference/feature-inventory.md`` §3, grep anchor
``Export events`` (count 1 in the doc).

The row's own evidence says what must be true: "The written ``export_jobs`` row
and file are read back by ``list_exports`` … and ``download_export``". That is
this spec's shape — start a job, wait for it, then prove the two readers see
what the writer wrote. The artefact lives at ``EXPORT_DIR = /tmp/exports``
inside the backend container, so the download route is the only external
surface, which is exactly right for an external-artefact golden path: nothing
here execs into a container.

CSV only, the form the UI defaults to; the JSON/ZIP/Excel branches share the
job plumbing but write different bytes, and pinning all four here would double
the polling cost for no new contract.
"""

from __future__ import annotations

import csv
import io
import time

import httpx
import pytest

pytestmark = [pytest.mark.network, pytest.mark.timeout(300)]

# The job is polled, not slept-on-blind: PENDING -> RUNNING -> COMPLETED moves
# through a FastAPI background task (run_export_job_with_db), so the wait is
# bounded by the marker above, not a fixed sleep.
POLL_INTERVAL_S = 2.0
POLL_DEADLINE_S = 180.0

# The export header is the *display* name of each column: events_to_csv writes
# col[1] for every (field, display) pair, and a request without "columns" gets
# EXTENDED_EXPORT_COLUMNS (export_service.py get_selected_columns -> None path).
# These are the display strings the user sees in the file; renaming a display
# name in export_service.py changes the artefact, so the artefact pins them.
EXPECTED_CSV_HEADER = [
    "Event ID",
    "Camera",
    "Started At",
    "Ended At",
    "Risk Score",
    "Risk Level",
    "Summary",
    "Detections",
    "Reviewed",
    "Object Types",
    "Reasoning",
]

TERMINAL_STATUSES = {"completed", "failed"}


def _wait_for_terminal(client: httpx.Client, job_id: str) -> dict:
    """Poll ``GET /api/exports/{job_id}`` until the job leaves PENDING/RUNNING.

    Returns the terminal job body; fails the test if the deadline passes, which
    surfaces a wedged background task as a timeout with the last-seen status
    rather than an opaque marker timeout.
    """
    deadline = time.monotonic() + POLL_DEADLINE_S
    last: dict = {}
    while time.monotonic() < deadline:
        response = client.get(f"/api/exports/{job_id}")
        assert response.status_code == 200, response.text[:500]
        last = response.json()
        if last.get("status") in TERMINAL_STATUSES:
            return last
        time.sleep(POLL_INTERVAL_S)
    pytest.fail(
        f"export job {job_id} did not reach a terminal status within "
        f"{POLL_DEADLINE_S:.0f}s; last status: {last.get('status')!r} "
        f"(progress: {last.get('progress')!r}, error: {last.get('error_message')!r})"
    )


@pytest.fixture(scope="module")
def completed_export(logged_in_api: httpx.Client) -> dict:
    """One real export job, run to completion, shared by this module.

    The smoke step of the same run has already put at least one event on the
    stack (feature_check smoke asserts its verdict), so the export has real
    rows to write — but zero rows is legal too: the service writes a
    header-only file, so the assertions below are written to hold either way.
    """
    start = logged_in_api.post(
        "/api/exports",
        json={"export_type": "events", "export_format": "csv"},
    )
    assert start.status_code == 202, start.text[:500]
    body = start.json()
    job_id = body["job_id"]
    assert job_id, f"202 without a job_id: {body!r}"
    # The row claims "sees export history with status/progress" — the start
    # response is where the UI first learns the job exists.
    assert body["status"] == "pending", body

    job = _wait_for_terminal(logged_in_api, job_id)
    assert job["status"] == "completed", (
        f"export job failed: {job.get('error_message')!r} (job {job_id})"
    )
    job["_job_id"] = job_id
    return job


def test_completed_job_reports_result_with_size(completed_export: dict) -> None:
    """The status endpoint's result block reflects the file that was written.

    ``_model_to_response`` only builds ``result`` when status is COMPLETED and
    ``output_path`` is set, so a non-zero ``output_size_bytes`` here is the
    server's own claim that a file exists — which the download test below then
    verifies independently, rather than trusting the claim.
    """
    result = completed_export.get("result")
    assert result is not None, f"completed job has no result block: {completed_export!r}"
    assert result["output_path"], result
    # Strictly positive, not merely non-negative: ``events_to_csv``
    # (``export_service.py:337``) writes the header row before it iterates the
    # rows (``writer.writerow(header_row)``, ``:359``), so a header-only export
    # is already 87 bytes (measured: ``len(events_to_csv([]).encode())``).
    # ``>= 0`` here would pass on a completed job that wrote nothing at all,
    # which is the vacuous shape the ratchet-side review of this PR caught.
    assert result["output_size_bytes"] > 0, result
    assert result["format"] == "csv", result


def test_completed_job_appears_in_history(
    logged_in_api: httpx.Client, completed_export: dict
) -> None:
    """``GET /api/exports`` — the history list the page shows — contains the job.

    The row's claim is a read-back: the INSERTed row must be visible to the
    list endpoint the UI polls. Asserting our id is among the returned ids
    proves writer and reader agree on the table, without depending on how many
    other jobs happen to exist.
    """
    listing = logged_in_api.get("/api/exports", params={"limit": 100})
    assert listing.status_code == 200, listing.text[:500]
    items = listing.json()["items"]
    ids = {item["id"] for item in items}
    assert completed_export["_job_id"] in ids, (
        f"job {completed_export['_job_id']} missing from /api/exports "
        f"({len(items)} items: {sorted(ids)[:5]}…)"
    )
    mine = next(item for item in items if item["id"] == completed_export["_job_id"])
    assert mine["status"] == "completed", mine
    assert mine["export_type"] == "events", mine
    assert mine["export_format"] == "csv", mine


def test_download_returns_csv_with_service_header(
    logged_in_api: httpx.Client, completed_export: dict
) -> None:
    """The artefact itself: right media type, attachment name, header row.

    This is the row's load-bearing observable — a job that reports
    ``completed`` but 404s on download is the "reports success it did not
    achieve" shape the inventory's half-built definition is about. The header
    strings come from ``EXTENDED_EXPORT_COLUMNS`` display names; the csv module
    parses rather than string-matches so a quoting change in the service (a
    summary containing a comma) can't false-red this.
    """
    download = logged_in_api.get(f"/api/exports/{completed_export['_job_id']}/download")
    assert download.status_code == 200, (
        f"download of a completed export answered {download.status_code}: {download.text[:300]}"
    )
    content_type = download.headers.get("content-type", "")
    assert content_type.startswith("text/csv"), content_type
    disposition = download.headers.get("content-disposition", "")
    assert "attachment" in disposition and "events_export_" in disposition, disposition

    rows = list(csv.reader(io.StringIO(download.text)))
    assert rows, "downloaded file parsed to zero rows"
    assert rows[0] == EXPECTED_CSV_HEADER, (
        f"header row drifted from EXTENDED_EXPORT_COLUMNS display names: {rows[0]!r}"
    )
