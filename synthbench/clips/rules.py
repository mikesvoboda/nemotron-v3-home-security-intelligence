"""The motion rules `clip check` enforces (clips design §3.2, ruling H3-R20).

A motion passes the still prompt rules 1-4 (each subject and prop named with a taxonomy term,
no blocklisted phrase, at most 1200 characters, no clock times) and rule 5: the camera never
moves and the shot never cuts. check appends CLIP_SUFFIX, as it appends CAMERA_SUFFIX to stills.
"""

from __future__ import annotations

import hashlib
from functools import cache
from pathlib import Path

import yaml

from synthbench.contract.clip import ClipSpec
from synthbench.prompt import rules
from synthbench.taxonomy.model import Taxonomy

CAMERA_MOVES_FILE = rules.BLOCKLIST_FILE.parent / "camera_moves.yaml"


@cache
def camera_moves(path: Path = CAMERA_MOVES_FILE) -> tuple[str, ...]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or set(data) != {"camera_moves"}:
        raise ValueError(f"{path}: expected one key, camera_moves")
    return tuple(str(phrase).lower() for phrase in data["camera_moves"])


def clip_problems(spec: ClipSpec, motion: str, tax: Taxonomy) -> list[str]:
    """Every rule the motion breaks for this clip, one line each; empty when it passes."""
    found = rules.problems(spec, motion, tax)
    found += [
        f"rule 5: remove '{phrase}' (the camera never moves and the shot never cuts)"
        for phrase in camera_moves()
        if rules.contains_phrase(motion, phrase)
    ]
    return found


def motion_text(spec: ClipSpec) -> str:
    """Exactly what H3 receives: the frozen motion, then the clip suffix."""
    if spec.prompt is None or spec.clip_suffix is None:
        raise ValueError(f"{spec.event_id} has no frozen motion")
    return f"{spec.prompt} {spec.clip_suffix}"


def motion_sha256(spec: ClipSpec) -> str:
    return hashlib.sha256(motion_text(spec).encode()).hexdigest()
