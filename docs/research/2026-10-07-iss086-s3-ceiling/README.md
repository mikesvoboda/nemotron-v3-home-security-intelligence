# ISS-086 S3-ceiling re-derivation (2026-10-07, offline)

The re-derivation the ISS-086 acceptance asks for ("the ceiling re-derived from exact
rows, not rounded percentages"), run offline from committed data and the surviving eval
store — no GPU, no new replay. It converts the register's `[A]` evidence bullets to
re-derived numbers and settles which of the three acceptance experiments are still worth
running. The register entry is
[`docs/vss-integration/17-action-plan.md`](../../vss-integration/17-action-plan.md),
ISS-086, update 2026-10-07.

Reproduce:

```
python3 docs/research/2026-10-07-iss086-s3-ceiling/rederive_sweep.py    # git-tracked data only
AGENT_GPU_DIR=/path/to/gpu/out python3 docs/research/2026-10-07-iss086-s3-ceiling/rederive_shipped.py
```

| file                  | what it is                                                                                                                  |
| --------------------- | --------------------------------------------------------------------------------------------------------------------------- |
| `rederive_sweep.py`   | C1-C7 for the 15 sweep arms from `items.csv` + the taxonomy (needs nothing outside this repo)                               |
| `rederive_shipped.py` | the same measures against the shipped OD-29 path, store run `663da001…`, dev/holdout roster from the store's `splits` table |
| `results-sweep.txt`   | captured output of the part-1 script (2026-10-07)                                                                           |
| `results-shipped.txt` | captured output of the part-2 script (2026-10-07)                                                                           |

## 1. Every `[A]` number in the charter reproduces from committed rows

Charter claims vs the pre-rubric `control-q4km` arm (all 450 sets, refusals folded to
score 0 so the denominators are the charter's 241/209):

| claim                      | charter `[A]`                         | re-derived                                                                                             | verdict                                                                                     |
| -------------------------- | ------------------------------------- | ------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------- |
| score polarization         | 68% in {0,5,10}, 23% ≥75, 8% in 20-70 | 67.8%, 24.9%, 7.3%                                                                                     | reproduces                                                                                  |
| AUROC incident vs benign   | ~0.70                                 | 0.679                                                                                                  | reproduces (arms.csv records 0.677; +0.002 is the refusal fold — disclosed, not hidden)     |
| best single threshold      | 42% TPR at 5% FPR                     | 0.423                                                                                                  | reproduces                                                                                  |
| miss anatomy               | 148/153 confirmed, 127 ≤10            | 147 misses, 139 (95%) confirmed, 126 (86%) ≤10                                                         | reproduces in shape; the exact 153-denominator is arm A (`b7972`), already `[V]` 2026-10-04 |
| A-group recovery, 8B       | 2/64                                  | 0/64 on control; arm A's 2/64 already `[V]`                                                            | reproduces                                                                                  |
| A-group recovery, flagship | ~7/64                                 | best of 15 arms = 7/64 (`gemma4-26b-a4b`, also the best S3 at 57.3%)                                   | reproduced in kind (same number from the sweep's largest arm)                               |
| the ceiling                | ≤ 177/241 = 73.4%                     | 177/241 on control; across all 15 arms the ceiling never exceeds 184/241 = 76.3% even with B+C perfect | reproduces; the band is 73.4-76.3%                                                          |

## 2. OD-29 overtook two of the three hypothesis legs; the construct leg stands

The shipped path (arm-B rubric text at floor 60, store run `663da001…`) collapses the
symptoms the charter read as the mechanism: polarization drops to 23.3% in {0,5,10} with
41.1% of scores in the 20-70 band, AUROC rises to 0.778, TPR@5%FPR to 0.535 — matching
the 2026-10-03 arm-B `[V]` readings exactly (a method control for this script). But the
group that the hypothesis is about does not move: **A-group recovery stays 3/64**
(loitering 0/9, peering_into_windows 0/9, trying_car_doors 0/9, package_theft 1/19,
casing_with_phone 1/9, tailgating 1/9) and the ceiling stays 180/241 = 74.7%.
Polarization was a symptom; the unrecoverable quarter is the construct.

## 3. The twin premise splits into two regimes, and the rubric fixed only one

Twin-pair AUROC on the shipped arm, over the 18 zone-sharing incident/benign pairs plus
the charter's named `neighbor_passing` pair (19 total; n = 8-29 per side) is bimodal with
a wide gap: **7 pairs at or above 0.705, 12 at or below 0.584, nothing in between.** The
split is not random — it is which benign the incident is shown against:

- **Rankable twins** (the ≥0.705 half): `trying_car_doors` vs `wildlife` 0.889,
  `peering_into_windows` vs `pet_activity` 0.875, `casing_with_phone` vs `wildlife` 0.815,
  `tailgating` vs `resident_arrival` 0.733, vs `delivery_driver` 0.728, `package_theft` vs
  `resident_arrival` 0.713, vs `delivery_driver` 0.705. The model separates the A-scenario
  from a benign that merely stands, walks, or does its generic job.
- **True twins** (the ≤0.584 half, matched appearance cue): `casing_with_phone` vs
  `flashlight_neighbor` 0.192, `trying_car_doors` vs `flashlight_neighbor` 0.245,
  `loitering` vs `winter_face_covering` 0.264, `loitering` vs `neighbor_passing` 0.333,
  `casing_with_phone` vs `hooded_jogger` 0.343, `trying_car_doors` vs `hooded_jogger`
  0.416, `peering_into_windows` vs `landscaper_machete` 0.460, `loitering` vs
  `resident_arrival` 0.483, `peering_into_windows` vs `yard_maintenance` 0.506,
  `package_theft` vs `winter_face_covering` 0.543, `loitering` vs `wildlife` 0.574,
  `tailgating` vs `winter_face_covering` 0.584.

Comparing the control arm (`b11376`, pre-rubric) to the shipped arm on the same pairs
shows the rubric did its work entirely on the rankable half and nothing on the true-twin
half. The driveway pairs flipped from deeply inverted to harvestable — `trying_car_doors`
vs `wildlife` 0.142→0.889, `casing_with_phone` vs `wildlife` 0.154→0.815 — and the
charter's own named pair `package_theft` vs `delivery_driver` improved 0.605→0.705. But
the two _true_ twins the charter named got **worse**: `loitering` vs `neighbor_passing`
0.506→0.333 and `loitering` vs `winter_face_covering` 0.577→0.264. (The charter's two
named pairs are doc 20 §2's `delivery_driver` and `neighbor_passing`; `neighbor_passing`
shares no zone with `loitering`, so it appears only via the explicit footer both scripts
print.)

So "about 26% of incidents look like their benign twin" holds twin-by-twin but not
uniformly: the blindness is appearance-cue-specific (a face covering, a maintenance
motion, a flashlight at a window), which is what makes relabelling — an OD-2 option —
scenario-selectable rather than all-or-nothing. The rankable-half improvement is what
raised the corpus-wide AUROC (§2); it did not move A-group recovery past 3/64, because
ranking above one generic benign is not the same test as crossing an item's absolute
floor.

## 4. Acceptance status: E1 shipped, E3 redundant, E2 is the only open premise

- **E1 (rubric arm)** ran 2026-10-03 and its arm-B text is the shipped text under OD-29 —
  done, at development-arm status as the register says.
- **E3 (prompt-by-size 2×2)** is redundant without spending the 32B GPU cell: its
  shipped-prompt × 32B cell already ran in the sweep (`qwen3vl-32b-q4km`: S3 39.4% vs the
  8B's 39.0%, A-group 1/64), and §2 shows the rubric cell cannot move a
  construct-bounded ceiling — the missing 4th cell varies only size, and size moved
  nothing across 12 arms (ceilings 73.4-76.3%).
- **E2 (logprob arm)** is the only acceptance item that could still add information, and
  even it starts disfavored: the handoff's off-the-capture reading (arm A 0.717, arm B
  0.771 vs the integer scores' 0.703/0.778, no gain at 5% FPR) is `[A]` but the only
  untried lever. Owner's call under OD-2.

## 5. The holdout is A-heavy (sharpens the ISS-016 caveat)

The frozen holdout's six scenarios include three A-scenarios (`casing_with_phone`,
`peering_into_windows`, `tailgating`): 27/64 = **42.2% of holdout incidents are A-group**
against 20.9% on dev (corpus-wide 26.6%). That composition gap, not just sample size,
explains part of the 47.5% dev to 32.8% holdout drop in the OD-29 dogfood report, and it
is the concrete instance of the unstratified-draw caveat ISS-016's closure note carries.

## Limits

- Part 1's control arm ran on `b11376`; the charter's arm-A figures came from `b7972`, and
  the 250/450 item agreement between builds (ISS-087) is why the control's miss counts are
  147/241-hits-94 rather than 153/88. Shapes reproduce; exact denominators are
  build-specific.
- Part 2 depends on the eval store surviving on the GPU host
  (`$AGENT_GPU_DIR/out/sbroot/...`); part 1 does not, and that asymmetry is why the
  re-derivation is split the way it is.
- Twin-pair AUROCs are small-n (9-29 per side) and interval-free; the bimodality is in the
  gaps between pairs, not in any one pair's precision.
