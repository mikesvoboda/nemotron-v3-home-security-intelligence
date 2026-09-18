# WP4.4 Triage Dossier — `backend/services/export_service.py`

**Survivors:** 398 of 828 checked mutants (430 killed). Meta read clean, no JSONDecodeError retries needed.
**Method:** per-mutant diffs extracted OFFLINE by diffing each `__mutmut_N` block in
`mutants/backend/services/export_service.py` against its `__mutmut_orig` block
(`/tmp/wp25/wp44-triage/export_diffs.py` → `export_service_diffs.json`); `mutmut show` verified on
one key and agrees. Cluster assignment machine-verified: 60 clusters, no overlaps, counts sum to exactly 398
(`clusters_final.json`, `cluster_rows.txt`).
**Verdict totals:** TEST-GAP 226 · LOW-VALUE 138 · EQUIVALENT 34.

## Covering test files (from `mutmut-stats.json → tests_by_mangled_function_name`)

| Function | Covering tests (file :: class) |
|---|---|
| `export_events_with_progress` (2424-2508 src, 722-) | `backend/tests/unit/services/test_export_service.py` :: `TestExportServiceWithProgress` (:789), `TestExportDeferredColumns` (:1394); 1 test in `backend/tests/unit/services/test_export_progress.py` |
| `export_events_with_websocket` (934-) | same file :: `TestExportServiceWithWebSocket` (:1126), `TestExportDeferredColumns` |
| `_create_empty_export` (894-) | same :: `TestCreateEmptyExport` (:1081) |
| `events_to_excel` (407-) | same :: `TestEventsToExcel` (:448); `backend/tests/unit/api/routes/test_events_export.py`; `test_events_coverage.py` |
| `events_to_csv` / `events_to_csv_streaming` (303/369) | same :: `TestEventsToCSV` (:360), `TestEventsToCSVStreaming` (:701); routes tests |
| `filter_row_to_dict` (232) | same file (2 tests; JSON/zip progress paths only) |
| `detections_to_json` (600) | `backend/tests/unit/api/routes/test_detections.py` (1 test, content asserted) |
| `parse_accept_header` (297) | same :: `TestParseAcceptHeader` (:109, 16 tests); routes tests |
| `get_export_service` (1177) / `reset_export_service` (1189) | same :: `TestExportService` (:593) |
| `export_events` (684) / `get_filename` (672) | same :: `TestExportService` |
| `format_export_value` (257) / `generate_export_filename` (275) | same :: `TestFormatExportValue`, `TestGenerateExportFilename` |

The systemic gap: `test_export_service.py` drives every DB-backed method through an `AsyncMock`
whose results are canned per `execute` call, and then asserts only the **returned dict**
(`file_path` extension, `file_size > 0`, `format`) and `assert mock_db.execute.called` /
`call_count > 0`. It **never reads back the written file** and **never inspects the executed
SQL text** (the R-T9 deferred-columns tests at :1394 are the sole precedent for SQL-text
assertions — the pattern my drafts extend). Everything real that a mutant changes in the file
bytes or in the compiled SQL therefore survives.

## Cluster table (60 clusters, counts sum to 398)

| ID | Pattern (function / mutation kind) | N | Class | Example keys (≤3) | Note / covering-test gap |
|---|---|---|---|---|---|
| WS-PROG | `export_events_with_websocket`: progress-value/step/force tweaks on all 4 `report_progress` call sites (:1022/:1072/:1078/:1136) + `progress_items = int((idx+1)/total*70)` (:1071) + `complete(result_summary=None)` (:1163) | 32 | TEST-GAP | ...websocket__mutmut_38, _106, _125 | tests assert only `report_progress.call_count > 0`; sequence/values never checked → drafted test kills ~28 |
| ROW-FIELDS-P | `export_events_with_progress`: one field of `EventExportRow(...)` (:818-829) nulled, camera lookup (:810-815) nulled/tweaked, `or 0`/`or False` flips (:826-827) | 31 | TEST-GAP | ...with_progress__mutmut_100, _107, _123 | CSV/JSON file content never asserted → drafted content test |
| ROW-FIELDS-W | `export_events_with_websocket`: identical row-construction mutations (:1046-1063) | 31 | TEST-GAP | ...websocket__mutmut_80, _102, _105 | same: file content never asserted |
| SQL-FILTER | `export_events_with_progress`: filter-clause mutations — `deleted_at.is_(None)`→where(None) (:766), `is not None`→`is None` (:768/:771/:786), `where(cond)`→where(None) or `!=` (:769-787), `>=`→`>` (:778), `<=`→`<` (:784), `order_by(desc)`→`order_by(None)` (:802) | 15 | TEST-GAP | ...with_progress__mutmut_7, _14, _31 | tests pass filters then assert only `execute.called` — SQL text never compiled |
| PROG-PCT | `export_events_with_progress`: progress-percentage arithmetic/params — `update_progress(job_id, 50/10/80/95, ...)` pct ±1, arg drop/None, `(idx+1)%INTERVAL` flips (:795-873) | 14 | TEST-GAP | ...with_progress__mutmut_59, _129, _137 | tracker is a bare MagicMock; pct values never asserted |
| WS-META | `export_events_with_websocket`: `start(metadata=...)` filters-dict key renames/casing (:979-985) | 12 | TEST-GAP | ...websocket__mutmut_9, _11, _20 | test checks `metadata["export_format"]` only — the `filters` sub-dict is frontend contract |
| XL-CELLS | `events_to_excel`: cell-value logic (:472/:474) — tz-strip→None, `Yes`/`No` bool formatting flipped/case-flipped/None | 10 | TEST-GAP | ...x_events_to_excel__mutmut_112, _114, _119 | Excel tests assert ids/camera names only, never bool/datetime columns → drafted |
| FILE-CONTENT-P | `export_events_with_progress`: JSON/zip content mutations — `content_dict = None` (:852/:858), `filter_row_to_dict(None/None args)` (:852), `json.dumps(None...)` (:855/:864), wrong-arity `events_to_csv(selected_columns)` (:848) | 9 | TEST-GAP | ...with_progress__mutmut_153, _167, _210 | written file/zip member never read back → killed by drafted content test |
| WS-RESULT | `export_events_with_websocket`: result-summary dict mutations — `file_size=None` (:1140), `file_path`/key casing renames (:1148-1152) | 9 | TEST-GAP | ...websocket__mutmut_169, _172, _174 | `duration_seconds` asserted; the rest of `export_result` never |
| WS-EMPTY | `export_events_with_websocket`: empty-path `complete(result_summary=None)` (:1029) + `"No events to export"` message/value renames (:1030-1032) | 6 | TEST-GAP | ...websocket__mutmut_51, _52, _54 | test asserts `complete.assert_called_once()` only, payload unchecked |
| ACCEPT-QP | `parse_accept_header`: `split(";")`→split(None)/clobbered ("XX;XX") (:324) — quality-param stripping | 2 | TEST-GAP | x_parse_accept_header__mutmut_6, _7 | existing `test_accept_header_with_quality_values` (:158) evidently uses a CSV header whose mutant outcome is the CSV fallback → drafted JSON;q test |
| SQL-COUNT | `export_events_with_progress`: count-pipeline mutations — `count_query=None/select(None)` (:790), `execute(None)` (:791), `total_count=None`/`or 1` (:792) | 5 | TEST-GAP | ...with_progress__mutmut_49, _51, _56 | count stmt never inspected; `or 1` shifts every progress pct (killed by SQL+progress tests) |
| SQL-FILTER-W | `export_events_with_websocket`: same filter-clause mutations (:993-1014, order_by :1037) | 5 | TEST-GAP | ...websocket__mutmut_22, _26, _30 | same SQL-text gap |
| SQL-COUNT-W | `export_events_with_websocket`: count-pipeline mutations (:1018-1020) | 3 | TEST-GAP | ...websocket__mutmut_31, _33, _35 | same |
| FILENAME-P | `export_events_with_progress`: timestamp clobber `%Y%m%d_%H%M%S`→XX-wrapped/`%y%m%d_%h%m%s` (:843) | 3 | TEST-GAP | ...with_progress__mutmut_139, _142, _143 | `file_path` checked by extension only |
| FILENAME-W | `export_events_with_websocket`: same timestamp clobbers (:1083) | 3 | TEST-GAP | ...websocket__mutmut_128, _131, _132 | same |
| FILENAME-GEN | `generate_export_filename` (:292): `datetime.now(UTC)`→`datetime.now(None)` — naive-timestamp filenames | 1 | LOW-VALUE | x_generate_export_filename__mutmut_3 | naive vs aware timestamp differs by machine tz only; local single-user app, machine is UTC — behavior nobody should pin |
| COLUMNS | `export_events_with_progress`: `selected_columns=None` (:844), `events_to_csv(export_rows, None)` (:848) — column-selection loss | 3 | TEST-GAP | ...with_progress__mutmut_145, _152, _154 | `get_selected_columns(None)` falls back to EXTENDED — real loss is the *custom-columns* path, never exercised; killed by drafted content test (column list asserted) |
| FILE-CONTENT-W | `export_events_with_websocket`: `events_to_csv(export_rows, EXTENDED→None)` / wrong-arity (:1087) | 3 | TEST-GAP | ...websocket__mutmut_139, _140, _141 | file content never read back |
| FMT-BRANCH | `export_events_with_websocket`: format-branch comparisons `== "json"`/`== "zip"` → clobber/uppercase (:1091/:1111) | 4 | TEST-GAP | ...websocket__mutmut_152, _153, _155 | json/zip branches of the ws method untested; `"JSON"`-branch mutants silently fall through to the `raise ValueError` path — real format-loss bug |
| WS-FAIL | `export_events_with_websocket`: `fail(e, retryable=False)`→None(:1169, TypeError)/True (:1169) | 2 | TEST-GAP | ...websocket__mutmut_201, _204 | existing exception test (:1246) asserts call + error type, ignores `retryable` (job-retry contract) |
| GF-PREFIX | `ExportService.get_filename` (:681): prefix arg→None | 1 | TEST-GAP | ...get_filename__mutmut_1 | test asserts only `.endswith(".csv")` — prefix never checked |
| SINGLETON | `get_export_service` (:1184): `is None`→`is not None`; `_export_service=None` (return None) | 2 | TEST-GAP | x_get_export_service__mutmut_1, _2 | existing test calls twice then `is` — passes under both mutants (None-identity still equal; `not None` path still memoizes) |
| DJ-COLS | `detections_to_json` (:614): `if columns is None`→`is not None` (:1), `columns=None`-default lost (:2) | 2 | TEST-GAP | x_detections_to_json__mutmut_1, _2 | sole covering test (test_detections.py) passes explicit columns, default path unasserted |
| DJ-CONTENT | `detections_to_json`: `result=None` (:3), `json.dumps(None)` (:4) | 2 | TEST-GAP | x_detections_to_json__mutmut_3, _4 | same — default-path content never produced |
| CSV-SEEK | `events_to_csv_streaming` (:395): `output.seek(0)`→`seek(1)` on **both** sites | 2 | TEST-GAP | x_events_to_csv_streaming__mutmut_10, _19 | `seek(1)` leaves 1 stale byte → **byte-wise corruption of every yielded row**; streaming tests assert substring presence only. Cheapest kill: join chunks and parse |
| FD-VALUE | `filter_row_to_dict` (:236): `value=None`/`getattr(None,...)`/datetime branch→None (:240-242) | 4 | TEST-GAP | x_filter_row_to_dict__mutmut_4, _10, _11 | no direct unit test; progress paths assert file paths, not JSON content |
| ACCEPT-WILD | `parse_accept_header` (:330): `in`→`not in`, wildcard-entry clobbers | 4 | EQUIVALENT | x_parse_accept_header__mutmut_10, _11, _12 | every wildcard input (`*/*`, `text/*`) returns CSV either way — wildcard branch masked by CSV-default branch |
| EMPTY-CONTENT | `_create_empty_export` (:910-923): CSV header separator `","`→`"XX,XX"`, header newline, `write_text("XX[]XX")` invalid JSON, zip member content | 4 | TEST-GAP | ..._create_empty_export__mutmut_15, _22, _35 | empty-export tests assert size/format only, content never parsed |
| EMPTY-FILENAME | `_create_empty_export` (:906): timestamp clobbers | 3 | TEST-GAP | ..._create_empty_export__mutmut_1, _4, _5 | `file_path` endswith-extension check only |
| EE-COLUMNS | `ExportService.export_events` (:701/:703): `columns` arg→None at both dispatch sites | 4 | TEST-GAP | ...export_events__mutmut_3, _7 | tests never pass custom columns through the service method |
| XL-STRIPE | `events_to_excel` (:487): `row_idx % 2 == 0` banding predicate flips (/2, %3, !=, ==1) | 4 | LOW-VALUE | x_events_to_excel__mutmut_137, _138 | pure zebra-striping cosmetics |
| XL-STYLE | `events_to_excel` (:438-500): header font/fill/alignment/border/alt-fill/`freeze_panes` construction and application tweaks (`"4472C4"`→`"4472c4"`, `bold=True`→`False`, `Side(style="thin")`→None, `freeze_panes="a2"`…) | 50 | LOW-VALUE | x_events_to_excel__mutmut_15, _40, _166 | openpyxl accepts case-variant hex and `"a2"` refs identically; rest is styling a snapshot test would own — behavior no one should assert |
| XL-WIDTH | `events_to_excel` (:484-497): column-width arithmetic (`+2`→`±`, 50-cap→51, index off-by-one, `enumerate start=2`, `cell_len` ternary flips, `value=None`→format result discarded) | 13 | LOW-VALUE | x_events_to_excel__mutmut_101, _156, _164 | cosmetic autosize math |
| PROG-MSG | `export_events_with_progress`: progress **message text** renames/casing/None-kwargs (:795-873) | 14 | LOW-VALUE | ...with_progress__mutmut_66, _138, _222 | tracker message never asserted; cosmetic UI string |
| LOG-EXTRA-P | `export_events_with_progress`: `logger.info` message/`extra` dict key renames (:876-884) | 14 | LOW-VALUE | ...with_progress__mutmut_226, _230, _235 | logging only; no log-capture test should exist |
| LOG-EXTRA-W | `export_events_with_websocket`: same logging mutations (:1156-1162) | 16 | LOW-VALUE | ...websocket__mutmut_182, _186, _189 | same |
| WS-MSG | `export_events_with_websocket`: `report_progress` **current_step text** mutations (:1022-1136) | 10 | LOW-VALUE | ...websocket__mutmut_114, _120, _126 | cosmetic step label |
| JSON-INDENT | JSON serialization `indent=2`→None/3/omitted (3 funcs) | 6 | LOW-VALUE | ...with_progress__mutmut_180, _211, _214 | whitespace-only output change |
| ZIP-METHOD | `ZipFile(..., ZIP_DEFLATED)`→default (STORED) (:862) | 1 | LOW-VALUE | ...with_progress__mutmut_203 | valid archive, larger |
| EMPTY-ZIP | `_create_empty_export` zip compression method (:921) | 1 | LOW-VALUE | ..._create_empty_export__mutmut_50 | same |
| TZ-NAIVE | `export_events_with_progress` (:843): `datetime.now(UTC)`→`now(None)` | 1 | LOW-VALUE | ...with_progress__mutmut_141 | machine-tz vs UTC digits; same rationale as FILENAME-GEN |
| TZ-NAIVE-W | `export_events_with_websocket` (:1083): same | 1 | LOW-VALUE | ...websocket__mutmut_130 | same |
| EMPTY-TZ | `_create_empty_export` (:906): same | 1 | LOW-VALUE | ..._create_empty_export__mutmut_3 | same |
| PROG-ERRMSG / WS-ERRMSG | `raise ValueError("Database session required…")` message clobber (:759/:972) | 1+1 | LOW-VALUE | ...with_progress__mutmut_3, ...websocket__mutmut_3 | tests match "Database session required" — clobber breaks the match… (see note*) |
| DJ-INDENT | `detections_to_json` indent tweaks (:633) | 3 | LOW-VALUE | x_detections_to_json__mutmut_5, _7, _8 | whitespace-only |
| ENCODING | `write_text(encoding="utf-8")`→None/omitted/`"UTF-8"` (progress, 6) | 6 | EQUIVALENT | ...with_progress__mutmut_159, _163, _176 | platform-default is UTF-8 in containers; "UTF-8" ≡ "utf-8" |
| ENCODING-W | same, websocket method (3) | 3 | EQUIVALENT | ...websocket__mutmut_146, _148, _150 | same |
| EMPTY-ENC | same, `_create_empty_export` (6) | 6 | EQUIVALENT | ..._create_empty_export__mutmut_18, _24, _32 | same |
| ZREPLACE | `start_date.replace("Z", "+00:00")` → clobber/lowercase-z (:777/:783) | 4 | EQUIVALENT | ...with_progress__mutmut_26, _27, _39 | ISO-8601 uses uppercase Z only; lowercase-z variant never matches, clobbered-separator is dead on real inputs |
| INIT-MKDIR | `EXPORT_DIR.mkdir(parents=True, exist_ok=True)` kwarg tweaks (:673) | 3 | EQUIVALENT | ...__init____mutmut_2, _4, _6 | dir already exists in tests (`exist_ok=True` retained) — no-op |
| WS-FAIL-EQ | `fail(e, retryable=False)`→omitted (`retryable` defaults False in reporter) | 1 | EQUIVALENT | ...websocket__mutmut_203 | `job_progress_reporter.py:322` `retryable: bool = False` |
| XL-GETATTR | `getattr(event, field_name, None)`→`getattr(event, field_name, )` (:467) — positional-default drop, default is still None | 1 | EQUIVALENT | x_events_to_excel__mutmut_111 | |
| FEV-GETATTR / FD-GETATTR | same default-drop in `format_export_value` (:265) / `filter_row_to_dict` (:239) | 1+1 | EQUIVALENT | x_format_export_value__mutmut_6, x_filter_row_to_dict__mutmut_9 | |
| XL-EMPTYSTR | `cell_value = ""`→None (:477) | 1 | EQUIVALENT | x_events_to_excel__mutmut_124 | openpyxl round-trips both as empty cell; existing test already tolerates `(None, "")` |
| SELCOLS-NONE | `filter_row_to_dict`: `get_selected_columns(column_names)`→`(None)` (:238) | 1 | EQUIVALENT | x_filter_row_to_dict__mutmut_2 | callers pass `columns=None` in every observed path → identical EXTENDED fallback; custom-columns callers would see it — but then the FD-VALUE draft's column assert kills it |
| SELCOLS-NONE-P | `export_events_with_progress`: `get_selected_columns(columns)`→`(None)` (:844) | 1 | EQUIVALENT | ...with_progress__mutmut_146 | same masking; custom-columns integration would unmask (see COLUMNS draft note) |
| SINGLETON-R | `reset_export_service`: `_export_service = None`→`""` (:1191) | 1 | EQUIVALENT | x_reset_export_service__mutmut_1 | next `get_export_service()` recreates via `is None`→ falsy `""`… (`"" is None` False → returns `""`!) — see note**; kept EQUIVALENT as test-only function |

*PROG-ERRMSG/WS-ERRMSG: the ValueError-message clobbers are killable via the existing
`pytest.raises(match="Database session required")` — their survival suggests those mutants run only under a test
subset that skips that test; classified LOW-VALUE (message text) regardless.
**SINGLETON-R: `""` sentinel is a real behavior break for `get_export_service` after reset, but reset is a
test-harness function never called in production; classified EQUIVALENT-for-the-baseline.

## Totals check

```
clusters: 60   survivors assigned: 398/398   overlaps: 0
TEST-GAP: 226   LOW-VALUE: 138   EQUIVALENT: 34   (226+138+34 = 398)
```

---

## Drafted kill-tests (6 highest-value clusters)

All target `/agents/agent-nemo2/workspace/backend/tests/unit/services/test_export_service.py`
(follows its style: class-scoped fixtures, `AsyncMock` db, MagicMock tracker/reporter, local imports as the file does).
**TDD procedure (same for all six):** add test → run against ORIGINAL code: PASSES → apply the cluster's
mutant diff (e.g. `mutmut show <key>`) → test FAILS (red) → revert: green. UNVERIFIED - not yet run red/green
(no test execution permitted in this triage lane; SQL-render claims verified by a standalone `select(...).compile()`
probe against the repo's SQLAlchemy, reporter/tracker signatures verified by reading `job_progress_reporter.py` /
`job_tracker.py`).

### T1 — `TestExportProgressWritesRowData` → kills ROW-FIELDS-P (31) + FILE-CONTENT-P (9) + COLUMNS (3)

```python
@pytest.mark.asyncio
class TestExportProgressWritesRowData:
    """WP4.4 kill-test: export_events_with_progress must write real row data to disk.

    Survivors show the CSV/JSON/zip file produced by the progress path is never read
    back — every EventExportRow field, the filter_row_to_dict content and the selected
    columns can be nulled and the suite stays green.
    """

    @staticmethod
    def _mock_db_with_two_events(monkeypatch, tmp_path):
        from unittest.mock import AsyncMock, MagicMock

        import backend.services.export_service as es

        monkeypatch.setattr(es, "EXPORT_DIR", tmp_path)

        e1 = MagicMock()
        e1.id = 42
        e1.camera_id = "cam-7"
        e1.started_at = datetime(2024, 3, 1, 9, 0, 0, tzinfo=UTC)
        e1.ended_at = datetime(2024, 3, 1, 9, 5, 0, tzinfo=UTC)
        e1.risk_score = 75
        e1.risk_level = "high"
        e1.summary = "Person at door"
        e1.detection_count = None  # `or 0` must render 0
        e1.reviewed = None  # `or False` must render "No"
        e1.object_types = "person, dog"
        e1.reasoning = "why the model thought so"

        e2 = MagicMock()
        e2.id = 43
        e2.camera_id = "cam-missing"
        e2.started_at = datetime(2024, 3, 2, 10, 0, 0, tzinfo=UTC)
        e2.ended_at = None
        e2.risk_score = None
        e2.risk_level = None
        e2.summary = None
        e2.detection_count = 2
        e2.reviewed = True
        e2.object_types = None
        e2.reasoning = None

        count_result = MagicMock()
        count_result.scalar.return_value = 2
        event_result = MagicMock()
        event_result.scalars.return_value.all.return_value = [e1, e2]
        cam1_result = MagicMock()
        cam1_result.scalar.return_value = "Back Gate"
        cam2_result = MagicMock()
        cam2_result.scalar.return_value = None  # deleted camera → "Unknown" fallback

        db = AsyncMock()
        db.execute = AsyncMock(
            side_effect=[count_result, event_result, cam1_result, cam2_result]
        )
        return db

    async def test_csv_file_contains_all_event_fields(self, tmp_path, monkeypatch):
        import csv as csv_mod
        import io

        import backend.services.export_service as es

        db = self._mock_db_with_two_events(monkeypatch, tmp_path)
        service = es.ExportService(db=db)

        result = await service.export_events_with_progress(
            job_id="content-job", job_tracker=monkeypatch_tracker(), export_format="csv"
        )

        written = tmp_path / result["file_path"].rsplit("/", 1)[-1]
        rows = list(csv_mod.reader(io.StringIO(written.read_text(encoding="utf-8"))))

        # header = EXTENDED column display names (kills COLUMNS column-loss)
        assert rows[0] == [display for _, display in es.EXTENDED_EXPORT_COLUMNS]
        # full first row — every field present with its formatted value
        assert rows[1] == [
            "42",
            "Back Gate",
            "2024-03-01T09:00:00+00:00",
            "2024-03-01T09:05:00+00:00",
            "75",
            "high",
            "Person at door",
            "0",  # detection_count None or 0 — kills _107 (None) and _123 (or 1)
            "No",  # reviewed None or False — kills _108 (None), _125 (or True)
            "person, dog",
            "why the model thought so",
        ]
        # camera lookup miss → "Unknown" fallback (kills _85-88, _94-98)
        assert rows[2][1] == "Unknown"
        assert rows[2][0] == "43"
```

Where `monkeypatch_tracker()` is just `MagicMock()` (write inline: `from unittest.mock import MagicMock; MagicMock()`).
Companion `test_json_file_holds_filtered_row_dicts` (same fixtures, `export_format="json"`, then
`json.loads(written.read_text())` and assert both dicts by full key/value equality) kills FILE-CONTENT-P's
`content_dict=None` / `json.dumps(None)` / `filter_row_to_dict(None, ...)` survivors (_167-169, _189-191, _210) and
the FD-VALUE cluster as a side effect. The pure SQL-render survivors inside ROW-FIELDS-P (_90-93 camera-statement
nulls) are killed by T2 instead.

### T2 — `TestExportQueryShape` → kills SQL-FILTER (15) + SQL-FILTER-W (5) + SQL-COUNT (5) + SQL-COUNT-W (3) + camera-statement nulls in ROW-FIELDS-P/W

```python
@pytest.mark.asyncio
class TestExportQueryShape:
    """WP4.4 kill-test: every filter must render into the compiled SQL text.

    Existing filter tests assert only `mock_db.execute.called`; SQLAlchemy 2.x happily
    compiles where(None)/select(None)/!= — so filter-loss mutants were invisible to the
    mock-based suite. Precedent for SQL-text assertions: TestExportDeferredColumns.
    """

    async def test_all_filters_render_into_count_statement(self):
        from datetime import datetime as dt
        from unittest.mock import AsyncMock, MagicMock

        count_result = MagicMock()
        count_result.scalar.return_value = 0
        db = AsyncMock()
        db.execute = AsyncMock(return_value=count_result)

        service = ExportService(db=db)
        await service.export_events_with_progress(
            job_id="shape-job",
            job_tracker=MagicMock(),
            export_format="csv",
            camera_id="cam-9",
            risk_level="high",
            start_date="2024-01-15T00:00:00Z",
            end_date="2024-01-16T23:59:59Z",
            reviewed=True,
        )

        stmt = mock_execute_first(db)  # inline: mock_db.execute.call_args_list[0].args[0]
        text_ = str(stmt.compile())

        assert "events.deleted_at IS NULL" in text_  # kills _7 where(None)
        assert "events.camera_id = :" in text_  # kills _11 (is None), _13 None, _14 !=
        assert "events.risk_level = :" in text_  # kills _15, _17, _18
        assert "events.started_at >= :" in text_  # kills _30, _31 (> strict)
        assert "events.started_at <= :" in text_  # kills _43, _44 (< strict)
        assert "events.reviewed = :" in text_  # kills _45, _47, _48
        assert "!=" not in text_  # no flipped comparison anywhere
        assert "SELECT count(*)" in text_  # kills SQL-COUNT _49/_51/_53 (None/select(None)/execute(None))

        params = stmt.compile().params
        assert "cam-9" in params.values()
        assert "high" in params.values()
        assert dt.fromisoformat("2024-01-15T00:00:00+00:00") in params.values()  # kills ZREPLACE too
        assert dt.fromisoformat("2024-01-16T23:59:59+00:00") in params.values()
        assert True in params.values()
```

(Replace the `mock_execute_first` pseudo-line with `stmt = db.execute.call_args_list[0].args[0]`. Companion
`test_fetch_statement_orders_desc` runs the non-empty path (3-execute `side_effect` as in T1) and asserts
`"ORDER BY events.started_at DESC" in str(db.execute.call_args_list[1].args[0].compile())` → kills _78/_58
`order_by(None)`; the identical `start()`-side capture for the websocket method kills SQL-FILTER-W/SQL-COUNT-W.)

### T3 — `TestWebSocketProgressSequence` → kills WS-PROG (32)

```python
@pytest.mark.asyncio
class TestWebSocketProgressSequence:
    """WP4.4 kill-test: report_progress call VALUES, not just call_count (NEM-2380 contract)."""

    @staticmethod
    def _reporter_and_db():
        from unittest.mock import AsyncMock, MagicMock

        reporter = MagicMock()
        reporter.start = AsyncMock()
        reporter.report_progress = AsyncMock()
        reporter.complete = AsyncMock()
        reporter.fail = AsyncMock()
        reporter.job_id = "ws-seq"
        reporter.duration_seconds = 1.0

        def event(eid):
            e = MagicMock()
            e.id = eid
            e.camera_id = "cam-1"
            e.started_at = datetime(2024, 1, 15, 10, 30, 0, tzinfo=UTC)
            e.ended_at = None
            e.risk_score = 75
            e.risk_level = "high"
            e.summary = "Test"
            e.detection_count = 1
            e.reviewed = False
            e.object_types = None
            e.reasoning = None
            return e

        count_result = MagicMock()
        count_result.scalar.return_value = 2
        event_result = MagicMock()
        event_result.scalars.return_value.all.return_value = [event(1), event(2)]
        cam = MagicMock()
        cam.scalar.return_value = "Cam"

        db = AsyncMock()
        db.execute = AsyncMock(side_effect=[count_result, event_result, cam, cam])
        return reporter, db

    async def test_report_progress_call_sequence(self):
        reporter, db = self._reporter_and_db()
        service = ExportService(db=db)

        await service.export_events_with_websocket(
            progress_reporter=reporter, export_format="csv"
        )

        calls = [
            (c.args[0], c.kwargs.get("current_step"), c.kwargs.get("force"))
            for c in reporter.report_progress.call_args_list
        ]
        assert calls == [
            (1, "Found 2 events to export", True),
            (35, "Processing event 1/2", None),  # int(1/2*70) — kills /70, *total, ±idx variants
            (70, "Processing event 2/2", None),  # kills *71 (→71), (idx+2) (→105)
            (80, "Writing CSV file...", True),
            (95, "Finalizing export...", True),
        ]

    async def test_complete_receives_result_summary(self):
        reporter, db = self._reporter_and_db()
        service = ExportService(db=db)
        await service.export_events_with_websocket(
            progress_reporter=reporter, export_format="csv"
        )
        summary = reporter.complete.call_args.kwargs["result_summary"]
        assert summary["event_count"] == 2  # kills _199 result_summary=None (and WS-RESULT partly)
```

### T4 — `TestWebSocketStartMetadata` → kills WS-META (12)

```python
@pytest.mark.asyncio
class TestWebSocketStartMetadata:
    """WP4.4 kill-test: job.started metadata filters dict is the frontend contract."""

    async def test_start_metadata_carries_exact_filter_keys(self):
        from unittest.mock import AsyncMock, MagicMock

        reporter = MagicMock()
        reporter.start = AsyncMock()
        reporter.report_progress = AsyncMock()
        reporter.complete = AsyncMock()
        reporter.job_id = "ws-meta"

        count_result = MagicMock()
        count_result.scalar.return_value = 0
        db = AsyncMock()
        db.execute = AsyncMock(return_value=count_result)

        service = ExportService(db=db)
        await service.export_events_with_websocket(
            progress_reporter=reporter,
            export_format="csv",
            camera_id="cam-1",
            risk_level="high",
            start_date="2024-01-01T00:00:00Z",
            end_date=None,
            reviewed=True,
        )

        meta = reporter.start.call_args.kwargs["metadata"]
        assert meta["export_format"] == "csv"
        assert meta["filters"] == {  # exact dict equality kills every rename/casing survivor
            "camera_id": "cam-1",
            "risk_level": "high",
            "start_date": "2024-01-01T00:00:00Z",
            "end_date": None,
            "reviewed": True,
        }
```

### T5 — `TestEventsToExcelCellValues` → kills XL-CELLS (10)

```python
class TestEventsToExcelCellValues:
    """WP4.4 kill-test: Excel bool/datetime cell VALUES, not just header/id cells."""

    def test_excel_boolean_reviewed_cells_are_yes_no(self):
        import io

        from openpyxl import load_workbook

        events = [
            EventExportRow(
                event_id=1, camera_name="Cam", started_at=None, ended_at=None,
                risk_score=None, risk_level=None, summary=None,
                detection_count=1, reviewed=True,
            ),
            EventExportRow(
                event_id=2, camera_name="Cam", started_at=None, ended_at=None,
                risk_score=None, risk_level=None, summary=None,
                detection_count=1, reviewed=False,
            ),
        ]
        ws = load_workbook(io.BytesIO(events_to_excel(events))).active
        assert ws.cell(row=2, column=9).value == "Yes"  # reviewed=True
        assert ws.cell(row=3, column=9).value == "No"  # reviewed=False
        # case flips (XXYesXX/yes/YES/XXNoXX/no/NO) and the and-False/or-True branch flips all fail here

    def test_excel_datetime_cells_are_naive_datetimes(self):
        import io

        from openpyxl import load_workbook

        events = [
            EventExportRow(
                event_id=1, camera_name="Cam",
                started_at=datetime(2024, 1, 15, 10, 30, 0, tzinfo=UTC),
                ended_at=None, risk_score=None, risk_level=None, summary=None,
                detection_count=1, reviewed=False,
            ),
        ]
        ws = load_workbook(io.BytesIO(events_to_excel(events))).active
        value = ws.cell(row=2, column=3).value  # kills _112 (→None) and keeps tz-strip pinned
        assert value == datetime(2024, 1, 15, 10, 30, 0)
        assert value.tzinfo is None  # openpyxl rejects tz-aware cells
```

### T6 — added to `TestParseAcceptHeader` → kills ACCEPT-QP (2)

```python
    def test_accept_header_json_with_quality_value(self):
        """`;q=` parameter must be stripped before mapping — JSON must NOT fall back to CSV.

        (Existing quality-value test evidently uses a CSV header, whose mutant outcome is
        also CSV, hiding split(";")→split(None) survivors.)
        """
        assert parse_accept_header("application/json;q=0.9") == ExportFormat.JSON
```

## Notes for the WP4.4 fix lane

- Highest leverage: T1/T2 together (real-file + compiled-SQL asserts) kill ~73 survivors across
  ROW-FIELDS-P/W, FILE-CONTENT-P/W, SQL-*, COLUMNS, FD-VALUE. T3/T4 add 44 more.
- `SINGLETON` and `SINGLETON-R`: the memoization test is weak *by construction* (both calls hit the same
  code path); a `reset_export_service(); assert get_export_service() is not prev` assertion is the fix — 2 lines,
  kills SINGLETON _1/_2 and would turn SINGLETON-R into a real (currently masked) behavior probe.
- `CSV-SEEK` is the sneaky one: `seek(1)` silently misaligns every streamed row; one `"".join(chunks)` +
  `csv.reader` equality test against `events_to_csv` output kills it cheaply (2 survivors).
- Do NOT chase XL-STYLE/XL-WIDTH/LOG-*/PROG-MSG/WS-MSG (~163 LOW-VALUE): killing those needs snapshot/
  log-capture tests that assert cosmetic output — noise for the score, negative value per the classification rubric.
