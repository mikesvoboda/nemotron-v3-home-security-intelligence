---
name: monitor-lines-are-not-truth
description: Monitor/tail events lag and can contradict disk — verify case verdicts against log files before narrating
metadata:
  node_type: memory
  type: reference
  originSessionId: 79a1f342-0c47-43c3-bc69-b513f06e89fc
  modified: 2026-09-17T09:07:42.826Z
---

Monitor tail-f events arrive delayed and out of sync with the source: during the WP2.5 playbook run (2026-09-16) monitor lines appeared to show verdicts (rc=1, 1024s) that the filesystem flatly contradicted — the per-case log still ended mid-run, the results file was 0 bytes, and the quoted wall self-contradicted the script's own bound. Two false narratives had to be walked back.

**Why:** each `run_case` prints its line only when the case completes; `tail -f` can replay an old line on re-arm and grep filters can make stale lines look fresh. Disk state (log size, dir listing, process table) is the primary record.

**How to apply:** before reporting any monitor event as a result, check `wc -c` on the log, the case dir listing, and `pgrep` for the run; a monitor line that contradicts disk (or physics — a wall over a bound the script can't produce) is noise, not a finding. Related: [[wp25-resume-pack-2026-09-16]].

**2026-09-17 addendum:** a dead monitor's queued backlog can burst out
MINUTES later, in original order, complete with the old run's death
sequence (generation "done" → stats failure → rc=1) — while the disk log
is frozen at its old size and no run process exists. Events even arrive
after TaskStop reports the task no longer exists. A live chained launch
waiting behind another job shows the SAME lines only when disk moves:
log size + mtime change and a real process. Cheap arbiter: one
`ls -la log; ps | grep [r]unpattern` call before any narration.
