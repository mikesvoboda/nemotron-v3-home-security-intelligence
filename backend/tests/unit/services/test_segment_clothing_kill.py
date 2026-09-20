"""WP3.2 kill tests for segformer_loader.segment_clothing — inverted threat signal.

Plan P §WP3.2: segformer_loader scores 29.4%; 152 of segment_clothing's 153
mutants survive, PROVEN non-equivalent. The function decides the security
signal from a clothing segmentation mask: which categories count, the
min_coverage gate, shoe consolidation, and the face-covered threat flag.

WHY 152 survived (observed while writing these tests): the function's outer
`except Exception: return ClothingSegmentationResult()` turns ANY internal
breakage into a silent empty result — a mutant that throws, or that flips a
condition into a dead branch, is indistinguishable from "ran fine, nothing
detected" unless the test pins the NON-default values. Every test below
asserts the exact happy-path result, so an internally-broken mutant lands on
the default and dies. (The swallow itself is WP3.2's kill-test subject too:
test_processor_error_is_invisible_is_NOT_asserted_here — no: see
test_failing_processor_returns_empty_default — the swallow is pinned as
SPEC so its semantics cannot silently widen.)

Doctrine: a synthetic torch.nn.Module emits a pinned one-hot logit volume
(argmax == the mask), a recording processor proves the crop wiring, and every
security-relevant branch gets its truth-table corner.

CPU-only: fake model, no SegFormer weights, no GPU.
"""

from __future__ import annotations

import numpy as np
import pytest
import torch
from PIL import Image

from backend.services.segformer_loader import segment_clothing


class FakeSegformer(torch.nn.Module):
    """One-hot logits per pixel: pixel (r,c) is class mask[r, c].

    A real nn.Module so `next(model.parameters()).device` — the production
    wiring line — works unmodified (a hand-rolled params object must be an
    ITERATOR; the first draft learned this the honest way).
    """

    def __init__(self, mask: np.ndarray, n_classes: int = 18) -> None:
        super().__init__()
        # a Parameter, not a buffer: buffers() don't appear in parameters(),
        # and an empty parameters() makes next() raise StopIteration — which
        # lands in the except-swallow and returns the silent empty result
        self._anchor = torch.nn.Parameter(torch.zeros(1))
        self._mask = mask
        self._n = n_classes
        self.calls = 0

    def forward(self, **_inputs):
        self.calls += 1
        h, w = self._mask.shape
        logits = torch.zeros(1, self._n, h, w)
        flat = self._mask.reshape(-1)
        rows, cols = np.divmod(np.arange(h * w), w)
        logits[0, flat, rows, cols] = 10.0
        return type("O", (), {"logits": logits})()


class FakeProcessor:
    def __init__(self, fail: bool = False) -> None:
        self.seen: list = []
        self._fail = fail

    def __call__(self, images=None, return_tensors=None):
        self.seen.append((images, return_tensors))
        if self._fail:
            raise RuntimeError("processor exploded")
        return {"pixel_values": torch.zeros(1, 3, 4, 4)}


def _mask_from(blocks: dict[int, float], h: int = 10, w: int = 10) -> np.ndarray:
    """Fill an h-by-w mask: {class_id: fraction}. Fractions sum to 1.0; blocks
    are contiguous row-major so coverage counts are EXACT (no rounding)."""
    total = h * w
    flat = np.zeros(total, dtype=np.int64)
    idx = 0
    for cls, frac in blocks.items():
        n = round(frac * total)
        flat[idx : idx + n] = cls
        idx += n
    assert idx == total, "block fractions must cover the mask exactly"
    return flat.reshape(h, w)


async def _run(mask: np.ndarray, min_coverage: float = 0.01, fail_processor: bool = False):
    h, w = mask.shape
    model = FakeSegformer(mask)
    processor = FakeProcessor(fail=fail_processor)
    img = Image.new("RGB", (w, h), (9, 9, 9))
    result = await segment_clothing(model, processor, img, min_coverage=min_coverage)
    return result, model, processor


# ------------------------------------------------------------- wiring


@pytest.mark.asyncio
async def test_processor_and_model_are_invoked_once_with_the_crop():
    mask = np.full((8, 8), 4, dtype=np.int64)  # all upper_clothes
    result, model, processor = await _run(mask)
    assert processor.seen[0][0] is not None and processor.seen[0][1] == "pt"
    assert model.calls == 1
    assert result.coverage_percentages == {"upper_clothes": 100.0}
    assert result.clothing_items == {"upper_clothes"}


# ----------------------------------------------------- coverage arithmetic


@pytest.mark.asyncio
async def test_coverage_percentages_are_exact_and_rounded_2dp():
    """30% hat / 60% pants / 10% background — pinned to 2dp. Kills coverage
    = count/total mutants (x100 placement, rounding, denominator)."""
    mask = _mask_from({1: 0.30, 6: 0.60, 0: 0.10})
    result, _, _ = await _run(mask)
    assert result.coverage_percentages == pytest.approx({"hat": 30.0, "pants": 60.0})
    assert "background" not in result.coverage_percentages, (
        "background is excluded by label, never reported (mutant: dropped guard)"
    )


@pytest.mark.asyncio
async def test_min_coverage_is_inclusive_ge_and_filters_tiny_classes():
    """1px of 100 = 1.0%: min_coverage=0.01 KEEPS it (>=), 0.02 DROPS it.
    A >= -> > mutant dies on the inclusive case; a removed gate dies on the
    exclusive one."""
    mask = _mask_from({3: 0.01, 4: 0.99})
    kept, _, _ = await _run(mask, min_coverage=0.01)
    assert kept.coverage_percentages.get("sunglasses") == pytest.approx(1.0)
    assert "sunglasses" in kept.clothing_items

    dropped, _, _ = await _run(mask, min_coverage=0.02)
    assert "sunglasses" not in dropped.coverage_percentages
    assert "sunglasses" not in dropped.clothing_items
    assert dropped.coverage_percentages == {"upper_clothes": pytest.approx(99.0)}


# ------------------------------------------------------ shoe consolidation


@pytest.mark.asyncio
async def test_shoes_consolidate_and_individual_entries_are_removed():
    """left_shoe 12% + right_shoe 8% -> ONE 'shoes' at 20.0, individual keys
    popped. Kills: missing pop (key leak), missing sum (halved coverage)."""
    mask = _mask_from({9: 0.12, 10: 0.08, 4: 0.80})
    result, _, _ = await _run(mask)
    assert result.coverage_percentages["shoes"] == pytest.approx(20.0)
    assert "left_shoe" not in result.coverage_percentages
    assert "right_shoe" not in result.coverage_percentages
    assert "shoes" in result.clothing_items


# -------------------------------------------------------- threat semantics


@pytest.mark.asyncio
async def test_face_covered_truth_table():
    """Rule: sunglasses AND (hat|scarf OR face<5%). Four corners pin the
    AND/OR/operand mutants that flip the threat signal (plan P's harm class).

    bool(...) because the face-coverage operand is a NUMPY bool (np.float64
    ratio < 5.0) and the `or` chain hands it through unconverted — observed
    while writing this: `has_face_covered is False` fails on the UNMUTATED
    source for the np.False_ it legitimately produces. Pin the VALUE."""
    r1, _, _ = await _run(_mask_from({3: 0.20, 1: 0.30, 11: 0.50}))
    assert bool(r1.has_face_covered) is True  # glasses + hat
    r2, _, _ = await _run(_mask_from({3: 0.20, 11: 0.60, 4: 0.20}))
    assert bool(r2.has_face_covered) is False  # glasses, face 60% visible, no headwear
    r3, _, _ = await _run(_mask_from({3: 0.20, 17: 0.30, 11: 0.50}))
    assert bool(r3.has_face_covered) is True  # scarf counts as head covering
    r4, _, _ = await _run(_mask_from({1: 0.30, 11: 0.70}))
    assert bool(r4.has_face_covered) is False  # headwear WITHOUT glasses


@pytest.mark.asyncio
async def test_bag_flag_and_non_security_labels_stay_out_of_items():
    mask = _mask_from({16: 0.20, 2: 0.30, 12: 0.25, 4: 0.25})
    result, _, _ = await _run(mask)
    assert result.has_bag is True
    assert "bag" in result.clothing_items
    assert not {"hair", "face", "left_leg"} & result.clothing_items
    assert result.coverage_percentages["hair"] == pytest.approx(30.0)


# ------------------------------------------------------------- mask shape


@pytest.mark.asyncio
async def test_raw_mask_is_argmax_at_crop_resolution():
    mask = _mask_from({5: 0.25, 7: 0.25, 8: 0.25, 14: 0.25})
    result, _, _ = await _run(mask)
    assert result.raw_mask.shape == (10, 10)
    assert set(np.unique(result.raw_mask)) == {5, 7, 8, 14}


# ------------------------------------------------- the swallow, pinned as spec


@pytest.mark.asyncio
async def test_internal_failure_degrades_to_empty_default_by_design():
    """The processor raising must return the EMPTY result (the documented
    degradation) — and crucially this test documents WHY 152 mutants survived:
    a broken mutant also lands here. That is only safe because every test
    above pins NON-default values; this file's suite shape is the fix.
    (If the swallow ever starts RAISING, this test goes red on purpose —
    changing degradation semantics is an owner call, not a drift.)"""
    mask = np.full((6, 6), 4, dtype=np.int64)
    result, _, processor = await _run(mask, fail_processor=True)
    assert processor.seen, "processor was invoked and raised — that's the injected failure"
    assert result.clothing_items == set()
    assert result.coverage_percentages == {}
    assert result.has_face_covered is False
    assert result.has_bag is False
