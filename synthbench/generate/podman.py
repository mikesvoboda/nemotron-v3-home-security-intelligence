"""The dedicated podman store for synthbench images, off the root filesystem.

Every synthbench podman call starts with podman_argv(): rootless podman with
--root under $SYNTHBENCH_PODMAN_ROOT (default /export/models/containers, on
ZFS) and its own --runroot, so the user's default store, which also holds the
compose stack, is never touched. Builds and pulls also run with podman_env(),
whose TMPDIR keeps podman's blob staging off /var/tmp. Plain `podman images`
does not list these images, by design. In shell commands:

    $(uv run python -m synthbench.generate.podman) images
"""

from __future__ import annotations

import os
import shlex
import sys
from collections.abc import Mapping
from pathlib import Path

DEFAULT_ROOT = "/export/models/containers"


def podman_root(env: Mapping[str, str] | None = None) -> Path:
    e = os.environ if env is None else env
    return Path(e.get("SYNTHBENCH_PODMAN_ROOT", DEFAULT_ROOT))


def podman_argv(env: Mapping[str, str] | None = None, *, uid: int | None = None) -> list[str]:
    """`podman` plus the global flags that select the synthbench store."""
    user = os.getuid() if uid is None else uid
    return [
        "podman",
        "--root",
        str(podman_root(env) / "storage"),
        "--runroot",
        f"/run/user/{user}/synthbench-containers",
    ]


def podman_env(env: Mapping[str, str] | None = None) -> dict[str, str]:
    """A copy of the environment with TMPDIR=<root>/tmp, for builds and pulls.

    Callers that build or pull create <root>/storage and <root>/tmp first.
    """
    e = os.environ if env is None else env
    return {**e, "TMPDIR": str(podman_root(e) / "tmp")}


def main() -> int:
    sys.stdout.write(shlex.join(podman_argv()) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
