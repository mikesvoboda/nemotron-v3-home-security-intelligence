# WP4.4 Triage Dossier — backend/services/prompts.py

- **Survivors:** 218 of 3085 checked mutants (exit_code_by_key == 0).
- **Diff extraction:** manual diff of `mutants/backend/services/prompts.py` variant bodies vs `backend/services/prompts.py` (saved raw per-mutant diffs at `/tmp/wp25/wp44-triage/prompts-diffs.txt`); spot-checked against `uv run mutmut show` — identical.
- **Covering test files (tests_by_mangled_function_name):**
  - `backend/tests/unit/services/test_prompts.py` — TestFormatEnhancedReidContext (line 3611), TestResolvePoseSceneConflict (3870), TestFormatPoseSceneConflictWarning (4024), TestFormatHouseholdContext (4898), MockHouseholdMatch (4875), TestCheckMemberSchedule (5232), TestFormatEnhancedClothingContext (7064), TestFormatSceneContext (7527), cross-camera imports (7722-7729), TestFormatTimeGap (7928), TestInferMovementPattern (7949)
  - `backend/tests/unit/services/test_prompt_formatters.py` — TestFormatOndemandEnrichmentContext (1253), TestFormatEnhancedClothingContext (1321), TestFormatFlorenceSceneContext (1384)

## Classification summary

| Classification | Mutants |
|---|---|
| TEST-GAP | 160 |
| LOW-VALUE | 34 |
| EQUIVALENT | 24 |
| **Total** | **218** |

Root cause of the TEST-GAP bulk: tests of these prompt formatters assert with `substring in result` on *happy-path fixtures where every optional dict key is present*. Mutants of (a) exact text lines, (b) `.get(key, default)` fallbacks, (c) non-dict/defensive branches, and (d) schedule day-selection fall through these assertions untouched.

## Cluster table

Counts sum to 218. Example keys are suffixes after `backend.services.prompts.`.

| # | Pattern (function / concern) | N | Class | Example keys | Note |
|---|---|---|---|---|---|
| C1 | `_format_time_gap`: minute/hour boundary `<`→`<=` / `+1` (`minutes<1`, `minutes<60`) | 4 | TEST-GAP | x__format_time_gap__mutmut_4, _5, _7 | Tests use 30/45/180/5400/7200 s — never exactly 60 s or 3600 s. `<=1` → "60 seconds ago" at 60 s; `<=60` → "60 minutes ago" at 1 h. Covering: TestFormatTimeGap (test_prompts.py:7928) |
| C2 | `_format_time_gap`: hours divisor `/60`→`/61` | 1 | TEST-GAP | x__format_time_gap__mutmut_12 | Survives because `:.1f` rounds 7200→"2.0" and 5400→"1.5" identically. Differs at e.g. 18000 s: "5.0" vs "4.9". Same test file |
| C3 | `_infer_movement_pattern`: `not prev or not cur` → `and` (empty-guard) | 1 | TEST-GAP | x__infer_movement_pattern__mutmut_1 | Test only passes (None,None); (None,"cam") never checked — mutant emits "moved from None to cam". TestInferMovementPattern (test_prompts.py:7949) |
| C4 | `_infer_movement_pattern`: `has_entry_point = False` → `True` | 1 | TEST-GAP | x__infer_movement_pattern__mutmut_6 | Every narrative gains "now at entry point"; happy-path tests only assert the first part. |
| C5 | `_infer_movement_pattern`: `has_entry_point = False` → `None` | 1 | EQUIVALENT | x__infer_movement_pattern__mutmut_5 | `None` falsy; identical control flow. |
| C6 | `_infer_movement_pattern`: `getattr(zc,"zone_type","")` default mutated (None / omitted / "XXXX") | 3 | EQUIVALENT | x__infer_movement_pattern__mutmut_11, _14, _17 | Default only matters when zone lacks `zone_type`; "" vs None vs "XXXX" all fail the membership checks identically. (omitted-default crashes on attribute-less zones — only realistic divergence, defensive.) |
| C7 | `_infer_movement_pattern`: `current_zone_types.append(ztype)` → `append(None)` | 1 | TEST-GAP | x__infer_movement_pattern__mutmut_18 | driveway/yard branches die; test_driveway_zone_detection still passes because "driveway" appears via the *camera name* substring. |
| C8 | `_infer_movement_pattern`: time thresholds `<2`/`<10` → `<=` / `+1` | 4 | TEST-GAP | x__infer_movement_pattern__mutmut_29, _30, _34 | Tests use 60/180/900 s; boundaries 120 s, 600 s, 660 s never probed. `<3` → 120 s becomes "in rapid succession". |
| C9 | `_infer_movement_pattern`: `"driveway"/"yard" in zones` → XX / UPPER / `not in` | 6 | TEST-GAP | x__infer_movement_pattern__mutmut_45, _51, _43 | `not in` flips branch order; XX/UPPER kill the branch. Zone descriptions silently vanish from risk narrative. |
| C10 | `_infer_movement_pattern`: narrative literals `parts.append(...)` XX/UPPER | 6 | TEST-GAP | x__infer_movement_pattern__mutmut_32, _41, _48 | "XXin rapid successionXX" still contains asserted substring "rapid succession"; needs exact-string or full-line assert. |
| C11 | `_infer_movement_pattern`: `", ".join` → `"XX, XX".join` | 1 | LOW-VALUE | x__infer_movement_pattern__mutmut_58 | Separator pollution in prompt text only; no logic. |
| C12 | `_infer_movement_pattern`: return `if parts or True` / else `"XXXX"` | 2 | EQUIVALENT | x__infer_movement_pattern__mutmut_56, _59 | `parts` is unconditionally non-empty after the guard; both fallback arms unreachable (and `join([])==""` anyway). |
| C13 | `check_member_schedule`: `day_names` list member XX/UPPER (per-day key) | 14 | TEST-GAP | x_check_member_schedule__mutmut_21, _25, _31 | Day-specific schedule key silently not found; tests only use Saturday, where the (dead) `elif is_saturday and "saturday" in` fallback masks it. Days Mon–Fri,Sun entirely unexercised. TestCheckMemberSchedule (test_prompts.py:5232) |
| C14 | `check_member_schedule`: redundant saturday/sunday `elif` key literals XX/UPPER | 4 | EQUIVALENT | x_check_member_schedule__mutmut_37, _38, _41 | Dead code: `elif is_saturday and "saturday" in typical_schedule` can never fire — its key is identical to `day_names[5]`, so the earlier lookup already caught any dict containing it. |
| C15 | `check_member_schedule`: `is_saturday`/`is_sunday` → None / `==6` / `==7` | 4 | EQUIVALENT | x_check_member_schedule__mutmut_12, _14, _15 | These flags feed only the dead elifs above; value can never change output. |
| C16 | `check_member_schedule`: day-guard operator flips (`!=`, `and`→`or`, `in`→`not in`) | 4 | TEST-GAP | x_check_member_schedule__mutmut_13, _16, _40 | `!=`/`or` make a dict like `{"saturday":"10:00-14:00","weekdays":...}` select the Saturday window on a *Monday*; M43 → `KeyError` on Sunday `{"weekends":...}` dict. Reachable, unasserted. |
| C17 | `check_member_schedule`: `schedule_value = None` → `""` | 1 | EQUIVALENT | x_check_member_schedule__mutmut_18 | `""` falls through all parse guards and returns `None` at the end anyway. |
| C18 | `check_member_schedule`: `hh*60 + mm` → `- mm` in start/end parse | 2 | TEST-GAP | x_check_member_schedule__mutmut_84, _92 | Every test uses round hours (`:00`), where `+0` and `-0` are identical. `09:30-17:30` moves the window by 2×minutes. |
| C19 | `check_member_schedule`: overnight window boundary ops (`end<start`→`<=`, overnight `>=`→`>`, `<=`→`<`) | 3 | TEST-GAP | x_check_member_schedule__mutmut_99, _101, _102 | Overnight test uses 23:00/03:00/12:00 — never exactly 22:00 or 06:00; `<=` on `end<start` turns "09:00-09:00" into all-day True. |
| C20 | `format_household_context`: legacy `base_risk = 5 if similarity > 0.9 else 15` | 4 | TEST-GAP | x_format_household_context__mutmut_54, _57, _58 | This branch runs only when `schedule_status is None`; tests cover True/False but never None+high-similarity. `and False`/`>=`/`>1.9` all change the LLM's stated base risk (5→15/15/15). TestFormatHouseholdContext (test_prompts.py:4898) |
| C21 | `format_household_context`: `similarity * 100` → `* 101` | 1 | TEST-GAP | x_format_household_context__mutmut_27 | Invisible for 2-decimal similarities (floor(101s)==floor(100s)); differs on 3-decimal production values (0.955→95 vs 96). |
| C22 | `format_household_context`: schedule line text XX ("Within expected hours" / "Outside normal hours") | 2 | TEST-GAP | x_format_household_context__mutmut_40, _48 | Tests assert substrings contained inside the XX-wrapped line. |
| C23 | `format_household_context`: ASCII box border chars XX / `box_width` 64→65 | 7 | LOW-VALUE | x_format_household_context__mutmut_2, _6, _13 | Cosmetic frame characters/width; no test or consumer depends on exact border. |
| C24 | `format_household_context`: "KNOWN PERSON MATCH: None" line case/XX variants | 3 | TEST-GAP | x_format_household_context__mutmut_61, _62, _63 | Assertion `"None" in result or "unknown" in result.lower()` is true even for the uppercased mutant. |
| C25 | `format_household_context`: "## RISK MODIFIERS (Apply These First)" header XX/UPPER | 2 | TEST-GAP | x_format_household_context__mutmut_18, _20 | `assert "RISK MODIFIERS" in result` survives both mutations. |
| C26 | `format_household_context`: return `"\n"` → `"XX\nXX"` join | 1 | LOW-VALUE | x_format_household_context__mutmut_76 | Join separator only. |
| C27 | `format_enhanced_reid_context`: RISK MODIFIER lines (-40/-20/-10) XX-wrapped or lowercased | 6 | TEST-GAP | x_format_enhanced_reid_context__mutmut_27, _28, _31 | Tests assert "-40 points"/"established trusted entity" substrings that survive wrapping/case change; the literal `RISK MODIFIER` token is asserted nowhere. TestFormatEnhancedReidContext (test_prompts.py:3611) |
| C28 | `format_enhanced_reid_context`: "Base risk: 50" / "No risk modifier" text XX | 2 | TEST-GAP | x_format_enhanced_reid_context__mutmut_5, _43 | "XX-> Base risk: 50XX" still contains "Base risk: 50". |
| C29 | `format_enhanced_reid_context`: return join `"\n"` → `"XX\nXX"` (both early + final return) | 2 | LOW-VALUE | x_format_enhanced_reid_context__mutmut_9, _47 | Separator text only. |
| C30 | `format_florence_attributes`: `valid_count += 1` → `=1`/`-=1`/`+=2` | 3 | EQUIVALENT | x_format_florence_attributes__mutmut_11, _12, _13 | `valid_count` is read only via `== 0`; every mutation preserves the zero/non-zero property. |
| C31 | `format_florence_attributes`: return join XX | 1 | LOW-VALUE | x_format_florence_attributes__mutmut_18 | Separator text only. |
| C32 | `format_florence_scene_context`: `high_risk` set members weapon/knife/tool/gun XX/UPPER | 8 | TEST-GAP | x_format_florence_scene_context__mutmut_33, _35, _39 | **Security-relevant**: those object labels stop being flagged HIGH RISK. Survive only because the test uses `crowbar` (whose own mutants were killed). TestFormatFlorenceSceneContext (test_prompt_formatters.py:1384) |
| C33 | `format_florence_scene_context`: risk comprehension `r in o.lower()` → `not in` | 1 | TEST-GAP | x_format_florence_scene_context__mutmut_44 | Inverts: benign labels get flagged, weapons escape. Existing fixture has 3 labels; mutant still shows a HIGH RISK line so the assert passes. |
| C34 | `format_florence_scene_context`: `florence_result.get("<section>")` key mutants (None / missing / XX / UPPER) × 4 sections | 16 | TEST-GAP | x_format_florence_scene_context__mutmut_49, _72, _77, _82 | `dense_captions`, `phrase_grounding`, `region_descriptions`, `security_vqa` extraction breaks → whole sections never render. **No test feeds these four keys at all.** |
| C35 | `format_florence_scene_context`: section guards `and isinstance(...)` → `or` | 4 | LOW-VALUE | x_format_florence_scene_context__mutmut_53, _76, _81, _86 | Only diverges on truthy-but-wrong-type values (crash instead of skip) — defensive path no pipeline produces. |
| C36 | `format_florence_scene_context`: labels default `[]` → `None` | 2 | EQUIVALENT | x_format_florence_scene_context__mutmut_23, _64 | Guarded by `if labels:`; both falsy. |
| C37 | `format_florence_scene_context`: labels default omitted (KeyError) / `isinstance or True` (AttributeError) | 4 | LOW-VALUE | x_format_florence_scene_context__mutmut_21, _25, _62 | Defensive-path crashes on shapes ("objects" without "labels", or non-dict) that callers never produce. |
| C38 | `format_florence_scene_context`: f-string `', '.join` XX separators + final `"\n"` join | 4 | LOW-VALUE | x_format_florence_scene_context__mutmut_30, _48, _71, _90 | Separator text within/between prompt lines. |
| C39 | `format_florence_scene_context`: header "### Scene Analysis (Florence-2)" XX | 1 | LOW-VALUE | x_format_florence_scene_context__mutmut_4 | Cosmetic header. |
| C40 | `format_ondemand_enrichment_context`: `if sections else ""` → `or True` | 1 | EQUIVALENT | x_format_ondemand_enrichment_context__mutmut_24 | `"\n\n".join([]) == ""` — fallback arm identical. |
| C41 | `format_ondemand_enrichment_context`: `"\n\n"` → `"XX\n\nXX"` join | 1 | LOW-VALUE | x_format_ondemand_enrichment_context__mutmut_26 | Separator text only. |
| C42 | `format_pose_scene_conflict_warning`: `scene_keywords` standing/walking/running/lying XX/UPPER | 8 | TEST-GAP | x_format_pose_scene_conflict_warning__mutmut_9, _11, _13 | Warning then says `scene shows "unknown"` instead of the real pose. Tests only ever use a `sitting` scene (whose mutants were killed). TestFormatPoseSceneConflictWarning (test_prompts.py:4024) |
| C43 | `format_pose_scene_conflict_warning`: `scene_pose = "unknown"` default → None/XX/UNKNOWN | 3 | LOW-VALUE | x_format_pose_scene_conflict_warning__mutmut_16, _17, _18 | Default only shows in warning text when no keyword matches; interpolated, never logic-tested. (M16 renders literal `None` — sloppy but cosmetic.) |
| C44 | `format_scene_context`: word-boundary ops (`rfind` args, `find`→`rfind`, needle XX, `>0`→`>1`) | 5 | TEST-GAP | x_format_scene_context__mutmut_11, _16, _17, _18, _20 | `find` mutant truncates at the FIRST space → caption collapses to "A..." while `len<=500 and endswith("...")` asserts still pass: the whole "truncate near the limit at a word boundary" contract is unasserted. TestFormatSceneContext (test_prompts.py:7527) |
| C44b | `format_scene_context`: `last_space > 0` → `>= 0` | 1 | EQUIVALENT | x_format_scene_context__mutmut_19 | Caption is `.strip()`ed first, so `last_space == 0` is unreachable. |
| C45 | `format_scene_context`: `truncate_at = max_length - 3` → `- 4` | 1 | LOW-VALUE | x_format_scene_context__mutmut_8 | Output stays within the documented max_length bound; loses one char of content. |
| C46 | `format_enhanced_clothing_context`: non-dict fallback arms broken (`isinstance or True` × 5 ternaries + `else str(x)` → `str(None)` × 5) | 14 | TEST-GAP | x_format_enhanced_clothing_context__mutmut_15, _25, _34 | Original supports non-dict entries (`getattr(obj,"confidence",0.0)` / `str(value)`); mutants crash (AttributeError) or print "None". No test feeds a non-dict sub-result. TestFormatEnhancedClothingContext (test_prompt_formatters.py:1321, test_prompts.py:7064) |
| C47 | `format_enhanced_clothing_context`: `get("confidence", 0.0)` default → None/omitted/1.0 (×4 categories) | 12 | TEST-GAP | x_format_enhanced_clothing_context__mutmut_22, _53, _115 | Dict without `confidence`: original → 0.0 (no ALERT); mutant 1.0 → spurious ALERT line, mutant None → TypeError crash. Tests always include `confidence`. |
| C48 | `format_enhanced_clothing_context`: `get("top_match", "<label>")` default → None/omitted/XX/UPPER (×5 categories) | 20 | TEST-GAP | x_format_enhanced_clothing_context__mutmut_27, _63, _94, _125, _144 | Largest gap: prompt falls back to "None"/KeyError/garbage label when `top_match` absent. Tests always include `top_match`. |
| C49 | `format_enhanced_clothing_context`: confidence thresholds `>0.5`/`>0.6` → `>=` | 3 | TEST-GAP | x_format_enhanced_clothing_context__mutmut_35, _66, _97 | Boundary confidences exactly 0.5/0.6 never tested; `>=` admits a lower-confidence match into the alert. |
| C50 | `format_enhanced_clothing_context`: header literal XX/case + return join XX | 4 | LOW-VALUE | x_format_enhanced_clothing_context__mutmut_4, _5, _151 | Header text unasserted but cosmetic to the LLM; join separator. |
| C51 | `resolve_pose_scene_conflict`: `resolution` explanation strings XX/case | 6 | TEST-GAP | x_resolve_pose_scene_conflict__mutmut_34, _36, _47 | Tests assert `"scene" in result["resolution"].lower()` — survives every case/wrap mutation; should assert exact string. TestResolvePoseSceneConflict (test_prompts.py:3870) |
| C52 | `resolve_pose_scene_conflict`: winner literal `"scene"` → `"XXsceneXX"`/`"SCENE"` | 2 | EQUIVALENT | x_resolve_pose_scene_conflict__mutmut_21, _22 | Downstream check is only `if resolved_winner == "pose"`; any non-"pose" value takes the identical scene return path. |

**Total: 218** (C1–C52; per-function sums: time_gap 5, movement 26, member_schedule 32, household 20, reid 10, florence_attrs 4, florence_scene 40, warning 11, scene_context 7, ondemand 2, clothing 53, resolve 8).

## Drafted tests (top-value TEST-GAP clusters)

All drafts are **UNVERIFIED — not yet run red/green**. TDD procedure for each: add the test → run against the mutant copy (or apply the diff manually) and confirm the specific assert fails → run against original `backend/services/prompts.py` and confirm it passes → only then commit.

### T1 — kills C13 (+C14/C15-adjacent, C16, C19; 21 of 32 member_schedule survivors)

Target file: `backend/tests/unit/services/test_prompts.py`, class `TestCheckMemberSchedule` (line 5232). `check_member_schedule` is already imported at module top.

```python
    @pytest.mark.parametrize(
        "day, key",
        [
            (0, "monday"),
            (1, "tuesday"),
            (2, "wednesday"),
            (3, "thursday"),
            (4, "friday"),
            (5, "saturday"),
            (6, "sunday"),
        ],
    )
    def test_day_specific_key_wins_over_generic_buckets(self, day: int, key: str) -> None:
        """NEM-3315: the day_names[weekday] lookup must find the lowercase day key.

        If a day's key is mutated (case/garbage), the lookup falls through to the
        01:00-02:00 weekday/weekend windows, flipping both verdicts.
        UNVERIFIED - not yet run red/green
        """
        from datetime import datetime

        schedule = {key: "10:00-14:00", "weekdays": "01:00-02:00", "weekends": "01:00-02:00"}
        # 2024-01-07 (Sunday) + day offset => the requested weekday
        base = datetime(2024, 1, 7, 11, 0) + __import__("datetime").timedelta(days=day)
        assert base.weekday() == day
        assert check_member_schedule(schedule, base) is True
        # Outside the day-specific window: only reachable if the day key resolved
        late = base.replace(hour=1, minute=30)
        assert check_member_schedule(schedule, late) is False

    def test_stray_saturday_key_does_not_override_weekday(self) -> None:
        """Day-guard flips (weekday != 5, and->or) must not select another day's window.

        UNVERIFIED - not yet run red/green
        """
        from datetime import datetime

        # Monday 2024-01-15 at 11:00
        schedule = {"saturday": "10:00-14:00", "weekdays": "01:00-02:00"}
        assert check_member_schedule(schedule, datetime(2024, 1, 15, 11, 0)) is False

        schedule = {"sunday": "10:00-14:00", "weekdays": "01:00-02:00"}
        assert check_member_schedule(schedule, datetime(2024, 1, 15, 11, 0)) is False

    def test_weekend_bucket_on_sunday_without_sunday_key(self) -> None:
        """'sunday' not-in flip must not KeyError / mis-select on a weekends-only dict.

        UNVERIFIED - not yet run red/green
        """
        from datetime import datetime

        # Sunday 2024-01-14
        schedule = {"weekends": "09:00-17:00"}
        assert check_member_schedule(schedule, datetime(2024, 1, 14, 10, 0)) is True
        assert check_member_schedule(schedule, datetime(2024, 1, 14, 18, 0)) is False

    def test_minute_component_parsed_into_window(self) -> None:
        """'*60 + mm' mutations shift the window by 2x the minute value.

        UNVERIFIED - not yet run red/green
        """
        from datetime import datetime

        schedule = {"daily": "09:30-17:30"}
        assert check_member_schedule(schedule, datetime(2024, 1, 15, 8, 30)) is False
        assert check_member_schedule(schedule, datetime(2024, 1, 15, 9, 15)) is False
        assert check_member_schedule(schedule, datetime(2024, 1, 15, 9, 45)) is True
        assert check_member_schedule(schedule, datetime(2024, 1, 15, 17, 15)) is True
        assert check_member_schedule(schedule, datetime(2024, 1, 15, 17, 45)) is False

    def test_overnight_window_exact_boundaries(self) -> None:
        """Overnight range is inclusive at both 22:00 and 06:00; equal start/end is not all-day.

        UNVERIFIED - not yet run red/green
        """
        from datetime import datetime

        schedule = {"daily": "22:00-06:00"}
        assert check_member_schedule(schedule, datetime(2024, 1, 15, 22, 0)) is True
        assert check_member_schedule(schedule, datetime(2024, 1, 15, 21, 59)) is False
        assert check_member_schedule(schedule, datetime(2024, 1, 15, 6, 0)) is True
        assert check_member_schedule(schedule, datetime(2024, 1, 15, 6, 1)) is False

        # Degenerate window: end_minutes == start_minutes must NOT take the overnight branch
        degenerate = {"daily": "09:00-09:00"}
        assert check_member_schedule(degenerate, datetime(2024, 1, 15, 12, 0)) is False
        assert check_member_schedule(degenerate, datetime(2024, 1, 15, 9, 0)) is True
```

### T2 — kills C34 (16 florence extraction-key survivors)

Target file: `backend/tests/unit/services/test_prompt_formatters.py`, class `TestFormatFlorenceSceneContext` (line 1384). Follows the file's in-test import style.

```python
    def test_extraction_sections_render_from_their_documented_keys(self) -> None:
        """dense_captions/phrase_grounding/region_descriptions/security_vqa must be read
        under their exact lowercase keys and rendered into their section blocks.

        Kills get(key) mutants (None / missing / XX / UPPER) that silently drop the
        whole section: each expected string is exact-line level, not fuzzy.
        UNVERIFIED - not yet run red/green
        """
        from backend.services.prompts import format_florence_scene_context

        result = format_florence_scene_context(
            {
                "dense_captions": [{"caption": "person near the side fence"}],
                "phrase_grounding": [
                    {"matched": True, "phrase": "face mask", "bboxes": [[1, 2, 3, 4]]}
                ],
                "region_descriptions": {"3": "carrying a cardboard box"},
                "security_vqa": {"3": {"Is a weapon visible?": "No weapon visible"}},
            }
        )

        assert "**Region Descriptions:**" in result
        assert "- person near the side fence" in result
        assert "**Phrase Grounding Matches:** face mask (1 location(s))" in result
        assert "**Detection Region Descriptions:**" in result
        assert "- [3] carrying a cardboard box" in result
        assert "**Security Assessment (VQA):**" in result
        assert "[Detection 3]:" in result
        assert "Q: Is a weapon visible?" in result
        assert "A: No weapon visible" in result
```

### T3 — kills C48 (20 clothing top_match-default survivors)

Target file: `backend/tests/unit/services/test_prompt_formatters.py`, class `TestFormatEnhancedClothingContext` (line 1321).

```python
    def test_missing_top_match_uses_fallback_labels(self) -> None:
        """Every category must print its documented default label when top_match is absent.

        XX / UPPER / None / KeyError (single-arg .get) fallback mutants change or crash
        the printed label. UNVERIFIED - not yet run red/green
        """
        from backend.services.prompts import format_enhanced_clothing_context

        result = format_enhanced_clothing_context(
            {
                "suspicious": {"confidence": 0.8},
                "delivery": {"confidence": 0.7},
                "utility": {"confidence": 0.6},
                "carrying": {"confidence": 0.9},
                "casual": {},
            }
        )

        assert "**ALERT**: suspicious attire (confidence: 80%)" in result
        assert "Service worker identified: delivery uniform (70%)" in result
        assert "Utility worker identified: utility worker (60%)" in result
        assert "Carrying: carrying item (90%)" in result
        assert "General attire: casual attire" in result
```

### T4 — kills C47 (12 clothing confidence-default survivors)

Same class/file as T3.

```python
    def test_missing_confidence_defaults_to_zero_and_no_alerts(self) -> None:
        """A category dict without 'confidence' means 0.0: no ALERT/uniform lines,
        carrying prints (0%). 1.0 mutants inject a spurious ALERT; None mutants crash
        on comparison/format. UNVERIFIED - not yet run red/green
        """
        from backend.services.prompts import format_enhanced_clothing_context

        result = format_enhanced_clothing_context(
            {
                "suspicious": {"top_match": "face covering"},
                "delivery": {"top_match": "courier vest"},
                "utility": {"top_match": "hi-vis vest"},
                "carrying": {"top_match": "toolbox"},
            }
        )

        assert "ALERT" not in result
        assert "Service worker identified" not in result
        assert "Utility worker identified" not in result
        assert "Carrying: toolbox (0%)" in result
```

### T5 — kills C46 (14 clothing non-dict fallback survivors)

Same class/file as T3.

```python
    def test_non_dict_category_entries_use_str_and_attr_fallback(self) -> None:
        """Sub-results that are plain strings (not dicts) must print via str() and take
        the getattr-confidence path (0.0). isinstance-or-True mutants raise
        AttributeError; str(None) mutants print "None".
        UNVERIFIED - not yet run red/green
        """
        from backend.services.prompts import format_enhanced_clothing_context

        result = format_enhanced_clothing_context(
            {
                "suspicious": "ski mask",
                "carrying": "large duffel bag",
                "casual": "business casual",
            }
        )

        assert "ALERT" not in result  # getattr("ski mask","confidence",0.0) == 0.0
        assert "Carrying: large duffel bag (0%)" in result
        assert "General attire: business casual" in result
```

### T6 — kills C32 + C33 (9 high-risk object flagging survivors)

Same class/file as T2.

```python
    @pytest.mark.parametrize("label", ["weapon", "knife", "crowbar", "tool", "gun"])
    def test_every_high_risk_keyword_triggers_flag(self, label: str) -> None:
        """Each member of the high_risk set must flag a matching label; the XX/UPPER
        mutants (weapon/knife/tool/gun) silently stop flagging.
        UNVERIFIED - not yet run red/green
        """
        from backend.services.prompts import format_florence_scene_context

        result = format_florence_scene_context({"security_objects": {"labels": [label]}})

        assert "**HIGH RISK OBJECTS**" in result
        assert label in result

    def test_benign_labels_are_not_flagged(self) -> None:
        """The 'r not in o.lower()' inversion must not flag ordinary labels.

        UNVERIFIED - not yet run red/green
        """
        from backend.services.prompts import format_florence_scene_context

        result = format_florence_scene_context(
            {"security_objects": {"labels": ["person", "backpack", "bicycle"]}}
        )

        assert "**Security Objects Detected:** person, backpack, bicycle" in result
        assert "**HIGH RISK OBJECTS**" not in result
```

## Notes for WP4.4

- T1–T6 collectively kill up to 91 of the 160 TEST-GAP mutants; remaining clusters (C1/C2 time-gap boundaries, C9/C10 movement text+thresholds, C20–C25 household display, C27/C28 reid text, C42 warning keywords, C44 scene-context boundary, C51 resolution strings) are each killable by one exact-string/boundary assert in the named covering test class.
- The recurring assertion anti-pattern to stamp out repo-wide: `assert needle in result` on formatter output. Prefer `result.splitlines()` membership or `==` on the full line for prompt contract strings.
- C35/C37/C43/C46 boundary: several "defensive-path crash" clusters are LOW-VALUE here because callers (enrichment pipeline) produce well-typed dicts; if WP4.4 wants belt-and-braces coverage anyway, T5 shows the template.
- EQUIVALENT clusters C14/C15 flag genuinely dead code in `check_member_schedule` (`elif is_saturday and "saturday" in ...` can never fire; `is_saturday`/`is_sunday` are write-only otherwise) — candidates for a small refactor ticket rather than tests.
