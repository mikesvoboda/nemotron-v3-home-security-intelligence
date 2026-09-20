"""WP3.1 kill tests for backend.services.age_classifier_loader.

Mutation history scored this module 0% (0/79 killed). Same design as the
gender suite: fake model/processor objects (a logits tensor is all the real
path consumes — no transformers download, no CUDA) plus the pure label
normalizer and formatter, asserted against the SPEC so each mutant class has
a concrete failing assertion to trip:

  * _normalize_age_label's full ladder: standard groups, the AGE_RANGES map,
    the numeric parse boundaries (3/13/20/36/51/66), the keyword branches and
    the adult default
  * is_minor is DERIVED in __post_init__ (constructor argument is overridden)
  * classify_age: softmax probabilities recomputed independently in the test,
    top-3 truncation and DESCENDING order of all_scores, display-name mapping
  * batch parity: same per-image result shape, empty input short-circuits
  * format_age_context: exact lines, the 0.5/0.7 confidence bands, MINOR note
"""

from __future__ import annotations

import math
from types import SimpleNamespace

import pytest
import torch
from PIL import Image

from backend.services.age_classifier_loader import (
    AGE_DISPLAY_NAMES,
    AGE_GROUPS,
    AGE_RANGES,
    AgeClassificationResult,
    _normalize_age_label,
    classify_age,
    classify_ages_batch,
    format_age_context,
    load_age_classifier_model,
)


class FakeModel:
    def __init__(self, logits: list[list[float]]) -> None:
        self._out = SimpleNamespace(logits=torch.tensor(logits, dtype=torch.float32))

    def parameters(self):
        yield torch.zeros(1)

    def __call__(self, **kwargs):
        return self._out


class FakeProcessor:
    def __init__(self) -> None:
        self.last_images = None

    def __call__(self, images, return_tensors="pt", padding=False):
        self.last_images = images
        return {"pixel_values": torch.zeros(1, 3, 8, 8)}


def _model_dict(labels, logits):
    return {"model": FakeModel(logits), "processor": FakeProcessor(), "labels": labels}


def _img() -> Image.Image:
    return Image.new("RGB", (8, 8), (9, 9, 9))


def softmax(logits: list[float]) -> list[float]:
    e = [math.exp(v) for v in logits]
    total = sum(e)
    return [v / total for v in e]


# ---------------------------------------------------------------- constants


class TestConstants:
    def test_age_groups_order(self) -> None:
        assert AGE_GROUPS == ["child", "teenager", "young_adult", "adult", "middle_aged", "senior"]

    def test_age_ranges_map_repairs(self) -> None:
        assert AGE_RANGES["0-2"] == "infant"
        assert AGE_RANGES["10-19"] == "teenager"
        assert AGE_RANGES["more than 70"] == "senior"

    def test_display_names(self) -> None:
        assert AGE_DISPLAY_NAMES["young_adult"] == "young adult (20-35 years)"
        assert AGE_DISPLAY_NAMES["middle_aged"] == "middle-aged (51-65 years)"


# ---------------------------------------------------- AgeClassificationResult


class TestAgeClassificationResult:
    def _mk(self, group: str, **kw) -> AgeClassificationResult:
        defaults = {"confidence": 0.8, "display_name": "x", "all_scores": {}}
        return AgeClassificationResult(age_group=group, **{**defaults, **kw})

    @pytest.mark.parametrize("group", ["infant", "child", "teenager"])
    def test_minors_derived(self, group: str) -> None:
        assert self._mk(group).is_minor is True

    @pytest.mark.parametrize("group", ["young_adult", "adult", "middle_aged", "senior"])
    def test_adults_not_minor(self, group: str) -> None:
        assert self._mk(group).is_minor is False

    def test_is_minor_overrides_constructor(self) -> None:
        # __post_init__ recomputes: a passed is_minor=True cannot lie about an adult
        assert self._mk("adult", is_minor=True).is_minor is False

    def test_to_dict_roundtrip(self) -> None:
        r = self._mk("child", display_name="child (3-12 years)", all_scores={"child": 0.8})
        assert r.to_dict() == {
            "age_group": "child",
            "confidence": 0.8,
            "display_name": "child (3-12 years)",
            "all_scores": {"child": 0.8},
            "is_minor": True,
        }

    def test_context_string_minor_suffix(self) -> None:
        assert self._mk("teenager", display_name="teenager (13-19 years)").to_context_string() == (
            "Estimated age: teenager (13-19 years) (80% confidence) [MINOR]"
        )

    def test_context_string_no_suffix_for_adult(self) -> None:
        assert self._mk("adult", display_name="adult (36-50 years)").to_context_string() == (
            "Estimated age: adult (36-50 years) (80% confidence)"
        )


# -------------------------------------------------------- _normalize_age_label


class TestNormalizeAgeLabel:
    @pytest.mark.parametrize("label", AGE_DISPLAY_NAMES)
    def test_standard_groups_pass_through(self, label: str) -> None:
        assert _normalize_age_label(label) == label

    @pytest.mark.parametrize("raw,expected", sorted(AGE_RANGES.items()))
    def test_range_map(self, raw: str, expected: str) -> None:
        assert _normalize_age_label(raw) == expected

    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("0-2", "infant"),  # map hit
            ("2-3", "infant"),  # parse: start < 3
            ("3-9", "child"),  # map hit
            ("12-13", "child"),  # parse: start < 13
            ("13-19", "teenager"),  # map hit
            ("19-20", "teenager"),  # parse: start < 20
            ("20-29", "young_adult"),  # map hit
            ("35-36", "young_adult"),  # parse: start < 36
            ("36-40", "adult"),  # parse: start < 51 (not in map)
            ("50-55", "adult"),  # parse: 50 < 51
        ],
    )
    def test_numeric_boundaries(self, raw: str, expected: str) -> None:
        assert _normalize_age_label(raw) == expected

    def test_numeric_boundaries_directly(self) -> None:
        # 50 parses adult (50 < 51); 51 parses middle_aged; 65 middle, 66 senior
        assert _normalize_age_label("50-x") == "adult"
        assert _normalize_age_label("51-x") == "middle_aged"
        assert _normalize_age_label("65-x") == "middle_aged"
        assert _normalize_age_label("66-x") == "senior"

    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("Kid", "child"),
            ("youngster", "young_adult"),
            ("teen", "teenager"),
            ("adolescent", "teenager"),
            ("elderly", "senior"),
            ("old man", "senior"),
            ("grown adult", "adult"),
            ("Baby", "infant"),
            ("something else", "adult"),  # documented default
        ],
    )
    def test_keyword_branches(self, raw: str, expected: str) -> None:
        assert _normalize_age_label(raw) == expected

    def test_unparseable_dash_falls_through(self) -> None:
        assert _normalize_age_label("teen-ish") == "teenager"  # keyword beats failed parse


# ------------------------------------------------------------------ classify_age


class TestClassifyAge:
    @pytest.mark.asyncio
    async def test_top_prediction_confidence_and_display(self) -> None:
        labels = ["child", "teenager", "adult"]
        probs = softmax([0.1, 0.2, 4.0])
        result = await classify_age(_model_dict(labels, [[0.1, 0.2, 4.0]]), _img())
        assert result.age_group == "adult"
        assert result.confidence == pytest.approx(probs[2])
        assert result.display_name == AGE_DISPLAY_NAMES["adult"]

    @pytest.mark.asyncio
    async def test_all_scores_is_top3_descending(self) -> None:
        labels = ["child", "teenager", "adult", "senior", "infant"]
        logits = [[0.0, 1.0, 5.0, 2.0, -1.0]]
        probs = softmax(logits[0])
        result = await classify_age(_model_dict(labels, logits), _img())
        expected = sorted(zip(labels, probs, strict=True), key=lambda kv: kv[1], reverse=True)[:3]
        assert [k for k, _ in result.all_scores.items()] == [k for k, _ in expected]
        for (ek, ev), result_item in zip(expected, result.all_scores.items(), strict=True):
            assert result_item[0] == ek
            assert result_item[1] == pytest.approx(ev)

    @pytest.mark.asyncio
    async def test_range_label_normalized_with_display(self) -> None:
        result = await classify_age(_model_dict(["20-29"], [[2.0]]), _img())
        assert result.age_group == "young_adult"
        assert result.display_name == "young adult (20-35 years)"

    @pytest.mark.asyncio
    async def test_non_rgb_converted(self) -> None:
        md = _model_dict(["adult"], [[1.0]])
        await classify_age(md, Image.new("L", (8, 8), 3))
        assert md["processor"].last_images.mode == "RGB"

    @pytest.mark.asyncio
    async def test_model_error_wrapped(self) -> None:
        class Boom(FakeModel):
            def __call__(self, **kwargs):
                raise ValueError("kaboom")

        md = _model_dict(["adult"], [[1.0]])
        md["model"] = Boom([[1.0]])
        with pytest.raises(RuntimeError, match="Age classification failed"):
            await classify_age(md, _img())


# ------------------------------------------------------------ classify_ages_batch


class TestClassifyAgesBatch:
    @pytest.mark.asyncio
    async def test_empty_returns_empty(self) -> None:
        assert await classify_ages_batch({"model": None, "processor": None, "labels": []}, []) == []

    @pytest.mark.asyncio
    async def test_one_row_per_image(self) -> None:
        labels = ["child", "adult"]
        md = _model_dict(labels, [[4.0, 0.0], [0.0, 4.0]])
        results = await classify_ages_batch(md, [_img(), _img()])
        assert [r.age_group for r in results] == ["child", "adult"]
        assert [r.is_minor for r in results] == [True, False]

    @pytest.mark.asyncio
    async def test_batch_minor_flag_and_top3(self) -> None:
        labels = ["child", "teenager", "adult"]
        md = _model_dict(labels, [[0.0, 3.0, 1.0]])
        (r,) = await classify_ages_batch(md, [_img()])
        assert r.age_group == "teenager"
        assert r.is_minor is True
        assert list(r.all_scores) == ["teenager", "adult", "child"]


# ----------------------------------------------------------- format_age_context


class TestFormatAgeContext:
    @staticmethod
    def _r(group="adult", conf=0.8):
        return AgeClassificationResult(
            age_group=group,
            confidence=conf,
            display_name=AGE_DISPLAY_NAMES[group],
            all_scores={},
        )

    def test_none(self) -> None:
        assert format_age_context(None) == "Age estimation: Not available"

    def test_basic_line(self) -> None:
        assert format_age_context(self._r()).startswith("Age: adult (36-50 years) (80%)")

    def test_detection_prefix(self) -> None:
        assert format_age_context(self._r(), detection_id="d9").startswith("Person d9: Age: ")

    def test_minor_note(self) -> None:
        assert "Minor detected" in format_age_context(self._r("child"))

    def test_low_confidence_qualifier(self) -> None:
        out = format_age_context(self._r(conf=0.4))
        assert "Low confidence" in out and "Medium confidence" not in out

    def test_medium_confidence_qualifier(self) -> None:
        out = format_age_context(self._r(conf=0.6))
        assert "Medium confidence" in out and "Low confidence" not in out

    def test_high_confidence_has_no_qualifier(self) -> None:
        out = format_age_context(self._r(conf=0.9))
        assert "Low confidence" not in out and "Medium confidence" not in out
        assert out == "Age: adult (36-50 years) (90%)"


# ---------------------------------------------------------------- CPU guard


class TestLoadCpuGuard:
    @pytest.mark.asyncio
    async def test_cpu_host_raises_runtime_error(self, tmp_path) -> None:
        with pytest.raises(RuntimeError, match=r"Age Classifier|Failed to load"):
            await load_age_classifier_model(str(tmp_path))
