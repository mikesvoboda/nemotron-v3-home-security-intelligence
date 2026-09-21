# WP4.4 Triage Dossier — backend/services/summary_parser.py

**Generated:** 2026-09-18 · **Source:** `mutants/backend/services/summary_parser.py.meta` (exit_code 0 = survived)
**Survivors:** 49 of 229 keys · **Status: UNVERIFIED — no tests executed (live mutation run owns the machine)**

## Covering tests (from `mutants/mutmut-stats.json` → `tests_by_mangled_function_name`)

- Primary: `backend/tests/unit/services/test_summary_parser.py` (all five survivor functions)
- Secondary: `backend/tests/unit/api/test_summaries.py` (exercises parse_summary_content via API layer)
- Raw diffs: `/tmp/wp25/wp44-triage/sp_diffs.txt` (collected via read-only `uv run mutmut show`, all 49)

## Key structural facts driving classification

1. `_get_pattern_icon` is called **only** from `_generate_bullet_points` over `dominant_patterns ⊆ BEHAVIOR_PATTERNS`, and every entry in `BEHAVIOR_PATTERNS` is a key in `pattern_icons`. The `.get(..., "alert-circle")` default fallback is therefore **unreachable** → default-arg mutants are equivalent.
2. For the two patterns whose *mapped icon equals the fallback icon* ("loitering"→alert-circle, "unusual activity"→alert-circle), key mutations (XX-prefixed / UPPERCASE) make `.get` miss and return the *same* icon → semantically equivalent.
3. `_determine_severity`'s list-comprehension filter `if e.get("risk_level")` means the `.get("risk_level", DEFAULT)` **default is never used** (body only runs for truthy risk_level; the falsy cases are filtered out before `.lower()`) → all default-arg mutants on that line, including the `None`-default, are equivalent (no crash is reachable).
4. Camera-bullet text is built as `f"Activity at {camera}" + (f": {context}" if context else "")` — exact-text equality on an empty-context camera bullet simultaneously kills the empty-context conditional mutants (`_generate_bullet_points` m18/m19) and the no-match sentinel mutant (`_extract_camera_context` m18).

## Cluster table (counts sum to 49)

| # | Function | Pattern | Keys (≤3 examples) | N | Class | Note |
|---|----------|---------|--------------------|---|-------|------|
| C1 | _determine_severity | risk_levels comprehension key/filter mutations ("risk_level"→None/XX/UPPER case in get or filter) → level list empty/blank → severity silently falls back to score | 4, 8, 11 | 6 | TEST-GAP | Tests use events with level AND matching high score (95/75) so fallback coincides; no test pairs a risk_level with a contradicting low score |
| C2 | _determine_severity | `"high"` branch string mutated ("XXhighXX"/"HIGH") → high branch dead → score fallback | 19, 20 | 2 | TEST-GAP | Same killer test as C1 |
| C3 | _determine_severity | `.lower()`→`.upper()` on level extraction → "critical"/"high" never match → score fallback | 3 | 1 | TEST-GAP | Existing critical test uses score 95 (fallback coincides); needs level+low score |
| C4 | _determine_severity | `.get("risk_level", DEFAULT)` default-arg mutations (None / "XXXX" / omitted) — default unreachable (filter excludes falsy/missing levels) | 5, 7, 10 | 3 | EQUIVALENT | Verified by control-flow: comprehension body never sees a missing/None level |
| C5 | _severity_from_score | score thresholds off-by-one (>=80→>80/>=81; >=60→>60/>=61; >=40→>40/>=41) | 2, 6, 10 | 6 | TEST-GAP | Existing tests use 85/65/45/25 — never the 80/60/40 boundary values |
| C6 | _generate_bullet_points | camera `icon="camera"` string mutated ("XXcameraXX"/"CAMERA") | 14, 15 | 2 | TEST-GAP | Camera bullets located by text in every test; `icon=="camera"` never asserted |
| C7 | _generate_bullet_points | empty-context suffix mutation: condition forced true `(camera_context) or True` → trailing ": "; else-branch "XXXX" sentinel | 18, 19 | 2 | TEST-GAP | No test asserts exact camera-bullet text with empty context |
| C8 | _generate_bullet_points | pattern bullet `severity=severity` dropped→None (explicit None / kwarg removed — both default to None) | 31, 34 | 2 | TEST-GAP | `test_bullet_point_severity_from_content` asserts only `any(severity is not None)` — camera bullet satisfies it |
| C9 | _generate_bullet_points | weather guard `and`→`or`: weather bullet added whenever weather exists OR bullets empty (incl. empty-weather "all clear" case) | 35 | 1 | TEST-GAP | `test_weather_bullet_point_not_added_when_camera_points_exist` builds `weather_bp` but never asserts it is empty |
| C10 | _generate_bullet_points | weather bullet text mutations (conditions_text→None, join sep "XX, XX", text=None) | 37, 39, 42 | 3 | TEST-GAP | Weather bullet checked only by `icon=="cloud"`; text never asserted |
| C11 | _generate_bullet_points | weather bullet `severity=None` kwarg removed → dataclass default None (identical) | 45 | 1 | EQUIVALENT | Original already passes None explicitly |
| C12 | _extract_camera_context | truncation threshold mutated (`>50`→`>=50` truncates exact-50; `>50`→`>51` leaves 51-char untruncated) | 12, 13 | 2 | TEST-GAP | Only test uses 60-char context, where original and mutants coincide |
| C13 | _extract_camera_context | truncation text mutated (`[:47]`→`[:48]`; `"..."`→`"XX...XX"`) | 16, 17 | 2 | TEST-GAP | `"..." in text` assertion passes for "XX...XX" and for [:48] |
| C14 | _extract_camera_context | no-match fallback `""`→`"XXXX"` | 18 | 1 | TEST-GAP | Same killer assertion as C7 (exact empty-context bullet text) |
| C15 | _extract_camera_context | `re.IGNORECASE` flag removed → context not found for differently-cased camera mention | 5 | 1 | TEST-GAP | `test_extract_camera_names_case_insensitive` only asserts `len(focus_areas)>=1` |
| C16 | _get_pattern_icon | "suspicious behavior" map entry mutations (key XX/UPPER → default alert-circle ≠ alert-triangle; value mutations) | 14, 16, 17 | 4 | TEST-GAP | `test_bullet_point_icons_for_each_pattern` omits "suspicious behavior" and "unusual activity" |
| C17 | _get_pattern_icon | "unusual activity" map **value** mutations (XX/UPPER case) | 20, 21 | 2 | TEST-GAP | Same gap: pattern absent from per-pattern icon test |
| C18 | _get_pattern_icon | key mutations on loitering/unusual-activity entries — `.get` miss returns fallback icon which **equals** the mapped icon | 2, 3, 18 | 4 | EQUIVALENT | alert-circle == mapped value for both; unkillable by construction |
| C19 | _get_pattern_icon | `.get` default fallback arg mutations (None / omitted / XX / UPPER) — fallback unreachable (callers pass only BEHAVIOR_PATTERNS, all keyed) | 35, 37, 39 | 4 | EQUIVALENT | No direct callers outside the module pass unknown patterns |

**Totals:** 37 TEST-GAP · 12 EQUIVALENT · 0 LOW-VALUE · sum 49 ✓

## Drafted tests (append to `backend/tests/unit/services/test_summary_parser.py`)

All marked `// UNVERIFIED - not yet run red/green`. TDD procedure for each: run against mutant copy → assertion fails (red); run against original → passes (green).

### T1 — `TestInternalHelpers::test_severity_from_score_boundary_values` → kills C5 (6 mutants)

```python
    @pytest.mark.parametrize(
        ("score", "expected"),
        [
            (80, "critical"),  # boundary: >=80 is critical
            (79, "high"),
            (60, "high"),      # boundary: >=60 is high
            (59, "medium"),
            (40, "medium"),    # boundary: >=40 is medium
            (39, "low"),
        ],
    )
    def test_severity_from_score_boundary_values(self, score: int, expected: str) -> None:
        """_severity_from_score must treat 80/60/40 as inclusive lower bounds.

        // UNVERIFIED - not yet run red/green
        """
        from backend.services.summary_parser import _severity_from_score

        assert _severity_from_score(score) == expected
```

Kills m2/m3 (80→critical), m6/m7 (60→high), m10/m11 (40→medium).

### T2 — `TestSeverityDetermination::test_risk_level_wins_over_contradicting_score` → kills C1, C2, C3 (9 mutants)

```python
    def test_risk_level_wins_over_contradicting_score(self) -> None:
        """Explicit risk_level must beat the score-based fallback, not coincide with it.

        // UNVERIFIED - not yet run red/green
        """
        content = "Activity at Kitchen."

        high_result = parse_summary_content(
            content, events=[{"risk_score": 50, "risk_level": "high"}]
        )
        high_bp = [bp for bp in high_result.bullet_points if "Kitchen" in bp.text]
        assert len(high_bp) == 1
        assert high_bp[0].severity == "high"  # not "medium" from score fallback

        critical_result = parse_summary_content(
            content, events=[{"risk_score": 50, "risk_level": "critical"}]
        )
        critical_bp = [bp for bp in critical_result.bullet_points if "Kitchen" in bp.text]
        assert len(critical_bp) == 1
        assert critical_bp[0].severity == "critical"  # not "medium" from score fallback
```

Every C1/C2/C3 mutant breaks level→severity matching, so severity degrades to score-derived "medium".

### T3 — `TestBulletPointGeneration::test_camera_bullet_point_exact_identity` → kills C6, C7, C14, C15 (6 mutants)

```python
    def test_camera_bullet_point_exact_identity(self) -> None:
        """Camera bullet icon and exact text, including empty-context and cased-mention cases.

        // UNVERIFIED - not yet run red/green
        """
        # Empty context: camera name at end of sentence -> no ": <ctx>" suffix, no sentinel
        result = parse_summary_content("Activity in the Kitchen.")
        assert len(result.bullet_points) == 1
        assert result.bullet_points[0].icon == "camera"
        assert result.bullet_points[0].text == "Activity at Kitchen"

        # Case-insensitive content: context must still be extracted (re.IGNORECASE)
        cased = parse_summary_content("Activity at BEACH FRONT LEFT: person detected.")
        beach_bp = [bp for bp in cased.bullet_points if "Beach Front Left" in bp.text]
        assert len(beach_bp) == 1
        assert beach_bp[0].text == "Activity at Beach Front Left: person detected"
```

The exact-text assertion on "Activity at Kitchen" kills m14/m15 (icon), m18/m19 (forced ": " suffix / "XXXX" sentinel), and `_extract_camera_context` m18 (": XXXX"). The cased assertion kills `_extract_camera_context` m5 (IGNORECASE removed → context "" → text loses suffix).

### T4 — `TestBulletPointGeneration::test_camera_context_truncation_exact_lengths` → kills C12, C13 (4 mutants)

```python
    def test_camera_context_truncation_exact_lengths(self) -> None:
        """Truncation boundary is strictly >50 chars, cut at 47 + ellipsis (total 50).

        // UNVERIFIED - not yet run red/green
        """
        ctx50 = "a" * 50
        r50 = parse_summary_content(f"Activity at Beach Front Left: {ctx50}")
        bp50 = [bp for bp in r50.bullet_points if "Beach Front Left" in bp.text]
        assert len(bp50) == 1
        # exactly 50 chars: NOT truncated (kills >=50 mutant)
        assert bp50[0].text == f"Activity at Beach Front Left: {ctx50}"

        ctx51 = "b" * 51
        r51 = parse_summary_content(f"Activity at Beach Front Left: {ctx51}")
        bp51 = [bp for bp in r51.bullet_points if "Beach Front Left" in bp.text]
        assert len(bp51) == 1
        # 51 chars: truncated to 47 + "..." (kills >51, [:48], "XX...XX" mutants)
        assert bp51[0].text == "Activity at Beach Front Left: " + "b" * 47 + "..."
```

### T5 — `TestBulletPointGeneration::test_pattern_bullets_severity_and_full_icon_map` → kills C8, C16, C17 (8 mutants)

```python
    def test_pattern_bullets_severity_and_full_icon_map(self) -> None:
        """Pattern bullets carry the overall severity and the full icon map, incl. two absent patterns.

        // UNVERIFIED - not yet run red/green
        """
        # Pattern-only bullets must carry severity (not silently None)
        loiter = parse_summary_content("Person was loitering near the entrance.", events=[{"risk_score": 75}])
        assert len(loiter.bullet_points) == 1
        assert loiter.bullet_points[0].icon == "alert-circle"
        assert loiter.bullet_points[0].text == "Loitering behavior detected"
        assert loiter.bullet_points[0].severity == "high"

        # "suspicious behavior" maps to alert-triangle (omitted from per-pattern test)
        susp = parse_summary_content("Suspicious behavior detected at Kitchen.")
        susp_bp = [bp for bp in susp.bullet_points if "suspicious behavior" in bp.text.lower()]
        assert len(susp_bp) == 1
        assert susp_bp[0].icon == "alert-triangle"

        # "unusual activity" maps to alert-circle (omitted from per-pattern test)
        unu = parse_summary_content("Unusual activity detected at Kitchen.")
        unu_bp = [bp for bp in unu.bullet_points if "unusual activity" in bp.text.lower()]
        assert len(unu_bp) == 1
        assert unu_bp[0].icon == "alert-circle"
```

(`severity == "high"` kills C8's m31/m34; the two omitted patterns' icons kill C16/C17 mutants.)

### T6 — `TestBulletPointGeneration::test_weather_bullet_point_exact_text_and_guard` → kills C9, C10 (4 mutants)

```python
    def test_weather_bullet_point_exact_text_and_guard(self) -> None:
        """Weather bullet: exact ", "-joined text, and never added beside camera/pattern bullets.

        // UNVERIFIED - not yet run red/green
        """
        weather_only = parse_summary_content("Activity during rainy nighttime conditions.")
        cloud = [bp for bp in weather_only.bullet_points if bp.icon == "cloud"]
        assert len(cloud) == 1
        assert cloud[0].text == "Activity during rainy, nighttime conditions"
        assert cloud[0].severity is None

        # Camera bullet present -> NO weather bullet at all (kills and->or guard mutant)
        with_camera = parse_summary_content("Activity at Kitchen during rainy conditions.")
        assert all(bp.icon != "cloud" for bp in with_camera.bullet_points)
        assert len(with_camera.bullet_points) == 1

        # Nothing extracted at all -> no bullet (guard must stay false on empty inputs)
        clear = parse_summary_content("All clear for the evening.")
        assert clear.bullet_points == []
```

Exact text kills m37 ("Activity during None conditions"), m39 ("XX, XX" join), m42 (text None); the guard assertions kill m35.

## Kill coverage of drafts vs. TEST-GAP mutants

T1: C5(6) · T2: C1+C2+C3(9) · T3: C6+C7+C14+C15(6) · T4: C12+C13(4) · T5: C8+C16+C17(8) · T6: C9+C10(4) — **37/37 TEST-GAP mutants covered.** EQUIVALENT clusters (12) are unkillable by construction (documented in table).

## Caveats (UNVERIFIED)

- Content strings chosen to avoid accidental camera/pattern/weather cross-matches (e.g. "Dock" alone matches no KNOWN_CAMERA — verified by offline regex/set simulation, not by running the suite).
- Exact-text assertions depend on `_extract_camera_context`'s `[^.!?]+` boundary: sentences end at "." so group capture excludes the period — simulation-verified for every drafted content string.
