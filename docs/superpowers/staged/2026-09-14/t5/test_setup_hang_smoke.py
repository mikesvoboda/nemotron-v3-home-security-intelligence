"""M3 T5 precondition harness (ruling packet §2 REMAINING CHECK + §5).

Proves, under the PROPOSED config (signal + func_only=false), that:
 (a) a synthetic hang inside FIXTURE SETUP fails inside the timeout budget
     with a normal pytest ERROR report — no node-down, summary survives;
 (b) pytest-rerunfailures composes with signal-timeout (the scar comment's
     claimed harm mechanism) — a setup-hang under --rerun=1 reruns and
     fails cleanly, process survives.

Run standalone, serial, cheap DB-free:
  cd repo && uv run pytest /tmp/t5/test_setup_hang_smoke.py -p no:cacheprovider \
    -p pytest_time...tamp --timeout=5 -q
Expected under proposed config: 1 error (setup timeout) in ~5-6s, exit 1,
NO "node down". Under thread-method this kills the process (exit 1, no
summary) — that contrast is the audit Part 6 claim re-verified.
"""
import time

import pytest


@pytest.fixture
def hanging_setup():
    time.sleep(120)  # wedged setup — the run-9 gw6 media_api class
    yield None


def test_setup_hang_reports_cleanly(hanging_setup):
    pytest.fail("unreachable: setup must time out first")
