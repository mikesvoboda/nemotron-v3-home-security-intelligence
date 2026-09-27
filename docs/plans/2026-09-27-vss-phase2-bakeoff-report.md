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
