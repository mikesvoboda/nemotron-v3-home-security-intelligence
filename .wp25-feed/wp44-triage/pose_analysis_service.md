# WP4.4 Triage Dossier — backend/services/pose_analysis_service.py

- Snapshot taken 2026-09-17 from `mutants/backend/services/pose_analysis_service.py.meta`
  (465 keys: 223 killed, **105 survived**, 137 still unchecked — live run may add more;
  clusters below cover the 105 survivors only).
- All diffs read via `uv run mutmut show <key>` (worked, ~0.6 s/call; no manual-diff fallback needed).
- Only covering test file for every function in this module (per `mutants/mutmut-stats.json`
  `tests_by_mangled_function_name`): **`backend/tests/unit/services/test_pose_analysis_service.py`** (104 test entries). No other file imports the module.

## How the survivors die / survive

Verdicts were computed mechanically, not by eyeballing: each survivor's real function source
was re-exec'd with its single-line substitution applied and compared to the original across a
fixture sweep (`/tmp/wp25/wp44-triage/sweep.py`, `killmatrix.json`), then every drafted test
case below was simulated red/green against original + all 105 mutants
(`/tmp/wp25/wp44-triage/redgreen.py`). Result: **GREEN on original (all cases), RED on 95/105
mutants**; the 10 that stay live are exactly the EQUIVALENT (9) + LOW-VALUE (1) clusters —
none of them change output for any input (they are `+=`→`=` mutations on the first accumulation
step where the accumulator is provably 0, a clamp boundary made unreachable by a guard, and a
0.5 px init bias).

## Why the existing tests leave these alive (root causes, 4 total)

1. **Every lying-down / hands-raised fixture supplies BOTH left and right keypoints**
   (`test_pose_analysis_service.py:840-881`, `:884-937`). The code deliberately accepts a single
   side (`or`, mean-over-whichever-present); no test ever runs the one-sided path, so retrieval
   mutants (wrong name → silent `None`) and `or`→`and` guard flips pass unnoticed.
2. **No fixture makes the two sides asymmetric** (`right_shoulder.y != left_shoulder.y` with the
   outcome depending on the mean). `+=`→`=` / `+=2` / `max(count,2)` accumulator mutants all keep
   symmetric fixtures at the same answer.
3. **Threshold tests sit far from boundaries** (lying fixture hs=350 vs vs=5, i.e. 70× the 1.5
   factor; hands raised at y=50 vs margin line 140; fighting ratio 3.0 dead-center of 2.0–4.0).
   Operator flips (`>`→`>=`, `*1.5`→`/1.5`→`*2.5`, band ends, `and`→`or`) need on-boundary fixtures.
4. **Posture-string tests use `"lying"` but never the normalized `"lying_down"`**
   (`test_pose_analysis_service.py:1014-1020`), and `analyze_pose` tests never assert alerts
   come from the posture argument (`:1056-1123`).

## Cluster table (sums to 105)

| # | Cluster (function @ module lines) | Count | Class | Example keys | Killers (drafted test) |
|---|-----------------------------------|-------|-------|--------------|------------------------|
| C1 | `detect_lying_down` keypoint retrieval → None/garbage name (`None`, `None` arg, `"XX…XX"`, `"UPPER"`) @225-230 | 16 | TEST-GAP | `x_detect_lying_down__mutmut_1`, `…_13`, `…_20` | T1 |
| C2 | `detect_lying_down` "need one shoulder AND one ankle" guard flipped to need both @233 | 2 | TEST-GAP | `x_detect_lying_down__mutmut_31`, `…_33` | T1 |
| C3 | `detect_lying_down` shoulder-mean accumulators (`+=`→`=`/`-=`/`+=2`, count variants, `max(count,1)`→`max(count,2)`, `/=`→`=`/`*`) @236-249 | 18 | TEST-GAP | `…_44`, `…_49`, `…_61` | T2 |
| C4 | `detect_lying_down` ankle-mean accumulators (same families) @251-263 | 19 | TEST-GAP | `…_78`, `…_83`, `…_96` | T2 |
| C5 | `detect_lying_down` first-step `+=`→`=` where accumulator is provably 0 (no-op) @241,243,255,257 etc. | 6 | EQUIVALENT | `…_41`, `…_75` | — (keep surviving; equivalent) |
| C6 | `detect_lying_down` span computation + branch thresholds: `abs(a-b)`→`abs(a+b)`, `vertical_span > 0`→`>= 0`/`> 1`, `hs > vs*1.5`→`>=`/`/1.5`/`*2.5` @266-275 | 6 | TEST-GAP | `…_105`, `…_109`, `…_111` | T3 |
| C7 | `detect_lying_down` `shoulder_x = 0.0`→`1.0` init bias (0.5 px with single shoulder) @236 | 1 | LOW-VALUE | `…_36` | — (sub-pixel, not worth asserting) |
| C8 | `detect_hands_raised` shoulder retrieval → None/garbage @303-304 | 8 | TEST-GAP | `x_detect_hands_raised__mutmut_19`, `…_26`, `…_31` | T4 |
| C9 | `detect_hands_raised` "need at least one shoulder" guard `and`→`or` / operand flips @306 | 3 | TEST-GAP | `…_33`, `…_34`, `…_35` | T4 |
| C10 | `detect_hands_raised` shoulder-mean accumulators + `max(count,2)` @310-318 | 6 | TEST-GAP | `…_37`, `…_39`, `…_45` | T4 |
| C11 | `detect_hands_raised` first-step `+=`→`=` no-ops @313,316 | 2 | EQUIVALENT | `…_40`, `…_42` | — |
| C12 | `detect_hands_raised` 10-px margin + `<`→`<=` / `shoulder_y - margin`→`+ margin` @323-325 | 5 | TEST-GAP | `…_58`, `…_60`, `…_61` | T5 |
| C13 | `detect_fighting_stance` hip-pair / ankle-pair guards `or`→`and` (drop-one-side accepted) @352,359 | 2 | TEST-GAP | `x_detect_fighting_stance__mutmut_15`, `…_33` | T6 |
| C14 | `detect_fighting_stance` hip-width clamp `< 1`→`< 2` (real change: width-1.5px hips) @364 | 1 | TEST-GAP | `…_41` | T6 |
| C15 | `detect_fighting_stance` clamp `< 1`→`<= 1` (unreachable boundary) @364 | 1 | EQUIVALENT | `…_40` | — |
| C16 | `detect_fighting_stance` `ankle_y_spread = abs(a-b)`→`abs(a+b)` @369 | 1 | TEST-GAP | `…_47` | T6 |
| C17 | `detect_fighting_stance` wide-band `2.0 < r < 4.0` flips: `<=4.0`→`2.0<=`, `<4.0`→`<=4.0`, upper `4.0`→`5.0` @380 | 3 | TEST-GAP | `…_52`, `…_53`, `…_54` | T6 |
| C18 | `detect_fighting_stance` asymmetry `>`→`>=` @384 | 1 | TEST-GAP | `…_56` | T6 |
| C19 | `detect_fighting_stance` final `is_wide_stance and is_asymmetric`→`or` @387 | 1 | TEST-GAP | `…_59` | T6 |
| C20 | `detect_security_alerts` posture tuple `("lying","lying_down")` string clobbers @412 | 2 | TEST-GAP | `x_detect_security_alerts__mutmut_15`, `…_16` | T7 |
| C21 | `analyze_pose` passes `posture=None` into `detect_security_alerts` @486 | 1 | TEST-GAP | `x_analyze_pose__mutmut_12` | T7 |

TEST-GAP: 95 mutants (16 clusters) · EQUIVALENT: 9 (C5, C11, C15) · LOW-VALUE: 1 (C7). Sum = 105.

## Drafted tests (6)

All in `backend/tests/unit/services/test_pose_analysis_service.py`, added to the existing
classes (no new imports needed — module already imports `detect_*`, `analyze_pose`,
`Keypoint`, `PoseResult` at lines 18-39). Every case below was simulated: **assert fails on
the cluster's mutant diff, passes on original** (TDD procedure). Marked UNVERIFIED because the
live mutation run owns this machine and no pytest may execute yet.

### T1 — kills C1 + C2 (18 mutants)

```python
    def test_single_side_keypoints_sufficient_for_lying(self) -> None:
        """Left-only, right-only and cross-side shoulder+ankle pairs still detect lying down.

        UNVERIFIED - not yet run red/green (simulated via /tmp/wp25/wp44-triage/redgreen.py).
        """
        left_only = {
            "left_shoulder": Keypoint(x=100, y=100, confidence=0.9, name="left_shoulder"),
            "left_ankle": Keypoint(x=300, y=100, confidence=0.9, name="left_ankle"),
        }
        right_only = {
            "right_shoulder": Keypoint(x=100, y=100, confidence=0.9, name="right_shoulder"),
            "right_ankle": Keypoint(x=300, y=100, confidence=0.9, name="right_ankle"),
        }
        cross_side = {
            "right_shoulder": Keypoint(x=100, y=100, confidence=0.9, name="right_shoulder"),
            "left_ankle": Keypoint(x=300, y=100, confidence=0.9, name="left_ankle"),
        }
        right_only_upright = {
            "right_shoulder": Keypoint(x=100, y=100, confidence=0.9, name="right_shoulder"),
            "right_ankle": Keypoint(x=105, y=500, confidence=0.9, name="right_ankle"),
        }

        # one of each side is enough (retrieval + guard mutants die here)
        assert detect_lying_down(left_only) is True
        assert detect_lying_down(right_only) is True
        assert detect_lying_down(cross_side) is True
        # and one-sided upright body is still not lying
        assert detect_lying_down(right_only_upright) is False
```

### T2 — kills C3 + C4 (37 mutants)

```python
    def test_lying_down_uses_mean_of_each_side(self) -> None:
        """Spans use the MEAN of the detected side, not sum/difference/last-write/divisor-2.

        UNVERIFIED - not yet run red/green.
        """
        # uneven shoulders (y 100/200) + level ankles at x 300/400:
        # mean sy=150 -> vs=50, mean sx=150 -> hs=200 -> 200 > 75 -> lying
        uneven_shoulders = {
            "left_shoulder": Keypoint(x=100, y=100, confidence=0.9, name="left_shoulder"),
            "right_shoulder": Keypoint(x=200, y=200, confidence=0.9, name="right_shoulder"),
            "left_ankle": Keypoint(x=300, y=100, confidence=0.9, name="left_ankle"),
            "right_ankle": Keypoint(x=400, y=100, confidence=0.9, name="right_ankle"),
        }
        # same but ankles below: mean-based vertical body -> not lying
        uneven_upright = {
            "left_shoulder": Keypoint(x=100, y=100, confidence=0.9, name="left_shoulder"),
            "right_shoulder": Keypoint(x=200, y=200, confidence=0.9, name="right_shoulder"),
            "left_ankle": Keypoint(x=105, y=500, confidence=0.9, name="left_ankle"),
            "right_ankle": Keypoint(x=205, y=500, confidence=0.9, name="right_ankle"),
        }
        # right shoulder y dropped (+=->= mutant) flips sy 150->200 and answer True->False
        right_y_matters = {
            "left_shoulder": Keypoint(x=100, y=100, confidence=0.9, name="left_shoulder"),
            "right_shoulder": Keypoint(x=200, y=200, confidence=0.9, name="right_shoulder"),
            "left_ankle": Keypoint(x=250, y=100, confidence=0.9, name="left_ankle"),
            "right_ankle": Keypoint(x=290, y=100, confidence=0.9, name="right_ankle"),
        }
        # right ankle x matters: mean ax=370 -> hs=220 < 1.5*vs(150)=225 False;
        # RA-only ax=390 -> hs=240 > 225 True
        right_x_matters = {
            "left_shoulder": Keypoint(x=100, y=100, confidence=0.9, name="left_shoulder"),
            "right_shoulder": Keypoint(x=200, y=100, confidence=0.9, name="right_shoulder"),
            "left_ankle": Keypoint(x=350, y=100, confidence=0.9, name="left_ankle"),
            "right_ankle": Keypoint(x=390, y=400, confidence=0.9, name="right_ankle"),
        }
        # right ankle y matters: mean ay=200 -> vs=100 -> hs=220>150 True;
        # RA-only ay=300 -> vs=200 -> hs=220 < 300 False
        right_y_matters_ankle = {
            "left_shoulder": Keypoint(x=100, y=100, confidence=0.9, name="left_shoulder"),
            "right_shoulder": Keypoint(x=200, y=100, confidence=0.9, name="right_shoulder"),
            "left_ankle": Keypoint(x=350, y=100, confidence=0.9, name="left_ankle"),
            "right_ankle": Keypoint(x=390, y=300, confidence=0.9, name="right_ankle"),
        }
        # max(count,1)->max(count,2) divisors: single shoulder halves sx/sy
        single_shoulder_x = {
            "left_shoulder": Keypoint(x=100, y=100, confidence=0.9, name="left_shoulder"),
            "left_ankle": Keypoint(x=140, y=130, confidence=0.9, name="left_ankle"),
        }  # sx=100: hs=40 < 45 -> False; divisor-2: sx=50 -> hs=90 -> True
        single_shoulder_y = {
            "left_shoulder": Keypoint(x=100, y=100, confidence=0.9, name="left_shoulder"),
            "left_ankle": Keypoint(x=140, y=40, confidence=0.9, name="left_ankle"),
        }  # sy=100 -> vs=60 -> False; divisor-2 sy=50 -> vs=10 -> hs=40>15 True
        single_ankle_y = {
            "left_shoulder": Keypoint(x=100, y=100, confidence=0.9, name="left_shoulder"),
            "left_ankle": Keypoint(x=140, y=190, confidence=0.9, name="left_ankle"),
        }  # ay=190 -> vs=90 -> False; divisor-2 ay=95 -> vs=5 -> hs=40>7.5 True

        assert detect_lying_down(uneven_shoulders) is True
        assert detect_lying_down(uneven_upright) is False
        assert detect_lying_down(right_y_matters) is True
        assert detect_lying_down(right_x_matters) is False
        assert detect_lying_down(right_y_matters_ankle) is True
        assert detect_lying_down(single_shoulder_x) is False
        assert detect_lying_down(single_shoulder_y) is False
        assert detect_lying_down(single_ankle_y) is False
```

### T3 — kills C6 (6 mutants)

```python
    def test_lying_down_span_branches_and_ratio_boundary(self) -> None:
        """vs>0 uses the 1.5x ratio (exactly-1.5 is NOT lying); vs==0 falls back to hs>50.

        UNVERIFIED - not yet run red/green.
        """
        # hs=50 exactly, vs=0 -> fallback branch: 50 > 50 is False
        zero_vertical = {
            "left_shoulder": Keypoint(x=100, y=100, confidence=0.9, name="left_shoulder"),
            "right_shoulder": Keypoint(x=200, y=100, confidence=0.9, name="right_shoulder"),
            "left_ankle": Keypoint(x=250, y=100, confidence=0.9, name="left_ankle"),
            "right_ankle": Keypoint(x=150, y=100, confidence=0.9, name="right_ankle"),
        }
        # hs=75, vs=50 -> ratio exactly 1.5 -> strict > -> False (kills >=, /1.5, *2.5, hs->100)
        ratio_exactly_1_5 = {
            "left_shoulder": Keypoint(x=100, y=100, confidence=0.9, name="left_shoulder"),
            "right_shoulder": Keypoint(x=200, y=100, confidence=0.9, name="right_shoulder"),
            "left_ankle": Keypoint(x=215, y=140, confidence=0.9, name="left_ankle"),
            "right_ankle": Keypoint(x=235, y=160, confidence=0.9, name="right_ankle"),
        }
        # hs=100, vs=50 -> 2.0x: above 1.5 (True) but below 2.5 (kills *2.5)
        ratio_2x = {
            "left_shoulder": Keypoint(x=100, y=100, confidence=0.9, name="left_shoulder"),
            "right_shoulder": Keypoint(x=200, y=100, confidence=0.9, name="right_shoulder"),
            "left_ankle": Keypoint(x=240, y=140, confidence=0.9, name="left_ankle"),
            "right_ankle": Keypoint(x=260, y=160, confidence=0.9, name="right_ankle"),
        }
        # hs=30.5, vs=0.5 -> ratio branch True; vs>1 mutant would take fallback (30.5>50 False)
        small_vertical = {
            "left_shoulder": Keypoint(x=100, y=100, confidence=0.9, name="left_shoulder"),
            "right_shoulder": Keypoint(x=200, y=100, confidence=0.9, name="right_shoulder"),
            "left_ankle": Keypoint(x=180, y=100, confidence=0.9, name="left_ankle"),
            "right_ankle": Keypoint(x=181, y=101, confidence=0.9, name="right_ankle"),
        }

        assert detect_lying_down(zero_vertical) is False
        assert detect_lying_down(ratio_exactly_1_5) is False
        assert detect_lying_down(ratio_2x) is True
        assert detect_lying_down(small_vertical) is True
```

### T4 — kills C8 + C9 + C10 (17 mutants)

```python
    def test_hands_raised_accepts_single_shoulder_and_uses_mean(self) -> None:
        """Either shoulder alone defines the line; both shoulders average; no shoulder -> False.

        UNVERIFIED - not yet run red/green.
        """
        left_shoulder_only = {
            "left_shoulder": Keypoint(x=100, y=150, confidence=0.9, name="left_shoulder"),
            "left_wrist": Keypoint(x=80, y=50, confidence=0.9, name="left_wrist"),
            "right_wrist": Keypoint(x=220, y=50, confidence=0.9, name="right_wrist"),
        }
        right_shoulder_only = {
            "right_shoulder": Keypoint(x=200, y=150, confidence=0.9, name="right_shoulder"),
            "left_wrist": Keypoint(x=80, y=50, confidence=0.9, name="left_wrist"),
            "right_wrist": Keypoint(x=220, y=50, confidence=0.9, name="right_wrist"),
        }
        no_shoulder = {
            "left_wrist": Keypoint(x=80, y=50, confidence=0.9, name="left_wrist"),
            "right_wrist": Keypoint(x=220, y=50, confidence=0.9, name="right_wrist"),
        }
        # uneven shoulders y=100/200 -> mean 150 -> wrists at 120 are above 140: True
        # last-write/first-write mutants use 200 or 100 and flip the answer
        uneven_mean_true = {
            "left_shoulder": Keypoint(x=100, y=100, confidence=0.9, name="left_shoulder"),
            "right_shoulder": Keypoint(x=200, y=200, confidence=0.9, name="right_shoulder"),
            "left_wrist": Keypoint(x=80, y=120, confidence=0.9, name="left_wrist"),
            "right_wrist": Keypoint(x=220, y=120, confidence=0.9, name="right_wrist"),
        }
        # same shape, wrists at 145: mean line 150-10=140 -> 145 not < 140 -> False
        # first-shoulder-only mutants use y=100 -> 145 < 90 false ... divisor-2 uses 75 -> False too
        uneven_mean_false = {
            "left_shoulder": Keypoint(x=100, y=100, confidence=0.9, name="left_shoulder"),
            "right_shoulder": Keypoint(x=200, y=200, confidence=0.9, name="right_shoulder"),
            "left_wrist": Keypoint(x=80, y=145, confidence=0.9, name="left_wrist"),
            "right_wrist": Keypoint(x=220, y=145, confidence=0.9, name="right_wrist"),
        }
        # divisor-2 on shoulder_y: single shoulder gives sy=75 instead of 150
        single_shoulder_mid = {
            "left_shoulder": Keypoint(x=100, y=150, confidence=0.9, name="left_shoulder"),
            "left_wrist": Keypoint(x=80, y=120, confidence=0.9, name="left_wrist"),
            "right_wrist": Keypoint(x=220, y=120, confidence=0.9, name="right_wrist"),
        }  # sy=150 -> 120 < 140 True; divisor-2 sy=75 -> 120 < 65 False

        assert detect_hands_raised(left_shoulder_only) is True
        assert detect_hands_raised(right_shoulder_only) is True
        assert detect_hands_raised(no_shoulder) is False
        assert detect_hands_raised(uneven_mean_true) is True
        assert detect_hands_raised(uneven_mean_false) is False
        assert detect_hands_raised(single_shoulder_mid) is True
```

### T5 — kills C12 (5 mutants)

```python
    def test_hands_raised_requires_ten_pixel_margin(self) -> None:
        """At exactly 10 px above the shoulder line the strict < margin means NOT raised.

        UNVERIFIED - not yet run red/green.
        """
        exactly_at_margin = {
            "left_shoulder": Keypoint(x=100, y=150, confidence=0.9, name="left_shoulder"),
            "right_shoulder": Keypoint(x=200, y=150, confidence=0.9, name="right_shoulder"),
            "left_wrist": Keypoint(x=80, y=140, confidence=0.9, name="left_wrist"),
            "right_wrist": Keypoint(x=220, y=140, confidence=0.9, name="right_wrist"),
        }
        # one wrist exactly at margin, other clearly up: AND still rejects (kills per-side <=)
        left_at_margin = {
            "left_shoulder": Keypoint(x=100, y=150, confidence=0.9, name="left_shoulder"),
            "right_shoulder": Keypoint(x=200, y=150, confidence=0.9, name="right_shoulder"),
            "left_wrist": Keypoint(x=80, y=140, confidence=0.9, name="left_wrist"),
            "right_wrist": Keypoint(x=220, y=100, confidence=0.9, name="right_wrist"),
        }
        right_at_margin = {
            "left_shoulder": Keypoint(x=100, y=150, confidence=0.9, name="left_shoulder"),
            "right_shoulder": Keypoint(x=200, y=150, confidence=0.9, name="right_shoulder"),
            "left_wrist": Keypoint(x=80, y=100, confidence=0.9, name="left_wrist"),
            "right_wrist": Keypoint(x=220, y=140, confidence=0.9, name="right_wrist"),
        }
        # 1 px below the margin line on one side: kills margin=11, -margin->+margin, <=
        left_raised_right_1px_short = {
            "left_shoulder": Keypoint(x=100, y=150, confidence=0.9, name="left_shoulder"),
            "right_shoulder": Keypoint(x=200, y=150, confidence=0.9, name="right_shoulder"),
            "left_wrist": Keypoint(x=80, y=139, confidence=0.9, name="left_wrist"),
            "right_wrist": Keypoint(x=220, y=141, confidence=0.9, name="right_wrist"),
        }
        # both 11 px up -> True only for margin==10 (kills margin=11)
        beyond_margin = {
            "left_shoulder": Keypoint(x=100, y=150, confidence=0.9, name="left_shoulder"),
            "right_shoulder": Keypoint(x=200, y=150, confidence=0.9, name="right_shoulder"),
            "left_wrist": Keypoint(x=80, y=139, confidence=0.9, name="left_wrist"),
            "right_wrist": Keypoint(x=220, y=139, confidence=0.9, name="right_wrist"),
        }

        assert detect_hands_raised(exactly_at_margin) is False
        assert detect_hands_raised(left_at_margin) is False
        assert detect_hands_raised(right_at_margin) is False
        assert detect_hands_raised(left_raised_right_1px_short) is False
        assert detect_hands_raised(beyond_margin) is True
```

### T6 — kills C13 + C14 + C16 + C17 + C18 + C19 (9 mutants)

```python
    def test_fighting_stance_guards_and_boundary_thresholds(self) -> None:
        """Both hips AND both ankles required; open band (2.0, 4.0); strict asymmetry.

        UNVERIFIED - not yet run red/green.
        """
        # guard flips: only one hip / only one ankle present
        one_hip = {
            "left_hip": Keypoint(x=100, y=150, confidence=0.9, name="left_hip"),
            "left_ankle": Keypoint(x=50, y=380, confidence=0.9, name="left_ankle"),
            "right_ankle": Keypoint(x=200, y=330, confidence=0.9, name="right_ankle"),
        }
        one_ankle = {
            "left_hip": Keypoint(x=100, y=150, confidence=0.9, name="left_hip"),
            "right_hip": Keypoint(x=150, y=150, confidence=0.9, name="right_hip"),
            "left_ankle": Keypoint(x=50, y=380, confidence=0.9, name="left_ankle"),
        }
        # ratio exactly 2.0 (open lower band) and exactly 4.0 (open upper band)
        ratio_2_0 = {
            "left_hip": Keypoint(x=100, y=150, confidence=0.9, name="left_hip"),
            "right_hip": Keypoint(x=150, y=150, confidence=0.9, name="right_hip"),
            "left_ankle": Keypoint(x=200, y=380, confidence=0.9, name="left_ankle"),
            "right_ankle": Keypoint(x=100, y=330, confidence=0.9, name="right_ankle"),
        }
        ratio_4_0 = {
            "left_hip": Keypoint(x=100, y=150, confidence=0.9, name="left_hip"),
            "right_hip": Keypoint(x=150, y=150, confidence=0.9, name="right_hip"),
            "left_ankle": Keypoint(x=300, y=380, confidence=0.9, name="left_ankle"),
            "right_ankle": Keypoint(x=100, y=330, confidence=0.9, name="right_ankle"),
        }
        ratio_4_5 = {  # kills upper-bound 4.0 -> 5.0
            "left_hip": Keypoint(x=100, y=150, confidence=0.9, name="left_hip"),
            "right_hip": Keypoint(x=150, y=150, confidence=0.9, name="right_hip"),
            "left_ankle": Keypoint(x=325, y=380, confidence=0.9, name="left_ankle"),
            "right_ankle": Keypoint(x=100, y=330, confidence=0.9, name="right_ankle"),
        }
        # asymmetry exactly at hip_width*0.5 (strict >) -> False
        exact_asym = {
            "left_hip": Keypoint(x=100, y=150, confidence=0.9, name="left_hip"),
            "right_hip": Keypoint(x=150, y=150, confidence=0.9, name="right_hip"),
            "left_ankle": Keypoint(x=50, y=380, confidence=0.9, name="left_ankle"),
            "right_ankle": Keypoint(x=200, y=355, confidence=0.9, name="right_ankle"),
        }
        # clamp <1 -> <2: hips 1.5 px apart. Original: 1.5 not < 1 -> no clamp -> ratio 3.5/1.5
        # = 2.33 (in band) but asym 0.6 > 1.5*0.5=0.75 fails -> False. Mutant: 1.5 < 2 ->
        # clamped to 1.0 -> ratio 3.5 (in band) AND asym 0.6 > 0.5 -> True.
        clamp_boundary = {
            "left_hip": Keypoint(x=100, y=150, confidence=0.9, name="left_hip"),
            "right_hip": Keypoint(x=101.5, y=150, confidence=0.9, name="right_hip"),
            "left_ankle": Keypoint(x=100, y=380, confidence=0.9, name="left_ankle"),
            "right_ankle": Keypoint(x=103.5, y=380.6, confidence=0.9, name="right_ankle"),
        }

        assert detect_fighting_stance(one_hip) is False
        assert detect_fighting_stance(one_ankle) is False
        assert detect_fighting_stance(ratio_2_0) is False
        assert detect_fighting_stance(ratio_4_0) is False
        assert detect_fighting_stance(ratio_4_5) is False
        assert detect_fighting_stance(exact_asym) is False
        assert detect_fighting_stance(clamp_boundary) is True
        # and a clear positive that stays True (kills `and`->`or` only with the negatives above)
        assert detect_fighting_stance({
            "left_hip": Keypoint(x=100, y=150, confidence=0.9, name="left_hip"),
            "right_hip": Keypoint(x=150, y=150, confidence=0.9, name="right_hip"),
            "left_ankle": Keypoint(x=50, y=380, confidence=0.9, name="left_ankle"),
            "right_ankle": Keypoint(x=200, y=330, confidence=0.9, name="right_ankle"),
        }) is True
```

(`ankle_y_spread` `-`->`+` mutant C16 dies on `exact_asym`/`ratio_*`/`clamp_boundary`:
summed y is huge and makes asymmetry trivially true where the original is False.)

### T7 — kills C20 + C21 (3 mutants)

```python
    def test_lying_down_alert_from_normalized_posture(self) -> None:
        """detect_security_alerts fires on the NORMALIZED posture 'lying_down', not just raw 'lying'."""
        keypoints: dict[str, Keypoint] = {}

        alerts = detect_security_alerts(keypoints, "lying_down")

        assert "lying_down" in alerts

    def test_analyze_pose_laying_posture_produces_lying_alert(self) -> None:
        """analyze_pose must forward the normalized posture so the posture-driven alert survives."""
        pose = PoseResult(keypoints={}, pose_class="lying", pose_confidence=0.5)

        result = analyze_pose(pose)

        assert result["posture"] == "lying_down"
        assert result["alerts"] == ["lying_down"]
```

## Simulation record (this machine, 2026-09-17)

- `sweep.py` fixture sweep vs originals: 65/105 mutants already behaviorally distinguishable —
  all 40 zero-kill cases are the equivalent/no-op families + threshold-boundary cases.
- `redgreen.py` (the 6 tests above, simulated): **GREEN on original; RED on 95/105**; live =
  C5 (6), C7 (1), C11 (2), C15 (1) — all EQUIVALENT/LOW-VALUE by analysis below.

## EQUIVALENT / LOW-VALUE detail (do not chase)

- **C5 / C11 (9)** — `shoulder_x += left.x` → `shoulder_x = left.x` (same for y/count, both lying-down
  accumulator pairs, and hands-raised shoulders): these mutate the FIRST executed accumulation
  step, where the accumulator is provably initialised to 0.0/0 immediately above the block —
  `0 + v == 0 = v` for every input, unconditionally. Verified: no distinguishing input found in
  an exhaustive fixture sweep; these 9 are the only retrieval-style survivors that are provable
  no-ops rather than merely untested.
- **C15 (1)** — `hip_width < 1` → `<= 1`: the only input in `[1-ε, 1]` window is `hip_width==1`
  exactly, where the clamp (`hip_width = 1.0`) rewrites 1.0 to 1.0 — self-cancelling; with
  `hip_width` in (1, …) both branches skip. Confirmed no distinguishing input in sweep.
- **C7 (1)** — `shoulder_x = 0.0` → `1.0` biases the single-shoulder mean by +0.5 px. Only
  distinguishable within 0.5 px of the ratio threshold; asserting a 0.5-px boundary is
  over-specification (LOW-VALUE), leave it.

## Coverage bookkeeping

- `mutants/mutmut-stats.json` maps every function of this module to 104 test nodes, all in
  `backend/tests/unit/services/test_pose_analysis_service.py` (class line refs in §"root causes").
- The drafted tests add ~7 test methods to classes `TestDetectLyingDownService` (file line 840),
  `TestDetectHandsRaisedService` (884), `TestDetectFightingStanceService` (940),
  `TestDetectSecurityAlertsService` (984), `TestAnalyzePoseService` (1056).
- When the run finishes, re-check meta: newly-checked mutants of the unchecked 137 will mostly
  follow these same clusters (e.g. `detect_crouching` survivors will mirror C3/C4/C6 patterns).
