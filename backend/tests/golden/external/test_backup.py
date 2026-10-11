"""F-100 — the data-management Backups row: a backup job writes a real
ZIP, and every reader (status, list, download, delete) agrees with the writer.

Inventory row: ``docs/reference/feature-inventory.md`` §3, grep anchor
``Backups (create, progress, list, download, delete)`` (count 1 in the doc).

The row lists five calls, and this spec exercises all five — but deliberately:
the four *readers* run against one shared completed job, while **delete gets a
job of its own.** That split is forced by the repo's own pytest config
(``pyproject.toml`` ``addopts`` = ``-p randomly --dist=worksteal``): test order
inside a module is not guaranteed, so a destructive test that consumed the
shared fixture would red its siblings whenever the randomizer ran it first. A
golden path that is green only under one fixed order is not a golden path.

Why an external golden path matters here specifically: ``BACKUP_DIR =
/tmp/backups`` (``backend/services/backup_service.py`` ``BACKUP_DIR``) is
*inside* the backend container, so the ZIP is unreachable from outside except
through the download route. The service writes the archive with pure
``zipfile`` — no ``pg_dump``, no subprocess — so this row is fully exercisable
in ``--fake`` mode, which is what makes it a golden path rather than an
operator-only row.

Status: ``xfail(strict=True)``, because every one of these assertions is
downstream of a backup reaching ``completed``, and none can while the
backend defect below stands. Ruling 86: a path that cannot pass demotes its
row to ``half-built`` with the failure cited as the evidence, so the row is
demoted (inventory §3.6, grep anchor ``Backups (create, progress, list,
download, delete)``) and this file stays as the executable pin.

The break, root-caused in the run and mutation-checked: every
``POST /api/backup`` fails as soon as one ``events`` row exists. The job
reaches ``failed`` with ``greenlet_spawn has not been called`` because
``BackupService._export_table`` walks ``mapper.columns`` and ``getattr``s each
one (``backend/services/backup_service.py:331``, ``:336``), and
``Event.reasoning`` / ``Event.llm_prompt`` are ``deferred()``
(``backend/models/event.py:72``, ``:74``), so reading them is synchronous IO
inside an ``AsyncSession``. The mutation control: the same walk with the two
deferred columns skipped exports the seeded row successfully, which is what
rules out "the loop is broken in general". The blast-radius control: no test in
the repo exports a populated ``events`` table through ``BackupService`` --
``backend/tests/unit/services/test_backup_service.py:249`` runs the real
``create_backup`` against ``FakeDB([])`` and asserts at ``:264`` that the
``events`` count is 0, ``backend/tests/integration/test_backup_service.py``
seeds only a Camera (``:37``; no ``Event(`` anywhere in the file), and
``backend/tests/integration/test_backup_restore.py`` does seed Events (``:381``)
but exercises ``create_pg_backup`` (``:123``, pg_dump) — a different
implementation. The cure this path never got is already in the
repo: ``export_service.py:766`` does
``select(Event).options(undefer(Event.reasoning))`` for the same column.

Why ``strict``: a plain ``xfail`` goes green when the defect is fixed, which is
the same silent-drift failure mode this whole inventory exists to catch. Strict
means the day someone lands the fix, this file turns XPASS-red and the row gets
promoted properly rather than quietly. One caveat that follows from the root
cause, stated rather than hidden: on a stack whose ``events`` table is *empty*
the loop body never runs, the backup succeeds, and these tests XPASS. The
feature-check harness always has at least one event by the time golden paths run
(the smoke step asserts its verdict), so CI is deterministic; a hand-run against
a virgin database XPASSing is not a flake, it is the fresh-install health that
kept this defect out of every unit test.
"""

from __future__ import annotations

import io
import json
import time
import zipfile

import httpx
import pytest

# Explicit timeout, not the ini default: pyproject.toml sets ``timeout = 5``, and
# a job that creates a ZIP and polls to completion needs room. ``network`` is the
# repo's marker for specs that talk HTTP to a live stack.
#
# ``xfail`` sits in ``pytestmark`` rather than on each test, because the failure
# fires in the *module fixture* (the create-and-wait that all four tests consume)
# and a per-test marker would have to be repeated four times to cover setup —
# verified empirically that the module-level form reports ``x`` for a fixture
# failure. ``strict`` is the load-bearing word: see the module docstring.
pytestmark = [
    pytest.mark.network,
    pytest.mark.timeout(300),
    pytest.mark.xfail(
        strict=True,
        reason="F-100 demoted to half-built: BackupService._export_table reads the "
        "deferred Event.reasoning / Event.llm_prompt inside an AsyncSession "
        "(backup_service.py:336, event.py:72) -> MissingGreenlet, so every backup "
        "fails once an events row exists. XPASS here means the undefer fix landed "
        "(precedent: export_service.py:766) and this row should be promoted.",
    ),
]

POLL_INTERVAL_S = 2.0
POLL_DEADLINE_S = 180.0

TERMINAL_STATUSES = {"completed", "failed"}


def _start_backup(client: httpx.Client) -> str:
    """``POST /api/backup`` and return the job id.

    The body is an empty object on purpose: ``BackupJobCreate`` declares no
    fields (a full backup exports everything by definition) but the parameter is
    still required, so a POST with no body at all would be a 422 rather than a
    202 — and a spec that sent ``{"tables": [...]}`` would be asserting a
    contract the schema does not have.
    """
    start = client.post("/api/backup", json={})
    assert start.status_code == 202, start.text[:500]
    body = start.json()
    job_id = body["job_id"]
    assert job_id, f"202 without a job_id: {body!r}"
    # The 202 is where the UI learns the job exists and starts polling.
    assert body["status"] == "pending", body
    assert body["message"], body
    return job_id


def _wait_for_terminal(client: httpx.Client, job_id: str) -> dict:
    """Poll ``GET /api/backup/{job_id}`` until the job leaves PENDING/RUNNING.

    Not shared with the export spec even though the shape is similar: a backup
    reports progress as a nested object (``progress.progress_percent``) while an
    export reports flat fields, so a common helper would need its own
    abstraction for one call site each. Failure prints the last progress block,
    which for a backup names the table it stalled on.
    """
    deadline = time.monotonic() + POLL_DEADLINE_S
    last: dict = {}
    while time.monotonic() < deadline:
        response = client.get(f"/api/backup/{job_id}")
        assert response.status_code == 200, response.text[:500]
        last = response.json()
        if last.get("status") in TERMINAL_STATUSES:
            return last
        time.sleep(POLL_INTERVAL_S)
    pytest.fail(
        f"backup job {job_id} did not reach a terminal status within "
        f"{POLL_DEADLINE_S:.0f}s; last: {last!r}"
    )


def _create_and_wait(client: httpx.Client) -> dict:
    """Create a backup and return its terminal job body, carrying ``_job_id``."""
    job_id = _start_backup(client)
    job = _wait_for_terminal(client, job_id)
    assert job["status"] == "completed", (
        f"backup job failed: {job.get('error_message')!r} (job {job_id})"
    )
    job["_job_id"] = job_id
    return job


@pytest.fixture(scope="module")
def completed_backup(logged_in_api: httpx.Client) -> dict:
    """One finished backup, shared by the three non-destructive assertions."""
    return _create_and_wait(logged_in_api)


def test_completed_backup_reports_file_and_manifest(completed_backup: dict) -> None:
    """The status endpoint claims a file and a manifest for the job."""
    job_id = completed_backup["_job_id"]
    assert completed_backup["file_path"], completed_backup
    assert completed_backup["file_size_bytes"] > 0, completed_backup
    manifest = completed_backup.get("manifest")
    assert manifest is not None, f"completed backup has no manifest: {job_id}"
    assert manifest["backup_id"] == job_id, manifest
    # The service exports one entry per table; an empty manifest would mean the
    # ZIP is a container with nothing in it, which downloads "fine".
    assert manifest["contents"], manifest
    for name, entry in manifest["contents"].items():
        assert entry["checksum"], f"table {name!r} has no checksum in the manifest"


def test_completed_backup_appears_in_list_with_download_url(
    logged_in_api: httpx.Client, completed_backup: dict
) -> None:
    """``GET /api/backup`` shows the job and points at the real download route.

    ``list_backups`` filters to COMPLETED rows only, so presence here is also a
    statement that the writer left the job in the state the reader expects. The
    ``download_url`` is a server-issued string, so it gets asserted exactly: a
    list that advertised a path the router does not serve would be a broken UI
    affordance invisible to any unit test.
    """
    listing = logged_in_api.get("/api/backup")
    assert listing.status_code == 200, listing.text[:500]
    body = listing.json()
    job_id = completed_backup["_job_id"]
    mine = [b for b in body["backups"] if b["id"] == job_id]
    assert mine, f"job {job_id} missing from /api/backup ({body['total']} total)"
    entry = mine[0]
    assert entry["status"] == "completed", entry
    assert entry["download_url"] == f"/api/backup/{job_id}/download", entry
    assert body["total"] == len(body["backups"]), body
    assert entry["file_size_bytes"] == completed_backup["file_size_bytes"], entry


def test_download_is_a_zip_whose_manifest_names_this_job(
    logged_in_api: httpx.Client, completed_backup: dict
) -> None:
    """The artefact: a real ZIP whose embedded manifest identifies this job.

    This is the row's load-bearing observable. A job that reports ``completed``
    and 404s here is exactly the "reports success it did not achieve" shape the
    inventory's half-built definition is about. Parsing the archive in memory
    rather than just checksumming bytes, because the interesting contract is
    internal: ``create_backup`` writes ``manifest.json`` with
    ``backup_id = job_id``, so the file proves its own provenance.
    """
    job_id = completed_backup["_job_id"]
    download = logged_in_api.get(f"/api/backup/{job_id}/download")
    assert download.status_code == 200, (
        f"download of a completed backup answered {download.status_code}: {download.text[:300]}"
    )
    assert download.headers.get("content-type", "").startswith("application/zip"), (
        download.headers.get("content-type")
    )
    disposition = download.headers.get("content-disposition", "")
    assert "attachment" in disposition and "backup_" in disposition, disposition

    archive = zipfile.ZipFile(io.BytesIO(download.content))
    names = set(archive.namelist())
    assert "manifest.json" in names, sorted(names)

    manifest = json.loads(archive.read("manifest.json").decode("utf-8"))
    assert manifest["backup_id"] == job_id, manifest
    # Every table the manifest claims was exported must actually be in the
    # archive — the manifest is the index the restore path reads, so an entry
    # without its file is a backup that restores with silent holes.
    missing = [name for name in manifest["contents"] if f"{name}.json" not in names]
    assert not missing, f"manifest lists {missing} but the ZIP has no such member"
    for name in manifest["contents"]:
        payload = json.loads(archive.read(f"{name}.json").decode("utf-8"))
        assert isinstance(payload, list), f"{name}.json is not a JSON array"
    assert len(download.content) == completed_backup["file_size_bytes"], (
        "the size the status endpoint reported is not the size that downloaded"
    )


def test_delete_removes_the_record_and_the_file(logged_in_api: httpx.Client) -> None:
    """The row's fifth call, on a backup created just for it.

    Own job, own file: the module fixture's backup stays intact for the other
    tests no matter what order ``-p randomly`` picks. Three observables, in the
    order a user would notice them — the DELETE answers, the record is gone
    (``_get_backup_job`` 404s once the row is deleted), the list stops
    advertising it, and the download stops serving it, which is the file
    unlink on disk surfacing over HTTP without exec-ing into the container.
    """
    victim = _create_and_wait(logged_in_api)
    job_id = victim["_job_id"]

    deleted = logged_in_api.delete(f"/api/backup/{job_id}")
    assert deleted.status_code == 200, deleted.text[:500]
    assert deleted.json() == {"deleted": True}, deleted.json()

    gone = logged_in_api.get(f"/api/backup/{job_id}")
    assert gone.status_code == 404, f"record survived DELETE: {gone.status_code}"

    listing = logged_in_api.get("/api/backup")
    assert listing.status_code == 200, listing.text[:500]
    ids = {b["id"] for b in listing.json()["backups"]}
    assert job_id not in ids, "deleted backup still listed"

    download = logged_in_api.get(f"/api/backup/{job_id}/download")
    assert download.status_code == 404, (
        f"download still answers {download.status_code} after DELETE — the "
        "record is gone but the file was not unlinked"
    )
