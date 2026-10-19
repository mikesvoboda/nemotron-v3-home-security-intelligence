# Qwen-era merge audit (ruling 262)

The to-do sheet for ruling 262 (record 6257468143): the code the Qwen-era merges left on main,
read as it stands at the pinned SHA below, one entry per PR the census keeps. Each fix is the
owner's call (`fix`, `skip`, `later`), made later by the lane that owns the path. The cites stay
at the pinned SHA as main moves; the package that later fixes an item re-reads it on its own base.

- **Pinned SHA:** `41bc0fce71f85ddd2795b67b1e7597990d3a5603` (main at this claim; the merge of #7262)
- **Census window:** merged 2026-10-07T00:00Z to 2026-10-18T07:36Z
- **Census:** every PR merged to main in the window carrying a `lane:` label and no label
  containing `heavy`, plus the `[red-main]` PRs with no label at all; excluding the owner
  session's PRs (head branch starting `uplevel/owner-`, or a `Co-Authored-By: Claude Opus`
  commit trailer in the merge). A PR's files are its merge commit's diff against its first
  parent, kept if the same path exists at the pinned SHA. One class per PR, first match in the
  order production, test, tooling; Markdown skipped; everything else skipped.
- **Census command:** the `python3 - "$PIN" <<'PY'` script in `[r262]`'s block in
  `docs/uplevel/packages/docs.md` (run with `$PIN` = the pinned SHA).
- **Census control:** at `a3b1bd336` the owner session's run gave 228 PRs — 52 production, 110
  test, 6 tooling, 60 none.

## Census counts at the pinned SHA

(batch 1 pending — filled when the census has run)

## Batches

Production first, then test, then tooling; within a class in PR-number order. Batch 1 is the
first ten production PRs; later batches are about fifteen PRs, one comment each. Each batch
records how many items a fresh unnamed refutation subagent (ruling 232) dropped.

| Batch | PRs | Items | Refuted | Comment |
| ----- | --- | ----- | ------- | ------- |
