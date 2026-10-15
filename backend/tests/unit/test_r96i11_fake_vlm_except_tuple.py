"""[r96i11] The fake VLM module must stay parseable below Python 3.14.

PEP 758 (shipped in 3.14) made ``except A, B:`` legal unparenthesized; every older
parser rejects it. Ruling 96 item 11 wants the parenthesized form in
``backend/ai_contract/fake/app.py``, "parseable on older Pythons, so the
reachability toolchain is no longer coupled to 3.14".

Two guards, because the defect is machine-maintained: ``ruff format`` at the repo's
``py314`` target REWRITES ``except (A, B):`` back into the unparenthesized form, so
a parse guard alone would go red again the next time anyone formats this file. The
pin guard is the one that keeps it fixed; the parse guard is the one that says the
pin is buying anything. Same shape as ``backend/tests/unit/synthbench/spikes/
test_p1_py312.py``, which exists for the identical reason on the renderer image's
files.
"""

from __future__ import annotations

import ast
import tomllib
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
FAKE_APP = "backend/ai_contract/fake/app.py"


def test_fake_vlm_app_parses_below_3_14() -> None:
    """The Done-when's parse clause: every ``except`` in the module, not one line.

    Whole-file on purpose. The module carried the PEP 758 form at three sites, so
    a one-line fix would still leave the file unparsable by any pre-3.14
    interpreter, which is what the ruling is about.
    """
    ast.parse(
        (REPO_ROOT / FAKE_APP).read_text(encoding="utf-8"),
        filename=FAKE_APP,
        feature_version=(3, 13),
    )


def test_ruff_targets_py313_for_the_fake_vlm_app() -> None:
    """The pin that keeps the fix from being formatted away.

    Without it, ``ruff format`` (repo target ``py314``) turns every parenthesized
    ``except`` in this file back into the 3.14-only form — and
    ``ruff format --check`` in CI stays GREEN while doing it, because the rewritten
    form is precisely what a ``py314`` target asks for.
    """
    ruff = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))["tool"]["ruff"]
    targets = ruff.get("per-file-target-version", {})
    assert targets.get(FAKE_APP) == "py313", (
        f"{FAKE_APP} must be pinned to py313 in [tool.ruff.per-file-target-version]: "
        f"ruff's repo-wide py314 target rewrites except tuples back to the unparenthesized "
        f"PEP 758 form, so ruff-format would undo ruling 96 item 11 got: {targets.get(FAKE_APP)!r}"
    )


def test_the_parse_guard_is_not_toothless() -> None:
    """The instrument itself, pinned (same idiom as scripts/test_check_coverage_diff.py).

    ``ast.parse`` on this box is 3.14 and accepts the bare form, so the guard above
    only bites if ``feature_version`` still rejects it. If a future CPython relaxes
    that, this test says so instead of the file guard passing for nothing.
    """
    with pytest.raises(SyntaxError):
        ast.parse(
            "try:\n    pass\nexcept OSError, ValueError:\n    pass\n", feature_version=(3, 13)
        )
