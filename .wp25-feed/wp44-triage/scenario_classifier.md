# WP4.4 Triage Dossier — backend/services/scenario_classifier.py

**Generated:** 2026-09-17 (WP4.3 finding feed → WP4.4). **Status: UNVERIFIED — no tests were run (live mutation run owns the machine).**

## Inputs

- Verdicts: `mutants/backend/services/scenario_classifier.py.meta` → 412 keys, **112 survivors**, 155 killed, 145 null (not yet checked).
- Diffs: `uv run mutmut show <key>` (batched via `mutmut.__main__.get_diff_for_mutant`, 0 errors; scratch copy at `/tmp/wp25/wp44-triage/_sc_diffs.txt`).
- Covering tests: `mutants/mutmut-stats.json → tests_by_mangled_function_name`. **All three survivor-bearing functions are covered only by `backend/tests/unit/services/test_scenario_classifier.py`** (783 lines; classes `TestApplyHysteresis` :230, `TestDetectTailgating` :296, `TestAdjustRiskScore` :369, `TestEdgeCases` :460, `TestTailgatingEscalation` :554).
- Survivor functions: `x_adjust_risk_score` 51, `x_detect_tailgating` 50, `x_apply_hysteresis` 11.
- Note: `adjust_risk_score` has **no production consumers yet** (repo-wide grep) — its metadata dict is a declared-but-unconsumed public contract (documented in the docstring), which is why key mutations survive. The test file contains **zero `caplog` assertions** — all logging mutations survive trivially.

## Structural facts that drive the verdicts

1. `detect_tailgating`'s gap loop reads `.get("detected_at", 0)` **directly**, ignoring the `timestamp` fallback used in the sort key. For timestamp-only inputs the loop sees all-zeros (gap 0.0, order-independent) — so mutations that only break the sort-key `timestamp` fallback are behavior-invariant (EQUIVALENT), while mutations observable through `detected_at`-keyed or time-missing dicts are not.
2. `adjust_risk_score` re-assigns `metadata["scenarios"]` and `metadata["floor_applied"]` **unconditionally**, so renaming their init keys leaves an invisible ghost key (correct key is re-added). `floor_score` / `tailgating` are only re-added inside branches → renaming their init keys yields a genuinely missing key on cold paths.
3. Existing tailgating tests assert loose bounds (`confidence > 0.5`, `>= result_2.confidence`) and one vacuous disjunction (`meta.get("tailgating") is not None or adjusted > 25`, :592) — the exact confidence/floor arithmetic is entirely unasserted.
4. `apply_hysteresis` tests only probe interior points (31/27, 28/32, 61/57, 86/82); every zone **edge** (buffer_low, boundary, buffer_high, buffer_high+1) and the previous_score-on-boundary case are unprobed.
5. `test_score_at_exact_boundary` (:492) runs the hysteresis pipeline but asserts only `adjusted == 29` — a value identical whether hysteresis runs or not. No test ever asserts `hysteresis_applied is True`.

## Cluster table (112 survivors, counts sum exactly)

Key format: `x_<function>__mutmut_<n>` (module prefix omitted).

| #   | Cluster (pattern @ function)                                                                                                                                                                                               | n   | Class      | Examples                                     | Kill rationale / note                                                                                                                                                                            |
| --- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --- | ---------- | -------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| C1  | metadata init key renames on unconditionally-reassigned keys (`"scenarios"`/`"floor_applied"` XX-cased/caps-cased; `"floor_applied": True` init)                                                                           | 5   | EQUIVALENT | x_adjust_risk_score\_\_4, \_\_6, \_\_8       | Correct key is re-added at :960/:964 before return; ghost key invisible to any lookup. Only full-dict equality would see it — not worth asserting.                                               |
| C2  | metadata init of **branch-conditionally**-reassigned keys: `"floor_score"`/`"tailgating"` renames; `"floor_score": 1`                                                                                                      | 5   | TEST-GAP   | x_adjust_risk_score\_\_9, \_\_11, \_\_12     | Cold path (`test_no_adjustment_for_normal_activity` :391) executes the init but never asserts `meta["floor_score"] == 0` or `"tailgating" in meta`; docstring promises both keys always present. |
| C3  | `classify_scenario` call drops its inputs (`detections=None` / arg removed, `reasoning=None` / arg removed)                                                                                                                | 4   | TEST-GAP   | x_adjust_risk_score\_\_19, \_\_22, \_\_23    | Tests pass detections+summary together (:449, "unauthorized" also in summary → survives `detections=None`) and never pass a reasoning-only or detections-only classification.                    |
| C4  | `metadata["floor_score"]` write corrupted (`= None`, key renamed, `get_scenario_floor_score(None)`)                                                                                                                        | 4   | TEST-GAP   | x_adjust_risk_score\_\_38, \_\_41            | Graffiti floor tests (:372) assert `adjusted >= 65` but never `meta["floor_score"] == 65`.                                                                                                       |
| C5  | tailgating metadata payload: dict replaced with `None` or all 5 inner keys renamed (`detected/confidence/description/persons_involved/time_gap_seconds`)                                                                   | 13  | TEST-GAP   | x_adjust_risk_score\_\_47, \_\_52, \_\_58    | Path executes in `test_rapid_entry_detection_escalation` (:578) but its assert is a disjunction satisfied by the score alone → payload wholly unasserted.                                        |
| C6  | tailgating escalation arithmetic/bound: `int(floor / conf)` ; `>=` for `>`                                                                                                                                                 | 2   | TEST-GAP   | x_adjust_risk_score\_\_63, \_\_64            | Escalation value never asserted (64 vs 46 undetected); no equality case (score already at effective floor → `floor_applied` must stay False).                                                    |
| C7  | `zone_type` not forwarded to `detect_tailgating` (`None` / arg dropped)                                                                                                                                                    | 2   | TEST-GAP   | x_adjust_risk_score\_\_44, \_\_46            | Pipeline test passes `zone_type="entry_point"` (:589) but never asserts the resulting confidence/floor boost is applied.                                                                         |
| C8  | tailgating-escalation `logger.info` message/`extra` mutations (msg→None, extra→None, extra-key renames)                                                                                                                    | 7   | LOW-VALUE  | x_adjust_risk_score\_\_65, \_\_66, \_\_69    | Observability text; file has zero caplog assertions and no log schema contract exists.                                                                                                           |
| C9  | `metadata["floor_applied"] = True` in escalation branch: →None/False, key renamed                                                                                                                                          | 4   | TEST-GAP   | x_adjust_risk_score\_\_74, \_\_77            | Detection-driven escalation never asserts `floor_applied is True` (only the _summary-keyword_ path does, :379).                                                                                  |
| C10 | hysteresis step guard `previous_score is not None` → `is None`                                                                                                                                                             | 1   | TEST-GAP   | x_adjust_risk_score\_\_79                    | See fact 5: no pipeline test asserts a hysteresis _change_ or flag-True.                                                                                                                         |
| C11 | hysteresis step trace: `pre_hysteresis = None`, `apply_hysteresis(_, None)`, `==` for `!=`                                                                                                                                 | 3   | TEST-GAP   | x_adjust_risk_score\_\_80, \_\_83, \_\_86    | Same missing pipeline assertion (adjusted==29 + `hysteresis_applied is True`/`is False` both directions).                                                                                        |
| C12 | final clamp `max(0, …)` → `max(1, …)`                                                                                                                                                                                      | 1   | TEST-GAP   | x_adjust_risk_score\_\_92                    | `test_score_bounds_enforced` (:422) only uses raw=150; raw=0 (legit zero-risk) never used.                                                                                                       |
| C13 | hysteresis buffer-zone width/bounds: `buffer_high ±1/±2`, `buffer_low <` → `<=`, upper `<` → `<=`/`<`                                                                                                                      | 4   | TEST-GAP   | x_apply_hysteresis\_\_6, \_\_8, \_\_9        | Zone edges 26, 33, 34 and downward-entry at 26 unprobed (fact 4).                                                                                                                                |
| C14 | hysteresis upward predicate: `and`→`or`; `previous_score <` boundary                                                                                                                                                       | 2   | TEST-GAP   | x_apply_hysteresis\_\_11, \_\_12             | `apply_hysteresis(28, 27)` (must stay 28) and previous exactly at boundary `(31, 29)`→29 unprobed.                                                                                               |
| C15 | hysteresis upward predicate `new_score >` → `>=`                                                                                                                                                                           | 1   | EQUIVALENT | x_apply_hysteresis\_\_13                     | When `new_score == boundary` both paths return `boundary` (fall-through vs `adjusted = boundary`) — provably identical output.                                                                   |
| C16 | hysteresis downward predicate: `previous_score >=`, `new_score <`                                                                                                                                                          | 2   | TEST-GAP   | x_apply_hysteresis\_\_17, \_\_18             | `(28, 29)` must be 28; `(29, 32)` must be 30 — previous-at-boundary unprobed.                                                                                                                    |
| C17 | hysteresis `logger.debug` messages → None                                                                                                                                                                                  | 2   | LOW-VALUE  | x_apply_hysteresis\_\_15, \_\_22             | Debug text, no caplog assertions anywhere.                                                                                                                                                       |
| C18 | person filter `or ""` → `or "XXXX"` sentinel default                                                                                                                                                                       | 1   | EQUIVALENT | x_detect_tailgating\_\_7                     | Both sides produce a non-`"person"` string when `object_type` is falsy — filter result identical.                                                                                                |
| C19 | entry-zone tuple member text mutated (`"door"`,`"gate"`,`"entrance"` XX/caps-cased)                                                                                                                                        | 6   | TEST-GAP   | x_detect_tailgating\_\_17, \_\_18, \_\_19    | `zone_type` is real domain data; only `"entry_point"` ever tested (:327, :589) → door/gate/entrance zones silently lose the +0.2 confidence boost.                                               |
| C20 | sort-key fallbacks broken, **observable** (`d.get(None,…)`, `…, None)`/single-arg → TypeError or order loss; `detected_at` key renamed; inner default 0→1 re-pairs a missing-time detection against low-valued timestamps) | 9   | TEST-GAP   | x_detect_tailgating\_\_29, \_\_30, \_\_33    | Dual timestamp-format support (docstring) untested: shuffled `detected_at` input + a dict missing both time keys (facts 1/3 of inputs) kill these; no test does.                                 |
| C21 | sort-key fallbacks broken, **behavior-invariant** (`d.get(None, 0)` inner, `"timestamp"` renamed to XX/CAPS)                                                                                                               | 3   | EQUIVALENT | x_detect_tailgating\_\_35, \_\_39, \_\_40    | Loop ignores sort order for any input where the fallback fires (all values 0 → order-independent); provably no output diff.                                                                      |
| C22 | 5.0 s window constant → 6.0 ; `time_gap <=` → `<`                                                                                                                                                                          | 2   | TEST-GAP   | x_detect_tailgating\_\_43, \_\_92            | Gap exactly 5.0 (must count) and 5.5 (must not) unprobed; existing gaps are 2/3/4/30 s.                                                                                                          |
| C23 | `float("inf")` → `float("INF")` init                                                                                                                                                                                       | 1   | EQUIVALENT | x_detect_tailgating\_\_49                    | Identical float.                                                                                                                                                                                 |
| C24 | gap-loop `.get("detected_at", 0)` default → None/removed/1                                                                                                                                                                 | 6   | TEST-GAP   | x_detect_tailgating\_\_57, \_\_64, \_\_67    | Mixed input (one detection has `detected_at`, one lacks it) → crash or wrong `time_gap_seconds`; never tested (fact 1).                                                                          |
| C25 | base-confidence formula: `0.5`→`1.5` term, `*0.15`→`/0.15`/`*1.15`, cap 0.9→1.9                                                                                                                                            | 4   | TEST-GAP   | x_detect_tailgating\_\_109, \_\_110, \_\_112 | Only loose `> 0.5` / monotonic `>=` asserts (:315, :366); exact values 0.65/0.8/0.9 and the 0.9 cap never asserted.                                                                              |
| C26 | entry-zone boost `+0.2`→`+1.2`, cap 0.95→1.95                                                                                                                                                                              | 2   | TEST-GAP   | x_detect_tailgating\_\_119, \_\_120          | `test_higher_confidence_at_entry_zone` compares two results instead of asserting 0.85/0.95.                                                                                                      |
| C27 | gap-discount thresholds/multipliers (`>3.0`→`>=`/`>4.0`, `>2.0`→`>=`/`>3.0`, `*0.9`→`/0.9`/`*1.9`)                                                                                                                         | 6   | TEST-GAP   | x_detect_tailgating\_\_121, \_\_123, \_\_124 | Discount boundaries at gap 2.0/2.5/3.0/3.5 untested — confidence curve interior never asserted.                                                                                                  |
| C28 | indicator `description` f-string text mutations (None/removed/`-1`/`+2` person count)                                                                                                                                      | 4   | LOW-VALUE  | x_detect_tailgating\_\_130, \_\_139, \_\_140 | Cosmetic human-readable string; count also carried in `persons_involved` (asserted). Nobody should pin the sentence.                                                                             |
| C29 | `time_gap_seconds` ternary → always `None` / kwarg dropped / `and False` / `==` flipped                                                                                                                                    | 4   | TEST-GAP   | x_detect_tailgating\_\_132, \_\_145          | `time_gap_seconds` is part of the indicator + pipeline payload and never asserted anywhere.                                                                                                      |
| C30 | `time_gap_seconds` ternary no-ops (`or True`, `float("INF")`)                                                                                                                                                              | 2   | EQUIVALENT | x_detect_tailgating\_\_144, \_\_148          | `min_time_gap` is finite whenever this line runs; both rewrites identical.                                                                                                                       |

**Totals:** 112 = adjust_risk_score 51 + detect_tailgating 50 + apply_hysteresis 11.
**By class:** TEST-GAP 21 clusters / 86 mutants · EQUIVALENT 7 clusters / 13 mutants · LOW-VALUE 3 clusters / 13 mutants (sum = 112).

## Drafted tests (kill the 6 highest-value clusters; 6 drafts → 21 TEST-GAP clusters)

**TDD procedure (one line):** each drafted test is written against the ORIGINAL semantics and must be run red against each named mutant (`uv run mutmut apply <key>` in the serial pytest lane after the mutation run releases the machine, or via WP4.4's runner) and green on the original — assert fails on mutant diff, passes on original.

Style follows `backend/tests/unit/services/test_scenario_classifier.py` (class-scoped methods, `-> None` annotations, docstrings; add `import pytest` to the import block). New class appended to the same file. `// UNVERIFIED - not yet run red/green`

```python
class TestWp44SurvivorGaps:
    """Kill-set for WP4.3 surviving mutants in hysteresis/tailgating/pipeline.

    Targets: apply_hysteresis buffer-edge and predicate operators,
    detect_tailgating timestamp handling + confidence curve, and the
    adjust_risk_score metadata/escalation contract (NEM-4522 semantics).
    """

    # --- Draft 1: confidence curve + zone boost + time_gap contract
    # Kills C25 (109-112), C26 (119-120), C27 (121-127), C29 (132/137/143/145)
    def test_tailgating_confidence_curve_exact(self) -> None:
        """Confidence is the exact documented curve, not merely > 0.5."""
        t = 1_000.0  # plain-float epoch; loop float()s the values

        def pair(gap: float) -> list[dict]:
            return [
                {"object_type": "person", "detected_at": t},
                {"object_type": "person", "detected_at": t + gap},
            ]

        # (gap, expected confidence) — base 0.5 + 0.15*n, then gap discounts:
        # >3.0 -> *0.8 ; elif >2.0 -> *0.9 ; boundaries at 2.0 and 3.0 exclusive.
        for gap, expected in [
            (1.5, 0.65),
            (2.0, 0.65),   # NOT discounted: 2.0 is not > 2.0
            (2.5, 0.585),  # * 0.9
            (3.0, 0.585),  # elif branch: 3.0 is not > 3.0
            (3.5, 0.52),   # * 0.8
        ]:
            result = detect_tailgating(pair(gap))
            assert result.confidence == pytest.approx(expected), f"gap={gap}"
            assert result.time_gap_seconds == pytest.approx(gap), f"gap={gap}"

        # base saturation cap 0.9 (4 persons -> 3 consecutive pairs -> 0.95 capped)
        crowd = [
            {"object_type": "person", "detected_at": t + i * 0.5} for i in range(4)
        ]
        assert detect_tailgating(crowd).confidence == pytest.approx(0.9)

        # entry-zone boost +0.2 and its own cap 0.95
        boosted = detect_tailgating(pair(2.0), zone_type="entry_point")
        assert boosted.confidence == pytest.approx(0.85)
        crowd_boosted = detect_tailgating(crowd, zone_type="entry_point")
        assert crowd_boosted.confidence == pytest.approx(0.95)

    # --- Draft 2: dual-timestamp handling + 5.0 s window boundary
    # Kills C20 (29/30/32/33/34/36/37/38), C24 (57/59/64/67/69/72), C22 (43/92)
    def test_tailgating_time_field_fallbacks(self) -> None:
        """Timestamp fallbacks and the 5.0 s window boundary are observable."""
        t = 1_000.0

        # Shuffled detected_at input: sorting must restore adjacency (t, t+1).
        shuffled = [
            {"object_type": "person", "detected_at": t + 9},
            {"object_type": "person", "detected_at": t},
            {"object_type": "person", "detected_at": t + 10},
        ]
        result = detect_tailgating(shuffled)
        assert result.detected is True
        assert result.persons_involved == 2
        assert result.time_gap_seconds == pytest.approx(1.0)

        # A detection missing BOTH time keys sorts as 0 (no TypeError) and
        # defaults to 0.0 in the gap loop.
        missing_time = [
            {"object_type": "person"},
            {"object_type": "person", "detected_at": 0.2},
            {"object_type": "person", "detected_at": 0.6},
        ]
        result = detect_tailgating(missing_time)
        assert result.detected is True
        assert result.time_gap_seconds == pytest.approx(0.2)

        # Present/absent mix: absent side must default to 0.0, never None/1.
        mixed = [
            {"object_type": "person", "detected_at": 0.4},
            {"object_type": "person"},
        ]
        result = detect_tailgating(mixed)
        assert result.time_gap_seconds == pytest.approx(0.4)

        # Window boundary: exactly 5.0 s counts, 5.5 s does not.
        exact = [
            {"object_type": "person", "detected_at": t},
            {"object_type": "person", "detected_at": t + 5.0},
        ]
        assert detect_tailgating(exact).detected is True
        outside = [
            {"object_type": "person", "detected_at": t},
            {"object_type": "person", "detected_at": t + 5.5},
        ]
        assert detect_tailgating(outside).detected is False

    # --- Draft 3: entry-zone alias set
    # Kills C19 (17-22)
    @pytest.mark.parametrize("zone_type", ["entry_point", "door", "gate", "entrance"])
    def test_entry_zone_aliases_all_boost(self, zone_type: str) -> None:
        """All four entry-zone aliases receive the +0.2 confidence boost."""
        t = 1_000.0
        detections = [
            {"object_type": "person", "detected_at": t},
            {"object_type": "person", "detected_at": t + 2.0},
        ]
        result = detect_tailgating(detections, zone_type=zone_type)
        assert result.confidence == pytest.approx(0.85)

    # --- Draft 4: tailgating pipeline metadata contract
    # Kills C5 (47-59), C6 (63-64), C7 (44-46), C9 (74-77)
    def test_adjust_risk_score_tailgating_metadata(self) -> None:
        """Detection-driven tailgating escalates with the exact contract payload."""
        t = 1_000.0
        detections = [
            {"object_type": "person", "detected_at": t},
            {"object_type": "person", "detected_at": t + 2.0},
        ]
        adjusted, meta = adjust_risk_score(
            raw_score=20,
            detections=detections,
            zone_type="entry_point",
        )
        # confidence 0.65 base + 0.2 zone boost = 0.85;
        # effective floor = int(55 * 0.85) = 46 (NOT int(55 / 0.85) = 64).
        assert adjusted == 46
        assert meta["floor_applied"] is True
        assert meta["tailgating"] == {
            "detected": True,
            "confidence": pytest.approx(0.85),
            "description": "2 persons detected entering in quick succession",
            "persons_involved": 2,
            "time_gap_seconds": 2.0,
        }

        # Score already AT the effective floor: no escalation, flag untouched.
        adjusted_eq, meta_eq = adjust_risk_score(
            raw_score=46,
            detections=detections,
            zone_type="entry_point",
        )
        assert adjusted_eq == 46
        assert meta_eq["floor_applied"] is False

    # --- Draft 5: cold-path metadata contract + per-source classification
    # Kills C2 (9-13), C3 (19/22/23/26), C4 (38-41), C10 (79), C11 (80/83/86),
    # C12 (92)
    def test_adjust_risk_score_metadata_contract(self) -> None:
        """Docstring metadata keys are always present with true values."""
        adjusted, meta = adjust_risk_score(
            raw_score=15,
            summary="Delivery driver dropping off package",
        )
        assert adjusted == 15
        assert meta["floor_applied"] is False
        assert meta["floor_score"] == 0          # kills ghost/1-init renames
        assert "tailgating" in meta and meta["tailgating"] is None

        # Zero-risk input must clamp to 0, not 1.
        zeroed, _ = adjust_risk_score(raw_score=0)
        assert zeroed == 0

        # Scenario keywords reachable from reasoning ONLY, and from
        # detections ONLY — each source is an independent input.
        _, meta_reason = adjust_risk_score(
            raw_score=20,
            reasoning="Person tagging the garage door with spray paint",
        )
        assert "graffiti" in meta_reason["scenarios"]
        assert meta_reason["floor_score"] == 65  # kills None/None-list/renames

        _, meta_detect = adjust_risk_score(
            raw_score=20,
            detections=[{"object_type": "vehicle", "description": "spray paint"}],
        )
        assert "graffiti" in meta_detect["scenarios"]

        # Hysteresis ENABLED: crossing within buffer holds at boundary.
        adjusted_h, meta_h = adjust_risk_score(
            raw_score=31,
            previous_score=27,
            apply_hysteresis_adjustment=True,
        )
        assert adjusted_h == 29
        assert meta_h["hysteresis_applied"] is True

        # Hysteresis enabled but no boundary crossed: flag stays False
        # (kills pre_hysteresis=None and the ==/!= inversion).
        adjusted_n, meta_n = adjust_risk_score(
            raw_score=31,
            previous_score=50,
            apply_hysteresis_adjustment=True,
        )
        assert adjusted_n == 31
        assert meta_n["hysteresis_applied"] is False

    # --- Draft 6: hysteresis buffer-zone edges + predicates
    # Kills C13 (6/8/9/10), C14 (11/12), C16 (17/18)
    def test_apply_hysteresis_buffer_zone_edges(self) -> None:
        """Buffer zone is exactly (boundary-3, boundary+4) with edge semantics."""
        # upper edge of LOW/MEDIUM zone (29 + 3 + 1): 32 and 33 hold, 34 passes
        assert apply_hysteresis(32, 27) == 29
        assert apply_hysteresis(33, 27) == 29
        assert apply_hysteresis(34, 27) == 34
        # lower edge exclusive: 26 is a genuine crossing, not buffer
        assert apply_hysteresis(26, 32) == 26
        # in-buffer but NOT crossing (prev same side) must pass through
        assert apply_hysteresis(28, 27) == 28
        # previous exactly AT boundary still counts as "below"/"at" side
        assert apply_hysteresis(31, 29) == 29
        assert apply_hysteresis(28, 29) == 28
        # downward crossing of a score sitting exactly on boundary holds above
        assert apply_hysteresis(29, 32) == 30
```

### Draft coverage accounting

| Draft                      | Clusters killed           | Mutants |
| -------------------------- | ------------------------- | ------- |
| D1 confidence curve        | C25, C26, C27, C29        | 16      |
| D2 time fallbacks + window | C20, C24, C22             | 16      |
| D3 zone aliases            | C19                       | 6       |
| D4 tailgating metadata     | C5, C6, C7, C9            | 21      |
| D5 metadata contract       | C2, C3, C4, C10, C11, C12 | 18      |
| D6 hysteresis edges        | C13, C14, C16             | 8       |

Not drafted (lower value or covered by the same asserts above): C8/C17/C28 (LOW-VALUE log/description text — recommend leave-surviving, ~13 mutants, document as accepted), EQUIVALENT clusters (14 mutants — recommend baseline exclusion list rather than tests).

## Notes / risks

- D4's `pytest.approx` inside a dict equality works (each value compared via `==`); if that reads awkwardly in review, de-sugar to per-key asserts.
- D2 asserts CURRENT original behavior for missing-time detections (default 0.0, sorts first). If that is judged a latent bug (detection at epoch 0 vs now → gap ≈ 1.7e9), the test still correctly pins present semantics; a follow-up product decision would change both code and test together.
- `test_score_at_exact_boundary` (:492) and `test_rapid_entry_detection_escalation` (:592, the `or`-disjunction) should be tightened when these drafts land — they are the "test exists but asserts too weakly" instances.
