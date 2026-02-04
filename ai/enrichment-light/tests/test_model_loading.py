"""Tests for enrichment-light model loading configuration.

These tests verify that models are correctly loaded based on environment
variable configuration, ensuring the fix for NEM-5376 is working.
"""

import os
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def clean_env(monkeypatch):
    """Clean environment fixture that removes enrichment-related env vars."""
    # Remove any existing enrichment env vars
    env_vars_to_remove = [
        "ENRICHMENT_PRELOAD_MODELS",
        "ENRICHMENT_POSE_SERVICE",
        "ENRICHMENT_THREAT_SERVICE",
        "ENRICHMENT_REID_SERVICE",
        "ENRICHMENT_PET_SERVICE",
        "ENRICHMENT_DEPTH_SERVICE",
    ]
    for var in env_vars_to_remove:
        monkeypatch.delenv(var, raising=False)
    yield monkeypatch


def test_should_load_model_defaults_to_light(clean_env):
    """Test that _should_load_model returns True for light service by default.

    This verifies the first condition for model loading: models are assigned
    to the 'light' service by default when ENRICHMENT_<MODEL>_SERVICE is not set.
    """
    # Import after setting env to ensure clean state
    import importlib
    import sys

    # Remove module from cache to force fresh import
    if "model" in sys.modules:
        del sys.modules["model"]

    import model as enrichment_light_model

    # Test all supported models default to 'light' service
    assert enrichment_light_model._should_load_model("pose") is True
    assert enrichment_light_model._should_load_model("threat") is True
    assert enrichment_light_model._should_load_model("reid") is True
    assert enrichment_light_model._should_load_model("pet") is True
    assert enrichment_light_model._should_load_model("depth") is True


def test_should_load_model_respects_heavy_assignment(clean_env):
    """Test that _should_load_model returns False when model assigned to heavy service."""
    clean_env.setenv("ENRICHMENT_POSE_SERVICE", "heavy")
    clean_env.setenv("ENRICHMENT_PET_SERVICE", "heavy")

    import importlib
    import sys

    if "model" in sys.modules:
        del sys.modules["model"]

    import model as enrichment_light_model

    # Models assigned to 'heavy' should not load on light service
    assert enrichment_light_model._should_load_model("pose") is False
    assert enrichment_light_model._should_load_model("pet") is False

    # Models still assigned to 'light' should load
    assert enrichment_light_model._should_load_model("threat") is True
    assert enrichment_light_model._should_load_model("reid") is True
    assert enrichment_light_model._should_load_model("depth") is True


def test_should_preload_model_with_empty_env(clean_env):
    """Test that _should_preload_model returns False when ENRICHMENT_PRELOAD_MODELS is empty.

    This tests the behavior before the fix: empty ENRICHMENT_PRELOAD_MODELS
    means no models are preloaded (all on-demand).
    """
    clean_env.setenv("ENRICHMENT_PRELOAD_MODELS", "")

    import sys

    if "model" in sys.modules:
        del sys.modules["model"]

    import model as enrichment_light_model

    # No models should be preloaded when env var is empty
    assert enrichment_light_model._should_preload_model("pose_estimator") is False
    assert enrichment_light_model._should_preload_model("threat_detector") is False
    assert enrichment_light_model._should_preload_model("person_reid") is False
    assert enrichment_light_model._should_preload_model("pet_classifier") is False
    assert enrichment_light_model._should_preload_model("depth_estimator") is False


def test_should_preload_model_with_full_list(clean_env):
    """Test that _should_preload_model returns True for models in the preload list.

    This tests the fix for NEM-5376: when ENRICHMENT_PRELOAD_MODELS contains
    all light models, they should all be preloaded.
    """
    clean_env.setenv(
        "ENRICHMENT_PRELOAD_MODELS",
        "pose_estimator,threat_detector,person_reid,pet_classifier,depth_estimator",
    )

    import sys

    if "model" in sys.modules:
        del sys.modules["model"]

    import model as enrichment_light_model

    # All models in the list should be preloaded
    assert enrichment_light_model._should_preload_model("pose_estimator") is True
    assert enrichment_light_model._should_preload_model("threat_detector") is True
    assert enrichment_light_model._should_preload_model("person_reid") is True
    assert enrichment_light_model._should_preload_model("pet_classifier") is True
    assert enrichment_light_model._should_preload_model("depth_estimator") is True


def test_should_preload_model_with_partial_list(clean_env):
    """Test selective preloading: only models in the list are preloaded."""
    clean_env.setenv(
        "ENRICHMENT_PRELOAD_MODELS",
        "pose_estimator,threat_detector",  # Only preload these two
    )

    import sys

    if "model" in sys.modules:
        del sys.modules["model"]

    import model as enrichment_light_model

    # Models in the list should be preloaded
    assert enrichment_light_model._should_preload_model("pose_estimator") is True
    assert enrichment_light_model._should_preload_model("threat_detector") is True

    # Models not in the list should not be preloaded (loaded on-demand)
    assert enrichment_light_model._should_preload_model("person_reid") is False
    assert enrichment_light_model._should_preload_model("pet_classifier") is False
    assert enrichment_light_model._should_preload_model("depth_estimator") is False


def test_two_condition_loading_both_true(clean_env):
    """Test that models load when BOTH conditions are met.

    Condition 1: Model assigned to 'light' service
    Condition 2: Model in ENRICHMENT_PRELOAD_MODELS list
    """
    # Set up: model assigned to light, and in preload list
    clean_env.setenv("ENRICHMENT_POSE_SERVICE", "light")
    clean_env.setenv("ENRICHMENT_PRELOAD_MODELS", "pose_estimator,threat_detector")

    import sys

    if "model" in sys.modules:
        del sys.modules["model"]

    import model as enrichment_light_model

    # Both conditions met - should load
    assert enrichment_light_model._should_load_model("pose") is True
    assert enrichment_light_model._should_preload_model("pose_estimator") is True


def test_two_condition_loading_first_false(clean_env):
    """Test that models DON'T load when first condition fails (assigned to heavy)."""
    # Set up: model assigned to HEAVY (not light), but in preload list
    clean_env.setenv("ENRICHMENT_POSE_SERVICE", "heavy")
    clean_env.setenv("ENRICHMENT_PRELOAD_MODELS", "pose_estimator,threat_detector")

    import sys

    if "model" in sys.modules:
        del sys.modules["model"]

    import model as enrichment_light_model

    # First condition fails - model should NOT load on light service
    assert enrichment_light_model._should_load_model("pose") is False
    # Second condition still passes
    assert enrichment_light_model._should_preload_model("pose_estimator") is True


def test_two_condition_loading_second_false(clean_env):
    """Test that models DON'T preload when second condition fails (not in list)."""
    # Set up: model assigned to light, but NOT in preload list
    clean_env.setenv("ENRICHMENT_POSE_SERVICE", "light")
    clean_env.setenv("ENRICHMENT_PRELOAD_MODELS", "threat_detector")  # pose not in list

    import sys

    if "model" in sys.modules:
        del sys.modules["model"]

    import model as enrichment_light_model

    # First condition passes
    assert enrichment_light_model._should_load_model("pose") is True
    # Second condition fails - model should load on-demand, not preloaded
    assert enrichment_light_model._should_preload_model("pose_estimator") is False


def test_docker_compose_default_value_simulation(clean_env):
    """Test that the docker-compose default value fixes NEM-5376.

    This simulates what happens when docker-compose.prod.yml sets:
      ENRICHMENT_PRELOAD_MODELS=${ENRICHMENT_LIGHT_PRELOAD_MODELS:-pose_estimator,threat_detector,person_reid,pet_classifier,depth_estimator}

    When ENRICHMENT_LIGHT_PRELOAD_MODELS is not set in .env, the default
    kicks in and all models should be preloaded.
    """
    # Simulate the docker-compose default value
    clean_env.setenv(
        "ENRICHMENT_PRELOAD_MODELS",
        "pose_estimator,threat_detector,person_reid,pet_classifier,depth_estimator",
    )

    import sys

    if "model" in sys.modules:
        del sys.modules["model"]

    import model as enrichment_light_model

    # With the fix, all models should be configured to preload
    models = [
        "pose_estimator",
        "threat_detector",
        "person_reid",
        "pet_classifier",
        "depth_estimator",
    ]
    for model_name in models:
        assert enrichment_light_model._should_preload_model(model_name) is True, (
            f"Model {model_name} should be preloaded with docker-compose default"
        )


def test_invalid_model_name_in_preload_list(clean_env):
    """Test that invalid model names in ENRICHMENT_PRELOAD_MODELS are rejected.

    Security test for NEM-4513: validate_preload_models_env should reject
    invalid model names.
    """
    clean_env.setenv(
        "ENRICHMENT_PRELOAD_MODELS",
        "pose_estimator,../../../etc/passwd,threat_detector",  # Path traversal attempt
    )

    import sys

    if "model" in sys.modules:
        del sys.modules["model"]

    import model as enrichment_light_model

    # Invalid model names should be rejected, causing _should_preload_model to return False
    # The function should log an error and return False for all models
    result = enrichment_light_model._should_preload_model("pose_estimator")
    # Result should be False because validation failed
    assert result is False, "Invalid model names should cause validation failure"
