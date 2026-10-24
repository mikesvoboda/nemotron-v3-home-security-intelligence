# 03. Idea catalogue

> Design proposal; nothing is built. Paths and numbers cited as evidence are as of `origin/main` `9cb9e60b0` (2026-10-23). Back to the [index](README.md).

This is the space the search would explore, organized by pipeline layer. It is a starting map, not a commitment: the manager writes briefs from it, and the findings register records what each brief learns.

## 1. Tags

**Cost class**, which decides how often the search can afford an idea:

| Class | Cost                                                              | Example                                                  |
| ----- | ----------------------------------------------------------------- | -------------------------------------------------------- |
| C1    | CPU seconds; re-scores cached output                              | A new decision head over cached detector and VLM outputs |
| C2    | GPU minutes; one replay                                           | A new prompt template, frame mode or crop policy         |
| C3    | GPU hours; training or a new model                                | A LoRA run, a new VLM download, a fresh scenario batch   |
| C4    | Blocked on a ruling or a corpus feature before it can be searched | A pose model; household identities in synthbench         |

C1 trials are cheap enough to spend a select set within an epoch. The manager budgets select queries per cost class ([`02-evaluation.md`](02-evaluation.md) §2).

**Evidence:** _measured_ (a number exists in the repo), _untested_, or _refuted_ (seeded into the findings register, §9). **Gate:** anything promotion needs beyond the standard path in [`02-evaluation.md`](02-evaluation.md) §8.

## 2. L0: Data

Every other layer depends on this one.

| Idea                                                                           | Targets                                      | Evidence                                                                    | Cost |
| ------------------------------------------------------------------------------ | -------------------------------------------- | --------------------------------------------------------------------------- | ---- |
| Fresh synthbench batches each epoch, over-sampling benign hard negatives       | S2 certification; resisting select-set reuse | 209 benign items cannot certify a 5% bar                                    | C3   |
| **Consistent household identities**: the same residents rendered across stills | Makes face and re-ID evaluable at all        | `resident_arrival` false alarms are 0 of 10 reachable by prompt (doc 23 §2) | C4   |
| Multi-camera clips of one event                                                | Re-ID, loitering, casing                     | Few incident clips exist yet                                                | C3   |
| Public datasets (UCF-Crime, XD-Violence, PA-100K, pose sets)                   | LoRA and system-1 **training only**          | None used locally                                                           | C3   |

## 3. L1: Small vision models that add context

| Model                                                    | Adds                                                                                              | For                                         | Evidence and gate                                                                                                                               |
| -------------------------------------------------------- | ------------------------------------------------------------------------------------------------- | ------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------- |
| **YOLOE-26**, open vocabulary                            | Threat objects: pry bar, bolt cutters, knife, ladder, gas can, balaclava, gloves, a phone held up | Object-cued incidents, without oracle props | Approved as a future slot (F12); untested                                                                                                       |
| **Face detection and household match**                   | Resident or unknown                                                                               | `resident_arrival` false alarms             | SCRFD and the recognizer are in `models.yml` but report "unavailable" on a default deploy; needs L0 identities                                  |
| **Re-ID** (OSNet-AIN)                                    | "Seen at another camera N minutes ago"                                                            | Casing, loitering                           | In `models.yml`; needs multi-camera clips                                                                                                       |
| **Person attributes**                                    | Hood up, face covered, gloves, hi-vis or uniform, carrying a box                                  | Delivery versus concealment                 | Untested; a new specialist pick                                                                                                                 |
| **Pose** (an RTMPose-class model)                        | Crouching, reaching, climbing, hands at a window, pulling a handle                                | Trying car doors, peering into windows      | C4: a new pick needs an owner spec revision. The legacy `yolov8n-pose` row was deleted by R8 S3 owner ruling 2 and stays deleted (`models.yml`) |
| **Head pose or gaze**                                    | Looking into a window versus walking past                                                         | Peering into windows                        | Untested; C4                                                                                                                                    |
| **Monocular depth** (a small Depth-Anything-class model) | Distance to a door, window or vehicle, without hand-drawn zones                                   | The context-risk group                      | Untested; C2                                                                                                                                    |
| **Action recognition** on clips (X3D or MoViNet class)   | Running, climbing, fighting, sneaking                                                             | The stranger-or-intent group                | External only: a 65.8M-parameter 3D CNN was better calibrated than VLMs for violence (ROC AUC 92.59%, cited in doc 20)                          |
| **Lighting, IR and weather classifier**                  | Routes image enhancement; sets confidence                                                         | Night false alarms                          | Untested; C2                                                                                                                                    |

Every new specialist keeps the existing ship gate: an owner-approved spec revision, a case where it changes the verdict, and a false-alarm measurement on the owner's night footage. The search may explore any of them.

## 4. L2: Deterministic algorithms

| Idea                           | Mechanism                                                                                                                                                                                            | Evidence                                                                                                                                                       |
| ------------------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Tracking**                   | A tracker (ByteTrack or OC-SORT class) over bursts yields real track ids, dwell, speed and path                                                                                                      | At the stamp no non-test code sets `Detection.track_id`, so the zone-crossing line the prompt prints is always false (doc 18, "Why the seams are empty today") |
| **Trajectory grammar**         | Finite-state rules over tracks and zones. Delivery: approach, door, leave. Car-door trying: vehicle to vehicle to vehicle. Casing: a perimeter loop. Tailgating: two entries within a short interval | Untested; emits typed facts for the VLM prompt and for L6                                                                                                      |
| **Object persistence**         | A package appeared, or disappeared while a non-resident was present                                                                                                                                  | The legacy package-tracking service was deleted with the legacy tier (R8); untested on the current path                                                        |
| **Key-frame selection**        | Motion energy, detection peaks, salient track moments                                                                                                                                                | A selector frame mode exists in the replay (ISS-037)                                                                                                           |
| **Enhancement and slicing**    | Contrast and gamma correction for IR; tiled detection for small distant objects                                                                                                                      | Untested; C2                                                                                                                                                   |
| **Evidence cross-checks**      | Lower the score when the VLM names an object the detector never saw; raise it when the detector saw a threat object the VLM ignored                                                                  | Untested; C1                                                                                                                                                   |
| **Frame aggregation**          | Max, mean, noisy-OR or hysteresis over per-frame scores within one batch window                                                                                                                      | Untested; C1                                                                                                                                                   |
| **Calibration and abstention** | Isotonic calibration per tier; conformal abstention that routes uncertain items to escalation with a coverage guarantee                                                                              | Shipping a threshold is owner territory (doc 23 §3); the search may propose operating points with evidence                                                     |

## 5. L3: What the VLM is shown and asked

| Idea                                                                                                                                      | Evidence                                                                                                                                                                                        |
| ----------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Multiple frames**: 4-frame bursts, 10 frames ending at the event, or a 2×2 mosaic in one image (fewer vision tokens)                    | The single-still ceiling is 73.4–76.3% (ISS-086 study). Clip numbers may not be published before the owner signs the clip preregistration (`docs/research/2026-10-07-clip-measurement-prereg/`) |
| **High-resolution crops** around detections, beside the full frame                                                                        | Untested; doc 23 diagnoses a perception limit                                                                                                                                                   |
| **Set-of-mark**: numbered boxes drawn on the image, matching the detections list                                                          | Untested                                                                                                                                                                                        |
| **Track-trail overlay**: the trajectory drawn onto the still, so one image shows motion                                                   | Untested                                                                                                                                                                                        |
| **Agentic zoom**: the VLM asks for a crop ("look at person 2's hands") as a tool call                                                     | Untested; C2                                                                                                                                                                                    |
| **A question checklist**: targeted yes or no questions instead of one holistic score ("is a hand on a door handle?"); the answers feed L6 | Untested. Follows from doc 23: the model fails at perceiving, so ask it to perceive                                                                                                             |
| **Thinking enabled**: thinking variants, or hybrid models with thinking on                                                                | Untested: every sweep arm ran with thinking off. Latency does not bind: about 6 s warm against a 30 s budget (doc 18)                                                                           |

## 6. L4: The VLM per GPU tier

Starting candidates come from doc 20 §3, which chose them on fit and support, not accuracy.

| Tier (budget)   | Starting candidates                                 | Evidence                                                                                                        |
| --------------- | --------------------------------------------------- | --------------------------------------------------------------------------------------------------------------- |
| 10 GB (8.5 GiB) | Qwen3.5-4B Q8_0                                     | Sweep: S2 3.3%, S3 35.3%                                                                                        |
| 12 GB (10.2)    | Qwen3.5-9B Q4_K_M                                   | Sweep: S2 3.8%, S3 34.9%                                                                                        |
| 16 GB (13.6)    | Qwen3.5-9B Q6_K; the shipped Qwen3-VL-8B Q4_K_M     | Sweep: S2 2.9%, S3 37.8%; shipped S2 10.0%, S3 39.0%                                                            |
| 24 GB (20.4)    | Gemma-4-26B-A4B; Qwen3.8-27B Q4_K_M                 | Sweep: the 27B had the best ranking (AUROC 0.810) and was the nearest miss under OD-26                          |
| 32 and 48 GB    | Larger dense models; a video-native VLM (ISS-093)   | Untested                                                                                                        |
| Any             | **Ensembles of different models** within the budget | Sweep arms matched the shipped model's verdict and score on only 72 to 252 of 450 items, so their errors differ |

All sweep numbers used oracle detections, one still and thinking off. Quantization variants are in scope, but expect most to fall inside the null envelope: the 27B read S3 49.4%, 54.8% and 44.0% at three quantizations.

## 7. L5: Adapting the model

| Idea                                                                                                    | Evidence and risk                                                                                                                                                      |
| ------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **QLoRA fine-tuning** on train-split scenarios and public data, merged, converted to GGUF and quantized | Doc 20 calls LoRA the only lever with large published gains on the same 8B. Risk: the adapter learns the image generator's look; it must win on fresh scenario batches |
| **A calibration adapter** on a small model                                                              | Proposed in doc 20; the same doc warns against assuming a LoRA fixes calibration                                                                                       |
| **Distillation** from the best large model into each tier                                               | One teacher serves every tier; capped by the items the teacher also gets wrong                                                                                         |
| **Preference tuning** on pairs of incidents and their benign look-alikes                                | Untested; aims at hard negatives directly                                                                                                                              |
| **A linear probe on frozen VLM hidden states**                                                          | Untested here. Needs a spike: does llama.cpp expose embeddings for multimodal input?                                                                                   |

## 8. L6: The decision layer (system-1)

This layer needs research before it is designed; [`04-system-1-research.md`](04-system-1-research.md) holds the open questions. The candidate roles:

| Role                    | Idea                                                                                                                                                                                                                                 | Why it matters                                                                                                                                                                                                                    |
| ----------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Fusion**              | A small CPU model over every cached signal (detector, open vocabulary, attributes, pose, track grammar, zone, time, household match, re-ID novelty, the VLM's score, verdict and checklist answers) outputs a calibrated probability | 127 of 153 S3 misses are scored 10 or below, and 148 of 153 carry a confirmed verdict (doc 20): the VLM's score is polarized. Trials are C1, so this is where the search runs fastest and where it wears out a select set fastest |
| **Gate**                | Skip the VLM on confident benign items                                                                                                                                                                                               | Saves latency and tokens for multi-frame inputs on small tiers; doc 18 notes latency alone does not bind                                                                                                                          |
| **Escalation**          | Send uncertain items to a larger VLM or to a "needs review" class                                                                                                                                                                    | An oracle router between the 8B and the flagship caps S3 at 60.6–66.4% on stills, because both are wrong on 95 of 450 items (doc 20)                                                                                              |
| **Rule-based severity** | The VLM emits typed facts; auditable rules compute the severity band                                                                                                                                                                 | Doc 23 recommends grading severity in a rule engine; OD-7 ruled the threat fast path "build, gated"                                                                                                                               |

## 9. Seeded results: do not re-buy

These seed the findings register. Each holds only under its recorded conditions (one still, oracle detections, the shipped 8B unless stated), so a change of conditions such as multi-frame input can reopen it.

| Result                                                                                                                                                       | Source                           |
| ------------------------------------------------------------------------------------------------------------------------------------------------------------ | -------------------------------- |
| Prompt wording alone did not pass OD-26 across ten arms at the then-shipped threshold of 30; arm B's text shipped later only as a pair with floor 60 (OD-29) | Doc 23 and its §5 follow-up      |
| A separate post-hoc judge downgraded 1 of 449 confirmed verdicts                                                                                             | Doc 23 §2                        |
| Doubling the token budget changed none of 450 answers on four arms                                                                                           | Doc 23, stage 3                  |
| Placing the verdict before the reasoning lowered S3 by 17 points                                                                                             | Doc 23 §2                        |
| Self-consistency over three samples moved along the same ROC curve                                                                                           | Doc 20                           |
| The first-digit logprob score held no hidden ranking headroom                                                                                                | `docs/vss-integration/README.md` |
| Swapping the model at one still did not separate any arm from the shipped one under OD-26                                                                    | Sweep report                     |

## 10. Suggested epoch order

1. **The realistic-input baseline**: detector and open-vocabulary output instead of oracle props. Required before anything else is comparable.
2. **Multiple frames, tracking and trail overlays.** They attack the stranger-or-intent group, where the ceiling evidence points.
3. **The fusion model** over cached signals: cheap trials aimed at the calibration problem, after the research in [`04-system-1-research.md`](04-system-1-research.md).
4. **Specialists**: household face match, re-ID, person attributes. Needs the L0 identity feature.
5. **Per-tier VLMs with thinking enabled**, and ensembles.
6. **LoRA and distillation**, once the corpus is large enough to resist overfitting.
