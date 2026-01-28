"""Scenario template library for synthetic data generation.

This module provides access to all scenario templates used for generating
synthetic security camera footage with known ground truth labels.

Usage:
    from scripts.synthetic.scenarios import (
        get_scenario,
        list_scenarios,
        get_time_modifier,
        get_weather_modifier,
        apply_modifiers,
    )

    # Get a specific scenario
    scenario = get_scenario("loitering")

    # List all available scenarios
    all_scenarios = list_scenarios()

    # Get environmental modifiers
    night = get_time_modifier("night")
    rain = get_weather_modifier("rain_heavy")

    # Apply modifiers to a scenario
    modified = apply_modifiers(scenario, time="night", weather="rain_light")
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

# Base path for scenario templates
SCENARIOS_DIR = Path(__file__).parent

# Category directories
NORMAL_DIR = SCENARIOS_DIR / "normal"
SUSPICIOUS_DIR = SCENARIOS_DIR / "suspicious"
THREATS_DIR = SCENARIOS_DIR / "threats"
ENVIRONMENTAL_DIR = SCENARIOS_DIR / "environmental"

# Cache for loaded scenarios
_scenario_cache: dict[str, dict[str, Any]] = {}
_time_modifiers_cache: dict[str, dict[str, Any]] | None = None
_weather_modifiers_cache: dict[str, dict[str, Any]] | None = None


class ScenarioNotFoundError(Exception):
    """Raised when a requested scenario template is not found."""

    pass


class ModifierNotFoundError(Exception):
    """Raised when a requested environmental modifier is not found."""

    pass


def _load_json_file(path: Path) -> dict[str, Any]:
    """Load and parse a JSON file."""
    with open(path, encoding="utf-8") as f:  # nosemgrep
        data: dict[str, Any] = json.load(f)
        return data


def _discover_scenarios() -> dict[str, Path]:
    """Discover all available scenario template files.

    Returns:
        Dictionary mapping scenario IDs to their file paths.
    """
    scenarios: dict[str, Path] = {}

    for category_dir in [NORMAL_DIR, SUSPICIOUS_DIR, THREATS_DIR]:
        if not category_dir.exists():
            continue

        for json_file in category_dir.glob("*.json"):
            # Use filename without extension as the scenario ID
            scenario_id = json_file.stem
            scenarios[scenario_id] = json_file

    return scenarios


def _load_scenario(scenario_id: str) -> dict[str, Any]:
    """Load a scenario template from disk.

    Args:
        scenario_id: The scenario identifier (e.g., "loitering", "break_in_attempt").

    Returns:
        The parsed scenario template dictionary.

    Raises:
        ScenarioNotFoundError: If the scenario template is not found.
    """
    if scenario_id in _scenario_cache:
        return copy.deepcopy(_scenario_cache[scenario_id])

    available = _discover_scenarios()

    if scenario_id not in available:
        raise ScenarioNotFoundError(
            f"Scenario '{scenario_id}' not found. Available scenarios: {sorted(available.keys())}"
        )

    scenario = _load_json_file(available[scenario_id])
    _scenario_cache[scenario_id] = scenario

    return copy.deepcopy(scenario)


def _load_time_modifiers() -> dict[str, dict[str, Any]]:
    """Load time modifiers from the environmental directory."""
    global _time_modifiers_cache  # noqa: PLW0603

    if _time_modifiers_cache is not None:
        return _time_modifiers_cache

    time_file = ENVIRONMENTAL_DIR / "time_modifiers.json"
    if not time_file.exists():
        _time_modifiers_cache = {}
        return _time_modifiers_cache

    data = _load_json_file(time_file)
    _time_modifiers_cache = {mod["id"]: mod for mod in data.get("modifiers", [])}

    return _time_modifiers_cache


def _load_weather_modifiers() -> dict[str, dict[str, Any]]:
    """Load weather modifiers from the environmental directory."""
    global _weather_modifiers_cache  # noqa: PLW0603

    if _weather_modifiers_cache is not None:
        return _weather_modifiers_cache

    weather_file = ENVIRONMENTAL_DIR / "weather_modifiers.json"
    if not weather_file.exists():
        _weather_modifiers_cache = {}
        return _weather_modifiers_cache

    data = _load_json_file(weather_file)
    _weather_modifiers_cache = {mod["id"]: mod for mod in data.get("modifiers", [])}

    return _weather_modifiers_cache


def get_scenario(scenario_id: str) -> dict[str, Any]:
    """Get a scenario template by ID.

    Args:
        scenario_id: The scenario identifier (e.g., "loitering", "break_in_attempt").

    Returns:
        A deep copy of the scenario template dictionary.

    Raises:
        ScenarioNotFoundError: If the scenario is not found.

    Example:
        >>> scenario = get_scenario("loitering")
        >>> print(scenario["name"])
        'Loitering Person'
    """
    return _load_scenario(scenario_id)


def get_scenario_variation(scenario_id: str, variation_id: str) -> dict[str, Any]:
    """Get a specific variation of a scenario.

    Args:
        scenario_id: The base scenario identifier.
        variation_id: The variation identifier within the scenario.

    Returns:
        The scenario with the variation's overrides applied.

    Raises:
        ScenarioNotFoundError: If the scenario or variation is not found.

    Example:
        >>> scenario = get_scenario_variation("loitering", "loitering_extended")
        >>> print(scenario["expected_outputs"]["risk"]["level"])
        'high'
    """
    scenario = _load_scenario(scenario_id)

    # Find the variation
    variation = None
    for var in scenario.get("variations", []):
        if var.get("id") == variation_id:
            variation = var
            break

    if variation is None:
        available_variations = [v.get("id") for v in scenario.get("variations", [])]
        raise ScenarioNotFoundError(
            f"Variation '{variation_id}' not found in scenario '{scenario_id}'. "
            f"Available variations: {available_variations}"
        )

    # Apply overrides
    return _apply_variation(scenario, variation)


def _apply_variation(scenario: dict[str, Any], variation: dict[str, Any]) -> dict[str, Any]:
    """Apply a variation's overrides to a base scenario."""
    result = copy.deepcopy(scenario)

    # Apply environment overrides
    if "environment_overrides" in variation:
        result["environment"].update(variation["environment_overrides"])

    # Apply scene overrides
    if "scene_overrides" in variation:
        result["scene"].update(variation["scene_overrides"])

    # Apply subject overrides
    if "subject_overrides" in variation:
        for override in variation["subject_overrides"]:
            index = override.get("index", 0)
            if index < len(result["subjects"]):
                for key, value in override.items():
                    if key != "index":
                        if isinstance(value, dict) and key in result["subjects"][index]:
                            result["subjects"][index][key].update(value)
                        else:
                            result["subjects"][index][key] = value

    # Append additional subjects
    if "subjects_append" in variation:
        result["subjects"].extend(variation["subjects_append"])

    # Replace subjects entirely if provided
    if "subjects" in variation:
        result["subjects"] = variation["subjects"]

    # Apply expected output overrides
    if "expected_output_overrides" in variation:
        _deep_update(result["expected_outputs"], variation["expected_output_overrides"])

    # Update variation metadata
    result["applied_variation"] = {
        "id": variation.get("id"),
        "name": variation.get("name"),
    }

    return result


def _deep_update(base: dict[str, Any], updates: dict[str, Any]) -> None:
    """Recursively update a dictionary with another dictionary."""
    for key, value in updates.items():
        if key in base and isinstance(base[key], dict) and isinstance(value, dict):
            _deep_update(base[key], value)
        else:
            base[key] = value


def list_scenarios() -> dict[str, list[str]]:
    """List all available scenario templates grouped by category.

    Returns:
        Dictionary mapping category names to lists of scenario IDs.

    Example:
        >>> scenarios = list_scenarios()
        >>> print(scenarios["suspicious"])
        ['loitering', 'prowling', 'casing']
    """
    result: dict[str, list[str]] = {
        "normal": [],
        "suspicious": [],
        "threats": [],
    }

    for category, category_dir in [
        ("normal", NORMAL_DIR),
        ("suspicious", SUSPICIOUS_DIR),
        ("threats", THREATS_DIR),
    ]:
        if category_dir.exists():
            result[category] = sorted([f.stem for f in category_dir.glob("*.json")])

    return result


def list_all_scenarios() -> list[str]:
    """List all available scenario template IDs.

    Returns:
        Sorted list of all scenario IDs across all categories.

    Example:
        >>> all_ids = list_all_scenarios()
        >>> "loitering" in all_ids
        True
    """
    return sorted(_discover_scenarios().keys())


def get_time_modifier(modifier_id: str) -> dict[str, Any]:
    """Get a time-of-day modifier by ID.

    Args:
        modifier_id: The modifier identifier (e.g., "night", "dawn", "dusk").

    Returns:
        A deep copy of the time modifier dictionary.

    Raises:
        ModifierNotFoundError: If the modifier is not found.

    Example:
        >>> night = get_time_modifier("night")
        >>> print(night["prompt_description"])
        'Nighttime with artificial lighting...'
    """
    modifiers = _load_time_modifiers()

    if modifier_id not in modifiers:
        raise ModifierNotFoundError(
            f"Time modifier '{modifier_id}' not found. "
            f"Available modifiers: {sorted(modifiers.keys())}"
        )

    return copy.deepcopy(modifiers[modifier_id])


def get_weather_modifier(modifier_id: str) -> dict[str, Any]:
    """Get a weather modifier by ID.

    Args:
        modifier_id: The modifier identifier (e.g., "rain_heavy", "fog", "snow_light").

    Returns:
        A deep copy of the weather modifier dictionary.

    Raises:
        ModifierNotFoundError: If the modifier is not found.

    Example:
        >>> fog = get_weather_modifier("fog")
        >>> print(fog["environment_settings"]["visibility"])
        'low'
    """
    modifiers = _load_weather_modifiers()

    if modifier_id not in modifiers:
        raise ModifierNotFoundError(
            f"Weather modifier '{modifier_id}' not found. "
            f"Available modifiers: {sorted(modifiers.keys())}"
        )

    return copy.deepcopy(modifiers[modifier_id])


def list_time_modifiers() -> list[str]:
    """List all available time modifier IDs.

    Returns:
        List of time modifier IDs.

    Example:
        >>> modifiers = list_time_modifiers()
        >>> "night" in modifiers
        True
    """
    return sorted(_load_time_modifiers().keys())


def list_weather_modifiers() -> list[str]:
    """List all available weather modifier IDs.

    Returns:
        List of weather modifier IDs.

    Example:
        >>> modifiers = list_weather_modifiers()
        >>> "fog" in modifiers
        True
    """
    return sorted(_load_weather_modifiers().keys())


def apply_modifiers(
    scenario: dict[str, Any],
    *,
    time: str | None = None,
    weather: str | None = None,
) -> dict[str, Any]:
    """Apply environmental modifiers to a scenario.

    Args:
        scenario: The base scenario dictionary.
        time: Optional time modifier ID (e.g., "night", "dawn").
        weather: Optional weather modifier ID (e.g., "rain_heavy", "fog").

    Returns:
        A new scenario dictionary with modifiers applied.

    Raises:
        ModifierNotFoundError: If a specified modifier is not found.

    Example:
        >>> scenario = get_scenario("loitering")
        >>> modified = apply_modifiers(scenario, time="night", weather="rain_light")
        >>> print(modified["environment"]["weather"])
        'rain_light'
    """
    result = copy.deepcopy(scenario)

    # Track applied modifiers
    result["applied_modifiers"] = {
        "time": time,
        "weather": weather,
    }

    # Apply time modifier
    if time is not None:
        time_mod = get_time_modifier(time)

        # Update environment settings
        result["environment"].update(time_mod["environment_settings"])
        result["environment"]["time_of_day"] = time_mod["time_of_day"]

        # Add camera effects if suggested
        suggested = time_mod.get("camera_adjustments", {}).get("suggested_effects", [])
        existing_effects = set(result.get("scene", {}).get("camera_effects", []))
        result["scene"]["camera_effects"] = list(existing_effects | set(suggested))

        # Apply risk modifier
        risk_mod = time_mod.get("risk_modifier", {})
        if "expected_outputs" in result and "risk" in result["expected_outputs"]:
            adjustment = risk_mod.get("base_adjustment", 0)
            result["expected_outputs"]["risk"]["min_score"] = min(
                100,
                result["expected_outputs"]["risk"].get("min_score", 0) + adjustment,
            )
            result["expected_outputs"]["risk"]["max_score"] = min(
                100,
                result["expected_outputs"]["risk"].get("max_score", 100) + adjustment,
            )

            # Add factors
            factors = result["expected_outputs"]["risk"].get("expected_factors", [])
            for factor in risk_mod.get("factors_to_add", []):
                if factor not in factors:
                    factors.append(factor)
            result["expected_outputs"]["risk"]["expected_factors"] = factors

        # Store prompt description for generation
        result["_time_prompt"] = time_mod.get("prompt_description", "")

    # Apply weather modifier
    if weather is not None:
        weather_mod = get_weather_modifier(weather)

        # Update environment settings (weather takes precedence for precipitation/visibility)
        for key, value in weather_mod["environment_settings"].items():
            result["environment"][key] = value
        result["environment"]["weather"] = weather_mod["weather"]

        # Add camera effects if suggested
        suggested = weather_mod.get("camera_adjustments", {}).get("suggested_effects", [])
        existing_effects = set(result.get("scene", {}).get("camera_effects", []))
        result["scene"]["camera_effects"] = list(existing_effects | set(suggested))

        # Apply expected output impacts
        impact = weather_mod.get("expected_output_impact", {})
        if impact and "expected_outputs" in result:
            _deep_update(result["expected_outputs"], impact)

        # Store prompt description for generation
        result["_weather_prompt"] = weather_mod.get("prompt_description", "")

    return result


def get_scenario_with_modifiers(
    scenario_id: str,
    variation_id: str | None = None,
    time: str | None = None,
    weather: str | None = None,
) -> dict[str, Any]:
    """Get a scenario with optional variation and environmental modifiers.

    This is a convenience function that combines get_scenario, get_scenario_variation,
    and apply_modifiers into a single call.

    Args:
        scenario_id: The scenario identifier.
        variation_id: Optional variation identifier.
        time: Optional time modifier ID.
        weather: Optional weather modifier ID.

    Returns:
        The fully configured scenario dictionary.

    Example:
        >>> scenario = get_scenario_with_modifiers(
        ...     "loitering",
        ...     variation_id="loitering_extended",
        ...     time="night",
        ...     weather="rain_light"
        ... )
    """
    if variation_id:
        scenario = get_scenario_variation(scenario_id, variation_id)
    else:
        scenario = get_scenario(scenario_id)

    if time or weather:
        scenario = apply_modifiers(scenario, time=time, weather=weather)

    return scenario


def clear_cache() -> None:
    """Clear all cached scenario and modifier data.

    Useful for testing or when scenario files are modified.
    """
    global _scenario_cache, _time_modifiers_cache, _weather_modifiers_cache  # noqa: PLW0602, PLW0603

    _scenario_cache.clear()
    _time_modifiers_cache = None
    _weather_modifiers_cache = None


# Public API
__all__ = [
    "ENVIRONMENTAL_DIR",
    "NORMAL_DIR",
    "SCENARIOS_DIR",
    "SUSPICIOUS_DIR",
    "THREATS_DIR",
    "ModifierNotFoundError",
    "ScenarioNotFoundError",
    "apply_modifiers",
    "clear_cache",
    "get_scenario",
    "get_scenario_variation",
    "get_scenario_with_modifiers",
    "get_time_modifier",
    "get_weather_modifier",
    "list_all_scenarios",
    "list_scenarios",
    "list_time_modifiers",
    "list_weather_modifiers",
]
