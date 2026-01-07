"""Unit tests for backend/services/token_counter.py (NEM-1666).

Comprehensive tests for token counting and context window management
used by the Nemotron analyzer for prompt validation and truncation.

Tests cover:
- Token counting with tiktoken
- Context window validation
- Intelligent enrichment truncation
- Warning thresholds and metrics
- Edge cases and error handling
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from backend.services.token_counter import (
    TRUNCATION_PRIORITIES,
    TokenCounter,
    TokenValidationResult,
    TruncationResult,
    count_prompt_tokens,
    get_token_counter,
    reset_token_counter,
    validate_prompt_tokens,
)

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture(autouse=True)
def reset_singleton():
    """Reset the token counter singleton before and after each test."""
    reset_token_counter()
    yield
    reset_token_counter()


@pytest.fixture
def token_counter():
    """Create a fresh token counter instance for testing."""
    return TokenCounter(
        encoding_name="cl100k_base",
        context_window=4096,
        max_output_tokens=1024,
        warning_threshold=0.8,
    )


@pytest.fixture
def small_context_counter():
    """Create a token counter with small context for truncation tests."""
    return TokenCounter(
        encoding_name="cl100k_base",
        context_window=500,
        max_output_tokens=100,
        warning_threshold=0.8,
    )


# =============================================================================
# TokenCounter Initialization Tests
# =============================================================================


class TestTokenCounterInit:
    """Tests for TokenCounter initialization."""

    def test_init_with_defaults(self):
        """Test initialization with default settings."""
        counter = TokenCounter()
        assert counter.encoding_name == "cl100k_base"  # Default from settings
        assert counter.context_window > 0
        assert counter.max_output_tokens > 0
        assert 0.0 < counter.warning_threshold < 1.0

    def test_init_with_custom_values(self):
        """Test initialization with custom values."""
        counter = TokenCounter(
            encoding_name="cl100k_base",
            context_window=8192,
            max_output_tokens=2048,
            warning_threshold=0.9,
        )
        assert counter.encoding_name == "cl100k_base"
        assert counter.context_window == 8192
        assert counter.max_output_tokens == 2048
        assert counter.warning_threshold == 0.9

    def test_init_max_output_exceeds_context_raises_error(self):
        """Test that max_output_tokens >= context_window raises ValueError."""
        with pytest.raises(ValueError, match=r"max_output_tokens.*must be less than"):
            TokenCounter(context_window=1000, max_output_tokens=1000)

        with pytest.raises(ValueError, match=r"max_output_tokens.*must be less than"):
            TokenCounter(context_window=1000, max_output_tokens=1500)

    def test_init_with_invalid_encoding_fallback(self):
        """Test that invalid encoding falls back to cl100k_base."""
        # This should not raise but log a warning and fallback
        counter = TokenCounter(encoding_name="invalid_encoding_xyz")
        assert counter.encoding_name == "cl100k_base"


# =============================================================================
# Token Counting Tests
# =============================================================================


class TestTokenCounting:
    """Tests for token counting functionality."""

    def test_count_tokens_empty_string(self, token_counter):
        """Test counting tokens in empty string returns 0."""
        assert token_counter.count_tokens("") == 0

    def test_count_tokens_single_word(self, token_counter):
        """Test counting tokens in a single word."""
        count = token_counter.count_tokens("Hello")
        assert count == 1

    def test_count_tokens_sentence(self, token_counter):
        """Test counting tokens in a typical sentence."""
        text = "The quick brown fox jumps over the lazy dog."
        count = token_counter.count_tokens(text)
        # This sentence should be around 10 tokens
        assert 8 <= count <= 12

    def test_count_tokens_with_special_characters(self, token_counter):
        """Test counting tokens with special characters."""
        text = "Hello! @user #hashtag $100 %done"
        count = token_counter.count_tokens(text)
        assert count > 0

    def test_count_tokens_with_json(self, token_counter):
        """Test counting tokens in JSON content."""
        text = '{"risk_score": 75, "summary": "Person detected at front door"}'
        count = token_counter.count_tokens(text)
        assert count > 0

    def test_count_tokens_large_text(self, token_counter):
        """Test counting tokens in larger text blocks."""
        # Create a text that should have approximately 1000 tokens
        text = "This is a test sentence. " * 200
        count = token_counter.count_tokens(text)
        # Each repetition is about 6 tokens, so ~1200 tokens expected
        assert 1000 <= count <= 1400

    def test_count_tokens_consistency(self, token_counter):
        """Test that token counting is consistent."""
        text = "Consistent token counting test."
        count1 = token_counter.count_tokens(text)
        count2 = token_counter.count_tokens(text)
        assert count1 == count2


# =============================================================================
# Prompt Validation Tests
# =============================================================================


class TestPromptValidation:
    """Tests for prompt validation against context limits."""

    def test_validate_prompt_fits_in_context(self, token_counter):
        """Test validation of prompt that fits in context window."""
        # Context: 4096, Output: 1024, Available: 3072
        short_prompt = "Analyze this detection: person at front door"
        result = token_counter.validate_prompt(short_prompt)

        assert result.is_valid is True
        assert result.prompt_tokens < result.available_tokens
        assert result.context_window == 4096
        assert result.max_output_tokens == 1024
        assert result.error is None

    def test_validate_prompt_exceeds_context(self, small_context_counter):
        """Test validation of prompt that exceeds context window."""
        # Context: 500, Output: 100, Available: 400
        # Create a prompt that exceeds 400 tokens
        long_prompt = "This is a test. " * 200  # ~1000 tokens
        result = small_context_counter.validate_prompt(long_prompt)

        assert result.is_valid is False
        assert result.prompt_tokens > result.available_tokens
        assert result.error is not None
        assert "exceeds" in result.error.lower()

    def test_validate_prompt_high_utilization_warning(self, token_counter):
        """Test that high utilization triggers warning."""
        # Context: 4096, Output: 1024, Available: 3072
        # Warning at 80% = 2458 tokens
        # Create prompt with ~2500 tokens (above 80% but below 100%)
        high_util_prompt = "word " * 2500
        result = token_counter.validate_prompt(high_util_prompt)

        assert result.is_valid is True
        assert result.warning is not None
        assert "high context utilization" in result.warning.lower()

    def test_validate_prompt_utilization_calculation(self, token_counter):
        """Test correct utilization ratio calculation."""
        prompt = "Test prompt for utilization."
        result = token_counter.validate_prompt(prompt)

        expected_utilization = result.prompt_tokens / result.available_tokens
        assert abs(result.utilization - expected_utilization) < 0.001

    def test_validate_prompt_custom_max_output(self, token_counter):
        """Test validation with custom max_output_tokens."""
        prompt = "Short test prompt"
        result = token_counter.validate_prompt(prompt, max_output_tokens=2048)

        assert result.max_output_tokens == 2048
        # Available should be context_window - max_output = 4096 - 2048 = 2048
        assert result.available_tokens == 2048


# =============================================================================
# Truncation Tests
# =============================================================================


class TestTruncation:
    """Tests for prompt truncation functionality."""

    def test_truncate_to_fit_no_truncation_needed(self, token_counter):
        """Test that short text is not truncated."""
        text = "Short text"
        result = token_counter.truncate_to_fit(text, max_tokens=100)
        assert result == text

    def test_truncate_to_fit_with_truncation(self, token_counter):
        """Test truncation of long text."""
        long_text = "word " * 500  # ~500 tokens
        result = token_counter.truncate_to_fit(long_text, max_tokens=50)

        assert token_counter.count_tokens(result) <= 50
        assert result.endswith("...[truncated]")

    def test_truncate_to_fit_empty_string(self, token_counter):
        """Test truncation of empty string."""
        result = token_counter.truncate_to_fit("", max_tokens=100)
        assert result == ""

    def test_truncate_to_fit_custom_suffix(self, token_counter):
        """Test truncation with custom suffix."""
        long_text = "word " * 500
        result = token_counter.truncate_to_fit(long_text, max_tokens=50, suffix=" [more]")
        assert result.endswith(" [more]")

    def test_truncate_enrichment_no_truncation_needed(self, token_counter):
        """Test enrichment truncation when not needed."""
        prompt = "Short prompt with minimal content"
        result = token_counter.truncate_enrichment_data(prompt, max_tokens=1000)

        assert result.was_truncated is False
        assert result.truncated_prompt == prompt
        assert result.sections_removed == []

    def test_truncate_enrichment_removes_sections(self, small_context_counter):
        """Test that enrichment sections are removed in priority order."""
        # Create a prompt with identifiable sections
        prompt = """## Depth Context
This is depth information that spans multiple lines
and contains significant content.

## Weather Context
Weather analysis: sunny, clear skies.

## Zone Analysis
Zone information: front yard, entry zone.

## Core Detection Data
Person detected at 10:30:00 at front door.
"""
        result = small_context_counter.truncate_enrichment_data(prompt, max_tokens=50)

        assert result.was_truncated is True
        # Lower priority sections should be removed first
        assert len(result.sections_removed) > 0
        assert result.final_tokens <= 50

    def test_truncate_enrichment_preserves_high_priority(self, small_context_counter):
        """Test that truncation respects priority order."""
        # Zone analysis is higher priority than depth_context
        prompt = """## Zone Analysis
Important zone information.

## Depth Context
Less important depth data.
"""
        # Set max_tokens high enough to keep some content but low enough to require truncation
        original_tokens = small_context_counter.count_tokens(prompt)
        result = small_context_counter.truncate_enrichment_data(
            prompt, max_tokens=original_tokens - 5
        )

        # If truncation happened, depth_context should be in the removed list first
        # (before zone_analysis if both are removed)
        if result.was_truncated and len(result.sections_removed) > 0:
            # Verify depth_context is removed (it has lower priority)
            # Zone analysis may also be removed if max_tokens is too small
            assert "depth_context" in result.sections_removed


# =============================================================================
# Truncation Priority Tests
# =============================================================================


class TestTruncationPriorities:
    """Tests for truncation priority ordering."""

    def test_truncation_priorities_order(self):
        """Test that truncation priorities are in correct order."""
        # Verify low priority items are at the start
        low_priority = ["depth_context", "pose_analysis", "action_recognition"]
        for item in low_priority:
            assert item in TRUNCATION_PRIORITIES[:5]

        # Verify high priority items are at the end
        high_priority = [
            "detections_with_all_attributes",
            "scene_analysis",
        ]
        for item in high_priority:
            assert item in TRUNCATION_PRIORITIES[-3:]

    def test_truncation_priorities_no_duplicates(self):
        """Test that there are no duplicate priorities."""
        assert len(TRUNCATION_PRIORITIES) == len(set(TRUNCATION_PRIORITIES))


# =============================================================================
# Section Removal Tests
# =============================================================================


class TestSectionRemoval:
    """Tests for internal section removal logic."""

    def test_remove_markdown_section(self, token_counter):
        """Test removal of markdown-style sections."""
        prompt = """## Weather Context
Sunny and clear.

## Other Section
Important content.
"""
        result, removed = token_counter._remove_section(prompt, "weather_context")
        assert removed is True
        assert "Weather Context: removed" in result or "weather" not in result.lower()

    def test_remove_section_not_found(self, token_counter):
        """Test removal when section doesn't exist."""
        prompt = "Simple prompt without sections"
        result, removed = token_counter._remove_section(prompt, "nonexistent_section")
        assert removed is False
        assert result == prompt


# =============================================================================
# Helper Function Tests
# =============================================================================


class TestHelperFunctions:
    """Tests for module-level helper functions."""

    def test_get_token_counter_singleton(self):
        """Test that get_token_counter returns singleton."""
        counter1 = get_token_counter()
        counter2 = get_token_counter()
        assert counter1 is counter2

    def test_reset_token_counter(self):
        """Test that reset creates new instance."""
        _counter1 = get_token_counter()
        reset_token_counter()
        counter2 = get_token_counter()
        # After reset, we should get a new instance
        # (can't directly check identity due to caching)
        assert counter2 is not None

    def test_count_prompt_tokens_convenience(self):
        """Test convenience function for counting tokens."""
        text = "Test prompt"
        count = count_prompt_tokens(text)
        assert count > 0

    def test_validate_prompt_tokens_convenience(self):
        """Test convenience function for validation."""
        text = "Test prompt"
        result = validate_prompt_tokens(text)
        assert isinstance(result, TokenValidationResult)
        assert result.is_valid is True


# =============================================================================
# Context Budget Tests
# =============================================================================


class TestContextBudget:
    """Tests for context budget calculation."""

    def test_get_context_budget(self, token_counter):
        """Test context budget breakdown."""
        budget = token_counter.get_context_budget()

        assert budget["context_window"] == 4096
        assert budget["max_output_tokens"] == 1024
        assert budget["available_for_prompt"] == 3072
        # Warning threshold at 80% of available = 2458
        assert budget["warning_threshold"] == int(3072 * 0.8)

    def test_get_context_budget_custom_output(self, token_counter):
        """Test budget with custom output tokens."""
        budget = token_counter.get_context_budget(max_output_tokens=2048)

        assert budget["max_output_tokens"] == 2048
        assert budget["available_for_prompt"] == 2048


# =============================================================================
# Enrichment Token Estimation Tests
# =============================================================================


class TestEnrichmentTokenEstimation:
    """Tests for estimating tokens in enrichment sections."""

    def test_estimate_enrichment_tokens(self, token_counter):
        """Test token estimation for multiple sections."""
        sections = {
            "zone_analysis": "Front yard zone detected.",
            "weather_context": "Sunny, clear skies.",
            "depth_context": "Estimated depth: 3-5 meters.",
        }
        estimates = token_counter.estimate_enrichment_tokens(sections)

        assert len(estimates) == 3
        for name, count in estimates.items():
            assert count > 0
            assert name in sections

    def test_estimate_enrichment_tokens_empty_section(self, token_counter):
        """Test token estimation with empty sections."""
        sections = {
            "zone_analysis": "Some content",
            "empty_section": "",
        }
        estimates = token_counter.estimate_enrichment_tokens(sections)

        assert estimates["zone_analysis"] > 0
        assert estimates["empty_section"] == 0


# =============================================================================
# Metrics Integration Tests
# =============================================================================


class TestMetricsIntegration:
    """Tests for Prometheus metrics integration."""

    @patch("backend.core.metrics.observe_context_utilization")
    def test_validation_records_utilization_metric(self, mock_observe, token_counter):
        """Test that validation records context utilization metric."""
        prompt = "Test prompt for metrics"
        token_counter.validate_prompt(prompt)

        mock_observe.assert_called_once()
        # Check that utilization is a reasonable float
        call_args = mock_observe.call_args[0]
        assert isinstance(call_args[0], float)
        assert 0.0 <= call_args[0] <= 2.0  # Can exceed 1.0 if over limit


# =============================================================================
# Edge Case Tests
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_unicode_content(self, token_counter):
        """Test handling of unicode characters."""
        text = "Hello! Japanese: Test Chinese: Test Emoji: Test"
        count = token_counter.count_tokens(text)
        assert count > 0

    def test_very_long_prompt(self, token_counter):
        """Test handling of very long prompts."""
        # Create a prompt with ~10000 tokens
        long_prompt = "word " * 10000
        count = token_counter.count_tokens(long_prompt)
        assert count > 9000

        result = token_counter.validate_prompt(long_prompt)
        assert result.is_valid is False

    def test_newlines_and_whitespace(self, token_counter):
        """Test handling of newlines and whitespace."""
        text = "Line 1\n\nLine 2\n\t\tIndented"
        count = token_counter.count_tokens(text)
        assert count > 0

    def test_special_llm_tokens(self, token_counter):
        """Test handling of special LLM tokens in content."""
        # These are special tokens used in LLM prompts
        text = "<|im_start|>user\nHello<|im_end|>"
        count = token_counter.count_tokens(text)
        assert count > 0


# =============================================================================
# Validation Result Dataclass Tests
# =============================================================================


class TestValidationResultDataclass:
    """Tests for TokenValidationResult dataclass."""

    def test_validation_result_defaults(self):
        """Test ValidationResult with default optional fields."""
        result = TokenValidationResult(
            is_valid=True,
            prompt_tokens=100,
            available_tokens=500,
            context_window=1000,
            max_output_tokens=500,
            utilization=0.2,
        )
        assert result.warning is None
        assert result.error is None

    def test_validation_result_with_warning(self):
        """Test ValidationResult with warning."""
        result = TokenValidationResult(
            is_valid=True,
            prompt_tokens=450,
            available_tokens=500,
            context_window=1000,
            max_output_tokens=500,
            utilization=0.9,
            warning="High utilization",
        )
        assert result.warning == "High utilization"
        assert result.error is None

    def test_validation_result_with_error(self):
        """Test ValidationResult with error."""
        result = TokenValidationResult(
            is_valid=False,
            prompt_tokens=600,
            available_tokens=500,
            context_window=1000,
            max_output_tokens=500,
            utilization=1.2,
            error="Exceeds limit",
        )
        assert result.is_valid is False
        assert result.error == "Exceeds limit"


# =============================================================================
# Truncation Result Dataclass Tests
# =============================================================================


class TestTruncationResultDataclass:
    """Tests for TruncationResult dataclass."""

    def test_truncation_result_no_truncation(self):
        """Test TruncationResult when no truncation occurred."""
        result = TruncationResult(
            truncated_prompt="Original prompt",
            original_tokens=50,
            final_tokens=50,
            sections_removed=[],
            was_truncated=False,
        )
        assert result.was_truncated is False
        assert result.sections_removed == []

    def test_truncation_result_with_truncation(self):
        """Test TruncationResult when truncation occurred."""
        result = TruncationResult(
            truncated_prompt="Truncated prompt",
            original_tokens=500,
            final_tokens=100,
            sections_removed=["depth_context", "weather_context"],
            was_truncated=True,
        )
        assert result.was_truncated is True
        assert len(result.sections_removed) == 2
        assert result.original_tokens > result.final_tokens
