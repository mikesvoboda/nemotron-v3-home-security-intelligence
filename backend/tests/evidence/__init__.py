"""Evidence harnesses for Uplevel packages (contract rule 3: tools live in the repo).

This directory is deliberately OUTSIDE the nightly unit tier (unit/contracts/security)
and the PR-gate unit shard (backend/tests/unit/), so its measurement tests run only
when a reviewer invokes them. See r109_nightly_gate_harness.py.
"""
