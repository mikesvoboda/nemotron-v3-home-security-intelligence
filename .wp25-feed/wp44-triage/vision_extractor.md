# WP4.4 Triage Dossier — backend/services/vision_extractor.py

**Survivors: 457 / 1362 checked (905 killed)** — from `mutants/backend/services/vision_extractor.py.meta` (`exit_code == 0`).
Diffs extracted offline by diffing each `__mutmut_N` variant body against `__mutmut_orig` in the mutant copy
(`mutants/backend/services/vision_extractor.py`, 105k lines of complete variant bodies) — cross-validated against
`uv run mutmut show` (works; one spot-check agreed). Raw per-mutant diff dump: `/tmp/wp25/wp44-triage/diffs.txt`
(1371 lines); classifier script: `/tmp/wp25/wp44-triage/classify.py` (counts reconcile to 457).

**Covering test file (single):** `backend/tests/unit/services/test_vision_extractor.py` (3178 lines; `backend/tests/unit/services/test_enrichment_pipeline.py` only imports the two `format_*` renderers).
`mutmut-stats.json → tests_by_mangled_function_name` confirms every surviving mutant's function maps to that one file.

**Structural finding that explains the big clusters:** every existing test that reaches `extract_batch_attributes`
stubs out `_extract_vehicle_internal`, `_extract_person_internal`, `_extract_scene_internal`,
`_extract_environment_internal`, `_extract_florence_enhanced`, and `_batch_query_florence` (test file lines
1400–1445, 2094–2133, 2611–2634, 2680–2703, 2792–2811) with lambdas/mocks that **ignore their arguments and
return canned objects**. So the entire batch-query + internal-extractor + florence-enhanced subsystem is *never
executed* under test — its mutants can only survive. Conversely the pure functions (`resolve_vehicle_type_conflict`,
`detect_cross_validation_error`, `clean_vqa_output`) are called but asserted *weakly* (substring checks, `is not None`).

Totals: TEST-GAP 296 · LOW-VALUE 111 · EQUIVALENT 50 (sum = 457).

---

## Cluster table

Src line refs are in `backend/services/vision_extractor.py`; test refs in `backend/tests/unit/services/test_vision_extractor.py`.

| # | Pattern (function / concern) | n | Class | Notes |
|---|---|---|---|---|
| A3 | `_extract_florence_enhanced` (src 1562–1801): client-call args dropped (`dense_caption(None)`), results→`FlorenceEnhancedScene` field sets swapped to `None`, `has_data` or-chain `or→and` flips + `is not None→is None`, bbox validity gate (`x2 > x1 and y2 > y1` → or/`>=`/len==5), `security_phrases=None`, gather→field mis-assembly | 54 | TEST-GAP | Function **never executed**: all 5 tests that would reach it replace it with a mock (file lines 1437–1445, 2129–2133, 2630–2634, 2699–2703, 2811+). No test asserts any `FlorenceEnhancedScene` field or the None-on-empty contract. |
| B2 | Forwarding call-arg drops on public methods (`extract_scene_analysis`, `extract_vehicle/person/environment`, `extract_with_vqa`, `caption`/`get_scene_caption`, `query_florence`): `_query_florence(None, ...)` / `(image, None, ...)` / positional reorder / kwarg drop | 42 | TEST-GAP | Tests execute the lines via mocks like `mock_query(image, task, text_input="")` that never assert `image is img`, `task == "<VQA>"`, non-empty `text_input` (e.g. file lines 1287–1297, 2599–2609). Behavior change: real client would query the wrong image/task. |
| A7 | `_extract_scene_internal` (src 1942–1992): `results[i]` index shifts, `clean_vqa_output` drop, negation-gate flips (`and not` → `or`/`and`), `split(",")` → `split(None)`/`split("XX,XX")`, SceneAnalysis field sets → None / kwarg drop | 32 | TEST-GAP | Same mock-away problem; only the *public* `extract_scene_analysis` has a test (file 1187–1213) and it asserts just `unusual_objects`/description. |
| A6 | `_extract_environment_internal` (src 1994–2032): time_of_day keyword cascade (`"night"`/`"dusk"/"dawn"/"evening"` `in→not in`, UPPERCASE, `or→and`), `results[i]` shifts, `time_of_day="day"→None`, `artificial_light/weather=` field drops | 27 | TEST-GAP | The dusk/dawn/evening cascade IS tested — but only for the *public* `extract_environment_context` (file 1281–1387). The internal twin is mock-away'd, so 27 mutants of the duplicated cascade are invisible. |
| B1 | `extract_batch_attributes` (src 1467–1560): `det.get("detection_id", str(len(...)))` default mutants (`None`, dropped arg, `str(None)`), bbox `tuple()` conversion flips, `cropped=None`, `yolo_confidence=None` forwarding, class_name default `""→None` (crash), kwargs dropped from `_extract_*_internal` calls | 38 | TEST-GAP | The batch test (file 1389–1464) supplies explicit `detection_id`s, never checks auto-id keying, never checks what args the internals receive (mocks take `image, yolo_class=None, yolo_confidence=None` and ignore them). |
| C5 | `resolve_vehicle_type_conflict` (src 214–315): `>=`→`>` at `YOLO_HIGH_CONFIDENCE_THRESHOLD` (0.70) boundary, default-confidence `0.75→1.75` and `is not None→or True`, both-null `and→or` routing, result-field identity (`conflict_detected=False→True/None`, all `yolo_class=/yolo_confidence=/florence_type=` →None) and `confidence_note=` →None/drop on the 5 return branches | 23 | TEST-GAP | Tests exist (file 2232–2368 `TestYOLOFlorenceConfidenceOverride`) and call the function but assert only `resolved_type`/`source`/`conflict_detected`; they avoid the exact boundary value 0.70 (test at line 2349 uses 0.71/0.69 despite its "boundary" name) and never assert `confidence_note` text or the echoed input fields. |
| C1 | `format_vehicle/person/scene/environment/batch/detections_with_attributes` (src 2062–2303): heading strings `"## Vehicles"→"XX## VehiclesXX"`, join separators `", "→"XX, XX"`/`"\n"→"XX\nXX"`, `"unknown"→"UNKNOWN"`, `"unknown"→None` defaults on `det.get`, `"No detections."` decoration | 58 | LOW-VALUE | Real string-output changes but pure Nemotron-prompt display text; no consumer parses these headings programmatically (LLM prompt context). Some exact-string tests exist but don't cover the tweaked literals. Not worth kill tests beyond what exists. |
| A2 | `_extract_florence_enhanced` telemetry payload: `record_enrichment_model_call("florence-enhanced")` label mutations, `add_span_event("florence_enhanced.start", {...})` event-name/attr-label mutations, `extra={"service","duration_ms"}` dict key/value mutations, `duration_ms: *1000→/1000/*1001`, `observe_...duration` label | 29 | LOW-VALUE | Real changes to Prometheus label values / span attributes, but no test asserts them for this module (test_business_metrics.py exercises the metric helpers standalone). Dashboard-label fidelity; assert-later tier. |
| A10 | `_extract_vehicle_internal` (src 1803–1893): batch-call args, `resolved_vehicle_type=None` (kills cross-validation fallback), `yolo_confidence=`→None/drop to resolver and result, commercial-text query args | 11 | TEST-GAP | Executed for real inside cross-validation tests (2588+) but assertions stop at `vehicle_type`/`validation_note` substrings (file 2717–2731); no test asserts `vehicle_attrs.yolo_confidence` survives or the default-resolution path. |
| C3 | `clean_vqa_output` (src 542–548) "VQA> without a `?`" recovery branch: `find→rfind`, `find("<", vqa_idx)` start-arg drops, `!= -1 → == -1/!= -2/!= +1` guard flips, `else ""→"XXXX"` | 11 | TEST-GAP | All existing inputs (file 361–496) contain `?` or no `VQA>` — the regex already eats the `VQA>...?` form, so the manual recovery block never runs. Needs input like `"VQA>what is this<loc_1>answer"`. |
| A8 | `_extract_person_internal` (src 1895–1940): `results[3]→results[4]` index shift, `clothing/action = validate_and_clean_vqa_output(...)` → None/None-arg, PersonAttributes field drops, `carrying ... if carrying_clean else None → or True` (crash on `None.lower()`) | 10 | TEST-GAP | Same mock-away pattern as A7/A6. |
| B3 | Public `extract_scene_analysis` (src 1361–1405) parse logic: negation-gate flips, `abandoned_response=None`, `split` changes, `abandoned_items=None`, `abandoned_items=` kwarg drop | 9 | TEST-GAP | Test at file 1187–1213 asserts only `unusual_objects` + `scene_description`; `tools_detected`/`abandoned_items` never checked. |
| A5 | `_batch_query_florence` (src 1019–1056): `BatchExtractItem(image=None/prompt=None)`, `batch_results=None`, error→`""` mapping, fallback VQA prompt-split boundary (`len(prompt) > len(VQA_TASK)` → `>=`), fallback call args dropped | 9 | TEST-GAP | Every test that would reach it replaces it with `mock_batch_query` (file 2612–2628 etc.); the fallback path is unexecuted. |
| C2 | `BatchExtractionResult.to_dict` / `CrossValidationError.to_dict` (src 862–896, 153–166): serialized key renames (`"florence_enhanced"→"FLORENCE_ENHANCED"/"XX...XX"`), conditional-truth swaps (`if x or True` → `.to_dict()` on None → AttributeError crash path; `and False` → always None) | 9 | TEST-GAP | `to_dict` tests (file 308–344, 2967–2984) check a few values but not exact key sets nor the None-conditional branches. |
| C6 | `detect_cross_validation_error` (src 417–475): `is_yolo_vehicle` `or→and` gate, all `CrossValidationError(...)` payload kwargs →None (`yolo_class`, `yolo_confidence`, `florence_description`, `message`) on both error branches | 8 | TEST-GAP | Tests (file 2495–2567) assert `error.is_critical` + message substrings only; payload field echo never checked; the vehicle→person branch's `is_yolo_vehicle` membership gate only tested via plain `"car"`. |
| C7 | `generate_validation_note` (src 340–379): person-vehicle-mismatch boolean (`==` `and`→`or`, `in→not in`, `"person"→"PERSON"/"XXpersonXX"/not in`), final `if yolo_class and florence_type →or` branch routing | 8 | TEST-GAP | Note tests (file 2370–2446) use only strong cases (person+truck); no case where only the *second* disjunct should fire (yolo=car + florence mentions person) — that's where `and→or` is silent. |
| C4 | `is_valid_vqa_output` / `validate_and_clean_vqa_output` (src 577–669): `len < _MIN_VALID_LENGTH` → `<=` boundary (2-char outputs), `.lower()→.upper()` whitelist lookup flips | 5 | TEST-GAP | Tests (file 1684–1876) never use a 2-char non-whitelist output (e.g. `"ab"`) or an uppercase whitelisted response (`"YES"`/`"Red"`). |
| A1 | `_extract_florence_enhanced` log-only: `logger.warning("...")` → None/XXXX/upper/lower message text (6 warning sites) + `"No Florence enhanced data available"` message text | 24 | EQUIVALENT | Pure log-message text; `logger.info/warning(None)` still emits fine. No caplog assertions. |
| A9 | log-only in misc methods: `__init__` init message (4), `_batch_query_florence` debug fallback msg (4), `query_florence` warning (1), `extract_batch_attributes` summary f-string + `is not None→is None` inside it (2), `_crop_image` invalid-bbox warning (1), `extract_with_vqa` summary (1), `_extract_vehicle_internal` conflict warning (1) | 14 | EQUIVALENT | Log text only, incl. the `enhanced=...is None` which only changes a log word. |
| H3 | Equivalent-within-branch guard rewrites: `not x or not y → and` at src 192 (`is_semantically_equivalent`), 436 (`detect_cross_validation_error`), 602 (`is_valid_vqa_output`), 344/345 `""→"XXXX"` (`.lower()` keeps falsy guard), `_clean_vqa_output` #20/#32/#33 (`find` can only return −1), `_parse_yes_no` #5/#6 (already lower-cased) | 10 | EQUIVALENT | Mutated value can never reach the mutated comparison — proven by tracing the preceding `find`/`strip().lower()` calls. |
| D2 | Boundary-only numeric tweaks on degenerate inputs: `_crop_image` padding guards `width > 0` → `>= 0 / > 1 / and False / or True / else 1` (12), `_parse_yes_no[:20]→[:21]` | 13 | LOW-VALUE | Only observable at 1–2px boxes / 20–21-char responses; `_crop_image` tests (file 586–633) assert sizes for normal + degenerate boxes and clamp; the delta lives inside `prepare_bbox_for_crop`'s clamping. |
| H2 | Dead defensive guards: `caption.strip() if caption else "" → if caption or True` (public caption/get_scene_caption/environment ×2) — `_query_florence` always returns str (`""` on error, src 1010–1017), so the `or True` crash path is unreachable; `"XXXX"` empty-string defaults same falsy class | 4 | LOW-VALUE | Guard only fires on a state producers never create. |
| D4 | Dead defensive else-None: `_parse_none_response #6` `if response.strip() else None → or True`, `extract_vehicle_attributes #54` / `extract_person_attributes #60` `if clean else None → or True` | 3 | LOW-VALUE | Mutant path calls `_parse_none_response(None)` → AttributeError, but callers pre-guard truthiness (src 1138/1189-1191/1236-1238), so the branch never runs. |
| A4→A2? — merged above (bqf log mutants counted in A9). | | | | |
| D3 | `_extract_vehicle_terms/_extract_person_terms #5`: `found.add(term) → found.add(None)` | 2 | LOW-VALUE | Set stays same truthiness (term was a matched substring); only observable in the f-string repr inside `detect_cross_validation_error` messages. Killable only via exact-message assert. |
| D1 | `generate_validation_note #5/#6`: `"unknown"→"XXunknownXX"/"UNKNOWN"` confidence fallback text | 2 | LOW-VALUE | Note display text for a None confidence. |
| H1 | Falsy-equivalent field tweaks in `_extract_vehicle_internal`: `commercial_text=None→""`, `validation_note=None→""` initializers (branch never reassigns when left alone — dataclass treats both as unset) | 2 | EQUIVALENT | Both falsy throughout downstream use; only exact-`is None` asserts would see it. |

**Check: 54+42+32+27+38+23+58+29+11+11+10+9+9+9+8+8+5+24+14+10+13+4+3+2+2+2 = 457 ✓**
(TEST-GAP 296 = A3+B2+A7+A6+B1+C5+A10+C3+A8+B3+A5+C2+C6+C7+C4; LOW-VALUE 111 = C1+A2+D2+H2+D4+D3+D1; EQUIVALENT 50 = A1+A9+H3+H1)

---

## Drafted kill-tests (6 tests, ~225 of the 296 TEST-GAP survivors)

All drafted against `backend/tests/unit/services/test_vision_extractor.py` (style: `from __future__ import
annotations`, class + docstrings, `@pytest.mark.asyncio` (asyncio_mode=auto but existing tests decorate
anyway), inline `from PIL import Image`). **All UNVERIFIED — not yet run red/green.**
TDD procedure for each: apply the cluster's mutant diff → new assert fails (red); revert to original → passes (green).

### Test 1 — `TestFlorenceEnhancedRealExecution::test_wires_all_client_results_and_passes_image`
**Kills cluster A3** (core subset: field-set → None, call-arg drops, gather mis-assembly, `security_phrases=None`, `client=None`). Today all tests mock this method away; here the real `_extract_florence_enhanced` runs against a fake client that records arguments.

```python
class TestFlorenceEnhancedRealExecution:
    """Execute _extract_florence_enhanced against a fake Florence client.

    Previously every test replaced this method with a mock, so none of its
    client-call arguments or FlorenceEnhancedScene field assembly was covered.
    """

    def setup_method(self) -> None:
        reset_vision_extractor()

    def teardown_method(self) -> None:
        reset_vision_extractor()

    @pytest.mark.asyncio
    async def test_wires_all_client_results_and_passes_image(self) -> None:
        """Each capability result lands in its own field; every call gets the real image."""
        from types import SimpleNamespace

        from PIL import Image

        from backend.services.florence_client import BoundingBox as FlorenceBoundingBox

        extractor = VisionExtractor()
        img = Image.new("RGB", (100, 100), "white")
        seen: list[tuple] = []

        class FakeClient:
            async def detect_security_objects(self, image):
                seen.append(("security", image))
                return SimpleNamespace(detections=[{"label": "person"}])

            async def dense_caption(self, image):
                seen.append(("dense", image))
                return [SimpleNamespace(caption="a person at the door", bbox=[0, 0, 10, 10])]

            async def ocr_with_regions(self, image):
                seen.append(("ocr", image))
                return [SimpleNamespace(text="FedEx", bbox=[1, 2, 3, 4])]

            async def phrase_grounding(self, image, phrases):
                seen.append(("grounding", image, list(phrases)))
                return [
                    SimpleNamespace(
                        phrase="person near door",
                        bboxes=[[0, 0, 5, 5]],
                        confidence_scores=[0.9],
                    )
                ]

            async def describe_regions(self, image, boxes):
                seen.append(("regions", image, list(boxes)))
                return [SimpleNamespace(caption="white sedan parked")]

        extractor._florence_client = FakeClient()
        detections = [{"class_name": "car", "bbox": [10, 10, 90, 90], "detection_id": "v1"}]

        enhanced = await extractor._extract_florence_enhanced(img, detections, [])

        assert enhanced is not None
        # Each capability result in its own field (kills `enhanced.X = None` mutants)
        assert enhanced.dense_captions == [{"caption": "a person at the door", "bbox": [0, 0, 10, 10]}]
        assert enhanced.text_regions == [{"text": "FedEx", "bbox": [1, 2, 3, 4]}]
        assert enhanced.phrase_grounding == [
            {
                "phrase": "person near door",
                "bboxes": [[0, 0, 5, 5]],
                "confidence_scores": [0.9],
                "matched": True,
            }
        ]
        assert enhanced.security_objects is not None
        assert enhanced.region_descriptions == {"v1": "white sedan parked"}
        # Every client call received the real image (kills `image -> None` arg mutants)
        assert all(entry[1] is img for entry in seen)
        # Phrase grounding got the security phrase list (kills security_phrases=None)
        phrases = next(e for e in seen if e[0] == "grounding")[2]
        assert "person with weapon" in phrases
        # Region boxes built from the detection bbox (kills bbox validation mutants)
        boxes = next(e for e in seen if e[0] == "regions")[2]
        assert boxes == [FlorenceBoundingBox(x1=10, y1=10, x2=90, y2=90)]
```

### Test 2 — `TestFlorenceEnhancedRealExecution::test_returns_none_only_when_every_source_is_empty` + single-source parametrization
**Kills the rest of A3** (the `has_data` or-chain: #97–#103, #112 `if not has_data` inversion — each or→and swap needs exactly one sole-source dataset to expose it).

```python
    @pytest.mark.asyncio
    @pytest.mark.parametrize("source", ["security", "dense", "ocr", "phrase", "regions", "vqa"])
    async def test_single_available_source_keeps_enhanced_result(self, source: str) -> None:
        """has_data must be True if ANY capability returned data (kills or->and chain flips)."""
        from types import SimpleNamespace

        from PIL import Image

        from backend.services.florence_client import FlorenceUnavailableError

        extractor = VisionExtractor()
        img = Image.new("RGB", (100, 100), "white")

        def only(name: str):
            async def hit(image, *args):
                return object()

            async def fail(image, *args):
                raise FlorenceUnavailableError("down")

            return hit if name == source else fail

        class FakeClient:
            async def detect_security_objects(self, image):
                r = await only("security")(image)
                return None if r is None else SimpleNamespace(detections=[])

            async def dense_caption(self, image):
                r = await only("dense")(image)
                return [] if r is None else [SimpleNamespace(caption="c", bbox=[0, 0, 1, 1])]

            async def ocr_with_regions(self, image):
                r = await only("ocr")(image)
                return [] if r is None else [SimpleNamespace(text="t", bbox=[0, 0, 1, 1])]

            async def phrase_grounding(self, image, phrases):
                r = await only("phrase")(image)
                return [] if r is None else [
                    SimpleNamespace(phrase="p", bboxes=[[0, 0, 1, 1]], confidence_scores=[0.5])
                ]

            async def describe_regions(self, image, boxes):
                r = await only("regions")(image)
                return [] if r is None else [SimpleNamespace(caption="desc")]

        extractor._florence_client = FakeClient()

        async def fake_vqa(image, bbox=None):
            return {"threat": "yes"}

        extractor.extract_security_vqa = fake_vqa

        detections = [{"class_name": "car", "bbox": [0, 0, 50, 50], "detection_id": "v1"}]
        person_dets = [{"class_name": "person", "bbox": [0, 0, 20, 20], "detection_id": "p1"}]

        enhanced = await extractor._extract_florence_enhanced(
            img, detections, person_dets if source == "vqa" else []
        )
        assert enhanced is not None, f"source={source} should keep the enhanced result alive"

    @pytest.mark.asyncio
    async def test_returns_none_when_every_source_fails(self) -> None:
        """All capabilities unavailable -> None (kills `if has_data:` inversion)."""
        from PIL import Image

        from backend.services.florence_client import FlorenceUnavailableError

        extractor = VisionExtractor()
        img = Image.new("RGB", (100, 100), "white")

        class DeadClient:
            async def detect_security_objects(self, image):
                raise FlorenceUnavailableError("down")

            async def dense_caption(self, image):
                raise FlorenceUnavailableError("down")

            async def ocr_with_regions(self, image):
                raise FlorenceUnavailableError("down")

            async def phrase_grounding(self, image, phrases):
                raise FlorenceUnavailableError("down")

        extractor._florence_client = DeadClient()

        enhanced = await extractor._extract_florence_enhanced(img, [], [])
        assert enhanced is None
```

### Test 3 — `TestBatchQueryFlorenceRealExecution`
**Kills cluster A5 (all 9)** and the batch-call-arg halves of A6/A7/A8/A10. Exercises both the batch path and the VQA-split fallback with argument-recording mocks.

```python
class TestBatchQueryFlorenceRealExecution:
    """Execute _batch_query_florence: batch mapping and the individual-call fallback."""

    def setup_method(self) -> None:
        reset_vision_extractor()

    def teardown_method(self) -> None:
        reset_vision_extractor()

    @pytest.mark.asyncio
    async def test_batch_path_builds_items_with_image_and_prompt_and_maps_results(self) -> None:
        from types import SimpleNamespace

        from PIL import Image

        extractor = VisionExtractor()
        img = Image.new("RGB", (8, 8), "gray")
        captured: list = []

        class BatchClient:
            async def batch_extract(self, items):
                captured.append(list(items))
                return [SimpleNamespace(result=f"r{i}", error=None) for i in range(len(items))]

        extractor._florence_client = BatchClient()

        out = await extractor._batch_query_florence(img, ["<CAPTION>", "<VQA>What color?"])

        assert out == ["r0", "r1"]  # order + value mapping preserved
        assert all(item.image is img for item in captured[0])  # kills image=None mutants
        assert [item.prompt for item in captured[0]] == ["<CAPTION>", "<VQA>What color?"]

    @pytest.mark.asyncio
    async def test_fallback_splits_vqa_prompts_into_task_and_text(self) -> None:
        from PIL import Image

        from backend.services.florence_client import FlorenceUnavailableError

        extractor = VisionExtractor()
        img = Image.new("RGB", (8, 8), "gray")
        calls: list[tuple] = []

        class BrokenClient:
            async def batch_extract(self, items):
                raise FlorenceUnavailableError("no batch endpoint")

        async def mock_query(image, task, text_input=""):
            calls.append((image, task, text_input))
            return "fb"

        extractor._florence_client = BrokenClient()
        extractor._query_florence = mock_query

        out = await extractor._batch_query_florence(
            img, ["<VQA>What color is the car?", "<CAPTION>", "<VQA>"]
        )

        assert out == ["fb", "fb", "fb"]
        # VQA prompts with a question split into (image, "<VQA>", question); bare prompts do not.
        assert calls[0] == (img, "<VQA>", "What color is the car?")
        assert calls[1] == (img, "<CAPTION>")
        assert calls[2] == (img, "<VQA>")  # len boundary: exact-length prompt is NOT split
```

### Test 4 — `TestInternalExtractorsMapBatchResults`
**Kills clusters A7 (32) + A6 (27) + A8 (10)**: `results[i]` index shifts, negation gates, comma split, time-of-day cascade, field identity for the three internal extractors the batch test mocks away.

```python
class TestInternalExtractorsMapBatchResults:
    """_extract_scene_internal / _environment_internal / _person_internal run against
    an argument-recording _batch_query_florence; every result index must land in the
    right field and every prompt set must reach the batch API with the real image."""

    def setup_method(self) -> None:
        reset_vision_extractor()

    def teardown_method(self) -> None:
        reset_vision_extractor()

    @pytest.mark.asyncio
    async def test_scene_internal_maps_cleaned_vqa_results(self) -> None:
        from PIL import Image

        extractor = VisionExtractor()
        img = Image.new("RGB", (64, 64), "gray")
        seen: dict = {}

        async def mock_batch(image, prompts):
            seen["image"] = image
            seen["prompts"] = list(prompts)
            # caption, unusual (VQA echo artifact), tools csv, abandoned (negative)
            return ["A quiet driveway", "VQA>Any unusual objects?a cardboard box", "crowbar, ladder", "none"]

        extractor._batch_query_florence = mock_batch

        result = await extractor._extract_scene_internal(img)

        assert seen["image"] is img
        assert seen["prompts"][0] == "<CAPTION>"
        assert result.scene_description == "A quiet driveway"
        assert result.unusual_objects == ["a cardboard box"]
        assert result.tools_detected == ["crowbar", "ladder"]
        assert result.abandoned_items == []  # "none" is a negative response

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        ("time_response", "expected"),
        [("it is NIGHT time", "night"), ("dawn approaches", "dusk"), ("evening light", "dusk"), ("bright noon", "day")],
    )
    async def test_environment_internal_time_cascade(self, time_response: str, expected: str) -> None:
        from PIL import Image

        extractor = VisionExtractor()
        img = Image.new("RGB", (64, 64), "gray")

        async def mock_batch(image, prompts):
            return [time_response, "yes", "overcast"]

        extractor._batch_query_florence = mock_batch

        result = await extractor._extract_environment_internal(img)

        assert result.time_of_day == expected
        assert result.artificial_light is True
        assert result.weather == "overcast"

    @pytest.mark.asyncio
    async def test_person_internal_maps_clothing_carrying_action(self) -> None:
        from PIL import Image

        extractor = VisionExtractor()
        img = Image.new("RGB", (64, 64), "gray")
        seen: dict = {}

        async def mock_batch(image, prompts):
            seen["image"] = image
            seen["prompts"] = list(prompts)
            # caption, clothing, carrying, service_worker, action
            return ["Person walking", "blue hoodie", "a backpack", "no", "walking away"]

        extractor._batch_query_florence = mock_batch

        result = await extractor._extract_person_internal(img)

        assert seen["image"] is img
        assert len(seen["prompts"]) == 5  # full prompt list forwarded, none dropped
        assert result.clothing == "blue hoodie"
        assert result.carrying == "a backpack"
        assert result.is_service_worker is False
        assert result.action == "walking away"
        assert result.caption == "Person walking"
```

### Test 5 — `TestPublicExtractorsForwardQueryArguments`
**Kills cluster B2 (42) + B3 (9) + A10 call-arg subset**: an argument-asserting `_query_florence` mock instead of the arg-ignoring ones at file 1287/2599.

```python
class TestPublicExtractorsForwardQueryArguments:
    """Public extract_* methods must pass (real image, right task, non-empty VQA text)
    to every _query_florence call — existing mocks accepted None/omitted args silently."""

    def setup_method(self) -> None:
        reset_vision_extractor()

    def teardown_method(self) -> None:
        reset_vision_extractor()

    def _recording_query(self, calls: list):
        async def mock_query(image, task, text_input=""):
            calls.append((image, task, text_input))
            if task == "<CAPTION>":
                return "A scene caption"
            if task == "<DETAILED_CAPTION>":
                return "A detailed caption"
            return "ladder, crowbar"

        return mock_query

    def _assert_calls(self, calls: list, img) -> None:
        assert calls, "expected at least one _query_florence call"
        for image, task, text_input in calls:
            assert image is img, "image argument dropped or replaced"
            assert task in ("<CAPTION>", "<VQA>", "<DETAILED_CAPTION>", "<MORE_DETAILED_CAPTION>")
            if task == "<VQA>":
                assert text_input, "VQA query text dropped"

    @pytest.mark.asyncio
    async def test_extract_scene_analysis_forwards_args_and_parses_lists(self) -> None:
        from PIL import Image

        extractor = VisionExtractor()
        img = Image.new("RGB", (64, 64), "white")
        calls: list = []
        extractor._query_florence = self._recording_query(calls)

        result = await extractor.extract_scene_analysis(img)

        self._assert_calls(calls, img)
        assert result.scene_description == "A scene caption"
        assert result.tools_detected == ["ladder", "crowbar"]  # comma-split asserted
        assert result.unusual_objects == ["ladder, crowbar"]

    @pytest.mark.asyncio
    async def test_extract_vehicle_and_person_attributes_forward_args(self) -> None:
        from PIL import Image

        extractor = VisionExtractor()
        img = Image.new("RGB", (64, 64), "white")

        for call in (
            extractor.extract_vehicle_attributes(img, bbox=(1, 1, 20, 20)),
            extractor.extract_person_attributes(img, bbox=(1, 1, 20, 20)),
        ):
            calls: list = []
            extractor._query_florence = self._recording_query(calls)
            await call
            self._assert_calls(calls, img)

    @pytest.mark.asyncio
    async def test_environment_and_caption_methods_forward_args(self) -> None:
        from PIL import Image

        extractor = VisionExtractor()
        img = Image.new("RGB", (64, 64), "white")
        calls: list = []
        extractor._query_florence = self._recording_query(calls)

        env = await extractor.extract_environment_context(img)
        assert env.time_of_day == "day"

        calls.clear()
        extractor._query_florence = self._recording_query(calls)
        await extractor.get_scene_caption(img)
        self._assert_calls(calls, img)

        calls.clear()
        extractor._query_florence = self._recording_query(calls)
        await extractor.extract_with_vqa(img, ["Is a person visible?"])
        self._assert_calls(calls, img)
```

### Test 6 — `TestExtractBatchIdentityAndConfidenceWiring` + `TestResolveVehicleTypeConflictExactContract`
**Kills B1 (38) + most of C5 (23)**: auto det-id keying, crop/confidence forwarding, resolver boundary + note/field identity.

```python
class TestExtractBatchIdentityAndConfidenceWiring:
    """extract_batch_attributes: auto detection ids, bbox tuple conversion and
    yolo_confidence forwarding are invisible to the existing batch test (explicit
    ids, arg-ignoring internal mocks)."""

    def setup_method(self) -> None:
        reset_vision_extractor()

    def teardown_method(self) -> None:
        reset_vision_extractor()

    @pytest.mark.asyncio
    async def test_missing_detection_ids_key_by_index_and_confidence_is_forwarded(self) -> None:
        from PIL import Image

        from backend.services.vision_extractor import FlorenceEnhancedScene

        extractor = VisionExtractor()
        img = Image.new("RGB", (200, 200), "gray")
        forwarded: dict = {}

        async def mock_vehicle(image, yolo_class=None, yolo_confidence=None):
            forwarded["vehicle"] = (image, yolo_class, yolo_confidence)
            return VehicleAttributes(
                color="white",
                vehicle_type="sedan",
                is_commercial=False,
                commercial_text=None,
                caption="White sedan",
            )

        async def mock_person(image):
            forwarded["person"] = (image,)
            return PersonAttributes(
                clothing="hat",
                carrying=None,
                is_service_worker=False,
                action="walking",
                caption="Person walking",
            )

        async def mock_scene(image):
            return SceneAnalysis()

        async def mock_env(image):
            return EnvironmentContext(time_of_day="day", artificial_light=False, weather=None)

        async def mock_enhanced(image, all_detections, person_dets):
            return FlorenceEnhancedScene()

        extractor._extract_vehicle_internal = mock_vehicle
        extractor._extract_person_internal = mock_person
        extractor._extract_scene_internal = mock_scene
        extractor._extract_environment_internal = mock_env
        extractor._extract_florence_enhanced = mock_enhanced

        detections = [
            {"class_name": "car", "bbox": [10, 10, 100, 100], "confidence": 0.85},
            {"class_name": "person", "bbox": [120, 120, 190, 190]},
        ]

        result = await extractor.extract_batch_attributes(img, detections)

        # Auto ids: str(index) — kills det.get default -> None / str(None) mutants
        assert "0" in result.vehicle_attributes
        assert "1" in result.person_attributes
        # bbox converted list->tuple and cropped (kills `cropped = None` and isinstance flip)
        v_image, v_class, v_conf = forwarded["vehicle"]
        assert v_image is not None and v_image.size != img.size
        assert v_class == "car"
        assert v_conf == 0.85  # kills yolo_confidence=None / kwarg-dropped mutants
```

```python
class TestResolveVehicleTypeConflictExactContract:
    """Boundary value, default-confidence note, and per-branch field identity —
    existing tests (file 2232-2368) skip the 0.70 value and never read
    confidence_note or the echoed yolo_class/yolo_confidence/florence_type."""

    def test_exact_threshold_favors_yolo(self) -> None:
        from backend.services.vision_extractor import (
            YOLO_HIGH_CONFIDENCE_THRESHOLD,
            resolve_vehicle_type_conflict,
        )

        r = resolve_vehicle_type_conflict("bus", YOLO_HIGH_CONFIDENCE_THRESHOLD, "car")
        assert r.resolved_type == "bus"  # >= is inclusive; `>` mutant flips to florence
        assert r.conflict_detected is True

    def test_missing_confidence_uses_documented_default_075(self) -> None:
        from backend.services.vision_extractor import resolve_vehicle_type_conflict

        r = resolve_vehicle_type_conflict("bus", None, "car")
        assert r.resolved_type == "bus"
        assert "75%" in r.confidence_note  # kills 0.75->1.75 and the `or True` conf flip

    def test_empty_yolo_class_still_uses_florence_branch(self) -> None:
        from backend.services.vision_extractor import resolve_vehicle_type_conflict

        r = resolve_vehicle_type_conflict("", 0.5, "sedan")
        assert (r.resolved_type, r.source, r.conflict_detected) == ("sedan", "florence", False)
        assert r.confidence_note == "Only Florence classification available"
        # kills `not yolo and not florence -> or` routing flip (would return "unknown"/"both")

    def test_every_branch_echoes_inputs_and_exact_note(self) -> None:
        from backend.services.vision_extractor import resolve_vehicle_type_conflict

        r0 = resolve_vehicle_type_conflict(None, None, None)
        assert (r0.resolved_type, r0.source, r0.conflict_detected) == ("unknown", "both", False)
        assert r0.confidence_note == "No classification available from either source"

        r1 = resolve_vehicle_type_conflict("car", 0.85, "sedan")
        assert r1.confidence_note == "Semantic match: YOLO 'car' matches Florence 'sedan'"
        assert (r1.yolo_class, r1.florence_type, r1.resolved_type) == ("car", "sedan", "sedan")

        r2 = resolve_vehicle_type_conflict("bus", 0.9, "car")
        assert r2.confidence_note == "High confidence YOLO (90%) overrides Florence 'car'"
        assert r2.yolo_confidence == 0.9  # kills payload-field -> None mutants

        r3 = resolve_vehicle_type_conflict("bus", 0.55, "motorcycle")
        assert r3.confidence_note == "Low YOLO confidence (55%), using Florence 'motorcycle'"
        assert r3.conflict_detected is False
```

Remaining TEST-GAP clusters (C1 n/a — LOW; C2/C3/C4/C6/C7 ≈ 41) are cheap to kill with exact-assert
extensions of existing tests: exact key sets for `to_dict` (file 308, 2967); one `clean_vqa_output("VQA>what is this<loc_1>answer")` case; `"ab"`/`"YES"` boundary calls; a `generate_validation_note(yolo_class="car", florence_type="a person walking", conflict_detected=True)` second-disjunct case; payload-field asserts on `detect_cross_validation_error`'s returned object.

---

## Covering-test file:line index

| Concern | Test location (`backend/tests/unit/services/test_vision_extractor.py`) | Weakness |
|---|---|---|
| clean_vqa_output | `TestCleanVqaOutput:361–496` | no `VQA>`-without-`?` input (C3) |
| is_valid / validate_and_clean | `TestIsValidVQAOutput:1684`, `TestValidateAndCleanVQAOutput:1798` | no 2-char / UPPERCASE boundary (C4) |
| crop | `TestVisionExtractorHelpers:531` (crop at 586–633) | normal + degenerate only (D2 low value) |
| env public cascade | `TestVisionExtractorExtraction:951` (1281–1387) | covers public, not `_extract_environment_internal` (A6) |
| batch | `test_extract_batch_attributes:1389–1464` | mocks all internals; explicit ids; ignores args (B1, A3, A5–A8, A10) |
| resolver | `TestYOLOFlorenceConfidenceOverride:2232–2368` | no 0.70 value, no note/field identity (C5) |
| validation notes | `TestYOLOFlorenceValidationNotes:2370–2446` | only first disjunct (C7) |
| cross-validation error | `TestPersonVehicleMismatchError:2495–2567` | no payload asserts (C6) |
| batch x-val | `TestExtractBatchAttributesWithCrossValidation:2570–2834` | arg-ignoring mocks (B2) |
| to_dict | `:308–344`, `TestCrossValidationError:2940–2984` | no exact key sets (C2) |
| formatters | `:636–948` | partial literal coverage (C1 low value) |

**Status: UNVERIFIED.** No tests were run and no repo files were modified (read-only pass per task constraints).
