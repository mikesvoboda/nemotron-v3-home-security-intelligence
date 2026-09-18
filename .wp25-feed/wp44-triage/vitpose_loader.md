# WP4.4 Triage Dossier — backend/services/vitpose_loader.py

**Survivors: 155** (of 624 checked mutants; exit_code 0). All survivors fall in the two
async entrypoints: `extract_pose_from_crop` (66) and `extract_poses_batch` (89).
No survivors in `load_vitpose_model`, `extract_keypoints_from_output`, `classify_pose`, or
`PoseResult.to_dict` (those were killed or untried).

Root cause common to nearly every survivor: **the success-path tests use an unconfigured
`MagicMock` as `processor`/`model`/`torch` and assert only `result.bbox`**
(`backend/tests/unit/services/test_vitpose_loader.py:747-831` crop, `:879-967` batch).
Any change to the mock's inputs or to the _filled_ PoseResult's keypoints/pose_class/
pose_confidence slips through silently — mock calls never raise, mock kwargs are never
inspected. The three structural fixes below (A1/A2/A3) kill ~125 of the 155.

## Covering test files

| File                                                                                                             | Line refs                                        | What it asserts                                |
| ---------------------------------------------------------------------------------------------------------------- | ------------------------------------------------ | ---------------------------------------------- |
| `backend/tests/unit/services/test_vitpose_loader.py`                                                             | 724, 747, 793 (crop); 845, 856, 879, 923 (batch) | bbox only on success; shape+bbox on exceptions |
| `backend/tests/unit/services/test_model_zoo.py`                                                                  | 2376, 2407, 2419                                 | same weak pattern                              |
| helpers reused by drafted tests: `numpy` + `post_process_pose_estimation` stub at test_vitpose_loader.py:778-782 |

## Cluster table (sums to 155)

| ID  | Count | Class      | Pattern                                                                                                  |
| --- | ----- | ---------- | -------------------------------------------------------------------------------------------------------- |
| C1  | 15    | TEST-GAP   | validation-guard conditions never fed invalid input                                                      |
| C2  | 33    | TEST-GAP   | success/fill-path PoseResult content (kp/pose_class/conf, classify_pose arg, min_conf kwarg, drop-kwarg) |
| C3  | 14    | TEST-GAP   | whole-call crash silently swallowed by except fallback; tests assert fallback shape only                 |
| C4  | 8     | TEST-GAP   | full-frame box construction (origin [0,0]→[1,0]/[0,1], null, boxes=None)                                 |
| C5  | 1     | TEST-GAP   | `result_idx < len(keypoints_list)` → `<=` (IndexError→fallback, same shape)                              |
| C6  | 3     | TEST-GAP   | `bbox=None` drop in results-init (incl. `or True` tautology in same line)                                |
| C7  | 1     | TEST-GAP   | no-valid-crops early-return `if not valid_crops` → `if valid_crops`                                      |
| C8  | 1     | TEST-GAP   | except-path `keypoints={}` → `None`                                                                      |
| C9  | 26    | LOW-VALUE  | processor/torch internals behind MagicMock (device, dataset_index, tensor args)                          |
| C10 | 16    | EQUIVALENT | log message text / exc_info / extra tweaks                                                               |
| C11 | 2     | EQUIVALENT | `min_confidence=0.3` kwarg removal == default                                                            |
| C12 | 6     | TEST-GAP   | bbox guard `i < len(bboxes)` tautologies + `<=` in init/except/fill blocks                               |
| C13 | 1     | EQUIVALENT | crop47 `or True` — except-path returns identical PoseResult values                                       |
| C14 | 14    | TEST-GAP   | processor-call contract kwargs (images/return_tensors dropped·None·"XXptXX"·"PT")                        |
| C15 | 14    | TEST-GAP   | extract_keypoints_from_output seam args (None-swap, kwarg drops, image_size/None)                        |

Class totals: TEST-GAP 110, LOW-VALUE 26, EQUIVALENT 19.

## Cluster detail

**C1 (15) — input-validation guards: TEST-GAP.** crop 1,2,3,4,5,6,7; batch 8,9,10,11,12,13,14,15.
`person_crop is None` flipped, `width<=0 or height<=0` → `and` / `<0` / `<=1`, `valid_* = None`,
`enumerate(None)`, `.append(None)`. No test ever passes `None` or a 0-width crop — the boundary
branches are never entered, so every operator tweak inside them survives. Kill: parametrized
None/0-dim tests asserting fallback shape + "model/processor untouched" (note: batch8, the
`crop is not None` flip, is _also_ killed by A2's happy-path content asserts via append(None)→
processor crash→fallback — it's slotted here because it mutates the filter guard).

**C2 (33) — success/fill-path PoseResult content: TEST-GAP.** crop 39,44,45,46,48,49,50,51,52,53,55,56,57;
batch 50,55,57,58,59,61,62,63,65,66,67,74,75,76,78,79,80,82,83,84. `keypoints=None`/dropped,
`pose_class=None`/`"XXunknownXX"`/`"UNKNOWN"`/dropped, `pose_confidence=None`/`1.0`/dropped,
`classify_pose(None)`, `keypoints_list[1]`, `and False`, min*conf `None`/`1.3`. Tests run these
lines (100% coverage) but assert **only bbox** — never that the mocked 0.9-confidence keypoints
made it into the result. Kill: A2 asserts `result.keypoints == expected` / non-empty /
`keypoints={}` on the degenerate fixture. (batch65/66 "XXunknownXX"/"UNKNOWN" are \_not* equivalent:
"unknown" is the documented pose contract, consumers compare against it; the init block only
survives on crops that classify unknown.)

**C3 (14) — whole-call crash swallowed: TEST-GAP.** crop 11,21,22,35; batch 5,6,7,20,30,31,46,56,71,72.
Whole-call → `None` where the mutation crashes mid-body (next(None), range(None), enumerate(None),
`results=None`) and the broad `except Exception` returns a valid-shaped fallback. Tests already
exercise the except path (`test_extract_*_exception`) but only assert the shape — they never prove
_which_ call crashed or that the happy path actually completed. Kill: A2's non-empty-keypoints
assert (a crashed body can't produce populated results); A1's untouched-mocks assert for C1.

**C4 (8) — full-frame box construction: TEST-GAP.** crop 8,9,10,13; batch 17,18,19,22.
`[[0,0,w,h]]` → `[[1,0,...]]`/`[[0,1,...]]` (crop9/10/batch18/19), `=None`, `boxes=None`. The box
origin is the top-down-pose contract (ViTPose maps keypoints relative to the box). Mock processor
accepts anything. Kill: A4 spy-assert.

**C5 (1) — batch73: TEST-GAP.** `if result_idx < len(keypoints_list)` → `<=`: with a
short keypoints*list this IndexError is swallowed → identical empty fallback. Kill: A3.
**C6 (3) — batch60,64,68: TEST-GAP.** `bbox=None` / kwarg-drop / `and False` in the results-init:
invalid-crop slots lose their bboxes (fallback contract broken). Kill: A3.
**C7 (1) — batch16: TEST-GAP.** `if not valid_crops` → `if valid_crops`: all-valid batches take the
early-return empty fallback — A1/A2 catch it (keypoints populated in orig, empty in mutant).
All-invalid batches survive (same output) — inherent.
**C8 (1) — batch99: TEST-GAP.** except-path `keypoints={}`→`None`: the \_only* surviving fallback
field mutation because the existing except tests DO assert `keypoints == {}` — but only for
crop/batch where `parameters` raises; batch99 is in the outer except whose existing test
(test_extract_poses_batch_exception) does NOT assert keypoints. Fix: add `pose_result.keypoints == {}`
to that loop (line 872-875) — one-line strengthening, no new test needed.

**C9 (26) — processor/torch internals behind MagicMock: LOW-VALUE.** crop 20,23-33; batch 29,32-44.
device=None, `.to(None)`, `dataset_index=torch.tensor([1])`/dropped, `torch.zeros(batch_size…)`,
dtype=None etc. Real changes, but under the mock harness they are invisible _and_ unobservable
without reimplementing torch semantics; asserting `processor(**kwargs) was called_with exact`
would be over-specification (brittle refactor-coupling). The one behaviorally-meaningful member
(`dataset_index [0]→[1]` = wrong MoE expert, crop29/batch34) belongs in a _contract_ test with a
fake that validates args — recommend A4-lite assert instead of per-arg tests; leave as LOW-VALUE
for scoring purposes.

**C10 (16) — log text/kwarg tweaks: EQUIVALENT.** crop 59-66; batch 89,90,91,92,94,95,96,97,98
(95 = exc_info drop). Message casing/XX-padding, `exc_info=None/False`, `extra` key renames.
Nobody asserts log payloads.
**C11 (2) — crop43/batch54: EQUIVALENT.** removing `min_confidence=0.3` = the signature default.
**C12 (6) — batch69,70,87,88,111,112: TEST-GAP (low).** `or True` tautology == orig where len==N;
`i <= len` only differs when `len(bboxes) > len(person_crops)` (short-bboxes caller). A1 kills the
`or True` set (short-bboxes crop=None → `bboxes[0]` IndexError); the `<=` set needs a test with
`len(bboxes) > len(crops)` — fold into A1 fixture (pass 3 bboxes / 2 crops) or accept survivors.
**C13 (1) — crop47: EQUIVALENT.** `or True` forces the `keypoints_list[0]` branch; a crash then
returns PoseResult(∅,unknown,0,bbox) — value-identical to the original's else branch.
**C14 (14) — processor contract kwargs: TEST-GAP.** crop 12,14,15,16,17,18,19; batch 21,23,24,25,26,27,28.
images=None/dropped, return_tensors=None/dropped/"XXptXX"/"PT". A REAL processor would raise or
mis-format, but the test mock swallows it — the contract (images=crop, boxes=[...], pt tensors) is
exactly the documented processor API and deserves an assert (A4). Cheap, no brittleness beyond
kwarg rename.
**C15 (14) — EKF seam args: TEST-GAP.** crop 34,36,37,38,40,41,42; batch 45,47,48,49,51,52,53.
`image_size=(h,w)`→None, outputs/processor=None, positional drops, image_sizes=None. Silently
degrades keypoint mapping (wrong h/w → wrong scale) or triggers swallowed except → empty kp;
A2's content assert + A4 seam spy kill. (crop35/batch46 whole-call→None are C3; they crash → fallback,
caught by A1 untouched-mocks / A2 content.)

## Drafted tests (append to backend/tests/unit/services/test_vitpose_loader.py)

// UNVERIFIED - not yet run red/green

```python
# Shared fixtures/helpers ------------------------------------------------------
import sys
from unittest.mock import MagicMock, call

import numpy as np
import pytest

from backend.services.vitpose_loader import (
    KEYPOINT_NAMES,
    PoseResult,
    extract_pose_from_crop,
    extract_poses_batch,
)


def _standing_post_process(*_args, **_kwargs):
    """post_process_pose_estimation stub: one person, all 17 keypoints @0.9.

    Geometry is a canonical STANDING pose (shoulder 50 < hip 100 < knee 150 <
    ankle 200, feet together) -> classify_pose == ("standing", 0.8).
    Coordinates match the crop size so image-size mixups stay invisible here;
    that concern is covered by the seam spy (A4).
    """
    kp = np.array(
        [
            [112.0, 50.0],   # nose
            [108.0, 45.0],   # left_eye
            [116.0, 45.0],   # right_eye
            [104.0, 42.0],   # left_ear
            [120.0, 42.0],   # right_ear
            [90.0, 80.0],    # left_shoulder
            [134.0, 80.0],   # right_shoulder
            [80.0, 120.0],   # left_elbow
            [144.0, 120.0],  # right_elbow
            [75.0, 160.0],   # left_wrist
            [149.0, 160.0],  # right_wrist
            [95.0, 150.0],   # left_hip
            [129.0, 150.0],  # right_hip
            [92.0, 180.0],   # left_knee
            [132.0, 180.0],  # right_knee
            [90.0, 210.0],   # left_ankle
            [134.0, 210.0],  # right_ankle
        ]
    )
    scores = np.array([0.9] * 17)
    return [[{"keypoints": kp, "scores": scores}]]


@pytest.fixture
def vitpose_mocks(monkeypatch):
    """Mocked torch + model + processor whose calls are observable."""
    mock_torch = MagicMock()
    ctx = MagicMock()
    ctx.__enter__ = MagicMock(return_value=None)
    ctx.__exit__ = MagicMock(return_value=None)
    mock_torch.inference_mode.return_value = ctx
    monkeypatch.setitem(sys.modules, "torch", mock_torch)

    device = MagicMock()
    param = MagicMock()
    param.device = device
    model = MagicMock()
    model.parameters.return_value = iter([param])
    processor = MagicMock()
    processor.post_process_pose_estimation.side_effect = _standing_post_process
    return model, processor, mock_torch
```

```python
# A1: invalid-input guards (kills C1, C3 untouched-mocks, C12 `or True`) --------
@pytest.mark.parametrize("bad_crop", [None, "zero-width", "zero-height"])
@pytest.mark.asyncio
async def test_extract_pose_from_crop_rejects_invalid_crops(bad_crop, monkeypatch):
    """None / zero-dimension crops must short-circuit WITHOUT touching model or processor."""
    from PIL import Image

    crop = None
    if bad_crop == "zero-width":
        crop = Image.new("RGB", (0, 224))
    elif bad_crop == "zero-height":
        crop = Image.new("RGB", (224, 0))

    mock_model = MagicMock()
    mock_processor = MagicMock()

    result = await extract_pose_from_crop(mock_model, mock_processor, crop, bbox=[0, 0, 10, 10])

    assert result.keypoints == {}
    assert result.pose_class == "unknown"
    assert result.pose_confidence == 0.0
    assert result.bbox == [0, 0, 10, 10]
    # Short-circuit means nothing downstream ran (kills guards that fall through).
    mock_processor.assert_not_called()
    mock_model.assert_not_called()


@pytest.mark.asyncio
async def test_extract_poses_batch_rejects_invalid_crops_without_calling_processor():
    """None / zero-dim crops are filtered; if nothing valid remains, early-return fallback
    with per-slot bboxes and NO model/processor call."""
    from PIL import Image

    crops = [None, Image.new("RGB", (0, 224)), Image.new("RGB", (224, 0))]
    bboxes = [[1, 2, 3, 4], [5, 6, 7, 8], [9, 10, 11, 12]]

    mock_model = MagicMock()
    mock_processor = MagicMock()

    result = await extract_poses_batch(mock_model, mock_processor, crops, bboxes)

    assert len(result) == 3
    for pose_result, bbox in zip(result, bboxes):
        assert pose_result.keypoints == {}
        assert pose_result.pose_class == "unknown"
        assert pose_result.pose_confidence == 0.0
        assert pose_result.bbox == bbox
    mock_processor.assert_not_called()
    mock_model.assert_not_called()
```

```python
# A2: success-path content (kills C2, C3 content, C7, most of C15 via content,
#     and batch65/66/67 text/float mutations) -----------------------------------
@pytest.mark.asyncio
async def test_extract_pose_from_crop_populates_classified_pose(vitpose_mocks):
    """Success path must carry the extracted keypoints + classification through, not just a bbox."""
    from PIL import Image

    model, processor, _ = vitpose_mocks
    result = await extract_pose_from_crop(
        model, processor, Image.new("RGB", (224, 224)), bbox=[0, 0, 224, 224]
    )

    assert isinstance(result, PoseResult)
    assert set(result.keypoints) == set(KEYPOINT_NAMES)
    for name, kp in result.keypoints.items():
        assert kp.name == name
        assert kp.confidence == pytest.approx(0.9)
    assert result.pose_class == "standing"
    assert result.pose_confidence == pytest.approx(0.8)
    assert result.bbox == [0, 0, 224, 224]


@pytest.mark.asyncio
async def test_extract_poses_batch_fills_valid_slots_with_classified_poses(vitpose_mocks):
    """Valid crops classify; an invalid crop keeps ONLY its fallback slot (keypoints={} + bbox)."""
    from PIL import Image

    model, processor, _ = vitpose_mocks
    crops = [Image.new("RGB", (224, 224)), None, Image.new("RGB", (224, 224))]
    bboxes = [[0, 0, 10, 10], [20, 20, 30, 30], [40, 40, 50, 50]]

    result = await extract_poses_batch(model, processor, crops, bboxes)

    assert len(result) == 3
    # Valid slots carry real keypoints (kills early-return flip, results=None, classify(None)
    # and every keypoints=None/pose_class=None/drop in the fill + init blocks).
    for idx in (0, 2):
        assert set(result[idx].keypoints) == set(KEYPOINT_NAMES)
        assert result[idx].pose_class == "standing"
        assert result[idx].pose_confidence == pytest.approx(0.8)
        assert result[idx].bbox == bboxes[idx]
    # Invalid slot: untouched fallback with its OWN bbox (kills bbox=None / drop in init).
    assert result[1].keypoints == {}
    assert result[1].pose_class == "unknown"
    assert result[1].pose_confidence == 0.0
    assert result[1].bbox == bboxes[1]
```

```python
# A3: short keypoints_list (kills C5, plus C6/C12 `<=` variants) ---------------
@pytest.mark.asyncio
async def test_extract_poses_batch_with_short_keypoints_list_fills_only_matching_slots(vitpose_mocks):
    """If post-processing yields fewer results than valid crops, matching slots fill and
    the rest keep the per-slot fallback (bbox preserved)."""
    from PIL import Image

    model, processor, _ = vitpose_mocks
    # First image gets the standing pose; second valid crop gets NO keypoint result.
    standing = _standing_post_process()
    processor.post_process_pose_estimation.side_effect = lambda *_a, **_k: [standing[0], []]

    crops = [Image.new("RGB", (224, 224)), Image.new("RGB", (224, 224))]
    bboxes = [[0, 0, 10, 10], [20, 20, 30, 30]]

    result = await extract_poses_batch(model, processor, crops, bboxes)

    assert set(result[0].keypoints) == set(KEYPOINT_NAMES)
    assert result[1].keypoints == {}
    assert result[1].pose_class == "unknown"
    assert result[1].bbox == bboxes[1]
```

```python
# A4: processor + seam contracts (kills C4, C14, C15) --------------------------
@pytest.mark.asyncio
async def test_extract_pose_from_crop_processor_call_contract(vitpose_mocks):
    """Processor is called with the crop, a full-frame box [[0,0,w,h]] and pt tensors;
    keypoints extraction receives (outputs, processor, [(h, w)], min_confidence=0.3)."""
    from PIL import Image

    import backend.services.vitpose_loader as vpl

    model, processor, _ = vitpose_mocks
    spy = MagicMock(wraps=vpl.extract_keypoints_from_output)
    crop = Image.new("RGB", (200, 224))  # NON-square (w=200, h=224) so (h,w) swaps are visible

    # Spy the module-level seam so argument order/defaults are pinned.
    orig = vpl.extract_keypoints_from_output
    vpl.extract_keypoints_from_output = spy
    try:
        await extract_pose_from_crop(model, processor, crop, bbox=[0, 0, 224, 224])
    finally:
        vpl.extract_keypoints_from_output = orig

    _, kwargs = processor.call_args
    assert kwargs["images"] is crop
    assert kwargs["boxes"] == [[[0, 0, 200, 224]]]
    assert kwargs["return_tensors"] == "pt"

    # Seam call: (outputs, processor, [(height, width)], min_confidence=0.3) positional/
    # keyword form used by the source: outputs, processor, [image_size] then kw.
    args, seam_kwargs = spy.call_args
    assert seam_kwargs["min_confidence"] == 0.3
    assert args[2] == [(224, 200)]  # (h, w) order — kills swaps & None
    assert args[0] is not None and args[1] is processor  # outputs + processor positions
```

## TDD procedure (one line each)

- **A1** `test_extract_pose_from_crop_rejects_invalid_crops` / `..._rejects_invalid_crops_without_calling_processor`: with `bad_crop=None` the assert `pose_class=="unknown"` passes on original (short-circuit returns it) but fails on crop1 (`is not None` flips past the guard → mock pipeline → pose_class=="standing"); `assert_not_called` fails the same way and on batch8/14/15 + init-bbox mutants.
- **A2** `test_extract_pose_from_crop_populates_classified_pose` / `test_extract_poses_batch_fills_valid_slots_with_classified_poses`: `set(result.keypoints)==set(KEYPOINT_NAMES)` passes on original (17 keypoints @0.9 ≥ default min_conf) and fails on every C2 mutant (keypoints=None/dropped, `keypoints_list[1]`, `classify_pose(None)`, `min_confidence=1.0`, `"XXunknownXX"`) and on C3 whole-call mutants (their except fallback yields `keypoints=={}`); result[1] bbox/keypoints asserts kill batch60/64/68/70 init drops and batch16.
- **A3** `test_extract_poses_batch_with_short_keypoints_list_fills_only_matching_slots`: `set(result[0].keypoints)==set(KEYPOINT_NAMES)` passes on original and fails on batch73 (`<=` → IndexError → all-empty fallback).
- **A4** `test_extract_pose_from_crop_processor_call_contract`: `kwargs["return_tensors"]=="pt"` / `boxes==[[[0,0,224,224]]]` / `args[2]==[(224,224)]` pass on original and fail on C4/C14/C15 (None/dropped/"PT"/`[[1,0,...]]`/`image_sizes` swap); on the mutated source the spy records the mutated args, so red is exact.

All four are UNVERIFIED — not executed per the live mutation-run constraint; run red-on-mutant/green-on-original before landing.
