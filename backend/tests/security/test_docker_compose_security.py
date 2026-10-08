"""Tests to validate Docker Compose security hardening for AI container services.

NEM-4976: Apply security hardening to AI container services

This module verifies that all AI services in docker-compose.prod.yml have
proper security hardening applied, including:
- no-new-privileges:true (prevents privilege escalation)
- cap_drop: ALL (drops all Linux capabilities by default)

These security controls follow the principle of least privilege and prevent
container escape attacks.
"""

import re
import shutil
import subprocess
from pathlib import Path
from typing import ClassVar

import pytest
import yaml

REPO_ROOT = Path(__file__).parent.parent.parent.parent


class TestDockerComposeSecurityHardening:
    """Tests for Docker Compose production security configuration."""

    # AI services that require security hardening
    # Note: individual per-model services (ai-yolo26, ai-florence, ai-clip,
    # ai-enrichment, ai-enrichment-light) were consolidated into ai-gateway
    # (Triton Inference Server + FastAPI gateway)
    #
    # R8 slice S2b (2026-09-29) removed `ai-llm` from this list because the
    # SERVICE is gone from docker-compose.prod.yml — the legacy LLM tier it ran
    # was deleted, not renamed. Leaving it here would have kept four green pins
    # asserting the existence of a container that no longer ships (this class
    # went red in CI precisely because the delete was real and the list was not).
    #
    # `ai-llm-vllm` is deliberately NOT added to this list; see
    # TestRetiredLlmServiceIsGone.test_the_surviving_vllm_engine_diverges_on_purpose
    # for what it actually carries and who owns closing that.
    AI_SERVICES: ClassVar[list[str]] = [
        "ai-gateway",
        # Phase 1.2: both survivors carry an identical posture (same
        # security_opt/cap_drop — the consistency test below pins that they
        # STAY identical).
        "ai-vlm",
    ]

    @pytest.fixture
    def docker_compose_path(self) -> Path:
        """Get the path to docker-compose.prod.yml."""
        # Navigate from tests/security/ to project root
        return Path(__file__).parent.parent.parent.parent / "docker-compose.prod.yml"

    @pytest.fixture
    def compose_config(self, docker_compose_path: Path) -> dict:
        """Load and parse docker-compose.prod.yml."""
        if not docker_compose_path.exists():
            pytest.skip(f"docker-compose.prod.yml not found at {docker_compose_path}")
        return yaml.safe_load(docker_compose_path.read_text())

    def test_docker_compose_prod_exists(self, docker_compose_path: Path) -> None:
        """Test that docker-compose.prod.yml exists."""
        assert docker_compose_path.exists(), (
            f"docker-compose.prod.yml not found at {docker_compose_path}"
        )

    def test_all_ai_services_defined(self, compose_config: dict) -> None:
        """Test that all expected AI services are defined in the compose file."""
        services = compose_config.get("services", {})
        for service_name in self.AI_SERVICES:
            assert service_name in services, (
                f"AI service '{service_name}' not found in docker-compose.prod.yml"
            )

    @pytest.mark.parametrize("service_name", AI_SERVICES)
    def test_ai_service_has_no_new_privileges(
        self, compose_config: dict, service_name: str
    ) -> None:
        """Test that AI service has no-new-privileges:true security option.

        no-new-privileges prevents processes inside the container from gaining
        additional privileges via setuid/setgid executables. This is a critical
        security control that prevents privilege escalation attacks.
        """
        services = compose_config.get("services", {})
        service = services.get(service_name, {})

        security_opts = service.get("security_opt", [])
        assert "no-new-privileges:true" in security_opts, (
            f"AI service '{service_name}' missing 'no-new-privileges:true' in security_opt. "
            "Add security_opt: ['no-new-privileges:true'] to prevent privilege escalation."
        )

    @pytest.mark.parametrize("service_name", AI_SERVICES)
    def test_ai_service_drops_all_capabilities(
        self, compose_config: dict, service_name: str
    ) -> None:
        """Test that AI service drops all Linux capabilities.

        Dropping all capabilities follows the principle of least privilege.
        Containers should only have the minimum capabilities required to function.
        If specific capabilities are needed, they should be explicitly added back.
        """
        services = compose_config.get("services", {})
        service = services.get(service_name, {})

        cap_drop = service.get("cap_drop", [])
        assert "ALL" in cap_drop, (
            f"AI service '{service_name}' missing 'ALL' in cap_drop. "
            "Add cap_drop: ['ALL'] to drop all Linux capabilities by default."
        )

    @pytest.mark.parametrize("service_name", AI_SERVICES)
    def test_ai_service_no_privileged_mode(self, compose_config: dict, service_name: str) -> None:
        """Test that AI service does not run in privileged mode.

        Privileged mode gives the container full access to host devices and
        kernel capabilities. AI services should never run privileged.
        """
        services = compose_config.get("services", {})
        service = services.get(service_name, {})

        privileged = service.get("privileged", False)
        assert not privileged, (
            f"AI service '{service_name}' has privileged: true. "
            "AI services must not run in privileged mode for security."
        )

    @pytest.mark.parametrize("service_name", AI_SERVICES)
    def test_ai_service_no_sys_admin_capability(
        self, compose_config: dict, service_name: str
    ) -> None:
        """Test that AI service does not add SYS_ADMIN capability.

        SYS_ADMIN is a dangerous capability that effectively grants root-like
        privileges. AI services should never require this capability.
        """
        services = compose_config.get("services", {})
        service = services.get(service_name, {})

        cap_add = service.get("cap_add", [])
        assert "SYS_ADMIN" not in cap_add, (
            f"AI service '{service_name}' has SYS_ADMIN in cap_add. "
            "AI services should not require SYS_ADMIN capability."
        )

    def test_security_hardening_consistency(self, compose_config: dict) -> None:
        """Test that security hardening is consistent across all AI services.

        All AI services should have identical security configurations to ensure
        a consistent security posture.
        """
        services = compose_config.get("services", {})

        security_configs = []
        for service_name in self.AI_SERVICES:
            service = services.get(service_name, {})
            config = {
                "security_opt": set(service.get("security_opt", [])),
                "cap_drop": set(service.get("cap_drop", [])),
                "privileged": service.get("privileged", False),
            }
            security_configs.append((service_name, config))

        # Compare all configs to the first one
        first_name, first_config = security_configs[0]
        for service_name, config in security_configs[1:]:
            assert config == first_config, (
                f"Security configuration mismatch between '{first_name}' and '{service_name}'. "
                "All AI services should have consistent security hardening."
            )


class TestExistingSecurityHardening:
    """Tests to verify existing infrastructure services maintain their security hardening."""

    # Infrastructure services that should already have security hardening
    INFRASTRUCTURE_SERVICES: ClassVar[list[str]] = [
        "postgres",
        "redis",
        "go2rtc",
        "prometheus",
        "grafana",
        "alertmanager",
        "blackbox-exporter",
        "redis-exporter",
        "json-exporter",
        "loki",
        "pyroscope",
        "tempo",
        "node-exporter",
        "cadvisor",
    ]

    @pytest.fixture
    def docker_compose_path(self) -> Path:
        """Get the path to docker-compose.prod.yml."""
        return Path(__file__).parent.parent.parent.parent / "docker-compose.prod.yml"

    @pytest.fixture
    def compose_config(self, docker_compose_path: Path) -> dict:
        """Load and parse docker-compose.prod.yml."""
        if not docker_compose_path.exists():
            pytest.skip(f"docker-compose.prod.yml not found at {docker_compose_path}")
        return yaml.safe_load(docker_compose_path.read_text())

    @pytest.mark.parametrize("service_name", INFRASTRUCTURE_SERVICES)
    def test_infrastructure_service_has_security_opt(
        self, compose_config: dict, service_name: str
    ) -> None:
        """Test that infrastructure services have security_opt defined.

        This ensures existing security hardening is not accidentally removed.
        """
        services = compose_config.get("services", {})
        if service_name not in services:
            pytest.skip(f"Service '{service_name}' not in compose file")

        service = services.get(service_name, {})

        # Services with security_opt should have no-new-privileges
        security_opts = service.get("security_opt", [])
        if security_opts:
            assert "no-new-privileges:true" in security_opts, (
                f"Infrastructure service '{service_name}' has security_opt but missing "
                "'no-new-privileges:true'. This may indicate accidental security regression."
            )


class TestComposeConfigValidation:
    """Tests to validate docker-compose.prod.yml can be parsed and validated."""

    @pytest.fixture
    def docker_compose_path(self) -> Path:
        """Get the path to docker-compose.prod.yml."""
        return Path(__file__).parent.parent.parent.parent / "docker-compose.prod.yml"

    def test_compose_file_is_valid_yaml(self, docker_compose_path: Path) -> None:
        """Test that docker-compose.prod.yml is valid YAML."""
        if not docker_compose_path.exists():
            pytest.skip(f"docker-compose.prod.yml not found at {docker_compose_path}")

        try:
            content = docker_compose_path.read_text()
            yaml.safe_load(content)
        except yaml.YAMLError as e:
            pytest.fail(f"docker-compose.prod.yml contains invalid YAML: {e}")

    def test_compose_file_has_services_section(self, docker_compose_path: Path) -> None:
        """Test that docker-compose.prod.yml has a services section."""
        if not docker_compose_path.exists():
            pytest.skip(f"docker-compose.prod.yml not found at {docker_compose_path}")

        content = yaml.safe_load(docker_compose_path.read_text())
        assert "services" in content, "docker-compose.prod.yml missing 'services' section"
        assert isinstance(content["services"], dict), "'services' section should be a dictionary"


# Every TRACKED compose file (`git ls-files '*docker-compose*.yml'`, pinned by
# test_the_tracked_compose_list_is_what_git_tracks).
TRACKED_COMPOSE_FILES: tuple[str, ...] = (
    "config/docker-compose.gb300.yml",
    "docker-compose.ci.yml",
    "docker-compose.prod.yml",
    "docker-compose.test.yml",
)

# Short syntax ``<source>:<target>[:<opts>]``. The shortest source wins, so the
# ``:-`` inside a ``${FOSCAM_BASE_PATH:-/export/foscam}`` default does not split
# the mount at the wrong colon.
_SHORT_MOUNT_RE = re.compile(r"^(?P<source>.*?):(?P<target>/[^:]*)(?::(?P<opts>[^:]*))?$")


class _ComposeLoader(yaml.SafeLoader):
    """safe_load that also reads compose's merge tags (!override, !reset)."""


def _construct_compose_tag(loader: yaml.SafeLoader, _suffix: str, node: yaml.Node) -> object:
    if isinstance(node, yaml.MappingNode):
        return loader.construct_mapping(node, deep=True)
    if isinstance(node, yaml.SequenceNode):
        return loader.construct_sequence(node, deep=True)
    return loader.construct_scalar(node)  # type: ignore[arg-type]


_ComposeLoader.add_multi_constructor("!", _construct_compose_tag)


def _camera_mounts(compose_text: str) -> list[tuple[str, str, set[str]]]:
    """(service, mount as written, options) for every camera-root mount.

    A camera-root mount targets ``/cameras`` or sources FOSCAM_BASE_PATH. For
    long syntax the relabel lives in ``bind.selinux``.
    """
    # _ComposeLoader IS a SafeLoader: it only adds plain-node reads of compose's
    # own tags, no Python object construction.
    config = yaml.load(compose_text, Loader=_ComposeLoader) or {}  # noqa: S506  # nosemgrep: unsafe-yaml-load
    out: list[tuple[str, str, set[str]]] = []
    for name, service in (config.get("services") or {}).items():
        for volume in (service or {}).get("volumes") or []:
            if isinstance(volume, dict):
                source = str(volume.get("source", ""))
                target = str(volume.get("target", ""))
                opts = {str((volume.get("bind") or {}).get("selinux", ""))}
            else:
                m = _SHORT_MOUNT_RE.match(str(volume))
                if m is None:
                    continue  # anonymous volume: no host dir to relabel
                source, target = m["source"], m["target"]
                opts = set((m["opts"] or "").split(","))
            if target.rstrip("/") == "/cameras" or "FOSCAM_BASE_PATH" in source:
                out.append((name, str(volume), opts))
    return out


def _services(fname: str) -> dict:
    """Service map of a tracked compose file, merge tags included.

    Plain `yaml.safe_load` RAISES on config/docker-compose.gb300.yml: it uses
    compose's own `!override` tag on `depends_on`, and a ConstructorError is not
    the same thing as "the retired service is absent" -- it would fail this
    file's absence pin for a reason that has nothing to do with ai-llm.
    `_ComposeLoader` (defined below, for the camera-mount sweep) reads those tags
    as plain mappings, so every compose pin in this module parses one same way.
    """
    return (yaml.load((REPO_ROOT / fname).read_text(), Loader=_ComposeLoader) or {}).get(  # noqa: S506  # nosemgrep: unsafe-yaml-load
        "services"
    ) or {}


class TestRetiredLlmServiceIsGone:
    """R8's compose-side DONE item: the legacy `ai-llm` service is gone from
    EVERY tracked compose file, not just the prod one.

    S2b deleted the service out of `docker-compose.prod.yml`, and this class went
    red in CI because its `AI_SERVICES` list still named it -- four green pins
    ("has no-new-privileges", "drops ALL", "not privileged", "no SYS_ADMIN")
    silently degenerating into `{}.get(...) == []` readings over an absent
    service. `test_ai_service_has_no_new_privileges` cannot tell "hardened" from
    "missing" on its own; that gap is what
    `test_no_evidence_is_admitted_to_the_hardened_list_by_absence` closes, and
    it is the general lesson: a parametrized security pin whose subject is
    deleted reports success, not absence.

    The absence pins are file-set-wide and exact-keyed. What is deliberately NOT
    duplicated here: `backend/tests/unit/core/test_ai_vlm_compose_service.py`
    already owns the prod-only absence, the `profiles == ["vllm"]` opt-in, and
    backend's depends_on shape; what is new is (a) every tracked compose file,
    (b) the prefix-vs-exact-key distinction, and (c) the list-vacuity guard.
    """

    @pytest.mark.parametrize("fname", TRACKED_COMPOSE_FILES)
    def test_no_compose_file_defines_the_retired_service(self, fname: str) -> None:
        """Exact-key absence: `ai-llm` as a service key appears nowhere.

        Asserted on parsed service keys, not by grepping the raw text, and that
        choice is measured rather than stylistic: `grep -c ai-llm` over this
        file set returns two hits -- one sentence of retirement prose
        (config/docker-compose.gb300.yml:43) and the live prefixed key
        `ai-llm-vllm:` (docker-compose.prod.yml:283). A text grep would call
        both ghosts. (The count was three until O1.2 deleted the third: the
        same kind of retirement prose in the ghcr compose file.) The parsed
        keys say what a file actually defines, and
        `test_the_retired_name_survives_only_as_prose_or_the_prefixed_key`
        pins the surviving hits so the prose allowance cannot widen silently.
        """
        services = _services(fname)
        assert services, f"{fname} parsed to zero services -- the loader moved"
        assert "ai-llm" not in services, (
            f"{fname} defines the retired `ai-llm` service. R8 S2 deleted the "
            "legacy LLM tier (602379e2) and container_orchestrator.py:66 keeps "
            "REFUSE re-adding it; a compose file that ships it anyway is the "
            "disagreement to resolve, not a test to relax"
        )

    def test_the_absence_pin_is_not_a_prefix_match(self) -> None:
        """Non-vacuity for the test above.

        `ai-llm-vllm` exists and is alive (profile-gated), and its name starts
        with the retired one. A detection written as a substring scan would
        report it as the ghost; a test written the other way (assert
        `"ai-llm" not in str(services)`) would pass only by accident of the
        prefixed key NOT being spelled exactly. This pins the concrete
        distinction: the exact key is gone, the prefixed key is deliberately
        still there.
        """
        services = _services("docker-compose.prod.yml")
        assert "ai-llm" not in services
        assert "ai-llm-vllm" in services, (
            "ai-llm-vllm left docker-compose.prod.yml without this class being "
            "updated -- if it is gone for good, that is a real retirement and "
            "the name in RETIRED_LLM_SERVICES plus the opt-in pin in "
            "test_ai_vlm_compose_service.py die with it"
        )

    def test_no_evidence_is_admitted_to_the_hardened_list_by_absence(self) -> None:
        """The guard the S2b CI failure actually taught.

        `AI_SERVICES` carried `ai-llm` AFTER the service was deleted, so four
        security pins passed over nothing (verified red-first on this tree:
        restoring the name to the list fails this pin, and the CI message is
        the vacuous-green `[] in []` shape rephrased). A list-driven pin must
        assert its subjects are real containers, or deleting a service reads as
        hardening it.
        """
        services = _services("docker-compose.prod.yml")
        hardened = TestDockerComposeSecurityHardening.AI_SERVICES
        assert hardened, (
            "AI_SERVICES is empty: every parametrized pin in "
            "TestDockerComposeSecurityHardening is vacuously green, including "
            "this guard"
        )
        ghosts = [name for name in hardened if name not in services]
        assert not ghosts, (
            f"AI_SERVICES names containers that do not exist: {ghosts} -- the "
            "hardening pins for those names are vacuous (service.get() on a "
            "missing service reads {} and every assertion passes)"
        )

    def test_the_surviving_vllm_engine_diverges_on_purpose(self) -> None:
        """`ai-llm-vllm` carries a DIFFERENT posture from the two hardened
        services, and is deliberately not in `AI_SERVICES`.

        It was not swept into the list by the same edit that dropped `ai-llm`,
        because sweeping it in would be one of two unowned moves dressed as a
        test fix: either (a) add `label=disable` to a production compose file --
        a runtime config change to a serving stack, not S2b's scope (S2b deletes
        code, it does not relabel containers), or (b) edit the consistency test
        to tolerate a difference, which is the "widen the quarantine" reflex the
        goal prompt forbids. So it stays outside the list and this test names the
        drift (measured 2026-09-29: ai-vlm and ai-gateway both
        `[no-new-privileges:true, label=disable]`, the engine only
        `[no-new-privileges:true]`, all three `cap_drop: [ALL]`) instead of
        hiding it.

        Who owns closing it: whoever opts the engine in for real -- the same
        standing decision that keeps it hidden (`profiles: [vllm]`, pinned by
        test_ai_vlm_compose_service.py::test_the_surviving_engine_stays_opt_in;
        `container_orchestrator.py:66 RETIRED_LLM_SERVICES` refuses both
        spellings at :531). Until then the divergence is visible, owned, and
        pinned.
        """
        services = _services("docker-compose.prod.yml")
        assert "ai-llm-vllm" not in TestDockerComposeSecurityHardening.AI_SERVICES, (
            "ai-llm-vllm joined AI_SERVICES; if its posture was actually "
            "aligned with ai-vlm/ai-gateway, update this test with the diff "
            "that proves it -- the list membership and the drift pin move together"
        )
        engine = services["ai-llm-vllm"]
        hardened = services["ai-vlm"]
        # cap_drop already agrees; the drift is one option in security_opt.
        assert engine.get("cap_drop") == hardened.get("cap_drop") == ["ALL"]
        drift = set(hardened.get("security_opt", [])) - set(engine.get("security_opt", []))
        assert drift == {"label=disable"}, (
            f"the drift between ai-vlm and ai-llm-vllm security_opt changed "
            f"shape: {drift}. This test exists to notice; decide which way to "
            "close it (align the compose file, or explain the new difference) "
            "rather than dropping the pin"
        )
        # ...and the option it lacks is not the one that keeps it off the GPU.
        assert engine.get("profiles") == ["vllm"], (
            "ai-llm-vllm is no longer profile-gated -- that is the control that "
            "keeps a second model off the VLM's GPU, and it outranks the "
            "security_opt drift recorded above"
        )

    def test_the_retired_name_survives_only_as_prose_or_the_prefixed_key(self) -> None:
        """The complement of the parsed-key pin, and the reason it is allowed to
        parse instead of grep: `ai-llm` is still WRITTEN in this file set,
        twice, and each time for a reason someone chose.

        gb300:43 is a comment explaining that a deleted depends_on entry
        pointed at the service R8 S2 retired (prose about a retirement has to
        be able to name what retired --
        same rule `TestDeadModulesAreGone.test_no_survivor_imports_the_dead`
        states for docstrings), and prod:283 is the live `ai-llm-vllm:` key that
        shares the prefix. Anything else is a new tenant in the retired slot:
        uncommenting a deleted service, or a rename landing the dead name on a
        live container.
        """
        strays: list[str] = []
        for fname in TRACKED_COMPOSE_FILES:
            for lineno, line in enumerate((REPO_ROOT / fname).read_text().splitlines(), start=1):
                if "ai-llm" not in line:
                    continue
                stripped = line.strip()
                if stripped.startswith("#"):
                    continue  # retirement prose
                if stripped == "ai-llm-vllm:":
                    continue  # the live prefixed key (prod only, today)
                strays.append(f"{fname}:{lineno}: {stripped}")
        assert not strays, "the retired service name reappeared as code, not prose:\n" + "\n".join(
            strays
        )


class TestCameraMountIsWatchableUnderSELinux:
    """The backend's file watcher needs an inotify WATCH on /cameras, and on an
    SELinux-enforcing host (the A5500 box: Fedora, enforcing) a container_t
    process may read a usr_t directory but not watch it. The audit log showed
    `avc: denied { watch watch_reads } ... path="/cameras" ... tcontext=usr_t`
    at every backend start, while the watcher logged "started successfully" and
    never received an event - so no upload was ever ingested (A5500 bring-up,
    2026-09-28). `:z` makes podman relabel the source to the shared
    container_file_t, the same fix the model-zoo mount already carries.
    """

    @pytest.fixture
    def backend_volumes(self) -> list[str]:
        path = Path(__file__).parent.parent.parent.parent / "docker-compose.prod.yml"
        return yaml.safe_load(path.read_text())["services"]["backend"]["volumes"]

    def test_camera_mount_is_relabelled_for_containers(self, backend_volumes: list[str]) -> None:
        camera = [v for v in backend_volumes if isinstance(v, str) and ":/cameras" in v]
        assert len(camera) == 1, f"expected one /cameras mount, found {camera}"
        options = camera[0].split(":/cameras", 1)[1].lstrip(":").split(",")
        assert "z" in options or "Z" in options, (
            f"{camera[0]!r} has no SELinux relabel option - the watcher cannot "
            "inotify-watch a usr_t camera root on an enforcing host"
        )

    # -- every compose file, every service (owner ruling 2026-09-28) ----------
    # The backend is not the only container that touches the camera root:
    # foscam-init chowns it BEFORE the backend starts (so on a fresh host it
    # is the first to touch the dir - the A5500 audit log also showed its
    # `avc: denied { setattr } for comm="chown" ... tcontext=...usr_t`). Each
    # such mount relabels.

    def test_the_tracked_compose_list_is_what_git_tracks(self) -> None:
        # The list below is explicit, not a working-tree glob: a stale local
        # docker-compose.override.yml (setup.py no longer generates one) is not
        # the repo's. This keeps the list honest wherever git is available.
        git = shutil.which("git")
        if git is None:
            pytest.skip("git not available")
        result = subprocess.run(  # noqa: S603  # real git ls-files, fixed argv, 30s timeout
            [git, "ls-files", "*docker-compose*.yml"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )
        if result.returncode != 0:
            pytest.skip(f"not a git checkout: {result.stderr.strip()}")
        assert sorted(result.stdout.split()) == sorted(TRACKED_COMPOSE_FILES)

    @pytest.mark.parametrize("fname", TRACKED_COMPOSE_FILES)
    def test_every_camera_mount_relabels(self, fname: str) -> None:
        text = (REPO_ROOT / fname).read_text()
        bare = [
            f"{service}: {mount}"
            for service, mount, opts in _camera_mounts(text)
            if not opts & {"z", "Z"}
        ]
        assert not bare, (
            f"{fname}: camera-root mount(s) without :z/:Z - {bare}. On an "
            "SELinux-enforcing host the container cannot watch (backend) or "
            "chown (foscam-init) a usr_t camera root; add z to the options"
        )

    def test_the_camera_mounts_that_must_relabel_are_found(self) -> None:
        # Non-vacuity: the pin above passes trivially if it finds nothing.
        found = {
            (fname, service)
            for fname in TRACKED_COMPOSE_FILES
            for service, _mount, _opts in _camera_mounts((REPO_ROOT / fname).read_text())
        }
        assert found >= {
            ("docker-compose.prod.yml", "backend"),
            ("docker-compose.prod.yml", "foscam-init"),
        }

    @pytest.mark.parametrize(
        ("volume", "relabels"),
        [
            ("${FOSCAM_BASE_PATH:-/export/foscam}:/cameras", False),
            ("${FOSCAM_BASE_PATH:-/export/foscam}:/cameras:ro", False),
            ("${FOSCAM_BASE_PATH:-/export/foscam}:/cameras:ro,z", True),
            ("${FOSCAM_BASE_PATH:-/export/foscam}:/cameras:Z", True),
            # the camera root mounted somewhere else is still the camera root
            ("${FOSCAM_BASE_PATH}:/data/cams:ro", False),
            ("/srv/cams:/cameras/:z", True),
            ({"type": "bind", "source": "/srv/cams", "target": "/cameras"}, False),
            (
                {
                    "type": "bind",
                    "source": "/srv/cams",
                    "target": "/cameras",
                    "bind": {"selinux": "z"},
                },
                True,
            ),
        ],
    )
    def test_the_detector_reads_short_and_long_syntax(
        self, volume: str | dict, relabels: bool
    ) -> None:
        text = yaml.safe_dump({"services": {"svc": {"volumes": [volume]}}})
        [(_service, _mount, opts)] = _camera_mounts(text)
        assert bool(opts & {"z", "Z"}) is relabels
