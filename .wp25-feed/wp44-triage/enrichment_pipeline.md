# WP4.4 Triage Dossier — backend/services/enrichment_pipeline.py (surviving mutants)

Run source: `mutants/backend/services/enrichment_pipeline.py.meta` (exit_code 0 = survived).
**Survivors: 162** of 666 checked (4471 not yet checked at collection time — triage is of the checked set).

All 162 survivors fall in exactly 4 methods of `class EnrichmentResult`:

| function                                                                   | survivors |
| -------------------------------------------------------------------------- | --------- |
| `get_summary_flags` (backend/services/enrichment_pipeline.py:1685)         | 74        |
| `to_dict` (backend/services/enrichment_pipeline.py:1333)                   | 62        |
| `to_prompt_context` (backend/services/enrichment_pipeline.py:1510)         | 25        |
| `get_weather_risk_modifier` (backend/services/enrichment_pipeline.py:1671) | 1         |

Method: diffs taken via `uv run mutmut show <key>` (validated) + bulk body-extraction/diff from the
mutants copy (cross-checked against `mutmut show` on keys 101/134/93 — identical). Full per-mutant
listing: `/tmp/wp25/wp44-triage/compact.txt`, raw diffs `/tmp/wp25/wp44-triage/diffs_all.json`.

## Covering test files (from mutants/mutmut-stats.json → tests_by_mangled_function_name)

| file                                                                         | relevant classes / lines                                                                                                                                                                                                                                                                                                      |
| ---------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `backend/tests/unit/services/test_enrichment_pipeline.py`                    | TestEnrichmentResultToDict :766, TestEnrichmentResultSummaryFlags :1008, TestEnrichmentResultToPromptContext :2226, ...SummaryFlagsExtended :2531, ...ToDictExtended :2577, TestEnrichmentResultPoseActionSummaryFlags :5361, TestEnrichmentResultPoseActionPromptContext :5444, TestEnrichmentResultWeatherIntegration :6580 |
| `backend/tests/unit/services/test_enrichment_pipeline_household_matching.py` | test_enrichment_result_to_dict_includes_household_matches :618                                                                                                                                                                                                                                                                |
| `backend/tests/unit/services/test_violence_loader.py`                        | test_enrichment_result_to_dict_includes_violence :229                                                                                                                                                                                                                                                                         |
| `backend/tests/unit/services/test_enrichment_data_consistency.py`            | TestHouseholdMatchToDict :374, TestEnrichmentDataRoundTrip :608 (these assert the nested `LicensePlateResult.to_dict`, not EnrichmentResult.to_dict's inline dicts)                                                                                                                                                           |

**Root cause of the whole feed:** the tests are "presence + one field" style — they check a flag/section
exists and spot-check one value, but never pin the payload **key set** of serialized dicts/flags, never
pin **severity values** (the vehicle-damage test even asserts `"critical" in sev or "warning" in sev`
— a tautology that accepts the flipped value AND matches `"critical" in "XXcriticalXX"` as substring),
and to_prompt_context is only tested for key presence, never that the enrichment data was actually
**passed to the formatters**.

## Cluster table (counts sum to 162)

| #   | function                  | pattern                                                                                                                                                                                                                                                                                                                                                    | count | class      | example keys (…\_\_mutmut_N)        |
| --- | ------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----- | ---------- | ----------------------------------- |
| 1   | to_dict                   | dict-key rename (`"k"` → `"XXkXX"`/`"K"`) in serialized sections: plate/face bbox+source_detection_id, pose_results, depth_analysis, threat_detection, age/gender/person_embeddings, smoke_fire, yolo_world, vision_extraction, household nested (detection_id/member_id/similarity/match_type/member_role/schedule_status/vehicle_id/vehicle_description) | 44    | TEST-GAP   | to_dict#3, to_dict#29, to_dict#67   |
| 2   | to_dict                   | `getattr(match,"member_role"/"schedule_status",…)` target/attr clobber → role & schedule always serialize as None                                                                                                                                                                                                                                          | 6     | TEST-GAP   | to_dict#79, to_dict#84, to_dict#94  |
| 3   | to_dict                   | optional-section ternary forced to None (`if x and False` / hasattr attr clobber) for depth, smoke_fire, vision_extraction, threat → section silently dropped                                                                                                                                                                                              | 6     | TEST-GAP   | to_dict#37, to_dict#60, to_dict#110 |
| 4   | to_dict                   | duck-typed threat guard (`… and hasattr(t,"to_dict")`) flipped to or/crash variants — observable only for threat objects lacking to_dict                                                                                                                                                                                                                   | 4     | LOW-VALUE  | to_dict#45, to_dict#47, to_dict#48  |
| 5   | to_dict                   | `getattr(m,"attr", )` default-arg omitted — HouseholdMatch slots dataclass always defines the field                                                                                                                                                                                                                                                        | 2     | EQUIVALENT | to_dict#83, to_dict#92              |
| 6   | to_prompt_context         | formatter arguments replaced by None/omitted (violence, image*quality, quality_change*\*, clothing_classifications/segmentation, vehicle_classifications/damage, pet, depth) → enrichment section silently becomes "No X" placeholder in the LLM prompt                                                                                                    | 14    | TEST-GAP   | to_prompt_context#3, #10, #26       |
| 7   | to_prompt_context         | pose payload: dict comprehension → None, or inner keys `"classification"`/`"confidence"` renamed → formatter falls back to "unknown"/0.0%                                                                                                                                                                                                                  | 6     | TEST-GAP   | to_prompt_context#35, #38, #41      |
| 8   | to_prompt_context         | action payload `{"0": self.action_results}` → None / and-False                                                                                                                                                                                                                                                                                             | 2     | TEST-GAP   | to_prompt_context#44, #45           |
| 9   | to_prompt_context         | `time_of_day=time_of_day` → None/omitted → damage prompt loses `**TIME CONTEXT**` line                                                                                                                                                                                                                                                                     | 2     | TEST-GAP   | to_prompt_context#27, #29           |
| 10  | to_prompt_context         | outer action dict key `"0"`→`"XX0XX"` — label-only text "Person XX0XX:" in prompt string                                                                                                                                                                                                                                                                   | 1     | LOW-VALUE  | to_prompt_context#47                |
| 11  | get_summary_flags         | suspicious-action severity pipeline unasserted: `severity=None`, ternary and-False/or-True on risk>=0.9 & >=0.7, threshold bumps 1.9/1.7, `>` vs `>=` at 0.7, all 3 severity value renames, payload `"severity"` key rename                                                                                                                                | 16    | TEST-GAP   | gsf#112, gsf#118, gsf#123           |
| 12  | get_summary_flags         | flag payload `"description"` key renamed (violence, suspicious_attire, face_covered, vehicle_damage incl. `', '.join` separator → `"XX, XX"`) — tests never touch description for these flags                                                                                                                                                              | 9     | TEST-GAP   | gsf#8, gsf#19, gsf#44               |
| 13  | get_summary_flags         | pose-flag severity tier `"alert" if pose_class=="crouching" else "warning"` — key renames, ==/!= flip, and-False/or-True, value renames (crouching→alert, running/lying→warning)                                                                                                                                                                           | 11    | TEST-GAP   | gsf#84, gsf#88, gsf#91              |
| 14  | get_summary_flags         | weather flag contract: type value + description/severity key+value renames — existing test filters `"weather" in type.lower()` (survives both renames) and asserts only `len>=1`                                                                                                                                                                           | 8     | TEST-GAP   | gsf#149, gsf#151, gsf#155           |
| 15  | get_summary_flags         | `dict.get` defaults/keys unreachable-at-call-site (detected_action/confidence always present when block entered: gate requires has_suspicious_action) + `>=0.9` vs `>0.9` (weights ∈ {1.0,.7,.5,.2})                                                                                                                                                       | 8     | EQUIVALENT | gsf#96, gsf#107, gsf#117            |
| 16  | get_summary_flags         | suspicious-pose set members "running"/"lying" clobbered — tests only exercise "crouching"                                                                                                                                                                                                                                                                  | 4     | TEST-GAP   | gsf#67, gsf#69                      |
| 17  | get_summary_flags         | pose gate `and`→`or`, `>`→`>=` at 0.5 — no negative case (standing/high-conf, boundary)                                                                                                                                                                                                                                                                    | 2     | TEST-GAP   | gsf#71, gsf#73                      |
| 18  | get_summary_flags         | action gate `has_suspicious_action and action_results` → `or` → benign actions emit suspicious_action flag                                                                                                                                                                                                                                                 | 1     | TEST-GAP   | gsf#93                              |
| 19  | get_summary_flags         | confidence lookup key renames (`"XXconfidenceXX"`/`"CONFIDENCE"`/`get(None,…)`) → description shows "(0% confidence)"                                                                                                                                                                                                                                      | 3     | TEST-GAP   | gsf#104, gsf#108, gsf#109           |
| 20  | get_summary_flags         | quality_issue flag `"severity":"alert"` key+value renames — test checks description only                                                                                                                                                                                                                                                                   | 4     | TEST-GAP   | gsf#60, gsf#62                      |
| 21  | get_summary_flags         | vehicle-damage severity inside already-true guard: and-False→warning, `XXcriticalXX` (survives substring tautology)                                                                                                                                                                                                                                        | 2     | TEST-GAP   | gsf#47, gsf#49                      |
| 22  | get_summary_flags         | same ternary: or-True→always critical, else-branch renames — unreachable-else / tautology (gate guarantees condition True)                                                                                                                                                                                                                                 | 3     | EQUIVALENT | gsf#48, gsf#51, gsf#52              |
| 23  | get_summary_flags         | weather gate `confidence >= 0.5` → `> 0.5` boundary (conf exactly 0.5 loses flag)                                                                                                                                                                                                                                                                          | 1     | TEST-GAP   | gsf#137                             |
| 24  | get_summary_flags         | low-visibility tuple member `"snowy"` renamed — test covers foggy only                                                                                                                                                                                                                                                                                     | 2     | TEST-GAP   | gsf#144, gsf#145                    |
| 25  | get_weather_risk_modifier | `self._determine_nighttime()` → None — clear-night +0.25 path becomes 0.0 (test covers foggy/0.1 which ignores the arg)                                                                                                                                                                                                                                    | 1     | TEST-GAP   | wrm#2                               |

**Totals: TEST-GAP 144 · EQUIVALENT 13 · LOW-VALUE 5 = 162.**

Highest-value targets: clusters 1-3 (66 keys: the serialization contract), 6-9 (24: prompt-context data
actually reaching the formatters), 11/13/21 (29: severity tiering of security flags), 12/14/16/17/24 (26:
flag payload contract), 23/25 (2 boundary/nighttime), 20 (4), 18 (1).

## Drafted tests (UNVERIFIED — not yet run red/green)

TDD procedure for each: add test → run → it FAILS against the mutant source (assertion on the mutated
value/key) and PASSES against original `backend/services/enrichment_pipeline.py`; a red/green check per
cluster before adding to the baseline. Style follows the existing classes in
`backend/tests/unit/services/test_enrichment_pipeline.py` (pytest classes, dataclass kwargs,
`from __future__ import annotations` already at file top).

### T1 — to_dict full serialization contract (kills clusters 1, 2, 3 = 56 mutants)

Append to class `TestEnrichmentResultToDict` in
`backend/tests/unit/services/test_enrichment_pipeline.py` (needs `from unittest.mock import MagicMock`
— already imported there — plus `HouseholdMatch` import):

```python
    def test_to_dict_serialization_contract_all_sections(self) -> None:
        """UNVERIFIED - not yet run red/green.

        Pins the serialized key set + values of every EnrichmentResult.to_dict()
        section (the storage/API contract). Kills every key-rename, getattr
        clobber, and forced-to-None-ternary mutant in to_dict.
        """
        from unittest.mock import MagicMock

        from backend.services.household_matcher import HouseholdMatch
        from backend.services.vitpose_loader import PoseResult

        bbox = BoundingBox(x1=1, y1=2, x2=3, y2=4, confidence=0.9)
        plate = LicensePlateResult(
            bbox=bbox, text="XYZ789", confidence=0.92, ocr_confidence=0.85, source_detection_id=1
        )
        face = FaceResult(bbox=bbox, confidence=0.97, source_detection_id=2)
        person_match = HouseholdMatch(
            member_id=7,
            member_name="Alice",
            similarity=0.91,
            match_type="person",
            member_role="resident",
            schedule_status=True,
        )
        vehicle_match = HouseholdMatch(
            vehicle_id=3,
            vehicle_description="Red Van",
            similarity=0.88,
            match_type="vehicle_visual",
        )
        depth = MagicMock()
        depth.to_dict.return_value = {"max_depth_m": 5.0}
        smoke = MagicMock()
        smoke.to_dict.return_value = {"smoke_detected": True}
        vision = MagicMock()
        vision.to_dict.return_value = {"persons": []}
        threat = MagicMock()
        threat.to_dict.return_value = {"weapon": "knife"}

        result = EnrichmentResult(
            license_plates=[plate],
            faces=[face],
            pose_results={"1": PoseResult(keypoints=[], pose_class="crouching", pose_confidence=0.8)},
            depth_analysis=depth,
            smoke_fire_detection=smoke,
            vision_extraction=vision,
            threat_detection=threat,
            age_classifications={},
            gender_classifications={},
            person_embeddings={},
            yolo_world_detections=[{"label": "person"}],
            person_household_matches={1: person_match},
            vehicle_household_matches={2: vehicle_match},
        )
        data = result.to_dict()

        # Top-level section keys (renames would drop/add keys)
        for key in (
            "license_plates", "faces", "pose_results", "depth_analysis", "threat_detection",
            "age_classifications", "gender_classifications", "person_embeddings",
            "smoke_fire_detection", "yolo_world_detections", "vision_extraction",
            "person_household_matches", "vehicle_household_matches",
        ):
            assert key in data, f"to_dict must expose section key {key!r}"

        # Nested plate/face payloads
        assert set(data["license_plates"][0]) == {
            "bbox", "text", "confidence", "ocr_confidence", "source_detection_id"
        }
        assert set(data["faces"][0]) == {"bbox", "confidence", "source_detection_id"}

        # Optional sections must serialize when populated (forced-None mutants)
        assert data["depth_analysis"] == {"max_depth_m": 5.0}
        assert data["smoke_fire_detection"] == {"smoke_detected": True}
        assert data["vision_extraction"] == {"persons": []}
        assert data["threat_detection"] == {"weapon": "knife"}

        # Household payloads: full key set incl. getattr-sourced role/schedule
        assert data["person_household_matches"]["1"] == {
            "detection_id": 1,
            "member_id": 7,
            "member_name": "Alice",
            "similarity": 0.91,
            "match_type": "person",
            "member_role": "resident",
            "schedule_status": True,
        }
        assert data["vehicle_household_matches"]["2"] == {
            "detection_id": 2,
            "vehicle_id": 3,
            "vehicle_description": "Red Van",
            "similarity": 0.88,
            "match_type": "vehicle_visual",
        }
```

Red: key renames → membership/equality assert fails (e.g. `"member_role": None` ≠ `"resident"`);
forced-None → `data["depth_analysis"] is None`. Green on original.

### T2 — suspicious-action severity tiers + confidence rendering (kills clusters 11, 19, 18 = 20 mutants)

Into class `TestEnrichmentResultPoseActionSummaryFlags` (line 5361):

```python
    @pytest.mark.parametrize(
        ("detected_action", "expected_severity"),
        [
            ("breaking in", "critical"),  # risk weight 1.0
            ("loitering", "alert"),        # risk weight 0.7
            ("trying", "warning"),         # suspicious keyword, neutral weight 0.5
        ],
    )
    def test_summary_flags_action_severity_tiers(
        self, detected_action: str, expected_severity: str
    ) -> None:
        """UNVERIFIED - not yet run red/green.

        Severity must tier exactly: weight >= 0.9 -> critical, >= 0.7 -> alert, else warning.
        Existing test checks description substring only. Also pins the confidence
        rendering ("90%") and the flag payload key set.
        """
        result = EnrichmentResult(
            action_results={"detected_action": detected_action, "confidence": 0.9}
        )
        flags = [f for f in result.get_summary_flags() if f["type"] == "suspicious_action"]
        assert len(flags) == 1
        assert flags[0]["severity"] == expected_severity
        assert "(90% confidence)" in flags[0]["description"]
        assert set(flags[0]) == {"type", "description", "severity"}

    def test_summary_flags_no_action_flag_for_benign_action(self) -> None:
        """UNVERIFIED - not yet run red/green.

        A benign (not suspicious) action must NOT produce a suspicious_action flag;
        pins the `has_suspicious_action and action_results` gate (and->or mutant
        would emit a warning-severity flag for 'walking normally').
        """
        result = EnrichmentResult(
            action_results={"detected_action": "walking normally", "confidence": 0.9}
        )
        flags = [f for f in result.get_summary_flags() if f["type"] == "suspicious_action"]
        assert flags == []
```

Weights verified against `backend/services/xclip_loader.py:679 get_action_risk_weight`
(high 1.0 / medium 0.7 / low 0.2 / neutral 0.5). Red: tiered values differ, `"XXcriticalXX"`/`None`/
`"WARNING"` ≠ expected, key set missing `"severity"` (renamed key → KeyError), benign-case list non-empty.

### T3 — strict severity of pose / vehicle-damage / quality flags (kills clusters 13, 21, 20 = 17 mutants)

Into class `TestEnrichmentResultSummaryFlagsExtended` (line 2531). Note the existing high-security test
at :2585 asserts `"critical" in sev or "warning" in sev` — replace that assert with the strict one here:

```python
    def test_summary_flags_pose_severity_crouching_alert_others_warning(self) -> None:
        """UNVERIFIED - not yet run red/green.

        crouching -> 'alert'; running/lying -> 'warning' (exact values; existing
        test only checks the description contains the pose class).
        """
        from backend.services.vitpose_loader import PoseResult

        crouch = EnrichmentResult(
            pose_results={"1": PoseResult(keypoints=[], pose_class="crouching", pose_confidence=0.85)}
        ).get_summary_flags()
        run = EnrichmentResult(
            pose_results={"1": PoseResult(keypoints=[], pose_class="running", pose_confidence=0.85)}
        ).get_summary_flags()

        crouch_flags = [f for f in crouch if f["type"] == "suspicious_pose"]
        run_flags = [f for f in run if f["type"] == "suspicious_pose"]
        assert len(crouch_flags) == 1 and len(run_flags) == 1
        assert crouch_flags[0]["severity"] == "alert"
        assert run_flags[0]["severity"] == "warning"

    def test_summary_flags_vehicle_high_security_damage_severity_is_critical(self) -> None:
        """UNVERIFIED - not yet run red/green.

        Strict equality (the old 'critical in sev or warning in sev' tautology also
        matched the flipped 'warning' and substring 'XXcriticalXX').
        """
        damage = VehicleDamageResult(
            detections=[DamageDetection(damage_type="glass_shatter", confidence=0.9, bbox=(0, 0, 50, 50))]
        )
        flags = EnrichmentResult(vehicle_damage={"1": damage}).get_summary_flags()
        vflag = next(f for f in flags if f["type"] == "vehicle_damage")
        assert vflag["severity"] == "critical"

    def test_summary_flags_quality_change_severity_is_alert(self) -> None:
        """UNVERIFIED - not yet run red/green. Pins the quality_issue severity value."""
        flags = EnrichmentResult(
            quality_change_detected=True, quality_change_description="Sudden quality degradation"
        ).get_summary_flags()
        qflag = next(f for f in flags if f["type"] == "quality_issue")
        assert qflag["severity"] == "alert"
```

### T4 — flag payload key set + pose negative/boundary cases (kills clusters 12, 16, 17 = 15 mutants)

Into class `TestEnrichmentResultSummaryFlags` (line 1008):

```python
    def test_all_flags_carry_exact_payload_keys(self) -> None:
        """UNVERIFIED - not yet run red/green.

        Every summary flag must carry exactly {type, description, severity}
        (Nemotron JSON contract). Kills description-key and severity-key renames
        across violence/attire/face-cover/vehicle-damage blocks.
        """
        clothing = ClothingClassification(
            top_category="ski mask", confidence=0.9, all_scores={},
            is_suspicious=True, is_service_uniform=False, raw_description="Alert: ski mask",
        )
        seg = ClothingSegmentationResult(
            clothing_items=set(), has_face_covered=True, has_bag=False, coverage_percentages={}
        )
        damage = VehicleDamageResult(
            detections=[
                DamageDetection(damage_type="glass_shatter", confidence=0.9, bbox=(0, 0, 50, 50)),
                DamageDetection(damage_type="scratch", confidence=0.8, bbox=(0, 0, 40, 40)),
            ]
        )
        result = EnrichmentResult(
            violence_detection=ViolenceDetectionResult(
                is_violent=True, confidence=0.85, violent_score=0.85, non_violent_score=0.15
            ),
            clothing_classifications={"1": clothing},
            clothing_segmentation={"1": seg},
            vehicle_damage={"1": damage},
        )
        flags = result.get_summary_flags()
        types = {f["type"] for f in flags}
        assert {"violence", "suspicious_attire", "face_covered", "vehicle_damage"} <= types
        for flag in flags:
            assert set(flag) == {"type", "description", "severity"}, f"bad payload keys: {flag}"
        vflag = next(f for f in flags if f["type"] == "vehicle_damage")
        # damage_types joined with ', ' — mutant joins with 'XX, XX'
        assert len(vflag["description"].split("Vehicle 1: ")[1].split(", ")) == 2

    def test_summary_flags_pose_negative_and_boundary_cases(self) -> None:
        """UNVERIFIED - not yet run red/green.

        running/lying must flag (set members), a high-confidence NON-suspicious
        pose must not (gate is AND, not OR), and confidence exactly 0.5 must not
        (gate is strictly >).
        """
        from backend.services.vitpose_loader import PoseResult

        def pose_flags(pose: object) -> list:
            return [
                f
                for f in EnrichmentResult(pose_results={"1": pose}).get_summary_flags()
                if f["type"] == "suspicious_pose"
            ]

        assert len(pose_flags(PoseResult(keypoints=[], pose_class="running", pose_confidence=0.9))) == 1
        assert len(pose_flags(PoseResult(keypoints=[], pose_class="lying", pose_confidence=0.9))) == 1
        assert pose_flags(PoseResult(keypoints=[], pose_class="standing", pose_confidence=0.95)) == []
        assert pose_flags(PoseResult(keypoints=[], pose_class="crouching", pose_confidence=0.5)) == []
```

### T5 — weather flag contract + boundary + snowy + clear-night modifier (kills clusters 14, 23, 24, 25 = 12 mutants)

Into class `TestEnrichmentResultWeatherIntegration` (line 6580):

```python
    def test_weather_flag_exact_contract(self) -> None:
        """UNVERIFIED - not yet run red/green.

        Exact type value, severity value, and description keys — the existing
        test's `"weather" in type.lower()` filter survives both key and value
        renames (lower() re-folds 'WEATHER_...'; the filter only checks type).
        """
        weather = WeatherResult(
            condition="foggy/hazy", simple_condition="foggy", confidence=0.85, all_scores={}
        )
        flags = EnrichmentResult(weather_classification=weather).get_summary_flags()
        wf = [f for f in flags if f["type"] == "weather_low_visibility"]
        assert len(wf) == 1
        assert wf[0]["severity"] == "info"
        assert set(wf[0]) == {"type", "description", "severity"}
        assert wf[0]["description"].startswith("Foggy conditions")
        assert "reduced visibility" in wf[0]["description"]

    @pytest.mark.parametrize("condition", ["foggy", "snowy"])
    def test_weather_low_visibility_flag_includes_snowy(self, condition: str) -> None:
        """UNVERIFIED - not yet run red/green. Tuple member 'snowy' must flag like foggy."""
        weather = WeatherResult(
            condition=condition, simple_condition=condition, confidence=0.8, all_scores={}
        )
        flags = EnrichmentResult(weather_classification=weather).get_summary_flags()
        assert [f for f in flags if f["type"] == "weather_low_visibility"]

    def test_weather_flag_at_confidence_boundary(self) -> None:
        """UNVERIFIED - not yet run red/green. Gate is >= 0.5, so conf exactly 0.5 flags."""
        weather = WeatherResult(
            condition="foggy/hazy", simple_condition="foggy", confidence=0.5, all_scores={}
        )
        flags = EnrichmentResult(weather_classification=weather).get_summary_flags()
        assert [f for f in flags if f["type"] == "weather_low_visibility"]

    def test_clear_night_weather_risk_modifier_uses_nighttime_flag(self) -> None:
        """UNVERIFIED - not yet run red/green.

        get_weather_risk_modifier must forward _determine_nighttime(); clear +
        is_nighttime=True -> +0.25 (mutant forwarding None yields 0.0). The foggy
        +0.1 test cannot see this path.
        """
        weather = WeatherResult(
            condition="clear/sunny", simple_condition="clear", confidence=0.9, all_scores={}
        )
        result = EnrichmentResult(weather_classification=weather, is_nighttime=True)
        assert result.get_weather_risk_modifier() == pytest.approx(0.25, abs=0.01)
```

### T6 — to_prompt_context formatter-argument contract (kills clusters 6, 7, 8, 9 = 24 mutants; also incidentally kills cluster 10's key-label mutant)

Into class `TestEnrichmentResultPoseActionPromptContext` (line 5444):

```python
    def test_to_prompt_context_forwards_populated_data_to_formatters(self) -> None:
        """UNVERIFIED - not yet run red/green.

        Every formatter must receive the actual enrichment payload (not None and
        not with args dropped). Mutants that swap self.<field> for None, or drop
        quality-change / time_of_day args, are invisible to key-presence tests.
        """
        from backend.services.vitpose_loader import PoseResult

        violence = ViolenceDetectionResult(
            is_violent=True, confidence=0.85, violent_score=0.85, non_violent_score=0.15
        )
        quality = ImageQualityResult(
            quality_score=45.0, brisque_score=30.0, is_blurry=True, is_noisy=False,
            is_low_quality=True, quality_issues=["blur"],
        )
        clothing = ClothingClassification(
            top_category="mask", confidence=0.9, all_scores={}, is_suspicious=True,
            is_service_uniform=False, raw_description="Alert: mask",
        )
        seg = ClothingSegmentationResult(
            clothing_items=set(), has_face_covered=True, has_bag=False, coverage_percentages={}
        )
        vehicles = {"1": VehicleClassificationResult(
            vehicle_type="sedan", confidence=0.9, display_name="sedan",
            is_commercial=False, all_scores={},
        )}
        damage = VehicleDamageResult(
            detections=[DamageDetection(damage_type="glass_shatter", confidence=0.9, bbox=(0, 0, 50, 50))]
        )
        pets = {"1": PetClassificationResult(
            animal_type="cat", confidence=0.9, cat_score=0.9, dog_score=0.1, is_household_pet=True
        )}
        pose = PoseResult(keypoints=[], pose_class="standing", pose_confidence=0.9)
        depth = MagicMock()
        actions = {"detected_action": "loitering", "confidence": 0.8}
        result = EnrichmentResult(
            violence_detection=violence,
            image_quality=quality,
            quality_change_detected=True,
            quality_change_description="Broken lens",
            clothing_classifications={"1": clothing},
            clothing_segmentation={"1": seg},
            vehicle_classifications=vehicles,
            vehicle_damage=damage,
            pet_classifications=pets,
            pose_results={"1": pose},
            action_results=actions,
            depth_analysis=depth,
        )

        targets = [
            "format_action_recognition_context", "format_clothing_analysis_context",
            "format_depth_context", "format_image_quality_context",
            "format_pet_classification_context", "format_pose_analysis_context",
            "format_vehicle_classification_context", "format_vehicle_damage_context",
            "format_violence_context", "format_weather_context",
        ]
        with ExitStack() as stack:
            mocks = {
                name: stack.enter_context(
                    patch(f"backend.services.prompts.{name}", return_value=f"MOCK:{name}")
                )
                for name in targets
            }
            context = result.to_prompt_context(time_of_day="night")

        assert all(context[key] == f"MOCK:{name}" for key, name in [
            ("violence_context", "format_violence_context"),
            ("image_quality_context", "format_image_quality_context"),
            ("clothing_analysis_context", "format_clothing_analysis_context"),
            ("vehicle_classification_context", "format_vehicle_classification_context"),
            ("vehicle_damage_context", "format_vehicle_damage_context"),
            ("pet_classification_context", "format_pet_classification_context"),
            ("pose_analysis", "format_pose_analysis_context"),
            ("action_recognition", "format_action_recognition_context"),
            ("depth_context", "format_depth_context"),
        ])
        mocks["format_violence_context"].assert_called_once_with(violence)
        mocks["format_image_quality_context"].assert_called_once_with(quality, True, "Broken lens")
        mocks["format_clothing_analysis_context"].assert_called_once_with(
            {"1": clothing}, {"1": seg}
        )
        mocks["format_vehicle_classification_context"].assert_called_once_with(vehicles)
        mocks["format_vehicle_damage_context"].assert_called_once_with(damage, time_of_day="night")
        mocks["format_pet_classification_context"].assert_called_once_with(pets)
        mocks["format_pose_analysis_context"].assert_called_once_with(
            {"1": {"classification": "standing", "confidence": 0.9}}
        )
        mocks["format_action_recognition_context"].assert_called_once_with({"0": actions})
        mocks["format_depth_context"].assert_called_once_with(depth)
```

Requires adding to the test-file header: `from contextlib import ExitStack` (`patch`, `MagicMock`, all
result-class imports already present at test_enrichment_pipeline.py:16-46). Red on every args→None /
args-dropped mutant (call-args mismatch), on pose inner-key renames (`classification`/`confidence`
fallback keys ≠ asserted payload dict), and on `time_of_day=None`. Green on original.

## Notes / judgment calls

- **EQUIVALENT (13):** inside the suspicious-action block the `has_suspicious_action` gate guarantees
  `"detected_action"` is present and suspicious, so the `get(..., default)` defaults at gsf 96/98/101/102
  are unreachable; `"confidence"` likewise always present → gsf 105/107/110 dead; risk weights are a
  discrete set {1.0,0.7,0.5,0.2} → `>=0.9` ≡ `>0.9` (gsf 117); the vehicle-damage ternary sits inside
  `if damage.has_high_security_damage:` so or-True and both else-branch renames (gsf 48/51/52) can never
  change output; `getattr(m,"attr")` vs 3-arg identical because HouseholdMatch is a slots dataclass whose
  fields always exist (to_dict 83/92).
- **LOW-VALUE (5):** to_dict 45/47/48/49 change crash/no-crash semantics of a defensive `hasattr(t,"to_dict")`
  duck-typing guard (asserting AttributeError-on-nonconforming-object is not a useful test); to_prompt_context
  47 only changes the literal det-id label string in prompt prose.
- The vehicle-damage severity tautology `"critical" in sev or "warning" in sev`
  (test_enrichment_pipeline.py:2585 block) should itself be replaced by T3's strict assert when T3 lands.
- Mutant count vs meta: 162 survivors here are of the 666 keys checked so far; 4471 were still `null`
  when this dossier was written. Re-triage after the run completes — new survivors in `_determine_nighttime`,
  `get_risk_modifiers`, `_serialize_pose_result` etc. are NOT in this dossier.
