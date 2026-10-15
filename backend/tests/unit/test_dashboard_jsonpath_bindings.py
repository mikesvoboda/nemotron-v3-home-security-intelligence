"""Every Grafana JSONPath leg in monitoring/ must bind a field the endpoint declares.

Ruling-188 routing (coordinator `6183912592`, citing frontend `6183836285`) filed
`consolidated.json` `"$[*].recommendation"` -> `"$[*].suggestion"` as a one-line ops
lane fix. That rename was correct but INCOMPLETE, and this test is why: the panel's
endpoint `/api/ai-audit/recommendations` returns a WRAPPER object
(`RecommendationsResponse{recommendations:[...], total_events_analyzed}`), not a bare
list, so a leg that anchors on the bare root -- `$[*].X` -- binds nothing no matter
what `X` is. Both of panel 277's legs had that shape, so `$[*].frequency` was broken
too. The cure is to re-anchor BOTH legs under the wrapper field
(`$.recommendations[*].suggestion` / `$.recommendations[*].frequency`), which is the
shape the working panels in the same files already use.

This is the offline counterpart to `backend/tests/integration/test_dashboard_queries.py`,
which validates that PromQL legs name metrics that exist (its docstring: "Typos in
metric names ... Dashboard queries that would fail in production"). That check needs a
live /metrics endpoint; this one needs only the imported schemas, so it runs in the unit
tier. Both target the same silent failure: a leg that reads something the backend never
emits renders an empty panel with no error anywhere -- Grafana just shows no data.

The checker walks the live FastAPI routers (env-free -- it imports the router modules,
never `backend.main`, which would need `DATABASE_URL`) to build {path: response_model},
then resolves each dashboard leg against the model it targets. A leg is broken when it
anchors on a key the wrapper does not declare, or anchors on the bare root against a
model that is an object (not a list).

Seven legs are still broken after this PR's one-panel fix -- panel "Quality Correlation
Leaderboard" (4 legs reading fields no endpoint emits: it is wired to the model
leaderboard but titled/desired as a per-camera correlation view, which needs product
intent, not a rename) and analytics "Risk History" (3 legs reading `$.history[*]` from
`EventStatsResponse`, which declares no `history`). They are held in the named
`KNOWN_BROKEN` registry below so the checker runs green WITH them, which (a) certifies
this PR's fix removed panel 277's two legs from the broken set and (b) fails the moment
an eighth leg breaks. The registry is a tracked follow-up, not a suppression: deleting
a fixed entry from it is how the next PR turns this green-by-name green-by-repair.
"""

from __future__ import annotations

import importlib
import json
import pkgutil
from pathlib import Path
from typing import Any

import pytest

DASHBOARDS_DIR = Path(__file__).resolve().parents[3] / "monitoring" / "grafana" / "dashboards"


def _route_models() -> dict[str, Any]:
    """Map GET path -> response_model across every route module, env-free.

    Walks `backend.api.routes.*` router attributes directly rather than importing
    `backend.main` (which requires `DATABASE_URL` at import time). All 61 route
    modules expose a `router`; a module that fails to import is a hard error here,
    not a skip -- a skipped module would make its paths read as "no route" and hide
    real breakage, which is the exact silent failure this file exists to catch.
    """
    import backend.api.routes as routes_pkg

    table: dict[str, Any] = {}
    for mod_info in pkgutil.iter_modules(routes_pkg.__path__):
        mod = importlib.import_module(f"backend.api.routes.{mod_info.name}")
        router = getattr(mod, "router", None)
        for route in getattr(router, "routes", []) or []:
            if getattr(route, "methods", None) and "GET" in route.methods:
                table[route.path] = getattr(route, "response_model", None)
    return table


def _iter_targets(dashboard: dict) -> list[tuple[str, str, dict]]:
    """(panel_title, url_path_without_query, target) for every target with fields."""
    out: list[tuple[str, str, dict]] = []

    def walk(panels: list[dict]) -> None:
        for panel in panels:
            if panel.get("type") == "row":
                walk(panel.get("panels", []) or [])
                continue
            for target in panel.get("targets", []) or []:
                url = (target.get("urlPath") or target.get("url") or "").split("?")[0]
                if url and (target.get("fields") or []):
                    out.append((panel.get("title", "?"), url, target))

    walk(dashboard.get("panels", []) or [])
    return out


def _root_anchored_field(jsonpath: str) -> str | None:
    """For a `$.field...` leg, the top-level key it reads. None for a bare-root `$[...]`.

    The distinction is the whole bug: `$.field[*].x` reads a field OF the wrapper,
    while `$[*].x` / `$.*.x` asserts the response root IS a list -- false for every
    ai-audit/analytics endpoint here, all of which return wrapper objects.
    """
    if not jsonpath.startswith("$."):
        return None  # bare `$[*]` / `$.` form -> claims the root is a list
    rest = jsonpath[2:]
    for stop in (".", "["):
        idx = rest.find(stop)
        if idx >= 0:
            rest = rest[:idx]
    return rest


def _broken_legs(table: dict[str, Any]) -> list[tuple[str, str, str, str]]:
    """Every (file, url, jsonPath, reason) that fails to bind its endpoint's model."""
    broken: list[tuple[str, str, str, str]] = []
    for path in sorted(DASHBOARDS_DIR.glob("*.json")):
        doc = json.loads(path.read_text())
        for _title, url, target in _iter_targets(doc):
            model = table.get(url)
            fields = getattr(model, "model_fields", None)
            for leg in target["fields"]:
                jp = leg.get("jsonPath")
                if not jp:
                    continue
                key = (path.name, url, jp)
                if model is None:
                    broken.append((*key, "no GET route declares this path"))
                elif fields is None:  # untyped / dict / list response: cannot verify
                    continue
                elif jp.startswith("$."):
                    anchor = _root_anchored_field(jp)
                    if anchor not in fields:
                        broken.append(
                            (
                                *key,
                                f"$.{anchor} not a field of {model.__name__} {list(fields)}",
                            )
                        )
                elif jp.startswith("$["):
                    # Bare-root leg against a Pydantic-object model: the root is an
                    # object, not a list, so a list anchor binds nothing.
                    broken.append((*key, f"bare-root list anchor vs object model {model.__name__}"))
    return broken


# Measured at this head, held by name so the checker is green-with-them and an eighth
# breakage goes red. Format: (dashboard_file, endpoint_path, jsonPath). Deleting an
# entry when its panel is repaired is required, not optional -- a stale entry means a
# leg that is now fine is being waved through.
KNOWN_BROKEN: set[tuple[str, str, str]] = {
    # consolidated "Quality Correlation Leaderboard": wired to the model leaderboard
    # endpoint but reads per-camera fields NO endpoint emits. Needs product intent
    # (a real per-camera correlation endpoint, or retitle to model fields) -- not a rename.
    ("consolidated.json", "/api/ai-audit/leaderboard", "$[*].camera"),
    ("consolidated.json", "/api/ai-audit/leaderboard", "$[*].correlation_score"),
    ("consolidated.json", "/api/ai-audit/leaderboard", "$[*].total_events"),
    ("consolidated.json", "/api/ai-audit/leaderboard", "$[*].high_quality_rate"),
    # analytics "Risk History": reads $.history[*] but EventStatsResponse declares
    # no `history`. Different file/endpoint; out of scope for the routed panel-277 fix.
    ("analytics.json", "/api/events/stats", "$.history[*].timestamp"),
    ("analytics.json", "/api/events/stats", "$.history[*].average_risk"),
    ("analytics.json", "/api/events/stats", "$.history[*].max_risk"),
}

RECOMMENDATIONS_URL = "/api/ai-audit/recommendations"
# The exact legs this PR repairs, asserted by name (ids repeat across panels in the
# same dashboard, so the key is (file, url, jsonPath), never the panel id).
FIXED_LEGS: set[str] = {
    "$.recommendations[*].suggestion",
    "$.recommendations[*].frequency",
}


def _recommendation_legs() -> list[str]:
    doc = json.loads((DASHBOARDS_DIR / "consolidated.json").read_text())
    legs: list[str] = []
    for _title, url, target in _iter_targets(doc):
        if url == RECOMMENDATIONS_URL:
            legs += [leg["jsonPath"] for leg in target["fields"] if leg.get("jsonPath")]
    return legs


class TestRecommendationPanelRepaired:
    """The routed one-liner's actual cure: BOTH panel-277 legs re-anchored."""

    def test_recommendations_panel_legs_are_the_two_repaired_paths(self) -> None:
        # exact, not "contains": an un-repaired `$[*].recommendation` or a leg added
        # by guesswork both fail here. This is the regression pin for the fix.
        assert set(_recommendation_legs()) == FIXED_LEGS
        assert "$[*].recommendation" not in _recommendation_legs()
        assert "$[*].frequency" not in _recommendation_legs()

    def test_repaired_legs_bind_the_endpoint_wrapper_and_item(self) -> None:
        from backend.api.schemas.ai_audit import RecommendationItem, RecommendationsResponse

        top = list(RecommendationsResponse.model_fields)
        item = set(RecommendationItem.model_fields)
        assert "recommendations" in top  # the anchor both legs now share
        # suggestion replaces the mis-named `recommendation`; frequency is an item field.
        assert "suggestion" in item
        assert "frequency" in item
        assert "recommendation" not in item  # the name the panel wrongly read


class TestNoUntrackedBrokenLeg:
    """The checker runs green WITH the seven named failures, and only those."""

    def test_broken_legs_are_exactly_the_known_broken_registry(self) -> None:
        broken = {(f, u, j) for (f, u, j, _reason) in _broken_legs(_route_models())}
        # Set equality is the ratchet: a NEW broken leg (not in KNOWN_BROKEN) fails,
        # AND a leg repaired-but-not-de-registered fails (so the registry can't rot).
        assert broken == KNOWN_BROKEN, (
            f"newly broken legs: {sorted(broken - KNOWN_BROKEN)}; "
            f"repaired-but-still-registered (remove from KNOWN_BROKEN): "
            f"{sorted(KNOWN_BROKEN - broken)}"
        )

    def test_the_checker_itself_is_not_vacuous(self) -> None:
        # A broken-leg detector that detects nothing is the grep-that-can't-match trap.
        # Prove it FINDS a leg known to be broken and PASSES one known to be fine.
        table = _route_models()
        broken_keys = {(f, u, j) for (f, u, j, _r) in _broken_legs(table)}
        assert ("consolidated.json", "/api/ai-audit/leaderboard", "$[*].camera") in broken_keys
        # 277 is repaired here -> must NOT be in the broken set anymore.
        assert not any(
            k[0] == "consolidated.json" and k[1] == RECOMMENDATIONS_URL for k in broken_keys
        )
        # a control known-good leg resolves.
        assert (
            "consolidated.json",
            "/api/ai-audit/stats",
            "$.avg_consistency_rate",
        ) not in broken_keys

    def test_route_table_walks_all_routers_without_skipping(self) -> None:
        # If a module silently failed to import, its paths would read "no route" and
        # mask breakage. Assert the walk covers the two endpoints we depend on.
        table = _route_models()
        assert RECOMMENDATIONS_URL in table
        assert "/api/ai-audit/leaderboard" in table
        assert "/api/ai-audit/stats" in table


def test_dashboards_dir_present() -> None:
    # A missing dir makes every loop above vacuously pass -- the empty-baseline trap.
    assert DASHBOARDS_DIR.is_dir(), f"{DASHBOARDS_DIR} not found"
    assert len(list(DASHBOARDS_DIR.glob("*.json"))) >= 5


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
