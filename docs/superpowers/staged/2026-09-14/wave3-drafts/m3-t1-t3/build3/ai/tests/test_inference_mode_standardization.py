"""Tests for torch.inference_mode() standardization (NEM-4998).

This module tests that all inference-only code paths use torch.inference_mode()
instead of torch.no_grad(). torch.inference_mode() is preferred for inference
because it:
1. Provides better performance (additional optimizations beyond no_grad)
2. Enforces that no gradients are computed (immutable tensors)
3. Reduces memory usage by not tracking view operations

torch.no_grad() should only be used when:
1. Backward compatibility is needed with older PyTorch versions
2. Gradients may be needed later in the same function scope
"""

from __future__ import annotations

import ast
import inspect
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from collections.abc import Iterator

# Root directory for AI module
AI_ROOT = Path(__file__).parent.parent


class NoGradVisitor(ast.NodeVisitor):
    """AST visitor to find torch.no_grad() usage in inference paths."""

    def __init__(self, filename: str) -> None:
        self.filename = filename
        self.no_grad_usages: list[tuple[int, str]] = []
        self.inference_mode_usages: list[tuple[int, str]] = []
        self._in_function: str | None = None

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        """Track function context for better error messages."""
        old_function = self._in_function
        self._in_function = node.name
        self.generic_visit(node)
        self._in_function = old_function

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        """Track async function context for better error messages."""
        old_function = self._in_function
        self._in_function = node.name
        self.generic_visit(node)
        self._in_function = old_function

    def visit_With(self, node: ast.With) -> None:
        """Check for torch.no_grad() and torch.inference_mode() usage."""
        for item in node.items:
            context_expr = item.context_expr

            # Check for torch.no_grad()
            if self._is_torch_no_grad(context_expr):
                context = (
                    f"in function {self._in_function}" if self._in_function else "at module level"
                )
                self.no_grad_usages.append((node.lineno, context))

            # Check for torch.inference_mode()
            if self._is_torch_inference_mode(context_expr):
                context = (
                    f"in function {self._in_function}" if self._in_function else "at module level"
                )
                self.inference_mode_usages.append((node.lineno, context))

        self.generic_visit(node)

    def _is_torch_no_grad(self, node: ast.expr) -> bool:
        """Check if the expression is torch.no_grad()."""
        if isinstance(node, ast.Call):
            func = node.func
            # torch.no_grad()
            if isinstance(func, ast.Attribute):
                if func.attr == "no_grad":
                    if isinstance(func.value, ast.Name) and func.value.id == "torch":
                        return True
        return False

    def _is_torch_inference_mode(self, node: ast.expr) -> bool:
        """Check if the expression is torch.inference_mode()."""
        if isinstance(node, ast.Call):
            func = node.func
            # torch.inference_mode()
            if isinstance(func, ast.Attribute):
                if func.attr == "inference_mode":
                    if isinstance(func.value, ast.Name) and func.value.id == "torch":
                        return True
        return False


def find_python_files(root: Path, exclude_tests: bool = True) -> Iterator[Path]:
    """Find all Python files in the directory tree.

    Args:
        root: Root directory to search
        exclude_tests: Whether to exclude test files

    Yields:
        Path objects for each Python file
    """
    for path in root.rglob("*.py"):
        # Skip __pycache__ directories
        if "__pycache__" in str(path):
            continue
        # Skip test files if requested
        if exclude_tests and ("test_" in path.name or path.name.startswith("test")):
            continue
        # Skip __init__.py files
        if path.name == "__init__.py":
            continue
        yield path


def analyze_file(filepath: Path) -> tuple[list[tuple[int, str]], list[tuple[int, str]]]:
    """Analyze a Python file for torch.no_grad() and torch.inference_mode() usage.

    Args:
        filepath: Path to the Python file

    Returns:
        Tuple of (no_grad_usages, inference_mode_usages)
    """
    try:
        source = filepath.read_text()
        tree = ast.parse(source)
        visitor = NoGradVisitor(str(filepath))
        visitor.visit(tree)
        return visitor.no_grad_usages, visitor.inference_mode_usages
    except SyntaxError:
        # Skip files with syntax errors
        return [], []


class TestInferenceModeStandardization:
    """Tests to ensure inference_mode is used consistently."""

    def test_warmup_utils_uses_inference_mode(self) -> None:
        """Test that warmup_utils.py uses torch.inference_mode() for inference paths.

        warmup_pipeline() and warmup_model_sync() are inference-only operations
        and should use torch.inference_mode().
        """
        filepath = AI_ROOT / "warmup_utils.py"
        assert filepath.exists(), f"File not found: {filepath}"

        no_grad_usages, inference_mode_usages = analyze_file(filepath)

        # After standardization, there should be no torch.no_grad() usages
        # in inference-only functions
        inference_functions = [
            "warmup_pipeline",
            "warmup_model_sync",
            "_run_hf_inference",
            "_run_direct_inference",
        ]

        no_grad_in_inference = [
            (line, ctx)
            for line, ctx in no_grad_usages
            if any(fn in ctx for fn in inference_functions)
        ]

        assert len(no_grad_in_inference) == 0, (
            f"Found torch.no_grad() in inference-only functions in {filepath}:\n"
            + "\n".join(f"  Line {line}: {ctx}" for line, ctx in no_grad_in_inference)
            + "\n\nThese should use torch.inference_mode() instead."
        )

    def test_batch_utils_uses_inference_mode(self) -> None:
        """Test that batch_utils.py uses torch.inference_mode() for inference paths.

        BatchProcessor.process_with_preprocessing() and create_batch_inference_fn()
        are inference-only operations and should use torch.inference_mode().
        """
        filepath = AI_ROOT / "batch_utils.py"
        assert filepath.exists(), f"File not found: {filepath}"

        no_grad_usages, inference_mode_usages = analyze_file(filepath)

        # After standardization, there should be no torch.no_grad() usages
        inference_functions = ["process_with_preprocessing", "batch_inference"]

        no_grad_in_inference = [
            (line, ctx)
            for line, ctx in no_grad_usages
            if any(fn in ctx for fn in inference_functions)
        ]

        assert len(no_grad_in_inference) == 0, (
            f"Found torch.no_grad() in inference-only functions in {filepath}:\n"
            + "\n".join(f"  Line {line}: {ctx}" for line, ctx in no_grad_in_inference)
            + "\n\nThese should use torch.inference_mode() instead."
        )

    def test_cuda_streams_uses_inference_mode(self) -> None:
        """Test that cuda_streams.py uses torch.inference_mode() for inference paths.

        StreamedInferencePipeline methods are inference-only operations
        and should use torch.inference_mode().
        """
        filepath = AI_ROOT / "cuda_streams.py"
        assert filepath.exists(), f"File not found: {filepath}"

        no_grad_usages, inference_mode_usages = analyze_file(filepath)

        # After standardization, there should be no torch.no_grad() usages
        inference_functions = [
            "_process_with_streams",
            "_process_sequential",
            "create_inference_on_stream",
            "wrapped",
        ]

        no_grad_in_inference = [
            (line, ctx)
            for line, ctx in no_grad_usages
            if any(fn in ctx for fn in inference_functions)
        ]

        assert len(no_grad_in_inference) == 0, (
            f"Found torch.no_grad() in inference-only functions in {filepath}:\n"
            + "\n".join(f"  Line {line}: {ctx}" for line, ctx in no_grad_in_inference)
            + "\n\nThese should use torch.inference_mode() instead."
        )

    def test_compile_utils_uses_inference_mode(self) -> None:
        """Test that compile_utils.py uses torch.inference_mode() for inference paths.

        warmup_compiled_model() and benchmark_compile_modes() are inference-only
        operations and should use torch.inference_mode().
        """
        filepath = AI_ROOT / "compile_utils.py"
        assert filepath.exists(), f"File not found: {filepath}"

        no_grad_usages, inference_mode_usages = analyze_file(filepath)

        # After standardization, there should be no torch.no_grad() usages
        inference_functions = ["warmup_compiled_model", "benchmark_compile_modes"]

        no_grad_in_inference = [
            (line, ctx)
            for line, ctx in no_grad_usages
            if any(fn in ctx for fn in inference_functions)
        ]

        assert len(no_grad_in_inference) == 0, (
            f"Found torch.no_grad() in inference-only functions in {filepath}:\n"
            + "\n".join(f"  Line {line}: {ctx}" for line, ctx in no_grad_in_inference)
            + "\n\nThese should use torch.inference_mode() instead."
        )

    def test_torch_optimizations_uses_inference_mode(self) -> None:
        """Test that torch_optimizations.py uses torch.inference_mode() for inference paths.

        warmup_compiled_model() is an inference-only operation and should use
        torch.inference_mode().
        """
        filepath = AI_ROOT / "torch_optimizations.py"
        assert filepath.exists(), f"File not found: {filepath}"

        no_grad_usages, inference_mode_usages = analyze_file(filepath)

        # After standardization, there should be no torch.no_grad() usages
        inference_functions = ["warmup_compiled_model"]

        no_grad_in_inference = [
            (line, ctx)
            for line, ctx in no_grad_usages
            if any(fn in ctx for fn in inference_functions)
        ]

        assert len(no_grad_in_inference) == 0, (
            f"Found torch.no_grad() in inference-only functions in {filepath}:\n"
            + "\n".join(f"  Line {line}: {ctx}" for line, ctx in no_grad_in_inference)
            + "\n\nThese should use torch.inference_mode() instead."
        )


class TestInferenceModePreservesExisting:
    """Tests that existing torch.inference_mode() usage is preserved."""

    def test_warmup_utils_preserves_inference_mode(self) -> None:
        """Test that warmup_utils.py still has torch.inference_mode() where expected."""
        filepath = AI_ROOT / "warmup_utils.py"
        assert filepath.exists(), f"File not found: {filepath}"

        no_grad_usages, inference_mode_usages = analyze_file(filepath)

        # warmup_vision_model has _run_hf_inference and _run_direct_inference
        # which should use inference_mode
        assert len(inference_mode_usages) >= 2, (
            f"Expected at least 2 torch.inference_mode() usages in {filepath}, "
            f"found {len(inference_mode_usages)}"
        )


class TestNoGradAllowedCases:
    """Tests that document where torch.no_grad() is intentionally kept.

    Some cases may legitimately need torch.no_grad() instead of inference_mode():
    1. When gradients may be needed later in the same function scope
    2. When backward compatibility with older PyTorch is required
    3. In calibration/quantization code where tensors need to be modified
    """

    def test_quantization_can_use_no_grad_for_calibration(self) -> None:
        """Verify quantization calibration can use no_grad() since it modifies tensors.

        Calibration passes data through the model to collect statistics,
        but the model's observers modify internal state. torch.no_grad() is
        appropriate here because inference_mode() creates immutable tensors.
        """
        # This test documents the expected behavior - quantization code
        # may legitimately use no_grad() for calibration
        pass  # No assertion - this is documentation
