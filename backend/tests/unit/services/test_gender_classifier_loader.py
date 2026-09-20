"""WP3.1 kill tests for backend.services.gender_classifier_loader.

Mutation history scored this module 0% (0/79 killed): the pure result/label/
format surface and the model-inference plumbing ran only through indirect
import coverage, so no assertion ever opposed a mutant. These tests drive
classify_gender / classify_genders_batch with FAKE model+processor objects
(a logits tensor is all the real call path needs — no transformers download,
no CUDA) and assert the SPEC at every branch:

  * softmax -> argmax -> label, with confidence recomputed from scratch in
    the test (math.exp), so a softmax/scaling mutation diverges
  * _find_label_index exact-vs-partial-vs-None and the binary-inference
    fallback (labels the matcher cannot see -> index 0=male, 1=female)
  * _normalize_gender_label's synonym sets and its raw-passthrough default
  * format strings pinned EXACTLY (the two formatters differ: "(90%
    confidence)" vs "(90%)"), the [low confidence] 0.6 boundary, prefix logic
  * demographics composition: note joining, [MINOR], display_name priority
  * the CPU-guard RuntimeError in load_gender_classifier_model
"""

from __future__ import annotations

import math
from types import SimpleNamespace

import pytest
import torch
from PIL import Image

from backend.services.gender_classifier_loader import (
    GENDER_LABELS,
    GenderClassificationResult,
    _find_label_index,
    _normalize_gender_label,
    classify_gender,
    classify_genders_batch,
    format_gender_context,
    format_person_demographics_context,
    load_gender_classifier_model,
)


class FakeModel:
    """Minimal stand-in: classify_* only needs parameters() (device/dtype)
    and a call returning .logits."""

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
    return {
        "model": FakeModel(logits),
        "processor": FakeProcessor(),
        "labels": labels,
    }


def _img() -> Image.Image:
    return Image.new("RGB", (8, 8), (9, 9, 9))


def softmax2(a: float, b: float) -> tuple[float, float]:
    ea, eb = math.exp(a), math.exp(b)
    return ea / (ea + eb), eb / (ea + eb)


# ---------------------------------------------------------------- constants


class TestGenderLabels:
    def test_labels_are_male_female_in_order(self) -> None:
        assert GENDER_LABELS == ["male", "female"]


# ----------------------------------------------------- GenderClassificationResult


class TestGenderClassificationResult:
    def test_to_dict_keys_and_values(self) -> None:
        r = GenderClassificationResult(
            gender="male", confidence=0.9, male_score=0.9, female_score=0.1
        )
        assert r.to_dict() == {
            "gender": "male",
            "confidence": 0.9,
            "male_score": 0.9,
            "female_score": 0.1,
        }

    def test_context_string_format_percent_confidence(self) -> None:
        r = GenderClassificationResult(
            gender="female", confidence=0.856, male_score=0.1, female_score=0.9
        )
        assert r.to_context_string() == "Gender: female (86% confidence)"


# ---------------------------------------------------------------- classify_gender


class TestClassifyGender:
    @pytest.mark.asyncio
    async def test_male_prediction_with_recomputed_softmax(self) -> None:
        pm, _ = softmax2(3.0, 0.0)
        result = await classify_gender(_model_dict(["male", "female"], [[3.0, 0.0]]), _img())
        assert result.gender == "male"
        assert result.confidence == pytest.approx(pm)
        assert result.male_score == pytest.approx(pm)
        assert result.female_score == pytest.approx(1 - pm)

    @pytest.mark.asyncio
    async def test_female_prediction_and_index_lookup(self) -> None:
        _, pf = softmax2(0.0, 3.0)
        result = await classify_gender(_model_dict(["male", "female"], [[0.0, 3.0]]), _img())
        assert result.gender == "female"
        assert result.female_score == pytest.approx(pf)

    @pytest.mark.asyncio
    async def test_case_insensitive_labels_normalized(self) -> None:
        pm, _ = softmax2(3.0, 0.0)
        result = await classify_gender(_model_dict(["Male", "Female"], [[3.0, 0.0]]), _img())
        assert result.gender == "male"  # _normalize applied to "Male"
        assert result.male_score == pytest.approx(pm)  # _find_label_index saw "MALE"~"Male"

    @pytest.mark.asyncio
    async def test_binary_fallback_when_labels_unmatchable(self) -> None:
        # "man"/"woman" defeat _find_label_index ("male" is not in "man"),
        # so the documented index convention kicks in: 0=male, 1=female
        pm, pf = softmax2(0.0, 2.0)
        result = await classify_gender(_model_dict(["man", "woman"], [[0.0, 2.0]]), _img())
        assert result.gender == "female"
        assert result.male_score == pytest.approx(pm)
        assert result.female_score == pytest.approx(pf)

    @pytest.mark.asyncio
    async def test_partial_label_match(self) -> None:
        # "female" is found as a substring of "female_person"
        _, pf = softmax2(0.0, 3.0)
        result = await classify_gender(
            _model_dict(["male_person", "female_person"], [[0.0, 3.0]]), _img()
        )
        assert result.female_score == pytest.approx(pf)

    @pytest.mark.asyncio
    async def test_non_rgb_input_converted_before_processor(self) -> None:
        md = _model_dict(["male", "female"], [[3.0, 0.0]])
        await classify_gender(md, Image.new("L", (8, 8), 7))
        assert md["processor"].last_images.mode == "RGB"

    @pytest.mark.asyncio
    async def test_model_error_wrapped_in_runtime_error(self) -> None:
        class Boom(FakeModel):
            def __call__(self, **kwargs):
                raise ValueError("kaboom")

        md = _model_dict(["male", "female"], [[0.0, 0.0]])
        md["model"] = Boom([[0.0, 0.0]])
        with pytest.raises(RuntimeError, match="Gender classification failed"):
            await classify_gender(md, _img())


# ------------------------------------------------------- classify_genders_batch


class TestClassifyGendersBatch:
    @pytest.mark.asyncio
    async def test_empty_input_returns_empty_without_model(self) -> None:
        assert (
            await classify_genders_batch({"model": None, "processor": None, "labels": []}, []) == []
        )

    @pytest.mark.asyncio
    async def test_one_result_per_image_in_order(self) -> None:
        md = {
            "model": FakeModel([[3.0, 0.0], [0.0, 3.0]]),
            "processor": FakeProcessor(),
            "labels": ["male", "female"],
        }
        results = await classify_genders_batch(md, [_img(), _img()])
        assert [r.gender for r in results] == ["male", "female"]

    @pytest.mark.asyncio
    async def test_batch_fallback_scores_use_positional_convention(self) -> None:
        md = {
            "model": FakeModel([[1.0, 2.0]]),
            "processor": FakeProcessor(),
            "labels": ["x", "y"],
        }
        p0, p1 = softmax2(1.0, 2.0)
        (r,) = await classify_genders_batch(md, [_img()])
        assert r.male_score == pytest.approx(p0)
        assert r.female_score == pytest.approx(p1)


# ------------------------------------------------------------ label helpers


class TestNormalizeGenderLabel:
    @pytest.mark.parametrize("raw", ["male", "MAN", "Boy", " m ", "Man"])
    def test_male_synonyms(self, raw: str) -> None:
        assert _normalize_gender_label(raw) == "male"

    @pytest.mark.parametrize("raw", ["female", "Woman", "GIRL", " f "])
    def test_female_synonyms(self, raw: str) -> None:
        assert _normalize_gender_label(raw) == "female"

    def test_unknown_label_passes_through_lowercased(self) -> None:
        assert _normalize_gender_label("NonBinary") == "nonbinary"


class TestFindLabelIndex:
    def test_exact_case_insensitive(self) -> None:
        assert _find_label_index(["Male", "Female"], "male") == 0
        assert _find_label_index(["Male", "Female"], "FEMALE") == 1

    def test_partial_match(self) -> None:
        assert _find_label_index(["male", "female_person"], "female") == 1

    def test_not_found_is_none(self) -> None:
        assert _find_label_index(["man", "woman"], "male") is None


# ------------------------------------------------------------- context format


class TestFormatGenderContext:
    def test_none_says_not_available(self) -> None:
        assert format_gender_context(None) == "Gender estimation: Not available"

    def test_basic_line_exact(self) -> None:
        r = GenderClassificationResult(
            gender="male", confidence=0.85, male_score=0.85, female_score=0.15
        )
        assert format_gender_context(r) == "Gender: male (85%)"

    def test_detection_id_prefix(self) -> None:
        r = GenderClassificationResult(
            gender="male", confidence=0.85, male_score=0.85, female_score=0.15
        )
        assert format_gender_context(r, detection_id="d-1") == "Person d-1: Gender: male (85%)"

    def test_low_confidence_qualifier_boundary(self) -> None:
        lo = GenderClassificationResult(
            gender="male", confidence=0.59, male_score=0.59, female_score=0.41
        )
        hi = GenderClassificationResult(
            gender="male", confidence=0.60, male_score=0.60, female_score=0.40
        )
        assert format_gender_context(lo).endswith("[low confidence]")
        assert "[low confidence]" not in format_gender_context(hi)


class TestFormatPersonDemographicsContext:
    @staticmethod
    def _age(**kw):
        defaults = {
            "age_group": "adult",
            "confidence": 0.8,
            "display_name": "adult (36-50 years)",
            "all_scores": {},
            "is_minor": False,
        }
        return SimpleNamespace(**{**defaults, **kw})

    @staticmethod
    def _gender(confidence=0.8, gender="male"):
        return GenderClassificationResult(
            gender=gender, confidence=confidence, male_score=confidence, female_score=1 - confidence
        )

    def test_nothing_gives_bare_person(self) -> None:
        assert format_person_demographics_context(None, None) == "Person:"

    def test_detection_id_prefix(self) -> None:
        assert format_person_demographics_context(None, None, detection_id="7") == "Person 7:"

    def test_gender_and_age_joined(self) -> None:
        out = format_person_demographics_context(self._age(), self._gender())
        assert out == "Person: male, adult (36-50 years)"

    def test_age_group_used_when_no_display_name(self) -> None:
        age = SimpleNamespace(age_group="teenager", confidence=0.8)
        out = format_person_demographics_context(age, None)
        assert out == "Person:, teenager"

    def test_uncertain_notes_joined(self) -> None:
        out = format_person_demographics_context(
            self._age(confidence=0.4), self._gender(confidence=0.4)
        )
        assert out.endswith("[gender uncertain, age uncertain]")

    def test_minor_note_appended(self) -> None:
        age = self._age(
            age_group="child", display_name="child (3-12 years)", confidence=0.9, is_minor=True
        )
        out = format_person_demographics_context(age, self._gender())
        assert out.endswith("[MINOR]")

    def test_age_uncertain_but_gender_confident(self) -> None:
        out = format_person_demographics_context(
            self._age(age_group="child", display_name="child (3-12 years)", confidence=0.4),
            self._gender(confidence=0.9),
        )
        assert "[age uncertain]" in out
        assert "gender uncertain" not in out


# ------------------------------------------------------------- CPU guard


class TestLoadCpuGuard:
    @pytest.mark.asyncio
    async def test_cpu_host_raises_runtime_error(self, monkeypatch, tmp_path) -> None:
        # No CUDA in this sandbox; the guard must refuse before any download.
        # (If a real GPU host ever runs this suite the guard passes through to
        # a from_pretrained failure on the empty tmp_path -- still RuntimeError.)
        with pytest.raises(RuntimeError, match=r"Gender Classifier|Failed to load"):
            await load_gender_classifier_model(str(tmp_path))
