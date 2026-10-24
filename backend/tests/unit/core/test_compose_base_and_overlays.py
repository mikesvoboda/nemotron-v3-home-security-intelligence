"""O3.2 Compose base and overlays (ruling 328, record 6378106167).

Pins:
1. Box 1 (ruling 328 item 1):
   - `docker-compose.prod.yml` and `docker-compose.ci.yml` are the two bases,
     each with its own overlays (`engine-false`, `marker-*`, `gb300`, and
     `prodshape` on prod; `fake-ai` and `sinks` on CI).
   - No overlay defines a whole service of its base (a service carrying `image`
     or `build` that the base already defines), and no service is fully defined
     (`image` or `build`) in two files of the same family.
   - Across the two bases, only the four accepted shared services (`backend`,
     `frontend`, `postgres`, `redis`) are defined in both.
2. Box 2:
   - One version per image across compose files; `postgres` and `redis` keep
     identical image versions across `prod`, `ci`, and `test`.
3. Box 4:
   - Comments in `docker-compose.prod.yml` are cut to concise operator notes
     (< 20% of lines, down from 46.2% / 790 lines), with commented-out
     `sentinel1..3` and `DOCKER SECRETS SETUP` tutorials removed.
4. Done when:
   - Every supported compose combination renders with `compose ... config`.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[4]
ENV_FILE = REPO_ROOT / "backend" / "tests" / "fixtures" / "compose-render.env"

PROD_BASE = "docker-compose.prod.yml"
PROD_OVERLAYS = (
    "docker-compose.engine-false.yml",
    "docker-compose.marker-false.yml",
    "docker-compose.marker-true.yml",
    "config/docker-compose.gb300.yml",
    "scripts/uplevel/docker-compose.prodshape.yml",
)

CI_BASE = "docker-compose.ci.yml"
CI_OVERLAYS = (
    "docker-compose.fake-ai.yml",
    "docker-compose.sinks.yml",
)

ACCEPTED_SHARED_BASE_SERVICES = frozenset({"backend", "frontend", "postgres", "redis"})

IMAGE_VERSION_COMPOSE_FILES = (
    "docker-compose.prod.yml",
    "docker-compose.ci.yml",
    "docker-compose.fake-ai.yml",
    "docker-compose.sinks.yml",
    "docker-compose.test.yml",
)


def _passthrough_tag(loader: yaml.SafeLoader, _tag_suffix: str, node: yaml.Node) -> Any:
    if isinstance(node, yaml.SequenceNode):
        return loader.construct_sequence(node)
    if isinstance(node, yaml.MappingNode):
        return loader.construct_mapping(node)
    return loader.construct_scalar(node)


yaml.SafeLoader.add_multi_constructor("!", _passthrough_tag)


def _load_compose(rel_path: str, root: Path = REPO_ROOT) -> dict[str, Any]:
    data = yaml.safe_load((root / rel_path).read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def _is_full_service_definition(svc_def: dict[str, Any] | None) -> bool:
    """True when a service mapping defines `image` or `build` (a full service definition)."""
    if not isinstance(svc_def, dict):
        return False
    return bool(svc_def.get("image") or svc_def.get("build"))


def check_family_no_duplicate_full_services(
    base_rel: str,
    overlay_rels: tuple[str, ...],
    *,
    root: Path = REPO_ROOT,
) -> list[str]:
    """Return violations where an overlay redefines a base service's image/build
    or where any service is fully defined (image or build) in two files of one family.
    """
    violations: list[str] = []
    base_services = _load_compose(base_rel, root).get("services") or {}
    base_defined = {
        name for name, sdef in base_services.items() if _is_full_service_definition(sdef)
    }

    seen_in: dict[str, str] = dict.fromkeys(base_defined, base_rel)

    for ov_rel in overlay_rels:
        ov_services = _load_compose(ov_rel, root).get("services") or {}
        for name, sdef in ov_services.items():
            if not _is_full_service_definition(sdef):
                continue
            if name in base_services:
                violations.append(
                    f"{ov_rel} redefines base service {name!r} (from {base_rel}) with image/build"
                )
            elif name in seen_in:
                violations.append(
                    f"service {name!r} is fully defined in both {seen_in[name]} and {ov_rel}"
                )
            else:
                seen_in[name] = ov_rel

    return violations


def _normalize_image_ref(image: str) -> tuple[str, str] | None:
    """Return `(repo_name, tag)` for a static image reference, ignoring registry prefix."""
    if "$" in image or ":" not in image:
        return None
    name_part, tag = image.rsplit(":", 1)
    repo_name = name_part.rsplit("/", 1)[-1]
    return repo_name, tag


def _compose_argv() -> list[str]:
    if shutil.which("podman"):
        return ["podman", "compose"]
    if shutil.which("docker"):
        return ["docker", "compose"]
    for binary in ("podman-compose", "docker-compose"):
        if shutil.which(binary):
            return [binary]
    raise AssertionError("Neither podman compose nor docker compose is available")


class TestBox1ComposeBaseAndOverlays:
    """Ruling 328 item 1: two bases (prod, ci) and their overlays never duplicate full services."""

    def test_prod_family_has_no_duplicate_full_service_definitions(self) -> None:
        violations = check_family_no_duplicate_full_services(PROD_BASE, PROD_OVERLAYS)
        assert violations == []

    def test_ci_family_has_no_duplicate_full_service_definitions(self) -> None:
        violations = check_family_no_duplicate_full_services(CI_BASE, CI_OVERLAYS)
        assert violations == []

    def test_shared_services_between_bases_are_only_the_accepted_four(self) -> None:
        prod_services = set((_load_compose(PROD_BASE).get("services") or {}).keys())
        ci_services = set((_load_compose(CI_BASE).get("services") or {}).keys())
        shared = prod_services & ci_services
        assert shared == ACCEPTED_SHARED_BASE_SERVICES

    def test_checker_catches_overlay_redefining_base_or_sibling_service(
        self, tmp_path: Path
    ) -> None:
        (tmp_path / "base.yml").write_text(
            "services:\n  backend:\n    build: ./backend\n  redis:\n    image: redis:7.4-alpine3.21\n",
            encoding="utf-8",
        )
        (tmp_path / "ov1.yml").write_text(
            "services:\n  backend:\n    image: custom-backend:latest\n  sink:\n    image: sink:1\n",
            encoding="utf-8",
        )
        (tmp_path / "ov2.yml").write_text(
            "services:\n  sink:\n    build: ./sink\n",
            encoding="utf-8",
        )
        violations = check_family_no_duplicate_full_services(
            "base.yml", ("ov1.yml", "ov2.yml"), root=tmp_path
        )
        assert len(violations) == 2
        assert "ov1.yml redefines base service 'backend'" in violations[0]
        assert "service 'sink' is fully defined in both ov1.yml and ov2.yml" in violations[1]


class TestBox2ImageVersionDrift:
    """Box 2: one version per image across compose files."""

    def test_one_version_per_image_across_compose_files(self) -> None:
        versions_by_repo: dict[str, dict[str, list[str]]] = {}
        for rel in IMAGE_VERSION_COMPOSE_FILES:
            services = _load_compose(rel).get("services") or {}
            for sname, sdef in services.items():
                if not isinstance(sdef, dict) or not sdef.get("image"):
                    continue
                parsed = _normalize_image_ref(str(sdef["image"]))
                if parsed is None:
                    continue
                repo_name, tag = parsed
                versions_by_repo.setdefault(repo_name, {}).setdefault(tag, []).append(
                    f"{rel}:{sname}"
                )

        drift = {repo_name: tags for repo_name, tags in versions_by_repo.items() if len(tags) > 1}
        assert drift == {}, f"Image version drift across compose files: {drift}"


class TestBox4ProdComposeCommentsTrimmed:
    """Box 4: cut comments in docker-compose.prod.yml to what an operator needs."""

    def test_prod_compose_comment_share_is_under_twenty_percent(self) -> None:
        lines = (REPO_ROOT / PROD_BASE).read_text(encoding="utf-8").splitlines()
        comment_lines = [line for line in lines if line.strip().startswith("#")]
        ratio = len(comment_lines) / len(lines)
        assert ratio < 0.20, (
            f"docker-compose.prod.yml still has {len(comment_lines)}/{len(lines)} "
            f"comment lines ({ratio:.1%}); expected < 20%"
        )

    def test_prod_compose_drops_commented_out_sentinel_and_secrets_tutorials(self) -> None:
        text = (REPO_ROOT / PROD_BASE).read_text(encoding="utf-8")
        assert "sentinel1:" not in text
        assert "DOCKER SECRETS SETUP" not in text


class TestDoneWhenSupportedCombinationsRender:
    """Done when: every supported combination renders with `compose ... config`."""

    @pytest.mark.timeout(120)
    @pytest.mark.parametrize(
        ("files", "extra_env", "expected_subset"),
        [
            (
                ("docker-compose.prod.yml",),
                {},
                {
                    "postgres",
                    "redis",
                    "ai-vlm",
                    "ai-gateway",
                    "backend",
                    "frontend",
                    "prometheus",
                    "grafana",
                },
            ),
            (
                ("docker-compose.prod.yml", "docker-compose.engine-false.yml"),
                {"ORCHESTRATOR_ENABLED": "false"},
                {"postgres", "redis", "ai-vlm", "ai-gateway", "backend", "frontend"},
            ),
            (
                ("docker-compose.prod.yml", "config/docker-compose.gb300.yml"),
                {},
                {
                    "postgres",
                    "redis",
                    "ai-vlm",
                    "ai-gateway",
                    "backend",
                    "prometheus",
                    "node-exporter",
                },
            ),
            (
                ("docker-compose.prod.yml", "scripts/uplevel/docker-compose.prodshape.yml"),
                {
                    "HSI_TEST_NAME_PREFIX": "o32-",
                    "PROD_SHAPE_RUN_ROOT": "__TMP_PATH__",
                },
                {"postgres", "redis", "ai-vlm", "ai-gateway", "backend", "frontend"},
            ),
            (
                ("docker-compose.ci.yml",),
                {},
                {"postgres", "redis", "backend", "frontend"},
            ),
            (
                ("docker-compose.ci.yml", "docker-compose.fake-ai.yml"),
                {},
                {"postgres", "redis", "backend", "frontend", "ai-vlm", "ai-gateway"},
            ),
            (
                ("docker-compose.ci.yml", "docker-compose.sinks.yml"),
                {},
                {
                    "postgres",
                    "redis",
                    "backend",
                    "frontend",
                    "mail-sink",
                    "webhook-sink",
                    "push-sink",
                },
            ),
            (
                ("docker-compose.ci.yml", "docker-compose.fake-ai.yml", "docker-compose.sinks.yml"),
                {},
                {
                    "postgres",
                    "redis",
                    "backend",
                    "frontend",
                    "ai-vlm",
                    "ai-gateway",
                    "mail-sink",
                    "webhook-sink",
                    "push-sink",
                },
            ),
            (
                ("docker-compose.test.yml",),
                {},
                {"postgres-test", "redis-test"},
            ),
        ],
    )
    def test_supported_combination_renders(
        self,
        tmp_path: Path,
        files: tuple[str, ...],
        extra_env: dict[str, str],
        expected_subset: set[str],
    ) -> None:
        argv = _compose_argv()
        cmd = [*argv, "--env-file", str(ENV_FILE)]
        for rel in files:
            cmd.extend(["-f", str(REPO_ROOT / rel)])
        cmd.extend(["config", "--services"])

        resolved_extra = {
            k: (str(tmp_path) if v == "__TMP_PATH__" else v) for k, v in extra_env.items()
        }
        env = {**os.environ, **resolved_extra}
        res = subprocess.run(  # noqa: S603 - argv is a literal list, never a shell string  # real
            cmd,
            capture_output=True,
            text=True,
            env=env,
            timeout=60,
            check=False,
        )
        assert res.returncode == 0, (
            f"compose config failed for {files} (rc={res.returncode}):\n{res.stderr[-1500:]}"
        )
        rendered_services = {line.strip() for line in res.stdout.splitlines() if line.strip()}
        assert expected_subset <= rendered_services
