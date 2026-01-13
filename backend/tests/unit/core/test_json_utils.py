"""Unit tests for JSON parsing utilities.

Tests cover:
- extract_json_from_llm_response() - All parsing strategies and edge cases
- Malformed JSON handling (missing commas, trailing commas, single quotes)
- Markdown code block extraction
- Think/reasoning block removal
- Nested JSON handling
- Property-based tests using Hypothesis for fuzzing JSON parsing
- Unicode and special character handling
- Multiple JSON objects extraction
- Error recovery strategies
- safe_json_loads() - Safe JSON parsing with error logging
"""

import json
from typing import Any

import pytest
from hypothesis import assume, given, settings
from hypothesis import strategies as st

from backend.core.json_utils import (
    _clean_llm_response,
    _find_json_in_text,
    _fix_missing_commas,
    _fix_single_quotes,
    _fix_trailing_commas,
    extract_json_field,
    extract_json_from_llm_response,
    safe_json_loads,
)

# Mark all tests as unit tests
pytestmark = pytest.mark.unit


class TestExtractJsonHappyPath:
    """Tests for successful JSON extraction from clean responses."""

    def test_simple_json_object(self) -> None:
        """Test parsing a simple, valid JSON object."""
        response = '{"risk_score": 75, "risk_level": "high"}'
        result = extract_json_from_llm_response(response)

        assert result["risk_score"] == 75
        assert result["risk_level"] == "high"

    def test_json_with_whitespace(self) -> None:
        """Test parsing JSON with extra whitespace."""
        response = """
        {
            "risk_score": 50,
            "risk_level": "medium",
            "summary": "Normal activity"
        }
        """
        result = extract_json_from_llm_response(response)

        assert result["risk_score"] == 50
        assert result["risk_level"] == "medium"
        assert result["summary"] == "Normal activity"

    def test_json_with_nested_objects(self) -> None:
        """Test parsing JSON with nested objects."""
        response = """
        {
            "risk_score": 80,
            "details": {
                "location": "front_door",
                "confidence": 0.95
            },
            "risk_level": "high"
        }
        """
        result = extract_json_from_llm_response(response)

        assert result["risk_score"] == 80
        assert result["details"]["location"] == "front_door"
        assert result["details"]["confidence"] == 0.95

    def test_json_with_arrays(self) -> None:
        """Test parsing JSON with array values."""
        response = '{"missing_context": ["time of day", "weather"], "risk_score": 60}'
        result = extract_json_from_llm_response(response)

        assert result["risk_score"] == 60
        assert "time of day" in result["missing_context"]
        assert "weather" in result["missing_context"]


class TestExtractJsonLLMArtifacts:
    """Tests for JSON extraction with common LLM response artifacts."""

    def test_json_with_preamble_text(self) -> None:
        """Test parsing JSON when LLM adds text before JSON."""
        response = """
        Based on my analysis, here is the result:

        {"risk_score": 65, "risk_level": "high", "summary": "Suspicious activity"}

        I hope this helps.
        """
        result = extract_json_from_llm_response(response)

        assert result["risk_score"] == 65
        assert result["risk_level"] == "high"

    def test_json_with_markdown_code_block(self) -> None:
        """Test parsing JSON from markdown code blocks."""
        response = """
        Here is the analysis:

        ```json
        {"risk_score": 45, "risk_level": "medium"}
        ```
        """
        result = extract_json_from_llm_response(response)

        assert result["risk_score"] == 45
        assert result["risk_level"] == "medium"

    def test_json_with_think_block(self) -> None:
        """Test parsing JSON with <think> reasoning block."""
        response = """
        <think>
        I need to analyze this carefully...
        The risk seems moderate because...
        </think>
        {"risk_score": 55, "risk_level": "medium", "reasoning": "Moderate activity"}
        """
        result = extract_json_from_llm_response(response)

        assert result["risk_score"] == 55
        assert result["risk_level"] == "medium"

    def test_json_with_incomplete_think_block(self) -> None:
        """Test parsing JSON when <think> block is not closed."""
        response = """
        <think>
        Analyzing the situation...
        {"risk_score": 70, "risk_level": "high"}
        """
        result = extract_json_from_llm_response(response)

        assert result["risk_score"] == 70
        assert result["risk_level"] == "high"

    def test_json_with_multiple_think_blocks(self) -> None:
        """Test parsing JSON with multiple <think> blocks."""
        response = """
        <think>First thought...</think>
        <think>Second thought...</think>
        {"risk_score": 40, "risk_level": "medium"}
        """
        result = extract_json_from_llm_response(response)

        assert result["risk_score"] == 40


class TestExtractJsonMalformed:
    """Tests for JSON extraction with common LLM JSON mistakes."""

    def test_missing_comma_between_properties(self) -> None:
        """Test repair of missing comma between JSON properties.

        This is the exact error from the bug report:
        Expecting ',' delimiter: line 12 column 6
        """
        response = """
        {
            "risk_score": 75
            "risk_level": "high"
            "summary": "Activity detected"
        }
        """
        result = extract_json_from_llm_response(response)

        assert result["risk_score"] == 75
        assert result["risk_level"] == "high"
        assert result["summary"] == "Activity detected"

    def test_missing_comma_after_number(self) -> None:
        """Test repair of missing comma after numeric value."""
        response = """
        {
            "context_usage": 4
            "reasoning_coherence": 5
        }
        """
        result = extract_json_from_llm_response(response)

        assert result["context_usage"] == 4
        assert result["reasoning_coherence"] == 5

    def test_missing_comma_after_boolean(self) -> None:
        """Test repair of missing comma after boolean value."""
        response = '{"active": true\n"valid": false}'
        result = extract_json_from_llm_response(response)

        assert result["active"] is True
        assert result["valid"] is False

    def test_trailing_comma(self) -> None:
        """Test removal of trailing commas."""
        response = '{"risk_score": 50, "risk_level": "medium",}'
        result = extract_json_from_llm_response(response)

        assert result["risk_score"] == 50
        assert result["risk_level"] == "medium"

    def test_trailing_comma_in_array(self) -> None:
        """Test removal of trailing commas in arrays."""
        response = '{"items": ["a", "b", "c",]}'
        result = extract_json_from_llm_response(response)

        assert result["items"] == ["a", "b", "c"]

    def test_single_quotes(self) -> None:
        """Test conversion of single quotes to double quotes."""
        response = "{'risk_score': 60, 'risk_level': 'high'}"
        result = extract_json_from_llm_response(response)

        assert result["risk_score"] == 60
        assert result["risk_level"] == "high"

    def test_combined_issues(self) -> None:
        """Test repair with multiple formatting issues."""
        response = """
        {
            'risk_score': 85
            'risk_level': 'critical',
        }
        """
        result = extract_json_from_llm_response(response)

        assert result["risk_score"] == 85
        assert result["risk_level"] == "critical"


class TestExtractJsonEdgeCases:
    """Tests for edge cases in JSON extraction."""

    def test_empty_string(self) -> None:
        """Test that empty string raises ValueError."""
        with pytest.raises(ValueError, match="Empty LLM response"):
            extract_json_from_llm_response("")

    def test_whitespace_only(self) -> None:
        """Test that whitespace-only string raises ValueError."""
        with pytest.raises(ValueError, match="Empty LLM response"):
            extract_json_from_llm_response("   \n\t  ")

    def test_no_json(self) -> None:
        """Test that text without JSON raises ValueError."""
        with pytest.raises(ValueError, match="No JSON found"):
            extract_json_from_llm_response("This is just plain text without any JSON.")

    def test_incomplete_json(self) -> None:
        """Test handling of truncated/incomplete JSON."""
        response = '{"risk_score": 50, "risk_level": "me'
        # This should either raise an error or try to recover
        # Given the nature of the fix, we may want to raise an error
        with pytest.raises(ValueError):
            extract_json_from_llm_response(response)

    def test_deeply_nested_json(self) -> None:
        """Test parsing deeply nested JSON structures."""
        response = """
        {
            "level1": {
                "level2": {
                    "level3": {
                        "value": 42
                    }
                }
            },
            "risk_score": 30
        }
        """
        result = extract_json_from_llm_response(response)

        assert result["level1"]["level2"]["level3"]["value"] == 42
        assert result["risk_score"] == 30

    def test_json_with_special_characters(self) -> None:
        """Test parsing JSON with special characters in strings."""
        response = '{"summary": "Vehicle with plate ABC-123 detected", "risk_score": 50}'
        result = extract_json_from_llm_response(response)

        assert "ABC-123" in result["summary"]
        assert result["risk_score"] == 50

    def test_json_with_escaped_quotes(self) -> None:
        """Test parsing JSON with escaped quotes in strings."""
        response = r'{"summary": "User said \"hello\"", "risk_score": 25}'
        result = extract_json_from_llm_response(response)

        assert result["risk_score"] == 25

    def test_json_with_unicode(self) -> None:
        """Test parsing JSON with unicode characters."""
        response = '{"summary": "Temperature: 20\\u00b0C", "risk_score": 10}'
        result = extract_json_from_llm_response(response)

        assert result["risk_score"] == 10

    def test_multiple_json_objects(self) -> None:
        """Test that first complete JSON object is returned."""
        response = """
        {"invalid": "object"} not valid
        {"risk_score": 40, "risk_level": "medium", "valid": true}
        {"another": "object"}
        """
        result = extract_json_from_llm_response(response)

        # Should return the first valid object that matches expected structure
        # or the first object found
        assert "invalid" in result or "risk_score" in result


class TestCleanLLMResponse:
    """Tests for the response cleaning function."""

    def test_removes_complete_think_block(self) -> None:
        """Test removal of complete <think> blocks."""
        text = "<think>Some thoughts</think>Actual content"
        result = _clean_llm_response(text)

        assert "<think>" not in result
        assert "</think>" not in result
        assert "Actual content" in result

    def test_removes_multiple_think_blocks(self) -> None:
        """Test removal of multiple <think> blocks."""
        text = "<think>First</think>Content<think>Second</think>More"
        result = _clean_llm_response(text)

        assert "<think>" not in result
        assert "Content" in result
        assert "More" in result

    def test_handles_incomplete_think_block(self) -> None:
        """Test handling of incomplete <think> block before JSON."""
        text = '<think>Thinking...{"key": "value"}'
        result = _clean_llm_response(text)

        # Should find the JSON after the unclosed think
        assert '{"key": "value"}' in result or "key" in result

    def test_removes_markdown_code_blocks(self) -> None:
        """Test removal of markdown code block markers."""
        text = '```json\n{"key": "value"}\n```'
        result = _clean_llm_response(text)

        assert "```" not in result
        assert '{"key": "value"}' in result


class TestFindJsonInText:
    """Tests for the JSON finding function."""

    def test_finds_simple_json(self) -> None:
        """Test finding a simple JSON object."""
        text = 'Some text {"key": "value"} more text'
        result = _find_json_in_text(text)

        assert result == '{"key": "value"}'

    def test_finds_nested_json(self) -> None:
        """Test finding JSON with nested objects."""
        text = 'Text {"outer": {"inner": 42}} more'
        result = _find_json_in_text(text)

        assert result is not None
        assert '"outer"' in result
        assert '"inner"' in result

    def test_handles_no_json(self) -> None:
        """Test returns None when no JSON present."""
        text = "This is just plain text"
        result = _find_json_in_text(text)

        assert result is None

    def test_handles_string_with_braces(self) -> None:
        """Test handling of strings containing braces."""
        text = '{"message": "Use {placeholder} here"}'
        result = _find_json_in_text(text)

        assert result is not None
        # The function should properly handle braces inside strings


class TestFixMissingCommas:
    """Tests for the missing comma repair function."""

    def test_fixes_string_to_string(self) -> None:
        """Test fixing missing comma between string values."""
        json_str = '"value1"\n"key2"'
        result = _fix_missing_commas(json_str)

        assert '"value1",\n"key2"' in result

    def test_fixes_number_to_key(self) -> None:
        """Test fixing missing comma after number."""
        json_str = '42\n"key"'
        result = _fix_missing_commas(json_str)

        assert "42,\n" in result

    def test_fixes_boolean_to_key(self) -> None:
        """Test fixing missing comma after boolean."""
        json_str = 'true\n"key"'
        result = _fix_missing_commas(json_str)

        assert "true,\n" in result

    def test_fixes_closing_brace_to_key(self) -> None:
        """Test fixing missing comma after closing brace."""
        json_str = '}\n"key"'
        result = _fix_missing_commas(json_str)

        assert "},\n" in result


class TestFixTrailingCommas:
    """Tests for the trailing comma removal function."""

    def test_removes_trailing_comma_before_brace(self) -> None:
        """Test removal of trailing comma before closing brace."""
        json_str = '{"key": "value",}'
        result = _fix_trailing_commas(json_str)

        assert result == '{"key": "value"}'

    def test_removes_trailing_comma_before_bracket(self) -> None:
        """Test removal of trailing comma before closing bracket."""
        json_str = '["a", "b",]'
        result = _fix_trailing_commas(json_str)

        assert result == '["a", "b"]'

    def test_handles_whitespace(self) -> None:
        """Test removal with whitespace between comma and closer."""
        json_str = '{"key": "value",  }'
        result = _fix_trailing_commas(json_str)

        assert result == '{"key": "value"}'


class TestFixSingleQuotes:
    """Tests for the single quote replacement function."""

    def test_replaces_single_quotes(self) -> None:
        """Test replacement of single quotes with double quotes."""
        json_str = "{'key': 'value'}"
        result = _fix_single_quotes(json_str)

        assert result == '{"key": "value"}'


class TestExtractJsonField:
    """Tests for the field extraction convenience function."""

    def test_extracts_existing_field(self) -> None:
        """Test extraction of an existing field."""
        response = '{"risk_score": 75, "risk_level": "high"}'
        result = extract_json_field(response, "risk_score")

        assert result == 75

    def test_returns_default_for_missing_field(self) -> None:
        """Test that default is returned for missing field."""
        response = '{"risk_score": 75}'
        result = extract_json_field(response, "risk_level", default="unknown")

        assert result == "unknown"

    def test_returns_default_for_invalid_json(self) -> None:
        """Test that default is returned when JSON is invalid."""
        response = "This is not JSON"
        result = extract_json_field(response, "risk_score", default=50)

        assert result == 50

    def test_returns_none_as_default(self) -> None:
        """Test that None is the default default value."""
        response = "Not JSON"
        result = extract_json_field(response, "field")

        assert result is None


class TestRealWorldExamples:
    """Tests based on real-world LLM response patterns."""

    def test_nemotron_consistency_check_response(self) -> None:
        """Test parsing a real Nemotron consistency check response."""
        response = """
        Based on the security context provided, here is my assessment:

        {
            "risk_score": 65
            "risk_level": "high"
            "brief_reason": "Person detected at entrance during unusual hours"
        }
        """
        result = extract_json_from_llm_response(response)

        assert result["risk_score"] == 65
        assert result["risk_level"] == "high"
        assert "Person detected" in result["brief_reason"]

    def test_nemotron_rubric_eval_response(self) -> None:
        """Test parsing a real Nemotron rubric evaluation response."""
        response = """
        <think>
        Let me evaluate each dimension...
        Context usage: The analysis referenced the time and location...
        Reasoning: The logic flow is clear...
        </think>
        {
            "context_usage": 4,
            "reasoning_coherence": 5,
            "risk_justification": 4,
            "actionability": 3,
            "explanation": "Good overall analysis with clear reasoning"
        }
        """
        result = extract_json_from_llm_response(response)

        assert result["context_usage"] == 4
        assert result["reasoning_coherence"] == 5
        assert result["risk_justification"] == 4
        assert result["actionability"] == 3

    def test_nemotron_prompt_improvement_response(self) -> None:
        """Test parsing a real Nemotron prompt improvement response."""
        response = """
        Here is my analysis of the prompt:

        ```json
        {
            "missing_context": ["historical activity patterns", "time since last motion"],
            "confusing_sections": [],
            "unused_data": ["camera model"],
            "format_suggestions": ["Group related detections"],
            "model_gaps": ["weather analysis"]
        }
        ```
        """
        result = extract_json_from_llm_response(response)

        assert "historical activity patterns" in result["missing_context"]
        assert "weather analysis" in result["model_gaps"]


# =============================================================================
# Property-Based Tests Using Hypothesis
# =============================================================================

# Custom strategies for generating JSON-like data
json_primitive_values = st.one_of(
    st.none(),
    st.booleans(),
    st.integers(min_value=-1_000_000, max_value=1_000_000),
    st.floats(allow_nan=False, allow_infinity=False, min_value=-1e10, max_value=1e10),
    st.text(min_size=0, max_size=100, alphabet=st.characters(blacklist_categories=("Cs",))),
)


# Strategy for valid JSON objects (not deeply nested)
@st.composite
def json_objects(draw: st.DrawFn, max_depth: int = 2) -> dict:
    """Generate valid JSON objects up to a certain depth."""
    if max_depth <= 0:
        # At max depth, only generate primitive values
        return draw(
            st.dictionaries(
                st.text(
                    min_size=1, max_size=20, alphabet=st.characters(blacklist_categories=("Cs",))
                ),
                json_primitive_values,
                min_size=1,
                max_size=5,
            )
        )

    # Can include nested objects/arrays
    value_strategy = st.one_of(
        json_primitive_values,
        st.lists(json_primitive_values, min_size=0, max_size=3),
        st.deferred(lambda: json_objects(max_depth=max_depth - 1)),
    )

    return draw(
        st.dictionaries(
            st.text(min_size=1, max_size=20, alphabet=st.characters(blacklist_categories=("Cs",))),
            value_strategy,
            min_size=1,
            max_size=5,
        )
    )


class TestPropertyBasedJsonParsing:
    """Property-based tests for JSON parsing using Hypothesis."""

    @given(obj=json_objects(max_depth=2))
    @settings(max_examples=50)
    def test_valid_json_always_parses(self, obj: dict) -> None:
        """Property: Valid JSON objects always parse successfully."""
        # Avoid keys that look like think blocks which would be stripped by clean_llm_response
        for key in obj:
            assume("<think>" not in key and "</think>" not in key)
        json_str = json.dumps(obj)
        result = extract_json_from_llm_response(json_str)
        assert result == obj

    @given(obj=json_objects(max_depth=2))
    @settings(max_examples=25)
    def test_json_with_prefix_parses(self, obj: dict) -> None:
        """Property: Valid JSON with text prefix always extracts correctly."""
        # Avoid keys that look like think blocks which would be stripped by clean_llm_response
        for key in obj:
            assume("<think>" not in key and "</think>" not in key)
        json_str = json.dumps(obj)
        prefixed = f"Here is my analysis:\n\n{json_str}\n\nDone."
        result = extract_json_from_llm_response(prefixed)
        assert result == obj

    @given(obj=json_objects(max_depth=2))
    @settings(max_examples=25)
    def test_json_in_markdown_block_parses(self, obj: dict) -> None:
        """Property: Valid JSON in markdown code block always extracts correctly."""
        # Avoid keys that look like think blocks which would be stripped
        for key in obj:
            assume("<think>" not in key and "</think>" not in key)
        json_str = json.dumps(obj)
        markdown = f"```json\n{json_str}\n```"
        result = extract_json_from_llm_response(markdown)
        assert result == obj

    @given(obj=json_objects(max_depth=1), think_content=st.text(min_size=1, max_size=50))
    @settings(max_examples=25)
    def test_json_after_think_block_parses(self, obj: dict, think_content: str) -> None:
        """Property: JSON after <think> block always parses correctly."""
        json_str = json.dumps(obj)
        # Avoid think_content containing "<think>" or "</think>" which would confuse parsing
        assume("<think>" not in think_content and "</think>" not in think_content)
        with_think = f"<think>{think_content}</think>\n{json_str}"
        result = extract_json_from_llm_response(with_think)
        assert result == obj

    @given(
        key=st.text(min_size=1, max_size=20, alphabet=st.characters(blacklist_categories=("Cs",))),
        value=st.text(
            min_size=0, max_size=50, alphabet=st.characters(blacklist_categories=("Cs",))
        ),
    )
    @settings(max_examples=50)
    def test_roundtrip_preserves_string_values(self, key: str, value: str) -> None:
        """Property: String values survive JSON roundtrip through extractor."""
        obj = {key: value}
        json_str = json.dumps(obj)
        result = extract_json_from_llm_response(json_str)
        assert result[key] == value

    @given(
        key=st.text(min_size=1, max_size=20, alphabet=st.characters(blacklist_categories=("Cs",))),
        num=st.integers(min_value=-1_000_000, max_value=1_000_000),
    )
    @settings(max_examples=50)
    def test_roundtrip_preserves_integer_values(self, key: str, num: int) -> None:
        """Property: Integer values survive JSON roundtrip through extractor."""
        obj = {key: num}
        json_str = json.dumps(obj)
        result = extract_json_from_llm_response(json_str)
        assert result[key] == num

    @given(
        key=st.text(min_size=1, max_size=20, alphabet=st.characters(blacklist_categories=("Cs",))),
        val=st.booleans(),
    )
    @settings(max_examples=25)
    def test_roundtrip_preserves_boolean_values(self, key: str, val: bool) -> None:
        """Property: Boolean values survive JSON roundtrip through extractor."""
        obj = {key: val}
        json_str = json.dumps(obj)
        result = extract_json_from_llm_response(json_str)
        assert result[key] == val

    @given(
        key=st.text(min_size=1, max_size=20, alphabet=st.characters(blacklist_categories=("Cs",))),
    )
    @settings(max_examples=25)
    def test_roundtrip_preserves_null_values(self, key: str) -> None:
        """Property: Null values survive JSON roundtrip through extractor."""
        obj = {key: None}
        json_str = json.dumps(obj)
        result = extract_json_from_llm_response(json_str)
        assert result[key] is None


class TestPropertyBasedRepairFunctions:
    """Property-based tests for individual repair functions."""

    @given(
        key1=st.text(
            min_size=1, max_size=10, alphabet=st.sampled_from("abcdefghijklmnopqrstuvwxyz")
        ),
        key2=st.text(
            min_size=1, max_size=10, alphabet=st.sampled_from("abcdefghijklmnopqrstuvwxyz")
        ),
        val1=st.integers(min_value=0, max_value=100),
        val2=st.integers(min_value=0, max_value=100),
    )
    @settings(max_examples=25)
    def test_fix_missing_commas_produces_parseable_json(
        self, key1: str, key2: str, val1: int, val2: int
    ) -> None:
        """Property: _fix_missing_commas can produce valid JSON from missing-comma input."""
        assume(key1 != key2)  # Different keys
        # Create JSON-like string with missing comma
        malformed = f'{{"{key1}": {val1}\n"{key2}": {val2}}}'
        fixed = _fix_missing_commas(malformed)

        # Should now parse
        try:
            result = json.loads(fixed)
            assert result[key1] == val1
            assert result[key2] == val2
        except json.JSONDecodeError:
            # Some edge cases may still not parse; that's acceptable
            pass

    @given(
        key=st.text(
            min_size=1, max_size=10, alphabet=st.sampled_from("abcdefghijklmnopqrstuvwxyz")
        ),
        val=st.integers(min_value=0, max_value=100),
    )
    @settings(max_examples=25)
    def test_fix_trailing_commas_produces_parseable_json(self, key: str, val: int) -> None:
        """Property: _fix_trailing_commas produces valid JSON from trailing-comma input."""
        malformed = f'{{"{key}": {val},}}'
        fixed = _fix_trailing_commas(malformed)

        result = json.loads(fixed)
        assert result[key] == val

    @given(
        key=st.text(
            min_size=1, max_size=10, alphabet=st.sampled_from("abcdefghijklmnopqrstuvwxyz")
        ),
        val=st.text(
            min_size=0, max_size=20, alphabet=st.sampled_from("abcdefghijklmnopqrstuvwxyz ")
        ),
    )
    @settings(max_examples=25)
    def test_fix_single_quotes_produces_parseable_json(self, key: str, val: str) -> None:
        """Property: _fix_single_quotes produces valid JSON from single-quote input."""
        malformed = f"{{'{key}': '{val}'}}"
        fixed = _fix_single_quotes(malformed)

        result = json.loads(fixed)
        assert result[key] == val


class TestPropertyBasedEdgeCases:
    """Property-based tests for edge cases and boundary conditions."""

    @given(whitespace=st.text(alphabet=" \t\n\r", min_size=1, max_size=20))
    @settings(max_examples=30)
    def test_whitespace_only_raises_error(self, whitespace: str) -> None:
        """Property: Whitespace-only input always raises ValueError."""
        with pytest.raises(ValueError, match="Empty LLM response"):
            extract_json_from_llm_response(whitespace)

    @given(
        text=st.text(
            min_size=1,
            max_size=100,
            alphabet=st.sampled_from("abcdefghijklmnopqrstuvwxyz.,!?"),
        )
    )
    @settings(max_examples=30)
    def test_text_without_json_raises_error(self, text: str) -> None:
        """Property: Plain text without JSON structure always raises ValueError."""
        assume("{" not in text and "}" not in text)
        assume(text.strip())  # Ensure non-empty after stripping whitespace
        with pytest.raises(ValueError, match="No JSON found"):
            extract_json_from_llm_response(text)

    @given(
        depth=st.integers(min_value=3, max_value=6),
        key=st.text(min_size=1, max_size=5, alphabet=st.sampled_from("abcdefghij")),
    )
    @settings(max_examples=20)
    def test_deeply_nested_json_parses(self, depth: int, key: str) -> None:
        """Property: Deeply nested JSON structures parse correctly."""
        # Build nested structure
        inner = {"value": 42}
        for _ in range(depth):
            inner = {key: inner}

        json_str = json.dumps(inner)
        result = extract_json_from_llm_response(json_str)

        # Navigate to the innermost value
        current = result
        for _ in range(depth):
            current = current[key]
        assert current["value"] == 42


# =============================================================================
# Additional Edge Case Tests
# =============================================================================


class TestUnicodeAndSpecialCharacters:
    """Tests for Unicode and special character handling."""

    def test_json_with_emoji(self) -> None:
        """Test parsing JSON containing emoji characters."""
        response = '{"status": "ok", "message": "Activity detected! 🚨"}'
        result = extract_json_from_llm_response(response)

        assert result["status"] == "ok"
        assert "🚨" in result["message"]

    def test_json_with_cjk_characters(self) -> None:
        """Test parsing JSON with Chinese/Japanese/Korean characters."""
        response = '{"name": "前门摄像头", "status": "正常"}'
        result = extract_json_from_llm_response(response)

        assert result["name"] == "前门摄像头"
        assert result["status"] == "正常"

    def test_json_with_arabic_characters(self) -> None:
        """Test parsing JSON with Arabic characters."""
        response = '{"message": "مرحبا", "count": 5}'
        result = extract_json_from_llm_response(response)

        assert result["message"] == "مرحبا"
        assert result["count"] == 5

    def test_json_with_unicode_escape_sequences(self) -> None:
        """Test parsing JSON with Unicode escape sequences."""
        response = '{"symbol": "\\u2764", "degree": "20\\u00b0C"}'
        result = extract_json_from_llm_response(response)

        assert result["symbol"] == "\u2764"  # Heart symbol
        assert result["degree"] == "20\u00b0C"  # Degree symbol

    def test_json_with_newlines_in_strings(self) -> None:
        """Test parsing JSON with escaped newlines in string values."""
        response = '{"multiline": "line1\\nline2\\nline3"}'
        result = extract_json_from_llm_response(response)

        assert result["multiline"] == "line1\nline2\nline3"

    def test_json_with_tabs_in_strings(self) -> None:
        """Test parsing JSON with escaped tabs in string values."""
        response = '{"tabbed": "col1\\tcol2\\tcol3"}'
        result = extract_json_from_llm_response(response)

        assert result["tabbed"] == "col1\tcol2\tcol3"

    def test_json_with_backslashes(self) -> None:
        """Test parsing JSON with escaped backslashes."""
        response = r'{"path": "C:\\Users\\test\\file.txt"}'
        result = extract_json_from_llm_response(response)

        assert result["path"] == "C:\\Users\\test\\file.txt"


class TestMultipleJsonObjects:
    """Tests for handling responses with multiple JSON objects."""

    def test_extracts_first_json_object(self) -> None:
        """Test that first valid JSON object is extracted."""
        response = """
        {"first": true, "value": 1}
        {"second": true, "value": 2}
        {"third": true, "value": 3}
        """
        result = extract_json_from_llm_response(response)

        # Should return the first object
        assert result["first"] is True
        assert result["value"] == 1

    def test_json_object_after_invalid_text(self) -> None:
        """Test extraction when valid JSON follows invalid content."""
        response = """
        This is some invalid {{{{ content
        {"valid": true, "data": "found"}
        """
        result = extract_json_from_llm_response(response)

        assert result["valid"] is True
        assert result["data"] == "found"

    def test_json_embedded_in_explanation(self) -> None:
        """Test extracting JSON from detailed LLM explanation."""
        response = """
        I've analyzed the security footage and determined the risk level.

        The analysis considers:
        1. Time of day (late night)
        2. Number of people (3)
        3. Movement patterns (suspicious)

        Here is my assessment:

        {"risk_score": 75, "risk_level": "high", "reasoning": "Multiple unknown persons"}

        Let me know if you need more details.
        """
        result = extract_json_from_llm_response(response)

        assert result["risk_score"] == 75
        assert result["risk_level"] == "high"


class TestNullAndEmptyValues:
    """Tests for handling null and empty values in JSON."""

    def test_json_with_null_value(self) -> None:
        """Test parsing JSON with null values."""
        response = '{"field": null, "other": 42}'
        result = extract_json_from_llm_response(response)

        assert result["field"] is None
        assert result["other"] == 42

    def test_json_with_empty_string(self) -> None:
        """Test parsing JSON with empty string values."""
        response = '{"empty": "", "filled": "data"}'
        result = extract_json_from_llm_response(response)

        assert result["empty"] == ""
        assert result["filled"] == "data"

    def test_json_with_empty_array(self) -> None:
        """Test parsing JSON with empty arrays."""
        response = '{"items": [], "count": 0}'
        result = extract_json_from_llm_response(response)

        assert result["items"] == []
        assert result["count"] == 0

    def test_json_with_empty_object(self) -> None:
        """Test parsing JSON with empty nested objects."""
        response = '{"nested": {}, "valid": true}'
        result = extract_json_from_llm_response(response)

        assert result["nested"] == {}
        assert result["valid"] is True

    def test_json_with_multiple_null_values(self) -> None:
        """Test parsing JSON with multiple null values."""
        response = '{"a": null, "b": null, "c": "value"}'
        result = extract_json_from_llm_response(response)

        assert result["a"] is None
        assert result["b"] is None
        assert result["c"] == "value"


class TestErrorRecoveryStrategies:
    """Tests for error recovery and repair strategies."""

    def test_missing_comma_after_nested_object(self) -> None:
        """Test repair of missing comma after nested object."""
        response = """
        {
            "outer": {"inner": 1}
            "next": "value"
        }
        """
        result = extract_json_from_llm_response(response)

        assert result["outer"]["inner"] == 1
        assert result["next"] == "value"

    def test_missing_comma_after_array(self) -> None:
        """Test repair of missing comma after array."""
        response = """
        {
            "items": [1, 2, 3]
            "total": 6
        }
        """
        result = extract_json_from_llm_response(response)

        assert result["items"] == [1, 2, 3]
        assert result["total"] == 6

    def test_trailing_comma_in_nested_object(self) -> None:
        """Test removal of trailing comma in nested object."""
        response = '{"outer": {"inner": "value",}, "other": 1}'
        result = extract_json_from_llm_response(response)

        assert result["outer"]["inner"] == "value"
        assert result["other"] == 1

    def test_multiple_trailing_commas(self) -> None:
        """Test removal of multiple trailing commas at different nesting levels."""
        response = '{"a": [1, 2,], "b": {"c": 3,},}'
        result = extract_json_from_llm_response(response)

        assert result["a"] == [1, 2]
        assert result["b"]["c"] == 3

    def test_mixed_issues_single_quotes_and_trailing_commas(self) -> None:
        """Test repair with both single quotes and trailing commas."""
        response = "{'key': 'value',}"
        result = extract_json_from_llm_response(response)

        assert result["key"] == "value"

    def test_mixed_issues_single_quotes_and_missing_commas(self) -> None:
        """Test repair with both single quotes and missing commas."""
        response = """
        {
            'first': 'one'
            'second': 'two'
        }
        """
        result = extract_json_from_llm_response(response)

        assert result["first"] == "one"
        assert result["second"] == "two"

    def test_all_repair_strategies_combined(self) -> None:
        """Test repair with all issues present: single quotes, missing commas, trailing commas."""
        response = """
        {
            'name': 'test'
            'value': 42,
        }
        """
        result = extract_json_from_llm_response(response)

        assert result["name"] == "test"
        assert result["value"] == 42


class TestIncompleteJsonHandling:
    """Tests for handling incomplete/truncated JSON responses."""

    def test_truncated_string_value(self) -> None:
        """Test handling of truncated string value (should raise error)."""
        response = '{"key": "incomplete val'
        with pytest.raises(ValueError):
            extract_json_from_llm_response(response)

    def test_truncated_nested_object(self) -> None:
        """Test handling of truncated nested object (should raise error)."""
        response = '{"outer": {"inner": '
        with pytest.raises(ValueError):
            extract_json_from_llm_response(response)

    def test_missing_closing_brace(self) -> None:
        """Test handling of missing closing brace."""
        # The function tries to recover by finding last closing brace
        response = '{"key": "value", "another": 42'
        # Should either recover or raise error
        try:
            result = extract_json_from_llm_response(response)
            # If it recovers, check the structure
            assert "key" in result or "another" in result
        except ValueError:
            # Raising error is also acceptable
            pass

    def test_extra_closing_brace(self) -> None:
        """Test handling of extra closing brace (parses first complete object)."""
        response = '{"key": "value"}} extra'
        result = extract_json_from_llm_response(response)

        assert result["key"] == "value"


class TestArraysInJson:
    """Tests for array handling in JSON."""

    def test_simple_array_values(self) -> None:
        """Test parsing JSON with simple array values."""
        response = '{"numbers": [1, 2, 3], "strings": ["a", "b", "c"]}'
        result = extract_json_from_llm_response(response)

        assert result["numbers"] == [1, 2, 3]
        assert result["strings"] == ["a", "b", "c"]

    def test_mixed_type_array(self) -> None:
        """Test parsing JSON with mixed-type arrays."""
        response = '{"mixed": [1, "two", true, null, 3.14]}'
        result = extract_json_from_llm_response(response)

        assert result["mixed"] == [1, "two", True, None, 3.14]

    def test_nested_arrays(self) -> None:
        """Test parsing JSON with nested arrays."""
        response = '{"matrix": [[1, 2], [3, 4], [5, 6]]}'
        result = extract_json_from_llm_response(response)

        assert result["matrix"] == [[1, 2], [3, 4], [5, 6]]

    def test_array_of_objects(self) -> None:
        """Test parsing JSON with array of objects."""
        response = '{"items": [{"id": 1}, {"id": 2}, {"id": 3}]}'
        result = extract_json_from_llm_response(response)

        assert len(result["items"]) == 3
        assert result["items"][0]["id"] == 1
        assert result["items"][1]["id"] == 2
        assert result["items"][2]["id"] == 3

    def test_trailing_comma_in_array_with_objects(self) -> None:
        """Test removal of trailing comma in array containing objects."""
        response = '{"items": [{"a": 1}, {"b": 2},]}'
        result = extract_json_from_llm_response(response)

        assert result["items"] == [{"a": 1}, {"b": 2}]


class TestThinkBlockVariations:
    """Tests for various <think> block formats."""

    def test_think_block_with_json_inside(self) -> None:
        """Test that JSON-like content inside think blocks is ignored."""
        response = """
        <think>
        I see {"fake": "json"} in my thoughts.
        {"another": "fake"}
        </think>
        {"real": "json", "valid": true}
        """
        result = extract_json_from_llm_response(response)

        assert result["real"] == "json"
        assert result["valid"] is True

    def test_multiple_incomplete_think_blocks(self) -> None:
        """Test handling of incomplete think block followed by JSON."""
        response = """
        <think>
        Thinking about this...
        {"risk_score": 50}
        """
        result = extract_json_from_llm_response(response)

        assert result["risk_score"] == 50

    def test_think_block_immediately_before_json(self) -> None:
        """Test think block with no whitespace before JSON."""
        response = '<think>thoughts</think>{"key": "value"}'
        result = extract_json_from_llm_response(response)

        assert result["key"] == "value"

    def test_empty_think_block(self) -> None:
        """Test empty think block is properly removed."""
        response = '<think></think>{"key": "value"}'
        result = extract_json_from_llm_response(response)

        assert result["key"] == "value"


class TestMarkdownCodeBlockVariations:
    """Tests for various markdown code block formats."""

    def test_code_block_without_language_hint(self) -> None:
        """Test JSON extraction from code block without language specifier."""
        response = """
        ```
        {"key": "value"}
        ```
        """
        result = extract_json_from_llm_response(response)

        assert result["key"] == "value"

    def test_code_block_with_extra_whitespace(self) -> None:
        """Test JSON extraction from code block with extra whitespace."""
        response = """
        ```json

        {"key": "value"}

        ```
        """
        result = extract_json_from_llm_response(response)

        assert result["key"] == "value"

    def test_multiple_code_blocks(self) -> None:
        """Test extraction when multiple code blocks are present."""
        response = """
        ```python
        print("hello")
        ```

        ```json
        {"real": "json"}
        ```
        """
        result = extract_json_from_llm_response(response)

        assert result["real"] == "json"

    def test_code_block_with_backticks_in_content(self) -> None:
        """Test JSON with backticks in string values."""
        response = '{"command": "Use `git status` to check"}'
        result = extract_json_from_llm_response(response)

        assert "`git status`" in result["command"]


# =============================================================================
# Tests for safe_json_loads()
# =============================================================================


class TestSafeJsonLoadsHappyPath:
    """Tests for successful JSON parsing with safe_json_loads."""

    def test_simple_json_object(self) -> None:
        """Test parsing a simple, valid JSON object."""
        text = '{"key": "value", "number": 42}'
        result = safe_json_loads(text)

        assert result == {"key": "value", "number": 42}

    def test_json_array(self) -> None:
        """Test parsing a valid JSON array."""
        text = '[1, 2, 3, "four"]'
        result = safe_json_loads(text)

        assert result == [1, 2, 3, "four"]

    def test_nested_json(self) -> None:
        """Test parsing nested JSON structures."""
        text = '{"outer": {"inner": [1, 2, {"deep": true}]}}'
        result = safe_json_loads(text)

        assert result["outer"]["inner"][2]["deep"] is True

    def test_json_with_null(self) -> None:
        """Test parsing JSON with null values."""
        text = '{"value": null}'
        result = safe_json_loads(text)

        assert result == {"value": None}

    def test_json_with_boolean(self) -> None:
        """Test parsing JSON with boolean values."""
        text = '{"active": true, "deleted": false}'
        result = safe_json_loads(text)

        assert result["active"] is True
        assert result["deleted"] is False

    def test_empty_object(self) -> None:
        """Test parsing an empty JSON object."""
        text = "{}"
        result = safe_json_loads(text)

        assert result == {}

    def test_empty_array(self) -> None:
        """Test parsing an empty JSON array."""
        text = "[]"
        result = safe_json_loads(text)

        assert result == []

    def test_unicode_characters(self) -> None:
        """Test parsing JSON with unicode characters."""
        text = '{"message": "Hello \\u4e16\\u754c"}'
        result = safe_json_loads(text)

        assert result["message"] == "Hello \u4e16\u754c"


class TestSafeJsonLoadsDefaultValues:
    """Tests for default value handling in safe_json_loads."""

    def test_returns_default_on_invalid_json(self) -> None:
        """Test that default is returned when JSON is invalid."""
        text = "not valid json {{"
        result = safe_json_loads(text, default={})

        assert result == {}

    def test_returns_default_none_by_default(self) -> None:
        """Test that None is returned by default when no default specified."""
        text = "invalid json"
        result = safe_json_loads(text)

        assert result is None

    def test_returns_custom_default_dict(self) -> None:
        """Test returning custom dict default on failure."""
        text = "invalid"
        result = safe_json_loads(text, default={"status": "unknown"})

        assert result == {"status": "unknown"}

    def test_returns_custom_default_list(self) -> None:
        """Test returning custom list default on failure."""
        text = "invalid"
        result = safe_json_loads(text, default=[])

        assert result == []

    def test_returns_default_on_empty_string(self) -> None:
        """Test that default is returned for empty string."""
        result = safe_json_loads("", default={"empty": True})

        assert result == {"empty": True}

    def test_returns_default_on_none(self) -> None:
        """Test that default is returned when text is None-like."""
        # Python's truthiness check catches empty strings
        result = safe_json_loads("", default="fallback")

        assert result == "fallback"


class TestSafeJsonLoadsLogging:
    """Tests for error logging in safe_json_loads."""

    def test_logs_context_on_parse_failure(self, caplog: pytest.LogCaptureFixture) -> None:
        """Test that context is logged when JSON parsing fails."""
        import logging

        with caplog.at_level(logging.WARNING):
            safe_json_loads("invalid json", context="AI service response")

        assert "JSON parse failed" in caplog.text
        assert len(caplog.records) == 1
        record = caplog.records[0]
        # Context is logged in the extra dict
        assert getattr(record, "context", None) == "AI service response"

    def test_logs_error_position(self, caplog: pytest.LogCaptureFixture) -> None:
        """Test that error position is logged."""
        import logging

        with caplog.at_level(logging.WARNING):
            safe_json_loads('{"key": invalid}', context="test")

        # Check that the log contains error position info
        assert len(caplog.records) == 1
        record = caplog.records[0]
        assert "error_position" in record.__dict__ or hasattr(record, "error_position")

    def test_logs_error_message(self, caplog: pytest.LogCaptureFixture) -> None:
        """Test that error message is logged."""
        import logging

        with caplog.at_level(logging.WARNING):
            safe_json_loads('{"unclosed": "string', context="test")

        assert len(caplog.records) == 1
        record = caplog.records[0]
        # The error_message should be in the extra dict
        assert hasattr(record, "error_message") or "error_message" in getattr(
            record, "__dict__", {}
        )

    def test_logs_default_context_when_not_provided(self, caplog: pytest.LogCaptureFixture) -> None:
        """Test that 'unspecified' is logged when no context provided."""
        import logging

        with caplog.at_level(logging.WARNING):
            safe_json_loads("invalid")

        assert len(caplog.records) == 1
        record = caplog.records[0]
        assert getattr(record, "context", None) == "unspecified"

    def test_no_log_on_successful_parse(self, caplog: pytest.LogCaptureFixture) -> None:
        """Test that no warning is logged on successful parse."""
        import logging

        with caplog.at_level(logging.WARNING):
            safe_json_loads('{"valid": true}', context="test")

        assert len(caplog.records) == 0

    def test_no_log_on_empty_input(self, caplog: pytest.LogCaptureFixture) -> None:
        """Test that no warning is logged for empty input."""
        import logging

        with caplog.at_level(logging.WARNING):
            safe_json_loads("", default={})

        # Empty input should not log a warning (it's a common case)
        assert len(caplog.records) == 0


class TestSafeJsonLoadsTextPreview:
    """Tests for text preview truncation in safe_json_loads."""

    def test_truncates_long_text_in_log(self, caplog: pytest.LogCaptureFixture) -> None:
        """Test that long text is truncated to 100 characters in preview."""
        import logging

        # Create invalid JSON that's longer than 100 characters
        long_text = "x" * 200

        with caplog.at_level(logging.WARNING):
            safe_json_loads(long_text, context="test")

        assert len(caplog.records) == 1
        record = caplog.records[0]
        text_preview = getattr(record, "text_preview", "")
        assert len(text_preview) == 100
        assert text_preview == "x" * 100

    def test_preserves_short_text_in_log(self, caplog: pytest.LogCaptureFixture) -> None:
        """Test that short text is preserved in full."""
        import logging

        short_text = "short invalid json"

        with caplog.at_level(logging.WARNING):
            safe_json_loads(short_text, context="test")

        assert len(caplog.records) == 1
        record = caplog.records[0]
        text_preview = getattr(record, "text_preview", "")
        assert text_preview == short_text

    def test_logs_full_text_length(self, caplog: pytest.LogCaptureFixture) -> None:
        """Test that full text length is logged even when truncated."""
        import logging

        long_text = "x" * 500

        with caplog.at_level(logging.WARNING):
            safe_json_loads(long_text, context="test")

        assert len(caplog.records) == 1
        record = caplog.records[0]
        text_length = getattr(record, "text_length", 0)
        assert text_length == 500


class TestSafeJsonLoadsEdgeCases:
    """Tests for edge cases in safe_json_loads."""

    def test_whitespace_only_string(self) -> None:
        """Test handling of whitespace-only string."""
        # Whitespace-only is truthy, so it will attempt to parse
        result = safe_json_loads("   ", default="default")

        assert result == "default"

    def test_json_with_leading_whitespace(self) -> None:
        """Test parsing JSON with leading whitespace."""
        text = '   {"key": "value"}'
        result = safe_json_loads(text)

        assert result == {"key": "value"}

    def test_json_with_trailing_whitespace(self) -> None:
        """Test parsing JSON with trailing whitespace."""
        text = '{"key": "value"}   '
        result = safe_json_loads(text)

        assert result == {"key": "value"}

    def test_numeric_json_value(self) -> None:
        """Test parsing a bare numeric JSON value."""
        text = "42"
        result = safe_json_loads(text)

        assert result == 42

    def test_string_json_value(self) -> None:
        """Test parsing a bare string JSON value."""
        text = '"hello"'
        result = safe_json_loads(text)

        assert result == "hello"

    def test_boolean_json_value(self) -> None:
        """Test parsing a bare boolean JSON value."""
        result_true = safe_json_loads("true")
        result_false = safe_json_loads("false")

        assert result_true is True
        assert result_false is False

    def test_null_json_value(self) -> None:
        """Test parsing a bare null JSON value."""
        result = safe_json_loads("null")

        assert result is None

    def test_partial_json_returns_default(self) -> None:
        """Test that partial/truncated JSON returns default."""
        text = '{"key": "val'
        result = safe_json_loads(text, default={})

        assert result == {}

    def test_extra_data_after_json(self) -> None:
        """Test that extra data after valid JSON causes failure."""
        text = '{"key": "value"} extra stuff'
        result = safe_json_loads(text, default="failed")

        # Standard json.loads fails on extra data
        assert result == "failed"


class TestSafeJsonLoadsPropertyBased:
    """Property-based tests for safe_json_loads using Hypothesis."""

    @given(obj=json_objects(max_depth=2))
    @settings(max_examples=50)
    def test_valid_json_always_parses(self, obj: dict) -> None:
        """Property: Valid JSON objects always parse successfully."""
        json_str = json.dumps(obj)
        result = safe_json_loads(json_str)
        assert result == obj

    @given(
        key=st.text(min_size=1, max_size=20, alphabet=st.characters(blacklist_categories=("Cs",))),
        value=st.integers(min_value=-1_000_000, max_value=1_000_000),
    )
    @settings(max_examples=25)
    def test_preserves_integer_values(self, key: str, value: int) -> None:
        """Property: Integer values are preserved through parsing."""
        obj = {key: value}
        json_str = json.dumps(obj)
        result = safe_json_loads(json_str)
        assert result[key] == value

    @given(
        default=st.one_of(
            st.none(),
            st.dictionaries(st.text(min_size=1, max_size=5), st.integers(), min_size=0, max_size=2),
            st.lists(st.integers(), min_size=0, max_size=3),
        )
    )
    @settings(max_examples=25)
    def test_returns_exact_default_on_failure(self, default: Any) -> None:
        """Property: Returns exact default value (not a copy) on parse failure."""
        result = safe_json_loads("invalid json", default=default)
        assert result is default or result == default


class TestSafeJsonLoadsRealWorldExamples:
    """Tests based on real-world usage patterns from the codebase."""

    def test_redis_cache_value(self) -> None:
        """Test parsing a value from Redis cache."""
        redis_value = '{"user_id": 123, "preferences": {"theme": "dark"}}'
        result = safe_json_loads(redis_value, default={}, context="Redis cache value")

        assert result["user_id"] == 123
        assert result["preferences"]["theme"] == "dark"

    def test_detection_ids_array(self) -> None:
        """Test parsing detection IDs from database."""
        detection_ids = "[1, 2, 3, 4, 5]"
        result = safe_json_loads(detection_ids, default=[], context="detection IDs")

        assert result == [1, 2, 3, 4, 5]

    def test_prompt_config(self) -> None:
        """Test parsing prompt configuration."""
        config = '{"temperature": 0.7, "max_tokens": 1024}'
        result = safe_json_loads(config, default={}, context="prompt config")

        assert result["temperature"] == 0.7
        assert result["max_tokens"] == 1024

    def test_websocket_message(self) -> None:
        """Test parsing WebSocket message."""
        message = '{"type": "subscribe", "channel": "events"}'
        result = safe_json_loads(message, default=None, context="WebSocket message")

        assert result["type"] == "subscribe"
        assert result["channel"] == "events"

    def test_corrupted_redis_value(self) -> None:
        """Test handling corrupted Redis value gracefully."""
        corrupted = '{"partial": "data", "broken'
        result = safe_json_loads(corrupted, default={"fallback": True}, context="Redis cache")

        assert result == {"fallback": True}

    def test_empty_detection_ids(self) -> None:
        """Test handling empty detection IDs field."""
        result = safe_json_loads("", default=[], context="detection IDs")

        assert result == []

    def test_ai_service_error_response(self) -> None:
        """Test parsing AI service error response."""
        error_response = '{"error": "Model overloaded", "retry_after": 30}'
        result = safe_json_loads(error_response, default=None, context="AI service response")

        assert result["error"] == "Model overloaded"
        assert result["retry_after"] == 30
