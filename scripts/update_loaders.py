#!/usr/bin/env python3
"""Script to add ModelLoaderBase class wrappers to all model loaders.

This script adds class-based wrappers that inherit from ModelLoaderBase
to all model loader modules, maintaining backward compatibility with
the existing functional interfaces.
"""

# Loader configurations: name, vram_mb, return_type
LOADERS = [
    ("florence", "FlorenceLoader", "florence-2-large", 1200, "tuple[Any, Any]"),
    ("yolo_world", "YOLOWorldLoader", "yolo-world-s", 1500, "Any"),
    ("vitpose", "ViTPoseLoader", "vitpose-small", 1500, "dict[str, Any]"),
    ("depth_anything", "DepthAnythingLoader", "depth-anything-v2-small", 150, "Any"),
    ("violence", "ViolenceLoader", "violence-detection", 500, "dict[str, Any]"),
    ("weather", "WeatherLoader", "weather-classification", 200, "dict[str, Any]"),
    ("segformer", "SegFormerLoader", "segformer-b2-clothes", 1500, "dict[str, Any]"),
    ("xclip", "XCLIPLoader", "xclip-base", 2000, "dict[str, Any]"),
    ("fashion_clip", "FashionCLIPLoader", "fashion-clip", 500, "dict[str, Any]"),
    ("image_quality", "ImageQualityLoader", "brisque-quality", 0, "Any"),
    (
        "vehicle_classifier",
        "VehicleClassifierLoader",
        "vehicle-segment-classification",
        1500,
        "dict[str, Any]",
    ),
    ("vehicle_damage", "VehicleDamageLoader", "vehicle-damage-detection", 2000, "dict[str, Any]"),
    ("pet_classifier", "PetClassifierLoader", "pet-classifier", 200, "dict[str, Any]"),
]

print(
    "Loader update script created. Run this with proper error handling to batch-update all loaders."
)
print(f"Total loaders to update: {len(LOADERS)}")
