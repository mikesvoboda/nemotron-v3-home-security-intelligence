"""WP3.1 kill tests for backend.services.zero_dce_loader.

The weekly mutation run scored this module 0% (0/31 killed) with reason
TRUE-ZERO: the pure helpers had NO unit coverage (only an integration test
under the gpu marker), so every mutant executed unchallenged. These tests
assert the SPEC, not just execution — each is written to FAIL against the
mutant class it targets:

  * BT.601 luminance coefficients and channel order (single-channel images
    pin each coefficient to a distinct value: R->0.299, G->0.587, B->0.114)
  * should_enhance's strict ``<`` (a pixel value of exactly the threshold
    must NOT enhance) and the default-threshold constants
  * _apply_curve's 8-iteration loop and curve formula, pinned by replaying
    the recurrence step-by-step in the test
  * forward's layer wiring (skip-cat order, relu placement, tanh), pinned by
    re-running the same sublayers manually — any wiring mutation diverges
  * load_zero_dce_model round-trip against a real torch.save'd state_dict
    (state-dict really loaded, really eval(), really keyed {"model","device"})
  * enhance_image's tensor<->PIL pipeline against an Identity model (round
    trip preserves pixels and size, grayscale input is converted)

CPU-only: the conv nets here are ~10K parameters, so real forwards are cheap.
"""

from __future__ import annotations

import pytest
import torch
from PIL import Image

from backend.services.zero_dce_loader import (
    LOW_LIGHT_BRIGHTNESS_THRESHOLD,
    SCALE_FACTOR,
    ZeroDCEPP,
    _compute_mean_brightness,
    enhance_image,
    load_zero_dce_model,
    should_enhance,
)


def _solid(rgb: tuple[int, int, int], size: tuple[int, int] = (4, 4)) -> Image.Image:
    return Image.new("RGB", size, rgb)


# --------------------------------------------------------------- constants


class TestConstants:
    def test_brightness_threshold_is_035(self) -> None:
        assert LOW_LIGHT_BRIGHTNESS_THRESHOLD == 0.35

    def test_scale_factor_is_full_resolution(self) -> None:
        assert SCALE_FACTOR == 1


# ------------------------------------------------------ _compute_mean_brightness


class TestComputeMeanBrightness:
    def test_red_uses_bt601_red_coefficient(self) -> None:
        # 0.299, not green's 0.587 or blue's 0.114 — pins coefficient AND channel order
        assert _compute_mean_brightness(_solid((255, 0, 0))) == pytest.approx(0.299, abs=1e-5)

    def test_green_uses_bt601_green_coefficient(self) -> None:
        assert _compute_mean_brightness(_solid((0, 255, 0))) == pytest.approx(0.587, abs=1e-5)

    def test_blue_uses_bt601_blue_coefficient(self) -> None:
        assert _compute_mean_brightness(_solid((0, 0, 255))) == pytest.approx(0.114, abs=1e-5)

    def test_black_is_zero_white_is_one(self) -> None:
        assert _compute_mean_brightness(_solid((0, 0, 0))) == pytest.approx(0.0, abs=1e-9)
        assert _compute_mean_brightness(_solid((255, 255, 255))) == pytest.approx(1.0, abs=1e-5)

    def test_mean_is_over_pixels_not_sum(self) -> None:
        img = Image.new("RGB", (2, 2))
        img.putpixel((0, 0), (255, 0, 0))
        img.putpixel((1, 0), (0, 255, 0))
        img.putpixel((0, 1), (0, 0, 255))
        # mean of (0.299, 0.587, 0.114, 0.0) — a sum() mutation would be ~4x larger
        assert _compute_mean_brightness(img) == pytest.approx((0.299 + 0.587 + 0.114) / 4, abs=1e-5)

    def test_grayscale_input_is_converted_to_rgb(self) -> None:
        # BT.601 weights sum to 1.0, so a converted gray image's luminance is v/255
        gray = Image.new("L", (4, 4), 128)
        assert _compute_mean_brightness(gray) == pytest.approx(128 / 255, abs=1e-5)


# ------------------------------------------------------------------ should_enhance


class TestShouldEnhance:
    def test_dark_image_is_enhanced(self) -> None:
        assert should_enhance(_solid((20, 20, 20))) is True

    def test_bright_image_is_not_enhanced(self) -> None:
        assert should_enhance(_solid((200, 200, 200))) is False

    def test_at_exact_threshold_is_not_enhanced(self) -> None:
        # 102/255 == 0.4 exactly; the predicate is strict `<`, not `<=`
        assert should_enhance(_solid((102, 102, 102)), threshold=0.4) is False

    def test_just_under_explicit_threshold_is_enhanced(self) -> None:
        assert should_enhance(_solid((101, 101, 101)), threshold=0.4) is True

    def test_default_threshold_is_the_module_constant(self) -> None:
        # 80/255 = 0.3137 < 0.35 -> True; 100/255 = 0.392 -> False
        assert should_enhance(_solid((80, 80, 80))) is True
        assert should_enhance(_solid((100, 100, 100))) is False


# -------------------------------------------------------------------- ZeroDCEPP


class TestApplyCurve:
    def test_eight_iteration_recurrence(self) -> None:
        """Replay x <- x + x_r * (x^2 - x) exactly 8 times and require equality:
        a mutated iteration count or curve algebra diverges."""
        torch.manual_seed(0)
        x = torch.rand(1, 3, 4, 4)
        x_r = torch.tanh(torch.randn(1, 3, 4, 4))
        model = ZeroDCEPP()
        expected = x.clone()
        for _ in range(8):
            expected = expected + x_r * (torch.pow(expected, 2) - expected)
        assert torch.allclose(model._apply_curve(x.clone(), x_r), expected, atol=1e-6)

    def test_zero_curve_parameters_are_the_identity(self) -> None:
        x = torch.rand(1, 3, 4, 4)
        out = ZeroDCEPP()._apply_curve(x, torch.zeros_like(x))
        assert torch.allclose(out, x, atol=1e-7)


class TestForward:
    def test_forward_matches_manual_layer_trace(self) -> None:
        """Re-run the documented topology from the model's own sublayers; the
        skip-cat order (x3|x4, x2|x5, x1|x6), relu placement and tanh head are
        all pinned."""
        torch.manual_seed(7)
        model = ZeroDCEPP().eval()
        x = torch.rand(1, 3, 8, 8)
        x1 = model.relu(model.e_conv1(x))
        x2 = model.relu(model.e_conv2(x1))
        x3 = model.relu(model.e_conv3(x2))
        x4 = model.relu(model.e_conv4(x3))
        x5 = model.relu(model.e_conv5(torch.cat([x3, x4], 1)))
        x6 = model.relu(model.e_conv6(torch.cat([x2, x5], 1)))
        x_r = torch.tanh(model.e_conv7(torch.cat([x1, x6], 1)))
        expected = model._apply_curve(x, x_r)
        assert torch.allclose(model(x), expected, atol=1e-5)

    def test_scale_one_output_is_input_shape_and_range(self) -> None:
        model = ZeroDCEPP().eval()
        x = torch.rand(1, 3, 8, 8)
        with torch.no_grad():
            out = model(x)
        assert out.shape == x.shape
        assert bool(((out >= 0) & (out <= 1)).all())

    def test_scale_two_resamples_back_to_input_size(self) -> None:
        model = ZeroDCEPP(scale_factor=2).eval()
        x = torch.rand(1, 3, 16, 16)
        with torch.no_grad():
            out = model(x)
        assert out.shape == x.shape


# ------------------------------------------------------------ load_zero_dce_model


class TestLoadZeroDceModel:
    @pytest.mark.asyncio
    async def test_missing_weights_raises_runtime_error(self, tmp_path) -> None:
        with pytest.raises(RuntimeError, match=r"Epoch99\.pth"):
            await load_zero_dce_model(str(tmp_path))

    @pytest.mark.asyncio
    async def test_roundtrip_loads_weights_into_eval_model(self, tmp_path) -> None:
        reference = ZeroDCEPP(scale_factor=SCALE_FACTOR).eval()
        torch.save(reference.state_dict(), tmp_path / "Epoch99.pth")

        result = await load_zero_dce_model(str(tmp_path))

        assert set(result) == {"model", "device"}
        model = result["model"]
        assert isinstance(model, ZeroDCEPP)
        assert model.training is False  # .eval() ran
        assert str(result["device"]) == "cpu"  # sandbox has no GPU
        # weights really loaded (not a fresh random init): same inputs -> same outputs
        x = torch.rand(1, 3, 8, 8)
        with torch.no_grad():
            assert torch.allclose(model(x), reference(x), atol=1e-6)


# ------------------------------------------------------------------ enhance_image


class TestEnhanceImage:
    @pytest.mark.asyncio
    async def test_identity_model_roundtrips_pixels_and_size(self) -> None:
        import numpy as np

        model_data = {"model": torch.nn.Identity(), "device": torch.device("cpu")}
        img = _solid((10, 128, 250), size=(6, 4))

        out = await enhance_image(model_data, img)

        assert out.size == (6, 4)
        assert out.mode == "RGB"
        # ToTensor /255 -> *255 / uint8 round trip; atol covers float32 truncation
        assert np.allclose(np.array(out), np.array(img), atol=1)

    @pytest.mark.asyncio
    async def test_grayscale_input_is_converted_to_rgb(self) -> None:
        model_data = {"model": torch.nn.Identity(), "device": torch.device("cpu")}
        gray = Image.new("L", (5, 5), 128)

        out = await enhance_image(model_data, gray)

        assert out.mode == "RGB"
        assert out.size == (5, 5)
