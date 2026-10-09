"""O1.9 (D12): ``:latest`` is a promise that the smoke test passed, so it must not exist before it.

``merge-core`` pushes each multi-arch manifest tagged ``latest`` plus
metadata-action's short sha (`deploy.yml:148-150` at ``acfe5b56``), and
``smoke-test`` runs AFTER that — ``needs: merge-core`` — pulling ``:latest``
itself (`deploy.yml:189-190`, ``IMAGE_TAG: latest`` at 196). Measured at run
``37726762316``, head ``acfe5b56``: the manifests were already live while the
run's only red job was the smoke test, so every consumer of ``:latest`` —
the then-shipped prebuilt-image compose stack (its ``IMAGE_TAG`` defaulted to
``latest``; O1.2 has since retired that file) and the operator's documented
pull path (the deployment runbook's ``export IMAGE_TAG=latest``, since
rewritten with the rest of the GHCR section) —
resolved images the pipeline had just declared broken. "Deploy is red" and "the
images everyone pulls are broken" are the same fact, and the louder half
(the red run) was the one nobody acted on.

Plan box 2 — "Publish ``:latest`` only after the smoke test passes, testing the
per-commit tag instead" — reorders the tier:

* ``merge-core`` publishes the immutable per-commit tag only (metadata-action's
  short sha, which it already pushes);
* ``smoke-test`` boots THAT tag, so the artifact under test is the one this
  commit built rather than a moving pointer that a later push can swap under it;
* a ``publish-latest`` job moves the pointer only after the smoke test passes.
  Supply-chain jobs sign/attest BY DIGEST (guarded in
  ``test_deploy_workflow_signs_by_digest.py``), so they key off the per-commit
  manifest and need no dependency on the pointer.

These guards parse the workflow (``yaml.safe_load``) rather than grep it, and
were written RED against ``acfe5b56``.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[4]
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "deploy.yml"
# The plan keeps this package's edits inside deploy.yml; the compose file is the
# other half of the IMAGE_TAG seam and is read for the guard below.
COMPOSE_CI = REPO_ROOT / "docker-compose.ci.yml"


@pytest.fixture(scope="module")
def jobs() -> dict:
    return yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))["jobs"]


def _needs(job: dict) -> set[str]:
    needs = job.get("needs")
    if isinstance(needs, str):
        return {needs}
    if isinstance(needs, dict):
        return set(needs)
    return set(needs or [])


def _runs(job: dict) -> str:
    return "\n".join(str(s.get("run") or "") for s in job.get("steps") or [])


def _metadata_tags(job: dict) -> list[str]:
    """The ``tags:`` block of the job's docker/metadata-action step, if any."""
    for step in job.get("steps") or []:
        uses = str(step.get("uses") or "")
        if uses.startswith("docker/metadata-action@"):
            raw = ((step.get("with") or {}).get("tags")) or ""
            return [line.strip() for line in str(raw).splitlines() if line.strip()]
    return []


# Full-line shell comments, and shell line continuations.
_COMMENT_LINE = re.compile(r"^[ \t]*#.*$", re.M)
_CONTINUATION = re.compile(r"\\\n[ \t]*")


def _commands(job: dict) -> str:
    """Runnable shell only — comments stripped, continuations joined.

    These guards decide what a job DOES, and comments quote the tags a job no
    longer uses. Matching prose makes a guard lie: the first draft of this file
    flagged ``merge-core`` as a ``:latest`` mover purely because its comment
    reads ":latest is not tagged here any more". Measure commands.
    """
    return _CONTINUATION.sub(" ", _COMMENT_LINE.sub("", _runs(job)))


def _step_env(job: dict) -> str:
    """Every step's ``env:`` map, flattened. IMAGE_TAG lives HERE, not in run:.

    A guard that only reads ``run:`` would pass forever against the old
    ``IMAGE_TAG: latest`` — the pre-fix state it is meant to catch. The first
    draft had exactly that hole.
    """
    return "\n".join(
        f"{k}={v}" for step in (job.get("steps") or []) for k, v in (step.get("env") or {}).items()
    )


def _acts_on(job: dict) -> str:
    """Everything a job can act on with an image: commands, step env, action inputs.

    ``anchore/sbom-action`` takes its image as a ``with: image:`` input
    (deploy.yml's SBOM step) and the smoke test gets its tag from a step ``env:``
    block — reading ``run:`` alone misses both, and both are exactly the
    pre-fix sites these guards exist to catch.
    """
    inputs = "\n".join(
        f"{k}={v}" for step in (job.get("steps") or []) for k, v in (step.get("with") or {}).items()
    )
    return "\n".join([_commands(job), _step_env(job), inputs])


def _moves_latest(job: dict) -> bool:
    """True if this job's COMMANDS retag something to ``:latest``.

    Both halves are needed and both are read from commands: ``docker tag`` /
    ``buildx imagetools create`` names the retag operation, ``:latest`` names
    the target. Neither half alone identifies a mover (inspecting :latest is not
    moving it; tagging is not necessarily the pointer).
    """
    commands = _commands(job)
    return bool(
        re.search(r"(docker tag|imagetools create)\b", commands)
        and re.search(r"[^\s]:latest", commands)
    )


def test_merge_core_does_not_publish_latest(jobs: dict) -> None:
    """Nothing may tag ``:latest`` before the smoke test has run.

    ``latest`` is the tag an operator's runbook or manual pull follows by
    default, so publishing it pre-smoke advertises an unvalidated build as the
    current one.
    """
    offenders = {
        job_id
        for job_id, job in jobs.items()
        if any("value=latest" in tag for tag in _metadata_tags(job))
    }
    assert not offenders, (
        f"jobs still tag :latest from metadata-action: {sorted(offenders)} — the "
        "pointer must move only after smoke-test passes (O1.9 box 2)"
    )


def test_smoke_test_uses_the_per_commit_tag(jobs: dict) -> None:
    """The smoke test tests THIS commit, not whatever ``latest`` happens to point at.

    A moving tag makes a red smoke test ambiguous: it could be this commit or a
    later one that repointed ``latest`` mid-run. The immutable short-sha tag
    removes the ambiguity, and it is the tag merge-core actually pushes
    (``type=sha,prefix=`` → 7-char short sha — the fact that killed cosign's
    tag-based signing, see test_deploy_workflow_signs_by_digest.py).
    """
    smoke = jobs.get("smoke-test") or {}
    assert _runs(smoke), "no smoke-test job to inspect"
    assert "${GITHUB_SHA::7}" in _commands(smoke), (
        "smoke-test must derive the per-commit tag from GITHUB_SHA in shell — "
        "GitHub expressions have no substring function, so a workflow-level "
        f"IMAGE_TAG cannot carry the 7-char tag:\n{_commands(smoke)[:700]}"
    )
    assert "IMAGE_TAG=latest" not in _step_env(smoke), (
        f"smoke-test still boots IMAGE_TAG=latest, testing a moving pointer: {_step_env(smoke)}"
    )
    assert ":latest" not in _acts_on(smoke), (
        f"smoke-test still names :latest somewhere: {_acts_on(smoke)[:700]}"
    )


def test_latest_publish_waits_for_the_smoke_test(jobs: dict) -> None:
    """Whichever job moves ``:latest`` must depend on ``smoke-test``.

    Commands only (see ``_commands``/``_moves_latest``): prose points both ways.
    The pre-fix workflow tagged ``:latest`` with no comment saying so, and the
    fixed workflow comments about ``:latest`` while NOT tagging it — the first
    draft of this file flagged ``merge-core`` as a mover purely on its comment.
    """
    movers = [job_id for job_id, job in jobs.items() if _moves_latest(job)]
    assert movers, (
        "no job moves the :latest pointer at all: O1.9 box 2 says publish it "
        "AFTER the smoke test, not never (that would be O1.2's removal, not this)"
    )
    for job_id in movers:
        assert "smoke-test" in _needs(jobs[job_id]), (
            f"{job_id} moves :latest but does not need smoke-test — publishing "
            "the current-image pointer before validation is D12's second half"
        )


def test_supply_chain_jobs_do_not_wait_for_the_pointer(jobs: dict) -> None:
    """Sign/SBOM/provenance key off the per-commit manifest, not ``:latest``.

    They sign by digest (guarded in test_deploy_workflow_signs_by_digest.py); if
    they resolved that digest — or scanned, in the SBOM action's case — through
    ``:latest`` they would race the pointer move, and since box 2 the pointer
    legitimately names the PREVIOUS commit while they run. Checked over
    commands, step env AND action inputs: the SBOM step's image is a ``with:``
    input, invisible to a run-block-only scan.
    """
    offenders = {
        job_id
        for job_id, job in jobs.items()
        if job_id.startswith(("sbom", "slsa")) and ":latest" in _acts_on(job)
    }
    assert not offenders, (
        f"supply-chain jobs name :latest, which since O1.9 lags the build: "
        f"{sorted(offenders)} — the failable input is a with.image or an inspect "
        "argument, not the prose explaining why it isn't one"
    )


def test_overlapping_pushes_serialize_behind_the_pointer() -> None:
    """:latest must be moved by at most one Deploy at a time.

    The self-review (finding 10) named the race box 2 leaves open: two pushes
    to main minutes apart run smoke→publish independently, and the SLOWER run —
    carrying the OLDER commit — can finish last and re-tag ``:latest`` to the
    superseded digest. The guards above say who may move the pointer and when;
    only a workflow-level ``concurrency`` group says how often. Queueing, not
    cancelling: killing a run between ``merge-core``'s push and the pointer
    move is how half-published state is born (the called-workflow caller-group
    trap at the top of trivy.yml is why the group must be STATIC here —
    deploy.yml is trigger-direct, so ``github.workflow`` renders its own name,
    and a per-run group would guard nothing).
    """
    doc = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    conc = doc.get("concurrency")
    assert isinstance(conc, dict), (
        "deploy.yml has no workflow-level concurrency — overlapping main "
        "pushes interleave smoke→publish and an older digest can win :latest"
    )
    assert conc.get("group"), "the concurrency block needs a group name"
    assert conc.get("cancel-in-progress") is False, (
        "cancel-in-progress must be FALSE: a queued push waits, a cancelled one can die mid-publish"
    )


def test_the_ci_compose_still_defaults_to_latest() -> None:
    """The compose file's own default is untouched — deploy.yml passes IMAGE_TAG.

    Pinned deliberately: if someone "fixes" the compose default to empty, every
    local run breaks and the workflow's per-commit tag silently stops applying.
    """
    doc = yaml.safe_load(COMPOSE_CI.read_text(encoding="utf-8"))
    backend_image = doc["services"]["backend"]["image"]
    assert "${IMAGE_TAG:-latest}" in backend_image, (
        f"docker-compose.ci.yml backend image changed shape: {backend_image}"
    )
