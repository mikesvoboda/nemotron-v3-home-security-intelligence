# Model sweep, 2026-10-03 and 04: twelve VLMs and three controls on the 450 `tierb-v0` stills

**Outcome.** Every one of the 15 arms ran to completion. Under the selection rule below (OD-26), **no arm advances: the shipped Qwen3-VL-8B Q4_K_M stays.** No arm comes near the S3 bar (the best reads 57.3% against 90%), and the arms that cut false alarms or raise S3 cannot be told apart from the shipped model once the scenario-level clustering of the 450 stills is respected. This sweep is a map of where the models sit, not a verdict that any of them should replace the shipped one.

This is the first committed record of the sweep. By the owner's decision of 2026-10-03 it was kept as off-repo scratch until it finished and a selection rule was set; both are now true (`sweep.log` ends `sweep finished` at 2026-10-04 01:38 EDT, which is 05:38 UTC). Every reading below is **recomputed from `items.csv` and `arms.csv` in this folder by `analysis.py`**, which asserts that each count it derives equals the sweep harness's own; the eval store those files were exported from (`eval.sqlite`) stays off-repo (D10).

**Claim scope (ISS-007).** The 450 stills are generated (FLUX.2) and their truth is declared, not verified; the owner's audit of 60 of them found the scene, people and conditions as declared (`p5a-2026-09-30.md`). The VLM was given **oracle detections** (each set's declared subjects at confidence 1.0, no box), not the shipped detector's output, and **no specialist context**. These numbers measure the client, the prompt and the model on stills; they do not measure the detector, the key-frame selector, the specialists or video. One run per arm.

## What was run

Every arm shares these conditions except where the next section says otherwise.

| Condition              | Value                                                                                                                                                                                                                                                                             |
| ---------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Corpus                 | The `tierb-v0` export: 450 stills, 209 benign (64 plain and 145 hard negatives) and 241 incidents (196 threat and 45 suspicious), in 31 scenarios                                                                                                                                 |
| Prompt, request        | The shipped assess prompt and constrained JSON schema through the repo's own `VlmClient`; one request per still; `max_tokens` 1024; read timeout 180 s for every arm (the shipped 25 s is not used, so a slow arm is not penalised); the grammar-enforcement probe on             |
| Sampling               | Greedy: `_ASSESS_TEMPERATURE = 0.0` at the replay commit (`9f4e65cd` is an ancestor of both replay commits, `ab3bd002` and `2cd619db`)                                                                                                                                            |
| Engine                 | llama.cpp `b11376-a55e952b8`, image `ai-vlm:sm103-b11376`, built from the repo's Dockerfile with `LLAMA_CPP_REF` overridden; the shipped default is `b7972`                                                                                                                       |
| Server settings        | 32,768 context over 2 slots (16,384 each); batch 2048, micro-batch 512; KV cache `q8_0`; flash attention on; all layers on the GPU; 1,280 vision tokens per still; prompt cache off (`LLAMA_ARG_CACHE_RAM=0`, `LLAMA_ARG_CACHE_IDLE_SLOTS=0`)                                     |
| Host                   | One GB300 through the `agent-gpu` runner (session cap 40,960 MiB). VRAM is the peak of `vram_actual_mib` sampled every 60 s, so a shorter spike can be missed. Per F13 the GB300 is not an S1 or S4 reading: VRAM and latency here are indicative only                            |
| Renderer-stopped check | Skipped on the owner's direction (OD-23, ISS-079), because the sandbox cannot read the renderer unit; every `run.json` records `renderer_check: SKIPPED`. The harness otherwise ran as shipped, through a request-rewrite shim for the extras below; the repo client is untouched |

**Where an arm differs from that.**

- **Thinking forced off** (the server flag `LLAMA_ARG_REASONING=off` plus `chat_template_kwargs {enable_thinking: false}` in each request) for the nine hybrid-thinking arms: Qwen3.5 4B and 9B, Qwen3.6-35B-A3B, Qwen3.8-27B (three quantizations) and the two Gemma 4 arms. The Qwen3-VL arms are instruct models and need no switch. These readings are non-thinking-mode readings.
- **The two Gemma 4 arms** use a micro-batch of 2048 and a **1,120** vision-token cap, not 1,280.
- **`control-defaultcache`** leaves the two prompt-cache settings unset (the llama.cpp defaults).
- The first control ran at replay commit `ab3bd002`, the rest at `2cd619db`; no code under `backend/`, `synthbench/` or `ai/` differs between the two (the commits between them are documentation).
- The driver `sweep.py` was edited once, between the fourth and fifth arms, to stop deleting weights after each arm; nothing else changed (both hashes are under Provenance).

### The weights

Every file was downloaded from its repository at its pinned size and checked against the repository's published sha256; the control's files are the shipped ones.

| Arm                                                         | Repository                                | Model file                           | Quant  | Bytes       | sha256 (model)                                                     | mmproj file                                 | mmproj precision | Bytes      | sha256 (mmproj)                                                    |
| ----------------------------------------------------------- | ----------------------------------------- | ------------------------------------ | ------ | ----------- | ------------------------------------------------------------------ | ------------------------------------------- | ---------------- | ---------- | ------------------------------------------------------------------ |
| `control-q4km` (also `control-rep`, `control-defaultcache`) | `Qwen/Qwen3-VL-8B-Instruct-GGUF`          | `Qwen3VL-8B-Instruct-Q4_K_M.gguf`    | Q4_K_M | 5027784800  | `67d1659bfe71b89d50b45a4ad1a9e5b997e5bb16ce5da66a6a6167abd569e9e2` | `mmproj-Qwen3VL-8B-Instruct-Q8_0.gguf`      | Q8_0             | 752289728  | `c6ba85508d82f42590e6eb77d5340369ab6fecf107a7561d809523d8aa5f3bfd` |
| `qwen3vl-8b-q8`                                             | `Qwen/Qwen3-VL-8B-Instruct-GGUF`          | `Qwen3VL-8B-Instruct-Q8_0.gguf`      | Q8_0   | 8709519456  | `0d264b3941185d00a74f75c4245521dae088ff1efc90ab8d1754e83f5844adb0` | `mmproj-Qwen3VL-8B-Instruct-Q8_0.gguf`      | Q8_0             | 752289728  | `c6ba85508d82f42590e6eb77d5340369ab6fecf107a7561d809523d8aa5f3bfd` |
| `qwen35-4b-q8`                                              | `unsloth/Qwen3.5-4B-GGUF`                 | `Qwen3.5-4B-Q8_0.gguf`               | Q8_0   | 4482403488  | `10cc391b403021dd11c614679d2fd92f611c3681d29e29651b717316965d61e1` | `mmproj-F16.gguf`                           | F16              | 672423616  | `cd88edcf8d031894960bb0c9c5b9b7e1fea6ebee02b9f7ce925a00d12891f864` |
| `qwen35-9b-q4km`                                            | `unsloth/Qwen3.5-9B-GGUF`                 | `Qwen3.5-9B-Q4_K_M.gguf`             | Q4_K_M | 5680522464  | `03b74727a860a56338e042c4420bb3f04b2fec5734175f4cb9fa853daf52b7e8` | `mmproj-F16.gguf`                           | F16              | 918166080  | `f70dc3509053962b0d0d3ee8a7eacebf5d60aa560cad78254ae8698516ae029f` |
| `qwen35-9b-q6k`                                             | `unsloth/Qwen3.5-9B-GGUF`                 | `Qwen3.5-9B-Q6_K.gguf`               | Q6_K   | 7458301152  | `91898433cf5ce0a8f45516a4cc3e9343b6e01d052d01f684309098c66a326c59` | `mmproj-F16.gguf`                           | F16              | 918166080  | `f70dc3509053962b0d0d3ee8a7eacebf5d60aa560cad78254ae8698516ae029f` |
| `gemma4-12b`                                                | `google/gemma-4-12B-it-qat-q4_0-gguf`     | `gemma-4-12b-it-qat-q4_0.gguf`       | Q4_0   | 6975879296  | `93567e57a8fe10b23569b9d9ec38cd005deedf71e29477c421a4b83f418a538b` | `mmproj-gemma-4-12b-it-qat-q4_0.gguf`       | Q4_0             | 175115616  | `cb018338a7538a9814d994bfe54644c71eb7ed54e31eae2f721e45fd3c260da7` |
| `qwen3vl-32b-q4km`                                          | `Qwen/Qwen3-VL-32B-Instruct-GGUF`         | `Qwen3VL-32B-Instruct-Q4_K_M.gguf`   | Q4_K_M | 19762150432 | `5cf0136e721d6294718ec71fd8c93b17ab5dd4e2714d6079e83fa46571ad94c8` | `mmproj-Qwen3VL-32B-Instruct-Q8_0.gguf`     | Q8_0             | 772360224  | `c01734a97adc350c1eebb957ed433afee4e376ebd0949163f659c76d8dcf20ca` |
| `gemma4-26b-a4b`                                            | `google/gemma-4-26B-A4B-it-qat-q4_0-gguf` | `gemma-4-26B_q4_0-it.gguf`           | Q4_0   | 14439363584 | `3eca3b8f6d7baf218a7dd6bba5fb59a56ee25fe2d567b6f5f589b4f697eca51d` | `gemma-4-26B-it-mmproj.gguf`                | ?                | 1194828160 | `a359953a076b877db30c31dbbb4c6d93b4a6e017ee5db5784247e4d4c0dd4f3b` |
| `qwen38-27b-q4km`                                           | `unsloth/Qwen3.8-27B-GGUF`                | `Qwen3.8-27B-UD-Q4_K_M.gguf`         | Q4_K_M | 16464440224 | `322e194ff79741c7baa497c240f677f54b201b0efab44ca8e50f122b39123482` | `mmproj-F16.gguf`                           | F16              | 927607488  | `cbb841a9ee0636b2ec172f5bb8df2ea8dfeb01e90fe7c6126581d662a0b4e43e` |
| `qwen38-27b-q6k`                                            | `unsloth/Qwen3.8-27B-GGUF`                | `Qwen3.8-27B-UD-Q6_K.gguf`           | Q6_K   | 21983677344 | `c9c206812fbe4ac7b76a729e25928b63f2ae89d37f69da7a71c20aec763cd436` | `mmproj-F16.gguf`                           | F16              | 927607488  | `cbb841a9ee0636b2ec172f5bb8df2ea8dfeb01e90fe7c6126581d662a0b4e43e` |
| `qwen3vl-30b-a3b-q8`                                        | `Qwen/Qwen3-VL-30B-A3B-Instruct-GGUF`     | `Qwen3VL-30B-A3B-Instruct-Q8_0.gguf` | Q8_0   | 32483932992 | `b9d01be012619d717c8a1e1cd5284c753ea66d56c24089461a58295fb17c1e64` | `mmproj-Qwen3VL-30B-A3B-Instruct-Q8_0.gguf` | Q8_0             | 712148928  | `82a9966edfdbc1b18a27fd90af96d50cbf111a51484f6290e946dccf461c8150` |
| `qwen36-35b-a3b-q6k`                                        | `unsloth/Qwen3.6-35B-A3B-GGUF`            | `Qwen3.6-35B-A3B-UD-Q6_K.gguf`       | Q6_K   | 29308320736 | `4fe53b148b46f9b88830e2a3055c5b15c3a4d1e3ddc9a1384a108d8b9d59f043` | `mmproj-BF16.gguf`                          | F16              | 902822624  | `356dfaa3111376a4f7165e32e8749713378d1700b37cf52e0c50d9f23322334d` |
| `qwen38-27b-iq2s`                                           | `ISTA-DASLab/Qwen3.8-27B-GSQ-RCO-GGUF`    | `Qwen3.8-27B-GSQ-RCO-IQ2_S.gguf`     | IQ2_S  | 9259510912  | `16c9802111aa9ef3acde465188d6d601f8db128ee3d828ad983a5caca4135ecb` | `mmproj-Qwen3.8-27B-BF16.gguf`              | F16              | 931146528  | `13cb7bebccbd04afc8f4090cb949ecf8937cdf7377c5799b1a0c594e7c0d3e16` |

## Readings

Rates carry 95% Wilson intervals. A refusal (here always a truncation at the 1,024-token budget, which the harness records as "unmeasured at this budget, not invalid") stays in the denominator as a non-event. "Identical to control" counts items whose verdict and score equal the first control's.

| Arm                    | S2 false alarms (n=209) | S3 incident hits (n=241) | AUROC | Recall at 5% false alarms | Refusals | Uncertain | Peak VRAM (GiB) | Identical to control |
| ---------------------- | ----------------------- | ------------------------ | ----- | ------------------------- | -------- | --------- | --------------- | -------------------- |
| `control-q4km`         | 21 = 10.0% [6.7-14.9]   | 94 = 39.0% [33.1-45.3]   | 0.677 | 42.3%                     | 2        | 8         | 8.8             | -/450                |
| `control-rep`          | 21 = 10.0% [6.7-14.9]   | 94 = 39.0% [33.1-45.3]   | 0.677 | 42.3%                     | 2        | 8         | 8.8             | 450/450              |
| `control-defaultcache` | 21 = 10.0% [6.7-14.9]   | 94 = 39.0% [33.1-45.3]   | 0.677 | 42.3%                     | 2        | 8         | 8.8             | 450/450              |
| `qwen3vl-8b-q8`        | 23 = 11.0% [7.4-16.0]   | 87 = 36.1% [30.3-42.3]   | 0.684 | 33.2%                     | 2        | 6         | 11.9            | 252/450              |
| `qwen35-4b-q8`         | 7 = 3.3% [1.6-6.8]      | 85 = 35.3% [29.5-41.5]   | 0.746 | 46.5%                     | 1        | 5         | 6.6             | 216/450              |
| `qwen35-9b-q4km`       | 8 = 3.8% [2.0-7.4]      | 84 = 34.9% [29.1-41.1]   | 0.772 | 48.5%                     | 2        | 0         | 7.5             | 192/450              |
| `qwen35-9b-q6k`        | 6 = 2.9% [1.3-6.1]      | 91 = 37.8% [31.9-44.0]   | 0.797 | 51.0%                     | 0        | 0         | 8.9             | 194/450              |
| `gemma4-12b`           | 13 = 6.2% [3.7-10.3]    | 101 = 41.9% [35.9-48.2]  | 0.766 | 52.3%                     | 0        | 12        | 9.5             | 200/450              |
| `qwen3vl-32b-q4km`     | 17 = 8.1% [5.1-12.6]    | 95 = 39.4% [33.5-45.7]   | 0.774 | 47.7%                     | 0        | 2         | 24.5            | 200/450              |
| `gemma4-26b-a4b`       | 42 = 20.1% [15.2-26.0]  | 138 = 57.3% [50.9-63.3]  | 0.795 | 58.1%                     | 0        | 15        | 17.7            | 165/450              |
| `qwen38-27b-q4km`      | 16 = 7.7% [4.8-12.1]    | 119 = 49.4% [43.1-55.6]  | 0.810 | 61.8%                     | 0        | 0         | 17.8            | 128/450              |
| `qwen38-27b-q6k`       | 26 = 12.4% [8.6-17.6]   | 132 = 54.8% [48.5-60.9]  | 0.818 | 56.4%                     | 0        | 0         | 22.7            | 122/450              |
| `qwen3vl-30b-a3b-q8`   | 17 = 8.1% [5.1-12.6]    | 112 = 46.5% [40.3-52.8]  | 0.754 | 49.8%                     | 23       | 0         | 33.6            | 158/450              |
| `qwen36-35b-a3b-q6k`   | 8 = 3.8% [2.0-7.4]      | 66 = 27.4% [22.1-33.3]   | 0.635 | 29.9%                     | 0        | 140       | 29.4            | 72/450               |
| `qwen38-27b-iq2s`      | 18 = 8.6% [5.5-13.2]    | 106 = 44.0% [37.9-50.3]  | 0.788 | 53.5%                     | 0        | 0         | 12.0            | 132/450              |

Against the owner-set bars (F14), whose rule is that a point estimate meeting a bar is a pass and an interval straddling it is marginal:

| Arm                    | S2 against the 5% bar      | S3 against the 90% bar |
| ---------------------- | -------------------------- | ---------------------- |
| `control-q4km`         | misses                     | misses                 |
| `control-rep`          | misses                     | misses                 |
| `control-defaultcache` | misses                     | misses                 |
| `qwen3vl-8b-q8`        | misses                     | misses                 |
| `qwen35-4b-q8`         | meets, interval straddles  | misses                 |
| `qwen35-9b-q4km`       | meets, interval straddles  | misses                 |
| `qwen35-9b-q6k`        | meets, interval straddles  | misses                 |
| `gemma4-12b`           | misses, interval straddles | misses                 |
| `qwen3vl-32b-q4km`     | misses                     | misses                 |
| `gemma4-26b-a4b`       | misses                     | misses                 |
| `qwen38-27b-q4km`      | misses, interval straddles | misses                 |
| `qwen38-27b-q6k`       | misses                     | misses                 |
| `qwen3vl-30b-a3b-q8`   | misses                     | misses                 |
| `qwen36-35b-a3b-q6k`   | meets, interval straddles  | misses                 |
| `qwen38-27b-iq2s`      | misses                     | misses                 |

**The controls.** `control-rep` and `control-defaultcache` match `control-q4km` on all 450 items. So the `b11376` replay is deterministic, and the two prompt-cache settings do not change the answers; the difference between this build and `b7972` (ISS-087) is the build.

**S3 by scenario group** (hits out of 64, 82 and 95 incidents; the groups are the sweep's own, with `package_theft`, `loitering`, `peering_into_windows`, `trying_car_doors`, `casing_with_phone` and `tailgating` as stranger or intent):

| Arm                    | Stranger or intent (n=64) | Context risk (n=82) | Object cued (n=95) |
| ---------------------- | ------------------------- | ------------------- | ------------------ |
| `control-q4km`         | 0                         | 20                  | 74                 |
| `control-rep`          | 0                         | 20                  | 74                 |
| `control-defaultcache` | 0                         | 20                  | 74                 |
| `qwen3vl-8b-q8`        | 0                         | 25                  | 62                 |
| `qwen35-4b-q8`         | 1                         | 15                  | 69                 |
| `qwen35-9b-q4km`       | 1                         | 25                  | 58                 |
| `qwen35-9b-q6k`        | 2                         | 31                  | 58                 |
| `gemma4-12b`           | 2                         | 23                  | 76                 |
| `qwen3vl-32b-q4km`     | 1                         | 33                  | 61                 |
| `gemma4-26b-a4b`       | 7                         | 51                  | 80                 |
| `qwen38-27b-q4km`      | 1                         | 47                  | 71                 |
| `qwen38-27b-q6k`       | 5                         | 47                  | 80                 |
| `qwen3vl-30b-a3b-q8`   | 3                         | 41                  | 68                 |
| `qwen36-35b-a3b-q6k`   | 1                         | 17                  | 48                 |
| `qwen38-27b-iq2s`      | 2                         | 34                  | 70                 |

**Latency per request, indicative only** (the GB300, two parallel slots, not an S4 reading):

| Arm                    | median | p95    | max    |
| ---------------------- | ------ | ------ | ------ |
| `control-q4km`         | 2.0 s  | 2.7 s  | 7.4 s  |
| `control-rep`          | 2.1 s  | 7.3 s  | 10.8 s |
| `control-defaultcache` | 2.0 s  | 2.7 s  | 6.6 s  |
| `qwen3vl-8b-q8`        | 2.3 s  | 5.5 s  | 12.6 s |
| `qwen35-4b-q8`         | 4.3 s  | 7.9 s  | 13.5 s |
| `qwen35-9b-q4km`       | 2.4 s  | 6.2 s  | 10.6 s |
| `qwen35-9b-q6k`        | 2.9 s  | 4.0 s  | 11.1 s |
| `gemma4-12b`           | 1.8 s  | 5.4 s  | 9.2 s  |
| `qwen3vl-32b-q4km`     | 9.2 s  | 21.5 s | 39.6 s |
| `gemma4-26b-a4b`       | 1.7 s  | 4.0 s  | 8.0 s  |
| `qwen38-27b-q4km`      | 13.6 s | 17.0 s | 19.5 s |
| `qwen38-27b-q6k`       | 6.9 s  | 17.7 s | 29.0 s |
| `qwen3vl-30b-a3b-q8`   | 3.4 s  | 8.6 s  | 18.7 s |
| `qwen36-35b-a3b-q6k`   | 2.6 s  | 8.1 s  | 12.4 s |
| `qwen38-27b-iq2s`      | 11.2 s | 14.2 s | 18.2 s |

## The selection rule (OD-26)

**How it was set.** On 2026-10-04 the owner told the agent: "set the selection rule and sweep report" (recorded with those words in the 17 Intake log, entry 'the sweep report and the selection rule'). The content of the rule below is the agent's **[A]** and is open to the owner's amendment. **It was set after the readings had been seen**, by the owner and the agent: its two margins were fixed in `analysis.py` before the script was first run, but the structure, the gates and the choice of yardstick were made with the data known. So it is a shortlisting rule, not a pre-registered test, and its output is a list of arms to confirm on items that did not choose them, never a pick.

**The rule** (the answers to ISS-097's items (a) to (e)):

- **(a) Metrics.** S3 hits (higher) and S2 false alarms (lower) decide. AUROC, recall at 5% false alarms, the uncertain rate and latency are reported and do not decide.
- **(b) Yardstick and test.** The shipped Qwen3-VL-8B Q4_K_M (`control-q4km`) on the same build is the yardstick, because no arm meets the F14 bars and absolute gates would select nothing; the bars stay the product's acceptance bars and are printed beside every arm. An arm is compared with the control on the same 450 items by a paired bootstrap that resamples whole scenarios (31 clusters, 10,000 resamples, seed 20261004), because stills of one scenario are not independent (ISS-043). With dS2 = S2 of the arm minus S2 of the control and dS3 likewise, in points:
  - _no clear harm:_ the upper bound of dS2 is at most +2.0 **and** the lower bound of dS3 is at least -5.0;
  - _clear benefit:_ the upper bound of dS2 is below 0 **or** the lower bound of dS3 is above 0.
- **(c) Gates beyond accuracy** (all must hold). G1: the arm scored all 450 items on the shared build. G2: refusals at most the control's 2 (spec S5 asks for none). G3: peak VRAM at most 18.4 GiB, which is S1's 20.4 GiB for the whole resident set minus a 2 GiB allowance for the detector, specialists and runtime; **that allowance is an assumption**, to be replaced by the S1 re-take on 24 GB-class hardware (ISS-046). Tier fit against the doc 20 budgets and S4 latency cannot be decided on a GB300 (F13). Licence is not applied here: F12 waives it as a selection criterion for specialist models, and the register for the VLMs is OD-18 (ISS-063).
- **(d) Selection and confirmation.** The 450 stills are the selection set. An arm that advances is confirmed **once** on a frozen holdout that did not choose it (ISS-016), under the same test, before anything changes in the product; and, because the shipped image pins `b7972`, it is re-qualified on the pinned build with a control replay (ISS-087).
- **(e) Unequal conditions.** Arms are compared as served: thinking forced off for nine arms, the 1,120 vision-token cap for the Gemma arms, and the mmproj precision differing between families. An arm that advances carries its conditions with it, and a confirmation run uses the shipped 1,280-token cap if the model allows.

**Result.**

| Arm                  | dS2 vs the control, points [95% scenario-cluster CI] | dS3 vs the control, points [95% scenario-cluster CI] | G2 refusals | G3 VRAM | No clear harm | Clear benefit | Advances |
| -------------------- | ---------------------------------------------------- | ---------------------------------------------------- | ----------- | ------- | ------------- | ------------- | -------- |
| `qwen3vl-8b-q8`      | -3.9 to +7.9                                         | -8.6 to +2.7                                         | yes         | yes     | no            | no            | **no**   |
| `qwen35-4b-q8`       | -13.6 to +0.0                                        | -8.5 to +0.9                                         | yes         | yes     | no            | no            | **no**   |
| `qwen35-9b-q4km`     | -12.3 to -0.9                                        | -11.7 to +3.3                                        | yes         | yes     | no            | yes           | **no**   |
| `qwen35-9b-q6k`      | -13.6 to +0.0                                        | -11.5 to +9.0                                        | yes         | yes     | no            | no            | **no**   |
| `gemma4-12b`         | -12.8 to +4.4                                        | -3.6 to +10.3                                        | yes         | yes     | no            | no            | **no**   |
| `qwen3vl-32b-q4km`   | -5.3 to +3.3                                         | -9.4 to +9.9                                         | yes         | no      | no            | no            | **no**   |
| `gemma4-26b-a4b`     | -2.3 to +22.2                                        | +7.6 to +33.7                                        | yes         | yes     | no            | yes           | **no**   |
| `qwen38-27b-q4km`    | -6.0 to +1.6                                         | -0.5 to +24.0                                        | yes         | yes     | yes           | no            | **no**   |
| `qwen38-27b-q6k`     | -0.8 to +5.4                                         | +7.0 to +27.3                                        | yes         | no      | no            | yes           | **no**   |
| `qwen3vl-30b-a3b-q8` | -9.6 to +4.7                                         | -1.8 to +17.9                                        | no          | no      | no            | no            | **no**   |
| `qwen36-35b-a3b-q6k` | -13.2 to +1.6                                        | -21.1 to -1.9                                        | yes         | no      | no            | no            | **no**   |
| `qwen38-27b-iq2s`    | -6.2 to +4.6                                         | -2.6 to +12.8                                        | yes         | yes     | no            | no            | **no**   |

**No arm advances.** Eight of the twelve model arms pass both gates; four fail one (the 30B-A3B fails G2 with 23 refusals and G3 on VRAM, and the 32B, the 27B Q6_K and the 35B-A3B fail G3). Of those, the nearest miss is **Qwen3.8-27B Q4_K_M**: it passes the gates and the no-harm test, and fails only the clear-benefit test, because the lower bound of its S3 gain is -0.5 points (the gain is +10.4 points, interval -0.5 to +24.0). The Qwen3.5-9B Q6_K arm has the largest false-alarm drop (S2 2.9% against 10.0%) but its S3 interval allows a loss of up to 11.5 points, so it fails no-harm.

**Why the rule is this hard to pass.** With 31 scenarios the clustered intervals are 6 to 26 points wide, so a margin of 5 points can be met only by an arm that is clearly better. The same data read item by item, treating the 450 stills as independent, look far more decisive, and that is the trap clustering exists to avoid:

| Arm                  | S2: false alarms only in the arm / only in the control | exact p  | S3: hits only in the arm / only in the control | exact p  |
| -------------------- | ------------------------------------------------------ | -------- | ---------------------------------------------- | -------- |
| `qwen3vl-8b-q8`      | 7 / 5                                                  | 0.774    | 9 / 16                                         | 0.23     |
| `qwen35-4b-q8`       | 2 / 16                                                 | 0.00131  | 9 / 18                                         | 0.122    |
| `qwen35-9b-q4km`     | 5 / 18                                                 | 0.0106   | 18 / 28                                        | 0.184    |
| `qwen35-9b-q6k`      | 2 / 17                                                 | 0.000729 | 23 / 26                                        | 0.775    |
| `gemma4-12b`         | 10 / 18                                                | 0.185    | 24 / 17                                        | 0.349    |
| `qwen3vl-32b-q4km`   | 6 / 10                                                 | 0.454    | 21 / 20                                        | 1        |
| `gemma4-26b-a4b`     | 30 / 9                                                 | 0.00107  | 49 / 5                                         | 3.89e-10 |
| `qwen38-27b-q4km`    | 9 / 14                                                 | 0.405    | 38 / 13                                        | 0.000621 |
| `qwen38-27b-q6k`     | 14 / 9                                                 | 0.405    | 46 / 8                                         | 1.38e-07 |
| `qwen3vl-30b-a3b-q8` | 10 / 14                                                | 0.541    | 36 / 18                                        | 0.0198   |
| `qwen36-35b-a3b-q6k` | 6 / 19                                                 | 0.0146   | 18 / 46                                        | 0.000617 |
| `qwen38-27b-iq2s`    | 10 / 13                                                | 0.678    | 29 / 17                                        | 0.104    |

For example, the 27B Q4_K_M arm's S3 gain is 38 hits against 13 (p = 0.0006) item by item but its clustered interval includes zero, and the Qwen3.5-9B Q6_K arm's false-alarm drop is 2 against 17 (p = 0.0007) item by item but its clustered interval touches zero. **The honest reading is that this corpus cannot separate the arms at the scenario level**, so more scenarios or a frozen holdout (ISS-016, ISS-043) are needed before any of them can be preferred to the shipped model. If the owner wants to carry the 27B Q4_K_M and the 9B Q6_K arms into that confirmation anyway, that is a choice the owner makes; it is not an output of the rule.

## What the readings show (descriptive; none of this is a selection)

- **No arm approaches the S3 bar.** The best, Gemma 4 26B-A4B, reads 138 of 241 (57.3%) and pays for it with 42 of 209 false alarms (20.1%), an S2 interval wholly above 5%.
- **The stranger-or-intent incidents stay out of reach.** The shipped model scores 0 of 64; no arm scores more than 7 of 64. That is the group ISS-086 argues one still cannot show.
- **Four arms' point estimates meet the 5% S2 bar**, all with intervals that straddle it: Qwen3.5-4B Q8_0 (3.3%), Qwen3.5-9B Q4_K_M (3.8%), Qwen3.5-9B Q6_K (2.9%) and Qwen3.6-35B-A3B Q6_K (3.8%). Their S3 sits between 27.4% and 37.8%; the 35B-A3B reaches its low S2 by calling 140 of 450 items uncertain and 155 rejected.
- **Ranking quality is highest in the Qwen3.8-27B arms** (AUROC 0.810 at Q4_K_M, 0.818 at Q6_K; 0.788 at IQ2_S) against 0.677 for the shipped model; recall at 5% false alarms is best at Q4_K_M (61.8%).
- **Quantization moves answers about as much as the architecture does.** The 27B reads S2 7.7%, 12.4% and 8.6% and S3 49.4%, 54.8% and 44.0% at Q4_K_M, Q6_K and IQ2_S; the 8B at Q8_0 and at Q4_K_M agree on only 252 of 450 items.
- **The models disagree with the shipped one on most items:** between 72 and 252 of 450 items match its verdict and score.
- **The 30B-A3B refuses 23 items**, all truncations at the 1,024-token budget (the verdict is unmeasured at that budget, not invalid), against 2 for the shipped model.
- **VRAM:** the 32B Q4_K_M peaks at 24.5 GiB, the 27B Q6_K at 22.7, the 35B-A3B at 29.4 and the 30B-A3B at 33.6; the shipped model peaks at 8.8. These are GB300 readings (F13).

## What this does not show

- A model that beats the shipped one. Nothing here is a confirmation.
- Anything about video, the detector, the key-frame selector or the specialists.
- Thinking-mode behaviour: nine arms ran with thinking forced off.
- How any arm behaves on the pinned `b7972` build, on a 24 GB card, or at the product's real latency.
- The effect of the prompt. The rubric prompt that lifted S3 on the 8B (ledger, 2026-10-03) was not run on these arms (ISS-086).
- A fair comparison for the two Gemma arms at the shipped vision-token cap.

## Re-derive it

1. `python3 analysis.py .` in this folder recomputes every table above from `items.csv` and `arms.csv` and asserts that each count equals the harness's (`s2_false_alarms`, `s3_hits`, `refusals`, AUROC and recall at 5% false alarms); it writes `stats.json`. It needs only the standard library.
2. Each `eval_run_id` and `run.json` above is in the off-repo eval store and synthbench root; `extract.py` shows how `items.csv` and `arms.csv` were produced from them.
3. The sha256 of each model and mmproj file is in the identity table; `sha256sum` of the kept weights equals it.

## Provenance

| Item                     | Value                                                                                                                                                                                                                                                                |
| ------------------------ | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Analysis                 | `analysis.py`, `extract.py` and the two CSV files in this folder (the sweep's own `analyze()` produced the AUROC, recall and group counts the analysis cross-checks)                                                                                                 |
| Driver                   | `sweep.py` sha256 `ec50f2274ada3f31ef21ead71bb93006e592d0a2d929d65abe0f7365c4325141` (the version from the fifth arm on); the version for the first four arms, before the keep-weights edit, is `7504d814e96fa054bd506abc4c16e58e075e93386b5f651ff5b5b8ecddef50df`   |
| Replay script            | `replay_arm.py` sha256 `a68d248fe902e829d1d64fb39859272bf5291e1d59d76c2d230b75ad3cdc7571`                                                                                                                                                                            |
| Recipes                  | `recipes.json` sha256 `c63af2bd1a8a68d8c6cd5bef50d2494a59a46524f8aacadc90080f20f564ce55`                                                                                                                                                                             |
| Copies in this repo      | `driver/` holds the driver `sweep.py` and its pre-edit copy `sweep.before-keep-weights.py`, `replay_arm.py`, `recipes.json`, the weights downloader `download_all.py`, the raw `results.jsonl`, `sweep.log` and `summary.md`; their sha256 values are the ones above |
| Where the originals live | `$AGENT_GPU_DIR/out/experiments/model-sweep/` (driver, `results.jsonl`, `sweep.log`, per-arm replay logs) and `$AGENT_GPU_DIR/out/sbroot/` (the eval store and `runs/replays/<id>/run.json`); these are off-repo scratch                                             |

### Run identity

| Arm                    | replay id                               | `eval_run_id`                      | `run.json` (under the synthbench root)                        | replay commit | replay minutes |
| ---------------------- | --------------------------------------- | ---------------------------------- | ------------------------------------------------------------- | ------------- | -------------- |
| `control-q4km`         | `20261003T194331Z-control-q4km`         | `f1faa819b375447897507a3b48c622bb` | `runs/replays/20261003T194331Z-control-q4km/run.json`         | `ab3bd002`    | 16.1           |
| `control-rep`          | `20261003T200059Z-control-rep`          | `891a1b7a5ebb4a6bb06a910c1c881153` | `runs/replays/20261003T200059Z-control-rep/run.json`          | `2cd619db`    | 21.5           |
| `control-defaultcache` | `20261003T202249Z-control-defaultcache` | `42d8820c91e446aa90d9a2c62e1db151` | `runs/replays/20261003T202249Z-control-defaultcache/run.json` | `2cd619db`    | 16.3           |
| `qwen3vl-8b-q8`        | `20261003T204300Z-qwen3vl-8b-q8`        | `ee110a58b7a94c8bab2aae73d20196fa` | `runs/replays/20261003T204300Z-qwen3vl-8b-q8/run.json`        | `2cd619db`    | 19.5           |
| `qwen35-4b-q8`         | `20261003T210915Z-qwen35-4b-q8`         | `5ba77c5ec224445da22e8726755a0d1a` | `runs/replays/20261003T210915Z-qwen35-4b-q8/run.json`         | `2cd619db`    | 32.3           |
| `qwen35-9b-q4km`       | `20261003T214542Z-qwen35-9b-q4km`       | `7717264dd9b04457a8c01eb09bc73495` | `runs/replays/20261003T214542Z-qwen35-9b-q4km/run.json`       | `2cd619db`    | 21.1           |
| `qwen35-9b-q6k`        | `20261003T220750Z-qwen35-9b-q6k`        | `9a0c3553115241b39d8f8b0d27f768bd` | `runs/replays/20261003T220750Z-qwen35-9b-q6k/run.json`        | `2cd619db`    | 23.1           |
| `gemma4-12b`           | `20261003T223156Z-gemma4-12b`           | `a61fb72437e14e52bcbab9549598f564` | `runs/replays/20261003T223156Z-gemma4-12b/run.json`           | `2cd619db`    | 16.6           |
| `qwen3vl-32b-q4km`     | `20261003T225034Z-qwen3vl-32b-q4km`     | `edd935335aa94088983760c4c8a50096` | `runs/replays/20261003T225034Z-qwen3vl-32b-q4km/run.json`     | `2cd619db`    | 84.5           |
| `gemma4-26b-a4b`       | `20261004T001645Z-gemma4-26b-a4b`       | `3a45c47e3550455c9838f190b1e8a9eb` | `runs/replays/20261004T001645Z-gemma4-26b-a4b/run.json`       | `2cd619db`    | 14.7           |
| `qwen38-27b-q4km`      | `20261004T003315Z-qwen38-27b-q4km`      | `2a38e63962d04c138593c62f0e5bcdba` | `runs/replays/20261004T003315Z-qwen38-27b-q4km/run.json`      | `2cd619db`    | 91.0           |
| `qwen38-27b-q6k`       | `20261004T020640Z-qwen38-27b-q6k`       | `3b0fe11af37f4407a8b3bb75c1776422` | `runs/replays/20261004T020640Z-qwen38-27b-q6k/run.json`       | `2cd619db`    | 71.4           |
| `qwen3vl-30b-a3b-q8`   | `20261004T032152Z-qwen3vl-30b-a3b-q8`   | `ad76d31c93c94161b24f190d01c859d5` | `runs/replays/20261004T032152Z-qwen3vl-30b-a3b-q8/run.json`   | `2cd619db`    | 30.2           |
| `qwen36-35b-a3b-q6k`   | `20261004T035525Z-qwen36-35b-a3b-q6k`   | `434c071091fe4432be8bc37bf8cb6fb0` | `runs/replays/20261004T035525Z-qwen36-35b-a3b-q6k/run.json`   | `2cd619db`    | 23.2           |
| `qwen38-27b-iq2s`      | `20261004T041952Z-qwen38-27b-iq2s`      | `a4f251dfcd234d729c9db9564abac575` | `runs/replays/20261004T041952Z-qwen38-27b-iq2s/run.json`      | `2cd619db`    | 78.6           |
