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
    clean_vqa_output,
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

    def test_vehicle_attributes_to_dict(self) -> None:
        """Test VehicleAttributes to_dict method."""
        attrs = VehicleAttributes(
            color="white",
            vehicle_type="sedan",
            is_commercial=True,
            commercial_text="Uber",
            caption="White Uber sedan",
        )

        result = attrs.to_dict()

        assert result["color"] == "white"
        assert result["vehicle_type"] == "sedan"
        assert result["is_commercial"] is True
        assert result["commercial_text"] == "Uber"
        assert result["caption"] == "White Uber sedan"


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

    def test_person_attributes_to_dict(self) -> None:
        """Test PersonAttributes to_dict method."""
        attrs = PersonAttributes(
            clothing="blue jacket",
            carrying="backpack",
            is_service_worker=True,
            action="walking",
            caption="Delivery person walking",
        )

        result = attrs.to_dict()

        assert result["clothing"] == "blue jacket"
        assert result["carrying"] == "backpack"
        assert result["is_service_worker"] is True
        assert result["action"] == "walking"
        assert result["caption"] == "Delivery person walking"


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

    def test_scene_analysis_to_dict(self) -> None:
        """Test SceneAnalysis to_dict method."""
        scene = SceneAnalysis(
            unusual_objects=["ladder"],
            tools_detected=["hammer", "drill"],
            abandoned_items=["package"],
            scene_description="Construction site",
        )

        result = scene.to_dict()

        assert result["unusual_objects"] == ["ladder"]
        assert result["tools_detected"] == ["hammer", "drill"]
        assert result["abandoned_items"] == ["package"]
        assert result["scene_description"] == "Construction site"


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

    def test_environment_context_to_dict(self) -> None:
        """Test EnvironmentContext to_dict method."""
        env = EnvironmentContext(
            time_of_day="night",
            artificial_light=True,
            weather="clear",
        )

        result = env.to_dict()

        assert result["time_of_day"] == "night"
        assert result["artificial_light"] is True
        assert result["weather"] == "clear"


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

    def test_batch_extraction_result_to_dict(self) -> None:
        """Test BatchExtractionResult to_dict method."""
        vehicle = VehicleAttributes(
            color="white",
            vehicle_type="van",
            is_commercial=True,
            commercial_text="FedEx",
            caption="FedEx van",
        )
        person = PersonAttributes(
            clothing="uniform",
            carrying="package",
            is_service_worker=True,
            action="delivering",
            caption="Delivery worker",
        )
        scene = SceneAnalysis(scene_description="Driveway")
        env = EnvironmentContext(time_of_day="day", artificial_light=False, weather="sunny")

        result = BatchExtractionResult(
            vehicle_attributes={"v1": vehicle},
            person_attributes={"p1": person},
            scene_analysis=scene,
            environment_context=env,
        )

        dict_result = result.to_dict()

        assert "vehicle_attributes" in dict_result
        assert "person_attributes" in dict_result
        assert "scene_analysis" in dict_result
        assert "environment_context" in dict_result
        assert dict_result["vehicle_attributes"]["v1"]["color"] == "white"
        assert dict_result["person_attributes"]["p1"]["clothing"] == "uniform"
        assert dict_result["scene_analysis"]["scene_description"] == "Driveway"
        assert dict_result["environment_context"]["time_of_day"] == "day"


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


class TestCleanVqaOutput:
    """Tests for clean_vqa_output function.

    This function removes Florence-2 VQA artifacts including:
    - VQA> prefix with echoed question
    - <loc_N> location tokens
    - Duplicated consecutive words
    """

    def test_clean_vqa_output_empty_string(self) -> None:
        """Test clean_vqa_output returns empty string for empty input."""
        assert clean_vqa_output("") == ""

    def test_clean_vqa_output_none_like_empty(self) -> None:
        """Test clean_vqa_output handles None-like inputs gracefully."""
        # Empty string case
        assert clean_vqa_output("") == ""

    def test_clean_vqa_output_removes_vqa_prefix(self) -> None:
        """Test clean_vqa_output removes VQA> prefix and echoed question."""
        # Full artifact from the issue description
        result = clean_vqa_output(
            "VQA>Are there any unusual objects in this scene<loc_1><loc_1><loc_998><loc_998>"
        )
        assert result == ""

        # VQA prefix with some actual answer
        result = clean_vqa_output("VQA>What tools are visible?A ladder and crowbar")
        assert result == "A ladder and crowbar"

    def test_clean_vqa_output_removes_loc_tokens(self) -> None:
        """Test clean_vqa_output removes <loc_N> location tokens."""
        # Simple case from issue description
        result = clean_vqa_output("A ladder against the wall<loc_100><loc_200>")
        assert result == "A ladder against the wall"

        # Multiple loc tokens scattered
        result = clean_vqa_output("<loc_684><loc_181><loc_999><loc_555>")
        assert result == ""

        # Loc tokens in middle of text
        result = clean_vqa_output("Person<loc_50>walking<loc_100>towards door")
        assert result == "Person walking towards door"

    def test_clean_vqa_output_removes_duplicated_words(self) -> None:
        """Test clean_vqa_output removes consecutive duplicated words."""
        # Case from issue description
        result = clean_vqa_output("tools visible visible (ladder)")
        assert result == "tools visible (ladder)"

        # Another duplication pattern from issue
        result = clean_vqa_output("etc.) etc.)")
        assert result == "etc.)"

        # Multiple duplications
        result = clean_vqa_output("the the quick brown brown fox")
        assert result == "the quick brown fox"

    def test_clean_vqa_output_case_insensitive_duplicates(self) -> None:
        """Test clean_vqa_output handles case-insensitive duplicates."""
        # Mixed case duplicates
        result = clean_vqa_output("Visible visible tools")
        assert result == "Visible tools"

        result = clean_vqa_output("NO no nothing detected")
        assert result == "NO nothing detected"

    def test_clean_vqa_output_preserves_valid_text(self) -> None:
        """Test clean_vqa_output preserves valid text without artifacts."""
        # Clean text should pass through unchanged
        assert clean_vqa_output("A ladder against the wall") == "A ladder against the wall"
        assert clean_vqa_output("Person walking towards door") == "Person walking towards door"
        assert clean_vqa_output("No unusual objects detected") == "No unusual objects detected"

    def test_clean_vqa_output_handles_whitespace(self) -> None:
        """Test clean_vqa_output normalizes whitespace."""
        # Multiple spaces
        result = clean_vqa_output("A   ladder   against   wall")
        assert result == "A ladder against wall"

        # Leading/trailing whitespace
        result = clean_vqa_output("  ladder against wall  ")
        assert result == "ladder against wall"

        # Newlines and tabs
        result = clean_vqa_output("ladder\t\tagainst\n\nwall")
        assert result == "ladder against wall"

    def test_clean_vqa_output_combined_artifacts(self) -> None:
        """Test clean_vqa_output handles multiple artifact types together."""
        # VQA prefix + loc tokens + duplicates + whitespace
        result = clean_vqa_output("VQA>Are there tools?ladder ladder visible<loc_100><loc_200>  ")
        assert result == "ladder visible"

        # Loc tokens + duplicates
        result = clean_vqa_output("tools<loc_50> visible visible<loc_100>")
        assert result == "tools visible"

    def test_clean_vqa_output_only_loc_tokens(self) -> None:
        """Test clean_vqa_output returns empty for only loc tokens."""
        result = clean_vqa_output("<loc_1><loc_2><loc_3>")
        assert result == ""

    def test_clean_vqa_output_loc_with_various_numbers(self) -> None:
        """Test clean_vqa_output handles loc tokens with various digit counts."""
        result = clean_vqa_output("test<loc_1><loc_12><loc_123><loc_1234>value")
        assert result == "test value"

    def test_clean_vqa_output_preserves_non_loc_angle_brackets(self) -> None:
        """Test clean_vqa_output preserves angle brackets that aren't loc tokens."""
        # Note: <other_tag> should be preserved (not a loc token)
        result = clean_vqa_output("text <something> more")
        assert result == "text <something> more"

    def test_clean_vqa_output_single_word(self) -> None:
        """Test clean_vqa_output handles single word input."""
        assert clean_vqa_output("ladder") == "ladder"
        assert clean_vqa_output("ladder<loc_1>") == "ladder"

    def test_clean_vqa_output_real_world_examples(self) -> None:
        """Test clean_vqa_output with real-world Florence-2 output examples."""
        # Example 1: VQA query echo with loc tokens
        result = clean_vqa_output(
            "VQA>Are there any unusual objects in this scene<loc_1><loc_1><loc_998><loc_998>"
        )
        assert result == ""

        # Example 2: Actual answer with loc tokens
        result = clean_vqa_output(
            "A suspicious person near the door<loc_684><loc_181><loc_999><loc_555>"
        )
        assert result == "A suspicious person near the door"

        # Example 3: Tools response with duplicates
        result = clean_vqa_output("ladder, crowbar visible visible")
        assert result == "ladder, crowbar visible"


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

    def test_parse_yes_no_with_yes_in_middle(self) -> None:
        """Test _parse_yes_no checks only first 20 characters for yes."""
        extractor = VisionExtractor()

        # "yes" not at start, beyond 20 chars - should be False
        assert extractor._parse_yes_no("not really but maybe yes later") is False
        # "yes" within first 20 chars
        assert extractor._parse_yes_no("it seems yes is true") is True

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

    def test_crop_image_invalid_bbox_returns_original(self) -> None:
        """Test _crop_image returns original image for invalid bbox."""
        from PIL import Image

        extractor = VisionExtractor()
        img = Image.new("RGB", (200, 200), color="green")

        # Invalid bbox (negative coords, zero dimensions, etc.)
        # Should return original image
        result = extractor._crop_image(img, (-10, -10, -5, -5))
        assert result.size == img.size

        # Zero width bbox
        result = extractor._crop_image(img, (50, 50, 50, 100))
        assert result.size == img.size

        # Zero height bbox
        result = extractor._crop_image(img, (50, 50, 100, 50))
        assert result.size == img.size


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

    def test_format_batch_exclude_environment(self) -> None:
        """Test formatting batch without environment context."""
        env = EnvironmentContext(time_of_day="night", artificial_light=True, weather="clear")
        result = BatchExtractionResult(environment_context=env)

        formatted = format_batch_extraction_result(result, include_environment=False)

        assert "## Environment" not in formatted

    def test_format_batch_with_scene_and_environment(self) -> None:
        """Test formatting batch with both scene and environment."""
        scene = SceneAnalysis(scene_description="Night scene")
        env = EnvironmentContext(time_of_day="night", artificial_light=True, weather=None)
        result = BatchExtractionResult(scene_analysis=scene, environment_context=env)

        formatted = format_batch_extraction_result(result)

        assert "## Scene Analysis" in formatted
        assert "## Environment" in formatted
        assert "Night scene" in formatted
        assert "Time of day: night" in formatted

    def test_format_batch_none_scene_with_include_true(self) -> None:
        """Test formatting when scene_analysis is None but include_scene=True."""
        result = BatchExtractionResult(scene_analysis=None)

        formatted = format_batch_extraction_result(result, include_scene=True)

        # Should not include scene section when scene_analysis is None
        assert "## Scene Analysis" not in formatted

    def test_format_batch_none_environment_with_include_true(self) -> None:
        """Test formatting when environment_context is None but include_environment=True."""
        result = BatchExtractionResult(environment_context=None)

        formatted = format_batch_extraction_result(result, include_environment=True)

        # Should not include environment section when environment_context is None
        assert "## Environment" not in formatted


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
    async def test_query_florence_handles_unavailable_error(self) -> None:
        """Test _query_florence handles FlorenceUnavailableError gracefully."""
        from PIL import Image

        from backend.services.florence_client import FlorenceUnavailableError

        extractor = VisionExtractor()

        # Mock the florence client to raise error
        async def mock_extract(image, prompt):
            raise FlorenceUnavailableError("Service is down")

        extractor._florence_client.extract = mock_extract

        img = Image.new("RGB", (100, 100), color="black")
        # Should return empty string on error, not raise
        result = await extractor._query_florence(img, "<CAPTION>")
        assert result == ""

    @pytest.mark.asyncio
    async def test_query_florence_formats_vqa_prompt(self) -> None:
        """Test _query_florence formats VQA prompts correctly."""
        from PIL import Image

        extractor = VisionExtractor()

        received_prompts = []

        async def mock_extract(image, prompt):
            received_prompts.append(prompt)
            return "test response"

        extractor._florence_client.extract = mock_extract

        img = Image.new("RGB", (100, 100), color="black")

        # VQA task with text_input should be formatted as <VQA>question
        await extractor._query_florence(img, "<VQA>", "What color is this?")
        assert received_prompts[-1] == "<VQA>What color is this?"

        # Non-VQA task should just use the task
        await extractor._query_florence(img, "<CAPTION>", "")
        assert received_prompts[-1] == "<CAPTION>"

        # Non-VQA task should ignore text_input
        await extractor._query_florence(img, "<DETAILED_CAPTION>", "ignored")
        assert received_prompts[-1] == "<DETAILED_CAPTION>"

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
    async def test_extract_vehicle_attributes_non_commercial(self) -> None:
        """Test extract_vehicle_attributes for non-commercial vehicle."""
        from PIL import Image

        extractor = VisionExtractor()

        async def mock_query(image, task, text_input=""):
            if task == "<CAPTION>":
                return "Red sedan"
            elif "color" in text_input.lower():
                return "red"
            elif "type" in text_input.lower():
                return "sedan"
            elif "commercial" in text_input.lower():
                return "no"
            return ""

        extractor._query_florence = mock_query

        img = Image.new("RGB", (100, 100), color="red")
        result = await extractor.extract_vehicle_attributes(img)

        # Commercial text query should not be called for non-commercial vehicles
        assert result.is_commercial is False
        assert result.commercial_text is None

    @pytest.mark.asyncio
    async def test_extract_vehicle_internal_commercial_text_extraction(self) -> None:
        """Test _extract_vehicle_internal extracts commercial text."""
        from PIL import Image

        extractor = VisionExtractor()

        async def mock_query(image, task, text_input=""):
            if task == "<CAPTION>":
                return "Amazon delivery van"
            elif "color" in text_input.lower():
                return "white"
            elif "type" in text_input.lower():
                return "van"
            elif "commercial" in text_input.lower():
                return "yes"
            elif "logo" in text_input.lower():
                return "Amazon Prime"
            return ""

        extractor._query_florence = mock_query

        img = Image.new("RGB", (100, 100), color="white")
        result = await extractor._extract_vehicle_internal(img)

        assert result.is_commercial is True
        assert result.commercial_text == "Amazon Prime"

    @pytest.mark.asyncio
    async def test_extract_vehicle_internal_commercial_text_none_response(self) -> None:
        """Test _extract_vehicle_internal handles 'none' commercial text."""
        from PIL import Image

        extractor = VisionExtractor()

        async def mock_query(image, task, text_input=""):
            if task == "<CAPTION>":
                return "White van"
            elif "color" in text_input.lower():
                return "white"
            elif "type" in text_input.lower():
                return "van"
            elif "commercial" in text_input.lower():
                return "yes"
            elif "logo" in text_input.lower():
                return "not visible"
            return ""

        extractor._query_florence = mock_query

        img = Image.new("RGB", (100, 100), color="white")
        result = await extractor._extract_vehicle_internal(img)

        assert result.is_commercial is True
        assert result.commercial_text is None  # "not visible" parsed as None

    @pytest.mark.asyncio
    async def test_extract_vehicle_internal_commercial_text_garbage_vqa(self) -> None:
        """Test _extract_vehicle_internal handles garbage VQA for commercial text."""
        from PIL import Image

        extractor = VisionExtractor()

        async def mock_query(image, task, text_input=""):
            if task == "<CAPTION>":
                return "White van"
            elif "color" in text_input.lower():
                return "white"
            elif "type" in text_input.lower():
                return "van"
            elif "commercial" in text_input.lower():
                return "yes"
            elif "logo" in text_input.lower():
                return "<loc_1><loc_2><loc_3>"  # Garbage VQA output
            return ""

        extractor._query_florence = mock_query

        img = Image.new("RGB", (100, 100), color="white")
        result = await extractor._extract_vehicle_internal(img)

        assert result.is_commercial is True
        assert result.commercial_text is None  # Garbage VQA rejected

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
    async def test_extract_environment_context_dusk(self) -> None:
        """Test extract_environment_context with dusk/dawn/evening."""
        from PIL import Image

        extractor = VisionExtractor()

        async def mock_query(image, task, text_input=""):
            if "time of day" in text_input.lower():
                return "dusk"
            elif "flashlight" in text_input.lower():
                return "no"
            elif "weather" in text_input.lower():
                return "none"
            return ""

        extractor._query_florence = mock_query

        img = Image.new("RGB", (200, 200), color="black")
        result = await extractor.extract_environment_context(img)

        assert result.time_of_day == "dusk"
        assert result.artificial_light is False
        assert result.weather is None

    @pytest.mark.asyncio
    async def test_extract_environment_context_dawn(self) -> None:
        """Test extract_environment_context with dawn."""
        from PIL import Image

        extractor = VisionExtractor()

        async def mock_query(image, task, text_input=""):
            if "time of day" in text_input.lower():
                return "dawn is breaking"
            return ""

        extractor._query_florence = mock_query

        img = Image.new("RGB", (200, 200), color="black")
        result = await extractor.extract_environment_context(img)

        assert result.time_of_day == "dusk"  # dawn is classified as dusk

    @pytest.mark.asyncio
    async def test_extract_environment_context_evening(self) -> None:
        """Test extract_environment_context with evening."""
        from PIL import Image

        extractor = VisionExtractor()

        async def mock_query(image, task, text_input=""):
            if "time of day" in text_input.lower():
                return "evening time"
            return ""

        extractor._query_florence = mock_query

        img = Image.new("RGB", (200, 200), color="black")
        result = await extractor.extract_environment_context(img)

        assert result.time_of_day == "dusk"  # evening is classified as dusk

    @pytest.mark.asyncio
    async def test_extract_environment_context_day_default(self) -> None:
        """Test extract_environment_context defaults to day."""
        from PIL import Image

        extractor = VisionExtractor()

        async def mock_query(image, task, text_input=""):
            if "time of day" in text_input.lower():
                return "bright sunny afternoon"
            return ""

        extractor._query_florence = mock_query

        img = Image.new("RGB", (200, 200), color="white")
        result = await extractor.extract_environment_context(img)

        assert result.time_of_day == "day"  # Default when not night/dusk/dawn/evening

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


class TestIsValidVQAOutput:
    """Tests for is_valid_vqa_output validation function.

    The is_valid_vqa_output function validates Florence-2 VQA output to detect
    garbage responses containing location tokens, prompt artifacts, or other
    invalid patterns that should not be used in downstream prompts.

    NEM-3009: VQA outputs like "Wearing: VQA>person wearing<loc_95><loc_86><loc_901><loc_918>"
    should be rejected in favor of fallback to scene captioning.
    """

    def test_valid_simple_answer(self) -> None:
        """Test valid simple text answers pass validation."""
        from backend.services.vision_extractor import is_valid_vqa_output

        assert is_valid_vqa_output("dark hoodie and jeans") is True
        assert is_valid_vqa_output("blue sedan") is True
        assert is_valid_vqa_output("Yes, walking towards the door") is True
        assert is_valid_vqa_output("No unusual objects detected") is True

    def test_rejects_location_tokens(self) -> None:
        """Test that outputs containing <loc_N> tokens are rejected."""
        from backend.services.vision_extractor import is_valid_vqa_output

        # Pure location tokens - garbage output
        assert is_valid_vqa_output("<loc_95><loc_86><loc_901><loc_918>") is False

        # Location tokens mixed with text - still garbage
        assert is_valid_vqa_output("person wearing<loc_95><loc_86>") is False
        assert is_valid_vqa_output("<loc_1>blue jacket<loc_2>") is False

        # Single location token
        assert is_valid_vqa_output("text<loc_123>") is False

    def test_rejects_vqa_prefix_artifact(self) -> None:
        """Test that outputs containing VQA> prefix are rejected."""
        from backend.services.vision_extractor import is_valid_vqa_output

        # VQA prefix with echoed question - common garbage pattern
        assert is_valid_vqa_output("VQA>person wearing") is False
        assert is_valid_vqa_output("VQA>What color is this?blue") is False

        # Case insensitive
        assert is_valid_vqa_output("vqa>person wearing") is False
        assert is_valid_vqa_output("Vqa>test") is False

    def test_rejects_poly_tokens(self) -> None:
        """Test that outputs containing <poly> tokens are rejected."""
        from backend.services.vision_extractor import is_valid_vqa_output

        assert is_valid_vqa_output("<poly>some content</poly>") is False
        assert is_valid_vqa_output("text with <poly> marker") is False

    def test_rejects_pad_tokens(self) -> None:
        """Test that outputs containing <pad> tokens are rejected."""
        from backend.services.vision_extractor import is_valid_vqa_output

        assert is_valid_vqa_output("<pad>") is False
        assert is_valid_vqa_output("text with <pad> token") is False
        assert is_valid_vqa_output("<pad><pad><pad>") is False

    def test_rejects_empty_and_whitespace(self) -> None:
        """Test that empty and whitespace-only outputs are rejected."""
        from backend.services.vision_extractor import is_valid_vqa_output

        assert is_valid_vqa_output("") is False
        assert is_valid_vqa_output("   ") is False
        assert is_valid_vqa_output("\n\t") is False

    def test_rejects_combined_garbage_patterns(self) -> None:
        """Test rejection of outputs combining multiple garbage patterns."""
        from backend.services.vision_extractor import is_valid_vqa_output

        # Real-world garbage from issue NEM-3009
        assert is_valid_vqa_output("VQA>person wearing<loc_95><loc_86><loc_901><loc_918>") is False

        # VQA prefix with poly tokens
        assert is_valid_vqa_output("VQA>What is this<poly>content") is False

        # Multiple token types
        assert is_valid_vqa_output("<loc_1><pad><poly>") is False

    def test_accepts_valid_after_cleaning(self) -> None:
        """Test that valid text is accepted even with normal punctuation."""
        from backend.services.vision_extractor import is_valid_vqa_output

        # Normal punctuation should not trigger false positives
        assert is_valid_vqa_output("The person is wearing a dark hoodie.") is True
        assert is_valid_vqa_output("Color: blue, Type: sedan") is True
        assert is_valid_vqa_output("Yes (with high confidence)") is True
        assert is_valid_vqa_output("No - nothing unusual detected") is True

    def test_accepts_angle_brackets_in_normal_text(self) -> None:
        """Test that normal angle brackets (not tokens) are accepted."""
        from backend.services.vision_extractor import is_valid_vqa_output

        # Normal comparison operators and brackets
        assert is_valid_vqa_output("The car is < 5 meters away") is True
        assert is_valid_vqa_output("Temperature > 20 degrees") is True

    def test_rejects_short_garbage_outputs(self) -> None:
        """Test rejection of outputs that are too short to be meaningful."""
        from backend.services.vision_extractor import is_valid_vqa_output

        # Single characters that are garbage
        assert is_valid_vqa_output("a") is False
        assert is_valid_vqa_output("-") is False

        # But valid short answers are OK
        assert is_valid_vqa_output("No") is True
        assert is_valid_vqa_output("Yes") is True
        assert is_valid_vqa_output("red") is True


class TestValidateAndCleanVQAOutput:
    """Tests for validate_and_clean_vqa_output combined function.

    This function combines validation and cleaning: it first cleans the VQA output
    to remove artifacts, then validates the result. Returns None if the output
    is invalid, allowing fallback to scene captioning.

    NEM-3009: This enables the fallback mechanism when VQA returns garbage.
    """

    def test_cleans_and_validates_good_output(self) -> None:
        """Test that valid output is cleaned and returned."""
        from backend.services.vision_extractor import validate_and_clean_vqa_output

        # Clean text passes through
        result = validate_and_clean_vqa_output("dark hoodie and jeans")
        assert result == "dark hoodie and jeans"

        # Text with only whitespace issues gets cleaned
        result = validate_and_clean_vqa_output("  blue sedan  ")
        assert result == "blue sedan"

    def test_rejects_text_with_loc_tokens(self) -> None:
        """Test that any text containing loc tokens is rejected (NEM-3304)."""
        from backend.services.vision_extractor import validate_and_clean_vqa_output

        # Text with loc tokens - should be rejected entirely per NEM-3304
        # Even valid text before loc tokens is rejected because loc tokens
        # indicate a failed VQA response
        result = validate_and_clean_vqa_output("dark hoodie and jeans<loc_100><loc_200>")
        assert result is None

        # Only loc tokens - should return None
        result = validate_and_clean_vqa_output("<loc_95><loc_86><loc_901><loc_918>")
        assert result is None

    def test_handles_vqa_prefix_garbage(self) -> None:
        """Test that VQA prefix garbage returns None."""
        from backend.services.vision_extractor import validate_and_clean_vqa_output

        # Real-world garbage from NEM-3009
        result = validate_and_clean_vqa_output(
            "VQA>person wearing<loc_95><loc_86><loc_901><loc_918>"
        )
        assert result is None

        # VQA prefix without loc tokens - rejected due to VQA> pattern
        result = validate_and_clean_vqa_output("VQA>What is the color?Blue sedan")
        assert result is None

    def test_returns_none_for_empty_after_cleaning(self) -> None:
        """Test that outputs that become empty after cleaning return None."""
        from backend.services.vision_extractor import validate_and_clean_vqa_output

        assert validate_and_clean_vqa_output("") is None
        assert validate_and_clean_vqa_output("   ") is None
        assert validate_and_clean_vqa_output("<loc_1><loc_2>") is None

    def test_handles_duplicate_removal_edge_cases(self) -> None:
        """Test duplicate word removal doesn't break valid text."""
        from backend.services.vision_extractor import validate_and_clean_vqa_output

        # Consecutive duplicates get cleaned
        result = validate_and_clean_vqa_output("visible visible tools")
        assert result == "visible tools"

        # Non-consecutive same words stay (only consecutive duplicates removed)
        result = validate_and_clean_vqa_output("the weather is the same")
        assert result == "the weather is the same"

    def test_preserves_meaningful_short_answers(self) -> None:
        """Test that short but meaningful answers are preserved."""
        from backend.services.vision_extractor import validate_and_clean_vqa_output

        assert validate_and_clean_vqa_output("Yes") == "Yes"
        assert validate_and_clean_vqa_output("No") == "No"
        assert validate_and_clean_vqa_output("red") == "red"
        assert validate_and_clean_vqa_output("blue") == "blue"


class TestVisionExtractorWithVQAValidation:
    """Tests for VisionExtractor methods using VQA validation and fallback.

    NEM-3009: When VQA returns garbage, the extractor should fall back to
    scene captioning to provide meaningful output instead.
    """

    def setup_method(self) -> None:
        """Reset service before each test."""
        reset_vision_extractor()

    def teardown_method(self) -> None:
        """Reset service after each test."""
        reset_vision_extractor()

    @pytest.mark.asyncio
    async def test_extract_person_attributes_validates_vqa_output(self) -> None:
        """Test that person attribute extraction validates VQA responses."""
        from PIL import Image

        extractor = VisionExtractor()
        query_responses = {
            "What is this person wearing?": "VQA>person wearing<loc_95><loc_86><loc_901><loc_918>",
            "Is this person carrying anything? If yes, what?": "backpack",
            "Does this person appear to be a delivery worker or service worker? Answer yes or no.": "No",
            "What is this person doing?": "walking",
        }

        async def mock_query(image, task, text_input=""):
            if task == "<CAPTION>":
                return "A person in dark clothing walking in the driveway"
            return query_responses.get(text_input, "")

        extractor._query_florence = mock_query

        img = Image.new("RGB", (200, 200), color="black")
        result = await extractor.extract_person_attributes(img)

        # Clothing should be None (garbage VQA output was rejected)
        assert result.clothing is None
        assert result.carrying == "backpack"
        assert result.action == "walking"
        assert result.is_service_worker is False

    @pytest.mark.asyncio
    async def test_extract_vehicle_attributes_validates_vqa_output(self) -> None:
        """Test that vehicle attribute extraction validates VQA responses."""
        from PIL import Image

        extractor = VisionExtractor()
        query_responses = {
            "What color is this vehicle?": "<loc_1><loc_2><loc_3><loc_4>",
            "What type of vehicle is this? (sedan, SUV, pickup, van, truck, motorcycle)": "SUV",
            "Is this a commercial vehicle? Answer yes or no.": "No",
        }

        async def mock_query(image, task, text_input=""):
            if task == "<CAPTION>":
                return "A white SUV parked in front of the house"
            return query_responses.get(text_input, "")

        extractor._query_florence = mock_query

        img = Image.new("RGB", (200, 200), color="black")
        result = await extractor.extract_vehicle_attributes(img)

        # Color should be None (garbage output) but vehicle_type should be valid
        assert result.color is None
        assert result.vehicle_type == "SUV"
        assert result.is_commercial is False
        assert "white SUV" in result.caption

    @pytest.mark.asyncio
    async def test_extract_scene_analysis_handles_garbage_vqa(self) -> None:
        """Test that scene analysis handles garbage VQA responses gracefully."""
        from PIL import Image

        extractor = VisionExtractor()

        async def mock_query(image, task, text_input=""):
            if task == "<CAPTION>":
                return "A driveway with a parked car at night"
            # Return garbage for all VQA queries
            return "VQA>Are there tools<loc_1><loc_2><loc_3>"

        extractor._query_florence = mock_query

        img = Image.new("RGB", (200, 200), color="black")
        result = await extractor.extract_scene_analysis(img)

        # All lists should be empty since VQA returned garbage
        assert result.tools_detected == []
        assert result.unusual_objects == []
        assert result.abandoned_items == []
        # But the scene description should still be valid
        assert "driveway" in result.scene_description.lower()

    @pytest.mark.asyncio
    async def test_extract_vehicle_internal_validates_vqa_output_nem3304(self) -> None:
        """Test that _extract_vehicle_internal validates VQA responses (NEM-3304).

        The internal methods used by batch extraction should validate VQA output
        just like the public methods do. Garbage VQA output with <loc_> tokens
        should result in None for that attribute, not raw garbage in the prompt.
        """
        from PIL import Image

        extractor = VisionExtractor()
        query_responses = {
            "What color is this vehicle?": "VQA>vehicle color<loc_95><loc_86>",
            "What type of vehicle is this? (sedan, SUV, pickup, van, truck, motorcycle)": "sedan<loc_1><loc_2>",
            "Is this a commercial vehicle? Answer yes or no.": "No",
        }

        async def mock_query(image, task, text_input=""):
            if task == "<CAPTION>":
                return "A silver sedan parked in the driveway"
            return query_responses.get(text_input, "")

        extractor._query_florence = mock_query

        img = Image.new("RGB", (200, 200), color="black")
        # Call the internal method directly
        result = await extractor._extract_vehicle_internal(img)

        # Color should be None (garbage VQA output with loc tokens)
        assert result.color is None, f"Expected None, got: {result.color}"
        # Vehicle type should also be None (has loc tokens)
        assert result.vehicle_type is None, f"Expected None, got: {result.vehicle_type}"
        # Caption should still be valid
        assert "sedan" in result.caption.lower()

    @pytest.mark.asyncio
    async def test_extract_person_internal_validates_vqa_output_nem3304(self) -> None:
        """Test that _extract_person_internal validates VQA responses (NEM-3304).

        The internal methods used by batch extraction should validate VQA output
        just like the public methods do. Garbage VQA output like
        "Wearing: VQA>person wearing<loc_95><loc_86><loc_901><loc_918>"
        should be rejected and return None instead of raw garbage.
        """
        from PIL import Image

        extractor = VisionExtractor()
        query_responses = {
            "What is this person wearing?": "VQA>person wearing<loc_95><loc_86><loc_901><loc_918>",
            "Is this person carrying anything? If yes, what?": "backpack",
            "Does this person appear to be a delivery worker or service worker? Answer yes or no.": "No",
            "What is this person doing?": "walking<loc_100>",
        }

        async def mock_query(image, task, text_input=""):
            if task == "<CAPTION>":
                return "A person in dark hoodie walking in the driveway"
            return query_responses.get(text_input, "")

        extractor._query_florence = mock_query

        img = Image.new("RGB", (200, 200), color="black")
        # Call the internal method directly
        result = await extractor._extract_person_internal(img)

        # Clothing should be None (garbage VQA output with loc tokens)
        assert result.clothing is None, f"Expected None, got: {result.clothing}"
        # Carrying should be valid (no loc tokens)
        assert result.carrying == "backpack"
        # Action should be None (has loc tokens)
        assert result.action is None, f"Expected None, got: {result.action}"
        # Caption provides fallback context
        assert "dark hoodie" in result.caption.lower()

    @pytest.mark.asyncio
    async def test_batch_extraction_validates_all_vqa_outputs_nem3304(self) -> None:
        """Test batch extraction validates VQA outputs (NEM-3304).

        When extracting attributes for multiple detections via extract_batch_attributes,
        all VQA outputs should be validated. Garbage outputs should result in None
        for those attributes while caption provides fallback context.
        """
        from PIL import Image

        extractor = VisionExtractor()

        # Mock responses with garbage VQA for person attributes
        async def mock_query(image, task, text_input=""):  # noqa: PLR0911
            if task == "<CAPTION>":
                return "Person in blue jacket near white car"
            if "wearing" in text_input.lower():
                return "VQA>person wearing<loc_95><loc_86><loc_901><loc_918>"
            if "color" in text_input.lower():
                return "white"
            if "type" in text_input.lower():
                return "sedan"
            if "commercial" in text_input.lower():
                return "No"
            if "carrying" in text_input.lower():
                return "nothing"
            if "service worker" in text_input.lower():
                return "No"
            if "doing" in text_input.lower():
                return "walking"
            # Scene and environment queries
            if "unusual" in text_input.lower() or "tools" in text_input.lower():
                return "No"
            if "abandoned" in text_input.lower():
                return "No"
            if "time of day" in text_input.lower():
                return "day"
            if "flashlight" in text_input.lower():
                return "No"
            if "weather" in text_input.lower():
                return "clear"
            return ""

        extractor._query_florence = mock_query

        img = Image.new("RGB", (400, 400), color="gray")
        detections = [
            {"class_name": "car", "bbox": [10, 10, 100, 100], "detection_id": "v1"},
            {"class_name": "person", "bbox": [200, 200, 300, 400], "detection_id": "p1"},
        ]

        result = await extractor.extract_batch_attributes(img, detections)

        # Person's clothing should be None (garbage VQA rejected)
        person_attrs = result.person_attributes.get("p1")
        assert person_attrs is not None
        assert person_attrs.clothing is None, f"Expected None, got: {person_attrs.clothing}"

        # Vehicle attributes should be valid (no garbage in responses)
        vehicle_attrs = result.vehicle_attributes.get("v1")
        assert vehicle_attrs is not None
        assert vehicle_attrs.color == "white"
        assert vehicle_attrs.vehicle_type == "sedan"
