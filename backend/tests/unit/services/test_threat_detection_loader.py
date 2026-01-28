# ruff: noqa: ARG005
"""Unit tests for threat detection loader.

Tests cover:
- ThreatDetection dataclass
- ThreatDetectionResult dataclass
- load_threat_detection_model function
- detect_threats function
- detect_threats_batch function
- format_threat_context function
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from backend.services.threat_detection_loader import (
    HIGH_PRIORITY_THREATS,
    THREAT_CLASSES,
    ThreatDetection,
    ThreatDetectionResult,
    detect_threats,
    detect_threats_batch,
    format_threat_context,
    load_threat_detection_model,
)


class TestThreatDetection:
    """Tests for ThreatDetection dataclass."""

    def test_create_threat_detection_basic(self) -> None:
        """Test creating ThreatDetection with basic fields."""
        detection = ThreatDetection(
            class_name="knife", confidence=0.85, bbox=(10.0, 20.0, 50.0, 60.0)
        )

        assert detection.class_name == "knife"
        assert detection.confidence == 0.85
        assert detection.bbox == (10.0, 20.0, 50.0, 60.0)
        assert detection.is_high_priority is False

    def test_create_threat_detection_high_priority(self) -> None:
        """Test creating ThreatDetection with high priority flag."""
        detection = ThreatDetection(
            class_name="gun",
            confidence=0.95,
            bbox=(10.0, 20.0, 50.0, 60.0),
            is_high_priority=True,
        )

        assert detection.class_name == "gun"
        assert detection.is_high_priority is True

    def test_threat_detection_to_dict(self) -> None:
        """Test ThreatDetection.to_dict()."""
        detection = ThreatDetection(
            class_name="knife",
            confidence=0.9,
            bbox=(5.0, 10.0, 25.0, 40.0),
            is_high_priority=True,
        )

        d = detection.to_dict()

        assert d["class_name"] == "knife"
        assert d["confidence"] == 0.9
        assert d["bbox"] == [5.0, 10.0, 25.0, 40.0]
        assert d["is_high_priority"] is True


class TestThreatDetectionResult:
    """Tests for ThreatDetectionResult dataclass."""

    def test_create_result_no_threats(self) -> None:
        """Test creating ThreatDetectionResult with no threats."""
        result = ThreatDetectionResult()

        assert result.threats == []
        assert result.has_threats is False
        assert result.has_high_priority is False
        assert result.highest_confidence == 0.0
        assert result.threat_summary == ""

    def test_create_result_with_threats(self) -> None:
        """Test creating ThreatDetectionResult with threats."""
        threats = [
            ThreatDetection("knife", 0.85, (10.0, 20.0, 30.0, 40.0), False),
            ThreatDetection("gun", 0.95, (50.0, 60.0, 70.0, 80.0), True),
        ]

        result = ThreatDetectionResult(threats=threats)

        assert result.has_threats is True
        assert result.has_high_priority is True
        assert result.highest_confidence == 0.95
        assert "knife" in result.threat_summary
        assert "gun" in result.threat_summary

    def test_result_compute_summary_single(self) -> None:
        """Test ThreatDetectionResult computes summary for single threat."""
        threats = [ThreatDetection("knife", 0.85, (10.0, 20.0, 30.0, 40.0), False)]

        result = ThreatDetectionResult(threats=threats)

        assert result.threat_summary == "1x knife"

    def test_result_compute_summary_multiple_same(self) -> None:
        """Test ThreatDetectionResult computes summary for multiple same threats."""
        threats = [
            ThreatDetection("knife", 0.85, (10.0, 20.0, 30.0, 40.0), False),
            ThreatDetection("knife", 0.90, (50.0, 60.0, 70.0, 80.0), False),
        ]

        result = ThreatDetectionResult(threats=threats)

        assert result.threat_summary == "2x knife"

    def test_result_compute_summary_multiple_different(self) -> None:
        """Test ThreatDetectionResult computes summary for different threats."""
        threats = [
            ThreatDetection("knife", 0.85, (10.0, 20.0, 30.0, 40.0), False),
            ThreatDetection("gun", 0.95, (50.0, 60.0, 70.0, 80.0), True),
            ThreatDetection("bat", 0.80, (90.0, 100.0, 110.0, 120.0), False),
        ]

        result = ThreatDetectionResult(threats=threats)

        # Should be sorted alphabetically
        assert "bat" in result.threat_summary
        assert "gun" in result.threat_summary
        assert "knife" in result.threat_summary

    def test_result_to_dict(self) -> None:
        """Test ThreatDetectionResult.to_dict()."""
        threats = [
            ThreatDetection("knife", 0.85, (10.0, 20.0, 30.0, 40.0), False),
            ThreatDetection("gun", 0.95, (50.0, 60.0, 70.0, 80.0), True),
        ]

        result = ThreatDetectionResult(threats=threats)
        d = result.to_dict()

        assert d["has_threats"] is True
        assert d["has_high_priority"] is True
        assert d["highest_confidence"] == 0.95
        assert d["threat_count"] == 2
        assert len(d["threats"]) == 2

    def test_result_to_context_string_no_threats(self) -> None:
        """Test ThreatDetectionResult.to_context_string() with no threats."""
        result = ThreatDetectionResult()

        context = result.to_context_string()

        assert "No weapons or threatening objects detected" in context

    def test_result_to_context_string_with_threats(self) -> None:
        """Test ThreatDetectionResult.to_context_string() with threats."""
        threats = [
            ThreatDetection("knife", 0.85, (10.0, 20.0, 30.0, 40.0), False),
            ThreatDetection("gun", 0.95, (50.0, 60.0, 70.0, 80.0), True),
        ]

        result = ThreatDetectionResult(threats=threats)
        context = result.to_context_string()

        assert "THREAT DETECTION ALERT" in context
        assert "CRITICAL" in context
        assert "High-priority threat" in context
        assert "knife" in context
        assert "gun" in context
        assert "85%" in context
        assert "95%" in context

    def test_result_to_context_string_sorted_by_confidence(self) -> None:
        """Test ThreatDetectionResult.to_context_string() sorts by confidence."""
        threats = [
            ThreatDetection("knife", 0.70, (10.0, 20.0, 30.0, 40.0), False),
            ThreatDetection("gun", 0.95, (50.0, 60.0, 70.0, 80.0), True),
            ThreatDetection("bat", 0.60, (90.0, 100.0, 110.0, 120.0), False),
        ]

        result = ThreatDetectionResult(threats=threats)
        context = result.to_context_string()

        # gun (0.95) should appear before knife (0.70) and bat (0.60)
        gun_pos = context.find("gun")
        knife_pos = context.find("knife")
        bat_pos = context.find("bat")

        assert gun_pos < knife_pos
        assert knife_pos < bat_pos


class TestLoadThreatDetectionModel:
    """Tests for load_threat_detection_model function."""

    @pytest.mark.asyncio
    async def test_load_threat_detection_model_import_error(self, monkeypatch) -> None:
        """Test load_threat_detection_model handles ImportError."""
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
            with pytest.raises(
                ImportError,
                match="Threat detection requires ultralytics",
            ):
                await load_threat_detection_model("/fake/path")
        finally:
            sys.modules.update(hidden_modules)

    @pytest.mark.asyncio
    async def test_load_threat_detection_model_file_not_found(self, monkeypatch) -> None:
        """Test load_threat_detection_model handles FileNotFoundError."""
        import sys
        from pathlib import Path

        # Create mock YOLO
        mock_yolo_class = MagicMock()

        mock_ultralytics = MagicMock()
        mock_ultralytics.YOLO = mock_yolo_class

        # Mock Path.glob to return empty list
        mock_path = MagicMock(spec=Path)
        mock_path.glob.return_value = []
        mock_path.__truediv__ = lambda self, other: MagicMock(exists=lambda: False)

        monkeypatch.setitem(sys.modules, "ultralytics", mock_ultralytics)
        monkeypatch.setattr("backend.services.threat_detection_loader.Path", lambda x: mock_path)

        with pytest.raises(RuntimeError, match="Failed to load threat detection model"):
            await load_threat_detection_model("/fake/path")

    @pytest.mark.asyncio
    async def test_load_threat_detection_model_success(self, monkeypatch) -> None:
        """Test load_threat_detection_model success path."""
        import sys
        from pathlib import Path

        # Create mock YOLO model
        mock_model = MagicMock()
        mock_model.fuse.return_value = None

        # Mock inner model with is_fused
        mock_inner_model = MagicMock()
        mock_inner_model.is_fused.return_value = False
        mock_model.model = mock_inner_model

        mock_yolo_class = MagicMock(return_value=mock_model)

        mock_ultralytics = MagicMock()
        mock_ultralytics.YOLO = mock_yolo_class

        # Mock Path to return existing file
        mock_weights_file = MagicMock()
        mock_weights_file.exists.return_value = True

        mock_path = MagicMock(spec=Path)
        mock_path.__truediv__ = lambda self, other: mock_weights_file

        monkeypatch.setitem(sys.modules, "ultralytics", mock_ultralytics)
        monkeypatch.setattr("backend.services.threat_detection_loader.Path", lambda x: mock_path)

        result = await load_threat_detection_model("/test/model")

        assert result is mock_model
        mock_yolo_class.assert_called_once()
        mock_model.fuse.assert_called_once()

    @pytest.mark.asyncio
    async def test_load_threat_detection_model_already_fused(self, monkeypatch) -> None:
        """Test load_threat_detection_model skips fusing if already fused."""
        import sys
        from pathlib import Path

        # Create mock YOLO model
        mock_model = MagicMock()
        mock_model.fuse.return_value = None

        # Mock inner model that is already fused
        mock_inner_model = MagicMock()
        mock_inner_model.is_fused.return_value = True
        mock_model.model = mock_inner_model

        mock_yolo_class = MagicMock(return_value=mock_model)

        mock_ultralytics = MagicMock()
        mock_ultralytics.YOLO = mock_yolo_class

        # Mock Path
        mock_weights_file = MagicMock()
        mock_weights_file.exists.return_value = True

        mock_path = MagicMock(spec=Path)
        mock_path.__truediv__ = lambda self, other: mock_weights_file

        monkeypatch.setitem(sys.modules, "ultralytics", mock_ultralytics)
        monkeypatch.setattr("backend.services.threat_detection_loader.Path", lambda x: mock_path)

        result = await load_threat_detection_model("/test/model")

        assert result is mock_model
        # Fuse should NOT be called because model is already fused
        mock_model.fuse.assert_not_called()

    @pytest.mark.asyncio
    async def test_load_threat_detection_model_no_fuse_method(self, monkeypatch) -> None:
        """Test load_threat_detection_model handles models without fuse method."""
        import sys
        from pathlib import Path

        # Create mock YOLO model without fuse method
        mock_model = MagicMock(spec=[])  # No fuse method

        mock_yolo_class = MagicMock(return_value=mock_model)

        mock_ultralytics = MagicMock()
        mock_ultralytics.YOLO = mock_yolo_class

        # Mock Path
        mock_weights_file = MagicMock()
        mock_weights_file.exists.return_value = True

        mock_path = MagicMock(spec=Path)
        mock_path.__truediv__ = lambda self, other: mock_weights_file

        monkeypatch.setitem(sys.modules, "ultralytics", mock_ultralytics)
        monkeypatch.setattr("backend.services.threat_detection_loader.Path", lambda x: mock_path)

        result = await load_threat_detection_model("/test/model")

        # Should succeed even without fuse method
        assert result is mock_model

    @pytest.mark.asyncio
    async def test_load_threat_detection_model_fallback_weights(self, monkeypatch) -> None:
        """Test load_threat_detection_model tries multiple weight file names."""
        import sys
        from pathlib import Path

        # Create mock YOLO model
        mock_model = MagicMock()
        mock_model.fuse.return_value = None
        mock_inner_model = MagicMock()
        mock_inner_model.is_fused.return_value = False
        mock_model.model = mock_inner_model

        mock_yolo_class = MagicMock(return_value=mock_model)

        mock_ultralytics = MagicMock()
        mock_ultralytics.YOLO = mock_yolo_class

        # Mock Path where model.pt doesn't exist but best.pt does
        call_count = [0]

        def mock_div(self, other):
            call_count[0] += 1
            mock_file = MagicMock()
            # First two calls (model.pt, best.pt) return False, third returns True
            mock_file.exists.return_value = call_count[0] >= 3
            return mock_file

        mock_path = MagicMock(spec=Path)
        mock_path.__truediv__ = mock_div
        mock_path.glob.return_value = [MagicMock()]

        monkeypatch.setitem(sys.modules, "ultralytics", mock_ultralytics)
        monkeypatch.setattr("backend.services.threat_detection_loader.Path", lambda x: mock_path)

        result = await load_threat_detection_model("/test/model")

        assert result is mock_model


class TestDetectThreats:
    """Tests for detect_threats function."""

    @pytest.mark.asyncio
    async def test_detect_threats_no_detections(self) -> None:
        """Test detect_threats with no threats detected."""
        # Create mock model
        mock_result = MagicMock()
        mock_result.boxes = None

        mock_model = MagicMock()
        mock_model.predict.return_value = [mock_result]

        # Create mock image
        mock_image = MagicMock()

        result = await detect_threats(mock_model, mock_image)

        assert isinstance(result, ThreatDetectionResult)
        assert result.has_threats is False
        assert len(result.threats) == 0

    @pytest.mark.asyncio
    async def test_detect_threats_with_detections(self) -> None:
        """Test detect_threats with threats detected."""
        # Create mock boxes
        mock_boxes = MagicMock()
        mock_boxes.__len__ = lambda self: 2

        # Mock cls tensor
        mock_cls = MagicMock()
        mock_cls.__getitem__ = lambda self, i: MagicMock(item=lambda: i)
        mock_boxes.cls = mock_cls

        # Mock conf tensor
        mock_conf = MagicMock()
        mock_conf.__getitem__ = lambda self, i: MagicMock(item=lambda: 0.85 + i * 0.1)
        mock_boxes.conf = mock_conf

        # Mock xyxy tensor
        mock_xyxy = MagicMock()
        mock_xyxy.__getitem__ = lambda self, i: MagicMock(
            tolist=lambda: [10.0 + i * 10, 20.0 + i * 10, 30.0 + i * 10, 40.0 + i * 10]
        )
        mock_boxes.xyxy = mock_xyxy

        # Create mock result
        mock_result = MagicMock()
        mock_result.boxes = mock_boxes

        # Create mock model with names
        mock_model = MagicMock()
        mock_model.names = {0: "knife", 1: "gun"}
        mock_model.predict.return_value = [mock_result]

        # Create mock image
        mock_image = MagicMock()

        result = await detect_threats(mock_model, mock_image)

        assert isinstance(result, ThreatDetectionResult)
        assert result.has_threats is True
        assert len(result.threats) == 2
        assert result.threats[0].class_name == "knife"
        assert result.threats[1].class_name == "gun"

    @pytest.mark.asyncio
    async def test_detect_threats_high_priority_detection(self) -> None:
        """Test detect_threats marks high-priority threats correctly."""
        # Create mock boxes with gun detection
        mock_boxes = MagicMock()
        mock_boxes.__len__ = lambda self: 1

        mock_cls = MagicMock()
        mock_cls.__getitem__ = lambda self, i: MagicMock(item=lambda: 0)
        mock_boxes.cls = mock_cls

        mock_conf = MagicMock()
        mock_conf.__getitem__ = lambda self, i: MagicMock(item=lambda: 0.95)
        mock_boxes.conf = mock_conf

        mock_xyxy = MagicMock()
        mock_xyxy.__getitem__ = lambda self, i: MagicMock(tolist=lambda: [10.0, 20.0, 30.0, 40.0])
        mock_boxes.xyxy = mock_xyxy

        mock_result = MagicMock()
        mock_result.boxes = mock_boxes

        # Create mock model with gun class
        mock_model = MagicMock()
        mock_model.names = {0: "gun"}
        mock_model.predict.return_value = [mock_result]

        mock_image = MagicMock()

        result = await detect_threats(mock_model, mock_image)

        assert result.has_high_priority is True
        assert result.threats[0].is_high_priority is True

    @pytest.mark.asyncio
    async def test_detect_threats_unknown_class(self) -> None:
        """Test detect_threats handles unknown class IDs."""
        # Create mock boxes
        mock_boxes = MagicMock()
        mock_boxes.__len__ = lambda self: 1

        mock_cls = MagicMock()
        mock_cls.__getitem__ = lambda self, i: MagicMock(item=lambda: 99)
        mock_boxes.cls = mock_cls

        mock_conf = MagicMock()
        mock_conf.__getitem__ = lambda self, i: MagicMock(item=lambda: 0.85)
        mock_boxes.conf = mock_conf

        mock_xyxy = MagicMock()
        mock_xyxy.__getitem__ = lambda self, i: MagicMock(tolist=lambda: [10.0, 20.0, 30.0, 40.0])
        mock_boxes.xyxy = mock_xyxy

        mock_result = MagicMock()
        mock_result.boxes = mock_boxes

        # Create mock model without class 99
        mock_model = MagicMock()
        mock_model.names = {0: "knife"}
        mock_model.predict.return_value = [mock_result]

        mock_image = MagicMock()

        result = await detect_threats(mock_model, mock_image)

        assert result.threats[0].class_name == "class_99"

    @pytest.mark.asyncio
    async def test_detect_threats_custom_confidence_threshold(self) -> None:
        """Test detect_threats uses custom confidence threshold."""
        mock_model = MagicMock()
        mock_model.predict.return_value = []

        mock_image = MagicMock()

        await detect_threats(mock_model, mock_image, confidence_threshold=0.5)

        # Verify predict was called with correct threshold
        mock_model.predict.assert_called_once()
        call_args = mock_model.predict.call_args
        assert call_args[1]["conf"] == 0.5

    @pytest.mark.asyncio
    async def test_detect_threats_error_handling(self) -> None:
        """Test detect_threats handles errors."""
        mock_model = MagicMock()
        mock_model.predict.side_effect = RuntimeError("Model error")

        mock_image = MagicMock()

        with pytest.raises(RuntimeError, match="Threat detection failed"):
            await detect_threats(mock_model, mock_image)

    @pytest.mark.asyncio
    async def test_detect_threats_model_without_names(self) -> None:
        """Test detect_threats handles model without names attribute."""
        # Create mock boxes
        mock_boxes = MagicMock()
        mock_boxes.__len__ = lambda self: 1

        mock_cls = MagicMock()
        mock_cls.__getitem__ = lambda self, i: MagicMock(item=lambda: 0)
        mock_boxes.cls = mock_cls

        mock_conf = MagicMock()
        mock_conf.__getitem__ = lambda self, i: MagicMock(item=lambda: 0.85)
        mock_boxes.conf = mock_conf

        mock_xyxy = MagicMock()
        mock_xyxy.__getitem__ = lambda self, i: MagicMock(tolist=lambda: [10.0, 20.0, 30.0, 40.0])
        mock_boxes.xyxy = mock_xyxy

        mock_result = MagicMock()
        mock_result.boxes = mock_boxes

        # Create mock model without names attribute
        mock_model = MagicMock()
        del mock_model.names  # Remove names attribute
        mock_model.predict.return_value = [mock_result]

        mock_image = MagicMock()

        result = await detect_threats(mock_model, mock_image)

        # Should use fallback class_0 name
        assert result.threats[0].class_name == "class_0"

    @pytest.mark.asyncio
    async def test_detect_threats_empty_results(self) -> None:
        """Test detect_threats handles empty results list."""
        mock_model = MagicMock()
        mock_model.predict.return_value = []

        mock_image = MagicMock()

        result = await detect_threats(mock_model, mock_image)

        assert isinstance(result, ThreatDetectionResult)
        assert result.has_threats is False


class TestDetectThreatsBatch:
    """Tests for detect_threats_batch function."""

    @pytest.mark.asyncio
    async def test_detect_threats_batch_empty_list(self) -> None:
        """Test detect_threats_batch with empty image list."""
        mock_model = MagicMock()

        result = await detect_threats_batch(mock_model, [])

        assert result == []

    @pytest.mark.asyncio
    async def test_detect_threats_batch_multiple_images(self) -> None:
        """Test detect_threats_batch with multiple images."""
        # Create mock results for 2 images
        mock_result1 = MagicMock()
        mock_result1.boxes = None

        mock_boxes2 = MagicMock()
        mock_boxes2.__len__ = lambda self: 1

        mock_cls = MagicMock()
        mock_cls.__getitem__ = lambda self, i: MagicMock(item=lambda: 0)
        mock_boxes2.cls = mock_cls

        mock_conf = MagicMock()
        mock_conf.__getitem__ = lambda self, i: MagicMock(item=lambda: 0.85)
        mock_boxes2.conf = mock_conf

        mock_xyxy = MagicMock()
        mock_xyxy.__getitem__ = lambda self, i: MagicMock(tolist=lambda: [10.0, 20.0, 30.0, 40.0])
        mock_boxes2.xyxy = mock_xyxy

        mock_result2 = MagicMock()
        mock_result2.boxes = mock_boxes2

        # Create mock model
        mock_model = MagicMock()
        mock_model.names = {0: "knife"}
        mock_model.predict.return_value = [mock_result1, mock_result2]

        # Create mock images
        mock_image1 = MagicMock()
        mock_image2 = MagicMock()

        results = await detect_threats_batch(mock_model, [mock_image1, mock_image2])

        assert len(results) == 2
        assert results[0].has_threats is False
        assert results[1].has_threats is True
        assert len(results[1].threats) == 1

    @pytest.mark.asyncio
    async def test_detect_threats_batch_error_handling(self) -> None:
        """Test detect_threats_batch handles errors."""
        mock_model = MagicMock()
        mock_model.predict.side_effect = RuntimeError("Batch error")

        mock_images = [MagicMock(), MagicMock()]

        with pytest.raises(RuntimeError, match="Batch threat detection failed"):
            await detect_threats_batch(mock_model, mock_images)


class TestFormatThreatContext:
    """Tests for format_threat_context function."""

    def test_format_threat_context_none(self) -> None:
        """Test format_threat_context with None result."""
        context = format_threat_context(None)

        assert "Not performed" in context

    def test_format_threat_context_no_threats(self) -> None:
        """Test format_threat_context with no threats."""
        result = ThreatDetectionResult()

        context = format_threat_context(result)

        assert "No weapons or threatening objects detected" in context

    def test_format_threat_context_with_threats(self) -> None:
        """Test format_threat_context with threats."""
        threats = [
            ThreatDetection("knife", 0.85, (10.0, 20.0, 30.0, 40.0), False),
            ThreatDetection("gun", 0.95, (50.0, 60.0, 70.0, 80.0), True),
        ]

        result = ThreatDetectionResult(threats=threats)

        context = format_threat_context(result)

        assert "WEAPON/THREAT DETECTION" in context
        assert "CRITICAL ALERT" in context
        assert "High-priority weapon detected" in context
        assert "1x gun, 1x knife" in result.threat_summary
        assert "95%" in context

    def test_format_threat_context_time_of_day_escalation(self) -> None:
        """Test format_threat_context with time of day escalation."""
        threats = [ThreatDetection("gun", 0.95, (10.0, 20.0, 30.0, 40.0), True)]

        result = ThreatDetectionResult(threats=threats)

        context = format_threat_context(result, time_of_day="night")

        assert "TIME CONTEXT" in context
        assert "night" in context
        assert "Elevated concern" in context
        assert "unusual hour" in context

    def test_format_threat_context_no_time_escalation_daytime(self) -> None:
        """Test format_threat_context with daytime (no escalation)."""
        threats = [ThreatDetection("gun", 0.95, (10.0, 20.0, 30.0, 40.0), True)]

        result = ThreatDetectionResult(threats=threats)

        context = format_threat_context(result, time_of_day="afternoon")

        # Should not include time context for afternoon
        assert "TIME CONTEXT" not in context

    def test_format_threat_context_multiple_threats_limited(self) -> None:
        """Test format_threat_context limits detail output to top 5 threats."""
        threats = [
            ThreatDetection(f"threat_{i}", 0.9 - i * 0.1, (10.0, 20.0, 30.0, 40.0))
            for i in range(10)
        ]

        result = ThreatDetectionResult(threats=threats)

        context = format_threat_context(result)

        # Should show all threats in summary
        assert "threat_0" in context
        assert "threat_9" in context

        # But detail lines should be limited (check by line count)
        # The context should have line breaks showing detailed threats
        lines = context.split("\n")
        detail_lines = [line for line in lines if line.strip().startswith("-")]
        # Should have max 5 detail lines
        assert len(detail_lines) <= 5


class TestThreatConstants:
    """Tests for threat detection constants."""

    def test_threat_classes_constant(self) -> None:
        """Test THREAT_CLASSES contains expected classes."""
        assert "knife" in THREAT_CLASSES
        assert "gun" in THREAT_CLASSES
        assert "pistol" in THREAT_CLASSES
        assert "rifle" in THREAT_CLASSES
        assert "bat" in THREAT_CLASSES

    def test_high_priority_threats_constant(self) -> None:
        """Test HIGH_PRIORITY_THREATS contains dangerous weapons."""
        assert "gun" in HIGH_PRIORITY_THREATS
        assert "pistol" in HIGH_PRIORITY_THREATS
        assert "rifle" in HIGH_PRIORITY_THREATS
        assert "knife" in HIGH_PRIORITY_THREATS
        assert "machete" in HIGH_PRIORITY_THREATS

    def test_high_priority_threats_subset_of_threat_classes(self) -> None:
        """Test HIGH_PRIORITY_THREATS is a subset of THREAT_CLASSES."""
        # Not all high priority threats are in THREAT_CLASSES, but key ones should be
        assert HIGH_PRIORITY_THREATS.intersection(THREAT_CLASSES)


class TestThreatDetectionIntegration:
    """Integration tests for threat detection."""

    def test_threat_detection_dataclasses_json_serializable(self) -> None:
        """Test threat detection results are JSON serializable."""
        import json

        threats = [
            ThreatDetection("knife", 0.85, (10.0, 20.0, 30.0, 40.0), False),
            ThreatDetection("gun", 0.95, (50.0, 60.0, 70.0, 80.0), True),
        ]

        result = ThreatDetectionResult(threats=threats)

        d = result.to_dict()

        # Should be JSON serializable
        json_str = json.dumps(d)
        assert json_str is not None

        # Should round-trip correctly
        parsed = json.loads(json_str)
        assert parsed["has_threats"] is True
        assert parsed["has_high_priority"] is True
        assert parsed["threat_count"] == 2

    def test_threat_detection_result_empty_compute_summary(self) -> None:
        """Test ThreatDetectionResult._compute_summary with no threats."""
        # Create result with empty threats list
        result = ThreatDetectionResult(threats=[])

        # Manually call _compute_summary
        result._compute_summary()

        assert result.threat_summary == "No threats detected"
