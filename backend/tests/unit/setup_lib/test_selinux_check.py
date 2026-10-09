"""Unit tests for setup_lib.selinux_check (A5500 box, 2026-09-28).

ABOUTME: One host check, two callers. On an SELinux-enforcing host a
container_t backend may READ a usr_t camera root but not inotify-WATCH it
(`avc: denied { watch watch_reads }`), so the file watcher goes blind unless
the root is container_file_t or the backend's /cameras mount relabels it
(:z/:Z). ``setup.py deploy`` runs this as a preflight and
``scripts/a5500_precheck.py`` renders it as its selinux_camera_root row. The
host readers are injected, so nothing here depends on the CI host's SELinux.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

import pytest
from setup_lib.selinux_check import (
    PASS,
    WARN,
    camera_root,
    check_camera_root,
    read_selinux_enforcing,
    read_selinux_label,
    service_camera_mounts,
)

SHARED_MODULE = Path(__file__).resolve().parents[4] / "setup_lib" / "selinux_check.py"
USR_T = "system_u:object_r:usr_t:s0"
CONTAINER_FILE_T = "system_u:object_r:container_file_t:s0"
ROOT = "/export/foscam"

# prod.yml's shape: backend and foscam-init both mount the camera root; only
# the backend watches it.
COMPOSE = """\
services:
  foscam-init:
    volumes:
      - ${FOSCAM_BASE_PATH:-/export/foscam}:/cameras:z
  backend:
    volumes:
      - ./backend/data:/app/data:z,U
      - ${FOSCAM_BASE_PATH:-/export/foscam}:/cameras{opts}
    environment:
      - FOSCAM_BASE_PATH=/cameras
  frontend:
    volumes:
      - ./frontend/dist:/usr/share/nginx/html:ro
"""


def _compose(tmp_path: Path, name: str, opts: str = "") -> Path:
    p = tmp_path / name
    p.write_text(COMPOSE.replace("{opts}", opts), encoding="utf-8")
    return p


def _check(
    mounts: dict[str, list[str]],
    *,
    enforcing: bool | None = True,
    label: str | None = USR_T,
    root: str = ROOT,
    asked: list[str] | None = None,
):
    def fake_label(path: str) -> str | None:
        if asked is not None:
            asked.append(path)
        return label

    return check_camera_root(
        root, mounts, selinux_enforcing=lambda: enforcing, selinux_label=fake_label
    )


class TestCameraRoot:
    def test_defaults_to_the_compose_default(self) -> None:
        assert camera_root({}) == "/export/foscam"
        assert camera_root({"FOSCAM_BASE_PATH": ""}) == "/export/foscam"

    def test_reads_foscam_base_path_unquoted(self) -> None:
        assert camera_root({"FOSCAM_BASE_PATH": "/srv/cams"}) == "/srv/cams"
        assert camera_root({"FOSCAM_BASE_PATH": "'/srv/cams'"}) == "/srv/cams"


class TestServiceCameraMounts:
    def test_only_the_backends_camera_mount_is_returned(self, tmp_path: Path) -> None:
        # foscam-init's mount is not the watcher's; env FOSCAM_BASE_PATH=/cameras
        # is not a mount.
        prod = _compose(tmp_path, "prod.yml", ":ro,z")
        assert service_camera_mounts([prod]) == {
            "prod.yml": ["${FOSCAM_BASE_PATH:-/export/foscam}:/cameras:ro,z"]
        }

    def test_every_file_gets_a_key_even_without_a_mount(self, tmp_path: Path) -> None:
        prod = _compose(tmp_path, "prod.yml")
        empty = tmp_path / "ci.yml"
        empty.write_text("services:\n  postgres:\n    image: postgres\n", encoding="utf-8")
        assert service_camera_mounts([prod, empty]) == {
            "prod.yml": ["${FOSCAM_BASE_PATH:-/export/foscam}:/cameras"],
            "ci.yml": [],
        }

    def test_a_missing_compose_file_reads_as_no_mount(self, tmp_path: Path) -> None:
        assert service_camera_mounts([tmp_path / "absent.yml"]) == {"absent.yml": []}


class TestCheckCameraRoot:
    def test_enforcing_usr_t_and_a_bare_mount_warns_with_both_fixes(self) -> None:
        v = _check({"prod.yml": ["${FOSCAM_BASE_PATH:-/export/foscam}:/cameras"]})
        assert v.verdict == WARN
        assert "usr_t" in v.detail
        assert "prod.yml: ${FOSCAM_BASE_PATH:-/export/foscam}:/cameras" in v.detail
        assert "avc: denied { watch }" in v.detail
        assert ":z" in v.detail
        assert (
            "sudo semanage fcontext -a -t container_file_t '/export/foscam(/.*)?' "
            "&& sudo restorecon -R /export/foscam"
        ) in v.detail

    def test_selinux_absent_passes(self) -> None:
        v = _check({"prod.yml": []}, enforcing=None, label=None)
        assert v.verdict == PASS
        assert "not present" in v.detail

    def test_selinux_permissive_passes(self) -> None:
        v = _check({"prod.yml": []}, enforcing=False)
        assert v.verdict == PASS
        assert "not enforcing" in v.detail

    def test_a_container_file_t_root_passes_whatever_the_mount(self) -> None:
        v = _check({"prod.yml": ["x:/cameras"]}, label=CONTAINER_FILE_T)
        assert v.verdict == PASS
        assert "container_file_t" in v.detail

    @pytest.mark.parametrize("opts", [":z", ":Z", ":ro,z", ":z,U"])
    def test_a_relabelling_mount_passes_and_is_named(self, opts: str) -> None:
        mount = f"${{FOSCAM_BASE_PATH:-/export/foscam}}:/cameras{opts}"
        v = _check({"prod.yml": [mount]})
        assert v.verdict == PASS
        assert f"prod.yml: {mount}" in v.detail

    def test_one_bare_file_among_relabelling_ones_warns_and_names_only_it(self) -> None:
        # Fixture names are arbitrary; O1.2 / UR-17 retired the compose file the
        # second one used to be named after (scripts/test_retired_paths.py).
        v = _check({"prod.yml": ["r:/cameras:z"], "legacy.yml": ["r:/cameras:ro"]})
        assert v.verdict == WARN
        assert "legacy.yml: r:/cameras:ro" in v.detail
        assert "prod.yml: " not in v.detail

    def test_no_backend_mount_anywhere_warns_naming_the_files_read(self) -> None:
        v = _check({"prod.yml": [], "legacy.yml": []})
        assert v.verdict == WARN
        assert "no backend /cameras mount found in prod.yml, legacy.yml" in v.detail

    def test_an_unreadable_label_under_enforcing_warns(self) -> None:
        v = _check({"prod.yml": ["r:/cameras"]}, label=None)
        assert v.verdict == WARN
        assert "UNREADABLE" in v.detail

    def test_the_label_is_read_from_the_given_root_only_when_enforcing(self) -> None:
        asked: list[str] = []
        _check({"prod.yml": []}, root="/srv/cams", asked=asked)
        assert asked == ["/srv/cams"]
        asked.clear()
        _check({"prod.yml": []}, enforcing=False, asked=asked)
        assert asked == []


class TestHostReaders:
    def test_enforce_file_values(self, tmp_path: Path) -> None:
        on, off = tmp_path / "on", tmp_path / "off"
        on.write_text("1\n")
        off.write_text("0\n")
        assert read_selinux_enforcing(on) is True
        assert read_selinux_enforcing(off) is False
        assert read_selinux_enforcing(tmp_path / "absent") is None

    def test_label_of_a_missing_path_is_none(self, tmp_path: Path) -> None:
        assert read_selinux_label(str(tmp_path / "absent")) is None


class TestImportLight:
    def test_the_module_imports_only_the_standard_library(self) -> None:
        # scripts/a5500_precheck.py loads this file BY PATH and must run with
        # no venv: a third-party (or setup_lib) import here would break it.
        tree = ast.parse(SHARED_MODULE.read_text(encoding="utf-8"))
        imported = {
            (node.module or "").split(".")[0]
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom)
        } | {
            alias.name.split(".")[0]
            for node in ast.walk(tree)
            if isinstance(node, ast.Import)
            for alias in node.names
        }
        assert imported <= set(sys.stdlib_module_names) | {"__future__"}, imported
