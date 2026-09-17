"""R-T9-MVSOURCE retirement lock — the phantom MV admin surface is GONE.

RED-FIRST for the retire decision (owner ruling pre-authorized the
sub-choice; DECIDE-on-evidence rationale in the ledger row):
the six materialized views + five SQL functions have NO shipped DDL on any
schema path (create_all cannot emit them; alembic was deleted f1e0ea9e and
is test-extra-only now), every aggregate getter had zero callers across all
git history, and the dashboard already computes the same aggregates inline
(analytics.py). What shipped was an admin router that degrades silently —
plus four admin endpoints with no auth dependency, against the repo's
admin-protection rule.

This file locks the END STATE from two angles:
1. API surface: app.openapi() must not expose /api/admin/materialized-views*.
2. Import surface: the five retired modules must raise ModuleNotFoundError.

If someone restores the feature properly (real DDL + auth deps + callers),
rewrite this lock to assert the shipped contract — do not delete it.
"""

from __future__ import annotations

import importlib

import pytest

from backend.main import app

RETIRED_MODULES = [
    "backend.services.materialized_views",
    "backend.services.materialized_view_scheduler",
    "backend.api.routes.materialized_views",
    "backend.api.schemas.materialized_views",
    "backend.services.enrichment_queries",
]


@pytest.mark.timeout(60)
def test_openapi_has_no_materialized_view_paths():
    """The admin MV routes must be absent from the live app's schema."""
    paths = app.openapi()["paths"]
    mv_paths = [p for p in paths if "materialized-views" in p]
    assert not mv_paths, f"retired MV routes still mounted: {mv_paths}"


@pytest.mark.timeout(60)
@pytest.mark.parametrize("module", RETIRED_MODULES)
def test_retired_module_is_unimportable(module: str):
    """The phantom service layer is deleted, not dead-but-present."""
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module(module)
