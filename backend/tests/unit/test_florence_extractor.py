"""Unit tests for Florence-2 extractor and loader.

Tests cover:
- VehicleAttributes dataclass and methods
- PersonAttributes dataclass and methods
- SceneAnalysis dataclass and methods
- EnvironmentContext dataclass and methods
- FlorenceExtractor helper methods (parsing, cropping)
- FlorenceExtractor extraction methods (with mocked model)
- florence_loader function
- Model Zoo Florence-2 registration
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from backend.services.florence_extractor import (
    ENVIRONMENT_QUERIES,
    PERSON_QUERIES,
    SCENE_QUERIES,
    VEHICLE_QUERIES,
    EnvironmentContext,
    FlorenceExtractor,
    PersonAttributes,
    SceneAnalysis,
    VehicleAttributes,
    get_florence_extractor,
    reset_florence_extractor,
)
from backend.services.florence_loader import load_florence_model
from backend.services.model_zoo import (
    get_model_config,
    get_model_zoo,
    reset_model_zoo,
)


class TestVehicleAttributes:
    """Tests for VehicleAttributes dataclass."""

    def test_default_values(self) -> None:
        """Test VehicleAttributes default values."""
        attrs = VehicleAttributes()

        assert attrs.color is None
        assert attrs.vehicle_type is None
        assert attrs.is_commercial is False
        assert attrs.commercial_text is None
        assert attrs.caption == ""
        assert attrs.confidence == 0.0

    def test_with_values(self) -> None:
        """Test VehicleAttributes with values."""
        attrs = VehicleAttributes(
            color="white",
            vehicle_type="sedan",
            is_commercial=True,
            commercial_text="FedEx",
            caption="A white FedEx delivery van",
            confidence=0.85,
        )

        assert attrs.color == "white"
        assert attrs.vehicle_type == "sedan"
        assert attrs.is_commercial is True
        assert attrs.commercial_text == "FedEx"
        assert attrs.caption == "A white FedEx delivery van"
        assert attrs.confidence == 0.85

    def test_to_dict(self) -> None:
        """Test VehicleAttributes to_dict conversion."""
        attrs = VehicleAttributes(
            color="red",
            vehicle_type="SUV",
            is_commercial=False,
            confidence=0.9,
        )

        d = attrs.to_dict()

        assert d["color"] == "red"
        assert d["vehicle_type"] == "SUV"
        assert d["is_commercial"] is False
        assert d["commercial_text"] is None
        assert d["confidence"] == 0.9

    def test_to_context_string_with_attributes(self) -> None:
        """Test VehicleAttributes context string with attributes."""
        attrs = VehicleAttributes(
            color="blue",
            vehicle_type="van",
            is_commercial=True,
            commercial_text="Amazon",
        )

        context = attrs.to_context_string()

        assert "Color: blue" in context
        assert "Type: van" in context
        assert "Commercial: Yes" in context
        assert "Company: Amazon" in context

    def test_to_context_string_empty(self) -> None:
        """Test VehicleAttributes context string when empty."""
        attrs = VehicleAttributes()
        context = attrs.to_context_string()
        assert context == "No attributes extracted"

    def test_to_context_string_caption_only(self) -> None:
        """Test VehicleAttributes context string with only caption."""
        attrs = VehicleAttributes(caption="A car in a parking lot")
        context = attrs.to_context_string()
        assert context == "A car in a parking lot"


class TestPersonAttributes:
    """Tests for PersonAttributes dataclass."""

    def test_default_values(self) -> None:
        """Test PersonAttributes default values."""
        attrs = PersonAttributes()

        assert attrs.clothing is None
        assert attrs.carrying is None
        assert attrs.is_service_worker is False
        assert attrs.action is None
        assert attrs.caption == ""
        assert attrs.confidence == 0.0

    def test_with_values(self) -> None:
        """Test PersonAttributes with values."""
        attrs = PersonAttributes(
            clothing="blue jacket, dark pants",
            carrying="backpack",
            is_service_worker=False,
            action="walking",
            caption="A person walking with a backpack",
            confidence=0.75,
        )

        assert attrs.clothing == "blue jacket, dark pants"
        assert attrs.carrying == "backpack"
        assert attrs.is_service_worker is False
        assert attrs.action == "walking"
        assert attrs.confidence == 0.75

    def test_to_dict(self) -> None:
        """Test PersonAttributes to_dict conversion."""
        attrs = PersonAttributes(
            clothing="uniform",
            carrying="package",
            is_service_worker=True,
            action="standing",
            confidence=0.8,
        )

        d = attrs.to_dict()

        assert d["clothing"] == "uniform"
        assert d["carrying"] == "package"
        assert d["is_service_worker"] is True
        assert d["action"] == "standing"
        assert d["confidence"] == 0.8

    def test_to_context_string_with_attributes(self) -> None:
        """Test PersonAttributes context string with attributes."""
        attrs = PersonAttributes(
            clothing="red shirt",
            carrying="briefcase",
            action="running",
            is_service_worker=True,
        )

        context = attrs.to_context_string()

        assert "Wearing: red shirt" in context
        assert "Carrying: briefcase" in context
        assert "Action: running" in context
        assert "service worker" in context

    def test_to_context_string_empty(self) -> None:
        """Test PersonAttributes context string when empty."""
        attrs = PersonAttributes()
        context = attrs.to_context_string()
        assert context == "No attributes extracted"


class TestSceneAnalysis:
    """Tests for SceneAnalysis dataclass."""

    def test_default_values(self) -> None:
        """Test SceneAnalysis default values."""
        analysis = SceneAnalysis()

        assert analysis.unusual_objects == []
        assert analysis.tools_detected == []
        assert analysis.abandoned_items == []
        assert analysis.scene_description == ""
        assert analysis.confidence == 0.0

    def test_with_values(self) -> None:
        """Test SceneAnalysis with values."""
        analysis = SceneAnalysis(
            unusual_objects=["ladder against fence"],
            tools_detected=["crowbar", "ladder"],
            abandoned_items=["suspicious package"],
            scene_description="A backyard with suspicious activity",
            confidence=0.9,
        )

        assert len(analysis.unusual_objects) == 1
        assert len(analysis.tools_detected) == 2
        assert len(analysis.abandoned_items) == 1
        assert analysis.confidence == 0.9

    def test_to_dict(self) -> None:
        """Test SceneAnalysis to_dict conversion."""
        analysis = SceneAnalysis(
            tools_detected=["hammer"],
            scene_description="A garage",
            confidence=0.7,
        )

        d = analysis.to_dict()

        assert d["tools_detected"] == ["hammer"]
        assert d["scene_description"] == "A garage"
        assert d["unusual_objects"] == []
        assert d["abandoned_items"] == []

    def test_has_security_concerns_true(self) -> None:
        """Test has_security_concerns returns True when concerns exist."""
        analysis = SceneAnalysis(tools_detected=["bolt cutters"])
        assert analysis.has_security_concerns() is True

        analysis2 = SceneAnalysis(unusual_objects=["person hiding"])
        assert analysis2.has_security_concerns() is True

        analysis3 = SceneAnalysis(abandoned_items=["package"])
        assert analysis3.has_security_concerns() is True

    def test_has_security_concerns_false(self) -> None:
        """Test has_security_concerns returns False when no concerns."""
        analysis = SceneAnalysis(scene_description="A normal front yard")
        assert analysis.has_security_concerns() is False

    def test_to_context_string_with_concerns(self) -> None:
        """Test SceneAnalysis context string with concerns."""
        analysis = SceneAnalysis(
            tools_detected=["ladder", "crowbar"],
            unusual_objects=["broken window"],
            abandoned_items=["bag"],
        )

        context = analysis.to_context_string()

        assert "Tools: ladder, crowbar" in context
        assert "Unusual: broken window" in context
        assert "Abandoned: bag" in context

    def test_to_context_string_empty(self) -> None:
        """Test SceneAnalysis context string when empty."""
        analysis = SceneAnalysis()
        context = analysis.to_context_string()
        assert context == "No unusual elements detected"


class TestEnvironmentContext:
    """Tests for EnvironmentContext dataclass."""

    def test_default_values(self) -> None:
        """Test EnvironmentContext default values."""
        context = EnvironmentContext()

        assert context.time_of_day == "unknown"
        assert context.artificial_light is False
        assert context.weather is None
        assert context.confidence == 0.0

    def test_with_values(self) -> None:
        """Test EnvironmentContext with values."""
        context = EnvironmentContext(
            time_of_day="night",
            artificial_light=True,
            weather="clear",
            confidence=0.85,
        )

        assert context.time_of_day == "night"
        assert context.artificial_light is True
        assert context.weather == "clear"
        assert context.confidence == 0.85

    def test_to_dict(self) -> None:
        """Test EnvironmentContext to_dict conversion."""
        context = EnvironmentContext(
            time_of_day="dusk",
            artificial_light=False,
            weather="rainy",
            confidence=0.7,
        )

        d = context.to_dict()

        assert d["time_of_day"] == "dusk"
        assert d["artificial_light"] is False
        assert d["weather"] == "rainy"
        assert d["confidence"] == 0.7

    def test_is_suspicious_lighting_true(self) -> None:
        """Test is_suspicious_lighting returns True for night + artificial."""
        context = EnvironmentContext(
            time_of_day="night",
            artificial_light=True,
        )
        assert context.is_suspicious_lighting() is True

    def test_is_suspicious_lighting_false(self) -> None:
        """Test is_suspicious_lighting returns False otherwise."""
        # Daytime with artificial light
        context1 = EnvironmentContext(
            time_of_day="day",
            artificial_light=True,
        )
        assert context1.is_suspicious_lighting() is False

        # Night without artificial light
        context2 = EnvironmentContext(
            time_of_day="night",
            artificial_light=False,
        )
        assert context2.is_suspicious_lighting() is False

    def test_to_context_string(self) -> None:
        """Test EnvironmentContext context string."""
        context = EnvironmentContext(
            time_of_day="night",
            artificial_light=True,
            weather="foggy",
        )

        context_str = context.to_context_string()

        assert "Time: night" in context_str
        assert "Artificial light detected" in context_str
        assert "Weather: foggy" in context_str


class TestFlorenceExtractorHelpers:
    """Tests for FlorenceExtractor helper methods."""

    def setup_method(self) -> None:
        """Reset extractor before each test."""
        reset_florence_extractor()

    def teardown_method(self) -> None:
        """Reset extractor after each test."""
        reset_florence_extractor()

    def test_extractor_init(self) -> None:
        """Test FlorenceExtractor initialization."""
        extractor = FlorenceExtractor()
        assert extractor.timeout_seconds == 30.0

        extractor_custom = FlorenceExtractor(timeout_seconds=60.0)
        assert extractor_custom.timeout_seconds == 60.0

    def test_parse_yes_no_positive(self) -> None:
        """Test _parse_yes_no with positive responses."""
        extractor = FlorenceExtractor()

        assert extractor._parse_yes_no("Yes") is True
        assert extractor._parse_yes_no("yes, it is") is True
        assert extractor._parse_yes_no("True") is True
        assert extractor._parse_yes_no("appears to be a delivery vehicle") is True
        assert extractor._parse_yes_no("looks like a commercial van") is True
        assert extractor._parse_yes_no("seems to be a service worker") is True

    def test_parse_yes_no_negative(self) -> None:
        """Test _parse_yes_no with negative responses."""
        extractor = FlorenceExtractor()

        assert extractor._parse_yes_no("No") is False
        assert extractor._parse_yes_no("no visible") is False
        assert extractor._parse_yes_no("nothing detected") is False
        assert extractor._parse_yes_no("") is False

    def test_parse_list_response_with_items(self) -> None:
        """Test _parse_list_response with items."""
        extractor = FlorenceExtractor()

        items = extractor._parse_list_response("ladder, crowbar, hammer")
        assert len(items) == 3
        assert "ladder" in items
        assert "crowbar" in items
        assert "hammer" in items

    def test_parse_list_response_empty(self) -> None:
        """Test _parse_list_response with empty/negative responses."""
        extractor = FlorenceExtractor()

        assert extractor._parse_list_response("No tools visible") == []
        assert extractor._parse_list_response("None detected") == []
        assert extractor._parse_list_response("Nothing unusual") == []

    def test_extract_color(self) -> None:
        """Test _extract_color method."""
        extractor = FlorenceExtractor()

        assert extractor._extract_color("The car is white") == "white"
        assert extractor._extract_color("A red pickup truck") == "red"
        assert extractor._extract_color("Black sedan parked") == "black"
        assert extractor._extract_color("Silver SUV") == "silver"
        assert extractor._extract_color("Gray van") == "gray"

    def test_extract_color_no_match(self) -> None:
        """Test _extract_color with no standard color."""
        extractor = FlorenceExtractor()

        # Returns full response if no standard color found
        result = extractor._extract_color("A vehicle")
        assert result == "A vehicle"

        # Returns None for empty
        assert extractor._extract_color("") is None

    def test_extract_vehicle_type(self) -> None:
        """Test _extract_vehicle_type method."""
        extractor = FlorenceExtractor()

        assert extractor._extract_vehicle_type("This is a sedan") == "sedan"
        assert extractor._extract_vehicle_type("Large SUV parked") == "suv"
        assert extractor._extract_vehicle_type("Pickup truck") == "pickup"
        assert extractor._extract_vehicle_type("Delivery van") == "van"
        assert extractor._extract_vehicle_type("Minivan with family") == "minivan"

    def test_extract_time_of_day(self) -> None:
        """Test _extract_time_of_day method."""
        extractor = FlorenceExtractor()

        assert extractor._extract_time_of_day("It is nighttime, very dark") == "night"
        assert extractor._extract_time_of_day("Dusk lighting visible") == "dusk"
        assert extractor._extract_time_of_day("Early morning sunrise") == "dawn"
        assert extractor._extract_time_of_day("Bright afternoon sunlight") == "day"
        assert extractor._extract_time_of_day("Midday based on shadows") == "day"
        assert extractor._extract_time_of_day("Unable to determine") == "unknown"

    def test_crop_bbox(self) -> None:
        """Test _crop_bbox method."""
        from PIL import Image

        extractor = FlorenceExtractor()

        # Create a test image
        image = Image.new("RGB", (200, 200), color="red")
        bbox = (50, 50, 100, 100)

        cropped = extractor._crop_bbox(image, bbox, padding=0)

        assert cropped.size == (50, 50)

    def test_crop_bbox_with_padding(self) -> None:
        """Test _crop_bbox with padding."""
        from PIL import Image

        extractor = FlorenceExtractor()

        image = Image.new("RGB", (200, 200), color="blue")
        bbox = (50, 50, 100, 100)

        cropped = extractor._crop_bbox(image, bbox, padding=10)

        # Should be 50 + 20 (padding on both sides)
        assert cropped.size == (70, 70)

    def test_crop_bbox_clamps_to_bounds(self) -> None:
        """Test _crop_bbox clamps to image bounds."""
        from PIL import Image

        extractor = FlorenceExtractor()

        image = Image.new("RGB", (100, 100), color="green")
        bbox = (0, 0, 50, 50)

        # With large padding, should still clamp to image bounds
        cropped = extractor._crop_bbox(image, bbox, padding=50)

        # Should be clamped to 0 on left/top
        assert cropped.size[0] <= 100
        assert cropped.size[1] <= 100


class TestFlorenceExtractorInference:
    """Tests for FlorenceExtractor inference methods with mocked model."""

    def setup_method(self) -> None:
        """Reset extractor before each test."""
        reset_florence_extractor()

    def teardown_method(self) -> None:
        """Reset extractor after each test."""
        reset_florence_extractor()

    @pytest.mark.asyncio
    async def test_extract_vehicle_attributes(self) -> None:
        """Test extract_vehicle_attributes with mocked model."""
        from PIL import Image

        extractor = FlorenceExtractor()

        # Create mock model tuple
        mock_model = MagicMock()
        mock_processor = MagicMock()
        model_tuple = (mock_model, mock_processor)

        # Mock _run_inference to return controlled responses
        responses = {
            VEHICLE_QUERIES["caption"]: "A white delivery van",
            VEHICLE_QUERIES["color"]: "White",
            VEHICLE_QUERIES["type"]: "Van",
            VEHICLE_QUERIES["commercial"]: "Yes, it appears to be a commercial vehicle",
            VEHICLE_QUERIES["logo"]: "FedEx logo visible",
        }

        async def mock_inference(model, image, prompt):
            return responses.get(prompt, "")

        with patch.object(extractor, "_run_inference", side_effect=mock_inference):
            image = Image.new("RGB", (640, 480), color="white")
            bbox = (100, 100, 300, 250)

            attrs = await extractor.extract_vehicle_attributes(model_tuple, image, bbox)

            assert attrs.color == "white"
            assert attrs.vehicle_type == "van"
            assert attrs.is_commercial is True
            assert attrs.commercial_text == "FedEx logo visible"
            assert attrs.confidence == 0.8

    @pytest.mark.asyncio
    async def test_extract_person_attributes(self) -> None:
        """Test extract_person_attributes with mocked model."""
        from PIL import Image

        extractor = FlorenceExtractor()
        model_tuple = (MagicMock(), MagicMock())

        responses = {
            PERSON_QUERIES["caption"]: "A person in casual clothes",
            PERSON_QUERIES["clothing"]: "Blue jacket and jeans",
            PERSON_QUERIES["carrying"]: "Yes, carrying a backpack",
            PERSON_QUERIES["service_worker"]: "No, this is a regular person",
            PERSON_QUERIES["action"]: "Walking",
        }

        async def mock_inference(model, image, prompt):
            return responses.get(prompt, "")

        with patch.object(extractor, "_run_inference", side_effect=mock_inference):
            image = Image.new("RGB", (640, 480), color="gray")
            bbox = (200, 50, 350, 400)

            attrs = await extractor.extract_person_attributes(model_tuple, image, bbox)

            assert attrs.clothing == "Blue jacket and jeans"
            assert "backpack" in attrs.carrying
            assert attrs.is_service_worker is False
            assert attrs.action == "Walking"
            assert attrs.confidence == 0.8

    @pytest.mark.asyncio
    async def test_extract_scene_analysis(self) -> None:
        """Test extract_scene_analysis with mocked model."""
        from PIL import Image

        extractor = FlorenceExtractor()
        model_tuple = (MagicMock(), MagicMock())

        responses = {
            SCENE_QUERIES["caption"]: "A backyard with a fence",
            SCENE_QUERIES["tools"]: "Yes, a ladder visible against the fence",
            SCENE_QUERIES["abandoned"]: "No abandoned items",
            SCENE_QUERIES["unusual"]: "Yes, ladder in unusual position",
        }

        async def mock_inference(model, image, prompt):
            return responses.get(prompt, "")

        with patch.object(extractor, "_run_inference", side_effect=mock_inference):
            image = Image.new("RGB", (1920, 1080), color="green")

            analysis = await extractor.extract_scene_analysis(model_tuple, image)

            assert "ladder" in " ".join(analysis.tools_detected).lower()
            assert analysis.abandoned_items == []
            assert len(analysis.unusual_objects) > 0
            assert analysis.confidence == 0.8
            assert analysis.has_security_concerns() is True

    @pytest.mark.asyncio
    async def test_extract_environment_context(self) -> None:
        """Test extract_environment_context with mocked model."""
        from PIL import Image

        extractor = FlorenceExtractor()
        model_tuple = (MagicMock(), MagicMock())

        responses = {
            ENVIRONMENT_QUERIES["time_of_day"]: "It appears to be nighttime based on darkness",
            ENVIRONMENT_QUERIES["artificial_light"]: "Yes, flashlight beam visible",
            ENVIRONMENT_QUERIES["weather"]: "Clear skies",
        }

        async def mock_inference(model, image, prompt):
            return responses.get(prompt, "")

        with patch.object(extractor, "_run_inference", side_effect=mock_inference):
            image = Image.new("RGB", (640, 480), color="black")

            context = await extractor.extract_environment_context(model_tuple, image)

            assert context.time_of_day == "night"
            assert context.artificial_light is True
            assert context.weather == "Clear skies"
            assert context.confidence == 0.8
            assert context.is_suspicious_lighting() is True

    @pytest.mark.asyncio
    async def test_extract_handles_errors(self) -> None:
        """Test that extraction handles errors gracefully."""
        from PIL import Image

        extractor = FlorenceExtractor()
        model_tuple = (MagicMock(), MagicMock())

        async def mock_inference_error(model, image, prompt):
            raise RuntimeError("Model failed")

        with patch.object(extractor, "_run_inference", side_effect=mock_inference_error):
            image = Image.new("RGB", (640, 480), color="white")
            bbox = (0, 0, 100, 100)

            # Should return empty attributes with 0 confidence
            attrs = await extractor.extract_vehicle_attributes(model_tuple, image, bbox)
            assert attrs.confidence == 0.0

            person_attrs = await extractor.extract_person_attributes(model_tuple, image, bbox)
            assert person_attrs.confidence == 0.0

            scene = await extractor.extract_scene_analysis(model_tuple, image)
            assert scene.confidence == 0.0

            env = await extractor.extract_environment_context(model_tuple, image)
            assert env.confidence == 0.0


class TestFlorenceExtractorGlobal:
    """Tests for global FlorenceExtractor instance."""

    def setup_method(self) -> None:
        """Reset extractor before each test."""
        reset_florence_extractor()

    def teardown_method(self) -> None:
        """Reset extractor after each test."""
        reset_florence_extractor()

    def test_get_florence_extractor_singleton(self) -> None:
        """Test that get_florence_extractor returns singleton."""
        extractor1 = get_florence_extractor()
        extractor2 = get_florence_extractor()

        assert extractor1 is extractor2

    def test_reset_florence_extractor(self) -> None:
        """Test that reset_florence_extractor resets the singleton."""
        extractor1 = get_florence_extractor()
        reset_florence_extractor()
        extractor2 = get_florence_extractor()

        assert extractor1 is not extractor2


class TestFlorenceLoader:
    """Tests for florence_loader module."""

    @pytest.mark.asyncio
    async def test_load_florence_model_import_error(self) -> None:
        """Test that load_florence_model raises ImportError when transformers missing."""
        with patch.dict("sys.modules", {"transformers": None}):
            import sys

            if "transformers" in sys.modules:
                del sys.modules["transformers"]

            with (
                patch(
                    "builtins.__import__",
                    side_effect=ImportError("No module named 'transformers'"),
                ),
                pytest.raises(ImportError),
            ):
                await load_florence_model("microsoft/Florence-2-large")

    @pytest.mark.asyncio
    async def test_load_florence_model_runtime_error(self) -> None:
        """Test that load_florence_model raises RuntimeError on failure."""
        mock_auto_model = MagicMock()
        mock_auto_model.from_pretrained.side_effect = ValueError("Model load failed")

        mock_auto_processor = MagicMock()

        with (
            patch.dict(
                "sys.modules",
                {
                    "transformers": MagicMock(
                        AutoModelForCausalLM=mock_auto_model,
                        AutoProcessor=mock_auto_processor,
                    ),
                    "torch": MagicMock(cuda=MagicMock(is_available=MagicMock(return_value=False))),
                },
            ),
            pytest.raises(RuntimeError, match="Failed to load Florence-2 model"),
        ):
            await load_florence_model("microsoft/Florence-2-large")


class TestFlorenceModelZooRegistration:
    """Tests for Florence-2 model registration in Model Zoo."""

    def setup_method(self) -> None:
        """Reset model zoo before each test."""
        reset_model_zoo()

    def teardown_method(self) -> None:
        """Reset model zoo after each test."""
        reset_model_zoo()

    def test_florence_2_in_model_zoo(self) -> None:
        """Test that Florence-2-large is registered in MODEL_ZOO."""
        zoo = get_model_zoo()

        assert "florence-2-large" in zoo

    def test_florence_2_config(self) -> None:
        """Test Florence-2-large configuration.

        Note: Florence-2 is now disabled in model_zoo because it runs as a
        dedicated service (ai-florence) instead of being loaded on-demand.
        """
        config = get_model_config("florence-2-large")

        assert config is not None
        assert config.name == "florence-2-large"
        assert config.path == "/models/model-zoo/florence-2-large"
        assert config.category == "vision-language"
        assert config.vram_mb == 1200
        # Disabled because Florence-2 runs as dedicated ai-florence service
        assert config.enabled is False
        assert config.available is False

    def test_florence_2_load_fn(self) -> None:
        """Test Florence-2-large load function is set correctly."""
        config = get_model_config("florence-2-large")

        assert config is not None
        assert config.load_fn is load_florence_model


class TestQueryConstants:
    """Tests for query constant definitions."""

    def test_vehicle_queries_defined(self) -> None:
        """Test VEHICLE_QUERIES contains expected keys."""
        expected_keys = ["caption", "color", "type", "commercial", "logo"]
        for key in expected_keys:
            assert key in VEHICLE_QUERIES

    def test_person_queries_defined(self) -> None:
        """Test PERSON_QUERIES contains expected keys."""
        expected_keys = ["caption", "clothing", "carrying", "service_worker", "action"]
        for key in expected_keys:
            assert key in PERSON_QUERIES

    def test_scene_queries_defined(self) -> None:
        """Test SCENE_QUERIES contains expected keys."""
        expected_keys = ["caption", "unusual", "tools", "abandoned"]
        for key in expected_keys:
            assert key in SCENE_QUERIES

    def test_environment_queries_defined(self) -> None:
        """Test ENVIRONMENT_QUERIES contains expected keys."""
        expected_keys = ["time_of_day", "artificial_light", "weather"]
        for key in expected_keys:
            assert key in ENVIRONMENT_QUERIES
