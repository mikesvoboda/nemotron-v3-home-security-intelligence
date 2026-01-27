"""Unit tests for Prompt A/B Testing Configuration (NEM-3731).

Tests the PromptExperiment dataclass, EXPERIMENTS dictionary,
and experiment retrieval functions.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from backend.config.prompt_ab_config import (
    EXPERIMENTS,
    PromptExperiment,
    get_enabled_experiments,
    get_experiment,
    list_experiments,
)

# =============================================================================
# PromptExperiment Dataclass Tests
# =============================================================================


class TestPromptExperimentCreation:
    """Tests for PromptExperiment dataclass creation and validation."""

    def test_create_basic_experiment(self) -> None:
        """Test creating a basic experiment with required fields only."""
        experiment = PromptExperiment(
            name="test_experiment",
            description="A test experiment",
            control_prompt_key="control_v1",
            variant_prompt_key="variant_v1",
        )

        assert experiment.name == "test_experiment"
        assert experiment.description == "A test experiment"
        assert experiment.control_prompt_key == "control_v1"
        assert experiment.variant_prompt_key == "variant_v1"
        # Check defaults
        assert experiment.traffic_split == 0.1
        assert experiment.eval_dataset_path == Path("data/synthetic")
        assert experiment.enabled is True
        assert len(experiment.metrics) == 4

    def test_create_experiment_with_custom_traffic_split(self) -> None:
        """Test creating an experiment with custom traffic split."""
        experiment = PromptExperiment(
            name="high_traffic_test",
            description="50/50 split test",
            control_prompt_key="baseline",
            variant_prompt_key="experimental",
            traffic_split=0.5,
        )

        assert experiment.traffic_split == 0.5

    def test_create_experiment_with_custom_metrics(self) -> None:
        """Test creating an experiment with custom metrics."""
        custom_metrics = ["accuracy", "precision", "recall"]
        experiment = PromptExperiment(
            name="custom_metrics_test",
            description="Test with custom metrics",
            control_prompt_key="v1",
            variant_prompt_key="v2",
            metrics=custom_metrics,
        )

        assert experiment.metrics == custom_metrics

    def test_create_experiment_with_custom_dataset_path(self) -> None:
        """Test creating an experiment with custom dataset path."""
        custom_path = Path("/custom/data/path")
        experiment = PromptExperiment(
            name="custom_path_test",
            description="Test with custom path",
            control_prompt_key="v1",
            variant_prompt_key="v2",
            eval_dataset_path=custom_path,
        )

        assert experiment.eval_dataset_path == custom_path

    def test_create_disabled_experiment(self) -> None:
        """Test creating a disabled experiment."""
        experiment = PromptExperiment(
            name="disabled_test",
            description="A disabled experiment",
            control_prompt_key="v1",
            variant_prompt_key="v2",
            enabled=False,
        )

        assert experiment.enabled is False


class TestPromptExperimentValidation:
    """Tests for PromptExperiment validation."""

    def test_empty_name_raises_error(self) -> None:
        """Test that empty name raises ValueError."""
        with pytest.raises(ValueError, match="Experiment name cannot be empty"):
            PromptExperiment(
                name="",
                description="Test",
                control_prompt_key="v1",
                variant_prompt_key="v2",
            )

    def test_empty_description_raises_error(self) -> None:
        """Test that empty description raises ValueError."""
        with pytest.raises(ValueError, match="Experiment description cannot be empty"):
            PromptExperiment(
                name="test",
                description="",
                control_prompt_key="v1",
                variant_prompt_key="v2",
            )

    def test_empty_control_prompt_key_raises_error(self) -> None:
        """Test that empty control prompt key raises ValueError."""
        with pytest.raises(ValueError, match="Control prompt key cannot be empty"):
            PromptExperiment(
                name="test",
                description="Test",
                control_prompt_key="",
                variant_prompt_key="v2",
            )

    def test_empty_variant_prompt_key_raises_error(self) -> None:
        """Test that empty variant prompt key raises ValueError."""
        with pytest.raises(ValueError, match="Variant prompt key cannot be empty"):
            PromptExperiment(
                name="test",
                description="Test",
                control_prompt_key="v1",
                variant_prompt_key="",
            )

    def test_same_control_and_variant_raises_error(self) -> None:
        """Test that same control and variant keys raises ValueError."""
        with pytest.raises(ValueError, match="Control and variant prompt keys must be different"):
            PromptExperiment(
                name="test",
                description="Test",
                control_prompt_key="same_key",
                variant_prompt_key="same_key",
            )

    def test_traffic_split_below_zero_raises_error(self) -> None:
        """Test that traffic split below 0.0 raises ValueError."""
        with pytest.raises(ValueError, match="traffic_split must be between 0.0 and 1.0"):
            PromptExperiment(
                name="test",
                description="Test",
                control_prompt_key="v1",
                variant_prompt_key="v2",
                traffic_split=-0.1,
            )

    def test_traffic_split_above_one_raises_error(self) -> None:
        """Test that traffic split above 1.0 raises ValueError."""
        with pytest.raises(ValueError, match="traffic_split must be between 0.0 and 1.0"):
            PromptExperiment(
                name="test",
                description="Test",
                control_prompt_key="v1",
                variant_prompt_key="v2",
                traffic_split=1.1,
            )

    def test_traffic_split_boundary_zero_valid(self) -> None:
        """Test that traffic split of 0.0 is valid (all control)."""
        experiment = PromptExperiment(
            name="test",
            description="Test",
            control_prompt_key="v1",
            variant_prompt_key="v2",
            traffic_split=0.0,
        )
        assert experiment.traffic_split == 0.0

    def test_traffic_split_boundary_one_valid(self) -> None:
        """Test that traffic split of 1.0 is valid (all variant)."""
        experiment = PromptExperiment(
            name="test",
            description="Test",
            control_prompt_key="v1",
            variant_prompt_key="v2",
            traffic_split=1.0,
        )
        assert experiment.traffic_split == 1.0


class TestPromptExperimentDefaultMetrics:
    """Tests for default metrics configuration."""

    def test_default_metrics_list(self) -> None:
        """Test that default metrics contains expected values."""
        experiment = PromptExperiment(
            name="test",
            description="Test",
            control_prompt_key="v1",
            variant_prompt_key="v2",
        )

        expected_metrics = [
            "json_parse_success_rate",
            "score_in_range_accuracy",
            "level_match_accuracy",
            "response_latency_ms",
        ]
        assert experiment.metrics == expected_metrics

    def test_metrics_are_mutable_copy(self) -> None:
        """Test that each experiment gets its own metrics list."""
        exp1 = PromptExperiment(
            name="test1",
            description="Test 1",
            control_prompt_key="v1",
            variant_prompt_key="v2",
        )
        exp2 = PromptExperiment(
            name="test2",
            description="Test 2",
            control_prompt_key="v1",
            variant_prompt_key="v2",
        )

        # Modify exp1's metrics
        exp1.metrics.append("custom_metric")

        # exp2's metrics should be unchanged
        assert "custom_metric" in exp1.metrics
        assert "custom_metric" not in exp2.metrics


# =============================================================================
# EXPERIMENTS Dictionary Tests
# =============================================================================


class TestExperimentsDictionary:
    """Tests for the predefined EXPERIMENTS dictionary."""

    def test_experiments_dictionary_exists(self) -> None:
        """Test that EXPERIMENTS dictionary is defined."""
        assert EXPERIMENTS is not None
        assert isinstance(EXPERIMENTS, dict)

    def test_experiments_contains_rubric_vs_current(self) -> None:
        """Test that rubric_vs_current experiment is defined."""
        assert "rubric_vs_current" in EXPERIMENTS
        experiment = EXPERIMENTS["rubric_vs_current"]
        assert experiment.name == "rubric_vs_current"
        assert experiment.control_prompt_key == "calibrated_system"
        assert experiment.variant_prompt_key == "rubric_enhanced"

    def test_experiments_contains_cot_vs_current(self) -> None:
        """Test that cot_vs_current experiment is defined."""
        assert "cot_vs_current" in EXPERIMENTS
        experiment = EXPERIMENTS["cot_vs_current"]
        assert experiment.name == "cot_vs_current"
        assert experiment.control_prompt_key == "calibrated_system"
        assert experiment.variant_prompt_key == "reasoning_enabled"

    def test_all_experiments_are_valid(self) -> None:
        """Test that all predefined experiments have valid configurations."""
        for name, experiment in EXPERIMENTS.items():
            assert experiment.name == name
            assert experiment.description
            assert experiment.control_prompt_key
            assert experiment.variant_prompt_key
            assert experiment.control_prompt_key != experiment.variant_prompt_key
            assert 0.0 <= experiment.traffic_split <= 1.0


# =============================================================================
# get_experiment() Tests
# =============================================================================


class TestGetExperiment:
    """Tests for get_experiment() function."""

    def test_get_existing_experiment(self) -> None:
        """Test retrieving an existing experiment."""
        experiment = get_experiment("rubric_vs_current")

        assert experiment is not None
        assert experiment.name == "rubric_vs_current"

    def test_get_another_existing_experiment(self) -> None:
        """Test retrieving cot_vs_current experiment."""
        experiment = get_experiment("cot_vs_current")

        assert experiment is not None
        assert experiment.name == "cot_vs_current"

    def test_get_nonexistent_experiment_returns_none(self) -> None:
        """Test that getting a nonexistent experiment returns None."""
        experiment = get_experiment("nonexistent_experiment")

        assert experiment is None

    def test_get_experiment_empty_string_returns_none(self) -> None:
        """Test that getting experiment with empty string returns None."""
        experiment = get_experiment("")

        assert experiment is None

    def test_get_experiment_case_sensitive(self) -> None:
        """Test that experiment names are case-sensitive."""
        experiment_lower = get_experiment("rubric_vs_current")
        experiment_upper = get_experiment("RUBRIC_VS_CURRENT")

        assert experiment_lower is not None
        assert experiment_upper is None


# =============================================================================
# list_experiments() Tests
# =============================================================================


class TestListExperiments:
    """Tests for list_experiments() function."""

    def test_list_experiments_returns_list(self) -> None:
        """Test that list_experiments returns a list."""
        names = list_experiments()

        assert isinstance(names, list)

    def test_list_experiments_contains_predefined(self) -> None:
        """Test that list contains predefined experiment names."""
        names = list_experiments()

        assert "rubric_vs_current" in names
        assert "cot_vs_current" in names

    def test_list_experiments_matches_dict_keys(self) -> None:
        """Test that list matches EXPERIMENTS dictionary keys."""
        names = list_experiments()

        assert set(names) == set(EXPERIMENTS.keys())


# =============================================================================
# get_enabled_experiments() Tests
# =============================================================================


class TestGetEnabledExperiments:
    """Tests for get_enabled_experiments() function."""

    def test_get_enabled_experiments_returns_list(self) -> None:
        """Test that get_enabled_experiments returns a list."""
        enabled = get_enabled_experiments()

        assert isinstance(enabled, list)

    def test_all_returned_experiments_are_enabled(self) -> None:
        """Test that all returned experiments have enabled=True."""
        enabled = get_enabled_experiments()

        for experiment in enabled:
            assert experiment.enabled is True

    def test_predefined_experiments_are_enabled_by_default(self) -> None:
        """Test that predefined experiments are enabled by default."""
        enabled = get_enabled_experiments()

        # Both predefined experiments should be enabled
        enabled_names = [exp.name for exp in enabled]
        assert "rubric_vs_current" in enabled_names
        assert "cot_vs_current" in enabled_names
