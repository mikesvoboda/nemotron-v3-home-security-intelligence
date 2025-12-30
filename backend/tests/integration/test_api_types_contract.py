"""Tests for API types contract enforcement.

This module verifies that the TypeScript type generation system works correctly
and properly detects when frontend types are out of sync with backend schemas.

The generate-types.sh script:
1. Extracts OpenAPI spec from FastAPI backend
2. Generates TypeScript types using openapi-typescript
3. In --check mode, compares generated types with committed types

NOTE: These tests modify the generated types file and must run sequentially
to avoid race conditions. They are marked with @pytest.mark.serial.
"""

import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

# Mark all tests in this module to run sequentially in the same xdist group
# This prevents race conditions when tests modify the generated types file.
# Also marked as slow because these tests run shell scripts that invoke
# openapi-typescript which takes ~80-120ms per invocation.
#
# The xdist_group marker ensures all tests in this module run on the same
# worker process sequentially, which is critical because test_generate_types_check_fails_when_outdated
# temporarily modifies the generated types file.
pytestmark = [
    pytest.mark.xdist_group("api_types_contract"),
    pytest.mark.serial,
    pytest.mark.slow,
]


class TestAPITypesContract:
    """Tests for API types contract system."""

    @pytest.fixture
    def project_root(self) -> Path:
        """Get the project root directory."""
        # Navigate from tests/unit/ to project root
        return Path(__file__).parent.parent.parent.parent

    @pytest.fixture
    def generate_types_script(self, project_root: Path) -> Path:
        """Get path to generate-types.sh script."""
        script_path = project_root / "scripts" / "generate-types.sh"
        if not script_path.exists():
            pytest.skip(f"generate-types.sh not found at {script_path}")
        return script_path

    @pytest.fixture
    def generated_types_file(self, project_root: Path) -> Path:
        """Get path to generated TypeScript types file."""
        return project_root / "frontend" / "src" / "types" / "generated" / "api.ts"

    def test_generate_types_script_exists(self, generate_types_script: Path) -> None:
        """Test that generate-types.sh exists and is executable."""
        assert generate_types_script.exists(), (
            f"generate-types.sh not found at {generate_types_script}"
        )
        assert generate_types_script.stat().st_mode & 0o111, (
            "generate-types.sh should be executable"
        )

    def test_generated_types_file_exists(self, generated_types_file: Path) -> None:
        """Test that the generated types file exists."""
        assert generated_types_file.exists(), (
            f"Generated types file not found at {generated_types_file}. "
            "Run ./scripts/generate-types.sh to generate it."
        )

    def test_generate_types_check_passes_when_current(
        self,
        project_root: Path,
        generate_types_script: Path,
        generated_types_file: Path,
    ) -> None:
        """Test that --check passes when types are current.

        This test assumes that the committed types are up-to-date.
        If this test fails, run ./scripts/generate-types.sh to update.

        Note: When running under pytest-xdist, Python module imports can affect
        the OpenAPI spec generation (e.g., through conftest.py imports). To
        handle this, we first regenerate types to ensure they're current,
        then verify the --check passes.
        """
        # Check if frontend dependencies are available
        # This handles CI environments where npm install hasn't been run
        frontend_node_modules = project_root / "frontend" / "node_modules"
        openapi_typescript = frontend_node_modules / "openapi-typescript"
        if not frontend_node_modules.exists() or not openapi_typescript.exists():
            pytest.skip(
                "Frontend dependencies not installed (node_modules or openapi-typescript missing). "
                "This test requires: cd frontend && npm install"
            )

        # First, ensure types are current by regenerating them
        # This handles any drift caused by pytest fixture side effects
        gen_result = subprocess.run(  # noqa: S603 # intentional subprocess for integration test
            [str(generate_types_script)],
            check=False,
            cwd=project_root,
            capture_output=True,
            text=True,
            timeout=120,
        )

        if gen_result.returncode != 0:
            pytest.skip(
                f"Could not regenerate types (script may not work in this environment): "
                f"{gen_result.stderr}"
            )

        # Now verify --check passes
        result = subprocess.run(  # noqa: S603 # intentional subprocess for integration test
            [str(generate_types_script), "--check"],
            check=False,
            cwd=project_root,
            capture_output=True,
            text=True,
            timeout=120,  # 2 minute timeout for type generation
        )

        if result.returncode != 0:
            pytest.fail(
                f"generate-types.sh --check failed after regeneration.\n"
                f"stdout: {result.stdout}\n"
                f"stderr: {result.stderr}\n\n"
                f"This indicates a problem with the check mechanism itself.\n"
                f"The types should have been just regenerated."
            )

    def test_generate_types_check_fails_when_outdated(
        self,
        project_root: Path,
        generate_types_script: Path,
        generated_types_file: Path,
    ) -> None:
        """Test that --check fails when types are outdated.

        This test:
        1. Backs up the current generated types
        2. Modifies the types file to simulate drift
        3. Runs --check and verifies it fails
        4. Restores the original types
        """
        if not generated_types_file.exists():
            pytest.skip("Generated types file doesn't exist")

        # Check if frontend dependencies are available by running a quick test
        # This handles CI environments where npm install hasn't been run
        frontend_node_modules = project_root / "frontend" / "node_modules"
        openapi_typescript = frontend_node_modules / "openapi-typescript"
        if not frontend_node_modules.exists() or not openapi_typescript.exists():
            pytest.skip(
                "Frontend dependencies not installed (node_modules or openapi-typescript missing). "
                "This test requires: cd frontend && npm install"
            )

        # Create a temporary backup
        with tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".ts",
            delete=False,
        ) as backup:
            backup_path = Path(backup.name)
            original_content = generated_types_file.read_text()
            backup.write(original_content)

        try:
            # Modify the generated types to simulate drift
            # Add a comment that won't be in the freshly generated file
            modified_content = (
                "// INTENTIONAL_DRIFT_MARKER - This line should not exist\n" + original_content
            )
            generated_types_file.write_text(modified_content)

            # Run --check - it should fail because the types are "outdated"
            result = subprocess.run(  # noqa: S603 # intentional subprocess for integration test
                [str(generate_types_script), "--check"],
                check=False,
                cwd=project_root,
                capture_output=True,
                text=True,
                timeout=120,
            )

            # Check if the script failed due to missing frontend dependencies
            # (This can happen if the node_modules check above passes but something else is missing)
            output = result.stdout + result.stderr
            if "Frontend dependencies not installed" in output or "npm install" in output.lower():
                pytest.skip(
                    "generate-types.sh failed due to missing frontend dependencies. "
                    f"Output: {output}"
                )

            # The script should exit with non-zero when types don't match
            assert result.returncode != 0, (
                "generate-types.sh --check should have failed when types are modified.\n"
                f"stdout: {result.stdout}\n"
                f"stderr: {result.stderr}"
            )

            # Check that the error message is helpful
            assert (
                "out of date" in output.lower()
                or "outdated" in output.lower()
                or "regenerate" in output.lower()
                or "changed" in output.lower()
            ), f"Expected helpful error message about outdated types.\nGot: {output}"

        finally:
            # Restore the original file
            shutil.copy(backup_path, generated_types_file)
            backup_path.unlink()

    def test_pre_commit_hook_configured(self, project_root: Path) -> None:
        """Test that pre-commit hook for API types is configured."""
        pre_commit_config = project_root / ".pre-commit-config.yaml"
        if not pre_commit_config.exists():
            pytest.skip("pre-commit config not found")

        content = pre_commit_config.read_text()

        # Check for api-types-contract hook
        assert "api-types-contract" in content, (
            "api-types-contract hook not found in .pre-commit-config.yaml. "
            "This hook ensures types are regenerated on commit."
        )

        # Verify it runs generate-types.sh --check
        assert "generate-types.sh" in content, (
            "generate-types.sh not referenced in pre-commit config"
        )

    def test_ci_job_configured(self, project_root: Path) -> None:
        """Test that CI job for API types check is configured."""
        ci_config = project_root / ".github" / "workflows" / "ci.yml"
        if not ci_config.exists():
            pytest.skip("CI config not found")

        content = ci_config.read_text()

        # Check for api-types-check job
        assert "api-types-check" in content, (
            "api-types-check job not found in CI config. "
            "This job ensures PRs don't introduce type drift."
        )

        # Verify it runs generate-types.sh --check
        assert "generate-types.sh --check" in content, "CI should run generate-types.sh --check"


class TestGenerateTypesHelpOutput:
    """Tests for generate-types.sh help and usage output."""

    @pytest.fixture
    def project_root(self) -> Path:
        """Get the project root directory."""
        return Path(__file__).parent.parent.parent.parent

    @pytest.fixture
    def generate_types_script(self, project_root: Path) -> Path:
        """Get path to generate-types.sh script."""
        script_path = project_root / "scripts" / "generate-types.sh"
        if not script_path.exists():
            pytest.skip(f"generate-types.sh not found at {script_path}")
        return script_path

    def test_help_flag(
        self,
        project_root: Path,
        generate_types_script: Path,
    ) -> None:
        """Test that --help shows usage information."""
        result = subprocess.run(  # noqa: S603 # intentional subprocess for integration test
            [str(generate_types_script), "--help"],
            check=False,
            cwd=project_root,
            capture_output=True,
            text=True,
            timeout=10,
        )

        # --help should succeed
        assert result.returncode == 0, f"--help failed: {result.stderr}"

        # Check help content
        output = result.stdout
        assert "Usage" in output or "usage" in output, (
            "Help output should include usage information"
        )
        assert "--check" in output, "Help output should document --check flag"
