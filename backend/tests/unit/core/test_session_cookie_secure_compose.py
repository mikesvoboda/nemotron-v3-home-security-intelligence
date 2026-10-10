"""Compose wiring for SESSION_COOKIE_SECURE (R55, self-review finding 3).

The R55 docs name ``SESSION_COOKIE_SECURE=false`` as the remedy for the
plain-http login loop on an EXPOSE_LAN box (env-reference "The login cookie
over http and TLS"), and ``Settings`` reads it — but the backend service
declares no ``env_file:`` and ``.env`` is dockerignored, so inside the
container Settings only sees what the ``environment:`` list passes. Before
R55 round 2 the variable appeared zero times in docker-compose.prod.yml
(while ``EXPOSE_LAN`` — the other half of the same two-variable decision —
was threaded there): the documented remedy was unsettable in the shipped
stack, and every operator following the doc followed it into a dead end.

Round 2 threads it ``${SESSION_COOKIE_SECURE:-true}`` — operator .env
override lands, and the shipped default stays the secure one (true = the
Settings default; threading must not silently flip it).

Same failure mode, same fix shape as test_camera_timezone_compose.py.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[4]
COMPOSE_FILES = ("docker-compose.prod.yml",)  # the one supported stack (O1.2, UR-17)


def _backend_env(compose_file: str) -> dict[str, str]:
    compose = yaml.safe_load((REPO_ROOT / compose_file).read_text(encoding="utf-8"))
    raw = compose["services"]["backend"].get("environment", [])
    assert isinstance(raw, list), f"{compose_file} backend environment should stay list-form"
    return dict(item.split("=", 1) for item in raw)


@pytest.mark.parametrize("compose_file", COMPOSE_FILES)
def test_session_cookie_secure_reaches_the_backend_container(compose_file: str) -> None:
    env = _backend_env(compose_file)
    assert env.get("SESSION_COOKIE_SECURE") == "${SESSION_COOKIE_SECURE:-true}", (
        f"{compose_file} must pass SESSION_COOKIE_SECURE=${{SESSION_COOKIE_SECURE:-true}} "
        "to the backend: without it the documented plain-http remedy is unsettable "
        "in the shipped stack (no env_file:, .env dockerignored), and the true "
        "default must match Settings' secure default, not flip it"
    )
