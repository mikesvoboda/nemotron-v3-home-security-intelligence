"""Integration tests for GitHub Actions workflow validation.

This module validates the YAML workflow files for:
- Correct YAML syntax
- Required keys (name, on, jobs)
- Job structure (runs-on, steps)
- Referenced actions exist
- Concurrency groups are properly configured
"""

import re
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
    # nosemgrep: path-traversal-open -- path from globbing the repo's own .github/workflows dir
    with open(path) as f:
        data = yaml.safe_load(f)

    # Handle YAML 1.1 'on' -> True conversion
    # GitHub Actions uses 'on' but PyYAML interprets it as boolean True
    if data and True in data and "on" not in data:
        data["on"] = data.pop(True)

    return data


def _step(workflow: dict[str, Any], job: str, name: str) -> dict[str, Any]:
    """Find a named step in a job, failing the test if absent."""
    for step in workflow["jobs"][job]["steps"]:
        if step.get("name") == name:
            return step
    pytest.fail(f"job {job!r} has no step named {name!r}")
    raise AssertionError  # unreachable; helps mypy


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


class TestUnitCoverageMergeWiring:
    """WP5.1: the unit-shard coverage DATA files must reach a real combine step.

    Before this WP the shards uploaded only Cobertura XML while the merge job
    globbed for `.coverage.*` data files that were never uploaded — so the
    combine branch never ran, `merged=true` never fired, and
    coverage-baseline.json was never published. The 85% backend floor was
    enforced by zero gates on a PR. These assertions pin the five mechanics
    that make the merge real; each one failing re-opens the silent no-op.
    """

    UNIT_UPLOAD_STEP = "Upload unit test coverage"

    def _steps(self, workflow: dict[str, Any], job: str) -> list[dict[str, Any]]:
        return workflow["jobs"][job]["steps"]

    def _step(self, workflow: dict[str, Any], job: str, name: str) -> dict[str, Any]:
        for step in self._steps(workflow, job):
            if step.get("name") == name:
                return step
        pytest.fail(f"job {job!r} has no step named {name!r}")
        raise AssertionError  # unreachable; helps mypy

    def test_unit_shards_upload_coverage_data_file(self, workflows_dir: Path) -> None:
        """The shard upload ships the pytest-cov DATA file, not just XML."""
        workflow = load_workflow(workflows_dir / "ci.yml")
        step = self._step(workflow, "unit-tests", self.UNIT_UPLOAD_STEP)
        paths = str(step["with"]["path"]).split()
        data_paths = [p for p in paths if p.endswith(".dat")]
        assert data_paths, (
            f"'{self.UNIT_UPLOAD_STEP}' must upload a .coverage data file (renamed "
            f"to a non-hidden *.dat) so the merge job can combine real measured "
            f"data; uploads only: {paths}"
        )

    def test_coverage_upload_survives_hidden_file_default(self, workflows_dir: Path) -> None:
        """Hidden data files need include-hidden-files OR a non-hidden name.

        upload-artifact v6 excludes dotfiles by default; uploading
        `.coverage.*` without the opt-in ships an EMPTY artifact and the run
        looks identical to the broken one (P WP5.1 trap 1).
        """
        workflow = load_workflow(workflows_dir / "ci.yml")
        step = self._step(workflow, "unit-tests", self.UNIT_UPLOAD_STEP)
        paths = str(step["with"]["path"]).split()
        hidden = [p for p in paths if Path(p).name.startswith(".")]
        if hidden:
            assert step["with"].get("include-hidden-files") is True, (
                f"uploads hidden files {hidden} without include-hidden-files: true"
            )
        else:
            assert any(p.endswith(".dat") for p in paths), (
                f"no hidden upload names, so the data file must be a non-hidden "
                f"*.dat rename; paths: {paths}"
            )

    def test_unit_coverage_artifact_name_glob_coupling(self, workflows_dir: Path) -> None:
        """Artifact name still matches the merge job's download pattern.

        scripts/test_shard_retry_wiring.py:178-179 pins the same coupling for
        the integration tier; renaming the unit artifact to describe its new
        contents breaks the download with NO error — it finds nothing.
        """
        workflow = load_workflow(workflows_dir / "ci.yml")
        upload = self._step(workflow, "unit-tests", self.UNIT_UPLOAD_STEP)
        name = str(upload["with"]["name"])
        download = self._step(
            workflow, "unit-tests-coverage-merge", "Download all coverage artifacts"
        )
        pattern = str(download["with"]["pattern"])
        assert pattern.startswith("coverage-unit-shard-"), pattern
        stem = pattern.rstrip("*")
        concrete = name.replace("${{ matrix.shard }}", "1").replace(
            "${{ matrix.python-version }}", "3.14"
        )
        assert concrete.startswith(stem), (
            f"upload artifact name {name!r} would no longer match the merge "
            f"download pattern {pattern!r}"
        )

    def test_merge_job_combines_from_download_directory(self, workflows_dir: Path) -> None:
        """The combine step must operate on the download path, not job CWD.

        download-artifact extracts under coverage-reports/ (P WP5.1 trap 2);
        a `.coverage.*` glob in the job CWD matches nothing and the vacuous
        `touch .coverage` branch keeps the whole gate silent.
        """
        workflow = load_workflow(workflows_dir / "ci.yml")
        combine = self._step(
            workflow, "unit-tests-coverage-merge", "Combine and check coverage threshold"
        )
        script = combine["run"]
        assert "coverage combine" in script, "combine step lost `coverage combine`"
        assert "coverage-reports/" in script, (
            "the combine invocation must name coverage-reports/ explicitly — "
            "that is where download-artifact extracts the shard data files"
        )

    def test_baseline_publish_stays_gated_on_real_combine(self, workflows_dir: Path) -> None:
        """WP0.9 invariant: merged=true (and thus the baseline) only fires on
        the combine-success path — never from the vacuous touch branch."""
        workflow = load_workflow(workflows_dir / "ci.yml")
        combine = self._step(
            workflow, "unit-tests-coverage-merge", "Combine and check coverage threshold"
        )
        script = combine["run"]
        merged_line = [ln for ln in script.splitlines() if "merged=true" in ln]
        assert merged_line, "combine step must still emit merged=true on success"
        # shell keyword only (line-initial `else`), not the word inside comments
        else_ln = [i for i, ln in enumerate(script.splitlines()) if ln.strip() == "else"]
        assert else_ln, "combine step lost its no-data branch guard entirely"
        first_else = else_ln[0]
        merged_ln = [i for i, ln in enumerate(script.splitlines()) if "merged=true" in ln]
        assert all(i < first_else for i in merged_ln), (
            "merged=true appears at/after the no-data branch — WP0.9 forbids "
            "the vacuous `touch .coverage` fill from ever minting a baseline"
        )


class TestIntegrationCoverageMergeWiring:
    """WP5.1/A2: integration-coverage-merge had NO combine step at all.

    The addendum's A2 verified it is download -> find -> Codecov. If the
    floor ruling (R-COVDENOM) lands on "combined", the integration tier
    needs the same COVERAGE_FILE + combine treatment as the unit tier;
    "make it compute, don't make it gate" says give it the machinery now
    and let the ruling decide what it gates. Same five mechanics as the
    unit tier, applied to the integration shape (per-job named files,
    one shared reusable workflow for the API shards).
    """

    def test_integration_jobs_upload_coverage_data_files(self, workflows_dir: Path) -> None:
        """Every integration tier upload carries a non-hidden .dat data file."""
        ci = load_workflow(workflows_dir / "ci.yml")
        shard = load_workflow(workflows_dir / "integration-shard.yml")
        # websocket/services/models jobs live in ci.yml; API shards in the
        # reusable integration-shard.yml (called by integration-tests-api
        # + the WP0.5 slow-runner retry).
        for job, step_name in (
            ("integration-tests-websocket", "Upload coverage artifact"),
            ("integration-tests-services", "Upload coverage artifact"),
            ("integration-tests-models", "Upload coverage artifact"),
        ):
            paths = str(_step(ci, job, step_name)["with"]["path"]).split()
            assert any(p.endswith(".dat") for p in paths), (
                f"ci.yml:{job}/{step_name} must upload a non-hidden .coverage "
                f"data file (*.dat) for the merge combine; paths: {paths}"
            )
        paths = str(
            _step(shard, "integration-shard", "Upload coverage artifact")["with"]["path"]
        ).split()
        assert any(p.endswith(".dat") for p in paths), (
            f"integration-shard.yml upload must carry a .dat data file for the "
            f"api shards; paths: {paths}"
        )

    def test_integration_merge_combines_from_download_directory(self, workflows_dir: Path) -> None:
        """The integration merge must actually combine, over coverage-reports/."""
        ci = load_workflow(workflows_dir / "ci.yml")
        combine = _step(ci, "integration-coverage-merge", "Combine integration coverage")
        script = combine["run"]
        assert "coverage combine" in script, "integration merge lost its combine call"
        assert "coverage-reports/" in script, (
            "combine must read the coverage-reports/ download dir — the "
            "artifacts are extracted there, not into the job CWD"
        )

    def test_integration_merge_emits_a_number(self, workflows_dir: Path) -> None:
        """Compute the number (not gate it): the merge must print a percent.

        R-COVDENOM is parked, so this job computes and REPORTS — a step
        summary line is the machine-checkable contract for "computed".
        """
        ci = load_workflow(workflows_dir / "ci.yml")
        combine = _step(ci, "integration-coverage-merge", "Combine integration coverage")
        assert "GITHUB_STEP_SUMMARY" in combine["run"], (
            "integration merge must write its computed percentage to the "
            "step summary (compute, don't gate)"
        )


class TestFrontendCoverageMergeWiring:
    """WP5.2: frontend shards must COMPUTE coverage and one job must really merge.

    Before this fix the shards ran `npx vitest run` with no --coverage (the
    comment at the run step said per-shard thresholds fail at ~6% each —
    right about per-shard thresholds, wrong as a conclusion), and
    frontend-coverage-merge was download -> find -> Codecov with no istanbul
    merge and no threshold step. Worse, all 8 shards wrote the same
    frontend/coverage/coverage-final.json and merge-multiple: true flattened
    them, so even had --coverage existed, one shard would have survived.

    R-FEFLOOR (ADDENDUM A3, parked): measured actuals 80.00/74.61/78.44/80.93
    vs thresholds 83/77/81/84. This job REPORTS the four numbers; it must not
    enforce — lowering thresholds and widening coverage.exclude are both
    prohibited, and enforcement stays the owner's call.
    """

    SHARD_RUN_STEP = "Run tests (shard ${{ matrix.shard }}/8)"
    MERGE_STEP = "Merge frontend coverage"
    REPORT_STEP = "Report frontend coverage (R-FEFLOOR: not enforced)"

    def _shard_run_steps(self, workflow: dict[str, Any]) -> list[dict[str, Any]]:
        return [
            s
            for s in workflow["jobs"]["frontend-tests"]["steps"]
            if str(s.get("name", "")).startswith("Run tests (shard")
        ]

    def test_every_shard_runs_with_coverage_thresholds_zeroed(self, workflows_dir: Path) -> None:
        ci = load_workflow(workflows_dir / "ci.yml")
        runs = self._shard_run_steps(ci)
        assert len(runs) == 1, f"expected one shard run step, found {len(runs)}"
        script = runs[0]["run"]
        assert "--coverage" in script, "frontend shard must collect coverage (WP5.2)"
        # Vitest has no "disable thresholds" switch; per-shard runs must zero
        # every metric or each shard fails its own 83/77/81/84 gate at ~12%.
        for metric in ("statements", "branches", "functions", "lines"):
            assert f"--coverage.thresholds.{metric}=0" in script, (
                f"shard run must zero the {metric} threshold (per-shard ~1/8 of "
                "total coverage cannot pass a whole-suite threshold)"
            )

    def test_shard_coverage_output_is_shard_unique(self, workflows_dir: Path) -> None:
        """8 shards x identical filenames + merge-multiple == silent collision.

        coverage-final.json from all 8 shards lands on one path; exactly one
        survives. The per-shard reportsDirectory is the only lever that keeps
        the artifacts distinguishable through download-artifact flattening.
        """
        ci = load_workflow(workflows_dir / "ci.yml")
        script = self._shard_run_steps(ci)[0]["run"]
        assert "--coverage.reportsDirectory" in script, (
            "shards must write coverage to distinct directories or 8 identical "
            "coverage-final.json files collide under merge-multiple: true"
        )
        assert "shard-${{ matrix.shard }}" in script or "shard-$SHARD" in script, (
            "the coverage output path must be parameterized by matrix.shard"
        )

    def test_upload_covers_the_shard_coverage_dir(self, workflows_dir: Path) -> None:
        ci = load_workflow(workflows_dir / "ci.yml")
        upload = _step(ci, "frontend-tests", "Upload coverage artifact")
        path = str(upload["with"]["path"])
        assert "coverage" in path, path
        # Load-bearing coupling, same class as the backend .dat glob pins: the
        # uploaded path must be the (parent of the) directory the run writes.
        assert "shard" in str(upload["with"]["name"]), "artifact name must stay shard-unique"

    def test_merge_job_merges_and_reports(self, workflows_dir: Path) -> None:
        ci = load_workflow(workflows_dir / "ci.yml")
        merge = _step(ci, "frontend-coverage-merge", self.MERGE_STEP)
        assert "merge-shard-coverage" in merge["run"], (
            "frontend-coverage-merge must run the istanbul merge script over the "
            "downloaded coverage-final.json files — today it only find|head's them"
        )
        report = _step(ci, "frontend-coverage-merge", self.REPORT_STEP)
        assert "GITHUB_STEP_SUMMARY" in report["run"], (
            "the merged four metrics must be written to the step summary"
        )
        assert "process.exit" not in report["run"], (
            "the reporting step must not enforce (R-FEFLOOR parked) — no gate "
            "flips without the owner"
        )

    def test_merge_script_unit_test_runs_before_merge(self, workflows_dir: Path) -> None:
        """The merger itself is tested (node --test) on CI, before it is trusted."""
        ci = load_workflow(workflows_dir / "ci.yml")
        merge = _step(ci, "frontend-coverage-merge", self.MERGE_STEP)
        assert "node --test" in merge["run"], (
            "merge script must run its unit check in-job before producing numbers"
        )

    def test_merger_unit_test_is_outside_the_vitest_sweep(self, workflows_dir: Path) -> None:
        """The node --test unit file must NOT match Vitest's default include.

        WP5.2 regression: the unit checks shipped as merge-shard-coverage.
        TEST.mjs — and Vitest's default include (**/*.{test,spec}.?(c|m)
        [jt]s?(x)) sweeps the whole frontend tree, scripts/ included. Shard
        1/8 (files sort first) collected it and died on
        `Cannot bundle built-in module "node:test"` — a node --test file is
        structurally unrunnable in the jsdom vitest environment. The fix is
        a name that node --test still runs (explicit path, and node's own
        *-test/_test globs) but vitest's sweep cannot match.
        """
        ci = load_workflow(workflows_dir / "ci.yml")
        merge = _step(ci, "frontend-coverage-merge", self.MERGE_STEP)
        m = re.search(r"node --test (\S+)", merge["run"])
        assert m, "merge step must name its unit-test file explicitly"
        unit = Path(m.group(1))
        assert not re.search(r"\.(test|spec)\.(c|m)?js$", unit.name), (
            f"{unit.name} matches Vitest's default *.test.{unit.suffix} glob — "
            "the node --test file would be collected (and fail) in every shard"
        )
        scripts_dir = workflows_dir.parent.parent / "frontend" / "scripts"
        swept = [
            p.name
            for p in scripts_dir.glob("*.mjs")
            if re.search(r"\.(test|spec)\.(c|m)?js$", p.name)
        ]
        assert swept == [], f"vitest-sweep-matching files under frontend/scripts: {swept}"


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

    # gpu-tests.yml existence test removed 2026-09-15 alongside the workflow
    # itself (GPU runner costs money; see d21fb418). The gpu-tests property
    # tests above already skip when the file is absent, so they stay valid if
    # an owner ever reintroduces a GPU workflow.

    def test_deploy_workflow_exists(self, workflows_dir: Path) -> None:
        """Verify deploy.yml exists."""
        assert (workflows_dir / "deploy.yml").exists(), "deploy.yml should exist"

    def test_nightly_workflow_exists(self, workflows_dir: Path) -> None:
        """Verify nightly.yml exists."""
        assert (workflows_dir / "nightly.yml").exists(), "nightly.yml should exist"


class TestAiTierWiring:
    """WP6.5: the un-darkened ai/ tier (WP6.1-6.4: 1764 collected / 0 errors) is
    wired into CI in a STAGED shape: the import-error-visible collect-only gate
    over the whole tier plus test RUNS for subtrees that are green today
    (ai/gateway - the deployed provider). Subtrees with ledger-recorded parked
    reds (WP6.4 classifications) join as each drains; a gate on a red subtree
    would make the branch red for a RECORDED reason, which the doctrine
    forbids as wiring noise. Structural assertions on ci.yml; the
    deliberately-broken-ai-test end-to-end proof is the plan's alternative
    Done-when and needs a live CI run (PR #6560 carries this commit)."""

    def _ci_text(self, workflows_dir: Path) -> str:
        ci = workflows_dir / "ci.yml"
        assert ci.exists(), "ci.yml should exist"
        return ci.read_text()

    def _ci_jobs(self, workflows_dir: Path) -> dict[str, Any]:
        # nosemgrep: path-traversal-open -- path from the workflows_dir fixture, repo's own ci.yml
        return load_workflow(workflows_dir / "ci.yml")["jobs"]

    def test_collection_gate_receives_ai(self, workflows_dir: Path) -> None:
        """The AST collection-sanity gate must scan ai/ too. Cheap (rc=0
        verified locally) and explicitly NOT sufficient — it never imports, so
        it passed clean (0.159s) on a tree with 19 collection errors; the
        collect-only step below is the one that can see them."""
        text = self._ci_text(workflows_dir)
        assert "check-test-collection.py backend frontend ai" in text, (
            "ci.yml collection-sanity step must pass `ai` to check-test-collection.py"
        )

    def test_ai_collect_only_gate_exists(self, workflows_dir: Path) -> None:
        """A step runs `pytest ai/ --collect-only` over the WHOLE tier and
        fails on any collection error (rc=2) — the gate that CAN see the
        WP6.2-class import errors (triton shadow, flat-slot collisions) the
        AST gate cannot."""
        jobs = self._ci_jobs(workflows_dir)
        ai_job = jobs.get("ai-tests")
        assert ai_job is not None, "ci.yml needs an ai-tests job"
        collect_steps = [
            s
            for s in ai_job["steps"]
            if "pytest" in s.get("run", "") and "--collect-only" in s.get("run", "")
        ]
        assert collect_steps, "ai-tests job must contain a `pytest ai/ --collect-only` step"

    def test_ai_gateway_suite_runs(self, workflows_dir: Path) -> None:
        """WP6.5 DECIDE applied per-subtree: ai/gateway (the deployed provider,
        green at 226/0 after WP6.4) has its own RUN step. Full-tree `pytest ai/`
        joins per-subtree as parked reds drain (WP6.4 ledger), so a parked-red
        subtree never holds the branch red for a recorded reason."""
        jobs = self._ci_jobs(workflows_dir)
        ai_job = jobs.get("ai-tests")
        assert ai_job is not None, "ci.yml needs an ai-tests job"
        runs = " ".join(s.get("run", "") for s in ai_job["steps"])
        assert "pytest ai/gateway" in runs, (
            "ai/gateway must have its own pytest RUN step (green today per "
            "WP6.4 ledger: 226 passed / 0 failed)"
        )

    def test_ai_job_converges_on_ci_gate(self, workflows_dir: Path) -> None:
        """WP0.6 invariant for the new job: direct ci-gate need AND a
        check_job line reading its result. A needs entry nobody inspects is
        ordering, not gating — scripts/test_ci_job_graph.py enforces the
        pairing tree-wide; this pins it for ai-tests specifically."""
        jobs = self._ci_jobs(workflows_dir)
        gate = jobs["ci-gate"]
        needs = gate["needs"]
        needs = needs if isinstance(needs, list) else list(needs)
        assert "ai-tests" in needs, "ci-gate must need ai-tests"
        gate_script = " ".join(s.get("run", "") for s in gate["steps"])
        assert "needs.ai-tests.result" in gate_script, (
            "ci-gate must check_job ai-tests's result — the WP0.6 "
            "invisibility class is exactly 'needs but never inspects'"
        )

    def test_ai_job_follows_backend_job_conventions(self, workflows_dir: Path) -> None:
        """Change-detection hygiene: the `if` mirrors the backend jobs (ai/**
        is ALREADY inside the detect-changes `backend` path filter - verified,
        ci.yml:42-46 - so no new output key is invented), and the job reuses
        the shared build-backend-deps like every other backend job."""
        jobs = self._ci_jobs(workflows_dir)
        ai_job = jobs["ai-tests"]
        condition = str(ai_job.get("if", ""))
        assert "detect-changes" in condition, (
            "ai-tests must honor detect-changes like every other backend job"
        )
        needs = ai_job.get("needs", [])
        needs = needs if isinstance(needs, list) else list(needs)
        assert "build-backend-deps" in needs, "ai-tests must reuse the shared deps job"
