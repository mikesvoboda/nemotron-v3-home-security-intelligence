> ESCAPING KEY: <LL-IM-START>/<LL-IM-END> = ChatML im_start/im_end; <LL-VISION-START>/<LL-IMG>/<LL-IMG-END> = vision_start/img/img_end; G-START-OF-TURN/G-END-OF-TURN/G-START-OF-IMAGE/G-END-OF-IMAGE/G-IMG = Gemma3 markers; G-TURN-OPEN/G-TURN-CLOSE/G-THINK/G-CHANNEL/CHANNEL-CLOSE = Gemma4 markers. Restore the pipe delimiters before use.
# PART 2 (continues after C1-C5). ALL special tokens escaped: <LL-IM-START> = im_start,
# <LL-IM-END> = im_end, <LL-VISION-START> = vision_start, etc. Gemma tokens escaped likewise.

## Q1 (cont.) — Qwen-VL family

- Template = ChatML: `<LL-IM-START>{role}\n{content}<LL-IM-END>\n`. No BOS is added
  (add_bos_token=false, bos_token=null in the shipped Qwen3-VL tokenizer_config). Generation
  prompt = `<LL-IM-START>assistant\n` (Instruct). Confidence: shipped artifact (byte-read).
- Qwen official docs: "It is crucial to use the designated one to ensure the precise control
  over the LLM's generation process"; "Starting with Qwen3, no default system messages are
  used." Fine-tuning footnote: "bos token should not be set to <\|im_start\|> or you may see
  double bot tokens." Source: qwen.readthedocs.io/en/latest/getting_started/concepts.html
  Confidence: official docs.
- Multi-image layout: images render in-place at their content position as
  `<LL-VISION-START><LL-IMG><LL-VISION-END><LL-IMG-END>`; the ONLY built-in label is
  optional `Picture N: ` via add_vision_id (official recommendation for multi-image; see C3).
  Confidence: shipped artifact + official README.
- Qwen3-VL is video-timestamped, image-untimestamped (C2). Gemma3-equivalent: no markers either.
- Resolution knobs: Qwen3-VL patch=16, merge=2 => 32x spatial compression; token budget per
  image settable 256-1280 via `size.longest_edge/shortest_edge` (= old max_pixels/min_pixels):
  `{"longest_edge": 1280*32*32, "shortest_edge": 256*32*32}`; dims round to multiples of 32
  (28 in Qwen2.5-VL). README: "You can directly insert a local file path, a URL, or a
  base64-encoded image into the position where you want in the text" (interleaving sanctioned).
  Source: QwenLM/Qwen3-VL README + preprocessor_config.json. Confidence: official docs + shipped.
  llama.cpp equivalent: --image-min-tokens / --image-max-tokens (default read from model).
  A swap changes this from prompt-adjacent code to a server flag.
- Grounding: JSON is the NATIVE output idiom, with no special bbox tokens in the Qwen3-VL
  family (old <box>/<ref> from 2023 are gone). Official eval prompts (report App. B.5/B.6) are
  one-liners and do NOT state the 0-1000 scale or the key name: `Locate every object that
  matches the description "{ref_sentence}" in the image. Report bbox coordinates in JSON
  format.` / `Report bbox coordinates in JSON format.` / `Output the point coordinates in JSON
  format. For example: [{"point_2d": [x, y], "label": "point_1"}]`. Only the 3D task spells
  the schema. Cookbooks do add extra keys by example: `{"bbox_2d": [x1,y1,x2,y2], "label": ...,
  "type": ..., "color": ...}` with the line "You can set the output format to include additional
  key information like object attributes, descriptions, etc." => format-by-example is the
  official Qwen technique. Confidence: tech report (PDF pp.36-38) + official cookbook.
  KEY NAME IS VERSION-PINNED: bbox_2d/point_2d = Qwen2-VL through Qwen3-VL; do NOT assume it
  survives to Qwen4-VL (the 0-1000 scale has better survival odds).
- Structured output: Qwen3-VL post-training explicitly trains format adherence — "We use
  task-specific format prompts to guide model outputs to the required formats and therefore do
  not rely on explicit format rewards"; RL "General RL" stage targets "instruction-following";
  an isolated RL stage suppresses "language mixing, excessive repetition, and formatting errors".
  Qwen3 LLM report: "Format Following ... respond appropriately to the /think and /no_think
  flags". No llama.cpp/GBNF interplay is documented by Qwen anywhere. NOT FOUND.
  Confidence: tech report.
- Sampling: official eval settings for the 8B you serve are temp 1.0/top-p 1.0/top-k 40/
  presence_penalty 2.0; modelcard VL defaults temp 0.7/top-p 0.8/top-k 20/presence 1.5.
  Modelcard Best Practices: "adjust the presence_penalty parameter between 0 and 2 to reduce
  endless repetitions... using a higher value may occasionally result in language mixing and a
  slight decrease in model performance"; "Standardize Output Format ... Add the following JSON
  structure to the prompt to standardize responses: 'Please show your choice in the answer
  field with only the choice letter'". => Qwen officially endorses field-constraining prose
  (portable), and does NOT endorse temperature 0. Confidence: modelcard + tech report.
- IFEval (prompt-format-following proxy), Qwen3-VL report Tables 9/10, read with care
  (columns run model x sampling config): rows incl. 68.2 / 82.3 / 83.7 / 67.1 / 81.2 / 83.0 /
  83.4 and 75.1 / 82.6 / 83.2 / 72.5 / 81.9 / 85.0 / 87.4 => mid-80s at 8B-class.
  Confidence: tech report (column mapping inferred from the two table headers).
- Doc gap: Qwen publishes NO prompt-engineering guidance for VL. The only official artifacts
  are the template, the cookbooks, and the 42-page report's Appendix B (full eval prompts).
  Appendix B = a corpus of Qwen-sanctioned phrasings for the exact shapes you use
  (JSON grounding, options-letter, "Answer the question using a single word or phrase").
  NOT FOUND: Qwen guidance on instruction verbosity tolerance, few-shot exemplar sensitivity,
  score bands / rubric anchoring. Thin.

## Q2 — Gemma

- HEADLINE: Gemma 3 is now "Legacy". Gemma 4 shipped 2026-03-02 (E2B/E4B), 03-11 (26B-A4B,
  31B), 05-23 (12B Unified); new template generation, native `system` role, thinking toggle,
  native video, per-image token budget. A Gemma swap must be evaluated as Gemma 4 — the two
  generations do NOT share a template. Sources: ai.google.dev/gemma/docs/releases + HF model
  API (I verified google/gemma-4-31B-it created 2026-03-11, gemma-4-12B-it-qat-q4_0-gguf
  2026-06-05). Confidence: official docs + verified registry.
- Gemma 1/2/3 turns: `<G-START-OF-TURN>user\n...<G-END-OF-TURN>\n<G-START-OF-TURN>model\n`,
  BOS prepended explicitly, roles are user/model. NO system role: "Gemma's instruction-tuned
  models are designed to work with only two roles: user and model... provide system-level
  instructions directly within the initial user prompt." The shipped Gemma-3 GGUF template
  degrades gracefully (prepends a system message's content to the first user turn) but RAISES
  "Conversation roles must alternate user/assistant/..." on consecutive same-role messages, and
  |trim-s content. Sources: ai.google.dev/gemma/docs/core/prompt-structure; GGUF-embedded jinja;
  arXiv:2503.19786 §3. Confidence: official docs + shipped artifact.
- Gemma 4 turns: `<bos><G-TURN-OPEN>system\n[G-THINK]\n<G-TURN-CLOSE>\n<G-TURN-OPEN>user\n...`
  with image placeholder G-IMG, tools G-TOOL/G-TOOL-CALL, thought channel
  `<G-CHANNEL>thought\n...<CHANNEL-CLOSE>`. Template-forced prefix: on 12B/26B-A4B/31B with
  thinking OFF, add_generation_prompt injects an EMPTY thought channel
  `<G-CHANNEL>thought\n<CHANNEL-CLOSE>` (docs: added to suppress "ghost" thought channels).
  => a template-forced prefix before your first token now exists on BOTH families. Sources:
  official Google GGUF chat_template (18,683 bytes) + ai.google.dev/gemma/docs/capabilities/thinking
  + prompt-formatting-gemma4. Confidence: shipped artifact + official docs.
- Multi-image (Gemma 3): one G-START-OF-IMAGE per image in array order, expanded by the
  processor to `G-START-OF-IMAGE + 256 x G-IMAGE + G-END-OF-IMAGE` (image_seq_length=256).
  NO index/timestamp/position marker; no documented max images; official prompting = list N
  images then ask. Source: transformers/models/gemma3/processing_gemma3.py. Confidence: official source.
- Resolution/tiles, verdict on your quoted numbers:
  * 896x896 CONFIRMED ("the Gemma vision encoder takes as input square images resized to
    896 x 896"; model card "normalized to 896 x 896 resolution and encoded to 256 tokens each").
  * ~256 tokens CONFIRMED but per TILE (4x4 avg-pool on the 896 encoder).
  * "5 tiles" is WRONG as a default — correction: pan&scan is adaptive and OFF by default in
    transformers (do_pan_and_scan=False; min_crop_size 256, max_num_crops 4,
    min_ratio_to_activate 1.2), and crops are a 1xN or Nx1 strip following the aspect ratio,
    NEVER 2x2. For a 1920x1080 doorbell frame: ratio 1.78>=1.2 fires, num_crops_w=2,
    num_crops_h=1 => 2 crops + 1 thumbnail = 3 tiles = 768 image tokens. A square frame does
    NOT fire => one 896^2 tile, 256 tokens (a 1080p square is downscaled ~1.2x).
  * Resolution matters a lot for security stills (Table 7, 2B probe): DocVQA 31.9->59.8,
    InfoVQA 23.1->33.7, TextVQA 44.1->58.0 from 256->896. Report: fixed resolution causes
    "unreadable text, or small objects disappearing".
  Sources: arXiv:2503.19786; transformers/models/gemma3/image_processing_gemma3.py; model card.
  Confidence: tech report + official source + model card.
- Gemma 4 supersedes the tile story: variable aspect ratio, dims divisible by 48, no ImageNet
  norm, configurable visual token budget {70,140,280,560,1120} (default 280); docs tie budget
  to task: "Use lower budgets for classification, captioning, or video understanding... higher
  budgets for OCR, document parsing, or reading small text". Demo: same street scene finds 2
  objects at 70, 5 at 140, 6 at 280/560. Confidence: official docs + modelcard.
- JSON/structured output: the Gemma 3 tech report has ZERO mentions of "JSON" or "structured"
  output and no structured-output eval => the documented-weakness reputation is NOT in primary
  sources. Google's own vision docs instead EXPECT markdown fences: prompt
  "detect person and car, output only ```json" and parser re.search(r'```json\s+(.*?)\s+```').
  Under your grammar the fence is simply ungrammatical — a non-issue for you, but it tells you
  Gemma's native idiom is fenced-JSON-by-example, not raw-JSON.
  Grounding: "Bounding box coordinates are expressed as normalized values relative to 1000x1000
  grid", key box_2d, order [y1,x1,y2,x2] (PaliGemma y-first). => scale portable with Qwen3-VL;
  key name AND axis order are family-specific (swapping Qwen<->Gemma silently inverts x/y).
  Small-Gemma compliance, official (FunctionGemma, Gemma 3 270M): misses semantic nuance; the
  ranked official fix is "Enriched Tool Definition ... often the most effective fix" > prompt
  engineering ("relies on user behavior") > fine-tuning; and it mandates a natural-language
  capability trigger: "You are a model that can do function calling with the following
  functions ... this phrase acts as a prompt-based trigger".
  Modelcard limits: "Models are better at tasks that can be framed with clear prompts and
  instructions. Open-ended or highly complex tasks might be challenging"; "not knowledge bases";
  "might lack the ability to apply common sense reasoning". IFEval (0-shot) Gemma 3 4B-IT ~80
  vs high-80s/90 at 12B/27B. Confidence: tech report (verified absence) + official docs + modelcard.
- Prompt style (family-specific): Google's Gemma 3 VISION eval protocol is 4-SHOT exemplars for
  DocVQA/InfoVQA/TextVQA/RealWorldQA/AI2D/ChartQA/VQAv2/OK-VQA/TallyQA/SpatialSense, 3-shot MMMU,
  0-shot BLINK/CountBench, and Table 20 states "No Chain-Of-Thought prompting nor normalization"
  for vision. Text IT benchmarks are 0-shot WITH CoT (GSM8K/GPQA/BBH). => few-shot exemplars are
  the sanctioned Gemma vision protocol; CoT prompting is explicitly not used for Gemma vision.
  Official vision prompting guidance: be specific ("Instead of 'describe this image', try
  'describe the scene in this image, focusing on the relationship...'"), provide constraints,
  and "Iterative Refinement: Begin with a basic prompt and gradually add complexity" — which is
  unavailable in a one-call verifier, so front-load specificity. Also do not "Expect Exact
  Counts for Extremely Dense Objects". No official standalone "Gemma 3 prompting guide" exists
  (verified absence: the official cookbook repo has docs/capabilities/* only, 491 blobs).
  Gemma 4: "highly capable reasoners, with configurable thinking modes"; thinking is toggled by
  G-THINK in the system turn; "No Thinking Content in History" (strip thoughts from prior turns
  — "critical for maintaining performance"); "Gemma Think" as a separate model does NOT exist
  (no google/* thinking repo) — that older claim is obsolete. Multilingual 140+ languages, no
  documented language-drift defect; non-factor for an English prompt.
  Confidence: tech report + official docs (verified absences included).
- Modality order (Gemma 4 card, portable-looking but currently Gemma-documented): "Image
  content BEFORE the text in your prompt. Audio content AFTER the text."
- Video: Gemma 4 has native video AND injects `MM:SS` text timestamps before each frame block
  (`00:00 G-IMG G-VIDEO...`), i.e. it moved toward Qwen3-VL's text-timestamp design. Gemma 3 =
  image only, no official video. Gemma 3n card claims video but has no docs template.
  Source: ai.google.dev/gemma/docs/capabilities/vision/video. Confidence: official docs.

## Q3 — What is documented as family-specific technique (Qwen vs Gemma)

- System prompt: Qwen3+ = real system role, no default injected. Gemma 3/3n = NO system role,
  fold into first user turn. Gemma 4 = native system role again. => the single biggest swap cost.
  Confidence: official docs both sides.
- Thinking before answer: Qwen3-VL = two separate model variants (Instruct / Thinking;
  post-training "bifurcate[d] ... into non-thinking and thinking variants"); hybrid /think
  /no_think flags only on Qwen3 LLMs; llama.cpp --reasoning on|off|auto + --chat-template-kwargs
  for enable_thinking; Qwen official docs note llama.cpp does not expose the template hard
  switch: "the quick workaround is to pass a custom chat template equivalent to always enable_
  thinking=False via --chat-template-file". Gemma 3/3n = non-thinking, zero shot only;
  Gemma 4 = toggle + a template-forced empty thought channel on the large sizes.
  Confidence: tech reports + official docs both sides.
- Few-shot exemplars: Gemma's own vision numbers are 4-shot; Qwen's are 0-shot + one-line
  format instruction (Appendix B). Qwen's only few-shot guidance I found is a user question
  answered by continuation ("Just like the demonstration in our paper: Qwen-VL... 2-shot
  CoT") — NOT official guidance. => exemplar count is a per-family knob, documented on the
  Gemma side, undocumented-but-0-shot on the Qwen side.
- CoT prompting: Qwen officially prompts CoT ("Please reason step by step, and put your final
  answer within \boxed{}"; Appendix B uses "Think step by step before answering"). Gemma 3
  vision evals explicitly use NO CoT. Same sentence, opposite documented protocol.
- Score bands / rubric anchoring: NOT FOUND on both sides. Neither family documents numeric
  band definitions, calibration, or 0-100 rubrics. Thin — neither family gives you cover here.
- Instruction verbosity tolerance: NOT FOUND for both (only the modelcard-level "clear prompts
  and instructions" line). Thin.
- Format-example vs instruction: both families documented via example, but Qwen's official
  examples are terse one-liners and Gemma's are 4-shot + fenced. => JSON-schema-in-prose is
  portable; exemplar COUNT and fence habit are not.
- Coordinate conventions: scale 0-1000 shared (Qwen3-VL normalized [0,1000]; Gemma "normalized
  values relative to 1000x1000 grid"); key name (bbox_2d vs box_2d) and axis order
  (x1y1x2y2 vs y1x1y2x2) differ => a silent data-corruption trap on swap, prompt-fixable.
- Language: Qwen presence_penalty-higher => documented "language mixing" side effect; Gemma
  140+ languages, no documented drift. Irrelevant for an English-only verifier, but the Qwen
  note matters if you ever raise penalties (see Q5).

## Q4 — Portability evidence (all abstracts verified via arXiv API)

- Sclar et al., "Quantifying Language Models' Sensitivity to Spurious Features in Prompt
  Design / How I learned to start worrying about prompt formatting", ICLR 2024 —
  https://arxiv.org/abs/2310.11324. VERIFIED: "extremely sensitive to subtle changes in prompt
  formatting in few-shot settings, with performance differences of up to 76 accuracy points
  (LLaMA-2-13B). Sensitivity remains even when increasing model size, the number of few-shot
  examples, or performing instruction tuning"; and the one that settles the question: "format
  performance only weakly correlates between models, which puts into question the
  methodological validity of comparing models with an arbitrarily chosen, fixed prompt format."
  => FORMAT is not portable, and cross-model comparison on one fixed format is unsound.
  Confidence: peer-reviewed tech report (abstract quoted).
- Zhao et al., "Calibrate Before Use", ICML 2021 — https://arxiv.org/abs/2102.09690. VERIFIED:
  "the choice of prompt format, training examples, and even the order of the training examples
  can cause accuracy to vary from near chance to near state-of-the-art"; bias toward answers
  "placed near the end of the prompt or ... common in the pre-training data". => direct hit on
  few-shot exemplar ORDER and on label-position bias in a verdict field.
  Confidence: peer-reviewed (abstract quoted).
- Tam et al., "Let Me Speak Freely?" — https://arxiv.org/abs/2408.02442. VERIFIED: "a
  significant decline in LLMs reasoning abilities under format restrictions... stricter format
  constraints generally lead to greater performance degradation in reasoning tasks".
  => keep the grammar for syntax, keep semantics/justification free-form.
  Confidence: peer-reviewed (abstract quoted).
- Grammar-Aligned Decoding — https://arxiv.org/abs/2405.21047. VERIFIED: "GCD techniques ...
  can distort the LLM's distribution, leading to outputs that are grammatical but appear with
  likelihoods that are not proportional to the ones given by the LLM, and so ultimately are
  low-quality." => a GBNF-forced risk_score digit is NOT a calibrated score; the distribution
  over digits is warped by the grammar. Relevant to thresholding a 0-100 field.
  Confidence: tech report (abstract quoted).
- VLM-specific, small models: "Zero-Shot Vision-Language Models for Classroom Engagement
  Recognition: A Benchmark Study of Prompt Sensitivity..." — https://arxiv.org/abs/2606.21861.
  VERIFIED: subjects include LLaVA-1.5-7B and Qwen2.5VL-7B-Instruct (i.e. YOUR size class),
  three prompt designs (minimal / rubric-anchored / CoT), and "extreme prompt sensitivity, with
  accuracy swings of up to 32 percentage points on identical images depending solely on prompt
  phrasing", plus "severe class collapse, where models assign 85-100% of predictions to a single
  ... level regardless of visual content". Class collapse is exactly the failure mode of a
  risk-scoring verifier. Confidence: tech report (abstract quoted) — domain is classroom, not
  security, so transfer by analogy only.
- VLM grounding prompt instability: "Prompt Sensitivity in Vision-Language Grounding" —
  https://arxiv.org/abs/2604.17126 (DETR+CLIP pipeline, 263 COCO val2017 images): "overlapping
  prompts such as 'a person,' 'a human,' and 'a pedestrian' frequently select different
  instances, with mean instability of 2.11 distinct selections across six prompts... Prompt
  ensembling does not improve quality and often shifts selections." Note the pipeline is
  DETR+CLIP, NOT an autoregressive VLM — so cite only as "prompt wording instability is
  documented in VLM grounding", not as a Qwen/Gemma finding. Confidence: tech report (abstract
  quoted), limited applicability.
- NOT FOUND: a primary study of grammar-constrained-decoding effect on small-VLM answer quality;
  a Qwen-vs-Gemma structured-output head-to-head. I searched grammar-constrained decoding impact
  quality, prompt format sensitivity vision language, VLM prompt sensitivity — the two above are
  the closest. Thin but honestly thin.
- Tooling-level evidence that family-neutrality is NOT assumed: llama.cpp ships a per-model
  built-in template list (gemma, chatml, llama3, phi3, ...); mtmd has per-model files
  (I listed tools/mtmd/models: qwen2vl.cpp, qwen3vl.cpp, internvl.cpp, gemma4v.cpp..., and note
  NO gemma3*.cpp — Gemma 3 vision goes through siglip.cpp).
  https://github.com/ggml-org/llama.cpp/tree/master/tools/mtmd/models. Confidence: official repo.

## Q5 — Practical transfer notes under llama.cpp + GBNF

- Verbatim limitation list, JSON-Schema->GBNF ("JSON Schemas -> GBNF"): additionalProperties
  defaults false; unsupported features are SKIPPED SILENTLY (advised to run the Python converter
  for warnings and test with llama-gbnf-validator); can't mix properties with anyOf/oneOf
  (#7703); prefixItems broken; "minimum, exclusiveMinimum, maximum, exclusiveMaximum: only
  supported for type integer, not number"; nested $refs broken (#8073); pattern must be
  ^...$; remote $refs unsupported in C++; string formats lack uri/email; no patternProperties;
  plus unlikely-ever: uniqueItems, contains/minContains, $anchor, not, if/then/else.
  Source: https://github.com/ggml-org/llama.cpp/blob/master/grammars/README.md
  Confidence: official docs (I read these lines directly).
- risk_score 0-100 IS enforced while it stays "type":"integer" (compiled digit alternation
  shown in that doc for a 0-150 example) and silently unenforced as "number". Keep integer.
  Also: key ORDER comes from the required-array order; "required-first" key ordering is a
  llama.cpp artifact (docs/llguidance.md contrasts LLGuidance: additionalProperties default
  true, any whitespace allowed, unsupported schemas ERROR instead of silently ignoring).
  Confidence: official docs.
- Schema is invisible to the model (verbatim in C-adjacent note above): all score-band MEANING
  must be prose. This is the load-bearing portability fact: semantics portable, syntax free.
  Confidence: official docs.
- Temperature 0 is NOT deterministic here. Verified in source: sampler chain default order is
  penalties;dry;top_n_sigma;top_k;typ_p;top_p;min_p;xtc;temperature (common/common.h:264 and
  tools/server/README.md line 122), repeat_penalty DEFAULT 1.1 (server README line 541), and
  common/sampling.h: "check if the token fits the grammar - if not: resample... (slower path)";
  "if grammar_first is true, the grammar is applied before the samplers (slower) useful in cases
  where all the resulting candidates (not just the sampled one) must fit the grammar" (default
  false). => the penalty sampler can move the argmax BEFORE grammar filtering, so a digit can
  be influenced by repeat-penalty against digits already emitted. Mitigations: keep risk_score
  before long free text (you do), or set "repeat_penalty":1.0 / "samplers":["temperature"].
  Confidence: official docs + source (verified).
- cache_prompt default true with documented caveat: "the logits are not guaranteed to be
  bit-for-bit identical for different batch sizes... enabling this option can cause
  nondeterministic results." With 1-4 variable image counts your prefixes differ per request
  anyway; still, do not claim temp-0 reproducibility. Confidence: official docs.
- Grammar throughput is real: PR #18135 ("grammar : parallel rejects", closed unmerged) reports
  "~160 t/s on gpt-oss-20b. With grammar, I get ~20 t/s" (~80 with OpenMP rejection). No
  documented multi-slot/parallel correctness caveat in the current server README (verified
  absence). Backend sampling + grammar is explicitly incompatible (LOG_WRN + assert in
  common/sampling.cpp). GBNF perf note: "x? x? x?... may result in extremely slow sampling.
  Instead, write x{0,N}". Confidence: GitHub PR + source + official docs.
- Cross-family template gotchas (all closed issues, verified to exist with these titles):
  * #11866 "Problems with official jinja templates (Gemma 2, Llama 3.2, Qwen 2.5)" — official HF
    templates produced "error parsing grammar" in llama.cpp for BOTH families => TEMPLATE-level,
    reappears on any swap. Prefer model-metadata template + --jinja (default enabled now).
  * #16749 (merged) "convert: clean Gemma vision/audio chat template markers" — <start_of_image>
    -> <media> marker mismatch caused EMPTY CONTENT in vision tests => TEMPLATE-level:
    image-placeholder naming is the #1 cross-family vision gotcha.
  * #22396 "`--json-schema` fails with 'Failed to initialize samplers: std::exception' on
    Gemma 4 (E2B/E4B), works with [hand-written grammar]" — same failure reproduced on Qwen3-4B
    and Qwen3.5-2B with the identical schema => hits BOTH families. Ship a hand-written GBNF
    fallback (keep a parallel --grammar-file path in your deploy).
  * #23677 "Grammar sampler crash: 'Unexpected empty grammar stack' on Gemma 4 <unused> tokens"
    (family of #12433 Gemma3 <unused32> spam, where a non-Q4_K_M quant avoided it) =>
    MODEL-level, but the lesson ports: a grammar crashes rather than degrades when a family
    emits reserved tokens. Your Q4_K_M choice is family-specific, not neutral.
  * Multimodal is officially unstable: tools/mtmd/README.md "under very heavy development, and
    breaking changes are expected"; docs/multimodal/gemma3.md "very experimental". Vision needs
    two GGUFs (-m + --mmproj).
  * For Qwen3-VL swaps: no ggml-org pre-quant set (docs/multimodal.md lists Qwen2/2.5-VL,
    InternVL, Gemma); Qwen3-VL support arrived via merged mtmd/clip PRs (#25781 align_corners,
    #21103, #17594, #21443). --image-min/max-tokens govern dynamic resolution.
  * Other swap candidates' llama.cpp support (verified in tools/mtmd/models): internvl.cpp
    exists; Phi-Vision has NO dedicated mtmd file in the current list (only phi3/phi4 text
    templates in the built-in list) => treat Phi-VL as the weakest llama.cpp citizen of your
    three candidates. Confidence: official repo listing.
- Debugging hooks: /v1 with /tokenize (return_metadata gives per-token special=true/false —
  shows what your images expand to), /apply-template (returns the formatted prompt WITHOUT
  inference — this is how you diff prompt bytes across families), /props (returns chat_template
  + chat_template_caps). Confidence: official docs.

## Technique table (works-on-Qwen? / works-on-Gemma? / evidence)

| Technique | Qwen3-VL | Gemma 3 | Gemma 4 | Evidence |
|---|---|---|---|---|
| ChatML-style turn syntax | native | NO | NO (own G-TURN form) | shipped templates both sides |
| System role for policy text | yes (no default since Qwen3) | NO (fold into user turn) | yes | readthedocs concepts; prompt-structure; g4 card |
| Ask for raw JSON object, no fence | yes (native idiom) | works but native idiom is ```json-fenced | native | Qwen App.B.5; Gemma vision docs parser |
| JSON format-by-example in prompt | yes, official | yes (fenced) | yes | Qwen cookbook/App.B; Gemma vision docs |
| Name the output KEY + 0-1000 scale | Qwen native key bbox_2d, x1y1x2y2 | key box_2d, y1x1y2x2 | box_2d/y-first lineage | Qwen report §3.2.4; Gemma vision docs |
| Per-image label ("Frame 1: ") | official (add_vision_id) | no convention; array order only | interleaved freely | Qwen README/template; gemma3 processing.py |
| Interleave text between images | yes, documented | yes | yes, "freely mix" | Qwen README; Gemma4 card |
| Images before the text | neutral (any position) | neutral | documented preference | Gemma 4 card §4 |
| 0-shot + terse format instruction | official eval style | off-protocol for vision | unknown | Qwen App.B (0-shot); Gemma T (4-shot) |
| 4-shot in-prompt exemplars | undocumented for Qwen | official vision protocol | unknown | Gemma 3 report Tables 19-20 |
| CoT/"think step by step" prose | official technique | explicitly NOT used for vision | thinking toggle instead | Qwen modelcard/App.B; Gemma T20 |
| /no_think flag | Qwen3 LLMs only, NOT VL | n/a | G-THINK token in system turn | Qwen docs; g4 card |
| Terse concrete instruction | fine | documented preference | documented | Gemma vision docs; modelcards |
| Long multi-clause instruction | NOT FOUND either side | NOT FOUND | NOT FOUND | verified absence |
| Numeric score bands / rubric | NOT FOUND | NOT FOUND | NOT FOUND | verified absence — both families thin |
| "answer using a single word or phrase" | official eval phrasing | n/a (documented for Gemma single-word answers too) | — | Qwen App.B.4 |
| temperature 0 greedy | against official guidance | official temp 1.0/top_p 0.95/top_k 64 | same | Qwen modelcard; Gemma 4 card §1 |
| presence_penalty ~1.5-2.0 | official anti-repetition | n/a | n/a | Qwen best practices (+ language-mixing caveat) |
| Grammar enforces 0-100 integer | yes (llama.cpp) | yes, but #22396/#23677 hit Gemma | same open-lineage | grammars/README; issues |
| Prefill assistant "{" to force JSON | template-dependent (continue_final_message) | template raises on role alternation | — | HF chat_templating docs |

## 3-line summary

1. Semantics carry, format does not: llama.cpp states the schema is invisible to the model
   (official docs), so the score-band MEANING, the field glosses, and the "what to look for in a
   still" prose are your portable asset — while Sclar et al. (arXiv:2310.11324) documents up to
   76-point swings from meaning-preserving format changes and, decisively, that "format
   performance only weakly correlates between models."
2. So a family-neutral prompt is worth writing as the SEED, not the artifact: expect to
   re-tune exactly four documented knobs per family (system-role placement, exemplar count
   0-shot vs 4-shot, CoT-in-prose vs thinking-toggle, fence tolerance + box key/axis order), and
   budget a per-family acceptance test rather than a prompt-only swap — the swap cost is
   dominated by TEMPLATE + llama.cpp plumbing (add_vision_id kwarg vs --chat-template-file,
   --image-min/max-tokens vs a token budget, and open #22396/#23677 grammar crashes that hit
   both families), not by prompt wording.
3. Dispatch per-family researchers only for the family you will actually deploy — and note the
   ground moved: your Gemma option is now Gemma 4 (native system role, thinking toggle,
   per-image token budget, MM:SS frame timestamps), which reverses several "Gemma can't"
   assumptions; neither family documents anything about numeric score bands or rubric
   anchoring, so that part of your redesign has NO primary-source support on either side and
   must be settled by your own eval, with temp-0 determinism itself already broken by the
   default repeat_penalty=1.1-before-grammar sampler order.
