"""Guard: R8-S3 retired hostnames and dead dispatch branches must leave the tree.

Row 61 (ledger 2026-10-01) closed slice 7 of the main-green plan: the residue
the 2026-09-30 evidence doc verified but no slice had owned.

Red-first evidence (measured against HEAD ``67ca4870`` before any fix):
    uv run pytest backend/tests/unit/scripts/test_main_green_residue.py -q
        -> 4 failed, 2 passed
The four reds are the four live residues: the ``instances`` list in
``scripts/seed-events.py`` still naming the deleted ``ai-florence:8092``
container (line 5674 at HEAD), the three retired image-size keys in
``setup_lib/image_pull.py`` ``estimate_pull_size`` (lines 220-222 at HEAD), the
loose past-tense claim in
``data/ai-pipeline-evaluation/04-fastapi-backend-evaluation.md`` section 14
(naming the nonexistent ``backend/services/clip_client.py``), and the four
unreachable model-download branches in ``setup_lib/model_downloader.py``
(lines ~1039-1070 at HEAD) whose models.yml rows R8 S3 deleted (owner rulings
1/4/5 — models.yml is owner-owned and untouched here).

Why each branch is unreachable and why the guard pins it this way:
``prompt_and_download_models`` dispatches on ``model.download_method or
model.name`` over rows parsed from models.yml (``build_model_specs``), and the
live models.yml carries no row selecting ``nemotron_gguf``, ``stgcn``,
``yolo_world``, or ``hf_cache``/``fashion-clip``/``marqo-fashionSigLIP``. The
guard pins the two edits actually made — the handler ``def``s and the dispatch
branches deleted, functions kept if a ruling names them — checked by string
presence, not behaviour, so a comment that merely names a retired path cannot
redden it while a resurrected branch does; models.yml stays the behavioural
authority. The two greens are forward guards (yolo26's size key and the live
handlers must survive any future sweep of the same shape).
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]

RETIRED_HOSTNAMES = ("ai-florence", "ai-clip", "ai-enrichment")


def _read(relative_path: str) -> str:
    return (REPO_ROOT / relative_path).read_text(encoding="utf-8")


class TestSeedEventsInstances:
    """scripts/seed-events.py:5674 seeded fake alerts against a deleted container."""

    def test_instances_list_has_no_retired_hostnames(self) -> None:
        source = _read("scripts/seed-events.py")
        instances_lines = [
            line for line in source.splitlines() if re.search(r"instances\s*=\s*\[", line)
        ]
        assert instances_lines, "seed-events.py lost its alert `instances` list entirely"
        for line in instances_lines:
            for retired in RETIRED_HOSTNAMES:
                assert retired not in line, (
                    f"instances list still names retired {retired!r}: {line}"
                )


class TestImagePullSizeEstimates:
    """setup_lib/image_pull.py:220-222 carried size keys for retired images."""

    def test_size_estimates_drop_retired_images(self) -> None:
        from setup_lib.image_pull import estimate_pull_size

        total = estimate_pull_size(
            [
                "ghcr.io/example/ai-florence:latest",
                "ghcr.io/example/ai-clip:latest",
                "ghcr.io/example/ai-enrichment:latest",
            ]
        )
        # Retired keys are gone, so all three fall to the 200 MB unknown-image
        # default (600 MB = "~600 MB"); when the retired keys are present the
        # estimate reads "~18 GB".
        assert total == "~600 MB", f"retired images still size above unknown-image default: {total}"

    def test_yolo26_size_key_survives(self) -> None:
        from setup_lib.image_pull import estimate_pull_size

        total = estimate_pull_size(["ghcr.io/example/ai-yolo26:latest"])
        assert total == "~7.8 GB", (
            f"ai-yolo26 (still kept per owner ruling) must size at 8000 MB: {total}"
        )


class TestEvaluationDocClaim:
    """Section 14 described clip_client.py — a file R8 deleted — as live."""

    def test_section_14_is_past_tense(self) -> None:
        doc = _read("data/ai-pipeline-evaluation/04-fastapi-backend-evaluation.md")
        section = doc.split("### 14.", 1)
        assert len(section) == 2, "section 14 vanished from the evaluation doc"
        body = section[1].split("### 15.", 1)[0]
        assert "The file `backend/services/clip_client.py` has unresolved" not in body, (
            "section 14 still asserts the conflict markers are live in a file that no longer exists"
        )


class TestModelDownloaderDispatch:
    """The four dispatch branches whose models.yml rows R8 S3 deleted."""

    RETIRED_BRANCHES = (
        "download_nemotron_gguf",
        "download_stgcnpp",
        "download_yolo_world",
        "download_marqo_fashionsiglip",
    )

    def test_retired_handlers_are_gone(self) -> None:
        source = _read("setup_lib/model_downloader.py")
        for name in self.RETIRED_BRANCHES:
            assert f"def {name}(" not in source, f"{name}() handler still defined"
            assert f"{name}(" not in source, f"{name}() still referenced (dispatch or call site)"

    def test_live_handlers_survive(self) -> None:
        source = _read("setup_lib/model_downloader.py")
        for name in ("download_yolo26_models", "download_osnet_reid", "download_yolov8n_pose"):
            assert f"def {name}(" in source, f"live handler {name}() must not be deleted"
