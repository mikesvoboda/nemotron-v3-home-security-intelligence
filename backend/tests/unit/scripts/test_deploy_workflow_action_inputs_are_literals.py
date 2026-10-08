"""O1.9 (self-review finding, head ``e0d3bca8``): ``${GITHUB_SHA::7}`` in an action INPUT stays a literal.

A workflow file stacks two interpreters. GitHub substitutes ``${{ … }}``
contexts wherever the YAML is read; bash expands ``${VAR::7}`` ONLY inside a
``run:`` block, because that is the only place a shell exists. A ``with:``
input gets the first and never the second — the action receives the
characters ``${GITHUB_SHA::7}`` verbatim, 16 of them, as a tag.

The consequence was reproduced end to end: ``sbom-and-sign``'s
``Generate SBOM`` step passed that literal to ``anchore/sbom-action``, the
action splices ``input.image`` into syft's argv unquoted, and syft 1.54.0
(the version that step's own log resolves), fed the bare ``name:tag`` exactly
as the action passes it, answered::

    oci-model: failed to parse reference … could not parse reference

— exit 1, 0-byte SBOM, on the exact run whose greenness is O1.9's Done-when.
Same failure class as the 40-vs-7-char tag bug the ``deploy.yml`` header
comment and ``test_deploy_workflow_signs_by_digest.py`` exist to prevent,
wearing shell clothes; ``actionlint`` cannot see it because it never
type-checks third-party action inputs (measured: the documented
``docker run … rhysd/actionlint`` command reports only main's pre-existing
``build-base-image.yml:70`` finding on both trees).

The repo already models the correct shape twice — derive in ``run:``, hand
the value over as output or env: ``smoke-test``'s ``Pull images`` step
exports ``TAG`` via ``$GITHUB_ENV``, and ``slsa-provenance``'s ``id:
digest`` step exports ``digest`` via ``$GITHUB_OUTPUT`` (step names, not
line numbers — this file's own lesson is that insertions move lines).
The fix follows them: a
``short-sha`` step exports the tag, ``with: image:`` interpolates it.

Both ``with:`` inputs and ``env:`` values are guarded, because both are
non-shell consumers: an ``env: FOO: ${GITHUB_SHA::7}`` would put the literal
in ``$FOO`` too. Two legitimate single-brace shapes are excluded BY NAME,
not by luck:

* ``${{ … }}`` — GitHub's own syntax (the regex requires a non-``{`` right
  after ``${``, so ``{{`` cannot match);
* JavaScript template literals in an action's script field
  (``actions/github-script``'s ``with: script``), which the action evaluates
  itself — listed in ``SCRIPT_FIELDS``. A sweep of all 39 workflows finds
  single-brace ``${`` inside a ``with:`` only inside those script bodies,
  except the one site this package fixes.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[4]
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "deploy.yml"

# ${NAME}, ${NAME:-def}, ${NAME::7}, ${#NAME}. (?!\{) rejects GitHub's own
# ${{ }} — a brace directly after ${ is context syntax, not shell.
SHELL_PARAM = re.compile(r"\$\{(?!{)")

# with: fields whose value is code the ACTION runs (JS template literals are
# legitimate there). Anything else holding ${ is a string the action will use raw.
SCRIPT_FIELDS = {"script", "scripts"}


@pytest.fixture(scope="module")
def workflow() -> dict:
    return yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))


def _non_shell_expansions(doc: Any) -> list[str]:
    """Every single-brace shell expansion sitting in a with:/env: value.

    Pure function so the guard can be shown to bite (see
    ``test_the_guard_bites_on_a_synthetic_workflow``): a parse that silently
    stops visiting inputs would otherwise report a clean pass forever.
    """
    offenders: list[str] = []

    def visit(node: Any, where: str) -> None:
        if isinstance(node, dict):
            for key, value in node.items():
                if key == "run":
                    continue  # run: IS a shell — expansions there are correct
                if key in ("with", "env") and isinstance(value, dict):
                    for field, raw in value.items():
                        if key == "with" and str(field) in SCRIPT_FIELDS:
                            continue  # code the action evaluates itself
                        for line in str(raw).splitlines():
                            if SHELL_PARAM.search(line):
                                offenders.append(f"{where}/{key}.{field}: {line.strip()}")
                    # with:/env: values are strings; nothing below to recurse
                else:
                    visit(value, f"{where}.{key}")
        elif isinstance(node, list):
            for index, item in enumerate(node):
                visit(item, f"{where}[{index}]")

    visit(doc, "$")
    return offenders


def test_no_shell_expansion_sits_in_an_action_input(workflow: dict) -> None:
    """Actions interpolate ``${{ }}`` and nothing else, so ``${VAR::7}`` is a typo that ships."""
    offenders = _non_shell_expansions(workflow)
    assert not offenders, (
        "with:/env: values containing shell-style ${…} — GitHub does not run a "
        "shell there, the action gets the literal characters: " + "; ".join(offenders)
    )


def test_the_guard_bites_on_a_synthetic_workflow() -> None:
    """Non-vacuity: the exact bug shape, in a fixture, must be caught.

    Written from the reproduced defect (sbom-action's ``image`` input), not
    from the fixed file — the guard was run against the offending head first
    (11 inputs scanned, 1 offender: sbom-and-sign/with.image).
    """
    synthetic = {
        "jobs": {
            "sbom-and-sign": {
                "steps": [
                    {
                        "name": "Generate SBOM",
                        "uses": "anchore/sbom-action@v0.24.3",
                        "with": {"image": "ghcr.io/o/r/backend:${GITHUB_SHA::7}"},
                    },
                    {
                        "name": "Legitimate: a shell does expand this",
                        "run": 'docker pull img:"${GITHUB_SHA::7}"',
                    },
                    {
                        "name": "Legitimate: GitHub context syntax",
                        "uses": "actions/checkout@v7",
                        "with": {"ref": "${{ github.sha }}"},
                    },
                    {
                        "name": "Legitimate: JS template literal, the action evaluates it",
                        "uses": "actions/github-script@v8",
                        "with": {"script": "core.info(`${process.env.FOO}`)"},
                    },
                ]
            }
        }
    }
    offenders = _non_shell_expansions(synthetic)
    assert len(offenders) == 1, f"expected exactly the one bug shape, got: {offenders}"
    assert "with.image" in offenders[0]


def test_the_fixed_head_derives_the_short_sha_in_a_step(workflow: dict) -> None:
    """The shape the fix must take: a run: step exports it, inputs interpolate it.

    Pins the resolution, not just the absence: an input may name the per-commit
    tag only through ``${{ env.* }}`` / ``${{ steps.*.outputs.* }}``.
    """
    sbom = workflow["jobs"]["sbom-and-sign"]
    exports = [
        step.get("id")
        for step in (sbom.get("steps") or [])
        if "GITHUB_OUTPUT" in str(step.get("run") or "")
        or "GITHUB_ENV" in str(step.get("run") or "")
    ]
    assert exports, "sbom-and-sign must derive the short sha in a run: step that exports it"
    image_input = str(
        next(
            (step.get("with") or {}).get("image")
            for step in (sbom.get("steps") or [])
            if (step.get("with") or {}).get("image")
        )
    )
    assert "${{ env." in image_input or "${{ steps." in image_input, (
        f"the SBOM image reference interpolates the tag from nowhere: {image_input!r}"
    )
