"""Comparison engine for A/B testing synthetic data against pipeline results.

ABOUTME: This module compares pipeline API results against expected_labels.json
for automated A/B testing of the AI pipeline. It validates that the actual
outputs from the detection/enrichment pipeline match the expected outputs
defined in synthetic scenario specifications.

The comparison engine supports multiple field types with appropriate comparison
methods:
- count: Exact match or within +/-1 tolerance
- min_confidence: Actual >= expected
- class: Exact string match
- is_suspicious: Boolean exact match
- score range: min <= actual <= max
- text_pattern: Regex match
- must_contain: All keywords present (case-insensitive)
- must_not_contain: No keywords present (case-insensitive)
- enum values: Exact match from allowed set
- distance range: Within [min, max] meters

Usage:
    engine = ComparisonEngine()
    result = engine.compare(expected_labels, actual_results)
    if result.passed:
        print("All tests passed!")
    else:
        for field_result in result.field_results:
            if not field_result.passed:
                print(f"FAIL: {field_result.field_name}")
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

# =============================================================================
# Synonym dictionary for semantic caption matching
# =============================================================================
# This dictionary maps expected keywords to sets of semantically equivalent terms.
# Used by Florence caption validation to handle natural language variation.
# For example, Florence might describe a "package" as "cardboard box" or "parcel".
#
# All keys and values MUST be lowercase for case-insensitive matching.
# =============================================================================

CAPTION_SYNONYMS: dict[str, set[str]] = {
    # Package/delivery related
    "package": {
        "package",
        "box",
        "parcel",
        "delivery",
        "cardboard box",
        "shipping box",
        "carton",
        "container",
        "crate",
        "bundle",
        "packet",
    },
    # Person/human related
    "person": {
        "person",
        "man",
        "woman",
        "individual",
        "figure",
        "someone",
        "human",
        "people",
        "adult",
        "child",
        "boy",
        "girl",
        "guy",
        "lady",
        "gentleman",
        "worker",
        "pedestrian",
    },
    # Vehicle related
    "car": {
        "car",
        "vehicle",
        "automobile",
        "sedan",
        "suv",
        "truck",
        "van",
        "pickup",
        "hatchback",
        "coupe",
        "minivan",
        "crossover",
        "motor vehicle",
    },
    "truck": {
        "truck",
        "pickup",
        "pickup truck",
        "lorry",
        "van",
        "delivery truck",
        "utility vehicle",
    },
    "van": {
        "van",
        "minivan",
        "cargo van",
        "delivery van",
        "panel van",
    },
    "motorcycle": {
        "motorcycle",
        "motorbike",
        "bike",
        "scooter",
        "moped",
    },
    "bicycle": {
        "bicycle",
        "bike",
        "cycle",
        "pedal bike",
    },
    # Building/structure related
    "door": {
        "door",
        "entrance",
        "entryway",
        "doorway",
        "front door",
        "entry",
        "threshold",
        "portal",
    },
    "porch": {
        "porch",
        "stoop",
        "veranda",
        "front steps",
        "steps",
        "landing",
        "deck",
        "entryway",
        "front porch",
    },
    "house": {
        "house",
        "home",
        "residence",
        "dwelling",
        "building",
        "property",
        "residential building",
        "structure",
    },
    "garage": {
        "garage",
        "carport",
        "car garage",
        "parking garage",
    },
    "driveway": {
        "driveway",
        "drive",
        "parking area",
        "front yard",
    },
    "yard": {
        "yard",
        "lawn",
        "garden",
        "front yard",
        "backyard",
        "grounds",
    },
    "fence": {
        "fence",
        "fencing",
        "barrier",
        "gate",
        "enclosure",
        "railing",
    },
    "window": {
        "window",
        "glass",
        "pane",
        "windowpane",
        "opening",
    },
    # Pet/animal related
    "dog": {
        "dog",
        "canine",
        "puppy",
        "pet",
        "hound",
        "pooch",
        "pup",
    },
    "cat": {
        "cat",
        "feline",
        "kitten",
        "pet",
        "kitty",
    },
    "animal": {
        "animal",
        "pet",
        "creature",
        "dog",
        "cat",
        "wildlife",
    },
    # Action/motion related
    "walking": {
        "walking",
        "approaching",
        "moving",
        "strolling",
        "striding",
        "stepping",
        "advancing",
        "coming",
        "going",
        "heading",
    },
    "running": {
        "running",
        "sprinting",
        "jogging",
        "rushing",
        "hurrying",
        "dashing",
        "fleeing",
    },
    "standing": {
        "standing",
        "waiting",
        "stationary",
        "still",
        "positioned",
        "stopped",
        "paused",
    },
    "sitting": {
        "sitting",
        "seated",
        "resting",
        "perched",
    },
    "bending": {
        "bending",
        "crouching",
        "stooping",
        "leaning",
        "kneeling",
        "hunching",
        "ducking",
    },
    "carrying": {
        "carrying",
        "holding",
        "transporting",
        "bearing",
        "bringing",
        "delivering",
    },
    # Object related
    "weapon": {
        "weapon",
        "gun",
        "knife",
        "firearm",
        "pistol",
        "rifle",
        "blade",
        "tool",
    },
    "bag": {
        "bag",
        "backpack",
        "sack",
        "purse",
        "handbag",
        "duffle",
        "tote",
        "satchel",
    },
    # Time/lighting related
    "night": {
        "night",
        "nighttime",
        "dark",
        "evening",
        "darkness",
        "after dark",
    },
    "day": {
        "day",
        "daytime",
        "daylight",
        "bright",
        "sunny",
        "morning",
        "afternoon",
    },
}


def check_caption_keywords_with_synonyms(caption: str, keywords: list[str]) -> bool:
    """Check if all keywords are present in caption using synonym expansion.

    For each keyword, checks if either the keyword itself or any of its synonyms
    appear in the caption. Uses case-insensitive matching.

    Args:
        caption: The caption text to search in.
        keywords: List of keywords that must be present (directly or via synonym).

    Returns:
        True if all keywords (or their synonyms) are found in the caption.

    Example:
        >>> check_caption_keywords_with_synonyms(
        ...     "A man holding a cardboard box",
        ...     ["person", "package"]
        ... )
        True  # "man" matches "person", "cardboard box" matches "package"
    """
    if not keywords:
        return True

    caption_lower = caption.lower()

    for keyword in keywords:
        keyword_lower = keyword.lower()
        # Get synonyms for this keyword, defaulting to just the keyword itself
        synonyms = CAPTION_SYNONYMS.get(keyword_lower, {keyword_lower})

        # Check if any synonym is present in the caption
        found = any(syn in caption_lower for syn in synonyms)
        if not found:
            return False

    return True


@dataclass
class FieldResult:
    """Result of comparing a single field between expected and actual values.

    Attributes:
        field_name: Dot-notation path to the field (e.g., "detections.0.class").
        passed: Whether the comparison passed.
        expected: The expected value from the scenario spec.
        actual: The actual value from the pipeline output.
        diff: Optional dictionary with detailed difference information.
    """

    field_name: str
    passed: bool
    expected: Any
    actual: Any
    diff: dict[str, Any] | None = None


@dataclass
class ComparisonResult:
    """Result of comparing all expected fields against actual pipeline output.

    Attributes:
        passed: Whether all field comparisons passed.
        field_results: List of individual field comparison results.
        summary: Dictionary with comparison statistics (total, passed, failed counts).
    """

    passed: bool
    field_results: list[FieldResult]
    summary: dict[str, Any] = field(default_factory=dict)


class ComparisonEngine:
    """Engine for comparing expected labels against actual pipeline results.

    This class provides methods to compare pipeline API results against
    expected_labels.json for A/B testing. It supports various comparison
    methods based on field type and handles nested structures like
    detections, risk_assessment, pose, clothing, and florence_caption.

    Example:
        engine = ComparisonEngine()

        expected = {
            "detections": [{"class": "person", "min_confidence": 0.75, "count": 1}],
            "risk_assessment": {"min_score": 40, "max_score": 70, "level": "medium"}
        }

        actual = {
            "detections": [{"class": "person", "confidence": 0.82}],
            "risk_score": 55,
            "risk_level": "medium"
        }

        result = engine.compare(expected, actual)
        print(f"Passed: {result.passed}")
    """

    # Tolerance for count comparisons
    COUNT_TOLERANCE = 1

    def compare(self, expected: dict[str, Any], actual: dict[str, Any]) -> ComparisonResult:
        """Compare expected labels against actual pipeline results.

        Iterates through all expected fields and compares them against
        corresponding actual values using appropriate comparison methods.

        Args:
            expected: Expected labels from scenario specification.
            actual: Actual results from pipeline API.

        Returns:
            ComparisonResult with pass/fail status and detailed field results.
        """
        field_results: list[FieldResult] = []

        # Compare detections
        if "detections" in expected:
            field_results.extend(
                self._compare_detections(expected["detections"], actual.get("detections", []))
            )

        # Compare license plate
        if "license_plate" in expected:
            field_results.extend(
                self._compare_license_plate(
                    expected["license_plate"], actual.get("license_plate", {})
                )
            )

        # Compare face detection
        if "face" in expected:
            field_results.extend(self._compare_face(expected["face"], actual.get("face", {})))

        # Compare OCR results
        if "ocr" in expected:
            field_results.extend(self._compare_ocr(expected["ocr"], actual.get("ocr", {})))

        # Compare pose estimation
        if "pose" in expected:
            field_results.extend(self._compare_pose(expected["pose"], actual.get("pose", {})))

        # Compare action recognition
        if "action" in expected:
            field_results.extend(self._compare_action(expected["action"], actual.get("action", {})))

        # Compare demographics
        if "demographics" in expected:
            field_results.extend(
                self._compare_demographics(expected["demographics"], actual.get("demographics", {}))
            )

        # Compare clothing
        if "clothing" in expected:
            field_results.extend(
                self._compare_clothing(expected["clothing"], actual.get("clothing", {}))
            )

        # Compare clothing segmentation
        if "clothing_segmentation" in expected:
            field_results.extend(
                self._compare_clothing_segmentation(
                    expected["clothing_segmentation"],
                    actual.get("clothing_segmentation", {}),
                )
            )

        # Compare threats
        if "threats" in expected:
            field_results.extend(
                self._compare_threats(expected["threats"], actual.get("threats", {}))
            )

        # Compare violence detection
        if "violence" in expected:
            field_results.extend(
                self._compare_violence(expected["violence"], actual.get("violence", {}))
            )

        # Compare weather
        if "weather" in expected:
            field_results.extend(
                self._compare_weather(expected["weather"], actual.get("weather", {}))
            )

        # Compare vehicle
        if "vehicle" in expected:
            field_results.extend(
                self._compare_vehicle(expected["vehicle"], actual.get("vehicle", {}))
            )

        # Compare vehicle damage
        if "vehicle_damage" in expected:
            field_results.extend(
                self._compare_vehicle_damage(
                    expected["vehicle_damage"], actual.get("vehicle_damage", {})
                )
            )

        # Compare pet detection
        if "pet" in expected:
            field_results.extend(self._compare_pet(expected["pet"], actual.get("pet", {})))

        # Compare depth estimation
        if "depth" in expected:
            field_results.extend(self._compare_depth(expected["depth"], actual.get("depth", {})))

        # Compare re-identification
        if "reid" in expected:
            field_results.extend(self._compare_reid(expected["reid"], actual.get("reid", {})))

        # Compare image quality
        if "image_quality" in expected:
            field_results.extend(
                self._compare_image_quality(
                    expected["image_quality"], actual.get("image_quality", {})
                )
            )

        # Compare florence caption
        if "florence_caption" in expected:
            field_results.extend(
                self._compare_florence_caption(
                    expected["florence_caption"], actual.get("florence_caption", "")
                )
            )

        # Compare risk assessment
        if "risk" in expected:
            field_results.extend(self._compare_risk_assessment(expected["risk"], actual))

        # Calculate summary
        total = len(field_results)
        passed_count = sum(1 for r in field_results if r.passed)
        failed_count = total - passed_count

        summary = {
            "total_fields": total,
            "passed": passed_count,
            "failed": failed_count,
            "pass_rate": passed_count / total if total > 0 else 1.0,
        }

        overall_passed = failed_count == 0

        return ComparisonResult(
            passed=overall_passed,
            field_results=field_results,
            summary=summary,
        )

    def compare_field(
        self, field_type: str, expected: Any, actual: Any, field_name: str = ""
    ) -> FieldResult:
        """Compare a single field using the appropriate comparison method.

        Args:
            field_type: Type of comparison to perform (count, min_confidence, etc.).
            expected: Expected value.
            actual: Actual value.
            field_name: Name of the field being compared.

        Returns:
            FieldResult with comparison outcome.
        """
        if field_type == "count":
            return self._compare_count(expected, actual, field_name)
        elif field_type == "min_confidence":
            return self._compare_min_confidence(expected, actual, field_name)
        elif field_type == "class":
            return self._compare_exact_string(expected, actual, field_name)
        elif field_type == "is_suspicious":
            return self._compare_boolean(expected, actual, field_name)
        elif field_type == "score_range":
            return self._compare_score_range(expected, actual, field_name)
        elif field_type == "text_pattern":
            return self._compare_text_pattern(expected, actual, field_name)
        elif field_type == "must_contain":
            return self._compare_must_contain(expected, actual, field_name)
        elif field_type == "must_not_contain":
            return self._compare_must_not_contain(expected, actual, field_name)
        elif field_type == "enum":
            return self._compare_enum(expected, actual, field_name)
        elif field_type == "distance_range":
            return self._compare_distance_range(expected, actual, field_name)
        else:
            # Default to exact match
            return self._compare_exact(expected, actual, field_name)

    # =========================================================================
    # Core comparison methods
    # =========================================================================

    def _compare_count(self, expected: int, actual: int | None, field_name: str) -> FieldResult:
        """Compare count with +/-1 tolerance.

        Args:
            expected: Expected count.
            actual: Actual count from pipeline.
            field_name: Name of the field.

        Returns:
            FieldResult indicating pass if actual is within tolerance of expected.
        """
        if actual is None:
            return FieldResult(
                field_name=field_name,
                passed=False,
                expected=expected,
                actual=actual,
                diff={"reason": "actual value is None"},
            )

        diff = abs(expected - actual)
        passed = diff <= self.COUNT_TOLERANCE

        return FieldResult(
            field_name=field_name,
            passed=passed,
            expected=expected,
            actual=actual,
            diff={"difference": diff, "tolerance": self.COUNT_TOLERANCE} if not passed else None,
        )

    def _compare_min_confidence(
        self, expected: float, actual: float | None, field_name: str
    ) -> FieldResult:
        """Compare confidence ensuring actual >= expected.

        Args:
            expected: Minimum expected confidence threshold.
            actual: Actual confidence from pipeline.
            field_name: Name of the field.

        Returns:
            FieldResult indicating pass if actual >= expected.
        """
        if actual is None:
            return FieldResult(
                field_name=field_name,
                passed=False,
                expected=f">={expected}",
                actual=actual,
                diff={"reason": "actual value is None"},
            )

        passed = actual >= expected

        return FieldResult(
            field_name=field_name,
            passed=passed,
            expected=f">={expected}",
            actual=actual,
            diff={"shortfall": expected - actual} if not passed else None,
        )

    def _compare_exact_string(
        self, expected: str, actual: str | None, field_name: str
    ) -> FieldResult:
        """Compare strings for exact match.

        Args:
            expected: Expected string value.
            actual: Actual string from pipeline.
            field_name: Name of the field.

        Returns:
            FieldResult indicating pass if strings match exactly.
        """
        if actual is None:
            return FieldResult(
                field_name=field_name,
                passed=False,
                expected=expected,
                actual=actual,
                diff={"reason": "actual value is None"},
            )

        passed = expected == actual

        return FieldResult(
            field_name=field_name,
            passed=passed,
            expected=expected,
            actual=actual,
            diff=None if passed else {"expected": expected, "actual": actual},
        )

    def _compare_boolean(self, expected: bool, actual: bool | None, field_name: str) -> FieldResult:
        """Compare boolean values for exact match.

        Args:
            expected: Expected boolean value.
            actual: Actual boolean from pipeline.
            field_name: Name of the field.

        Returns:
            FieldResult indicating pass if booleans match.
        """
        if actual is None:
            return FieldResult(
                field_name=field_name,
                passed=False,
                expected=expected,
                actual=actual,
                diff={"reason": "actual value is None"},
            )

        passed = expected == actual

        return FieldResult(
            field_name=field_name,
            passed=passed,
            expected=expected,
            actual=actual,
            diff=None if passed else {"expected": expected, "actual": actual},
        )

    def _compare_score_range(
        self, expected: dict[str, float], actual: float | None, field_name: str
    ) -> FieldResult:
        """Compare score ensuring min <= actual <= max.

        Args:
            expected: Dictionary with 'min' and 'max' keys defining the range.
            actual: Actual score from pipeline.
            field_name: Name of the field.

        Returns:
            FieldResult indicating pass if actual is within range.
        """
        min_val = expected.get("min", float("-inf"))
        max_val = expected.get("max", float("inf"))

        if actual is None:
            return FieldResult(
                field_name=field_name,
                passed=False,
                expected=f"[{min_val}, {max_val}]",
                actual=actual,
                diff={"reason": "actual value is None"},
            )

        passed = min_val <= actual <= max_val

        return FieldResult(
            field_name=field_name,
            passed=passed,
            expected=f"[{min_val}, {max_val}]",
            actual=actual,
            diff={
                "min": min_val,
                "max": max_val,
                "actual": actual,
                "out_of_range_by": min(abs(actual - min_val), abs(actual - max_val))
                if not passed
                else 0,
            }
            if not passed
            else None,
        )

    def _compare_text_pattern(
        self, expected: str, actual: str | None, field_name: str
    ) -> FieldResult:
        """Compare text against regex pattern.

        Args:
            expected: Regex pattern to match against.
            actual: Actual text from pipeline.
            field_name: Name of the field.

        Returns:
            FieldResult indicating pass if text matches pattern.
        """
        if actual is None:
            return FieldResult(
                field_name=field_name,
                passed=False,
                expected=f"pattern: {expected}",
                actual=actual,
                diff={"reason": "actual value is None"},
            )

        try:
            passed = bool(re.match(expected, actual))
        except re.error as e:
            return FieldResult(
                field_name=field_name,
                passed=False,
                expected=f"pattern: {expected}",
                actual=actual,
                diff={"reason": f"invalid regex pattern: {e}"},
            )

        return FieldResult(
            field_name=field_name,
            passed=passed,
            expected=f"pattern: {expected}",
            actual=actual,
            diff={"pattern": expected, "actual": actual} if not passed else None,
        )

    def _compare_must_contain(
        self, expected: list[str], actual: str | None, field_name: str
    ) -> FieldResult:
        """Compare text ensuring all keywords are present (case-insensitive).

        Args:
            expected: List of keywords that must be present.
            actual: Actual text from pipeline.
            field_name: Name of the field.

        Returns:
            FieldResult indicating pass if all keywords are found.
        """
        if actual is None:
            return FieldResult(
                field_name=field_name,
                passed=False,
                expected=f"must contain: {expected}",
                actual=actual,
                diff={"reason": "actual value is None"},
            )

        actual_lower = actual.lower()
        missing = [kw for kw in expected if kw.lower() not in actual_lower]
        passed = len(missing) == 0

        return FieldResult(
            field_name=field_name,
            passed=passed,
            expected=f"must contain: {expected}",
            actual=actual,
            diff={"missing_keywords": missing} if not passed else None,
        )

    def _compare_must_not_contain(
        self, expected: list[str], actual: str | None, field_name: str
    ) -> FieldResult:
        """Compare text ensuring no keywords are present (case-insensitive).

        Args:
            expected: List of keywords that must NOT be present.
            actual: Actual text from pipeline.
            field_name: Name of the field.

        Returns:
            FieldResult indicating pass if no keywords are found.
        """
        if actual is None:
            # If actual is None, no forbidden keywords can be present
            return FieldResult(
                field_name=field_name,
                passed=True,
                expected=f"must not contain: {expected}",
                actual=actual,
            )

        actual_lower = actual.lower()
        found = [kw for kw in expected if kw.lower() in actual_lower]
        passed = len(found) == 0

        return FieldResult(
            field_name=field_name,
            passed=passed,
            expected=f"must not contain: {expected}",
            actual=actual,
            diff={"found_forbidden_keywords": found} if not passed else None,
        )

    def _compare_enum(
        self, expected: list[str], actual: str | None, field_name: str
    ) -> FieldResult:
        """Compare value against allowed enum values.

        Args:
            expected: List of allowed values.
            actual: Actual value from pipeline.
            field_name: Name of the field.

        Returns:
            FieldResult indicating pass if actual is in allowed set.
        """
        if actual is None:
            return FieldResult(
                field_name=field_name,
                passed=False,
                expected=f"one of: {expected}",
                actual=actual,
                diff={"reason": "actual value is None"},
            )

        passed = actual in expected

        return FieldResult(
            field_name=field_name,
            passed=passed,
            expected=f"one of: {expected}",
            actual=actual,
            diff={"allowed_values": expected, "actual": actual} if not passed else None,
        )

    def _compare_distance_range(
        self, expected: list[float], actual: float | None, field_name: str
    ) -> FieldResult:
        """Compare distance ensuring value is within [min, max] meters.

        Args:
            expected: List of [min, max] distance values in meters.
            actual: Actual distance from pipeline.
            field_name: Name of the field.

        Returns:
            FieldResult indicating pass if distance is within range.
        """
        if len(expected) != 2:
            return FieldResult(
                field_name=field_name,
                passed=False,
                expected=expected,
                actual=actual,
                diff={"reason": "expected must be [min, max] list"},
            )

        min_dist, max_dist = expected

        if actual is None:
            return FieldResult(
                field_name=field_name,
                passed=False,
                expected=f"[{min_dist}m, {max_dist}m]",
                actual=actual,
                diff={"reason": "actual value is None"},
            )

        passed = min_dist <= actual <= max_dist

        return FieldResult(
            field_name=field_name,
            passed=passed,
            expected=f"[{min_dist}m, {max_dist}m]",
            actual=actual,
            diff={
                "min": min_dist,
                "max": max_dist,
                "actual": actual,
            }
            if not passed
            else None,
        )

    def _compare_exact(self, expected: Any, actual: Any, field_name: str) -> FieldResult:
        """Compare values for exact equality.

        Args:
            expected: Expected value.
            actual: Actual value from pipeline.
            field_name: Name of the field.

        Returns:
            FieldResult indicating pass if values are equal.
        """
        passed = expected == actual

        return FieldResult(
            field_name=field_name,
            passed=passed,
            expected=expected,
            actual=actual,
            diff=None if passed else {"expected": expected, "actual": actual},
        )

    # =========================================================================
    # Nested structure comparison methods
    # =========================================================================

    def _compare_detections(
        self, expected: list[dict[str, Any]], actual: list[dict[str, Any]]
    ) -> list[FieldResult]:
        """Compare detection lists.

        Validates count per class, minimum confidence, and class names.

        Args:
            expected: List of expected detection specifications.
            actual: List of actual detections from pipeline.

        Returns:
            List of FieldResult for each comparison performed.
        """
        results: list[FieldResult] = []

        for _, exp_det in enumerate(expected):
            exp_class = exp_det.get("class")
            exp_count = exp_det.get("count")
            exp_min_conf = exp_det.get("min_confidence")

            # Filter actual detections by class
            matching_actual = [d for d in actual if d.get("class") == exp_class]

            # Compare count
            if exp_count is not None:
                results.append(
                    self._compare_count(
                        exp_count,
                        len(matching_actual),
                        f"detections.{exp_class}.count",
                    )
                )

            # Compare min confidence for matching detections
            if exp_min_conf is not None and matching_actual:
                max_confidence = max((d.get("confidence", 0) for d in matching_actual), default=0)
                results.append(
                    self._compare_min_confidence(
                        exp_min_conf,
                        max_confidence,
                        f"detections.{exp_class}.confidence",
                    )
                )
            elif exp_min_conf is not None and not matching_actual:
                results.append(
                    FieldResult(
                        field_name=f"detections.{exp_class}.confidence",
                        passed=False,
                        expected=f">={exp_min_conf}",
                        actual=None,
                        diff={"reason": f"no detections of class '{exp_class}' found"},
                    )
                )

        return results

    def _compare_license_plate(
        self, expected: dict[str, Any], actual: dict[str, Any]
    ) -> list[FieldResult]:
        """Compare license plate detection results.

        Args:
            expected: Expected license plate specification.
            actual: Actual license plate results from pipeline.

        Returns:
            List of FieldResult for each comparison performed.
        """
        results: list[FieldResult] = []

        # Compare detected flag
        if "detected" in expected:
            results.append(
                self._compare_boolean(
                    expected["detected"],
                    actual.get("detected"),
                    "license_plate.detected",
                )
            )

        # Compare text pattern if plate was expected to be detected
        if expected.get("detected") and "text_pattern" in expected:
            results.append(
                self._compare_text_pattern(
                    expected["text_pattern"],
                    actual.get("text"),
                    "license_plate.text",
                )
            )

        return results

    def _compare_face(self, expected: dict[str, Any], actual: dict[str, Any]) -> list[FieldResult]:
        """Compare face detection results.

        Args:
            expected: Expected face detection specification.
            actual: Actual face detection results from pipeline.

        Returns:
            List of FieldResult for each comparison performed.
        """
        results: list[FieldResult] = []

        if "detected" in expected:
            results.append(
                self._compare_boolean(
                    expected["detected"],
                    actual.get("detected"),
                    "face.detected",
                )
            )

        if "count" in expected:
            results.append(
                self._compare_count(
                    expected["count"],
                    actual.get("count"),
                    "face.count",
                )
            )

        if "visible" in expected:
            results.append(
                self._compare_boolean(
                    expected["visible"],
                    actual.get("visible"),
                    "face.visible",
                )
            )

        return results

    def _compare_ocr(self, expected: dict[str, Any], actual: dict[str, Any]) -> list[FieldResult]:
        """Compare OCR results.

        Args:
            expected: Expected OCR specification.
            actual: Actual OCR results from pipeline.

        Returns:
            List of FieldResult for each comparison performed.
        """
        results: list[FieldResult] = []

        if "expected_text" in expected:
            actual_texts = actual.get("texts", [])
            actual_combined = " ".join(actual_texts).lower()
            for exp_text in expected["expected_text"]:
                passed = exp_text.lower() in actual_combined
                results.append(
                    FieldResult(
                        field_name=f"ocr.expected_text.{exp_text}",
                        passed=passed,
                        expected=f"contains '{exp_text}'",
                        actual=actual_texts,
                        diff={"missing_text": exp_text} if not passed else None,
                    )
                )

        if "min_confidence" in expected:
            max_conf = max(actual.get("confidences", [0]), default=0)
            results.append(
                self._compare_min_confidence(
                    expected["min_confidence"],
                    max_conf,
                    "ocr.confidence",
                )
            )

        return results

    def _compare_pose(self, expected: dict[str, Any], actual: dict[str, Any]) -> list[FieldResult]:
        """Compare pose estimation results.

        Validates posture classification, suspicious flag, and visible keypoints.

        Args:
            expected: Expected pose specification.
            actual: Actual pose results from pipeline.

        Returns:
            List of FieldResult for each comparison performed.
        """
        results: list[FieldResult] = []

        if "posture" in expected:
            results.append(
                self._compare_exact_string(
                    expected["posture"],
                    actual.get("posture"),
                    "pose.posture",
                )
            )

        if "is_suspicious" in expected:
            results.append(
                self._compare_boolean(
                    expected["is_suspicious"],
                    actual.get("is_suspicious"),
                    "pose.is_suspicious",
                )
            )

        if "keypoints_visible" in expected:
            actual_keypoints = actual.get("keypoints_visible", [])
            missing = [kp for kp in expected["keypoints_visible"] if kp not in actual_keypoints]
            passed = len(missing) == 0
            results.append(
                FieldResult(
                    field_name="pose.keypoints_visible",
                    passed=passed,
                    expected=expected["keypoints_visible"],
                    actual=actual_keypoints,
                    diff={"missing_keypoints": missing} if not passed else None,
                )
            )

        return results

    def _compare_action(
        self, expected: dict[str, Any], actual: dict[str, Any]
    ) -> list[FieldResult]:
        """Compare action recognition results.

        Args:
            expected: Expected action specification.
            actual: Actual action results from pipeline.

        Returns:
            List of FieldResult for each comparison performed.
        """
        results: list[FieldResult] = []

        if "action" in expected:
            results.append(
                self._compare_exact_string(
                    expected["action"],
                    actual.get("action"),
                    "action.action",
                )
            )

        if "is_suspicious" in expected:
            results.append(
                self._compare_boolean(
                    expected["is_suspicious"],
                    actual.get("is_suspicious"),
                    "action.is_suspicious",
                )
            )

        return results

    def _compare_demographics(
        self, expected: dict[str, Any], actual: dict[str, Any]
    ) -> list[FieldResult]:
        """Compare demographics (age, gender) results.

        Args:
            expected: Expected demographics specification.
            actual: Actual demographics results from pipeline.

        Returns:
            List of FieldResult for each comparison performed.
        """
        results: list[FieldResult] = []

        if "age_range" in expected:
            results.append(
                self._compare_exact_string(
                    expected["age_range"],
                    actual.get("age_range"),
                    "demographics.age_range",
                )
            )

        if "gender" in expected:
            results.append(
                self._compare_exact_string(
                    expected["gender"],
                    actual.get("gender"),
                    "demographics.gender",
                )
            )

        return results

    def _compare_clothing(
        self, expected: dict[str, Any], actual: dict[str, Any]
    ) -> list[FieldResult]:
        """Compare clothing classification results.

        Validates clothing type, color, and suspicious flag.

        Args:
            expected: Expected clothing specification.
            actual: Actual clothing results from pipeline.

        Returns:
            List of FieldResult for each comparison performed.
        """
        results: list[FieldResult] = []

        if "type" in expected:
            results.append(
                self._compare_exact_string(
                    expected["type"],
                    actual.get("type"),
                    "clothing.type",
                )
            )

        if "color" in expected:
            results.append(
                self._compare_exact_string(
                    expected["color"],
                    actual.get("color"),
                    "clothing.color",
                )
            )

        if "is_suspicious" in expected:
            results.append(
                self._compare_boolean(
                    expected["is_suspicious"],
                    actual.get("is_suspicious"),
                    "clothing.is_suspicious",
                )
            )

        return results

    def _compare_clothing_segmentation(
        self, expected: dict[str, Any], actual: dict[str, Any]
    ) -> list[FieldResult]:
        """Compare clothing segmentation results.

        Args:
            expected: Expected clothing segmentation specification.
            actual: Actual segmentation results from pipeline.

        Returns:
            List of FieldResult for each comparison performed.
        """
        results: list[FieldResult] = []

        if "segments" in expected:
            actual_segments = actual.get("segments", [])
            missing = [s for s in expected["segments"] if s not in actual_segments]
            passed = len(missing) == 0
            results.append(
                FieldResult(
                    field_name="clothing_segmentation.segments",
                    passed=passed,
                    expected=expected["segments"],
                    actual=actual_segments,
                    diff={"missing_segments": missing} if not passed else None,
                )
            )

        return results

    def _compare_threats(
        self, expected: dict[str, Any], actual: dict[str, Any]
    ) -> list[FieldResult]:
        """Compare threat detection results.

        Args:
            expected: Expected threat specification.
            actual: Actual threat results from pipeline.

        Returns:
            List of FieldResult for each comparison performed.
        """
        results: list[FieldResult] = []

        if "has_threat" in expected:
            results.append(
                self._compare_boolean(
                    expected["has_threat"],
                    actual.get("has_threat"),
                    "threats.has_threat",
                )
            )

        if "types" in expected:
            actual_types = actual.get("types", [])
            missing = [t for t in expected["types"] if t not in actual_types]
            passed = len(missing) == 0
            results.append(
                FieldResult(
                    field_name="threats.types",
                    passed=passed,
                    expected=expected["types"],
                    actual=actual_types,
                    diff={"missing_threat_types": missing} if not passed else None,
                )
            )

        if "max_severity" in expected:
            severity_order = ["low", "medium", "high", "critical"]
            exp_severity = expected["max_severity"]
            act_severity = actual.get("max_severity")

            if act_severity is None:
                results.append(
                    FieldResult(
                        field_name="threats.max_severity",
                        passed=False,
                        expected=exp_severity,
                        actual=act_severity,
                        diff={"reason": "actual value is None"},
                    )
                )
            else:
                exp_idx = (
                    severity_order.index(exp_severity) if exp_severity in severity_order else -1
                )
                act_idx = (
                    severity_order.index(act_severity) if act_severity in severity_order else -1
                )
                passed = act_idx >= exp_idx
                results.append(
                    FieldResult(
                        field_name="threats.max_severity",
                        passed=passed,
                        expected=f">={exp_severity}",
                        actual=act_severity,
                        diff={"expected_min": exp_severity, "actual": act_severity}
                        if not passed
                        else None,
                    )
                )

        return results

    def _compare_violence(
        self, expected: dict[str, Any], actual: dict[str, Any]
    ) -> list[FieldResult]:
        """Compare violence detection results.

        Args:
            expected: Expected violence specification.
            actual: Actual violence results from pipeline.

        Returns:
            List of FieldResult for each comparison performed.
        """
        results: list[FieldResult] = []

        if "detected" in expected:
            results.append(
                self._compare_boolean(
                    expected["detected"],
                    actual.get("detected"),
                    "violence.detected",
                )
            )

        if "confidence_threshold" in expected:
            actual_conf = actual.get("confidence")
            if expected["detected"]:
                # If violence expected, confidence should meet threshold
                results.append(
                    self._compare_min_confidence(
                        expected["confidence_threshold"],
                        actual_conf,
                        "violence.confidence",
                    )
                )

        return results

    def _compare_weather(
        self, expected: dict[str, Any], actual: dict[str, Any]
    ) -> list[FieldResult]:
        """Compare weather classification results.

        Args:
            expected: Expected weather specification.
            actual: Actual weather results from pipeline.

        Returns:
            List of FieldResult for each comparison performed.
        """
        results: list[FieldResult] = []

        if "condition" in expected:
            results.append(
                self._compare_exact_string(
                    expected["condition"],
                    actual.get("condition"),
                    "weather.condition",
                )
            )

        if "affects_visibility" in expected:
            results.append(
                self._compare_boolean(
                    expected["affects_visibility"],
                    actual.get("affects_visibility"),
                    "weather.affects_visibility",
                )
            )

        return results

    def _compare_vehicle(
        self, expected: dict[str, Any], actual: dict[str, Any]
    ) -> list[FieldResult]:
        """Compare vehicle classification results.

        Args:
            expected: Expected vehicle specification.
            actual: Actual vehicle results from pipeline.

        Returns:
            List of FieldResult for each comparison performed.
        """
        results: list[FieldResult] = []

        if "type" in expected:
            results.append(
                self._compare_exact_string(
                    expected["type"],
                    actual.get("type"),
                    "vehicle.type",
                )
            )

        if "color" in expected:
            results.append(
                self._compare_exact_string(
                    expected["color"],
                    actual.get("color"),
                    "vehicle.color",
                )
            )

        return results

    def _compare_vehicle_damage(
        self, expected: dict[str, Any], actual: dict[str, Any]
    ) -> list[FieldResult]:
        """Compare vehicle damage detection results.

        Args:
            expected: Expected vehicle damage specification.
            actual: Actual vehicle damage results from pipeline.

        Returns:
            List of FieldResult for each comparison performed.
        """
        results: list[FieldResult] = []

        if "detected" in expected:
            results.append(
                self._compare_boolean(
                    expected["detected"],
                    actual.get("detected"),
                    "vehicle_damage.detected",
                )
            )

        return results

    def _compare_pet(self, expected: dict[str, Any], actual: dict[str, Any]) -> list[FieldResult]:
        """Compare pet detection results.

        Args:
            expected: Expected pet specification.
            actual: Actual pet results from pipeline.

        Returns:
            List of FieldResult for each comparison performed.
        """
        results: list[FieldResult] = []

        if "type" in expected:
            results.append(
                self._compare_exact_string(
                    expected["type"],
                    actual.get("type"),
                    "pet.type",
                )
            )

        if "is_known_pet" in expected:
            results.append(
                self._compare_boolean(
                    expected["is_known_pet"],
                    actual.get("is_known_pet"),
                    "pet.is_known_pet",
                )
            )

        return results

    def _compare_depth(self, expected: dict[str, Any], actual: dict[str, Any]) -> list[FieldResult]:
        """Compare depth estimation results.

        Args:
            expected: Expected depth specification.
            actual: Actual depth results from pipeline.

        Returns:
            List of FieldResult for each comparison performed.
        """
        results: list[FieldResult] = []

        if "subject_distance_m" in expected:
            results.append(
                self._compare_distance_range(
                    expected["subject_distance_m"],
                    actual.get("subject_distance_m"),
                    "depth.subject_distance_m",
                )
            )

        return results

    def _compare_reid(self, expected: dict[str, Any], actual: dict[str, Any]) -> list[FieldResult]:
        """Compare re-identification results.

        Args:
            expected: Expected re-ID specification.
            actual: Actual re-ID results from pipeline.

        Returns:
            List of FieldResult for each comparison performed.
        """
        results: list[FieldResult] = []

        if "same_person_as" in expected:
            results.append(
                self._compare_exact_string(
                    expected["same_person_as"],
                    actual.get("same_person_as"),
                    "reid.same_person_as",
                )
            )

        if "similarity_threshold" in expected:
            results.append(
                self._compare_min_confidence(
                    expected["similarity_threshold"],
                    actual.get("similarity"),
                    "reid.similarity",
                )
            )

        return results

    def _compare_image_quality(
        self, expected: dict[str, Any], actual: dict[str, Any]
    ) -> list[FieldResult]:
        """Compare image quality (BRISQUE) results.

        Args:
            expected: Expected image quality specification.
            actual: Actual image quality results from pipeline.

        Returns:
            List of FieldResult for each comparison performed.
        """
        results: list[FieldResult] = []

        if "min_brisque_score" in expected and "max_brisque_score" in expected:
            results.append(
                self._compare_score_range(
                    {"min": expected["min_brisque_score"], "max": expected["max_brisque_score"]},
                    actual.get("brisque_score"),
                    "image_quality.brisque_score",
                )
            )

        return results

    def _compare_florence_caption(
        self, expected: dict[str, Any], actual: str | dict[str, Any]
    ) -> list[FieldResult]:
        """Compare Florence caption results using semantic synonym matching.

        Validates must_contain (with synonym expansion) and must_not_contain keywords.
        The must_contain check uses synonym expansion to handle natural language
        variation in Florence captions (e.g., "cardboard box" matches "package").

        Args:
            expected: Expected caption specification with must_contain/must_not_contain.
            actual: Actual caption string or dict from pipeline.

        Returns:
            List of FieldResult for each comparison performed.
        """
        results: list[FieldResult] = []

        # Handle actual as either string or dict with 'caption' key
        if isinstance(actual, dict):
            caption_text = actual.get("caption", "")
        else:
            caption_text = actual if actual else ""

        if "must_contain" in expected:
            results.append(
                self._compare_must_contain_semantic(
                    expected["must_contain"],
                    caption_text,
                    "florence_caption.must_contain",
                )
            )

        if "must_not_contain" in expected:
            results.append(
                self._compare_must_not_contain(
                    expected["must_not_contain"],
                    caption_text,
                    "florence_caption.must_not_contain",
                )
            )

        return results

    def _compare_must_contain_semantic(
        self, expected: list[str], actual: str | None, field_name: str
    ) -> FieldResult:
        """Compare text ensuring all keywords are present using synonym expansion.

        For each keyword, checks if either the keyword itself or any of its synonyms
        from CAPTION_SYNONYMS appear in the text. Uses case-insensitive matching.

        Args:
            expected: List of keywords that must be present (directly or via synonym).
            actual: Actual text from pipeline.
            field_name: Name of the field.

        Returns:
            FieldResult indicating pass if all keywords (or synonyms) are found.
        """
        if actual is None:
            return FieldResult(
                field_name=field_name,
                passed=False,
                expected=f"must contain (semantic): {expected}",
                actual=actual,
                diff={"reason": "actual value is None"},
            )

        actual_lower = actual.lower()
        missing = []

        for keyword in expected:
            keyword_lower = keyword.lower()
            # Get synonyms for this keyword, defaulting to just the keyword itself
            synonyms = CAPTION_SYNONYMS.get(keyword_lower, {keyword_lower})

            # Check if any synonym is present in the caption
            found = any(syn in actual_lower for syn in synonyms)
            if not found:
                missing.append(keyword)

        passed = len(missing) == 0

        return FieldResult(
            field_name=field_name,
            passed=passed,
            expected=f"must contain (semantic): {expected}",
            actual=actual,
            diff={"missing_keywords": missing} if not passed else None,
        )

    def _compare_risk_assessment(
        self, expected: dict[str, Any], actual: dict[str, Any]
    ) -> list[FieldResult]:
        """Compare risk assessment results.

        Validates risk score range, level, and expected factors.

        Args:
            expected: Expected risk specification.
            actual: Actual results from pipeline (may have risk_score/risk_level at top level).

        Returns:
            List of FieldResult for each comparison performed.
        """
        results: list[FieldResult] = []

        # Risk score might be at top level or nested
        actual_score = actual.get("risk_score") or actual.get("risk", {}).get("score")

        if "min_score" in expected and "max_score" in expected:
            results.append(
                self._compare_score_range(
                    {"min": expected["min_score"], "max": expected["max_score"]},
                    actual_score,
                    "risk.score",
                )
            )

        # Risk level might be at top level or nested
        actual_level = actual.get("risk_level") or actual.get("risk", {}).get("level")

        if "level" in expected:
            results.append(
                self._compare_exact_string(
                    expected["level"],
                    actual_level,
                    "risk.level",
                )
            )

        # Expected factors
        if "expected_factors" in expected:
            actual_factors = actual.get("risk_factors") or actual.get("risk", {}).get("factors", [])
            missing = [f for f in expected["expected_factors"] if f not in actual_factors]
            passed = len(missing) == 0
            results.append(
                FieldResult(
                    field_name="risk.expected_factors",
                    passed=passed,
                    expected=expected["expected_factors"],
                    actual=actual_factors,
                    diff={"missing_factors": missing} if not passed else None,
                )
            )

        return results
