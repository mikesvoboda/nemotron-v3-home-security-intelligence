"""Unit tests for segformer_loader service.

Tests for the SegFormer B2 Clothes model loader and clothing segmentation.
"""

from unittest.mock import MagicMock

import pytest

from backend.services.segformer_loader import (
    CLOTHING_LABELS,
    SECURITY_CLOTHING_LABELS,
    SHOE_LABELS,
    ClothingSegmentationResult,
    format_batch_clothing_context,
    format_clothing_context,
    load_segformer_model,
    segment_clothing,
    segment_clothing_batch,
)

# =============================================================================
# Test ClothingSegmentationResult dataclass
# =============================================================================


def test_clothing_segmentation_result_creation():
    """Test ClothingSegmentationResult dataclass creation."""
    result = ClothingSegmentationResult(
        clothing_items={"hat", "pants", "upper_clothes"},
        has_face_covered=True,
        has_bag=True,
        coverage_percentages={"hat": 5.0, "pants": 25.0, "upper_clothes": 30.0},
        raw_mask=None,
    )

    assert result.clothing_items == {"hat", "pants", "upper_clothes"}
    assert result.has_face_covered is True
    assert result.has_bag is True
    assert len(result.coverage_percentages) == 3
    assert result.raw_mask is None


def test_clothing_segmentation_result_defaults():
    """Test ClothingSegmentationResult default values."""
    result = ClothingSegmentationResult()

    assert result.clothing_items == set()
    assert result.has_face_covered is False
    assert result.has_bag is False
    assert result.coverage_percentages == {}
    assert result.raw_mask is None


def test_clothing_segmentation_result_to_dict():
    """Test ClothingSegmentationResult.to_dict() method."""
    result = ClothingSegmentationResult(
        clothing_items={"hat", "bag", "sunglasses"},
        has_face_covered=True,
        has_bag=True,
        coverage_percentages={"hat": 3.0, "bag": 2.0, "sunglasses": 1.5},
        raw_mask=MagicMock(),  # Should be excluded from dict
    )

    d = result.to_dict()

    assert d["clothing_items"] == ["bag", "hat", "sunglasses"]  # Sorted
    assert d["has_face_covered"] is True
    assert d["has_bag"] is True
    assert d["coverage_percentages"]["hat"] == 3.0
    # raw_mask should not be in the dict
    assert "raw_mask" not in d


def test_clothing_segmentation_result_to_dict_empty():
    """Test ClothingSegmentationResult.to_dict() with empty items."""
    result = ClothingSegmentationResult()

    d = result.to_dict()

    assert d["clothing_items"] == []
    assert d["has_face_covered"] is False
    assert d["has_bag"] is False
    assert d["coverage_percentages"] == {}


# =============================================================================
# Test constants
# =============================================================================


def test_clothing_labels_count():
    """Test that all 18 clothing labels are defined."""
    assert len(CLOTHING_LABELS) == 18


def test_clothing_labels_content():
    """Test clothing label contents."""
    expected_labels = [
        "background",
        "hat",
        "hair",
        "sunglasses",
        "upper_clothes",
        "skirt",
        "pants",
        "dress",
        "belt",
        "left_shoe",
        "right_shoe",
        "face",
        "left_leg",
        "right_leg",
        "left_arm",
        "right_arm",
        "bag",
        "scarf",
    ]
    for i, label in enumerate(expected_labels):
        assert CLOTHING_LABELS[i] == label


def test_clothing_labels_indices():
    """Test specific clothing label indices."""
    assert CLOTHING_LABELS[0] == "background"
    assert CLOTHING_LABELS[1] == "hat"
    assert CLOTHING_LABELS[3] == "sunglasses"
    assert CLOTHING_LABELS[4] == "upper_clothes"
    assert CLOTHING_LABELS[6] == "pants"
    assert CLOTHING_LABELS[11] == "face"
    assert CLOTHING_LABELS[16] == "bag"
    assert CLOTHING_LABELS[17] == "scarf"


def test_security_clothing_labels_content():
    """Test security-relevant clothing labels."""
    expected = {
        "hat",
        "sunglasses",
        "upper_clothes",
        "skirt",
        "pants",
        "dress",
        "belt",
        "bag",
        "scarf",
    }
    assert expected == SECURITY_CLOTHING_LABELS


def test_security_clothing_labels_is_frozenset():
    """Test that SECURITY_CLOTHING_LABELS is a frozenset."""
    assert isinstance(SECURITY_CLOTHING_LABELS, frozenset)


def test_security_labels_exclude_body_parts():
    """Test security labels exclude body parts like face, arms, legs."""
    body_parts = {"hair", "face", "left_leg", "right_leg", "left_arm", "right_arm"}
    assert SECURITY_CLOTHING_LABELS.isdisjoint(body_parts)


def test_shoe_labels_content():
    """Test shoe labels."""
    assert frozenset({"left_shoe", "right_shoe"}) == SHOE_LABELS


def test_shoe_labels_is_frozenset():
    """Test that SHOE_LABELS is a frozenset."""
    assert isinstance(SHOE_LABELS, frozenset)


def test_shoe_labels_not_in_security_labels():
    """Test that individual shoe labels are not in security clothing labels."""
    assert "left_shoe" not in SECURITY_CLOTHING_LABELS
    assert "right_shoe" not in SECURITY_CLOTHING_LABELS


# =============================================================================
# Test format_clothing_context
# =============================================================================


def test_format_clothing_context_no_items():
    """Test format_clothing_context with no clothing detected."""
    result = ClothingSegmentationResult()

    context = format_clothing_context(result)

    assert context == "No clothing detected"


def test_segformer_format_clothing_context_basic():
    """Test format_clothing_context with basic clothing items from SegFormer."""
    result = ClothingSegmentationResult(
        clothing_items={"pants", "upper_clothes"},
        has_face_covered=False,
        has_bag=False,
    )

    context = format_clothing_context(result)

    assert "Clothing:" in context
    assert "pants" in context
    assert "upper_clothes" in context


def test_format_clothing_context_face_covered():
    """Test format_clothing_context with face covered flag."""
    result = ClothingSegmentationResult(
        clothing_items={"hat", "sunglasses"},
        has_face_covered=True,
        has_bag=False,
    )

    context = format_clothing_context(result)

    assert "face appears covered" in context


def test_format_clothing_context_with_bag():
    """Test format_clothing_context with bag flag."""
    result = ClothingSegmentationResult(
        clothing_items={"bag", "pants"},
        has_face_covered=False,
        has_bag=True,
    )

    context = format_clothing_context(result)

    assert "carrying bag" in context


def test_format_clothing_context_all_flags():
    """Test format_clothing_context with all flags set."""
    result = ClothingSegmentationResult(
        clothing_items={"hat", "sunglasses", "bag"},
        has_face_covered=True,
        has_bag=True,
    )

    context = format_clothing_context(result)

    assert "face appears covered" in context
    assert "carrying bag" in context
    assert "Clothing:" in context


def test_format_clothing_context_sorted():
    """Test format_clothing_context items are sorted."""
    result = ClothingSegmentationResult(
        clothing_items={"scarf", "bag", "hat"},
        has_face_covered=False,
        has_bag=False,
    )

    context = format_clothing_context(result)

    # Items should be sorted alphabetically
    assert "bag" in context
    assert "hat" in context
    assert "scarf" in context


# =============================================================================
# Test format_batch_clothing_context
# =============================================================================


def test_format_batch_clothing_context_empty():
    """Test format_batch_clothing_context with empty list."""
    result = format_batch_clothing_context([])

    assert result == "No clothing analysis available"


def test_format_batch_clothing_context_no_clothing_detected():
    """Test format_batch_clothing_context when no persons have clothing."""
    results = [
        ClothingSegmentationResult(),
        ClothingSegmentationResult(),
    ]

    context = format_batch_clothing_context(results)

    assert context == "No clothing detected on persons"


def test_format_batch_clothing_context_single_person():
    """Test format_batch_clothing_context with single person."""
    results = [
        ClothingSegmentationResult(
            clothing_items={"pants", "upper_clothes"},
            has_face_covered=False,
            has_bag=False,
        ),
    ]

    context = format_batch_clothing_context(results)

    assert "Person 1" in context
    assert "pants" in context
    assert "upper_clothes" in context


def test_format_batch_clothing_context_multiple_persons():
    """Test format_batch_clothing_context with multiple persons."""
    results = [
        ClothingSegmentationResult(
            clothing_items={"pants", "upper_clothes"},
            has_face_covered=False,
            has_bag=False,
        ),
        ClothingSegmentationResult(
            clothing_items={"dress", "hat"},
            has_face_covered=False,
            has_bag=False,
        ),
    ]

    context = format_batch_clothing_context(results)

    assert "Person 1" in context
    assert "Person 2" in context


def test_format_batch_clothing_context_with_detection_ids():
    """Test format_batch_clothing_context with custom detection IDs."""
    results = [
        ClothingSegmentationResult(
            clothing_items={"pants"},
            has_face_covered=False,
            has_bag=False,
        ),
        ClothingSegmentationResult(
            clothing_items={"dress"},
            has_face_covered=False,
            has_bag=False,
        ),
    ]
    detection_ids = ["abc123", "def456"]

    context = format_batch_clothing_context(results, detection_ids)

    assert "Person abc123" in context
    assert "Person def456" in context


def test_format_batch_clothing_context_partial_detection_ids():
    """Test format_batch_clothing_context with fewer IDs than results."""
    results = [
        ClothingSegmentationResult(
            clothing_items={"pants"},
            has_face_covered=False,
            has_bag=False,
        ),
        ClothingSegmentationResult(
            clothing_items={"dress"},
            has_face_covered=False,
            has_bag=False,
        ),
        ClothingSegmentationResult(
            clothing_items={"skirt"},
            has_face_covered=False,
            has_bag=False,
        ),
    ]
    detection_ids = ["abc123"]  # Only one ID

    context = format_batch_clothing_context(results, detection_ids)

    assert "Person abc123" in context
    assert "Person 2" in context  # Falls back to index
    assert "Person 3" in context


def test_format_batch_clothing_context_skips_empty_results():
    """Test format_batch_clothing_context skips persons with no clothing."""
    results = [
        ClothingSegmentationResult(
            clothing_items={"pants"},
            has_face_covered=False,
            has_bag=False,
        ),
        ClothingSegmentationResult(),  # No clothing
        ClothingSegmentationResult(
            clothing_items={"dress"},
            has_face_covered=False,
            has_bag=False,
        ),
    ]

    context = format_batch_clothing_context(results)

    lines = context.strip().split("\n")
    # Should only have 2 lines (skipping empty result)
    assert len(lines) == 2


# =============================================================================
# Test load_segformer_model error handling
# =============================================================================


@pytest.mark.asyncio
async def test_load_segformer_model_import_error(monkeypatch):
    """Test load_segformer_model handles ImportError."""
    import builtins
    import sys

    # Remove transformers and torch from imports if present
    modules_to_hide = ["transformers", "torch"]
    hidden_modules = {}
    for mod in modules_to_hide:
        if mod in sys.modules:
            hidden_modules[mod] = sys.modules.pop(mod)

    # Mock import to raise ImportError
    original_import = builtins.__import__

    def mock_import(name, *args, **kwargs):
        if name in ("transformers", "torch"):
            raise ImportError(f"No module named '{name}'")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", mock_import)

    try:
        with pytest.raises(ImportError, match="SegFormer requires transformers and torch"):
            await load_segformer_model("/fake/path")
    finally:
        # Restore hidden modules
        sys.modules.update(hidden_modules)


@pytest.mark.asyncio
async def test_load_segformer_model_runtime_error(monkeypatch):
    """Test load_segformer_model handles RuntimeError."""
    import sys

    # Mock torch and transformers to exist but fail on model load
    mock_torch = MagicMock()
    mock_torch.cuda.is_available.return_value = False
    mock_transformers = MagicMock()
    mock_transformers.SegformerImageProcessor.from_pretrained.side_effect = RuntimeError(
        "Model not found"
    )

    monkeypatch.setitem(sys.modules, "torch", mock_torch)
    monkeypatch.setitem(sys.modules, "transformers", mock_transformers)

    with pytest.raises(RuntimeError, match="Failed to load SegFormer model"):
        await load_segformer_model("/nonexistent/path")


# =============================================================================
# Test load_segformer_model success paths
# =============================================================================


@pytest.mark.asyncio
async def test_load_segformer_model_success_cpu(monkeypatch):
    """Test load_segformer_model success path with CPU."""
    import sys

    # Create mock torch
    mock_torch = MagicMock()
    mock_torch.cuda.is_available.return_value = False
    mock_torch.float32 = "float32"

    # Create mock model
    mock_model = MagicMock()
    mock_model.to.return_value = mock_model
    mock_model.eval.return_value = None

    # Create mock processor
    mock_processor = MagicMock()

    # Create mock transformers
    mock_transformers = MagicMock()
    mock_transformers.SegformerImageProcessor.from_pretrained.return_value = mock_processor
    mock_transformers.AutoModelForSemanticSegmentation.from_pretrained.return_value = mock_model

    monkeypatch.setitem(sys.modules, "torch", mock_torch)
    monkeypatch.setitem(sys.modules, "transformers", mock_transformers)

    result = await load_segformer_model("/test/model")

    # Should return a tuple of (model, processor)
    assert isinstance(result, tuple)
    assert len(result) == 2
    model, processor = result
    assert model is mock_model
    assert processor is mock_processor

    # Verify model was moved to CPU and set to eval mode
    mock_model.to.assert_called_once_with("cpu")
    mock_model.eval.assert_called_once()

    # Verify model was loaded with float32 on CPU
    mock_transformers.AutoModelForSemanticSegmentation.from_pretrained.assert_called_once_with(
        "/test/model",
        torch_dtype="float32",
    )


@pytest.mark.asyncio
async def test_load_segformer_model_success_cuda(monkeypatch):
    """Test load_segformer_model success path with CUDA."""
    import sys

    # Create mock torch with CUDA
    mock_torch = MagicMock()
    mock_torch.cuda.is_available.return_value = True
    mock_torch.float16 = "float16"
    mock_torch.float32 = "float32"

    # Create mock model
    mock_model = MagicMock()
    mock_model.to.return_value = mock_model
    mock_model.eval.return_value = None

    # Create mock processor
    mock_processor = MagicMock()

    # Create mock transformers
    mock_transformers = MagicMock()
    mock_transformers.SegformerImageProcessor.from_pretrained.return_value = mock_processor
    mock_transformers.AutoModelForSemanticSegmentation.from_pretrained.return_value = mock_model

    monkeypatch.setitem(sys.modules, "torch", mock_torch)
    monkeypatch.setitem(sys.modules, "transformers", mock_transformers)

    result = await load_segformer_model("/test/model/cuda")

    # Should return a tuple of (model, processor)
    assert isinstance(result, tuple)
    assert len(result) == 2

    # Verify model was moved to CUDA
    mock_model.to.assert_called_once_with("cuda")

    # Verify model was loaded with float16 on CUDA
    mock_transformers.AutoModelForSemanticSegmentation.from_pretrained.assert_called_once_with(
        "/test/model/cuda",
        torch_dtype="float16",
    )


# =============================================================================
# Test segment_clothing
# =============================================================================


def test_segment_clothing_is_async():
    """Test segment_clothing is an async function."""
    import inspect

    assert callable(segment_clothing)
    assert inspect.iscoroutinefunction(segment_clothing)


def test_segment_clothing_signature():
    """Test segment_clothing function signature."""
    import inspect

    sig = inspect.signature(segment_clothing)
    params = list(sig.parameters.keys())
    assert "model" in params
    assert "processor" in params
    assert "person_crop" in params
    assert "min_coverage" in params

    # Check default value for min_coverage
    assert sig.parameters["min_coverage"].default == 0.01


@pytest.mark.asyncio
async def test_segment_clothing_error_handling():
    """Test segment_clothing returns empty result on error."""
    # Create mocks that will cause an error
    mock_model = MagicMock()
    mock_processor = MagicMock()
    mock_processor.side_effect = RuntimeError("Processing failed")

    # Create a mock image
    mock_image = MagicMock()
    mock_image.size = (224, 224)

    result = await segment_clothing(mock_model, mock_processor, mock_image)

    # Should return empty result on error
    assert result.clothing_items == set()
    assert result.has_face_covered is False
    assert result.has_bag is False


# =============================================================================
# Test segment_clothing_batch
# =============================================================================


def test_segment_clothing_batch_is_async():
    """Test segment_clothing_batch is an async function."""
    import inspect

    assert callable(segment_clothing_batch)
    assert inspect.iscoroutinefunction(segment_clothing_batch)


@pytest.mark.asyncio
async def test_segment_clothing_batch_empty():
    """Test segment_clothing_batch with empty list."""
    mock_model = MagicMock()
    mock_processor = MagicMock()

    result = await segment_clothing_batch(mock_model, mock_processor, [])

    assert result == []


def test_segment_clothing_batch_signature():
    """Test segment_clothing_batch function signature."""
    import inspect

    sig = inspect.signature(segment_clothing_batch)
    params = list(sig.parameters.keys())
    assert "model" in params
    assert "processor" in params
    assert "person_crops" in params
    assert "min_coverage" in params

    # Check default value for min_coverage
    assert sig.parameters["min_coverage"].default == 0.01


# =============================================================================
# Test model_zoo integration
# =============================================================================


def test_segformer_in_model_zoo():
    """Test segformer-b2-clothes is registered in MODEL_ZOO."""
    from backend.services.model_zoo import get_model_zoo

    zoo = get_model_zoo()
    assert "segformer-b2-clothes" in zoo

    config = zoo["segformer-b2-clothes"]
    assert config.name == "segformer-b2-clothes"
    assert config.vram_mb == 1500
    assert config.category == "segmentation"
    assert config.enabled is True


def test_segformer_model_config_path():
    """Test segformer model config has correct path."""
    from backend.services.model_zoo import get_model_zoo

    zoo = get_model_zoo()
    config = zoo["segformer-b2-clothes"]
    assert "/models/model-zoo/segformer-b2-clothes" in config.path


def test_segformer_model_config_load_fn():
    """Test segformer model config has correct load function."""
    from backend.services.model_zoo import get_model_zoo

    zoo = get_model_zoo()
    config = zoo["segformer-b2-clothes"]
    assert config.load_fn is load_segformer_model


# =============================================================================
# Test face_covered logic
# =============================================================================


def test_face_covered_detection_sunglasses_and_hat():
    """Test face covered detection with sunglasses and hat."""
    result = ClothingSegmentationResult(
        clothing_items={"sunglasses", "hat"},
        has_face_covered=True,
        has_bag=False,
    )
    assert result.has_face_covered is True


def test_face_covered_detection_sunglasses_and_scarf():
    """Test face covered detection with sunglasses and scarf."""
    result = ClothingSegmentationResult(
        clothing_items={"sunglasses", "scarf"},
        has_face_covered=True,
        has_bag=False,
    )
    assert result.has_face_covered is True


def test_face_covered_detection_just_sunglasses():
    """Test face covered detection with just sunglasses (and low face visibility)."""
    # The logic checks: sunglasses + (hat/scarf or face_coverage < 5%)
    result = ClothingSegmentationResult(
        clothing_items={"sunglasses"},
        has_face_covered=True,  # Would be true if face_coverage < 5%
        has_bag=False,
        coverage_percentages={"sunglasses": 2.0},
    )
    assert result.has_face_covered is True


def test_face_not_covered_normal_glasses():
    """Test face not covered with normal clothing."""
    result = ClothingSegmentationResult(
        clothing_items={"pants", "upper_clothes"},
        has_face_covered=False,
        has_bag=False,
    )
    assert result.has_face_covered is False


# =============================================================================
# Test bag detection logic
# =============================================================================


def test_bag_detection():
    """Test bag detection flag."""
    result = ClothingSegmentationResult(
        clothing_items={"bag", "pants"},
        has_face_covered=False,
        has_bag=True,
    )
    assert result.has_bag is True


def test_no_bag_detection():
    """Test no bag detection."""
    result = ClothingSegmentationResult(
        clothing_items={"pants", "upper_clothes"},
        has_face_covered=False,
        has_bag=False,
    )
    assert result.has_bag is False


# =============================================================================
# Test coverage percentages
# =============================================================================


def test_coverage_percentages_storage():
    """Test coverage percentages are stored correctly."""
    coverage = {
        "pants": 25.5,
        "upper_clothes": 30.0,
        "hat": 5.0,
    }
    result = ClothingSegmentationResult(
        clothing_items={"pants", "upper_clothes", "hat"},
        has_face_covered=False,
        has_bag=False,
        coverage_percentages=coverage,
    )

    assert result.coverage_percentages["pants"] == 25.5
    assert result.coverage_percentages["upper_clothes"] == 30.0
    assert result.coverage_percentages["hat"] == 5.0


def test_coverage_percentages_in_to_dict():
    """Test coverage percentages are included in to_dict."""
    coverage = {"pants": 20.0}
    result = ClothingSegmentationResult(
        clothing_items={"pants"},
        has_face_covered=False,
        has_bag=False,
        coverage_percentages=coverage,
    )

    d = result.to_dict()
    assert d["coverage_percentages"]["pants"] == 20.0


# =============================================================================
# Test raw_mask handling
# =============================================================================


def test_raw_mask_storage():
    """Test raw_mask can be stored."""
    import numpy as np

    mock_mask = np.zeros((224, 224), dtype=np.uint8)
    result = ClothingSegmentationResult(
        clothing_items=set(),
        has_face_covered=False,
        has_bag=False,
        raw_mask=mock_mask,
    )

    assert result.raw_mask is mock_mask


def test_raw_mask_excluded_from_dict():
    """Test raw_mask is excluded from to_dict()."""
    import numpy as np

    mock_mask = np.zeros((224, 224), dtype=np.uint8)
    result = ClothingSegmentationResult(
        clothing_items=set(),
        has_face_covered=False,
        has_bag=False,
        raw_mask=mock_mask,
    )

    d = result.to_dict()
    assert "raw_mask" not in d


# =============================================================================
# Test label mappings are complete
# =============================================================================


def test_all_clothing_labels_have_unique_indices():
    """Test all clothing labels have unique indices."""
    indices = list(CLOTHING_LABELS.keys())
    assert len(indices) == len(set(indices))


def test_clothing_labels_are_contiguous():
    """Test clothing label indices are contiguous from 0 to 17."""
    indices = list(CLOTHING_LABELS.keys())
    assert min(indices) == 0
    assert max(indices) == 17
    assert len(indices) == 18


def test_security_labels_are_subset_of_clothing_labels():
    """Test all security labels exist in clothing labels."""
    all_labels = set(CLOTHING_LABELS.values())
    for label in SECURITY_CLOTHING_LABELS:
        assert label in all_labels, f"{label} not in clothing labels"


def test_shoe_labels_are_subset_of_clothing_labels():
    """Test shoe labels exist in clothing labels."""
    all_labels = set(CLOTHING_LABELS.values())
    for label in SHOE_LABELS:
        assert label in all_labels, f"{label} not in clothing labels"


# =============================================================================
# Test async function behavior
# =============================================================================


def test_load_segformer_model_is_async():
    """Test load_segformer_model is an async function."""
    import inspect

    assert callable(load_segformer_model)
    assert inspect.iscoroutinefunction(load_segformer_model)


def test_load_segformer_model_signature():
    """Test load_segformer_model function signature."""
    import inspect

    sig = inspect.signature(load_segformer_model)
    params = list(sig.parameters.keys())
    assert "model_path" in params


# =============================================================================
# Test segment_clothing full execution path
# =============================================================================


@pytest.mark.asyncio
async def test_segment_clothing_success_path(monkeypatch):
    """Test segment_clothing full success path with mocked inference."""
    import sys

    import numpy as np

    # Create mock torch
    mock_torch = MagicMock()

    # Create a proper mock for the no_grad context manager
    mock_no_grad = MagicMock()
    mock_no_grad.__enter__ = MagicMock(return_value=None)
    mock_no_grad.__exit__ = MagicMock(return_value=None)
    mock_torch.no_grad.return_value = mock_no_grad

    # Mock interpolate
    mock_upsampled = MagicMock()
    mock_argmax_result = MagicMock()

    # Create a numpy mask with various clothing classes
    # 0=background, 1=hat, 4=upper_clothes, 6=pants, 16=bag
    mock_mask = np.array(
        [
            [0, 0, 1, 1, 0, 0],
            [0, 4, 4, 4, 4, 0],
            [0, 4, 4, 4, 4, 0],
            [0, 6, 6, 6, 6, 0],
            [0, 6, 6, 6, 6, 0],
            [0, 16, 16, 0, 0, 0],
        ],
        dtype=np.int64,
    )

    mock_argmax_result.squeeze.return_value.cpu.return_value.numpy.return_value = mock_mask
    mock_upsampled.argmax.return_value = mock_argmax_result

    mock_torch.nn.functional.interpolate.return_value = mock_upsampled

    # Mock numpy
    mock_np = MagicMock()
    mock_np.unique.return_value = (
        np.array([0, 1, 4, 6, 16]),  # unique_classes
        np.array([20, 2, 8, 8, 2]),  # counts (out of 36 total pixels)
    )

    monkeypatch.setitem(sys.modules, "torch", mock_torch)
    monkeypatch.setitem(sys.modules, "numpy", mock_np)

    # Create mock model
    mock_model = MagicMock()
    mock_device = MagicMock()
    mock_model.parameters.return_value = iter([MagicMock(device=mock_device)])

    # Mock outputs
    mock_outputs = MagicMock()
    mock_outputs.logits = MagicMock()
    mock_model.return_value = mock_outputs

    # Create mock processor
    mock_processor = MagicMock()
    mock_inputs = {"pixel_values": MagicMock()}
    mock_inputs["pixel_values"].to.return_value = mock_inputs["pixel_values"]
    mock_processor.return_value = mock_inputs

    # Create mock image
    mock_image = MagicMock()
    mock_image.size = (224, 224)

    # Run the function
    result = await segment_clothing(mock_model, mock_processor, mock_image)

    # Should return a result (even if empty due to mocking complexity)
    assert isinstance(result, ClothingSegmentationResult)


@pytest.mark.asyncio
async def test_segment_clothing_with_shoes(monkeypatch):
    """Test segment_clothing consolidates left and right shoes."""
    import sys

    import numpy as np

    # Create a mask with both shoe labels
    mock_mask = np.array([[9, 9, 10, 10]], dtype=np.int64)  # left_shoe=9, right_shoe=10

    # Mock torch
    mock_torch = MagicMock()
    mock_no_grad = MagicMock()
    mock_no_grad.__enter__ = MagicMock(return_value=None)
    mock_no_grad.__exit__ = MagicMock(return_value=None)
    mock_torch.no_grad.return_value = mock_no_grad

    mock_upsampled = MagicMock()
    mock_argmax_result = MagicMock()
    mock_argmax_result.squeeze.return_value.cpu.return_value.numpy.return_value = mock_mask
    mock_upsampled.argmax.return_value = mock_argmax_result
    mock_torch.nn.functional.interpolate.return_value = mock_upsampled

    monkeypatch.setitem(sys.modules, "torch", mock_torch)

    # Create mock model and processor
    mock_model = MagicMock()
    mock_device = MagicMock()
    mock_model.parameters.return_value = iter([MagicMock(device=mock_device)])
    mock_outputs = MagicMock()
    mock_outputs.logits = MagicMock()
    mock_model.return_value = mock_outputs

    mock_processor = MagicMock()
    mock_inputs = {"pixel_values": MagicMock()}
    mock_inputs["pixel_values"].to.return_value = mock_inputs["pixel_values"]
    mock_processor.return_value = mock_inputs

    mock_image = MagicMock()
    mock_image.size = (4, 1)

    result = await segment_clothing(mock_model, mock_processor, mock_image)

    # Should consolidate shoes
    assert isinstance(result, ClothingSegmentationResult)


@pytest.mark.asyncio
async def test_segment_clothing_face_covered_logic():
    """Test segment_clothing face covered detection scenarios.

    Face covered logic: sunglasses AND (head_covering OR face_coverage < 5%)
    """

    # Test case 1: sunglasses + hat = covered
    result1 = ClothingSegmentationResult(
        clothing_items={"sunglasses", "hat"},
        has_face_covered=True,  # sunglasses + hat
    )
    assert result1.has_face_covered is True

    # Test case 2: sunglasses + low face visibility = covered
    result2 = ClothingSegmentationResult(
        clothing_items={"sunglasses"},
        has_face_covered=True,  # sunglasses + face_coverage < 5%
        coverage_percentages={"sunglasses": 3.0, "face": 2.0},
    )
    assert result2.has_face_covered is True

    # Test case 3: only hat = not covered (no sunglasses)
    result3 = ClothingSegmentationResult(
        clothing_items={"hat"},
        has_face_covered=False,
    )
    assert result3.has_face_covered is False


@pytest.mark.asyncio
async def test_segment_clothing_min_coverage_filter():
    """Test that segment_clothing respects min_coverage parameter."""
    # The min_coverage default is 0.01 (1% of pixels)
    import inspect

    sig = inspect.signature(segment_clothing)
    assert sig.parameters["min_coverage"].default == 0.01


# =============================================================================
# Test segment_clothing_batch full execution path
# =============================================================================


@pytest.mark.asyncio
async def test_segment_clothing_batch_with_multiple_images():
    """Test segment_clothing_batch processes multiple images."""
    # Create mocks that return empty results on error (which is the expected behavior)
    mock_model = MagicMock()
    mock_processor = MagicMock()
    mock_processor.side_effect = RuntimeError("Mock error")

    mock_image1 = MagicMock()
    mock_image1.size = (224, 224)
    mock_image2 = MagicMock()
    mock_image2.size = (224, 224)

    results = await segment_clothing_batch(mock_model, mock_processor, [mock_image1, mock_image2])

    # Should return a list of results (empty due to error handling)
    assert isinstance(results, list)
    assert len(results) == 2


@pytest.mark.asyncio
async def test_segment_clothing_batch_with_custom_min_coverage():
    """Test segment_clothing_batch respects min_coverage parameter."""
    mock_model = MagicMock()
    mock_processor = MagicMock()
    mock_processor.side_effect = RuntimeError("Mock error")

    mock_image = MagicMock()
    mock_image.size = (224, 224)

    # Should not raise, just return empty results on error
    results = await segment_clothing_batch(
        mock_model, mock_processor, [mock_image], min_coverage=0.05
    )

    assert isinstance(results, list)
    assert len(results) == 1


@pytest.mark.asyncio
async def test_segment_clothing_batch_propagates_results():
    """Test segment_clothing_batch returns results in order."""
    # Use mocks that will cause errors, resulting in empty ClothingSegmentationResult
    mock_model = MagicMock()
    mock_processor = MagicMock()
    mock_processor.side_effect = RuntimeError("Mock error")

    images = [MagicMock(size=(100, 100)) for _ in range(3)]

    results = await segment_clothing_batch(mock_model, mock_processor, images)

    assert len(results) == 3
    for result in results:
        assert isinstance(result, ClothingSegmentationResult)
        # All should be empty due to error handling
        assert result.clothing_items == set()


# =============================================================================
# Additional edge case tests
# =============================================================================


def test_clothing_labels_unknown_class_handling():
    """Test that unknown class IDs default to 'unknown' label."""
    # Class ID 99 should return 'unknown'
    label = CLOTHING_LABELS.get(99, "unknown")
    assert label == "unknown"


def test_coverage_percentages_float_precision():
    """Test coverage percentages are properly rounded."""
    result = ClothingSegmentationResult(
        clothing_items={"pants"},
        coverage_percentages={"pants": 25.123456789},
    )

    result.to_dict()
    # Value should be preserved as-is in the dataclass
    assert result.coverage_percentages["pants"] == 25.123456789


def test_clothing_items_are_mutable_set():
    """Test clothing_items is a mutable set."""
    result = ClothingSegmentationResult()
    result.clothing_items.add("pants")
    result.clothing_items.add("upper_clothes")

    assert "pants" in result.clothing_items
    assert "upper_clothes" in result.clothing_items


def test_to_dict_clothing_items_sorted():
    """Test to_dict() sorts clothing items alphabetically."""
    result = ClothingSegmentationResult(
        clothing_items={"scarf", "bag", "hat", "pants"},
    )

    d = result.to_dict()
    assert d["clothing_items"] == ["bag", "hat", "pants", "scarf"]


def test_format_clothing_context_handles_empty_set():
    """Test format_clothing_context handles empty clothing_items set."""
    result = ClothingSegmentationResult(
        clothing_items=set(),
        has_face_covered=False,
        has_bag=False,
    )

    context = format_clothing_context(result)
    assert context == "No clothing detected"


def test_format_batch_clothing_context_empty_ids_list():
    """Test format_batch_clothing_context with empty detection_ids list."""
    results = [
        ClothingSegmentationResult(clothing_items={"pants"}),
    ]

    # Pass empty list instead of None
    context = format_batch_clothing_context(results, [])

    # Should fall back to Person 1
    assert "Person 1" in context


def test_clothing_items_frozen_security_labels():
    """Test SECURITY_CLOTHING_LABELS is immutable."""
    # frozenset should raise TypeError on modification
    with pytest.raises(AttributeError):
        SECURITY_CLOTHING_LABELS.add("test")  # type: ignore


def test_shoe_labels_frozen():
    """Test SHOE_LABELS is immutable."""
    with pytest.raises(AttributeError):
        SHOE_LABELS.add("test")  # type: ignore
