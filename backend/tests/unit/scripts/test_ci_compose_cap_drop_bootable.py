"""Main-green slice 1: the CI compose must boot postgres/redis *with* the hardening.

``docker-compose.ci.yml`` runs every service with ``cap_drop: [ALL]`` and
``no-new-privileges:true``. For the two upstream images that is exactly the
combination that cannot boot, measured byte-for-byte both in CI (smoke job at
heads ``18339acd`` and ``67ca4870``, step "Start services") and locally in
this repo's sandbox from a clean ``docker compose up``:

* postgres:16-alpine starts as root; its entrypoint does
  ``chown postgres /var/lib/postgresql/data`` — CHOWN is dropped —
  ``chown: /var/lib/postgresql/data: Operation not permitted``, exit 1.
* redis:7.4-alpine3.21 starts as root; its entrypoint does
  ``setpriv --reuid redis`` — SETUID/SETGID are dropped —
  ``setpriv: setresuid failed: Operation not permitted``, exit 127
  (127 is setpriv's exit code, NOT a missing command).

The fix is NOT to drop the hardening (owner ruling: never delete it without
a ruling). The fix is to start the containers as the users those images'
entrypoints would have dropped to, so no privilege is ever needed:
``user: "70:70"`` for postgres, ``user: "999:1000"`` for redis — uids read
from the running containers with ``id`` (postgres 70:70, redis 999:1000).
Postgres needs one more thing: a tmpfs mounted at ``/var/lib/postgresql/data``
is root-owned and uid 70 cannot ``chmod`` the mount point itself
(``initdb: error: could not change permissions of directory ... Operation
not permitted`` — measured after only adding the user pin), so PGDATA moves
one level down into a directory initdb creates for itself.

The compose guard below was SEEN RED at main tip ``67ca4870`` (8 failed,
1 passed — the pass is the hardening-retention pin, which is a guard rather
than a repro) before the compose edits. Six of the eight are pre-existing
reds in the same smoke job that CI has never reached because postgres exits
first, each measured against the exact images CI pulls:

* the frontend image is ``nginxinc/nginx-unprivileged`` and listens on 8080
  (``frontend/nginx.conf:71``), so the ``3000:80`` mapping and the
  in-container ``localhost:80`` healthcheck both reached nothing;
* ``read_only: true`` kills that frontend at ``sed -i`` on its own nginx
  config — ``docker-compose.prod.yml:897`` already carries a NOTE ruling
  this service non-read-only, and the CI compose contradicted it;
* ``PYTHON_GIL=0`` is fatal against the GIL-enabled ``backend:latest``;
* with no ``ENVIRONMENT``, Settings defaults to ``production`` and raises
  on the CI redis's missing password (both other composes set
  ``development`` explicitly);
* the read-only rootfs makes the lifespan FileWatcher raise
  ``[Errno 30] /cameras``, the lifespan's except swallows it, and
  ``/health/ready`` answers 503 forever without a ``/cameras`` tmpfs.
"""

from __future__ import annotations

from pathlib import Path, PurePosixPath

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[4]
COMPOSE = REPO_ROOT / "docker-compose.ci.yml"


@pytest.fixture(scope="module")
def services() -> dict:
    return yaml.safe_load(COMPOSE.read_text(encoding="utf-8"))["services"]


def _env(service: dict) -> dict:
    """Compose list-style ``environment`` as a dict."""
    out = {}
    for entry in service.get("environment") or []:
        key, _, value = str(entry).partition("=")
        out[key] = value
    return out


def test_hardening_is_kept(services: dict) -> None:
    """The owner ruling: cap_drop ALL + no-new-privileges stay. Pin them."""
    for name in ("postgres", "redis", "backend", "frontend"):
        svc = services[name]
        assert "ALL" in (svc.get("cap_drop") or []), f"{name} lost cap_drop: ALL"
        assert "no-new-privileges:true" in (svc.get("security_opt") or []), (
            f"{name} lost security_opt no-new-privileges:true"
        )


def test_postgres_runs_as_the_postgres_uid(services: dict) -> None:
    """cap_drop ALL removes the entrypoint's drop-to-postgres ability; pin it."""
    assert services["postgres"].get("user") == "70:70", (
        "postgres:16-alpine must run as its service uid 70:70 — as root with "
        "cap_drop ALL its entrypoint dies on 'chown: Operation not permitted'"
    )


def test_redis_runs_as_the_redis_uid(services: dict) -> None:
    assert services["redis"].get("user") == "999:1000", (
        "redis:7.4-alpine3.21 must run as its service uid 999:1000 — as root "
        "with cap_drop ALL its entrypoint dies on 'setpriv: setresuid failed'"
    )


def test_postgres_pgdata_is_below_the_tmpfs_mount_point(services: dict) -> None:
    """A tmpfs mount point is root-owned; initdb (uid 70) cannot chmod it.

    PGDATA must sit inside — not on — a tmpfs path so initdb creates and
    owns the datadir itself.
    """
    env = _env(services["postgres"])
    pgdata = env.get("PGDATA")
    tmpfs_paths = set(services["postgres"].get("tmpfs") or [])
    assert pgdata, "postgres must set PGDATA explicitly"
    assert any(pgdata.startswith(f"{p}/") for p in tmpfs_paths), (
        f"PGDATA={pgdata} must live inside a tmpfs mount "
        f"(tmpfs: {sorted(tmpfs_paths)}), not ON a mount point"
    )
    assert pgdata.rstrip("/") not in tmpfs_paths, (
        f"PGDATA={pgdata} is a tmpfs mount point — root-owned, initdb cannot "
        "chmod it with cap_drop ALL"
    )


def test_backend_does_not_force_gil_off(services: dict) -> None:
    """PYTHON_GIL=0 is fatal against the image CI actually pulls.

    The CI job signs/pulls ``backend:latest`` built from
    ``python:3.14-slim-bookworm`` — measured inside that image:
    ``sysconfig.get_config_var('Py_GIL_DISABLED') == 0`` and running any
    python with ``PYTHON_GIL=0`` exits 1 with
    ``Fatal Python error: config_read_gil: Disabling the GIL is not
    supported by this build``. The entrypoint's DB-wait loop is python, so
    every CI backend start would die at the first health poll — CI never
    saw it only because postgres exits before backend leaves 'Created'.
    The free-threaded base exists (docker/python-freethreaded/, built by
    .github/workflows/python-freethreaded.yml) but the backend Dockerfile's
    prod stage does not use it, so the env var is a guaranteed crash, not
    a perf knob, until that build switch happens.
    """
    env = _env(services["backend"])
    assert env.get("PYTHON_GIL") != "0", (
        "the shipped backend image is GIL-enabled (Py_GIL_DISABLED=0); "
        "PYTHON_GIL=0 makes every python invocation fatal"
    )


def test_backend_overrides_the_production_environment_default(services: dict) -> None:
    """Settings.environment defaults to 'production' (config.py:813) — measured.

    backend:latest then hard-raises at import:
    ``REDIS_PASSWORD must be set for production environment`` (config.py:3276),
    which the CI redis deliberately does not require. The prod compose sets
    ENVIRONMENT=${ENVIRONMENT:-development} explicitly
    (docker-compose.prod.yml:479); the CI compose set nothing and inherited
    the production default.
    """
    env = _env(services["backend"])
    assert env.get("ENVIRONMENT") == "development", (
        "backend must pin ENVIRONMENT=development like the prod compose "
        "— the field defaults to 'production' and Settings raises without "
        "REDIS_PASSWORD there"
    )


def test_backend_gives_the_filewatcher_a_writable_cameras_path(services: dict) -> None:
    """read_only rootfs + inotify on /cameras = readiness 503 forever.

    backend/main.py starts FileWatcher(use_polling=False) on
    settings.foscam_base_path (FOSCAM_BASE_PATH=/cameras in this file).
    On the read-only rootfs the watch setup raises ``[Errno 30] Read-only
    file system: '/cameras'`` inside the lifespan's Redis try-block — the
    except swallows it, pipeline_manager is never constructed or
    registered, and /health/ready answers 503 ("Pipeline manager not
    registered — marking as not ready", backend/api/routes/system.py:692)
    for the whole 120 s CI wait loop. Measured: with a tmpfs at /cameras
    the backend boots, registers, and answers the probe.
    """
    tmpfs_paths = set(services["backend"].get("tmpfs") or [])
    assert any(p.rstrip("/") == "/cameras" for p in tmpfs_paths), (
        f"backend tmpfs {sorted(tmpfs_paths)} must include /cameras — the "
        "read-only rootfs makes the lifespan FileWatcher raise Errno 30 and "
        "silently skip pipeline_manager registration"
    )


def test_backend_gives_the_runtime_env_a_writable_path(services: dict) -> None:
    """Every config SAVE is a file write, and the rootfs cannot take one.

    Three routes persist settings and all three default to ``./data/runtime.env``:
    ``system.py:_runtime_env_path`` (``PATCH /api/system/config``, the F-195
    retention save), the same resolver under ``PUT /api/system/severity``, and
    ``settings_api.py:_get_runtime_env_path`` (``PATCH /api/v1/settings``,
    F-190/F-191's Save). Under ``read_only: true``
    that default cannot be created — measured in the image CI pulls, under this
    file's exact flags (cap_drop ALL, no-new-privileges, and as the image's own
    uid 1000): ``[Errno 30] Read-only file system``, surfaced to the user as a
    500 and a "Failed to update log retention" toast. Ruling 127 routed the fix
    to F2.3 as "`HSI_RUNTIME_ENV_PATH` (ops-b owns it)".

    The cure is the path, NOT the hardening: ``read_only`` stays (asserted
    below), which is why this is the sibling of the ``/cameras`` pin rather
    than the frontend pin above. Two properties make the cure correct, and this
    test holds both, because the two writers validate differently —
    ``system.py`` has a traversal guard whose ``allowed_bases`` includes
    ``tempfile.gettempdir()`` and silently FALLS BACK to the unwritable
    ``./data/runtime.env`` if the configured path is rejected, while
    ``settings_api.py`` has NO validator at all and will happily write wherever
    it is told. So the value must be (a) inside a mount that is writable and
    (b) still under the tempdir that guard accepts:

    * ``/tmp`` is already a tmpfs in this file, so no new mount is needed and
      nothing baked into the image is shadowed (measured: the backend image
      ships neither ``/app/data/runtime.env`` nor ``/app/.env``);
    * the container's ``gettempdir()`` is ``/tmp`` only because nothing sets
      ``TMPDIR`` for this service — pin that too, because a later ``TMPDIR``
      moves the guard's allowed base off ``/tmp`` and the guard's silent
      fallback puts the Errno 30 right back.
    """
    svc = services["backend"]
    assert svc.get("read_only"), (
        "backend keeps read_only: true — the runtime-env fix is a writable "
        "PATH, not a writable root filesystem (owner ruling: never delete "
        "hardening without a ruling)"
    )
    env = _env(svc)
    runtime_env = env.get("HSI_RUNTIME_ENV_PATH")
    assert runtime_env, (
        "backend must set HSI_RUNTIME_ENV_PATH: all three settings-save routes "
        "default to ./data/runtime.env, which read_only: true cannot write "
        "— every Save answers 500 [Errno 30] without it"
    )
    parent = str(PurePosixPath(runtime_env).parent)
    tmpfs_paths = {p.rstrip("/") for p in svc.get("tmpfs") or []}

    # Containment under a mount, not equality with one — prefix-safe, so
    # `/tmpevil` never counts as under `/tmp`. A subdirectory of a tmpfs is
    # writable and `_write_runtime_env` creates it (`path.parent.mkdir
    # (parents=True)`, system.py:2572), so `/tmp/hsi/runtime.env` boots. The
    # property under test is "the save lands on a WRITABLE mount", not "the
    # path is spelled exactly /tmp".
    def _under(mount: str) -> bool:
        return parent == mount or parent.startswith(mount + "/")

    assert any(_under(m) for m in tmpfs_paths), (
        f"HSI_RUNTIME_ENV_PATH={runtime_env} must live under one of this "
        f"service's tmpfs mounts {sorted(tmpfs_paths)} — a path inside the "
        "read-only rootfs restores the [Errno 30] the F-190/F-191/F-195 rows "
        "cite"
    )
    # Containment under the guard's base, NOT equality with it. system.py's
    # guard is `str(path).startswith(base)` for base in allowed_bases
    # (:2545-2556) and _write_runtime_env does `path.parent.mkdir(parents=True)`
    # (:2572), so /tmp/hsi/runtime.env clears the guard AND creates its own
    # parent — it works. Asserting parent == "/tmp" here would red a compose
    # value that boots, which is a stricter contract than the product has.
    assert parent == "/tmp" or parent.startswith("/tmp/"), (  # noqa: S108
        f"HSI_RUNTIME_ENV_PATH={runtime_env} must be contained under /tmp: "
        "system.py's traversal guard allows tempfile.gettempdir() — which in "
        "this image is /tmp — by PREFIX, and falls back to the unwritable "
        "./data/runtime.env for anything else (settings_api.py has no "
        "validator at all, so only this guard can veto)"
    )
    assert env.get("TMPDIR") is None, (
        "backend must not set TMPDIR: it relocates tempfile.gettempdir(), "
        "which is the base system.py's guard allows, and the guard's silent "
        "fallback re-introduces the unwritable ./data/runtime.env"
    )


def test_frontend_is_not_read_only_like_prod_ruled(services: dict) -> None:
    """docker-compose.prod.yml:897 already ruled this service cannot be read-only.

    Its entrypoint rewrites /etc/nginx/conf.d/default.conf with ``sed -i``
    at startup; with ``read_only: true`` the container dies on
    ``sed: can't create temp file ... Read-only file system`` (measured
    against ``frontend:latest`` pulled from GHCR). cap_drop/no-new-privileges
    stay pinned by the first test — that ruling is untouched.
    """
    assert not services["frontend"].get("read_only"), (
        "frontend must not be read_only: its entrypoint sed -i's its own "
        "nginx config at startup — see the NOTE in docker-compose.prod.yml"
    )


def test_frontend_port_maps_to_the_unprivileged_listen_port(services: dict) -> None:
    """The frontend image is nginx-unprivileged listening on 8080.

    docker-compose.ci.yml mapped '3000:80'; nothing listens on 80 in that
    image (frontend/nginx.conf: listen 8080; frontend/Dockerfile EXPOSE
    8080 8443), so the CI wait loop could never reach the container.
    """
    ports = [str(p) for p in services["frontend"].get("ports") or []]
    assert any(p.endswith(":8080") for p in ports), (
        f"frontend ports {ports} must map the host port to 8080 — "
        "the image listens there, never on 80"
    )
