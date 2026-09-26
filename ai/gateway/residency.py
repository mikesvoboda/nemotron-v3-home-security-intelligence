"""Triton model residency sets — the rev-6 residency control (Phase 1.4).

Spec rev 6 (owner ruling F11): with one load set left after rev 5, Triton
load control has no job. The gateway keeps --model-control-mode=none, and
residency is decided by **which model directories sit in the repository
when Triton scans it**. The retired models are absent, so they cannot load
— E4's missing residency control, expressed as a file set rather than a
load RPC.

Mechanics (entrypoint step 0d, before Triton starts): the active named set
(``GATEWAY_MODEL_SET``) is resolved from the environment, then
``apply_model_set`` prunes the live repository to it by *moving* excluded
model directories into a sibling staging tree — and moving them back when a
later start selects a wider set. Nothing is deleted, so switching sets is
idempotent and reversible without an image rebuild, which is exactly what
the A5500 bring-up (1.7: "no retired model loads") and any rollback need.

The default is ``full`` — today's complete 14-model repository. That is a
behavior-preserving default on purpose: the shipped default backend (the
nemotron pipeline, unsupported but not yet deleted, R8) still calls the
enrichment models through the gateway, and no CI tier boots a real Triton
container to absorb a surprise shrink. 1.5 flips the backend default to
``vlm`` mode and 1.7 sets ``GATEWAY_MODEL_SET=vlm`` for the A5500 bring-up;
only then does the repository narrow.

This module is import-light on purpose (no yaml, no tritonclient): the
entrypoint calls it as ``python -m ai.gateway.residency`` and the unit tier
imports it directly.
"""

from __future__ import annotations

import argparse
import os
import shutil
from pathlib import Path

# Today's complete Triton model repository — the behavior-preserving
# default. Kept in sync with ai/gateway/main.py ALL_MODELS by test
# (test_residency.TestNamedSets); if they drift, a deployment would serve a
# repository the gateway's own /health does not describe.
FULL_MODEL_SET: tuple[str, ...] = (
    "yolo26",
    "clip",
    "clip_text",
    "florence2",
    "vehicle",
    "fashion_clip",
    "demographics_age",
    "demographics_gender",
    "pet",
    "depth",
    "reid",
    "pose",
    "threat",
    "stgcn_action",
)

# The unconditional members of the `vlm` repository: the YOLO26 gate and the
# resident re-ID specialist (spec §2 Triton row, rev 6).
VLM_MODEL_BASE: tuple[str, ...] = ("yolo26", "reid")

# The optional fourth specialist (D3 rev 6). Task 3b owes the ledgered
# include/not-include call; until then this flag is how it is opted in.
VLM_THREAT_MODEL = "threat"

_TRUTHY = {"1", "true", "yes", "on"}


def get_model_set(name: str, *, threat_enabled: bool = False) -> tuple[str, ...]:
    """The model directories the named set serves.

    Raises:
        KeyError: for an unknown set name — a typo in GATEWAY_MODEL_SET must
            stop the container, not silently serve the wrong footprint.
    """
    if name == "full":
        return FULL_MODEL_SET
    if name == "vlm":
        if threat_enabled:
            return (*VLM_MODEL_BASE, VLM_THREAT_MODEL)
        return VLM_MODEL_BASE
    raise KeyError(f"unknown GATEWAY_MODEL_SET: {name!r} (expected 'vlm' or 'full')")


def resolve_active_set() -> tuple[str, ...]:
    """The set selected by the environment (entrypoint/GATEWAY_MODEL_SET).

    Default ``full``: see the module docstring for why narrowing is an
    explicit selection, not a side effect of this change.
    """
    name = os.getenv("GATEWAY_MODEL_SET", "full").strip().lower()
    threat = os.getenv("GATEWAY_ENABLE_THREAT", "").strip().lower() in _TRUTHY
    return get_model_set(name, threat_enabled=threat)


def apply_model_set(
    repository: Path,
    retired_dir: Path,
    keep: tuple[str, ...],
) -> None:
    """Prune ``repository`` to exactly ``keep``, staging the rest in
    ``retired_dir`` — and promoting previously retired dirs back.

    Only names inside FULL_MODEL_SET are ever moved: a foreign directory is
    not ours to judge. Moves are whole model directories (config.pbtxt +
    version dirs + symlinks), so a promoted model is byte-identical to its
    baked original.
    """
    keep_set = set(keep)
    retired_dir.mkdir(parents=True, exist_ok=True)

    # Retire: live dirs of known models outside the keep set.
    for name in FULL_MODEL_SET:
        live = repository / name
        if name not in keep_set and live.is_dir():
            dest = retired_dir / name
            if dest.exists():
                shutil.rmtree(dest)  # stale copy from an older switch
            shutil.move(str(live), str(dest))

    # Promote: previously retired dirs the keep set wants back.
    for name in keep_set:
        staged = retired_dir / name
        if staged.is_dir():
            dest = repository / name
            if dest.exists():
                shutil.rmtree(staged)  # already live; drop the stale copy
            else:
                shutil.move(str(staged), str(dest))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--repository",
        type=Path,
        default=Path(os.getenv("TRITON_MODEL_REPOSITORY", "/models/repository")),
    )
    parser.add_argument(
        "--retired-dir",
        type=Path,
        default=None,
        help="sibling staging tree (default: <repository>.retired)",
    )
    args = parser.parse_args()
    retired = args.retired_dir or Path(f"{args.repository}.retired")
    keep = resolve_active_set()
    apply_model_set(args.repository, retired, keep)
    print(
        f"[residency] model set={os.getenv('GATEWAY_MODEL_SET', 'full')} "
        f"serving {len(keep)} model(s): {', '.join(sorted(keep))}",
        flush=True,
    )


if __name__ == "__main__":
    main()
