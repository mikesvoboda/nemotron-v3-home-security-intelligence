# /goal prompt — post-M2-bake-off work (branch sync → residency fix → eval intake → larger-model survey)

Written 2026-09-27 after PR #6681 merged (squash → `github/main` `4bfd6fa4`) and the owner
ruled "yes. this is a good plan" on the 1→2→3 sequence. Paste everything inside the fenced
block into `/goal`. The three in-work items are the NEW content; the rest carries forward
verbatim from the governing goal so the new session inherits the same invariants.

```text
VSS GAMING-GPU workstream. Branch feat/vss-gaming-gpu-profile. Paths repo-relative.

STATE: M0 CLOSED (PR #6678, main a0105b63). M1 CLOSED and PR #6681 MERGED by the owner
2026-09-27 as a SQUASH (github/main 4bfd6fa4; the branch's 75 commits are not in main by
identity, and main carries 1 commit the branch lacks). Phase 2's bake-off ran: report
docs/plans/2026-09-27-vss-phase2-bakeoff-report.md + its same-day erratum; S1/S4 NOT claimed
(F13 reserves them for 24 GB-class hardware). Phase 2 plan
docs/superpowers/plans/2026-09-27-vss-phase2-evaluation-bakeoff.md has zero unchecked boxes;
remaining Phase 2/3 steps are owner-run (2.3 Brev matrix, 3.1 sign-off) or owner decisions.

ORDERED WORK for this session, in this order:
0. BRANCH HYGIENE first, nothing else lands before it. Fetch github, then merge github/main
   into feat/vss-gaming-gpu-profile (squash-merge makes a rebase hostile: the same content
   exists twice, so take the merge). Prove the tree after: unit -n auto to the banked
   identity (below), contracts -n0, gen-ai-contract --check current. The point is that the
   NEXT PR shows the real diff, not 75 merged commits.
1. SPECIALIST RESIDENCY FIX - ledger item 24's defect, live and re-verified 2026-09-27, it
   contradicts F11 ("specialists resident") on the target card. The chain:
   backend/core/config.py:2859 backend_model_preload defaults False; setup.py:645,861,1022
   auto-set it on total_vram_mb > 24*1024 - a STRICT >, so the 24 GB A5500 loses on its own
   spec figure; and backend/main.py:1166-1173 filters the boot sweep on cfg.enabled and not
   cfg.available, NEVER on cfg.preload, so a models.yml row that says "preload: true"
   preloads nothing and one that says nothing preloads everything the flag permits. Net on
   production hardware: the OSNet and face handles are absent at boot, so the re-ID leg and
   face enrollment answer "unavailable" (the correct degrade, but NOT residency), and the
   measured cost of NOT fixing it is a ~1.158 s cold load per request (item 24's numbers:
   cold load 1.158 s, warm extract 0.11 s, a transient load releases at refcount 0). Fix
   TDD-first: a failing test for each named defect BEFORE touching setup.py, config.py or
   main.py. The >= edge is a behavior change on setup.py's auto-detect - if the right shape
   is in doubt, present the options rather than self-resolving; the cfg.preload dead flag is
   pure plumbing. Full tier gates green + the real-bytes posture where it applies; ledger the
   fix as its own dated item and CLOSE item 24's "what" sentence with a pointer, never by
   rewriting the row.
2. SYNTHETIC-EVAL INTAKE CONTRACT - the collision-free half of the owner's parallel work.
   Another agent builds the synthetic DATA PIPELINE (the incident-media generation the F5
   amendment ruled); the freeze/replay side is ours and done: backend/evaluation/eval_store.py
   (create_all schema, the D10 repo-residence guard, _render_specialist_outputs,
   load_stock_items, the F12 clause that a sub-gate crop renders "not identifiable", never
   "unknown"). Write the pinning of WHAT THEIR OUTPUT MUST LOOK LIKE TO LAND: born-labeled
   shape; the 0.5 bar >=100 benign / >=20 incidents (we are nowhere near the incident side -
   the bake-off scored S3 at n=8 and S2 at n=5, which is WHY the bars could not rank
   candidates); the real-media refusal at write time (D10 - their incident frames are
   SYNTHETIC and must still never enter git; aggregate metrics only); attribution sidecars
   per the stock precedent; the corpus count-identity block. Then DRY-RUN one synthetic batch
   through the shipped freeze + replay path so their first real drop meets schema surprises
   here, not in a bake-off. TDD-first; ledger the contract as its own dated item; ledger
   open-issue 19 gets a "what this unblocks" pointer when the corpus actually lands - until
   then item 19 stays [O].
3. LARGER-MODEL SURVEY - turn the 2026-09-27 arithmetic into readings. The survey (real HF
   blob sizes + the shipped KV derivation: layers x kv_heads x 128 x 2 x f16 x 16384 cells x
   2 slots, which reproduces the table's A/C 4608 MiB and B 768 MiB exactly; +2.0 GiB buffers
   from B/C's measured fit-vs-actual delta; +3.0 GiB stack per the spec's vlm-mode budget; S1
   bar 20.4 GiB) concluded: nothing meaningfully past 12B fits 24 GB at the shipped config -
   Mistral-Small-3.2-24B lands 24.2, Qwen3-VL-30B-A3B 26.3 (Q3_K_M 22.7), Qwen3-VL-32B 32.5,
   Gemma-3-27B 36.7 - and the BAR, not the card, is what says so. All five are ungated on HF
   and all five architectures are already registered in our shipped llama.cpp build
   (qwen3vl/qwen3vlmoe/mistral3/gemma3 in the b11090 tree) - engine support is a non-issue.
   Do: agent-gpu pull + fit-probe + the SAME n=13 harness over Mistral-Small-3.2-24B and
   Qwen3-VL-30B-A3B (weights under $AGENT_GPU_DIR/models, never committed), and add the
   criterion-differentiation read: A 4B pasted one flat evidence string into 7 of its 11
   parseable verdicts while B and C differentiated every criterion on every item (B even
   caught an epoch-timestamp inconsistency unaided) - the reasoning signal appears to
   saturate by 8B, and these two runs are the first test of what beyond 12B earns. Expect the
   fit verdict to stay NO; the run is about quality-per-next-tier and banking rows for the
   item-19 re-run, and it changes no bar - if a reading comes in OVER 20.4 GiB that is the
   result, recorded, not a failure. Additive erratum to the bake-off report (dated, appended;
   never rewrite the shipped table), run ids recorded, ledger item with [V]/[C] markers.

READ in order - root AGENTS.md does not link this work: docs/vss-integration/AGENTS.md
("Start here") -> docs/vss-integration/13-implementation-brief.md ->
docs/superpowers/specs/2026-09-23-vss-gaming-gpu-profile-design.md: source of truth for
D1-D12, S1-S6, G0-4. Where it says podman, read agent-gpu.

INVARIANTS (break one = fail):
GPU: go through agent-gpu, never around it. Declare --vram honestly: exceeding it stops the
container in ~15 s, so declare the real working set (a VLM server: ~14, not 2). The broker
admits only what fits beside the flagship vLLM, which stays resident; never touch the rootful
dgx-inference containers; agent-gpu rm when done.
Privacy: real-camera imagery, labels, snapshots never enter git - synthetic items and
aggregate metrics only; wipe the eval store at Brev teardown (D10).
Legacy path is UNSUPPORTED (spec rev 5, ledger F10): never deploy it, measure against it, or
extend it - there is no control; S2/S3 are fixed bars. Its existing tests keep passing; the
code stays until R8 deletes it (build empty states, not deletions). Tests run the SHIPPED
default: the integration mock LLM passes the P0.3 enforcement check, and the legacy wire is
pinned only in tests whose subject IS legacy (owner ruling on PR #6678, superseding the
tier-wide pin).
Milestones close on executed evidence (command, result, commit, S#s), not code.

GPU MECHANICS: agent-gpu build --context workspace:ai/vlm --tag ai-vlm:sm103 --build-arg
CUDA_ARCHITECTURES=103. agent-gpu pull all base images first - builds never pull. No RUN-line
flags (--mount= incl.), no ONBUILD. --mount takes a whole root, ROOT:TARGET: weights under
$AGENT_GPU_DIR/models (never commit them), results to out. Serve with --port; use the printed
http://host.docker.internal:<port> URL.

PLAN ONE PHASE AT A TIME; never plan a later milestone. G0 CLOSED 2026-09-24, P0 CLOSED
2026-09-25, M1 CLOSED and #6681 MERGED 2026-09-27. Phase 2's agent-doable work is done; this
session executes the ordered list above - do NOT write a Phase 3 plan (3.1 is the owner's
sign-off). superpowers:*/codex absent here: write each phase plan to docs/superpowers/plans/
matching files there; milestone review = built-in code-review.

SPIKES: the brief's five, before you build, one row each: command and result. Unrunnable =
BLOCKED, never an unobserved pass.

LEDGER docs/plans/2026-09-23-vss-gaming-gpu-ledger.md - created and linked from
docs/vss-integration/AGENTS.md (done once; don't redo). Rows: per step (G0.1..4.3) and per
spike - status, date, command, result, commit. Doc-vs-repo conflict: ledger row or dated
errata in docs/vss-integration/, never a silent spec edit; keep the [V][C][E][?][O][A]
markers. Known-stale: the spec's 61 risk_score sites (0.25) do not reproduce - recount with
git grep -nE 'risk_score\s*(>=|<=|>|<)' -- backend/ ':(exclude)backend/tests/' and log count
plus recipe. READ the ledger's items 20, 22 (re-ID full swap - OSNet-AIN x1.0 is the one
person-vector space, model_id provenance, 410 on the client-vector match endpoint), 24
(residency defect - this session's item 1), 28/30 (owner-queued decisions) before touching
any of those areas. Review doctrine, items 29+30: open the file:line before acting on any
finding; the CRITICAL label is the least trustworthy part of a review; fan-out passes invent,
full-file passes miss - both directions are real.

GATES. uv sync only if .venv is missing (it persists once built here). TDD: failing test
first. uv run pytest backend/tests/unit/ -n auto. uv run pytest backend/tests/contracts/
-n0 --timeout=30 - never xfail/skip in contracts/ai_providers; an AST scan enforces it.
Integration needs live Postgres+Redis (PG :5433 + Redis :6380, UP and connect-checked IN THE
SAME SESSION before claiming the tier ran; if not up, don't claim it ran). cd frontend && npm
ci && npm run typecheck. After ai_contract changes run scripts/gen-ai-contract.py --check; on
red, regenerate, commit backend/ai_contract/ + goldens. Banked tier identities (from captured
logs, re-verify against your own run): unit "1 failed, 30544 passed, 124 skipped, 8 xfailed"
- the ONE sanctioned failure is test_deploy_phases::test_skips_when_skip_build (systemctl
env-fail); contracts 646 passed exit 0; integration "4089 passed, 107 skipped, 2 xfailed"
PYTEST_EXIT=0. A background tier with a 0-byte log is NOT a pass (ledger item 27).

COMMIT GATE: no hooks installed, uvx absent - nothing gates a commit but you. Once: uv python
install 3.12 (a hook pins it). Before every commit: uv tool run pre-commit run --files
<changed> FROM REPO ROOT (wrong cwd = vacuous green), NEVER --all-files (it reformats 158
files and wipes node_modules), then the message check DIRECTLY: uv tool run
conventional-pre-commit <types> <file> - the pre-commit wrapper for it false-rejects dotted
scopes (ledger erratum 2026-09-25). After any hook edits files, re-stage and re-gate until
zero churn before committing. Every /tmp/msgN.txt ends WITH the attribution trailer WHEN
WRITTEN (see PUSH); after git commit -F, spend one grep - git log -1 --format='%B' | grep
Co-Authored - before declaring a slice shipped; a pushed trailer miss is disclosed, never
force-pushed.

CI READING: gh api repos/<r>/commits/<sha>/check-runs needs --paginate (this repo's head has
~75 check-run rows, the API pages at 30 - an un-paginated poll watches a MOVING window and
can say "all concluded" with 17 jobs queued; a success count that DECREASES between ticks is
the tell). gh pr checks is TSV: the status is column 2. Two pushes minutes apart
SELF-CANCEL the intermediate head (concurrency cancel-in-progress: true - see
.github/workflows/test-coverage-gate.yml:9-11): a head showing failure + mass-cancel means
read gh run view <id> --json conclusion first and judge the NEWEST head; never re-run failed
jobs to launder a self-cancel. A green head identity here is 67 success / 0 failure / 1
neutral (Trivy) / 7 skipped.

STOP AND ASK (evidence, never self-resolve): VLM pick at M2; go-live sign-off 3.1; setting
S2_MAX/S3_MIN (owner sets before step 2.2); any change to a D# or S#; anything touching
dgx-inference; any Brev spend; any agent-gpu refusal or VRAM squeeze; reasoning-LLM R10 (note
2026-09-27: the owner ruled there is no separate LLM - the shipped path registers exactly one
op, required={"vlm_assess"} at backend/ai_contract/providers.py:184-188, and the bigger-VLM
survey is how R10 gets absorbed rather than spent - any proposal to ADD a second model is a
stop-and-ask); the two owner-queued measurement findings (item 28's probe budget - 700
clears both builds; item 30's S3 floor midpoint - 117 above / 160 equal / 0 below); picking up
any 12-postponed-roadmap.md item; PRs, merges. PUSH: standing permission (owner ruling
2026-09-25, ledger open-issue 11) - after each committed task, git push github
feat/vss-gaming-gpu-profile without asking. Attribution: end every commit message with
Co-Authored-By: Claude Code <noreply@anthropic.com>; end every PR description with
the Generated-with-Claude-Code line.

REPORT per work item (0-3), not per milestone anymore: proven with S#s where applicable,
failed and why, next, decisions I owe. Aggregate metrics only.
```
