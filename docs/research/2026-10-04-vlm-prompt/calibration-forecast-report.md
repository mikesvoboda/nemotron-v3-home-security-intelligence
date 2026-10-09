# Prompt/schema research for VLM risk-score calibration (Qwen3-VL-8B-Instruct Q4_K_M, llama.cpp llama-server, grammar-constrained single JSON reply, 1-4 stills)

All arXiv IDs below were verified against the arXiv API and/or OpenAlex by DOI->title lookup; a few items are marked
"**ID/title verified, body not read**" — treat those as pointers, not as sourced numbers. Anything labelled
_[LLM-text-only]_ may not transfer to an 8B VLM.

Verified local context (for fit-checking): the shipped prompt lives in
`/agents/agent-vss5/workspace/backend/services/vlm_client.py` (`_render_prompt`, ~line 531-567): the risk instruction is the
single clause "how threatening it is (risk_score 0-100)"; field order is verdict, risk_score, summary, reasoning,
description, criteria, provenance. Response schema: `/agents/agent-vss5/workspace/backend/ai_contract/schemas/vlm_assess.response.json`.

---

## Q1. Few-shot / in-context exemplars for VLMs producing structured JSON

- **Open-weight multimodal models often do NOT benefit from exemplar stacks; closed frontier models do.** Many-shot ICL in
  multimodal foundation models: GPT-4o / Gemini 1.5 Pro improve log-linearly up to ~2,000 exemplars across 14 datasets, but
  "open-weights multimodal foundation models like Llama 3.2-Vision **do not benefit from the demonstrating examples**."
  Most important caveat for an 8B open VLM: do not assume the GPT-4o "show worked examples" playbook transfers.
  — _Many-Shot In-Context Learning in Multimodal Foundation Models_, https://arxiv.org/abs/2405.09798 — paper with 14-dataset ablations.
- **Mechanism: current MLLMs cannot "in-context tune" from raw exemplars**; Multimodal Task Vectors (compressing a large exemplar
  set into an activation-space vector) recover many-shot gains that raw exemplar prompting fails to produce. The published
  workaround needs white-box activation access a chat-completion deployment does not have.
  — _Multimodal Task Vectors Enable Many-Shot Multimodal In-Context Learning_, https://arxiv.org/abs/2406.15334 — paper with ablations.
- **Multimodal ICL is a documented weak spot of current MLLMs generally.** MIBench (13 tasks / 13K samples, includes a multi-image
  in-context-learning section): "current models excel in single-image tasks, but exhibit significant shortcomings when faced with
  multi-image inputs." — https://arxiv.org/abs/2407.15272 (EMNLP 2024) — paper with ablations, multimodal.
- **Worked examples that display JSON teach format, not judgment — and format surface is the part measurably associated with
  degradation in open-weight models** (see Q4: the format tax is mostly in the _prompt_, before any decoder constraint).
  Adding 4-8 full input->JSON exemplars buys you format conditioning you already get free from the grammar.
  — _The Format Tax_, https://arxiv.org/abs/2604.03616 — paper, 6 open-weight + 4 API models x 4 formats. _[LLM-text-only]_
- **Where few exemplars demonstrably act is the score distribution, via anchoring** (see Q2). Exemplar scores should be expected
  to behave as anchors, not as demonstrations of reasoning; and the anchoring effect is threshold-like (presence matters more than
  exact values), so 3-5 band-defining lines are enough — the exemplar COUNT trade is mostly token cost, not quality.
  — _inference_, grounded in https://arxiv.org/abs/2608.25869 (see Q2).
- **Explicit gap:** no paper found that studies image+input+desired-JSON exemplars specifically for risk/severity _score
  calibration_ (nothing like "lingering at windows with no purpose -> 40" as a published visual exemplar condition). Closest
  evidence: text-judge anchoring (Q2) and class/definition-conditional prompting in surveillance VLMs (Q2 headline + Q5).
  — _inference from absence across arXiv + OpenAlex searches (title/abstract level)_.
- Text-side classics (apply only if you do add exemplars — order must be chosen, not incidental): few-shot prompt-order
  sensitivity causes very large accuracy swings and is partly fixable by permutation-calibration; demonstration order permutes
  accuracy in the few-shot regime. — _Fantastically Ordered Prompts_, https://arxiv.org/abs/2104.08786;
  _Calibrate Before Use_, https://arxiv.org/abs/2102.09690 — papers with ablations. _[LLM-text-only]_
- **Multimodal analogue of order sensitivity:** reordering multimodal context swings MLLM accuracy "between advanced performance
  and random guessing"; attention concentrates at the **beginning and end** of the multimodal sequence; deliberately placing key
  content in those slots gave **+14.7%** (video-caption matching) and **+17.8%** (VQA) with no extra compute; they propose
  Position-Invariant Accuracy (PIA). Evaluated model list is not in the abstract (small models unconfirmed).
  — _Order Matters: Exploring Order Sensitivity in Multimodal Large Language Models_, https://arxiv.org/abs/2410.16983 — paper.
- **Exemplar-count economics at a 16K slot:** distilling many-shot exemplars into a compact rule artifact retains most gains in
  text settings — supports "compact band sheet, not 8 full exemplar transcripts."
  — _Distilling Many-Shot In-Context Learning into a Cheat Sheet_, https://arxiv.org/abs/2509.20820 — **ID/title verified, body
  not read**. _[LLM-text-only]_

**Q1 net:** few full image+JSON exemplars are a weak/uncertain lever for an 8B open VLM (possibly negative given the format tax);
a compact textual band/rubric sheet is cheaper and better evidenced; exemplar _scores_ will anchor the distribution (that is the
mechanism, and it is the thing to validate on synthbench).

---

## Q2. Verbalized / calibrated risk scoring; band anchoring; fighting low-polarization

- **VLM verbalized confidence is severely miscalibrated, worst in small models, and the bias direction is overconfidence**
  (high scores regardless of actual visual competence). Extracted numbers: Qwen2.5-VL-7B ECE = 0.496 (MMMU-Pro), 0.660
  (MathVision); 72B = 0.392 / 0.580; models "systematically overconfident across a wide range of confidence bins"; small/A3B
  models worst. Their fix, **VCAP (Visual Confidence-Aware Prompting)**, is a **two-stage describe-then-judge** structure:
  stage 1 asks the model to describe the visual input in detail and give a confidence score (perception isolated); stage 2 asks
  the final answer + confidence "taking into account your confidence score of the description." Measured: overall ECE
  0.467 -> 0.424 (7B) and 0.431 -> 0.365 (72B); VCAP beat Top-K and self-reflection. Read carefully for your case: the published
  VLM-calibration win is **description-before-judgment**, not rubric wording; and it is a two-turn structure, which your
  single-call contract cannot do verbatim (only a description _field_ before the score approximates it).
  — _Seeing is Believing, but How Much? A Comprehensive Analysis of Verbalized Calibration in Vision-Language Models_,
  https://arxiv.org/abs/2505.20236 (also ACL/EMNLP version: https://doi.org/10.18653/v1/2025.emnlp-main.74)
  — paper with ablations, multimodal, includes 7B-class models.
- **Best single source for your exact failure mode:** _Are Multimodal LLMs Ready for Surveillance? A Reality Check on Zero-Shot
  Anomaly Detection in the Wild_, https://arxiv.org/abs/2603.04727. SOTA MLLMs on ShanghaiTech + CHAD, VAD reformulated as
  binary classification, with **prompt-specificity and temporal-window (1-3 s) ablations**: "we find a pronounced **conservative
  bias** in zero-shot settings; while models exhibit **high confidence, they disproportionately favor the 'normal' class,
  resulting in high precision but a recall collapse that limits practical utility"; "**class-specific instructions can
  significantly shift this decision boundary, improving the peak F1-score on ShanghaiTech from 0.09 to 0.64**, yet recall remains
  a critical bottleneck"; the authors call for "**recall-oriented prompting and model calibration**". This is your bug
  ("nothing visibly harmful right now" -> normal / low score) reproduced and measured on VLMs, with the fix direction confirmed.
  — paper with ablations, multimodal.
- **Anchoring in LLM judges is large, threshold-like, and not fixable by CoT or warnings.** _Anchoring Bias in LLM-as-a-Judge
  Systems: Prior Scores Compromise Evaluation Independence_, https://arxiv.org/abs/2608.25869: 185,271 evaluations of 20 fixed
  texts; 7 of 8 models showed a significant anchored-metadata effect; Cohen's d up to 0.71; token-level probes showed
  "**introducing anchored metadata produces a marked redistribution of output-score probabilities, while changing the anchor
  value within the tested below-threshold range produces comparatively little additional variation**"; anchored metadata blocked
  48% of error corrections and flipped 10.18% of correct judgments; **CoT prompting and a metadata-disregard warning did not
  reduce the total anchoring effect** (the warning did improve paired accuracy in the industry experiment). Design consequence:
  naming bands + worked scores WILL shift your distribution (that is the intended mechanism), the shift is coarse rather than
  fine-tuned, and you cannot prompt the model into "ignoring" the anchors.
  — paper, 185K-eval bootstrap CIs. _[LLM-judge-text-only; multimodal analogue unverified]_
- **Raw verbalized numbers are model-shaped, not truth-shaped; post-hoc recalibration beats prompt-only elicitation.**
  _Can LLMs Express Their Uncertainty?_, https://arxiv.org/abs/2306.13063: verbalized scores systematically overconfident;
  calibration improves with capability; white-box only narrowly beats black-box (AUROC 0.522 -> 0.605); **no method consistently
  outperforms the others**; all struggle on specialist-knowledge tasks. _Just Ask for Calibration_,
  https://arxiv.org/abs/2305.14975: RLHF models need calibration tuning on their own generations (Brier/ECE) — prompting alone
  leaves them miscalibrated. _On Verbalized Confidence Scores for LLMs_, https://arxiv.org/abs/2412.14737, and _Calibrating
  Verbalized Probabilities_, https://arxiv.org/abs/2410.06707, push the same conclusion (fit a mapping on the emitted scale).
  _[LLM-text-only; the last two are ID/title verified, bodies not read]_
- **Absolute numeric scores from open evaluators diverge from human scores even with custom rubrics; the field's answer is a
  probability-weighted readout rather than the greedy digit.** Prometheus 2 notes existing open evaluator LMs "issue scores that
  significantly diverge from those assigned by humans" — https://arxiv.org/abs/2405.15801; G-Eval computes its score as a
  **token-probability-weighted expected value over the candidate score tokens** precisely because greedy discrete scores cluster —
  https://arxiv.org/abs/2303.16634. — papers. _[LLM-text-only, but directly actionable with llama.cpp logprobs]_
- **Central-tendency bias in multimodal ordinal scoring** is documented (clinical ordinal scoring audit) — adjacent, opposite
  polarity to your failure (yours is low-polarization, not mid-latching); pointer only.
  — _Auditing Multimodal LLM Raters: Central Tendency Bias in Clinical Ordinal Scoring_, https://arxiv.org/abs/2605.16386 —
  **ID/title verified, body not read**.
- **Band-endpoint naming specifically ("0-29 routine, 30-59 medium, ..."): no direct study found.** What supports it: (a) the
  threshold-like anchoring result above (presence of anchor values redistributes the score mass; exact endpoints matter less);
  (b) the surveillance result that class-specific instructions move the operating point by 7x F1. Treat "naming bands shifts the
  mean; naming endpoint numbers moves the tails" as **inference**, not a sourced finding.

---

## Q3. Multi-image prompting for small VLMs (2-4 stills, one chat request)

- **Hallucination rises with the number of attached images, and content position inside the image sequence matters.**
  MIHBench (first systematic multi-image hallucination benchmark): "a **progressive relationship between the number of image
  inputs and the likelihood of hallucination occurrences**"; single-image hallucination tendency predicts multi-image behaviour;
  "the influence of same-object image ratios and the **positional placement of negative samples within image sequences**"; their
  mitigation (Dynamic Attention Balancing) is inference/weights-side, not prompt-side. So 4 stills really are riskier than 2, and
  frame ordering is a live variable. — https://arxiv.org/abs/2508.00726 — paper with ablations, multimodal.
- **Multi-image ability is a known MLLM weak spot generally**, incl. open models, cross-image reasoning and fine-grained
  perception specifically — MIBench, https://arxiv.org/abs/2407.15272 — paper, multimodal.
- **Primacy/recency: the middle frames are underweighted; order to exploit it.** Reordering multimodal context swings accuracy
  "between advanced performance and random guessing"; MLLMs "pay special attention to certain multimodal context positions,
  particularly **the beginning and end**"; deliberate placement gave +14.7% / +17.8% with no extra compute.
  — https://arxiv.org/abs/2410.16983 — paper. Practical: put the most diagnostic still **last** (recency slot, adjacent to the
  text), or first; never let a middle frame carry the case.
- **Production-verified mitigation that NVIDIA ships: per-frame temporal grounding injected into the prompt by default.**
  RT-VLM config: `RTVI_ADD_TIMESTAMP_TO_VLM_PROMPT` (default `true`) plus `RTVI_TIMESTAMP_PROMPT_PREFIX/SUFFIX_{FILE,RTSP}_SOURCE`
  templates with `{timestamps}`, `{query}`, `{first_ts}`, `{last_ts}`; the shipped default instruction is literally
  "IMPORTANT: Frame 1 corresponds to timestamp {first_ts} seconds, and the last frame corresponds to timestamp {last_ts}
  seconds. All timestamps in your response MUST be between ... Do NOT use timestamps starting from 0 ..." (source:
  `services/rtvi/rt-vlm/src/models/vllm_compatible/vllm_compatible_model.py`, `_DEFAULT_EVS_TIMESTAMP_INSTRUCTION`, in
  https://github.com/NVIDIA-AI-Blueprints/video-search-and-summarization). Cosmos-Reason's model card goes further: the model
  **recognizes timestamps burned into the bottom of each frame** ("Our AI model recognizes timestamps added at the bottom of each
  frame for accurate temporal localization"), recommends `fps=4` to match training. Frame labels + time deltas are the
  vendor-validated pattern for exactly this pipeline shape — this is docs/model-card evidence (deployment-grade), not an ablation.
  — https://docs.nvidia.com/vss/latest/real-time-vlm.html , https://huggingface.co/nvidia/Cosmos-Reason1-7B
- **Forcing long CoT on 7B-class video VLMs does not help and can hurt.** Paired direct / CoT / answer-first evaluation on
  Video-MME subsets with Qwen2.5-VL: the chains are genuinely video-conditioned (swapping the video collapses chain overlap and
  flips most final letters), "yet on the same data, **forced CoT does not improve MCQ accuracy, and on the smaller 7B model it
  produces a small but statistically supported drop**." — https://arxiv.org/abs/2606.22862 — paper with ablations + scorer
  discipline, multimodal, 7B. Also relevant to Q4.
- **Documented failure envelope of a same-size-class video reasoner (Cosmos-Reason1-7B model card):** "may not follow the video
  or text input accurately in challenging cases ... fast camera movements, overlapping human-object interactions, **low lighting
  with high motion blur**, and multiple people performing different actions simultaneously"; also "Recommend using 4096 or more
  output max tokens to avoid truncation of long chain-of-thought response" (your 2,048 reply cap would truncate a Cosmos-style CoT).
  — https://huggingface.co/nvidia/Cosmos-Reason1-7B — model card (docs).
- **Your own model card's recommended sampling is not greedy:** Qwen3-VL-8B-Instruct lists temperature 0.7 / top_p 0.8 /
  top_k 20 / presence_penalty 1.5 for the VL setting. The card documents **no** multi-image guidance, no interleaving
  recommendation, no per-image token cap, and no image-count limit (those live in the technical report/processor docs), and no
  documented weaknesses. — https://huggingface.co/Qwen/Qwen3-VL-8B-Instruct — docs. Flag: temp-0 argmax is off the vendor's
  recommended operating point; the card does not say whether that matters for constrained structured output.
- MM1.5 (training-side, 1B-30B incl. small models) is the closest evidence that multi-image competence is a _data mixture_
  property you cannot prompt in — it deliberately optimized the visual instruction-tuning mixture for "multi-image reasoning".
  — https://arxiv.org/abs/2409.20566 — paper with ablations, multimodal.

---

## Q4. Committing a scalar before justification; grammar-constrained decoding

- **The field order you shipped is a documented pathology.** _Let Me Speak Freely? A Study on the Impact of Format Restrictions
  on Performance of Large Language Models_, https://arxiv.org/abs/2408.02442: under constrained JSON, "**100% of GPT-3.5 Turbo
  JSON-mode responses placed the 'answer' key before the 'reason' key**" (models self-sabotage CoT under JSON mode); GSM8K:
  LLaMA-3-8B 75.13 (free text) -> 48.90 (JSON+schema) -> 65.38 (JSON-mode constrained decoding); Claude-3-Haiku 86.51 -> 23.44;
  GPT-3.5 75.99 -> 49.25; Last-Letter 70.1 -> 28.0 (LLaMA-3-8B); "stricter format constraints generally lead to greater
  performance degradation"; the mitigation that worked is **decouple**: free-form first, then a second pass to reformat
  ("NL-to-Format", nearly identical to unrestricted NL). No escape-token experiment; no controlled size-scaling study (they only
  had LLaMA-3-8B and Gemma-2-9B open-weight, and note GPT-4o-mini degrades far less).
  — paper with ablations. _[LLM-text-only, but the answer-before-reason-key finding is exactly your situation and the 8B row is
  your model class]_
- **The tax is mostly in the prompt, not the sampler.** _The Format Tax_, https://arxiv.org/abs/2604.03616: "structured output
  requirements — JSON, XML, LaTeX, Markdown — substantially degrade reasoning and writing performance across open-weight models
  ... constrained decoding ... sampling bias accounts for only a fraction of the degradation. **The dominant cost enters at the
  prompt: format-requesting instructions alone cause most of the accuracy loss, before any decoder constraint is applied**";
  decoupling reasoning from formatting recovers most of the accuracy; "most recent closed-weight models show little to no format
  tax, suggesting the problem is not inherent ... but a gap that current open-weight models have yet to close."
  Consequence for you: the grammar is not the main suspect — the instruction block is — so piling JSON-exemplar surface into the
  prompt is on the wrong side of this finding. — paper (open-weight focused). _[LLM-text-only]_
- **Hard-constraint decoding distorts small-model semantics.** _The Hidden Cost of Structured Generation in LLMs:
  Draft-Conditioned Constrained Decoding_, https://arxiv.org/abs/2603.03305: masking + renormalization "can distort generation
  when the model assigns low probability mass to valid continuations, pushing decoding toward locally valid yet semantically
  incorrect trajectories"; unconstrained-draft-then-constrain improves strict structured accuracy by up to **+24 pp
  (15.2% -> 39.0% on GSM8K with a 1B model)**. — paper + KL-projection analysis. _[LLM-text-only]_
- **Order-of-generation evidence in VLMs specifically (rationale-first needs scale; answer-first is more format-robust).**
  _Evaluating Explanation-Driven Vision-Language Reasoning via Generation Order Interventions_,
  https://arxiv.org/abs/2609.29496: controlled single-step generation (no CoT) across knowledge-intensive QA, visual entailment,
  compositional grounding; "**larger models emerge as a prerequisite for reliably supporting rationale-first reasoning at
  scale**", however "**answer-first generation is less prone to format-related errors in structured output**"; accuracy and
  faithfulness are jointly set by "explanation ordering, model scale and pre-training knowledge, task-specific fine-tuning, and
  task structure". This is the most on-point source for the trade you are making: a short description-before-score field helps
  causality but costs format reliability on an 8B model. — paper with controlled interventions, multimodal.
- **Text-side CoT-order/faithfulness background (why "reasoning after the committed number" is decoration).**
  _Language Models Don't Always Say What They Think: Unfaithful Explanations in Chain-of-Thought Prompting_,
  https://arxiv.org/abs/2305.04388 — paper with designed biases; the stated rationale does not reflect the actual computation.
  _Chains That See, Answers That Don't_ (above, Q3) adds the VLM result that forced CoT does not buy accuracy at 7B.
  _[2305.04388 is LLM-text-only]_
- **Community-verified workaround in your exact stack (llama.cpp), and it is a server-side fix, not a prompt fix.**
  Issue ggml-org/llama.cpp#12276 "Feature Request: grammar / json schema with reasoning format. Allow model free to think but
  strict to answer" (closed): "**The model should be free to reason, but strict with an answer format** ... If the model is free
  to reason for a while instead of putting the answer right in the json, **the performance might be better**", with option B —
  "let the model generate until it hits [END-OF-THINKING-TAG], then apply grammar. (This is the current work around method I'm
  using)". (Token bytes intentionally elided here.) Merged PR ggml-org/llama.cpp#20970 "common : inhibit lazy grammar sampler
  while reasoning is active" implements the same principle: "Inhibit lazy grammar sampler while reasoning is active to avoid
  grammar constraining when a tool call tag ... is present in the reasoning output ... tokens are not passed to the grammar"
  while the reasoning sampler is active. llama-server README confirms the knobs: `-j/--json-schema` ("JSON schema to constrain
  generations"), `--grammar` (BNF), `--reasoning-format` (`none|deepseek|deepseek-legacy`), `--reasoning-budget N`
  (-1 unrestricted, 0 immediate end), and per-request `reasoning_format` / `reasoning_control` / `reasoning_effort` on
  `/v1/chat/completions`.
  — https://github.com/ggml-org/llama.cpp/issues/12276 , https://github.com/ggml-org/llama.cpp/pull/20970 ,
  https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md — GitHub issue/PR + docs (deployment-grade, no
  accuracy ablation). Caveat: Qwen3-VL **Instruct** has no thinking channel, so for your model this principle has to be
  implemented in the _schema_ (an early free-text-ish field before the score), not via reasoning tags — which is exactly what
  the generation-order paper says is scale-limited and format-risky.
- **Score-readout alternative that the grammar does not fight:** instead of trusting the greedy digit at `risk_score`, read an
  **expected value over the enumerated digit tokens** from the constrained step's logprobs (G-Eval-style token-weighted scoring,
  https://arxiv.org/abs/2303.16634), or average that across 2-3 non-greedy samples if the contract tolerates it (your setup is
  temperature 0 with no seed, i.e. a single argmax of a _renormalized, grammar-masked_ distribution — the DCCD/Format-Tax
  results say that argmax is a distorted estimator). llama-server exposes logprobs on the OpenAI-compatible endpoints.
  — _inference from the G-Eval + constrained-decoding sources_; llama.cpp logprobs availability: docs, only partially verified.

---

## Q5. Transferable material from NVIDIA VSS and similar security-camera deployments

Primary sources: the NVIDIA VSS blueprint repo (Apache-2.0) — https://github.com/NVIDIA-AI-Blueprints/video-search-and-summarization
— and https://docs.nvidia.com/vss/latest/ (VSS ships Cosmos Reason 1/2 **and Qwen3-VL** as its RT-VLM models, per the docs).

- **Architecture: NVIDIA does not let the VLM own the severity number.** VSS's Alerts microservice "uses Vision Language Models
  to verify alert authenticity" and persists verdicts labelled **confirmed / rejected / unverified** plus reasoning traces;
  severity/escalation comes from Behavior Analytics — deterministic spatial rules (tripwire crossings, ROI entry/exit,
  proximity, restricted zones, confined areas, stop duration). Read as a design verdict on your pipeline: an 8B VLM supplies
  _verification + evidence_; the 0-100 comes from detector/track facts (loiter duration, zone, time-of-day, repeat visits).
  — https://docs.nvidia.com/vss/latest/alert-verification-service.html , https://docs.nvidia.com/vss/latest/behavior-analytics.html — docs.
- **Every shipped event-verification prompt puts reasoning BEFORE the answer.** `services/alert/alert_type_config.json` and the
  per-industry `deploy/docker/industry-profiles/*/vlm-as-verifier/configs/alert_type_config.json` files all use the pattern:
  "Answer the question using the following format: [think-tag] Your reasoning. [/think-tag] Write your final answer immediately
  after the [/think-tag] tag" (collision / stop anomaly / movement anomaly / tailgating). I.e. the vendor's production ordering
  is rationale-then-verdict — the opposite of your shipped `risk_score`-before-justification order.
  Counter-example in the same product: RT-VLM anomaly captioning prompts ask for **"Anomaly Detected: Yes/No / Reason: [Brief
  explanation]"** (verdict first, reason after), with system prompt "Answer the user's question correctly in yes or no", and the
  docs advise "Use a prompt that expects a structured Yes/No response for anomaly detection". So NVIDIA ships both orders;
  the _binary_ verifier tolerates verdict-first, the _definitional_ prompts insist on reasoning-first.
  — https://docs.nvidia.com/vss/latest/real-time-vlm.html — docs + shipped configs.
- **The most directly transferable artifact in the whole corpus: the warehouse "proximity violation" verifier prompt**
  (`deploy/docker/industry-profiles/warehouse-operations/vlm-as-verifier/configs/alert_type_config.json`, ~1,900 words system +
  user). It is a production answer to precisely your failure (calm precursor behaviour dismissed as routine). Mechanics worth
  copying, in priority order:
  1. **Operational definition table instead of a one-line rubric** — a "STRICT CLASSIFICATION TABLE (ID | Label | Definition |
     Hazard Status)" where each row's Definition is observable geometry, plus a "Hazard Status: TRUE (Unsafe) / FALSE (Safe)" column.
  2. **A counterfactual test that removes the "nothing harmful right now" heuristic** — the "freeze test": "If the pedestrian had
     FROZEN in place and NOT moved at all, would the forklift have driven into them or passed within ~1 meter of their body?
     YES -> ... potential near miss. NO -> ... This is routine, even if the pedestrian chose to move."
  3. **An explicit anti-calmness clause** — "IMPORTANT — NEAR MISSES CAN LOOK CALM: Do not require panic, running, or dramatic
     swerving to classify as a near miss. ... Workers are trained to yield — their calm reaction does not reduce the danger. The
     danger is in the geometry of the situation ..., not in the pedestrian's emotional response." (Direct analogue for loitering
     at windows / trying car doors: the risk is exposure/opportunity, not observed harm.)
  4. **Named scenario enumeration** ("COMMON NEAR-MISS SCENARIOS ... often wrongly dismissed": head-on, from behind, crossing,
     turning into, close pass) and a symmetric "WHAT IS NOT a near miss (routine encounters)" list — a two-sided band definition.
  5. **A mandatory self-audit before emitting, aimed at the low-score bias specifically** — "Q3: Am I dismissing a genuine near
     miss just because the pedestrian reacted calmly, because it happened in a shared aisle, or because I described it using
     words like 'routine'? Near misses DO happen in shared aisles, and calm reactions do not make them safe."
  6. **Description/label consistency rules with a stated tie-break** — "If there is ANY contradiction ... FIX THE CLASSIFICATION
     to match what you actually observed. Do not fabricate danger to justify Near Miss, and do not dismiss real path
     intersections as 'routine'."
  7. **Schema fields that force agreement** — `prediction_class_id`, `prediction_label`, `prediction_answer`, plus
     `video_description` whose required content is enumerated (identification, path, freeze test, forced-vs-voluntary) — with
     "These three fields must ALWAYS agree. Double-check before outputting." Note their output order is
     class_id/label/answer then description — verdict-first like yours — so they buy causal ordering by making the _description
     requirements_ part of the instructions and the _self-audit_ explicit, not by reordering fields. That is a viable pattern for
     you if the field order is truly frozen.
     Confidence: shipped production config (docs/artifact), **no published ablation** — it is evidence of what a vendor converged
     on for this failure mode, not of measured effect size. Their budget is ~1,900 words; yours is ~hundreds of tokens, so port the
     _mechanisms_ (2)+(3)+(5)+(6) compressed, not the length.
- **Also shipped: a "conservative-verification" style prompt with 6 gating preconditions** (smart-city `Stop Anomaly` /
  `Movement Anomaly` configs) that name both classes with definitions before asking a Yes/No, and a "tailgating" prompt with
  "**Category Definitions**" for Normal Access vs Tailgating. Pattern: define the positive class AND the negative class, then ask.
  — same repo paths.
- **Temporal grounding in prompts (repeat of Q3, VSS-specific):** default timestamp instruction + configurable
  `RTVI_TIMESTAMP_PROMPT_{PREFIX,SUFFIX}_{FILE,RTSP}_SOURCE` templates exposing `{timestamps}`, `{first_ts}`, `{last_ts}`;
  `VLM_SYSTEM_PROMPT`, `VLM_PROMPT_MAX_LENGTH` / `VLM_SYSTEM_PROMPT_MAX_LENGTH` defaults of 10,240 chars (their VLM prompts are
  length-capped, so vendor guidance is "a few hundred to a few thousand characters", i.e. in the same order as your budget);
  for Cosmos Reason, timestamps are burned into frames and the default system prompt requests `<start> <end> caption` event lists
  at fps=4. — docs + `services/rtvi/rt-vlm/src/models/vllm_compatible/vllm_compatible_model.py`.
- **Adjacent deployment literature:** _Large Language Models for Video Surveillance Applications_ (https://arxiv.org/abs/2501.02850,
  application/survey level) and the CHAD/ShanghaiTech benchmark above. No published _risk-score_ prompt for security cameras was
  found anywhere — VSS itself keeps the VLM binary/ternary-verdict and derives severity from analytics (first bullet).
  — survey/docs; and absence-of-evidence from title/abstract searches.

---

## If we change only 3 things

1. **Replace the one-sentence rubric with a compressed precursor-criterion band sheet, written two-sided, with an explicit
   anti-calmness clause.** Evidence: the VLM surveillance benchmark's measured conservative bias with recall collapse and its
   demonstrated fix ("class-specific instructions ... F1 on ShanghaiTech from 0.09 to 0.64", https://arxiv.org/abs/2603.04727);
   NVIDIA's production near-miss prompt (freeze test / "near misses can look calm" / two-sided scenario lists,
   https://github.com/NVIDIA-AI-Blueprints/video-search-and-summarization). Concretely for ~200-300 tokens: define bands by
   _observable behaviour + exposure_ rather than by harm ("precursor behaviour at a dwelling/car: attempting entry, peering in,
   repeated approach without a service purpose -> mid band"), add one "routine" list (delivery at a door, resident with keys,
   worker in a lit work zone), and one line stating that absence of visible harm does not imply a low score — score the
   counterfactual exposure. Expect the named numbers to anchor the distribution (https://arxiv.org/abs/2608.25869); that is the
   mechanism, so measure the shift on synthbench rather than assuming it.
2. **Stop trusting the greedy digit: make the scalar an expected value (or a deterministic function), not one argmax.**
   Cheapest: request logprobs and compute EV over the constrained `risk_score` digit tokens at that step (G-Eval's token-weighted
   scoring, https://arxiv.org/abs/2303.16634), then fit a monotone post-hoc recalibration on synthbench (the text-calibration
   literature's consistent conclusion: https://arxiv.org/abs/2305.14975, https://arxiv.org/abs/2412.14737). Structurally stronger
   (and what NVIDIA actually ships): derive most of the 0-100 from detector/track facts (dwell time in a private zone, door/window
   proximity, repeat visits, night hours) and let the VLM's verdict/rubric adjust it — https://docs.nvidia.com/vss/latest/behavior-analytics.html.
   Rationale: a Q4_K_M 8B's absolute 0-100 under grammar-masked greedy decoding is a known-bad readout (Format Tax says the
   prompt cost dominates; DCCD says masked argmax drifts semantically, 15.2% -> 39.0% when a draft precedes the constraint;
   VCAP shows even 7B VLMs run ECE 0.5-0.7 on verbalized numbers).
3. **Fix the frame contract, and buy causal ordering where it is cheap.** (a) Label every still and give the deltas —
   "Frame 1/4, t=0s ... Frame 4/4, t=+7s, oldest first" — plus one explicit question about what changed between frames; NVIDIA
   ships exactly this by default (`RTVI_ADD_TIMESTAMP_TO_VLM_PROMPT`, "Frame 1 corresponds to timestamp ...") and Cosmos Reason is
   trained on in-frame timestamps. (b) Respect the primacy/recency finding: the middle stills are underweighted and hallucination
   grows with image count (https://arxiv.org/abs/2410.16983, https://arxiv.org/abs/2508.00726) — so prefer 2 well-chosen stills
   over 4, and put the most diagnostic one last. (c) For ordering, add a _short_ structured observation field before
   `risk_score` (enum/short-string, grammar-safe) rather than a long rationale: describe-then-judge is the published VLM
   calibration win (VCAP, ECE 0.467 -> 0.424 at 7B) and NVIDIA's verifier prompts all reason-before-answer, but the
   generation-order study warns "larger models emerge as a prerequisite for reliably supporting rationale-first reasoning" and
   "answer-first generation is less prone to format-related errors in structured output" (https://arxiv.org/abs/2609.29496), while
   forced CoT at 7B gave a small but statistically supported accuracy drop (https://arxiv.org/abs/2606.22862). If field order is
   frozen, port NVIDIA's substitute instead: enumerated description requirements + a one-line self-audit ("am I calling this low
   only because nothing harmful is visible right now?") + a description/label consistency rule — verdict-first is what their
   RT-VLM anomaly prompts ship, so it is not the blocked path.
