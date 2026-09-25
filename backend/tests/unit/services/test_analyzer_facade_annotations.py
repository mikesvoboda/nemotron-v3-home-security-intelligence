"""Runtime-resolvability of AnalyzerServiceFacade annotations (CI 3.14.2 pin).

PR #6679 CI red: unittest.mock.create_autospec of
AnalyzerServiceFacade.get_cache_service raised
``NameError: name 'CacheService' is not defined`` on Python 3.14.2.

Root cause: the module carries no ``from __future__ import annotations``,
so under PEP 649 (3.14) each method gets a lazy ``__annotate__`` that
evaluates its annotations against MODULE GLOBALS at runtime -- but
``CacheService`` (and friends) are imported only under
``if TYPE_CHECKING:``. Any runtime consumer that evaluates annotations
(inspect.signature, mock.create_autospec, pydantic-style validators)
explodes. The regression was invisible locally because mock on 3.14.4
falls back to ForwardRef while 3.14.2 evaluates eagerly -- CI's patch
level is the one that bites.

These tests pin the class invariant: every public method signature must
resolve with the TYPE_CHECKING imports genuinely absent from module
globals (the CI import graph).
"""

from __future__ import annotations

import inspect

import pytest

import backend.services.analyzer_facade as facade_mod
from backend.services.analyzer_facade import AnalyzerServiceFacade


def _public_methods() -> list[str]:
    return [
        name
        for name, obj in inspect.getmembers(AnalyzerServiceFacade, callable)
        if not name.startswith("_")
    ]


@pytest.mark.parametrize("method_name", _public_methods())
def test_method_signature_resolves_without_type_checking_names(method_name: str):
    """inspect.signature() must not raise, evaluated against module globals.

    The premise this proves: the annotated types are TYPE_CHECKING-only,
    so a bare name in the annotation is a NameError the moment anything
    (signature, autospec) evaluates it. If a future edit makes the
    imports real, the test stops being a repro -- never a failure mode.
    """
    method = getattr(AnalyzerServiceFacade, method_name)
    assert inspect.signature(method) is not None


def test_type_checking_names_are_not_module_globals():
    """Premise pin: the annotated types are genuinely TYPE_CHECKING-only.

    If someone promotes these to real runtime imports, this fires and the
    annotation-quoting pin above can be retired deliberately.
    """
    missing = [
        name
        for name in ("CacheService", "ContextEnricher", "EnrichmentPipeline")
        if name not in vars(facade_mod)
    ]
    assert missing == ["CacheService", "ContextEnricher", "EnrichmentPipeline"]


def test_get_cache_service_return_annotation_resolves():
    """Direct repro of the CI NameError traceback path."""
    method = AnalyzerServiceFacade.get_cache_service
    # Under PEP 649 this triggers __annotate__ against module globals;
    # pre-fix it raised NameError: name 'CacheService' is not defined.
    evaluated = method.__annotations__
    assert "return" in evaluated


def test_create_autospec_of_get_cache_service_survives():
    """The exact CI call shape: patch(..., autospec=True) on the method."""
    from unittest.mock import patch

    with patch(
        "backend.services.analyzer_facade.AnalyzerServiceFacade.get_cache_service",
        autospec=True,
        side_effect=RuntimeError("cache disabled in harness"),
    ) as spy:
        assert spy is not None
