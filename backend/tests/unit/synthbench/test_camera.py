"""The camera stage (agent-driven design §7; parent §3.4): size, format, determinism, IR,
lens distortion and the timestamp overlay."""

from __future__ import annotations

import io
import re

import numpy as np
import pytest
from numpy.typing import NDArray
from PIL import Image
from synthbench.generate.camera.model import (
    distort,
    load_params,
    overlay_time,
    render_still,
)

from backend.tests.unit.synthbench import helpers as h

PARAMS = load_params()
SMALL = PARAMS.updated(size=(192, 108))  # the same stage on a small image: fast tests
STAMP = "2026-03-04 10:15:09"


def _decode(jpeg: bytes) -> NDArray[np.int16]:
    with Image.open(io.BytesIO(jpeg)) as image:
        return np.asarray(image.convert("RGB"), dtype=np.int16)


def test_the_default_still_is_a_1920x1080_jpeg() -> None:
    still = render_still(
        h.png(), camera="eave_wide", lighting="day", overlay_text=STAMP, seed=7, params=PARAMS
    )
    with Image.open(io.BytesIO(still)) as image:
        assert (image.format, image.size) == ("JPEG", (1920, 1080))


def test_the_same_inputs_give_the_same_bytes_and_other_seeds_differ() -> None:
    first = render_still(
        h.png(),
        camera="doorbell_fisheye",
        lighting="dusk",
        overlay_text=STAMP,
        seed=1,
        params=SMALL,
    )
    again = render_still(
        h.png(),
        camera="doorbell_fisheye",
        lighting="dusk",
        overlay_text=STAMP,
        seed=1,
        params=SMALL,
    )
    other = render_still(
        h.png(),
        camera="doorbell_fisheye",
        lighting="dusk",
        overlay_text=STAMP,
        seed=2,
        params=SMALL,
    )
    assert first == again
    assert first != other


def test_ir_night_is_grey() -> None:
    red = h.png(color=(200, 40, 40))
    night = _decode(
        render_still(
            red, camera="eave_wide", lighting="ir_night", overlay_text="", seed=3, params=SMALL
        )
    )
    day = _decode(
        render_still(red, camera="eave_wide", lighting="day", overlay_text="", seed=3, params=SMALL)
    )
    assert np.abs(night[..., 0] - night[..., 1]).max() <= 3
    assert np.abs(day[..., 0] - day[..., 1]).mean() > 50


def test_distortion_magnifies_the_centre_and_keeps_k_0_as_is() -> None:
    pixels = np.zeros((101, 201, 3), dtype=np.float32)
    pixels[50, 150] = 255.0  # halfway between the centre (x=100) and the right edge
    out = distort(pixels, 0.3)
    _ys, xs = np.nonzero(out[..., 0] > 20)
    assert xs.min() > 150  # pushed outward: barrel distortion magnifies the centre
    assert distort(pixels, 0.0) is pixels


def test_the_overlay_draws_only_in_the_top_left() -> None:
    plain = _decode(
        render_still(
            h.png(), camera="pole_lot", lighting="day", overlay_text="", seed=5, params=PARAMS
        )
    )
    stamped = _decode(
        render_still(
            h.png(), camera="pole_lot", lighting="day", overlay_text=STAMP, seed=5, params=PARAMS
        )
    )
    ys, xs = np.nonzero(np.abs(stamped - plain).sum(axis=2) > 60)
    assert len(ys) > 0
    assert ys.max() < 120
    assert xs.max() < 700


def test_the_default_parameters_cover_the_taxonomy() -> None:
    assert {camera.id for camera in h.TAX.cameras} <= set(PARAMS.distortion)
    assert {light.id for light in h.TAX.lighting} <= set(PARAMS.noise_sigma)
    assert set(PARAMS.ir_lighting) <= {light.id for light in h.TAX.lighting}
    assert PARAMS.id == "default-v1"


def test_an_unknown_camera_is_refused() -> None:
    with pytest.raises(ValueError, match="cover no camera"):
        render_still(h.png(), camera="drone", lighting="day", overlay_text="", seed=1, params=SMALL)


def test_overlay_times_keep_the_scene_time_and_put_snow_in_winter() -> None:
    stamp = overlay_time("20:15", "clear", 9)
    assert re.fullmatch(r"2026-\d\d-\d\d 20:15:\d\d", stamp)
    assert stamp == overlay_time("20:15", "clear", 9)
    assert {overlay_time("07:00", "snow", seed)[5:7] for seed in range(50)} <= {"12", "01", "02"}
