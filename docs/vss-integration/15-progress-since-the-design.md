# 15 — Progress Since the Design (2026-09-23 → 2026-10-03)

What has shipped, what was measured, and what changed since the design was approved. The design is
[`2026-09-23-vss-gaming-gpu-profile-design.md`](../superpowers/specs/2026-09-23-vss-gaming-gpu-profile-design.md)
(the spec). The execution record is
[`2026-09-23-vss-gaming-gpu-ledger.md`](../plans/2026-09-23-vss-gaming-gpu-ledger.md) (the ledger).

> **Currency — 2026-10-03.** Written at repo tip `5c605e1d` (`main` through PR #6767 plus one docs
> commit). Every **[V]** below was read or run at that tip in this session. On a number that comes
> from the ledger or a committed report, **[V]** means I read that line at the tip; the measurement
> itself was taken by someone else and is not re-run here. Measurements dated 2026-10-03 are quoted
> from the working note
> [`2026-10-03-vss-vlm-exercise-handoff.md`](../plans/2026-10-03-vss-vlm-exercise-handoff.md), which
> is untracked at the time of writing (`git status` shows `??`), and are cross-checked against that
> session's score files where the text says so. This page is a status record, not a plan. Line
> anchors rot within a day in this repo: re-run the grep before you quote one.
>
> **Three commits landed after the pin (2026-10-03).** `9f4e65cd` made the assess call greedy
> (`temperature` 0.0, not an unseeded 0.1), `d8482861` deleted the retired Nemotron
> prompt-evaluation harness, and `efa1b586` deleted `tools/nemo_data_designer/` and the `nemo`
> dependency extra (which also lifts the `cryptography` ceiling noted in §6; the upgrade is not
> applied). Everything above §9 is the record at `5c605e1d`: where it says "unseeded 0.1", "a draw"
> or "noise", read it as true at the pin. Line anchors into `backend/services/vlm_client.py` (from
> `:98` on), `backend/evaluation/s_metrics.py` and `backend/evaluation/vlm_replay.py` are as of the
> pin and have since moved. §9 says what changed and gives the new anchors.

## How to read this page

Sources, and how far each is trusted:

1. **Files, commits and tests read or run at the tip.** These carry **[V]** and a path or SHA.
2. **The ledger and committed reports.** Quoted as "the ledger records ...". Rows are identified by
   their title and the commit that added them, never by row number (rows renumber on merge).
3. **Agent-produced digests** of the non-merge commits since 2026-09-18 and of the docs. They quote
   444 commits **[A]**, a figure from digests that are not in the repo. Counting with
   `git log --no-merges --since='2026-09-18 00:00:00 +0000'` gives 437 at `5c605e1d` and 439 at
   `d8482861` **[V]** (a date-only `--since` takes the current time of day; run at about 19:40Z on
   2026-10-03 it gave 435 and 437). No claim here depends on the difference. The digests are a map
   only. This repo has a documented history of agent-invented citations (the ledger row "The M1
   milestone review's biggest finding was two agents inventing code"), so a digest claim appears
   here only after I re-read its file or commit. The claims that did not survive are listed in §8.

Four status words are used, and they are different things:

| Word     | Meaning                                                 |
| -------- | ------------------------------------------------------- |
| shipped  | in `main`, and on the default path                      |
| measured | a number exists, with its conditions stated             |
| accepted | an owner record (**[O]** in the ledger or spec) says so |
| open     | none of the above, or a measured bar is not met         |

**Shipped is not accepted.** The VLM path became the default on 2026-09-27. No owner acceptance of
any measured reading is recorded, and S2 and S3 miss their bars in every corpus-scale reading.

**In one paragraph.** In ten days the design went from an approved spec to a shipped default. The VLM
path (`4bfd6fa4`, #6681, 2026-09-27) turns each detector batch into one constrained verdict call,
stores it as an `EventVerification`, and shows it in the UI. The legacy text-LLM and enrichment tier
were then deleted (R8, 2026-09-28 to 2026-09-30). Two measurement layers now exist: an A5500
hardware run (2026-09-28) that read fit and latency, and a synthetic-corpus replay (2026-09-29
onward) that reads S2 and S3. The readings: S1 and S4 pass on the A5500 as recorded; S3 fails its
90% bar by about 54 points in every reading; S2 misses its 5% bar by about 3 points, with
run-to-run noise of a similar size; S5's zero-refusal bar is missed in two of three corpus
readings; and M1 stays open because the notification link has no production caller. (Since the pin
the run-to-run noise is fixed: `9f4e65cd` made the assess call greedy; §9.)

## 1. State of play

### Success criteria S1-S6 and milestones M0-M4

| Item | Bar                                                      | Reading                                     | Status                                   | Evidence                                     |
| ---- | -------------------------------------------------------- | ------------------------------------------- | ---------------------------------------- | -------------------------------------------- |
| S1   | peak ≤ 20.4 GiB, 24 GB-class only (F13)                  | A5500: 9,606 MiB; 9,826 MiB at slot ceiling | measured, PASS; not accepted             | ledger `4dbd8bb3`, `ec1ac051` (n1)           |
| S2   | ≤ 5% (F14 [O])                                           | 6.7%, then 9.1% and 8.6% (n2, n3)           | measured; misses in all three            | `p5a-2026-09-30.md`; handoff (n2)            |
| S3   | ≥ 90% (F14 [O])                                          | 36.5%, then 36.1% and 34.9% (n2)            | measured; fails by ~54 points            | same; the gap is [C]                         |
| S4   | p95 ≤ 30 s with cold starts, 24 GB-class                 | A5500: p95 16.2 s over 21 requests          | measured, PASS; not accepted             | ledger `1f2921a4` (n1)                       |
| S5   | 0 unparseable; failures reach dashboard and notification | A5500: 0 of 13; corpus: 1, 0, 1 of 450      | partly measured; open                    | ledger; `p5a-2026-09-30.md`; handoff         |
| S6   | conformance green incl. `vlm_assess`                     | `backend/tests/contracts`: 464 passed (n6)  | measured [V]; not accepted               | pytest run 2026-10-03                        |
| M0   | merged, tiers green, eval store at bar                   | met 2026-09-25: #6678 (`a0105b63`)          | shipped; accepted [O]                    | ledger "P0 — phase close"                    |
| M1   | `vlm` mode end to end on the A5500                       | chain ran except the notification link (n4) | shipped; open on one link                | grep at the tip [V]; ledger                  |
| M2   | the owner picks the VLM                                  | Qwen3-VL-8B, "for now" (2026-09-28) (n5)    | shipped; pick accepted, closure open [O] | ledger "M2 PROVISIONAL PICK"                 |
| M3   | go-live holds 14 days                                    | no start recorded                           | open, not started [?]                    | absence of a record                          |
| M4   | RT-VLM conformance, fit record, Delta                    | deferred; `RTVI_VLM` adapter is Phase 4     | open, deferred                           | `backend/ai_contract/provider.py` `RTVI_VLM` |

The bar wording is the spec's (S1-S6 at `:83-88`, M0 at `:436`, M1-M4 in §8 of the spec). The F14
numbers are the ledger's.

**Notes on the table.**

1. **A5500 conditions.** From the ledger rows "A5500 RUN, 8B PRIMARY", "A5500 RUN, CONTINUED" and
   "A5500 S4 RE-TAKEN", **[V]** as read. S1: 9,606 MiB peak on the corpus run against a 20,890 MiB bar
   (20.4 GiB is 20,889.6 MiB **[C]**); 9,722-9,826 MiB at a full-slot ceiling; 9,662 MiB during the S4
   re-take. Resident: `yolo26` and `reid` in `ai-gateway`, plus `ai-vlm`; the backend's torch is
   CPU-only; 37 of 37 layers on the GPU. The GB300's 9,056 MiB (handoff) is a fit reading, not S1
   (F13). S4: p95 16.2 s over 21 requests on the shipped verdict path, against 21.7 s before the
   1,024-token budget, native boxes and the image cap; first request after a cold restart 13.3 s. S5:
   0 of 13 refused for the 8B, and 8 of 13 for the 4B pair. None of these has an owner acceptance.
2. **Conditions for every S2/S3 number, stated first.** The readings are the committed P5a baseline
   (14 of 209 false alarms, 88 of 241 hits; intervals [4.0-10.9] and [30.7-42.8]) and the two
   2026-10-03 runs (19 of 209 [5.9-13.8] and 87 of 241 [30.3-42.3]; 18 of 209 [5.5-13.2] and 84 of
   241 [29.1-41.1]). The truth is _declared_ by the sampler and unverified. The owner's 60-still
   audit found scene, people and conditions truth error 0.0% [0.0-6.0], and the declared prop missing
   in 1 of 15 **[V]** (`p5a-2026-09-30.md`, section "Audit"). The VLM is given each event's declared
   subjects and props as detections at confidence 1.0, an "ideal detector" (decision A6). It gets no
   specialist context. The stills are generated, not Foscam near-IR. These are accuracy figures
   only. The S2 denominator is 64 plain benign stills plus 145 hard negatives (batch 5 was steered
   to five hard-negative scenarios), so S2 is a hard-negative-weighted false-alarm rate, not a
   deployment rate **[V]** (the report's own slices: benign 0.0% at n=64, hard negatives 9.7%
   [5.8-15.6] at n=145). The S3 denominator is 196 threat plus 45 suspicious stills.
3. **F14's rule** (ledger section "Open issues & owner-decision queue", the F14 entry): one
   operating point; report n and a 95% Wilson interval; **pass** means the point estimate meets the
   bar; label **marginal** when the interval straddles it **[V]**. By that rule the baseline S2 is
   marginal (6.7% against 5%, interval straddles). Both 2026-10-03 S2 intervals lie wholly above 5%,
   which F14 does not give a name; it is simply not a pass. S3's per-item floor is the declared
   risk-band _midpoint_ run through the shipped banding (`floor_for_expected_score` in
   `backend/evaluation/levels.py`), not the declared minimum; the ledger queued that mismatch as an
   open owner question and it is unchanged **[V]**. The corpus has no zero-floor incident, so "all"
   equals "excluding zero floor" in every reading **[V]**. The older `10/20` S3 reading (the ledger
   row "A5500 RUN, CONTINUED") is another harness and corpus, a 38-item detections-plus-images set on
   the A5500; it is not a predecessor of the 450-item numbers **[V]**.
4. **The M1 gap, precisely.** At the tip `NotificationFilterService.should_notify`
   (`backend/services/notification_filter.py:35`), `AlertRuleEngine.evaluate_event`
   (`backend/services/alert_engine.py:166`) and `NotificationService.deliver_alert`
   (`backend/services/notification.py:633`) have no non-test caller; the only other hits are
   docstring examples, the examples in `backend/services/AGENTS.md` and an unrelated route
   function (`backend/api/routes/ai_audit.py:193`) **[V]** (`grep -rn` over `backend/` minus tests,
   `.py` and `.md`). The browser hook's `showSecurityAlert`
   (`frontend/src/hooks/useDesktopNotifications.ts:371`) has one non-test caller, the wrapper at
   `frontend/src/hooks/useIntegratedNotifications.ts:247`, and that wrapper's own
   `showSecurityAlert` (`:225`) is never called outside tests **[V]** (`grep -rn` over
   `frontend/src`, `.ts` and `.tsx`, minus tests).
   `VlmAnalyzer` persists the event and broadcasts it (`_broadcast`,
   `backend/services/vlm_analyzer.py:765`), so the dashboard half of S5 is wired and the
   notification half is not.
5. **Flip condition (iii)** (ledger row "M2 PROVISIONAL PICK") reopens the pick if "post-item-19
   corpus S3 < `S3_MIN` 90%, or candidate C's `uncertain` rate ... proves to be a real hedging
   prior". The first arm now has a reading below 90% on a corpus. The second arm has a reading
   against it: `uncertain` is 2, 6 and 8 of 450 (0.4%-1.8%) **[V]**, not the 0.231 of the 13-item
   set. Whether a declared-truth synthetic corpus is the corpus the condition names is recorded
   nowhere I could find **[?]** (owner).
6. **S6** was run for this page: `uv run python -m pytest backend/tests/contracts -n 4` gives 464
   passed: 410 in `backend/tests/contracts/ai_providers`, including 13 in
   `backend/tests/contracts/ai_providers/test_conformance_vlm.py` **[V]** (collected with
   `--collect-only`; the figure is the same at `efa1b586`, §9). The ledger recorded 646 at Phase
   1.1, before R8 retired provider surfaces; I did not diff the two collections, so the cause of
   the drop is **[A]**.

### Who accepted what

Owner records **[O]**, by date, as they appear in the ledger, the spec or the repo:

- **2026-09-25, M0.** The owner enabled automerge on #6678 at 12:42:37Z; it merged at 13:02:23Z
  (ledger "P0 — phase close").
- **2026-09-25, F10-F14.** F10: the legacy path is unsupported and S2/S3 are fixed bars. F11:
  specialists are resident and their outputs reach the VLM. F12: face and plate picks; licenses are
  not a criterion. F13: Phase 2 may run before M1 closes, and S1/S4 are read only on 24 GB-class
  hardware. F14: "use 5% and 90%, record them in the ledger."
- **2026-09-26, re-ID.** "full swap. ignore previous architecture. we do not have to support
  backwards compatability."
- **2026-09-28, M2.** "lets go with Qwen3-VL-8B for now. we can revisit later if needed."
- **2026-09-29 and 2026-09-30, R8.** Picked up early, with the original 14-day trigger reversed;
  backwards compatibility not required; `PIPELINE_MODE=legacy` must raise; the A5500 ruled out for
  the work (`docs/vss-integration/12-postponed-roadmap.md`, under the heading "R8. Post-go-live
  deletion", the "Picked up" blockquote). Two further rulings on
  2026-09-30 (date inferred from the commit `13e7250d` that added the ledger row, which carries none)
  split the table retirement and chose deletion for the frontend panels (ledger row "S4/S5
  UNBLOCKED BY TWO OWNER RULINGS").
- **Synthbench.** The P1 picks, approved 2026-09-28 (spec rev 2); the `tierb-v0` taxonomy sign-off,
  2026-09-29 (`synthbench/taxonomy/tier_b_v0.yaml:10`); P5a decisions A1-A7, 2026-09-29; stopping
  the Cosmos replay at 321 of 450 items, 2026-09-30; waiving the clip pilot gate (C13), 2026-09-30
  (`1eeda952`).
- **2026-10-01, merges.** After merging #6754 the owner delegated "you have authority to merge PRs
  as needed." It covers merging only. The who/when acceptance blanks for CI classes B, C, D, E and F
  are still blank (§6).

Recorded as **not accepted**, because no owner record exists: the S1 and S4 readings; the S2 and S3
readings, and with them whether the 8B pick stands; the notification half of S5; M1; M3 and M4; clips
as anything but an unscored asset; the 4B pair as a fallback (it fails S5); and Brev spend (a
stop-and-ask: the ledger records that no Brev VM was started, so the hardware matrix has no
reading). The A5500 rows of the ledger contain the word "accept" zero times **[V]** (`grep -c`).

### What the design said, and what is built

| As designed, or as first built                                | At the tip                                                |
| ------------------------------------------------------------- | --------------------------------------------------------- |
| `legacy` "stays selectable" until R8 deletes it (spec §2)     | `PIPELINE_MODE=legacy` raises at boot (n1)                |
| Face and plate in the backend; re-ID and threat in Triton     | re-ID leg in the backend; threat is not a specialist (n2) |
| S2 and S3 owned by the owner, marked `[?]`                    | set by F14; the spec rows were never back-edited (n3)     |
| Worst-case prompt ~12.2K tokens (4 images, ~6K text, ~1K out) | a full 16,384-token slot; the client fits to it (n4)      |
| Verdict budget 400 / 700 tokens, pixel boxes (first client)   | 1,024 / 1,088; `bbox_2d` boxes; provenance stamped (n5)   |
| Synthetic media run "live end to end" (synthbench D1)         | P5a is a direct-call replay; P5b is not built (n6)        |
| Clips are kept for a video VLM (C1)                           | a 459-clip round; no consumer; `VlmClient` refuses video  |

Notes **[V]**:

- (n1) `validate_pipeline_mode` at `backend/core/config.py:1062`; the only live construction point,
  `build_pipeline_analyzer` in `backend/services/pipeline_factory.py` (a second, uncalled one sits
  in `analyze_vlm_batch`, `backend/services/vlm_analyzer.py:823`: `grep -rn analyze_vlm_batch`
  over `*.py` finds only its definition); and the test
  `backend/tests/unit/core/test_config_pipeline_mode_hard_raise.py` (7 passed).
- (n2) The spec row is at `:119`; the Triton set is at `ai/gateway/residency.py:60`; the re-ID call
  is at `backend/services/vlm_specialists.py:723` (the import of `osnet_loader` is at `:705`).
- (n3) Spec `:84-85`; code `backend/evaluation/s_metrics.py:32-33`.
- (n4) The compose erratum is at `docker-compose.prod.yml:196`; the fit is `_fitted_prompt` at
  `backend/services/vlm_client.py:676`.
- (n5) `backend/services/vlm_client.py:91`, `:97` and `:252`.
- (n6) `backend/evaluation/vlm_replay.py:121`, and the `COMMANDS` tuple at `synthbench/cli.py:43`.

## 2. The VLM path as built

The flow, each hop read at the tip **[V]**: a still lands in the camera root; the file watcher picks
it up; YOLO26 (Triton inside `ai-gateway`) detects; the batch aggregator fires `wake_ai_vlm()` once,
when a batch opens (`backend/services/batch_aggregator.py:674-676`), and hands the batch on when it
closes; `select_key_frames` picks at most four distinct stills; the specialist stage adds three
short text lines; `VlmClient.assess` makes one constrained call to llama.cpp;
`apply_verdict_invariants` applies the §6 rules; the analyzer writes an `Event` and an
`EventVerification` in one transaction and broadcasts the result. Every failure becomes
`verification_failed` with a NULL score and level, never a default score.

Each piece below names the commit that shipped it and the file read. The work of 2026-09-25 to
2026-09-27 reached `main` twice: as squashes (#6681 `4bfd6fa4`, #6684 `e33c44c6`) and as individual
commits through the merge of #6685 (`418dc032`); the work of 2026-09-28 came in through #6698
(`8df51918`) **[V]** (merge ancestry). The SHAs below are the individual commits unless a squash is
named.

- **`ai-vlm` serving.** llama.cpp `b7972`; Qwen3-VL-8B-Instruct `Q4_K_M` plus `mmproj` `Q8_0`
  (5,027,784,800 and 752,289,728 bytes, read with `ls -l`); `CTX_SIZE` 32,768 over 2 slots, 16,384
  per slot; KV `q8_0`; each still capped at 1,280 vision tokens; idle sleep after 300 s; behind
  compose profile `vlm`. One Dockerfile builds `sm_103` (GB300, aarch64) and `sm_86` (A5500, x86)
  through `CUDA_ARCHITECTURES`. Shipped: the Dockerfile in `a0105b63`; the service in `8d39f1b6`
  (2026-09-25); the 8B default in `54141d9c` (2026-09-27); the KV flags forwarded in `7b75f5bd`
  (2026-09-28). Verified at `docker-compose.prod.yml:134`, `:154-155`, `:179-180`, `:189`,
  `:205-206`, `:222-223`, `:236` and `ai/vlm/Dockerfile:46`, `:64`, `:119`.
- **`VlmClient`.** One chat call: `response_format` `json_schema`, base64 stills, `temperature` 0.1
  with no seed at `5c605e1d` (greedy since `9f4e65cd`, §9), one retry at 0.0, `max_tokens` 1,024
  (probe 1,088). An enforcement probe runs once
  per client instance and caches only ENFORCED (`:240`). The breaker is `ai-vlm`; truncation and
  context overflow are budget errors kept off it. The prompt is fitted to the slot, boxes go out as
  `bbox_2d` on a 0-1000 scale, and provenance is stamped from `/props`, not model-written. Shipped:
  `9b1b9899` (2026-09-25); hardening in `01080b51`, `bdb55335`, `d1e279fd`, `6106ea98`, `7141cad0`
  (2026-09-27) and `5b929a52`, `a2d8c710`, `235a9c0f`, `51b1b9b0` (2026-09-28). Verified at
  `backend/services/vlm_client.py:85`, `:91`, `:97`, `:107`, `:115`, `:134`, `:144`, `:159`, `:252`,
  `:676`, `:796`, `:805-807`, `:946`, `:981` (anchors as of `5c605e1d`; §9 gives the shift), and the
  probe machinery in `backend/services/constrained_decoding.py`.
- **Key-frame selector.** At most 4 distinct stills, one per file, strongest first; no
  temporal-diversity term. Shipped `9b1b9899`; one-per-file rule `01080b51` (2026-09-27). Verified at
  `backend/services/key_frame_selector.py:37` and `:73`.
- **Analyzer and ladder.** `VlmAnalyzer`: `rejected` clamps the score to the LOW band's top and logs
  the clamp; the level is always derived by `SeverityService`; a failed call stores
  `verification_failed`. One live construction point returns it (`build_pipeline_analyzer`); a
  second, uncalled one sits in `analyze_vlm_batch` (`backend/services/vlm_analyzer.py:823`). Shipped
  `9b1b9899`; factory and default flip `4c0f12a1` (2026-09-26). Verified at
  `backend/services/vlm_analyzer.py:255`, `:344`, `:690`, `:707`, `:765`, `:823` and
  `backend/services/pipeline_factory.py`.
- **Contract op.** `vlm_assess` is available on `per_model_server` and `fake`, not on `gateway`.
  `VlmVerdict` has no `risk_level` field and forbids extra keys. Both VLM provider ids register
  with `deployed=False`. Shipped `030b378a` (2026-09-25). Verified at
  `backend/ai_contract/operations.py:81`, `backend/services/vlm_verdict.py:55`,
  `backend/ai_contract/providers.py:178-195` and
  `backend/ai_contract/schemas/vlm_assess.request.json`.
- **Storage and API.** An `event_verifications` table; a `verification` object on REST and
  WebSocket event payloads; a `?verdict=` filter on `GET /events` and search. Shipped: table and
  payloads `a0105b63` (#6678); filter `1c575e21` (2026-09-26). Verified at
  `backend/models/event_verification.py:64` and `backend/api/routes/events.py:283`.
- **Residency set.** The gateway accepts only `GATEWAY_MODEL_SET=vlm`: `yolo26` and `reid`, plus
  `threat` when `GATEWAY_ENABLE_THREAT` is truthy (default false). Triton keeps
  `--model-control-mode=none`, and the repository is pruned at entrypoint step 0d. Shipped `c271d5e7`
  (2026-09-25); the `full` set removed by `3b73b9b6` (2026-09-30). Verified at
  `ai/gateway/residency.py:52`, `:60`, `:69`, `ai/gateway/entrypoint.sh:118`, `:147` and
  `docker-compose.prod.yml:387-388`.
- **Frontend verdict surfaces.** `VerdictBadge` (five states; `verification_failed` is red,
  `rejected` is muted but listed), verdict filter chips, `EventVerificationSection` in the event
  modal, null-safe risk rendering. Shipped `677a40f6`, `ca6d734c` (2026-09-26), `4bc16ebe`,
  `058ac533` (2026-09-27). Verified at `frontend/src/components/common/VerdictBadge.tsx:88` and
  `frontend/src/components/events/EventDetailModal.tsx:913`.
- **Host integration.** Running the chain on the A5500 exposed defects in the container path, all
  fixed on 2026-09-28: specialists could not load in the prod backend (`f7eb2b87`); YOLO26 exported
  the wrong head (`54e92736`); the gateway died at import on Python 3.12 (`eb7de160`); the Triton
  re-ID export was not OSNet-AIN (`08d5ceb9`); KV quantization never reached llama-server
  (`7b75f5bd`); the file watcher was blind under SELinux (`96d5ed60`, `5efd7075`). Verified at
  `backend/Dockerfile:134` (`--extra face`), `ai/gateway/export/export_yolo26.py` and
  `backend/services/file_watcher.py`.

`54141d9c` is dated 2026-09-27 23:14 (UTC-04:00) and cites an owner ruling that the ledger dates
2026-09-28 **[V]**.

**What the shipped path does not do yet** (each read at the tip **[V]**):

- **A plain `docker compose up` starts a backend that dials a VLM it did not start.** `ai-vlm` is
  behind profile `vlm` (`docker-compose.prod.yml:154-155`) and the backend defaults to `vlm`
  (`:484`); the backend dials `AI_VLM_URL` (`:552`). `setup.py deploy` names the profile (`_ModePlan`
  at `setup_lib/deploy_phases.py:66`, `_MODE_PLANS` at `:101`), so the scripted route brings it up;
  the manual route is `--profile vlm`, documented at `docker-compose.prod.yml:133` (and in
  `llms.txt:36`, `:60`, `:162`).
- **The release artifact cannot serve the VLM path.** `docker-compose.ghcr.yml` defines no `ai-vlm`
  service (its services are `postgres`, `redis`, `ai-gateway`, `backend`, `go2rtc`, `frontend` and the
  monitoring stack), and `.github/workflows/deploy.yml` publishes only `backend` and `frontend`. The
  workflow calls the missing service "a reported publish gap, owner-adjudicated" (`:32`).
- **Video is refused.** A clip-sourced detection row carries the clip's path
  (`backend/services/detector_client.py:1173-1174`), the extracted JPEGs are deleted after detection
  (`backend/services/pipeline_workers.py:746`), and `VlmClient` raises `VlmImageError` for any
  suffix outside `IMAGE_MIME_TYPES` (`backend/services/vlm_client.py:463-487`), so a clip-sourced
  batch becomes `verification_failed`. Clips cannot reach `vlm_assess`. The client's comment says
  ffmpeg is not in the backend image; `backend/Dockerfile:170` installs it in the prod stage, so that
  sentence is stale.
- **Without detections the VLM declines to judge.** The P5a probe: with `Detections: []` the shipped
  prompt made both Qwen3-VL-8B and the flagship answer `uncertain`, risk 0, on 5 of 6 incident and 4
  of 5 benign stills (`docs/benchmarks/synthbench/p5a-probes.md`, section "What changed the
  design"). The product VLM verifies detector candidates; it is not a scene reasoner.
- **A verdict is a draw; the input does not determine it (the record at `5c605e1d`; fixed by
  `9f4e65cd`, §9).** At the pin `temperature` was 0.1 with no seed
  (`backend/services/vlm_client.py:796`, introduced in `9b1b9899` (2026-09-25), on `main` via the
  squash `4bfd6fa4` (2026-09-27)). 0.0 was used for the §6 retry (`:805-807`, which re-sends after a
  transport error, a non-200 reply or a schema-invalid reply), for the enforcement probe (`:351`)
  and for the wake ping (`:959`); the verdict draw itself was 0.1. `grep -i seed` over
  `vlm_client.py`, `vlm_analyzer.py` and `vlm_verdict.py` returned nothing **[V]** (read from
  `git show 5c605e1d:<path>`). §3 puts a number on what that cost.
- **The provider registry understates deployment.** Both VLM provider ids register with
  `deployed=False` and a comment that "the honest deployed flip rides M2"
  (`backend/ai_contract/providers.py:178-195`). The registry declares the op's path as
  `/vlm/chat/completions` (`backend/ai_contract/operations.py:84`), while the client calls the
  engine at `/v1/chat/completions` (`backend/services/vlm_client.py:85`), so the registry cannot be
  used to derive the client's URL.
- **Health gates the detector, not the VLM.** `yolo26` is `critical: True` and `ai-vlm` is
  `critical: False` (`backend/api/routes/system.py:5111`, `:5120`); `ai-vlm` is registered on the
  degradation manager as non-critical with push-only health (`backend/main.py:1150`).
- **The alerts page still shows a NULL score as a low one.** `AlertsPage.tsx` and
  `AlertCameraGroup.tsx` coalesce `risk_score` to 0 and carry no `VerdictBadge`
  (`frontend/src/components/alerts/AlertsPage.tsx:116`, `:260`, `:317`;
  `frontend/src/components/alerts/AlertCameraGroup.tsx:74`). The ledger row on the null-score display
  problem queued this on 2026-09-27; it is unchanged.
- **The currency banners cite a line that moved.** The banners in `README.md`, `AGENTS.md` and
  `00-context.md` cite line 578 of `docker-compose.prod.yml` for the default flip. It was line 578
  when the banners were written (`6798ee59`) and moved to `:484` when R8 S2b (`602379e2`) deleted the
  `ai-llm` blocks above it **[V]** (`git show <sha>:docker-compose.prod.yml`). The currency gate
  matches phrases, not line numbers, so it stays green while the anchor rots.

**Sizing, as recorded.** A5500: KV pool 2,448 MiB at `q8_0` against 4,608 MiB at f16 (the f16 figure
was the real pool until `7b75f5bd`, because the image never forwarded the KV flags); load from a
dropped page cache 2.2 s; first request after idle sleep 13.1-14.5 s; the heaviest corpus batch was
7,443 tokens, not the spec's ~12.2K (ledger rows `4dbd8bb3`, `ec1ac051`, `1f2921a4` **[V]**). GB300:
the shipped config read 9,056 MiB actual on 2026-10-03 (handoff; not S1, F13), and the P5a probe read
11,216 MiB on 2026-09-29 (`docs/benchmarks/synthbench/p5a-probes.md:45`). The two GB300 readings
differ by 2,160 MiB, which is exactly the difference between the two KV pool figures above
(4,608 − 2,448) **[C]**; that the probe ran an f16 pool is an inference, not a reading **[?]**.

## 3. Measurement infrastructure

### Eval store and replay harness (Phase 2, 2026-09-27)

At `5c605e1d` `backend/evaluation/` held the VLM measurement code that existed before synthbench,
beside the retired Nemotron prompt-evaluation harness (`harness.py` and six siblings, deleted in
`d8482861`; §9). `EvalStore` (`backend/evaluation/eval_store.py:41`) is an off-repo SQLite store of
frozen items, runs and results; a guard refuses media paths inside the checkout or a capture root
(D10). Generation 2 (`build_gen2`, `79087e3c`) carries the specialist prompt text, because
generation 1 had none. `AssessInput.specialist_outputs` is the one carrier
(`backend/evaluation/assess_input.py:43`, `6737c750`). `run_replay`
(`backend/evaluation/vlm_replay.py:209` at the pin, `b3ef67d1`) feeds each frozen item through the
shipped `VlmClient`, sequentially, and writes results. `s_metrics.py` computes S2, S3 and S5 with an
in-repo Wilson interval and prints the F14 bars beside the rates as `S2_MAX_PCT = 5.0` and
`S3_MIN_PCT = 90.0` (`backend/evaluation/s_metrics.py:32-33` at the pin). Nothing enforces them: the
file says so in its own comment, and pass or fail is a reader's judgement under F14 **[V]**.

The Phase 2 bake-off (A Qwen3-VL-4B, B Nemotron-Nano-12B-v2-VL, C Qwen3-VL-8B) ran on 13 stock
items; the ledger row "M2 PROVISIONAL PICK" says the corpus "ordered nothing", and the spec header and
design (`docs/superpowers/specs/2026-09-23-vss-gaming-gpu-profile-design.md:14`, `:304`) and the
report (`docs/plans/2026-09-27-vss-phase2-bakeoff-report.md:291`, "resource shape and build
dependency") say the pick was made on resource shape, not accuracy **[V]**. The report is
`docs/plans/2026-09-27-vss-phase2-bakeoff-report.md`. Its refusal counts were taken at the old
700/400 budgets and are not reproducible on current code (§1, design table).

### Synthbench, P0 to P5a

`python -m synthbench` is a separate top-level package; only `synthbench/run/` and
`synthbench/score/` may import `backend` (`synthbench/AGENTS.md:35`) **[V]**. Its commands are the
`COMMANDS` tuple at `synthbench/cli.py:43`: `sample`, `check`, `render`, `camera`, `triage`,
`report`, `clip`, `corpus`, `doctor`, `export`, `audit`, `replay`, `score` **[V]**. Exit codes: 0
done, 1 fix the request, 2 stop and ask the owner. The phases come from the parent spec's table
(`docs/superpowers/specs/2026-09-27-synthetic-benchmark-generation-design.md`, phase rows at
`:586-594`).

| Phase | What                                                  | Commits                                                    | State                       |
| ----- | ----------------------------------------------------- | ---------------------------------------------------------- | --------------------------- |
| P0    | Foscam filename to capture time; `camera_timezone`    | `b265d147` (#6683, 2026-09-27)                             | shipped                     |
| P1    | model bake-off; FLUX.2 [dev] stills, H3 turbo clips   | `e316ad79` (#6697, 2026-09-28)                             | done; picks approved [O]    |
| P2    | contract, corpus store, taxonomy, quota sampler       | `27d87993`, `8f45a29a`, `e4d1141f`, `6af0b86e`, `84a0e5e1` | shipped                     |
| P3    | agent-driven generation: render, camera, triage       | `0e6d3100`, `237363e7`, `5c84dd3c`; accepted `2e2186e7`    | shipped; two blanks (n1)    |
| P4    | independent verifier                                  | none                                                       | not built; audit stands in  |
| P5a   | VLM replay scoring: export, replay, audit, score      | `c2a1566b`, `e175c6c7`, `fe8d50f1`, `4b653251`, `502df6e2` | shipped; baseline committed |
| P5b   | live pipeline instance                                | none                                                       | not built, deferred [A]     |
| clips | H3 clip rounds: sample, check, render, triage, report | `01df30cc`, `dcca5499`, `1dfadda5`, `5e32d9ba`, `0be8b3f3` | supply only; unscored       |

Notes **[V]**: (n1) the P3 acceptance doc records a pass and leaves two owner-fill blanks
(`docs/benchmarks/synthbench/p3-acceptance.md:30` and `:57`). P1's
report is `docs/benchmarks/synthbench/p1-bakeoff.md`: a VLM judge failed calibration as a render gate
(agreement 55%, Cohen's kappa 0.06, n=123). P4 has no command in `COMMANDS`. P5a landed in #6732
(`502df6e2`, 2026-09-29).

**Corpus `tierb-v0`**, as read on 2026-10-03: 460 events drawn (pilot-1 10, batch-1 50, batches 2-5
100 each), 459 `ready` and 1 `failed` (`B-batch-4-063`, scenario `pet_activity`). Ready labels:
incident 241, benign 209, ambiguous 9. The taxonomy has 32 scenarios: 14 threat, 7 benign, 5 hard
negative, 5 suspicious, 1 ambiguous. Taxonomy sha256 `fb8de9c6176d76aa...` (full value in
`corpus.json`), renders 1280x720, exported stills 1920x1080 **[V]** (parsed `index.jsonl`,
`corpus.json` and `synthbench/taxonomy/tier_b_v0.yaml`; the handoff adds 956 `jpg` stills, 481 `mp4`
clips and 2.6 GB). The camera stage's parameters are committed defaults
(`synthbench/generate/camera/default-v1.json`), never fitted to Foscam footage. Scenario labels
follow placement and declared risk band: suspicious scenarios are labelled `incident` with lower
bands, which is why S3 has 45 suspicious stills in its denominator
(`synthbench/taxonomy/tier_b_v0.yaml:15`).

**Clips lane.** The `clips-1` round has 459 clip events. Their latest status per event, read from
`clip-index.jsonl`: 164 ready, 80 failed, 10 rendered and awaiting triage, 205 prompted and not yet
rendered **[V]** (a snapshot; the round was not finished). The clips design keeps clips for a video
VLM (C1) and scores nothing; the pilot gate was built in `1dfadda5` (2026-09-30 01:09), the owner's
waiver was recorded 33 minutes later in `1eeda952` (01:42), and the gate code was removed at 37
minutes in `b74ca19d` (01:46) **[V]** (`git show -s --format=%ad`). No clip audit is designed or
required (C13) **[A]**: the absence was not read from an audit log, because `/synthbench/audits` is
not mounted in the sandbox. The note `docs/synthbench/h3-prompt-notes.md` records that H3 follows a
crossing subject by moving the camera (a runner crossing the frame: 13 finished, 0 ready), counted
mid-round on 2026-10-01 and marked "seen once". No doc names a video-VLM candidate
or a clip bar **[?]**.

### The committed baseline and the three readings of 2026-10-03

The committed P5a report is `docs/benchmarks/synthbench/p5a-2026-09-30.md` (`502df6e2`, scored at
`ca73f1ef`, replay `20260930T014002Z-qwen3-vl-8b`, 18 minutes 43 seconds). On 2026-10-03 the same
450 sets were replayed twice more through the same code, in the exercise sandbox, against the 8B
served from a fenced `agent-gpu` container on the GB300.

| Reading                  | S2 (false alarms of 209) | S3 (hits of 241)       | Refused | `uncertain` |
| ------------------------ | ------------------------ | ---------------------- | ------- | ----------- |
| committed, 2026-09-30    | 14 = 6.7% [4.0-10.9]     | 88 = 36.5% [30.7-42.8] | 1       | 2           |
| run 1, 2026-10-03 13:12Z | 19 = 9.1% [5.9-13.8]     | 87 = 36.1% [30.3-42.3] | 0       | 6           |
| run 2, 2026-10-03 13:30Z | 18 = 8.6% [5.5-13.2]     | 84 = 34.9% [29.1-41.1] | 1       | 8           |

Run 1 is replay `20261003T131219Z-qwen3-vl-8b` scored as `20261003T133003Z`; run 2 is
`20261003T133050Z-qwen3-vl-8b` scored as `20261003T134742Z`. The counts, intervals and refusals come
from each score's `metrics.json` **[V]** and match the handoff. Run 2's refusal is `B-batch-4-012`,
whose reasoning reads "vlm verdict reply hit its token budget" (the handoff names the error
`VlmTruncatedError`, `stop='length'` at 1,024 tokens); it is reported as unmeasured, not as a
verdict **[V]**.

**Identity.** All three readings share the export labels sha256 (`3a9b16e3...c847d`, equal to the
committed report's), build `b7972-e06088da0`, the shipped prompt, `max_tokens` 1,024, a 25 s read
timeout and the enforcement probe on **[V]**. The weights are `Qwen3VL-8B-Instruct-Q4_K_M.gguf`:
the sandbox copy hashes to sha256 `67d1659b...e9e2`, the committed report's value **[V]** (I
re-hashed it and matched). That does not show what the fenced `agent-gpu` container served on
2026-10-03: both 2026-10-03 score files record `identity.replays[].weights` as `unrecorded`, so
nothing in the scores or `run.json` ties the served file to that hash, and the same-weights claim
for those runs rests on the handoff's "owner-verified against vss1" **[O]**. The two 2026-10-03
`run.json` files record commit `5c605e1d`. None of the 13 files in or adjacent to the measured path
changed between `ca73f1ef` and `5c605e1d`: `git diff --numstat ca73f1ef 5c605e1d --` over
`vlm_client.py`, `vlm_verdict.py`, `vlm_analyzer.py`, `vlm_specialists.py`,
`key_frame_selector.py`, `vlm_replay.py`, `s_metrics.py`, `levels.py`, `assess_input.py`,
`label_import.py`, `ai/vlm/Dockerfile`, `synthbench/run/replay.py` and `synthbench/export/vss.py`
prints nothing **[V]**. Not all 13 are on the replay path itself. `replay_item`
(`backend/evaluation/vlm_replay.py:121`) calls `client.assess` directly and never imports
`vlm_specialists` or `vlm_analyzer`; `key_frame_selector` enters only as the `MAX_KEY_FRAMES`
constant that `vlm_client` imports (it caps the image-token estimate); `synthbench/export/vss.py`
and `ai/vlm/Dockerfile` sit upstream, in export and in serving **[V]** (the import lines at the
pin). Since the pin three of the 13 have changed: `vlm_client.py` (`9f4e65cd`; §9), and
`s_metrics.py` and `vlm_replay.py` (`d8482861`, comments and docstrings only; §9). Both 2026-10-03
runs bypassed the renderer check by owner direction (`run.json` field `renderer_check`):
`synthbench replay` refused from the sandbox because `systemctl` is absent, so a scratch driver ran
`execute()` minus `renderer_stopped`; that driver is not in the repo (handoff Addendum 2) **[V]**.

**Noise.** Over the three readings the S2 false-alarm count is 14, 19 and 18 (mean 17.0 = 8.1%,
sample sd 2.6), and the S3 hit count is 88, 87 and 84 (mean 86.3 = 35.8%, sample sd 2.1) **[C]** (n=3:
a rough band, not an interval). Both metrics fail their bars in every reading. Between the two
same-session runs only 278 of 450 items (62%) returned an identical verdict and score. Of the 449
items scored in both runs, 164 changed score (123 of them by 10 points or more, the largest by 95)
and 51 changed risk level; counting the one refusal in run 2 (`B-batch-4-012`, NULL score and level)
as a change gives 165 and 52 **[V]** (recomputed from the two replays' rows in the eval store, with
`score_to_level`). The benign false-alarm sets overlap poorly (13 items in both runs, 6 only in run
1, 5 only in run 2; Jaccard 13/24 = 0.54 [C]);
the incident hit sets overlap better (76 in both, 11 and 8 in one only; Jaccard 76/95 = 0.80 [C])
(handoff Addendum 3). All of the S2 rise from 14 to 19 sits in the three hard-negative scenarios
(`power_tools_at_night` 5 to 8, `hooded_jogger` 8 to 9, `flashlight_neighbor` 1 to 2); every plain
benign scenario is 0 in the committed baseline and in run 1 (handoff Addendum 2). In run 2, 2 of the
18 false alarms are `wildlife` stills (plain benign: `B-batch-2-069` at score 30 and `B-batch-3-047`
at 60), a plain-benign S2 of 2 of 64 = 3.1% **[C]**; the other 16 are hard negatives
(`power_tools_at_night` 4, `hooded_jogger` 9, `flashlight_neighbor` 3), read from run 2's
`results.jsonl` **[V]**. The S2 range of 5 items (2.4 points)
compares with a mean gap to the bar of 3.1 points [C]: the noise is the same order as the gap. (This
is the record at `5c605e1d`. The noise is fixed since `9f4e65cd`; §9.)

**Cause.** At `5c605e1d` the shipped assess request sampled at `temperature` 0.1 with no seed, so a
replay was one draw and a live verdict near the medium threshold could flip on a re-run (the code is
in §2). The committed baseline's 14 against the 2026-10-03 runs' 18-19 is within what that allowed; it is not
evidence of a regression, because the 13 files were unchanged between `ca73f1ef` and the pin. The
replay also stores the client's raw score
(`replay_item`, `backend/evaluation/vlm_replay.py:121`) and does not apply
`apply_verdict_invariants`, so in principle it can count a `rejected` benign item as a false alarm
that production would clamp. In the two 2026-10-03 runs all 9 `rejected` verdicts (4 and 5) are
benign items that scored 10 or less, so the clamp would have changed no S2 count **[V]**
(`results.jsonl` of each score).

At 14:16Z the session's runs directory also held replay directories with a `-T0` suffix
(`20261003T134843Z-qwen3-vl-8b-T0`, a 3-item smoke run, and the two full runs named in §9) and no
score for them. They are not reported in this section; they are the temperature-0 replays reported
in §9.

### What the replay cannot say

- **Nothing about the detector or the specialists.** The detections are the declared truth and the
  specialist lines are absent. Specialist context in S2/S3 is unmeasured until P5b exists.
- **Nothing about latency or memory.** The benchmark host is shared (decision A1); those readings
  come from the A5500.
- **Little about deployment rates.** The corpus is hard-negative-weighted on the benign side and
  incident-weighted overall (241 of 450).
- **Nothing about Foscam near-IR.** The stills are generated, then upsampled to 1920x1080 and given
  an uncalibrated camera look.

## 4. R8: the legacy AI pipeline is gone

R8 (retire the legacy text-LLM path, the enrichment tier, their tables and panels) was deferred in
the 2026-09-23 design and picked up early by owner instruction on 2026-09-29 (§1, who accepted what).
Its design is
[`2026-09-28-r8-legacy-retirement-design.md`](../superpowers/specs/2026-09-28-r8-legacy-retirement-design.md)
and its measured scope is
[`2026-09-28-r8-legacy-retirement-scope.md`](../plans/2026-09-28-r8-legacy-retirement-scope.md).
The stats below are `git show --shortstat` at the tip **[V]**.

| Slice | Commit and PR (date)                      | What went                                        | Size                |
| ----- | ----------------------------------------- | ------------------------------------------------ | ------------------- |
| S0    | `6798ee59`, #6714 (2026-09-28)            | nothing: dated banners and a currency gate       | docs and a script   |
| S1    | `734f5e40`, via #6719 (2026-09-28)        | the mode branches; `legacy` now raises           | 21 files, −578      |
| S2a   | `0ba90d5f`, via #6719 (2026-09-29)        | nothing: probe vocabulary moved (n1)             | 8 files             |
| S2b   | `602379e2`, via #6719 (2026-09-29)        | legacy analyzer, enrichment tier, `ai-llm`       | 330 files, −171,329 |
| S3    | `3b73b9b6`, #6733 (2026-09-30)            | Florence, CLIP, enrichment trees; 11 Triton dirs | 282 files, −64,149  |
| S4    | `cafad910`, #6735 (2026-09-30)            | two enrichment tables, with a DROP runbook       | 16 files, −846      |
| S5    | `392d69fd`, #6736 (2026-09-30)            | five enrichment panels, `poseVisualization`      | 25 files, −5,729    |
| docs  | `496caf62`, `aabd7cd6`, `bee1cc96`, #6739 | provisioning script; the docs next agents read   | 496caf62: 2 files   |
| CI    | `52bf046b`, #6740 (2026-09-30)            | dead `build-ai` and `merge-ai` jobs              | workflow            |

Notes **[V]**: (n1) the vocabulary moved to `backend/services/constrained_decoding.py`. S1 is named
PR #6716 in the ledger row; the commit reached `main` through #6719 (ancestry of the merge
`aaf29361`). S2b deleted `nemotron_analyzer` (5,327 lines), `enrichment_pipeline` (7,662),
`enrichment_client` (3,334), `vision_extractor` (2,303), the `ai-llm` service, `ai/nemotron/`,
`ai/start_llm.sh` and `ai/start_nemotron.sh`. S3 deleted `ai/florence`, `ai/clip`, `ai/enrichment`,
`ai/enrichment-light`, 11 of the 14 Triton model directories, the `/clip`, `/florence` and
`/enrichment` gateway routers, `clip_client` and `florence_client`. S4 retired `demographics_results`
and `reid_embeddings` with the operator runbook
`docs/api/migrations/2026-09-30-retire-demographics-reid-tables.sql`. S5 removed
`components/enrichment/` and the "retired" empty state that `4bfd6fa4` had shipped. The `496caf62`
script now fetches 5 of 10 catalogue rows (763 MB by the catalogue figure). `52bf046b` removed jobs
that had been red on every main push since S3 deleted the trees they built (the comment is in
`.github/workflows/deploy.yml`).

Across seven commits (S1, S2a, S2b, S3, S4, S5 and the provisioning script) the sums are +22,405
and −243,071 lines, net −220,666 **[C]** (inputs: 672+284+3,613+16,215+712+583+326 and
578+124+171,329+64,149+846+5,729+316). 205 of S3's 282 file changes are deletions. 177 of S2b's 330
are, and 130 of those are `test_*.py` files under `backend/tests`; the commit message says "~96 of
their test files" **[V]** (`git show --name-status`).

**Triton was pruned, not deleted.** The digests behind this page said R8 deleted `ai/triton`. It did
not. `ai/triton` still exists with 13 tracked files and a model repository of `reid`, `threat` and
`yolo26`; `ai/gateway`, `ai/yolo26` and `ai/vlm` also remain, and `ai/gateway/adapters` holds
`yolo26.py` and `enrichment_light.py` **[V]**. The gateway mounts only `/yolo26` and `/enrich-lt`
(`ai/gateway/main.py:276-277`); `/enrich-lt` exposes `/threat-detect`, `/person-reid` and `/health`.
What is gone is `ai/florence`, `ai/clip`, `ai/enrichment`, `ai/enrichment-light` and `ai/nemotron`
**[V]** (`ls`).

**What the VLM path keeps.** The probe machinery in `backend/services/constrained_decoding.py`; the
settings `nemotron_context_window`, `nemotron_max_output_tokens` and `nemotron_verification_engine`,
which have live readers (`backend/services/token_counter.py:144-145`,
`backend/services/vlm_client.py:259`, `backend/services/vlm_analyzer.py:370`); three loaders,
`face_recognizer_loader`, `fast_alpr_loader` and `osnet_loader`; and the callers re-homed from the
deleted LLM onto `ai-vlm` (`summary_generator`, `prompt_service`, `pipeline_quality_audit_service`,
`performance_collector`), which now share the verdict path's two slots **[V]** (`grep ai_vlm_url`).
Tables `pose_results`, `threat_detections` and `action_results` stay in the schema
(`backend/models/enrichment.py:49`, `:102`, `:163`); the only constructors outside tests are in
`scripts/seed-events.py`, and the alert-rule test route still reads them (the route claim is the
ledger's, **[A]**).

**What R8 left alive.** Each was read at the tip **[V]**:

- `ai-llm-vllm` survives as an opt-in profile `vllm` (`docker-compose.prod.yml:278`), and the
  orchestrator refuses to manage it (`RETIRED_LLM_SERVICES` at
  `backend/services/container_orchestrator.py:66`, used at `:531`).
- `ai/gateway/export/` still has exporters for models that no longer exist (`export_clip.py`,
  `export_demographics.py`, `export_depth.py`, `export_stgcn.py` and others).
- A plate-OCR call always answers 503: `_PlateOCRHolder.get` raises `ImportError` because the module
  it wrapped was swept (`backend/services/alpr_service.py:524-560`). The specialist leg uses
  `fast_alpr_loader` instead (§5).
- Stale comments: `ai/gateway/main.py` still calls `FULL_MODEL_SET` "the complete Triton model
  repository", although the name now means a three-entry universe (`ai/gateway/residency.py:52`).
- The Nemotron text-LLM prompt-evaluation harness, a fifth survivor the list above omitted (found on
  2026-10-03 and read at `5c605e1d` with `git ls-tree`): `backend/evaluation/harness.py` (it POSTed
  to a `nemotron_url`), six sibling modules, their unit tests, `test_nemotron_prompts.py`, and a
  nightly workflow, `.github/workflows/prompt-evaluation.yml` (cron `0 2 * * *`). **Removed since
  the pin, in `d8482861`; §9.**

## 5. Specialists and residency after R8

The specialist stage (`collect_specialist_outputs`, `backend/services/vlm_specialists.py`) computes
three short text lines over the key frames before `vlm_assess` and sends them in
`AssessInput.specialist_outputs`. The keys are `faces`, `plates` and `person_reid`
(`SPECIALIST_KEYS`, `:881`). Each leg returns one of two fixed phrases when it cannot run,
`unavailable: specialist did not run` or `unavailable (re-enroll)` (`_unavailable_line`, `:93`); no
exception text reaches the prompt (owner ruling 2026-09-26, `9cd44ae1`). Replay does not run the
specialists; it feeds the stored lines. Shipped in `3a8e2184` (2026-09-25) and `4bfd6fa4`.

| Leg           | What runs                                    | State at the tip                                  |
| ------------- | -------------------------------------------- | ------------------------------------------------- |
| `faces`       | CPU ONNX SCRFD plus `w600k_r50`, hash-pinned | weights hand-placed; thresholds PROVISIONAL (n1)  |
| `person_reid` | OSNet-AIN x1.0, 512-d, in the backend        | real since `12f78722`; threshold PROVISIONAL (n2) |
| `plates`      | `fast-alpr` plus a household-vehicle lookup  | likely `unavailable` in the shipped image (n3)    |
| `threat`      | not a specialist                             | no line; the key is not emitted (n4)              |

Notes on the table:

- **(n1) `faces` [V].** The loader forces `CPUExecutionProvider`
  (`backend/services/face_recognizer_loader.py:152`). The two files are sha256-pinned in
  `models.yml`, and a wrong file is treated as missing
  (`backend/services/face_recognizer_loader.py:15`). Both rows carry `download_method: skip`, so an
  operator must place them by hand. The match, gate and scan thresholds are marked PROVISIONAL
  (`backend/core/config.py:1786-1810`). Outcomes are four-valued: match, unknown, not identifiable,
  unavailable; a crop that fails the quality gate is never "unknown"
  (`backend/services/vlm_specialists.py:19-24`). Enrollment is server-side with a stored
  `model_id`; `POST /api/face-recognition/known-persons/{person_id}/embeddings` always answers 410
  (`backend/api/routes/face_recognition.py:340-384`).
- **(n2) `person_reid` [V].** The leg calls `osnet_loader` in the backend
  (`backend/services/vlm_specialists.py:705`, `:723`). A vector from another embedding space reads
  `unavailable (re-enroll)`, and `POST /api/household-matcher/match-person` is retired with 410
  (`backend/api/routes/household_matcher.py:9`). The similarity threshold of 0.7 is PROVISIONAL
  (`backend/core/config.py:1713`). The Triton `reid` model stays resident in the gateway, and a grep
  finds no caller of the gateway's `/person-reid` outside the contract registry and tests.
- **(n3) `plates`.** `fast-alpr` is declared only in the optional `alpr` extra
  (`pyproject.toml:192-193`), and the backend image installs `--extra face` only
  (`backend/Dockerfile:134`) **[V]**. That the leg then answers `unavailable` is an inference; I
  did not run the image **[A]**.
- **(n4) `threat` [V].** `SPECIALIST_KEYS` and its comment are at
  `backend/services/vlm_specialists.py:870-881`: the shipped threat model's card reports an
  identical 83.0% recall for every class (the F12 ruling), and `GATEWAY_ENABLE_THREAT` stays false
  (`docker-compose.prod.yml:388`). `collect_specialist_outputs` takes `run_threat: bool = False`
  (`:891`) and adds a `threat` key only inside `if run_threat:` (`:926`); a grep of `run_threat`
  outside tests finds the definition, the docstring and that `if`, so no caller sets it and the key
  is not emitted. If the slot were enabled it would read `unavailable: specialist did not run`,
  because `not_included` is not in `_UNAVAILABLE_PHRASES` (`:87-90`).

**Boot residency.** The face and re-ID legs load at boot only when `BACKEND_MODEL_PRELOAD` is true.
The compose default is false (`docker-compose.prod.yml:489`); `setup.py` turns it on for 24 GB cards,
inclusively (`PRELOAD_MIN_VRAM_MB = 24 * 1024`, `setup_lib/nvidia_detect.py:221`, owner ruling
2026-09-27, `03d1524c`); the selector honours the row-level `preload:` flag
(`select_preload_candidates`, `backend/main.py:640`) **[V]**. A compose deployment that never set
the flag serves `unavailable` for faces and re-ID **[A]**: inferred from the `models.yml` comment
that the face leg never triggers a load; the backend was not run without the flag.

**What the A5500 S1 reading did and did not include.** The spec's S1 wording is "with the detector,
the specialists and the VLM resident". The recorded set is `yolo26` and `reid` in the gateway plus
`ai-vlm`; the backend's torch is CPU-only, and `threat` is off (ledger row "A5500 RUN, 8B PRIMARY")
**[V]**. Before a bring-up claims S1, say which residency set it was measured on.

## 6. CI and main-green

Main's CI after R8 is a list of owner-held decisions, not code defects. The ledger's red census at
`f9778503`, and its re-reads at `aa1dfbf6` and `93a45f39` (118 and 102 check-runs, `CI Gate` green at
both), name six classes **[A]** (counts not re-measured; they need `gh`). A, the Trivy image scan,
was repaired (`a33fb127`, merged as #6754) and is closed. B, an invalid `LINEAR_API_KEY`, accounts
for three reds in three jobs. C, the `Dependabot` uv job, fails on the repo's own `cryptography`
ceiling plus one advisory with no patched version (options 1-3 are the owner's). At the pin the
ceiling was the `nemo` extra: `data-designer>=0.9.2` requires `cryptography>=48.0.1,<=49`
(`pyproject.toml:159-161` at `5c605e1d`, **[V]** with `git show`), and `uv.lock` held
`cryptography` 49.0.0. Since the pin `efa1b586` (2026-10-03) deleted that extra: the data-designer
ceiling is gone, the lock still reads 49.0.0, and the `ecdsa` advisory with no patched version is
untouched. I did not check whether the Dependabot job now passes **[?]** (§9). D, `Smoke Test
Deployment`, dies because `yolo26` is `critical: True` on a GPU-less runner
(`backend/api/routes/system.py:5111`). E, `ZAP API Scan`, is cancelled by its own 20-minute timeout.
F, the Linear sync workflow, had an install bug (`dff99364`, fixed) and then ran for the first time
and met the same dead key. Two fixes landed that were not red rows: `8ac34ac2` made
`rollback-summary` declare the `needs:` it reads, and `616b60b2` stopped a green job printing "No
open CI failure issues found" off a Linear error envelope. The ledger also records that the
rollback job files an issue and verifies images exist, and retags and redeploys nothing
(`.github/workflows/rollback.yml:116`). The who/when acceptance blanks for B, C, D and E, and for
F, are still `____` in the ledger **[V]**. The ledger entry that records the merge delegation says
the acceptance blanks of the red-census row and of the class F row "are still `____` and still the
owner's alone", and the later entry on the two halves of class F says its blank "remains `____`"
(read at the tip; the literal `____` occurs only in those two prose lines, not in the rows' own
fields). The merge delegation of 2026-10-01 does not cover them. Frontend statement coverage is
recorded at 79.9708 against an 80 floor **[A]** and passes because the merge script rounds before a
strict `<` (`round1` at `frontend/scripts/merge-shard-coverage.mjs:121`, the comparison at `:205`)
**[V]**. Do not fix any of these inside a VLM PR.

## 7. Timeline

Every SHA was checked with `git cat-file -t`; dates are the author date in the committer's local
zone (UTC-04:00), so a late-evening commit can fall on the next UTC day. SHAs from the pre-rebase
branch that the ledger still cites (for example `58163f23f`, `0fcb173df`) are not ancestors of the
tip and are not used here; their main-line twins are `7b75f5bd` and `54e92736`.

| Date       | Commit or source                   | What                                                                                         |
| ---------- | ---------------------------------- | -------------------------------------------------------------------------------------------- |
| 2026-09-19 | `b301a217` (#6557)                 | VSS research docs 00-07 land: "research in progress", nothing implemented                    |
| 2026-09-23 | spec header (`:3`)                 | design approved section by section by the owner                                              |
| 2026-09-25 | `a0105b63` (#6678)                 | P0: `event_verifications`, null-safe live path, eval store, probes, spec and ledger; M0 met  |
| 2026-09-25 | `030b378a`                         | `vlm_assess` contract: op, generated schemas, provider slots, FakeProvider fault knobs (1.1) |
| 2026-09-25 | `8d39f1b6`                         | `ai-vlm` compose service and llama.cpp image (1.2)                                           |
| 2026-09-25 | `9b1b9899`                         | key-frame selector, `VlmClient`, `VlmAnalyzer`, the §6 ladder, wake-on-open (1.3)            |
| 2026-09-25 | `d0baa7a3`, `c271d5e7`, `3a8e2184` | spec rev 6: static `vlm` residency set; specialist stage feeds the prompt (1.3b, 1.4)        |
| 2026-09-25 | `d3f60079`, `752ad1e0`             | CPU face leg; server-side enrollment with provenance                                         |
| 2026-09-25 | `f620ba49`, `ca1902e4`             | F14 sets S2 at 5% and S3 at 90%; F13 lets Phase 2 run before M1                              |
| 2026-09-26 | `4c0f12a1`                         | `PIPELINE_MODE` defaults to `vlm`; one analyzer factory (1.5)                                |
| 2026-09-26 | `677a40f6`, `ca6d734c`, `1c575e21` | verdict badge, verification section, `?verdict=` filter (1.6)                                |
| 2026-09-26 | `e28def43`, `12f78722`             | re-ID one-space swap to OSNet-AIN x1.0 with vector provenance                                |
| 2026-09-27 | `4bfd6fa4` (#6681)                 | Phase 1 ships: the VLM path runs end to end and is the default                               |
| 2026-09-27 | `01080b51`, `bdb55335`, `d1e279fd` | M1 review fixes: key-frame budget counts stills; clips refused; prompt fitted to the slot    |
| 2026-09-27 | `6106ea98`, `7141cad0`             | a truncated reply is inconclusive and cannot open the breaker                                |
| 2026-09-27 | `79087e3c`, `b3ef67d1`             | eval-store generation 2; the Phase 2 replay harness with Wilson intervals                    |
| 2026-09-27 | `b265d147` (#6683)                 | synthbench begins: capture time from Foscam filenames                                        |
| 2026-09-27 | `54141d9c`, `c4d8ac5e`             | Qwen3-VL-8B becomes the shipped default (owner ruling dated 2026-09-28 in the ledger)        |
| 2026-09-28 | `e316ad79` (#6697)                 | synthbench P1: bake-off, ComfyUI stack, approved picks                                       |
| 2026-09-28 | `4dbd8bb3`, `ec1ac051`, `1f2921a4` | A5500 run recorded: S1 and S4 read PASS; M1 chain run; 4B fallback fails S5                  |
| 2026-09-28 | `5b929a52`, `a2d8c710`             | native `bbox_2d` boxes; 1,024-token budget; prompt fit matches the served slot               |
| 2026-09-28 | `7b75f5bd`, `54e92736`, `08d5ceb9` | KV flags reach llama-server; YOLO26 head and re-ID exports fixed                             |
| 2026-09-28 | `27d87993` to `84a0e5e1`           | synthbench P2: contract, store, taxonomy, sampler, `sample`                                  |
| 2026-09-28 | `6798ee59` (#6714)                 | R8 S0: currency banners and a gate                                                           |
| 2026-09-28 | `734f5e40` (#6719)                 | R8 S1: `PIPELINE_MODE=legacy` raises                                                         |
| 2026-09-29 | `602379e2` (#6719)                 | R8 S2b: the legacy LLM and enrichment tier deleted, 330 files                                |
| 2026-09-29 | `2e2186e7`, `4dcb079e`, `28fc5fda` | synthbench P3 acceptance; the generation skill; taxonomy sign-off note                       |
| 2026-09-29 | `c2a1566b`, `e175c6c7`, `fe8d50f1` | P5a: `export vss`, `replay`, `audit`                                                         |
| 2026-09-29 | `4b653251`, `502df6e2` (#6732)     | P5a: `score`; the first scored result of the shipped VLM                                     |
| 2026-09-30 | `3b73b9b6` (#6733)                 | R8 S3: Florence provider retired; gateway pruned to the `vlm` set                            |
| 2026-09-30 | `cafad910`, `392d69fd`, `496caf62` | R8 S4 (tables), S5 (panels), provisioning                                                    |
| 2026-09-30 | `01df30cc`, `1eeda952`, `0be8b3f3` | H3 clip rounds: design; pilot gate waived; clip render                                       |
| 2026-09-30 | `52bf046b`, `2c4855b5`, `c2c6c561` | main-green: dead AI image jobs removed; CI compose bootable; sign by digest                  |
| 2026-10-01 | `a33fb127`, `8ac34ac2`, `dff99364` | main-green: Trivy repaired; rollback summary needs; Linear sync install                      |
| 2026-10-01 | `616b60b2` (#6766)                 | the Linear close step stops printing a false all-clear                                       |
| 2026-10-01 | `5c605e1d`                         | the pinned tip: h3 notes on subjects that cross the frame                                    |
| 2026-10-03 | handoff Addenda 2-3                | two further full replays: S2 9.1% and 8.6%, S3 36.1% and 34.9%; run-to-run noise measured    |
| 2026-10-03 | handoff Addendum 4                 | two temperature-0 replays agree on 450 of 450; S2 18 of 209, S3 88 of 241 (§9)               |
| 2026-10-03 | `9f4e65cd`                         | after the pin: the assess call samples greedily, `_ASSESS_TEMPERATURE = 0.0` (§9)            |
| 2026-10-03 | `d8482861`                         | after the pin: the retired Nemotron prompt-evaluation harness is deleted (§9)                |
| 2026-10-03 | `efa1b586`                         | after the pin: the `nemo_data_designer` tool and the `nemo` extra are deleted (§9)           |

## 8. Claims from the inputs that did not survive, and open items

Corrections, so a reader who meets these claims elsewhere knows where they stand:

- **"R8 deleted `ai/triton`."** False. Triton was pruned to `yolo26`, `reid` and `threat` (§4).
- **"The docs' cite of line 578 of `docker-compose.prod.yml` never resolved."** It resolved when
  written and rotted when R8 S2b shrank the file (§2). The line is `:484`.
- **"S2's bar is still `[?]`, ask the owner."** F14 set 5% and 90% on 2026-09-25. Only the spec text
  was never back-edited.
- **"`10/20` is the predecessor of the 450-item S3."** It is a different harness and set.
- **"Cosmos-Reason2-8B is a live blocked candidate for P5a."** The P5a report says Cosmos was
  replayed, stopped at 321 of 450 by the owner, and left unscored.
- **"ffmpeg is not in the backend image."** The comment at `backend/services/vlm_client.py:472-474`
  says so; `backend/Dockerfile:170` installs it. The refusal of video stands for other reasons
  (§2).
- **"R8 S2b deleted ~96 test files."** The commit message says so; the diff deletes 130 `test_*.py`
  files under `backend/tests` (§4).
- **"`temperature` 0 is used only for the §6 transport retry."** The handoff's Addendum 3 says so,
  and this page repeated it before the 2026-10-03 correction. At `5c605e1d` the retry re-sent after
  a transport error, a non-200 reply and a schema-invalid reply, and 0.0 was also sent by the
  enforcement probe and the wake ping (§2).
- **Not carried, because I could not verify them:** the specialist-stage timings (0.041-0.514 s per
  batch), the generation agent's throughput and `text_overlay` rates, and the mutation-score series.
  CI check-run counts are carried only as ledger claims **[A]**.

Open and owner-held, in the order they block progress: the M1 notification link (where to call
`should_notify`, and whether to wire `evaluate_event` and `deliver_alert` in the same slice); how
to read S3 (keep the midpoint floor, or use the minimum), and the remedy for a 54-point gap (prompt
and score work, re-scoping, or a bar revision, which is owner-only); whether declared-truth
synthetic scores count for flip condition (iii) [?]; whether to sample at a fixed seed or
temperature 0, or take a majority of k draws, given the noise in §3 (done 2026-10-03: `9f4e65cd`
chose temperature 0, §9); a spec revision that records F14's numbers and corrects the M1, S1 and
residency text; a video-VLM lane for clips; P5b; Brev spend; and go-live sign-off. Added
2026-10-03: the `cryptography` 49.0.0 to 50.0.2 lock bump that `efa1b586` made resolvable and did
not apply (§6, §9) was the owner's call, made the same day: applied in `f0ff083e` (§9).

## 9. Changes after the pinned tip (2026-10-03)

Three commits landed after `5c605e1d`, all authored on 2026-10-03 (UTC-04:00); each was read with
`git show --stat` **[V]**. The page above is the record at the pin and is not rewritten; this
section says what has changed since, and where a pinned fact now needs a qualifier.

**`9f4e65cd` (11:18): the assess call is greedy.** The commit is "fix(vlm): the assess call samples
greedily - temperature 0, not an unseeded 0.1". It touches `backend/services/vlm_client.py` (13
insertions, 3 deletions) and `backend/tests/unit/services/test_vlm_client.py`. It adds
`_ASSESS_TEMPERATURE = 0.0` (`:103`) and sends it as the assess call's `temperature` (`:802`). The
§6 retry stays explicit at 0.0 (`:811-817`) and is now a plain re-send of the same body, because the
first attempt is greedy too; whether a re-send after a schema-invalid reply can return anything
different depends on the engine and was not tested **[?]**. `test_assess_samples_greedily` pins the
constant, the wire value and the absence of `top_p`, `top_k`, `min_p` and `seed`;
`test_transport_error_retries_once_at_temperature_zero` now asserts that the first attempt is at 0
as well. I ran both: 2 passed **[V]**.

- **The noise is fixed.** Two temperature-0 replays of the same 450 sets,
  `20261003T134900Z-qwen3-vl-8b-T0` and `20261003T141303Z-qwen3-vl-8b-T0`, returned an identical
  verdict and risk score on **450 of 450** items; the two temperature-0.1 replays of §3 agreed on
  278 of 450. Both temperature-0 runs read **S2 18 of 209** (8.6%, interval [5.5-13.2]) and **S3 88
  of 241** (36.5%, [30.7-42.8]) with 0 refusals **[V]** (the agreement count is a read-only
  comparison of the two replays' rows in the eval store; the S2/S3 figures are the `report` object
  in each replay's `run.json`).
- **What that run was.** The `run.json` of each full temperature-0 replay carries a
  `sampling_override` field reading "EXPERIMENT: temperature forced to 0.0 via transport shim; chat
  requests rewritten: 451" (450 items plus the probe); the 3-item temperature-0 smoke run
  (`20261003T134843Z-qwen3-vl-8b-T0`) reads "rewritten: 4". The three temperature-0.1 replays of §3
  (`20261003T131134Z-qwen3-vl-8b`, a 3-item smoke run, and the two full runs) carry no
  `sampling_override`. All six replays then in the directory record commit `5c605e1d`: the four
  full ones (`20261003T131219Z-qwen3-vl-8b`, `20261003T133050Z-qwen3-vl-8b`,
  `20261003T134900Z-qwen3-vl-8b-T0`, `20261003T141303Z-qwen3-vl-8b-T0`) and the two smoke runs. So
  the temperature-0 figures were taken on the pinned code
  with the request body rewritten by a scratch driver; at that time no full 450-item replay had been
  run on the code of `9f4e65cd` itself **[V]** (`run.json` fields under `runs/replays/`). Added
  2026-10-03, read at 19:07Z: that no longer holds. `runs/replays/`
  now also holds a 3-item probe (`20261003T154000Z-qwen3-vl-8b-probe`) and two full 450-item
  replays, `20261003T154038Z-qwen3-vl-8b-armA-shipped` and
  `20261003T161804Z-qwen3-vl-8b-armB-rubric`, all of which record commit `d8482861` (which
  contains `9f4e65cd`). Their `run.json` `experiment` field calls them "EXPERIMENT arm via
  transport shim; repo client untouched; development arm, NOT a holdout", with logprobs requested
  and, for `armB-rubric`, 450 rubric replacements; `armA-shipped` records no `sampling_override`.
  I have not read their results and no result of theirs is used on this page **[V]** (`run.json`
  fields only). The wire value the shim wrote is the one the commit now sends,
  so I expect the same readings, and that is an expectation, not a reading **[?]**. Neither
  temperature-0 replay was scored with `synthbench score`; the `scores` directory holds only the two
  temperature-0.1 scores **[V]** (`ls`).
- **It added noise, not accuracy.** The temperature-0 readings (S2 18, S3 88) sit inside the
  temperature-0.1 spread (S2 14, 19, 18; S3 88, 87, 84) and next to its means (17.0 and 86.3)
  **[C]**. S2 still misses its 5% bar (the interval lies wholly above it) and S3 still fails 90% by
  about 54 points, so the verdict of §1 does not move; what changes is that one replay is now a
  reproducible reading and not one draw, and A/B comparisons can be paired.
- **What now needs a qualifier.** The §2 bullet "A verdict is a draw" and the §3 **Noise** and
  **Cause** paragraphs are true at the pin and false at `9f4e65cd`; the "13 files unchanged" claim
  of §3 **Identity** is now true of 10 of them. No seed was added (the test pins its absence); at
  temperature 0 a majority of k draws would have nothing to vote over **[C]**, so the §8 open item
  on a seed, temperature 0 or a majority is done. The baseline's 14 against 18 at temperature 0 is
  one reading each, not a regression test, because the baseline was a temperature-0.1 draw.
- **Anchors moved.** `vlm_client.py` anchors from `:98` on moved +6 (`VlmTruncatedError` `:134` to
  `:140`, `_fitted_prompt` `:676` to `:682`, the assess `temperature` `:796` to `:802`), and +10 past
  the retry loop (`wake` `:946` to `:956`, `wake_ai_vlm` `:981` to `:991`) **[V]** (`grep -n` at
  `d8482861`). Prefer the symbol.

**`d8482861` (11:34): the evaluation package is VLM-path only.** The commit is "chore(eval): remove
the retired Nemotron prompt-evaluation harness": 43 files changed, 137 insertions, 7,770 deletions
**[V]** (`git show --shortstat`). It deletes 17 files: `backend/evaluation/` `harness.py`,
`prompt_evaluator.py`, `prompt_eval_dataset.py`, `combined_dataset.py`, `ab_experiment_runner.py`,
`metrics.py` and `reports.py`; six unit tests under `backend/tests/unit/evaluation/`;
`backend/tests/integration/test_nemotron_prompts.py`; `.github/workflows/prompt-evaluation.yml`;
and the two `prompt-evaluation-results.md` pages under `docs/developer/` and `docs/development/`.
The rest of the 43 files is edits so that nothing points at the deleted code (`pyproject.toml`,
`mkdocs.yml`, `scripts/validate.sh`, the suppression registry, `scripts/gen-ai-contract.py` and its
one regenerated schema, and active docs).

- **What the package is now.** `backend/evaluation/` holds `assess_input`, `control_freeze`,
  `eval_store`, `label_import`, `levels`, `s_metrics` and `vlm_replay` (plus `__init__.py`, which
  exports nothing, and `AGENTS.md`) **[V]** (`ls`; `__init__.py` read). These are the modules
  `synthbench replay` and `score` drive.
- **What it corrects here.** At `5c605e1d` the package also held the text-LLM harness, which the
  "What R8 left alive" list in §4 did not name; that bullet now records it and its removal. §3's
  description of `backend/evaluation/` is scoped to the pin for the same reason. The message of
  `9f4e65cd` named the harness's own 0.1 temperature (line 554 of `harness.py` at the pin) as left
  alone; `d8482861` deleted that file 16 minutes later.
- **Anchors moved.** The `S2_MAX_PCT` and `S3_MIN_PCT` lines of `s_metrics.py` moved from `:32-33`
  to `:30-31`; in `vlm_replay.py`, `replay_item` moved from `:121` to `:118` and `run_replay` from
  `:209` to `:206` **[V]** (`grep -n`). The only changes to those two files are comments and
  docstrings: the "no `harness.py`" bullet in the `vlm_replay.py` docstring went, and so did the
  replay test that asserted the module never imports the harness
  (`test_never_imports_the_legacy_harness`), since the module no longer exists.
- **Left alone on purpose** (the commit message, **[A]**): historical records including this
  directory, the prompt-management feature (`prompt_service.PromptEvaluator` is a different class),
  `tools/nemo_data_designer` and the `nemo` extra. Both named paths still existed at `d8482861`
  **[V]** (`ls`, `grep`, read when this section was first written); `efa1b586` removed them
  (below).
- **Checked at `d8482861` for this page** **[V]**: `backend/tests/contracts` run with `-n 4` gives
  464 passed, the same as the pin (§1, note 6); `backend/tests/unit/evaluation` gives 189 passed and
  1 skipped. The commit's own counts (5,930 tests; 32,799 collected) are the author's and were not
  re-run **[A]**. Both runs were repeated at `efa1b586` with the same result **[V]**.

**`efa1b586` (15:39): the NeMo Data Designer tooling and the `nemo` extra are gone.** The commit is
"chore(tools): remove the NeMo Data Designer tooling and the nemo extra": 41 files changed, 36
insertions, 8,873 deletions, of which 29 files are deletions and 12 are edits **[V]**
(`git show --shortstat` and `--name-status`). `git ls-files tools` returns nothing at the tip, so
the `tools/` package (its only tool was `nemo_data_designer`) is gone; untracked, ignored
`__pycache__` files remain in a working tree that once had the package **[V]** (`find tools`).

- **What went.** `tools/nemo_data_designer/` and `tools/__init__.py`; the tool's only importers,
  `backend/tests/integration/test_multimodal_pipeline.py` and `test_enrichment_edge_cases.py`; the
  `backend/tests/fixtures/synthetic/` fixtures; two `nemo-data-designer.md` pages under `docs/`. The
  `pyproject.toml` edit drops both `nemo` dependency blocks (`data-designer`, `pandas`, `pyarrow`,
  `numpy`), the `tools/**` ruff ignore and the `multimodal` and `enrichment` pytest markers;
  `backend/tests/conftest.py` loses the `synthetic_scenarios` and `scenario_by_type` fixtures
  **[V]** (`git show --stat`, `git show efa1b586 -- pyproject.toml`).
- **The lock.** `uv.lock` drops 23 packages (`data-designer`, `data-designer-config`,
  `data-designer-engine`, `pandas`, `pyarrow`, `duckdb`, `mcp`, `sqlfluff`, `pyjwt`, `pytz` and
  others) and adds none **[V]** (the `uv.lock` diff of the commit has 23 removed and no added
  `name = ` lines). "Changes no version" is the commit message's claim **[A]**.
- **The census baseline.** `scripts/test_suppression_census.py` lowers `pytest_skip_imperative`
  from 99 to 86 (`:536` at `d8482861`, `:543` at the tip) **[V]**; its docstring says 10 skip sites
  went with the harness test in `d8482861` and 3 with this commit, and that `d8482861` left this
  guard red because its verification ran `backend/tests/unit/scripts`, not the repo-root `scripts/`
  tests **[A]** (the commit message and docstring; I did not run the guard at `d8482861`). At the
  tip `scripts/test_suppression_census.py` gives 8 passed **[V]**.
- **The `cryptography` ceiling.** §6 class C: at the pin, `data-designer-engine>=0.9.2` held
  `cryptography` at `<=49` and `uv.lock` read 49.0.0. In the committed tree of `efa1b586`,
  `uv.lock` still reads 49.0.0 **[V]** (`git show efa1b586:uv.lock`), and the dry run
  `uv lock --dry-run --upgrade-package cryptography`, run against that tree on 2026-10-03 at about
  19:40Z, reported "Update cryptography v49.0.0 -> v50.0.2" **[V]** (it writes nothing). The upgrade
  is **not applied in the commit**: the commit says so, and the ledger has no entry on it (`grep`
  for `efa1b586` and `50.0.2` finds nothing) **[V]**. The owner has been asked and has not ruled
  **[A]** (stated by the workflow that commissioned this edit, not read from a record). The
  `.trivyignore` entry for CVE-2026-69247 (`:207-220`) and the note in
  `.github/workflows/dependency-audit.yml:72-77` still blame the `nemo` extra, which no longer
  exists; the commit leaves both alone until the bump lands **[V]** (`git show efa1b586:<path>`).
  Applying the bump is a dependency-policy change and is the owner's call; option 2 of the ledger's
  class C entry (drop the extra) is the lever this commit pulled. Added 2026-10-03, read at 19:45Z:
  the working tree now carries uncommitted edits to `uv.lock` (the diff is `cryptography` 49.0.0 to
  50.0.2 and nothing else), `.trivyignore` and `.github/workflows/dependency-audit.yml` (mtimes
  15:44 UTC-04:00) **[V]** (`git status`, `git diff`), made by something other than this edit. Who
  made them, and whether the owner has ruled, I do not know **[?]**. Read the committed files, not
  the working tree, when checking the statements above.
- **Applied later the same day (`f0ff083e`).** The owner ruled in-session ("yes we can perform the cryptography upgrade", 2026-10-03 **[O]**) and `f0ff083e` applies it: `uv.lock` changes exactly one package (`cryptography` 49.0.0 to 50.0.2), the `CVE-2026-69247` entry is deleted from `.trivyignore` (its own text said to), and the four `--ignore-vuln` flags written for the old ceiling are removed from `dependency-audit.yml` **[V: `git show --stat f0ff083e`]**. `pip-audit` over the new lock, exported as CI does and run without those four ignores, reported "No known vulnerabilities found" **[V: run 2026-10-03]**; the unit and contract tiers passed (28,271) and the scripts tiers (663) on `cryptography` 50.0.2 **[V: recorded in the commit message]**. The uncommitted edits noted above were these. Whether the Dependabot uv job now passes is not read **[?]**.
- **M1's missing decision exists (`ab3bd002`).** `decide_notification` in `backend/services/notification_filter.py` loads the preferences, the camera's setting and the quiet hours and calls `should_notify`; `vlm_analyzer` runs it in its own short session after the event commits (skipped in replay) and the answer rides the WebSocket `event` as `data.notify`, the key absent when no decision was made; the frontend type is regenerated (`notify?: boolean | null`) **[V: `git show --stat ab3bd002`, 7 files, +397/-13]**. Red first: 9 new analyzer tests failed with `KeyError: 'notify'` before the code; 13 tests added; unit, contract and repo-root scripts tiers 28,563 passed **[V: recorded in the commit message]**. **M1 is not closed:** nothing acts on `notify` yet (the frontend `showSecurityAlert`, the alert-rule engine and `deliver_alert` have no caller of it) and no live-database integration run was possible in the sandbox.
- **Every measured number is specific to the llama.cpp build (found 2026-10-03, after `ab3bd002`).** The shipped 8B Q4_K_M, same weights, prompt and greedy decoding, served on a newly built llama.cpp `b11376` (`a55e952b8`; the sweep also sets `LLAMA_ARG_CACHE_RAM=0` and `LLAMA_ARG_CACHE_IDLE_SLOTS=0`) and replayed over the same 450 sets read **S2 21/209, S3 94/241, AUROC 0.677, 2 refusals** (both `VlmTruncatedError` at 1,024 tokens) against S2 18/209, S3 88/241, AUROC 0.703, 0 refusals on `b7972`; item by item only 250 of 450 return an identical (verdict, risk_score), 143 differ by 10 points or more **[V: `eval.sqlite`, run `20261003T194331Z-control-q4km` against `20261003T154038Z-qwen3-vl-8b-armA-shipped`]**. The cause (build or the two cache flags) is not attributed **[?]**; a repeat control and a default-cache control were running. Both builds fail the F14 bars. A cross-model comparison is valid only on one build, and a build bump needs a control replay (register ISS-087).
- **What it does not change.** No file on the VLM path or the replay path is touched (the
  `--stat` list has nothing under `backend/services/`, `backend/evaluation/`, `synthbench/` or
  `ai/`), so the §3 readings and the temperature-0 results stand **[V]**.
