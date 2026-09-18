# WP4.4 Triage Dossier — backend/services/enrichment_pipeline.py

**Date:** 2026-09-18 · **Run:** WP4.3 mutation baseline (status at time of extraction)
**Survivors:** 2879 of 4837 mutants (1958 killed, 0 unchecked). Exit codes read from
`mutants/backend/services/enrichment_pipeline.py.meta` (`exit_code_by_key`, 0 = survived).
**Method:** diffs reconstructed by slicing `mutants/backend/services/enrichment_pipeline.py`
with the line-range spans in `.py.spans` (mutant slice vs `__mutmut_orig` slice, difflib
`n=0`), then clustered by mutation-kind × semantic sink (AST walk of the original source to
find whether each mutated literal sits in a logger call, metrics call, if-condition,
serialized-output function, or data-path assignment/call). Coverage judged from
`mutants/mutmut-stats.json → tests_by_mangled_function_name`.
UNVERIFIED — no tests were run (live mutation run owns the machine).

## Covering test files (line anchors)

| File | Key regions |
|---|---|
| `backend/tests/unit/services/test_enrichment_pipeline.py` | fixtures 59–97; `TestEnrichmentResultRiskModifiers` :899; `TestEnrichmentResultSummaryFlags` :1009; two-persons violence gate :1377; `TestEnrichmentServiceMode` :2001; `TestEnrichmentPipelineEnrichBatchWithTracking` :4328; `TestEnrichmentResultPoseActionSummaryFlags` :5361 |
| `backend/tests/unit/services/test_enrichment_classification_errors.py` | 5xx-logs-warning :174; extra-dict key asserts :746 |
| `backend/tests/unit/services/test_enrichment_error_handling.py` | `from_exception` status classification, boundaries 429/500/400 :176–212 |
| `backend/tests/unit/services/test_enrichment_tracking.py` | model-name lists (dataclass only, not enrich_batch_with_tracking) :75–123 |
| `backend/tests/unit/services/test_enrichment_parallelization.py` | phase prerequisite gating (partial) |

## Cluster table (sums to 2879)

| # | Pattern (sink × mutation) | Count | Class | Example keys (suffix after `xǁ`/`x_`) |
|---|---|---|---|---|
| 1 | Log message text + `extra={}` dict keys/values in `logger.*` calls case-UPPERed / `XX`-wrapped / →None / dropped (mostly `_classify_pets`, `_classify_person_clothing`, `_classify_vehicle_types`, `enrich_batch`) | 707 | EQUIVALENT | `_classify_person_clothing__mutmut_96`; `_classify_pets_via_service__mutmut_102`; `detect_vehicle_damage__mutmut_31` |
| 2 | Ternary `… if X else …` inside logger f-strings forced `and False`/`or True` (yes/no log fragments) | 24 | EQUIVALENT | `_analyze_depth__mutmut_48`; `_assess_image_quality__mutmut_26`; `_run_parallel_enrichment__mutmut_487` |
| 3 | Falsy sentinel swap `None → ""` on locals (falsiness preserved) | 6 | EQUIVALENT | `_run_parallel_enrichment__mutmut_409`; `_enrich_single_detection_unified__mutmut_29`; `__init____mutmut_62` |
| 4 | `raise RuntimeError(...)`/assert message **text** changed (5 payload-bucket members) | 5 | EQUIVALENT | `_assess_image_quality__mutmut_45`; `_classify_weather__mutmut_41` |
| 5 | No-op span artifact (mutant body identical to orig) | 1 | EQUIVALENT | `_pil_to_bytes__mutmut_2` |
| 6 | `exc_info=True → False` on `logger.error(...)` | 14 | LOW-VALUE | `_analyze_depth__mutmut_70`; `_run_reid__mutmut_94`; `_classify_clothing_via_service__mutmut_114` |
| 7 | `zip(..., strict=True) → False` defensiveness flip | 6 | LOW-VALUE | `_safe_classify_demographics__mutmut_60`; `_run_parallel_enrichment__mutmut_601` |
| 8 | `"is_transient": True/False` flips **inside logger `extra={}` dicts** (the asserted copy on the `EnrichmentError` object is elsewhere) | 17 | LOW-VALUE | `_classify_person_clothing__mutmut_112`; `_classify_pets__mutmut_70`; `_classify_vehicle_types__mutmut_68` |
| 9 | `__init__` keyword feature-flag default `bool = True → False` (silently disables a model for callers who omit the kwarg; tests always pass explicit kwargs) | 10 | LOW-VALUE | `__init____mutmut_18` (`scene_ocr_enabled`) |
| 10 | Mixed defensive bool kwargs: `asyncio.gather(return_exceptions=True)` swap, external-lib kwargs (`model.predict(verbose=False)`, `ocr(cls=True)`), `options["face_visible"]=True`, ctor bool defaults (`is_service_uniform=False`) | 11 | LOW-VALUE | `_enrich_animals_via_unified_service__mutmut_20`; `_run_yolo_detection__mutmut_12`; note: the gather flips are genuinely risky but only on task-exception paths tests never raise into |
| 11 | `continue → break` inside per-detection classify loops (remaining detections silently skipped when one crop fails) | 5 | TEST-GAP | `_classify_pets__mutmut_32`; `_classify_person_clothing__mutmut_32`; `_classify_clothing_via_service__mutmut_20` |
| 12 | Metrics labels/args to `record_enrichment_model_call` / `observe_enrichment_model_duration` / `set_enrichment_success_rate` case-UPPERed/`XX`/→None/dropped (534; dashboards consume labels but no test pins them) | 534 | LOW-VALUE | `classify_weather__mutmut_55`; `safe_clip_scene_classify__mutmut_21`; note: one parametrized snapshot test would kill ~500 at once — cheap win for WP4.4 if label fidelity is deemed worth pinning |
| 13 | Tracking model-name strings in `enrich_batch_with_tracking`: `error_model_mapping` keys/values, `successful_models.append("…")`, `if "…" not in failed_models` checks mutated → failures/successes attributed to a phantom name | 26 | TEST-GAP | `enrich_batch_with_tracking__mutmut_167`/`_182`/`_220`; covering class :4328 asserts only license_plate + vision names |
| 14 | `and → or` (and precedence swaps) in model-run gates: `pose_estimation_enabled and persons` → `... or persons`, depth/scene-ocr/reid/violence/tracking gates → models scheduled with no applicable detections | 109 | TEST-GAP | `_run_parallel_enrichment__mutmut_133`/`_242`/`_294`; `enrich_batch_with_tracking__mutmut_141`/`_211` |
| 15 | `not` removal / `is not None → is None` on gates, cascade deferral (`if not persons:`), mapping guards, `pil_image_available` inversion | 45 | TEST-GAP | `_run_parallel_enrichment__mutmut_7`; `_map_unified_to_enrichment_result` re-ids; `enrich_batch_with_tracking` pil-avail |
| 16 | Case/XX mutations **inside if-conditions**: `detection_type == "person"→"PERSON"` routing in `_map_unified`/`_enrich_single_detection_unified`, `phase1_dict` membership keys in `_process_phase1_results` (`"smoke_fire_detection"→"SMOKE_FIRE_DETECTION"`), `model_manager.load("vit-age-classifier")` model names | 116 | TEST-GAP | `_map_unified_to_enrichment_result__mutmut_70`; `_process_phase1_results__mutmut_11`/`_15` |
| 17 | Comparison-operator flips: `500 <= status < 600` transient boundary in `_classify_pets/_person_clothing/_vehicle_types`, `risk_weight >= 0.9/0.7` severity tiers, `pose_confidence > 0.5`, `>= → >` thresholds, `== → !=` pose severity pick, `_crop_to_bbox x2 < x1` | 39 | TEST-GAP | `get_summary_flags__mutmut_117`/`_73`; `_classify_person_clothing__mutmut_116` |
| 18 | Numeric constants changed: every `get_risk_modifiers` weight (`pet_only -0.7→-1.7` etc.), `_should_run_for_quality` tier order, `.get("confidence", 0.0→1.0)` defaults, thresholds | 79 | TEST-GAP | `get_risk_modifiers__mutmut_14`/`_25`/`_7`; `_should_run_for_quality__mutmut_4` |
| 19 | Ternary/guard forced into else: `severity "alert" if crouching else "warning"` forced, `det_id = str(d.id) if d.id else str(i)` forced (`or True` → det_id literally "True" for falsy ids), `reid_service if ... else get_reid_service()` forced, bbox fallbacks | 62 | TEST-GAP | `_analyze_depth__mutmut_6`; `__init____mutmut_68`; `get_summary_flags` severity picks |
| 20 | Other condition flips: `in → not in` membership (`phase1_dict`, `failed_models`), `str(e).lower() → .upper()`, `is None → is not None` service guards, `ANIMAL_CLASSES` membership negation | 31 | TEST-GAP | `process_phase1_results__mutmut_167`/`_174`; `_assess_image_quality__mutmut_58` |
| 21 | Arithmetic flips: `perf_counter() - start_time → + start_time` (garbage durations fed to duration histograms), timeout fractions `*0.7/*0.5`, `*1000→/1000` scale | 49 | LOW-VALUE | `_analyze_depth__mutmut_55`; `_run_parallel_enrichment__mutmut_379` |
| 22 | Serialized-output payload keys/values (`to_dict`/`to_storage_dict`/`to_prompt_context`/`get_summary_flags` dict literals) case/XX/None — breaks storage round-trip & prompt schema for **not-yet-asserted** keys (data-consistency tests assert only a key subset) | 144 | TEST-GAP | `to_dict__mutmut_30` (`"POSE_RESULTS"`); `get_summary_flags__mutmut_42`; `to_storage_dict__mutmut_22` |
| 23 | String case/XX on result-constructor kwargs and pipeline payload dicts outside output fns: `depth_sampling_method="center"→"CENTER"`, `phase1_tasks["osnet_reid"]` write-side keys (asymmetric with the read side in #16 → result silently dropped), cascade tuple model names | 263 | TEST-GAP | `_analyze_depth__mutmut_37`; `_run_parallel_enrichment__mutmut_478`; note: killable broadly by asserting mocked collaborator call-args per model path |
| 24 | Serialized/error payload fields set to None (`to_dict` sub-dict args, `EnrichmentError(reason=str(exc)→str(None))`, `details=` args) | 66 | TEST-GAP | `to_dict__mutmut_83`; `from_exception__mutmut_101`/`_102` |
| 25 | Call args → None to collaborators/mappers: `_crop_to_bbox(image, person.bbox→None)`, `client.classify_clothing(crop, bbox_tuple→None)`, `getattr(x,"f",None→)`, `Semaphore(settings.…→None)` — mocked AsyncMock collaborators accept anything | 337 | TEST-GAP | `_safe_classify_demographics` crop mutants; `_classify_clothing_via_service__mutmut_26`; `__init____mutmut_75` |
| 26 | Whole call-arg or call dropped (result → None) on payload/error paths: `zip(det_ids, age_batch→∅)` (misaligned mapping, path unexecuted), `details=error_details, )` drop, `result = None` replacing service calls | 173 | TEST-GAP | `from_exception__mutmut_100`; `safe_run_scene_ocr_crops` mutants |

**Totals:** EQUIVALENT 743 · LOW-VALUE 641 · TEST-GAP 1495 (= 2879 ✓)

## Key findings

1. **~48% of survivors are observability noise** (clusters 1, 6, 8, 12, 21 = 1311): logger text/extra dicts and Prometheus labels. Baseline noise floor, not a test problem — except that the same mutation engine also touched the ~1495 behavior-bearing literals below.
2. **The tracking pipeline is under-asserted where it matters**: `enrich_batch_with_tracking` has exactly 4 covering tests; they pin `license_plate` and `vision` by name and never exercise 12 of 14 mapped models, per-model success rates, or the `failed_models` membership logic — clusters 13, 14, 20 concentrate there.
3. **Risk math has no exact-value tests**: `get_risk_modifiers` tests assert sign only (`> 0`, `< 0`); every weight constant survived. Severity thresholds in `get_summary_flags`/`to_context_string` are asserted for violence only; the `>= 0.7 / >= 0.9` action tiers and weather/pose confidence boundaries were never tested at the boundary value.
4. **The HTTP-status transient boundary is tested on `EnrichmentError.from_exception` but not on the three `_classify_*` methods** whose `500 <= code < 600` branches drive transient-vs-permanent logging (test_enrichment_error_handling.py :192 uses interior values 500/502/503/504 — `<= 600` and `500 <` mutants only die at 600/500-with-`<`).
5. **Detection-type routing in service mode is string-matched and untested**: `_map_unified_to_enrichment_result` guards (`detection_type == "person"` etc.) and `_process_phase1_results` membership keys accept ANY-case mutation. A mutant mapping a car's pose/threat/re-id data was invisible.

## Drafted tests (UNVERIFIED - not yet run red/green)

TDD procedure (all six): add test → run against mutant copy for a listed key (`uv run mutmut show <key>` to confirm the line) → assertion must FAIL red; run against original source → must pass green; then mark the cluster killed in the WP4.4 ledger.

### T1 — `test_quality_tier_order_and_bogus_tier` (kills #18 `_should_run_for_quality` NUM members, #16 tier-arg→None members)
Target: `backend/tests/unit/services/test_enrichment_pipeline.py` (new class next to :2264's method, e.g. after `TestEnrichmentPipelineHelperMethodsCoverage`).
```python
class TestEnrichmentQualityTierOrder:
    """WP4.4: pin the minimal<standard<full tier order (surviving NUM mutants)."""

    def test_quality_tier_order(self) -> None:
        """Each quality level permits exactly its tier and all cheaper tiers."""
        pipeline = EnrichmentPipeline()
        for level, allowed in (
            ("minimal", {"minimal"}),
            ("standard", {"minimal", "standard"}),
            ("full", {"minimal", "standard", "full"}),
        ):
            pipeline._quality_level = level
            for tier in ("minimal", "standard", "full"):
                assert pipeline._should_run_for_quality(tier) is (tier in allowed), (
                    f"level={level} tier={tier}"
                )

    def test_unknown_tier_is_never_allowed(self) -> None:
        """Unknown tiers fall back to the strictest order, not 'run everything'."""
        pipeline = EnrichmentPipeline()
        pipeline._quality_level = "full"
        assert pipeline._should_run_for_quality("bogus-tier") is False
```
Red-proof: `level_order = {"minimal": 1, ...}` mutant makes `("minimal","standard")` return True → first loop fails; `level_order.get(tier, 3)` mutant makes bogus-tier return True. Green on original (`current >= required` with 0/1/2 and default 2).

### T2 — `test_model_gates_respect_detection_types` (kills #14 and→or gate flips, #15 not-removal at gates)
Target: same file; mirrors `test_enrich_batch_violence_detection_requires_two_persons` (:1377) kwargs style.
```python
class TestEnrichmentGateDetectionTypes:
    """WP4.4: models gated on detection categories must not run without them."""

    @pytest.mark.asyncio
    async def test_pose_gate_requires_persons(
        self,
        test_image: Image.Image,
        vehicle_detection: DetectionInput,
        mock_model_manager: MagicMock,
    ) -> None:
        """pose_estimation_enabled alone must not schedule pose work for a vehicle-only frame."""
        with (
            patch("backend.services.enrichment_pipeline.get_vision_extractor", autospec=True),
            patch("backend.services.enrichment_pipeline.get_reid_service", autospec=True),
            patch("backend.services.enrichment_pipeline.get_scene_change_detector", autospec=True),
        ):
            pipeline = EnrichmentPipeline(
                model_manager=mock_model_manager,
                license_plate_enabled=False,
                face_detection_enabled=False,
                vision_extraction_enabled=False,
                reid_enabled=False,
                scene_change_enabled=False,
                violence_detection_enabled=False,
                weather_classification_enabled=False,
                clothing_classification_enabled=False,
                clothing_segmentation_enabled=False,
                vehicle_classification_enabled=False,
                vehicle_damage_detection_enabled=False,
                image_quality_enabled=False,
                pet_classification_enabled=False,
                depth_estimation_enabled=False,
                scene_ocr_enabled=False,
                pose_estimation_enabled=True,
            )
            with patch.object(
                pipeline, "_safe_estimate_poses", new_callable=AsyncMock
            ) as mock_pose:
                mock_pose.return_value = []
                await pipeline.enrich_batch([vehicle_detection], {None: test_image})
                mock_pose.assert_not_called()

    @pytest.mark.asyncio
    async def test_depth_gate_requires_high_confidence(
        self,
        test_image: Image.Image,
        mock_model_manager: MagicMock,
    ) -> None:
        """Low-confidence detections (excluded from high_conf_detections) must not schedule depth."""
        low_conf = DetectionInput(
            id=9,
            class_name="car",
            confidence=0.2,
            bbox=BoundingBox(x1=1, y1=1, x2=50, y2=50),
        )
        with (
            patch("backend.services.enrichment_pipeline.get_vision_extractor", autospec=True),
            patch("backend.services.enrichment_pipeline.get_reid_service", autospec=True),
            patch("backend.services.enrichment_pipeline.get_scene_change_detector", autospec=True),
        ):
            pipeline = EnrichmentPipeline(
                model_manager=mock_model_manager,
                license_plate_enabled=False,
                face_detection_enabled=False,
                vision_extraction_enabled=False,
                reid_enabled=False,
                scene_change_enabled=False,
                violence_detection_enabled=False,
                weather_classification_enabled=False,
                clothing_classification_enabled=False,
                clothing_segmentation_enabled=False,
                vehicle_classification_enabled=False,
                vehicle_damage_detection_enabled=False,
                image_quality_enabled=False,
                pet_classification_enabled=False,
                scene_ocr_enabled=False,
                pose_estimation_enabled=False,
                depth_estimation_enabled=True,
            )
            with patch.object(
                pipeline, "_safe_analyze_depth", new_callable=AsyncMock
            ) as mock_depth:
                mock_depth.return_value = None
                await pipeline.enrich_batch([low_conf], {None: test_image})
                mock_depth.assert_not_called()
```
Red-proof: `self.pose_estimation_enabled or persons` mutant (key `_run_parallel_enrichment__mutmut_133`) schedules the pose task with zero persons → `assert_not_called` fails; same for depth gate `or high_conf_detections` (`_mutmut_242`). Green: original `and`-gates skip.

### T3 — `test_error_operation_maps_to_canonical_model_name` (kills #13 tracking strings, part of #15/#20 tracking membership flips)
Target: same file, extend class `TestEnrichmentPipelineEnrichBatchWithTracking` (:4328) — same patch stack, but `enrich_batch` itself stubbed so each mapping row is driven directly.
```python
    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        ("operation", "model_name"),
        [
            ("license_plate_detection", "license_plate"),
            ("face_detection", "face"),
            ("vision_extraction", "vision"),
            ("re_identification", "reid"),
            ("scene_change_detection", "scene_change"),
            ("violence_detection", "violence"),
            ("weather_classification", "weather"),
            ("clothing_classification", "clothing"),
            ("clothing_segmentation", "segformer"),
            ("vehicle_damage_detection", "vehicle_damage"),
            ("vehicle_classification", "vehicle_class"),
            ("image_quality_assessment", "image_quality"),
            ("pet_classification", "pet"),
            ("depth_estimation", "depth"),
        ],
    )
    async def test_error_operation_maps_to_canonical_model_name(
        self,
        operation: str,
        model_name: str,
        vehicle_detection: DetectionInput,
        test_image: Image.Image,
        mock_model_manager: MagicMock,
    ) -> None:
        """Each mapped operation's failure lands under its canonical short model name."""
        from backend.services.enrichment_pipeline import EnrichmentResult

        failed = EnrichmentResult(errors=[f"{operation} failed: boom"])
        pipeline = EnrichmentPipeline(model_manager=mock_model_manager)
        with (
            patch.object(
                pipeline, "enrich_batch", new_callable=AsyncMock, return_value=failed
            ),
            patch("backend.core.metrics.record_enrichment_batch_status", autospec=True),
            patch("backend.core.metrics.record_enrichment_failure", autospec=True) as mock_fail,
            patch("backend.core.metrics.record_enrichment_partial_batch", autospec=True),
            patch("backend.core.metrics.set_enrichment_success_rate", autospec=True),
        ):
            tracking = await pipeline.enrich_batch_with_tracking(
                [vehicle_detection], {None: test_image}, camera_id="cam-1"
            )

        assert tracking.failed_models == [model_name]
        assert tracking.errors[model_name].startswith(operation)
        mock_fail.assert_called_once_with(model_name)
        assert model_name not in tracking.successful_models
```
Red-proof: case-flipping the mapping key (`"weather_classification"→"WEATHER_..."`, `enrich_batch_with_tracking__mutmut_46`-family) yields `failed_models == []`; flipping the value yields `["WEATHER"]`; `if "weather" not in failed_models` → `in` mutants append the phantom name to `successful_models` → last assert fails. Green on original.

### T4 — `test_risk_modifier_exact_weights` (kills #18 get_risk_modifiers NUM — 16 mutants, 2 CMP boundary members)
Target: same file, class `TestEnrichmentResultRiskModifiers` (:899) — exact values instead of the current sign-only asserts.
```python
    @pytest.mark.parametrize(
        ("result", "expected"),
        [
            (
                EnrichmentResult(
                    violence_detection=ViolenceDetectionResult(
                        is_violent=True,
                        confidence=1.0,
                        violent_score=1.0,
                        non_violent_score=0.0,
                    )
                ),
                {"violence": 1.0},
            ),
            (
                EnrichmentResult(
                    pet_classifications={
                        "1": PetClassificationResult(
                            animal_type="dog",
                            confidence=0.95,
                            cat_score=0.05,
                            dog_score=0.95,
                            is_household_pet=True,
                        )
                    }
                ),
                {"pet_only": -0.7},
            ),
            (
                EnrichmentResult(
                    faces=[FaceResult(bbox=BoundingBox(x1=1, y1=1, x2=9, y2=19))],
                    pet_classifications={
                        "1": PetClassificationResult(
                            animal_type="dog",
                            confidence=0.95,
                            cat_score=0.05,
                            dog_score=0.95,
                            is_household_pet=True,
                        )
                    },
                ),
                {"confirmed_pet": -0.3},
            ),
            (
                EnrichmentResult(
                    clothing_classifications={
                        "1": ClothingClassification(
                            top_category="ski mask",
                            confidence=0.9,
                            all_scores={},
                            is_suspicious=True,
                            is_service_uniform=False,
                            raw_description="Alert: ski mask",
                        )
                    }
                ),
                {"suspicious_attire": 0.3},
            ),
            (EnrichmentResult(quality_change_detected=True), {"quality_change": 0.2}),
            (
                EnrichmentResult(action_results={"detected_action": "breaking in", "confidence": 0.9}),
                {"suspicious_action": 0.4},
            ),
            (
                # "unknown thing" maps to the neutral 0.5 weight -> moderate tier via >= 0.5
                EnrichmentResult(action_results={"detected_action": "unknown thing", "confidence": 0.5}),
                {"moderate_action": 0.2},
            ),
            (
                EnrichmentResult(action_results={"detected_action": "delivering", "confidence": 0.9}),
                {"benign_action": -0.15},
            ),
            (
                EnrichmentResult(
                    weather_classification=WeatherResult(
                        condition="heavy rain",
                        simple_condition="rainy",
                        confidence=0.5,  # exact boundary: >= 0.5 must include
                        all_scores={},
                    )
                ),
                {"weather_rainy": -0.15},
            ),
        ],
    )
    def test_risk_modifier_exact_weights(
        self, result: EnrichmentResult, expected: dict[str, float]
    ) -> None:
        """Named risk modifiers carry their exact documented weights."""
        modifiers = result.get_risk_modifiers()
        assert modifiers.keys() == expected.keys()
        for name, weight in expected.items():
            assert modifiers[name] == pytest.approx(weight), name
```
Red-proof: `modifiers["pet_only"] = -1.7` (`get_risk_modifiers__mutmut_14`), `0.3→1.3` (`_25`), `action_weight >= 0.5 → > 0.5` (`_64`: neutral 0.5 loses `moderate_action`), `weather ... >= 0.5 → > 0.5` (`_76` at conf 0.5) all fail their case. Green on original.

### T5 — `test_summary_flag_severity_boundaries` (kills #17 severity/threshold CMP members, #19 severity-pick GUARD members)
Target: same file, class `TestEnrichmentResultPoseActionSummaryFlags` (:5361).
```python
    @pytest.mark.parametrize(
        ("detected_action", "expected_severity"),
        [
            ("breaking in", "critical"),  # risk weight 1.0 >= 0.9
            ("loitering", "alert"),       # weight 0.7: >= 0.7 boundary must be alert, not warning
        ],
    )
    def test_summary_flags_action_severity_boundaries(
        self, detected_action: str, expected_severity: str
    ) -> None:
        """Action severity tiers switch exactly at weights 0.9 / 0.7."""
        result = EnrichmentResult(
            action_results={"detected_action": detected_action, "confidence": 0.9}
        )
        action_flags = [f for f in result.get_summary_flags() if f["type"] == "suspicious_action"]
        assert len(action_flags) == 1
        assert action_flags[0]["severity"] == expected_severity

    @pytest.mark.parametrize(
        ("pose_class", "pose_confidence", "expect_flag", "severity"),
        [
            ("crouching", 0.85, True, "alert"),
            ("running", 0.85, True, "warning"),
            ("crouching", 0.50, False, None),  # > 0.5 boundary: exactly 0.5 must NOT flag
        ],
    )
    def test_summary_flags_pose_severity_and_confidence_boundary(
        self,
        pose_class: str,
        pose_confidence: float,
        expect_flag: bool,
        severity: str | None,
    ) -> None:
        """Suspicious-pose flag needs confidence > 0.5; crouching alone is 'alert'."""
        from backend.services.vitpose_loader import PoseResult

        pose = PoseResult(keypoints=[], pose_class=pose_class, pose_confidence=pose_confidence)
        result = EnrichmentResult(pose_results={"1": pose})
        pose_flags = [f for f in result.get_summary_flags() if f["type"] == "suspicious_pose"]
        assert bool(pose_flags) is expect_flag
        if expect_flag:
            assert pose_flags[0]["severity"] == severity

    def test_summary_flags_weather_confidence_boundary(self) -> None:
        """Weather flags trigger at confidence exactly 0.5 (>= boundary)."""
        result = EnrichmentResult(
            weather_classification=WeatherResult(
                condition="dense fog",
                simple_condition="foggy",
                confidence=0.5,
                all_scores={},
            )
        )
        flags = [f for f in result.get_summary_flags() if f["type"] == "weather_low_visibility"]
        assert len(flags) == 1
```
Red-proof: `"alert" if risk_weight >= 0.7` → `> 0.7` (`get_summary_flags__mutmut_123`) turns loitering into warning; `pose_confidence > 0.5` → `>=` (`_73`) flags at 0.50; `weather ... >= 0.5 → >` (`_137`) drops the fog flag; `"alert" if pose.pose_class == "crouching"` → `!=` (`_88`) swaps crouching/running severities. Green on original.

### T6 — `test_phase1_results_key_routing` (kills #16 phase1 membership, #20 in/not-in flips, part of #15)
Target: same file — direct call of the sync `_process_phase1_results` (no async machinery needed).
```python
class TestPhase1ResultKeyRouting:
    """WP4.4: _process_phase1_results keys are load-bearing; pin one representative per key family."""

    def test_phase1_populates_fields_per_key(self, mock_model_manager: MagicMock) -> None:
        pipeline = EnrichmentPipeline(model_manager=mock_model_manager)
        result = EnrichmentResult()
        weather = WeatherResult(
            condition="heavy rain", simple_condition="rainy", confidence=0.8, all_scores={}
        )
        clothing = ClothingClassification(
            top_category="FedEx uniform",
            confidence=0.88,
            all_scores={},
            is_suspicious=False,
            is_service_uniform=True,
            raw_description="Service worker",
        )
        phase1: dict[str, Any] = {
            "weather_classification": weather,
            "clothing_classification": {"1": clothing},
            "face_detection": [
                FaceResult(bbox=BoundingBox(x1=1, y1=1, x2=10, y2=20), confidence=0.7)
            ],
            "license_plate_detection": [
                LicensePlateResult(
                    bbox=BoundingBox(x1=1, y1=1, x2=30, y2=20),
                    text="ABC123",
                    confidence=0.9,
                    ocr_confidence=0.8,
                )
            ],
        }
        pipeline._process_phase1_results(result, phase1)
        assert result.weather_classification is weather
        assert result.clothing_classifications == {"1": clothing}
        assert len(result.faces) == 1
        assert len(result.license_plates) == 1
        assert not result.errors  # happy values must not be misfiled as exceptions

    def test_phase1_missing_keys_are_noops(self, mock_model_manager: MagicMock) -> None:
        pipeline = EnrichmentPipeline(model_manager=mock_model_manager)
        result = EnrichmentResult()
        pipeline._process_phase1_results(result, {})
        assert result.weather_classification is None
        assert result.faces == []
        assert result.license_plates == []
        assert result.clothing_classifications == {}
```
Red-proof: `if "weather_classification" in phase1_dict` → `"WEATHER_CLASSIFICATION"` / `not in` (`_process_phase1_results__mutmut_15`, `_167`-family) leaves `weather_classification` None (first test) or populates from `{}` (second, for `in→not in` on every key). Green on original.

### T7 (bonus) — `test_http_status_transient_boundary_is_exclusive` (kills #17 `500 <= status < 600` members in `_classify_*`)
Target: `backend/tests/unit/services/test_enrichment_classification_errors.py` (extends the 5xx test at :174 — same mock stack).
```python
    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        ("status_code", "expect_warning"),
        [
            (500, True),   # lower boundary is inclusive: 500 = transient server error
            (499, False),  # 4xx = permanent client error
            (600, False),  # upper bound is exclusive: 600 must NOT be transient
        ],
    )
    async def test_http_status_transient_boundary_is_exclusive(
        self,
        enrichment_pipeline: EnrichmentPipeline,
        test_image: Image.Image,
        person_detection: DetectionInput,
        caplog: pytest.LogCaptureFixture,
        status_code: int,
        expect_warning: bool,
    ) -> None:
        """`500 <= status < 600` must be exact: 500 warns, 499/600 log errors."""
        mock_response = MagicMock()
        mock_response.status_code = status_code
        exc = httpx.HTTPStatusError(
            "Boundary status", request=MagicMock(), response=mock_response
        )

        async def mock_context_manager(*args: Any, **kwargs: Any) -> Any:
            raise exc

        enrichment_pipeline.model_manager.load = MagicMock(
            return_value=AsyncMock(__aenter__=mock_context_manager, __aexit__=AsyncMock())
        )

        with caplog.at_level(logging.WARNING):
            results = await enrichment_pipeline._classify_person_clothing(
                [person_detection], test_image
            )

        assert results == {}
        if expect_warning:
            assert any(
                r.levelno == logging.WARNING and "server error" in r.getMessage()
                for r in caplog.records
            )
        else:
            assert any(
                r.levelno == logging.ERROR and "client error" in r.getMessage()
                for r in caplog.records
            )
```
Red-proof: `<= 600` mutant (`_classify_pets__mutmut_116`-family) treats 600 as server-error warning; `500 < status_code` treats 500 as client error. Green on original. Copy the fixture to `_classify_pets`/`_classify_vehicle_types` to cover their instances (same pattern per :466 and :298 classes).

**TDD procedure (one line, all):** run the drafted test against the mutant copy selected via `uv run mutmut show <key>` for one listed example key — assertion must fail red; run against `backend/services/enrichment_pipeline.py` original — must pass green; then the whole cluster's keys are marked killable in WP4.4.

## Residual TEST-GAP clusters without drafts (kill ideas, not drafted)
- **#23/#25/#26 (773 mutants, ctor-kwargs + call-args on data paths):** kill broadly by asserting mocked collaborator **call args** per model path (e.g. `client.classify_clothing.assert_awaited_once_with(crop, expected_bbox_tuple)` instead of `assert_called_once()`); existing service-mode tests (:2001) use `assert_called_once()` only.
- **#11 continue→break:** two-detection lists where the first crop fails; assert the second still classified.
- **#22 serialized keys:** extend `test_enrichment_data_consistency.py` with full-key-set equality for `to_dict()`/`to_storage_dict()` per populated result.
