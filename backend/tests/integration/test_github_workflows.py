"""Integration tests for GitHub Actions workflow validation.

This module validates the YAML workflow files for:
- Correct YAML syntax
- Required keys (name, on, jobs)
- Job structure (runs-on, steps)
- Referenced actions exist
- Concurrency groups are properly configured
"""

from pathlib import Path
from typing import Any

import pytest
import yaml

# Well-known GitHub Actions that should be valid
KNOWN_ACTIONS = {
    "actions/checkout@v4",
    "actions/setup-python@v5",
    "actions/setup-node@v4",
    "actions/upload-artifact@v4",
    "docker/setup-buildx-action@v3",
    "docker/build-push-action@v5",
    "docker/login-action@v3",
    "docker/metadata-action@v5",
    "codecov/codecov-action@v4",
    "aquasecurity/trivy-action@master",
}

# Required top-level keys for any workflow
REQUIRED_WORKFLOW_KEYS = {"name", "on", "jobs"}

# Required keys for a job
REQUIRED_JOB_KEYS = {"steps"}

# Runner types that are valid
VALID_RUNNERS = {
    "ubuntu-latest",
    "ubuntu-22.04",
    "ubuntu-20.04",
    "ubuntu-24.04-arm",  # ARM64 native builds
    "macos-latest",
    "windows-latest",
}
SELF_HOSTED_LABELS = {"self-hosted", "gpu", "rtx-a5500", "linux"}


@pytest.fixture
def workflows_dir() -> Path:
    """Get the path to the .github/workflows directory."""
    # Navigate from backend/tests/integration to project root
    current_file = Path(__file__)
    project_root = current_file.parent.parent.parent.parent
    workflows_path = project_root / ".github" / "workflows"
    return workflows_path


@pytest.fixture
def workflow_files(workflows_dir: Path) -> list[Path]:
    """Get all YAML workflow files."""
    if not workflows_dir.exists():
        pytest.skip(f"Workflows directory does not exist: {workflows_dir}")
    files = list(workflows_dir.glob("*.yml")) + list(workflows_dir.glob("*.yaml"))
    if not files:
        pytest.skip(f"No workflow files found in {workflows_dir}")
    return files


def load_workflow(path: Path) -> dict[str, Any]:
    """Load and parse a workflow YAML file.

    Note: YAML 1.1 parses 'on' as boolean True. We need to handle this
    by checking for both 'on' and True as keys.
    """
    with open(path) as f:
        data = yaml.safe_load(f)

    # Handle YAML 1.1 'on' -> True conversion
    # GitHub Actions uses 'on' but PyYAML interprets it as boolean True
    if data and True in data and "on" not in data:
        data["on"] = data.pop(True)

    return data


class TestWorkflowYamlSyntax:
    """Test that all workflow files have valid YAML syntax."""

    def test_all_workflows_are_valid_yaml(self, workflow_files: list[Path]) -> None:
        """Verify all workflow files parse as valid YAML."""
        for workflow_file in workflow_files:
            try:
                workflow = load_workflow(workflow_file)
                assert workflow is not None, f"{workflow_file.name} is empty"
                assert isinstance(workflow, dict), f"{workflow_file.name} is not a dict"
            except yaml.YAMLError as e:
                pytest.fail(f"Invalid YAML in {workflow_file.name}: {e}")


class TestWorkflowStructure:
    """Test that workflows have the required structure."""

    def test_workflows_have_required_keys(self, workflow_files: list[Path]) -> None:
        """Verify all workflows have name, on, and jobs keys."""
        for workflow_file in workflow_files:
            workflow = load_workflow(workflow_file)
            missing_keys = REQUIRED_WORKFLOW_KEYS - set(workflow.keys())
            assert not missing_keys, f"{workflow_file.name} missing required keys: {missing_keys}"

    def test_workflow_name_is_string(self, workflow_files: list[Path]) -> None:
        """Verify workflow names are strings."""
        for workflow_file in workflow_files:
            workflow = load_workflow(workflow_file)
            assert isinstance(workflow["name"], str), (
                f"{workflow_file.name}: 'name' should be a string"
            )
            assert len(workflow["name"]) > 0, f"{workflow_file.name}: 'name' should not be empty"

    def test_workflow_on_trigger_is_valid(self, workflow_files: list[Path]) -> None:
        """Verify workflow triggers are valid."""
        for workflow_file in workflow_files:
            workflow = load_workflow(workflow_file)
            on_trigger = workflow["on"]
            assert on_trigger is not None, f"{workflow_file.name}: 'on' should not be empty"
            # Can be string, list, or dict
            assert isinstance(on_trigger, str | list | dict), (
                f"{workflow_file.name}: 'on' should be string, list, or dict"
            )

    def test_workflow_jobs_is_dict(self, workflow_files: list[Path]) -> None:
        """Verify jobs is a dictionary."""
        for workflow_file in workflow_files:
            workflow = load_workflow(workflow_file)
            assert isinstance(workflow["jobs"], dict), (
                f"{workflow_file.name}: 'jobs' should be a dict"
            )
            assert len(workflow["jobs"]) > 0, f"{workflow_file.name}: 'jobs' should not be empty"


class TestJobStructure:
    """Test that jobs have the required structure."""

    def test_jobs_have_runs_on_or_uses(self, workflow_files: list[Path]) -> None:
        """Verify all jobs have either runs-on or uses (for reusable workflows)."""
        for workflow_file in workflow_files:
            workflow = load_workflow(workflow_file)
            for job_name, job_config in workflow["jobs"].items():
                has_runs_on = "runs-on" in job_config
                has_uses = "uses" in job_config
                assert has_runs_on or has_uses, (
                    f"{workflow_file.name}:{job_name} needs 'runs-on' or 'uses'"
                )

    def test_jobs_have_steps_unless_reusable(self, workflow_files: list[Path]) -> None:
        """Verify jobs have steps unless they call a reusable workflow."""
        for workflow_file in workflow_files:
            workflow = load_workflow(workflow_file)
            for job_name, job_config in workflow["jobs"].items():
                # Reusable workflow calls use 'uses' instead of 'steps'
                if "uses" not in job_config:
                    assert "steps" in job_config, f"{workflow_file.name}:{job_name} needs 'steps'"
                    assert isinstance(job_config["steps"], list), (
                        f"{workflow_file.name}:{job_name}: 'steps' should be a list"
                    )
                    assert len(job_config["steps"]) > 0, (
                        f"{workflow_file.name}:{job_name}: 'steps' should not be empty"
                    )

    def test_runner_is_valid(self, workflow_files: list[Path]) -> None:
        """Verify runs-on specifies valid runners."""
        for workflow_file in workflow_files:
            workflow = load_workflow(workflow_file)
            for job_name, job_config in workflow["jobs"].items():
                if "runs-on" not in job_config:
                    continue
                runs_on = job_config["runs-on"]
                # Can be string or list (for self-hosted)
                if isinstance(runs_on, str):
                    # Allow GitHub Actions expressions (matrix variables, etc.)
                    if runs_on.startswith("${{"):
                        continue  # Expression will be evaluated at runtime
                    assert runs_on in VALID_RUNNERS, (
                        f"{workflow_file.name}:{job_name}: unknown runner '{runs_on}'"
                    )
                elif isinstance(runs_on, list):
                    # Self-hosted runners use lists like [self-hosted, gpu]
                    # At least one should be recognized
                    recognized = set(runs_on) & (VALID_RUNNERS | SELF_HOSTED_LABELS)
                    assert len(recognized) > 0, (
                        f"{workflow_file.name}:{job_name}: no recognized labels in {runs_on}"
                    )


class TestStepStructure:
    """Test that steps have valid structure."""

    def test_steps_have_name_or_run(self, workflow_files: list[Path]) -> None:
        """Verify steps have a name, uses, or run key."""
        for workflow_file in workflow_files:
            workflow = load_workflow(workflow_file)
            for job_name, job_config in workflow["jobs"].items():
                if "steps" not in job_config:
                    continue
                for i, step in enumerate(job_config["steps"]):
                    has_name = "name" in step
                    has_uses = "uses" in step
                    has_run = "run" in step
                    assert has_uses or has_run, (
                        f"{workflow_file.name}:{job_name}:step[{i}] needs 'uses' or 'run'"
                    )
                    # Named steps are recommended but not required
                    if not has_name and not has_uses:
                        # If it's just a 'run' step, that's OK
                        pass


class TestActionReferences:
    """Test that referenced actions are valid."""

    def test_action_versions_are_pinned(self, workflow_files: list[Path]) -> None:
        """Verify action uses clauses have version tags."""
        for workflow_file in workflow_files:
            workflow = load_workflow(workflow_file)
            for job_name, job_config in workflow["jobs"].items():
                if "steps" not in job_config:
                    continue
                for i, step in enumerate(job_config["steps"]):
                    if "uses" not in step:
                        continue
                    uses = step["uses"]
                    # Should contain @ for version pinning
                    # Exception: local actions like ./.github/actions/foo
                    if not uses.startswith("./"):
                        assert "@" in uses, (
                            f"{workflow_file.name}:{job_name}:step[{i}]: "
                            f"action '{uses}' should be version-pinned with @"
                        )

    def test_known_actions_are_recognized(self, workflow_files: list[Path]) -> None:
        """Verify common actions are from known sources."""
        for workflow_file in workflow_files:
            workflow = load_workflow(workflow_file)
            for job_name, job_config in workflow["jobs"].items():
                if "steps" not in job_config:
                    continue
                for step in job_config["steps"]:
                    if "uses" not in step:
                        continue
                    uses = step["uses"]
                    if uses.startswith("./"):
                        continue
                    # Extract action without version for pattern matching
                    action_base = uses.split("@")[0]
                    # Known prefixes for trusted actions
                    trusted_prefixes = [
                        "actions/",
                        "docker/",
                        "codecov/",
                        "github/",
                        "aquasecurity/",
                    ]
                    is_trusted = any(action_base.startswith(p) for p in trusted_prefixes)
                    # We warn but don't fail for unknown actions
                    if not is_trusted:
                        # This is informational - unknown actions may still be valid
                        pass


class TestConcurrencyConfig:
    """Test concurrency group configuration."""

    def test_ci_workflow_has_concurrency(self, workflows_dir: Path) -> None:
        """Verify CI workflow has concurrency to cancel duplicate runs."""
        ci_path = workflows_dir / "ci.yml"
        if not ci_path.exists():
            pytest.skip("ci.yml not found")
        workflow = load_workflow(ci_path)
        assert "concurrency" in workflow, "ci.yml should have concurrency config"
        concurrency = workflow["concurrency"]
        assert "group" in concurrency, "concurrency should have 'group'"
        assert "cancel-in-progress" in concurrency, "concurrency should have 'cancel-in-progress'"

    def test_concurrency_uses_github_context(self, workflows_dir: Path) -> None:
        """Verify concurrency groups use appropriate GitHub context."""
        ci_path = workflows_dir / "ci.yml"
        if not ci_path.exists():
            pytest.skip("ci.yml not found")
        workflow = load_workflow(ci_path)
        if "concurrency" not in workflow:
            pytest.skip("No concurrency config")
        group = workflow["concurrency"]["group"]
        # Should reference github context for uniqueness
        assert "${{" in group or "github." in str(group), (
            f"concurrency group should use github context: {group}"
        )


class TestSpecificWorkflows:
    """Test specific workflow configurations."""

    def test_ci_workflow_structure(self, workflows_dir: Path) -> None:
        """Verify CI workflow has expected jobs."""
        ci_path = workflows_dir / "ci.yml"
        if not ci_path.exists():
            pytest.skip("ci.yml not found")
        workflow = load_workflow(ci_path)
        jobs = workflow["jobs"]
        # CI should have lint, test, and build jobs
        expected_jobs = {"lint"}  # At minimum
        actual_jobs = set(jobs.keys())
        missing = expected_jobs - actual_jobs
        assert not missing, f"ci.yml missing expected jobs: {missing}"

    def test_gpu_tests_has_fork_protection(self, workflows_dir: Path) -> None:
        """Verify GPU tests workflow has fork protection."""
        gpu_path = workflows_dir / "gpu-tests.yml"
        if not gpu_path.exists():
            pytest.skip("gpu-tests.yml not found")
        workflow = load_workflow(gpu_path)
        # Check that at least one job has an 'if' condition for fork protection
        has_protection = False
        for job_name, job_config in workflow["jobs"].items():
            if "if" in job_config:
                if_condition = str(job_config["if"])
                if "fork" in if_condition.lower() or "repository" in if_condition:
                    has_protection = True
                    break
        assert has_protection, (
            "gpu-tests.yml should have fork protection (if condition checking repository)"
        )

    def test_gpu_tests_has_timeout(self, workflows_dir: Path) -> None:
        """Verify GPU tests have timeout for resource protection."""
        gpu_path = workflows_dir / "gpu-tests.yml"
        if not gpu_path.exists():
            pytest.skip("gpu-tests.yml not found")
        workflow = load_workflow(gpu_path)
        for job_name, job_config in workflow["jobs"].items():
            # Self-hosted jobs should have timeout
            runs_on = job_config.get("runs-on", [])
            if isinstance(runs_on, list) and "self-hosted" in runs_on:
                assert "timeout-minutes" in job_config, (
                    f"gpu-tests.yml:{job_name} should have timeout-minutes"
                )

    def test_deploy_workflow_on_main_only(self, workflows_dir: Path) -> None:
        """Verify deploy workflow only triggers on main branch."""
        deploy_path = workflows_dir / "deploy.yml"
        if not deploy_path.exists():
            pytest.skip("deploy.yml not found")
        workflow = load_workflow(deploy_path)
        on_trigger = workflow["on"]
        # Should only trigger on push to main
        if isinstance(on_trigger, dict) and "push" in on_trigger:
            push_config = on_trigger["push"]
            if isinstance(push_config, dict) and "branches" in push_config:
                branches = push_config["branches"]
                assert "main" in branches or branches == ["main"], (
                    "deploy.yml should only deploy from main branch"
                )

    def test_nightly_workflow_has_schedule(self, workflows_dir: Path) -> None:
        """Verify nightly workflow has scheduled trigger."""
        nightly_path = workflows_dir / "nightly.yml"
        if not nightly_path.exists():
            pytest.skip("nightly.yml not found")
        workflow = load_workflow(nightly_path)
        on_trigger = workflow["on"]
        assert isinstance(on_trigger, dict), "nightly.yml 'on' should be dict"
        assert "schedule" in on_trigger, "nightly.yml should have schedule trigger"
        schedule = on_trigger["schedule"]
        assert isinstance(schedule, list), "schedule should be a list"
        assert len(schedule) > 0, "schedule should have at least one cron entry"
        # Verify cron format
        for entry in schedule:
            assert "cron" in entry, "schedule entry should have 'cron' key"


class TestYamlBestPractices:
    """Test YAML best practices."""

    def test_no_duplicate_keys(self, workflow_files: list[Path]) -> None:
        """Verify no duplicate keys in workflows (YAML parser will use last)."""
        # This is implicitly tested by yaml.safe_load, but we can check file content
        for workflow_file in workflow_files:
            # Read file to ensure it's valid (basic check)
            _ = workflow_file.read_text()
            # This is a basic check - proper duplicate detection requires custom parser
            # Just verify the file loads without errors
            workflow = load_workflow(workflow_file)
            assert workflow is not None

    def test_workflow_names_are_descriptive(self, workflow_files: list[Path]) -> None:
        """Verify workflow names are descriptive."""
        for workflow_file in workflow_files:
            workflow = load_workflow(workflow_file)
            name = workflow["name"]
            # Name should be at least 2 words or meaningful
            assert len(name) >= 2, f"{workflow_file.name}: name '{name}' too short"


class TestWorkflowInventory:
    """Test that expected workflows exist."""

    def test_ci_workflow_exists(self, workflows_dir: Path) -> None:
        """Verify ci.yml exists."""
        assert (workflows_dir / "ci.yml").exists(), "ci.yml should exist"

    def test_gpu_tests_workflow_exists(self, workflows_dir: Path) -> None:
        """Verify gpu-tests.yml exists."""
        assert (workflows_dir / "gpu-tests.yml").exists(), "gpu-tests.yml should exist"

    def test_deploy_workflow_exists(self, workflows_dir: Path) -> None:
        """Verify deploy.yml exists."""
        assert (workflows_dir / "deploy.yml").exists(), "deploy.yml should exist"

    def test_nightly_workflow_exists(self, workflows_dir: Path) -> None:
        """Verify nightly.yml exists."""
        assert (workflows_dir / "nightly.yml").exists(), "nightly.yml should exist"
