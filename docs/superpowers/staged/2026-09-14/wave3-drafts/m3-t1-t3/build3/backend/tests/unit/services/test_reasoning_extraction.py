"""Unit tests for chain-of-thought reasoning extraction (NEM-3727).

These tests cover the extract_reasoning_and_response function which parses
Nemotron LLM output containing <think>...</think> blocks for chain-of-thought
reasoning.

Test Categories:
    - Valid <think> block extraction
    - Missing <think> blocks (returns empty reasoning)
    - Malformed tags (incomplete, nested, etc.)
    - Edge cases (whitespace, multiple blocks, special characters)
"""

import pytest

from backend.services.nemotron_analyzer import extract_reasoning_and_response

# Mark all tests in this file as unit tests
pytestmark = pytest.mark.unit


class TestExtractReasoningAndResponse:
    """Tests for the extract_reasoning_and_response function."""

    # =========================================================================
    # Valid <think> Block Extraction
    # =========================================================================

    def test_extract_valid_think_block_with_json(self):
        """Test extraction with valid <think> block followed by JSON."""
        text = '<think>Analyzing the scene systematically...</think>{"risk_score": 25, "risk_level": "low"}'
        reasoning, response = extract_reasoning_and_response(text)

        assert reasoning == "Analyzing the scene systematically..."
        assert response == '{"risk_score": 25, "risk_level": "low"}'

    def test_extract_multiline_reasoning(self):
        """Test extraction with multiline reasoning content."""
        text = """<think>
Let me analyze this detection:
1. Time: 2:30 PM - normal daytime hours
2. Location: Front entrance
3. Person: Face matched to household member

Conclusion: This is likely a resident returning home.
</think>{"risk_score": 10, "risk_level": "low", "summary": "Resident arriving home"}"""

        reasoning, response = extract_reasoning_and_response(text)

        assert "Let me analyze this detection:" in reasoning
        assert "1. Time: 2:30 PM" in reasoning
        assert "Conclusion: This is likely a resident" in reasoning
        assert '{"risk_score": 10' in response
        assert "Resident arriving home" in response

    def test_extract_reasoning_with_special_characters(self):
        """Test extraction with special characters in reasoning."""
        text = '<think>Risk factors: +15 for time, -10 for known face. Score = 25.</think>{"risk_score": 25}'
        reasoning, response = extract_reasoning_and_response(text)

        assert "+15 for time" in reasoning
        assert "-10 for known face" in reasoning
        assert "Score = 25" in reasoning
        assert response == '{"risk_score": 25}'

    def test_extract_reasoning_with_newlines_and_whitespace(self):
        """Test extraction preserves internal newlines but strips outer whitespace."""
        text = """<think>

Step 1: Check time of day
Step 2: Evaluate location

</think>

{"risk_score": 30}"""

        reasoning, response = extract_reasoning_and_response(text)

        # Internal newlines preserved
        assert "Step 1:" in reasoning
        assert "Step 2:" in reasoning
        # Outer whitespace stripped
        assert not reasoning.startswith("\n")
        assert not reasoning.endswith("\n")
        # Response should be clean
        assert response == '{"risk_score": 30}'

    def test_extract_reasoning_with_unicode(self):
        """Test extraction with unicode characters in reasoning."""
        text = '<think>Analysis: Person detected near entrance. Confidence: 95%</think>{"risk_score": 40}'
        reasoning, response = extract_reasoning_and_response(text)

        assert "Person detected near entrance" in reasoning
        assert "Confidence: 95%" in reasoning

    # =========================================================================
    # No <think> Block Present
    # =========================================================================

    def test_no_think_block_returns_empty_reasoning(self):
        """Test that missing <think> block returns empty reasoning."""
        text = '{"risk_score": 50, "risk_level": "medium", "summary": "Activity detected"}'
        reasoning, response = extract_reasoning_and_response(text)

        assert reasoning == ""
        assert response == text

    def test_json_only_response(self):
        """Test handling of JSON-only response without any think blocks."""
        text = '{"risk_score": 75, "risk_level": "high"}'
        reasoning, response = extract_reasoning_and_response(text)

        assert reasoning == ""
        assert response == '{"risk_score": 75, "risk_level": "high"}'

    def test_empty_string_input(self):
        """Test handling of empty string input."""
        text = ""
        reasoning, response = extract_reasoning_and_response(text)

        assert reasoning == ""
        assert response == ""

    def test_whitespace_only_input(self):
        """Test handling of whitespace-only input."""
        text = "   \n\t  "
        reasoning, response = extract_reasoning_and_response(text)

        assert reasoning == ""
        assert response == ""

    def test_plain_text_without_json(self):
        """Test handling of plain text without JSON or think blocks."""
        text = "Some random text that is not JSON"
        reasoning, response = extract_reasoning_and_response(text)

        assert reasoning == ""
        assert response == "Some random text that is not JSON"

    # =========================================================================
    # Malformed Tags
    # =========================================================================

    def test_unclosed_think_tag_returns_original(self):
        """Test that unclosed <think> tag returns empty reasoning."""
        text = '<think>Incomplete reasoning without closing tag {"risk_score": 30}'
        reasoning, response = extract_reasoning_and_response(text)

        # No closing tag means no valid think block
        assert reasoning == ""
        # Original text returned as-is (stripped)
        assert response == text

    def test_unopened_think_tag(self):
        """Test handling of </think> without opening tag."""
        text = 'Some preamble</think>{"risk_score": 25}'
        reasoning, response = extract_reasoning_and_response(text)

        # No opening tag means no valid think block
        assert reasoning == ""
        assert response == text.strip()

    def test_mismatched_case_tags(self):
        """Test that case-sensitive tags require exact match."""
        text = '<THINK>Uppercase tags</THINK>{"risk_score": 20}'
        reasoning, response = extract_reasoning_and_response(text)

        # Uppercase tags don't match the pattern
        assert reasoning == ""
        assert response == text.strip()

    def test_extra_whitespace_in_tags(self):
        """Test that tags with internal whitespace don't match."""
        text = '< think >Content</ think >{"risk_score": 15}'
        reasoning, response = extract_reasoning_and_response(text)

        # Tags with spaces don't match
        assert reasoning == ""
        assert response == text.strip()

    def test_reversed_tags(self):
        """Test handling of reversed opening/closing tags."""
        text = '</think>Content<think>{"risk_score": 40}'
        reasoning, response = extract_reasoning_and_response(text)

        # Reversed tags don't create valid block
        assert reasoning == ""
        assert response == text.strip()

    def test_empty_think_block(self):
        """Test handling of empty <think></think> block."""
        text = '<think></think>{"risk_score": 55}'
        reasoning, response = extract_reasoning_and_response(text)

        # Empty block should extract empty reasoning
        assert reasoning == ""
        assert response == '{"risk_score": 55}'

    def test_whitespace_only_think_block(self):
        """Test handling of whitespace-only <think> block."""
        text = '<think>   \n\t  </think>{"risk_score": 60}'
        reasoning, response = extract_reasoning_and_response(text)

        # Whitespace-only block should extract to empty string after strip
        assert reasoning == ""
        assert response == '{"risk_score": 60}'

    # =========================================================================
    # Nested Content and Multiple Blocks
    # =========================================================================

    def test_nested_angle_brackets_in_reasoning(self):
        """Test that angle brackets in reasoning content are handled."""
        text = '<think>Risk is score > 50 but < 80, so medium level.</think>{"risk_score": 65}'
        reasoning, response = extract_reasoning_and_response(text)

        assert "score > 50 but < 80" in reasoning
        assert response == '{"risk_score": 65}'

    def test_json_like_content_in_reasoning(self):
        """Test handling of JSON-like content inside <think> block."""
        text = '<think>Factors: {"time": "night", "count": 2}</think>{"risk_score": 70}'
        reasoning, response = extract_reasoning_and_response(text)

        assert '{"time": "night", "count": 2}' in reasoning
        assert response == '{"risk_score": 70}'

    def test_multiple_think_blocks_extracts_first(self):
        """Test that multiple think blocks - first is extracted, all removed."""
        text = '<think>First reasoning</think><think>Second reasoning</think>{"risk_score": 45}'
        reasoning, response = extract_reasoning_and_response(text)

        # First block's content is extracted
        assert reasoning == "First reasoning"
        # Both blocks removed from response
        assert "<think>" not in response
        assert "</think>" not in response
        assert response == '{"risk_score": 45}'

    def test_think_block_with_nested_xml_like_tags(self):
        """Test <think> block containing other XML-like tags."""
        text = '<think>Analysis: <important>high priority</important> area detected</think>{"risk_score": 80}'
        reasoning, response = extract_reasoning_and_response(text)

        assert "<important>high priority</important>" in reasoning
        assert response == '{"risk_score": 80}'

    # =========================================================================
    # Edge Cases and Real-World Scenarios
    # =========================================================================

    def test_realistic_nemotron_output(self):
        """Test with realistic Nemotron chain-of-thought output."""
        text = """<think>
Let me analyze this security detection systematically:

TIME ANALYSIS:
- Detection time: 11:42 PM
- This is outside normal household activity hours (typically 7 AM - 10 PM)
- Late night activity increases baseline risk

LOCATION ANALYSIS:
- Camera: Front Entrance
- This is a sensitive entry point requiring attention

ENTITY ANALYSIS:
- 1 person detected
- No face match found in household database
- Appears to be unknown individual

BEHAVIORAL ANALYSIS:
- Person is walking toward the door
- No lingering or suspicious movement patterns
- Normal pace of approach

RISK CALCULATION:
- Base score: 20 (unknown person)
- Time modifier: +15 (late night)
- Location modifier: +10 (entry point)
- Behavior modifier: -10 (normal approach)
- Final score: 35

CONCLUSION:
Medium risk - Unknown person at entry point during late hours, but behavior
appears normal. Worth monitoring but not immediately alarming.
</think>{"risk_score": 35, "risk_level": "medium", "summary": "Unknown person approaching front entrance at night", "reasoning": "Person detected at 11:42 PM approaching front door. No face match found. Time of day and entry point location increase risk, but normal walking behavior reduces concern."}"""

        reasoning, response = extract_reasoning_and_response(text)

        # Verify reasoning extraction
        assert "TIME ANALYSIS:" in reasoning
        assert "LOCATION ANALYSIS:" in reasoning
        assert "ENTITY ANALYSIS:" in reasoning
        assert "BEHAVIORAL ANALYSIS:" in reasoning
        assert "RISK CALCULATION:" in reasoning
        assert "Final score: 35" in reasoning

        # Verify JSON response
        assert '"risk_score": 35' in response
        assert '"risk_level": "medium"' in response
        assert "<think>" not in response
        assert "</think>" not in response

    def test_think_block_at_end_of_text(self):
        """Test <think> block at the end (unusual but possible)."""
        text = '{"risk_score": 30}<think>Post-analysis notes</think>'
        reasoning, response = extract_reasoning_and_response(text)

        assert reasoning == "Post-analysis notes"
        assert response == '{"risk_score": 30}'

    def test_think_block_in_middle_of_text(self):
        """Test <think> block in the middle of text."""
        text = 'Preamble<think>Analysis here</think>{"risk_score": 40}Epilogue'
        reasoning, response = extract_reasoning_and_response(text)

        assert reasoning == "Analysis here"
        assert response == 'Preamble{"risk_score": 40}Epilogue'

    def test_very_long_reasoning_content(self):
        """Test extraction with very long reasoning content."""
        long_content = "A" * 10000  # 10KB of reasoning
        text = f"<think>{long_content}</think>" + '{"risk_score": 50}'

        reasoning, response = extract_reasoning_and_response(text)

        assert len(reasoning) == 10000
        assert reasoning == long_content
        assert response == '{"risk_score": 50}'

    def test_reasoning_with_code_blocks(self):
        """Test reasoning containing markdown code blocks."""
        text = """<think>
```python
risk = calculate_risk(time="night", person="unknown")
# Returns 45
```
Based on this calculation, medium risk.
</think>{"risk_score": 45}"""

        reasoning, response = extract_reasoning_and_response(text)

        assert "```python" in reasoning
        assert "calculate_risk" in reasoning
        assert response == '{"risk_score": 45}'

    def test_reasoning_with_html_entities(self):
        """Test reasoning containing HTML entities."""
        text = (
            '<think>Risk &gt; 50 means high alert &amp; action required</think>{"risk_score": 60}'
        )
        reasoning, response = extract_reasoning_and_response(text)

        # HTML entities preserved as-is
        assert "&gt;" in reasoning
        assert "&amp;" in reasoning

    def test_double_think_open_tags(self):
        """Test handling of double opening tags."""
        text = '<think><think>Double open</think>{"risk_score": 30}'
        reasoning, response = extract_reasoning_and_response(text)

        # Should match from first <think> to first </think>
        assert "<think>Double open" in reasoning
        assert response == '{"risk_score": 30}'


class TestExtractReasoningIntegrationWithSchema:
    """Integration tests combining extraction with LLM response schema."""

    def test_extraction_integrates_with_llm_response_schema(self):
        """Test that extracted response can be parsed by LLM schema."""
        import json

        text = '<think>Analysis complete</think>{"risk_score": 50, "risk_level": "medium", "summary": "Activity detected", "reasoning": "Standard detection"}'

        reasoning, response = extract_reasoning_and_response(text)

        # Verify we can parse the extracted JSON
        parsed = json.loads(response)
        assert parsed["risk_score"] == 50
        assert parsed["risk_level"] == "medium"

    def test_extraction_with_llm_response_with_reasoning_schema(self):
        """Test combining extraction with LLMResponseWithReasoning schema."""
        import json

        from backend.api.schemas.llm_response import (
            LLMResponseWithReasoning,
            LLMRiskResponse,
        )

        text = """<think>
Systematic analysis:
- Time: Daytime
- Person: Known resident
- Location: Driveway
Conclusion: Low risk, routine activity.
</think>{"risk_score": 15, "risk_level": "low", "summary": "Resident in driveway", "reasoning": "Known resident detected during daytime hours in normal location."}"""

        # Extract reasoning and response
        chain_of_thought, response = extract_reasoning_and_response(text)

        # Parse the JSON response
        parsed = json.loads(response)

        # Create validated risk response
        risk_response = LLMRiskResponse.model_validate(parsed)

        # Create response with reasoning
        response_with_cot = LLMResponseWithReasoning.from_risk_response(
            risk_response,
            chain_of_thought=chain_of_thought,
        )

        # Verify all fields
        assert response_with_cot.risk_score == 15
        assert response_with_cot.risk_level == "low"
        assert response_with_cot.summary == "Resident in driveway"
        assert "Known resident" in response_with_cot.reasoning
        assert "Systematic analysis:" in response_with_cot.chain_of_thought
        assert "Low risk, routine activity" in response_with_cot.chain_of_thought
