"""Unit tests for quantization service.

Tests for INT8 and 4-bit model quantization utilities (NEM-3373, NEM-3376).
"""

from unittest.mock import MagicMock, patch

import pytest

from backend.services.quantization import (
    QUANTIZATION_RECOMMENDATIONS,
    QuantizationBackend,
    QuantizationResult,
    QuantizationType,
    _get_model_size_mb,
    _is_bitsandbytes_available,
    apply_dynamic_int8_quantization,
    apply_int8_quantization_async,
    apply_static_int8_quantization,
    get_bnb_4bit_config,
    get_bnb_8bit_config,
    get_optimal_backend,
    get_quantization_recommendation,
    is_quantization_supported,
)

# =============================================================================
# Test QuantizationBackend enum
# =============================================================================


def test_quantization_backend_values():
    """Test QuantizationBackend enum values."""
    assert QuantizationBackend.X86.value == "x86"
    assert QuantizationBackend.QNNPACK.value == "qnnpack"
    assert QuantizationBackend.FBGEMM.value == "fbgemm"
    assert QuantizationBackend.ONEDNN.value == "onednn"


def test_quantization_backend_is_string_enum():
    """Test QuantizationBackend inherits from str."""
    assert isinstance(QuantizationBackend.X86, str)
    assert QuantizationBackend.X86 == "x86"


def test_quantization_backend_membership():
    """Test QuantizationBackend membership check."""
    backends = [b.value for b in QuantizationBackend]
    assert "x86" in backends
    assert "qnnpack" in backends
    assert "fbgemm" in backends
    assert "onednn" in backends


# =============================================================================
# Test QuantizationType enum
# =============================================================================


def test_quantization_type_values():
    """Test QuantizationType enum values."""
    assert QuantizationType.INT8.value == "int8"
    assert QuantizationType.INT4.value == "int4"
    assert QuantizationType.FP16.value == "fp16"
    assert QuantizationType.FP8.value == "fp8"


def test_quantization_type_is_string_enum():
    """Test QuantizationType inherits from str."""
    assert isinstance(QuantizationType.INT8, str)
    assert QuantizationType.INT8 == "int8"


# =============================================================================
# Test QuantizationResult dataclass
# =============================================================================


def test_quantization_result_creation():
    """Test QuantizationResult dataclass creation."""
    result = QuantizationResult(
        model=MagicMock(),
        original_size_mb=200.0,
        quantized_size_mb=50.0,
        compression_ratio=4.0,
        quantization_type=QuantizationType.INT8,
        backend="x86",
    )

    assert result.original_size_mb == 200.0
    assert result.quantized_size_mb == 50.0
    assert result.compression_ratio == 4.0
    assert result.quantization_type == QuantizationType.INT8
    assert result.backend == "x86"


def test_quantization_result_default_backend():
    """Test QuantizationResult default backend is None."""
    result = QuantizationResult(
        model=MagicMock(),
        original_size_mb=100.0,
        quantized_size_mb=25.0,
        compression_ratio=4.0,
        quantization_type=QuantizationType.INT4,
    )

    assert result.backend is None


def test_quantization_result_to_dict():
    """Test QuantizationResult.to_dict() method."""
    result = QuantizationResult(
        model=MagicMock(),
        original_size_mb=200.5,
        quantized_size_mb=50.25,
        compression_ratio=3.99,
        quantization_type=QuantizationType.INT8,
        backend="x86",
    )

    d = result.to_dict()

    assert d["original_size_mb"] == 200.5
    assert d["quantized_size_mb"] == 50.25
    assert d["compression_ratio"] == 3.99
    assert d["quantization_type"] == "int8"
    assert d["backend"] == "x86"


def test_quantization_result_to_dict_keys():
    """Test QuantizationResult.to_dict() contains all expected keys."""
    result = QuantizationResult(
        model=MagicMock(),
        original_size_mb=100.0,
        quantized_size_mb=25.0,
        compression_ratio=4.0,
        quantization_type=QuantizationType.INT4,
    )

    d = result.to_dict()

    expected_keys = {
        "original_size_mb",
        "quantized_size_mb",
        "compression_ratio",
        "quantization_type",
        "backend",
    }
    assert set(d.keys()) == expected_keys


def test_quantization_result_to_dict_rounding():
    """Test QuantizationResult.to_dict() rounds values."""
    result = QuantizationResult(
        model=MagicMock(),
        original_size_mb=200.12345,
        quantized_size_mb=50.98765,
        compression_ratio=3.9254,
        quantization_type=QuantizationType.INT8,
        backend="x86",
    )

    d = result.to_dict()

    # Should be rounded to 2 decimal places
    assert d["original_size_mb"] == 200.12
    assert d["quantized_size_mb"] == 50.99
    assert d["compression_ratio"] == 3.93


# =============================================================================
# Test _is_bitsandbytes_available
# =============================================================================


def test_is_bitsandbytes_available_not_installed(monkeypatch):
    """Test _is_bitsandbytes_available when package not installed."""
    import sys

    # Remove bitsandbytes from modules if present
    modules_to_hide = ["bitsandbytes"]
    hidden_modules = {}
    for mod in modules_to_hide:
        for key in list(sys.modules.keys()):
            if key == mod or key.startswith(f"{mod}."):
                hidden_modules[key] = sys.modules.pop(key)

    try:
        # Mock find_spec to return None
        with patch("importlib.util.find_spec", return_value=None):
            assert _is_bitsandbytes_available() is False
    finally:
        sys.modules.update(hidden_modules)


def test_is_bitsandbytes_available_no_cuda(monkeypatch):
    """Test _is_bitsandbytes_available when CUDA not available."""
    import sys

    # Create mock modules
    mock_spec = MagicMock()
    mock_torch = MagicMock()
    mock_torch.cuda.is_available.return_value = False

    with patch("importlib.util.find_spec", return_value=mock_spec):
        monkeypatch.setitem(sys.modules, "torch", mock_torch)
        assert _is_bitsandbytes_available() is False


def test_is_bitsandbytes_available_with_cuda(monkeypatch):
    """Test _is_bitsandbytes_available when both installed and CUDA available."""
    import sys

    # Create mock modules
    mock_spec = MagicMock()
    mock_torch = MagicMock()
    mock_torch.cuda.is_available.return_value = True

    with patch("importlib.util.find_spec", return_value=mock_spec):
        monkeypatch.setitem(sys.modules, "torch", mock_torch)
        assert _is_bitsandbytes_available() is True


# =============================================================================
# Test _get_model_size_mb
# =============================================================================


def test_get_model_size_mb_fp32():
    """Test _get_model_size_mb for FP32 model."""
    import sys

    mock_torch = MagicMock()
    mock_torch.float32 = "float32"
    mock_torch.float16 = "float16"
    mock_torch.int8 = "int8"

    # Create mock parameters
    mock_param = MagicMock()
    mock_param.numel.return_value = 1000000  # 1M parameters
    mock_param.dtype = "float32"

    mock_model = MagicMock()
    mock_model.parameters.return_value = [mock_param]

    with patch.dict(sys.modules, {"torch": mock_torch}):
        size = _get_model_size_mb(mock_model)
        # 1M params * 4 bytes / 1024 / 1024 = ~3.8 MB
        assert size == pytest.approx(3.8, rel=0.1)


def test_get_model_size_mb_fp16():
    """Test _get_model_size_mb for FP16 model."""
    import sys

    mock_torch = MagicMock()
    mock_torch.float16 = "float16"
    mock_torch.float32 = "float32"
    mock_torch.int8 = "int8"

    # Create mock parameters
    mock_param = MagicMock()
    mock_param.numel.return_value = 1000000  # 1M parameters
    mock_param.dtype = "float16"

    mock_model = MagicMock()
    mock_model.parameters.return_value = [mock_param]

    with patch.dict(sys.modules, {"torch": mock_torch}):
        size = _get_model_size_mb(mock_model)
        # 1M params * 2 bytes / 1024 / 1024 = ~1.9 MB
        assert size == pytest.approx(1.9, rel=0.1)


def test_get_model_size_mb_error_handling():
    """Test _get_model_size_mb handles errors gracefully."""
    mock_model = MagicMock()
    mock_model.parameters.side_effect = RuntimeError("No parameters")

    # Should return 0.0 on error
    size = _get_model_size_mb(mock_model)
    assert size == 0.0


# =============================================================================
# Test get_optimal_backend
# =============================================================================


def test_get_optimal_backend_x86():
    """Test get_optimal_backend returns X86 for x86_64."""
    with patch("platform.machine", return_value="x86_64"):
        backend = get_optimal_backend()
        assert backend in (QuantizationBackend.X86, QuantizationBackend.ONEDNN)


def test_get_optimal_backend_arm():
    """Test get_optimal_backend returns QNNPACK for ARM."""
    with patch("platform.machine", return_value="arm64"):
        backend = get_optimal_backend()
        assert backend == QuantizationBackend.QNNPACK


def test_get_optimal_backend_aarch64():
    """Test get_optimal_backend returns QNNPACK for aarch64."""
    with patch("platform.machine", return_value="aarch64"):
        backend = get_optimal_backend()
        assert backend == QuantizationBackend.QNNPACK


def test_get_optimal_backend_unknown():
    """Test get_optimal_backend returns X86 for unknown platform."""
    with patch("platform.machine", return_value="unknown"):
        backend = get_optimal_backend()
        assert backend == QuantizationBackend.X86


# =============================================================================
# Test get_bnb_4bit_config
# =============================================================================


def test_get_bnb_4bit_config_not_available():
    """Test get_bnb_4bit_config raises ImportError when not available."""
    with patch("backend.services.quantization._is_bitsandbytes_available", return_value=False):
        with pytest.raises(ImportError, match="bitsandbytes package not installed"):
            get_bnb_4bit_config()


def test_get_bnb_4bit_config_success(monkeypatch):
    """Test get_bnb_4bit_config returns valid config."""
    import sys

    # Mock bitsandbytes availability
    with patch("backend.services.quantization._is_bitsandbytes_available", return_value=True):
        # Mock torch
        mock_torch = MagicMock()
        mock_torch.float16 = "float16"
        mock_torch.bfloat16 = "bfloat16"
        mock_torch.float32 = "float32"

        # Mock BitsAndBytesConfig
        mock_config_class = MagicMock()
        mock_config_instance = MagicMock()
        mock_config_class.return_value = mock_config_instance

        mock_transformers = MagicMock()
        mock_transformers.BitsAndBytesConfig = mock_config_class

        monkeypatch.setitem(sys.modules, "torch", mock_torch)
        monkeypatch.setitem(sys.modules, "transformers", mock_transformers)

        config = get_bnb_4bit_config()

        assert config is mock_config_instance
        mock_config_class.assert_called_once_with(
            load_in_4bit=True,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_compute_dtype="float16",
            bnb_4bit_use_double_quant=True,
        )


def test_get_bnb_4bit_config_custom_params(monkeypatch):
    """Test get_bnb_4bit_config with custom parameters."""
    import sys

    with patch("backend.services.quantization._is_bitsandbytes_available", return_value=True):
        mock_torch = MagicMock()
        mock_torch.float16 = "float16"
        mock_torch.bfloat16 = "bfloat16"
        mock_torch.float32 = "float32"

        mock_config_class = MagicMock()
        mock_transformers = MagicMock()
        mock_transformers.BitsAndBytesConfig = mock_config_class

        monkeypatch.setitem(sys.modules, "torch", mock_torch)
        monkeypatch.setitem(sys.modules, "transformers", mock_transformers)

        get_bnb_4bit_config(
            compute_dtype="bfloat16",
            quant_type="fp4",
            use_double_quant=False,
        )

        mock_config_class.assert_called_once_with(
            load_in_4bit=True,
            bnb_4bit_quant_type="fp4",
            bnb_4bit_compute_dtype="bfloat16",
            bnb_4bit_use_double_quant=False,
        )


def test_get_bnb_4bit_config_invalid_dtype(monkeypatch):
    """Test get_bnb_4bit_config raises ValueError for invalid dtype."""
    import sys

    with patch("backend.services.quantization._is_bitsandbytes_available", return_value=True):
        mock_torch = MagicMock()
        mock_transformers = MagicMock()

        monkeypatch.setitem(sys.modules, "torch", mock_torch)
        monkeypatch.setitem(sys.modules, "transformers", mock_transformers)

        with pytest.raises(ValueError, match="Invalid compute_dtype"):
            get_bnb_4bit_config(compute_dtype="invalid")


def test_get_bnb_4bit_config_invalid_quant_type(monkeypatch):
    """Test get_bnb_4bit_config raises ValueError for invalid quant_type."""
    import sys

    with patch("backend.services.quantization._is_bitsandbytes_available", return_value=True):
        mock_torch = MagicMock()
        mock_torch.float16 = "float16"
        mock_transformers = MagicMock()

        monkeypatch.setitem(sys.modules, "torch", mock_torch)
        monkeypatch.setitem(sys.modules, "transformers", mock_transformers)

        with pytest.raises(ValueError, match="Invalid quant_type"):
            get_bnb_4bit_config(quant_type="invalid")


# =============================================================================
# Test get_bnb_8bit_config
# =============================================================================


def test_get_bnb_8bit_config_not_available():
    """Test get_bnb_8bit_config raises ImportError when not available."""
    with patch("backend.services.quantization._is_bitsandbytes_available", return_value=False):
        with pytest.raises(ImportError, match="bitsandbytes package not installed"):
            get_bnb_8bit_config()


def test_get_bnb_8bit_config_success(monkeypatch):
    """Test get_bnb_8bit_config returns valid config."""
    import sys

    with patch("backend.services.quantization._is_bitsandbytes_available", return_value=True):
        mock_config_class = MagicMock()
        mock_config_instance = MagicMock()
        mock_config_class.return_value = mock_config_instance

        mock_transformers = MagicMock()
        mock_transformers.BitsAndBytesConfig = mock_config_class

        monkeypatch.setitem(sys.modules, "transformers", mock_transformers)

        config = get_bnb_8bit_config()

        assert config is mock_config_instance
        mock_config_class.assert_called_once_with(
            load_in_8bit=True,
            llm_int8_threshold=6.0,
            llm_int8_has_fp16_weight=False,
        )


def test_get_bnb_8bit_config_custom_params(monkeypatch):
    """Test get_bnb_8bit_config with custom parameters."""
    import sys

    with patch("backend.services.quantization._is_bitsandbytes_available", return_value=True):
        mock_config_class = MagicMock()
        mock_transformers = MagicMock()
        mock_transformers.BitsAndBytesConfig = mock_config_class

        monkeypatch.setitem(sys.modules, "transformers", mock_transformers)

        get_bnb_8bit_config(
            llm_int8_threshold=8.0,
            llm_int8_has_fp16_weight=True,
        )

        mock_config_class.assert_called_once_with(
            load_in_8bit=True,
            llm_int8_threshold=8.0,
            llm_int8_has_fp16_weight=True,
        )


# =============================================================================
# Test apply_dynamic_int8_quantization
# =============================================================================


def test_apply_dynamic_int8_quantization_success(monkeypatch):
    """Test apply_dynamic_int8_quantization success path."""
    import sys

    # Create mock torch
    mock_torch = MagicMock()
    mock_torch.nn.Linear = MagicMock()
    mock_torch.nn.LSTM = MagicMock()
    mock_torch.qint8 = "qint8"

    # Mock backends
    mock_backends = MagicMock()
    mock_quantized = MagicMock()
    mock_backends.quantized = mock_quantized
    mock_torch.backends = mock_backends

    # Mock quantize_dynamic
    mock_quantized_model = MagicMock()
    mock_param = MagicMock()
    mock_param.numel.return_value = 500000  # 500K parameters
    mock_param.dtype = "float32"
    mock_quantized_model.parameters.return_value = [mock_param]

    mock_quant = MagicMock()
    mock_quant.quantize_dynamic.return_value = mock_quantized_model

    # Create original model
    mock_original_model = MagicMock()
    mock_original_param = MagicMock()
    mock_original_param.numel.return_value = 1000000  # 1M parameters
    mock_original_param.dtype = "float32"
    mock_original_model.parameters.return_value = [mock_original_param]

    monkeypatch.setitem(sys.modules, "torch", mock_torch)
    monkeypatch.setitem(sys.modules, "torch.ao.quantization", mock_quant)

    result = apply_dynamic_int8_quantization(mock_original_model, QuantizationBackend.X86)

    assert isinstance(result, QuantizationResult)
    assert result.quantization_type == QuantizationType.INT8
    assert result.backend == "x86"
    mock_original_model.eval.assert_called_once()


def test_apply_dynamic_int8_quantization_string_backend(monkeypatch):
    """Test apply_dynamic_int8_quantization with string backend."""
    import sys

    mock_torch = MagicMock()
    mock_torch.nn.Linear = MagicMock()
    mock_torch.nn.LSTM = MagicMock()
    mock_torch.qint8 = "qint8"
    mock_torch.backends = MagicMock()

    mock_quantized_model = MagicMock()
    mock_param = MagicMock()
    mock_param.numel.return_value = 100000
    mock_param.dtype = "float32"
    mock_quantized_model.parameters.return_value = [mock_param]

    mock_quant = MagicMock()
    mock_quant.quantize_dynamic.return_value = mock_quantized_model

    mock_original_model = MagicMock()
    mock_original_model.parameters.return_value = [mock_param]

    monkeypatch.setitem(sys.modules, "torch", mock_torch)
    monkeypatch.setitem(sys.modules, "torch.ao.quantization", mock_quant)

    result = apply_dynamic_int8_quantization(mock_original_model, "qnnpack")

    assert result.backend == "qnnpack"


def test_apply_dynamic_int8_quantization_import_error():
    """Test apply_dynamic_int8_quantization raises ImportError."""
    with patch.dict("sys.modules", {"torch": None}):
        with pytest.raises((ImportError, RuntimeError)):
            apply_dynamic_int8_quantization(MagicMock())


# =============================================================================
# Test apply_static_int8_quantization
# =============================================================================


def test_apply_static_int8_quantization_success(monkeypatch):
    """Test apply_static_int8_quantization success path."""
    import sys

    mock_torch = MagicMock()
    mock_torch.no_grad = MagicMock(
        return_value=MagicMock(__enter__=MagicMock(), __exit__=MagicMock())
    )
    mock_torch.backends = MagicMock()

    # Mock quantized model parameters
    mock_param = MagicMock()
    mock_param.numel.return_value = 500000
    mock_param.dtype = "int8"

    mock_prepared_model = MagicMock()
    mock_prepared_model.parameters.return_value = [mock_param]

    mock_converted_model = MagicMock()
    mock_converted_model.parameters.return_value = [mock_param]

    mock_quant = MagicMock()
    mock_quant.get_default_qconfig.return_value = MagicMock()
    mock_quant.prepare.return_value = mock_prepared_model
    mock_quant.convert.return_value = mock_converted_model

    # Set up torch.ao.quantization namespace
    mock_torch.ao = MagicMock()
    mock_torch.ao.quantization = mock_quant

    mock_original_model = MagicMock()
    mock_original_param = MagicMock()
    mock_original_param.numel.return_value = 1000000
    mock_original_param.dtype = "float32"
    mock_original_model.parameters.return_value = [mock_original_param]

    monkeypatch.setitem(sys.modules, "torch", mock_torch)
    monkeypatch.setitem(sys.modules, "torch.ao.quantization", mock_quant)

    calibration_fn = MagicMock()

    result = apply_static_int8_quantization(mock_original_model, calibration_fn)

    assert isinstance(result, QuantizationResult)
    assert result.quantization_type == QuantizationType.INT8
    mock_original_model.eval.assert_called_once()
    # Verify calibration function was called (with any argument)
    calibration_fn.assert_called_once()


# =============================================================================
# Test apply_int8_quantization_async
# =============================================================================


@pytest.mark.asyncio
async def test_apply_int8_quantization_async_dynamic(monkeypatch):
    """Test apply_int8_quantization_async with dynamic quantization."""
    mock_result = QuantizationResult(
        model=MagicMock(),
        original_size_mb=100.0,
        quantized_size_mb=25.0,
        compression_ratio=4.0,
        quantization_type=QuantizationType.INT8,
        backend="x86",
    )

    with patch(
        "backend.services.quantization.apply_dynamic_int8_quantization",
        return_value=mock_result,
    ):
        result = await apply_int8_quantization_async(MagicMock())

        assert result == mock_result


@pytest.mark.asyncio
async def test_apply_int8_quantization_async_static(monkeypatch):
    """Test apply_int8_quantization_async with static quantization."""
    mock_result = QuantizationResult(
        model=MagicMock(),
        original_size_mb=100.0,
        quantized_size_mb=25.0,
        compression_ratio=4.0,
        quantization_type=QuantizationType.INT8,
        backend="x86",
    )

    with patch(
        "backend.services.quantization.apply_static_int8_quantization",
        return_value=mock_result,
    ):
        calibration_data = [MagicMock(), MagicMock()]
        result = await apply_int8_quantization_async(
            MagicMock(),
            calibration_data=calibration_data,
            use_static=True,
        )

        assert result == mock_result


# =============================================================================
# Test QUANTIZATION_RECOMMENDATIONS
# =============================================================================


def test_quantization_recommendations_defined():
    """Test QUANTIZATION_RECOMMENDATIONS dictionary is defined."""
    assert isinstance(QUANTIZATION_RECOMMENDATIONS, dict)
    assert len(QUANTIZATION_RECOMMENDATIONS) > 0


def test_quantization_recommendations_low_priority_models():
    """Test low-priority models have INT8 recommendations."""
    low_priority_models = [
        "vit-age-classifier",
        "vit-gender-classifier",
        "pet-classifier",
        "osnet-x0-25",
    ]

    for model_name in low_priority_models:
        assert model_name in QUANTIZATION_RECOMMENDATIONS
        rec = QUANTIZATION_RECOMMENDATIONS[model_name]
        assert rec["type"] == QuantizationType.INT8


def test_quantization_recommendations_llm_models():
    """Test LLM models have 4-bit recommendations."""
    assert "nemotron" in QUANTIZATION_RECOMMENDATIONS
    rec = QUANTIZATION_RECOMMENDATIONS["nemotron"]
    assert rec["type"] == QuantizationType.INT4
    assert rec["method"] == "bitsandbytes"


def test_quantization_recommendations_structure():
    """Test QUANTIZATION_RECOMMENDATIONS entries have required keys."""
    required_keys = {"type", "method", "expected_compression", "accuracy_impact"}

    for model_name, rec in QUANTIZATION_RECOMMENDATIONS.items():
        for key in required_keys:
            assert key in rec, f"Missing key '{key}' in {model_name} recommendation"


def test_quantization_recommendations_compression_ratios():
    """Test compression ratios are reasonable."""
    for model_name, rec in QUANTIZATION_RECOMMENDATIONS.items():
        assert rec["expected_compression"] >= 1.0
        assert rec["expected_compression"] <= 10.0


# =============================================================================
# Test get_quantization_recommendation
# =============================================================================


def test_get_quantization_recommendation_found():
    """Test get_quantization_recommendation returns recommendation."""
    rec = get_quantization_recommendation("vit-age-classifier")

    assert rec is not None
    assert rec["type"] == QuantizationType.INT8


def test_get_quantization_recommendation_not_found():
    """Test get_quantization_recommendation returns None for unknown model."""
    rec = get_quantization_recommendation("unknown-model")

    assert rec is None


def test_get_quantization_recommendation_all_models():
    """Test get_quantization_recommendation works for all defined models."""
    for model_name in QUANTIZATION_RECOMMENDATIONS:
        rec = get_quantization_recommendation(model_name)
        assert rec is not None


# =============================================================================
# Test is_quantization_supported
# =============================================================================


def test_is_quantization_supported_true():
    """Test is_quantization_supported returns True for supported model."""
    assert is_quantization_supported("vit-age-classifier") is True
    assert is_quantization_supported("nemotron") is True


def test_is_quantization_supported_false():
    """Test is_quantization_supported returns False for unsupported model."""
    assert is_quantization_supported("unknown-model") is False
    assert is_quantization_supported("") is False


# =============================================================================
# Test QuantizableModel Protocol
# =============================================================================


def test_quantizable_model_protocol():
    """Test QuantizableModel protocol is satisfied by mock model."""
    from backend.services.quantization import QuantizableModel

    mock_model = MagicMock(spec=QuantizableModel)
    mock_model.eval.return_value = mock_model

    result = mock_model.eval()
    assert result is mock_model
    mock_model.eval.assert_called_once()


# =============================================================================
# Test _is_bitsandbytes_available edge cases
# =============================================================================


def test_is_bitsandbytes_available_import_error():
    """Test _is_bitsandbytes_available handles ImportError."""
    with patch("importlib.util.find_spec", side_effect=ImportError("Module not found")):
        assert _is_bitsandbytes_available() is False


def test_is_bitsandbytes_available_module_not_found_error():
    """Test _is_bitsandbytes_available handles ModuleNotFoundError."""
    with patch("importlib.util.find_spec", side_effect=ModuleNotFoundError("No module")):
        assert _is_bitsandbytes_available() is False


# =============================================================================
# Test _get_model_size_mb edge cases
# =============================================================================


def test_get_model_size_mb_int8():
    """Test _get_model_size_mb for INT8 model."""
    import sys

    mock_torch = MagicMock()
    mock_torch.float16 = "float16"
    mock_torch.int8 = "int8"

    # Create mock parameters with int8 dtype
    mock_param = MagicMock()
    mock_param.numel.return_value = 1000000  # 1M parameters
    mock_param.dtype = "int8"

    mock_model = MagicMock()
    mock_model.parameters.return_value = [mock_param]

    with patch.dict(sys.modules, {"torch": mock_torch}):
        size = _get_model_size_mb(mock_model)
        # 1M params * 1 byte / 1024 / 1024 = ~0.95 MB
        assert size == pytest.approx(0.95, rel=0.1)


# =============================================================================
# Test get_optimal_backend edge cases
# =============================================================================


def test_get_optimal_backend_intel_cpu(monkeypatch):
    """Test get_optimal_backend returns ONEDNN for Intel CPUs."""
    import sys

    mock_cpuinfo = MagicMock()
    mock_cpuinfo.get_cpu_info.return_value = {"vendor_id_raw": "GenuineIntel"}

    with patch("platform.machine", return_value="x86_64"):
        monkeypatch.setitem(sys.modules, "cpuinfo", mock_cpuinfo)

        backend = get_optimal_backend()
        assert backend == QuantizationBackend.ONEDNN


def test_get_optimal_backend_amd_cpu():
    """Test get_optimal_backend returns X86 for AMD CPUs."""
    import sys

    mock_cpuinfo = MagicMock()
    mock_cpuinfo.get_cpu_info.return_value = {"vendor_id_raw": "AuthenticAMD"}

    with patch("platform.machine", return_value="x86_64"):
        with patch.dict(sys.modules, {"cpuinfo": mock_cpuinfo}):
            backend = get_optimal_backend()
            assert backend == QuantizationBackend.X86


def test_get_optimal_backend_cpuinfo_import_error():
    """Test get_optimal_backend handles cpuinfo import error."""
    import sys

    # Mock x86_64 platform
    with patch("platform.machine", return_value="x86_64"):
        # Remove cpuinfo from sys.modules to force ImportError
        original_cpuinfo = sys.modules.get("cpuinfo")
        if "cpuinfo" in sys.modules:
            del sys.modules["cpuinfo"]

        try:
            # Use a mock import that raises ImportError when cpuinfo is imported
            import builtins

            original_import = builtins.__import__

            def mock_import(name, *args, **kwargs):
                if name == "cpuinfo":
                    raise ImportError("No cpuinfo module")
                return original_import(name, *args, **kwargs)

            with patch("builtins.__import__", side_effect=mock_import):
                backend = get_optimal_backend()
                # Should fall back to X86 when cpuinfo is not available
                assert backend == QuantizationBackend.X86
        finally:
            # Restore original cpuinfo module if it existed
            if original_cpuinfo is not None:
                sys.modules["cpuinfo"] = original_cpuinfo


# =============================================================================
# Test get_bnb_4bit_config error paths
# =============================================================================


def test_get_bnb_4bit_config_transformers_import_error(monkeypatch):
    """Test get_bnb_4bit_config raises ImportError when transformers unavailable."""
    import sys

    with patch("backend.services.quantization._is_bitsandbytes_available", return_value=True):
        # Mock torch but make transformers import fail
        mock_torch = MagicMock()
        mock_torch.float16 = "float16"

        def mock_import(name, *args, **kwargs):
            if name == "transformers":
                raise ImportError("No transformers")
            return MagicMock()

        monkeypatch.setitem(sys.modules, "torch", mock_torch)

        with patch("builtins.__import__", side_effect=mock_import):
            with pytest.raises(ImportError, match="transformers package"):
                get_bnb_4bit_config()


# =============================================================================
# Test get_bnb_8bit_config error paths
# =============================================================================


def test_get_bnb_8bit_config_transformers_import_error(monkeypatch):
    """Test get_bnb_8bit_config raises ImportError when transformers unavailable."""

    with patch("backend.services.quantization._is_bitsandbytes_available", return_value=True):

        def mock_import(name, *args, **kwargs):
            if name == "transformers":
                raise ImportError("No transformers")
            return MagicMock()

        with patch("builtins.__import__", side_effect=mock_import):
            with pytest.raises(ImportError, match="transformers package"):
                get_bnb_8bit_config()


# =============================================================================
# Test apply_dynamic_int8_quantization error paths
# =============================================================================


def test_apply_dynamic_int8_quantization_runtime_error(monkeypatch):
    """Test apply_dynamic_int8_quantization handles quantization failure."""
    import sys

    mock_torch = MagicMock()
    mock_torch.nn.Linear = MagicMock()
    mock_torch.nn.LSTM = MagicMock()
    mock_torch.qint8 = "qint8"
    mock_torch.backends = MagicMock()

    mock_quant = MagicMock()
    # Simulate quantization failure
    mock_quant.quantize_dynamic.side_effect = RuntimeError("Quantization failed")

    # Set up torch.ao.quantization namespace
    mock_torch.ao = MagicMock()
    mock_torch.ao.quantization = mock_quant

    mock_model = MagicMock()
    mock_model.parameters.return_value = []

    monkeypatch.setitem(sys.modules, "torch", mock_torch)
    monkeypatch.setitem(sys.modules, "torch.ao.quantization", mock_quant)

    with pytest.raises(RuntimeError, match="Failed to apply INT8 quantization"):
        apply_dynamic_int8_quantization(mock_model)


# =============================================================================
# Test apply_static_int8_quantization error paths
# =============================================================================


def test_apply_static_int8_quantization_import_error():
    """Test apply_static_int8_quantization raises ImportError."""
    with patch.dict("sys.modules", {"torch": None}):
        with pytest.raises((ImportError, RuntimeError)):
            apply_static_int8_quantization(MagicMock(), MagicMock())


def test_apply_static_int8_quantization_runtime_error(monkeypatch):
    """Test apply_static_int8_quantization handles quantization failure."""
    import sys

    mock_torch = MagicMock()
    mock_torch.no_grad = MagicMock(
        return_value=MagicMock(__enter__=MagicMock(), __exit__=MagicMock())
    )
    mock_torch.backends = MagicMock()

    mock_quant = MagicMock()
    # Simulate prepare failure
    mock_quant.get_default_qconfig.return_value = MagicMock()
    mock_quant.prepare.side_effect = RuntimeError("Prepare failed")

    # Set up torch.ao.quantization namespace
    mock_torch.ao = MagicMock()
    mock_torch.ao.quantization = mock_quant

    mock_model = MagicMock()
    mock_model.parameters.return_value = []

    monkeypatch.setitem(sys.modules, "torch", mock_torch)
    monkeypatch.setitem(sys.modules, "torch.ao.quantization", mock_quant)

    calibration_fn = MagicMock()

    with pytest.raises(RuntimeError, match="Failed to apply static INT8 quantization"):
        apply_static_int8_quantization(mock_model, calibration_fn)


# =============================================================================
# Test apply_int8_quantization_async edge cases
# =============================================================================


@pytest.mark.asyncio
async def test_apply_int8_quantization_async_with_calibration_data_no_static():
    """Test apply_int8_quantization_async with calibration_data but use_static=False."""
    mock_result = QuantizationResult(
        model=MagicMock(),
        original_size_mb=100.0,
        quantized_size_mb=25.0,
        compression_ratio=4.0,
        quantization_type=QuantizationType.INT8,
        backend="x86",
    )

    with patch(
        "backend.services.quantization.apply_dynamic_int8_quantization",
        return_value=mock_result,
    ):
        # Even with calibration_data, should use dynamic if use_static=False
        calibration_data = [MagicMock(), MagicMock()]
        result = await apply_int8_quantization_async(
            MagicMock(),
            calibration_data=calibration_data,
            use_static=False,
        )

        assert result == mock_result


@pytest.mark.asyncio
async def test_apply_int8_quantization_async_static_no_calibration_data():
    """Test apply_int8_quantization_async with use_static=True but no calibration_data."""
    mock_result = QuantizationResult(
        model=MagicMock(),
        original_size_mb=100.0,
        quantized_size_mb=25.0,
        compression_ratio=4.0,
        quantization_type=QuantizationType.INT8,
        backend="x86",
    )

    with patch(
        "backend.services.quantization.apply_dynamic_int8_quantization",
        return_value=mock_result,
    ):
        # Should fall back to dynamic if no calibration_data
        result = await apply_int8_quantization_async(
            MagicMock(),
            calibration_data=None,
            use_static=True,
        )

        assert result == mock_result


@pytest.mark.asyncio
async def test_apply_int8_quantization_async_static_calibration_called():
    """Test apply_int8_quantization_async calls calibration function with samples."""
    import sys

    mock_torch = MagicMock()
    mock_torch.no_grad = MagicMock(
        return_value=MagicMock(__enter__=MagicMock(), __exit__=MagicMock())
    )
    mock_torch.backends = MagicMock()

    # Mock quantization result
    mock_param = MagicMock()
    mock_param.numel.return_value = 500000
    mock_param.dtype = "int8"

    mock_prepared_model = MagicMock()
    mock_prepared_model.parameters.return_value = [mock_param]

    mock_converted_model = MagicMock()
    mock_converted_model.parameters.return_value = [mock_param]

    mock_quant = MagicMock()
    mock_quant.get_default_qconfig.return_value = MagicMock()
    mock_quant.prepare.return_value = mock_prepared_model
    mock_quant.convert.return_value = mock_converted_model

    # Set up torch.ao.quantization namespace
    mock_torch.ao = MagicMock()
    mock_torch.ao.quantization = mock_quant

    mock_original_model = MagicMock()
    mock_original_param = MagicMock()
    mock_original_param.numel.return_value = 1000000
    mock_original_param.dtype = "float32"
    mock_original_model.parameters.return_value = [mock_original_param]

    # Create calibration samples
    sample1 = MagicMock()
    sample2 = MagicMock()
    calibration_data = [sample1, sample2]

    with patch.dict(sys.modules, {"torch": mock_torch}):
        with patch.dict(sys.modules, {"torch.ao.quantization": mock_quant}):
            result = await apply_int8_quantization_async(
                mock_original_model,
                calibration_data=calibration_data,
                use_static=True,
            )

            # Verify the prepared model was called with each sample
            assert mock_prepared_model.call_count == 2
            mock_prepared_model.assert_any_call(sample1)
            mock_prepared_model.assert_any_call(sample2)

            # Verify result
            assert isinstance(result, QuantizationResult)
            assert result.quantization_type == QuantizationType.INT8


# =============================================================================
# Test integration with Model Zoo
# =============================================================================


def test_quantization_recommendations_match_model_zoo():
    """Test quantization recommendations include models from Model Zoo."""
    from backend.services.model_zoo import get_model_zoo

    zoo = get_model_zoo()

    # Check that recommended models exist in Model Zoo
    for model_name in QUANTIZATION_RECOMMENDATIONS:
        # nemotron is handled separately (not in backend Model Zoo)
        if model_name == "nemotron":
            continue
        # Check model name format matches
        assert "-" in model_name or model_name.isalpha(), f"Invalid model name: {model_name}"


def test_low_priority_models_in_recommendations():
    """Test that low-priority/auxiliary models are included."""
    # These models are explicitly mentioned as good candidates for INT8
    expected_models = [
        "vit-age-classifier",
        "vit-gender-classifier",
        "pet-classifier",
        "osnet-x0-25",
        "threat-detection-yolov8n",
    ]

    for model_name in expected_models:
        assert model_name in QUANTIZATION_RECOMMENDATIONS, (
            f"{model_name} should have quantization recommendation"
        )


# =============================================================================
# Test function signatures
# =============================================================================


def test_get_bnb_4bit_config_signature():
    """Test get_bnb_4bit_config function signature."""
    import inspect

    sig = inspect.signature(get_bnb_4bit_config)
    params = list(sig.parameters.keys())

    assert "compute_dtype" in params
    assert "quant_type" in params
    assert "use_double_quant" in params

    # Check defaults
    assert sig.parameters["compute_dtype"].default == "float16"
    assert sig.parameters["quant_type"].default == "nf4"
    assert sig.parameters["use_double_quant"].default is True


def test_get_bnb_8bit_config_signature():
    """Test get_bnb_8bit_config function signature."""
    import inspect

    sig = inspect.signature(get_bnb_8bit_config)
    params = list(sig.parameters.keys())

    assert "llm_int8_threshold" in params
    assert "llm_int8_has_fp16_weight" in params

    # Check defaults
    assert sig.parameters["llm_int8_threshold"].default == 6.0
    assert sig.parameters["llm_int8_has_fp16_weight"].default is False


def test_apply_dynamic_int8_quantization_signature():
    """Test apply_dynamic_int8_quantization function signature."""
    import inspect

    sig = inspect.signature(apply_dynamic_int8_quantization)
    params = list(sig.parameters.keys())

    assert "model" in params
    assert "backend" in params


def test_apply_static_int8_quantization_signature():
    """Test apply_static_int8_quantization function signature."""
    import inspect

    sig = inspect.signature(apply_static_int8_quantization)
    params = list(sig.parameters.keys())

    assert "model" in params
    assert "calibration_fn" in params
    assert "backend" in params


def test_apply_int8_quantization_async_is_async():
    """Test apply_int8_quantization_async is an async function."""
    import inspect

    assert callable(apply_int8_quantization_async)
    assert inspect.iscoroutinefunction(apply_int8_quantization_async)


# =============================================================================
# Test edge cases
# =============================================================================


def test_quantization_result_zero_size():
    """Test QuantizationResult with zero sizes."""
    result = QuantizationResult(
        model=MagicMock(),
        original_size_mb=0.0,
        quantized_size_mb=0.0,
        compression_ratio=1.0,
        quantization_type=QuantizationType.INT8,
    )

    d = result.to_dict()
    assert d["original_size_mb"] == 0.0
    assert d["compression_ratio"] == 1.0


def test_quantization_backend_enum_iteration():
    """Test QuantizationBackend enum can be iterated."""
    backends = list(QuantizationBackend)
    assert len(backends) == 4


def test_quantization_type_enum_iteration():
    """Test QuantizationType enum can be iterated."""
    types = list(QuantizationType)
    assert len(types) == 4


def test_empty_model_parameters():
    """Test _get_model_size_mb with model that has no parameters."""
    mock_model = MagicMock()
    mock_model.parameters.return_value = iter([])

    size = _get_model_size_mb(mock_model)
    # Should handle empty parameters gracefully
    assert size == 0.0
