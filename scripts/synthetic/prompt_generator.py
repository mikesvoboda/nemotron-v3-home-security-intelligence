#!/usr/bin/env python3
# ABOUTME: Converts structured scenario specifications to natural language prompts for Veo/Gemini APIs.
# ABOUTME: Handles camera effects, time of day, weather, subject descriptions, and scene generation.
"""
Prompt generator for synthetic security camera footage.

Converts structured scenario specifications (JSON) into natural language prompts
suitable for NVIDIA's inference API (Veo 3.1 for video, Gemini for images).

Usage:
    from scripts.synthetic.prompt_generator import PromptGenerator

    generator = PromptGenerator()
    prompt = generator.generate_prompt(scenario_spec)
"""

from __future__ import annotations

from typing import Any

# Base template for security camera prompts
SECURITY_CAMERA_PROMPT = """
Security camera footage from a {camera_type} camera mounted at {location}.
{time_description}. {weather_description}.
{camera_effects_description}

Scene: {scene_description}

{subject_descriptions}

{action_description}

Style: Realistic security camera footage, {resolution} quality,
slight motion blur, {lighting_style} lighting.
{timestamp_overlay}
""".strip()


# Camera effect modifiers mapping
CAMERA_EFFECT_DESCRIPTIONS: dict[str, str] = {
    "fisheye_distortion": "Wide-angle fisheye lens with barrel distortion at edges",
    "ir_night_vision": "Infrared night vision mode, grayscale with slight green tint",
    "timestamp_overlay": "White timestamp text in bottom-right corner",
    "motion_blur": "Slight motion blur on moving subjects",
    "compression_artifacts": "Mild JPEG compression artifacts typical of security footage",
    "low_framerate": "Slightly choppy motion typical of 15fps security cameras",
    "lens_flare": "Subtle lens flare from bright light sources",
    "rain_on_lens": "Water droplets visible on camera lens",
    "dust_on_lens": "Slight dust or debris on camera lens reducing clarity",
}


# Time of day descriptions
TIME_OF_DAY_DESCRIPTIONS: dict[str, dict[str, str]] = {
    "dawn": {
        "description": "Early morning at dawn, golden hour lighting with soft shadows",
        "lighting_style": "warm golden hour",
        "sky_condition": "pink and orange gradients on the horizon",
    },
    "day": {
        "description": "Midday with bright natural lighting",
        "lighting_style": "bright natural",
        "sky_condition": "clear blue sky with occasional clouds",
    },
    "dusk": {
        "description": "Evening at dusk, warm sunset lighting with long shadows",
        "lighting_style": "warm sunset",
        "sky_condition": "orange and purple hues on the horizon",
    },
    "night": {
        "description": "Nighttime with artificial lighting",
        "lighting_style": "low-light artificial",
        "sky_condition": "dark sky with visible stars or clouds",
    },
    "midnight": {
        "description": "Late night, very dark with minimal lighting",
        "lighting_style": "very low-light",
        "sky_condition": "completely dark sky",
    },
}


# Weather condition descriptions
WEATHER_DESCRIPTIONS: dict[str, dict[str, str]] = {
    "clear": {
        "description": "Clear weather conditions",
        "visibility": "excellent visibility",
        "effects": "",
    },
    "rain": {
        "description": "Rainy conditions with visible precipitation",
        "visibility": "reduced visibility due to rain",
        "effects": "rain drops visible, wet surfaces reflecting light",
    },
    "snow": {
        "description": "Snowy conditions with visible snowfall",
        "visibility": "reduced visibility due to snow",
        "effects": "snowflakes visible, white ground coverage",
    },
    "fog": {
        "description": "Foggy conditions with limited visibility",
        "visibility": "significantly reduced visibility due to fog",
        "effects": "hazy atmosphere, diffused lighting",
    },
    "wind": {
        "description": "Windy conditions",
        "visibility": "good visibility",
        "effects": "vegetation and loose objects moving from wind",
    },
    "overcast": {
        "description": "Overcast sky with diffused lighting",
        "visibility": "good visibility",
        "effects": "soft, even lighting without harsh shadows",
    },
    "partly_cloudy": {
        "description": "Partly cloudy with variable lighting",
        "visibility": "good visibility",
        "effects": "occasional shadows as clouds pass",
    },
}


# Camera type descriptions
CAMERA_TYPE_DESCRIPTIONS: dict[str, str] = {
    "doorbell": "video doorbell mounted at eye level beside the front door",
    "porch": "porch camera mounted under the eave looking down at the entrance",
    "driveway": "driveway camera mounted on the garage capturing vehicle approaches",
    "backyard": "backyard camera covering the patio and yard area",
    "garage": "garage-mounted camera with wide-angle view of the property",
    "corner": "corner-mounted camera providing diagonal coverage",
    "floodlight": "floodlight camera providing illuminated coverage at night",
    "indoor": "indoor camera positioned in a common area",
}


# Location descriptions
LOCATION_DESCRIPTIONS: dict[str, str] = {
    "front_porch": "the front porch area near the main entrance",
    "front_door": "directly facing the front door entrance",
    "driveway": "the driveway and vehicle approach area",
    "backyard": "the backyard with patio and lawn area",
    "side_yard": "the side yard along the property boundary",
    "garage": "the garage entrance and nearby area",
    "walkway": "the walkway leading to the house",
    "gate": "the property gate or fence entrance",
    "pool_area": "the pool and surrounding deck area",
    "garden": "the garden area with landscaping",
}


# Subject type descriptions
SUBJECT_TYPE_TEMPLATES: dict[str, str] = {
    "person": "A {appearance} person {position_desc}",
    "vehicle": "A {appearance} vehicle {position_desc}",
    "pet": "A {appearance} {animal_type} {position_desc}",
    "package": "A {appearance} package {position_desc}",
    "delivery_person": "A delivery person in {uniform} uniform {position_desc}",
}


# Action descriptions for suspicious behavior
ACTION_DESCRIPTIONS: dict[str, str] = {
    "loitering": "lingering in the area without apparent purpose",
    "prowling": "moving cautiously while checking doors and windows",
    "casing": "observing the property from a distance",
    "approaching": "walking toward the entrance",
    "leaving": "departing from the property",
    "entering": "entering through the door",
    "exiting": "exiting through the door",
    "running": "running quickly across the scene",
    "walking": "walking at a normal pace",
    "standing": "standing still in the area",
    "crouching": "crouching or bending down",
    "looking_around": "looking around nervously",
    "checking_windows": "examining or testing windows",
    "checking_doors": "examining or testing door handles",
    "carrying_items": "carrying objects or bags",
    "taking_package": "picking up a package",
    "delivering": "delivering a package to the door",
    "driving_by": "driving past the property",
    "parking": "parking a vehicle",
    "unloading": "unloading items from a vehicle",
}


# Position descriptions
POSITION_DESCRIPTIONS: dict[str, str] = {
    "near_door": "near the front door",
    "at_door": "directly at the front door",
    "in_driveway": "in the driveway",
    "on_walkway": "on the walkway",
    "near_window": "near a window",
    "at_gate": "at the property gate",
    "in_yard": "in the yard area",
    "on_porch": "on the porch",
    "at_edge": "at the edge of the property",
    "in_street": "in the street near the property",
    "behind_bushes": "partially hidden behind bushes or landscaping",
    "in_shadows": "in a shadowed area",
}


class PromptGenerator:
    """Generate natural language prompts from structured scenario specifications.

    This class converts structured JSON scenario specifications into natural
    language prompts suitable for video/image generation APIs like Veo 3.1
    and Gemini.

    Example:
        >>> generator = PromptGenerator()
        >>> spec = {
        ...     "scene": {"location": "front_porch", "camera_type": "doorbell"},
        ...     "environment": {"time_of_day": "night", "weather": "clear"},
        ...     "subjects": [{"type": "person", "action": "loitering"}],
        ... }
        >>> prompt = generator.generate_prompt(spec)
    """

    def __init__(self, default_resolution: str = "720p") -> None:
        """Initialize the prompt generator.

        Args:
            default_resolution: Default resolution for generated content.
        """
        self.default_resolution = default_resolution

    def generate_prompt(self, scenario_spec: dict[str, Any]) -> str:
        """Generate a natural language prompt from a scenario specification.

        Args:
            scenario_spec: Dictionary containing scenario details including:
                - scene: Camera type, location, effects
                - environment: Time of day, weather, lighting, season
                - subjects: List of subjects with appearances and actions
                - generation: Format and count settings

        Returns:
            A formatted natural language prompt string.

        Raises:
            ValueError: If required fields are missing from the specification.
        """
        # Extract main sections
        scene = scenario_spec.get("scene", {})
        environment = scenario_spec.get("environment", {})
        subjects = scenario_spec.get("subjects", [])
        generation = scenario_spec.get("generation", {})

        # Generate component descriptions
        camera_type = self._get_camera_type_description(scene.get("camera_type", "porch"))
        location = self._get_location_description(scene.get("location", "front_porch"))
        time_desc = self._get_time_description(environment.get("time_of_day", "day"))
        weather_desc = self._get_weather_description(environment.get("weather", "clear"))
        camera_effects = self._get_camera_effects_description(scene.get("camera_effects", []))
        scene_desc = self._get_scene_description(scene, environment)
        subject_descs = self._get_subject_descriptions(subjects)
        action_desc = self._get_action_description(subjects)
        lighting_style = self._get_lighting_style(environment)
        resolution = generation.get("resolution", self.default_resolution)
        timestamp = self._get_timestamp_overlay(scene.get("timestamp_overlay", False))

        # Format the prompt
        prompt = SECURITY_CAMERA_PROMPT.format(
            camera_type=camera_type,
            location=location,
            time_description=time_desc,
            weather_description=weather_desc,
            camera_effects_description=camera_effects,
            scene_description=scene_desc,
            subject_descriptions=subject_descs,
            action_description=action_desc,
            resolution=resolution,
            lighting_style=lighting_style,
            timestamp_overlay=timestamp,
        )

        # Clean up extra whitespace
        return self._clean_prompt(prompt)

    def _get_camera_type_description(self, camera_type: str) -> str:
        """Get the description for a camera type.

        Args:
            camera_type: The camera type identifier.

        Returns:
            Human-readable camera type description.
        """
        return CAMERA_TYPE_DESCRIPTIONS.get(
            camera_type, f"{camera_type.replace('_', ' ')} security"
        )

    def _get_location_description(self, location: str) -> str:
        """Get the description for a location.

        Args:
            location: The location identifier.

        Returns:
            Human-readable location description.
        """
        return LOCATION_DESCRIPTIONS.get(location, location.replace("_", " "))

    def _get_time_description(self, time_of_day: str) -> str:
        """Get the time of day description.

        Args:
            time_of_day: Time identifier (dawn, day, dusk, night, midnight).

        Returns:
            Descriptive text for the time of day.
        """
        time_info = TIME_OF_DAY_DESCRIPTIONS.get(time_of_day, TIME_OF_DAY_DESCRIPTIONS["day"])
        return time_info["description"]

    def _get_weather_description(self, weather: str) -> str:
        """Get the weather condition description.

        Args:
            weather: Weather identifier (clear, rain, snow, fog, wind).

        Returns:
            Descriptive text for weather conditions.
        """
        weather_info = WEATHER_DESCRIPTIONS.get(weather, WEATHER_DESCRIPTIONS["clear"])
        desc = weather_info["description"]
        if weather_info["effects"]:
            desc += f", {weather_info['effects']}"
        return desc

    def _get_camera_effects_description(self, effects: list[str]) -> str:
        """Get combined camera effects description.

        Args:
            effects: List of camera effect identifiers.

        Returns:
            Combined description of all camera effects.
        """
        if not effects:
            return ""

        effect_texts = []
        for effect in effects:
            if effect in CAMERA_EFFECT_DESCRIPTIONS:
                effect_texts.append(CAMERA_EFFECT_DESCRIPTIONS[effect])

        if not effect_texts:
            return ""

        return "Camera effects: " + ". ".join(effect_texts) + "."

    def _get_scene_description(self, scene: dict[str, Any], environment: dict[str, Any]) -> str:
        """Generate a scene description from scene and environment data.

        Args:
            scene: Scene configuration dictionary.
            environment: Environment configuration dictionary.

        Returns:
            Natural language scene description.
        """
        parts = []

        # Add location context
        location = scene.get("location", "residential property")
        location_desc = LOCATION_DESCRIPTIONS.get(location, location.replace("_", " "))
        parts.append(f"A residential property showing {location_desc}")

        # Add season if specified
        season = environment.get("season")
        if season:
            season_descs = {
                "spring": "with spring vegetation and mild conditions",
                "summer": "with lush summer foliage",
                "fall": "with autumn colors and falling leaves",
                "winter": "with bare trees and winter conditions",
            }
            parts.append(season_descs.get(season, f"during {season}"))

        # Add lighting context
        lighting = environment.get("lighting")
        if lighting:
            lighting_descs = {
                "bright_sun": "under bright sunlight",
                "overcast": "under overcast skies with diffused light",
                "shadows": "with strong shadows from nearby structures",
                "headlights": "illuminated by vehicle headlights",
                "flashlight": "with flashlight beam visible",
                "low_ambient_streetlight": "with dim streetlight illumination",
            }
            if lighting in lighting_descs:
                parts.append(lighting_descs[lighting])

        return ". ".join(parts) + "." if parts else "A typical residential setting."

    def _get_subject_descriptions(self, subjects: list[dict[str, Any]]) -> str:
        """Generate descriptions for all subjects in the scene.

        Args:
            subjects: List of subject dictionaries.

        Returns:
            Combined subject descriptions.
        """
        if not subjects:
            return "No visible subjects in the scene."

        descriptions = []
        for i, subject in enumerate(subjects, 1):
            desc = self._describe_subject(subject, i)
            if desc:
                descriptions.append(desc)

        return "\n".join(descriptions) if descriptions else "Subjects present in scene."

    def _describe_subject(self, subject: dict[str, Any], index: int) -> str:
        """Generate a description for a single subject.

        Args:
            subject: Subject configuration dictionary.
            index: Subject index for reference.

        Returns:
            Natural language description of the subject.
        """
        subject_type = subject.get("type", "person")
        appearance = subject.get("appearance", {})
        position = subject.get("position", "")
        behavior_notes = subject.get("behavior_notes", "")

        # Build appearance description
        appearance_parts = []
        if isinstance(appearance, dict):
            if appearance.get("clothing"):
                appearance_parts.append(appearance["clothing"].replace("_", " "))
            if appearance.get("face_visible") is False:
                appearance_parts.append("with face obscured")
            if appearance.get("build"):
                appearance_parts.append(appearance["build"])
            if appearance.get("color"):
                appearance_parts.append(appearance["color"])
        elif isinstance(appearance, str):
            appearance_parts.append(appearance)

        appearance_text = " ".join(appearance_parts) if appearance_parts else ""

        # Get position description
        position_desc = POSITION_DESCRIPTIONS.get(position, position.replace("_", " "))
        if position_desc:
            position_desc = f"positioned {position_desc}"

        # Build the subject description
        if subject_type == "person":
            desc = f"Subject {index}: A"
            if appearance_text:
                desc += f" {appearance_text}"
            desc += " person"
            if position_desc:
                desc += f" {position_desc}"
        elif subject_type == "vehicle":
            desc = f"Subject {index}: A"
            if appearance_text:
                desc += f" {appearance_text}"
            desc += " vehicle"
            if position_desc:
                desc += f" {position_desc}"
        elif subject_type == "pet":
            animal_type = (
                appearance.get("animal_type", "dog") if isinstance(appearance, dict) else "pet"
            )
            desc = f"Subject {index}: A {appearance_text} {animal_type}"
            if position_desc:
                desc += f" {position_desc}"
        else:
            desc = f"Subject {index}: A {subject_type}"
            if appearance_text:
                desc += f" ({appearance_text})"
            if position_desc:
                desc += f" {position_desc}"

        # Add behavior notes
        if behavior_notes:
            desc += f", {behavior_notes}"

        return desc + "."

    def _get_action_description(self, subjects: list[dict[str, Any]]) -> str:
        """Generate action descriptions for subjects.

        Args:
            subjects: List of subject dictionaries.

        Returns:
            Combined action descriptions.
        """
        if not subjects:
            return "Empty scene with no activity."

        actions = []
        for i, subject in enumerate(subjects, 1):
            action = subject.get("action", "")
            duration = subject.get("duration_sec")

            if action:
                action_text = ACTION_DESCRIPTIONS.get(action, action.replace("_", " "))
                desc = f"Subject {i} is {action_text}"
                if duration:
                    desc += f" for approximately {duration} seconds"
                actions.append(desc)

        if not actions:
            return "Subjects are present in the scene."

        return "Actions: " + ". ".join(actions) + "."

    def _get_lighting_style(self, environment: dict[str, Any]) -> str:
        """Determine the lighting style from environment settings.

        Args:
            environment: Environment configuration dictionary.

        Returns:
            Lighting style description.
        """
        time_of_day = environment.get("time_of_day", "day")
        time_info = TIME_OF_DAY_DESCRIPTIONS.get(time_of_day, TIME_OF_DAY_DESCRIPTIONS["day"])
        return time_info["lighting_style"]

    def _get_timestamp_overlay(self, enabled: bool) -> str:
        """Get timestamp overlay description if enabled.

        Args:
            enabled: Whether timestamp overlay is enabled.

        Returns:
            Timestamp overlay description or empty string.
        """
        if enabled:
            return "Include a realistic security camera timestamp overlay in the bottom-right corner showing date and time."
        return ""

    def _clean_prompt(self, prompt: str) -> str:
        """Clean up the prompt by removing extra whitespace and blank lines.

        Args:
            prompt: Raw prompt string.

        Returns:
            Cleaned prompt string.
        """
        # Split into lines and clean
        lines = prompt.split("\n")
        cleaned_lines = []
        prev_blank = False

        for line in lines:
            stripped = line.strip()
            is_blank = not stripped

            # Skip consecutive blank lines
            if is_blank and prev_blank:
                continue

            cleaned_lines.append(stripped if stripped else "")
            prev_blank = is_blank

        # Remove leading/trailing blank lines
        while cleaned_lines and not cleaned_lines[0]:
            cleaned_lines.pop(0)
        while cleaned_lines and not cleaned_lines[-1]:
            cleaned_lines.pop()

        return "\n".join(cleaned_lines)

    def generate_image_prompt(self, scenario_spec: dict[str, Any]) -> str:
        """Generate a prompt optimized for still image generation.

        Similar to generate_prompt but adjusted for single-frame capture.

        Args:
            scenario_spec: Dictionary containing scenario details.

        Returns:
            A formatted natural language prompt for image generation.
        """
        # Use the base prompt but adjust for still image
        prompt = self.generate_prompt(scenario_spec)

        # Add still image specific instructions
        prompt += "\n\nThis is a single frame capture from the security camera, frozen in time."

        return prompt

    def generate_video_prompt(
        self, scenario_spec: dict[str, Any], duration_seconds: int = 8
    ) -> str:
        """Generate a prompt optimized for video generation.

        Similar to generate_prompt but with duration and motion context.

        Args:
            scenario_spec: Dictionary containing scenario details.
            duration_seconds: Target video duration.

        Returns:
            A formatted natural language prompt for video generation.
        """
        prompt = self.generate_prompt(scenario_spec)

        # Add video-specific instructions
        subjects = scenario_spec.get("subjects", [])
        if subjects:
            motion_desc = self._get_motion_description(subjects, duration_seconds)
            prompt += f"\n\n{motion_desc}"

        return prompt

    def _get_motion_description(self, subjects: list[dict[str, Any]], duration: int) -> str:
        """Generate motion description for video prompts.

        Args:
            subjects: List of subject dictionaries.
            duration: Video duration in seconds.

        Returns:
            Motion description for video.
        """
        parts = [f"This is a {duration}-second continuous security camera recording."]

        for subject in subjects:
            action = subject.get("action", "")
            if action in ["loitering", "standing"]:
                parts.append("The subject remains mostly stationary with subtle movements.")
            elif action in ["walking", "approaching", "leaving"]:
                parts.append("The subject moves through the frame at a walking pace.")
            elif action in ["running"]:
                parts.append("The subject moves quickly through the frame.")
            elif action in ["prowling", "looking_around"]:
                parts.append("The subject moves cautiously, looking around frequently.")

        return " ".join(parts)


def generate_prompt_from_file(spec_path: str) -> str:
    """Convenience function to generate a prompt from a JSON spec file.

    Args:
        spec_path: Path to the JSON scenario specification file.

    Returns:
        Generated prompt string.

    Raises:
        FileNotFoundError: If the spec file doesn't exist.
        json.JSONDecodeError: If the spec file isn't valid JSON.
    """
    import json
    from pathlib import Path

    spec_file = Path(spec_path)
    with spec_file.open("r") as f:
        spec = json.load(f)

    generator = PromptGenerator()
    return generator.generate_prompt(spec)


if __name__ == "__main__":
    # Example usage when run directly
    import json

    example_spec = {
        "id": "example-001",
        "category": "suspicious_activity",
        "name": "loitering_at_night",
        "scene": {
            "location": "front_porch",
            "camera_type": "doorbell",
            "camera_effects": ["fisheye_distortion", "ir_night_vision"],
            "timestamp_overlay": True,
        },
        "environment": {
            "time_of_day": "night",
            "lighting": "low_ambient_streetlight",
            "weather": "clear",
            "season": "winter",
        },
        "subjects": [
            {
                "type": "person",
                "appearance": {"clothing": "dark_hoodie", "face_visible": False},
                "action": "loitering",
                "position": "near_door",
                "duration_sec": 45,
                "behavior_notes": "looking around nervously, checking windows",
            }
        ],
        "generation": {"format": "video", "count": 3, "resolution": "720p"},
    }

    generator = PromptGenerator()

    print("=" * 60)
    print("SCENARIO SPEC:")
    print("=" * 60)
    print(json.dumps(example_spec, indent=2))

    print("\n" + "=" * 60)
    print("GENERATED PROMPT:")
    print("=" * 60)
    print(generator.generate_prompt(example_spec))

    print("\n" + "=" * 60)
    print("VIDEO PROMPT (8 seconds):")
    print("=" * 60)
    print(generator.generate_video_prompt(example_spec, duration_seconds=8))
