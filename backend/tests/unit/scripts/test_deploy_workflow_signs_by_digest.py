"""Main-green slice 2: SBOM & Sign must sign the manifest that was actually pushed.

``SBOM & Sign`` has been red on every deploy-tier push — measured at heads
``18339acd`` and ``67ca4870``, failing step ``Sign container image``, same
message modulo the SHA::

    Error: signing [.../frontend:67ca48707b6110e38e6b1ecf3b5f142de9f82972]:
    accessing entity: entity not found in registry, error:
    GET .../frontend/manifests/67ca48707b...: MANIFEST_UNKNOWN: manifest unknown

Not a secret and not a permission (the step's own ``:latest`` sign reaches
``Signing artifact…`` cleanly and ``id-token: write`` is already granted):
the tag simply was never pushed. ``merge-core`` pushes its manifest list
with tags from ``docker/metadata-action`` ``type=sha,prefix=``, whose
default is the **7-char short** SHA — measured in that job's own log at
``67ca4870`` (run ``36774195879``, job ``110089046513``): the only image
tags anywhere in it are ``frontend:latest`` and ``frontend:67ca487``. The
sign step then signs ``:latest`` (fine) plus ``:${{ github.sha }}`` — 40
chars — a manifest that exists nowhere. The matrix's ``(backend)`` sibling
shows ``cancelled``: fail-fast of this same one bug, not a second bug.

The durable fix is to sign **by digest**. cosign v4.1.2 warns inside the
very failing job's downloaded log that a tag "uses a tag, not a digest, to
identify the image to sign" and signing "images by tag will be removed in a
future release". A cosign signature attaches to a manifest digest either
way — signing a tag only records which digest the resolver happened to
pick — so one digest sign covers every tag (``latest``, the short sha, any
future tag). Resolving the digest with ``docker buildx imagetools inspect
--format '{{json .Manifest}}' | jq -r '.digest'`` is this repo's own
shipped pattern (``.github/workflows/rollback.yml:97``) and was verified
working from a sandbox against the live registry.

These guards parse the workflow rather than grep it and were SEEN RED at
main tip (3 failed) before the deploy.yml edits. needs-target regression
for this file is already guarded by
``test_deploy_workflow_retired_ai_images.py::test_needs_targets_exist`` —
not duplicated here.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[4]
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "deploy.yml"

# cosign takes exactly one subject reference: the last token of its command
# line. Line continuations (`` \\\n``) are joined first so multi-line
# attest commands parse as one command.
_COSIGN_CMD_RE = re.compile(r"^\s*(cosign\s+(?:sign|attest)\b.*\S)\s*$", re.M)


def _cosign_refs(workflow: dict) -> list[tuple[str, str]]:
    """(job/step, subject reference) for every cosign sign/attest command."""
    out = []
    for job_id, job in workflow["jobs"].items():
        for step in job.get("steps") or []:
            run = re.sub(r"\\\n\s*", " ", str(step.get("run") or ""))
            for cmd in _COSIGN_CMD_RE.findall(run):
                out.append((f"{job_id}/{step.get('name', '?')}", cmd.split()[-1]))
    return out


@pytest.fixture(scope="module")
def workflow() -> dict:
    return yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))


def test_every_cosign_reference_is_a_canonical_digest(workflow: dict) -> None:
    """cosign must point at ``name@sha256:…`` (or a resolved digest output).

    The bug's shape: sign ``:latest`` plus ``:${{ github.sha }}``. The
    full-sha tag was never pushed — merge-core's metadata-action
    ``type=sha`` default is the 7-char short sha — so the second sign died
    MANIFEST_UNKNOWN and fail-fast cancelled the backend sibling.
    """
    refs = _cosign_refs(workflow)
    assert refs, "fixture broke: no cosign sign/attest commands found"
    offenders = [f"{where}: {ref}" for where, ref in refs if "@" not in ref]
    assert not offenders, (
        "cosign signs bare tags, but the pushed tags are latest + SHORT sha "
        f"(metadata-action type=sha default), so tag refs are luck at best: {offenders}"
    )


def test_signing_job_resolves_the_pushed_digest(workflow: dict) -> None:
    """A cosign-bearing job must RESOLVE the digest it signs, in-job.

    ``docker buildx imagetools inspect … --format '{{json .Manifest}}'`` is
    the shipped pattern (.github/workflows/rollback.yml:97). Without a
    resolution step the refs can only be tags — which is exactly how every
    deploy has been red since before R8.
    """
    offenders = []
    for job_id, job in workflow["jobs"].items():
        steps = job.get("steps") or []
        runs = [str(s.get("run") or "") for s in steps]
        if not any(re.search(r"cosign\s+(sign|attest)\b", r) for r in runs):
            continue
        if not any(
            ("imagetools inspect" in r) or ("DOCKER_METADATA_OUTPUT_JSON" in r) for r in runs
        ):
            offenders.append(job_id)
    assert not offenders, f"jobs run cosign without resolving the pushed digest: {offenders}"


def test_summary_does_not_claim_unpushed_tags(workflow: dict) -> None:
    """The deployment summary must not advertise `Tags: latest, <full sha>`.

    The registry carries ``latest`` + the 7-char short sha (measured in
    merge-core's own job log); the echo repeated the false claim the sign
    step died on, so the next reader of a run summary trusts a tag that
    ``docker pull`` cannot fetch.
    """
    offenders = {
        f"{job_id}/{step.get('name', '?')}"
        for job_id, job in workflow["jobs"].items()
        for step in job.get("steps") or []
        if "Tags: latest, ${{ github.sha }}" in str(step.get("run") or "")
    }
    assert not offenders, (
        "the workflow echoes 'Tags: latest, ${{ github.sha }}' but "
        f"merge-core never pushes that tag: {sorted(offenders)}"
    )
