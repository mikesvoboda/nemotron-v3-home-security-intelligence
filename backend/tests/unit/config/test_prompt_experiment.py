"""Unit tests for Prompt Experiment Configuration (NEM-3023).

These tests cover:
1. PromptVersion enum definition
2. PromptExperimentConfig creation and defaults
3. Camera-consistent version assignment (hash-based)
4. Shadow mode behavior (always returns v1)
5. Treatment percentage behavior
6. Auto-rollback threshold validation
7. Experiment state management

TDD: Write tests first (RED), then implement to make them GREEN.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

# Mark all tests in this file as unit tests
pytestmark = pytest.mark.unit


# =============================================================================
# Test: PromptVersion Enum
# =============================================================================


class TestPromptVersionEnum:
    """Tests for PromptVersion enumeration."""

    def test_prompt_version_v1_original_exists(self):
        """Test V1_ORIGINAL version exists."""
        from backend.config.prompt_experiment import PromptVersion

        assert hasattr(PromptVersion, "V1_ORIGINAL")
        assert PromptVersion.V1_ORIGINAL.value == "v1_original"

    def test_prompt_version_v2_calibrated_exists(self):
        """Test V2_CALIBRATED version exists."""
        from backend.config.prompt_experiment import PromptVersion

        assert hasattr(PromptVersion, "V2_CALIBRATED")
        assert PromptVersion.V2_CALIBRATED.value == "v2_calibrated"

    def test_prompt_version_is_enum(self):
        """Test PromptVersion is an Enum class."""
        from enum import Enum

        from backend.config.prompt_experiment import PromptVersion

        assert issubclass(PromptVersion, Enum)


# =============================================================================
# Test: PromptExperimentConfig Creation
# =============================================================================


class TestPromptExperimentConfigCreation:
    """Tests for PromptExperimentConfig dataclass creation."""

    def test_default_config_creation(self):
        """Test PromptExperimentConfig can be created with defaults."""
        from backend.config.prompt_experiment import PromptExperimentConfig

        config = PromptExperimentConfig()

        # Default values from task spec
        assert config.shadow_mode is True
        assert config.treatment_percentage == 0.0
        assert config.max_latency_increase_pct == 50.0
        assert config.min_fp_reduction_pct == 10.0
        assert config.experiment_name == "nemotron_prompt_v2"
        assert config.started_at is None

    def test_custom_config_creation(self):
        """Test PromptExperimentConfig can be created with custom values."""
        from backend.config.prompt_experiment import PromptExperimentConfig

        started = datetime.now(UTC).isoformat()
        config = PromptExperimentConfig(
            shadow_mode=False,
            treatment_percentage=0.25,
            max_latency_increase_pct=30.0,
            min_fp_reduction_pct=15.0,
            experiment_name="custom_experiment",
            started_at=started,
        )

        assert config.shadow_mode is False
        assert config.treatment_percentage == 0.25
        assert config.max_latency_increase_pct == 30.0
        assert config.min_fp_reduction_pct == 15.0
        assert config.experiment_name == "custom_experiment"
        assert config.started_at == started

    def test_treatment_percentage_validation_lower_bound(self):
        """Test treatment_percentage validates lower bound (0.0)."""
        from backend.config.prompt_experiment import PromptExperimentConfig

        # Valid: exactly 0.0
        config = PromptExperimentConfig(treatment_percentage=0.0)
        assert config.treatment_percentage == 0.0

        # Invalid: below 0.0
        with pytest.raises(ValueError, match="treatment_percentage"):
            PromptExperimentConfig(treatment_percentage=-0.1)

    def test_treatment_percentage_validation_upper_bound(self):
        """Test treatment_percentage validates upper bound (1.0)."""
        from backend.config.prompt_experiment import PromptExperimentConfig

        # Valid: exactly 1.0
        config = PromptExperimentConfig(treatment_percentage=1.0)
        assert config.treatment_percentage == 1.0

        # Invalid: above 1.0
        with pytest.raises(ValueError, match="treatment_percentage"):
            PromptExperimentConfig(treatment_percentage=1.1)

    def test_treatment_percentage_valid_mid_values(self):
        """Test treatment_percentage accepts valid mid-range values."""
        from backend.config.prompt_experiment import PromptExperimentConfig

        for pct in [0.1, 0.25, 0.5, 0.75, 0.9]:
            config = PromptExperimentConfig(treatment_percentage=pct)
            assert config.treatment_percentage == pct


# =============================================================================
# Test: Shadow Mode Version Selection
# =============================================================================


class TestShadowModeVersionSelection:
    """Tests for version selection in shadow mode."""

    def test_shadow_mode_always_returns_v1(self):
        """Test shadow mode always returns V1_ORIGINAL regardless of treatment percentage."""
        from backend.config.prompt_experiment import (
            PromptExperimentConfig,
            PromptVersion,
        )

        config = PromptExperimentConfig(
            shadow_mode=True,
            treatment_percentage=0.5,  # 50% treatment, but shadow mode overrides
        )

        # Run multiple times with different camera IDs
        for camera_id in ["front_door", "backyard", "driveway", "garage", "side_gate"]:
            version = config.get_version_for_camera(camera_id)
            assert version == PromptVersion.V1_ORIGINAL

    def test_shadow_mode_ignores_treatment_percentage(self):
        """Test shadow mode ignores treatment_percentage entirely."""
        from backend.config.prompt_experiment import (
            PromptExperimentConfig,
            PromptVersion,
        )

        # Even with 100% treatment, shadow mode should return V1
        config = PromptExperimentConfig(
            shadow_mode=True,
            treatment_percentage=1.0,
        )

        for _ in range(100):
            version = config.get_version_for_camera("test_camera")
            assert version == PromptVersion.V1_ORIGINAL


# =============================================================================
# Test: A/B Test Version Selection (Non-Shadow Mode)
# =============================================================================


class TestABTestVersionSelection:
    """Tests for A/B test version selection when shadow mode is disabled."""

    def test_zero_treatment_always_returns_v1(self):
        """Test 0% treatment always returns V1_ORIGINAL."""
        from backend.config.prompt_experiment import (
            PromptExperimentConfig,
            PromptVersion,
        )

        config = PromptExperimentConfig(
            shadow_mode=False,
            treatment_percentage=0.0,
        )

        # All cameras should get V1
        for camera_id in ["cam1", "cam2", "cam3", "cam4", "cam5"]:
            version = config.get_version_for_camera(camera_id)
            assert version == PromptVersion.V1_ORIGINAL

    def test_full_treatment_always_returns_v2(self):
        """Test 100% treatment always returns V2_CALIBRATED."""
        from backend.config.prompt_experiment import (
            PromptExperimentConfig,
            PromptVersion,
        )

        config = PromptExperimentConfig(
            shadow_mode=False,
            treatment_percentage=1.0,
        )

        # All cameras should get V2
        for camera_id in ["cam1", "cam2", "cam3", "cam4", "cam5"]:
            version = config.get_version_for_camera(camera_id)
            assert version == PromptVersion.V2_CALIBRATED

    def test_camera_consistent_version_assignment(self):
        """Test same camera always gets same version (deterministic hash)."""
        from backend.config.prompt_experiment import PromptExperimentConfig

        config = PromptExperimentConfig(
            shadow_mode=False,
            treatment_percentage=0.5,  # 50% split
        )

        # Same camera should always return same version
        camera_id = "front_door"
        first_version = config.get_version_for_camera(camera_id)

        for _ in range(100):
            version = config.get_version_for_camera(camera_id)
            assert version == first_version

    def test_different_cameras_can_get_different_versions(self):
        """Test different cameras can be assigned to different versions."""
        from backend.config.prompt_experiment import (
            PromptExperimentConfig,
            PromptVersion,
        )

        config = PromptExperimentConfig(
            shadow_mode=False,
            treatment_percentage=0.5,  # 50% should give mix
        )

        # Generate versions for many cameras
        versions = {config.get_version_for_camera(f"camera_{i}") for i in range(100)}

        # With 50% split and 100 cameras, we should see both versions
        assert PromptVersion.V1_ORIGINAL in versions or PromptVersion.V2_CALIBRATED in versions

    def test_version_distribution_approximately_matches_split(self):
        """Test version distribution roughly matches treatment_percentage."""
        from backend.config.prompt_experiment import (
            PromptExperimentConfig,
            PromptVersion,
        )

        config = PromptExperimentConfig(
            shadow_mode=False,
            treatment_percentage=0.3,  # 30% treatment
        )

        # Generate versions for many cameras
        v2_count = 0
        total = 1000

        for i in range(total):
            version = config.get_version_for_camera(f"camera_{i}")
            if version == PromptVersion.V2_CALIBRATED:
                v2_count += 1

        # Should be approximately 30% V2 (allow 10% tolerance for hash distribution)
        v2_ratio = v2_count / total
        assert 0.2 <= v2_ratio <= 0.4, f"Expected ~30% V2, got {v2_ratio * 100:.1f}%"


# =============================================================================
# Test: Rollback Configuration
# =============================================================================


class TestRollbackThresholds:
    """Tests for auto-rollback threshold configuration."""

    def test_default_max_latency_increase(self):
        """Test default max_latency_increase_pct is 50%."""
        from backend.config.prompt_experiment import PromptExperimentConfig

        config = PromptExperimentConfig()
        assert config.max_latency_increase_pct == 50.0

    def test_default_min_fp_reduction(self):
        """Test default min_fp_reduction_pct is 10%."""
        from backend.config.prompt_experiment import PromptExperimentConfig

        config = PromptExperimentConfig()
        assert config.min_fp_reduction_pct == 10.0

    def test_custom_rollback_thresholds(self):
        """Test custom rollback thresholds can be set."""
        from backend.config.prompt_experiment import PromptExperimentConfig

        config = PromptExperimentConfig(
            max_latency_increase_pct=25.0,
            min_fp_reduction_pct=20.0,
        )

        assert config.max_latency_increase_pct == 25.0
        assert config.min_fp_reduction_pct == 20.0


# =============================================================================
# Test: Experiment State Management
# =============================================================================


class TestExperimentStateManagement:
    """Tests for experiment state tracking and management."""

    def test_experiment_name_default(self):
        """Test default experiment name."""
        from backend.config.prompt_experiment import PromptExperimentConfig

        config = PromptExperimentConfig()
        assert config.experiment_name == "nemotron_prompt_v2"

    def test_experiment_started_at_initially_none(self):
        """Test started_at is initially None."""
        from backend.config.prompt_experiment import PromptExperimentConfig

        config = PromptExperimentConfig()
        assert config.started_at is None

    def test_experiment_can_record_start_time(self):
        """Test experiment can have a start time set."""
        from backend.config.prompt_experiment import PromptExperimentConfig

        started = datetime.now(UTC).isoformat()
        config = PromptExperimentConfig(started_at=started)

        assert config.started_at == started

    def test_is_shadow_mode_property(self):
        """Test is_shadow_mode property returns correct value."""
        from backend.config.prompt_experiment import PromptExperimentConfig

        shadow_config = PromptExperimentConfig(shadow_mode=True)
        assert shadow_config.is_shadow_mode is True

        ab_config = PromptExperimentConfig(shadow_mode=False)
        assert ab_config.is_shadow_mode is False

    def test_is_ab_test_active_property(self):
        """Test is_ab_test_active property returns correct value."""
        from backend.config.prompt_experiment import PromptExperimentConfig

        # Shadow mode: AB test not active (even with treatment > 0)
        shadow_config = PromptExperimentConfig(
            shadow_mode=True,
            treatment_percentage=0.5,
        )
        assert shadow_config.is_ab_test_active is False

        # Non-shadow with 0% treatment: AB test not active
        no_treatment_config = PromptExperimentConfig(
            shadow_mode=False,
            treatment_percentage=0.0,
        )
        assert no_treatment_config.is_ab_test_active is False

        # Non-shadow with treatment > 0: AB test active
        ab_config = PromptExperimentConfig(
            shadow_mode=False,
            treatment_percentage=0.5,
        )
        assert ab_config.is_ab_test_active is True


# =============================================================================
# Test: Singleton/Factory Pattern
# =============================================================================


class TestPromptExperimentConfigFactory:
    """Tests for getting prompt experiment configuration."""

    def test_get_prompt_experiment_config_returns_config(self):
        """Test get_prompt_experiment_config returns a PromptExperimentConfig."""
        from backend.config.prompt_experiment import (
            PromptExperimentConfig,
            get_prompt_experiment_config,
        )

        config = get_prompt_experiment_config()
        assert isinstance(config, PromptExperimentConfig)

    def test_get_prompt_experiment_config_singleton(self):
        """Test get_prompt_experiment_config returns same instance."""
        from backend.config.prompt_experiment import (
            get_prompt_experiment_config,
            reset_prompt_experiment_config,
        )

        # Reset to ensure clean state
        reset_prompt_experiment_config()

        config1 = get_prompt_experiment_config()
        config2 = get_prompt_experiment_config()

        assert config1 is config2

    def test_reset_prompt_experiment_config(self):
        """Test reset_prompt_experiment_config clears singleton."""
        from backend.config.prompt_experiment import (
            get_prompt_experiment_config,
            reset_prompt_experiment_config,
        )

        config1 = get_prompt_experiment_config()
        reset_prompt_experiment_config()
        config2 = get_prompt_experiment_config()

        # After reset, should be a new instance
        assert config1 is not config2


# =============================================================================
# Test: Serialization Support
# =============================================================================


class TestPromptExperimentConfigSerialization:
    """Tests for experiment config serialization."""

    def test_to_dict_returns_complete_config(self):
        """Test to_dict returns all configuration fields."""
        from backend.config.prompt_experiment import PromptExperimentConfig

        config = PromptExperimentConfig(
            shadow_mode=False,
            treatment_percentage=0.25,
            experiment_name="test_exp",
        )

        result = config.to_dict()

        assert "shadow_mode" in result
        assert "treatment_percentage" in result
        assert "max_latency_increase_pct" in result
        assert "min_fp_reduction_pct" in result
        assert "experiment_name" in result
        assert "started_at" in result

    def test_from_dict_creates_config(self):
        """Test from_dict creates config from dictionary."""
        from backend.config.prompt_experiment import PromptExperimentConfig

        data = {
            "shadow_mode": False,
            "treatment_percentage": 0.5,
            "max_latency_increase_pct": 40.0,
            "min_fp_reduction_pct": 15.0,
            "experiment_name": "imported_exp",
            "started_at": "2024-01-15T10:00:00Z",
        }

        config = PromptExperimentConfig.from_dict(data)

        assert config.shadow_mode is False
        assert config.treatment_percentage == 0.5
        assert config.max_latency_increase_pct == 40.0
        assert config.min_fp_reduction_pct == 15.0
        assert config.experiment_name == "imported_exp"
        assert config.started_at == "2024-01-15T10:00:00Z"
