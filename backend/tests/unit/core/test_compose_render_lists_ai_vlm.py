"""The Done-when for O1.3, executable: a default `config --services` render lists `ai-vlm`.

`docs/uplevel/30-ops.md` O1.3 states its bar as a command an operator runs:
"`podman compose -f docker-compose.prod.yml config --services` with no profile
flag lists `ai-vlm`". The structural pin next door
(`test_ai_vlm_compose_service.py::test_starts_by_default`) proves the same fact
from the parsed YAML, but a Done-when phrased as a command deserves the command:
this test renders the real compose file through a real compose binary and reads
the render. It is the version of the evidence a reviewer or CI can rerun, which
the PR body's pasted output is not (contract rule 3: work from /tmp does not
count).

The compose file interpolates several variables with no default, so the render
needs an env file; it is committed (`backend/tests/fixtures/compose-render.env`)
for the same reason — without it the check only runs on a configured operator
box, and `.env.example` deliberately does not render the file (the A5500
env-template note records that).

Compose tooling varies by machine, so the first available of
`podman compose` / `docker compose` / `podman-compose` / `docker-compose` is
used and the test skips when none exists (a laptop with neither is not a
failure of the compose file). `podman compose` — the Done-when's own tool — is
tried first. The render is read verbatim: the point is that a plain
`config --services`, no `--profile` anywhere, resolves the service.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[4]
COMPOSE_FILE = REPO_ROOT / "docker-compose.prod.yml"
ENV_FILE = REPO_ROOT / "backend" / "tests" / "fixtures" / "compose-render.env"


def _compose_argv() -> list[str] | None:
    """The first compose invocation this machine can run, Done-when order."""
    if shutil.which("podman"):
        return ["podman", "compose"]
    if shutil.which("docker"):
        return ["docker", "compose"]
    for binary in ("podman-compose", "docker-compose"):
        if shutil.which(binary):
            return [binary]
    return None


@pytest.mark.timeout(120)  # a cold compose render can outlast the 5s default
def test_default_services_render_lists_ai_vlm() -> None:
    """No profile flag is passed, and the plain render resolves `ai-vlm`.

    The fixture is asserted to exist rather than skipped-if-missing: the file
    being in the repo IS the finding this test closes, and its absence is the
    failure mode (evidence that only lives in someone's /tmp), not a skip.
    """
    assert ENV_FILE.is_file(), (
        f"{ENV_FILE.relative_to(REPO_ROOT)} is missing; the Done-when render "
        "needs a committed env because the compose file interpolates several "
        "variables with no default"
    )
    argv = _compose_argv()
    if argv is None:
        pytest.skip("no compose binary (podman/docker) on this machine")
    # The process environment stays inherited (podman needs XDG_RUNTIME_DIR,
    # compose needs PATH), which is safe for this assertion: the two variables
    # the fixture supplies are hard-required for interpolation to run at all,
    # and no interpolated value adds or removes a service — the set of service
    # KEYS in the file is what `--services` prints, so the result cannot
    # depend on the machine's env.
    result = subprocess.run(  # noqa: S603 - argv is a literal list, never a shell string  # real
        [
            *argv,
            "--env-file",
            str(ENV_FILE),
            "-f",
            str(COMPOSE_FILE),
            "config",
            "--services",
        ],
        capture_output=True,
        text=True,
        timeout=100,
        check=False,
    )
    assert result.returncode == 0, (
        f"{' '.join(argv)} config --services failed (exit {result.returncode}):\n"
        f"{result.stderr[-2000:]}"
    )
    services = {line.strip() for line in result.stdout.splitlines() if line.strip()}
    assert "ai-vlm" in services, (
        "a plain `config --services` with no --profile flag does not list "
        f"ai-vlm; it resolved: {sorted(services)}"
    )
