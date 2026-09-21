---
name: pkill-self-match-trap
description: "pkill -f matches the killing command's OWN cmdline and kills your shell mid-call (rc 144); kill by PID from a bracketed-pattern ps instead"
metadata:
  node_type: memory
  type: feedback
  originSessionId: 79a1f342-0c47-43c3-bc69-b513f06e89fc
  modified: 2026-09-17T08:52:25.895Z
---

`pkill -f "pytest backend/tests/unit"` inside a Bash tool call killed the
calling shell itself: the bash -c wrapper's cmdline contains the pattern
text, so pkill's regex hits its own process. Symptom: the tool result is
just `Exit code 144` and nothing after the pkill ran.

**Why:** pkill -f matches full command lines of ALL processes, including the
one issuing the pkill (the snapshot-wrapper shell embeds the eval'd command
string verbatim). Same trap applies to `pgrep -f` sanity checks run after a
kill.

**How to apply:** enumerate first with a bracketed pattern that can't match
itself (`ps -eo pid,cmd | grep "[m]utmut run" | grep -v grep`), then
`kill <PIDs>` explicitly. For waiting loops use `pgrep -f "[v]alidate.sh"`.
Never chain `pkill -f X; <more work>` expecting the rest to run. Related:
[[monitor-lines-are-not-truth]] (verify against ps/disk, not event streams).
