"""Unit tests for JSON parsing utilities.

Tests cover:
- extract_json_from_llm_response() - All parsing strategies and edge cases
- Malformed JSON handling (missing commas, trailing commas, single quotes)
- Markdown code block extraction
- Think/reasoning block removal
- Nested JSON handling
"""

import pytest

from backend.core.json_utils import (
    _clean_llm_response,
    _find_json_in_text,
    _fix_missing_commas,
    _fix_single_quotes,
    _fix_trailing_commas,
    extract_json_field,
    extract_json_from_llm_response,
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
