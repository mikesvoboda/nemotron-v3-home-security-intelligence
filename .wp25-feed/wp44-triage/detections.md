# WP4.4 Triage Dossier — backend/api/routes/detections.py

**Survivors:** 157 of 753 keys (524 killed, 72 unchecked) — source: `mutants/backend/api/routes/detections.py.meta`
**Diffs:** all 157 collected via `uv run mutmut show <key>` (staged under `/tmp/wp25/wp44-triage/detections-diffs/`).
**Covering tests** (from `mutants/mutmut-stats.json` → `tests_by_mangled_function_name`):

- `backend/tests/unit/api/routes/test_detections.py` (primary; TestExtractClothing… @ :149, TestExtractVehicle… @ :254, TestValidateEnrichmentData @ :313, TestTransformEnrichmentData @ :397, TestParseRangeHeader @ :510, TestGetDetectionImage @ :968, TestFileReadSpecificExceptions @ :2733)
- `backend/tests/unit/routes/test_detections_routes.py` (cache-header route tests, e.g. `test_get_detection_image_full_cache_header` @ :1267)
- `backend/tests/unit/api/schemas/test_detections.py` (TestValidateEnrichmentData)
- `backend/tests/unit/services/test_video_support.py` (TestRangeHeaderParsing — a _separate implementation_, not this module's `_parse_range_header`)

**Key runtime facts used for classification (verified via one-off import checks, no test execution):**

- Pydantic v2.13 (strict): `PersonEnrichmentData(is_suspicious=None)` / `VehicleEnrichmentData(has_damage=None)` **raise ValidationError** → `None`-default mutants on typed-model constructor args are crash mutants (500 via endpoint), killable with a missing-key payload test. `1`/`True`/`0.0` coerce fine, so the boolean flips are _silent_ behavior changes.
- `max([None])` raises TypeError → face-`confidence` default `0 → None` mutants crash when a face dict lacks `confidence`.
- `starlette Response` normalizes header names to lowercase bytes (`b'cache-control'`) and lookup is case-insensitive → header-name-case mutants semantically equivalent (and `test_detections_routes.py::test_get_detection_image_full_cache_header` already asserts through case-insensitive lookup, consistent with survival).
- `open(path, "RB")` is valid (mode case-insensitive) → equivalent.
- `_parse_range_header` clamps `end = min(end, file_size - 1)` _after_ both `file_size - 1` sites → `end = file_size + 1 / - 2` variants absorbed → equivalent.
- `dict.get(None, default)` does NOT raise — it just reads a key that's never present (returns default). So `.get(None, False)` mutants behave like "flag key absent": observable only when the input payload HAS the real key set to True.
- `VideoProcessor.extract_thumbnail` defaults: `output_path=None`, `timestamp=None`, `size=(320, 240)` → dropping `output_path=`/`timestamp=` kwargs is equivalent against the real service; `size=`/`video_path=` removals are real but only observable by asserting the mock's call kwargs (existing test does only `assert_called_once()`).
- `_sanitize_errors` begins `if not errors: return []` → `get("errors", [] → None)` equivalent.
- Existing tests assert exception `detail` **substrings case-insensitively** for the file-read helpers (`"not found" in str(detail).lower()`) → case-fold/XX-padding of those details/messages is equivalent _for this suite_.

## Cluster table (counts sum to 157: EQUIVALENT 78, TEST-GAP 60, LOW-VALUE 19)

| #   | Cluster (pattern @ function)                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                       | Count | Class      | Example keys (≤3)                                                                                                                                    |
| --- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ----- | ---------- | ---------------------------------------------------------------------------------------------------------------------------------------------------- |
| A1  | `.get(key, {})`/`[]` default → `None` under truthiness guards (`_extract_clothing` 3,10; `_extract_vehicle` 3; `_transform` 48,85,185; `validate` 5,55,105,126)                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                    | 10    | EQUIVALENT | `…x__extract_clothing_from_enrichment__mutmut_3`, `…x__transform_enrichment_data__mutmut_48`, `…x_validate_enrichment_data__mutmut_126`              |
| A2  | `.get()` default arg removed entirely (becomes `None`) — same falsiness, same code path                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                            | 10    | EQUIVALENT | `…x__extract_clothing_from_enrichment__mutmut_5`, `…x__transform_enrichment_data__mutmut_187`, `…x_validate_enrichment_data__mutmut_7`               |
| A3  | `next(iter(x), None)` default arg removed (default was already `None` — no-op)                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                     | 7     | EQUIVALENT | `…x__extract_clothing_from_enrichment__mutmut_22`, `…x__transform_enrichment_data__mutmut_193`, `…x_validate_enrichment_data__mutmut_113`            |
| A4  | `""` default → `None`/removed on truthiness-guarded `raw_description`/`carrying` reads                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                             | 6     | EQUIVALENT | `…x__extract_clothing_from_enrichment__mutmut_27`, `…x_validate_enrichment_data__mutmut_68`, `…x_validate_enrichment_data__mutmut_76`                |
| A5  | Output-dict / constructor-**key renames** (`"color"`, `"count"`, `"detected"`, `"score"`, `"weather"`, `"pose"`, `"depth"`, `"is_low_quality"`, `"quality_issues"` → XX-padded/UPPER) — canonical consumers use the lowercase key; response_model drops unknown extra keys                                                                                                                                                                                                                                                                                                                                                                                                                                         | 18    | EQUIVALENT | `…x__extract_vehicle_from_enrichment__mutmut_22`, `…x__transform_enrichment_data__mutmut_31`, `…x__transform_enrichment_data__mutmut_164`            |
| A6  | Case-only variants that stay semantically identical: HTTP header **name** case (`"Cache-Control"`→`"cache-control"`/`"CACHE-CONTROL"` — starlette lowercases on emit, lookup is case-insensitive) and `open(mode="RB")` (mode is case-insensitive) — image 6,17,18; video 19,30,31                                                                                                                                                                                                                                                                                                                                                                                                                                 | 6     | EQUIVALENT | `…x__get_full_image_for_image__mutmut_17`, `…x__get_full_image_for_video__mutmut_30`, `…x__get_full_image_for_video__mutmut_19`                      |
| A7  | Pure message-text: `detail`/`ValueError` strings XX-padded or case-folded (tests match case-insensitively or not at all — e.g. `test_parse_range_invalid_format` uses `match="Invalid range header format"`, a substring of `"XXInvalid range header formatXX"`)                                                                                                                                                                                                                                                                                                                                                                                                                                                   | 10    | EQUIVALENT | `…x__get_full_image_for_image__mutmut_32`, `…x__get_full_image_for_video__mutmut_40`, `…x__parse_range_header__mutmut_6`                             |
| A8  | Branch/arithmetic tweaks absorbed downstream or provable no-ops: `end = file_size ± k` before the final clamp (parse 24,33,53,54), `range_spec.endswith("XX-XX")` (no input ends with that), `int(parts[1]) if (parts[1]) or True` where `parts[1]==""` is unreachable in that branch (parse 49), `parts[0] if (parts) or True` where `parts` is always non-empty (clothing 49)                                                                                                                                                                                                                                                                                                                                    | 7     | EQUIVALENT | `…x__parse_range_header__mutmut_24`, `…x__parse_range_header__mutmut_49`, `…x__extract_clothing_from_enrichment__mutmut_49`                          |
| A9  | Explicit-`None` constructor kwarg removals (`vehicle_color=None`, `action=None`, `breed=None`, `weather=None`) — model/field default is also `None`                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                | 4     | EQUIVALENT | `…x_validate_enrichment_data__mutmut_39`, `…x_validate_enrichment_data__mutmut_90`, `…x_validate_enrichment_data__mutmut_138`                        |
| B1  | **Vehicle damage defaults** (`_extract_vehicle_from_enrichment`): `vd.get("has_damage", False→True/None/removed)`, `vd.get("damage_types", []→None/removed)` — needs a `vehicle_damage` entry present but schema-defaulted                                                                                                                                                                                                                                                                                                                                                                                                                                                                                         | 5     | TEST-GAP   | `…x__extract_vehicle_from_enrichment__mutmut_51`, `…x__extract_vehicle_from_enrichment__mutmut_56`, `…x__extract_vehicle_from_enrichment__mutmut_61` |
| B2  | `validate_enrichment_data` **has_damage**: init `False→True` + `.get("has_damage", False→True/None/removed)` — existing test never builds a vehicle at all (asserts only type + is_commercial False)                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                               | 4     | TEST-GAP   | `…x_validate_enrichment_data__mutmut_24`, `…x_validate_enrichment_data__mutmut_28`, `…x_validate_enrichment_data__mutmut_33`                         |
| B3  | `validate_enrichment_data` **is_commercial / is_suspicious**: input-key renames (incl. `.get(None,…)`), kwarg dropped from the constructor (`is_commercial=` removed → schema default), and default flips `False→True` / `→None` (→ ValidationError = 500) — existing fixtures omit the keys entirely, so every one of these equals "absent → False" today                                                                                                                                                                                                                                                                                                                                                         | 11    | TEST-GAP   | `…x_validate_enrichment_data__mutmut_45`, `…x_validate_enrichment_data__mutmut_51`, `…x_validate_enrichment_data__mutmut_96`                         |
| B4  | `_transform_enrichment_data` **violence/face no-data + partial-data contract**: `{"detected": False, "score": 0.0}` / `{"detected": False, "count": 0}` init flips, `is_violent` default `False→True/None/removed`, `confidence` default `0→None` (max crash) `/→1`, score `0.0→None/1.0` — tests only supply fully-populated payloads                                                                                                                                                                                                                                                                                                                                                                             | 12    | TEST-GAP   | `…x__transform_enrichment_data__mutmut_96`, `…x__transform_enrichment_data__mutmut_120`, `…x__transform_enrichment_data__mutmut_133`                 |
| B5  | `_transform_enrichment_data` **image_quality input-key reads**: `iq.get("is_low_quality"/"quality_issues")` renamed to `None`-key / UPPER / XX (silently reads missing key → wrong None) and `quality_issues` default `[]→None/removed` — test fixture always sets every key                                                                                                                                                                                                                                                                                                                                                                                                                                       | 8     | TEST-GAP   | `…x__transform_enrichment_data__mutmut_166`, `…x__transform_enrichment_data__mutmut_172`, `…x__transform_enrichment_data__mutmut_176`                |
| B6  | String default `"" → "XXXX"` on `raw_description`/`carrying` — a missing-key payload leaks the literal `"XXXX"` into the API response (`raw_desc.split(", ")` on `"XXXX"` → `["XXXX"]` → upper=="XXXX")                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                            | 3     | TEST-GAP   | `…x__extract_clothing_from_enrichment__mutmut_32`, `…x_validate_enrichment_data__mutmut_73`, `…x_validate_enrichment_data__mutmut_81`                |
| B7  | `_get_full_image_for_video` **extract_thumbnail kwargs unasserted**: `video_path=None`, `video_path=`/`size=`/`output_path=`/`timestamp=` kwargs dropped, `size=None`, `size=(1921,1080)`, `size=(1920,1081)` — the one success-path test (`test_detections.py::TestGetDetectionImage::test_get_image_video_detection_full_extracts_frame` @ :1259) only asserts `assert_called_once()`                                                                                                                                                                                                                                                                                                                            | 8     | TEST-GAP   | `…x__get_full_image_for_video__mutmut_2`, `…x__get_full_image_for_video__mutmut_8`, `…x__get_full_image_for_video__mutmut_9`                         |
| B8  | `_get_full_image_for_video` frame guard: `if not frame_path or not exists(p)` → `and` (None frame falls through to `open(None)` → wrong error path) and `exists(None)`                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                             | 2     | TEST-GAP   | `…x__get_full_image_for_video__mutmut_10`, `…x__get_full_image_for_video__mutmut_13`                                                                 |
| B9  | `_get_full_image_for_video` **Cache-Control dropped/altered**: `headers=None`, headers kwarg removed, header renamed to XX-padded, value `"XXpublic, max-age=3600XX"` / `"PUBLIC, MAX-AGE=3600"` — the video-path success test asserts body + media_type only (image path's cache test at `test_detections_routes.py:1267` never exercises video)                                                                                                                                                                                                                                                                                                                                                                  | 5     | TEST-GAP   | `…x__get_full_image_for_video__mutmut_23`, `…x__get_full_image_for_video__mutmut_29`, `…x__get_full_image_for_video__mutmut_33`                      |
| B10 | `_parse_range_header` `if start > end:` → `>=` — single-byte ranges (`bytes=N-N`) wrongly rejected; all existing fixtures use start ≠ end                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                          | 1     | TEST-GAP   | `…x__parse_range_header__mutmut_68`                                                                                                                  |
| B11 | Ternary-guard flip `raw_desc if raw_desc else None` → `if (raw_desc) or True else None` — empty clothing description surfaces as `""` instead of `None`                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                            | 1     | TEST-GAP   | `…x_validate_enrichment_data__mutmut_94`                                                                                                             |
| C1  | `open()` argument mutants observable **only against the real filesystem** (`path=None`, mode `None`/removed/`"XXrbXX"`) — the unit suite mocks `builtins.open` wholesale (`patch("builtins.open", mock_open(...))`) so the args are never exercised; would need integration coverage; not behavior anyone asserts at unit level                                                                                                                                                                                                                                                                                                                                                                                    | 10    | LOW-VALUE  | `…x__get_full_image_for_image__mutmut_1`, `…x__get_full_image_for_image__mutmut_4`, `…x__get_full_image_for_video__mutmut_15`                        |
| C2  | `logger.warning/error(None)` — message text dropped; debuggability only, nothing asserted                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                          | 4     | LOW-VALUE  | `…x__get_full_image_for_image__mutmut_26`, `…x__get_full_image_for_image__mutmut_34`, `…x__get_full_image_for_video__mutmut_34`                      |
| C3  | **Stale-cache suspects**: survivors that _contradict existing assertions_ on disk — `detail=None`/detail-removed (image 22,24) vs `TestFileReadSpecificExceptions::test_get_full_image_file_not_found_error` (@ :2741: `assert "not found" in str(exc_info.value.detail).lower()`), and `clothing_description=raw_desc if raw_desc else None` kwarg dropped (validate 92 → `person.clothing_description` becomes None, should fail `test_validate_person_enrichment`'s `== "red shirt, black pants"`). WP4.3 widened-set pipeline likely did not execute those tests against these mutants. **Re-verify red/green in the serial WP4.4 pytest lane before trusting these verdicts; expect them to flip to killed.** | 3     | LOW-VALUE  | `…x__get_full_image_for_image__mutmut_22`, `…x__get_full_image_for_image__mutmut_24`, `…x_validate_enrichment_data__mutmut_92`                       |
| C4  | `detail=` line + `) from e` exception **chaining removed** (`raise HTTPException(...) from e` → plain raise) — status_code unchanged, only `__cause__` lost; nothing in the suite asserts exception chaining on these paths                                                                                                                                                                                                                                                                                                                                                                                                                                                                                        | 2     | LOW-VALUE  | `…x__get_full_image_for_video__mutmut_36`, `…x__get_full_image_for_video__mutmut_38`                                                                 |

Per-function reconciliation (verified against parsed diff set): clothing 10 (A1:2 A2:2 A3:2 A4:2 A8:1 B6:1) · vehicle 10 (A1:1 A2:1 A3:1 A5:2 B1:5) · transform 43 (A1:3 A2:3 A3:1 A5:16 B4:12 B5:8) · parse 10 (A7:3 A8:6 B10:1) · image 17 (A6:3 A7:4 C1:5 C2:3 C3:2) · video 29 (A6:3 A7:3 C1:5 C2:1 C4:2 B7:8 B8:2 B9:5) · validate 38 (A1:4 A2:4 A3:3 A4:4 A9:4 B2:4 B3:11 B6:2 B11:1 C3:1). Total 157.

## Drafted tests (6 highest-value TEST-GAP clusters)

All UNVERIFIED — not yet run red/green. TDD procedure for each: apply the cluster's mutant, the new assertion FAILS; on original source, PASSES; then keep the file green.

Style follows `backend/tests/unit/api/routes/test_detections.py` (module already imports `_extract_vehicle_from_enrichment`, `_parse_range_header`, `_transform_enrichment_data`, `validate_enrichment_data`, `get_detection_image`, `DetectionFactory`, `mock_open`, `patch`, `AsyncMock`; fixtures `mock_db_session`, `mock_video_processor`, `mock_thumbnail_generator` already defined there).

### T1 — kills B1 → append to `class TestExtractVehicleFromEnrichment` (test_detections.py)

```python
    def test_extract_vehicle_damage_present_key_with_schema_defaults(self):
        """vehicle_damage entry lacking has_damage/damage_types keys must use False/[] (not None/True)."""
        enrichment_data = {
            "vehicle_classifications": {
                "det_0": {"vehicle_type": "van", "confidence": 0.7, "is_commercial": False}
            },
            "vehicle_damage": {"det_0": {}},  # damage record present, schema keys absent
        }
        result = _extract_vehicle_from_enrichment(enrichment_data)
        assert result is not None
        assert result["damage_detected"] is False
        assert result["damage_types"] == []
```

Kills 51/53/56 (`False→None//removed/True`) and 61/63 (`[]→None/removed`).

### T2 — kills B2 + B3 (+ opportunistically B6's validate half and B11) → append to `class TestValidateEnrichmentData`

```python
    def test_validate_vehicle_flags_from_present_and_missing_keys(self):
        """is_commercial/has_damage read from present keys; absent keys default to False.

        Missing-key payloads also pin the crash/None mutants: is_commercial=None /
        has_damage=None raise pydantic ValidationError, and .get(None, ...) /
        .get("IS_COMMERCIAL", ...) silently read a never-present key (False) — only a
        present-key=True fixture distinguishes them.
        """
        present = validate_enrichment_data(
            {
                "vehicle_classifications": {
                    "det_0": {"vehicle_type": "truck", "is_commercial": True}
                },
                "vehicle_damage": {"det_0": {"has_damage": True}},
            }
        )
        assert present is not None and present.vehicle is not None
        assert present.vehicle.is_commercial is True   # kills key renames 45/49/50
        assert present.vehicle.has_damage is True      # kills key renames 28/30

        missing = validate_enrichment_data(
            {
                "vehicle_classifications": {"det_0": {"vehicle_type": "truck"}},
                "vehicle_damage": {"det_0": {}},
            }
        )
        assert missing.vehicle.is_commercial is False  # kills default-True 51 + None-defaults 96/98
        assert missing.vehicle.has_damage is False     # kills default-True 33 + None ValidationError 28

        no_damage_record = validate_enrichment_data(
            {"vehicle_classifications": {"det_0": {"vehicle_type": "truck"}}}
        )
        assert no_damage_record.vehicle.has_damage is False  # kills init flip 24

    def test_validate_person_is_suspicious_and_description_present_and_missing(self):
        """is_suspicious True is preserved; absent keys default False / clothing_description None."""
        present = validate_enrichment_data(
            {
                "clothing_classifications": {
                    "det_0": {"raw_description": "red jacket", "is_suspicious": True}
                }
            }
        )
        assert present.person.is_suspicious is True  # kills key renames 95/99/100

        missing = validate_enrichment_data({"clothing_classifications": {"det_0": {}}})
        assert missing.person.is_suspicious is False  # kills default-True 101 + None 96/98
        assert missing.person.clothing_description is None  # kills 73/81 ("XXXX") + 94 (or True)
        assert missing.person.carrying == []
```

### T3 — kills B4 → append to `class TestTransformEnrichmentData`

```python
    def test_transform_enrichment_contract_when_sections_absent(self):
        """Empty (non-None) enrichment still yields canonical violence/face dicts."""
        result = _transform_enrichment_data(1, {}, None)
        assert result["violence"] == {"detected": False, "score": 0.0}  # kills init flips 120/123
        assert result["face"] == {"detected": False, "count": 0}        # kills count init flip 96

    def test_transform_violence_present_without_is_violent_or_confidence(self):
        """violence_detection without keys defaults detected=False, score=0.0."""
        result = _transform_enrichment_data(1, {"violence_detection": {}}, None)
        assert result["violence"]["detected"] is False  # kills 128/130 (None) and 133 (True)
        assert result["violence"]["score"] == 0.0       # kills 137/139 (None) and 142 (1.0)

    def test_transform_faces_without_confidence_defaults_to_zero(self):
        """Face confidence defaults to 0 — max() must not crash and must not default to 1."""
        result = _transform_enrichment_data(1, {"faces": [{"bbox": [0, 0, 1, 1]}]}, None)
        assert result["face"]["count"] == 1
        assert result["face"]["confidence"] == 0  # kills 107/109 (None → max() TypeError) and 112 (1)
```

Note: `test_transform_enrichment_contract_when_sections_absent` may _additionally_ kill some A5 key-rename survivors (94/95/118/119/121/122) via the dict-equality asserts — acceptable bonus, A5 stays EQUIVALENT because canonical consumers are unaffected.

### T4 — kills B7 → append to `class TestGetDetectionImage`

```python
    @pytest.mark.asyncio
    async def test_get_full_image_video_requests_full_view_kwargs(
        self, mock_db_session, mock_video_processor
    ):
        """Full-image video path must request the FULL 1920x1080 frame at the given path."""
        from backend.api.routes.detections import _get_full_image_for_video

        mock_video_processor.extract_thumbnail = AsyncMock(return_value="/tmp/frame.jpg")  # noqa: S108
        with (
            patch(
                "backend.api.routes.detections.os.path.exists", return_value=True, autospec=True
            ),
            patch("builtins.open", mock_open(read_data=b"jpeg")),
        ):
            await _get_full_image_for_video(
                video_path="/videos/a.mp4", video_processor=mock_video_processor
            )

        mock_video_processor.extract_thumbnail.assert_called_once_with(
            video_path="/videos/a.mp4",
            output_path=None,
            timestamp=None,
            size=(1920, 1080),
        )
```

Kills all 8 of B7 (2–9): `None`, off-by-one, and dropped-kwarg variants all fail kwargs equality (dropped `output_path=`/`timestamp=` happen to be the real defaults but the _mock call shape_ must stay explicit — pin the contract).

### T5 — kills B8 (+13) and B10

```python
    @pytest.mark.asyncio
    async def test_get_full_image_for_video_rejects_none_frame_path(self, mock_video_processor):
        """extract_thumbnail returning None must 500 with the extraction-failure detail, not reach open()."""
        from backend.api.routes.detections import _get_full_image_for_video

        mock_video_processor.extract_thumbnail = AsyncMock(return_value=None)
        with pytest.raises(HTTPException) as exc_info:
            await _get_full_image_for_video(
                video_path="/videos/a.mp4", video_processor=mock_video_processor
            )
        assert exc_info.value.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert exc_info.value.detail == "Failed to extract frame from video"  # kills or→and (10)

    @pytest.mark.asyncio
    async def test_get_full_image_for_video_rejects_missing_frame_file(self, mock_video_processor):
        """frame_path returned but file absent on disk must 500 with the extraction-failure detail.

        Deliberately uses the REAL os.path.exists (no patch): the mutant exists(None)
        raises TypeError and is caught by the generic handler, producing a different detail.
        """
        from backend.api.routes.detections import _get_full_image_for_video

        mock_video_processor.extract_thumbnail = AsyncMock(return_value="/nonexistent/wp44-gone.jpg")  # noqa: S108
        with pytest.raises(HTTPException) as exc_info:
            await _get_full_image_for_video(
                video_path="/videos/a.mp4", video_processor=mock_video_processor
            )
        assert exc_info.value.detail == "Failed to extract frame from video"  # kills 13

    def test_parse_range_single_byte_range_is_valid(self):
        """start == end is a legal one-byte range; only start > end is invalid."""
        assert _parse_range_header("bytes=500-500", 10000) == (500, 500)  # kills >= flip (68)
```

Place the first two in `TestFileReadSpecificExceptions`, the last in `TestParseRangeHeader`.

### T6 — kills B9 → append to `class TestGetDetectionImage`

```python
    @pytest.mark.asyncio
    async def test_get_image_full_video_response_sets_cache_control(
        self, mock_db_session, mock_video_processor, mock_thumbnail_generator
    ):
        """Full-size frame response for video detections must carry the cache header (parity with image path)."""
        detection = DetectionFactory(
            id=21, file_path="/export/foscam/test.mp4", media_type="video", file_type="video/mp4"
        )
        mock_video_processor.extract_thumbnail = AsyncMock(return_value="/tmp/frame.jpg")  # noqa: S108
        with (
            patch(
                "backend.api.routes.detections.get_detection_or_404",
                return_value=detection,
                autospec=True,
            ),
            patch(
                "backend.api.routes.detections.os.path.exists", return_value=True, autospec=True
            ),
            patch("builtins.open", mock_open(read_data=b"full frame")),
        ):
            response = await get_detection_image(
                detection_id=21,
                full=True,
                db=mock_db_session,
                thumbnail_generator=mock_thumbnail_generator,
                video_processor=mock_video_processor,
            )

        assert response.headers["Cache-Control"] == "public, max-age=3600"
```

Kills 23/26 (header absent), 29 (renamed), 32/33 (mangled value).

## Notes

- B5 fold-in candidate: `_transform_enrichment_data(1, {"image_quality": {}}, None)` must yield `{"score": None, "is_blurry": None, "is_low_quality": None, "quality_issues": [], "quality_change_detected": None}` — kills all 8 of B5. Add as T3b in the same class if WP4.4 wants all 60 TEST-GAP mutants killable from drafted code.
- T2 covers B3's `__mutmut_41` too (dropped `is_commercial=` constructor kwarg: the present-key True fixture makes it default to False and fail the `is True` assert).
- C3 verdicts are suspect against the on-disk suite (assertions exist that should kill them). Re-run those five mutants in the serial WP4.4 lane before budgeting any "gap" time there; likely they flip to killed on their own (WP4.3 widened-set / stale-cache artifact).
- A5/A7 are EQUIVALENT _for canonical consumers_ (lowercase response keys, case-insensitive detail matching). Strict full-dict asserts (T3 test 1) may opportunistically kill some A5 mutants — fine, but doesn't change classification.
