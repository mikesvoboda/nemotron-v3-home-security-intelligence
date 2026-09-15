"""Per-phase duration recorder for the integration tier (setup/call/teardown).

Motivation: rss_trace_plugin2 only records call-phase deltas; the owner needs
true per-phase durations to decide the timeout_func_only / shared-budget
change. report.duration already carries exactly this (seconds per phase) —
this plugin just appends every report row to a per-worker TSV IMMEDIATELY,
so a mid-run worker crash only loses the in-flight test.

Also joins each nodeid's @slow / explicit @timeout(N) marker (collected
per-xdist-worker at collection time) so the analysis can show which items
already exceed the shared budget by design.

Output: $DURATIONS_DIR/<worker>.tsv rows: nodeid \t when \t dur \t outcome \t slow \t timeout_mark
Load: PYTHONPATH=backend/tests/plugins DURATIONS_DIR=<dir> -p durations_plugin
(DURATIONS_DIR defaults to the gitignored .pytest_cache/durations — not /tmp,
which a cleanup once wiped mid-analysis and cost the evidence).
"""

import os
from pathlib import Path

OUT_DIR = Path(os.environ.get("DURATIONS_DIR", ".pytest_cache/durations"))
_markers: dict[str, tuple[str, str]] = {}


def pytest_collection_modifyitems(config, items):
    for item in items:
        t = item.get_closest_marker("timeout")
        tm = str(t.args[0]) if t and t.args else ""
        _markers[item.nodeid] = ("1" if item.get_closest_marker("slow") else "0", tm)


def pytest_runtest_logreport(report):
    if report.when not in ("setup", "call", "teardown"):
        return
    OUT_DIR.mkdir(exist_ok=True)
    worker = os.environ.get("PYTEST_XDIST_WORKER", "main")
    slow, tm = _markers.get(report.nodeid, ("?", ""))
    with (OUT_DIR / f"{worker}.tsv").open("a") as f:
        f.write(
            f"{report.nodeid}\t{report.when}\t{report.duration:.3f}"
            f"\t{report.outcome}\t{slow}\t{tm}\n"
        )
