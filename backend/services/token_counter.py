"""Token counting service for LLM context window management (NEM-1666).

This module provides token counting utilities for validating prompts
against LLM context window limits and intelligently truncating content
when necessary.

Key Features:
    - Tiktoken-based token counting with configurable encoding
    - Context utilization tracking with warning thresholds
    - Intelligent truncation of enrichment data by priority
    - Prometheus metrics for context utilization monitoring

Usage:
    from backend.services.token_counter import get_token_counter

    counter = get_token_counter()

    # Count tokens in a string
    token_count = counter.count_tokens(prompt_text)

    # Validate prompt fits in context window
    result = counter.validate_prompt(
        prompt=prompt_text,
        max_output_tokens=1536,
    )
    if not result.is_valid:
        # Handle truncation or error
        truncated_prompt = counter.truncate_enrichment_data(prompt_text, max_tokens)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache

import tiktoken

from backend.core.config import get_settings
from backend.core.logging import get_logger

logger = get_logger(__name__)

# Priority order for truncation (lowest priority truncated first)
# These sections can be removed from prompts if context is exceeded
TRUNCATION_PRIORITIES = [
    "depth_context",  # Lowest priority - often not critical
    "pose_analysis",  # Future feature, placeholder text
    "action_recognition",  # Future feature, placeholder text
    "pet_classification_context",  # Nice to have but not critical
    "image_quality_context",  # Informational
    "weather_context",  # Informational
    "vehicle_damage_context",  # Can be summarized
    "vehicle_classification_context",  # Can be summarized
    "clothing_analysis_context",  # Can be summarized
    "violence_context",  # Important but can be summarized
    "reid_context",  # Important for tracking
    "cross_camera_summary",  # Important for correlation
    "baseline_comparison",  # Important for anomaly detection
    "zone_analysis",  # Important for context
    "detections_with_all_attributes",  # High priority - core data
    "scene_analysis",  # High priority - core analysis
]


@dataclass(frozen=True)
class TokenValidationResult:
    """Result of token count validation.

    Attributes:
        is_valid: Whether the prompt fits within context limits
        prompt_tokens: Number of tokens in the prompt
        available_tokens: Maximum tokens available for prompt
        context_window: Total context window size
        max_output_tokens: Tokens reserved for output
        utilization: Context utilization ratio (0.0 to 1.0)
        warning: Warning message if utilization is high but valid
        error: Error message if validation failed
    """

    is_valid: bool
    prompt_tokens: int
    available_tokens: int
    context_window: int
    max_output_tokens: int
    utilization: float
    warning: str | None = None
    error: str | None = None


@dataclass(slots=True)
class TruncationResult:
    """Result of prompt truncation operation.

    Attributes:
        truncated_prompt: The truncated prompt text
        original_tokens: Token count before truncation
        final_tokens: Token count after truncation
        sections_removed: List of sections that were removed
        was_truncated: Whether any truncation occurred
    """

    truncated_prompt: str
    original_tokens: int
    final_tokens: int
    sections_removed: list[str] = field(default_factory=list)
    was_truncated: bool = False


class TokenCounter:
    """Service for counting tokens and managing LLM context windows.

    This service uses tiktoken for accurate token counting and provides
    utilities for validating prompts and truncating content when context
    limits are approached.

    Attributes:
        encoding_name: Name of the tiktoken encoding (e.g., "cl100k_base")
        context_window: Maximum context window size in tokens
        max_output_tokens: Tokens reserved for LLM output
        warning_threshold: Utilization threshold for warnings (0.0 to 1.0)
        model_name: Name of the LLM model (for metrics labeling)
    """

    def __init__(
        self,
        encoding_name: str | None = None,
        context_window: int | None = None,
        max_output_tokens: int | None = None,
        warning_threshold: float | None = None,
        model_name: str | None = None,
    ):
        """Initialize the token counter.

        Args:
            encoding_name: Tiktoken encoding name. Defaults to settings.llm_tokenizer_encoding
            context_window: Max context window. Defaults to settings.nemotron_context_window
            max_output_tokens: Output tokens. Defaults to settings.nemotron_max_output_tokens
            warning_threshold: Warning threshold. Defaults to settings.context_utilization_warning_threshold
            model_name: Name of the LLM model. Defaults to settings.nemotron_model_name or "nemotron-mini"
        """
        settings = get_settings()

        self.encoding_name = encoding_name or settings.llm_tokenizer_encoding
        self.context_window = context_window or settings.nemotron_context_window
        self.max_output_tokens = max_output_tokens or settings.nemotron_max_output_tokens
        self.warning_threshold = warning_threshold or settings.context_utilization_warning_threshold
        # NEM-3288: Model name for context utilization metrics
        # Ensure model_name is always a string (never None)
        _model_name = (
            model_name or getattr(settings, "nemotron_model_name", None) or "nemotron-mini"
        )
        self.model_name: str = _model_name

        # Validate max_output_tokens fits in context window
        if self.max_output_tokens >= self.context_window:
            raise ValueError(
                f"max_output_tokens ({self.max_output_tokens}) must be less than "
                f"context_window ({self.context_window})"
            )

        # Load the tiktoken encoding
        try:
            self._encoding = tiktoken.get_encoding(self.encoding_name)
        except Exception as e:
            logger.warning(
                f"Failed to load tiktoken encoding '{self.encoding_name}', "
                f"falling back to cl100k_base: {e}"
            )
            self._encoding = tiktoken.get_encoding("cl100k_base")
            self.encoding_name = "cl100k_base"

        logger.debug(
            f"TokenCounter initialized: encoding={self.encoding_name}, "
            f"context_window={self.context_window}, max_output={self.max_output_tokens}"
        )

    def count_tokens(self, text: str) -> int:
        """Count the number of tokens in a text string.

        Args:
            text: The text to count tokens for

        Returns:
            Number of tokens in the text
        """
        if not text:
            return 0
        return len(self._encoding.encode(text))

    def validate_prompt(
        self,
        prompt: str,
        max_output_tokens: int | None = None,
    ) -> TokenValidationResult:
        """Validate that a prompt fits within context window limits.

        Args:
            prompt: The prompt text to validate
            max_output_tokens: Override for output tokens (defaults to instance setting)

        Returns:
            TokenValidationResult with validation details
        """
        output_tokens = max_output_tokens or self.max_output_tokens
        available_tokens = self.context_window - output_tokens
        prompt_tokens = self.count_tokens(prompt)
        utilization = prompt_tokens / available_tokens if available_tokens > 0 else 1.0

        # Record metrics
        from backend.core.metrics import (
            observe_context_utilization,
            set_llm_context_utilization_ratio,
        )

        observe_context_utilization(utilization)
        # NEM-3288: Also set the gauge metric for current context utilization
        # This enables Grafana dashboards to show real-time utilization
        set_llm_context_utilization_ratio(model=self.model_name, utilization=utilization)

        is_valid = prompt_tokens <= available_tokens
        warning = None
        error = None

        if not is_valid:
            error = (
                f"Prompt ({prompt_tokens} tokens) exceeds available context "
                f"({available_tokens} tokens = {self.context_window} window - "
                f"{output_tokens} output reserved)"
            )
            logger.warning(
                f"Context window exceeded: {error}",
                extra={
                    "prompt_tokens": prompt_tokens,
                    "available_tokens": available_tokens,
                    "context_window": self.context_window,
                    "utilization": utilization,
                },
            )
        elif utilization >= self.warning_threshold:
            warning = (
                f"High context utilization ({utilization:.1%}): "
                f"{prompt_tokens}/{available_tokens} tokens used. "
                f"Consider reducing enrichment data."
            )
            logger.warning(
                f"High context utilization: {warning}",
                extra={
                    "prompt_tokens": prompt_tokens,
                    "available_tokens": available_tokens,
                    "utilization": utilization,
                },
            )

        return TokenValidationResult(
            is_valid=is_valid,
            prompt_tokens=prompt_tokens,
            available_tokens=available_tokens,
            context_window=self.context_window,
            max_output_tokens=output_tokens,
            utilization=utilization,
            warning=warning,
            error=error,
        )

    def truncate_to_fit(
        self,
        text: str,
        max_tokens: int,
        suffix: str = "...[truncated]",
    ) -> str:
        """Truncate text to fit within a token limit.

        Performs simple truncation by removing tokens from the end.

        Args:
            text: Text to truncate
            max_tokens: Maximum tokens allowed
            suffix: Suffix to append when truncated

        Returns:
            Truncated text that fits within max_tokens
        """
        if not text:
            return text

        tokens = self._encoding.encode(text)
        if len(tokens) <= max_tokens:
            return text

        # Reserve tokens for suffix
        suffix_tokens = self.count_tokens(suffix)
        target_tokens = max_tokens - suffix_tokens

        if target_tokens <= 0:
            return suffix

        # Decode truncated tokens and append suffix
        truncated_tokens = tokens[:target_tokens]
        truncated_text: str = self._encoding.decode(truncated_tokens)

        return truncated_text + suffix

    def truncate_enrichment_data(
        self,
        prompt: str,
        max_tokens: int,
    ) -> TruncationResult:
        """Intelligently truncate enrichment sections from a prompt.

        Removes enrichment sections in priority order (lowest priority first)
        until the prompt fits within the token limit.

        Args:
            prompt: The full prompt with enrichment sections
            max_tokens: Maximum tokens allowed for the prompt

        Returns:
            TruncationResult with truncated prompt and metadata
        """
        original_tokens = self.count_tokens(prompt)

        if original_tokens <= max_tokens:
            return TruncationResult(
                truncated_prompt=prompt,
                original_tokens=original_tokens,
                final_tokens=original_tokens,
                sections_removed=[],
                was_truncated=False,
            )

        truncated_prompt = prompt
        sections_removed: list[str] = []

        # Try removing sections in priority order
        for section_name in TRUNCATION_PRIORITIES:
            if self.count_tokens(truncated_prompt) <= max_tokens:
                break

            # Try to find and remove this section
            truncated_prompt, removed = self._remove_section(truncated_prompt, section_name)
            if removed:
                sections_removed.append(section_name)
                logger.debug(
                    f"Removed section '{section_name}' to reduce prompt size",
                    extra={
                        "section": section_name,
                        "current_tokens": self.count_tokens(truncated_prompt),
                        "target_tokens": max_tokens,
                    },
                )

        final_tokens = self.count_tokens(truncated_prompt)

        # If still too large, do simple truncation as last resort
        if final_tokens > max_tokens:
            logger.warning(
                f"Section removal insufficient, performing hard truncation: "
                f"{final_tokens} -> {max_tokens} tokens"
            )
            truncated_prompt = self.truncate_to_fit(truncated_prompt, max_tokens)
            final_tokens = self.count_tokens(truncated_prompt)

        return TruncationResult(
            truncated_prompt=truncated_prompt,
            original_tokens=original_tokens,
            final_tokens=final_tokens,
            sections_removed=sections_removed,
            was_truncated=True,
        )

    def _remove_section(self, prompt: str, section_name: str) -> tuple[str, bool]:
        """Remove a named section from the prompt.

        Sections are identified by headers like "## Section Name" or "{section_name}".

        Args:
            prompt: The prompt text
            section_name: Name of the section to remove (in snake_case)

        Returns:
            Tuple of (modified_prompt, was_removed)
        """
        import re

        # Convert snake_case to Title Case for header matching
        title_case_name = section_name.replace("_", " ").title()

        # Pattern 1: Markdown header section (## Section Name\n...until next ## or end)
        markdown_pattern = rf"## {re.escape(title_case_name)}\n.*?(?=\n## |\n<\||$)"

        # Pattern 2: Template variable placeholder {section_name}
        placeholder_pattern = rf"\{{{section_name}\}}"

        # Pattern 3: Section with the snake_case name in a header
        snake_case_pattern = rf"## {re.escape(section_name)}\n.*?(?=\n## |\n<\||$)"

        for pattern in [markdown_pattern, snake_case_pattern]:
            match = re.search(pattern, prompt, re.DOTALL | re.IGNORECASE)
            if match:
                # Replace with minimal placeholder to indicate removal
                modified = (
                    prompt[: match.start()]
                    + f"[{title_case_name}: removed]\n"
                    + prompt[match.end() :]
                )
                return modified, True

        # Check for placeholder pattern
        if re.search(placeholder_pattern, prompt):
            modified = re.sub(placeholder_pattern, "[removed]", prompt)
            return modified, True

        return prompt, False

    def estimate_enrichment_tokens(
        self,
        enrichment_sections: dict[str, str],
    ) -> dict[str, int]:
        """Estimate token counts for each enrichment section.

        Useful for understanding which sections consume the most context.

        Args:
            enrichment_sections: Dict mapping section names to their content

        Returns:
            Dict mapping section names to their token counts
        """
        return {name: self.count_tokens(content) for name, content in enrichment_sections.items()}

    def get_context_budget(self, max_output_tokens: int | None = None) -> dict[str, int]:
        """Get the token budget breakdown for context window.

        Args:
            max_output_tokens: Override for output tokens

        Returns:
            Dict with context_window, max_output_tokens, available_for_prompt
        """
        output_tokens = max_output_tokens or self.max_output_tokens
        return {
            "context_window": self.context_window,
            "max_output_tokens": output_tokens,
            "available_for_prompt": self.context_window - output_tokens,
            "warning_threshold": int(
                (self.context_window - output_tokens) * self.warning_threshold
            ),
        }


# Global singleton instance
_token_counter: TokenCounter | None = None


@lru_cache(maxsize=1)
def get_token_counter() -> TokenCounter:
    """Get the global TokenCounter singleton.

    Returns:
        TokenCounter instance configured from settings
    """
    global _token_counter  # noqa: PLW0603
    if _token_counter is None:
        _token_counter = TokenCounter()
    return _token_counter


def reset_token_counter() -> None:
    """Reset the global TokenCounter singleton (for testing)."""
    global _token_counter  # noqa: PLW0603
    _token_counter = None
    get_token_counter.cache_clear()


def count_prompt_tokens(prompt: str) -> int:
    """Convenience function to count tokens in a prompt.

    Args:
        prompt: The prompt text

    Returns:
        Number of tokens
    """
    return get_token_counter().count_tokens(prompt)


def validate_prompt_tokens(
    prompt: str,
    max_output_tokens: int | None = None,
) -> TokenValidationResult:
    """Convenience function to validate a prompt's token count.

    Args:
        prompt: The prompt text to validate
        max_output_tokens: Override for output tokens

    Returns:
        TokenValidationResult with validation details
    """
    return get_token_counter().validate_prompt(prompt, max_output_tokens)
