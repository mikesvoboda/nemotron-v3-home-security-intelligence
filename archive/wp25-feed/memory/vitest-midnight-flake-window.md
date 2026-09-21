---
name: vitest-midnight-flake-window
description: "FIXED cc17daab: Date.now()-relative mocks failed 00:00-02:00 UTC; freeze clock per-test, never globally (userEvent v14 stalls). Sibling flake: test_redis_pubsub publish-before-listen race"
metadata:
  node_type: memory
  type: project
  originSessionId: a4bfff8c-fd38-45e3-bf4d-045ba7d1b435
  modified: 2026-09-16T02:53:35.746Z
---

Discovered 2026-09-16 on PR #6546 (audit-regen, content- innocent): its CI Gate failed on
`Frontend Tests (Vitest 11/16)` → `ZoneAlertFeed.test.tsx > groups alerts by time by default`
at 00:15 UTC. Mocks built with `new Date(Date.now() - 3600000)` at **collection time**;
in the 00:00–02:00 UTC window (2h reach for the 1h/2h offsets) `isToday()` fails and the
'Today' group-header assertion dies. Will re-poison every PR's Vitest shard nightly until
the fix (branch `fix/zone-alert-feed-midnight-flake`, pinned `FROZEN_NOW` + per-test
`vi.useFakeTimers()`) merges.

**Why:** queue timing collides with this window — rebases pushed 00:00–02:00 UTC burn
~25 min of free-tier runner time on the known-bad shard (see [[github-free-tier-boundaries-2026]]).

**How to apply:** (1) during 00:00–02:00 UTC, prefer landing clock-fix PRs before pushing
rebase sweeps; a Vitest failure in that window is probably this, check the UTC timestamp
before deep-diagnosing; (2) fix pattern = module-scope fixed reference Date + fake timers
scoped to the ONE time-dependent test — globally freezing in beforeEach makes userEvent v14
time out at 30s × N tests (measured 7 failures); (3) repo convention examples with frozen
clocks: TimeGroupedEvents.test.tsx, PersonJourneyTimeline.test.tsx (they already set SystemTime
— the hazard lives in files that DON'T). Sibling files still asserting Today/Yesterday without
freezing (DateRangePicker, FilterChips, useDateRangeState) were checked 2026-09-16 — their data
is absolute-date, safe.
