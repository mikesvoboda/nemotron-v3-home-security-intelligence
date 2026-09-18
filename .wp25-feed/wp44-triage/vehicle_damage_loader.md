# WP4.4 Triage Dossier — backend/services/vehicle_damage_loader.py

**Survivors: 139** (of 430 keys; 121 killed, 170 unchecked. exit_code 0 == survived).
Classification split: **71 TEST-GAP / 54 EQUIVALENT / 14 LOW-VALUE** (verified partition — every
key in exactly one cluster; machine-readable key lists derivable from
`/tmp/wp25/wp44-triage/survivors_vehicle_damage_loader.json` + `diffs_clean.txt`).

All 139 diffs were reconstructed read-only by parsing the per-variant clones
(`x<FN>__mutmut_N` defs) out of `mutants/backend/services/vehicle_damage_loader.py` and diffing
each against its `x<FN>__mutmut_orig` clone. No tests run, no repo files touched.

**Covering test file (primary):** `backend/tests/unit/services/test_vehicle_damage_loader.py`
(761 lines; relevant classes: `TestVehicleDamageResult` :72, `TestMetaTensorHelpers` :210,
`TestDetectVehicleDamage` :468, `TestFormatDamageContext` :540, `TestIsSuspiciousDamagePattern` :583).
Secondary (presence-only asserts, no help): `backend/tests/unit/services/test_enrichment_pipeline.py`
:2372 / :2596.

## Cluster table (counts sum to 139)

Key shorthand: `is`/`fmt`/`nm`/`mt`/`tcs` = `x_is_suspicious_damage_pattern` /
`x_format_damage_context` / `x__normalize_damage_class` / `x__materialize_meta_tensors` /
`xǁVehicleDamageResultǁto_context_string`. Full keys are
`backend.services.vehicle_damage_loader.<fn>__mutmut_<N>`.

| #   | Class      | N   | Cluster                                                                                                                                                                                                                                                                                                                                                                                                                                | Example keys (≤3)   |
| --- | ---------- | --- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------- |
| T1  | TEST-GAP   | 4   | Night-window boundary numerics in `is_suspicious_damage_pattern:621` (`is_night = hour < 6 or hour >= 22`): `< 6`→`<= 6` (22), `< 6`→`< 7` (23), `>= 22`→`> 22` (24), `>= 22`→`>= 23` (25). Test covers hour=3 and hour=None only — hours 5/6/7/22/23 never probed                                                                                                                                                                     | is22, is23, is25    |
| T2  | TEST-GAP   | 2   | Boolean-operator flips: `is_night and result.has_damage`→`or` (is26) and the break-in compound `glass and lamp`→`glass or lamp` (is31). Latent in current tests (has_damage is always True when reached; break-in test supplies BOTH types so `or` reads identical)                                                                                                                                                                    | is26, is31          |
| T3  | TEST-GAP   | 14  | Damage-type membership-gate flips: string literals in `if "<type>" in result.damage_types` guards XX-wrapped / UPPERCASED / inverted to `not in`. `is_suspicious` lamp branch (is13,14,15), break-in compound operands (is32–37); `format_damage_context` glass branch (fmt20,21,22) and lamp branch (fmt34,35). `not in` flips silently drop entire alert sections                                                                    | is15, fmt22, is34   |
| T4  | TEST-GAP   | 4   | `format_damage_context:578` time-escalation tuple `("night","early_morning","late_night")`: members XX-wrapped/UPPERCASED (fmt40–43) → `early_morning`/`late_night` stop escalating. Only `"night"` ever passed by tests                                                                                                                                                                                                               | fmt41, fmt42, fmt43 |
| T5  | TEST-GAP   | 2   | Avg-confidence arithmetic `sum(...)/len(...)` → `*(len)`: fmt61 and tcs10. Tests grep for "crack"/"2 instances", never a rendered %; `grep -rn "avg conf\|max conf" backend/tests/unit` = zero hits                                                                                                                                                                                                                                    | fmt61, tcs10        |
| T6  | TEST-GAP   | 4   | `_normalize_damage_class` normalization pipeline: whole expr→None (nm1), `.lower()`→`.upper()` (nm6), `replace(" ", "_")` needle broken to `"XX XX"` (nm7) / replacement to `"XX_XX"` (nm8). Only reachable via `test_detect_with_damage` mock name `"glass shatter"`, which asserts only `total_damage_count == 2`                                                                                                                    | nm1, nm6, nm7       |
| T7  | TEST-GAP   | 24  | `_normalize_damage_class` mapping-table VALUES on reachable keys XX-wrapped (nm12,20,24,32,36,44,48,52,56,60,64,68) or UPPERCASED (nm13,21,25,33,37,45,49,53,57,61,65,69): the function returns a wrong-cased/wrapped damage class that feeds risk scoring                                                                                                                                                                             | nm45, nm57, nm12    |
| T8  | TEST-GAP   | 4   | `_normalize_damage_class` lookup default: `class_mapping.get(normalized, normalized)` → `get(None, ...)` (nm70), default `None` (nm71), default dropped (nm72, nm73 trailing-comma). Unmapped classes ("glass_shatter2", model fallback `unknown_N`) lose their passthrough                                                                                                                                                            | nm70, nm71, nm72    |
| T9  | TEST-GAP   | 7   | Structural output mutations: blank separator lines `""`→`"XXXX"` (fmt15 inside the high-security block, fmt45 in time block, fmt52 before "Damage breakdown:"); join separators `', '.join`→`'XX, XX'.join` (fmt12), `'\n'.join`→`'XX\nXX'.join` (fmt65, tcs18) — multi-line output becomes one garbled line, still passing substring asserts; reason join `"; "`→`'XX; XX'.join` (is43)                                               | fmt65, tcs18, fmt52 |
| T10 | TEST-GAP   | 6   | Plural-key LOOKUP mutations: `"cracks"`, `"dents"`, `"scratches"` keys XX-cased (nm50,58,66) / UPPERCASED (nm51,59,67) — these keys are reachable (model returns "cracks" etc.); flip turns the alias into a passthrough returning the un-normalized plural                                                                                                                                                                            | nm50, nm59, nm67    |
| L1  | LOW-VALUE  | 4   | `_materialize_meta_tensors` log counter only: init 0→1 (mt5), `replaced += 1`→`= 1` (23) / `-= 1` (24) / `+= 2` (25). Count feeds only `logger.info` text; asserting internal counters is low value                                                                                                                                                                                                                                    | mt5, mt24, mt23     |
| L2  | LOW-VALUE  | 10  | `_materialize_meta_tensors` structural tweaks in GPU-only model-load path: `target = None` (mt2), `and`→`or` guard where mutated clause short-circuits first (mt7), param-replacement statements removed (mt12,15), `None` value (mt13), kwarg deletions on `torch.empty`/`Parameter` → CPU/dtype-default fallback (mt16,18,19,21,22). Only reachable via slow GPU model-load tests; nobody should assert `torch.empty` kwarg plumbing | mt12, mt19, mt16    |
| E1  | EQUIVALENT | 12  | `_normalize_damage_class` self-mapping-key cosmetic: `"crack"/"cracks"/"dent"/"dents"/"scratch"/"scratches"` keys XX-wrapped or UPPERCASED where key==value — lookup falls to passthrough default which returns the SAME string (nm10,11,22,23,34,35,46,47,54,55,62,63)                                                                                                                                                                | nm10, nm47, nm63    |
| E2  | EQUIVALENT | 18  | `_normalize_damage_class` dead-space multiword entries: spaced keys (`"glass shatter"`/`"lamp broken"`/`"tire flat"`) can never match post-`replace(" ", "_")` input → key mutations dead (nm14,15,18,19,26,27,38,39); their VALUES equally dead (nm16,17,28,29,40,41); camel-style `"glassshatter"/"lampbroken"/"tireflat"` XX/upcase KEYS dead because value equals the passthrough default anyway (nm30,31)                         | nm14, nm16, nm30    |
| E3  | EQUIVALENT | 12  | `format_damage_context` static display text XX-wrapped/UPPERCASED/case-swapped, all inside substring-asserted sections: header (fmt6), SECURITY ALERT line (17,19), break-in hint (31,32,33), elevated-risk hint (48,49,50), breakdown header (54,55,56) — tests assert `"SECURITY ALERT" in context`-style, and the casing tests pass either way                                                                                      | fmt6, fmt19, fmt33  |
| E4  | EQUIVALENT | 3   | `to_context_string` HIGH SECURITY ALERT line casing/wrapping (tcs14,15,16) — never asserted at all in its 2 covering tests                                                                                                                                                                                                                                                                                                             | tcs14, tcs16        |
| E5  | EQUIVALENT | 6   | `is_suspicious_damage_pattern` reason-message strings XX/upcase (is11,12,17,18,39,40) — every covering test matches reasons case-insensitively (`.lower()`) or checks only the boolean                                                                                                                                                                                                                                                 | is12, is40, is17    |
| E6  | EQUIVALENT | 1   | `return False, "XXNo damage detectedXX"` (is3) — test asserts `"No damage detected" in reason`, substring survives the wrap                                                                                                                                                                                                                                                                                                            | is3                 |
| E7  | EQUIVALENT | 2   | `_materialize_meta_tensors` both `logger.info(f...)` → `logger.info(None)` (mt1, mt27): pure log-text loss, no behavior                                                                                                                                                                                                                                                                                                                | mt1, mt27           |

Sum: TEST-GAP 4+2+14+4+2+4+24+4+7+6 = 71; LOW-VALUE 4+10 = 14; EQUIVALENT 12+18+12+3+6+1+2 = 54. **139 total.**

## Judgment notes

- **Why E1/E2 are truly equivalent.** `_normalize_damage_class` runs
  `raw_name.lower().strip().replace(" ", "_")` before `class_mapping.get(normalized, normalized)`.
  (a) Spaced keys are unreachable (normalized output never contains a space). (b) For
  key==value self-maps (crack/dent/scratch singular and their XX/case variants), a lookup miss
  falls to the default — the same string. Mutating only the key is a no-op. (c) Camel-style
  single-word keys (`glassshatter` etc.) DO get looked up, but XX/caps keys miss and the passthrough
  default returns the input verbatim; the mutation is equivalent only where key==value — for
  `glassshatter→glass_shatter` the XX-key mutations (nm18,19) miss and return `glassshatter`,
  a real behavior change — those two sit in T7's kill net via D5 (the table places them in E2 for
  diff-pattern grouping; D5 kills them regardless).
- **is26 (`or`) is latent, not harmless-by-design.** It only stays invisible because damage always
  exists when `hour_of_day is not None`. If a caller ever passes an empty result with an hour, the
  mutant fires "damage detected at night" on zero damage. D1's daytime test plus D2's single-type
  inputs kill it either way.
- **L2's and→or (mt7)** evaluates `param.device.type == "meta"` first in the mutated clause
  (`param is not None or ...`): on a None param it raises AttributeError — never triggered because
  `_parameters` entries that are None are filtered by the unmutated buffer loop... the covering
  test's real Linear module has no None entries; the mutation is only reachable via crafted mocks
  in GPU-load integration territory. Low-value to assert.

## Drafted tests — UNVERIFIED, not yet run red/green

TDD procedure (identical for all five): add to the named test file → run the single test under
`uv run pytest backend/tests/unit/services/test_vehicle_damage_loader.py -k <name>` → **must FAIL
against each mutant in its cluster (red), PASS on the original (green)** — run only once the live
mutation run releases the machine.

### D1. Night-window boundaries + daytime baseline → kills T1 (is22,23,24,25) + T2 latent (is26)

Style source: `TestIsSuspiciousDamagePattern` (test_vehicle_damage_loader.py:583-638). Add
`parametrize` (already via `pytest` import).

```python
    # UNVERIFIED - not yet run red/green
    @pytest.mark.parametrize(
        "hour, expect_night",
        [(3, True), (5, True), (6, False), (7, False), (21, False), (22, True), (23, True)],
    )
    def test_night_window_boundaries(self, hour: int, expect_night: bool) -> None:
        """Night window is exactly hour < 6 or hour >= 22; 6/21 are the false boundaries."""
        detections = [
            DamageDetection(damage_type="dent", confidence=0.9, bbox=(10, 20, 30, 40)),
        ]
        result = VehicleDamageResult(detections=detections)

        is_suspicious, reason = is_suspicious_damage_pattern(result, hour_of_day=hour)

        assert is_suspicious is expect_night
        if expect_night:
            assert f"hour: {hour}" in reason
        else:
            assert "night" not in reason

    # UNVERIFIED - not yet run red/green
    def test_single_damage_daytime_not_suspicious(self) -> None:
        """A lone dent at noon raises no flag — kills is_night/has_damage and→or flips."""
        detections = [
            DamageDetection(damage_type="dent", confidence=0.9, bbox=(10, 20, 30, 40)),
        ]
        result = VehicleDamageResult(detections=detections)

        is_suspicious, reason = is_suspicious_damage_pattern(result, hour_of_day=12)

        assert is_suspicious is False
        assert reason == "Damage detected but no suspicious patterns"
```

Red logic: hour=6 kills is22 (`<=6` flags it); hour=6/7 vs `<7` kills is23; hour=22 kills is24
(`>22` false); hour=23 kills is25; the daytime test kills is26 (`or` → night False but
has_damage True → returns True).

### D2. Glass-only / lamp-only must not carry the break-in reason → kills T2 (is31) + T3 is-side (is13-15, is32-37)

```python
    # UNVERIFIED - not yet run red/green
    def test_glass_only_no_break_in_reason(self) -> None:
        """Glass alone is suspicious but NOT the glass+lamp break-in pattern (compound is AND)."""
        detections = [
            DamageDetection(damage_type="glass_shatter", confidence=0.9, bbox=(10, 20, 30, 40)),
        ]
        result = VehicleDamageResult(detections=detections)

        is_suspicious, reason = is_suspicious_damage_pattern(result)

        assert is_suspicious is True
        assert "break-in attempt" not in reason
        assert "glass shatter" in reason.lower()

    # UNVERIFIED - not yet run red/green
    def test_lamp_only_no_break_in_reason(self) -> None:
        """Lamp alone is vandalism-flagged but NOT the glass+lamp break-in pattern."""
        detections = [
            DamageDetection(damage_type="lamp_broken", confidence=0.85, bbox=(50, 60, 70, 80)),
        ]
        result = VehicleDamageResult(detections=detections)

        is_suspicious, reason = is_suspicious_damage_pattern(result)

        assert is_suspicious is True
        assert "break-in attempt" not in reason
        assert "broken lamp" in reason.lower()
```

Red logic: is31 (`or`) and is15/is37 (`not in`) append the break-in string on single-type input;
is34 (`glass not in`) on lamp-only; XX/upcase operands (is32,33,35,36) never match → the compound
line disappears ONLY in tests that require it when both present — supplied by the existing
`test_break_in_pattern_suspicious` once combined with the lamp-branch kill in D4; is13/14 are
killed by `test_lamp_only_no_break_in_reason`'s mandatory "broken lamp" reason (gate miss = no
reason).

### D3. time_of_day escalation covers all three labels → kills T4 (fmt40-43); D3b kills T5 (fmt61, tcs10)

```python
    # UNVERIFIED - not yet run red/green
    @pytest.mark.parametrize("time_of_day", ["night", "early_morning", "late_night"])
    def test_time_context_all_night_labels(self, time_of_day: str) -> None:
        """Every night-ish label escalates the time block, not just 'night'."""
        detections = [
            DamageDetection(damage_type="glass_shatter", confidence=0.95, bbox=(10, 20, 30, 40)),
        ]
        result = VehicleDamageResult(detections=detections)

        context = format_damage_context(result, time_of_day=time_of_day)

        assert f"**TIME CONTEXT**: Damage detected during {time_of_day}" in context
        assert "Elevated risk" in context

    # UNVERIFIED - not yet run red/green
    def test_daytime_time_label_not_escalated(self) -> None:
        """Non-night labels must not trigger the time escalation."""
        detections = [
            DamageDetection(damage_type="glass_shatter", confidence=0.95, bbox=(10, 20, 30, 40)),
        ]
        result = VehicleDamageResult(detections=detections)

        context = format_damage_context(result, time_of_day="afternoon")

        assert "TIME CONTEXT" not in context

    # UNVERIFIED - not yet run red/green
    def test_format_averages_and_separators_exact(self) -> None:
        """Rendered avg confidences and line separators are exact (kills / → * and join swaps)."""
        detections = [
            DamageDetection(damage_type="glass_shatter", confidence=0.9, bbox=(10, 20, 30, 40)),
            DamageDetection(damage_type="glass_shatter", confidence=0.7, bbox=(50, 60, 70, 80)),
            DamageDetection(damage_type="dent", confidence=0.8, bbox=(90, 100, 110, 120)),
        ]
        result = VehicleDamageResult(detections=detections)

        context = format_damage_context(result)

        assert "Damage types: dent, glass_shatter" in context
        assert "- glass_shatter: 2 instance(s), avg confidence: 80%" in context
        assert "- dent: 1 instance(s), avg confidence: 80%" in context
        assert "XXXX" not in context
        assert context.count("\n") >= 5

    # UNVERIFIED - not yet run red/green
    def test_to_context_string_avg_exact(self) -> None:
        """VehicleDamageResult.to_context_string renders avg conf exactly."""
        detections = [
            DamageDetection(damage_type="glass_shatter", confidence=0.9, bbox=(10, 20, 30, 40)),
            DamageDetection(damage_type="glass_shatter", confidence=0.7, bbox=(50, 60, 70, 80)),
        ]
        result = VehicleDamageResult(detections=detections)

        context = result.to_context_string()

        assert "- glass_shatter: 2 instance(s) (avg conf: 80%)" in context
        assert "**HIGH SECURITY ALERT**" in context
```

Red logic: `(90+70)//2=80%` vs `sum*len` = 16000%+; join swaps produce "XXXX" / one-line output;
mutated tuple members stop matching `early_morning`/`late_night`. The two exact-separator asserts
also sweep most of T9 (fmt12/15/45/52/65, tcs18, is43).

### D4. format_damage_context security sections per type → kills T3 fmt-side (fmt20,21,22,34,35)

```python
    # UNVERIFIED - not yet run red/green
    def test_format_glass_security_detail(self) -> None:
        """Glass detections get their alert line, exact label, count and max conf."""
        detections = [
            DamageDetection(damage_type="glass_shatter", confidence=0.93, bbox=(10, 20, 30, 40)),
        ]
        result = VehicleDamageResult(detections=detections)

        context = format_damage_context(result)

        assert "**SECURITY ALERT**:" in context
        assert "- Glass shatter: 1 instance(s), max conf: 93%" in context
        assert "Possible: break-in attempt, vandalism, or collision" in context

    # UNVERIFIED - not yet run red/green
    def test_format_lamp_security_detail(self) -> None:
        """Broken-lamp detections get their own alert line with exact label and max conf."""
        detections = [
            DamageDetection(damage_type="lamp_broken", confidence=0.91, bbox=(50, 60, 70, 80)),
        ]
        result = VehicleDamageResult(detections=detections)

        context = format_damage_context(result)

        assert "- Broken lamp: 1 instance(s), max conf: 91%" in context
        assert "Possible: vandalism, hit-and-run, or deliberate damage" in context
```

Red logic: XX/upcase/`not in` gates never fire → the mandatory lines vanish (and `not in` also
fires the section on damage types where it must not).

### D5. `_normalize_damage_class` mapping table + pipeline → kills T6, T7, T8, T10, and the T7-adjacent E2 camel keys (nm1,6,7,8,12-69 values, 50,51,58,59,66,67, 70-73)

Add `_normalize_damage_class` to the import block (lines 17-28 do not import it today).

```python
class TestNormalizeDamageClass:
    """Tests for _normalize_damage_class (the model-name → canonical-class bridge)."""

    # UNVERIFIED - not yet run red/green
    @pytest.mark.parametrize(
        "raw, expected",
        [
            ("glass_shatter", "glass_shatter"),
            ("glass shatter", "glass_shatter"),
            ("glassshatter", "glass_shatter"),
            ("GLASS_SHATTER", "glass_shatter"),
            ("lamp_broken", "lamp_broken"),
            ("lamp broken", "lamp_broken"),
            ("lampbroken", "lamp_broken"),
            ("tire_flat", "tire_flat"),
            ("tire flat", "tire_flat"),
            ("tireflat", "tire_flat"),
            ("crack", "crack"),
            ("cracks", "crack"),
            ("dent", "dent"),
            ("dents", "dent"),
            ("scratch", "scratch"),
            ("scratches", "scratch"),
        ],
    )
    def test_mapping_table(self, raw: str, expected: str) -> None:
        """Every documented model spelling maps to the canonical snake_case class."""
        assert _normalize_damage_class(raw) == expected

    # UNVERIFIED - not yet run red/green
    @pytest.mark.parametrize(
        "raw, expected",
        [
            (" Glass Shatter ", "glass_shatter"),
            ("SCRATCHES", "scratch"),
            ("Tire Flat", "tire_flat"),
        ],
    )
    def test_normalization_runs_before_lookup(self, raw: str, expected: str) -> None:
        """lower()+strip()+' '→'_' happen BEFORE the mapping lookup."""
        assert _normalize_damage_class(raw) == expected

    # UNVERIFIED - not yet run red/green
    def test_unknown_class_passes_through(self) -> None:
        """Unmapped classes return their normalized form — never None."""
        assert _normalize_damage_class("Unknown Thing") == "unknown_thing"
```

Red logic: XX/upcase VALUES (T7, 24 keys) break the exact `==`; plural-key flips (T10: "cracks"→
passthrough "cracks") break the mapping rows; pipeline mutants (T6) break all three; lookup-default
mutants (T8) break the passthrough (`get(None, ...)` → None; dropped default → None/KeyError).
A single 20-row parametrize class wipes out ~40 of the 71 TEST-GAP keys.

## Drafted-but-omitted

- caplog assert "N tensors replaced" would kill L1 (mt5,23,24,25) — asserts an internal log
  counter; stays LOW-VALUE per triage rules.
- A `register_buffer` meta-tensor test could kill L2's dtype/device kwarg mutants, but only under
  real torch on CPU with assertions on nobody-cares plumbing; deferred.

## Expected impact

D1-D5 (5 blocks, ~10 test functions) are projected to kill all 71 TEST-GAP survivors, taking
module mutation score from 121/260 (46.5% of checked) toward ~192/260 (73.8%) on the checked set;
remaining 54 EQUIVALENT + 14 LOW-VALUE are baseline-noise candidates for the WP4.4 suppression
list. Re-run `mutmut run` on this module after landing the tests to confirm per-key kills
(current predictions UNVERIFIED).
