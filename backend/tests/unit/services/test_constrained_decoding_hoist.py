"""R8 S2a: the constrained-decoding block must live in its OWN module.

ABOUTME: ``nemotron_analyzer.py`` is ~98% legacy and R8 deletes it, but its
:294-411 block is imported by the SHIPPED VLM path (design spec §2, measured:
``vlm_client.py``, ``vlm_analyzer.py``, ``evaluation/vlm_replay.py``, the boot
gate in ``main.py``, and the CI probe CLI ``scripts/vlm_probes/enforcement.py``
-- five importers, not the four the first scoping pass counted). Deleting the
file whole breaks the shipped pipeline AT IMPORT and the S-1 enforcement
verdict with it. So the block is hoisted to ``services/constrained_decoding.py``
FIRST and every importer repoints; only then does 2b delete the analyzer.

Why a test and not just a move: the hoist's whole purpose is that the VLM
path's enforcement vocabulary no longer sits behind a legacy module. A test
that imports the vocabulary from the NEW home, and a source pin that the
surviving modules never import it from the OLD one, is what makes a future
re-introduction (``from backend.services.nemotron_analyzer import
ConstrainedDecodingNotEnforced`` back in ``vlm_client``) red instead of
silent -- and instead of a mystery ``ModuleNotFoundError`` at boot once 2b
lands.

Negative space kept honest: the probe CONTRACT's behavior is pinned by
``test_p03_constrained_verdict.py`` and the enforcement probes; this file
pins the MOVE -- same objects, one home, shipped importers repointed. It
asserts identity (``is``), not copies: a second definition of
``ConstrainedDecodingNotEnforced`` that drifts from the first is exactly the
P0.3 fabrication this class exists to prevent.
"""

from __future__ import annotations

from pathlib import Path

import pytest

MODULE = "backend/services/constrained_decoding.py"
SHIPPED_IMPORTERS = [
    "backend/services/vlm_client.py",
    "backend/services/vlm_analyzer.py",
    "backend/evaluation/vlm_replay.py",
    "backend/main.py",
]


class TestNewHomeExists:
    def test_module_imports_and_carries_the_vocabulary(self) -> None:
        """The block's names, from the new home."""
        from backend.services import constrained_decoding as cd

        for name in (
            "VerificationRowOutcome",
            "ConstrainedDecodingNotEnforced",
            "PROBE_PROMPT",
            "_TRUNCATED_STOPS",
            "_is_length_truncated",
            "_probe_completion",
            "build_probe_schema",
        ):
            assert hasattr(cd, name), f"{MODULE} must define {name}"


class TestShippedImportersRepointed:
    @pytest.mark.parametrize("relpath", SHIPPED_IMPORTERS)
    def test_no_shipped_module_imports_the_vocabulary_from_the_analyzer(self, relpath: str) -> None:
        """The deletion-safety property 2b depends on.

        Checked as source text, not by importing: an import-time check cannot
        tell WHICH module a re-exported name came from, and ``backend.services``
        eagerly imports the analyzer today, so a live check would pass even
        with the old edge in place.
        """
        src = Path(relpath).read_text()
        assert "from backend.services.nemotron_analyzer import" not in src, (
            f"{relpath} still imports from the analyzer - S2b's rm breaks "
            f"the shipped path at import"
        )

    @pytest.mark.parametrize("relpath", SHIPPED_IMPORTERS)
    def test_shipped_modules_that_need_it_import_the_new_home(self, relpath: str) -> None:
        src = Path(relpath).read_text()
        assert "constrained_decoding" in src, f"{relpath} must import from constrained_decoding"

    def test_the_ci_probe_cli_repoints_too(self) -> None:
        """scripts/ is outside the AST gate's backend/ scope, so it is pinned
        here explicitly: a CI probe that imports the deleted module turns a
        green Gate red for the wrong reason."""
        src = Path("scripts/vlm_probes/enforcement.py").read_text()
        assert "from backend.services.nemotron_analyzer import" not in src
        assert "constrained_decoding" in src


class TestSingleDefinition:
    def test_the_analyzer_reuses_the_hoisted_objects_and_does_not_redefine(self) -> None:
        """Identity, not equality. Two definitions of the fail-closed class
        mean an `except ConstrainedDecodingNotEnforced` in one layer misses
        a raise from the other - a fabricated 'enforced'."""
        from backend.services import constrained_decoding as cd

        assert cd.ConstrainedDecodingNotEnforced.__module__ == (
            "backend.services.constrained_decoding"
        )
        src = Path("backend/services/nemotron_analyzer.py").read_text()
        assert "class ConstrainedDecodingNotEnforced" not in src
        assert "def build_probe_schema" not in src
        assert "def _probe_completion" not in src
        # The analyzer still USES the vocabulary (its own runtime gate) - it
        # just no longer owns it.
        assert "from backend.services.constrained_decoding import" in src

    def test_the_probe_contract_is_the_same_object_the_ci_cli_builds(self) -> None:
        from backend.services import constrained_decoding as cd
        from backend.services.nemotron_analyzer import build_probe_schema as analyzer_build

        assert analyzer_build is cd.build_probe_schema
