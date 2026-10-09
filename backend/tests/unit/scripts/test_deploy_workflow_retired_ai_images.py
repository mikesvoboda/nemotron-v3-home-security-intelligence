"""R8 follow-up: deploy.yml must not build, merge, sign or attest retired AI images.

R8 S3 deleted ``ai/florence``, ``ai/clip`` and ``ai/enrichment`` (commit
``3b73b9b6``, the owner's S3 ruling covered all three serving trees), but
``.github/workflows/deploy.yml`` kept building them. Every push to main since
has run ``Build ai-florence``/``Build ai-clip``/``Build ai-enrichment`` to
``lstat ai/florence: no such file or directory`` — measured, not inferred:
the last pre-S3 deploy run (head ``18339acd``, 2026-09-30T00:06Z) had all
three builds green; the first post-S3 run (head ``c69add19``, 07:00Z) has
exactly those three failing. The downstream ``needs: [merge-core, merge-ai]``
wiring then drags SBOM, staging and provenance along a job chain that can
never fully succeed, and ``Rollback to Stable Images`` fires on every push.

These tests parse the workflow (not grep it) so the guard survives
reformatting, and they are forward-looking:

1. no retired image name may appear in ANY matrix (build or consumer);
2. every ``dockerfile`` a build matrix names must exist in the tree — that
   is the general form of the bug, and it reds today;
3. every consumer list (merge/sbom/provenance) must be a subset of what the
   build matrices actually produce;
4. every ``needs:`` target must be a job that exists in the file — cutting a
   job without rewiring is how the next person reintroduces the outage.

What stays deliberately UNFIXED here (report-only, ledger item 56): the ghcr
compose pulls ``ai-gateway`` (and should also carry ``ai-vlm``) while
deploy.yml publishes neither — that publish gap is an owner adjudication,
not something this guard forces.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[4]
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "deploy.yml"

# Serving trees R8 deleted (S2: ai-llm; S3: florence/clip/enrichment; and
# yolo26's image retired earlier — the ai-yolo26-image archive tree). A name here
# must not survive in any matrix, only in comments explaining its deletion.
RETIRED_IMAGE_NAMES = {
    "ai-florence",
    "ai-clip",
    "ai-enrichment",
    "ai-llm",
    "ai-yolo26",
}


@pytest.fixture(scope="module")
def jobs() -> dict:
    workflow = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    return workflow["jobs"]


def _matrix_images(job: dict) -> list:
    """Image entries of a job's matrix, normalized to (name, dockerfile|None)."""
    matrix = (job.get("strategy") or {}).get("matrix") or {}
    images = matrix.get("image") or []
    out = []
    for entry in images:
        if isinstance(entry, dict):
            out.append((entry.get("name"), entry.get("dockerfile")))
        else:
            out.append((entry, None))
    return out


def _build_produced(jobs: dict) -> set:
    return {
        name
        for job_id, job in jobs.items()
        if job_id.startswith("build-")
        for name, _ in _matrix_images(job)
    }


def test_no_retired_image_names_in_any_matrix(jobs: dict) -> None:
    offenders = {
        f"{job_id}:{name}"
        for job_id, job in jobs.items()
        for name, _ in _matrix_images(job)
        if name in RETIRED_IMAGE_NAMES
    }
    assert not offenders, (
        "deploy.yml still references R8-retired images — their trees are "
        f"deleted and every main push will red: {sorted(offenders)}"
    )


def test_every_build_matrix_dockerfile_exists(jobs: dict) -> None:
    missing = [
        dockerfile
        for job_id, job in jobs.items()
        if job_id.startswith("build-")
        for _, dockerfile in _matrix_images(job)
        if dockerfile and not (REPO_ROOT / dockerfile).is_file()
    ]
    assert not missing, (
        "build matrix names Dockerfiles that are not in the tree "
        f"(buildx will fail with lstat ... no such file): {missing}"
    )


def test_consumer_lists_are_subset_of_built_images(jobs: dict) -> None:
    built = _build_produced(jobs)
    orphans = {
        f"{job_id}:{name}"
        for job_id, job in jobs.items()
        if job_id.startswith(("merge-", "sbom", "slsa"))
        for name, _ in _matrix_images(job)
        if name not in built
    }
    assert not orphans, (
        "merge/SBOM/provenance matrices list images no build job produces "
        f"(nothing to merge/sign/attest): {sorted(orphans)}"
    )


def test_needs_targets_exist(jobs: dict) -> None:
    broken = {
        f"{job_id} -> {dep}"
        for job_id, job in jobs.items()
        for dep in (
            job["needs"]
            if isinstance(job.get("needs"), list)
            else [job["needs"]]
            if job.get("needs")
            else []
        )
        if dep not in jobs
    }
    assert not broken, f"jobs wait on needs targets that do not exist in the file: {sorted(broken)}"
