"""Threat category classification for home surveillance.

This module defines a security-focused taxonomy for classifying detected threats
in home surveillance systems. The categories are based on NVIDIA's safety
categories, adapted for residential security applications.

The threat categories help the Nemotron analyzer classify detections into
specific threat types, enabling more targeted alerting and response actions.

References:
- NEM-3730: Add Threat Category Classification
- NVIDIA Safety Categories: https://developer.nvidia.com/nvidia-nemotron-safety

Example Usage:
    >>> from backend.services.threat_categories import (
    ...     ThreatCategory,
    ...     get_category_prompt_section,
    ... )
    >>> # Use in prompt construction
    >>> prompt_section = get_category_prompt_section()
    >>> print(prompt_section)
    ## THREAT CATEGORIES
    - violence: Physical violence or fighting
    - weapon_visible: Firearm, knife, or weapon visible
    ...

    >>> # Use in response schemas
    >>> categories = [ThreatCategory.TRESPASSING, ThreatCategory.SURVEILLANCE_CASING]
    >>> primary = ThreatCategory.TRESPASSING
"""

from __future__ import annotations

from enum import Enum


class ThreatCategory(str, Enum):
    """Security threat categories for home surveillance.

    These categories represent the types of threats that can be detected
    in home surveillance footage. Categories are ordered roughly by
    severity, with NONE indicating no threat detected.

    Inherits from str to enable JSON serialization and string comparison.

    Attributes:
        VIOLENCE: Physical violence or fighting detected
        WEAPON_VISIBLE: Firearm, knife, or other weapon visible
        CRIMINAL_PLANNING: Evidence of planning criminal activity
        THREAT_INTIMIDATION: Threatening or intimidating behavior
        FRAUD_DECEPTION: Deceptive behavior (e.g., impersonation)
        ILLEGAL_ACTIVITY: General illegal activity detected
        PROPERTY_DAMAGE: Vandalism or destruction of property
        TRESPASSING: Unauthorized entry or presence on property
        THEFT_ATTEMPT: Attempted theft of property
        SURVEILLANCE_CASING: Reconnaissance or casing of property
        NONE: No threat detected (normal activity)
    """

    VIOLENCE = "violence"
    WEAPON_VISIBLE = "weapon_visible"
    CRIMINAL_PLANNING = "criminal_planning"
    THREAT_INTIMIDATION = "threat_intimidation"
    FRAUD_DECEPTION = "fraud_deception"
    ILLEGAL_ACTIVITY = "illegal_activity"
    PROPERTY_DAMAGE = "property_damage"
    TRESPASSING = "trespassing"
    THEFT_ATTEMPT = "theft_attempt"
    SURVEILLANCE_CASING = "surveillance_casing"
    NONE = "none"

    def __str__(self) -> str:
        """Return the string value of the threat category."""
        return self.value


# Category descriptions for prompt inclusion and documentation
THREAT_CATEGORY_DESCRIPTIONS: dict[ThreatCategory, str] = {
    ThreatCategory.VIOLENCE: "Physical violence or fighting",
    ThreatCategory.WEAPON_VISIBLE: "Firearm, knife, or weapon visible",
    ThreatCategory.CRIMINAL_PLANNING: "Evidence of planning criminal activity",
    ThreatCategory.THREAT_INTIMIDATION: "Threatening or intimidating behavior",
    ThreatCategory.FRAUD_DECEPTION: "Deceptive behavior such as impersonation",
    ThreatCategory.ILLEGAL_ACTIVITY: "General illegal activity detected",
    ThreatCategory.PROPERTY_DAMAGE: "Vandalism or destruction of property",
    ThreatCategory.TRESPASSING: "Unauthorized entry or presence on property",
    ThreatCategory.THEFT_ATTEMPT: "Taking property without permission",
    ThreatCategory.SURVEILLANCE_CASING: "Reconnaissance or casing of property",
    ThreatCategory.NONE: "No threat detected",
}


def get_category_prompt_section() -> str:
    """Generate prompt section listing all threat categories.

    Creates a formatted markdown section that can be included in LLM prompts
    to guide threat classification. Each category is listed with its value
    and description for the model to reference.

    Returns:
        Formatted markdown string with header and category list.

    Example:
        >>> section = get_category_prompt_section()
        >>> print(section)
        ## THREAT CATEGORIES
        - violence: Physical violence or fighting
        - weapon_visible: Firearm, knife, or weapon visible
        - criminal_planning: Evidence of planning criminal activity
        ...
    """
    lines = ["## THREAT CATEGORIES"]
    for category in ThreatCategory:
        description = THREAT_CATEGORY_DESCRIPTIONS[category]
        lines.append(f"- {category.value}: {description}")
    return "\n".join(lines)
