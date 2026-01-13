"""Unit tests for VisionExtractor service.

Tests cover:
- Data classes (VehicleAttributes, PersonAttributes, SceneAnalysis, etc.)
- VisionExtractor class methods
- Formatting functions for Nemotron prompt
- Global service singleton
"""

from __future__ import annotations

import pytest

from backend.services.vision_extractor import (
    PERSON_CLASS,
    SECURITY_VQA_QUERIES,
    VEHICLE_CLASSES,
    BatchExtractionResult,
    EnvironmentContext,
    PersonAttributes,
    SceneAnalysis,
    VehicleAttributes,
    VisionExtractor,
    format_batch_extraction_result,
    format_detections_with_attributes,
    format_environment_context,
    format_person_attributes,
    format_scene_analysis,
    format_vehicle_attributes,
    get_vision_extractor,
    reset_vision_extractor,
)


class TestVehicleAttributes:
    """Tests for VehicleAttributes dataclass."""

    def test_vehicle_attributes_creation(self) -> None:
        """Test creating VehicleAttributes with all fields."""
        attrs = VehicleAttributes(
            color="white",
            vehicle_type="sedan",
            is_commercial=False,
            commercial_text=None,
            caption="A white sedan parked in the driveway",
        )

        assert attrs.color == "white"
        assert attrs.vehicle_type == "sedan"
        assert attrs.is_commercial is False
        assert attrs.commercial_text is None
        assert attrs.caption == "A white sedan parked in the driveway"

    def test_vehicle_attributes_commercial(self) -> None:
        """Test VehicleAttributes for commercial vehicle."""
        attrs = VehicleAttributes(
            color="white",
            vehicle_type="van",
            is_commercial=True,
            commercial_text="FedEx",
            caption="A white FedEx delivery van",
        )

        assert attrs.is_commercial is True
        assert attrs.commercial_text == "FedEx"

    def test_vehicle_attributes_frozen(self) -> None:
        """Test VehicleAttributes is immutable."""
        attrs = VehicleAttributes(
            color="red",
            vehicle_type="SUV",
            is_commercial=False,
            commercial_text=None,
            caption="Red SUV",
        )

        with pytest.raises(Exception):  # FrozenInstanceError
            attrs.color = "blue"  # type: ignore[misc]


class TestPersonAttributes:
    """Tests for PersonAttributes dataclass."""

    def test_person_attributes_creation(self) -> None:
        """Test creating PersonAttributes with all fields."""
        attrs = PersonAttributes(
            clothing="blue jacket, dark pants",
            carrying="backpack",
            is_service_worker=False,
            action="walking",
            caption="Person walking towards the house",
        )

        assert attrs.clothing == "blue jacket, dark pants"
        assert attrs.carrying == "backpack"
        assert attrs.is_service_worker is False
        assert attrs.action == "walking"

    def test_person_attributes_service_worker(self) -> None:
        """Test PersonAttributes for service worker."""
        attrs = PersonAttributes(
            clothing="brown uniform",
            carrying="package",
            is_service_worker=True,
            action="delivering",
            caption="Delivery worker with package",
        )

        assert attrs.is_service_worker is True

    def test_person_attributes_frozen(self) -> None:
        """Test PersonAttributes is immutable."""
        attrs = PersonAttributes(
            clothing="red shirt",
            carrying=None,
            is_service_worker=False,
            action="standing",
            caption="Person standing",
        )

        with pytest.raises(Exception):
            attrs.action = "running"  # type: ignore[misc]


class TestSceneAnalysis:
    """Tests for SceneAnalysis dataclass."""

    def test_scene_analysis_creation(self) -> None:
        """Test creating SceneAnalysis with all fields."""
        scene = SceneAnalysis(
            unusual_objects=["ladder against fence"],
            tools_detected=["ladder"],
            abandoned_items=["package near door"],
            scene_description="Residential driveway at night",
        )

        assert scene.unusual_objects == ["ladder against fence"]
        assert scene.tools_detected == ["ladder"]
        assert scene.abandoned_items == ["package near door"]

    def test_scene_analysis_defaults(self) -> None:
        """Test SceneAnalysis default values."""
        scene = SceneAnalysis()

        assert scene.unusual_objects == []
        assert scene.tools_detected == []
        assert scene.abandoned_items == []
        assert scene.scene_description == ""

    def test_scene_analysis_mutable(self) -> None:
        """Test SceneAnalysis can be modified (not frozen)."""
        scene = SceneAnalysis()
        scene.tools_detected.append("crowbar")

        assert "crowbar" in scene.tools_detected


class TestEnvironmentContext:
    """Tests for EnvironmentContext dataclass."""

    def test_environment_context_creation(self) -> None:
        """Test creating EnvironmentContext with all fields."""
        env = EnvironmentContext(
            time_of_day="night",
            artificial_light=True,
            weather="clear",
        )

        assert env.time_of_day == "night"
        assert env.artificial_light is True
        assert env.weather == "clear"

    def test_environment_context_day(self) -> None:
        """Test EnvironmentContext for daytime."""
        env = EnvironmentContext(
            time_of_day="day",
            artificial_light=False,
            weather=None,
        )

        assert env.time_of_day == "day"
        assert env.artificial_light is False
        assert env.weather is None

    def test_environment_context_frozen(self) -> None:
        """Test EnvironmentContext is immutable."""
        env = EnvironmentContext(
            time_of_day="dusk",
            artificial_light=False,
            weather="cloudy",
        )

        with pytest.raises(Exception):
            env.time_of_day = "night"  # type: ignore[misc]


class TestBatchExtractionResult:
    """Tests for BatchExtractionResult dataclass."""

    def test_batch_extraction_result_defaults(self) -> None:
        """Test BatchExtractionResult default values."""
        result = BatchExtractionResult()

        assert result.vehicle_attributes == {}
        assert result.person_attributes == {}
        assert result.scene_analysis is None
        assert result.environment_context is None

    def test_batch_extraction_result_with_data(self) -> None:
        """Test BatchExtractionResult with actual data."""
        vehicle = VehicleAttributes(
            color="black",
            vehicle_type="truck",
            is_commercial=False,
            commercial_text=None,
            caption="Black truck",
        )
        person = PersonAttributes(
            clothing="gray hoodie",
            carrying=None,
            is_service_worker=False,
            action="walking",
            caption="Person in hoodie",
        )
        scene = SceneAnalysis(scene_description="Night scene")
        env = EnvironmentContext(time_of_day="night", artificial_light=False, weather=None)

        result = BatchExtractionResult(
            vehicle_attributes={"v1": vehicle},
            person_attributes={"p1": person},
            scene_analysis=scene,
            environment_context=env,
        )

        assert len(result.vehicle_attributes) == 1
        assert len(result.person_attributes) == 1
        assert result.scene_analysis is not None
        assert result.environment_context is not None


class TestConstants:
    """Tests for module constants."""

    def test_vehicle_classes(self) -> None:
        """Test VEHICLE_CLASSES contains expected classes."""
        assert "car" in VEHICLE_CLASSES
        assert "truck" in VEHICLE_CLASSES
        assert "bus" in VEHICLE_CLASSES
        assert "motorcycle" in VEHICLE_CLASSES

    def test_person_class(self) -> None:
        """Test PERSON_CLASS is 'person'."""
        assert PERSON_CLASS == "person"


class TestVisionExtractorInit:
    """Tests for VisionExtractor initialization."""

    def setup_method(self) -> None:
        """Reset service before each test."""
        reset_vision_extractor()

    def teardown_method(self) -> None:
        """Reset service after each test."""
        reset_vision_extractor()

    def test_vision_extractor_creation(self) -> None:
        """Test VisionExtractor can be created."""
        extractor = VisionExtractor()
        assert extractor is not None

    def test_global_service_singleton(self) -> None:
        """Test global service singleton."""
        extractor1 = get_vision_extractor()
        extractor2 = get_vision_extractor()

        assert extractor1 is extractor2

    def test_reset_vision_extractor(self) -> None:
        """Test reset clears singleton."""
        extractor1 = get_vision_extractor()
        reset_vision_extractor()
        extractor2 = get_vision_extractor()

        assert extractor1 is not extractor2


class TestVisionExtractorHelpers:
    """Tests for VisionExtractor helper methods."""

    def test_parse_yes_no_yes(self) -> None:
        """Test _parse_yes_no with yes responses."""
        extractor = VisionExtractor()

        assert extractor._parse_yes_no("yes") is True
        assert extractor._parse_yes_no("Yes, it is") is True
        assert extractor._parse_yes_no("YES") is True
        assert extractor._parse_yes_no("yes, a delivery vehicle") is True

    def test_parse_yes_no_no(self) -> None:
        """Test _parse_yes_no with no responses."""
        extractor = VisionExtractor()

        assert extractor._parse_yes_no("no") is False
        assert extractor._parse_yes_no("No, it is not") is False
        assert extractor._parse_yes_no("not visible") is False

    def test_parse_none_response_nothing(self) -> None:
        """Test _parse_none_response with nothing responses."""
        extractor = VisionExtractor()

        assert extractor._parse_none_response("nothing") is None
        assert extractor._parse_none_response("none") is None
        assert extractor._parse_none_response("not carrying anything") is None
        assert extractor._parse_none_response("empty") is None

    def test_parse_none_response_something(self) -> None:
        """Test _parse_none_response with actual content."""
        extractor = VisionExtractor()

        assert extractor._parse_none_response("backpack") == "backpack"
        assert extractor._parse_none_response("carrying a box") == "carrying a box"

    def test_is_negative_response(self) -> None:
        """Test _is_negative_response."""
        extractor = VisionExtractor()

        assert extractor._is_negative_response("no, nothing visible") is True
        assert extractor._is_negative_response("none detected") is True
        assert extractor._is_negative_response("not present") is True
        assert extractor._is_negative_response("yes, ladder visible") is False
        assert extractor._is_negative_response("ladder against wall") is False

    def test_crop_image(self) -> None:
        """Test _crop_image adds padding and clamps to bounds."""
        from PIL import Image

        extractor = VisionExtractor()
        img = Image.new("RGB", (200, 200), color="red")

        # Crop with 10% padding
        cropped = extractor._crop_image(img, (50, 50, 100, 100))

        # Original box is 50x50, with 10% padding = 5px each side
        # So cropped should be 60x60 (50 + 5 + 5)
        assert cropped.size[0] == 60
        assert cropped.size[1] == 60

    def test_crop_image_clamps_to_bounds(self) -> None:
        """Test _crop_image clamps to image boundaries."""
        from PIL import Image

        extractor = VisionExtractor()
        img = Image.new("RGB", (100, 100), color="blue")

        # Crop near edge - padding should be clamped
        cropped = extractor._crop_image(img, (0, 0, 50, 50))

        # Left/top padding would go negative, clamped to 0
        assert cropped.size[0] <= 55  # 50 + 5 padding max
        assert cropped.size[1] <= 55


class TestFormatVehicleAttributes:
    """Tests for format_vehicle_attributes function."""

    def test_format_vehicle_basic(self) -> None:
        """Test basic vehicle formatting."""
        attrs = VehicleAttributes(
            color="white",
            vehicle_type="sedan",
            is_commercial=False,
            commercial_text=None,
            caption="A white sedan",
        )

        result = format_vehicle_attributes(attrs)

        assert "Vehicle: A white sedan" in result
        assert "Color: white" in result
        assert "Type: sedan" in result

    def test_format_vehicle_commercial(self) -> None:
        """Test commercial vehicle formatting."""
        attrs = VehicleAttributes(
            color="white",
            vehicle_type="van",
            is_commercial=True,
            commercial_text="Amazon",
            caption="Amazon delivery van",
        )

        result = format_vehicle_attributes(attrs)

        assert "Commercial vehicle (Amazon)" in result

    def test_format_vehicle_with_id(self) -> None:
        """Test vehicle formatting with detection ID."""
        attrs = VehicleAttributes(
            color="black",
            vehicle_type="SUV",
            is_commercial=False,
            commercial_text=None,
            caption="Black SUV",
        )

        result = format_vehicle_attributes(attrs, detection_id="v123")

        assert "[v123]" in result


class TestFormatPersonAttributes:
    """Tests for format_person_attributes function."""

    def test_format_person_basic(self) -> None:
        """Test basic person formatting."""
        attrs = PersonAttributes(
            clothing="blue jacket",
            carrying="backpack",
            is_service_worker=False,
            action="walking",
            caption="Person walking",
        )

        result = format_person_attributes(attrs)

        assert "Person: Person walking" in result
        assert "Wearing: blue jacket" in result
        assert "Carrying: backpack" in result
        assert "Action: walking" in result

    def test_format_person_service_worker(self) -> None:
        """Test service worker formatting."""
        attrs = PersonAttributes(
            clothing="brown uniform",
            carrying="package",
            is_service_worker=True,
            action="delivering",
            caption="Delivery worker",
        )

        result = format_person_attributes(attrs)

        assert "service/delivery worker" in result

    def test_format_person_with_id(self) -> None:
        """Test person formatting with detection ID."""
        attrs = PersonAttributes(
            clothing="red shirt",
            carrying=None,
            is_service_worker=False,
            action="standing",
            caption="Person standing",
        )

        result = format_person_attributes(attrs, detection_id="p456")

        assert "[p456]" in result


class TestFormatSceneAnalysis:
    """Tests for format_scene_analysis function."""

    def test_format_scene_with_elements(self) -> None:
        """Test scene formatting with detected elements."""
        scene = SceneAnalysis(
            unusual_objects=["ladder against fence"],
            tools_detected=["ladder", "crowbar"],
            abandoned_items=["package"],
            scene_description="Night scene in driveway",
        )

        result = format_scene_analysis(scene)

        assert "Scene: Night scene in driveway" in result
        assert "Unusual objects: ladder against fence" in result
        assert "Tools detected: ladder, crowbar" in result
        assert "Abandoned items: package" in result

    def test_format_scene_empty(self) -> None:
        """Test scene formatting with no elements."""
        scene = SceneAnalysis()

        result = format_scene_analysis(scene)

        assert "No notable scene elements detected" in result


class TestFormatEnvironmentContext:
    """Tests for format_environment_context function."""

    def test_format_environment_night(self) -> None:
        """Test night environment formatting."""
        env = EnvironmentContext(
            time_of_day="night",
            artificial_light=True,
            weather="clear",
        )

        result = format_environment_context(env)

        assert "Time of day: night" in result
        assert "Artificial light source detected" in result
        assert "Weather: clear" in result

    def test_format_environment_day(self) -> None:
        """Test day environment formatting."""
        env = EnvironmentContext(
            time_of_day="day",
            artificial_light=False,
            weather=None,
        )

        result = format_environment_context(env)

        assert "Time of day: day" in result
        assert "Artificial light" not in result


class TestFormatBatchExtractionResult:
    """Tests for format_batch_extraction_result function."""

    def test_format_batch_empty(self) -> None:
        """Test formatting empty batch result."""
        result = BatchExtractionResult()

        formatted = format_batch_extraction_result(result)

        assert "No vision extraction data available" in formatted

    def test_format_batch_with_vehicles(self) -> None:
        """Test formatting batch with vehicles."""
        vehicle = VehicleAttributes(
            color="red",
            vehicle_type="truck",
            is_commercial=False,
            commercial_text=None,
            caption="Red truck",
        )
        result = BatchExtractionResult(vehicle_attributes={"v1": vehicle})

        formatted = format_batch_extraction_result(result)

        assert "## Vehicles" in formatted
        assert "Red truck" in formatted

    def test_format_batch_with_persons(self) -> None:
        """Test formatting batch with persons."""
        person = PersonAttributes(
            clothing="black hoodie",
            carrying=None,
            is_service_worker=False,
            action="walking",
            caption="Person in hoodie",
        )
        result = BatchExtractionResult(person_attributes={"p1": person})

        formatted = format_batch_extraction_result(result)

        assert "## Persons" in formatted
        assert "Person in hoodie" in formatted

    def test_format_batch_exclude_scene(self) -> None:
        """Test formatting batch without scene analysis."""
        scene = SceneAnalysis(scene_description="Test scene")
        result = BatchExtractionResult(scene_analysis=scene)

        formatted = format_batch_extraction_result(result, include_scene=False)

        assert "## Scene Analysis" not in formatted


class TestFormatDetectionsWithAttributes:
    """Tests for format_detections_with_attributes function."""

    def test_format_detections_empty(self) -> None:
        """Test formatting empty detections."""
        result = BatchExtractionResult()

        formatted = format_detections_with_attributes([], result)

        assert "No detections" in formatted

    def test_format_detections_with_vehicle_attrs(self) -> None:
        """Test formatting detections with vehicle attributes."""
        vehicle = VehicleAttributes(
            color="blue",
            vehicle_type="sedan",
            is_commercial=True,
            commercial_text="Uber",
            caption="Blue Uber sedan",
        )
        result = BatchExtractionResult(vehicle_attributes={"det1": vehicle})

        detections = [
            {
                "detection_id": "det1",
                "class_name": "car",
                "confidence": 0.95,
                "bbox": [100, 100, 200, 200],
            }
        ]

        formatted = format_detections_with_attributes(detections, result)

        assert "car (95%)" in formatted
        assert "blue" in formatted
        assert "sedan" in formatted
        assert "commercial: Uber" in formatted

    def test_format_detections_with_person_attrs(self) -> None:
        """Test formatting detections with person attributes."""
        person = PersonAttributes(
            clothing="red jacket",
            carrying="box",
            is_service_worker=True,
            action="walking",
            caption="Delivery person",
        )
        result = BatchExtractionResult(person_attributes={"det2": person})

        detections = [
            {
                "detection_id": "det2",
                "class_name": "person",
                "confidence": 0.88,
                "bbox": [50, 50, 150, 300],
            }
        ]

        formatted = format_detections_with_attributes(detections, result)

        assert "person (88%)" in formatted
        assert "red jacket" in formatted
        assert "carrying box" in formatted
        assert "service worker" in formatted


class TestVisionExtractorExtraction:
    """Tests for VisionExtractor extraction methods."""

    def setup_method(self) -> None:
        """Reset service before each test."""
        reset_vision_extractor()

    def teardown_method(self) -> None:
        """Reset service after each test."""
        reset_vision_extractor()

    @pytest.mark.asyncio
    async def test_extract_vehicle_attributes_calls_florence(self) -> None:
        """Test extract_vehicle_attributes uses Florence-2 model."""
        from PIL import Image

        extractor = VisionExtractor()

        async def mock_query(image, task, text_input=""):
            """Mock _query_florence - now uses HTTP client, no model parameter."""
            if task == "<CAPTION>":
                return "White delivery van"
            elif "color" in text_input.lower():
                return "white"
            elif "type" in text_input.lower():
                return "van"
            elif "commercial" in text_input.lower():
                return "yes"
            elif "logo" in text_input.lower():
                return "FedEx"
            return ""

        extractor._query_florence = mock_query

        img = Image.new("RGB", (100, 100), color="white")
        result = await extractor.extract_vehicle_attributes(img)

        assert result.caption == "White delivery van"
        assert result.color == "white"
        assert result.vehicle_type == "van"
        assert result.is_commercial is True
        assert result.commercial_text == "FedEx"

    @pytest.mark.asyncio
    async def test_extract_person_attributes_calls_florence(self) -> None:
        """Test extract_person_attributes uses Florence-2 model."""
        from PIL import Image

        extractor = VisionExtractor()

        async def mock_query(image, task, text_input=""):
            """Mock _query_florence - now uses HTTP client, no model parameter."""
            if task == "<CAPTION>":
                return "Person walking towards door"
            elif "wearing" in text_input.lower():
                return "blue jacket"
            elif "carrying" in text_input.lower():
                return "backpack"
            elif "service worker" in text_input.lower():
                return "no"
            elif "doing" in text_input.lower():
                return "walking"
            return ""

        extractor._query_florence = mock_query

        img = Image.new("RGB", (100, 100), color="blue")
        result = await extractor.extract_person_attributes(img)

        assert "Person walking" in result.caption
        assert result.clothing == "blue jacket"
        assert result.carrying == "backpack"
        assert result.is_service_worker is False
        assert result.action == "walking"

    @pytest.mark.asyncio
    async def test_extract_scene_analysis(self) -> None:
        """Test extract_scene_analysis."""
        from PIL import Image

        extractor = VisionExtractor()

        async def mock_query(image, task, text_input=""):
            """Mock _query_florence - now uses HTTP client, no model parameter."""
            if task == "<CAPTION>":
                return "Night scene with driveway"
            elif "unusual" in text_input.lower():
                return "ladder visible"
            elif "tools" in text_input.lower():
                return "ladder"
            elif "abandoned" in text_input.lower():
                return "no"
            return ""

        extractor._query_florence = mock_query

        img = Image.new("RGB", (200, 200), color="black")
        result = await extractor.extract_scene_analysis(img)

        assert "Night scene" in result.scene_description
        assert "ladder visible" in result.unusual_objects
        assert "ladder" in result.tools_detected

    @pytest.mark.asyncio
    async def test_extract_scene_caption(self) -> None:
        """Test extract_scene_caption uses DETAILED_CAPTION_TASK."""
        from PIL import Image

        extractor = VisionExtractor()

        async def mock_query(image, task, text_input=""):
            """Mock _query_florence - returns detailed caption for DETAILED_CAPTION_TASK."""
            if task == "<DETAILED_CAPTION>":
                return "A residential driveway at night with a white sedan parked near the garage. The scene is illuminated by a porch light. A person in a dark jacket is walking toward the front door carrying a package."
            elif task == "<CAPTION>":
                return "Night scene with car and person"
            return ""

        extractor._query_florence = mock_query

        img = Image.new("RGB", (640, 480), color="black")
        result = await extractor.extract_scene_caption(img)

        assert "residential driveway" in result
        assert "white sedan" in result
        assert "porch light" in result
        assert "dark jacket" in result

    @pytest.mark.asyncio
    async def test_extract_scene_caption_empty_response(self) -> None:
        """Test extract_scene_caption handles empty response gracefully."""
        from PIL import Image

        extractor = VisionExtractor()

        async def mock_query(image, task, text_input=""):
            """Mock _query_florence - returns empty string."""
            return ""

        extractor._query_florence = mock_query

        img = Image.new("RGB", (640, 480), color="black")
        result = await extractor.extract_scene_caption(img)

        assert result == ""

    @pytest.mark.asyncio
    async def test_extract_scene_caption_strips_whitespace(self) -> None:
        """Test extract_scene_caption strips leading/trailing whitespace."""
        from PIL import Image

        extractor = VisionExtractor()

        async def mock_query(image, task, text_input=""):
            """Mock _query_florence - returns caption with whitespace."""
            if task == "<DETAILED_CAPTION>":
                return "  A detailed scene description with extra spaces  \n"
            return ""

        extractor._query_florence = mock_query

        img = Image.new("RGB", (640, 480), color="black")
        result = await extractor.extract_scene_caption(img)

        assert result == "A detailed scene description with extra spaces"
        assert not result.startswith(" ")
        assert not result.endswith(" ")
        assert not result.endswith("\n")

    @pytest.mark.asyncio
    async def test_extract_environment_context(self) -> None:
        """Test extract_environment_context."""
        from PIL import Image

        extractor = VisionExtractor()

        async def mock_query(image, task, text_input=""):
            """Mock _query_florence - now uses HTTP client, no model parameter."""
            if "time of day" in text_input.lower():
                return "night"
            elif "flashlight" in text_input.lower():
                return "yes"
            elif "weather" in text_input.lower():
                return "clear"
            return ""

        extractor._query_florence = mock_query

        img = Image.new("RGB", (200, 200), color="black")
        result = await extractor.extract_environment_context(img)

        assert result.time_of_day == "night"
        assert result.artificial_light is True
        assert result.weather == "clear"

    @pytest.mark.asyncio
    async def test_extract_batch_attributes(self) -> None:
        """Test extract_batch_attributes processes multiple detections."""
        from PIL import Image

        extractor = VisionExtractor()

        # Track calls to identify context
        call_count = {"vehicle": 0, "person": 0}

        async def mock_extract_vehicle(image):
            """Mock _extract_vehicle_internal - uses HTTP client."""
            call_count["vehicle"] += 1
            return VehicleAttributes(
                color="white",
                vehicle_type="sedan",
                is_commercial=False,
                commercial_text=None,
                caption="White sedan",
            )

        async def mock_extract_person(image):
            """Mock _extract_person_internal - uses HTTP client."""
            call_count["person"] += 1
            return PersonAttributes(
                clothing="blue shirt",
                carrying=None,
                is_service_worker=False,
                action="walking",
                caption="Person walking",
            )

        async def mock_extract_scene(image):
            """Mock _extract_scene_internal - uses HTTP client."""
            return SceneAnalysis(scene_description="Test scene")

        async def mock_extract_env(image):
            """Mock _extract_environment_internal - uses HTTP client."""
            return EnvironmentContext(
                time_of_day="day",
                artificial_light=False,
                weather=None,
            )

        extractor._extract_vehicle_internal = mock_extract_vehicle
        extractor._extract_person_internal = mock_extract_person
        extractor._extract_scene_internal = mock_extract_scene
        extractor._extract_environment_internal = mock_extract_env

        img = Image.new("RGB", (400, 400), color="gray")

        detections = [
            {"class_name": "car", "bbox": [10, 10, 100, 100], "detection_id": "v1"},
            {"class_name": "person", "bbox": [200, 200, 300, 400], "detection_id": "p1"},
            {"class_name": "truck", "bbox": [50, 50, 150, 150], "detection_id": "v2"},
        ]

        result = await extractor.extract_batch_attributes(img, detections)

        # Should have 2 vehicles and 1 person
        assert len(result.vehicle_attributes) == 2
        assert len(result.person_attributes) == 1
        assert result.scene_analysis is not None
        assert result.environment_context is not None
        assert call_count["vehicle"] == 2
        assert call_count["person"] == 1


class TestSecurityVQAQueries:
    """Tests for SECURITY_VQA_QUERIES constant."""

    def test_security_vqa_queries_contains_expected_keys(self) -> None:
        """Test SECURITY_VQA_QUERIES contains all expected security question keys."""
        expected_keys = [
            "looking_at_camera",
            "weapons_or_tools",
            "face_covering",
            "bags_or_packages",
            "gloves",
            "interaction_with_property",
            "flashlight",
            "crouching_or_hiding",
        ]
        for key in expected_keys:
            assert key in SECURITY_VQA_QUERIES, f"Missing key: {key}"

    def test_security_vqa_queries_all_are_questions(self) -> None:
        """Test all security VQA queries end with question marks."""
        for key, question in SECURITY_VQA_QUERIES.items():
            assert question.endswith("?"), f"Query '{key}' should end with '?'"

    def test_security_vqa_queries_not_empty(self) -> None:
        """Test SECURITY_VQA_QUERIES is not empty."""
        assert len(SECURITY_VQA_QUERIES) >= 5, "Should have at least 5 security queries"


class TestVisionExtractorVQA:
    """Tests for VisionExtractor VQA methods."""

    def setup_method(self) -> None:
        """Reset service before each test."""
        reset_vision_extractor()

    def teardown_method(self) -> None:
        """Reset service after each test."""
        reset_vision_extractor()

    @pytest.mark.asyncio
    async def test_extract_with_vqa_returns_answers(self) -> None:
        """Test extract_with_vqa returns dictionary of question-answer pairs."""
        from PIL import Image

        extractor = VisionExtractor()

        async def mock_query(image, task, text_input=""):
            """Mock _query_florence for VQA queries."""
            if "looking at the camera" in text_input.lower():
                return "Yes, the person is looking directly at the camera"
            elif "weapons" in text_input.lower():
                return "No weapons visible"
            elif "mask" in text_input.lower():
                return "The person is not wearing a mask"
            return ""

        extractor._query_florence = mock_query

        img = Image.new("RGB", (200, 200), color="black")
        questions = [
            "Is this person looking at the camera?",
            "Are there any weapons or tools visible?",
            "Is this person wearing a mask or face covering?",
        ]

        result = await extractor.extract_with_vqa(img, questions)

        assert len(result) == 3
        assert "Is this person looking at the camera?" in result
        assert "Yes" in result["Is this person looking at the camera?"]

    @pytest.mark.asyncio
    async def test_extract_with_vqa_filters_empty_answers(self) -> None:
        """Test extract_with_vqa filters out empty answers."""
        from PIL import Image

        extractor = VisionExtractor()

        async def mock_query(image, task, text_input=""):
            """Mock _query_florence - some questions return empty."""
            if "looking at the camera" in text_input.lower():
                return "Yes"
            elif "weapons" in text_input.lower():
                return ""  # Empty answer
            elif "mask" in text_input.lower():
                return "   "  # Whitespace only
            return ""

        extractor._query_florence = mock_query

        img = Image.new("RGB", (200, 200), color="black")
        questions = [
            "Is this person looking at the camera?",
            "Are there any weapons or tools visible?",
            "Is this person wearing a mask or face covering?",
        ]

        result = await extractor.extract_with_vqa(img, questions)

        # Only one question should have an answer
        assert len(result) == 1
        assert "Is this person looking at the camera?" in result

    @pytest.mark.asyncio
    async def test_extract_with_vqa_with_bbox(self) -> None:
        """Test extract_with_vqa crops image when bbox provided."""
        from PIL import Image

        extractor = VisionExtractor()
        crop_called = {"called": False, "bbox": None}

        original_crop = extractor._crop_image

        def mock_crop(image, bbox):
            crop_called["called"] = True
            crop_called["bbox"] = bbox
            return original_crop(image, bbox)

        extractor._crop_image = mock_crop

        async def mock_query(image, task, text_input=""):
            return "Yes"

        extractor._query_florence = mock_query

        img = Image.new("RGB", (400, 400), color="gray")
        questions = ["Is this person looking at the camera?"]
        bbox = (100, 100, 200, 200)

        await extractor.extract_with_vqa(img, questions, bbox=bbox)

        assert crop_called["called"] is True
        assert crop_called["bbox"] == bbox

    @pytest.mark.asyncio
    async def test_extract_with_vqa_empty_questions_list(self) -> None:
        """Test extract_with_vqa handles empty questions list."""
        from PIL import Image

        extractor = VisionExtractor()

        img = Image.new("RGB", (200, 200), color="black")

        result = await extractor.extract_with_vqa(img, [])

        assert result == {}

    @pytest.mark.asyncio
    async def test_extract_with_vqa_strips_whitespace(self) -> None:
        """Test extract_with_vqa strips leading/trailing whitespace from answers."""
        from PIL import Image

        extractor = VisionExtractor()

        async def mock_query(image, task, text_input=""):
            return "  Yes, looking at camera  \n"

        extractor._query_florence = mock_query

        img = Image.new("RGB", (200, 200), color="black")
        questions = ["Is this person looking at the camera?"]

        result = await extractor.extract_with_vqa(img, questions)

        assert result["Is this person looking at the camera?"] == "Yes, looking at camera"

    @pytest.mark.asyncio
    async def test_extract_security_vqa_uses_predefined_questions(self) -> None:
        """Test extract_security_vqa uses SECURITY_VQA_QUERIES."""
        from PIL import Image

        extractor = VisionExtractor()
        asked_questions = []

        async def mock_query(image, task, text_input=""):
            asked_questions.append(text_input)
            return "Yes"

        extractor._query_florence = mock_query

        img = Image.new("RGB", (200, 200), color="black")

        await extractor.extract_security_vqa(img)

        # Should have asked all security questions
        assert len(asked_questions) == len(SECURITY_VQA_QUERIES)
        for question in SECURITY_VQA_QUERIES.values():
            assert question in asked_questions

    @pytest.mark.asyncio
    async def test_extract_security_vqa_with_bbox(self) -> None:
        """Test extract_security_vqa passes bbox to extract_with_vqa."""
        from PIL import Image

        extractor = VisionExtractor()
        crop_called = {"called": False}

        original_crop = extractor._crop_image

        def mock_crop(image, bbox):
            crop_called["called"] = True
            return original_crop(image, bbox)

        extractor._crop_image = mock_crop

        async def mock_query(image, task, text_input=""):
            return "Yes"

        extractor._query_florence = mock_query

        img = Image.new("RGB", (400, 400), color="gray")
        bbox = (50, 50, 150, 150)

        await extractor.extract_security_vqa(img, bbox=bbox)

        assert crop_called["called"] is True
