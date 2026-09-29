"""Unit tests for setup_lib.deploy module.

Tests deployment configuration, compose command detection, compose runner,
env file parsing, and deployment orchestration.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest


class TestDeployConfig:
    """Tests for DeployConfig dataclass."""

    def test_default_values(self, tmp_path: Path) -> None:
        """Should have sensible defaults for all optional fields."""
        from setup_lib.deploy import DeployConfig

        config = DeployConfig(project_root=tmp_path)

        assert config.compose_file == "docker-compose.prod.yml"
        assert config.compose_cmd == []
        assert config.destroy_volumes is False
        assert config.skip_build is False
        assert config.skip_export is False
        assert config.force_export is False
        assert config.verbose is True
        assert config.env == {}
        assert config._export_process is None

    def test_env_loading(self, tmp_path: Path) -> None:
        """Should accept env dict and make it accessible."""
        from setup_lib.deploy import DeployConfig

        env = {"API_PORT": "8000", "REDIS_PORT": "6379"}
        config = DeployConfig(project_root=tmp_path, env=env)

        assert config.env == env
        assert config.env["API_PORT"] == "8000"

    def test_custom_compose_file(self, tmp_path: Path) -> None:
        """Should accept a custom compose file name."""
        from setup_lib.deploy import DeployConfig

        config = DeployConfig(project_root=tmp_path, compose_file="docker-compose.test.yml")

        assert config.compose_file == "docker-compose.test.yml"


class TestPipelineMode:
    """DeployConfig.pipeline_mode - the ONE place deploy decides the mode.

    It must resolve exactly as the backend container will: compose interpolates
    backend's PIPELINE_MODE=${PIPELINE_MODE:-vlm} from the env compose_run hands
    it ({**os.environ, **config.env}), and Settings.pipeline_mode lower/strips
    it, defaults to vlm and REJECTS everything else.

    R8 S2b: "vlm vs legacy" is retired -- the deployer's legacy branch is gone
    with the ai-llm compose services it brought up, so the mode is vlm and
    anything else raises. The shape of the resolution is still what is pinned
    (shell-then-env precedence, lower/strip, the empty default), because a
    deploy that decided the mode differently would start a stack the backend
    then refuses to boot.
    """

    def test_defaults_to_vlm_when_unset(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Unset everywhere -> vlm (Settings.pipeline_mode's default)."""
        from setup_lib.deploy import DeployConfig

        monkeypatch.delenv("PIPELINE_MODE", raising=False)
        config = DeployConfig(project_root=tmp_path)

        assert config.pipeline_mode == "vlm"

    def test_empty_value_is_vlm(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """PIPELINE_MODE= (empty) -> vlm, as compose's ${PIPELINE_MODE:-vlm} does."""
        from setup_lib.deploy import DeployConfig

        monkeypatch.delenv("PIPELINE_MODE", raising=False)
        config = DeployConfig(project_root=tmp_path, env={"PIPELINE_MODE": ""})

        assert config.pipeline_mode == "vlm"

    def test_legacy_in_env_file_raises(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """PIPELINE_MODE=legacy left in .env fails the deploy instead of picking a path.

        R8 S2b retired the deployer's legacy branch: it named the ai-llm compose
        services that no longer exist, so a deploy that accepted the value would
        have stopped the stack and then failed to bring the LLM back. The pin is
        the same fact the backend's boot-time validator carries
        (backend/tests/unit/core/test_config_pipeline_mode_hard_raise.py), read
        from the side that has to decide what to start -- and like the backend's,
        it RAISES rather than warn: a warning is not a guard.
        """
        from setup_lib.deploy import DeployConfig

        monkeypatch.delenv("PIPELINE_MODE", raising=False)
        config = DeployConfig(project_root=tmp_path, env={"PIPELINE_MODE": "legacy"})

        with pytest.raises(ValueError, match="legacy"):
            _ = config.pipeline_mode

    def test_the_raise_text_names_the_value_and_offers_no_retired_choice(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The operator sees only the message: it must say what was rejected, name
        vlm as the one accepted mode, and must not still read as if legacy were a
        choice (the wording S1's backend raise retired, kept in the same words here).
        """
        from setup_lib.deploy import DeployConfig

        monkeypatch.delenv("PIPELINE_MODE", raising=False)
        config = DeployConfig(project_root=tmp_path, env={"PIPELINE_MODE": "legacy"})

        with pytest.raises(ValueError) as excinfo:
            _ = config.pipeline_mode
        text = str(excinfo.value)
        assert "legacy" in text.lower()
        assert "vlm" in text.lower()
        assert "'vlm' or 'legacy'" not in text
        assert "retired" in text.lower()

    def test_normalizes_case_and_whitespace(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """' VLM ' is vlm, and ' LEGACY ' is still legacy - lower()/strip() must not
        become a way to smuggle either value past the check.
        """
        from setup_lib.deploy import DeployConfig

        monkeypatch.delenv("PIPELINE_MODE", raising=False)
        normalized = DeployConfig(project_root=tmp_path, env={"PIPELINE_MODE": " VLM "})

        assert normalized.pipeline_mode == "vlm"

        sneaked = DeployConfig(project_root=tmp_path, env={"PIPELINE_MODE": " LEGACY "})

        with pytest.raises(ValueError, match="legacy"):
            _ = sneaked.pipeline_mode

    def test_shell_env_used_when_env_file_is_silent(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """setup.py never writes PIPELINE_MODE, so a shell export reaches compose --
        and a shell `export PIPELINE_MODE=legacy` must raise here, not be read as a
        mode. Precedence is the fact under test: the .env wins over the shell, so
        pin the raise through both sources.
        """
        from setup_lib.deploy import DeployConfig

        monkeypatch.setenv("PIPELINE_MODE", "legacy")
        config = DeployConfig(project_root=tmp_path, env={})

        with pytest.raises(ValueError, match="legacy"):
            _ = config.pipeline_mode

    def test_env_file_wins_over_shell(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """compose_run layers config.env over os.environ; the mode must agree."""
        from setup_lib.deploy import DeployConfig

        monkeypatch.setenv("PIPELINE_MODE", "legacy")
        config = DeployConfig(project_root=tmp_path, env={"PIPELINE_MODE": "vlm"})

        assert config.pipeline_mode == "vlm"

    @pytest.mark.parametrize(
        ("source", "value"),
        [
            pytest.param("env", "vlm", id="env-plain"),
            pytest.param("env", "VLM", id="env-upper"),
            pytest.param("env", " vlm ", id="env-padded"),
            pytest.param("env", "Vlm", id="env-mixed"),
            pytest.param("shell", "vlm", id="shell-plain"),
            pytest.param("shell", "VLM", id="shell-upper"),
            pytest.param("shell", " vlm ", id="shell-padded"),
            pytest.param("shell", "Vlm", id="shell-mixed"),
        ],
    )
    def test_vlm_spellings_are_accepted_from_either_source(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        source: str,
        value: str,
    ) -> None:
        """Every spelling of the one real mode resolves to it from either source.

        S2b left exactly one plan in setup_lib/deploy_phases.py's _MODE_PLANS, so
        this is no longer a two-way check -- it is the positive half of the raise.
        Without it, a normalization bug would look identical to the hard raise
        (both are a ValueError), and a .env written by hand as PIPELINE_MODE=VLM
        would fail a deploy that works.
        """
        from setup_lib.deploy import DeployConfig

        if source == "shell":
            monkeypatch.setenv("PIPELINE_MODE", value)
            config = DeployConfig(project_root=tmp_path)
        else:
            monkeypatch.delenv("PIPELINE_MODE", raising=False)
            config = DeployConfig(project_root=tmp_path, env={"PIPELINE_MODE": value})

        assert config.pipeline_mode == "vlm"

    def test_unknown_value_raises(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """A typo must not silently pick a pipeline (Settings raises on it too)."""
        from setup_lib.deploy import DeployConfig

        monkeypatch.delenv("PIPELINE_MODE", raising=False)
        config = DeployConfig(project_root=tmp_path, env={"PIPELINE_MODE": "legcy"})

        with pytest.raises(ValueError, match="legcy"):
            _ = config.pipeline_mode


class TestDeployResult:
    """Tests for DeployResult dataclass."""

    def test_success_result(self) -> None:
        """Should store success state and message."""
        from setup_lib.deploy import DeployResult

        result = DeployResult(success=True, message="All good")

        assert result.success is True
        assert result.message == "All good"

    def test_failure_result(self) -> None:
        """Should store failure state and message."""
        from setup_lib.deploy import DeployResult

        result = DeployResult(success=False, message="Something broke")

        assert result.success is False
        assert result.message == "Something broke"


class TestDeployPhase:
    """Tests for DeployPhase dataclass."""

    def test_required_default(self) -> None:
        """Should default to required=True."""
        from setup_lib.deploy import DeployPhase, DeployResult

        phase = DeployPhase(
            name="test",
            description="Test phase",
            func=lambda _: DeployResult(True, "ok"),
        )

        assert phase.required is True

    def test_optional_phase(self) -> None:
        """Should accept required=False."""
        from setup_lib.deploy import DeployPhase, DeployResult

        phase = DeployPhase(
            name="test",
            description="Test phase",
            func=lambda _: DeployResult(True, "ok"),
            required=False,
        )

        assert phase.required is False


class TestDetectComposeCommand:
    """Tests for detect_compose_command() function."""

    def test_detects_podman_compose_native(self) -> None:
        """Should return ['podman', 'compose'] when native compose works."""
        from setup_lib.deploy import detect_compose_command

        with (
            patch(
                "shutil.which",
                side_effect=lambda cmd: "/usr/bin/podman" if cmd == "podman" else None,
                autospec=True,
            ),
            patch("subprocess.run", autospec=True) as mock_run,
        ):
            mock_run.return_value = subprocess.CompletedProcess(
                args=[], returncode=0, stdout="podman compose version 1.0", stderr=""
            )

            result = detect_compose_command()

            assert result == ["podman", "compose"]

    def test_detects_podman_compose_external(self) -> None:
        """Should return ['podman-compose'] when native fails but external works."""
        from setup_lib.deploy import detect_compose_command

        def which_side_effect(cmd):
            if cmd == "podman":
                return "/usr/bin/podman"
            if cmd == "podman-compose":
                return "/usr/bin/podman-compose"
            return None

        with (
            patch("shutil.which", side_effect=which_side_effect, autospec=True),
            patch("subprocess.run", autospec=True) as mock_run,
        ):
            # First call (podman compose version) fails, second (podman-compose --version) succeeds
            mock_run.side_effect = [
                subprocess.CompletedProcess(args=[], returncode=1, stdout="", stderr="error"),
                subprocess.CompletedProcess(
                    args=[], returncode=0, stdout="podman-compose 1.0", stderr=""
                ),
            ]

            result = detect_compose_command()

            assert result == ["/usr/bin/podman-compose"]

    def test_raises_when_none_found(self) -> None:
        """Should raise RuntimeError when no compose command is available."""
        from setup_lib.deploy import detect_compose_command

        with patch("shutil.which", return_value=None, autospec=True):
            with pytest.raises(RuntimeError, match="No compose command found"):
                detect_compose_command()


class TestComposeRun:
    """Tests for compose_run() function."""

    def test_capture_mode(self, tmp_path: Path) -> None:
        """Should return CompletedProcess when capture=True."""
        from setup_lib.deploy import DeployConfig, compose_run

        config = DeployConfig(
            project_root=tmp_path,
            compose_cmd=["podman", "compose"],
        )

        with patch("subprocess.run", autospec=True) as mock_run:
            mock_run.return_value = subprocess.CompletedProcess(
                args=[], returncode=0, stdout="output", stderr=""
            )

            result = compose_run(config, "ps", capture=True)

            assert isinstance(result, subprocess.CompletedProcess)
            assert result.returncode == 0
            mock_run.assert_called_once()
            call_kwargs = mock_run.call_args[1]
            assert call_kwargs["capture_output"] is True

    def test_passthrough_mode(self, tmp_path: Path) -> None:
        """Should return bool when capture=False (default)."""
        from setup_lib.deploy import DeployConfig, compose_run

        config = DeployConfig(
            project_root=tmp_path,
            compose_cmd=["podman", "compose"],
        )

        with patch("subprocess.run", autospec=True) as mock_run:
            mock_run.return_value = subprocess.CompletedProcess(
                args=[], returncode=0, stdout="", stderr=""
            )

            result = compose_run(config, "up", "-d")

            assert result is True

    def test_returns_false_on_failure(self, tmp_path: Path) -> None:
        """Should return False when command fails in passthrough mode."""
        from setup_lib.deploy import DeployConfig, compose_run

        config = DeployConfig(
            project_root=tmp_path,
            compose_cmd=["podman", "compose"],
        )

        with patch("subprocess.run", autospec=True) as mock_run:
            mock_run.return_value = subprocess.CompletedProcess(
                args=[], returncode=1, stdout="", stderr="error"
            )

            result = compose_run(config, "up", "-d")

            assert result is False

    def test_verbose_prints_command(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Should print command when verbose=True."""
        from setup_lib.deploy import DeployConfig, compose_run

        config = DeployConfig(
            project_root=tmp_path,
            compose_cmd=["podman", "compose"],
            verbose=True,
        )

        with patch("subprocess.run", autospec=True) as mock_run:
            mock_run.return_value = subprocess.CompletedProcess(
                args=[], returncode=0, stdout="", stderr=""
            )

            compose_run(config, "ps")

            captured = capsys.readouterr()
            assert "podman compose" in captured.out

    def test_returns_false_on_file_not_found(self, tmp_path: Path) -> None:
        """Should return False when command binary not found."""
        from setup_lib.deploy import DeployConfig, compose_run

        config = DeployConfig(
            project_root=tmp_path,
            compose_cmd=["nonexistent"],
        )

        with patch("subprocess.run", side_effect=FileNotFoundError(), autospec=True):
            result = compose_run(config, "ps")

            assert result is False

    def test_capture_returns_error_on_file_not_found(self, tmp_path: Path) -> None:
        """Should return CompletedProcess with returncode=1 on FileNotFoundError in capture mode."""
        from setup_lib.deploy import DeployConfig, compose_run

        config = DeployConfig(
            project_root=tmp_path,
            compose_cmd=["nonexistent"],
        )

        with patch("subprocess.run", side_effect=FileNotFoundError(), autospec=True):
            result = compose_run(config, "ps", capture=True)

            assert isinstance(result, subprocess.CompletedProcess)
            assert result.returncode == 1

    def test_env_merged_into_command(self, tmp_path: Path) -> None:
        """Should merge config.env into subprocess environment."""
        from setup_lib.deploy import DeployConfig, compose_run

        config = DeployConfig(
            project_root=tmp_path,
            compose_cmd=["podman", "compose"],
            env={"CUSTOM_VAR": "value"},
        )

        with patch("subprocess.run", autospec=True) as mock_run:
            mock_run.return_value = subprocess.CompletedProcess(
                args=[], returncode=0, stdout="", stderr=""
            )

            compose_run(config, "ps")

            call_kwargs = mock_run.call_args[1]
            assert call_kwargs["env"]["CUSTOM_VAR"] == "value"


class TestLoadEnv:
    """Tests for load_env() function."""

    def test_parses_key_value(self, tmp_path: Path) -> None:
        """Should parse KEY=VALUE lines from .env file."""
        from setup_lib.deploy import load_env

        env_file = tmp_path / ".env"
        env_file.write_text("API_PORT=8000\nREDIS_PORT=6379\n")

        result = load_env(tmp_path)

        assert result == {"API_PORT": "8000", "REDIS_PORT": "6379"}

    def test_skips_comments_and_blanks(self, tmp_path: Path) -> None:
        """Should skip comment lines and empty lines."""
        from setup_lib.deploy import load_env

        env_file = tmp_path / ".env"
        env_file.write_text("# This is a comment\n\nAPI_PORT=8000\n\n# Another comment\n")

        result = load_env(tmp_path)

        assert result == {"API_PORT": "8000"}

    def test_handles_quoted_values(self, tmp_path: Path) -> None:
        """Should strip surrounding quotes from values."""
        from setup_lib.deploy import load_env

        env_file = tmp_path / ".env"
        env_file.write_text("DB_NAME=\"mydb\"\nDB_USER='admin'\n")

        result = load_env(tmp_path)

        assert result["DB_NAME"] == "mydb"
        assert result["DB_USER"] == "admin"

    def test_returns_empty_on_missing_file(self, tmp_path: Path) -> None:
        """Should return empty dict when .env file doesn't exist."""
        from setup_lib.deploy import load_env

        result = load_env(tmp_path)

        assert result == {}

    def test_skips_lines_without_equals(self, tmp_path: Path) -> None:
        """Should skip lines without = separator."""
        from setup_lib.deploy import load_env

        env_file = tmp_path / ".env"
        env_file.write_text("VALID=yes\nINVALID_LINE\n")

        result = load_env(tmp_path)

        assert result == {"VALID": "yes"}

    def test_handles_value_with_equals(self, tmp_path: Path) -> None:
        """Should handle values that contain = signs."""
        from setup_lib.deploy import load_env

        env_file = tmp_path / ".env"
        env_file.write_text(
            "DATABASE_URL=postgres://user:pass@host/db?opt=val\n"  # pragma: allowlist secret
        )

        result = load_env(tmp_path)

        assert (
            result["DATABASE_URL"]
            == "postgres://user:pass@host/db?opt=val"  # pragma: allowlist secret
        )


class TestRunDeploy:
    """Tests for run_deploy() function."""

    def test_all_phases_pass(self, tmp_path: Path) -> None:
        """Should return True when all phases succeed."""
        from setup_lib.deploy import DeployConfig, DeployPhase, DeployResult, run_deploy

        config = DeployConfig(project_root=tmp_path)

        mock_phases = [
            DeployPhase(name="one", description="Phase 1", func=lambda _: DeployResult(True, "ok")),
            DeployPhase(name="two", description="Phase 2", func=lambda _: DeployResult(True, "ok")),
        ]

        with patch("setup_lib.deploy_phases.DEPLOY_PHASES", mock_phases):
            result = run_deploy(config)

            assert result is True

    def test_required_phase_fails(self, tmp_path: Path) -> None:
        """Should return False and stop when a required phase fails."""
        from setup_lib.deploy import DeployConfig, DeployPhase, DeployResult, run_deploy

        calls = []

        def phase_ok(c):
            calls.append("ok")
            return DeployResult(True, "ok")

        def phase_fail(c):
            calls.append("fail")
            return DeployResult(False, "broken")

        def phase_after(c):
            calls.append("after")
            return DeployResult(True, "ok")

        config = DeployConfig(project_root=tmp_path)

        mock_phases = [
            DeployPhase(name="one", description="Phase 1", func=phase_ok, required=True),
            DeployPhase(name="two", description="Phase 2", func=phase_fail, required=True),
            DeployPhase(name="three", description="Phase 3", func=phase_after, required=True),
        ]

        with patch("setup_lib.deploy_phases.DEPLOY_PHASES", mock_phases):
            result = run_deploy(config)

            assert result is False
            assert calls == ["ok", "fail"]

    def test_optional_phase_fails_continues(self, tmp_path: Path) -> None:
        """Should continue when an optional phase fails."""
        from setup_lib.deploy import DeployConfig, DeployPhase, DeployResult, run_deploy

        calls = []

        def phase_ok(c):
            calls.append("ok")
            return DeployResult(True, "ok")

        def phase_fail_optional(c):
            calls.append("fail_optional")
            return DeployResult(False, "skipped")

        config = DeployConfig(project_root=tmp_path)

        mock_phases = [
            DeployPhase(name="one", description="Phase 1", func=phase_ok, required=True),
            DeployPhase(
                name="two", description="Phase 2", func=phase_fail_optional, required=False
            ),
            DeployPhase(name="three", description="Phase 3", func=phase_ok, required=True),
        ]

        with patch("setup_lib.deploy_phases.DEPLOY_PHASES", mock_phases):
            result = run_deploy(config)

            assert result is True
            assert calls == ["ok", "fail_optional", "ok"]

    def test_unknown_pipeline_mode_aborts_before_any_phase(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A bad PIPELINE_MODE fails the deploy before stop tears anything down."""
        from setup_lib.deploy import DeployConfig, DeployPhase, DeployResult, run_deploy

        monkeypatch.delenv("PIPELINE_MODE", raising=False)
        calls = []

        def phase_stop(c):
            calls.append("stop")
            return DeployResult(True, "ok")

        config = DeployConfig(project_root=tmp_path, env={"PIPELINE_MODE": "legcy"})
        mock_phases = [DeployPhase(name="stop", description="Stop", func=phase_stop)]

        with patch("setup_lib.deploy_phases.DEPLOY_PHASES", mock_phases):
            result = run_deploy(config)

        assert result is False
        assert calls == []

    def test_logs_the_pipeline_mode(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """The deploy log says which pipeline it brought up."""
        from setup_lib.deploy import DeployConfig, DeployPhase, DeployResult, run_deploy

        monkeypatch.delenv("PIPELINE_MODE", raising=False)
        config = DeployConfig(project_root=tmp_path)
        mock_phases = [
            DeployPhase(name="one", description="Phase 1", func=lambda _: DeployResult(True, "ok"))
        ]

        with patch("setup_lib.deploy_phases.DEPLOY_PHASES", mock_phases):
            run_deploy(config)

        assert "Pipeline mode: vlm" in capsys.readouterr().out
