#!/usr/bin/env python3
"""Tests for the WP1.5 flaky-tracking CONSUMER (cap 1h work package).

Run explicitly; outside testpaths:

    uv run python -m pytest scripts/test_flake_consumer.py -q

WP1.5's defect: the per-shard flaky-test-tracking-*.jsonl artifacts are
uploaded on every CI run and NOTHING READS THEM — `flake_allowlist: 0` was
evidence of no consumer, not of no flakes. The done-when: something reads
them and produces (a) a ranked flake list and (b) a named-owner list.

Pins three seams:
  1. analyze-flaky-tests.py --owner-summary writes the ranked table with an
     explicit OWNER column: registered -> allowlist tracking ref; unregistered
     -> the literal "no owner" (an unowned flake must be VISIBLE as unowned).
  2. fetch-ci-artifacts.py --self-test runs the whole real selection +
     download + extract flow against a canned local GitHub API: newest main
     CI run WITH matching artifacts wins, the current run id is never a
     source, runs without matching artifacts are skipped, and a dead API
     exits non-zero (a CI bug cannot masquerade as "no flakes").
  3. ci.yml carries a flake-report job wired into ci-gate's reach (or
     Linear-triaged), invoking BOTH scripts — the consumer must be the
     scheduled reader of the per-run artifacts, not a nightly re-runner of
     its own tests.
"""

from __future__ import annotations

import http.server
import json
import subprocess
import threading
import zipfile
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
ANALYZER = REPO_ROOT / "scripts" / "analyze-flaky-tests.py"
HARVESTER = REPO_ROOT / "scripts" / "fetch-ci-artifacts.py"
CI = REPO_ROOT / ".github" / "workflows" / "ci.yml"


def jsonl_line(ts: str, outcomes: dict[str, list[str]]) -> str:
    """One conftest.py session-summary line: nodeid -> outcomes list."""
    tests = {}
    for nodeid, oc in outcomes.items():
        passed = sum(1 for o in oc if o == "passed")
        failed = sum(1 for o in oc if o == "failed")
        tests[nodeid] = {
            "outcomes": [{"outcome": o, "rerun": False, "duration": 0.1} for o in oc],
            "total_runs": len(oc),
            "passed": passed,
            "failed": failed,
            "reruns": 0,
            "pass_rate": passed / len(oc),
            "flaky_marked": False,
        }
    return json.dumps({"timestamp": ts, "exit_status": 0, "tests": tests}) + "\n"


@pytest.fixture
def corpus(tmp_path: Path) -> Path:
    """Artifact-layout corpus: download-artifact v4 nests <artifact-dir>/<file>."""
    a = tmp_path / "corpus" / "run-a"
    a.mkdir(parents=True)
    # flaky.test_x: passes everywhere EXCEPT one failure -> persisting flake,
    # unregistered. flaky.test_reg: also flaky but registered in the
    # synthetic allowlist below. stable.test_ok: never fails.
    (a / "flaky-test-tracking-unit-shard-1.jsonl").write_text(
        jsonl_line(
            "2026-09-19T02:00:00+00:00",
            {
                "backend/tests/unit/test_foo.py::test_x": ["passed", "passed"],
                "backend/tests/unit/test_foo.py::test_reg": ["passed"],
                "backend/tests/unit/test_foo.py::test_ok": ["passed", "passed"],
            },
        )
    )
    (a / "flaky-test-tracking-unit-shard-2.jsonl").write_text(
        jsonl_line(
            "2026-09-19T02:00:00+00:00",
            {
                "backend/tests/unit/test_foo.py::test_x": ["failed"],
                "backend/tests/unit/test_foo.py::test_reg": ["failed"],
                "backend/tests/unit/test_foo.py::test_ok": ["passed"],
            },
        )
    )
    b = tmp_path / "corpus" / "run-b"
    b.mkdir()
    (b / "flaky-test-tracking-unit-shard-1.jsonl").write_text(
        jsonl_line(
            "2026-09-19T03:00:00+00:00",
            {
                "backend/tests/unit/test_foo.py::test_x": ["passed", "failed"],
                "backend/tests/unit/test_foo.py::test_reg": ["passed", "passed"],
                "backend/tests/unit/test_foo.py::test_ok": ["passed", "passed", "passed"],
            },
        )
    )
    # MEASURED SHAPE (WP1.5 live harvest): the artifact regex also drags in
    # playwright's e2e-results.json — a pretty-printed multi-line JSON whose
    # every line fails line-wise json.loads, and whose scalars reach .get()
    # as non-dict records. The consumer faces the REAL artifact tree, so the
    # analyzer must shrug this off, not crash on it (it did: AttributeError
    # 'str' object has no attribute 'get' against the first live corpus).
    (b / "e2e-results.json").write_text(
        '{\n  "suites": [\n    "junk",\n    123\n  ]\n}\n"a string line"\n'
    )
    allow = tmp_path / "allowlist.yml"
    allow.write_text(
        "flakes:\n"
        "  - id: test_reg\n"
        "    tracking: NEM-9001\n"
        "    owner: mikesvoboda\n"
        "    expires: 2099-01-01\n"
    )
    return tmp_path


def run_analyzer(corpus_root: Path, summary: Path) -> subprocess.CompletedProcess:
    env_summary = str(summary)
    import os

    e = dict(os.environ, GITHUB_STEP_SUMMARY=env_summary, MIN_RUNS="2")
    return subprocess.run(
        [
            "python3",
            str(ANALYZER),
            str(corpus_root / "corpus"),
            "--allowlist-file",
            str(corpus_root / "allowlist.yml"),
            "--owner-summary",
        ],
        capture_output=True,
        text=True,
        check=False,
        env=e,
    )


def test_owner_summary_ranks_with_named_owners(corpus: Path, tmp_path: Path):
    """done-when: RANKED list + named-owner list, as a real GHA summary."""
    summary = tmp_path / "step-summary.md"
    r = run_analyzer(corpus, summary)
    assert r.returncode == 0, r.stderr[-400:]
    text = summary.read_text()
    assert "RANKED" in text.upper(), "no ranked table in the summary"
    # both flakes present, with pass rates
    assert "test_x" in text and "test_reg" in text
    # ranking: test_x (2 fail / 5 runs) is flakier than test_reg (1 fail / 3)
    assert text.index("test_x") < text.index("test_reg"), "table is not ranked by flakiness"
    # owner column: registered shows the tracking ref; unregistered says so
    assert "NEM-9001" in text, "registered flake must show its tracking ref"
    assert "no owner" in text.lower(), "unregistered flake must be visible as UNOWNED"
    # stable test must NOT appear
    assert "test_ok" not in text
    # corpus size is printed even when flakes ARE found — the zero-flake case
    # must still show its denominator, or "no flakes" is indistinguishable
    # from "read nothing" (the WP0.5 vacuous-pass class).
    assert "Corpus: **3**" in text, "summary must state how many tests were read"


def test_owner_summary_absent_flag_is_noop(corpus: Path, tmp_path: Path):
    """Without --owner-summary nothing changes (the nightly caller is untouched)."""
    summary = tmp_path / "s2.md"
    import os

    e = dict(os.environ, GITHUB_STEP_SUMMARY=str(summary))
    r = subprocess.run(
        [
            "python3",
            str(ANALYZER),
            str(corpus / "corpus"),
            "--allowlist-file",
            str(corpus / "allowlist.yml"),
        ],
        capture_output=True,
        text=True,
        check=False,
        env=e,
    )
    assert r.returncode == 0, r.stderr[-400:]


# ---------------------------------------------------------------------------
# Harvest: fetch-ci-artifacts.py --self-test against a canned API.
# ---------------------------------------------------------------------------


def test_harvest_selects_and_downloads(tmp_path: Path):
    """--self-test: newest-with-artifacts wins, current run never, fail loud."""
    zip_a = tmp_path / "art-a.zip"
    with zipfile.ZipFile(zip_a, "w") as z:
        z.writestr("flaky-test-tracking-unit-shard-1.jsonl", jsonl_line("t", {"x::y": ["passed"]}))
        z.writestr("flaky-test-tracking-unit-shard-2.jsonl", jsonl_line("t", {"x::z": ["passed"]}))
    zip_c = tmp_path / "art-c.zip"
    with zipfile.ZipFile(zip_c, "w") as z:
        z.writestr("playwright-test-results-1/chromium/junit.xml", "<testsuites/>")

    routes = {
        "/repos/o/r/actions/workflows?per_page=100": {
            "workflows": [{"id": 7, "path": ".github/workflows/ci.yml"}]
        },
        "/repos/o/r/actions/workflows/7/runs?branch=main&status=success&per_page=8": {
            "workflow_runs": [
                {"id": 103, "status": "completed", "head_branch": "main"},  # the CURRENT run
                {"id": 102, "status": "completed", "head_branch": "main"},  # no artifacts -> skip
                {"id": 101, "status": "completed", "head_branch": "main"},  # the winner
            ]
        },
        "/repos/o/r/actions/runs/103/artifacts?per_page=100": {"artifacts": []},
        "/repos/o/r/actions/runs/102/artifacts?per_page=100": {"artifacts": []},
        "/repos/o/r/actions/runs/101/artifacts?per_page=100": {
            "artifacts": [
                {
                    "id": 901,
                    "name": "test-results-unit-shard-1-py3.14",
                    "archive_download_url": "{base}/dl/a",
                },
                {
                    "id": 902,
                    "name": "playwright-test-results-1",
                    "archive_download_url": "{base}/dl/c",
                },
            ]
        },
    }
    body_map = {"{base}/dl/a": zip_a, "{base}/dl/c": zip_c}

    class H(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path in ("/dl/a", "/dl/c"):
                f = body_map["{base}/dl" + self.path[3:]]
                self.send_response(200)
                self.end_headers()
                self.wfile.write(f.read_bytes())
                return
            r = routes.get(self.path)
            if r is None:
                self.send_error(404)
                return
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            base = f"http://127.0.0.1:{self.server.server_address[1]}"
            self.wfile.write(json.dumps(r, default=str).replace("{base}", base).encode())

        def log_message(self, *a):
            pass

    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), H)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    try:
        base = f"http://127.0.0.1:{srv.server_address[1]}"
        out = tmp_path / "out"
        r = subprocess.run(
            [
                "python3",
                str(HARVESTER),
                "--self-test",
                "--api-base",
                base,
                "--repo",
                "o/r",
                "--current-run-id",
                "103",
                "--out",
                str(out),
            ],
            capture_output=True,
            text=True,
            check=False,
            timeout=60,
        )
        assert r.returncode == 0, f"harvest failed: {r.stdout[-300:]} {r.stderr[-300:]}"
        found = sorted(p.name for p in out.rglob("*.jsonl"))
        assert len(found) == 2, f"expected the 2 jsonl from run 101, got {found}"
        assert "selected run 101" in r.stdout, "selection log must name the winning run"

        # dead API -> non-zero (silence must not read as 'no flakes')
        r2 = subprocess.run(
            [
                "python3",
                str(HARVESTER),
                "--self-test",
                "--api-base",
                "http://127.0.0.1:1",
                "--repo",
                "o/r",
                "--current-run-id",
                "1",
                "--out",
                str(tmp_path / "out2"),
            ],
            capture_output=True,
            text=True,
            check=False,
            timeout=60,
        )
        assert r2.returncode != 0, "dead API must exit non-zero (fail loud, not empty)"
    finally:
        srv.shutdown()


def test_harvest_skips_expired_and_stale(tmp_path: Path):
    """Finding-4 hardening (measured 2026-09-21): the runs-list API served a
    PR job a stale page whose newest candidate was a January run with
    expired artifacts -> every download 410 Gone -> baseline empty -> TPA
    fail-closed red, while a correct page was served to a sibling job. The
    harvester must be immune to that page: expired artifacts are not
    harvestable (GitHub 410s their zip — measured on artifact 5038838599),
    so an expired artifact must not make a run "selected" at all — the run
    drops out of candidacy and the walk continues to the next page entry."""
    zip_fresh = tmp_path / "fresh.zip"
    with zipfile.ZipFile(zip_fresh, "w") as z:
        z.writestr("flaky-test-tracking-unit-shard-1.jsonl", jsonl_line("t", {"x::y": ["passed"]}))

    routes = {
        "/repos/o/r/actions/workflows?per_page=100": {
            "workflows": [{"id": 7, "path": ".github/workflows/ci.yml"}]
        },
        "/repos/o/r/actions/workflows/7/runs?branch=main&status=success&per_page=8": {
            "workflow_runs": [
                # the shape the stale page served: same run listed TWICE —
                # first a months-old copy whose artifacts are all expired,
                # then the fresh run that a correct page would have led with.
                {"id": 201, "status": "completed", "head_branch": "main"},
                {"id": 200, "status": "completed", "head_branch": "main"},
            ]
        },
        "/repos/o/r/actions/runs/201/artifacts?per_page=100": {
            "artifacts": [
                {
                    "id": 801,
                    "name": "test-results-unit-shard-1-py3.14",
                    "archive_download_url": "{base}/dl/stale",
                    "expired": True,
                }
            ]
        },
        "/repos/o/r/actions/runs/200/artifacts?per_page=100": {
            "artifacts": [
                {
                    "id": 800,
                    "name": "test-results-unit-shard-1-py3.14",
                    "archive_download_url": "{base}/dl/fresh",
                    "expired": False,
                }
            ]
        },
    }
    body_map = {"{base}/dl/fresh": zip_fresh}

    class H(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == "/dl/stale":
                self.send_error(410)  # GitHub's honest answer for expired zips
                return
            if self.path == "/dl/fresh":
                self.send_response(200)
                self.end_headers()
                self.wfile.write(zip_fresh.read_bytes())
                return
            r = routes.get(self.path)
            if r is None:
                self.send_error(404)
                return
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            base = f"http://127.0.0.1:{self.server.server_address[1]}"
            self.wfile.write(json.dumps(r, default=str).replace("{base}", base).encode())

        def log_message(self, *a):
            pass

    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), H)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    try:
        base = f"http://127.0.0.1:{srv.server_address[1]}"
        out = tmp_path / "out"
        r = subprocess.run(
            [
                "python3",
                str(HARVESTER),
                "--self-test",
                "--api-base",
                base,
                "--repo",
                "o/r",
                "--current-run-id",
                "1",
                "--out",
                str(out),
            ],
            capture_output=True,
            text=True,
            check=False,
            timeout=60,
        )
        assert r.returncode == 0, f"harvest failed: {r.stdout[-300:]} {r.stderr[-300:]}"
        assert "selected run 200" in r.stdout, (
            f"expired-only candidate 201 must be skipped, expected selection of 200: {r.stdout[-400:]}"
        )
        assert len(list(out.rglob("*.jsonl"))) == 1
    finally:
        srv.shutdown()


def test_harvest_skips_pre_retention_candidates(tmp_path: Path):
    """Finding-4's SECOND stale-page signature (measured 2026-09-21 19:22Z,
    run 35637776479 TPA): the runs-list page served a runner job EIGHT
    January candidates (ids 20716417308..20753667016) whose artifacts are
    long fully deleted — not expired-flagged, just gone, so the artifact
    listing yields nothing and every candidate "skips" into a vacuous
    HarvestError while fresh main runs sat unharvested on the honest page.
    A run older than artifact retention is unharvestable BY DEFINITION
    (repo sets retention-days: 7) and its created_at says so on the page
    itself — the walk must drop it before the artifact query and keep
    walking, so one stale page can never blank the baseline."""
    zip_fresh = tmp_path / "fresh.zip"
    with zipfile.ZipFile(zip_fresh, "w") as z:
        z.writestr("flaky-test-tracking-unit-shard-1.jsonl", jsonl_line("t", {"x::y": ["passed"]}))

    routes = {
        "/repos/o/r/actions/workflows?per_page=100": {
            "workflows": [{"id": 7, "path": ".github/workflows/ci.yml"}]
        },
        "/repos/o/r/actions/workflows/7/runs?branch=main&status=success&per_page=8": {
            "workflow_runs": [
                # the stale page shape, minus the expired flag: an ancient
                # run listed first, a fresh one second. created_at is served
                # in the page itself — no clock access needed beyond "now".
                {
                    "id": 301,
                    "status": "completed",
                    "head_branch": "main",
                    "created_at": "2025-01-05T20:56:44Z",
                },
                {
                    "id": 300,
                    "status": "completed",
                    "head_branch": "main",
                    "created_at": "2020-01-01T00:00:00Z",
                },  # far future (see below)
            ]
        },
        "/repos/o/r/actions/runs/300/artifacts?per_page=100": {
            "artifacts": [
                {
                    "id": 900,
                    "name": "test-results-unit-shard-1-py3.14",
                    "archive_download_url": "{base}/dl/fresh",
                }
            ]
        },
    }

    class H(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            import datetime

            if self.path == "/dl/fresh":
                self.send_response(200)
                self.end_headers()
                self.wfile.write(zip_fresh.read_bytes())
                return
            r = routes.get(self.path)
            if r is None:
                self.send_error(404)
                return
            doc = json.loads(json.dumps(r, default=str))
            # the script compares created_at against its own clock; serve
            # run 300 as "created 1h ago" so its freshness is relative, not
            # a literal the test suite rots on.
            for run in doc.get("workflow_runs", []):
                if run["id"] == 300:
                    now = datetime.datetime.now(datetime.UTC)
                    run["created_at"] = (now - datetime.timedelta(hours=1)).strftime(
                        "%Y-%m-%dT%H:%M:%SZ"
                    )
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            base = f"http://127.0.0.1:{self.server.server_address[1]}"
            self.wfile.write(json.dumps(doc, default=str).replace("{base}", base).encode())

        def log_message(self, *a):
            pass

    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), H)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    try:
        base = f"http://127.0.0.1:{srv.server_address[1]}"
        out = tmp_path / "out"
        r = subprocess.run(
            [
                "python3",
                str(HARVESTER),
                "--self-test",
                "--api-base",
                base,
                "--repo",
                "o/r",
                "--current-run-id",
                "1",
                "--out",
                str(out),
            ],
            capture_output=True,
            text=True,
            check=False,
            timeout=60,
        )
        assert r.returncode == 0, f"harvest failed: {r.stdout[-400:]} {r.stderr[-300:]}"
        assert "selected run 300" in r.stdout, (
            f"pre-retention 301 must be skipped, expected 300: {r.stdout[-400:]}"
        )
        assert "retention" in r.stdout.lower(), "skip reason must NAME retention (stale-page tell)"
        assert len(list(out.rglob("*.jsonl"))) == 1
    finally:
        srv.shutdown()


def test_harvest_retries_stale_selection(tmp_path: Path):
    """Finding-4 hardening #3 (measured 2026-09-21 21:00Z, runs 35650649386
    (#6629 head, WITH the retention filter) + 35650688761 (#6631 head)): the
    retention filter did its job — all eight January candidates correctly
    refused ("beyond artifact retention") — but a job makes ONE candidate-
    list request, GitHub served that ONE request a fully-stale page, and the
    walk still died vacuously. Both lanes failed identically. Staleness is
    per-request (sibling jobs minutes apart hit honest pages), so a vacuous
    selection is retried --list-retries times with --retry-sleep between —
    a stale page is a transient API lie, and only a persistently-stale one
    may exit non-zero (fail-loud doctrine intact: retrying != tolerating).
    Canned API: first list call serves the stale page (one pre-retention
    run); the second serves the fresh run. Default retry-sleep is 300s;
    the test drives it at 0.05s."""
    zip_fresh = tmp_path / "fresh.zip"
    with zipfile.ZipFile(zip_fresh, "w") as z:
        z.writestr("flaky-test-tracking-unit-shard-1.jsonl", jsonl_line("t", {"x::y": ["passed"]}))

    state = {"lists": 0}

    class H(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            import datetime

            if self.path == "/dl/fresh":
                self.send_response(200)
                self.end_headers()
                self.wfile.write(zip_fresh.read_bytes())
                return
            if self.path == "/repos/o/r/actions/workflows?per_page=100":
                doc = {"workflows": [{"id": 7, "path": ".github/workflows/ci.yml"}]}
            elif self.path.startswith("/repos/o/r/actions/workflows/7/runs"):
                state["lists"] += 1
                if state["lists"] == 1:
                    # the lie: a page whose only candidate predates retention
                    doc = {
                        "workflow_runs": [
                            {
                                "id": 401,
                                "status": "completed",
                                "head_branch": "main",
                                "created_at": "2025-01-05T20:56:44Z",
                            }
                        ]
                    }
                else:
                    now = datetime.datetime.now(datetime.UTC)
                    doc = {
                        "workflow_runs": [
                            {
                                "id": 400,
                                "status": "completed",
                                "head_branch": "main",
                                "created_at": (now - datetime.timedelta(hours=1)).strftime(
                                    "%Y-%m-%dT%H:%M:%SZ"
                                ),
                            }
                        ]
                    }
            elif self.path == "/repos/o/r/actions/runs/400/artifacts?per_page=100":
                base = f"http://127.0.0.1:{self.server.server_address[1]}"
                doc = {
                    "artifacts": [
                        {
                            "id": 950,
                            "name": "test-results-unit-shard-1-py3.14",
                            "archive_download_url": f"{base}/dl/fresh",
                        }
                    ]
                }
            else:
                self.send_error(404)
                return
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(doc, default=str).encode())

        def log_message(self, *a):
            pass

    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), H)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    try:
        base = f"http://127.0.0.1:{srv.server_address[1]}"
        out = tmp_path / "out"
        r = subprocess.run(
            [
                "python3",
                str(HARVESTER),
                "--self-test",
                "--api-base",
                base,
                "--repo",
                "o/r",
                "--current-run-id",
                "1",
                "--out",
                str(out),
                "--list-retries",
                "3",
                "--retry-sleep",
                "0.05",
            ],
            capture_output=True,
            text=True,
            check=False,
            timeout=60,
        )
        assert r.returncode == 0, (
            f"stale-then-honest page must converge, got rc={r.returncode}: "
            f"{r.stdout[-400:]} {r.stderr[-200:]}"
        )
        assert "selected run 400" in r.stdout
        assert "retry" in r.stdout.lower(), "the retry must be VISIBLE in the log"
        assert state["lists"] >= 2, "the honest page was never actually re-requested"
        assert len(list(out.rglob("*.jsonl"))) == 1
    finally:
        srv.shutdown()


def test_ci_yml_wires_the_consumer():
    """ci.yml must carry the flake-report consumer, gate- or triage-classed."""
    import yaml

    with CI.open() as f:
        data = yaml.safe_load(f)
    jobs = data["jobs"]
    assert "flake-report" in jobs, "WP1.5: no consumer job reads the per-run flaky tracking"
    job = jobs["flake-report"]
    script = "\n".join(s.get("run", "") for s in job["steps"])
    assert "fetch-ci-artifacts.py" in script, "consumer must HARVEST ci.yml's own artifacts"
    assert "analyze-flaky-tests.py" in script, "consumer must run the analyzer"
    assert "--owner-summary" in script, "consumer must produce the owner table"
    # WP0.6 graph rule: red-able jobs are GATE-carried or Linear-triaged.
    triaged = any("Linear" in (s.get("name") or "") for s in job["steps"])
    gate = jobs["ci-gate"]
    gate_script = "\n".join(s.get("run", "") for s in gate["steps"])
    gate_carried = "flake-report" in gate.get("needs", []) and "flake-report" in gate_script
    assert gate_carried or triaged, (
        "flake-report red is neither carried by ci-gate nor Linear-triaged (WP0.6)"
    )
    # the twice-bitten selection rule now has ONE implementation: TPA's
    # baseline fetch uses the shared script, no curl/jq heredoc left.
    tpa = jobs["test-performance-audit"]
    tpa_script = "\n".join(s.get("run", "") for s in tpa["steps"])
    assert "fetch-ci-artifacts.py" in tpa_script, "TPA must use the shared harvester"
    assert "workflows/$WFID" not in tpa_script, "the duplicated curl selection must be gone"
