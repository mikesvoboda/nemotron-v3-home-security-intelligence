"""Unit tests for weather_loader service.

Tests for the Weather-Image-Classification model loader and classifier.
"""

from unittest.mock import MagicMock

import pytest

from backend.services.weather_loader import (
    WEATHER_LABELS,
    WEATHER_SIMPLE_LABELS,
    WeatherResult,
    format_weather_for_nemotron,
    get_visibility_factor,
    load_weather_model,
    weather_affects_visibility,
)

# Test WeatherResult dataclass


def test_weather_result_creation():
    """Test WeatherResult dataclass creation."""
    result = WeatherResult(
        condition="cloudy/overcast",
        simple_condition="cloudy",
        confidence=0.87,
        all_scores={
            "cloudy/overcast": 0.87,
            "foggy/hazy": 0.08,
            "rain/storm": 0.03,
            "snow/frosty": 0.01,
            "sun/clear": 0.01,
        },
    )

    assert result.condition == "cloudy/overcast"
    assert result.simple_condition == "cloudy"
    assert result.confidence == 0.87
    assert len(result.all_scores) == 5


def test_weather_result_to_dict():
    """Test WeatherResult.to_dict() method."""
    result = WeatherResult(
        condition="rain/storm",
        simple_condition="rainy",
        confidence=0.92,
        all_scores={"rain/storm": 0.92, "cloudy/overcast": 0.05},
    )

    d = result.to_dict()

    assert d["condition"] == "rain/storm"
    assert d["simple_condition"] == "rainy"
    assert d["confidence"] == 0.92
    assert d["all_scores"]["rain/storm"] == 0.92


def test_weather_result_to_context_string():
    """Test WeatherResult.to_context_string() method."""
    result = WeatherResult(
        condition="foggy/hazy",
        simple_condition="foggy",
        confidence=0.75,
        all_scores={"foggy/hazy": 0.75},
    )

    context = result.to_context_string()

    assert "foggy" in context
    assert "75%" in context
    assert "Weather" in context


def test_weather_result_context_string_high_confidence():
    """Test context string with high confidence."""
    result = WeatherResult(
        condition="sun/clear",
        simple_condition="clear",
        confidence=0.99,
        all_scores={"sun/clear": 0.99},
    )

    context = result.to_context_string()

    assert "clear" in context
    assert "99%" in context


# Test constants


def test_weather_labels_count():
    """Test that all 5 weather labels are defined."""
    assert len(WEATHER_LABELS) == 5


def test_weather_labels_content():
    """Test weather label contents."""
    expected = ["cloudy/overcast", "foggy/hazy", "rain/storm", "snow/frosty", "sun/clear"]
    assert expected == WEATHER_LABELS


def test_weather_simple_labels_mapping():
    """Test simple label mappings."""
    assert WEATHER_SIMPLE_LABELS["cloudy/overcast"] == "cloudy"
    assert WEATHER_SIMPLE_LABELS["foggy/hazy"] == "foggy"
    assert WEATHER_SIMPLE_LABELS["rain/storm"] == "rainy"
    assert WEATHER_SIMPLE_LABELS["snow/frosty"] == "snowy"
    assert WEATHER_SIMPLE_LABELS["sun/clear"] == "clear"


def test_all_labels_have_simple_mapping():
    """Test that all labels have simple mappings."""
    for label in WEATHER_LABELS:
        assert label in WEATHER_SIMPLE_LABELS


# Test format_weather_for_nemotron


def test_format_weather_none():
    """Test format_weather_for_nemotron with None input."""
    result = format_weather_for_nemotron(None)
    assert "unknown" in result.lower()


def test_format_weather_clear():
    """Test format_weather_for_nemotron with clear weather."""
    weather = WeatherResult(
        condition="sun/clear",
        simple_condition="clear",
        confidence=0.95,
        all_scores={"sun/clear": 0.95},
    )

    result = format_weather_for_nemotron(weather)

    assert "clear" in result
    assert "95%" in result
    assert "visibility" in result.lower()


def test_format_weather_foggy():
    """Test format_weather_for_nemotron with foggy weather."""
    weather = WeatherResult(
        condition="foggy/hazy",
        simple_condition="foggy",
        confidence=0.88,
        all_scores={"foggy/hazy": 0.88},
    )

    result = format_weather_for_nemotron(weather)

    assert "foggy" in result
    assert "reduced" in result.lower()


def test_format_weather_rainy():
    """Test format_weather_for_nemotron with rainy weather."""
    weather = WeatherResult(
        condition="rain/storm",
        simple_condition="rainy",
        confidence=0.72,
        all_scores={"rain/storm": 0.72},
    )

    result = format_weather_for_nemotron(weather)

    assert "rainy" in result
    assert "72%" in result


def test_format_weather_snowy():
    """Test format_weather_for_nemotron with snowy weather."""
    weather = WeatherResult(
        condition="snow/frosty",
        simple_condition="snowy",
        confidence=0.81,
        all_scores={"snow/frosty": 0.81},
    )

    result = format_weather_for_nemotron(weather)

    assert "snowy" in result


def test_format_weather_cloudy():
    """Test format_weather_for_nemotron with cloudy weather."""
    weather = WeatherResult(
        condition="cloudy/overcast",
        simple_condition="cloudy",
        confidence=0.65,
        all_scores={"cloudy/overcast": 0.65},
    )

    result = format_weather_for_nemotron(weather)

    assert "cloudy" in result


# Test weather_affects_visibility


def test_visibility_affected_foggy():
    """Test visibility is affected by foggy weather."""
    weather = WeatherResult(
        condition="foggy/hazy",
        simple_condition="foggy",
        confidence=0.9,
        all_scores={},
    )
    assert weather_affects_visibility(weather) is True


def test_visibility_affected_rainy():
    """Test visibility is affected by rainy weather."""
    weather = WeatherResult(
        condition="rain/storm",
        simple_condition="rainy",
        confidence=0.85,
        all_scores={},
    )
    assert weather_affects_visibility(weather) is True


def test_visibility_affected_snowy():
    """Test visibility is affected by snowy weather."""
    weather = WeatherResult(
        condition="snow/frosty",
        simple_condition="snowy",
        confidence=0.78,
        all_scores={},
    )
    assert weather_affects_visibility(weather) is True


def test_visibility_not_affected_clear():
    """Test visibility is not affected by clear weather."""
    weather = WeatherResult(
        condition="sun/clear",
        simple_condition="clear",
        confidence=0.92,
        all_scores={},
    )
    assert weather_affects_visibility(weather) is False


def test_visibility_not_affected_cloudy():
    """Test visibility is not affected by cloudy weather."""
    weather = WeatherResult(
        condition="cloudy/overcast",
        simple_condition="cloudy",
        confidence=0.88,
        all_scores={},
    )
    assert weather_affects_visibility(weather) is False


def test_visibility_none_weather():
    """Test visibility check with None weather."""
    assert weather_affects_visibility(None) is False


# Test get_visibility_factor


def test_visibility_factor_clear():
    """Test visibility factor for clear weather."""
    weather = WeatherResult(
        condition="sun/clear",
        simple_condition="clear",
        confidence=1.0,
        all_scores={},
    )
    factor = get_visibility_factor(weather)
    assert factor == 1.0


def test_visibility_factor_cloudy():
    """Test visibility factor for cloudy weather."""
    weather = WeatherResult(
        condition="cloudy/overcast",
        simple_condition="cloudy",
        confidence=1.0,
        all_scores={},
    )
    factor = get_visibility_factor(weather)
    assert factor == 0.9


def test_visibility_factor_rainy():
    """Test visibility factor for rainy weather."""
    weather = WeatherResult(
        condition="rain/storm",
        simple_condition="rainy",
        confidence=1.0,
        all_scores={},
    )
    factor = get_visibility_factor(weather)
    assert factor == 0.7


def test_visibility_factor_foggy():
    """Test visibility factor for foggy weather."""
    weather = WeatherResult(
        condition="foggy/hazy",
        simple_condition="foggy",
        confidence=1.0,
        all_scores={},
    )
    factor = get_visibility_factor(weather)
    assert factor == 0.5


def test_visibility_factor_snowy():
    """Test visibility factor for snowy weather."""
    weather = WeatherResult(
        condition="snow/frosty",
        simple_condition="snowy",
        confidence=1.0,
        all_scores={},
    )
    factor = get_visibility_factor(weather)
    assert factor == 0.5


def test_visibility_factor_none():
    """Test visibility factor with None weather."""
    factor = get_visibility_factor(None)
    assert factor == 0.8  # Default neutral value


def test_visibility_factor_low_confidence():
    """Test visibility factor adjusts for low confidence."""
    weather = WeatherResult(
        condition="foggy/hazy",
        simple_condition="foggy",
        confidence=0.5,  # 50% confidence
        all_scores={},
    )
    factor = get_visibility_factor(weather)
    # With 50% confidence, factor should be between 0.5 and 0.8
    assert 0.5 < factor < 0.8


# Test load_weather_model error handling


@pytest.mark.asyncio
async def test_load_weather_model_import_error(monkeypatch):
    """Test load_weather_model handles ImportError."""
    import builtins
    import sys

    # Remove transformers from imports if present
    modules_to_hide = ["transformers", "torch"]
    hidden_modules = {}
    for mod in modules_to_hide:
        if mod in sys.modules:
            hidden_modules[mod] = sys.modules.pop(mod)

    # Mock import to raise ImportError
    original_import = builtins.__import__

    def mock_import(name, *args, **kwargs):
        if name in ("transformers", "torch"):
            raise ImportError(f"No module named '{name}'")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", mock_import)

    try:
        with pytest.raises(ImportError, match="transformers and torch"):
            await load_weather_model("/fake/path")
    finally:
        # Restore hidden modules
        sys.modules.update(hidden_modules)


@pytest.mark.asyncio
async def test_load_weather_model_runtime_error(monkeypatch):
    """Test load_weather_model handles RuntimeError."""
    import sys

    # Mock torch and transformers to exist but fail on model load
    mock_torch = MagicMock()
    mock_torch.cuda.is_available.return_value = False
    mock_transformers = MagicMock()
    mock_transformers.AutoImageProcessor.from_pretrained.side_effect = RuntimeError(
        "Model not found"
    )

    monkeypatch.setitem(sys.modules, "torch", mock_torch)
    monkeypatch.setitem(sys.modules, "transformers", mock_transformers)

    with pytest.raises(RuntimeError, match="Failed to load Weather"):
        await load_weather_model("/nonexistent/path")


# Test model_zoo integration


def test_weather_model_in_zoo():
    """Test weather-classification is registered in MODEL_ZOO."""
    from backend.services.model_zoo import get_model_zoo

    zoo = get_model_zoo()
    assert "weather-classification" in zoo

    config = zoo["weather-classification"]
    assert config.name == "weather-classification"
    assert config.vram_mb == 200
    assert config.category == "classification"
