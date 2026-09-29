"""R8 S1: PIPELINE_MODE=legacy must RAISE at boot, not warn.

ABOUTME: Owner rulings 2026-09-29 (spec §0, verbatim): "we do not have to support backwards
compatability" and "we should hard raise". Before this slice the validator at
backend/core/config.py accepted "legacy" and only logged a warning -- so a deployment with a
stale PIPELINE_MODE=legacy in its .env BOOTED the unsupported pipeline. The warning was the
guard, and a warning is not a guard: nothing stopped the boot. These tests pin the raise from
two directions -- the validator called directly (fast, precise about the exception's text) and
Settings constructed through the model (what a boot actually does; pydantic wraps a validator's
ValueError into a ValidationError).

Deliberate negative space: the raise text must NAME the bad value and must NOT offer legacy as
an option -- the message is the only thing an operator with a broken boot ever reads.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from backend.core.config import Settings


class TestLegacyHardRaises:
    def test_legacy_raises_from_the_validator_directly(self) -> None:
        """The owner ruling is a raise, not a warning: the validator must not return "legacy"."""
        with pytest.raises(ValueError, match=r"[Ll]egacy"):
            Settings.validate_pipeline_mode("legacy")

    def test_legacy_raises_when_settings_are_constructed(self) -> None:
        """What a boot actually does: pydantic wraps the validator's ValueError."""
        with pytest.raises(ValidationError):
            Settings(pipeline_mode="legacy")  # type: ignore[arg-type]

    def test_the_env_spelling_raises_too(self) -> None:
        """PIPELINE_MODE is read from env as a string; case/spaces must not smuggle it through."""
        with pytest.raises((ValueError, ValidationError)):
            Settings.validate_pipeline_mode("LEGACY")
        with pytest.raises((ValueError, ValidationError)):
            Settings.validate_pipeline_mode(" legacy ")

    def test_the_raise_text_names_the_value_and_does_not_offer_legacy_as_a_choice(self) -> None:
        """An operator sees only the message. It must say what was wrong and what is accepted --
        and must not read as if legacy were still an option (the retired wording)."""
        with pytest.raises(ValueError) as excinfo:
            Settings.validate_pipeline_mode("legacy")
        text = str(excinfo.value)
        assert "legacy" in text.lower()
        assert "vlm" in text.lower()
        # The accepted-values list must not still enumerate legacy as selectable. A phrasing like
        # "must be 'vlm' or 'legacy'" would tell the operator to do the forbidden thing.
        assert "'vlm' or 'legacy'" not in text
        assert (
            "retired" in text.lower() or "removed" in text.lower() or "unsupported" in text.lower()
        )


class TestNoneStillDefaultsToVlm:
    def test_none_resolves_to_vlm(self) -> None:
        """An UNSET mode is not an invalid mode: absent env must keep booting on vlm.

        This is the existing None branch and S1 does not change it -- pinned so the hard raise
        cannot widen into "missing PIPELINE_MODE crashes the boot", which would take down every
        deployment that never set the variable (the prod default is `${PIPELINE_MODE:-vlm}`).
        """
        assert Settings.validate_pipeline_mode(None) == "vlm"


class TestVlmStillParses:
    def test_vlm_and_its_spellings_parse(self) -> None:
        for value in ("vlm", "VLM", " vlm "):
            assert Settings.validate_pipeline_mode(value) == "vlm"


class TestUnknownValuesStillRaise:
    def test_typos_raise_as_before(self) -> None:
        """The never-silently-fallback rule predates S1; it must survive the rewrite."""
        for value in ("vlmm", "Legacy-mode", "", "auto"):
            with pytest.raises(ValueError):
                Settings.validate_pipeline_mode(value)
