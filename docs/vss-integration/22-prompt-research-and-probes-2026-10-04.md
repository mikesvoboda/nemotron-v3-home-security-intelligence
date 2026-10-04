# 22. Prompt research and the risk-score probes (2026-10-04)

> Frozen research record, like docs 00-14: this describes what was measured and learned on
> 2026-10-04 about the `vlm_assess` prompt, not what is true today. What the stack runs is
> [README section 2](README.md) and
> [the current-state page](../architecture/ai-pipeline-current-state.md). Everything here is
> **[A]** agent-authored except quoted sources. Provenance levels used below:
> **V** = the researcher (or agent) read the primary artifact (paper body, repo file, shipped
> template bytes, llama.cpp source); **L** = abstract/title verified via API, body not read —
> treat as a pointer, not a finding; **I** = inference.

## 1. Why this doc exists

Three probes over one month tried to fix a measured failure: the shipped one-call VLM verifier
answers `confirmed` with `risk_score` 0-10 on genuinely suspicious scenes (sweep A-group
0/64, S3 39%). The probes and two dispatched online research tracks (2026-10-04) converged on
the same conclusion, and it is not a prompt-wording conclusion. This doc records all of it so
the next attempt (and the eventual Tier-C decision) starts from evidence.

## 2. The probes (measured on GPU, single still per event, shipped client + grammar, temp 0)

Harness: transport-shim arms over the shipped `VlmClient` (only prompt text / request fields
change; grammar, grounding rows, breaker intact). 37 events = 17 incidents (floors 30/60 by
expected band) + 20 benigns (S2 guardrail; FA = confirmed AND score >= 30). Incident set
reproduces probe 1's events; the `ship` arm reproduces the sweep control bit-exactly (temp-0
identity check — any delta is the text).

| probe | question                                                                      | result                                                                                                                                                                                                                                                                                                                                                                                                                                                         |
| ----- | ----------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1     | do 4 ordered clip-frames beat the single still, same prompt?                  | **null.** 0/17 hits either way; all scores 0-10 under `confirmed`. Reframed the failure as calibration collapse, not perception.                                                                                                                                                                                                                                                                                                                               |
| 2     | does a band rubric + frame-context note lift scores? (run at 1024 max_tokens) | partial, confounded: rubric lifted scores to 20-25, frame-note alone did nothing — and one rich arm truncated by call 6. The truncation finding promoted the `max_tokens` raise (1024 -> 2048, commit `26b900bc`, README section 2 row).                                                                                                                                                                                                                       |
| 3     | which Tier-A text component moves what? 5 arms x 37 events at 2048            | **moves the operating point, not the discrimination.** ship 0/17 hits, 0/20 FA -> best arm 5/17 hits, **8/20 FA**; AUROC 0.39 -> 0.59. The 25-30 plateau sits ON the FA line on both sides; the behavior taxonomy fired 60 on flashlight/face-covering benigns; floor-60 scenarios (peering, trying car doors) hit 0 times in every arm. Zero truncations, zero verdict flips. No arm advances to the 450-still replay (S2 gate fails at ~40% FA on this set). |

Probe 3 artifacts: `results3.jsonl` (185 rows) and the arm texts live in the session
scratchpad (not durable); the arm ladder is specified in `prompt-draft-1.md` (two
INDEPENDENT questions + band names / + taxonomy / + tiebreakers / + point examples).
**Open follow-up: bank the arm texts in-repo before the scratchpad is lost** (ISS pending).

**Probe 4 (complete 2026-10-04, corrected — see the concurrency note below).** Arms:
NVIDIA-condensed criterion text (`nc`), the same text with `repeat_penalty: 1.0`
(`nc_rp1`), and a describe-then-score two-turn arm (`nc_2turn`, floor-60 incidents + 5
named benigns only). On the 37-event set:

| arm        | incident hits | benign FA | AUROC |
| ---------- | ------------- | --------- | ----- |
| `nc`       | 12/17         | 17/20     | 0.625 |
| `nc_rp1`   | 11/17         | 16/20     | 0.643 |
| `nc_2turn` | 1/11          | 4/5       | 0.300 |

Reading **[I]**: `nc` confirms probe 3 — criterion text lifts hits (12/17, best yet) while
FAs rise with them; still no arm through the S2 gate. `repeat_penalty: 1.0` is a **real,
large, and useless** effect: it changes the score on 8 of 37 events in BOTH directions
(a floor-60 incident falls 60 → 30 and loses its hit; three others rise), yet the AUROC
gap vs `nc` is ~6 of 340 pairs — the sampler-order mechanism (section 4.4) is confirmed,
but the effect is a reshuffle, not a lift. **`nc_2turn` collapses (AUROC 0.300)**: the
free description makes the model more literal — it scores the calm description it just
wrote. The cheap simulation says the Tier-C field reorder is not worth its contract cost
as this shape; VCAP's gain needs a separate judge stage, not a self-described one-shot.

**Concurrency correction (2026-10-04 ~19:07-19:14 UTC).** The first 11 events per arm were
run while a second client shared the server; batched greedy decoding differs from solo, so
those rows were invalid. All 11 were re-run solo on an idle server; 5 of 29 re-run
(verdict, score) pairs changed, and the table above is the corrected merge
(`results4-final.jsonl`, 90 rows). Pre-correction the same data read
`nc` 0.609 / `nc_rp1` 0.666 with `nc_rp1` taking 12/17 hits — the contamination had made
the penalty arm look better than it is. The rule this came from: **one client per server,
always** (the stage-1 experiment kit guards this mechanically).

EV-over-logprobs follow-up (G-Eval-style expected value over `risk_score`'s first digit,
section 3, from the same runs' captured logprobs) — **complete at full n, non-win.** First
run on the provable-clean 26-event subset (6 incidents): EV ≈ argmax (nc 0.625 vs 0.663;
`nc_rp1` 0.708 both). Re-run at full n (37/arm, 17 incidents; alignment re-proven 74/74 by
content equality with offset and cross-arm controls, both audits unrebutted; EV_C = the
primary two-position variant): AUROC nc argmax 0.6250 vs EV_C 0.6324, `nc_rp1` 0.6426 vs
0.6676 — paired-bootstrap gaps −0.007 [−0.109, +0.089] and −0.025 [−0.109, +0.055],
P(argmax wins) 0.43/0.26: coin-flip. What looks like an EV edge is **tie-breaking, not
signal**: argmax ties 31-36% of incident×benign pairs (20 of 37 rows emit exactly 30),
EV_C ties 0% — it converts 0.5-credits into random credits. On the native-floor rule EV_C
is strictly worse: 7/17 hits vs argmax's 12/17 (`nc`) buying 6 fewer FA — the same trade,
3× the n. Median |EV − argmax| ≈ 0.1 point: the grammar saturates the digit distribution,
leaving no mass to monetize. The subset's higher argmax numbers did NOT carry
(0.6625 → 0.6250; 0.7083 → 0.6426) — a caution on subset-first reading [I].

## 3. What the external evidence says (researcher track 1: few-shot, calibration, ordering)

Each line: finding — source — provenance. Flag **[text-only]** = LLM-text study, transfer to
an 8B VLM is by analogy.

**Exemplars are the wrong lever for this model class.**

- Many-shot ICL helps closed frontier models log-linearly; "open-weights multimodal
  foundation models like Llama 3.2-Vision **do not benefit** from the demonstrating
  examples." — [arXiv:2405.09798](https://arxiv.org/abs/2405.09798), 14-dataset ablations — V.
- The mechanism: current MLLMs cannot in-context-tune from raw exemplar stacks; recovery
  needs Multimodal Task Vectors (white-box activation access we do not have). —
  [arXiv:2406.15334](https://arxiv.org/abs/2406.15334) — V.
- Multi-image is a documented MLLM weak spot across families. —
  [arXiv:2407.15272](https://arxiv.org/abs/2407.15272) (MIBench) — V.
- No study found on image+JSON exemplars for risk/severity calibration specifically. Absence
  verified across arXiv/OpenAlex title+abstract search — I.

**The verbalized number is a weak readout; anchoring is real but coarse.**

- VLM verbalized confidence is severely miscalibrated, worst at small sizes, biased toward
  overconfidence. The measured fix (VCAP) is **describe-then-judge** (two-stage), not rubric
  wording: ECE 0.467 -> 0.424 at 7B-class. —
  [arXiv:2505.20236](https://arxiv.org/abs/2505.20236) — V. **This is direct support for the
  reason-before-score field reorder.**
- Anchoring by prior scores: 185,271 evaluations, Cohen's d up to 0.71; **presence** of
  anchored values redistributes the output distribution while the value itself barely
  matters; CoT instructions and "disregard the anchor" warnings do not reduce the effect. —
  [arXiv:2608.25869](https://arxiv.org/abs/2608.25869) — V. [text-only] **Probe 3's 25-30
  plateau across all arms is this: the band numbers anchor, the behavior prose barely
  differentiates.**
- Verbalized scores are systematically overconfident; white-box methods only narrowly beat
  black-box; no elicitation method consistently wins; post-hoc recalibration beats prompt
  tweaks. — [arXiv:2306.13063](https://arxiv.org/abs/2306.13063),
  [arXiv:2305.14975](https://arxiv.org/abs/2305.14975) — V;
  [arXiv:2412.14737](https://arxiv.org/abs/2412.14737),
  [arXiv:2410.06707](https://arxiv.org/abs/2410.06707) — L (pointers). [text-only]
- Open judge LMs "issue scores that significantly diverge from those assigned by humans";
  G-Eval scores by **token-probability-weighted expected value over the scale** precisely
  because greedy discrete scores cluster. — [arXiv:2405.15801](https://arxiv.org/abs/2405.15801),
  [arXiv:2303.16634](https://arxiv.org/abs/2303.16634) — V. [text-only] **Supports an
  EV-over-logprobs read of `risk_score`'s first digit as a cheaper better estimator than the
  argmax digit (probe 4 captures the logprobs).**

**The exact failure mode is published.**

- "Are Multimodal LLMs Ready for Surveillance?" (zero-shot VAD, prompt-specificity and
  temporal-window ablations): "pronounced conservative bias... disproportionately favor the
  'normal' class... high precision but a **recall collapse**"; **class-specific instructions
  moved the boundary F1 0.09 -> 0.64** on ShanghaiTech; recall remains the bottleneck; the
  authors call for recall-oriented prompting. —
  [arXiv:2603.04727](https://arxiv.org/abs/2603.04727) — V, multimodal. **The single closest
  external analogue of the shipped pipeline's failure and of the fix direction.**
- 7B-class VLM scoring benchmark: "extreme prompt sensitivity, with accuracy swings of up to
  32 percentage points on identical images depending solely on prompt phrasing" and "severe
  class collapse... 85-100% of predictions to a single level." —
  [arXiv:2606.21861](https://arxiv.org/abs/2606.21861) — V (abstract-level), domain-analogy
  only.

**Commit-before-justify is a documented pathology of our field order.**

- Under JSON-schema constraints, 100% of GPT-3.5 JSON-mode replies put `answer` before
  `reason` (models self-sabotage CoT under JSON mode); GSM8K under constraint: LLaMA-3-8B
  75.13 -> 48.90; the mitigation that worked was free-form-then-reformat. —
  [arXiv:2408.02442](https://arxiv.org/abs/2408.02442) ("Let Me Speak Freely?") — V.
  [text-only, but the field-order row is our exact situation and the 8B row is our class]
- "The Format Tax": format-requesting instructions alone cause most of the accuracy loss,
  before any decoder constraint — i.e. the grammar is not the main suspect, the instruction
  block is; adding more JSON-exemplar prompt surface is on the wrong side. —
  [arXiv:2604.03616](https://arxiv.org/abs/2604.03616) — V. [text-only]
- Hard-constraint masking "pushes decoding toward locally valid yet semantically incorrect
  trajectories"; draft-then-constrain recovers up to +24pp at 1B. —
  [arXiv:2603.03305](https://arxiv.org/abs/2603.03305) — V. [text-only]
- On 7B video VLMs, forced CoT does not improve accuracy and slightly hurts the 7B row —
  reasoning-BEFORE-answer as free text is supported (VCAP, NVIDIA), verbose CoT is not. —
  [arXiv:2606.22862](https://arxiv.org/abs/2606.22862) — V.

**Multi-frame contract.**

- Hallucination grows monotonically with image count; position of content within the image
  sequence matters (mitigation offered is inference-side, not prompt-side). —
  [arXiv:2508.00726](https://arxiv.org/abs/2508.00726) (MIHBench) — V. **4 frames are
  measurably worse than 2; the key-frame selector's ceiling of 4 is on the right side of
  this, going lower is defensible.**
- Multimodal primacy/recency: attention concentrates at sequence start/end; deliberate
  placement +14.7% / +17.8% with no extra compute. —
  [arXiv:2410.16983](https://arxiv.org/abs/2410.16983) — V. Practical: the most diagnostic
  frame goes last (adjacent to the text) or first, never the middle.
- NVIDIA ships per-frame timestamp instructions by default (`RTVI_ADD_TIMESTAMP_TO_VLM_PROMPT`,
  "Frame 1 corresponds to timestamp..."); Cosmos-Reason was trained with timestamps burned
  into frames. Frame labels + deltas are the vendor-validated pattern. —
  [NVIDIA VSS docs, real-time-vlm](https://docs.nvidia.com/vss/latest/real-time-vlm.html),
  [Cosmos-Reason1-7B card](https://huggingface.co/nvidia/Cosmos-Reason1-7B) — V (docs).

## 4. What NVIDIA's own VSS prompts do (researcher track 1, read from the open repo) — and track 2's format findings

1. **NVIDIA never asks the VLM for a 0-100 number.** In the alert microservice the VLM
   verifies authenticity with a 3-valued verdict (`confirmed / rejected / unverified` —
   exactly our vocabulary); **severity comes from rule-based Behavior Analytics** (proximity,
   dwell, tripwire, zone entry). An architectural argument against the numeric core of our
   contract: compute risk from detector/track facts, let the VLM supply the evidence verdict.
   — NVIDIA VSS alert docs + `services/alert/blueprint_config/*.json` — V.
2. **Every NVIDIA event-verification blueprint reasons BEFORE the constrained answer**
   (`<reasoning>...<answer>...</answer>`), even though the answer region is strict. Their
   warehouse near-miss prompt attacks our failure mode with named devices: operational
   definitions for the NEGATIVE class as well as the positive; a frozen-person counterfactual
   ("if the pedestrian had FROZEN in place, would the forklift have reached them?");
   anti-calmness ("NEAR MISSES CAN LOOK CALM — the danger is in the geometry, not the
   emotional response"); a self-audit ("Am I dismissing a genuine near miss because I
   described it using words like 'routine'?"). Their full prompt is ~1,900 words; the
   transferable part at our budget is the criterion reformulation + one counterfactual +
   the anti-calmness clause (probe 4's `nc` text). — V.
3. **Grammar is invisible to the model** (llama.cpp grammars/README, verbatim: the schema
   "is not injected into the prompt... describe it explicitly in your prompt") — band
   semantics must be prose; only shape is free. `minimum`/`maximum` compile into the grammar
   **only for `"type": "integer"`, not `number`** — keep `risk_score` integer or the 0-100
   bound silently evaporates. — [grammars/README.md](https://github.com/ggml-org/llama.cpp/blob/master/grammars/README.md) — V.
4. **Temp-0 "greedy" is not the model's argmax.** Verified in llama.cpp source: the default
   sampler chain runs penalties first (`repeat_penalty` default **1.1**, before temperature),
   and penalty resampling sees grammar-feasible candidates — digits included. Determinism
   holds (our replay matched bit-exact), but the ranking can be penalty-shaped. Probe-4
   `nc_rp1` tests it; `"repeat_penalty": 1.0` or `"samplers": ["temperature"]` are the knobs.
   — `common/common.h` sampler order, server README — V.
5. **Qwen3-VL's native grounding format IS our 0-1000 convention** (tech report §3.2.4 —
   deliberately changed FROM Qwen2.5-VL absolute pixels; the "Qwen prefers its own format"
   lore describes older generations). `bbox_2d`/`point_2d` key names are version-pinned, not
   guaranteed forward. Qwen3-VL adds per-frame text timestamps for VIDEO only (`<3.0
seconds>`); stills get no template timestamps — frame labels must be our own prose, or
   the official `add_vision_id` (`Picture N:`) via per-request `chat_template_kwargs`. —
   [arXiv:2511.21631](https://arxiv.org/abs/2511.21631), Qwen3-VL README/cookbook, shipped
   `tokenizer_config.json` — V.
6. **Qwen officially recommends against temperature 0** (modelcard: temp 0.7 / top-p 0.8 /
   top-k 20 / presence 1.5; presence_penalty 0-2 documented to fight repetition with a
   language-mixing caveat). Our greedy choice is off the vendor's operating point — deliberate
   (replay determinism), but it should be a stated trade-off, not an assumption. — V.

## 5. Qwen vs Gemma: what is portable (researcher track 2, full report `/tmp/research/qwen-gemma-report.md`, bank this file)

- **Semantics carry, format does not.** "Format performance only weakly correlates between
  models" — one fixed prompt format across models is methodologically unsound for comparison
  (Sclar et al., [arXiv:2310.11324](https://arxiv.org/abs/2310.11324), up to 76pt swings from
  meaning-preserving reformatting) — V. **This flags the 15-arm sweep's cross-model ranking:
  it compared families under one format. Finalist re-qualification should run top-2 models x
  2-3 formats. [A]**
- Documented family-specific knobs (system-role placement; exemplar count — **Gemma's own
  vision evals are 4-shot, Qwen's are 0-shot + one-line format instruction**; CoT prose —
  official for Qwen, explicitly NOT used in Gemma vision evals; fence habit — Google's vision
  docs expect ```json fences, ungrammatical under our grammar; box key/axis order —
  Qwen `bbox_2d` [x1,y1,x2,y2] vs Gemma `box_2d` **[y1,x1,y2,x2]**, a silent swap trap). — V
  across Qwen/Gemma docs, tech reports, shipped templates.
- **Neither family documents anything about numeric score bands or rubric anchoring**
  (verified absence both sides). Our rubric work has no primary-source cover on either side;
  synthbench IS the evidence. — V (absence).
- **Gemma 3 is legacy** (Gemma 4 shipped 2026: native system role, thinking toggle,
  configurable visual-token budget {70..1120}, MM:SS per-frame timestamps, variable aspect
  ratio). The sweep already tested gemma4 rows; any future swap is a Gemma 4 evaluation, and
  the swap cost is dominated by llama.cpp plumbing, not prompt wording (open issues #22396
  `--json-schema` sampler crash on Gemma 4 AND Qwen3-class, #23677 grammar-stack crash;
  keep a hand-written GBNF path). Gemma 3 tile facts: 896x896, 256 tokens PER TILE, pan&scan
  OFF by default (adaptive 1xN strips; a 1920x1080 frame = 3 tiles/768 tokens; square frame
  = 1 tile/256). — V (HF API, official docs, transformers source).

## 6. What follows, in ascending cost [A]

1. **Criterion reformulation, still pure text** (probe 4 `nc`): exposure/precursor criterion,
   operational NEGATIVE class, frozen-person counterfactual, anti-calmness clause. No behavior
   exemplar numbers beyond the band ladder (anchoring presence is the mechanism; extra
   exemplars are the Format Tax side).
2. **Better scalar estimators, contract intact**: expected value over `risk_score`'s first
   digit from logprobs (G-Eval precedent); `repeat_penalty: 1.0`; and per-frame `Picture N:`
   labels via `chat_template_kwargs` for bursts. A post-hoc score recalibration on synthbench
   if the shape remains band-shaped.
3. **Tier C, owner-gated, now with evidence**: reason-before-score (description field before
   `risk_score` in schema+grammar — VCAP measured the same structure as describe-then-judge;
   NVIDIA ships reasoning-before-answer) and, more radically, **severity from detector/track
   features with a 3-valued VLM verdict** (NVIDIA's actual architecture; the VLM's numeric
   judgment removed). Probe 4's `nc_2turn` arm simulates (2) cheaply before (3) is proposed
   with data.
4. Whatever the outcome: the 450-still replay remains the gate for S2/S3, and any model-choice
   re-ranking runs >= 2 prompt formats (section 5).

## 7. Register pointers [A]

- The sweep one-format ranking caveat (section 5) belongs in `17-action-plan.md` as open
  work for the finalists' re-qualification.
- ~~"Bank probe arm texts + probe logs in-repo" (section 2) is open.~~ **Done** — the
  arm ladder, probe scripts, probe 3/4 result rows and both researcher tracks' full
  reports are in [`docs/research/2026-10-04-vlm-prompt/`](../research/2026-10-04-vlm-prompt/README.md);
  the multi-MB logprobs captures stayed out of the repo.
