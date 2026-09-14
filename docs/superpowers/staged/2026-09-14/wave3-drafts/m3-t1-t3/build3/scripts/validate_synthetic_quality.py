#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "httpx",
#     "pillow",
# ]
# ///
# ABOUTME: Validates synthetic data generation quality by comparing prompts to actual images.
# ABOUTME: Documents which scenarios have alignment issues due to AI model content policies.
"""
Synthetic Data Quality Validation Script.

This script validates the quality and alignment of synthetic security camera footage
by comparing generation prompts against actual image content using Florence-2 captions.

Background:
    AI image generation models (Gemini, Veo, etc.) are trained to refuse generating
    certain content like weapons, violence, and break-in scenarios. This means that
    even when prompts describe these scenarios, the generated images may not match.

    This script documents which scenarios suffer from this prompt-image misalignment
    and provides recommendations for using stock footage or real test data instead.

Usage:
    # Audit all scenario templates (no images needed)
    uv run scripts/validate_synthetic_quality.py audit

    # Validate a specific generation run against Florence captions
    uv run scripts/validate_synthetic_quality.py validate --run-id 20260125_143022

    # Generate alignment report
    uv run scripts/validate_synthetic_quality.py report

Outputs:
    - data/synthetic/validation_report.json: Detailed validation results
    - data/synthetic/scenario_alignment_status.json: Per-scenario alignment documentation
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

# Add project root to path for imports
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.synthetic.scenarios import (  # noqa: E402
    get_scenario,
    list_all_scenarios,
)

# Output paths
DATA_DIR = PROJECT_ROOT / "data" / "synthetic"
VALIDATION_REPORT_PATH = DATA_DIR / "validation_report.json"
ALIGNMENT_STATUS_PATH = DATA_DIR / "scenario_alignment_status.json"


@dataclass
class ContentPolicyConstraint:
    """Documents a known content policy constraint for AI image generation."""

    category: str  # Category of restricted content
    description: str  # Human-readable description
    affected_elements: list[str]  # Scenario elements affected
    recommendation: str  # Recommended alternative approach


# Known content policy constraints for AI image generation models
# These are elements that Gemini, Veo, DALL-E, etc. typically refuse to generate
KNOWN_CONTENT_RESTRICTIONS = [
    ContentPolicyConstraint(
        category="weapons",
        description="AI models refuse to generate images of weapons (guns, knives, etc.)",
        affected_elements=[
            "handgun",
            "firearm",
            "pistol",
            "rifle",
            "knife",
            "blade",
            "weapon",
            "crowbar",
            "pry_bar",
            "bat",
        ],
        recommendation="Use stock footage from Pexels/Pixabay or real test images",
    ),
    ContentPolicyConstraint(
        category="violence",
        description="AI models refuse to generate violent or threatening scenarios",
        affected_elements=[
            "aggressive",
            "threatening",
            "brandishing",
            "assault",
            "attack",
            "violence",
            "breaking",
            "forcing",
            "kicking",
        ],
        recommendation="Use stock footage depicting suspicious but non-violent activity",
    ),
    ContentPolicyConstraint(
        category="crime",
        description="AI models may refuse explicit criminal activity depictions",
        affected_elements=[
            "break_in",
            "burglary",
            "theft",
            "stealing",
            "intruder",
            "trespassing",
        ],
        recommendation="Use stock footage or staged real images with consent",
    ),
    ContentPolicyConstraint(
        category="face_concealment",
        description="AI models may have issues with masked/hooded figures",
        affected_elements=[
            "mask",
            "face_covering",
            "balaclava",
            "hood_up",
            "face_obscured",
        ],
        recommendation="Use stock footage of people in winter clothing/hats as proxy",
    ),
]


@dataclass
class ScenarioAlignment:
    """Documents the alignment status of a scenario."""

    scenario_id: str
    category: str
    name: str
    alignment_status: str  # "likely_valid", "likely_misaligned", "unknown"
    confidence: str  # "high", "medium", "low"
    content_policy_risks: list[str]  # List of potential restriction categories
    problematic_elements: list[str]  # Specific elements that may not render
    recommendation: str
    notes: str = ""


@dataclass
class ValidationReport:
    """Complete validation report for synthetic data."""

    generated_at: str
    total_scenarios: int
    likely_valid: int
    likely_misaligned: int
    unknown: int
    scenarios: list[ScenarioAlignment] = field(default_factory=list)
    summary: str = ""


def analyze_scenario_for_restrictions(scenario: dict[str, Any]) -> tuple[list[str], list[str]]:
    """Analyze a scenario spec for potential content policy restrictions.

    Args:
        scenario: The scenario specification dictionary.

    Returns:
        Tuple of (risk_categories, problematic_elements).
    """
    risk_categories: set[str] = set()
    problematic_elements: list[str] = []

    # Convert scenario to lowercase string for keyword searching
    scenario_str = json.dumps(scenario).lower()

    for constraint in KNOWN_CONTENT_RESTRICTIONS:
        for element in constraint.affected_elements:
            if element.lower() in scenario_str:
                risk_categories.add(constraint.category)
                problematic_elements.append(element)

    return list(risk_categories), problematic_elements


def determine_alignment_status(
    risk_categories: list[str], problematic_elements: list[str]
) -> tuple[str, str]:
    """Determine the likely alignment status based on content policy risks.

    Args:
        risk_categories: List of content policy risk categories.
        problematic_elements: List of specific problematic elements.

    Returns:
        Tuple of (alignment_status, confidence).
    """
    if not risk_categories:
        return "likely_valid", "high"

    # High-risk categories that almost always cause misalignment
    high_risk = {"weapons", "violence"}
    medium_risk = {"crime", "face_concealment"}

    if high_risk & set(risk_categories):
        return "likely_misaligned", "high"
    elif medium_risk & set(risk_categories):
        return "likely_misaligned", "medium"
    else:
        return "unknown", "low"


def generate_recommendation(
    alignment_status: str, risk_categories: list[str], category: str
) -> str:
    """Generate a recommendation for addressing alignment issues.

    Args:
        alignment_status: The determined alignment status.
        risk_categories: List of content policy risk categories.
        category: The scenario category (normal, suspicious, threats).

    Returns:
        Recommendation string.
    """
    if alignment_status == "likely_valid":
        return "AI-generated images should work well for this scenario."

    recommendations = []

    if "weapons" in risk_categories:
        recommendations.append(
            "Use stock footage from Pexels (search: 'security camera suspicious person')"
        )
    if "violence" in risk_categories:
        recommendations.append("Use staged test footage with actors")
    if "crime" in risk_categories:
        recommendations.append(
            "Consider using --source=stock for Pexels/Pixabay footage, "
            "or update expected_labels.json to match actual generated content"
        )
    if "face_concealment" in risk_categories:
        recommendations.append("Stock footage of people in winter clothing can work as proxy")

    if not recommendations:
        recommendations.append(
            "Review generated images manually and update expected_labels.json accordingly"
        )

    return " | ".join(recommendations)


def audit_scenario(scenario_id: str) -> ScenarioAlignment:
    """Audit a single scenario for potential alignment issues.

    Args:
        scenario_id: The scenario identifier.

    Returns:
        ScenarioAlignment documenting the scenario's status.
    """
    try:
        scenario = get_scenario(scenario_id)
    except Exception as e:
        return ScenarioAlignment(
            scenario_id=scenario_id,
            category="unknown",
            name=scenario_id,
            alignment_status="unknown",
            confidence="low",
            content_policy_risks=[],
            problematic_elements=[],
            recommendation="Failed to load scenario",
            notes=f"Error: {e}",
        )

    risk_categories, problematic_elements = analyze_scenario_for_restrictions(scenario)
    alignment_status, confidence = determine_alignment_status(risk_categories, problematic_elements)
    recommendation = generate_recommendation(
        alignment_status, risk_categories, scenario.get("category", "unknown")
    )

    # Generate notes about specific issues
    notes_parts = []
    if "weapons" in risk_categories:
        notes_parts.append(
            "Weapons will NOT be visible in AI-generated images due to safety policies"
        )
    if "violence" in risk_categories:
        notes_parts.append("Aggressive/violent poses will be sanitized by AI image generators")
    if "crime" in risk_categories:
        notes_parts.append("Criminal activity depiction may be softened or refused")

    return ScenarioAlignment(
        scenario_id=scenario_id,
        category=scenario.get("category", "unknown"),
        name=scenario.get("name", scenario_id),
        alignment_status=alignment_status,
        confidence=confidence,
        content_policy_risks=risk_categories,
        problematic_elements=problematic_elements,
        recommendation=recommendation,
        notes=" | ".join(notes_parts) if notes_parts else "",
    )


def audit_all_scenarios() -> ValidationReport:
    """Audit all scenario templates for potential alignment issues.

    Returns:
        ValidationReport with all scenario alignments.
    """
    scenarios = []
    likely_valid = 0
    likely_misaligned = 0
    unknown = 0

    all_scenario_ids = list_all_scenarios()

    for scenario_id in all_scenario_ids:
        alignment = audit_scenario(scenario_id)
        scenarios.append(alignment)

        if alignment.alignment_status == "likely_valid":
            likely_valid += 1
        elif alignment.alignment_status == "likely_misaligned":
            likely_misaligned += 1
        else:
            unknown += 1

    summary = (
        f"Audited {len(scenarios)} scenarios. "
        f"Likely valid for AI generation: {likely_valid}. "
        f"Likely misaligned (need stock footage): {likely_misaligned}. "
        f"Unknown: {unknown}."
    )

    return ValidationReport(
        generated_at=datetime.now(UTC).isoformat(),
        total_scenarios=len(scenarios),
        likely_valid=likely_valid,
        likely_misaligned=likely_misaligned,
        unknown=unknown,
        scenarios=scenarios,
        summary=summary,
    )


def print_scenario_table(scenarios: list[ScenarioAlignment]) -> None:
    """Print a formatted table of scenario alignment status.

    Args:
        scenarios: List of ScenarioAlignment objects.
    """
    # Group by category
    by_category: dict[str, list[ScenarioAlignment]] = {}
    for s in scenarios:
        by_category.setdefault(s.category, []).append(s)

    status_emoji = {
        "likely_valid": "[OK]",
        "likely_misaligned": "[WARN]",
        "unknown": "[?]",
    }

    for category, category_scenarios in sorted(by_category.items()):
        print(f"\n{'=' * 60}")
        print(f"  {category.upper()} SCENARIOS")
        print("=" * 60)

        for s in sorted(category_scenarios, key=lambda x: x.scenario_id):
            status = status_emoji.get(s.alignment_status, "[?]")
            print(f"\n{status} {s.scenario_id}: {s.name}")
            print(f"    Alignment: {s.alignment_status} (confidence: {s.confidence})")

            if s.content_policy_risks:
                print(f"    Content risks: {', '.join(s.content_policy_risks)}")

            if s.problematic_elements:
                elements_str = ", ".join(s.problematic_elements[:5])
                if len(s.problematic_elements) > 5:
                    elements_str += f" (+{len(s.problematic_elements) - 5} more)"
                print(f"    Problematic: {elements_str}")

            if s.notes:
                print(f"    Notes: {s.notes}")

            print(f"    Recommendation: {s.recommendation}")


def save_report(report: ValidationReport, path: Path) -> None:
    """Save validation report to JSON file.

    Args:
        report: The ValidationReport to save.
        path: Output path for the JSON file.
    """
    path.parent.mkdir(parents=True, exist_ok=True)

    # Convert dataclasses to dictionaries
    report_dict = {
        "generated_at": report.generated_at,
        "total_scenarios": report.total_scenarios,
        "likely_valid": report.likely_valid,
        "likely_misaligned": report.likely_misaligned,
        "unknown": report.unknown,
        "summary": report.summary,
        "scenarios": [asdict(s) for s in report.scenarios],
    }

    with open(path, "w", encoding="utf-8") as f:  # nosemgrep: path-traversal-open
        json.dump(report_dict, f, indent=2)

    print(f"\nReport saved to: {path}")


def cmd_audit(args: argparse.Namespace) -> int:
    """Execute the audit command.

    Args:
        args: Parsed command line arguments.

    Returns:
        Exit code (0 for success).
    """
    print("Auditing all synthetic scenario templates...")
    print("This analyzes scenario specs for content policy restrictions.\n")

    report = audit_all_scenarios()

    # Print table
    print_scenario_table(report.scenarios)

    # Print summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"\nTotal scenarios: {report.total_scenarios}")
    print(f"  Likely valid for AI generation: {report.likely_valid}")
    print(f"  Likely misaligned (need alternatives): {report.likely_misaligned}")
    print(f"  Unknown/needs verification: {report.unknown}")

    # Save report
    if args.output:
        output_path = Path(args.output)
    else:
        output_path = VALIDATION_REPORT_PATH

    save_report(report, output_path)

    # Print recommendations
    misaligned = [s for s in report.scenarios if s.alignment_status == "likely_misaligned"]
    if misaligned:
        print("\n" + "=" * 60)
        print("RECOMMENDED ACTIONS")
        print("=" * 60)
        print("\nThe following scenarios likely have prompt-image misalignment:")
        for s in misaligned:
            print(f"\n  - {s.scenario_id}: {s.name}")
            if s.problematic_elements:
                print(f"    Issue: Contains {', '.join(s.problematic_elements[:3])}")
            print(f"    Action: {s.recommendation}")

        print("\n\nTo use stock footage instead of AI generation:")
        print("  uv run scripts/synthetic_data.py generate --scenario <name> --source stock")

    return 0


def cmd_validate(args: argparse.Namespace) -> int:
    """Execute the validate command to check a specific generation run.

    Args:
        args: Parsed command line arguments.

    Returns:
        Exit code (0 for success, 1 for validation failures).
    """
    if not args.run_id:
        print("Error: --run-id is required for validate command", file=sys.stderr)
        return 1

    # Find the run directory
    run_dirs = list(DATA_DIR.glob(f"*/*_{args.run_id}"))
    if not run_dirs:
        print(f"Error: Run not found: {args.run_id}", file=sys.stderr)
        return 1
    if len(run_dirs) > 1:
        print(f"Error: Multiple runs match: {args.run_id}", file=sys.stderr)
        for d in run_dirs:
            print(f"  - {d}", file=sys.stderr)
        return 1

    run_dir = run_dirs[0]
    print(f"Validating run: {run_dir.name}")

    # Load scenario spec and prompt
    scenario_path = run_dir / "scenario_spec.json"
    prompt_path = run_dir / "generation_prompt.txt"
    expected_path = run_dir / "expected_labels.json"
    media_dir = run_dir / "media"

    if not scenario_path.exists():
        print(f"Error: scenario_spec.json not found in {run_dir}", file=sys.stderr)
        return 1

    with open(scenario_path, encoding="utf-8") as f:  # nosemgrep: path-traversal-open
        scenario = json.load(f)

    # Audit the scenario
    scenario_id = scenario.get("id", run_dir.name.rsplit("_", 1)[0])
    alignment = audit_scenario(scenario_id)

    print(f"\nScenario: {alignment.name}")
    print(f"Category: {alignment.category}")
    print(f"Alignment status: {alignment.alignment_status} ({alignment.confidence} confidence)")

    if alignment.content_policy_risks:
        print(f"Content policy risks: {', '.join(alignment.content_policy_risks)}")

    if alignment.problematic_elements:
        print(f"Problematic elements: {', '.join(alignment.problematic_elements)}")

    if alignment.notes:
        print(f"Notes: {alignment.notes}")

    print(f"\nRecommendation: {alignment.recommendation}")

    # Check if media files exist
    if media_dir.exists():
        media_files = list(media_dir.glob("*.*"))
        print(f"\nMedia files found: {len(media_files)}")

        if alignment.alignment_status == "likely_misaligned":
            print("\n*** WARNING ***")
            print("This scenario likely has prompt-image misalignment.")
            print("The generated images may not match the expected_labels.json.")
            print("Consider using --source=stock to get more accurate test data.")
    else:
        print("\nNo media files found (generation may not have been run yet)")

    # Load and show expected labels
    if expected_path.exists():
        with open(expected_path, encoding="utf-8") as f:  # nosemgrep: path-traversal-open
            expected = json.load(f)

        print("\nExpected labels summary:")
        if "detections" in expected:
            print(f"  Detections: {expected['detections']}")
        if "threats" in expected:
            print(f"  Threats: {expected['threats']}")
        if "risk" in expected:
            print(f"  Risk: {expected['risk']}")
        if "florence_caption" in expected:
            print(f"  Florence caption requirements: {expected['florence_caption']}")

        if alignment.alignment_status == "likely_misaligned":
            print("\n*** EXPECTED LABELS MAY NEED UPDATE ***")
            print("Since AI-generated images likely don't match the prompt,")
            print("you should either:")
            print("  1. Use stock footage (--source=stock) which may better match")
            print("  2. Update expected_labels.json to reflect actual image content")

    return 0


def cmd_report(args: argparse.Namespace) -> int:
    """Generate a summary report of scenario alignment status.

    Args:
        args: Parsed command line arguments.

    Returns:
        Exit code (0 for success).
    """
    report = audit_all_scenarios()

    # Group scenarios by alignment status
    by_status: dict[str, list[ScenarioAlignment]] = {
        "likely_valid": [],
        "likely_misaligned": [],
        "unknown": [],
    }

    for s in report.scenarios:
        by_status[s.alignment_status].append(s)

    print("=" * 60)
    print("SYNTHETIC DATA QUALITY REPORT")
    print("=" * 60)
    print(f"\nGenerated: {report.generated_at}")
    print(f"\n{report.summary}")

    print("\n" + "-" * 60)
    print("SCENARIOS SUITABLE FOR AI GENERATION")
    print("-" * 60)
    for s in by_status["likely_valid"]:
        print(f"  [OK] {s.scenario_id}: {s.name}")

    print("\n" + "-" * 60)
    print("SCENARIOS REQUIRING STOCK FOOTAGE")
    print("-" * 60)
    for s in by_status["likely_misaligned"]:
        risks = ", ".join(s.content_policy_risks) if s.content_policy_risks else "unknown"
        print(f"  [!] {s.scenario_id}: {s.name}")
        print(f"      Reason: {risks}")

    if by_status["unknown"]:
        print("\n" + "-" * 60)
        print("SCENARIOS REQUIRING VERIFICATION")
        print("-" * 60)
        for s in by_status["unknown"]:
            print(f"  [?] {s.scenario_id}: {s.name}")

    # Save structured report
    if args.output:
        output_path = Path(args.output)
    else:
        output_path = ALIGNMENT_STATUS_PATH

    save_report(report, output_path)

    return 0


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Validate synthetic data generation quality",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    # Audit command
    audit_parser = subparsers.add_parser(
        "audit",
        help="Audit all scenario templates for content policy restrictions",
    )
    audit_parser.add_argument(
        "--output",
        "-o",
        help="Output path for validation report JSON",
    )

    # Validate command
    validate_parser = subparsers.add_parser(
        "validate",
        help="Validate a specific generation run",
    )
    validate_parser.add_argument(
        "--run-id",
        "-r",
        help="Run ID to validate (timestamp, e.g., 20260125_143022)",
    )
    validate_parser.add_argument(
        "--florence-url",
        help="Florence service URL for caption generation (default: http://localhost:8092)",
        default="http://localhost:8092",
    )

    # Report command
    report_parser = subparsers.add_parser(
        "report",
        help="Generate alignment status report",
    )
    report_parser.add_argument(
        "--output",
        "-o",
        help="Output path for report JSON",
    )

    args = parser.parse_args()

    if args.command == "audit":
        return cmd_audit(args)
    elif args.command == "validate":
        return cmd_validate(args)
    elif args.command == "report":
        return cmd_report(args)
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())
