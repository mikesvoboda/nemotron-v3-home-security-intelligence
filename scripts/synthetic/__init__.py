# ABOUTME: Package for synthetic data generation system for testing the Home Security Intelligence pipeline.
# ABOUTME: Provides tools for generating synthetic security camera footage with known ground truth labels.
"""
Synthetic Data Generation Package.

This package provides tools for generating synthetic security camera footage
using NVIDIA's inference API (Veo 3.1 for videos, Gemini for images) and
running A/B comparison tests against the AI pipeline.

Modules:
    - prompt_generator: Converts structured scenario specs to natural language prompts
    - media_generator: Handles Veo 3.1 (video) and Gemini (image) API calls
    - comparison_engine: A/B testing logic comparing pipeline output to expected labels
    - report_generator: Creates JSON test reports

Usage:
    from scripts.synthetic import PromptGenerator, MediaGenerator

    # Generate a prompt from a scenario spec
    generator = PromptGenerator()
    prompt = generator.generate_prompt(scenario_spec)

    # Generate media using the prompt
    media_gen = MediaGenerator()
    result = media_gen.generate_video(prompt)
"""

from scripts.synthetic.comparison_engine import (
    ComparisonEngine,
    ComparisonResult,
    FieldResult,
)
from scripts.synthetic.media_generator import (
    GenerationResult,
    GenerationTimeoutError,
    MediaGenerator,
    MediaGeneratorError,
    MediaStatus,
    generate_image_sync,
    generate_video_sync,
)
from scripts.synthetic.prompt_generator import (
    CAMERA_EFFECT_DESCRIPTIONS,
    SECURITY_CAMERA_PROMPT,
    TIME_OF_DAY_DESCRIPTIONS,
    WEATHER_DESCRIPTIONS,
    PromptGenerator,
    generate_prompt_from_file,
)
from scripts.synthetic.report_generator import (
    FailureDetail,
    ModelResult,
    ReportGenerator,
    ReportSummary,
    SampleModelResult,
    TestReport,
)
from scripts.synthetic.stock_footage import (
    CATEGORY_SEARCH_TERMS,
    SCENARIO_SEARCH_TERMS,
    StockFootageDownloader,
    StockFootageError,
    StockResult,
    StockSource,
    download_stock_sync,
    search_stock_sync,
)

__all__ = [
    "CAMERA_EFFECT_DESCRIPTIONS",
    "CATEGORY_SEARCH_TERMS",
    "SCENARIO_SEARCH_TERMS",
    "SECURITY_CAMERA_PROMPT",
    "TIME_OF_DAY_DESCRIPTIONS",
    "WEATHER_DESCRIPTIONS",
    # Comparison engine
    "ComparisonEngine",
    "ComparisonResult",
    "FailureDetail",
    "FieldResult",
    "GenerationResult",
    "GenerationTimeoutError",
    # Media generation
    "MediaGenerator",
    "MediaGeneratorError",
    "MediaStatus",
    "ModelResult",
    # Prompt generation
    "PromptGenerator",
    # Report generation
    "ReportGenerator",
    "ReportSummary",
    "SampleModelResult",
    # Stock footage
    "StockFootageDownloader",
    "StockFootageError",
    "StockResult",
    "StockSource",
    "TestReport",
    "download_stock_sync",
    "generate_image_sync",
    "generate_prompt_from_file",
    "generate_video_sync",
    "search_stock_sync",
]
