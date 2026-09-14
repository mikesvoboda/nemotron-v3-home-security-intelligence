# m3-t1-t3 (salvaged from /tmp/wave3-draft/t1-t3 pre-restart)

- **t1.patch** (zero-risk deletions, audit 1.1/1.2): applies CLEAN at HEAD ab9e5774.
- **t3.patch** (permanently-skipped unit tests → integration split, audit 1.3):
  was cut pre-T5-step-1, so its conftest hunk @400 now conflicts. `git apply -3`
  merges cleanly (no markers): verified at HEAD — cli_cap/T5 hunks survive,
  file parses. Apply with `git apply -3` and eyeball the conftest docstring hunk.
- Also salvaged: stack-final.patch (earlier iteration, superseded by t1+t3 here).
- build/ + build3/ = draft workbenches (file trees as drafted); kept for diffing.

Chain context (verified same day in throwaway worktree): wave3 t5→t6→t7 stack
clean atop HEAD, t3-draft/t3.patch (M2 vitest) clean on top of that, and
t10/t13/t14/t4 all apply after the chain. w0-runbook ledger-addition.patch is
DIRTY (ledger gained T5 entries below its anchor — rebase its text at apply time).
