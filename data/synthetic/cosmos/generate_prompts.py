#!/usr/bin/env python3
"""
Generate Cosmos prompt JSON files from the manifest and templates.
"""

import json
import yaml
from pathlib import Path
from jinja2 import Environment, FileSystemLoader

BASE_DIR = Path(__file__).parent
TEMPLATES_DIR = BASE_DIR / "prompts" / "templates"
OUTPUT_DIR = BASE_DIR / "prompts" / "generated"
MANIFEST_PATH = BASE_DIR / "generation_manifest.yaml"


def load_yaml(path: Path) -> dict:
    """Load a YAML file."""
    with open(path) as f:
        return yaml.safe_load(f)


def load_template_component(category: str, component_id: str) -> dict:
    """Load a template component (scene, environment, subject, action)."""
    path = TEMPLATES_DIR / category / f"{component_id}.yaml"
    if path.exists():
        return load_yaml(path)
    return {}


def render_prompt(video_config: dict, defaults: dict) -> str:
    """Render a prompt from video config using Jinja2 templates."""
    
    # Check if there's a prompt_override (training videos use this)
    if "prompt_override" in video_config:
        return video_config["prompt_override"]
    
    # Load template components
    scene = load_template_component("scenes", video_config.get("scene", "front_porch"))
    environment = load_template_component("environments", video_config.get("environment", "night_clear"))
    subject = load_template_component("subjects", video_config.get("subject", "person_suspicious"))
    action = load_template_component("actions", video_config.get("action", "approach_door"))
    
    # Apply overrides from video config
    if "subject_override" in video_config:
        subject["description"] = video_config["subject_override"]
        subject["appearance"] = ""
    
    if "action_override" in video_config:
        action["sequence_description"] = video_config["action_override"]
        action["additional_details"] = ""
    
    # Generation params
    generation = {
        "duration_seconds": video_config.get("duration_seconds", 15)
    }
    
    # Load and render Jinja2 template
    env = Environment(loader=FileSystemLoader(str(TEMPLATES_DIR)))
    template = env.get_template("base_prompt.jinja2")
    
    prompt = template.render(
        scene=scene,
        environment=environment,
        subject=subject,
        action=action,
        generation=generation
    )
    
    # Clean up extra whitespace
    prompt = " ".join(prompt.split())
    
    return prompt


def create_cosmos_json(video_id: str, prompt: str, output_dir: Path) -> Path:
    """Create a Cosmos-compatible JSON file for inference."""
    output_dir.mkdir(parents=True, exist_ok=True)
    
    json_data = {
        "inference_type": "text2world",
        "name": video_id,
        "prompt": prompt
    }
    
    output_path = output_dir / f"{video_id}.json"
    with open(output_path, "w") as f:
        json.dump(json_data, f, indent=2)
    
    return output_path


def process_manifest():
    """Process the manifest and generate all prompt files."""
    manifest = load_yaml(MANIFEST_PATH)
    defaults = manifest.get("defaults", {})
    
    generated_files = []
    
    # Process presentation videos
    presentation = manifest.get("presentation", {})
    for category_name, videos in presentation.items():
        if not isinstance(videos, list):
            continue
        for video in videos:
            video_id = video["id"]
            print(f"Generating prompt for {video_id}: {video.get('description', '')[:50]}...")
            
            prompt = render_prompt(video, defaults)
            output_path = create_cosmos_json(video_id, prompt, OUTPUT_DIR)
            generated_files.append({
                "id": video_id,
                "category": "presentation",
                "subcategory": category_name,
                "path": str(output_path),
                "duration_seconds": video.get("duration_seconds", 15)
            })
    
    # Process training videos
    training = manifest.get("training", {})
    for category_name, videos in training.items():
        if not isinstance(videos, list):
            continue
        for video in videos:
            video_id = video["id"]
            print(f"Generating prompt for {video_id}: {video.get('description', '')[:50]}...")
            
            prompt = render_prompt(video, defaults)
            output_path = create_cosmos_json(video_id, prompt, OUTPUT_DIR)
            generated_files.append({
                "id": video_id,
                "category": "training",
                "subcategory": category_name,
                "path": str(output_path),
                "duration_seconds": video.get("duration_seconds", 30)
            })
    
    # Write manifest of generated files
    manifest_output = OUTPUT_DIR / "generation_queue.json"
    with open(manifest_output, "w") as f:
        json.dump({
            "total": len(generated_files),
            "files": generated_files
        }, f, indent=2)
    
    print(f"\nGenerated {len(generated_files)} prompt files in {OUTPUT_DIR}")
    print(f"Queue manifest: {manifest_output}")
    
    return generated_files


if __name__ == "__main__":
    process_manifest()
