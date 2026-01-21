"""Unit tests for backend.evaluation.harness module."""

from __future__ import annotations

import pytest

pd = pytest.importorskip("pandas", reason="pandas required for evaluation tests")

from backend.evaluation.harness import (  # noqa: E402
    DEFAULT_NEMOTRON_URL,
    EvaluationResult,
    PromptEvaluator,
    PromptTemplate,
    generate_mock_scenarios,
)


class TestPromptTemplate:
    """Tests for PromptTemplate dataclass."""

    def test_prompt_template_creation(self) -> None:
        """PromptTemplate should be creatable with all required fields."""
        template = PromptTemplate(
            name="test",
            description="Test template",
            template_key="TEST_PROMPT",
            enrichment_required="none",
        )
        assert template.name == "test"
        assert template.description == "Test template"
        assert template.template_key == "TEST_PROMPT"
        assert template.enrichment_required == "none"


class TestEvaluationResult:
    """Tests for EvaluationResult dataclass."""

    def test_default_values(self) -> None:
        """EvaluationResult should have sensible defaults."""
        result = EvaluationResult(
            scenario_id="test_001",
            template_name="basic",
            scenario_type="normal",
            enrichment_level="none",
        )
        assert result.risk_score == 0
        assert result.risk_level == ""
        assert result.reasoning == ""
        assert result.success is True
        assert result.error_message == ""

    def test_full_result(self) -> None:
        """EvaluationResult should store all fields correctly."""
        result = EvaluationResult(
            scenario_id="test_001",
            template_name="enriched",
            scenario_type="suspicious",
            enrichment_level="basic",
            risk_score=45,
            risk_level="medium",
            reasoning="Detected unknown person",
            summary="Suspicious activity",
            ground_truth_range=(30, 55),
            risk_deviation=0.0,
            key_point_coverage=0.8,
            reasoning_similarity=0.7,
            latency_ms=150.5,
            success=True,
        )
        assert result.risk_score == 45
        assert result.ground_truth_range == (30, 55)
        assert result.latency_ms == 150.5


class TestGenerateMockScenarios:
    """Tests for generate_mock_scenarios function."""

    def test_generates_requested_count(self) -> None:
        """Should generate the requested number of scenarios."""
        scenarios = generate_mock_scenarios(10)
        assert len(scenarios) == 10

        scenarios = generate_mock_scenarios(50)
        assert len(scenarios) == 50

    def test_default_count_is_20(self) -> None:
        """Default count should be 20."""
        scenarios = generate_mock_scenarios()
        assert len(scenarios) == 20

    def test_contains_required_columns(self) -> None:
        """Generated scenarios should have all required columns."""
        scenarios = generate_mock_scenarios(5)
        required_columns = [
            "scenario_id",
            "scenario_type",
            "enrichment_level",
            "time_of_day",
            "camera_location",
            "detections_list",
            "ground_truth_range",
            "reasoning_key_points",
            "expected_summary",
        ]
        for col in required_columns:
            assert col in scenarios.columns, f"Missing column: {col}"

    def test_scenario_types_are_valid(self) -> None:
        """Scenario types should be from the valid set."""
        scenarios = generate_mock_scenarios(100)  # Generate enough to cover all types
        valid_types = {"normal", "suspicious", "threat", "edge_case"}
        actual_types = set(scenarios["scenario_type"].unique())
        assert actual_types.issubset(valid_types)

    def test_enrichment_levels_are_valid(self) -> None:
        """Enrichment levels should be from the valid set."""
        scenarios = generate_mock_scenarios(100)
        valid_levels = {"none", "basic", "full"}
        actual_levels = set(scenarios["enrichment_level"].unique())
        assert actual_levels.issubset(valid_levels)

    def test_ground_truth_ranges_match_scenario_types(self) -> None:
        """Ground truth ranges should match scenario types."""
        scenarios = generate_mock_scenarios(40)  # Enough for coverage

        expected_ranges = {
            "normal": (0, 25),
            "suspicious": (30, 55),
            "threat": (70, 100),
            "edge_case": (20, 60),
        }

        for _, row in scenarios.iterrows():
            scenario_type = row["scenario_type"]
            expected = expected_ranges[scenario_type]
            assert row["ground_truth_range"] == expected, (
                f"Wrong range for {scenario_type}: {row['ground_truth_range']} != {expected}"
            )


class TestPromptEvaluator:
    """Tests for PromptEvaluator class."""

    def test_default_initialization(self) -> None:
        """Evaluator should initialize with sensible defaults."""
        evaluator = PromptEvaluator()
        assert evaluator.nemotron_url == DEFAULT_NEMOTRON_URL
        assert evaluator.mock_mode is False
        assert evaluator.results == []

    def test_mock_mode_initialization(self) -> None:
        """Evaluator should respect mock_mode parameter."""
        evaluator = PromptEvaluator(mock_mode=True)
        assert evaluator.mock_mode is True

    def test_custom_nemotron_url(self) -> None:
        """Evaluator should accept custom Nemotron URL."""
        custom_url = "http://custom:8000/v1/completions"
        evaluator = PromptEvaluator(nemotron_url=custom_url)
        assert evaluator.nemotron_url == custom_url

    def test_parse_llm_response_valid_json(self) -> None:
        """Should parse valid JSON response."""
        evaluator = PromptEvaluator()
        response = '{"risk_score": 45, "risk_level": "medium", "reasoning": "Test", "summary": "Test summary"}'
        parsed = evaluator._parse_llm_response(response)

        assert parsed["risk_score"] == 45
        assert parsed["risk_level"] == "medium"
        assert parsed["reasoning"] == "Test"
        assert parsed["summary"] == "Test summary"

    def test_parse_llm_response_with_think_blocks(self) -> None:
        """Should handle <think> blocks in response."""
        evaluator = PromptEvaluator()
        response = """<think>
        Let me analyze this carefully...
        The person appears to be unknown.
        </think>
        {"risk_score": 60, "risk_level": "high", "reasoning": "Unknown person", "summary": "Alert"}"""
        parsed = evaluator._parse_llm_response(response)

        assert parsed["risk_score"] == 60
        assert parsed["risk_level"] == "high"

    def test_parse_llm_response_invalid_json(self) -> None:
        """Should return defaults for invalid JSON."""
        evaluator = PromptEvaluator()
        response = "This is not JSON at all"
        parsed = evaluator._parse_llm_response(response)

        assert parsed["risk_score"] == 50  # Default
        assert parsed["risk_level"] == "medium"  # Default

    def test_generate_mock_response(self) -> None:
        """Mock response should be within expected range most of the time."""
        evaluator = PromptEvaluator(mock_mode=True)
        template = PromptTemplate(
            name="test",
            description="Test",
            template_key="TEST",
            enrichment_required="none",
        )
        scenario = {
            "scenario_type": "threat",
            "ground_truth_range": (70, 100),
            "reasoning_key_points": ["threat", "immediate"],
            "expected_summary": "Threat detected",
        }

        # Generate multiple responses to check distribution
        responses = [evaluator._generate_mock_response(scenario, template) for _ in range(50)]

        # Check that most responses are in range (80% expected)
        in_range = sum(1 for r in responses if 70 <= r["risk_score"] <= 100)
        assert in_range >= 30  # At least 60% in range (accounting for randomness)

    @pytest.mark.asyncio
    async def test_evaluate_scenario_mock_mode(self) -> None:
        """Evaluate scenario should work in mock mode."""
        evaluator = PromptEvaluator(mock_mode=True)
        template = PromptTemplate(
            name="basic",
            description="Basic template",
            template_key="RISK_ANALYSIS_PROMPT",
            enrichment_required="none",
        )
        scenario = {
            "scenario_id": "test_001",
            "scenario_type": "normal",
            "enrichment_level": "none",
            "ground_truth_range": (0, 25),
            "reasoning_key_points": ["expected activity"],
            "expected_summary": "Normal activity",
            "camera_location": "front_door",
            "detections_list": "1 person detected",
        }

        result = await evaluator.evaluate_scenario(scenario, template)

        assert result.scenario_id == "test_001"
        assert result.template_name == "basic"
        assert result.success is True
        assert result.latency_ms > 0

    @pytest.mark.asyncio
    async def test_evaluate_all_mock_mode(self) -> None:
        """Evaluate all should process all scenarios and templates."""
        evaluator = PromptEvaluator(mock_mode=True)
        scenarios = generate_mock_scenarios(5)

        # Only use 2 templates for faster testing
        templates = [
            PromptTemplate(
                name="basic",
                description="Basic",
                template_key="RISK_ANALYSIS_PROMPT",
                enrichment_required="none",
            ),
            PromptTemplate(
                name="enriched",
                description="Enriched",
                template_key="ENRICHED_RISK_ANALYSIS_PROMPT",
                enrichment_required="basic",
            ),
        ]

        results_df = await evaluator.evaluate_all(scenarios, templates=templates)

        # Should have 5 scenarios * 2 templates = 10 results
        assert len(results_df) == 10
        assert len(evaluator.results) == 10

    def test_results_to_dataframe(self) -> None:
        """Results should be correctly converted to DataFrame."""
        evaluator = PromptEvaluator()
        evaluator.results = [
            EvaluationResult(
                scenario_id="test_001",
                template_name="basic",
                scenario_type="normal",
                enrichment_level="none",
                risk_score=20,
                risk_level="low",
                reasoning="Test reasoning",
                summary="Test summary",
                ground_truth_range=(0, 25),
                risk_deviation=0.0,
                key_point_coverage=0.8,
                reasoning_similarity=0.7,
                latency_ms=100.0,
                success=True,
            ),
        ]

        df = evaluator.results_to_dataframe()

        assert len(df) == 1
        assert df.iloc[0]["scenario_id"] == "test_001"
        assert df.iloc[0]["risk_score"] == 20
        assert df.iloc[0]["ground_truth_min"] == 0
        assert df.iloc[0]["ground_truth_max"] == 25

    def test_results_to_dataframe_empty(self) -> None:
        """Empty results should return empty DataFrame."""
        evaluator = PromptEvaluator()
        df = evaluator.results_to_dataframe()
        assert len(df) == 0

    @pytest.mark.asyncio
    async def test_progress_callback_called(self) -> None:
        """Progress callback should be called during evaluation."""
        evaluator = PromptEvaluator(mock_mode=True)
        scenarios = generate_mock_scenarios(3)

        templates = [
            PromptTemplate(
                name="basic",
                description="Basic",
                template_key="RISK_ANALYSIS_PROMPT",
                enrichment_required="none",
            ),
        ]

        progress_calls = []

        def progress_callback(current: int, total: int) -> None:
            progress_calls.append((current, total))

        await evaluator.evaluate_all(
            scenarios, templates=templates, progress_callback=progress_callback
        )

        # Should have 3 progress calls (one per scenario)
        assert len(progress_calls) == 3
        assert progress_calls[-1] == (3, 3)  # Final call should be (3, 3)


class TestPromptEvaluatorRenderPrompt:
    """Tests for prompt rendering."""

    def test_render_basic_prompt(self) -> None:
        """Basic prompt should render without enrichment fields."""
        evaluator = PromptEvaluator()
        template = PromptTemplate(
            name="basic",
            description="Basic",
            template_key="RISK_ANALYSIS_PROMPT",
            enrichment_required="none",
        )
        scenario = {
            "camera_location": "front_door",
            "detections_list": "1 person detected at 0s",
        }

        prompt = evaluator._render_prompt(template, scenario)

        assert "front_door" in prompt
        assert "1 person detected" in prompt

    def test_render_enriched_prompt(self) -> None:
        """Enriched prompt should include zone and baseline data."""
        evaluator = PromptEvaluator()
        template = PromptTemplate(
            name="enriched",
            description="Enriched",
            template_key="ENRICHED_RISK_ANALYSIS_PROMPT",
            enrichment_required="basic",
        )
        scenario = {
            "camera_location": "front_door",
            "detections_list": "1 person detected",
            "day_type": "weekday",
            "zone_analysis": "Zone: front_door (entry_point: true)",
            "baseline_comparison": "Expected: 2-5 detections",
            "deviation_score": 0.3,
            "cross_camera_summary": "No other activity",
        }

        prompt = evaluator._render_prompt(template, scenario)

        assert "Zone Analysis" in prompt or "zone_analysis" in prompt.lower()
        assert "Baseline" in prompt or "baseline" in prompt.lower()
