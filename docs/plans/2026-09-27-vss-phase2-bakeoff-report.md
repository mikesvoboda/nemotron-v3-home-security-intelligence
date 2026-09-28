# Phase 2 bake-off report — what the GB300 measured, and what it could not

Plan: `docs/superpowers/plans/2026-09-27-vss-phase2-evaluation-bakeoff.md` (task 2.2.5/2.2.6).
Evidence rows: `docs/plans/2026-09-23-vss-gaming-gpu-ledger.md`, 2.2.1–2.2.4. Aggregate
metrics only (D10): no per-item content, no imagery, no labels beyond stock scenario names.

Three of the four spec candidates ran on the GB300 through `agent-gpu`, each in the build it
would ship in, each config-matched (`CTX_SIZE 32768`, `PARALLEL 2`), each replaying the same
frozen gen-2 items through the same harness. The fourth is BLOCKED with its numbers. The corpus
is the honest constraint, so read the constraint before the numbers:

**What this corpus can and cannot measure.** 13 of gen-2's 426 items carry media, and all 13 are
stock items whose frozen snapshot has an empty `detections` list, so the shipped prompt asserts
"the detections below were produced by an object detector" over nothing (ledger finding C).
The 8 stock incidents expect `risk_score` 0, which floors at `low`, and `low` cannot be failed —
so **S3 here measures whether a model emits the grammar, not whether it is salient**. The 408
synthetic items are labeled but have no images (owner item 19), and the 5 items that carry a
`specialist_outputs` block have no media (finding D). **The fixed-bar verdicts on `S2_MAX = 5 %`
/ `S3_MIN = 90 %` (F14) stay BLOCKED on that media.** Every S2/S3 number below is a floor on
grammar, printed with its n and its 95 % Wilson interval, never a bar verdict.

## The spec's four lines, per candidate

|                             | **A** Qwen3-VL-4B Q4_K_M                   | **B** Nemotron-Nano-12B-v2-VL Q4_K_M                  | **C** Qwen3-VL-8B Q4_K_M                                         | **D** Cosmos-Reason2-8B                        |
| --------------------------- | ------------------------------------------ | ----------------------------------------------------- | ---------------------------------------------------------------- | ---------------------------------------------- |
| image / engine              | `ai-vlm:sm103-v12` b7972                   | `ai-vlm:sm103-b11090` b11090                          | `ai-vlm:sm103-v12` b7972                                         | —                                              |
| **S2** FP rate (n=5)        | 0 %, [0.000, 0.434]                        | 0 %, [0.000, 0.434]                                   | 0 %, [0.000, 0.434]                                              | BLOCKED                                        |
| **S3** `all` (n=8)          | 0.875, [0.529, 0.978]                      | 0.875, [0.529, 0.978]                                 | 1.000, [0.676, 1.000]                                            | BLOCKED                                        |
| **S3** excl. zero-floor     | n=0 — cannot be taken                      | n=0 — cannot be taken                                 | n=0 — cannot be taken                                            | BLOCKED                                        |
| verdict mix (n=13)          | conf 9 / unc 2 / failed 2                  | rej 11 / unc 1 / failed 1                             | conf 10 / unc 3 / failed 0                                       | BLOCKED                                        |
| **S4** latency (indicative) | med 6.4 s p95 20.7 s                       | med 6.2 s p95 14.6 s                                  | med 7.5 s p95 10.8 s                                             | BLOCKED                                        |
| **S5** unparseable          | 0 (2 refusals surfaced, `broken_rows: []`) | 0 (1 refusal surfaced)                                | 0 (no refusals)                                                  | BLOCKED                                        |
| **uncertain** rate          | 0.154                                      | 0.077                                                 | 0.231                                                            | BLOCKED                                        |
| **tool probe (R3)**         | SUPPORTED, both arms, arg honoured         | SUPPORTED, both arms, arg honoured                    | SUPPORTED, both arms, arg honoured                               | BLOCKED                                        |
| **long-context KV**         | **4608 MiB** / 16384 cells (36 KV layers)  | **768 MiB** / 16384 cells (**6** KV layers — hybrid)  | **4608 MiB** / 16384 cells (36 KV layers)                        | needs own vLLM BF16                            |
| **license / gating**        | apache-2.0 (GGUF header), ungated          | nvidia-open-model-license (gating term), ungated repo | apache-2.0 (HF repo tag; the GGUF header carries no license key) | **gated: auto**, license `other`, 17.5 GB BF16 |
| VRAM measured               | 7285 MiB projected (fit log)               | 10118 MiB actual, 7998 projected                      | 11216 MiB actual, 9376 projected                                 | —                                              |

Run ids: A `896a4c2b` (pin `ba823226`), B `4e02a70e` (pin `390dd640`), C `5a8a714e` (pin
`e673b671`). `git diff ba823226..e673b671 -- backend/` is empty: the harness that produced all
three is the same code, which is what makes the columns comparable at all.

## What the numbers support, and what they do not

**S1 and S4 are not claimed.** F13 reserves both for 24 GB-class hardware; the latency rows above
are labelled indicative and the fit numbers are single-container readings on a 249 GiB GPU, which
is not the question S1 asks (≤ 20.4 GiB with detector + specialists + VLM resident, no CPU
offload). Those close in step 2.3, on the owner's hardware.

**No candidate ordering is supportable on n=13.** A and B have identical S3 point estimates and
identical Wilson intervals; C's point estimate is higher and its interval still overlaps both.
The intervals are the honest statement: at n=8 the corpus cannot distinguish 0.875 from 1.000.

**What the mix shows where recall hides it.** A and B tie on S3 while answering opposite ways —
A returns `confirmed` on 9 of 13 items, B returns `rejected` on 11 of 13 — because every scored
answer clears the stock incidents' `low` floor, so the recall figure is indifferent to the
substance of the answer. This is precisely the pattern the spec warns about (§:276-279), and it is
why the mix is printed beside the bars rather than folded into them. On this corpus the mix is the
only line that separates the candidates at all, and it is the weakest kind of evidence: 13 items,
no detections, no specialist context.

**The probe's one refusal is finding A, not the model.** All three runs replay the same 13 items
in the same order; `stock:break_in_attempt` is item 1, and A and B each refused exactly that item
with `ConstrainedDecodingNotEnforced` while C answered it. That item is the scene ledger finding A
measured truncating at the probe's 400-token budget. Against B — the case where a real enforcement
gap would matter most — the image-free enforcement probe was run three times: `ENFORCED`, exit 0,
all three. A build that genuinely did not enforce would refuse every item, not item 1. So the
refusals are read as a budget artifact at the probe boundary; the repair (`finish_reason`-aware
triage that keeps fail-closed) is finding A's own change, not a Phase 2 fold-in. **Update on that
repair, same day, and a correction to this report's own paragraph:** it shipped, and the first
follow-up measurement of the shipped client retracted a sentence this report had just gained. An
earlier proof had claimed the 400-token cliff "did not reproduce on the shipped shape" — that was
_wrong, and wrong in the exact way finding A is about_: it drove the probe with the analyzer schema
(4 scalar fields) while the shipped chat probe sends the full verdict wire schema (it adds a required
`description`, a `criteria` array, a `provenance` object — far more required output). Re-measured
with the shipped client's own `_wire_schema()`, the cliff is real and is not a clean cliff but a
_coin flip_: repeated identical requests at 400 echo 3/4 on `break_in_attempt` (4/4 at 700),
`pet_activity` 0/4 at 400 → 4/4 at 700, `loitering` needs ≈2000, `casing`/`delivery_driver` stable at 400. So `break_in_attempt` refusing item 1 above is the shipped probe's own behavior, not only a
`s3_salience_stock.py` artifact — and because the enforcement gate caches once per client, a scene at
the cliff makes a run's verdict depend on which image came first. That cache-vs-cliff interaction is
recorded as ledger finding G (an open question for the owner, not silently folded into the triage).
What the repair validly proved still stands: driven to truncation on purpose (budgets 100/150) every
truncated reply reclassifies `ignored → inconclusive` and `ignored` appears zero times, so the triage
neither forgives prose nor condemns a budget — and the assess leg's identical truncation is now its
own honest cause (`VlmTruncatedError`, raised once, no futile same-budget retry) rather than a
schema-invalid model blame. Ledger finding A carries the runs and gate numbers; finding G and open
issue 28 carry the budget question the owner owns.

**The KV line is the one difference that survives the corpus noise,** because it is a log reading
rather than a measurement of model behaviour: at the same context and parallelism, B spends 768 MiB
where A and C spend 4608 MiB, because `nemotron_h` carries KV on 6 of its 63 layers. On the long
multimodal prompts the vlm path actually sends, that is a ~6× per-token difference in the resource
that decides how many live streams one GPU can hold. It is also the reading a 24 GB box cares
about most, so it is the number worth re-checking in 2.3.

**Candidate C was BLOCKED in the plan and is not in fact blocked** — an honest supersession, not
a small victory. The plan's finding D-P2-4 rested on `cas-bridge.xethub.hf.co` → 403. Re-tested
rather than reused: that host **answers**, and its 403 is CloudFront's own `MissingKey` body — a
signed-URL requirement, not a sandbox network block. HuggingFace's current `resolve/` redirect no
longer points there; it lands on `us.aws.cdn.hf.co`, which serves public files without a signed
key, and the ungated official `Qwen/Qwen3-VL-8B-Instruct-GGUF` repo carries Q4_K_M (5.03 GB) +
mmproj Q8_0 (0.75 GB). Weights were fetched to `$AGENT_GPU_DIR/models/vlm/` (never in git, D10) and the
candidate ran with no new code. Two operational notes fell out: files fetched into the models root
land mode 640 and the serving user is "other", so they need `chmod 644` (finding E, same class).

**Candidate D stays BLOCKED, and two blockers, not one.** `nvidia/Cosmos-Reason2-8B` is
`gated: auto` with license `other`, so it needs an accepted HF account before the weights are
downloadable at all; and its BF16 shape is 17.5 GB of safetensors with no GGUF quant upstream,
which spec :281-282 already frames as "our own vLLM, quality reference only". The one thing that
unblocks it: the owner placing a weights directory under `$AGENT_GPU_DIR/models/vlm/` (or an
accepted HF token), plus a vLLM build for `sm103`, which the repo does not have. It is not
dropped (D-P2-4).

## What this report explicitly does not do

1. **It does not pick the model.** D5/M2 is the owner's call; the columns above exist to be
   weighed, and the strongest honest sentence this corpus supports is "all three run the shipped
   wire, tool-call with the required argument, and enforce constrained decoding; none is
   distinguishable on salience here."
2. **It does not claim S1 or S4.** Indicative numbers only, labelled as such (F13). 2.3 is the
   gate, on 24 GB-class hardware.
3. **It does not restate S-3's hedging question as answered.** The `uncertain` rates (0.154 /
   0.077 / 0.231) are its first measurement, on 13 items with no specialist context — the exact
   condition 1.3b deferred to, and finding D shows the deferred question ("does the VLM hedge when
   specialist context is present?") still cannot be asked on the shipped wire. The spread between
   C and B is consistent with models sitting at different hedging priors; that is a hint, not an
   answer, and the corpus that answers it is the owner's synthetic media.
4. **It does not print a bar verdict.** F14's 5 % / 90 % appear as `bar_pct` inside each report
   JSON, beside the mix, never against a silently-reset bar, and never as "passed" on a corpus
   where S3's floor cannot be failed.

Report JSONs (aggregate-only) live at
`$AGENT_GPU_DIR/out/eval-store/gen-2/reports/2.2.3-candb-ctx32k-p2.json` and
`2.2.4-candc.json` plus `2.1.6-smoke-ba82322.json` (candidate A), wiped with the store at Brev
teardown (D10).

## Erratum (dated 2026-09-27, same day; found by the harness review, ledger item 30)

**Candidate A's S5 row under-read A by one.** The summary table's S5 row says A had "0 unparseable,
2 refusals surfaced", and the finding-A prose says "the probe's **one** refusal". A's second refusal
was not an enforcement artifact: queried against the eval store's stored rows (the class name each
refused row carries in `raw_response.error`), A's two refusals were `stock:break_in_attempt` →
`ConstrainedDecodingNotEnforced` — the one the prose counts — AND `stock:vehicle_parking` →
`VlmSchemaError`, a real unparseable. The pre-fix harness reported refusals as one undifferentiated
count and could not name the class, so "0" was what the row could see, not what happened. The
fixed `s5_refusals` (shipped at `8ad70693`) emits `unparseable` / `unavailable` / `by_error_class`
precisely so a 2.2 report cannot repeat this; re-running A's 13 items through the fixed metrics on
the STORED rows gives unparseable = 1 for A, 0 for B, 0 for C. S5's bar ("0 unparseable verdicts")
therefore reads **failed by 1** for A on the stock corpus — which does not change the ranking story
this report tells (it explicitly does not pick a model, and a 1-of-13 schema miss on one scene is
reported, not laundered), but the row as printed is wrong and stands corrected here, dated, not
silently edited above.

**One sharpening of the finding-A attribution, same erratum, measured the same day.** The 400-token
cliff the attribution leans on had been walked on build **A** only (`b7972`: 3/4 echo on the shipped
chat-wire schema, ledger finding G). B's `break_in_attempt` refusal — same scene, same error class —
was corroborated for B only by the image-free enforcement probe (three × ENFORCED), which pins the
_build_, not the _scene × budget_. The gap is closed by measurement, not argument: B re-served
(`b11090-b1c2863e2`, `agent-gpu`, `--vram 20`, `rm`'d after) and the shipped client's own probe body
run n=8 per cell at temp 0 — **B truncates `break_in_attempt` at 400 on 8/8 requests and echoes on
8/8 at 700** (full reply ≈1595 chars; the 400-token reply reaches ≈1582 before `finish_reason=length`),
while the control scene `casing` echoes 8/8 at both budgets. So B's single refusal IS the budget
artifact, deterministically — and not a broken build: the same scene clears two rows down the ladder,
and the run's own enforcement gate passed on the SECOND item's image at 400, which is finding G's
cache-vs-cliff interaction confirmed live on B (an inconclusive probe caches nothing; item 2's image
answered ENFORCED and the other 11 items flew). The shapes differ by build — A coin-flips (3/4), B
deterministically truncates (0/8) — but the class is shared, and 700 now measures as clearing
`break_in_attempt` on BOTH builds (A: 4/4, finding G's own ladder; B: 8/8, this one), which is
input to open issue 28, not a new question.
(`/tmp/b_probe_ladder.json`, aggregate counts only, D10.)

**What the correction does NOT touch:** the S4 p95 figures (20.7 / 14.6 / 10.8 s). The harness that
computed them had an off-by-one (`latencies[int(n*0.95)]`, one rank high at whole-multiple n), but
at these runs' n=13 both the old index and the fixed nearest-rank rule give rank 13, so these
numbers were always the quantity claimed — verified, not assumed, when the p95 code was fixed.
Candidate D stays BLOCKED, the KV reading stands, and finding G (the probe budget) is unchanged:
`break_in_attempt`'s refusal was already attributed to the 400-token cliff; this adds only that
A's OTHER refusal was a different class entirely.

## Erratum 2 — dated 2026-09-27, larger-model survey (ledger item 34); the table above is NOT rewritten

The Phase 3 goal asked whether a model past 12 B earns its keep, so two more candidates ran
through **this report's own harness** — the same frozen gen-2 n=13 media items, the same
`run_replay` code, config-matched (`CTX_SIZE 32768`, `PARALLEL 2`), on the GB300 through
`agent-gpu`, aggregate output only (D10). This section is additive: the A/B/C/D columns above are
the bake-off as it ran; the survey's two rows are `E` and `F` below and live nowhere else.

|                                                                                                                                                              | **E** Qwen3-VL-30B-A3B Q4_K_M                                                                                                               | **F** Mistral-Small-3.2-24B Q4_K_M                                                                                                                                                                                         |
| ------------------------------------------------------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| weights / source                                                                                                                                             | official `Qwen/Qwen3-VL-30B-A3B-Instruct-GGUF` 17.28 GiB + mmproj Q8_0 0.66 GiB, ungated, header arch `qwen3vlmoe` (128 experts / 8 active) | **no GGUF in the official `mistralai` repo** — mirrors only; ran `unsloth/…-GGUF` 13.35 GiB + mmproj-F16 0.82 GiB, ungated, `quantized_by: Unsloth`, header arch `llama` (the `mistral3` vision tower lives in the mmproj) |
| build that answers the wire                                                                                                                                  | `ai-vlm:sm103-v12` b7972 (loads and answers; see the budget finding)                                                                        | **needs `ai-vlm:sm103-b11090`** — at b7972 its `json_schema` requests 500 (finding ① below)                                                                                                                                |
| **S2** FP rate (n=5)                                                                                                                                         | 0 %, but **only 1 of 5 scored — 4 refused**                                                                                                 | 0 %, [0.000, 0.434], refused 0                                                                                                                                                                                             |
| **S3** `all` (n=8)                                                                                                                                           | 0.25 — 6 of 8 refused (refusals read as unfailable here, so this number is budget-dead, not salience-dead)                                  | 0.875, [0.529, 0.978], 1 refused                                                                                                                                                                                           |
| verdict mix (n=13)                                                                                                                                           | rejected 3 / **failed 10**                                                                                                                  | confirmed 1 / **uncertain 11** / failed 1                                                                                                                                                                                  |
| **S4** latency (indicative)                                                                                                                                  | med 6.7 s p95 23.9 s (the p95 is the max: the truncated items burn the full budget)                                                         | **med 3.8 s p95 8.1 s — the fastest of all six**                                                                                                                                                                           |
| **S5** unparseable                                                                                                                                           | 0 broken, **10 refusals: 9 × `VlmTruncatedError` @ 700 + 1 `ConstrainedDecodingNotEnforced`**                                               | 0 broken, 1 refusal (`break_in_attempt` — finding A's cliff item, now confirmed on a fourth build)                                                                                                                         |
| KV                                                                                                                                                           | 3072 MiB (48 layers; lower than A/C's 4608 despite more layers — the MoE geometry pays less KV, mirroring B's hybrid-class effect)          | 5120 MiB                                                                                                                                                                                                                   |
| VRAM (VLM-only residency on the GB300 — an S1 _component estimate_; S1 proper is the whole stack on 24 GB hardware, F13/spec :387, measured on neither here) | projected 20897 / broker-actual **22688 MiB — exceeds the 20889 MiB (20.4 GiB) S1 budget on the VLM alone**                                 | projected 18688 / broker-actual **20274 MiB (p2 probe) and 20680 MiB (the scored run) — leaves only ≈210–615 MiB of the S1 budget for everything else**                                                                    |
| **tool probe (R3)**                                                                                                                                          | SUPPORTED, both arms, multimodal, arg honoured, exit 0                                                                                      | SUPPORTED, both arms, multimodal, arg honoured, exit 0 (on b11090)                                                                                                                                                         |
| license / provenance                                                                                                                                         | `apache-2.0` HF tag; **header carries no license key** (finding F generalizes: the repo tag is the source)                                  | `apache-2.0` (model card); GGUF header carries no license key AND is third-party-converted — two provenance hops where A/E need one                                                                                        |

**The goal's "nothing past 12 B fits the 20.4 GiB S1 bar at shipped config" is half right, and the
wrong half is the interesting one.** Measured on the GB300 at VLM-only residency (the component
estimate the design's :387 explicitly allows before 24 GB hardware exists — this is NOT an S1
verdict, which is the whole stack on 24 GB hardware, F13): the 30 B-A3B **exceeds the S1 budget on
the VLM alone** (22688 > 20889 MiB), so it is out on fit regardless of the rest of the stack.
Mistral 24 B leaves only ≈210–615 MiB of that budget — technically still "fits," but there is no
room left for the detector and the specialists, which is the majority of what S1's definition
requires resident. So the claim stands in substance ("nothing past 12 B fits the full shipped
stack at 24 GB") and is wrong in its stated reason (24 B is not over the bar by itself — it is a
margin too thin to hold the stack); the A5500 run (2.3, owner-run) is the measurement that settles
it honestly.

**Finding ① — llama.cpp b7972's `response_format: json_schema` path fails against this GGUF, and the
first F row was that failure, not the model.** The first F serve (b7972, the A/C image) replayed
13/13 refused: 5 × `ConstrainedDecodingNotEnforced`, then the shipped breaker OPEN swallowed the
remaining 8 as `VlmUnavailableError` (run `0123c66c` — kept as the artifact's evidence, never
counted). Localized with the endpoint up: `json_schema` requests returned HTTP 500
(`Failed to parse input at pos N`, the string lives in the server binary) at ~75–100 % — **with or
without an image, at PARALLEL 1 or 2** — while plain completion, `response_format: json_object`,
and the _same grammar sent directly_ were 6/6 clean. The enforcement probe's single ENFORCED pass
had passed through the same ~25 % window the s2 probe's arm B kept missing — intermittency, which
is why a one-shot probe is not a line. The same weights on `ai-vlm:sm103-b11090` (already shipped
for candidate B) answered `json_schema` **8/8 clean**, and the scored F row above ran there. None of
A/B/C's models trip this on their own builds, so nothing shipped changes today; the follow-up is
naming the llama.cpp commit that fixed the server-side `response_format`→grammar translation,
since F is the first `llama`-arch GGUF this harness ever ran.

**Finding ② — the survey's answer to "does past-12 B earn its keep?" is no, and it arrives on the
budget axis, not the quality axis.** E's dominant failure is finding A's class at model scale: 9 of
13 replies hit the shipped 700-token verdict budget `stop='length'` — a bigger model writing a
longer verdict answers the same wire WORSE, and `break_in_attempt`'s truncation ladder (finding A/G)
now has a third shape: deterministically over budget on its own, not just at the probe cliff. F
fits the budget (median 3.8 s, the fastest reply of any candidate) and pays for it in hedging: 11 of
13 `uncertain`. Neither model shows a quality gain the n=13 corpus could even see.

**The criterion-differentiation read, reconciled.** The goal's parenthetical "(A 4B flat-repeated
evidence 7/11; B/C differentiated all)" is two measures compressed into one clause; the recipe is
reproduced here from the stored replies because the transcript's original was never written down
(`$AGENT_GPU_DIR/out/eval-store/gen-2/tools/crit_diff.py`, aggregate counts only). Over answered
items (a stored reply whose criteria rows carry evidence):

- **m1 — single-criterion answers** (exactly 1 criteria row: nothing to differentiate):
  A **7/11** — the goal's number reproduces exactly. C 7/13, B 0/12, E 1/3 (only 3 items answered),
  F **9/12**.
- **m2 — repeated evidence across criteria** (≥2 criteria, fewer distinct evidence strings than
  rows): A 1/11, B 1/12, **C 0/13** ("differentiated all" is an m2 statement), E 0/3, F 0/12.

Read the pair together and the "larger models differentiate better" story does not hold: the 4 B's
headline 7/11 is m1, and under that same measure C is 7/13 and F is 9/12 — the bigger models answer
single-criterion just as often; under m2 every candidate is near-clean, so m2 ranks nothing at
n = 13. Neither measure separates anything the report's own non-claim (n=13 is a grammar floor,
F14) does not already forbid.

**Registration claim, restated as measured.** "All five architectures register in our llama.cpp
build": the four GGUF-expressible survey archs (`qwen3vl`, `qwen3vlmoe`, `nemotron_h`, `mistral3`)
are REGISTERED — verified by string in `libllama.so` of `ai-vlm:sm103-v12` (an earlier grep against
the executable alone said ABSENT; the registry lives in the shared library, not the binary). The
fifth, Cosmos-Reason2-8B, cannot even be read: its HF `config.json` is gated (401) and it has no
GGUF — D's BLOCKED stands.

**Commands (for re-run, not for re-belief):** pull by
`curl -sSL -C - --retry 5 https://huggingface.co/<repo>/resolve/main/<file>` into
`$AGENT_GPU_DIR/models/vlm/` + `chmod 644` (finding F's read bit again; both pairs landing at once
was checked and impossible — `df` read 29 G free against 32.1 GiB of weights — so the survey ran
one weight set at a time and deleted each after its leg: E first, then F; the bake-off's own A/B/C
weights were not touched. Both survey files landed at their exact HF-reported byte counts). Serve exactly C's row shape with
`--mount models:/models --env MODEL_PATH=/models/vlm/<file> --env MMPROJ_PATH=… --env
GPU_LAYERS=auto --env CTX_SIZE=32768 --env PARALLEL=2 --env PORT=8098 --vram` declared honestly
(28672 E, 22528 F; broker actuals 22688 / 20274–20680). Replay:
`uv run python -m backend.evaluation.vlm_replay --store "$AGENT_GPU_DIR/out/eval-store/gen-2"
--candidate <file>@<image> --vlm-url http://host.docker.internal:18100 --out <report>` with
`FOSCAM_BASE_PATH=$AGENT_GPU_DIR/out/media` (the stock-media capture-root guard; the first attempt
without it refused all 13 items before any read — the guard working, not a model failure). Reports:
`gen-2/reports/2.4-survey-{qwen3vl-30b,mistral-24b,mistral-24b-b11090}.json`; runs
E `e4ea8bbd`, F-artifact `0123c66c`, F `90ed4690`, all pinned `d3794497`;
`agent-gpu rm` after each serve → `containers: []`. These are GB300 readings: **indicative only
(F13), never bar verdicts (F14), and not a pick** — the M2 decision still belongs to the owner.

## M2 resolved by owner instruction (dated 2026-09-28, ledger item 35); the table above is NOT rewritten

The owner picked, verbatim: **"lets go with Qwen3-VL-8B for now. we can revisit later if needed."**
Column **C — Qwen3-VL-8B-Instruct Q4_K_M** is the shipped serving VLM, and the shipped default moved
to it (`.env.example`, compose, `Settings.vlm_model_id`, spec rev 7). Nothing in the table above is
edited, reordered, or re-scored; this section is additive, in the same shape as the two errata above.

**What this corpus decided, and what it did not.** Stated again plainly because it is this report's
own standing non-claim (§"What this report explicitly does not do") and the pick does not quietly
retire it: **n=13 ordered nothing.** Every S2/S3 figure here is GB300-indicative (F13) and never a
bar verdict (F14), and the C-vs-A gap in the verdict mix is inside what 13 items can separate. The
pick was made on **resource shape and build dependency** — the axis this report did have evidence on
(KV geometry from the GGUF headers, the fit readings, the b7972/b11090 build finding) — which is
exactly the use the report said its evidence could support and no more.

**The flip conditions, written falsifiable while they are fresh** — each is a measurement that
reopens the pick, not a mood:

1. **8B fails S1 on 24 GB hardware** ⇒ fall to the 4B pair. It is the named fallback row in the
   A5500 handout, so this aborts onto a model with a number rather than into a re-run.
2. **KV density turns out to bind stream count** ⇒ **Nemotron-Nano-12B-v2-VL reopens ahead of both**:
   its KV is 768 MiB against our 4608 MiB (6 KV layers of 63 vs 36 of 36). This is the one axis where
   a candidate beat the pick on measured evidence, and it beats it on a bigger model too.
3. **Post-item-19 corpus S3 < `S3_MIN` 90 %**, or C's `uncertain` rate 0.231 proves to be a real
   hedging prior rather than 13-item noise ⇒ the pick reopens.

**What is NOT adopted from this report:** no S#/D# text change beyond rev 7's identity sentences, and
the `uncertain` spread stays a 13-item hint. The A/B/C/D table remains the historical candidate set —
it is what ran, and rewriting it would destroy the only comparison anyone can re-check.
