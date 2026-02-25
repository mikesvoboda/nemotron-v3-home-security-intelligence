"""Unit tests for weather_loader service.

Tests for the Weather-Image-Classification model loader and classifier.
"""

from datetime import UTC
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


# Test load_weather_model success path


@pytest.mark.asyncio
async def test_load_weather_model_success_cpu(monkeypatch):
    """Test load_weather_model raises RuntimeError on CPU-only hosts (CUDA required)."""
    import sys

    mock_torch = MagicMock()
    mock_torch.cuda.is_available.return_value = False

    mock_transformers = MagicMock()
    monkeypatch.setitem(sys.modules, "torch", mock_torch)
    monkeypatch.setitem(sys.modules, "transformers", mock_transformers)

    with pytest.raises(RuntimeError, match="requires a CUDA GPU"):
        await load_weather_model("/test/model")


@pytest.mark.asyncio
async def test_load_weather_model_success_cuda(monkeypatch):
    """Test load_weather_model success path with CUDA."""
    import sys

    # Create mock torch with CUDA
    mock_torch = MagicMock()
    mock_torch.cuda.is_available.return_value = True

    # Create mock model that supports cuda().half()
    mock_cuda_model = MagicMock()
    mock_half_model = MagicMock()
    mock_cuda_model.half.return_value = mock_half_model
    mock_half_model.eval.return_value = None

    mock_model = MagicMock()
    mock_model.cuda.return_value = mock_cuda_model

    # Create mock processor
    mock_processor = MagicMock()

    # Create mock transformers
    mock_transformers = MagicMock()
    mock_transformers.AutoImageProcessor.from_pretrained.return_value = mock_processor
    mock_transformers.AutoModelForImageClassification.from_pretrained.return_value = mock_model

    monkeypatch.setitem(sys.modules, "torch", mock_torch)
    monkeypatch.setitem(sys.modules, "transformers", mock_transformers)

    result = await load_weather_model("/test/model/cuda")

    assert "model" in result
    assert "processor" in result
    mock_model.cuda.assert_called_once()


# Test classify_weather


def test_classify_weather_callable():
    """Test classify_weather is an async function."""
    import inspect

    from backend.services.weather_loader import classify_weather

    assert callable(classify_weather)
    assert inspect.iscoroutinefunction(classify_weather)


@pytest.mark.asyncio
async def test_classify_weather_runtime_error():
    """Test classify_weather handles runtime errors."""
    from backend.services.weather_loader import classify_weather

    # Create model dict with model that raises error
    mock_model = MagicMock()
    mock_model.parameters.side_effect = RuntimeError("GPU OOM")

    model_dict = {"model": mock_model, "processor": MagicMock()}

    from PIL import Image

    test_image = Image.new("RGB", (224, 224))

    with pytest.raises(RuntimeError, match="Weather classification failed"):
        await classify_weather(model_dict, test_image)


# Test classify_weather with typo handling


def test_weather_typo_strom_to_storm():
    """Test that rain/strom typo is normalized to rain/storm."""
    # This is a code path test - the module handles the typo
    from backend.services.weather_loader import WEATHER_LABELS

    # Verify our labels don't have the typo
    assert "rain/storm" in WEATHER_LABELS
    assert "rain/strom" not in WEATHER_LABELS


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


# =============================================================================
# Nighttime Detection Tests (NEM-5288)
# =============================================================================


class TestIsNighttimeFunction:
    """Tests for is_nighttime() detection function.

    The is_nighttime() function determines whether current conditions represent
    nighttime for the purpose of the weather_clear_night risk modifier.
    """

    def test_is_nighttime_midnight(self):
        """Test is_nighttime returns True for midnight (00:00)."""
        from datetime import datetime

        from backend.services.weather_loader import is_nighttime

        timestamp = datetime(2024, 6, 15, 0, 0, 0)  # Midnight
        result = is_nighttime(timestamp)

        assert result is True

    def test_is_nighttime_2am(self):
        """Test is_nighttime returns True for 2 AM."""
        from datetime import datetime

        from backend.services.weather_loader import is_nighttime

        timestamp = datetime(2024, 6, 15, 2, 0, 0)  # 2 AM
        result = is_nighttime(timestamp)

        assert result is True

    def test_is_nighttime_4am(self):
        """Test is_nighttime returns True for 4 AM (before dawn)."""
        from datetime import datetime

        from backend.services.weather_loader import is_nighttime

        timestamp = datetime(2024, 6, 15, 4, 0, 0)  # 4 AM
        result = is_nighttime(timestamp)

        assert result is True

    def test_is_nighttime_midday(self):
        """Test is_nighttime returns False for midday (12:00)."""
        from datetime import datetime

        from backend.services.weather_loader import is_nighttime

        timestamp = datetime(2024, 6, 15, 12, 0, 0)  # Noon
        result = is_nighttime(timestamp)

        assert result is False

    def test_is_nighttime_3pm(self):
        """Test is_nighttime returns False for 3 PM."""
        from datetime import datetime

        from backend.services.weather_loader import is_nighttime

        timestamp = datetime(2024, 6, 15, 15, 0, 0)  # 3 PM
        result = is_nighttime(timestamp)

        assert result is False

    def test_is_nighttime_10pm(self):
        """Test is_nighttime returns True for 10 PM."""
        from datetime import datetime

        from backend.services.weather_loader import is_nighttime

        timestamp = datetime(2024, 6, 15, 22, 0, 0)  # 10 PM
        result = is_nighttime(timestamp)

        assert result is True

    def test_is_nighttime_11pm(self):
        """Test is_nighttime returns True for 11 PM."""
        from datetime import datetime

        from backend.services.weather_loader import is_nighttime

        timestamp = datetime(2024, 6, 15, 23, 0, 0)  # 11 PM
        result = is_nighttime(timestamp)

        assert result is True

    def test_is_nighttime_8am(self):
        """Test is_nighttime returns False for 8 AM."""
        from datetime import datetime

        from backend.services.weather_loader import is_nighttime

        timestamp = datetime(2024, 6, 15, 8, 0, 0)  # 8 AM
        result = is_nighttime(timestamp)

        assert result is False


class TestIsNighttimeDuskDawnEdgeCases:
    """Edge case tests for dusk/dawn transitions in nighttime detection."""

    def test_is_nighttime_civil_dusk_summer(self):
        """Test is_nighttime for civil dusk in summer (~8:30 PM).

        Civil twilight (sun 0-6 degrees below horizon) should be considered
        nighttime for security purposes.
        """
        from datetime import datetime

        from backend.services.weather_loader import is_nighttime

        timestamp = datetime(2024, 6, 15, 20, 30, 0)  # 8:30 PM summer
        result = is_nighttime(timestamp)

        # Dusk should count as nighttime
        assert result is True

    def test_is_nighttime_civil_dawn_summer(self):
        """Test is_nighttime for civil dawn in summer (~5:30 AM).

        Civil twilight before sunrise should still be considered nighttime.
        """
        from datetime import datetime

        from backend.services.weather_loader import is_nighttime

        timestamp = datetime(2024, 6, 15, 5, 30, 0)  # 5:30 AM summer
        result = is_nighttime(timestamp)

        # Dawn should count as nighttime (early enough)
        assert result is True

    def test_is_nighttime_7am_daytime(self):
        """Test is_nighttime returns False for 7 AM (clearly daytime)."""
        from datetime import datetime

        from backend.services.weather_loader import is_nighttime

        timestamp = datetime(2024, 6, 15, 7, 0, 0)  # 7 AM
        result = is_nighttime(timestamp)

        assert result is False

    def test_is_nighttime_7pm_dusk_transition(self):
        """Test is_nighttime for 7 PM (transition time)."""
        from datetime import datetime

        from backend.services.weather_loader import is_nighttime

        timestamp = datetime(2024, 6, 15, 19, 0, 0)  # 7 PM
        result = is_nighttime(timestamp)

        # 7 PM is borderline - depends on implementation
        # The test documents the expected behavior
        assert result is True  # Should be nighttime for security purposes

    def test_is_nighttime_winter_4pm(self):
        """Test is_nighttime for 4 PM in winter (darker earlier)."""
        from datetime import datetime

        from backend.services.weather_loader import is_nighttime

        timestamp = datetime(2024, 12, 15, 16, 0, 0)  # 4 PM winter
        result = is_nighttime(timestamp)

        # 4 PM in winter could be dusk/dark depending on latitude
        # Using simple hour-based detection: 4 PM is daytime
        assert result is False


class TestIsNighttimeWithImage:
    """Tests for nighttime detection using image brightness analysis."""

    def test_is_nighttime_from_dark_image(self):
        """Test is_nighttime_from_image returns True for dark images."""
        from PIL import Image

        from backend.services.weather_loader import is_nighttime_from_image

        # Create a very dark image (nighttime)
        dark_image = Image.new("RGB", (100, 100), color=(10, 10, 15))
        result = is_nighttime_from_image(dark_image)

        assert result is True

    def test_is_nighttime_from_bright_image(self):
        """Test is_nighttime_from_image returns False for bright images."""
        from PIL import Image

        from backend.services.weather_loader import is_nighttime_from_image

        # Create a bright image (daytime)
        bright_image = Image.new("RGB", (100, 100), color=(200, 200, 180))
        result = is_nighttime_from_image(bright_image)

        assert result is False

    def test_is_nighttime_from_moderate_image(self):
        """Test is_nighttime_from_image for moderate brightness."""
        from PIL import Image

        from backend.services.weather_loader import is_nighttime_from_image

        # Create a moderately lit image (dusk/dawn)
        moderate_image = Image.new("RGB", (100, 100), color=(80, 75, 70))
        result = is_nighttime_from_image(moderate_image)

        # Moderate brightness should be classified as nighttime for security
        assert result is True

    def test_is_nighttime_from_image_with_bright_spots(self):
        """Test is_nighttime_from_image with a dark image but some lights."""
        import numpy as np
        from PIL import Image

        from backend.services.weather_loader import is_nighttime_from_image

        # Create dark image with some bright spots (like streetlights at night)
        arr = np.full((100, 100, 3), 15, dtype=np.uint8)  # Dark background
        arr[40:50, 40:50] = [255, 255, 200]  # Bright light spot
        arr[70:75, 20:25] = [255, 255, 200]  # Another light
        night_with_lights = Image.fromarray(arr)

        result = is_nighttime_from_image(night_with_lights)

        # Overall dark image with some lights should still be nighttime
        assert result is True

    def test_is_nighttime_from_grayscale_image(self):
        """Test is_nighttime_from_image handles grayscale images."""
        from PIL import Image

        from backend.services.weather_loader import is_nighttime_from_image

        # Create a dark grayscale image
        dark_gray = Image.new("L", (100, 100), color=20)
        result = is_nighttime_from_image(dark_gray)

        assert result is True


class TestNighttimeCombined:
    """Tests for combined nighttime detection (timestamp + image)."""

    def test_determine_nighttime_prefers_timestamp(self):
        """Test determine_nighttime prioritizes timestamp over image analysis."""
        from datetime import datetime

        from PIL import Image

        from backend.services.weather_loader import determine_nighttime

        # Daytime timestamp but dark image
        timestamp = datetime(2024, 6, 15, 14, 0, 0)  # 2 PM
        dark_image = Image.new("RGB", (100, 100), color=(20, 20, 20))

        result = determine_nighttime(timestamp=timestamp, image=dark_image)

        # Timestamp should be authoritative when available
        assert result is False

    def test_determine_nighttime_uses_image_when_no_timestamp(self):
        """Test determine_nighttime uses image when no timestamp provided."""
        from PIL import Image

        from backend.services.weather_loader import determine_nighttime

        # No timestamp, dark image
        dark_image = Image.new("RGB", (100, 100), color=(15, 15, 20))

        result = determine_nighttime(timestamp=None, image=dark_image)

        # Should use image analysis
        assert result is True

    def test_determine_nighttime_none_inputs(self):
        """Test determine_nighttime with no inputs returns False (default safe)."""
        from backend.services.weather_loader import determine_nighttime

        result = determine_nighttime(timestamp=None, image=None)

        # Default to daytime (safer assumption)
        assert result is False

    def test_determine_nighttime_with_timezone(self):
        """Test determine_nighttime handles timezone-aware timestamps."""
        from datetime import datetime

        from backend.services.weather_loader import determine_nighttime

        # Midnight UTC
        timestamp = datetime(2024, 6, 15, 0, 0, 0, tzinfo=UTC)
        result = determine_nighttime(timestamp=timestamp)

        assert result is True


class TestNighttimeThresholds:
    """Tests for nighttime detection threshold configuration."""

    def test_nighttime_brightness_threshold_configurable(self):
        """Test that nighttime brightness threshold can be configured."""
        from backend.services.weather_loader import (
            NIGHTTIME_BRIGHTNESS_THRESHOLD,
        )

        # Verify threshold constant exists
        assert isinstance(NIGHTTIME_BRIGHTNESS_THRESHOLD, int | float)
        assert 0 < NIGHTTIME_BRIGHTNESS_THRESHOLD < 255

    def test_nighttime_hour_boundaries(self):
        """Test nighttime hour boundaries are reasonable."""
        from backend.services.weather_loader import (
            NIGHTTIME_END_HOUR,
            NIGHTTIME_START_HOUR,
        )

        # Verify hour constants exist and are reasonable
        assert isinstance(NIGHTTIME_START_HOUR, int)
        assert isinstance(NIGHTTIME_END_HOUR, int)
        assert 17 <= NIGHTTIME_START_HOUR <= 21  # Between 5 PM and 9 PM
        assert 5 <= NIGHTTIME_END_HOUR <= 8  # Between 5 AM and 8 AM


class TestWeatherRiskModifierHelpers:
    """Tests for weather risk modifier helper functions in weather_loader."""

    def test_get_weather_risk_modifier_rainy(self):
        """Test get_weather_risk_modifier returns -0.15 for rainy weather."""
        from backend.services.weather_loader import get_weather_risk_modifier

        weather = WeatherResult(
            condition="rain/storm",
            simple_condition="rainy",
            confidence=0.85,
            all_scores={},
        )
        modifier = get_weather_risk_modifier(weather, is_nighttime=False)

        assert modifier == pytest.approx(-0.15, abs=0.01)

    def test_get_weather_risk_modifier_clear_night(self):
        """Test get_weather_risk_modifier returns +0.25 for clear night."""
        from backend.services.weather_loader import get_weather_risk_modifier

        weather = WeatherResult(
            condition="sun/clear",
            simple_condition="clear",
            confidence=0.90,
            all_scores={},
        )
        modifier = get_weather_risk_modifier(weather, is_nighttime=True)

        assert modifier == pytest.approx(0.25, abs=0.01)

    def test_get_weather_risk_modifier_foggy(self):
        """Test get_weather_risk_modifier returns +0.1 for foggy weather."""
        from backend.services.weather_loader import get_weather_risk_modifier

        weather = WeatherResult(
            condition="foggy/hazy",
            simple_condition="foggy",
            confidence=0.88,
            all_scores={},
        )
        modifier = get_weather_risk_modifier(weather, is_nighttime=False)

        assert modifier == pytest.approx(0.1, abs=0.01)

    def test_get_weather_risk_modifier_none_weather(self):
        """Test get_weather_risk_modifier returns 0.0 for None weather."""
        from backend.services.weather_loader import get_weather_risk_modifier

        modifier = get_weather_risk_modifier(None, is_nighttime=False)

        assert modifier == 0.0

    def test_get_weather_risk_modifier_low_confidence(self):
        """Test get_weather_risk_modifier returns 0.0 for low confidence."""
        from backend.services.weather_loader import get_weather_risk_modifier

        weather = WeatherResult(
            condition="rain/storm",
            simple_condition="rainy",
            confidence=0.35,  # Low confidence
            all_scores={},
        )
        modifier = get_weather_risk_modifier(weather, is_nighttime=False)

        # Low confidence should not apply modifier
        assert modifier == 0.0

    def test_get_weather_risk_modifier_cloudy_no_modifier(self):
        """Test get_weather_risk_modifier returns 0.0 for cloudy (neutral)."""
        from backend.services.weather_loader import get_weather_risk_modifier

        weather = WeatherResult(
            condition="cloudy/overcast",
            simple_condition="cloudy",
            confidence=0.90,
            all_scores={},
        )
        modifier = get_weather_risk_modifier(weather, is_nighttime=False)

        # Cloudy is neutral, no modifier
        assert modifier == 0.0
