#!/usr/bin/env python3
"""
Cosmos Video Generation Prompt Generator

Generates text prompts for NVIDIA Cosmos video generation by rendering
Jinja2 templates with YAML component files.

Usage:
    # Preview single prompt
    python scripts/cosmos_prompt_generator.py --id P01 --preview

    # Generate single prompt file
    python scripts/cosmos_prompt_generator.py --id P01

    # Generate all prompts
    python scripts/cosmos_prompt_generator.py --all

    # Generate batch JSONL for Cosmos
    python scripts/cosmos_prompt_generator.py --all --batch
"""

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

import yaml
from jinja2 import Environment, FileSystemLoader, select_autoescape

# Paths
PROJECT_ROOT = Path(__file__).parent.parent
COSMOS_DIR = PROJECT_ROOT / "data" / "synthetic" / "cosmos"
TEMPLATES_DIR = COSMOS_DIR / "prompts" / "templates"
OUTPUT_DIR = COSMOS_DIR / "cosmos_prompts"
MANIFEST_PATH = COSMOS_DIR / "generation_manifest.yaml"


def validate_path_within_directory(path: Path, allowed_base: Path) -> Path:
    """
    Validate that a path is within the allowed base directory.

    Prevents path traversal attacks by resolving the path and checking
    it starts with the allowed base directory.

    Args:
        path: The path to validate
        allowed_base: The base directory that path must be within

    Returns:
        The resolved absolute path

    Raises:
        ValueError: If the path is outside the allowed directory
    """
    resolved_path = path.resolve()
    resolved_base = allowed_base.resolve()

    if (
        not str(resolved_path).startswith(str(resolved_base) + "/")
        and resolved_path != resolved_base
    ):
        raise ValueError(f"Path '{path}' is outside allowed directory '{allowed_base}'")

    return resolved_path


def load_yaml(path: Path, allowed_base: Path | None = None) -> dict:
    """Load a YAML file with optional path validation."""
    if allowed_base is not None:
        path = validate_path_within_directory(path, allowed_base)
    with path.open() as f:
        return yaml.safe_load(f)


def load_manifest() -> dict:
    """Load the generation manifest."""
    return load_yaml(MANIFEST_PATH, allowed_base=COSMOS_DIR)


def load_component(component_type: str, component_id: str) -> dict:
    """Load a template component (scene, subject, environment, action)."""
    # Validate component_type and component_id don't contain path traversal
    if ".." in component_type or "/" in component_type or "\\" in component_type:
        raise ValueError(f"Invalid component type: {component_type}")
    if ".." in component_id or "/" in component_id or "\\" in component_id:
        raise ValueError(f"Invalid component ID: {component_id}")

    component_path = TEMPLATES_DIR / component_type / f"{component_id}.yaml"
    if not component_path.exists():
        raise FileNotFoundError(f"Component not found: {component_path}")
    return load_yaml(component_path, allowed_base=TEMPLATES_DIR)


def render_prompt(video_spec: dict, template_env: Environment) -> str:
    """Render a prompt from a video specification."""
    # Check for direct prompt override (training videos often have these)
    if "prompt_override" in video_spec:
        return video_spec["prompt_override"]

    # Load template
    template = template_env.get_template("base_prompt.jinja2")

    # Load components
    scene = load_component("scenes", video_spec["scene"])
    environment = load_component("environments", video_spec["environment"])
    subject = load_component("subjects", video_spec["subject"])
    action = load_component("actions", video_spec["action"])

    # Apply overrides if present
    if "subject_override" in video_spec:
        subject["description"] = video_spec["subject_override"]
    if "action_override" in video_spec:
        action["sequence_description"] = video_spec["action_override"]

    # Render
    prompt = template.render(
        scene=scene,
        environment=environment,
        subject=subject,
        action=action,
        generation={"duration_seconds": video_spec["duration_seconds"]},
    )

    # Clean up whitespace
    prompt = " ".join(prompt.split())

    return prompt


def get_video_spec(manifest: dict, video_id: str) -> dict | None:
    """Find a video specification by ID."""
    # Search presentation videos
    for scenario_name, videos in manifest.get("presentation", {}).items():
        for video in videos:
            if video["id"] == video_id:
                video["category"] = "presentation"
                video["scenario"] = scenario_name
                return video

    # Search training videos
    for category_name, videos in manifest.get("training", {}).items():
        for video in videos:
            if video["id"] == video_id:
                video["category"] = "training"
                video["scenario"] = category_name
                return video

    return None


def get_all_video_specs(manifest: dict) -> list[dict]:
    """Get all video specifications."""
    specs = []

    # Presentation videos
    for scenario_name, videos in manifest.get("presentation", {}).items():
        for video in videos:
            video["category"] = "presentation"
            video["scenario"] = scenario_name
            specs.append(video)

    # Training videos
    for category_name, videos in manifest.get("training", {}).items():
        for video in videos:
            video["category"] = "training"
            video["scenario"] = category_name
            specs.append(video)

    return specs


def generate_prompt_file(video_spec: dict, prompt: str, output_dir: Path) -> Path:
    """Write a prompt to a file."""
    # Validate output_dir is within COSMOS_DIR
    validated_output_dir = validate_path_within_directory(output_dir, COSMOS_DIR)
    validated_output_dir.mkdir(parents=True, exist_ok=True)

    video_id = video_spec["id"]
    variation = video_spec.get("variation", "default")

    # Validate video_id and variation don't contain path traversal
    if ".." in video_id or "/" in video_id or "\\" in video_id:
        raise ValueError(f"Invalid video ID: {video_id}")
    if ".." in variation or "/" in variation or "\\" in variation:
        raise ValueError(f"Invalid variation: {variation}")

    # Text prompt file
    prompt_path = validated_output_dir / f"{video_id}_{variation}.txt"
    with prompt_path.open("w") as f:
        f.write(prompt)

    # JSON metadata file
    meta_path = validated_output_dir / f"{video_id}_{variation}.json"
    metadata = {
        "id": video_id,
        "variation": variation,
        "category": video_spec.get("category"),
        "scenario": video_spec.get("scenario"),
        "duration_seconds": video_spec.get("duration_seconds"),
        "prompt": prompt,
        "generated_at": datetime.now(UTC).isoformat(),
    }
    with meta_path.open("w") as f:
        json.dump(metadata, f, indent=2)

    return prompt_path


def generate_batch_jsonl(specs: list[dict], prompts: list[str], output_path: Path) -> None:
    """Generate a JSONL batch file for Cosmos inference."""
    # Validate output_path is within COSMOS_DIR
    validated_output_path = validate_path_within_directory(output_path, COSMOS_DIR)
    validated_output_path.parent.mkdir(parents=True, exist_ok=True)

    with validated_output_path.open("w") as f:
        for spec, prompt in zip(specs, prompts, strict=False):
            entry = {
                "prompt": prompt,
                "output_name": f"{spec['id']}_{spec.get('variation', 'default')}",
            }
            f.write(json.dumps(entry) + "\n")


def main():
    parser = argparse.ArgumentParser(description="Generate Cosmos video prompts")
    parser.add_argument("--id", help="Video ID to generate (e.g., P01, T15)")
    parser.add_argument("--all", action="store_true", help="Generate all prompts")
    parser.add_argument("--preview", action="store_true", help="Preview prompt without writing")
    parser.add_argument("--batch", action="store_true", help="Also generate batch JSONL file")
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR, help="Output directory")

    args = parser.parse_args()

    if not args.id and not args.all:
        parser.error("Either --id or --all is required")

    # Load manifest and setup template environment
    manifest = load_manifest()
    template_env = Environment(
        loader=FileSystemLoader(TEMPLATES_DIR),
        autoescape=select_autoescape(default_for_string=True, default=True),
    )

    if args.id:
        # Generate single prompt
        video_spec = get_video_spec(manifest, args.id)
        if not video_spec:
            print(f"Error: Video ID '{args.id}' not found in manifest", file=sys.stderr)
            sys.exit(1)

        prompt = render_prompt(video_spec, template_env)

        if args.preview:
            print(f"=== {args.id}: {video_spec.get('description', '')} ===")
            print(f"Duration: {video_spec.get('duration_seconds')}s")
            print(f"Category: {video_spec.get('category')}")
            print(f"Scenario: {video_spec.get('scenario')}")
            print()
            print("--- PROMPT ---")
            print(prompt)
            print()
            print(f"Word count: {len(prompt.split())}")
        else:
            output_path = generate_prompt_file(video_spec, prompt, args.output_dir)
            print(f"Generated: {output_path}")

    elif args.all:
        # Generate all prompts
        specs = get_all_video_specs(manifest)
        prompts = []

        print(f"Generating {len(specs)} prompts...")

        for spec in specs:
            prompt = render_prompt(spec, template_env)
            prompts.append(prompt)

            if not args.preview:
                output_path = generate_prompt_file(spec, prompt, args.output_dir)
                print(f"  {spec['id']}: {output_path.name}")

        if args.preview:
            # Just show summary
            print(f"\nTotal: {len(specs)} prompts")
            print(
                f"  Presentation: {len([s for s in specs if s.get('category') == 'presentation'])}"
            )
            print(f"  Training: {len([s for s in specs if s.get('category') == 'training'])}")

        if args.batch and not args.preview:
            # Generate batch files
            presentation_specs = [s for s in specs if s.get("category") == "presentation"]
            presentation_prompts = [
                prompts[i] for i, s in enumerate(specs) if s.get("category") == "presentation"
            ]

            training_specs = [s for s in specs if s.get("category") == "training"]
            training_prompts = [
                prompts[i] for i, s in enumerate(specs) if s.get("category") == "training"
            ]

            presentation_batch = args.output_dir / "presentation_batch.jsonl"
            training_batch = args.output_dir / "training_batch.jsonl"

            generate_batch_jsonl(presentation_specs, presentation_prompts, presentation_batch)
            generate_batch_jsonl(training_specs, training_prompts, training_batch)

            print("\nBatch files:")
            print(f"  {presentation_batch}")
            print(f"  {training_batch}")

        if not args.preview:
            print(f"\nDone! {len(specs)} prompts generated in {args.output_dir}")


if __name__ == "__main__":
    main()
