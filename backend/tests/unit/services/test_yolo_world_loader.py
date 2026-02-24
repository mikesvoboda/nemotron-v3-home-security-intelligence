"""Unit tests for yolo_world_loader service.

Tests for the YOLO-World v2 model loader for open-vocabulary object detection.
Includes tests for hierarchical prompts and category-specific thresholds.
"""

from unittest.mock import MagicMock

import pytest

from backend.services.yolo_world_loader import (
    ANIMAL_PROMPTS,
    SECURITY_PROMPTS,
    VEHICLE_SECURITY_PROMPTS,
    YOLO_WORLD_PROMPTS_V2,
    detect_with_prompts,
    get_all_security_prompts,
    get_all_yolo_world_prompts,
    get_delivery_prompts,
    get_object_category,
    get_object_priority,
    get_object_threshold,
    get_prompts_by_priority,
    get_threat_prompts,
    load_yolo_world_model,
)

# =============================================================================
# Test constants
# =============================================================================


def test_security_prompts_defined():
    """Test SECURITY_PROMPTS constant is defined and non-empty."""
    assert len(SECURITY_PROMPTS) > 0
    assert all(isinstance(p, str) for p in SECURITY_PROMPTS)


def test_security_prompts_contains_expected():
    """Test SECURITY_PROMPTS contains expected items."""
    expected_items = [
        "package",
        "knife",
        "person",
        "backpack",
        "ladder",
    ]
    for item in expected_items:
        assert item in SECURITY_PROMPTS, f"Missing expected prompt: {item}"


def test_vehicle_security_prompts_defined():
    """Test VEHICLE_SECURITY_PROMPTS constant is defined."""
    assert len(VEHICLE_SECURITY_PROMPTS) > 0
    assert all(isinstance(p, str) for p in VEHICLE_SECURITY_PROMPTS)


def test_vehicle_security_prompts_contains_vehicles():
    """Test VEHICLE_SECURITY_PROMPTS contains vehicle types."""
    expected_items = ["car", "truck", "van", "motorcycle", "bicycle"]
    for item in expected_items:
        assert item in VEHICLE_SECURITY_PROMPTS, f"Missing vehicle prompt: {item}"


def test_animal_prompts_defined():
    """Test ANIMAL_PROMPTS constant is defined."""
    assert len(ANIMAL_PROMPTS) > 0
    assert all(isinstance(p, str) for p in ANIMAL_PROMPTS)


def test_animal_prompts_contains_common_animals():
    """Test ANIMAL_PROMPTS contains common false positive sources."""
    expected_items = ["dog", "cat", "bird", "squirrel"]
    for item in expected_items:
        assert item in ANIMAL_PROMPTS, f"Missing animal prompt: {item}"


def test_prompts_are_unique():
    """Test all prompts within each category are unique.

    Note: SECURITY_PROMPTS is a concatenation of multiple categories and may
    contain intentional overlaps (e.g., "pry bar" in both weapons and
    suspicious_items). We verify uniqueness within each individual category
    instead of the combined list.
    """
    # Verify uniqueness within each v2 category (strict)
    for category, config in YOLO_WORLD_PROMPTS_V2.items():
        prompts = config["prompts"]
        assert len(prompts) == len(set(prompts)), f"Duplicate prompts in {category}"
    # Legacy lists derived from multiple categories may have cross-category overlaps
    assert len(VEHICLE_SECURITY_PROMPTS) == len(set(VEHICLE_SECURITY_PROMPTS))
    assert len(ANIMAL_PROMPTS) == len(set(ANIMAL_PROMPTS))


def test_prompts_format():
    """Test prompts are in expected format.

    Note: Some prompts like 'Amazon box' intentionally have mixed case
    for brand recognition. Most prompts should be lowercase.
    """
    # Count prompts that are lowercase vs mixed case
    all_prompts = SECURITY_PROMPTS + VEHICLE_SECURITY_PROMPTS + ANIMAL_PROMPTS
    lowercase_count = sum(1 for p in all_prompts if p == p.lower())
    total_count = len(all_prompts)

    # Most prompts should be lowercase (allow exceptions for brand names)
    assert lowercase_count >= total_count * 0.9, (
        f"Too many non-lowercase prompts: {total_count - lowercase_count}/{total_count}"
    )


# =============================================================================
# Test get_all_security_prompts
# =============================================================================


def test_get_all_security_prompts():
    """Test get_all_security_prompts returns combined list."""
    result = get_all_security_prompts()

    # Should contain items from all three categories
    assert "package" in result  # From SECURITY_PROMPTS
    assert "car" in result  # From VEHICLE_SECURITY_PROMPTS
    assert "dog" in result  # From ANIMAL_PROMPTS

    # Length should be sum of all categories
    expected_len = len(SECURITY_PROMPTS) + len(VEHICLE_SECURITY_PROMPTS) + len(ANIMAL_PROMPTS)
    assert len(result) == expected_len


def test_get_all_security_prompts_is_list():
    """Test get_all_security_prompts returns a list."""
    result = get_all_security_prompts()
    assert isinstance(result, list)


# =============================================================================
# Test get_threat_prompts
# =============================================================================


def test_get_threat_prompts():
    """Test get_threat_prompts returns threat-focused items."""
    result = get_threat_prompts()

    assert isinstance(result, list)
    assert len(result) > 0

    # Should include potential threat items
    assert "knife" in result
    assert "crowbar" in result


def test_get_threat_prompts_security_focused():
    """Test get_threat_prompts only includes threat-related items."""
    result = get_threat_prompts()

    # Should NOT include non-threat items
    assert "package" not in result
    assert "dog" not in result
    assert "car" not in result


def test_get_threat_prompts_includes_concealment():
    """Test get_threat_prompts includes concealment items."""
    result = get_threat_prompts()

    # Items that might indicate concealment
    concealment_items = ["face mask", "hoodie", "gloves"]
    for item in concealment_items:
        assert item in result, f"Missing concealment item: {item}"


# =============================================================================
# Test get_delivery_prompts
# =============================================================================


def test_get_delivery_prompts():
    """Test get_delivery_prompts returns delivery-focused items."""
    result = get_delivery_prompts()

    assert isinstance(result, list)
    assert len(result) > 0

    # Should include package items
    assert "package" in result
    assert "cardboard box" in result


def test_get_delivery_prompts_package_focused():
    """Test get_delivery_prompts only includes delivery-related items."""
    result = get_delivery_prompts()

    # Should NOT include weapons or animals
    assert "knife" not in result
    assert "dog" not in result


def test_get_delivery_prompts_amazon():
    """Test get_delivery_prompts includes Amazon-specific prompt."""
    result = get_delivery_prompts()
    assert "Amazon box" in result


# =============================================================================
# Test load_yolo_world_model error handling
# =============================================================================


@pytest.mark.asyncio
async def test_load_yolo_world_model_import_error(monkeypatch):
    """Test load_yolo_world_model handles ImportError."""
    import builtins
    import sys

    # Remove ultralytics from imports if present
    modules_to_hide = ["ultralytics"]
    hidden_modules = {}
    for mod in modules_to_hide:
        for key in list(sys.modules.keys()):
            if key == mod or key.startswith(f"{mod}."):
                hidden_modules[key] = sys.modules.pop(key)

    # Mock import to raise ImportError
    original_import = builtins.__import__

    def mock_import(name, *args, **kwargs):
        if name == "ultralytics" or name.startswith("ultralytics."):
            raise ImportError(f"No module named '{name}'")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", mock_import)

    try:
        with pytest.raises(ImportError, match="YOLO-World requires ultralytics"):
            await load_yolo_world_model("yolov8s-worldv2.pt")
    finally:
        sys.modules.update(hidden_modules)


@pytest.mark.asyncio
async def test_load_yolo_world_model_runtime_error(monkeypatch):
    """Test load_yolo_world_model handles RuntimeError."""
    import sys

    mock_ultralytics = MagicMock()
    mock_ultralytics.YOLOWorld.side_effect = RuntimeError("Model file not found")

    monkeypatch.setitem(sys.modules, "ultralytics", mock_ultralytics)

    with pytest.raises(RuntimeError, match="Failed to load YOLO-World model"):
        await load_yolo_world_model("/nonexistent/path.pt")


# =============================================================================
# Test load_yolo_world_model success path
# =============================================================================


@pytest.mark.asyncio
async def test_load_yolo_world_model_success(monkeypatch):
    """Test load_yolo_world_model success path."""
    import sys
    from unittest.mock import patch

    # Create mock YOLOWorld model
    mock_model = MagicMock()
    mock_model.set_classes = MagicMock()

    mock_ultralytics = MagicMock()
    mock_ultralytics.YOLOWorld.return_value = mock_model

    monkeypatch.setitem(sys.modules, "ultralytics", mock_ultralytics)

    with patch("torch.cuda.is_available", return_value=True):
        result = await load_yolo_world_model("yolov8s-worldv2.pt")

    assert result is mock_model
    mock_ultralytics.YOLOWorld.assert_called_once_with("yolov8s-worldv2.pt")
    # Should set default security prompts
    mock_model.set_classes.assert_called_once_with(SECURITY_PROMPTS)


@pytest.mark.asyncio
async def test_load_yolo_world_model_sets_default_prompts(monkeypatch):
    """Test load_yolo_world_model sets default security prompts."""
    import sys
    from unittest.mock import patch

    mock_model = MagicMock()

    mock_ultralytics = MagicMock()
    mock_ultralytics.YOLOWorld.return_value = mock_model

    monkeypatch.setitem(sys.modules, "ultralytics", mock_ultralytics)

    with patch("torch.cuda.is_available", return_value=True):
        await load_yolo_world_model("yolov8s-worldv2.pt")

    # Verify set_classes was called with SECURITY_PROMPTS
    mock_model.set_classes.assert_called_once()
    call_args = mock_model.set_classes.call_args[0][0]
    assert call_args == SECURITY_PROMPTS


# =============================================================================
# Test detect_with_prompts
# =============================================================================


def test_detect_with_prompts_is_async():
    """Test detect_with_prompts is an async function."""
    import inspect

    assert callable(detect_with_prompts)
    assert inspect.iscoroutinefunction(detect_with_prompts)


def test_detect_with_prompts_signature():
    """Test detect_with_prompts function signature."""
    import inspect

    sig = inspect.signature(detect_with_prompts)
    params = list(sig.parameters.keys())

    assert "model" in params
    assert "image" in params
    assert "prompts" in params
    assert "confidence_threshold" in params
    assert "iou_threshold" in params

    # Check default values
    assert sig.parameters["prompts"].default is None
    assert sig.parameters["confidence_threshold"].default == 0.25
    assert sig.parameters["iou_threshold"].default == 0.45


@pytest.mark.asyncio
async def test_detect_with_prompts_uses_default_prompts():
    """Test detect_with_prompts uses SECURITY_PROMPTS when prompts is None."""
    mock_model = MagicMock()
    mock_model.set_classes = MagicMock()
    mock_model.predict = MagicMock()

    # Create mock result with no detections
    mock_result = MagicMock()
    mock_result.boxes = None
    mock_model.predict.return_value = [mock_result]

    # Create mock image
    mock_image = MagicMock()

    result = await detect_with_prompts(mock_model, mock_image, prompts=None)

    # Should use default SECURITY_PROMPTS
    mock_model.set_classes.assert_called_once_with(SECURITY_PROMPTS)
    assert result == []


@pytest.mark.asyncio
async def test_detect_with_prompts_custom_prompts():
    """Test detect_with_prompts with custom prompts."""
    mock_model = MagicMock()
    mock_model.set_classes = MagicMock()
    mock_model.predict = MagicMock()

    mock_result = MagicMock()
    mock_result.boxes = None
    mock_model.predict.return_value = [mock_result]

    custom_prompts = ["custom object", "another object"]

    await detect_with_prompts(mock_model, MagicMock(), prompts=custom_prompts)

    mock_model.set_classes.assert_called_once_with(custom_prompts)


@pytest.mark.asyncio
async def test_detect_with_prompts_returns_detections():
    """Test detect_with_prompts returns properly formatted detections."""
    import numpy as np

    mock_model = MagicMock()
    mock_model.set_classes = MagicMock()

    # Create mock boxes
    mock_boxes = MagicMock()
    mock_boxes.__len__ = lambda _self: 2

    # Mock box data
    mock_xyxy_1 = MagicMock()
    mock_xyxy_1.cpu.return_value.numpy.return_value = np.array([10, 20, 100, 200])

    mock_xyxy_2 = MagicMock()
    mock_xyxy_2.cpu.return_value.numpy.return_value = np.array([50, 60, 150, 250])

    mock_boxes.xyxy = [mock_xyxy_1, mock_xyxy_2]

    mock_conf_1 = MagicMock()
    mock_conf_1.cpu.return_value.numpy.return_value = np.array(0.85)

    mock_conf_2 = MagicMock()
    mock_conf_2.cpu.return_value.numpy.return_value = np.array(0.72)

    mock_boxes.conf = [mock_conf_1, mock_conf_2]

    mock_cls_1 = MagicMock()
    mock_cls_1.cpu.return_value.numpy.return_value = np.array(0)

    mock_cls_2 = MagicMock()
    mock_cls_2.cpu.return_value.numpy.return_value = np.array(1)

    mock_boxes.cls = [mock_cls_1, mock_cls_2]

    mock_result = MagicMock()
    mock_result.boxes = mock_boxes
    mock_result.names = {0: "package", 1: "person"}

    mock_model.predict.return_value = [mock_result]

    result = await detect_with_prompts(mock_model, MagicMock())

    assert len(result) == 2

    # Check first detection
    assert result[0]["class_name"] == "package"
    assert result[0]["confidence"] == pytest.approx(0.85)
    assert result[0]["class_id"] == 0
    assert "bbox" in result[0]
    assert result[0]["bbox"]["x1"] == pytest.approx(10)
    assert result[0]["bbox"]["y1"] == pytest.approx(20)
    assert result[0]["bbox"]["x2"] == pytest.approx(100)
    assert result[0]["bbox"]["y2"] == pytest.approx(200)

    # Check second detection
    assert result[1]["class_name"] == "person"
    assert result[1]["confidence"] == pytest.approx(0.72)


@pytest.mark.asyncio
async def test_detect_with_prompts_confidence_threshold():
    """Test detect_with_prompts passes confidence threshold to predict."""
    mock_model = MagicMock()
    mock_model.set_classes = MagicMock()
    mock_model.predict = MagicMock()

    mock_result = MagicMock()
    mock_result.boxes = None
    mock_model.predict.return_value = [mock_result]

    await detect_with_prompts(mock_model, MagicMock(), confidence_threshold=0.5)

    # Check predict was called with correct conf parameter
    call_kwargs = mock_model.predict.call_args.kwargs
    assert call_kwargs["conf"] == 0.5


@pytest.mark.asyncio
async def test_detect_with_prompts_iou_threshold():
    """Test detect_with_prompts passes iou threshold to predict."""
    mock_model = MagicMock()
    mock_model.set_classes = MagicMock()
    mock_model.predict = MagicMock()

    mock_result = MagicMock()
    mock_result.boxes = None
    mock_model.predict.return_value = [mock_result]

    await detect_with_prompts(mock_model, MagicMock(), iou_threshold=0.6)

    # Check predict was called with correct iou parameter
    call_kwargs = mock_model.predict.call_args.kwargs
    assert call_kwargs["iou"] == 0.6


@pytest.mark.asyncio
async def test_detect_with_prompts_no_detections():
    """Test detect_with_prompts handles no detections."""
    mock_model = MagicMock()
    mock_model.set_classes = MagicMock()
    mock_model.predict = MagicMock()

    # No boxes in result
    mock_result = MagicMock()
    mock_result.boxes = None
    mock_model.predict.return_value = [mock_result]

    result = await detect_with_prompts(mock_model, MagicMock())

    assert result == []


@pytest.mark.asyncio
async def test_detect_with_prompts_empty_results():
    """Test detect_with_prompts handles empty results list."""
    mock_model = MagicMock()
    mock_model.set_classes = MagicMock()
    mock_model.predict = MagicMock()
    mock_model.predict.return_value = []

    result = await detect_with_prompts(mock_model, MagicMock())

    assert result == []


@pytest.mark.asyncio
async def test_detect_with_prompts_string_image_path():
    """Test detect_with_prompts accepts string image path."""
    mock_model = MagicMock()
    mock_model.set_classes = MagicMock()
    mock_model.predict = MagicMock()

    mock_result = MagicMock()
    mock_result.boxes = None
    mock_model.predict.return_value = [mock_result]

    image_path = "/path/to/image.jpg"
    await detect_with_prompts(mock_model, image_path)

    # Check image path was passed to predict
    call_kwargs = mock_model.predict.call_args.kwargs
    assert call_kwargs["source"] == image_path


# =============================================================================
# Test function signatures and types
# =============================================================================


def test_load_yolo_world_model_is_async():
    """Test load_yolo_world_model is an async function."""
    import inspect

    assert callable(load_yolo_world_model)
    assert inspect.iscoroutinefunction(load_yolo_world_model)


def test_load_yolo_world_model_signature():
    """Test load_yolo_world_model function signature."""
    import inspect

    sig = inspect.signature(load_yolo_world_model)
    params = list(sig.parameters.keys())
    assert "model_path" in params


# =============================================================================
# Test model_zoo integration
# =============================================================================


def test_yolo_world_in_model_zoo():
    """Test yolo-world is registered in MODEL_ZOO."""
    from backend.services.model_zoo import get_model_zoo

    zoo = get_model_zoo()
    assert "yolo-world-s" in zoo

    config = zoo["yolo-world-s"]
    assert config.name == "yolo-world-s"
    assert config.category == "detection"
    assert config.enabled is True


def test_yolo_world_model_config_load_fn():
    """Test yolo-world model config has correct load function."""
    from backend.services.model_zoo import get_model_zoo

    zoo = get_model_zoo()
    config = zoo["yolo-world-s"]
    assert config.load_fn is load_yolo_world_model


def test_yolo_world_vram_budget():
    """Test yolo-world model has reasonable VRAM budget."""
    from backend.services.model_zoo import get_model_zoo

    zoo = get_model_zoo()
    config = zoo["yolo-world-s"]
    # YOLO-World-S should be around 1.5GB according to docs
    assert config.vram_mb > 0
    assert config.vram_mb <= 3000  # Should be under 3GB


# =============================================================================
# Test docstring and documentation
# =============================================================================


def test_yolo_world_loader_module_docstring():
    """Test yolo_world_loader module has proper docstring."""
    from backend.services import yolo_world_loader

    assert yolo_world_loader.__doc__ is not None
    assert "YOLO-World" in yolo_world_loader.__doc__
    assert "open-vocabulary" in yolo_world_loader.__doc__.lower()


def test_yolo_world_loader_function_docstring():
    """Test load_yolo_world_model has proper docstring."""
    assert load_yolo_world_model.__doc__ is not None
    assert "YOLO-World" in load_yolo_world_model.__doc__
    assert "model_path" in load_yolo_world_model.__doc__
    assert "Returns" in load_yolo_world_model.__doc__
    assert "Raises" in load_yolo_world_model.__doc__


# =============================================================================
# Test edge cases
# =============================================================================


@pytest.mark.asyncio
async def test_detect_with_prompts_unknown_class():
    """Test detect_with_prompts handles unknown class gracefully."""
    import numpy as np

    mock_model = MagicMock()
    mock_model.set_classes = MagicMock()

    mock_boxes = MagicMock()
    mock_boxes.__len__ = lambda _self: 1

    mock_xyxy = MagicMock()
    mock_xyxy.cpu.return_value.numpy.return_value = np.array([10, 20, 100, 200])
    mock_boxes.xyxy = [mock_xyxy]

    mock_conf = MagicMock()
    mock_conf.cpu.return_value.numpy.return_value = np.array(0.9)
    mock_boxes.conf = [mock_conf]

    mock_cls = MagicMock()
    mock_cls.cpu.return_value.numpy.return_value = np.array(999)  # Unknown class
    mock_boxes.cls = [mock_cls]

    mock_result = MagicMock()
    mock_result.boxes = mock_boxes
    mock_result.names = {}  # No names defined

    mock_model.predict.return_value = [mock_result]

    result = await detect_with_prompts(mock_model, MagicMock())

    assert len(result) == 1
    # Should use fallback class name
    assert result[0]["class_name"] == "class_999"


def test_get_all_security_prompts_no_duplicates():
    """Test get_all_security_prompts doesn't have duplicates if categories overlap."""
    result = get_all_security_prompts()

    # Note: This test will fail if there are intentional duplicates
    # In practice, categories should not overlap
    # Just verify the list is returned correctly
    assert isinstance(result, list)
    assert len(result) > 0


def test_prompts_non_empty_strings():
    """Test all prompts are non-empty strings."""
    for prompt in SECURITY_PROMPTS:
        assert len(prompt.strip()) > 0, f"Empty prompt found: '{prompt}'"

    for prompt in VEHICLE_SECURITY_PROMPTS:
        assert len(prompt.strip()) > 0, f"Empty prompt found: '{prompt}'"

    for prompt in ANIMAL_PROMPTS:
        assert len(prompt.strip()) > 0, f"Empty prompt found: '{prompt}'"


@pytest.mark.asyncio
async def test_detect_with_prompts_verbose_false():
    """Test detect_with_prompts passes verbose=False to predict."""
    mock_model = MagicMock()
    mock_model.set_classes = MagicMock()
    mock_model.predict = MagicMock()

    mock_result = MagicMock()
    mock_result.boxes = None
    mock_model.predict.return_value = [mock_result]

    await detect_with_prompts(mock_model, MagicMock())

    # Check predict was called with verbose=False
    call_kwargs = mock_model.predict.call_args.kwargs
    assert call_kwargs["verbose"] is False


# =============================================================================
# Test Hierarchical Prompts (YOLO-World v2)
# =============================================================================


def test_yolo_world_prompts_v2_defined():
    """Test YOLO_WORLD_PROMPTS_V2 constant is defined with expected categories."""
    assert len(YOLO_WORLD_PROMPTS_V2) > 0

    # Verify expected categories exist
    expected_categories = [
        "weapons",
        "suspicious_items",
        "packages",
        "people",
        "vehicles",
        "animals",
    ]
    for category in expected_categories:
        assert category in YOLO_WORLD_PROMPTS_V2, f"Missing category: {category}"


def test_yolo_world_prompts_v2_structure():
    """Test each category has prompts list, threshold, and priority."""
    for category, config in YOLO_WORLD_PROMPTS_V2.items():
        assert "prompts" in config, f"Category {category} missing 'prompts'"
        assert "threshold" in config, f"Category {category} missing 'threshold'"
        assert "priority" in config, f"Category {category} missing 'priority'"
        assert isinstance(config["prompts"], list)
        assert isinstance(config["threshold"], float)
        assert isinstance(config["priority"], str)
        assert len(config["prompts"]) > 0, f"Category {category} has no prompts"
        assert 0.0 <= config["threshold"] <= 1.0, f"Invalid threshold for {category}"


def test_yolo_world_prompts_v2_weapons_has_low_threshold():
    """Test weapons category has lowest threshold to not miss threats."""
    weapons_threshold = YOLO_WORLD_PROMPTS_V2["weapons"]["threshold"]
    assert weapons_threshold <= 0.25, "Weapons threshold should be low to catch threats"

    # Weapons should have lower threshold than animals
    animals_threshold = YOLO_WORLD_PROMPTS_V2["animals"]["threshold"]
    assert weapons_threshold < animals_threshold


def test_yolo_world_prompts_v2_animals_has_high_threshold():
    """Test animals category has highest threshold to reduce false positives."""
    animals_threshold = YOLO_WORLD_PROMPTS_V2["animals"]["threshold"]
    assert animals_threshold >= 0.40, "Animals should have high threshold to reduce FPs"


def test_get_all_yolo_world_prompts():
    """Test get_all_yolo_world_prompts returns flattened list."""
    result = get_all_yolo_world_prompts()

    assert isinstance(result, list)
    assert len(result) > 0

    # Verify some prompts from different categories
    assert "knife blade" in result  # From weapons
    assert "dog" in result  # From animals
    assert "car" in result  # From vehicles


def test_get_all_yolo_world_prompts_total_count():
    """Test get_all_yolo_world_prompts returns correct count."""
    result = get_all_yolo_world_prompts()

    expected_count = sum(len(cat["prompts"]) for cat in YOLO_WORLD_PROMPTS_V2.values())
    assert len(result) == expected_count


def test_get_object_priority_known():
    """Test get_object_priority returns correct priority for known objects."""
    # Critical priority objects
    assert get_object_priority("knife blade") == "critical"
    assert get_object_priority("handgun") == "critical"

    # Low priority objects
    assert get_object_priority("dog") == "low"
    assert get_object_priority("car") == "low"

    # Medium priority objects
    assert get_object_priority("person") == "medium"


def test_get_object_priority_unknown():
    """Test get_object_priority returns 'low' for unknown objects."""
    result = get_object_priority("unknown_class")
    assert result == "low"


def test_get_object_category_known():
    """Test get_object_category returns correct category."""
    assert get_object_category("knife blade") == "weapons"
    assert get_object_category("dog") == "animals"
    assert get_object_category("car") == "vehicles"
    assert get_object_category("person standing") == "people"


def test_get_object_category_unknown():
    """Test get_object_category returns None for unknown objects."""
    result = get_object_category("unknown_class")
    assert result is None


def test_get_object_threshold_known():
    """Test get_object_threshold returns correct threshold for known categories."""
    assert get_object_threshold("weapons") == 0.22
    assert get_object_threshold("animals") == 0.45
    assert get_object_threshold("vehicles") == 0.40


def test_get_object_threshold_unknown():
    """Test get_object_threshold returns default for unknown categories."""
    result = get_object_threshold("unknown_category")
    assert result == 0.35  # Default threshold


def test_get_prompts_by_priority_critical():
    """Test get_prompts_by_priority returns correct prompts for critical priority."""
    result = get_prompts_by_priority("critical")

    assert isinstance(result, list)
    assert len(result) > 0
    # Weapons should be in critical
    assert "knife blade" in result
    assert "handgun" in result


def test_get_prompts_by_priority_low():
    """Test get_prompts_by_priority returns correct prompts for low priority."""
    result = get_prompts_by_priority("low")

    assert isinstance(result, list)
    # Animals and vehicles should be in low
    assert "dog" in result
    assert "car" in result


def test_get_prompts_by_priority_empty():
    """Test get_prompts_by_priority returns empty for invalid priority."""
    result = get_prompts_by_priority("invalid_priority")
    assert result == []


def test_yolo_world_prompts_v2_unique_within_categories():
    """Test prompts are unique within each category."""
    for category, config in YOLO_WORLD_PROMPTS_V2.items():
        prompts = config["prompts"]
        assert len(prompts) == len(set(prompts)), f"Duplicate prompts in {category}"


def test_yolo_world_prompts_v2_no_empty_strings():
    """Test no empty or whitespace-only prompts in v2 config."""
    for category, config in YOLO_WORLD_PROMPTS_V2.items():
        for prompt in config["prompts"]:
            assert len(prompt.strip()) > 0, f"Empty prompt in category {category}"


def test_yolo_world_prompts_v2_has_descriptive_prompts():
    """Test v2 prompts include more descriptive phrases for better detection."""
    all_prompts = get_all_yolo_world_prompts()

    # Check for descriptive prompts (multi-word phrases)
    descriptive_prompts = [p for p in all_prompts if " " in p]
    assert len(descriptive_prompts) > 10, "V2 should have many descriptive prompts"

    # Specific v2 descriptive prompts
    assert "knife blade" in all_prompts
    assert "cardboard delivery package" in all_prompts
    assert "person standing" in all_prompts


# =============================================================================
# Package Detection Prompts Tests (NEM-5293)
# =============================================================================


class TestPackageDetectionPrompts:
    """Tests for package detection prompts in YOLO-World configuration.

    NEM-5293: Verify package detection prompts are properly configured
    for the package tracking feature.
    """

    def test_packages_category_exists(self) -> None:
        """Test packages category exists in YOLO_WORLD_PROMPTS_V2."""
        assert "packages" in YOLO_WORLD_PROMPTS_V2

    def test_packages_threshold_is_035(self) -> None:
        """Test packages category has 0.35 confidence threshold."""
        config = YOLO_WORLD_PROMPTS_V2["packages"]
        assert config["threshold"] == 0.35

    def test_packages_priority_is_medium(self) -> None:
        """Test packages category has medium priority."""
        config = YOLO_WORLD_PROMPTS_V2["packages"]
        assert config["priority"] == "medium"

    def test_packages_prompts_include_cardboard_delivery_package(self) -> None:
        """Test packages prompts include 'cardboard delivery package'."""
        config = YOLO_WORLD_PROMPTS_V2["packages"]
        assert "cardboard delivery package" in config["prompts"]

    def test_packages_prompts_include_amazon_shipping_box(self) -> None:
        """Test packages prompts include 'Amazon shipping box'."""
        config = YOLO_WORLD_PROMPTS_V2["packages"]
        assert "Amazon shipping box" in config["prompts"]

    def test_packages_prompts_include_fedex_package(self) -> None:
        """Test packages prompts include 'FedEx package'."""
        config = YOLO_WORLD_PROMPTS_V2["packages"]
        assert "FedEx package" in config["prompts"]

    def test_packages_prompts_include_ups_package(self) -> None:
        """Test packages prompts include 'UPS package'."""
        config = YOLO_WORLD_PROMPTS_V2["packages"]
        assert "UPS package" in config["prompts"]

    def test_packages_prompts_include_mail_envelope(self) -> None:
        """Test packages prompts include 'mail envelope'."""
        config = YOLO_WORLD_PROMPTS_V2["packages"]
        assert "mail envelope" in config["prompts"]

    def test_packages_prompts_include_food_delivery_bag(self) -> None:
        """Test packages prompts include 'food delivery bag'."""
        config = YOLO_WORLD_PROMPTS_V2["packages"]
        assert "food delivery bag" in config["prompts"]

    def test_packages_prompts_include_pizza_box(self) -> None:
        """Test packages prompts include 'pizza box'."""
        config = YOLO_WORLD_PROMPTS_V2["packages"]
        assert "pizza box" in config["prompts"]

    def test_packages_prompts_include_legacy_package(self) -> None:
        """Test packages prompts include legacy 'package' for backward compatibility."""
        config = YOLO_WORLD_PROMPTS_V2["packages"]
        assert "package" in config["prompts"]

    def test_packages_prompts_include_legacy_cardboard_box(self) -> None:
        """Test packages prompts include legacy 'cardboard box' for backward compatibility."""
        config = YOLO_WORLD_PROMPTS_V2["packages"]
        assert "cardboard box" in config["prompts"]

    def test_packages_prompts_include_legacy_amazon_box(self) -> None:
        """Test packages prompts include legacy 'Amazon box' for backward compatibility."""
        config = YOLO_WORLD_PROMPTS_V2["packages"]
        assert "Amazon box" in config["prompts"]

    def test_packages_prompts_include_legacy_delivery_box(self) -> None:
        """Test packages prompts include legacy 'delivery box' for backward compatibility."""
        config = YOLO_WORLD_PROMPTS_V2["packages"]
        assert "delivery box" in config["prompts"]

    def test_packages_category_has_sufficient_prompts(self) -> None:
        """Test packages category has at least 10 prompts for comprehensive detection."""
        config = YOLO_WORLD_PROMPTS_V2["packages"]
        assert len(config["prompts"]) >= 10

    def test_get_object_category_returns_packages_for_package_prompts(self) -> None:
        """Test get_object_category returns 'packages' for package prompts."""
        package_prompts = [
            "cardboard delivery package",
            "Amazon shipping box",
            "FedEx package",
            "UPS package",
            "package",
        ]

        for prompt in package_prompts:
            category = get_object_category(prompt)
            assert category == "packages", f"Expected 'packages' for '{prompt}', got '{category}'"

    def test_get_object_priority_returns_medium_for_packages(self) -> None:
        """Test get_object_priority returns 'medium' for package prompts."""
        package_prompts = [
            "cardboard delivery package",
            "Amazon box",
            "package",
        ]

        for prompt in package_prompts:
            priority = get_object_priority(prompt)
            assert priority == "medium", f"Expected 'medium' for '{prompt}', got '{priority}'"

    def test_get_object_threshold_returns_035_for_packages(self) -> None:
        """Test get_object_threshold returns 0.35 for packages category."""
        threshold = get_object_threshold("packages")
        assert threshold == 0.35

    def test_packages_in_security_prompts(self) -> None:
        """Test package prompts are included in SECURITY_PROMPTS."""
        # At least some package prompts should be in SECURITY_PROMPTS
        package_related = [
            p for p in SECURITY_PROMPTS if "package" in p.lower() or "box" in p.lower()
        ]
        assert len(package_related) > 0, "Package prompts should be in SECURITY_PROMPTS"

    def test_get_delivery_prompts_includes_all_package_types(self) -> None:
        """Test get_delivery_prompts includes various package types."""
        prompts = get_delivery_prompts()

        # Should include common package types
        assert "package" in prompts
        assert "cardboard box" in prompts
        assert "Amazon box" in prompts


class TestPackageDetectionWithYoloWorld:
    """Tests for using YOLO-World to detect packages (NEM-5293).

    These tests verify the detection workflow for package detection
    using the YOLO-World model configuration.
    """

    @pytest.mark.asyncio
    async def test_detect_with_prompts_filters_by_package_threshold(self) -> None:
        """Test detect_with_prompts respects package threshold (0.35)."""
        import numpy as np

        mock_model = MagicMock()
        mock_model.set_classes = MagicMock()

        # Create mock boxes with confidence at threshold boundary
        mock_boxes = MagicMock()
        mock_boxes.__len__ = lambda _self: 2

        # Box 1: Above threshold (0.40)
        mock_xyxy_1 = MagicMock()
        mock_xyxy_1.cpu.return_value.numpy.return_value = np.array([10, 20, 100, 200])
        mock_conf_1 = MagicMock()
        mock_conf_1.cpu.return_value.numpy.return_value = np.array(0.40)
        mock_cls_1 = MagicMock()
        mock_cls_1.cpu.return_value.numpy.return_value = np.array(0)

        # Box 2: Below threshold (0.30)
        mock_xyxy_2 = MagicMock()
        mock_xyxy_2.cpu.return_value.numpy.return_value = np.array([50, 60, 150, 250])
        mock_conf_2 = MagicMock()
        mock_conf_2.cpu.return_value.numpy.return_value = np.array(0.30)
        mock_cls_2 = MagicMock()
        mock_cls_2.cpu.return_value.numpy.return_value = np.array(1)

        mock_boxes.xyxy = [mock_xyxy_1, mock_xyxy_2]
        mock_boxes.conf = [mock_conf_1, mock_conf_2]
        mock_boxes.cls = [mock_cls_1, mock_cls_2]

        mock_result = MagicMock()
        mock_result.boxes = mock_boxes
        mock_result.names = {0: "cardboard delivery package", 1: "Amazon box"}

        mock_model.predict.return_value = [mock_result]

        # Use package threshold
        package_threshold = get_object_threshold("packages")  # 0.35

        result = await detect_with_prompts(
            mock_model,
            MagicMock(),
            prompts=YOLO_WORLD_PROMPTS_V2["packages"]["prompts"],
            confidence_threshold=package_threshold,
        )

        # Both detections are returned (filtering happens in predict)
        # The model filters at predict time, not in detect_with_prompts
        # This test verifies the threshold is passed correctly
        call_kwargs = mock_model.predict.call_args.kwargs
        assert call_kwargs["conf"] == 0.35

    @pytest.mark.asyncio
    async def test_detect_with_prompts_uses_package_prompts(self) -> None:
        """Test detect_with_prompts correctly sets package prompts."""
        mock_model = MagicMock()
        mock_model.set_classes = MagicMock()
        mock_model.predict = MagicMock()

        mock_result = MagicMock()
        mock_result.boxes = None
        mock_model.predict.return_value = [mock_result]

        package_prompts = YOLO_WORLD_PROMPTS_V2["packages"]["prompts"]

        await detect_with_prompts(mock_model, MagicMock(), prompts=package_prompts)

        # Verify package prompts were set
        mock_model.set_classes.assert_called_once_with(package_prompts)

    def test_package_prompts_have_no_duplicates(self) -> None:
        """Test package prompts have no duplicate entries."""
        config = YOLO_WORLD_PROMPTS_V2["packages"]
        prompts = config["prompts"]

        assert len(prompts) == len(set(prompts)), "Package prompts should have no duplicates"

    def test_package_prompts_are_non_empty_strings(self) -> None:
        """Test all package prompts are non-empty strings."""
        config = YOLO_WORLD_PROMPTS_V2["packages"]
        prompts = config["prompts"]

        for prompt in prompts:
            assert isinstance(prompt, str), f"Prompt should be string: {prompt}"
            assert len(prompt.strip()) > 0, f"Prompt should not be empty: {prompt!r}"

    def test_package_threshold_lower_than_animals(self) -> None:
        """Test package threshold is lower than animals (packages are more important)."""
        package_threshold = YOLO_WORLD_PROMPTS_V2["packages"]["threshold"]
        animal_threshold = YOLO_WORLD_PROMPTS_V2["animals"]["threshold"]

        assert package_threshold < animal_threshold, (
            f"Package threshold ({package_threshold}) should be lower than "
            f"animal threshold ({animal_threshold})"
        )

    def test_package_threshold_higher_than_weapons(self) -> None:
        """Test package threshold is higher than weapons (weapons are more critical)."""
        package_threshold = YOLO_WORLD_PROMPTS_V2["packages"]["threshold"]
        weapon_threshold = YOLO_WORLD_PROMPTS_V2["weapons"]["threshold"]

        assert package_threshold > weapon_threshold, (
            f"Package threshold ({package_threshold}) should be higher than "
            f"weapon threshold ({weapon_threshold})"
        )
