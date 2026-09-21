---
name: comm-tab-prefix-trap
description: comm -1/-2/-3 print the right column TAB-prefixed — cut/comm joins downstream silently fail
metadata:
  node_type: memory
  type: reference
  originSessionId: 79a1f342-0c47-43c3-bc69-b513f06e89fc
  modified: 2026-09-16T16:17:18.448Z
---

`comm -1`, `-2`, `-3` print the non-shared column prefixed with a TAB
(`-3` prefixes the right-column lines; `-1` the left-only, etc). Downstream
`cut -d: -f1` keeps the tab, so a later `comm -12` join against clean file
lists matches NOTHING — silently, with plausible-looking zero results.

Caught in the WP2.1 bake-off: `comm -3 parent.txt truth.txt | cut -d: -f1`
→ affected.files every line tab-led → both selectors scored a false 0/1
recall while both had actually selected the file. Fix: always `sed 's/^\t//'`
after a comm column that can carry the prefix, and cross-check one parsed
artifact against an independently counted number before trusting a table.

Related: [[goal-prompt-workflow]]
