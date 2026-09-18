# WP4.4 Triage Dossier — backend/services/export_service.py

- **Snapshot**: 2026-09-17, meta `mutants/backend/services/export_service.py.meta`. **180 SURVIVED** of 342 checked (828 total; 486 still unchecked — WP4.4 should re-pull the meta before acting; all 180 were diff-verified via `mutmut show`, raw diffs at `/tmp/wp25/wp44-triage/export_service-diffs.txt` + `export_service-diffs2.txt`).
- **Covering test files** (from `mutmut-stats.json` `tests_by_mangled_function_name`):
  - `backend/tests/unit/services/test_export_service.py` (primary; key lines: `test_get_export_service_singleton`:603, `test_get_filename`:631, `test_export_events_csv`:641, `test_export_events_excel`:664, `TestCreateEmptyExport`:1081-1122, `TestExportServiceWithWebSocket`:1125-1345, `test_websocket_method_fetch_undefers_reasoning`:1476)
  - `backend/tests/unit/api/routes/test_detections.py` (`test_export_detections_json_format`:2997)
  - `backend/tests/unit/services/test_export_progress.py` (`test_export_with_progress_updates_job_tracker`:232)
- **Structural note**: `export_events_with_websocket` has *zero production callers* (docstring at `export_service.py:989-991` confirms; grep found none). Its mutants matter for the WP3 cancel-on-push path / future wiring only — several clusters are LOW-VALUE *for that reason* even though the mutation is real. The progress method *is* production-wired and has its own mutant set (not in this module's survivor list — different file, different meta).

## Cluster table (counts sum to 180)

| # | Cluster | n | Class | Pattern (function:line) | Covering tests — what they miss |
|---|---------|---|-------|--------------------------|--------------------------------|
| A | `detections_to_json` body | 4 | **TEST-GAP** | `is None`→`is not None` (614); default columns→None (615); `result=[]`→None (617); `json.dumps(result…)`→dumps(None) (628) | `test_export_detections_json_format` (`test_detections.py:2997`) mocks **empty results** and asserts only `media_type` + Content-Disposition header. Body runs once but nothing asserts the JSON payload. Production caller: `backend/api/routes/detections.py:2165`. |
| B | `detections_to_json` indent | 3 | LOW-VALUE | `indent=2`→None/(dropped)/3 (628) | Cosmetic serialization; nobody should assert whitespace. |
| C | `events_to_csv_streaming` seek | 2 | **TEST-GAP** | `output.seek(0)`→`seek(1)` followed by `output.truncate()` (395,403) | NOT empty — `seek(1);truncate()` keeps the header's first char, so every data chunk is prefixed with a stray `"E"` (from "Event ID"). Streaming tests join chunks (`test_streaming_contains_data` :751) or check only chunk 0, so the contamination rides through; a per-chunk row parse kills both. |
| D | `filter_row_to_dict` content | 5 | **TEST-GAP** | `get_selected_columns(column_names)`→`(None)` (242); `getattr(row,field,None)`→None / getattr(None,…) (245); value→None (248,250) | Only covered via `test_export_with_progress_json/zip_format` (`test_export_service.py:913,:955`) which assert `result["format"]`/`file_path` extension only — never open the file. Direct unit call would kill all 5. |
| E | `filter_row_to_dict` getattr default | 1 | LOW-VALUE | `getattr(row, field, None)`→`getattr(row, field)` (245) | Defensive tweak; all EXTENDED columns exist on `EventExportRow`, so unreachable divergence. |
| F | singleton lifecycle | 3 | **TEST-GAP** | `if _export_service is None`→`is not None` (1184); `_export_service = ExportService()`→None (1185); reset `=None`→`""` (1192) | `test_get_export_service_singleton` (`:603`) only asserts `service1 is service2` — true for None-returns and vacuous after the `""` sentinel (never None again). Never tests reset→re-create. |
| G | `get_filename` delegate | 1 | **TEST-GAP** | `generate_export_filename(prefix,…)`→`(None,…)` (682) | Real rename: `f"{prefix}_..."` renders `"None_20240917_...csv"` — callers (routes building Content-Disposition) get a wrong filename. `test_get_filename` (`:631`) asserts only the `.csv/.xlsx` suffix; adding `assert csv_filename.startswith("events_")` kills it. |
| H | `export_events` delegate columns | 4 | **TEST-GAP** | `events_to_excel(events, columns)`→`(events,None)`/(events,) (701); same for `events_to_csv` (703) | `test_export_events_csv/_excel` (`:641,:664`) never pass `columns` — None mutant falls back to defaults and output is byte-identical. Callers with real columns (routes) not exercised at this seam. |
| I | `_create_empty_export` file content | 4 | **TEST-GAP** | header join sep `,`→`"XX,XX"` (912); `header+"\n"`→`header+"XX\nXX"` (913); `"[]"`→`"XX[]XX"` (917); `writestr(...,"[]")`→`"XX[]XX"` (923) | `TestCreateEmptyExport` (`:1084-1115`) asserts only `file_size > 0` — any content passes. Files are written to real `EXPORT_DIR`; nobody parses them. |
| J | `_create_empty_export` encoding kwarg | 6 | EQUIVALENT | `encoding="utf-8"`→None/(dropped)/`"UTF-8"` (913,917) | `Path.write_text(None)` uses locale default = utf-8 in this stack; `"UTF-8"` == `"utf-8"`. Pure no-op tweaks. |
| K | timestamp format (both methods) | 8 | **LOW-VALUE** | `strftime("%Y%m%d_%H%M%S")`→None/`"XX…XX"`/`"%y%m%d_%h%m%s"`; `now(UTC)`→`now(None)` (906, 1083) | Filename stays `events_export_<digits>.csv` for `None` (literal "None") and the broken-format variants; only the XX-wrapped variant changes the shape, and no test parses the timestamp out of `file_path`. `now(UTC)`→`now(None)` only drops the tz arg (same wall time). Assertable via regex on `file_path` if WP4.4 wants it cheap. |
| L | `_create_empty_export` zip compression | 1 | **TEST-GAP** | `zipfile.ZIP_DEFLATED`→None (922) — `ZipFile` raises `ValueError: compression … not supported` | Covered by `test_create_empty_zip` yet survived → strong hint the mutmut test-selection for this key did not execute the zip case (coverage/selection gap, not assertion weakness). Same drafted test as I also kills it. |
| M | `export_events_with_websocket` ValueError message | 1 | EQUIVALENT | `raise ValueError("Database session required…")`→XX-wrapped (972) | Existing test uses `match="Database session required"` which is a *search* — still matches inside `"XXDatabase session required for export_events_with_websocketXX"`. Equivalent *for the current assertion*; message-text mutants are EQUIVALENT-by-contract here. |
| N | websocket `job.started` metadata/filters | 12 | **TEST-GAP** | `"filters"`→`"FILTERS"/"XXfiltersXX"` + 5 filter keys ×2 case variants each (979-984) | `test_export_with_websocket_starts_reporter` (`:1162`) asserts only `metadata["export_format"]` — the whole `filters` sub-dict is never inspected. WebSocket payload contract for the UI is silently mutated. |
| O | websocket SQL construction | 12 | **TEST-GAP** | `.where(Event.deleted_at.is_(None))`→`.where(None)` (993); `camera_id/risk_level/reviewed is not None`→`is None` (996,999,1014); `select(func.count())`→None/`select(None)`/execute(None) (1018-1019); `order_by(None)` (1038); camera `select(...).where(...)`→None/where(None)/select(None)/`==`→`!=` (1048-1049) | Filter tests (`:997-1077` analogues; websocket has none of these) assert only `mock_db.execute.called`; mocks swallow malformed statements. `test_websocket_method_fetch_undefers_reasoning` (`:1476`) DOES capture stmts but only checks `events.reasoning` in `stmts[1]` — soft-deleted-row filter, active filters, order_by and the camera `==` flip are unchecked. Compile-string asserts kill the `is_(None)`→`where(None)` and `==`→`!=` cases; note `where(None)` is *accepted* by SQLAlchemy (no-op), so it must be a string assert, not a raises-assert. |
| P | `total_count or 0` → `or 1` | 1 | **TEST-GAP** | `result.scalar() or 0`→`or 1` (1020) — scalar()==0 → total becomes 1: empty runs take the full-export path and the completion message misreports | Every websocket test's empty-path assertion (`reporter.complete` called) is also satisfied by the full path when the mocked event query returns empty scalars; no test asserts *which* path ran. |
| Q | websocket `report_progress` call args | 34 | **TEST-GAP** | All 4 report sites (1/"Found N"/force @1022; progress_items/"Processing event i/n" @1072; 80/"Writing {FMT} file…"/force @1078; 95/"Finalizing export…"/force @1136): positional→None/dropped, step→None/text-cases, `force=True`→None/False, 1→2, 80→81, 95→96 | `test_export_with_websocket_reports_progress` (`:1206`) asserts `call_count > 0` only. No test pins any progress value, step text or force flag on this method. |
| R | websocket progress formula | 6 | **TEST-GAP** | `int((idx+1)/total*70)`→None / `/70` / `*(idx+1)*total*70` / `(idx-1)` / `(idx+2)` / `*71` (1071) | Same gap as Q; a single-item run hides `(idx+1)*total*70` — the drafted test uses **two** events to disambiguate. |
| S | empty-run completion summary | 6 | **TEST-GAP** | `result_summary={**export_result,"message":…}`→None (1030); `"message"` key →`XXmessageXX`/`MESSAGE`; value `"No events to export"`→3 case variants (1032) | `test_export_with_websocket_completes_successfully` (`:1184`) asserts `complete` called + return-dict `event_count` — never inspects `result_summary`. |
| T | camera-name fallback | 9 | **TEST-GAP** | `camera_name="Unknown"`→None/3 case variants (1046); `camera_result.scalar() or "Unknown"`→None/`and`/3 variants (1051) | Mocked `camera_result.scalar()` always returns `"Camera"`, so the fallback branches never evaluate in tests; the returned camera name is never asserted into output. |
| U | EventExportRow wiring | 18 | **TEST-GAP** | whole call→None (1053); each kwarg→None (event_id/camera_name/started_at/ended_at/risk_score/risk_level/summary/detection_count/reviewed/object_types/reasoning, 1055-1065); `detection_count or 0`→`and 0`/`or 1`; `reviewed or False`→`and False`/`or True`; object_types/reasoning kwargs dropped | Tests run the loop but assert only `report_progress.call_count` / `file_size>0`. The file content (CSV/JSON) is never opened. |
| V | websocket CSV columns arg | 3 | TEST-GAP | `events_to_csv(export_rows, EXTENDED_EXPORT_COLUMNS)`→`(…,None)`/dropped/`events_to_csv(EXTENDED_EXPORT_COLUMNS)` (1086) | Content never inspected — None falls back to base `EXPORT_COLUMNS` (drops object_types/reasoning headers). Zero-prod-caller mitigates. |
| W | websocket write encoding | 3 | EQUIVALENT | `encoding="utf-8"`→None/(dropped)/"UTF-8" (1089) | Same no-op class as J. |
| X | websocket format-branch strings | 4 | LOW-VALUE | `elif export_format == "json"/"zip"`→case/XX variants (1090,1110) | Would silently route to `else: raise ValueError`, but `test_export_with_websocket_invalid_format` only exercises format `"invalid"`; real "json"/"zip" websocket runs untested (zero prod callers). |
| Y | websocket result dict | 9 | **TEST-GAP** | `file_size = filepath.stat().st_size`→None (1140); result keys `file_path/file_size/event_count/format`→case/XX variants (1143-1148) | `test_export_with_websocket_includes_duration` (`:1306`) asserts only `duration_seconds`; key renames and `file_size=None` ride through. Cheap to kill by strengthening that existing test. |
| Z | completion `logger.info` extras | 16 | LOW-VALUE | log message text ×4 + all 5 `extra{...}` keys ×2-3 variants (1151-1160) | Structured-log message/key text; nobody should assert log formatting. |
| AA | `complete(result_summary=export_result)`→None | 1 | TEST-GAP | (1163) success path completion payload dropped | `complete` presence is asserted, payload never — same gap as S. Killed by drafted test T1/T5. |
| AB | `fail(e, retryable=False)` variants | 3 | **LOW-VALUE** | `retryable=False`→None / dropped / True (1169) — None/False are falsy-identical at every consumer; `True` flips the UI "retry offered" flag on failed exports | `test_export_with_websocket_handles_exception` (`:1246`) asserts `fail` called + exception type, not the `retryable` kwarg. |

**Classification totals (partition machine-validated against the meta: 180/180, no key in two clusters):**
- TEST-GAP: C2 + A4 + D5 + F3 + G1 + H4 + I4 + L1 + N12 + O12 + P1 + Q34 + R6 + S6 + T9 + U18 + V3 + Y9 + AA1 = **135**
- LOW-VALUE: B3 + E1 + K8 + X4 + Z16 + AB3 = **35**
- EQUIVALENT: J6 + M1 + W3 = **10**
- 135 + 35 + 10 = **180** ✔ (Q key set = {39–46, 113–127, 158–168} = 34 keys.)

## Drafted tests (UNVERIFIED — not yet run red/green)

TDD procedure (same for all): add the test, run it against the *mutant* source for a key in the target cluster → assertion must FAIL; run against `backend/services/export_service.py` original → must PASS. Then wire into the module's test file and re-run the file green.

### T1 — websocket row wiring (kills U×18, T-fallback half, AA×1) → `backend/tests/unit/services/test_export_service.py`, class `TestExportServiceWithWebSocket` (after `test_export_with_websocket_includes_duration`, :1346)

```python
    async def test_websocket_row_wiring_preserves_event_fields(
        self, mock_db, mock_progress_reporter
    ):
        # UNVERIFIED - not yet run red/green
        """Each EventExportRow field must be wired from the Event (not stubbed
        None / dropped), including the `detection_count or 0` and
        `reviewed or False` fallbacks; the JSON file is the observable sink.
        Also locks complete(result_summary=<real dict>)."""
        import json
        from pathlib import Path
        from unittest.mock import AsyncMock, MagicMock

        from backend.services.export_service import EXPORT_DIR

        event = MagicMock()
        event.id = 42
        event.camera_id = "cam-1"
        event.started_at = datetime(2024, 1, 15, 10, 30, 0, tzinfo=UTC)
        event.ended_at = datetime(2024, 1, 15, 10, 31, 30, tzinfo=UTC)
        event.risk_score = 77
        event.risk_level = "high"
        event.summary = "Person in driveway"
        event.detection_count = None  # exercises `or 0`
        event.reviewed = None  # exercises `or False`
        event.object_types = "person,vehicle"
        event.reasoning = "loitering near garage"

        event_result = MagicMock()
        event_result.scalars.return_value.all.return_value = [event]
        camera_result = MagicMock()
        camera_result.scalar.return_value = "Driveway Cam"
        count_result = MagicMock()
        count_result.scalar.return_value = 1
        mock_db.execute = AsyncMock(side_effect=[count_result, event_result, camera_result])

        service = ExportService(db=mock_db)
        result = await service.export_events_with_websocket(
            progress_reporter=mock_progress_reporter,
            export_format="json",
        )

        payload = json.loads((EXPORT_DIR / Path(result["file_path"]).name).read_text(encoding="utf-8"))
        row = payload[0]
        assert row["event_id"] == 42
        assert row["camera_name"] == "Driveway Cam"
        assert row["started_at"] == "2024-01-15T10:30:00+00:00"
        assert row["ended_at"] == "2024-01-15T10:31:30+00:00"
        assert row["risk_score"] == 77
        assert row["risk_level"] == "high"
        assert row["summary"] == "Person in driveway"
        assert row["detection_count"] == 0  # `event.detection_count or 0`
        assert row["reviewed"] is False  # `event.reviewed or False`
        assert row["object_types"] == "person,vehicle"
        assert row["reasoning"] == "loitering near garage"

        summary = mock_progress_reporter.complete.call_args[1]["result_summary"]
        assert summary["file_path"] == result["file_path"]
        assert summary["event_count"] == 1
```
Red-proofs: every kwarg→None variant nulls a JSON field; `or 1`/`and 0` (detection_count=None → `None and 0` = None) / `or True` / `and False` (→None) all violate the two fallback asserts; dropped object_types/reasoning kwargs fall back to dataclass defaults None; whole-call→None raises TypeError; 199 makes `complete.call_args[1]` lack `result_summary` → KeyError.

### T2 — `_create_empty_export` byte-exact contents (kills I×4, L×1) → class `TestCreateEmptyExport` (:1081)

```python
    async def test_create_empty_export_writes_expected_file_contents(
        self, tmp_path, monkeypatch
    ):
        # UNVERIFIED - not yet run red/green
        """Header-only CSV must be exactly the comma-joined EXTENDED header;
        empty JSON must be exactly '[]'; the zip member must be exactly b'[]'.
        Also pins ZIP_DEFLATED (compression=None makes ZipFile raise)."""
        import csv
        import io
        import zipfile
        from pathlib import Path

        import backend.services.export_service as export_module
        from backend.services.export_service import EXTENDED_EXPORT_COLUMNS

        monkeypatch.setattr(export_module, "EXPORT_DIR", tmp_path)
        service = ExportService()

        csv_result = await service._create_empty_export("csv")
        csv_text = (tmp_path / Path(csv_result["file_path"]).name).read_text(encoding="utf-8")
        assert list(csv.reader(io.StringIO(csv_text))) == [[c[1] for c in EXTENDED_EXPORT_COLUMNS]]

        json_result = await service._create_empty_export("json")
        assert (tmp_path / Path(json_result["file_path"]).name).read_text(encoding="utf-8") == "[]"

        zip_result = await service._create_empty_export("zip")
        with zipfile.ZipFile(tmp_path / Path(zip_result["file_path"]).name) as zf:
            assert zf.read(zf.namelist()[0]) == b"[]"
```
Red-proofs: `"XX,XX".join` breaks the csv.reader parse equality; `header+"XX\nXX"` adds rows; `"XX[]XX"` breaks both `== "[]"` asserts (json side as text AND raises json-context contract); compression=None → `ZipFile.__init__` ValueError before the zip is even created. (EXPORT_DIR is a module global read at call time — monkeypatch holds.)

### T3 — singleton reset lifecycle (kills F×3) → class `TestExportService` (:593, inherits autouse `reset_service`)

```python
    def test_get_export_service_returns_new_instance_after_reset(self):
        # UNVERIFIED - not yet run red/green
        """reset_export_service() must sever the cached singleton so the next
        get_export_service() re-creates a REAL instance (kills inverted cache
        check, None-assignment, and the '' falsy-but-never-None sentinel)."""
        first = get_export_service()
        assert isinstance(first, ExportService)
        assert get_export_service() is first

        reset_export_service()

        second = get_export_service()
        assert isinstance(second, ExportService)
        assert second is not first
```
Red-proofs: `is not None` inversion / `= None` → `isinstance(..., ExportService)` fails; reset-to-`""` → second call returns `""` (not None → no rebuild) → both isinstance and `is not first` fail.

### T4 — `export_events` columns pass-through (kills H×4) → class `TestExportService` (:593)

```python
    def test_export_events_honors_custom_columns(self):
        # UNVERIFIED - not yet run red/green
        """The columns argument must reach events_to_csv / events_to_excel;
        None-mutants silently fall back to the 9-column default set."""
        import io

        from openpyxl import load_workbook

        service = ExportService()
        events = [
            EventExportRow(
                event_id=1,
                camera_name="Test",
                started_at=datetime(2024, 1, 15, 10, 30, 0, tzinfo=UTC),
                ended_at=None,
                risk_score=50,
                risk_level="medium",
                summary="Test event",
                detection_count=1,
                reviewed=False,
            ),
        ]
        columns = [("event_id", "ID"), ("camera_name", "Camera")]

        content = service.export_events(events, ExportFormat.CSV, columns=columns)
        assert "Summary" not in content  # default fallback would add the Summary header
        assert "Risk" not in content

        data = service.export_events(events, ExportFormat.EXCEL, columns=columns)
        ws = load_workbook(io.BytesIO(data)).active
        assert ws.cell(row=1, column=1).value == "ID"
        assert ws.cell(row=1, column=3).value is None  # only 2 columns survived
```
(Do NOT assert `"ID,Camera" in content` for the CSV side — the default header "Event ID,Camera" contains that substring; the absence asserts are the sound ones.)

### T5 — websocket progress ladder + filters metadata + completion summary (kills Q×34, R×6, N×12, S×6, P×1 — also T's fallback via scenario B) → class `TestExportServiceWithWebSocket` (:1125)

```python
    async def test_websocket_progress_ladder_filter_metadata_and_summary(
        self, mock_db, mock_progress_reporter
    ):
        # UNVERIFIED - not yet run red/green
        """Reporter contract for export_events_with_websocket:
        - job.started metadata echoes the filter set under the exact keys;
        - empty run: progress 1 + 'Found 0 events to export' + force=True,
          complete(result_summary=export_result + {'message': 'No events to export'});
        - non-empty run (2 events disambiguate the int((idx+1)/total*70)
          formula): ladder 1 → 35 → 70 → 80 → 95 with exact step texts and
          force flags on the 80/95 steps. Kills every report_progress arg,
          formula, metadata-key, summary and path-selection (or 1) mutant."""
        from unittest.mock import AsyncMock, MagicMock

        # --- empty scenario ---
        count_result = MagicMock()
        count_result.scalar.return_value = 0
        mock_db.execute = AsyncMock(return_value=count_result)

        service = ExportService(db=mock_db)
        await service.export_events_with_websocket(
            progress_reporter=mock_progress_reporter,
            export_format="csv",
            camera_id="cam-9",
            risk_level="high",
            start_date="2024-01-15T00:00:00Z",
            end_date="2024-01-16T00:00:00Z",
            reviewed=True,
        )

        meta = mock_progress_reporter.start.call_args[1]["metadata"]
        assert meta["export_format"] == "csv"
        assert meta["filters"] == {
            "camera_id": "cam-9",
            "risk_level": "high",
            "start_date": "2024-01-15T00:00:00Z",
            "end_date": "2024-01-16T00:00:00Z",
            "reviewed": True,
        }
        first = mock_progress_reporter.report_progress.call_args_list[0]
        assert first[0][0] == 1
        assert first[1]["current_step"] == "Found 0 events to export"
        assert first[1]["force"] is True
        summary = mock_progress_reporter.complete.call_args[1]["result_summary"]
        assert summary["message"] == "No events to export"
        assert summary["event_count"] == 0

        # --- non-empty scenario: 2 events ---
        def _mk_event(n):
            ev = MagicMock()
            ev.id = n
            ev.camera_id = f"cam-{n}"
            ev.started_at = datetime(2024, 1, 15, 10, 30, 0, tzinfo=UTC)
            ev.ended_at = None
            ev.risk_score = 50
            ev.risk_level = "medium"
            ev.summary = f"E{n}"
            ev.detection_count = 1
            ev.reviewed = False
            ev.object_types = None
            ev.reasoning = None
            return ev

        event_result = MagicMock()
        event_result.scalars.return_value.all.return_value = [_mk_event(1), _mk_event(2)]
        camera_result = MagicMock()
        camera_result.scalar.return_value = "Cam"
        count2 = MagicMock()
        count2.scalar.return_value = 2
        mock_db.execute = AsyncMock(
            side_effect=[count2, event_result, camera_result, camera_result]
        )

        reporter = MagicMock()
        reporter.start = AsyncMock()
        reporter.report_progress = AsyncMock()
        reporter.complete = AsyncMock()
        reporter.fail = AsyncMock()
        reporter.job_id = "ladder-job"
        reporter.duration_seconds = 1.0

        await service.export_events_with_websocket(
            progress_reporter=reporter, export_format="csv"
        )

        calls = reporter.report_progress.call_args_list
        assert [c[0][0] for c in calls] == [1, 35, 70, 80, 95]
        assert calls[1][1]["current_step"] == "Processing event 1/2"
        assert calls[2][1]["current_step"] == "Processing event 2/2"
        assert calls[3][1]["current_step"] == "Writing CSV file..."
        assert calls[3][1]["force"] is True
        assert calls[4][1]["current_step"] == "Finalizing export..."
        assert calls[4][1]["force"] is True
```
Formula disambiguation with total=2: `/70`→[0,0]; `(idx+1)*total*70`→[140,280]; `(idx-1)`→[0,35]; `(idx+2)`→[70,105]; `*71`→[35,71]. P-kill: `or 1` on the empty scenario makes it take the fetch path, so `complete` summary lacks "message" → KeyError.

### T6 — `filter_row_to_dict` direct unit coverage (kills D×5; E×1 NOT killable — see note) → new class after `TestEventsToCSVStreaming` (:786) in `backend/tests/unit/services/test_export_service.py`

```python
class TestFilterRowToDict:
    """Direct unit coverage for the json/zip column filter (progress + websocket exports)."""

    ROW = None  # built per-test

    def _row(self):
        return EventExportRow(
            event_id=7,
            camera_name="Front Door",
            started_at=datetime(2024, 1, 15, 10, 30, 0, tzinfo=UTC),
            ended_at=None,
            risk_score=60,
            risk_level="medium",
            summary="Test",
            detection_count=2,
            reviewed=True,
            object_types="person",
            reasoning="because",
        )

    def test_selects_columns_and_isoformats_datetimes(self):
        # UNVERIFIED - not yet run red/green
        """None → all columns with datetime isoformatting; a name list → exactly
        those columns in order; all-invalid names → full set (documented fallback)."""
        from backend.services.export_service import filter_row_to_dict

        row = self._row()
        full = filter_row_to_dict(row, None)
        assert full["started_at"] == "2024-01-15T10:30:00+00:00"
        assert full["ended_at"] is None
        assert full["event_id"] == 7
        assert full["reasoning"] == "because"

        selected = filter_row_to_dict(row, ["event_id", "reasoning"])
        assert selected == {"event_id": 7, "reasoning": "because"}

        assert filter_row_to_dict(row, ["nope"]) == full
```
Red-proofs: `get_selected_columns(None)` mutant makes `selected == full` (≠ 2-key dict); value→None mutants null every field; isoformat→None breaks the started_at assert.

## Weaker-but-cheap follow-ups (not drafted, WP4.4 backlog)

- **Y×9 / T-remaining ×6**: strengthen `test_export_with_websocket_includes_duration` (`test_export_service.py:1306`) with `assert result["file_size"] > 0; assert result["format"] == "csv"; assert result["event_count"] == 1; assert result["file_path"].endswith(".csv")` and, with `camera_result.scalar.return_value = None`, `assert "Unknown" in <file content>` (kills T case variants + fallback operators).
- **O×12**: extend `test_websocket_method_fetch_undefers_reasoning` (`:1476`) to also assert `"events.deleted_at IS NULL" in str(stmts[0].compile())` (kills the `where(None)` soft-delete drop), `"ORDER BY events.started_at DESC"` in `stmts[1]`, camera stmt `str(stmts[2])` contains `cameras.id = :param_1` (kills `!=` flip), and pass `camera_id="cam-1", reviewed=True` with a filters-on test asserting the compiled WHERE text.
- **A×4**: raise `test_export_detections_json_format` (`test_detections.py:2997`) from empty-mocks to one mocked detection and assert the returned StreamingResponse body parses to a JSON array whose element carries `detection_id` and the default column set.
- **AB×3**: if the UI honors `retryable`, add `assert call_args[1]["retryable"] is False` to `test_export_with_websocket_handles_exception` (:1263) — one line, kills 2 of 3 (the `True` flip; None/dropped are falsy-identical).
- **C×2**: in each `TestEventsToCSVStreaming` test that reads data chunks, assert each post-header chunk parses as exactly one clean CSV row: `rows = list(csv.reader(io.StringIO(chunks[1]))); assert len(rows) == 1 and rows[0][0] == "1"` — kills both `seek(1)` mutants (their chunks start with a stray `"E"`).
- **G×1**: add `assert csv_filename.startswith("events_")` to `test_get_filename` (`test_export_service.py:631`).
- **J, M, W, E, B**: do not bother — EQUIVALENT/LOW-VALUE. Consider marking for the mutmut `skip` list if WP4.4 supports annotation, or leaving as permanent score loss.

## Caveats

- Meta was mid-write during triage: survivor count grew 106→180 during the session (WP4.3 checker advancing). Snapshot at close: 180 survivors / 342 checked / 486 unchecked. **Re-pull the meta before WP4.4 implementation** — unchecked keys may add new survivors (pattern-wise they will fold into clusters A–AC).
- `test_export_service.py` uses module-global `EXPORT_DIR = Path("/tmp/exports")`; drafted tests either read from it (T1/T5, same convention as existing tests) or monkeypatch it (T2). Keep T2's monkeypatch — the file-content asserts are the whole point.
- Existing tests use `MagicMock()` event fixtures; the `or 0`/`or False` fallbacks have never seen `None` inputs (always int/bool), which is why U's operator mutants survived silently.
