"""Run this tier against a RUNNING fake (O2.1).

Every hop in this tier reaches the fake through ``create_fake_app()``, directly
or through ``fake_provider_ops()``, which builds it. With ``FAKE_AI_URL`` set to
the base URL of a running fake (``docker-compose.fake-ai.yml``), the
argument-less factory returns ``remote_app(FAKE_AI_URL)`` instead, so the same
assertions run against the container:

    FAKE_AI_URL=http://127.0.0.1:8090 uv run pytest backend/tests/contracts/ai_providers/

Calls WITH arguments (a custom build, a custom scenario book) configure an app
the container cannot be, so they stay in-process. The run fails if no request
reached the container: a seam that silently stopped applying would otherwise
pass the whole tier in-process and claim the container conformed.

Unset (the default, and CI), this file changes nothing.
"""

from __future__ import annotations

import os
from typing import Any

import pytest

FAKE_AI_URL_ENV = "FAKE_AI_URL"
_URL = os.environ.get(FAKE_AI_URL_ENV, "").strip()
_FORWARDED: list[tuple[str, str]] = []


def _install_remote_factory(url: str) -> None:
    """Swap the factory BEFORE the tier's modules import it (pytest imports a
    directory's conftest first), so their ``from ... import create_fake_app``
    binds the remote one."""
    import backend.ai_contract.fake as fake_pkg
    import backend.ai_contract.fake.app as fake_app
    from backend.ai_contract.fake.remote import remote_app

    in_process = fake_app.create_fake_app

    def create_fake_app(*args: Any, **kwargs: Any) -> Any:
        if args or kwargs:
            return in_process(*args, **kwargs)
        return remote_app(url, on_request=lambda method, path: _FORWARDED.append((method, path)))

    fake_app.create_fake_app = create_fake_app  # type: ignore[assignment]
    fake_pkg.create_fake_app = create_fake_app  # type: ignore[assignment]
    fake_app._get_shared_app.cache_clear()


if _URL:
    _install_remote_factory(_URL)


def pytest_report_header() -> str | None:
    if _URL:
        return f"fake AI: {FAKE_AI_URL_ENV}={_URL} (this tier drives the running container)"
    return None


@pytest.hookimpl(optionalhook=True)
def pytest_testnodedown(node: Any) -> None:
    """Under xdist each worker counts its own forwards; the controller sums them."""
    _FORWARDED.extend(("worker", "forward") for _ in range(node.workeroutput.get("fake_ai", 0)))


def pytest_sessionfinish(session: pytest.Session) -> None:
    if not _URL:
        return
    workeroutput = getattr(session.config, "workeroutput", None)
    if workeroutput is not None:  # an xdist worker: report, let the controller judge
        workeroutput["fake_ai"] = len(_FORWARDED)
        return
    if not _FORWARDED:
        session.exitstatus = pytest.ExitCode.TESTS_FAILED
        reporter = session.config.pluginmanager.get_plugin("terminalreporter")
        if reporter is not None:
            reporter.write_line(
                f"{FAKE_AI_URL_ENV} is set but no request reached {_URL}: the tier ran "
                "in-process only",
                red=True,
            )


def pytest_terminal_summary(terminalreporter: Any) -> None:
    if _URL:
        terminalreporter.write_line(f"fake AI: {len(_FORWARDED)} requests forwarded to {_URL}")
