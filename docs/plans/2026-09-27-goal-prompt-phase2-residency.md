# /goal prompt - post-#6681 work (branch sync -> residency fix -> eval intake -> bigger-model survey)

Written 2026-09-27 after PR #6681 merged (squash -> `github/main` `4bfd6fa4`) and the owner
ruled "yes. this is a good plan" on the 1->2->3 sequence. Paste everything inside the fenced
block into `/goal` - the block measures 3994 characters, under the 4000 cap. Rationale and
detail live below the block, where they can be long.

```text
VSS GAMING-GPU workstream, branch feat/vss-gaming-gpu-profile. Paths repo-relative.

STATE: M0+M1 CLOSED; #6681 squash-merged to github/main (4bfd6fa4). Phase 2 bake-off ran (report + erratum in docs/plans/). S1/S4 NOT claimed (F13: 24 GB-class HW); Phase 2's plan: zero unchecked boxes.

ORDER:
0. BRANCH HYGIENE: merge github/main in (squash makes rebase hostile), re-prove tiers -
   the next PR then shows its real diff, not 75 merged commits.
1. RESIDENCY FIX - item 24, live, breaks F11 on the target card: preload defaults False;
   setup.py auto-sets it on total_vram_mb > 24*1024 (strict > - the 24 GB A5500 loses on
   its own spec figure); main.py's boot sweep filters enabled-and-not-available, never
   cfg.preload. Net: handles absent at boot, legs answer "unavailable", ~1.16 s cold load/request. Re-derive from item 24; RED-FIRST per defect before
   setup.py/config.py/main.py; the >= edge changes auto-detect - if in doubt present
   options. Dated ledger item; close 24 by pointer.
2. SYNTHETIC-EVAL INTAKE - a parallel agent builds the pipeline; freeze/replay is ours
   (backend/evaluation/eval_store.py). Pin their output contract: born-labeled shape;
   >=100 benign / >=20 incident bar (bake-off: S3 n=8, S2 n=5 - why bars can't rank);
   D10 real-media write refusal (their frames never enter git); attribution sidecars;
   count-identity block. DRY-RUN one batch through freeze+replay. RED-FIRST; dated
   ledger item; issue 19 stays [O] until corpus lands.
3. LARGER-MODEL SURVEY - agent-gpu pull + fit probe + the SAME n=13 harness over
   Mistral-Small-3.2-24B and Qwen3-VL-30B-A3B (weights: $AGENT_GPU_DIR/models). Nothing past 12B
   fits the 20.4 GiB S1 bar at shipped config; all five architectures register in our
   llama.cpp build. Add the criterion-differentiation read (A 4B
   flat-repeated evidence 7/11; B/C differentiated all): does past-12B earn its keep?
   Over-bar readings are RESULTS. Dated additive erratum; never rewrite the table.

INVARIANTS: GPU only via agent-gpu, never around it; --vram honest (~14 for a VLM server);
agent-gpu rm when done; never touch rootful dgx-inference. D10: real-camera imagery/labels never
enter git - synthetic items + aggregate metrics only. Legacy path UNSUPPORTED (F10):
tests pass, code not extended or measured against. Evidence closes steps: command, result,
commit, S#s, [V][C][E][?][O][A]; unrunnable = BLOCKED.

GATES: TDD red-first. unit: pytest backend/tests/unit/ -n auto: "1 failed, 30544 passed, 124 skipped,
8 xfailed" (sole sanctioned failure test_skips_when_skip_build). contracts -n0 --timeout=30, never xfail/skip in ai_providers.
Integration needs PG :5433 + Redis :6380 connect-checked in-session, else don't claim ran. gen-ai-contract --check after ai_contract edits. A 0-byte background-tier log is no pass (item 27).

COMMIT: repo root: SKIP=hadolint uv tool run pre-commit run --files <staged>, never
--all-files, re-stage to zero churn; then uv tool run conventional-pre-commit <types>
/tmp/msg.txt alone (it false-rejects dotted scopes). Msgs end "Co-Authored-By: Claude Code
<noreply@anthropic.com>" WHEN WRITTEN; grep the commit. CI: check-runs needs --paginate; gh pr checks status is column 2; pushes self-cancel
(cancel-in-progress) - judge the newest head (gh run view --json conclusion).

STOP AND ASK: M2 pick; go-live 3.1; any D#/S#; Brev spend; dgx-inference; agent-gpu
refusal/VRAM squeeze; R10 (no second model - one op only, required=
{"vlm_assess"}); item 28 budget (700 clears both); item 30 S3 floor; any
12-postponed-roadmap item; PRs, merges. PUSH standing permission: after each committed task git push github <branch>.

READ: docs/vss-integration/AGENTS.md -> 13-implementation-brief.md -> spec (D1-D12, S1-S6).
Ledger docs/plans/2026-09-23-vss-gaming-gpu-ledger.md items 20/22/24/28/30 first. Review
doctrine 29/30: open file:line before acting; CRITICAL labels least trustworthy.

REPORT per item 0-3: proven (S#s), failed + why, next, decisions owed. Aggregates.
```

---

## Why the block says what it says (not pasted)

- **Step 0 leads because the merge is load-bearing.** A squash-merge leaves the branch's 75
  commits absent from main _by identity_ while main holds one commit absent from the branch;
  rebasing would duplicate the content, so the prescribed shape is a merge. Every later item's
  PR is only reviewable after that, and the merge landed as `e62aa86b` with a provably empty
  content diff (`git diff --stat HEAD^1 HEAD` printed nothing), which is what makes "prove the
  tiers" a verification rather than a repair.
- **The residency item names its three defects but not its line numbers.** The chain (the
  `config.py` default, the three strict-`>` sites in `setup.py`, the `main.py` sweep that
  filters on `enabled and not available`) is verified here and in ledger item 24; making the
  next session re-read item 24 is deliberate - line anchors go stale within one slice (ledger
  item 25's own lesson), so the goal points at the durable description and keeps the one
  durable fact, the ~1.16 s cold-load price. `>` -> `>=` changes setup.py's auto-detect
  behavior, which is why the block says present options rather than self-resolve.
- **Step 2 states ownership boundaries**, because the collision risk isn't their generator,
  it's our freeze path meeting it mid-flight; the n=8/n=5 counts are in the block because they
  are the _evidence_ for why the corpus size is the blocker, not a platitude about wanting
  more data.
- **Step 3 pre-commits the framing**: a reading over 20.4 GiB is the expected result, recorded
  - otherwise a run that answers "no" reads like a failure to a later reader (and the fit
    arithmetic reproduces the shipped table's own KV rows exactly, so new candidates are
    comparable rather than freshly invented).
- **R10 appears in stop-and-ask with the 2026-09-27 finding**, since the owner's intent is one
  model and the shipped registry proves it (`required={"vlm_assess"}` at
  `backend/ai_contract/providers.py:184-188`) - the risk is a future session helpfully
  _adding_ the deferred reasoner.
- **What the 4000-char cap cut** (3994 measured, re-measure with `wc` before pasting if the
  wording changes): the GPU build/pull/mount mechanics recipe (the invariants line keeps what
  must never break; the recipe lives in G0's ledger rows and the spec), the frontend
  typecheck gate line (rides the TS-regen rule in the spec's gates), the read-order preamble
  compressed to pointers, the spike doctrine, plan history, and every per-rule explanation.
  All of it is one `git show fd2aefbc` away in this file's prior version.
