# WP4.4 Triage Dossier — `backend/services/vision_extractor.py`

**Survivors: 135** (exit_code 0) / 1362 generated mutants — 475 killed, 752 unchecked.
**Classes: TEST-GAP 128 · LOW-VALUE 1 · EQUIVALENT 6.** Partition mechanically verified: every survivor key appears in exactly one cluster (script in Notes).

## Method

- Survivor keys from `mutants/backend/services/vision_extractor.py.meta` → `exit_code_by_key`.
- Diffs: AST-parsed the mutant copy `mutants/backend/services/vision_extractor.py`, `ast.unparse`'d every `*__mutmut_N` variant against its `*__mutmut_orig` sibling (byte-verified against `uv run mutmut show` on a sample). Full clean diff dump: `/tmp/wp25/survivor_diffs_clean.txt`. No test execution, no repo writes.
- All coverage from **`backend/tests/unit/services/test_vision_extractor.py`** (3178 lines); one extra caller in `backend/tests/unit/services/test_enrichment_pipeline.py` (`test_enrich_batch_with_tracking_success_rate`, touches only `format_batch_extraction_result`'s killed mutants).

Mutant-key prefix `backend.services.vision_extractor.` omitted below. Method-qualified keys: `person` = `xǁVisionExtractorǁextract_person_attributes`, `vehicle` = `…extract_vehicle_attributes`, `scene` = `…extract_scene_analysis`, `envctx` = `…extract_environment_context`, `caption` = `…extract_scene_caption`, `qf` = `…_query_florence`; `cvv` = `x_detect_cross_validation_error`, `fda` = `x_format_detections_with_attributes`, `fbe` = `x_format_batch_extraction_result`, `fva/fpa/fsa/fenv` = the `x_format_{vehicle,person}_attributes`/`scene_analysis`/`environment_context`, `ivqa` = `x_is_valid_vqa_output`, `BER/CEV` = `xǁBatchExtractionResultǁto_dict` / `xǁCrossValidationErrorǁto_dict`.

## Final cluster table (sums to 135, script-verified)

| ID | Pattern | N | Class | Example keys |
|----|---------|---|-------|--------------|
| C01 | `_query_florence(image→None)` at caller sites (image identity never checked by mocks) | 19 | TEST-GAP | `qf__7`, `envctx__8`, `person__3` |
| C02 | `_query_florence` VQA task-arg clobbered/dropped → question loses `<VQA>` prefix; keyword-matching mocks still route it | 20 | TEST-GAP | `envctx__9`, `person__29`, `scene__30` |
| C03 | `_query_florence` unavailable-path `logger.warning(f'Florence service unavailable: {e}')` → `logger.warning(None)` | 1 | LOW-VALUE | `qf__11` |
| C04 | `detect_cross_validation_error` returned-error evidence fields (`yolo_class`/`yolo_confidence`/`florence_description`) → `None` (both mismatch branches) | 6 | TEST-GAP | `cvv__23`, `cvv__39` |
| C05 | `cvv` vehicle-person-branch `message` → `None` (tests assert `is_critical` only) | 1 | TEST-GAP | `cvv__36` |
| C06 | `cvv` early-exit guard `not a or not b → not a and not b` (single-`None` input: mutant AttributeError / wrong branch) | 1 | TEST-GAP | `cvv__1` |
| C07 | `cvv` `is_yolo_vehicle` membership `VEHICLE_TERMS or YOLO_TO_FLORENCE_EQUIVALENCE → and` — tests use only `"car"`, which is in BOTH collections | 1 | TEST-GAP | `cvv__11` |
| C08 | `_extract_{person,vehicle}_terms` `found.add(term) → found.add(None)` (set becomes `{None}`, poisons message/union typing) | 2 | TEST-GAP | `x__extract_person_terms__5` |
| C09 | `extract_scene_analysis` abandoned/tools pipeline: query skipped, `clean_vqa_output(None)`, tools-guard `and→or` (fires on empty), tools `split(None)`/`split('XX,XX')`, abandoned negation flip, `abandoned_items=None` masked by field default, dropped kwarg — tests never read `abandoned_items` and answer single-token tools | 9 | TEST-GAP | `scene__24`, `scene__50`, `scene__62` |
| C10 | `to_dict()` dict-**key** string mutations (`florence_enhanced`, `yolo_confidence`, `florence_description`) — to_dict tests check 4 of 5 keys / 3 of 5 keys via substring | 6 | TEST-GAP | `BER__13`, `CEV__8` |
| C11 | `BatchExtractionResult.to_dict` conditional-serialization guards: `scene/env or True` → `.to_dict()` on `None` = AttributeError; `florence_enhanced and False` → never serialized | 3 | TEST-GAP | `BER__8`, `BER__15` |
| C12 | format prefix empty-branch `'' → 'XXXX'` (vehicle/person attribute prefix) | 2 | TEST-GAP | `fva__5`, `fpa__5` |
| C13 | format prefix guard `if detection_id → or True` → renders literal `"[None] "` for id-less detections | 2 | TEST-GAP | `fva__4`, `fpa__4` |
| C14 | `format_environment_context` artificial-light message clobber (day test only asserts absence; night test's substring matches inside `XX…XX`) | 1 | TEST-GAP | `fenv__3` |
| C15 | `format_detections_with_attributes` bbox rendering: `bbox=None`, `det.get(None,[])`, default `None`, `bbox_str=None`, `if bbox and False`, `''.join`, `str(None)`, `'XX[]XX'`, key clobbers — no test supplies a minimal or float bbox dict | 11 | TEST-GAP | `fda__27`, `fda__34`, `fda__39` |
| C16 | `format_detections_with_attributes` missing-key defaults (`class_name → None/'XXXX'/'UNKNOWN'`, `confidence → None (crash on {:.0%})/1.0`) — every test dict is fully populated | 7 | TEST-GAP | `fda__12`, `fda__26` |
| C17 | `fda` attribute-segment text: `commercial` label ×3, `', '`-join clobbers in vehicle & person attr branches (single-element lists make `'XX'` invisible), `'service worker'` label | 6 | TEST-GAP | `fda__49`, `fda__56`, `fda__64` |
| C18 | `fda` `det_id` default `'' → None/'XXXX'` (misses attributes keyed `''`) | 3 | TEST-GAP | `fda__4`, `fda__9` |
| C19 | `fda` `'No detections.'` sentinel — test uses `"No detections" in`, substring survives `XX…XX` | 1 | TEST-GAP | `fda__72` |
| C20 | `fbe` `det_id` not forwarded: `format_{vehicle,person}_attributes(attrs, None)` / arg dropped → `[None]`/no prefix; batch tests never assert `" [v1] "` | 4 | TEST-GAP | `fbe__8`, `fbe__22` |
| C21 | `fbe` section-header sentinels (`## Vehicles`, `## Persons`, `## Scene Analysis\n`, `## Environment\n`, no-data string) — substring matching survives `XX…XX` | 5 | TEST-GAP | `fbe__3`, `fbe__29` |
| C22 | multi-element block `'\n'.join` / `'\n\n'.join` clobbers — all fixtures render ONE vehicle + optional single sections, so the join is never invoked | 7 | TEST-GAP | `fbe__47`, `fda__76`, `fva__21` |
| C24 | `is_valid_vqa_output` length boundary `< 2 → <= 2` (2-char garbage `"ab"`/`"xy"` accepted) | 1 | TEST-GAP | `ivqa__11` |
| C25 | prompt-line `', '`/`', '` join delimiter clobbers with single-element fixtures (env final join, person/vehicle detail joins, scene unusual/abandoned joins) | 5 | TEST-GAP | `fenv__8`, `fsa__5`, `fpa__17` |
| C26 | `format_scene_analysis` `'No notable scene elements detected.'` sentinel clobber (substring assertion) | 1 | TEST-GAP | `fsa__13` |
| C28 | `format_person_attributes` service-worker detail message text (`XX…XX`, lowercase) — substring assertion | 2 | TEST-GAP | `fpa__12`, `fpa__13` |
| C35 | `extract_{person,vehicle}_attributes` validation guard `if clean else None → or True` — `validate_and_clean_vqa_output` returns **None** on garbage input ⇒ `_parse_none_response(None)` AttributeError; no test feeds garbage carrying/commercial_text while keeping the other answers valid | 2 | TEST-GAP | `person__60`, `vehicle__54` |
| E1 | `ivqa__1`: `not text or not text.strip()` → `and`. Equivalent: whitespace-only truthy text has falsy `.strip()`, so `False` returned either way; empty short-circuits both | 1 | EQUIVALENT | `ivqa__1` |
| E2 | `envctx__34`: `if time_response or True`. `_query_florence` contract returns `str`; for any str, `.lower()` is the same result (None is out-of-contract) | 1 | EQUIVALENT | `envctx__34` |
| E3 | `ivqa__8`: `.lower()→.upper()`. All garbage regexes are `re.IGNORECASE` and `_VALID_SHORT_RESPONSES` is all-lowercase ⇒ no input changes verdict | 1 | EQUIVALENT | `ivqa__8` |
| E4 | `caption__7`: `if caption or True else ''`. For `""`, `"".strip()` == `""` ⇒ same result under the `str` contract | 1 | EQUIVALENT | `caption__7` |
| E5 | `envctx__36`: empty-time fallback `'' → 'XXXX'`. `'XXXX'` contains no night/dusk/dawn/evening keyword ⇒ still classified `"day"` | 1 | EQUIVALENT | `envctx__36` |
| E6 | `fda__36`: `if bbox or True`. Empty bbox ⇒ `f"[{''.join([])}]"` == `"[]"` == else-branch literal | 1 | EQUIVALENT | `fda__36` |

TEST-GAP clusters sum to 128; + C03 (1) + E1–E6 (6) = **135** ✔ (script-verified partition, see Notes).

## Why the TEST-GAPs are gaps (covering test file: `backend/tests/unit/services/test_vision_extractor.py`)

| Cluster(s) | Existing tests (line) | Missing assertion |
|---|---|---|
| C01/C02 | `test_extract_vehicle_attributes_calls_florence` :1012, `…person…` :1155, `test_extract_scene_analysis` :1187, `test_extract_environment_context` :1281, caption tests :1215 | mocks `mock_query(image, task, text_input="")` never record/inspect `image` or `task`; their `return ""` fallback hides mis-routing |
| C04/C05 | `TestPersonVehicleMismatchError` :2495 (asserts `is_critical` + message substrings), `TestCrossValidationError` :2940 (constructs dataclass directly) | returned error echoes inputs (`yolo_class`, `yolo_confidence`, `florence_description`, non-empty `message`) |
| C06 | none call with one `None` argument | `yolo_class=None` / `florence_description=None` ⇒ `None` result, no crash |
| C07 | all cvv tests use `"car"` (member of both collections) | a class in only one collection (`"van"` ∈ VEHICLE_TERMS, ∉ equivalence map) still flags vehicle side |
| C08 | cvv tests never inspect the term-set content in `message` | message names the discovered terms; set stays `set[str]` |
| C09 | :1187 answers `"no"` for abandoned, never touches `result.abandoned_items`; tools answer `"ladder"` single-token | abandoned positive ⇒ `[answer]`; negatives ⇒ `[]` (not `None`); `"ladder, pry bar"` ⇒ two items |
| C10/C11 | `test_batch_extraction_result_to_dict` :308 (4 keys checked, `florence_enhanced` never), `test_cross_validation_error_to_dict` :2967 | full key set of both payloads; `None` members serialize to `None`, present members to dicts |
| C12–C22, C25, C26, C28 | `TestFormat*` :636–:948 — every assertion is `"needle" in result` with fully-populated single-entity fixtures | exact rendered strings: sentinels equal, prefixes absent when id-less, multi-entity/multi-item joins with `", "` and `"\n"`, `.get` defaults against minimal dicts, float→int bbox |
| C24 | `test_rejects_short_garbage_outputs` :1784 (len-1 + valid shorts only) | 2-char non-whitelist rejected |
| C35 | Nem-3304 tests :1976–:2160 validate whole-attribute garbage; none combine valid caption/color + GARBAGE carrying/commercial_text | validation-failed ⇒ attribute `None`, no AttributeError |
| C03 | `test_query_florence_handles_unavailable_error` :963 checks the `""` fallback only | warning log text (optional kill via `caplog`) |

## Drafted tests — 5 for the highest-value clusters

Target file: `backend/tests/unit/services/test_vision_extractor.py` (async classes need `@pytest.mark.asyncio` as existing ones do). **All UNVERIFIED — not yet run red/green.**
TDD procedure (each): against every mutant variant in the cluster the new assertion must fail/error; against the unmutated original it must pass; then rerun the sweep for this module and confirm the cluster keys flip to killed.

### T1 `test_query_florence_call_args_propagation` — kills C01 (19) + C02 (20) = 39

```python
    @pytest.mark.asyncio
    async def test_query_florence_call_args_propagation(self) -> None:
        """Extraction methods must forward the image and the exact task to _query_florence.

        WP4.4 C01/C02: existing mocks dispatch on text_input only, so clobbered
        image/task args route invisibly. // UNVERIFIED - not yet run red/green
        """
        from PIL import Image

        extractor = VisionExtractor()
        calls: list[tuple[object, str, str]] = []

        async def mock_query(image, task, text_input=""):
            calls.append((image, task, text_input))
            return ""

        extractor._query_florence = mock_query
        img = Image.new("RGB", (64, 64), color="white")

        await extractor.extract_scene_caption(img)
        assert calls[-1][:2] == (img, "<DETAILED_CAPTION>")

        calls.clear()
        await extractor.extract_scene_analysis(img)
        assert len(calls) == 4
        assert all(c[0] is img for c in calls)
        assert calls[0][1] == "<CAPTION>"
        assert [c[1] for c in calls[1:]] == ["<VQA>"] * 3

        calls.clear()
        await extractor.extract_environment_context(img)
        assert [c[0] for c in calls] == [img] * 3, "gather must pass the image 3x"
        assert [c[1] for c in calls] == ["<VQA>"] * 3
        for c in calls:
            assert c[2] in (
                ENVIRONMENT_QUERIES["time_of_day"],
                ENVIRONMENT_QUERIES["artificial_light"],
                ENVIRONMENT_QUERIES["weather"],
            )

        calls.clear()
        await extractor.extract_vehicle_attributes(img)
        assert [c[0] for c in calls] == [img] * 4  # caption, color, type, commercial
        assert calls[0][1] == "<CAPTION>"
        assert all(c[1] == "<VQA>" for c in calls[1:])

        calls.clear()
        await extractor.extract_person_attributes(img)
        assert [c[0] for c in calls] == [img] * 5
        assert calls[0][1] == "<CAPTION>"
        assert all(c[1] == "<VQA>" for c in calls[1:])
```

Add `ENVIRONMENT_QUERIES` to the import block at :14. Kill check: C01 ⇒ `calls[i][0] is None` (or `c[0] is img` fails via positional shift); C02 ⇒ task slot holds question/`""`/`None`.

### T1b `test_query_florence_forwards_image_to_client` — kills `qf__7` (completes C01: 19/19)

```python
    @pytest.mark.asyncio
    async def test_query_florence_forwards_image_to_client(self) -> None:
        """_query_florence must hand the PIL image to the Florence HTTP client.

        WP4.4 qf__7: client call site passes None image; existing client-mock
        test (:983) records prompts only. // UNVERIFIED - not yet run red/green
        """
        from PIL import Image

        extractor = VisionExtractor()
        received: list[object] = []

        async def mock_extract(image, prompt):
            received.append(image)
            return "ok"

        extractor._florence_client.extract = mock_extract
        img = Image.new("RGB", (32, 32), color="black")
        out = await extractor._query_florence(img, "<VQA>", "what color?")

        assert out == "ok"
        assert received[-1] is img
```

### T2 `test_scene_analysis_abandoned_items_pipeline` — kills C09 (9)

```python
    @pytest.mark.asyncio
    async def test_scene_analysis_abandoned_items_pipeline(self) -> None:
        """Abandoned answers captured, negatives rejected, tools comma-parsed.

        WP4.4 C09: test_extract_scene_analysis (:1187) never reads
        abandoned_items and answers tools with a single token.
        // UNVERIFIED - not yet run red/green
        """
        from PIL import Image

        extractor = VisionExtractor()
        img = Image.new("RGB", (100, 100), color="gray")

        async def positive_query(image, task, text_input=""):
            if task == "<CAPTION>":
                return "Driveway scene"
            low = text_input.lower()
            if "unusual" in low:
                return "disturbance near garage"
            if "tools" in low:
                return "ladder, pry bar"
            if "abandoned" in low:
                return "cardboard box near door"
            return ""

        extractor._query_florence = positive_query
        result = await extractor.extract_scene_analysis(img)
        assert result.unusual_objects == ["disturbance near garage"]
        assert result.tools_detected == ["ladder", "pry bar"]
        assert result.abandoned_items == ["cardboard box near door"]

        async def negative_query(image, task, text_input=""):
            return "" if task == "<CAPTION>" else "none"

        extractor._query_florence = negative_query
        empty = await extractor.extract_scene_analysis(img)
        assert empty.unusual_objects == []
        assert empty.tools_detected == []
        assert empty.abandoned_items == []  # list per field default, NOT None
        assert empty.to_dict()["abandoned_items"] == []
```

Kill check: `scene__24/37/38` (query skipped / clean(None)) ⇒ positive leg `[]`; `__53` (negation flip) ⇒ negative leg `["none"]`; `__45` (guard `or`) ⇒ negative leg `tools_detected == ["none"]`; `__49/50` ⇒ tools not split; `__55/62` ⇒ `None`/`[]` on positive leg, and `__55`'s `None` caught by `== []` / to_dict.

### T3 `test_format_functions_exact_output` — kills C12 (2), C13 (2), C14 (1), C19 (1), C20 (4), C21 (5), C22 (7), C25 (5), C26 (1), C28 (2) = 30 (+C10/C11 partially via batch)

```python
    def test_format_functions_exact_output(self) -> None:
        """Exact rendered strings for every format_* helper.

        WP4.4: substring assertions let sentinel, prefix and join-delimiter
        mutants live. // UNVERIFIED - not yet run red/green
        """
        vehicle = VehicleAttributes(
            color="white", vehicle_type="van", is_commercial=True,
            commercial_text="FedEx", caption="FedEx van",
        )
        person = PersonAttributes(
            clothing="uniform", carrying="package", is_service_worker=True,
            action="delivering", caption="Delivery worker",
        )

        assert format_vehicle_attributes(vehicle) == (
            "Vehicle: FedEx van\n  Color: white, Type: van, Commercial vehicle (FedEx)"
        )
        assert format_person_attributes(person) == (
            "Person: Delivery worker\n  Wearing: uniform, Carrying: package, "
            "Action: delivering, Appears to be service/delivery worker"
        )
        # id-less fallbacks must emit no prefix at all (never 'XXXX' / '[None] ')
        assert not format_vehicle_attributes(vehicle, "").startswith("[")
        assert not format_person_attributes(person, "").startswith("[")

        scene = SceneAnalysis(
            unusual_objects=["ladder", "crowbar on ground"],
            tools_detected=["hammer"],
            abandoned_items=["box", "bag"],
            scene_description="",
        )
        assert format_scene_analysis(scene) == (
            "Unusual objects: ladder, crowbar on ground\n"
            "Tools detected: hammer\n"
            "Abandoned items: box, bag"
        )
        assert format_scene_analysis(SceneAnalysis()) == "No notable scene elements detected."

        assert format_environment_context(
            EnvironmentContext(time_of_day="night", artificial_light=True, weather="clear")
        ) == "Time of day: night, Artificial light source detected, Weather: clear"

        assert format_batch_extraction_result(BatchExtractionResult()) == (
            "No vision extraction data available."
        )
        second_vehicle = VehicleAttributes(
            color="red", vehicle_type="truck", is_commercial=False,
            commercial_text=None, caption="Red truck",
        )
        batch = BatchExtractionResult(
            vehicle_attributes={"v1": vehicle, "v2": second_vehicle},
            person_attributes={"p1": person},
        )
        assert format_batch_extraction_result(batch) == (
            "## Vehicles\n"
            "[v1] Vehicle: FedEx van\n"
            "  Color: white, Type: van, Commercial vehicle (FedEx)\n"
            "[v2] Vehicle: Red truck\n  Color: red, Type: truck\n"
            "\n"
            "## Persons\n"
            "[p1] Person: Delivery worker\n"
            "  Wearing: uniform, Carrying: package, Action: delivering, "
            "Appears to be service/delivery worker"
        )

        assert format_detections_with_attributes([], BatchExtractionResult()) == "No detections."
```

Two-entity vehicle block exercises the `'\n'.join` and det_id forwarding the single-entity fixtures skip. Re-verify the literal block char-for-char on the green run.

### T4 `test_format_detections_defaults_and_bbox_rendering` — kills C15 (11) + C16 (7) + C17 (6) + C18 (3) = 27

```python
    def test_format_detections_defaults_and_bbox_rendering(self) -> None:
        """Minimal detection dicts must hit .get() defaults; bbox must render exact.

        WP4.4: all existing detection fixtures are fully-populated with
        single-attr lists, so defaults, bbox guards and ', ' separators
        inside [ ... ] segments are untested.
        // UNVERIFIED - not yet run red/green
        """
        assert format_detections_with_attributes([{"class_name": "car"}], BatchExtractionResult()) == (
            "- car (0%) at []"
        )
        assert format_detections_with_attributes([{}], BatchExtractionResult()) == (
            "- unknown (0%) at []"
        )

        float_bbox = [{
            "detection_id": "d", "class_name": "person",
            "confidence": 0.88, "bbox": [50.7, 50.2, 150.9, 300.1],
        }]
        assert format_detections_with_attributes(float_bbox, BatchExtractionResult()) == (
            "- person (88%) at [50, 50, 150, 300]"
        )

        vehicle = VehicleAttributes(
            color="blue", vehicle_type="sedan", is_commercial=True,
            commercial_text="Uber", caption="Blue Uber sedan",
        )
        person = PersonAttributes(
            clothing="red jacket", carrying="box", is_service_worker=True,
            action="walking", caption="Delivery person",
        )
        result = BatchExtractionResult(
            vehicle_attributes={"v": vehicle}, person_attributes={"p": person}
        )
        dets = [
            {"detection_id": "v", "class_name": "car", "confidence": 0.95,
             "bbox": [100, 100, 200, 200]},
            {"detection_id": "p", "class_name": "person", "confidence": 0.88,
             "bbox": [50, 50, 150, 300]},
        ]
        assert format_detections_with_attributes(dets, result) == (
            "- car (95%) at [100, 100, 200, 200] [blue, sedan, commercial: Uber]\n"
            "- person (88%) at [50, 50, 150, 300] [red jacket, carrying box, "
            "walking, service worker]"
        )

        # detection dict without detection_id must not pick up attrs via
        # None/'XXXX' lookup and must not crash
        orphan = [{"class_name": "car", "confidence": 0.5, "bbox": [0, 0, 1, 1]}]
        assert format_detections_with_attributes(orphan, result) == (
            "- car (50%) at [0, 0, 1, 1]"
        )
```

Kill notes: `confidence → None` default crashes `"{:.0%}"`; `→ 1.0` renders `(100%)`; `bbox = det.get(None, [])` alone still renders `"[]"` green — the float-bbox line kills it (lookup key must be `"bbox"`).

### T5 `test_detect_cross_validation_error_payload_and_boundaries` — kills C04 (6) + C05 (1) + C06 (1) + C07 (1) + C08 (2) = 11

```python
    def test_detect_cross_validation_error_payload_and_boundaries(self) -> None:
        """Errors must echo full evidence; guards and term-collection boundaries hold.

        WP4.4: TestPersonVehicleMismatchError (:2495) asserts is_critical and
        message substrings only; evidence fields, one-side-None guards and the
        VEHICLE_TERMS / YOLO_TO_FLORENCE_EQUIVALENCE membership split untested.
        // UNVERIFIED - not yet run red/green
        """
        from backend.services.vision_extractor import detect_cross_validation_error

        error = detect_cross_validation_error(
            yolo_class="person", yolo_confidence=0.88,
            florence_description="A white truck parked in the driveway",
        )
        assert error is not None
        assert error.is_critical is True
        assert error.yolo_class == "person"
        assert error.yolo_confidence == 0.88
        assert error.florence_description == "A white truck parked in the driveway"

        error2 = detect_cross_validation_error(
            yolo_class="car", yolo_confidence=0.9,
            florence_description="A person walking in dark clothing",
        )
        assert error2 is not None
        assert isinstance(error2.message, str) and error2.message
        assert "'car'" in error2.message
        assert "person" in error2.message.lower()
        assert (error2.yolo_class, error2.yolo_confidence) == ("car", 0.9)

        # one-side-None inputs must return None, never crash (cvv_1)
        assert detect_cross_validation_error(None, 0.9, "a truck") is None
        assert detect_cross_validation_error("person", 0.9, None) is None

        # "van" is in VEHICLE_TERMS but NOT in YOLO_TO_FLORENCE_EQUIVALENCE:
        # vehicle-side detection must not require both (cvv_11)
        error3 = detect_cross_validation_error(
            yolo_class="van", yolo_confidence=0.95,
            florence_description="A person standing near the door",
        )
        assert error3 is not None
        assert error3.yolo_class == "van"

        # extracted terms name the specific mismatch in the message (add(None))
        error4 = detect_cross_validation_error(
            yolo_class="person", yolo_confidence=0.7,
            florence_description="A car parked",
        )
        assert error4 is not None
        assert "car" in error4.message
```

## Batch kill recipes (remaining TEST-GAP clusters)

- **C10 + C11 (to_dict, 9):** extend `test_batch_extraction_result_to_dict` (:308): build with a populated `FlorenceEnhancedScene` ⇒ `dict_result["florence_enhanced"]["security_objects"] == [...]`; build `BatchExtractionResult()` (all members None) ⇒ each optional key `is None` (kills C11 `or True` AttributeError and the `and False` never-serialize); extend `test_cross_validation_error_to_dict` (:2967): `assert set(result) == {"is_critical", "message", "yolo_class", "yolo_confidence", "florence_description"}` + `result["yolo_confidence"] == 0.88` + `result["florence_description"] == "A car in the parking lot"`.
- **C24 (1):** in `TestIsValidVQAOutput.test_rejects_short_garbage_outputs` (:1784): `assert is_valid_vqa_output("ab") is False` (and `"xy"`).
- **C35 (2):** new async test, pattern of `test_extract_person_attributes_validates_vqa_output` (:1894): caption/other answers valid, **carrying** raw = `"<loc_1>x<loc_2>"` ⇒ `result.carrying is None`; vehicle commercial=`"yes"` + commercial_text raw garbage ⇒ `commercial_text is None`. Mutants AttributeError (`_parse_none_response(None)`).
- **C03 (1, optional):** add `caplog` text assertion to `test_query_florence_handles_unavailable_error` (:963): `"Florence service unavailable" in caplog.text`.
- **E-clusters (6):** no tests warranted — semantic no-ops under the declared contracts (E2/E4 would need out-of-contract `None` inputs from `_query_florence`, which its own exception path already normalizes to `""`).

## Notes

- **Partition verification:** meta-survivor set == union of cluster key sets, each key exactly once (script check: total 135, dups 0, missing 0, extras 0). Class totals: TEST-GAP 128 (C01,C02,C04–C22,C24,C25,C26,C28,C35), LOW-VALUE 1 (C03), EQUIVALENT 6 (E1–E6). Sum 128+1+6 = 135 ✔.
- **E1 proof sketch** (`ivqa__1`): `and`-version returns `not text and not text.strip()`; for truthy `text`, first conjunct False ⇒ no early return; whitespace-only reaches length check, len 0 < 2, `""` ∉ whitelist ⇒ False — same as original early return.
- **C01 split of labor:** `qf__7` clobbers the image at the *client* call site (`self._florence_client.extract(None, prompt)`), so T1 (which intercepts `_query_florence`) kills the other 18 caller-site keys, and **T1b kills `qf__7`** — together C01 = 19/19. `qf__11` (logger message `None`) is C03, caplog recipe only.
- No repo files modified; no tests run. Sole write: this dossier.
