"""Expand the P1 cases into jobs, stage-major (each model's jobs are contiguous)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from synthbench.spikes.p1_bakeoff import cases as c


@dataclass(frozen=True)
class Job:
    model: str
    kind: str  # "t2i" | "edit" | "i2v"
    case: str
    seed: int
    prompt: str
    width: int
    height: int
    output: str  # relative to the bake-off root
    inputs: tuple[str, ...] = ()
    frames: int = 0


def image_jobs() -> list[Job]:
    jobs: list[Job] = []
    for model in c.T2I_MODELS:
        width, height = c.MODEL_SIZES[model]
        for case in c.CASES:
            for seed in c.SEEDS:
                out = f"images/{model}/{case.id}/{seed}.png"
                jobs.append(Job(model, "t2i", case.id, seed, case.prompt, width, height, out))
        reference = f"images/{model}/identity/reference.png"
        jobs.append(
            Job(
                model,
                "t2i",
                "identity_reference",
                c.SEEDS[0],
                c.IDENTITY_REFERENCE,
                width,
                height,
                reference,
            )
        )
        for index, shot in enumerate(c.SHOTS):
            for lighting in c.LIGHTING:
                out = f"images/{model}/identity/{index}_{lighting}.png"
                if model in c.EDIT_MODELS:
                    prompt = c.identity_edit_prompt(shot, lighting)
                    jobs.append(
                        Job(
                            model,
                            "edit",
                            "identity",
                            c.SEEDS[0],
                            prompt,
                            width,
                            height,
                            out,
                            inputs=(reference,),
                        )
                    )
                else:
                    prompt = c.identity_t2i_prompt(shot, lighting)
                    jobs.append(
                        Job(model, "t2i", "identity", c.SEEDS[0], prompt, width, height, out)
                    )
    return jobs


def keyframe_path(ref: str) -> str:
    if ref.startswith("identity:"):
        _, shot, lighting = ref.split(":")
        return f"images/{c.KEYFRAME_MODEL}/identity/{shot}_{lighting}.png"
    return f"images/{c.KEYFRAME_MODEL}/{ref}/{c.KEYFRAME_SEED}.png"


def clip_jobs() -> list[Job]:
    jobs: list[Job] = []
    for model in c.I2V_MODELS:
        width, height = c.CLIP_SIZES[model]
        for clip in c.CLIPS:
            for seed in c.CLIP_SEEDS:
                jobs.append(
                    Job(
                        model,
                        "i2v",
                        clip.id,
                        seed,
                        clip.motion,
                        width,
                        height,
                        f"clips/{model}/{clip.id}/{seed}.mp4",
                        inputs=(keyframe_path(clip.keyframe),),
                        frames=c.CLIP_FRAMES[model],
                    )
                )
    return jobs


def pending(jobs: list[Job], root: Path) -> list[Job]:
    return [job for job in jobs if not (root / job.output).exists()]
