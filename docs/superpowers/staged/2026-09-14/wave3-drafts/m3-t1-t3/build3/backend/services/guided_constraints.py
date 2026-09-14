"""NVIDIA NIM guided generation constraints for risk analysis.

This module provides guided_choice and guided_regex configurations for
NVIDIA NIM's constrained decoding feature, ensuring valid outputs for
risk levels, recommended actions, entity types, and threat levels.

The guided_choice parameter constrains the LLM to output only from a
predefined set of valid choices, eliminating parsing errors and invalid
values.

See NEM-3729 for implementation details.
"""

from __future__ import annotations

# =============================================================================
# Choice Constants
# =============================================================================

# Risk level choices for guided_choice parameter
RISK_LEVEL_CHOICES: list[str] = ["low", "medium", "high", "critical"]

# Recommended action choices
RECOMMENDED_ACTION_CHOICES: list[str] = [
    "none",
    "review_later",
    "review_soon",
    "alert_homeowner",
    "immediate_response",
]

# Entity type choices
ENTITY_TYPE_CHOICES: list[str] = ["person", "vehicle", "animal", "object"]

# Threat level choices for entities
THREAT_LEVEL_CHOICES: list[str] = ["low", "medium", "high"]


# =============================================================================
# Configuration Functions
# =============================================================================


def get_guided_choice_config(field: str) -> dict[str, dict[str, list[str]]] | None:
    """Get guided_choice configuration for a specific field.

    Args:
        field: Field name (risk_level, recommended_action, entity_type, threat_level)

    Returns:
        Dict with nvext guided_choice config, or None if field not supported

    Example:
        >>> config = get_guided_choice_config("risk_level")
        >>> config
        {'nvext': {'guided_choice': ['low', 'medium', 'high', 'critical']}}
    """
    choices_map: dict[str, list[str]] = {
        "risk_level": RISK_LEVEL_CHOICES,
        "recommended_action": RECOMMENDED_ACTION_CHOICES,
        "entity_type": ENTITY_TYPE_CHOICES,
        "threat_level": THREAT_LEVEL_CHOICES,
    }

    if field not in choices_map:
        return None

    return {"nvext": {"guided_choice": choices_map[field]}}


def get_guided_regex_config(field: str) -> dict[str, dict[str, str]] | None:
    """Get guided_regex configuration for numeric fields.

    Args:
        field: Field name (risk_score, threat_level_score, intent_score, time_context_score)

    Returns:
        Dict with nvext guided_regex config, or None if field not supported

    Example:
        >>> config = get_guided_regex_config("risk_score")
        >>> config
        {'nvext': {'guided_regex': '[0-9]|[1-9][0-9]|100'}}
    """
    regex_map: dict[str, str] = {
        "risk_score": r"[0-9]|[1-9][0-9]|100",  # 0-100
        "threat_level_score": r"[0-4]",  # 0-4
        "intent_score": r"[0-3]",  # 0-3
        "time_context_score": r"[0-2]",  # 0-2
    }

    if field not in regex_map:
        return None

    return {"nvext": {"guided_regex": regex_map[field]}}


# =============================================================================
# Validation Functions
# =============================================================================


def validate_risk_level(level: str) -> bool:
    """Validate that a risk level is valid.

    Args:
        level: Risk level string to validate

    Returns:
        True if the level is valid, False otherwise

    Example:
        >>> validate_risk_level("high")
        True
        >>> validate_risk_level("extreme")
        False
    """
    return level in RISK_LEVEL_CHOICES


def validate_recommended_action(action: str) -> bool:
    """Validate that a recommended action is valid.

    Args:
        action: Recommended action string to validate

    Returns:
        True if the action is valid, False otherwise

    Example:
        >>> validate_recommended_action("alert_homeowner")
        True
        >>> validate_recommended_action("call_police")
        False
    """
    return action in RECOMMENDED_ACTION_CHOICES


def validate_entity_type(entity_type: str) -> bool:
    """Validate that an entity type is valid.

    Args:
        entity_type: Entity type string to validate

    Returns:
        True if the entity type is valid, False otherwise

    Example:
        >>> validate_entity_type("person")
        True
        >>> validate_entity_type("robot")
        False
    """
    return entity_type in ENTITY_TYPE_CHOICES


def validate_threat_level(threat_level: str) -> bool:
    """Validate that a threat level is valid.

    Args:
        threat_level: Threat level string to validate

    Returns:
        True if the threat level is valid, False otherwise

    Example:
        >>> validate_threat_level("medium")
        True
        >>> validate_threat_level("critical")
        False
    """
    return threat_level in THREAT_LEVEL_CHOICES
