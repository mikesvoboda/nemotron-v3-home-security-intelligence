---
name: gh-pr-checks-no-json
description: "gh pr checks has no --json flag in this sandbox's gh — monitors built on it poll nothing and expire with zero events; use plain output or REST instead"
metadata:
  node_type: memory
  type: reference
  originSessionId: a4bfff8c-fd38-45e3-bf4d-045ba7d1b435
  modified: 2026-09-15T22:30:07.530Z
---

In this environment (gh as of 2026-09-15), `gh pr checks <n> --json ...` fails with
`unknown flag: --json` (supported: `--watch`, `--required`, `--fail-fast`, `--interval`).
Two Monitor watches on PR 6542 silently polled nothing and expired with 0 events because
their jq pipelines assumed a --json flag that the loop's `2>/dev/null` swallowed.

**How to apply:** in monitor/poll loops use `gh pr checks <n>` plain (columns: name, status,
duration, URL) and grep, or `gh api repos/{owner}/{repo}/commits/{sha}/check-runs` for
structured data. A monitor that expires with no events after a long window is suspect
evidence of a broken filter, not a quiet CI. Related: [[github-free-tier-boundaries-2026]]
