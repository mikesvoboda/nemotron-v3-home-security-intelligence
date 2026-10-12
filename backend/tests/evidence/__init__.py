"""Evidence harnesses for Uplevel packages (contract rule 3: tools live in the repo).

This directory is deliberately OUTSIDE the nightly unit tier (unit/contracts/security)
and the PR-gate unit shard (backend/tests/unit/), so its measurement tests run only
when a reviewer invokes them. See AGENTS.md in this directory for the tools, the
EVIDENCE_R109 switch and the traps; test_r109_nightly_gate_harness.py carries the
PROVENANCE boundary for the figures it re-derives.
"""
