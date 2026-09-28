"""Every P1 bake-off graph, built exactly as the runner builds it, validates offline.

The runner sends 344 graphs (312 images + 32 clips) through run._graph. Each one is
checked against the captured v0.37.0 /object_info, so a change to a builder, a case or
the runner that ComfyUI would reject fails here instead of inside a GPU window.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from synthbench.generate.comfy.validate import validate_graph
from synthbench.spikes.p1_bakeoff import run
from synthbench.spikes.p1_bakeoff.plan import clip_jobs, image_jobs

REPO_ROOT = Path(__file__).resolve().parents[5]
SNAPSHOT = REPO_ROOT / "synthbench" / "generate" / "comfy" / "object_info.v0.37.0.json"


def test_every_bakeoff_graph_validates_against_the_snapshot() -> None:
    object_info: dict[str, Any] = json.loads(SNAPSHOT.read_text())
    jobs = image_jobs() + clip_jobs()
    assert len(jobs) == 344
    assert {job.kind for job in jobs} == {"t2i", "edit", "i2v"}
    errors = {}
    for job in jobs:
        uploads = [f"upload-{i}.png" for i, _ in enumerate(job.inputs)]  # names come at run time
        found = validate_graph(run._graph(job, uploads), object_info)
        if found:
            errors[job.output] = found
    assert errors == {}
