"""P1 bake-off job expansion: counts, stage-major order, identity and keyframe wiring."""

from __future__ import annotations

from itertools import groupby
from pathlib import Path

from synthbench.spikes.p1_bakeoff import cases as c
from synthbench.spikes.p1_bakeoff.plan import clip_jobs, image_jobs, keyframe_path, pending


def test_image_job_counts() -> None:
    jobs = image_jobs()
    per_model = len(c.CASES) * len(c.SEEDS) + 1 + len(c.SHOTS) * len(c.LIGHTING)
    assert per_model == 52
    assert len(jobs) == per_model * len(c.T2I_MODELS) == 312


def test_jobs_are_stage_major_so_each_model_loads_once() -> None:
    models = [model for model, _ in groupby(image_jobs(), key=lambda j: j.model)]
    assert models == list(c.T2I_MODELS)


def test_edit_models_edit_their_own_reference_and_others_prompt_it() -> None:
    jobs = image_jobs()
    for model in c.T2I_MODELS:
        identity = [j for j in jobs if j.model == model and j.case == "identity"]
        assert len(identity) == 15
        reference = next(j for j in jobs if j.model == model and j.case == "identity_reference")
        assert jobs.index(reference) < min(jobs.index(j) for j in identity)
        if model in c.EDIT_MODELS:
            assert {j.kind for j in identity} == {"edit"}
            assert {j.inputs for j in identity} == {(reference.output,)}
        else:
            assert {j.kind for j in identity} == {"t2i"}


def test_every_output_path_is_unique() -> None:
    outputs = [j.output for j in image_jobs() + clip_jobs()]
    assert len(outputs) == len(set(outputs))


def test_clip_jobs_use_keyframes_from_the_keyframe_model() -> None:
    jobs = clip_jobs()
    assert len(jobs) == len(c.I2V_MODELS) * len(c.CLIPS) * len(c.CLIP_SEEDS) == 16
    assert {j.inputs[0].split("/")[1] for j in jobs} == {c.KEYFRAME_MODEL}
    assert {j.frames for j in jobs if j.model == "ltx-2.5"} == {c.CLIP_FRAMES["ltx-2.5"]}
    for model in c.I2V_MODELS:
        assert {(j.width, j.height) for j in jobs if j.model == model} == {c.CLIP_SIZES[model]}


def test_clip_sizes_and_frames_fit_each_video_model() -> None:
    assert set(c.CLIP_SIZES) == set(c.CLIP_FRAMES) == set(c.I2V_MODELS)
    assert all(side % 32 == 0 for side in c.CLIP_SIZES["ltx-2.5"])  # the LTX latent grid
    assert (c.CLIP_FRAMES["ltx-2.5"] - 1) % 8 == 0  # LTX-2.5: 8n + 1 frames
    assert (c.CLIP_FRAMES["wan2.2-i2v"] - 1) % 4 == 0  # Wan 2.2: 4n + 1 frames


def test_keyframe_paths() -> None:
    assert keyframe_path("knife") == f"images/{c.KEYFRAME_MODEL}/knife/{c.KEYFRAME_SEED}.png"
    assert keyframe_path("identity:1:day") == f"images/{c.KEYFRAME_MODEL}/identity/1_day.png"


def test_pending_skips_finished_outputs(tmp_path: Path) -> None:
    jobs = image_jobs()[:2]
    done = tmp_path / jobs[0].output
    done.parent.mkdir(parents=True)
    done.write_bytes(b"png")
    assert pending(jobs, tmp_path) == jobs[1:]


def test_every_case_prompt_names_the_security_camera_framing() -> None:
    assert all("security camera" in case.prompt for case in c.CASES)
    plate = next(case for case in c.CASES if case.id == "legible_plate")
    assert plate.ocr_target == "8KXR-417"
    assert "no text" not in plate.prompt  # the plate case must not forbid the text it measures
