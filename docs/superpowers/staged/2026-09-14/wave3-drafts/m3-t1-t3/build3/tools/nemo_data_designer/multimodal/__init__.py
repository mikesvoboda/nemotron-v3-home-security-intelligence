"""Multimodal evaluation pipeline for comparing local detections against NVIDIA vision.

This module provides tools to evaluate the local YOLO26v2 + Nemotron pipeline
against NVIDIA's vision-capable models to generate ground truth and validate
detection accuracy.

Components:
    - NVIDIAVisionAnalyzer: Wrapper for NVIDIA vision API calls
    - MultimodalGroundTruthGenerator: Generate ground truth from curated images
    - PipelineComparator: Compare local pipeline outputs against NVIDIA ground truth

Usage:
    from tools.nemo_data_designer.multimodal import (
        NVIDIAVisionAnalyzer,
        MultimodalGroundTruthGenerator,
        PipelineComparator,
    )

    # Analyze images with NVIDIA vision
    analyzer = NVIDIAVisionAnalyzer()
    result = await analyzer.analyze_image(Path("image.jpg"))

    # Generate ground truth dataset
    generator = MultimodalGroundTruthGenerator(image_dir, analyzer)
    ground_truth_df = await generator.generate_ground_truth()

    # Compare local pipeline to NVIDIA ground truth
    comparator = PipelineComparator()
    report = comparator.generate_comparison_report(local_results, nvidia_ground_truth)
"""

from tools.nemo_data_designer.multimodal.ground_truth_generator import (
    MultimodalGroundTruthGenerator,
)
from tools.nemo_data_designer.multimodal.image_analyzer import (
    NVIDIAVisionAnalyzer,
    VisionAnalysisResult,
)
from tools.nemo_data_designer.multimodal.pipeline_comparator import (
    PipelineComparator,
)

__all__ = [
    "MultimodalGroundTruthGenerator",
    "NVIDIAVisionAnalyzer",
    "PipelineComparator",
    "VisionAnalysisResult",
]
