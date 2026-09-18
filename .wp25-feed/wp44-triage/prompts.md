# WP4.4 Triage Dossier — `backend/services/prompts.py`

**Surviving mutants: 888** (verdict histogram at extraction time: 888 survived / 1388 killed / 809 `-24` timeouts-still-running; extraction snapshot 2026-09-18, meta may still grow).
Method: `mutmut show` fails (`FileNotFoundError: Could not find mutant …` — cache is mid-run), so all 888 diffs were recovered by manual alignment: each `x<FN>__mutmut_N` block in `mutants/backend/services/prompts.py` diffed line-by-line against its `__mutmut_orig` sibling (879 single-line mutants + 9 multi-line block mutants, byte-exact prefix/suffix extraction, 0 unexplained). Mutations classified mechanically by string-role (AST ancestor walk: string in `getattr`/`hasattr` attr name, dict `.get` *key* vs *default*, set-membership operand, f-string literal, join separator, docstring) plus mutation shape.
**Equivalence notes baked into the table:** `getattr(x, K, {}) or {}` → default `None` is a no-op (the `or {}` folds it back); `getattr(..., False)` → `None` is falsy-equivalent at every consumption site in this module (`if is_suspicious:`, `"YES" if x else`); but **deleting** the default (`False`) makes missing attributes *truthy* — those are test gaps, not equivalents. String `XX…XX`/case flips inside *semantic operands* (`in ("crouching", "lying")`, `getattr(o, "is_suspicious")`, `{"weapon", "knife"}`, `detection_ids[i] = "person"`) change behavior and are TEST-GAP despite being string-text mutations; only pure decoration (section headers, notes, join separators, `\n` joins) is LOW-VALUE.
PEP 758 note: the module's `except ValueError, IndexError:` (line 3218) is **valid** on the 3.14 runner — no "survived because unimportable" artifacts here; every survivor is a genuine behavioral survivor.

## Covering test files (from `tests_by_mangled_function_name`)

- `backend/tests/unit/services/test_prompts.py` — 8022 lines, primary for this module (620/629 fn→file edges)
- `backend/tests/unit/services/test_prompt_formatters.py` — secondary (104 edges); `TestFormatClothingAnalysisContext`:232, `TestFormatDetectionsWithAllEnrichment`:684, `TestPromptTemplateStructure`:710, `TestFormatEnhancedClothingContext`:1321
- `backend/tests/unit/services/test_nemotron_analyzer.py`, `test_enrichment_pipeline.py`, `backend/tests/unit/test_llm_prompt_formatting.py`, `test_format_scene_ocr_context.py` — indirect callers
- **Zero asserted literals** for `check_member_schedule`'s covering tests (`TestCheckMemberSchedule`, test_prompts.py:5232) — it is only ever tested via `weekdays`/`all_day` schedule keys, never a day-name key.

## Cluster table (counts sum to 888)

| # | Pattern (function/concern) | Count | Class | Example keys (≤3) |
|---|---|---|---|---|
| 1 | **B1-decor-XXwrap** — `"XX<literal>XX"` wrap inside pure decoration: `", "`/`"\n"`/`"\n\n"` join separators, section headers (`"## Detection Confidence Quality"`, `"### Scene Analysis (Florence-2)"`, `"## CAMERA HEALTH ALERT"`), note lines, box borders (`top_border = "+" + "-"*box_width`), `day_names` list entries | 157 | LOW-VALUE | x_build_person_analysis_section__mutmut_88 / _140, x_format_confidence_quality_summary__mutmut_40 |
| 2 | **M-arg-or-call-to-None** — call/argument of a `getattr`/`hasattr`/`float()` read replaced by `None` (obj arg or whole call): `getattr(clothing, "is_suspicious", False)` → `getattr(None, …)` / → `None`; 10× each in `format_clip_analysis_context` CLIP field reads, 9× `format_camera_health_context`, 7× `x__collect_detection_ids_from_enrichment` | 111 | TEST-GAP | x_build_person_analysis_section__mutmut_102 / _103, x_format_camera_health_context__mutmut_3 |
| 3 | **C-semantic-string** — string mutation inside a *semantic operand*: membership sets (`in ("crouching","crawling","lying")`, `high_risk = {"weapon","knife",…}`, `scene_keywords`, `day_names` day-lookup), attribute/key names (`"is_suspicious"`, `"pose_results"`, `"clip_scene_classification"`, `"coverage_percentages"`, `"animal_type"`, `"dense_captions"`) case-flipped/XX-wrapped → lookup silently misses or `TypeError` swallowed | 104 | TEST-GAP | x_build_person_analysis_section__mutmut_19 / _20 / _55 |
| 4 | **B2-decor-case** — case flip of pure decoration text (headers/notes: `"YES"`→`"yes"`, `"CRITICAL: Verify…"`→lower, `"RISK MODIFIER: +30 points…"`, pet/age/pose note lines) | 102 | LOW-VALUE | x_build_person_analysis_section__mutmut_162 / _179, x_format_camera_health_context__mutmut_59 |
| 5 | **J-num-tweak** — numeric constant shifted (`0`→`1` default confidence, `[:3]`→`[:4]` category cap, `0.90`→`1.9`/`1.75`→ tier boundary, `3`→`4`, `5`→`6`, `15`→`16` risk modifier, `weekdays == 5`→`6`, `* 100`→`200`, `box_width 64`→`5`) | 60 | TEST-GAP | x_build_person_analysis_section__mutmut_49 / _79, x_format_household_context__mutmut_2 |
| 6 | **K-cmp-op-flip** — comparison operator flipped/inserted (`==`→`!=` on tier/count guards, `>=`/`>` tweaks on `confidence <= 0`, `pet.confidence >= 0.85`, `age.confidence < 0.7`, `end_minutes < start_minutes`, `minutes < 2/10`) | 39 | TEST-GAP | x_format_confidence_quality_summary__mutmut_14 / _21 / _44 |
| 7 | **A-guard-force-branch** — `(cond) or True` / `(cond) and False` appended to `isinstance`/`hasattr`/truthiness guards (e.g. `if isinstance(susp, dict)`, `if categories else "unknown"`, `if clothing_suspicious`, `if match.similarity > 0.9`, `num_cameras > 1`) → forces one branch always | 30 | TEST-GAP | x_build_person_analysis_section__mutmut_78 / _157, x_format_enhanced_clothing_context__mutmut_15 |
| 8 | **B4-decor-text** — other literal-text swaps in prose (`.upper()`→`.lower()` of tier label, `" - trust fully"` suffix case) | 29 | LOW-VALUE | x_build_person_analysis_section__mutmut_96 / _98 |
| 9 | **P2-inert-default** — `.get("key", "unknown")` string default XX-wrapped/case-flipped where tests never omit the key (inert under current fixtures) | 27 | LOW-VALUE | x_build_person_analysis_section__mutmut_34 / _35 |
| 10 | **H-empty-to-XXXX** — `""`/empty-string seed becomes `"XXXX"` (line buffers `suffix = ""`, `lines.append("")` blank separators) | 26 | LOW-VALUE | x_format_confidence_quality_summary__mutmut_49 / _56 |
| 11 | **I2-default-swap** — numeric/empty default → `None` at *guarded* or dead consumption (`0.0`→`None` under `if confidence > 0` guard; `""`→`None` on unused paths) | 22 | LOW-VALUE | x_build_person_analysis_section__mutmut_44 / _131 |
| 12 | **I5-None-default** — `getattr(..., None)` default deleted/→`""`: silently changes miss-vs-default semantics for optional CLIP fields and zone/camera names | 19 | TEST-GAP | x__collect_detection_ids_from_enrichment__mutmut_75, x_format_clip_analysis_context__mutmut_7 |
| 13 | **L-subexpr-drop** — argument/`"key", ` deleted: `getattr(enrichment_result)` (attr-name dropped → `TypeError` swallowed by callers, CLIP section vanishes), `clothing.get("is_suspicious", False)` → `clothing.get(False)` (always default `False`), `_compute_confidence_quality(...) if …` whole arm dropped | 17 | TEST-GAP | x_format_clip_analysis_context__mutmut_5 / _6, x_build_person_analysis_section__mutmut_166 |
| 14 | **E-bool-flip** — `False`→`True` / `True`→`False` initializer/default flip (`clothing_suspicious = False`→`True`, `has_confirmed_pets`, `has_minors`, `has_threat`, `acknowledged` default `True`→`False` in camera health) | 16 | TEST-GAP | x_build_person_analysis_section__mutmut_111 / _128, x_format_camera_health_context__mutmut_13 |
| 15 | **I2b-numeric-default-deleted** — `0.0` default *deleted* → `.get("confidence")` returns `None` → `TypeError` swallowed inside the module → entire enrichment/clothing section silently vanishes | 15 | TEST-GAP | x_build_person_analysis_section__mutmut_46, x_format_enhanced_clothing_context__mutmut_19 |
| 16 | **I4a-False->None-falsy-equiv** — `getattr(…,"is_suspicious", False)` → default `None`; falsy at every consumption site (`if bool()`, `"YES" if … else`) → semantically identical | 15 | EQUIVALENT | x_build_person_analysis_section__mutmut_105 / _122 |
| 17 | **P1-visible-default-label** — string default of `.get`/`getattr` swapped/None (`pose_class` default `"unknown"`→`None` → `None.lower()` crash or visible `None`, `"animal"` fallback, `"vehicle"`/`"suspicious attire"`/`"delivery uniform"` `top_match` fallbacks → LLM sees wrong label) | 14 | TEST-GAP | x_build_person_analysis_section__mutmut_29 / _31, x__collect_detection_ids_from_enrichment__mutmut_78 |
| 18 | **I2b-collection-default-deleted** — `[]`/`{}` default *deleted* → `.get(key)` → `None` → `None[:3]`/`None or {}` behavior change (categories slice, `bbox = det.get("bbox", [])` deletion) | 13 | TEST-GAP | x_build_person_analysis_section__mutmut_133, x__collect_detection_ids_from_enrichment__mutmut_8 |
| 19 | **D1-guarded-or->and** — `getattr(er, K, {}) or {}` → `… and {}`: `X and {}` always yields `{}` → entire loop/section silently skipped (NOT equivalent; the `or{}` only makes the default swap equivalent) | 11 | TEST-GAP | x_format_confidence_quality_summary__mutmut_12 (guard site), x__collect_detection_ids_from_enrichment__mutmut_14 / _26 |
| 20 | **I1-guarded-default-none** — `getattr(er, K, {}) or {}` default → `None`: `None or {}` = `{}` — semantically identical | 11 | EQUIVALENT | x__collect_detection_ids_from_enrichment__mutmut_5 / _17 / _29 |
| 21 | **I4b-False-default-deleted** — `getattr(…,"is_suspicious", False)` → `getattr(…,"is_suspicious")` (1-arg) → missing attr raises; swallowed → **section silently drops**, vs default `False` keeps section | 9 | TEST-GAP | x_build_person_analysis_section__mutmut_108 / _125 / _167 |
| 22 | **D3-and->or** — `if a and b:` → `or` (`is_valid_vqa_output(v_attrs.commercial_text)` guard, `if hasattr(action,"action") and hasattr(action,"confidence")`, `if day and "sunday" in schedule`) → guard bypassed | 9 | TEST-GAP | x_build_person_analysis_section__mutmut_224, x_format_detections_with_all_enrichment__mutmut_8 |
| 23 | **D5-insert-not** — `not ` inserted into conditions (`if conf is None or conf <= 0` → `if not conf is None …`, `elif is_sunday and …`, `has_entry_point`) → inverted early-exit | 7 | TEST-GAP | x_format_confidence_quality_summary__mutmut_13 / _50 |
| 24 | **K-arith-flip** — `+`→`-` (`start_parts[0]*60 + start_parts[1]` in schedule minutes), `+=`→`-=` (`counts[tier] -= 1`), `*`→`/` (`similarity * 100`), `+`→`XX+XX` in border concat | 7 | TEST-GAP | x_format_confidence_quality_summary__mutmut_18 / _19, x_check_member_schedule__mutmut_84 |
| 25 | **D4-drop-not** — `if not detections:` → `if detections:` (empty→summary swapped), `if scene_scores is not None:` → `is None` (CLIP sections inverted) | 5 | TEST-GAP | x_format_confidence_quality_summary__mutmut_1, x_format_clip_analysis_context__mutmut_18 |
| 26 | **G-continue->break** — loop early-exit (`if count == 0: continue→break` in tier loop drops remaining tiers; `if minutes<2: continue` in anomaly loop) | 3 | TEST-GAP | x_format_confidence_quality_summary__mutmut_46, x__build_tracking_narratives__mutmut_5 |
| 27 | **F-True->None** — `getattr(sc,"acknowledged", True)` → default `None` (falsy → unacknowledged camera silently alerts) — distinct from E because flip direction differs | 1 | TEST-GAP | x_format_camera_health_context__mutmut_7 |
| 28 | **N-multiline-block-arg** — whole-call/kwarg block deletions: `risk_modifier=15,` kwarg removed from `ClassAnomalyResult(…)`, `counts/tier_labels` dict literal → `None` block swap, `_infer_movement_pattern(` call → `movement = None` | 9 | TEST-GAP | x_format_class_anomaly_context__mutmut_43 / _56, x_format_confidence_quality_summary__mutmut_2 |

**Totals: TEST-GAP 499 / LOW-VALUE 363 / EQUIVALENT 26 — sum 888 (±0).**
The largest single kill opportunity is C-semantic-string + M-arg-or-call-to-None + D1 + L: ~150 survivors in `x__collect_detection_ids_from_enrichment`, `x_format_clip_analysis_context`, `x_format_confidence_quality_summary` that one or two well-factored parametrized tests can mow.

## Drafted tests (6 highest-value clusters)

All `// UNVERIFIED — not yet run red/green`. TDD procedure (same for each): add the test, run it against the **mutant** copy (or a hand-applied one-line diff) → assertion fails (red); run against `backend/services/prompts.py` as-is → passes (green). Then batch-verify against the surviving keys of that cluster.

### Draft 1 — kills **D1-guarded-or->and (11)** + **I1-guarded-default-none (11, equiv confirmation)** + most of C/M in `_collect_detection_ids_from_enrichment`
Target file: `backend/tests/unit/services/test_prompts.py` (class `TestFormatDetectionsWithAllEnrichment` @ 2052; import `_collect_detection_ids_from_enrichment` locally, matching the file's per-test local-import style).
// UNVERIFIED — not yet run red/green

```python
class TestCollectDetectionIdsFromEnrichment:
    """Tests for _collect_detection_ids_from_enrichment (WP4.4 mutation kill).

    Each enrichment source uses the ``getattr(er, key, {}) or {}`` idiom. The
    surviving mutants (a) flip ``or`` to ``and`` so a present bucket collapses
    to an empty dict (every id from that source silently disappears) and
    (b) clobber the attribute name so getattr falls back to the empty default.
    These tests exercise EVERY source with a present bucket and assert the
    full returned mapping — both mutant families fail loudly here.
    """

    def test_all_sources_populate_expected_class_names(self) -> None:
        from types import SimpleNamespace

        from backend.services.prompts import _collect_detection_ids_from_enrichment

        enrichment = SimpleNamespace(
            clothing_classifications={"c1": {}},
            clothing_segmentation={"c2": {}},
            pose_results={"c3": {}},
            vehicle_classifications={"v1": {}},
            vehicle_damage={"v2": {}},
            pet_classifications={"p1": SimpleNamespace(animal_type="dog")},
        )
        vision = SimpleNamespace(
            person_attributes={"p2": {}},
            vehicle_attributes={"p1": {}},  # already claimed by pet -> person wins
        )
        result = _collect_detection_ids_from_enrichment(enrichment, vision)

        assert result["c1"] == "person"  # clothing_classifications
        assert result["c2"] == "person"  # clothing_segmentation
        assert result["c3"] == "person"  # pose_results
        assert result["v1"] == "vehicle"  # vehicle_classifications
        assert result["v2"] == "vehicle"  # vehicle_damage
        assert result["p1"] == "dog"  # pet animal_type passthrough
        assert result["p2"] == "person"  # vision_extraction, no clobber of p1
        assert result == {"c1": "person", "c2": "person", "c3": "person",
                          "v1": "vehicle", "v2": "vehicle", "p1": "dog", "p2": "person"}

    def test_pet_without_animal_type_falls_back_to_animal(self) -> None:
        from types import SimpleNamespace

        from backend.services.prompts import _collect_detection_ids_from_enrichment

        enrichment = SimpleNamespace(
            clothing_classifications={}, clothing_segmentation={}, pose_results={},
            vehicle_classifications={}, vehicle_damage={},
            pet_classifications={"p1": SimpleNamespace()},  # no animal_type
        )
        result = _collect_detection_ids_from_enrichment(enrichment, None)
        assert result == {"p1": "animal"}

    def test_none_defaults_iterate_cleanly(self) -> None:
        from types import SimpleNamespace

        from backend.services.prompts import _collect_detection_ids_from_enrichment

        # Attributes present but None -> the ``or {}`` fold must keep this empty,
        # while the ``or -> and`` mutants also collapse here; the full-dict
        # assertion in test_all_sources… is the primary killer.
        enrichment = SimpleNamespace(
            clothing_classifications=None, clothing_segmentation=None, pose_results=None,
            vehicle_classifications=None, vehicle_damage=None, pet_classifications=None,
        )
        assert _collect_detection_ids_from_enrichment(enrichment, None) == {}
```

Kill check for D1 on mutant `…__mutmut_14` (`… "clothing_segmentation", {}) and {}`): `c2` never enters the dict → first test's `result["c2"]` raises `KeyError` (red). On the original the whole-dict equality passes (green). Covers `…__mutmut_14/26/35/47/60` (or→and) and the per-source attr-name C mutants (wrong attr name → empty bucket → missing key).

### Draft 2 — kills **K-cmp-op-flip (39)**, **D4-drop-not (5)**, **D5-insert-not (7)**, **G-continue->break (3)**, **K-arith-flip (partial)** in `format_confidence_quality_summary` + `_compute_confidence_quality`
Target file: `backend/tests/unit/services/test_prompts.py` (append new class; the function's only current covering test is an indirect call in `test_nemotron_analyzer.py::test_analyze_batch_calls_enrichment_pipeline` — no direct assertions exist today).
// UNVERIFIED — not yet run red/green

```python
class TestFormatConfidenceQualitySummary:
    """Tests for format_confidence_quality_summary tier boundaries (WP4.4).

    Surviving mutants flip ``==``/``<=``/``>=`` guards, ``continue`` to
    ``break`` in the zero-count tier loop, ``+=1`` to ``-=1``, and the
    ``conf is None or conf <= 0`` validity guard. A 4-tier fixture hits every
    tier boundary (0.90/0.75/0.60) and the invalid-confidence filter.
    """

    def test_empty_returns_empty(self) -> None:
        from backend.services.prompts import format_confidence_quality_summary

        assert format_confidence_quality_summary([]) == ""

    def test_tier_distribution_counts_and_boundaries(self) -> None:
        from backend.services.prompts import format_confidence_quality_summary

        detections = [
            {"class_name": "person", "confidence": 0.95},
            {"class_name": "car", "confidence": 0.90},   # exact EXCELLENT boundary
            {"class_name": "dog", "confidence": 0.75},   # exact GOOD boundary
            {"class_name": "cat", "confidence": 0.60},   # exact MODERATE boundary
            {"class_name": "bag", "confidence": 0.59},   # MARGINAL
            {"class_name": "ghost", "confidence": 0},    # invalid -> excluded
            {"class_name": "shadow"},                    # missing confidence -> excluded
        ]
        result = format_confidence_quality_summary(detections)

        assert "## Detection Confidence Quality" in result
        assert "- 2 detection(s) at EXCELLENT confidence (>=0.90) - trust fully" in result
        assert "- 1 detection(s) at GOOD confidence (0.75-0.89) - trust fully" in result
        assert "- 1 detection(s) at MODERATE confidence (0.60-0.74)" in result
        assert "- 1 detection(s) at MARGINAL confidence (<0.60)" in result
        # guidance block + join structure
        assert "Confidence guidance: EXCELLENT/GOOD detections are reliable." in result
        assert result.startswith("## Detection Confidence Quality\n")

    def test_confidence_quality_tier_boundaries(self) -> None:
        from backend.services.prompts import _ConfidenceQuality, _compute_confidence_quality

        assert _compute_confidence_quality(0.90) == _ConfidenceQuality.EXCELLENT
        assert _compute_confidence_quality(0.75) == _ConfidenceQuality.GOOD
        assert _compute_confidence_quality(0.60) == _ConfidenceQuality.MODERATE
        assert _compute_confidence_quality(0.0) == _ConfidenceQuality.MARGINAL
```

Kill check for G mutant `…__mutmut_46` (`if count == 0: continue→break`): fixture gives all four tiers count>0, so a `break` can't be distinguished… it can here via mutant `…__mutmut_18` (`+=1`→`-=1`): EXCELLENT count becomes −2 → line prints "- -2 detection(s)…" → assertion red. Boundary mutants (`>=0.90`→`>0.90`, `0.90`→`1.9`) flip the exact-boundary detections. Note: G-continue->break is *also* killed by Draft 5's time-gap case. TDD: red on each mutant, green on original.

### Draft 3 — kills **D1/L/M/I5 in CLIP field reads (≈45 survivors)** + **D4-drop-not (4 of 5)** in `format_clip_analysis_context`
Target file: `backend/tests/unit/services/test_prompt_formatters.py` (append after `TestFormatClothingAnalysisContext` @ 232; local-import style matches the file).
// UNVERIFIED — not yet run red/green

```python
class TestFormatClipAnalysisContextSections:
    """Per-field emission tests for format_clip_analysis_context (WP4.4).

    The function reads five optional CLIP fields via
    ``getattr(er, "<name>", None)`` and emits one section per non-None field.
    Survivors clobber the attribute name, delete the attr argument, or invert
    the ``is not None`` guards — every one of those silently drops or inverts a
    section. These tests emit each field in isolation and require its section.
    """

    @staticmethod
    def _clip_result(**fields):
        from types import SimpleNamespace

        defaults = dict(
            clip_scene_classification=None, clip_scene_top_label=None,
            clip_threat_matches=None, clip_anomaly_score=None,
            clip_anomaly_similarity=None,
        )
        return SimpleNamespace(**{**defaults, **fields})

    def test_all_none_returns_empty(self) -> None:
        from backend.services.prompts import format_clip_analysis_context

        assert format_clip_analysis_context(self._clip_result()) == ""

    def test_scene_classification_emits_scene_section(self, monkeypatch) -> None:
        import backend.services.prompts as prompts

        monkeypatch.setattr(
            prompts, "format_clip_scene_classification",
            lambda scores, top: "SCENE-SECTION", raising=False,
        )
        result = prompts.format_clip_analysis_context(
            self._clip_result(clip_scene_classification={"backyard": 0.9},
                             clip_scene_top_label="backyard")
        )
        assert "SCENE-SECTION" in result

    def test_anomaly_score_emits_anomaly_section(self, monkeypatch) -> None:
        import backend.services.prompts as prompts

        monkeypatch.setattr(
            prompts, "format_clip_anomaly_context",
            lambda score, sim: "ANOMALY-SECTION", raising=False,
        )
        result = prompts.format_clip_analysis_context(
            self._clip_result(clip_anomaly_score=0.42, clip_anomaly_similarity=0.31)
        )
        assert "ANOMALY-SECTION" in result

    def test_missing_attribute_means_no_section_not_crash(self) -> None:
        """An object without the CLIP attributes at all must yield ""."""
        from types import SimpleNamespace

        from backend.services.prompts import format_clip_analysis_context

        assert format_clip_analysis_context(SimpleNamespace()) == ""
```

Kill check: attribute-name clobber (`"clip_anomaly_score"`→`"XXclip_anomaly_scoreXX"`) → getattr default `None` → no `ANOMALY-SECTION` → red. D4 mutant `…__mutmut_18` (`if scene_scores is not None` → `is None`) → all-none test gets scene section (non-`""`) → red. The `getattr(er)` one-arg variants raise `TypeError` which this path doesn't swallow → red loudly. Green on original (note: monkeypatch targets the real helper names `format_clip_scene_classification` / `format_clip_anomaly_context` / `format_clip_threat_analysis` — verify they're module-level before finalizing; if they're imported lazily, replace the monkeypatch with a real dict payload asserted on the section header instead).

### Draft 4 — kills **I5-None-default + P1-visible-default-label + part of M** (day-name lookup) in `check_member_schedule`
Target file: `backend/tests/unit/services/test_prompts.py` (extend `TestCheckMemberSchedule` @ 5232 — whose covering tests currently assert zero string literals and only exercise `weekdays`/`all_day`).
// UNVERIFIED — not yet run red/green

```python
    def test_day_specific_key_used_on_friday(self) -> None:
        """Day-name schedule keys must be looked up case-sensitively per day."""
        schedule = {"friday": "08:00-12:00"}
        # 2024-01-19 is a Friday (weekday()==4)
        assert check_member_schedule(schedule, datetime(2024, 1, 19, 10, 0)) is True
        assert check_member_schedule(schedule, datetime(2024, 1, 19, 13, 0)) is False
        # a case-clobbered day_names entry ("FRIDAY") or a weekday index off-by-one
        # misses the key -> None instead of True/False
        assert check_member_schedule(schedule, datetime(2024, 1, 19, 10, 0)) is not None

    def test_saturday_key_preferred_over_weekends(self) -> None:
        schedule = {"saturday": "09:00-10:00", "weekends": "00:00-23:59"}
        # 2024-01-20 is a Saturday (weekday()==5)
        assert check_member_schedule(schedule, datetime(2024, 1, 20, 9, 30)) is True
        assert check_member_schedule(schedule, datetime(2024, 1, 20, 11, 30)) is False

    def test_overnight_window_wraps_midnight(self) -> None:
        schedule = {"daily": "22:00-06:00"}
        assert check_member_schedule(schedule, datetime(2024, 1, 15, 23, 30)) is True
        assert check_member_schedule(schedule, datetime(2024, 1, 16, 3, 0)) is True
        assert check_member_schedule(schedule, datetime(2024, 1, 16, 12, 0)) is False

    def test_malformed_time_string_returns_none_not_crash(self) -> None:
        schedule = {"weekdays": "9am-till-5"}
        assert check_member_schedule(schedule, datetime(2024, 1, 15, 10, 0)) is None
```

Kill check: mutant `…__mutmut_29` (`"friday"`→`"FRIDAY"`) → day_names lookup misses → `schedule_value None` → returns `None` → red on both True/False asserts. `weekday == 5`→`6`/`is_sunday and` index shifts break the Saturday case. The `+`→`-` minutes mutants (`start_parts[0]*60 - start_parts[1]`) break the overnight window's `<=`/`>=` bounds (23:30 inside a mis-computed 1320−30=1290 window). Green on original.

### Draft 5 — kills **A-guard-force-branch (partial), E-bool-flip (2), I4b, I5 in `_build_tracking_narratives`/`_infer_movement_pattern`**
Target file: `backend/tests/unit/services/test_prompts.py` (extend `TestBuildTrackingNarratives` @ 7985 and `TestInferMovementPattern` @ 7949; mock classes `MockEntityMatch`/`MockEntityEmbedding`/`MockZoneContext` already in file).
// UNVERIFIED — not yet run red/green

```python
    def test_missing_prev_camera_attr_falls_back_to_unknown_camera(self) -> None:
        """entity without camera_id -> narrative still renders with 'unknown camera'."""
        from types import SimpleNamespace

        entity = SimpleNamespace(attributes={"carrying": "backpack"})  # no camera_id
        match = MockEntityMatch(entity=entity, similarity=0.9, time_gap_seconds=120.0)
        result = _build_tracking_narratives({"42": [match]}, "Person", "current_cam", None)
        assert len(result) == 1
        assert "unknown camera" in result[0]
        assert "carrying backpack" in result[0]  # prev_attrs.get("carrying") survives

    def test_movement_pattern_rendered_when_inferred(self) -> None:
        zones = [MockZoneContext(zone_name="Driveway", zone_type="driveway")]
        entity = SimpleNamespace(camera_id="driveway_cam", attributes={})
        match = MockEntityMatch(entity=entity, similarity=0.9, time_gap_seconds=60.0)
        result = _build_tracking_narratives({"42": [match]}, "Person", "front_cam", zones)
        assert "Movement pattern:" in result[0]
        # zone_type membership strings ("driveway") are semantic: the (movement) or True
        # guard mutant would print "Movement pattern: None." via the empty-string arm
        assert "driveway" in result[0].lower()

    def test_time_gap_wording_uses_time_gap_seconds(self) -> None:
        entity = SimpleNamespace(camera_id="driveway_cam", attributes={})
        match = MockEntityMatch(entity=entity, similarity=0.9, time_gap_seconds=120.0)
        result = _build_tracking_narratives({"42": [match]}, "Person", "front_cam", None)
        assert "2 minute" in result[0].lower()  # _format_time_gap(120) wording
```

Kill check: `"unknown camera"`→`"XXunknown cameraXX"` (C) and `getattr(match_entity, "camera_id", None)` default→`""` (I5, `…__mutmut_22`) change/remove the fallback text → red. `(movement) or True` mutant prints `Movement pattern: None.` because `movement=""` is forced into the f-string arm → red. TDD: red on mutant diff, green on original. (Also kills G `…__mutmut_5` `continue→break` via a two-match variant if the first match's entity is `None`-attributed; kept simple here.)

### Draft 6 — kills **E-bool-flip (camera health), F-True->None, D1 in `_infer_movement_pattern`, I2b (camera-health default deletion)**
Target file: `backend/tests/unit/services/test_prompts.py` (extend `TestFormatCameraHealthContext` @ 3100; `MockSceneChange` @ 3084 already has `similarity_score/change_type/acknowledged`).
// UNVERIFIED — not yet run red/green

```python
    def test_missing_acknowledged_attribute_treated_as_acknowledged(self) -> None:
        """The getattr default is True: unknown objects must NOT alert (fail-closed)."""
        from types import SimpleNamespace

        from backend.services.prompts import format_camera_health_context

        # An object that does not carry `acknowledged` at all.
        result = format_camera_health_context(
            "cam1", [SimpleNamespace(similarity_score=0.4, change_type="view_tampered")],
        )
        assert result == ""  # default acknowledged=True -> silent

    def test_unknown_change_type_renders_generic_branch(self) -> None:
        from backend.services.prompts import format_camera_health_context

        scene_changes = [MockSceneChange(similarity_score=0.5, change_type="totally_new")]
        result = format_camera_health_context("camera_1", scene_changes)  # type: ignore[arg-type]
        assert "CAMERA HEALTH ALERT" in result
        assert "Scene change detected (similarity: 50%)" in result
        assert "Detection accuracy may be affected" in result
        assert "Baseline patterns" not in result
        assert "Verify camera integrity" not in result

    def test_similarity_default_used_when_attribute_missing(self) -> None:
        from types import SimpleNamespace

        from backend.services.prompts import format_camera_health_context

        sc = SimpleNamespace(change_type="view_blocked", acknowledged=False)  # no score
        result = format_camera_health_context("camera_1", [sc])
        assert "similarity: 0%" in result  # default 0.0, not a crash / None
```

Kill check: mutant `…__mutmut_7` (`getattr(sc, "acknowledged", True)`→default `None`) → unknown object treated as unacknowledged → `result != ""` → red. `True→False` flip (`…__mutmut_13`) same. Unknown-type mutants (`…__mutmut_31` `"unknown"`→`"UNKNOWN"` — harmless here, but `"unknown"`→`None` `…__mutmut_24` prints `similarity: None%`/crash) → exact-line asserts red. `0.0`→`None` default (I2b path: `:.0%` of `None` raises) → red. Green on original.

## Notes for the fixer lane (WP4.4 serial verify)

- Drafts use `types.SimpleNamespace` deliberately: the module's `getattr(x, name, default)` idiom and its dict/object dual-shape handling mean a namespace with *only* the named attrs exercises the real code path without importing the pydantic models; keep it that way to avoid coupling to `EnrichmentResult` construction.
- Draft 3's monkeypatch names (`format_clip_scene_classification`, `format_clip_anomaly_context`, `format_clip_threat_analysis`) are the sibling formatter functions called inside `format_clip_analysis_context` (prompts.py ~1293–1305) — confirm they're module-level before running; fallback plan in Draft 3 text.
- No repo files were modified by this triage; all drafts are proposals pending red/green in the single pytest lane.
