"""Ruling 168: the fast path's "disabled" is an explicit flag, not a sentinel.

F-187's 500 came from the sentinel itself: `fast_path_confidence_threshold`
defaulted to 2.0 to mean "disabled", and `GET /api/v1/settings` fed that value
into `DetectionSettings.fast_path_threshold`, whose schema caps it at `le=1.0`
— pydantic rejected the app's own default and the route never returned. The
owner's answer (ruling 168, option b) makes the disabled state explicit:
`fast_path_enabled` is the master switch, and the threshold stays inside the
0.0-1.0 band its consumers already enforce.

These tests run against the REAL `Settings` class: the sentinel and the band
are config behaviour, not route behaviour, and a mocked Settings would pass
them vacuously.
"""

import pytest
from pydantic import ValidationError

from backend.core.config import Settings

DATABASE_URL = "postgresql+asyncpg://test:test@localhost:5432/test"  # pragma: allowlist secret


@pytest.fixture
def settings_env(monkeypatch):
    """A minimal valid environment for `Settings`, with the fast-path vars cleared.

    Args:
        monkeypatch: pytest monkeypatch, yielded so tests can set env vars.

    Yields:
        The monkeypatch object.
    """
    for var in ("FAST_PATH_ENABLED", "FAST_PATH_CONFIDENCE_THRESHOLD", "FAST_PATH_OBJECT_TYPES"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("DATABASE_URL", DATABASE_URL)
    monkeypatch.setenv("ENVIRONMENT", "development")
    yield monkeypatch


class TestFastPathFlag:
    """`fast_path_enabled` exists, defaults False, and parses from the env."""

    def test_fast_path_enabled_defaults_false(self, settings_env) -> None:
        """The shipped default is disabled: the fast path is OFF out of the box.

        Ruling 168: "add `fast_path_enabled: bool` (default `false`)".
        """
        assert Settings().fast_path_enabled is False

    def test_fast_path_enabled_reads_env_var(self, settings_env) -> None:
        """FAST_PATH_ENABLED=true turns the master switch on."""
        settings_env.setenv("FAST_PATH_ENABLED", "true")
        assert Settings().fast_path_enabled is True


class TestThresholdBand:
    """The threshold lives inside the 0.0-1.0 band its schemas already enforce."""

    def test_threshold_default_is_within_the_band(self) -> None:
        """The default no longer exceeds the schema bound that 500s the settings route.

        F-187: default 2.0 vs `DetectionSettings.fast_path_threshold` `le=1.0`
        (backend/api/schemas/settings_api.py:49). With the default inside the
        band, `GET /api/v1/settings` can construct its own response.
        """
        field = Settings.model_fields["fast_path_confidence_threshold"]
        assert field.default == 0.9
        assert 0.0 <= field.default <= 1.0

    def test_legacy_sentinel_is_clamped_into_the_band_not_rejected(self, settings_env) -> None:
        """A deployment whose runtime.env still holds the old 2.0 sentinel boots.

        Tightening the band to `le=1.0` would otherwise make a legacy value a
        ValidationError AT STARTUP: `get_settings()` reads
        `data/runtime.env` (backend/core/config.py:3497-3500), and a settings
        page that once wrote the sentinel would brick every later boot. A
        clamped 1.0 with `fast_path_enabled` False is exactly the ruling's
        "disabled, whatever the threshold".
        """
        settings_env.setenv("FAST_PATH_CONFIDENCE_THRESHOLD", "2.0")
        assert Settings().fast_path_confidence_threshold == 1.0

    def test_any_out_of_band_above_value_folds_to_one_not_rejected(self, settings_env) -> None:
        """Every value above the band folds to 1.0, not just the 2.0 default.

        HEAD shipped `le=10.0` and its banner told operators to set ANY value
        >1.0 to mean "disabled", so live env files hold 2.0, 3.0, 10.0 — not
        only 2.0. A clamp that forgave exactly 2.0 would re-create the boot
        brick for a deployment that used 10.0. Folding to 1.0 is always the
        safe direction: a value >1.0 could only ever have meant "never fires",
        and 1.0 is its closest in-band analog (fires only at certainty, and
        fast_path_enabled gates it off anyway). Pinning 1.5 (not 2.0) so the
        invariant is "fold the band", not "special-case one number".
        """
        settings_env.setenv("FAST_PATH_CONFIDENCE_THRESHOLD", "1.5")
        assert Settings().fast_path_confidence_threshold == 1.0

    def test_in_band_threshold_is_left_alone(self, settings_env) -> None:
        """Clamping the sentinel must not clamp ordinary values.

        Without this pair, a validator that returned 1.0 unconditionally would
        pass the test above.
        """
        settings_env.setenv("FAST_PATH_CONFIDENCE_THRESHOLD", "0.75")
        assert Settings().fast_path_confidence_threshold == 0.75

    def test_out_of_band_below_is_still_rejected(self, settings_env) -> None:
        """The lower bound is real: the clamp forgives the legacy upper sentinel only."""
        settings_env.setenv("FAST_PATH_CONFIDENCE_THRESHOLD", "-0.5")
        with pytest.raises(ValidationError):
            Settings()
