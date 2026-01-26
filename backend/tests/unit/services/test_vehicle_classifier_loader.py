"""Unit tests for vehicle_classifier_loader service.

Tests for the ResNet-50 Vehicle Segment Classification model loader and classifier.
"""

from unittest.mock import MagicMock

import pytest

from backend.services.vehicle_classifier_loader import (
    COMMERCIAL_VEHICLE_CLASSES,
    NON_VEHICLE_CLASSES,
    VEHICLE_DISPLAY_NAMES,
    VEHICLE_SEGMENT_CLASSES,
    YOLO26_VEHICLE_CLASSES,
    VehicleClassificationResult,
    classify_vehicle,
    classify_vehicles_batch,
    format_vehicle_classification_context,
    load_vehicle_classifier,
)

# Test constants


def test_vehicle_segment_classes_count():
    """Test that all 11 vehicle segment classes are defined."""
    assert len(VEHICLE_SEGMENT_CLASSES) == 11


def test_vehicle_segment_classes_content():
    """Test vehicle segment class contents."""
    expected = [
        "articulated_truck",
        "background",
        "bicycle",
        "bus",
        "car",
        "motorcycle",
        "non_motorized_vehicle",
        "pedestrian",
        "pickup_truck",
        "single_unit_truck",
        "work_van",
    ]
    assert expected == VEHICLE_SEGMENT_CLASSES


def test_vehicle_segment_classes_sorted():
    """Test vehicle segment classes are sorted alphabetically."""
    assert sorted(VEHICLE_SEGMENT_CLASSES) == VEHICLE_SEGMENT_CLASSES


def test_yolo26_vehicle_classes():
    """Test YOLO26 vehicle classes are defined."""
    expected = {"car", "truck", "bus", "motorcycle", "bicycle"}
    assert expected == YOLO26_VEHICLE_CLASSES


def test_yolo26_classes_is_frozenset():
    """Test YOLO26 classes is a frozenset."""
    assert isinstance(YOLO26_VEHICLE_CLASSES, frozenset)


def test_non_vehicle_classes():
    """Test non-vehicle classes are defined."""
    expected = {"background", "pedestrian"}
    assert expected == NON_VEHICLE_CLASSES


def test_non_vehicle_classes_is_frozenset():
    """Test non-vehicle classes is a frozenset."""
    assert isinstance(NON_VEHICLE_CLASSES, frozenset)


def test_commercial_vehicle_classes():
    """Test commercial vehicle classes are defined."""
    expected = {"articulated_truck", "single_unit_truck", "work_van"}
    assert expected == COMMERCIAL_VEHICLE_CLASSES


def test_commercial_classes_is_frozenset():
    """Test commercial classes is a frozenset."""
    assert isinstance(COMMERCIAL_VEHICLE_CLASSES, frozenset)


def test_vehicle_display_names_count():
    """Test that display names are defined for vehicle types."""
    # Should have display names for all vehicle types except background and pedestrian
    assert len(VEHICLE_DISPLAY_NAMES) == 9


def test_vehicle_display_names_content():
    """Test vehicle display names are descriptive."""
    assert VEHICLE_DISPLAY_NAMES["car"] == "car/sedan"
    assert VEHICLE_DISPLAY_NAMES["pickup_truck"] == "pickup truck"
    assert VEHICLE_DISPLAY_NAMES["work_van"] == "work van/delivery van"
    assert VEHICLE_DISPLAY_NAMES["articulated_truck"] == "articulated truck (semi/18-wheeler)"
    assert VEHICLE_DISPLAY_NAMES["single_unit_truck"] == "single-unit truck (box truck/delivery)"


def test_display_names_exclude_non_vehicle():
    """Test that non-vehicle classes don't have display names."""
    assert "background" not in VEHICLE_DISPLAY_NAMES
    assert "pedestrian" not in VEHICLE_DISPLAY_NAMES


def test_all_vehicle_classes_have_display_names():
    """Test that all vehicle classes (except non-vehicle) have display names."""
    vehicle_only = [c for c in VEHICLE_SEGMENT_CLASSES if c not in NON_VEHICLE_CLASSES]
    for cls in vehicle_only:
        assert cls in VEHICLE_DISPLAY_NAMES, f"Missing display name for {cls}"


# Test VehicleClassificationResult dataclass


def test_vehicle_classification_result_creation():
    """Test VehicleClassificationResult dataclass creation."""
    result = VehicleClassificationResult(
        vehicle_type="pickup_truck",
        confidence=0.87,
        display_name="pickup truck",
        is_commercial=False,
        all_scores={
            "pickup_truck": 0.87,
            "car": 0.08,
            "single_unit_truck": 0.03,
        },
    )

    assert result.vehicle_type == "pickup_truck"
    assert result.confidence == 0.87
    assert result.display_name == "pickup truck"
    assert result.is_commercial is False
    assert len(result.all_scores) == 3


def test_vehicle_classification_result_commercial():
    """Test VehicleClassificationResult with commercial vehicle."""
    result = VehicleClassificationResult(
        vehicle_type="work_van",
        confidence=0.92,
        display_name="work van/delivery van",
        is_commercial=True,
        all_scores={"work_van": 0.92, "car": 0.05},
    )

    assert result.vehicle_type == "work_van"
    assert result.is_commercial is True


def test_vehicle_classification_result_to_dict():
    """Test VehicleClassificationResult.to_dict() method."""
    result = VehicleClassificationResult(
        vehicle_type="car",
        confidence=0.95,
        display_name="car/sedan",
        is_commercial=False,
        all_scores={"car": 0.95, "pickup_truck": 0.03},
    )

    d = result.to_dict()

    assert d["vehicle_type"] == "car"
    assert d["confidence"] == 0.95
    assert d["display_name"] == "car/sedan"
    assert d["is_commercial"] is False
    assert d["all_scores"]["car"] == 0.95


def test_vehicle_classification_result_to_dict_all_fields():
    """Test to_dict includes all expected fields."""
    result = VehicleClassificationResult(
        vehicle_type="bus",
        confidence=0.88,
        display_name="bus",
        is_commercial=False,
        all_scores={"bus": 0.88},
    )

    d = result.to_dict()

    expected_keys = {"vehicle_type", "confidence", "display_name", "is_commercial", "all_scores"}
    assert set(d.keys()) == expected_keys


def test_vehicle_classification_result_to_context_string():
    """Test VehicleClassificationResult.to_context_string() method."""
    result = VehicleClassificationResult(
        vehicle_type="motorcycle",
        confidence=0.75,
        display_name="motorcycle",
        is_commercial=False,
        all_scores={"motorcycle": 0.75},
    )

    context = result.to_context_string()

    assert "motorcycle" in context
    assert "75%" in context
    assert "Vehicle type" in context


def test_vehicle_classification_result_context_string_commercial():
    """Test context string includes commercial indicator."""
    result = VehicleClassificationResult(
        vehicle_type="articulated_truck",
        confidence=0.99,
        display_name="articulated truck (semi/18-wheeler)",
        is_commercial=True,
        all_scores={"articulated_truck": 0.99},
    )

    context = result.to_context_string()

    assert "articulated truck" in context
    assert "99%" in context
    assert "Commercial/delivery vehicle" in context


def test_vehicle_classification_result_context_string_high_confidence():
    """Test context string with high confidence."""
    result = VehicleClassificationResult(
        vehicle_type="car",
        confidence=0.99,
        display_name="car/sedan",
        is_commercial=False,
        all_scores={"car": 0.99},
    )

    context = result.to_context_string()

    assert "car/sedan" in context
    assert "99%" in context


# Test format_vehicle_classification_context


def test_format_vehicle_classification_context_basic():
    """Test format_vehicle_classification_context basic output."""
    result = VehicleClassificationResult(
        vehicle_type="car",
        confidence=0.95,
        display_name="car/sedan",
        is_commercial=False,
        all_scores={"car": 0.95},
    )

    formatted = format_vehicle_classification_context(result)

    assert "Vehicle: car/sedan" in formatted
    assert "Confidence: 95.0%" in formatted


def test_format_vehicle_classification_context_commercial():
    """Test format_vehicle_classification_context with commercial vehicle."""
    result = VehicleClassificationResult(
        vehicle_type="work_van",
        confidence=0.88,
        display_name="work van/delivery van",
        is_commercial=True,
        all_scores={"work_van": 0.88},
    )

    formatted = format_vehicle_classification_context(result)

    assert "Vehicle: work van/delivery van" in formatted
    assert "Commercial/delivery vehicle" in formatted
    assert "Confidence: 88.0%" in formatted


def test_format_vehicle_classification_context_low_confidence():
    """Test format_vehicle_classification_context shows alternative for low confidence."""
    result = VehicleClassificationResult(
        vehicle_type="pickup_truck",
        confidence=0.55,
        display_name="pickup truck",
        is_commercial=False,
        all_scores={"pickup_truck": 0.55, "car": 0.35, "work_van": 0.10},
    )

    formatted = format_vehicle_classification_context(result)

    assert "Vehicle: pickup truck" in formatted
    assert "Confidence: 55.0%" in formatted
    assert "Alternative:" in formatted
    assert "car/sedan" in formatted  # Should show the alternative


def test_format_vehicle_classification_context_no_alternative_high_conf():
    """Test format_vehicle_classification_context doesn't show alternative at high confidence."""
    result = VehicleClassificationResult(
        vehicle_type="bus",
        confidence=0.85,
        display_name="bus",
        is_commercial=False,
        all_scores={"bus": 0.85, "single_unit_truck": 0.10},
    )

    formatted = format_vehicle_classification_context(result)

    assert "Vehicle: bus" in formatted
    assert "Alternative:" not in formatted


def test_format_vehicle_classification_context_no_alternative_single_score():
    """Test format_vehicle_classification_context with single score."""
    result = VehicleClassificationResult(
        vehicle_type="bicycle",
        confidence=0.45,
        display_name="bicycle",
        is_commercial=False,
        all_scores={"bicycle": 0.45},  # Only one score
    )

    formatted = format_vehicle_classification_context(result)

    assert "Vehicle: bicycle" in formatted
    # No alternative shown because only one score
    assert "Alternative:" not in formatted


# Test load_vehicle_classifier error handling


@pytest.mark.asyncio
async def test_load_vehicle_classifier_import_error(monkeypatch):
    """Test load_vehicle_classifier handles ImportError."""
    import builtins
    import sys

    # Remove torch and torchvision from imports if present
    modules_to_hide = ["torch", "torchvision"]
    hidden_modules = {}
    for mod in modules_to_hide:
        # Also hide submodules
        for key in list(sys.modules.keys()):
            if key == mod or key.startswith(f"{mod}."):
                hidden_modules[key] = sys.modules.pop(key)

    # Mock import to raise ImportError
    original_import = builtins.__import__

    def mock_import(name, *args, **kwargs):
        if (
            name in ("torch", "torchvision")
            or name.startswith("torch.")
            or name.startswith("torchvision.")
        ):
            raise ImportError(f"No module named '{name}'")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", mock_import)

    try:
        with pytest.raises(ImportError, match="torch and torchvision"):
            await load_vehicle_classifier("/fake/path")
    finally:
        # Restore hidden modules
        sys.modules.update(hidden_modules)


@pytest.mark.asyncio
async def test_load_vehicle_classifier_runtime_error(monkeypatch, tmp_path):
    """Test load_vehicle_classifier handles RuntimeError."""
    import sys

    # Create a mock model directory without weights
    model_dir = tmp_path / "model"
    model_dir.mkdir()

    # Create mock torch and torchvision
    mock_torch = MagicMock()
    mock_torch.cuda.is_available.return_value = False
    mock_torch.load.side_effect = RuntimeError("Model not found")

    # Create mock models module
    mock_models = MagicMock()
    mock_model = MagicMock()
    mock_models.resnet50.return_value = mock_model

    mock_torchvision = MagicMock()
    mock_torchvision.models = mock_models

    monkeypatch.setitem(sys.modules, "torch", mock_torch)
    monkeypatch.setitem(sys.modules, "torchvision", mock_torchvision)
    monkeypatch.setitem(sys.modules, "torchvision.models", mock_models)
    monkeypatch.setitem(sys.modules, "torchvision.transforms", MagicMock())

    with pytest.raises(RuntimeError, match="Failed to load Vehicle Segment Classification"):
        await load_vehicle_classifier(str(model_dir))


@pytest.mark.asyncio
async def test_load_vehicle_classifier_missing_weights(monkeypatch, tmp_path):
    """Test load_vehicle_classifier handles missing weights file."""
    import sys

    # Create a mock model directory without weights
    model_dir = tmp_path / "model"
    model_dir.mkdir()
    # Create classes.txt but not weights
    (model_dir / "classes.txt").write_text("car\ntruck\n")

    # Create mock torch and torchvision
    mock_torch = MagicMock()
    mock_torch.cuda.is_available.return_value = False

    mock_nn = MagicMock()
    mock_torch.nn = mock_nn

    # Create mock models module
    mock_models = MagicMock()
    mock_model = MagicMock()
    mock_model.fc = MagicMock()
    mock_model.fc.in_features = 2048
    mock_models.resnet50.return_value = mock_model

    mock_transforms = MagicMock()

    mock_torchvision = MagicMock()
    mock_torchvision.models = mock_models
    mock_torchvision.transforms = mock_transforms

    monkeypatch.setitem(sys.modules, "torch", mock_torch)
    monkeypatch.setitem(sys.modules, "torch.nn", mock_nn)
    monkeypatch.setitem(sys.modules, "torchvision", mock_torchvision)
    monkeypatch.setitem(sys.modules, "torchvision.models", mock_models)
    monkeypatch.setitem(sys.modules, "torchvision.transforms", mock_transforms)

    with pytest.raises(RuntimeError, match="Failed to load Vehicle Segment Classification"):
        await load_vehicle_classifier(str(model_dir))


# Test load_vehicle_classifier success path


@pytest.mark.asyncio
async def test_load_vehicle_classifier_success_cpu(monkeypatch, tmp_path):
    """Test load_vehicle_classifier success path with CPU."""
    import sys

    # Create a mock model directory
    model_dir = tmp_path / "model"
    model_dir.mkdir()
    (model_dir / "pytorch_model.bin").write_bytes(b"fake weights")
    (model_dir / "classes.txt").write_text("\n".join(VEHICLE_SEGMENT_CLASSES))

    # Create mock torch
    mock_torch = MagicMock()
    mock_torch.cuda.is_available.return_value = False
    mock_torch.load.return_value = {}

    # Create mock nn.Linear
    mock_linear = MagicMock()
    mock_nn = MagicMock()
    mock_nn.Linear.return_value = mock_linear
    mock_torch.nn = mock_nn

    # Create mock model
    mock_model = MagicMock()
    mock_model.fc = MagicMock()
    mock_model.fc.in_features = 2048
    mock_model.eval.return_value = None
    mock_model.load_state_dict.return_value = None

    # Create mock models module
    mock_models = MagicMock()
    mock_models.resnet50.return_value = mock_model

    # Create mock transforms
    mock_transforms = MagicMock()
    mock_compose = MagicMock()
    mock_transforms.Compose.return_value = mock_compose

    mock_torchvision = MagicMock()
    mock_torchvision.models = mock_models
    mock_torchvision.transforms = mock_transforms

    monkeypatch.setitem(sys.modules, "torch", mock_torch)
    monkeypatch.setitem(sys.modules, "torch.nn", mock_nn)
    monkeypatch.setitem(sys.modules, "torchvision", mock_torchvision)
    monkeypatch.setitem(sys.modules, "torchvision.models", mock_models)
    monkeypatch.setitem(sys.modules, "torchvision.transforms", mock_transforms)

    result = await load_vehicle_classifier(str(model_dir))

    assert "model" in result
    assert "transform" in result
    assert "classes" in result
    assert len(result["classes"]) == 11
    mock_model.eval.assert_called_once()


@pytest.mark.asyncio
async def test_load_vehicle_classifier_success_cuda(monkeypatch, tmp_path):
    """Test load_vehicle_classifier success path with CUDA."""
    import sys

    # Create a mock model directory
    model_dir = tmp_path / "model"
    model_dir.mkdir()
    (model_dir / "pytorch_model.bin").write_bytes(b"fake weights")
    (model_dir / "classes.txt").write_text("\n".join(VEHICLE_SEGMENT_CLASSES))

    # Create mock torch with CUDA
    mock_torch = MagicMock()
    mock_torch.cuda.is_available.return_value = True
    mock_torch.load.return_value = {}

    # Create mock nn.Linear
    mock_linear = MagicMock()
    mock_nn = MagicMock()
    mock_nn.Linear.return_value = mock_linear
    mock_torch.nn = mock_nn

    # Create mock model that supports cuda()
    mock_cuda_model = MagicMock()
    mock_cuda_model.eval.return_value = None

    mock_model = MagicMock()
    mock_model.fc = MagicMock()
    mock_model.fc.in_features = 2048
    mock_model.load_state_dict.return_value = None
    mock_model.cuda.return_value = mock_cuda_model

    # Create mock models module
    mock_models = MagicMock()
    mock_models.resnet50.return_value = mock_model

    # Create mock transforms
    mock_transforms = MagicMock()
    mock_compose = MagicMock()
    mock_transforms.Compose.return_value = mock_compose

    mock_torchvision = MagicMock()
    mock_torchvision.models = mock_models
    mock_torchvision.transforms = mock_transforms

    monkeypatch.setitem(sys.modules, "torch", mock_torch)
    monkeypatch.setitem(sys.modules, "torch.nn", mock_nn)
    monkeypatch.setitem(sys.modules, "torchvision", mock_torchvision)
    monkeypatch.setitem(sys.modules, "torchvision.models", mock_models)
    monkeypatch.setitem(sys.modules, "torchvision.transforms", mock_transforms)

    result = await load_vehicle_classifier(str(model_dir))

    assert "model" in result
    assert "transform" in result
    assert "classes" in result
    mock_model.cuda.assert_called_once()


@pytest.mark.asyncio
async def test_load_vehicle_classifier_fallback_classes(monkeypatch, tmp_path):
    """Test load_vehicle_classifier uses fallback classes when classes.txt missing."""
    import sys

    # Create a mock model directory WITHOUT classes.txt
    model_dir = tmp_path / "model"
    model_dir.mkdir()
    (model_dir / "pytorch_model.bin").write_bytes(b"fake weights")
    # Note: no classes.txt file

    # Create mock torch
    mock_torch = MagicMock()
    mock_torch.cuda.is_available.return_value = False
    mock_torch.load.return_value = {}

    # Create mock nn.Linear
    mock_linear = MagicMock()
    mock_nn = MagicMock()
    mock_nn.Linear.return_value = mock_linear
    mock_torch.nn = mock_nn

    # Create mock model
    mock_model = MagicMock()
    mock_model.fc = MagicMock()
    mock_model.fc.in_features = 2048
    mock_model.eval.return_value = None
    mock_model.load_state_dict.return_value = None

    # Create mock models module
    mock_models = MagicMock()
    mock_models.resnet50.return_value = mock_model

    # Create mock transforms
    mock_transforms = MagicMock()
    mock_compose = MagicMock()
    mock_transforms.Compose.return_value = mock_compose

    mock_torchvision = MagicMock()
    mock_torchvision.models = mock_models
    mock_torchvision.transforms = mock_transforms

    monkeypatch.setitem(sys.modules, "torch", mock_torch)
    monkeypatch.setitem(sys.modules, "torch.nn", mock_nn)
    monkeypatch.setitem(sys.modules, "torchvision", mock_torchvision)
    monkeypatch.setitem(sys.modules, "torchvision.models", mock_models)
    monkeypatch.setitem(sys.modules, "torchvision.transforms", mock_transforms)

    result = await load_vehicle_classifier(str(model_dir))

    # Should use the default VEHICLE_SEGMENT_CLASSES
    assert result["classes"] == VEHICLE_SEGMENT_CLASSES


# Test classify_vehicle


def test_classify_vehicle_callable():
    """Test classify_vehicle is an async function."""
    import inspect

    assert callable(classify_vehicle)
    assert inspect.iscoroutinefunction(classify_vehicle)


def test_classify_vehicle_signature():
    """Test classify_vehicle has expected parameters."""
    import inspect

    sig = inspect.signature(classify_vehicle)
    params = list(sig.parameters.keys())

    assert "model_dict" in params
    assert "image" in params
    assert "top_k" in params
    assert sig.parameters["top_k"].default == 3


@pytest.mark.asyncio
async def test_classify_vehicle_runtime_error():
    """Test classify_vehicle handles runtime errors."""
    from PIL import Image

    test_image = Image.new("RGB", (224, 224))

    # Create model dict with model that raises error
    mock_model = MagicMock()
    mock_model.parameters.side_effect = RuntimeError("GPU OOM")

    model_dict = {
        "model": mock_model,
        "transform": MagicMock(),
        "classes": VEHICLE_SEGMENT_CLASSES,
    }

    with pytest.raises(RuntimeError, match="Vehicle classification failed"):
        await classify_vehicle(model_dict, test_image)


@pytest.mark.asyncio
async def test_classify_vehicle_success(monkeypatch):
    """Test classify_vehicle success path."""
    import sys

    from PIL import Image

    test_image = Image.new("RGB", (224, 224))

    # Create mock torch with tensor operations
    mock_torch = MagicMock()

    # Create mock tensor
    mock_output = MagicMock()

    # Create mock probabilities (11 classes, pickup_truck should win)
    # Order: articulated_truck, background, bicycle, bus, car, motorcycle,
    # non_motorized_vehicle, pedestrian, pickup_truck, single_unit_truck, work_van
    mock_probs = MagicMock()
    mock_probs.__iter__ = lambda _self: iter(
        [
            MagicMock(item=lambda: 0.02),  # articulated_truck
            MagicMock(item=lambda: 0.01),  # background
            MagicMock(item=lambda: 0.01),  # bicycle
            MagicMock(item=lambda: 0.03),  # bus
            MagicMock(item=lambda: 0.15),  # car
            MagicMock(item=lambda: 0.02),  # motorcycle
            MagicMock(item=lambda: 0.01),  # non_motorized_vehicle
            MagicMock(item=lambda: 0.01),  # pedestrian
            MagicMock(item=lambda: 0.70),  # pickup_truck (winner)
            MagicMock(item=lambda: 0.03),  # single_unit_truck
            MagicMock(item=lambda: 0.01),  # work_van
        ]
    )

    def mock_probs_getitem(self, idx):
        items = [0.02, 0.01, 0.01, 0.03, 0.15, 0.02, 0.01, 0.01, 0.70, 0.03, 0.01]
        mock_item = MagicMock()
        mock_item.item.return_value = items[idx]
        return mock_item

    mock_probs.__getitem__ = lambda _self, _idx: mock_probs_getitem(mock_probs, _idx)

    mock_softmax_output = MagicMock()
    mock_softmax_output.__getitem__ = lambda _self, _idx: mock_probs

    mock_torch.nn.functional.softmax.return_value = mock_softmax_output
    mock_torch.no_grad.return_value.__enter__ = MagicMock(return_value=None)
    mock_torch.no_grad.return_value.__exit__ = MagicMock(return_value=None)

    # Create mock model
    mock_model = MagicMock()
    mock_device = MagicMock()
    mock_model.parameters.return_value = iter([MagicMock(device=mock_device)])
    mock_model.return_value = mock_output

    # Create mock transform
    mock_transform = MagicMock()
    mock_transformed = MagicMock()
    mock_transformed.unsqueeze.return_value = MagicMock()
    mock_transform.return_value = mock_transformed

    model_dict = {
        "model": mock_model,
        "transform": mock_transform,
        "classes": VEHICLE_SEGMENT_CLASSES,
    }

    monkeypatch.setitem(sys.modules, "torch", mock_torch)

    result = await classify_vehicle(model_dict, test_image)

    assert isinstance(result, VehicleClassificationResult)


# Test classify_vehicles_batch


def test_classify_vehicles_batch_callable():
    """Test classify_vehicles_batch is an async function."""
    import inspect

    assert callable(classify_vehicles_batch)
    assert inspect.iscoroutinefunction(classify_vehicles_batch)


def test_classify_vehicles_batch_signature():
    """Test classify_vehicles_batch has expected parameters."""
    import inspect

    sig = inspect.signature(classify_vehicles_batch)
    params = list(sig.parameters.keys())

    assert "model_dict" in params
    assert "images" in params
    assert "top_k" in params
    assert sig.parameters["top_k"].default == 3


@pytest.mark.asyncio
async def test_classify_vehicles_batch_empty():
    """Test classify_vehicles_batch returns empty list for empty input."""
    model_dict = {
        "model": MagicMock(),
        "transform": MagicMock(),
        "classes": VEHICLE_SEGMENT_CLASSES,
    }

    result = await classify_vehicles_batch(model_dict, images=[])

    assert result == []


@pytest.mark.asyncio
async def test_classify_vehicles_batch_runtime_error():
    """Test classify_vehicles_batch handles runtime errors."""
    from PIL import Image

    test_images = [Image.new("RGB", (224, 224)) for _ in range(3)]

    # Create model dict with model that raises error
    mock_model = MagicMock()
    mock_model.parameters.side_effect = RuntimeError("GPU OOM")

    model_dict = {
        "model": mock_model,
        "transform": MagicMock(),
        "classes": VEHICLE_SEGMENT_CLASSES,
    }

    with pytest.raises(RuntimeError, match="Batch vehicle classification failed"):
        await classify_vehicles_batch(model_dict, test_images)


@pytest.mark.asyncio
async def test_classify_vehicles_batch_success(monkeypatch):
    """Test classify_vehicles_batch success path."""
    import sys

    from PIL import Image

    test_images = [Image.new("RGB", (224, 224)) for _ in range(2)]

    # Create mock torch with tensor operations
    mock_torch = MagicMock()

    # Create mock tensor that can be stacked
    mock_tensor = MagicMock()
    mock_torch.stack.return_value = mock_tensor

    # Create mock probs for each image in batch - 11 classes each
    # First image: car, Second image: work_van (commercial)
    def create_mock_probs(car_wins=True):
        mock_probs = MagicMock()
        if car_wins:
            # Car wins - index 4 in VEHICLE_SEGMENT_CLASSES
            items = [0.01, 0.01, 0.01, 0.02, 0.80, 0.02, 0.01, 0.01, 0.05, 0.03, 0.03]
        else:
            # Work van wins - index 10 in VEHICLE_SEGMENT_CLASSES (commercial)
            items = [0.02, 0.01, 0.01, 0.02, 0.10, 0.01, 0.01, 0.01, 0.05, 0.03, 0.73]

        def mock_probs_getitem(self, idx):
            mock_item = MagicMock()
            mock_item.item.return_value = items[idx]
            return mock_item

        mock_probs.__getitem__ = lambda _self, _idx: mock_probs_getitem(mock_probs, _idx)
        return mock_probs

    mock_probs_batch = [create_mock_probs(car_wins=True), create_mock_probs(car_wins=False)]

    # Make all_probs iterable
    mock_all_probs = MagicMock()
    mock_all_probs.__iter__ = lambda _self: iter(mock_probs_batch)

    mock_torch.nn.functional.softmax.return_value = mock_all_probs
    mock_torch.no_grad.return_value.__enter__ = MagicMock(return_value=None)
    mock_torch.no_grad.return_value.__exit__ = MagicMock(return_value=None)

    # Create mock model
    mock_model = MagicMock()
    mock_device = MagicMock()
    mock_model.parameters.return_value = iter([MagicMock(device=mock_device)])
    mock_model.return_value = MagicMock()

    # Create mock transform
    mock_transform = MagicMock()
    mock_transformed = MagicMock()
    mock_transform.return_value = mock_transformed

    model_dict = {
        "model": mock_model,
        "transform": mock_transform,
        "classes": VEHICLE_SEGMENT_CLASSES,
    }

    monkeypatch.setitem(sys.modules, "torch", mock_torch)

    results = await classify_vehicles_batch(model_dict, test_images)

    assert len(results) == 2
    assert all(isinstance(r, VehicleClassificationResult) for r in results)
    # First result should be car (non-commercial)
    assert results[0].vehicle_type == "car"
    assert results[0].is_commercial is False
    # Second result should be work_van (commercial)
    assert results[1].vehicle_type == "work_van"
    assert results[1].is_commercial is True


@pytest.mark.asyncio
async def test_classify_vehicles_batch_with_non_rgb_image(monkeypatch):
    """Test classify_vehicles_batch handles RGBA images by converting to RGB."""
    import sys

    from PIL import Image

    # Create RGBA image (not RGB)
    test_images = [Image.new("RGBA", (224, 224))]

    # Create mock torch
    mock_torch = MagicMock()
    mock_tensor = MagicMock()
    mock_torch.stack.return_value = mock_tensor

    # Create mock probs - car wins
    mock_probs = MagicMock()
    items = [0.01, 0.01, 0.01, 0.02, 0.80, 0.02, 0.01, 0.01, 0.05, 0.03, 0.03]

    def mock_probs_getitem(self, idx):
        mock_item = MagicMock()
        mock_item.item.return_value = items[idx]
        return mock_item

    mock_probs.__getitem__ = lambda _self, _idx: mock_probs_getitem(mock_probs, _idx)

    mock_all_probs = MagicMock()
    mock_all_probs.__iter__ = lambda _self: iter([mock_probs])

    mock_torch.nn.functional.softmax.return_value = mock_all_probs
    mock_torch.no_grad.return_value.__enter__ = MagicMock(return_value=None)
    mock_torch.no_grad.return_value.__exit__ = MagicMock(return_value=None)

    # Create mock model
    mock_model = MagicMock()
    mock_device = MagicMock()
    mock_model.parameters.return_value = iter([MagicMock(device=mock_device)])
    mock_model.return_value = MagicMock()

    # Create mock transform
    mock_transform = MagicMock()

    model_dict = {
        "model": mock_model,
        "transform": mock_transform,
        "classes": VEHICLE_SEGMENT_CLASSES,
    }

    monkeypatch.setitem(sys.modules, "torch", mock_torch)

    results = await classify_vehicles_batch(model_dict, test_images)

    assert len(results) == 1
    assert results[0].vehicle_type == "car"


# Test model_zoo integration


def test_vehicle_segment_classification_in_model_zoo():
    """Test vehicle-segment-classification is registered in MODEL_ZOO."""
    from backend.services.model_zoo import get_model_zoo

    zoo = get_model_zoo()
    assert "vehicle-segment-classification" in zoo

    config = zoo["vehicle-segment-classification"]
    assert config.name == "vehicle-segment-classification"
    assert config.vram_mb == 1500
    assert config.category == "classification"


def test_vehicle_segment_classification_uses_correct_loader():
    """Test vehicle-segment-classification uses load_vehicle_classifier."""
    from backend.services.model_zoo import get_model_zoo

    zoo = get_model_zoo()
    config = zoo["vehicle-segment-classification"]
    assert config.load_fn == load_vehicle_classifier


def test_vehicle_segment_classification_path():
    """Test vehicle-segment-classification has correct path."""
    from backend.services.model_zoo import get_model_zoo

    zoo = get_model_zoo()
    config = zoo["vehicle-segment-classification"]
    assert "/models/model-zoo/vehicle-segment-classification" in config.path


def test_vehicle_segment_classification_enabled():
    """Test vehicle-segment-classification is enabled."""
    from backend.services.model_zoo import get_model_zoo

    zoo = get_model_zoo()
    config = zoo["vehicle-segment-classification"]
    assert config.enabled is True


# Test edge cases


def test_vehicle_classification_result_all_zeros():
    """Test VehicleClassificationResult with zero confidence."""
    result = VehicleClassificationResult(
        vehicle_type="car",
        confidence=0.0,
        display_name="car/sedan",
        is_commercial=False,
        all_scores={"car": 0.0},
    )

    d = result.to_dict()
    assert d["confidence"] == 0.0


def test_vehicle_classification_result_empty_scores():
    """Test VehicleClassificationResult with empty all_scores."""
    result = VehicleClassificationResult(
        vehicle_type="car",
        confidence=0.5,
        display_name="car/sedan",
        is_commercial=False,
        all_scores={},
    )

    d = result.to_dict()
    assert d["all_scores"] == {}


def test_format_context_unknown_vehicle_type():
    """Test format_vehicle_classification_context with unknown vehicle type."""
    result = VehicleClassificationResult(
        vehicle_type="unknown_vehicle",
        confidence=0.5,
        display_name="unknown_vehicle",  # Falls back to type name
        is_commercial=False,
        all_scores={"unknown_vehicle": 0.5},
    )

    formatted = format_vehicle_classification_context(result)

    assert "Vehicle: unknown_vehicle" in formatted
    assert "Confidence: 50.0%" in formatted


def test_vehicle_display_names_all_valid():
    """Test that all display names are non-empty strings."""
    for vehicle_type, display_name in VEHICLE_DISPLAY_NAMES.items():
        assert isinstance(display_name, str)
        assert len(display_name) > 0
        assert vehicle_type in VEHICLE_SEGMENT_CLASSES


def test_commercial_classes_are_vehicles():
    """Test that all commercial classes are in vehicle segment classes."""
    for cls in COMMERCIAL_VEHICLE_CLASSES:
        assert cls in VEHICLE_SEGMENT_CLASSES


def test_non_vehicle_classes_in_segment_classes():
    """Test that non-vehicle classes are in vehicle segment classes."""
    for cls in NON_VEHICLE_CLASSES:
        assert cls in VEHICLE_SEGMENT_CLASSES


def test_vehicle_classification_image_modes():
    """Test that classify_vehicle handles different image modes."""
    # This is a design check - the function should convert to RGB
    import inspect

    source = inspect.getsource(classify_vehicle)
    assert 'convert("RGB")' in source or "convert('RGB')" in source


def test_batch_classification_image_modes():
    """Test that classify_vehicles_batch handles different image modes."""
    # This is a design check - the function should convert to RGB
    import inspect

    source = inspect.getsource(classify_vehicles_batch)
    assert 'convert("RGB")' in source or "convert('RGB')" in source
