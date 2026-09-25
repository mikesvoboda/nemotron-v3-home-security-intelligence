"""TDD battery: scripts/fetch-ci-artifacts.py stale-runs-list hardening.

Root cause (MEASURED, PR run 35866358876 @ ffe92812, audit job 107212436979):
select_run() issues exactly ONE runs-list request (?branch=main&status=success)
with no created-date filter; GitHub served a stale page whose 8 candidates were
ALL 'created 260d ago', the client-side MAX_CANDIDATE_AGE_DAYS filter dropped
every one, select_run_with_retries re-read the IDENTICAL URL 3x, and the
baseline came up empty -> audit-test-durations.py fail-closed -> every breach
red. Fresh main runs with artifacts existed; they simply never appeared on the
served page. Fix: add a server-side created>= filter (now - FRESH_QUERY_DAYS)
to the runs-list query so an all-stale page is structurally impossible.
"""

from __future__ import annotations

import datetime
import importlib.util
import re
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

REPO_ROOT = Path(__file__).resolve().parents[4]
_hy = importlib.util.spec_from_file_location(
    "fetch_ci_artifacts", REPO_ROOT / "scripts" / "fetch-ci-artifacts.py"
)
fca = importlib.util.module_from_spec(_hy)
_hy.loader.exec_module(fca)

WF = ".github/workflows/ci.yml"


def _run(rid: int, created_iso: str) -> dict:
    return {"id": rid, "created_at": created_iso}


def _fresh(days_ago: float = 1.0) -> str:
    return (datetime.datetime.now(datetime.UTC) - datetime.timedelta(days=days_ago)).isoformat()


def _stale(days_ago: float = 260.0) -> str:
    return (datetime.datetime.now(datetime.UTC) - datetime.timedelta(days=days_ago)).isoformat()


def _is_stale(run: dict) -> bool:
    age = fca._run_age_days(run.get("created_at", ""))
    return age is not None and age > fca.MAX_CANDIDATE_AGE_DAYS


class FakeApi:
    """Canned GitHub API honoring the created>= qualifier exactly the way the
    real /actions/workflows/{id}/runs endpoint documents it: when present, only
    runs created at/after the bound are returned."""

    def __init__(self, runs: list[dict], *, stale_without_filter: bool = False):
        self.runs = runs
        self.stale_without_filter = stale_without_filter
        self.urls: list[str] = []

    def __call__(self, url: str, token: str):
        self.urls.append(url)
        if "/actions/workflows?" in url:
            return {"workflows": [{"path": WF, "id": 77}]}
        m = re.search(r"created(?:=%3E|%3E%3D|>=)(\d{4}-\d{2}-\d{2})", url)
        runs = self.runs
        if m:
            bound = datetime.datetime.fromisoformat(m.group(1)).replace(tzinfo=datetime.UTC)
            assert bound < datetime.datetime.now(datetime.UTC), (
                "created>= bound must be in the past"
            )
            runs = [r for r in runs if r["created_at"][:10] >= m.group(1)]
        elif self.stale_without_filter:
            # the measured CI failure shape: the unfiltered page GitHub
            # served contained ONLY 260-day-old runs, fresh ones absent.
            runs = [r for r in runs if _is_stale(r)]
        if "/workflows/77/runs" in url:
            return {"workflow_runs": runs}
        if "/artifacts" in url:
            rid = int(re.search(r"/runs/(\d+)/artifacts", url).group(1))
            if rid in {r["id"] for r in self.runs}:
                return {
                    "artifacts": [
                        {"name": "test-results-unit-shard-1", "expired": False, "id": rid * 10}
                    ]
                }
            return {"artifacts": []}
        raise AssertionError(f"unexpected url {url}")


def _select(api: FakeApi, monkeypatch):
    monkeypatch.setattr(fca, "_get_json", api)
    return fca.select_run(
        "http://fake",
        "o/r",
        "tok",
        WF,
        current_run_id=999,
        artifact_re=re.compile(r"^test-results-unit-shard-"),
        max_runs=10,
    )


def test_runs_list_query_carries_created_filter(monkeypatch):
    api = FakeApi([_run(1, _fresh())])
    picked = _select(api, monkeypatch)
    assert [rid for rid, _ in picked] == [1]
    runs_urls = [u for u in api.urls if "/workflows/77/runs" in u]
    assert runs_urls, "no runs-list request was issued"
    for u in runs_urls:
        # server-side age filter: created=> (GitHub's documented qualifier,
        # measured 2026-09-24: created=%3E<date> FILTERS, created%3E=<date>
        # is silently IGNORED and returns the whole unfiltered page)
        assert re.search(r"created(=%3E|%3E%3D|>=)\d{4}-\d{2}-\d{2}", u), (
            f"runs-list query lacks the created>= stale-page filter: {u}"
        )


def test_stale_page_cannot_defeat_selection(monkeypatch):
    # The measured CI failure shape: the page GitHub served carried ONLY
    # 260-day-old runs (fresh run 7 was simply absent from the served page).
    # Without the created>= filter the client keeps reading that same page and
    # dies with HarvestError (that IS the measured failure). With the filter
    # the server honours created>= and run 7 comes back.
    api = FakeApi(
        [_run(7, _fresh()), _run(1, _stale()), _run(2, _stale())], stale_without_filter=True
    )
    picked = _select(api, monkeypatch)
    assert [rid for rid, _ in picked] == [7]


def test_no_recent_runs_still_raises_honestly(monkeypatch):
    api = FakeApi([_run(1, _stale()), _run(2, _stale())])
    with pytest.raises(fca.HarvestError):
        _select(api, monkeypatch)
