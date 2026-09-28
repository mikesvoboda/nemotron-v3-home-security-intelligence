"""Compose wiring for CAMERA_TIMEZONE (synthbench P0, final-review I1).

Settings reads ``camera_timezone`` to turn Foscam filename times into capture
moments, and ``.env.example`` tells operators to set it in ``.env``. But the
backend service declares no ``env_file:`` and ``.env`` is dockerignored, so
inside the container Settings only sees what the ``environment:`` list
passes. An unthreaded variable is silently ignored: the operator sets it,
the container keeps the unset path, and nothing reports it.

These tests pin that both shipped compose files thread it, with an empty
default so an unset host variable still means "unset" (the validator turns
``""`` into ``None``, keeping today's behavior).
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[4]
COMPOSE_FILES = ("docker-compose.prod.yml", "docker-compose.ghcr.yml")


def _backend_env(compose_file: str) -> dict[str, str]:
    compose = yaml.safe_load((REPO_ROOT / compose_file).read_text(encoding="utf-8"))
    raw = compose["services"]["backend"].get("environment", [])
    assert isinstance(raw, list), f"{compose_file} backend environment should stay list-form"
    return dict(item.split("=", 1) for item in raw)


@pytest.mark.parametrize("compose_file", COMPOSE_FILES)
def test_camera_timezone_reaches_the_backend_container(compose_file: str) -> None:
    env = _backend_env(compose_file)
    assert env.get("CAMERA_TIMEZONE") == "${CAMERA_TIMEZONE:-}", (
        f"{compose_file} must pass CAMERA_TIMEZONE=${{CAMERA_TIMEZONE:-}} to the "
        "backend: without it a .env setting never reaches Settings in the container"
    )
