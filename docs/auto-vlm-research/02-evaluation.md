# 02. Evaluation, the Pareto front and anti-gaming

> Design proposal; nothing is built. Paths and numbers cited as evidence are as of `origin/main` `9cb9e60b0` (2026-10-23). Back to the [index](README.md).

## 1. Why autocuda's measurement model does not transfer

autocuda ranks trials by geomean speedup over a reference, measures noise as the coefficient of variation over five reruns, and declares a stall when the record improves by less than 0.25% in an hour. Each assumption breaks here.

- **Reruns are identical.** Replays decode greedily; the sweep's three controls matched on 450 of 450 items. A rerun-based noise estimate reads zero, which is wrong.
- **The uncertainty is the sample.** `tierb-v0` holds 450 stills in 31 scenarios. Stills of one scenario are not independent, so the honest intervals are clustered by scenario and run 6 to 26 points wide (`docs/benchmarks/synthbench/sweep-2026-10-03/report.md`, "Why the rule is this hard to pass"). A search that keeps the best of hundreds of trials on that sample reports the luckiest one.
- **A ratio of rates breaks.** S2 is a false-alarm rate where lower is better. A recipe that calls everything benign drives S2 to zero and its "speedup" to infinity.
- **The step is coarse.** One incident of 241 is worth 0.41 points of S3, so a 0.25% stall threshold means nothing.

## 2. Data, splits and epochs

**Sources** (decision D2): the existing `tierb-v0` export, fresh synthbench batches rendered for the search, and public datasets for training only.

**Splits** are drawn by whole scenario with a published hash, as ISS-016's split is (`synthbench/export/vss.py`, `draw_split`). Three tiers:

| Tier    | Visible to                         | Used for                                                      |
| ------- | ---------------------------------- | ------------------------------------------------------------- |
| train   | Workers, per item                  | Error analysis; LoRA and system-1 training (with public data) |
| select  | Workers and manager, as aggregates | Ranking and the Pareto front                                  |
| holdout | The owner's `confirm` verb         | One OD-26 confirmation per candidate                          |

**The holdout must include benign items.** ISS-016's holdout holds 6 incident scenarios and no benign items, so it cannot check S2 at all (`docs/benchmarks/synthbench/dogfood-2026-10-06/summary.md`). The first fresh batch should over-sample benign hard negatives, both for a holdout that can measure S2 and because 209 benign items cannot certify a 5% bar.

**Epochs rotate the data.** Each epoch renders a fresh scenario batch. Rendering stops the flagship that the workers run on, so it happens between epochs with the fleet drained ([`05-stack-integration.md`](05-stack-integration.md) §4). The previous select set moves into train, and the new batch supplies the next select set. The scorer's query ledger counts select queries per epoch, and `autovlm status` reports the count against a budget, so the manager sees when a select set is wearing out. Fresh data each epoch is the strongest defence against adaptive overfitting: knowledge the search gathered about last epoch's select set does not transfer to this epoch's.

## 3. Realistic inputs

The executor runs the recipe's detector and specialists over every item and caches the results. The VLM never receives the declared subjects and props that the current replay passes as oracle detections.

This lowers the baseline, honestly. In the sweep the shipped model hit 74 of 95 object-cued incidents, a group whose cues the oracle names outright (sweep report, "S3 by scenario group"). A production detector does not emit "crowbar". The first deliverable of phase P1 is the realistic baseline per tier, and every later claim is measured against it.

## 4. What every trial records

On the select split:

- **Primary accuracy:** S3 at the threshold that yields 5% S2 **on the train split**, applied unchanged to select. Fitting the threshold on the split being scored flatters the result.
- **Also reported:** S2 and S3 at that threshold with scenario-cluster intervals; AUROC; S2 and S3 at the shipped floor of 60, for comparison with OD-29; S3 per scenario group (stranger or intent, context risk, object cued); refusal, uncertain and truncation rates.
- **Cost:** estimated resident VRAM of the **whole stack** (detector, specialists, VLM weights, projector and KV cache at the configured context) and latency median and p95. GB300 readings are indicative only (F13); tier fit is confirmed on Brev (§5).

## 5. GPU tiers and the Pareto front

**Buckets** follow the budgets of `docs/vss-integration/20-model-tiers-benchmark-and-training.md` §3, at 0.85 of card memory, plus one unbounded bucket for the GB300 ceiling:

| Card   | 10 GB   | 12 GB    | 16 GB    | 24 GB    | 32 GB    | 48 GB    | GB300     |
| ------ | ------- | -------- | -------- | -------- | -------- | -------- | --------- |
| Budget | 8.5 GiB | 10.2 GiB | 13.6 GiB | 20.4 GiB | 27.2 GiB | 40.8 GiB | unbounded |

A trial sits in the smallest bucket its stack fits, and competes in that bucket and every larger one.

**A trial joins a front** when, against that tier's incumbent on the same select items, a paired bootstrap that resamples whole scenarios shows OD-26's two conditions: no clear harm (the upper bound of the S2 change is at most +2 points and the lower bound of the S3 change is at least −5 points) and clear benefit (the upper bound of the S2 change is below zero, or the lower bound of the S3 change is above zero). A stack that fits a smaller bucket with no clear harm also joins, because it moves the front down a tier. The margins are OD-26's at the stamp; the harness reads them from configuration, so the owner can change them.

**Brev confirmation.** A front member counts as a tier result only after a Brev card of that tier measures its VRAM and latency (S1, S4) on the pinned llama.cpp build. Until then `autovlm status` marks it provisional.

## 6. The noise floor: a null-perturbation envelope

Rerun variance is zero, so autovlm measures what meaningless changes do instead. Once per epoch the executor runs the incumbent of each tier under three null perturbations:

1. **The other llama.cpp build.** Two builds disagree on 44% of items for the same weights and prompt (ISS-087).
2. **Two prompt paraphrases** that preserve meaning.
3. **A JPEG re-encode** of the inputs.

The spread of S2 and S3 changes across these runs is the envelope. A trial's gain counts as **improved** only if it clears both the cluster interval and the envelope; otherwise it is **neutral**. The display borrows autocuda's improved, neutral and regressed labels.

**A new epoch starts** when no tier's front has changed for a set number of trials or hours, replacing autocuda's 0.25%-per-hour rule.

## 7. Anti-gaming

Three layers, from strongest to weakest.

**Layer 1: by construction.**

- Inputs are blinded ([`01-architecture.md`](01-architecture.md) §3.3).
- Labels live behind the scorer's uid and socket (§3.6 there).
- Select answers are aggregates only; the holdout answers the owner alone.
- The search manifest is an allow-list. The scorer, splits, export and taxonomy are outside every worktree.

**Layer 2: mechanical checks on every trial.** A failed check records the trial as a failure.

| Check                    | Catches                                                                                                                     |
| ------------------------ | --------------------------------------------------------------------------------------------------------------------------- |
| Vocabulary               | Prompts, templates or plugins that contain taxonomy scenario names or generator prompt vocabulary                           |
| Refusals and truncations | More than the incumbent's                                                                                                   |
| Uncertain-rate cap       | Buying a low S2 by abstaining: the Qwen3.6-35B-A3B arm reached 3.8% S2 by calling 140 of 450 items uncertain (sweep report) |
| Degenerate output        | A constant score, or a verdict distribution collapsed to one value                                                          |
| Group non-regression     | A gain in one scenario group bought by a loss in another, beyond a set margin (doc 23's B+C guard)                          |
| Manifest                 | A diff outside the allowed paths                                                                                            |

**Layer 3: judgement.** At the end of each epoch an auditor reviews every trial that changed a front. It looks for what a check cannot express: rules keyed to generator artefacts, time-of-day shortcuts that mirror the taxonomy's sampling, and prompt text that teaches the select set's scenes. A finding reclassifies the trial and taints its descendants, so the front falls back to the last clean member.

## 8. How a winner leaves the harness

The harness never changes `main` or the product. A front member becomes a candidate, and then:

1. **Brev tier confirmation** on the pinned build (§5).
2. **One OD-26 holdout confirmation**, invoked by the owner.
3. **An owner ruling**, with the existing gates still in force: thresholds are owner territory (doc 23 §3), and a new specialist needs an owner-approved spec revision and a false-alarm check on the owner's night footage.
4. **A product PR** that turns the recipe into backend configuration and code, carrying the build identity that ISS-087 requires.
