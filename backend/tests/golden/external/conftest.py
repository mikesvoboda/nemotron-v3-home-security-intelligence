"""Fixtures for the BE-1 golden paths (F2.3 batch, ruling 87).

Golden paths run against a live test deployment brought up by
``scripts/feature-check.sh`` (O2.2, #6961). The harness exports its contract as
``FEATURE_CHECK_*`` variables and invokes this directory as
``pytest backend/tests/golden`` (``scripts/feature_check.py`` ``golden()``), so
these fixtures read that contract and nothing else — no ``.env``, no assumed
ports, no localhost defaults.

Two rules shape this file, both from the split post on
#6854 (ruling 87/86):

* **Collection must never crash.** The harness's ``--list`` analogue (pytest
  collection, which CI and every lane run) must succeed on a machine with no
  harness env. So every env read is lazy — inside a fixture, never at import —
  and a partial env produces ``skip``, not an error.
* **These paths are unmocked.** They drive the real HTTP surface of the stack.
  Nothing here patches a backend function; a spec that could not pass against
  the real deployment gets demoted to ``half-built`` with its failure cited
  (ruling 86), not patched to pass.
"""

from __future__ import annotations

import json
import os
from collections.abc import Iterator
from typing import Any

import httpx
import pytest

# The harness exports exactly these (feature_check.py Run.env, read at F2.1).
_REQUIRED_ENV = (
    "FEATURE_CHECK_API_URL",
    "FEATURE_CHECK_ADMIN_USERNAME",
    "FEATURE_CHECK_ADMIN_PASSWORD",
)


def _missing_env() -> list[str]:
    """Which required harness variables are absent or empty right now."""
    return [name for name in _REQUIRED_ENV if not os.environ.get(name)]


@pytest.fixture(scope="session")
def harness_mode() -> str:
    """``fake`` or ``real`` — the mode the run was started in."""
    return os.environ.get("FEATURE_CHECK_MODE", "fake")


@pytest.fixture(scope="session")
def api_url() -> str:
    """The backend's entry point for this run, as the harness publishes it.

    Self-skips rather than raising when the harness env is absent, so
    ``pytest --collect-only`` stays green on a machine without a stack.
    """
    missing = _missing_env()
    if missing:
        pytest.skip(f"feature-check harness env absent: {', '.join(missing)}")
    return os.environ["FEATURE_CHECK_API_URL"].rstrip("/")


@pytest.fixture(scope="session")
def admin_credentials() -> dict[str, str]:
    """The first admin the harness registered."""
    missing = _missing_env()
    if missing:
        pytest.skip(f"feature-check harness env absent: {', '.join(missing)}")
    return {
        "username": os.environ["FEATURE_CHECK_ADMIN_USERNAME"],
        "password": os.environ["FEATURE_CHECK_ADMIN_PASSWORD"],
    }


@pytest.fixture(scope="session")
def cameras_by_scenario() -> dict[str, str]:
    """scenario name -> backend camera id, from the harness's ``cameras.json``.

    An empty mapping (rather than a skip) when the file is absent: a spec that
    needs a camera checks for its scenario and skips itself, which keeps a spec
    that needs no camera runnable.
    """
    path = os.environ.get("FEATURE_CHECK_CAMERAS", "")
    if not path or not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as handle:
        loaded: Any = json.load(handle)
    if not isinstance(loaded, dict):
        return {}
    return {str(k): str(v) for k, v in loaded.items()}


@pytest.fixture(scope="session")
def api(api_url: str) -> Iterator[httpx.Client]:
    """An unauthenticated client against the run's backend.

    Session-scoped on purpose: the golden specs are read-only against one stack,
    and a module-scoped scrape fixture may only depend on session (or module)
    scope — a function-scoped client would raise ``ScopeMismatch`` at collection,
    which under ``--strict-markers``-style hygiene is worse than a slow test.
    Under ``--dist=worksteal`` this is per worker, which is still correct.

    The CI stack runs with ``EXPOSE_LAN`` unset, so the auth middleware is a
    pass-through (``backend/api/middleware/auth.py`` ``AuthMiddleware.__call__``
    returns early when ``get_settings().expose_lan`` is false) — verified live,
    not assumed: an unauthenticated ``GET /api/events`` answers 200 on a
    feature-check stack. A spec that needs a principal uses
    :func:`logged_in_api`.
    """
    with httpx.Client(base_url=api_url, timeout=30.0) as client:
        yield client


@pytest.fixture
def logged_in_api(api_url: str, admin_credentials: dict[str, str]) -> Iterator[httpx.Client]:
    """A client carrying the session cookie ``POST /api/auth/login`` sets.

    Login is in ``OPEN_PATHS`` so it answers without a credential in either
    mode; the cookie then authenticates the write/read paths the job rows use.
    """
    with httpx.Client(base_url=api_url, timeout=30.0) as client:
        response = client.post("/api/auth/login", json=admin_credentials)
        if response.status_code != 200:
            pytest.skip(
                f"login answered {response.status_code}, not 200: "
                "the run's first admin is not available to this spec"
            )
        yield client
