# WP4.4 Triage Dossier — backend/services/summary_detail_service.py

Snapshot taken 2026-09-17. Meta (`mutants/backend/services/summary_detail_service.py.meta`):
251 keys total — **111 SURVIVED (exit 0)**, 65 killed, 75 null (not yet checked at read time;
the survivor set can only grow as the live run finishes the remaining 75 — re-diff before
building WP4.4 tasks from this list).

Diffs obtained via `uv run mutmut show <key>` for all 111 survivors (raw dump:
`/tmp/wp25/wp44-triage/survivor-diffs.txt`). No tests were run; no repo files were touched.

**Coverage context** (from `mutants/mutmut-stats.json` -> `tests_by_mangled_function_name`):

| function                           | covering tests live in                                                                                                                                                                                            |
| ---------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `TimelineEvent.to_dict`            | `backend/tests/unit/services/test_summary_detail_service.py` (1 test: `TestEdgeCases::test_timeline_event_to_dict`, line 467)                                                                                     |
| `SummaryDetailService.export_json` | same file `TestExportJSON` (lines 208-280) + `TestEdgeCases::test_export_handles_unicode` (501); `backend/tests/unit/api/routes/test_summaries_detail.py::TestExportSummary::test_export_summary_json` (line 301) |
| `SummaryDetailService.export_csv`  | same file `TestExportCSV` (lines 283-359) + unicode test (501); route test `TestExportSummary::test_export_summary_csv` (test_summaries_detail.py line 360)                                                       |
| `SummaryDetailService.export_pdf`  | same file `TestExportPDF` (lines 362-386) — both tests assert ONLY `isinstance(result, bytes)` plus the vacuous `result.startswith(b"%PDF") or len(result) > 0` (line 376)                                        |

**Key enabler fact** (used for the EQUIVALENT calls): the DB columns feeding every
timestamp guard are NOT NULL — `backend/models/summary.py:63-65`
(`window_start/window_end/generated_at`, `nullable=False`) and
`backend/models/event.py:56` (`started_at`, `nullable=False`). The `... else None`
branches they guard are dead code in production, so mutations that only distinguish
the `None` branch are equivalent on the reachable input domain.

## Cluster table (counts sum to 111)

| #   | Pattern                                                                                                                                                                                                                                                                                      | Count | Class        | Example keys (<=3)                                                           | Notes                                                                                                                                                                                                                                                                                                                                |
| --- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----- | ------------ | ---------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| 1   | `export_pdf` PDF structural boilerplate: case flips (`/Type`->`/type`, `Tj`->`tj`), `XX...XX` wraps on obj/stream/xref/trailer/xref-number lines, `BT/Td/Tj` operator tweaks                                                                                                                 | 52    | LOW-VALUE    | `export_pdf__mutmut_10`, `export_pdf__mutmut_19`, `export_pdf__mutmut_54`    | export_pdf is a self-declared placeholder fake PDF (docstring: "minimal implementation — real PDF would use ReportLab"); the bytes are not a parseable PDF even in the original (`/Length 500` mismatch, `startxref 0`), so these interior-token tweaks have no consumer-observable behavior worth asserting.                        |
| 2   | `export_pdf` framing bytes unasserted: header `%PDF-1.4`->`XX%PDF-1.4XX`/`%pdf-1.4` (4,5), footer `%%EOF`->`XX%%EOFXX`/`%%eof` (58,59)                                                                                                                                                       | 4     | **TEST-GAP** | `export_pdf__mutmut_4`, `export_pdf__mutmut_58`, `export_pdf__mutmut_5`      | The only format assertion, `test_summary_detail_service.py:376`, is `startswith(b"%PDF") or len(result) > 0` — the `or len>0` makes it vacuous. Fix: separate startswith/endswith asserts (draft T1).                                                                                                                                |
| 3   | `export_pdf` interpolated body content unasserted: `build_timeline(events)`->`build_timeline(None)` (2, timeline count prints 0 always), `content[:100]`->`content[:101]` (42)                                                                                                               | 2     | **TEST-GAP** | `export_pdf__mutmut_2`, `export_pdf__mutmut_42`                              | Mutant 2 is a real logic change (PDF text says "Timeline Events: 0" for any input); 42 is an off-by-one on the 100-char content preview, only observable with >100-char content. Cheap kill: assert `b"(Timeline Events: 3)"` in output + long-content preview boundary (not drafted — lower value than T1-T6; add when convenient). |
| 4   | `export_pdf` codec-name tweak `"utf-8"`->`"UTF-8"` (65)                                                                                                                                                                                                                                      | 1     | EQUIVALENT   | `export_pdf__mutmut_65`                                                      | Python codec aliases; byte-identical output.                                                                                                                                                                                                                                                                                         |
| 5   | `export_json` event/metadata schema keys renamed (`"url"`->`"XXurlXX"`/`"URL"`; `"exported_at"/"format"/"version"`->`"XX...XX"`/`"UPPER"`) and static metadata values tweaked (`"json"`->`"XXjsonXX"`/`"JSON"`, `"1.0"`->`"XX1.0XX"`)                                                        | 11    | **TEST-GAP** | `export_json__mutmut_44`, `export_json__mutmut_48`, `export_json__mutmut_54` | `test_export_json_events` (test_summary_detail_service.py:246-265) checks key presence for all event keys EXCEPT `"url"`, and never asserts metadata beyond `"metadata" in data` and `metadata["event_count"]`. These keys/values are the download contract. Kill via full key-set equality + metadata values (draft T2).            |
| 6   | `export_json` `json.dumps` indent tweaks: `indent=2`->`None`/absent/`3` (60,63,65)                                                                                                                                                                                                           | 3     | LOW-VALUE    | `export_json__mutmut_60`                                                     | Whitespace-only; `json.loads` output identical. Nobody should assert pretty-print width.                                                                                                                                                                                                                                             |
| 7   | `export_json` `ensure_ascii=False` dropped/flipped (61 `ensure_ascii=None`, 64 arg removed, 66 `ensure_ascii=True`)                                                                                                                                                                          | 3     | **TEST-GAP** | `export_json__mutmut_66`                                                     | The existing unicode test `test_export_handles_unicode` (test_summary_detail_service.py:501-523) asserts after `json.loads`, which unescapes `\uXXXX` — so it passes on the mutant. The raw export bytes DO change (CJK -> `中文`). Kill by asserting raw chars before parsing (folded into draft T2).                               |
| 8   | Conditional-isoformat guard forced to else (`cond and False`) — timestamp/date values silently become `None`/`""` on every real input: `to_dict` timestamp (5), `export_csv` timestamp cell (13), `export_json` `window_start`/`window_end`/`generated_at` (16,20,24) + event timestamp (32) | 6     | **TEST-GAP** | `to_dict__mutmut_5`, `export_json__mutmut_16`, `export_csv__mutmut_13`       | Every covering test checks only `assert "window_start" in summary_data` etc. (test_summary_detail_service.py:242-244; route test asserts nothing on timestamps). Values are computed on every export and never asserted. Kill via value assertions (draft T5).                                                                       |
| 9   | Same guards forced to if (`cond or True`)                                                                                                                                                                                                                                                    | 6     | EQUIVALENT   | `to_dict__mutmut_6`, `export_json__mutmut_17`, `export_csv__mutmut_14`       | Differs only when the value is `None` (crash instead of None-output); source columns are `nullable=False` (summary.py:63-65, event.py:56) so the else branch is dead — equivalent on the reachable domain.                                                                                                                           |
| 10  | Fallback constant tweak on a dead else: csv timestamp else `""`->`"XXXX"` (15), csv `event_url or "XXXX"` (26)                                                                                                                                                                               | 2     | EQUIVALENT   | `export_csv__mutmut_15`, `export_csv__mutmut_26`                             | 15: `event.timestamp` comes from NOT-NULL `started_at` -> else never taken. 26: `event_url` is always the non-empty f-string `/events/{id}` set by `build_timeline` -> `or` short-circuits identically.                                                                                                                              |
| 11  | None-field placeholder render: `x or ""`->`x or "XXXX"` and `if cond or True` str-mutation, on genuinely NULLABLE fields (`Event.summary`, `risk_score`, `risk_level`): `to_dict` summary (12), csv summary/score/level (17,19,22,24), json event summary (39)                               | 6     | **TEST-GAP** | `export_csv__mutmut_17`, `export_csv__mutmut_19`, `export_json__mutmut_39`   | Null inputs ARE a thing (`test_event_with_none_values` exists for build_timeline), but no test ever EXPORTS a null-field event — so "None risk score must render as empty cell, not `XXXX`/`None`" is never asserted. Kill via one null-field export test (draft T6).                                                                |
| 12  | `export_csv` row cell value mutations on non-null core input: risk-score guard `and False` (18), `str(None)` (20), `is None` comparison flip (21), `risk_level and ""` (23), `event_url and ""` (25)                                                                                         | 5     | **TEST-GAP** | `export_csv__mutmut_23`, `export_csv__mutmut_25`, `export_csv__mutmut_20`    | `test_export_csv_rows` (:305-322) only checks `rows[1][0]` and camera substring; every other column is unasserted, so a CSV with empty Risk Score/URL columns ships green. Kill via full-row equality (draft T4).                                                                                                                    |
| 13  | `export_csv` `csv.writer(output, QUOTE_ALL)` -> `csv.writer(output)` (8)                                                                                                                                                                                                                     | 1     | LOW-VALUE    | `export_csv__mutmut_8`                                                       | QUOTE_MINIMAL still produces a valid, parseable CSV; test asserts parseability, and CSV consumers shouldn't care about quote style.                                                                                                                                                                                                  |
| 14  | `TimelineEvent.to_dict` key renames (`"summary"`,`"risk_score"`,`"risk_level"`,`"event_url"` -> `XX...XX`/`UPPER`) (9,10,13-18) + summary value dropped to `""` (`and ""`) (11)                                                                                                              | 9     | **TEST-GAP** | `to_dict__mutmut_9`, `to_dict__mutmut_15`, `to_dict__mutmut_11`              | Only covering test (`test_timeline_event_to_dict`, :467-479) checks key presence for 3 of 7 keys and asserts NO values. to_dict feeds the detail-panel API payload. Kill via key-set + value assertions (draft T3).                                                                                                                  |

Totals: TEST-GAP 46, LOW-VALUE 56, EQUIVALENT 9 -> 111.

The LOW-VALUE majority is expected: `export_pdf` alone contributes 55 of 111 survivors and is
an admitted placeholder whose only real contracts are the framing markers and the interpolated
summary values (clusters 2-3). The highest-value structural fix behind several TEST-GAP
clusters is the vacuous-`or` assertion at test_summary_detail_service.py:376.

## Drafted tests (ALL UNVERIFIED — not yet run red/green)

All six go in `backend/tests/unit/services/test_summary_detail_service.py`; imports already
present in that file (`csv`, `io`, `json`, `datetime UTC`, `MagicMock`, fixtures
`detail_service`, `mock_summary`, `mock_events`). TDD for each: run the test against each
mutant copy in its cluster (expect RED — the listed assertion flips), run against original
(expect GREEN); then re-run `mutmut run` for the module to confirm the cluster kills.

### T1 — TestExportPDF (kills cluster 2: export_pdf\_\_mutmut_4, 5, 58, 59)

RED: mutant header/footer bytes fail the strict `startswith`/`endswith` (current test passes
them via its vacuous `or len(result) > 0`). GREEN: original passes.

```python
    def test_export_pdf_has_pdf_header_and_eof_footer(
        self,
        detail_service: SummaryDetailService,
        mock_summary: MagicMock,
        mock_events: list[MagicMock],
    ) -> None:
        """PDF export must open with the %PDF header and terminate with the %%EOF marker.

        Replaces the vacuous `startswith(b"%PDF") or len(result) > 0` pattern.
        """
        result = detail_service.export_pdf(mock_summary, mock_events)

        assert result.startswith(b"%PDF-1.4")
        assert result.endswith(b"%%EOF")
```

### T2 — TestExportJSON (kills cluster 5: 11 mutants; and cluster 7: 61, 64, 66)

RED: renamed keys break the set-equality; tweaked metadata values break the value asserts;
`ensure_ascii=True/None` escapes the CJK so the raw-string assert fails. GREEN on original.

```python
    def test_export_json_document_schema_is_stable(
        self,
        detail_service: SummaryDetailService,
        mock_summary: MagicMock,
        mock_events: list[MagicMock],
    ) -> None:
        """Export JSON is a consumer contract: exact keys, metadata values, raw unicode."""
        result = detail_service.export_json(mock_summary, mock_events)
        data = json.loads(result)

        assert set(data["summary"]) == {
            "id", "type", "content", "event_count",
            "window_start", "window_end", "generated_at",
        }
        assert set(data["events"][0]) == {
            "id", "timestamp", "camera", "summary",
            "risk_score", "risk_level", "url",
        }
        assert set(data["metadata"]) == {"exported_at", "event_count", "format", "version"}
        assert data["metadata"]["format"] == "json"
        assert data["metadata"]["version"] == "1.0"
        assert data["metadata"]["event_count"] == 3

        # ensure_ascii=False must keep non-ASCII raw in the exported TEXT
        # (the existing unicode test parses with json.loads, which unescapes \\uXXXX — too weak)
        unicode_event = MagicMock()
        unicode_event.id = 7
        unicode_event.started_at = datetime(2026, 1, 21, 14, 0, tzinfo=UTC)
        unicode_event.camera = MagicMock()
        unicode_event.camera.name = "Kamera"
        unicode_event.summary = "中文 \U0001f600"
        unicode_event.risk_score = 10
        unicode_event.risk_level = "low"
        raw = detail_service.export_json(mock_summary, [unicode_event])
        assert "中文" in raw
        assert "\\u4e2d" not in raw
```

### T3 — TestEdgeCases (kills cluster 14: to_dict\_\_mutmut_9,10,11,13,14,15,16,17,18)

RED: any key rename breaks the key-set equality; `summary and ""` yields `""` != full string.
GREEN on original.

```python
    def test_timeline_event_to_dict_matches_export_contract(
        self,
        detail_service: SummaryDetailService,
        mock_events: list[MagicMock],
    ) -> None:
        """to_dict must expose the exact key set and values the detail panel consumes."""
        event_dict = detail_service.build_timeline(mock_events)[0].to_dict()

        assert set(event_dict) == {
            "event_id", "timestamp", "camera_name", "summary",
            "risk_score", "risk_level", "event_url",
        }
        assert event_dict["event_id"] == 101
        assert event_dict["camera_name"] == "Front Door"
        assert event_dict["summary"] == "Person detected approaching the front door"
        assert event_dict["risk_score"] == 75
        assert event_dict["risk_level"] == "high"
        assert event_dict["event_url"] == "/events/101"
```

### T4 — TestExportCSV (kills cluster 12: export_csv\_\_mutmut_18, 20, 21, 23, 25)

RED: risk-score guard/score-string mutations empty or corrupt column 4; `risk_level and ""`
and `event_url and ""` empty columns 5-6 (full-row equality catches all). GREEN on original.

```python
    def test_export_csv_row_contains_all_column_values(
        self,
        detail_service: SummaryDetailService,
        mock_summary: MagicMock,
        mock_events: list[MagicMock],
    ) -> None:
        """Every CSV column must carry the event's value, not an empty placeholder."""
        result = detail_service.export_csv(mock_summary, mock_events)
        rows = list(csv.reader(io.StringIO(result)))

        assert rows[0] == [
            "Event ID", "Timestamp", "Camera", "Summary",
            "Risk Score", "Risk Level", "Event URL",
        ]
        assert rows[1] == [
            "101",
            "2026-01-21T14:10:00+00:00",
            "Front Door",
            "Person detected approaching the front door",
            "75",
            "high",
            "/events/101",
        ]
```

### T5 — TestEdgeCases (kills cluster 8: to_dict**mutmut_5, export_csv**mutmut_13, export_json\_\_mutmut_16, 20, 24, 32)

RED: `and False` guards force the else branch -> all date/time values come back `None`/`""`
against a value assertion. GREEN on original.

```python
    def test_exported_timestamps_are_isoformat_of_real_values(
        self,
        detail_service: SummaryDetailService,
        mock_summary: MagicMock,
        mock_events: list[MagicMock],
    ) -> None:
        """Serialized date/time fields must carry the real isoformat values, never silent None."""
        data = json.loads(detail_service.export_json(mock_summary, mock_events))

        assert data["summary"]["window_start"] == "2026-01-21T14:00:00+00:00"
        assert data["summary"]["window_end"] == "2026-01-21T15:00:00+00:00"
        assert data["summary"]["generated_at"] == "2026-01-21T14:55:00+00:00"
        assert data["events"][0]["timestamp"] == "2026-01-21T14:10:00+00:00"

        assert detail_service.build_timeline(mock_events)[0].to_dict()["timestamp"] == (
            "2026-01-21T14:10:00+00:00"
        )

        csv_rows = list(csv.reader(io.StringIO(detail_service.export_csv(mock_summary, mock_events))))
        assert csv_rows[1][1] == "2026-01-21T14:10:00+00:00"
```

### T6 — TestExportCSV (kills cluster 11: to_dict**mutmut_12, export_csv**mutmut_17, 19, 22, 24, export_json\_\_mutmut_39)

RED: null fields render as `"XXXX"`/`"None"` placeholders instead of empty cells/strings.
GREEN on original.

```python
    def test_none_optional_fields_render_as_empty_in_all_exports(
        self,
        detail_service: SummaryDetailService,
        mock_summary: MagicMock,
    ) -> None:
        """Events with nullable summary/risk fields must export empty values, never placeholders."""
        event = MagicMock()
        event.id = 5
        event.started_at = datetime(2026, 1, 21, 14, 0, tzinfo=UTC)
        event.camera = MagicMock()
        event.camera.name = "Camera"
        event.summary = None
        event.risk_score = None
        event.risk_level = None

        assert detail_service.build_timeline([event])[0].to_dict()["summary"] == ""

        csv_rows = list(csv.reader(io.StringIO(detail_service.export_csv(mock_summary, [event]))))
        assert csv_rows[1] == [
            "5",
            "2026-01-21T14:00:00+00:00",
            "Camera",
            "",
            "",
            "",
            "/events/5",
        ]

        data = json.loads(detail_service.export_json(mock_summary, [event]))
        assert data["events"][0]["summary"] == ""
        assert data["events"][0]["risk_score"] is None
        assert data["events"][0]["risk_level"] is None
```

## Not drafted (deliberately)

- Cluster 3 (2 mutants): add `assert b"(Timeline Events: 3)" in result` to T1 plus a
  long-content preview-boundary assert — worth folding in at implementation time if the
  reviewer wants all TEST-GAP clusters killed by drafted code, but lower value than T1-T6.
- All LOW-VALUE and EQUIVALENT clusters: killable only with brittle assertions on
  placeholder-PDF tokens, whitespace width, quote style, or type-impossible `None` inputs.

## Caveats

- 75 keys were still `null` (unchecked) in the meta at read time; this triage covers only
  the 111 confirmed survivors.
- Classification of clusters 9/10 rests on the NOT NULL columns; if a future migration makes
  `window_start`/`started_at` nullable, cluster 9 flips to TEST-GAP (assert None-branch output).
