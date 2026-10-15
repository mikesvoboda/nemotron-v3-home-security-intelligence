"""Ruling 168 item 3: `system.py` reads the fast-path threshold without clamping it.

Before ruling 168 the only way to express "fast path off" was an out-of-band
threshold: ``fast_path_confidence_threshold`` defaulted to ``2.0`` and
``GET /api/system/config`` / ``PATCH /api/system/config`` clamped it to ``1.0``
on the way out so the response schema (``le=1.0``) would accept it. Ruling 168
moved the disabled state into the explicit ``fast_path_enabled`` flag and folded
the legacy sentinel back into the band in one place, ``config.py``'s
``_clamp_legacy_fast_path_sentinel`` validator. With every value the settings
object can hold already inside 0.0-1.0, the two route clamps are dead code — and
dead code that rewrites a config value on read is what produced F-187's 500, so
they come out rather than sit.

These tests pin the *shape* the clamps were, because the removal is otherwise
invisible to a mocked-Settings test: a mock holding 0.9 returns 0.9 clamped or
unclamped, so a round-trip assertion passes either way. The AST leg fails on the
clamped source and passes on the passthrough; the behavioural legs pin what the
frontend depends on staying true.
"""

from __future__ import annotations

import ast
import inspect
from unittest.mock import AsyncMock, MagicMock, create_autospec, patch

import pytest
from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import Response

from backend.api.routes import system as system_routes
from backend.api.schemas.system import ConfigResponse, ConfigUpdateRequest
from backend.core.config import Settings

DATABASE_URL = "postgresql+asyncpg://test:test@localhost:5432/test"  # pragma: allowlist secret


def _return_field_expression(func: object, field: str) -> ast.expr:
    """Return the expression a route passes to `field` in its ConfigResponse(...).

    Args:
        func: The route function to inspect.
        field: Keyword argument name inside the ``ConfigResponse(...)`` call.

    Returns:
        The AST node for that keyword's value.

    Raises:
        AssertionError: If the function has no ``ConfigResponse(...)`` call, or
            that call does not pass `field` at all.
    """
    tree = ast.parse(inspect.getsource(func))
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "ConfigResponse"
        ):
            for keyword in node.keywords:
                if keyword.arg == field:
                    return keyword.value
    raise AssertionError(f"{func.__name__} never passes {field!r} to ConfigResponse")


def _reads_the_settings_field(node: ast.expr, field: str) -> bool:
    """True when `node` mentions ``settings.<field>`` anywhere inside it.

    Args:
        node: The AST expression to search.
        field: Attribute name, e.g. ``fast_path_confidence_threshold``.

    Returns:
        Whether any ``Attribute`` node named `field` appears under `node`.
    """
    return any(isinstance(child, ast.Attribute) and child.attr == field for child in ast.walk(node))


class TestNoReadClamp:
    """Both config routes hand the stored threshold straight to the response."""

    @pytest.mark.parametrize("route", ["get_config", "patch_config"])
    def test_threshold_is_a_bare_attribute_read(self, route: str) -> None:
        """The response field is ``settings.fast_path_confidence_threshold``, unchanged.

        Ruling 168 item 3 removes both clamps. A ``min(...)`` or a conditional
        around the read is the clamp coming back; a bare attribute read is the
        passthrough. This is the leg that is red on the clamped source.
        """
        expr = _return_field_expression(
            getattr(system_routes, route), "fast_path_confidence_threshold"
        )

        assert isinstance(expr, ast.Attribute), (
            f"{route} wraps fast_path_confidence_threshold in {type(expr).__name__}; ruling 168 "
            "item 3 asks for a plain read of the stored value, the clamp having become dead code "
            "once config.py folds the legacy sentinel into the band."
        )
        assert expr.attr == "fast_path_confidence_threshold"

    @pytest.mark.parametrize("route", ["get_config", "patch_config"])
    def test_no_min_call_touches_the_threshold(self, route: str) -> None:
        """No ``min(...)`` rewrites the threshold in either route.

        Paired with the leg above so a refactor that hides the clamp behind a
        helper call (which would still be a rewrite on read) is caught by the
        name rather than by the node type.
        """
        func = getattr(system_routes, route)
        tree = ast.parse(inspect.getsource(func))
        offenders = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "min"
            and _reads_the_settings_field(node, "fast_path_confidence_threshold")
        ]
        assert not offenders, (
            f"{route} still clamps the threshold with min() at line(s) "
            f"{[o.lineno for o in offenders]}."
        )


def _mock_settings(threshold: float = 0.9) -> object:
    """A stand-in Settings with every field ``ConfigResponse`` needs.

    Args:
        threshold: Value for ``fast_path_confidence_threshold``.

    Returns:
        An autospec'd Settings mock.
    """
    settings = create_autospec(Settings, instance=True)
    settings.app_name = "Home Security Intelligence"
    settings.app_version = "1.0.0"
    settings.retention_days = 30
    settings.log_retention_days = 7
    settings.batch_window_seconds = 90
    settings.batch_idle_timeout_seconds = 30
    settings.detection_confidence_threshold = 0.5
    settings.fast_path_confidence_threshold = threshold
    settings.fast_path_enabled = False
    settings.grafana_url = "http://localhost:3002"
    settings.debug = False
    return settings


class TestReadReturnsStoredValue:
    """The band is enforced where the value is set, so the read is a passthrough."""

    @pytest.mark.asyncio
    async def test_get_config_returns_the_top_of_the_band_unchanged(self) -> None:
        """A stored 1.0 reaches the client as 1.0.

        1.0 is the value ``config.py``'s validator folds a legacy 2.0 sentinel
        into, so this is the exact value the old clamp existed to manufacture.
        Now that the fold happens at parse time, the route must hand back the
        same number it read rather than recomputing it — and the response schema
        still bounds it, so nothing downstream loosens.
        """
        settings = _mock_settings(threshold=1.0)
        get_settings = create_autospec(system_routes.get_settings, return_value=settings)
        with patch.object(system_routes, "get_settings", get_settings):
            response = await system_routes.get_config(response=Response())

        assert isinstance(response, ConfigResponse)
        assert response.fast_path_confidence_threshold == 1.0

    @pytest.mark.asyncio
    async def test_get_config_does_not_round_an_in_band_value(self) -> None:
        """An ordinary 0.75 comes back as 0.75 (the clamp's no-op case stays green).

        Paired with the 1.0 leg: a route that returned 1.0 unconditionally would
        pass the leg above and fail this one.
        """
        settings = _mock_settings(threshold=0.75)
        get_settings = create_autospec(system_routes.get_settings, return_value=settings)
        with patch.object(system_routes, "get_settings", get_settings):
            response = await system_routes.get_config(response=Response())

        assert response.fast_path_confidence_threshold == 0.75

    @pytest.mark.asyncio
    async def test_patch_config_echoes_the_stored_threshold_unchanged(
        self, tmp_path, monkeypatch
    ) -> None:
        """The save response reports the threshold the settings object holds.

        The patch response carried the same clamp; it is removed with the read
        one. The request here changes only the enable flag, so the stored
        threshold is the one the response must echo back. It is deliberately
        0.75 and not 1.0: a response hardcoded to the band's top (the value the
        old clamp manufactured) passes a 1.0 round-trip and fails this one.
        """
        monkeypatch.setenv("HSI_RUNTIME_ENV_PATH", str(tmp_path / "runtime.env"))
        settings = _mock_settings(threshold=0.75)
        get_settings = create_autospec(system_routes.get_settings, return_value=settings)
        get_settings.cache_clear = MagicMock()

        with (
            patch.object(system_routes, "get_settings", get_settings),
            patch.object(system_routes, "AuditService", autospec=True) as mock_audit,
        ):
            mock_audit.log_action = AsyncMock()
            response = await system_routes.patch_config(
                request=MagicMock(spec=Request),
                response=Response(),
                update=ConfigUpdateRequest(fast_path_enabled=False),
                db=AsyncMock(spec=AsyncSession),
            )

        assert response.fast_path_confidence_threshold == 0.75


class TestFoldStillLivesInConfig:
    """Removing the read clamps moved nothing: config.py still owns the band."""

    def test_config_still_folds_a_legacy_sentinel(self, monkeypatch) -> None:
        """A runtime.env holding the retired 2.0 still boots, folded to 1.0.

        This is the guard that makes the route clamps redundant: no Settings
        instance can carry a threshold above 1.0, so a route cannot 500 on its
        own response schema. Pre-existing behaviour, asserted here because this
        PR's whole argument rests on it.
        """
        for var in (
            "FAST_PATH_ENABLED",
            "FAST_PATH_CONFIDENCE_THRESHOLD",
            "FAST_PATH_OBJECT_TYPES",
        ):
            monkeypatch.delenv(var, raising=False)
        monkeypatch.setenv("DATABASE_URL", DATABASE_URL)
        monkeypatch.setenv("ENVIRONMENT", "development")
        monkeypatch.setenv("FAST_PATH_CONFIDENCE_THRESHOLD", "2.0")

        assert Settings().fast_path_confidence_threshold == 1.0
