"""F-298 — the detections-export row: the documented export endpoint really
serves a CSV and a JSON of detections under content negotiation.

Inventory row: ``docs/reference/feature-inventory.md`` §3.13, grep anchor
``GET /api/detections/export`` (count 1 in the doc).

Documented contract (``docs/developer/api/core-resources.md`` "Export
detections"): ``GET /api/detections/export`` with Accept-based negotiation —
``text/csv``/``application/csv`` → CSV, ``application/json`` → JSON, anything
else → CSV fallback — implemented by ``backend/api/routes/detections.py``
``export_detections`` + ``backend/services/export_service.py``. The rows the
service writes are pinned here by *display header*, read from the code
(``DETECTION_EXPORT_COLUMNS``), not from the doc: the doc's CSV example shows
a ``thumbnail_path`` column the code's column list does not contain — a
doc-vs-code discrepancy this spec refuses to paper over by asserting either
side as gospel. The 11 names the code writes are the contract a rename
breaks.

Also asserted: the attachment disposition prefix, the JSON shape (array of
objects keyed by the same field names), the EXCEL accept → CSV demotion, and
the 400 an inverted date range must get. Not asserted: the 429. The endpoint
documents "rate-limited to 10 requests/minute" but the middleware fails OPEN
on Redis errors (``backend/api/middleware/rate_limit.py``), so a 429 is
documented, not deterministic — recorded in the row's evidence, not tested.
"""

from __future__ import annotations

import csv
import io
import json
from typing import Any

import httpx
import pytest

pytestmark = [pytest.mark.network, pytest.mark.timeout(120)]

EXPORT_PATH = "/api/detections/export"

# The display header the code writes (export_service.DETECTION_EXPORT_COLUMNS,
# in order). Read the names out of the CSV response, not out of this list: the
# assertion is that the served header equals the pinned list, so a rename or a
# reorder anywhere upstream fails here.
EXPECTED_CSV_HEADER: list[str] = [
    "Detection ID",
    "Camera",
    "Detected At",
    "Object Type",
    "Confidence",
    "Bbox X",
    "Bbox Y",
    "Bbox Width",
    "Bbox Height",
    "File Path",
    "Media Type",
]

# The JSON export keys rows by field name (detections_to_json), not display
# name — the snake_case halves of the same tuples.
EXPECTED_JSON_KEYS: list[str] = [
    "detection_id",
    "camera_name",
    "detected_at",
    "object_type",
    "confidence",
    "bbox_x",
    "bbox_y",
    "bbox_width",
    "bbox_height",
    "file_path",
    "media_type",
]

# The disposition filename starts with this prefix (generate_export_filename
# stamps a UTC timestamp inside it, which is not asserted).
EXPECTED_FILENAME_PREFIX = "detections_export_"

EXCEL_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _disposition_filename(response: httpx.Response) -> str:
    """The filename the Content-Disposition header names, asserted as present."""
    disposition = response.headers.get("content-disposition", "")
    assert disposition.startswith("attachment;"), disposition
    assert f'filename="{EXPECTED_FILENAME_PREFIX}' in disposition, disposition
    filename = disposition.split('filename="', 1)[1].split('"', 1)[0]
    assert filename.startswith(EXPECTED_FILENAME_PREFIX), disposition
    return filename


def test_f298_default_export_answers_csv_with_the_pinned_header(
    api: httpx.Client,
) -> None:
    """A bare GET is CSV, with the header the code's column list writes.

    The doc's example shows a 12-column CSV including ``thumbnail_path``; the
    code's column list has 11 and no thumbnail. This assertion pins the code
    (the served artefact), so the row's evidence records the discrepancy
    instead of this spec guessing which side is right.
    """
    response = api.get(EXPORT_PATH)
    assert response.status_code == 200, response.text[:500]
    assert response.headers["content-type"].startswith("text/csv"), response.headers
    _disposition_filename(response)
    rows = list(csv.reader(io.StringIO(response.text)))
    assert rows, "empty CSV body"
    assert rows[0] == EXPECTED_CSV_HEADER, f"served header {rows[0]!r}"


def test_f298_json_export_is_an_array_keyed_by_the_field_names(
    api: httpx.Client,
) -> None:
    """Accept: application/json answers JSON, an array of field-keyed objects."""
    response = api.get(EXPORT_PATH, headers={"Accept": "application/json"})
    assert response.status_code == 200, response.text[:500]
    assert response.headers["content-type"].startswith("application/json"), response.headers
    _disposition_filename(response)
    payload: Any = json.loads(response.text)
    assert isinstance(payload, list), type(payload).__name__
    assert len(payload) >= 1, "an export of a live stack has at least the smoke detection"
    keys = set(payload[0])
    assert keys == set(EXPECTED_JSON_KEYS), f"served keys {sorted(keys)!r}"
    for item in payload:
        assert set(item) == keys, "rows disagree on their key sets"


def test_f298_excel_accept_falls_back_to_csv(api: httpx.Client) -> None:
    """The route demotes the EXCEL format to CSV rather than serving a workbook."""
    response = api.get(EXPORT_PATH, headers={"Accept": EXCEL_MIME})
    assert response.status_code == 200, response.text[:500]
    assert response.headers["content-type"].startswith("text/csv"), response.headers
    rows = list(csv.reader(io.StringIO(response.text)))
    assert rows and rows[0] == EXPECTED_CSV_HEADER, f"served header {rows[:1]!r}"


def test_f298_inverted_date_range_answers_400(api: httpx.Client) -> None:
    """start after end is a 400, not an empty 200 that reads as a quiet all-clear."""
    response = api.get(
        EXPORT_PATH,
        params={
            "start_date": "2026-01-02T00:00:00Z",
            "end_date": "2026-01-01T00:00:00Z",
        },
    )
    assert response.status_code == 400, response.text[:500]
