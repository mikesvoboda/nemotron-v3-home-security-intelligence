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

R8 S3 (owner ruling, 2026-09-29): the ``full`` set is RETIRED and there is no
bare-module fallback — an unset GATEWAY_MODEL_SET raises at container start,
the same doctrine as PIPELINE_MODE's hard raise (S1). The fallback had already
stopped mattering to deployments (1.5 flipped the shipped default to ``vlm`` in
docker-compose.prod.yml and .env.example, and compose always passes
``${GATEWAY_MODEL_SET:-vlm}`` — the pair is pinned together in
backend/tests/unit/core/test_gateway_model_set_compose.py); what it kept
serving was the legacy pipeline's "bring the whole repo up" affordance, and R8
deleted the pipeline that needed it. Silence is now treated as what it is: a
misconfigured container, not a deliberate choice.

This module is import-light on purpose (no yaml, no tritonclient): the
entrypoint calls it as ``python -m ai.gateway.residency`` and the unit tier
imports it directly.
"""

from __future__ import annotations

import argparse
import os
import shutil
from pathlib import Path

# The names this deployment manages — what R8 S3 leaves of the 14-model
# rev-6 repository after the legacy prune (goal prompt S3: KEEP
# yolo26/reid/threat or S1's PASS is void). It is no longer a "full" SELECTABLE
# set (ruling 3 retired that name); it is the universe apply_model_set is
# allowed to move, and the list main.py derives ALL_MODELS from so /health can
# never describe a model the repository does not ship. The 11 retired dirs were
# removed with `git rm` in the same slice: apply_model_set only moves names
# inside THIS tuple, so a pruned set over an unpruned repository would have
# made Triton serve the leftovers as foreign directories — the residency trap
# the prune exists to close. Kept in sync with ai/gateway/main.py ALL_MODELS by
# test (test_residency.TestNamedSets).
FULL_MODEL_SET: tuple[str, ...] = (
    "yolo26",
    "reid",
    "threat",
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
            stop the container, not silently serve the wrong footprint. Since
            R8 S3 (owner ruling) ``full`` is in that class too: the name is no
            longer an accepted selection, so an operator who reaches for the
            old "bring everything up" set gets a named refusal instead of a
            repository whose models no longer exist in the image.
    """
    if name == "vlm":
        if threat_enabled:
            return (*VLM_MODEL_BASE, VLM_THREAT_MODEL)
        return VLM_MODEL_BASE
    raise KeyError(f"unknown GATEWAY_MODEL_SET: {name!r} (expected 'vlm')")


def resolve_active_set() -> tuple[str, ...]:
    """The set selected by the environment (entrypoint/GATEWAY_MODEL_SET).

    No default: R8 S3 retired ``full``, and with no default left to fall back
    to, an unset variable is a misconfigured container — it raises through
    ``get_model_set`` (empty name is unknown) rather than serving a surprise
    footprint. Same fail-at-start doctrine as PIPELINE_MODE (S1).
    """
    name = os.getenv("GATEWAY_MODEL_SET", "").strip().lower()
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
        f"[residency] model set={os.getenv('GATEWAY_MODEL_SET', '<unset>')} "
        f"serving {len(keep)} model(s): {', '.join(sorted(keep))}",
        flush=True,
    )


if __name__ == "__main__":
    main()
