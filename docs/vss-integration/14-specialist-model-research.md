# 14 — Specialist Model Research (2026-09-25)

Candidate models for the **resident specialists** that feed the VLM through `specialist_outputs`
(spec rev 6, D3). It was written from the owner's host session. The rulings it depends on are in
the ledger as **F12**:

- licenses are **not** a selection criterion;
- the face gap is closed with option A;
- YOLOE-26 is approved for a future open-vocabulary slot.

**What this doc is for:**

- **§1 (faces, plates)** feeds Phase 1 Task 3b now. The plan's Task 3b names the picks.
- **Everything else is a proposal for spec rev 7.** Nothing there enters the build without an
  owner-approved spec change. Its shortlist is at the end.

## The test a specialist must pass

A specialist is worth its memory only if it gives the VLM **a fact that isn't in the 1-4 stills**:

| Fact        | Why the VLM can't get it itself                                   |
| ----------- | ----------------------------------------------------------------- |
| Identity    | Recognizing a household face or plate needs the household gallery |
| Memory      | Knowing what is normal for this camera needs its history          |
| Time        | Seeing motion needs more frames than the key stills               |
| Fine detail | Small or distant objects are exactly where small VLMs fail        |

Further requirements:

- **Output:** one short line, for example `face: unknown adult, face covered (0.91)`. Anything that
  needs a paragraph is the VLM's job.
- **Budget:** about 300 MB of GPU memory or less at FP16, or run on CPU. The spec's VRAM row
  allows about 2 GiB for all resident specialists together.
- **Latency:** milliseconds per crop, because S4 gives the whole verdict 30 s at p95.

The owner chose three gap buckets for this round: identity, fine detail, and time plus memory.
Audio events, night/IR image quality and wildlife classification were not researched.

## Method and evidence levels

Three host-side agents opened the **primary source** for every candidate (Hugging Face model
card, GitHub repo or LICENSE, NGC page, or paper). File sizes come from the HF or GitHub APIs.
Any field no primary source confirmed is marked `unverified`. **est.** marks an agent's own
estimate, usually latency from parameter count or FLOPs. Perplexity deep research
(`sonar-deep-research`) supplied leads only; its tables were mostly `unverified`, and nothing
here rests on it alone.

## §1 Identity (Phase 1 Task 3b)

### Faces: the picks

| Role                                               | Model                                                               | Evidence                                                                     | Size                                      | Notes                                                                                                   |
| -------------------------------------------------- | ------------------------------------------------------------------- | ---------------------------------------------------------------------------- | ----------------------------------------- | ------------------------------------------------------------------------------------------------------- |
| Detection + 5 landmarks                            | **SCRFD-10G-KPS** (`scrfd_10g_bnkps.onnx`, InsightFace `buffalo_l`) | WIDER val 95.16 / 93.87 / **83.05** (easy / medium / hard)                   | 3.86M params, 16.9 MB                     | Landmarks allow ArcFace 5-point alignment                                                               |
| Embedding                                          | **`w600k_r50.onnx`** (InsightFace `buffalo_l`, R50, WebFace600K)    | IJB-C (TAR @ FAR 1e-4) **97.25**; MR-ALL 91.25                               | whole pack 326 MB; this file `unverified` | Load with onnxruntime on CPU, hash-pinned                                                               |
| Challenger for small/night faces (bake-off, later) | **AdaFace** IR101 or IR18 (WebFace4M/12M)                           | IR101: TinyFace Rank-1 **72.29**; IR18: LFW 99.53, CFP-FP 97.26, AgeDB 96.47 | IR18 96 MB                                | Its quality-adaptive margin targets low-quality faces. No published ONNX, but export is straightforward |
| Tiny fallback                                      | EdgeFace-S γ0.5                                                     | IJB-C 95.63, CFP-FP 95.74                                                    | 3.65M params, 14.7 MB                     | For when CPU time matters                                                                               |
| Face quality (later)                               | CR-FIQA                                                             | Top ranks in NIST FATE-Quality (the authors' claim)                          | `unverified`                              | A size-and-score gate is enough for 3b                                                                  |

- **The old "~1.5 GB VRAM" figure is not the model's cost.** It came from the `insightface`
  package's `FaceAnalysis` putting all five `buffalo_l` models on the GPU. The face leg needs two
  ONNX files, run on CPU.
- **Why not the current face detector:** `yolo11-face` (AdamCodd YOLOv11n; WIDER 0.942 / 0.921 /
  0.810; 5.4 MB FP16) outputs boxes only. ArcFace-family embedders are trained on aligned crops,
  so unaligned crops quietly lose accuracy.

**For reference, the permissive alternatives set aside by the license ruling:**

- **AuraFace-v1 `glintr100.onnx`** (Apache-2.0; 260.7 MB FP32; LFW 99.65, CFP-FP 95.19; no
  IJB-C or TinyFace figures published). Watch out for the rest of that repo: four of its five
  ONNX files are byte-identical to InsightFace's `antelopev2` pack.
- **YuNet** (MIT; 233 KB; WIDER 0.884 / 0.866 / 0.750).
- **eDifFIQA(T)** (CC-BY-4.0; 7.3 MB).

### Plates

| Part               | Model                                                                     | Evidence                                                             | Size            |
| ------------------ | ------------------------------------------------------------------------- | -------------------------------------------------------------------- | --------------- |
| Detector (keep)    | `yolo-v9-t-384-license-plate-end2end` (open-image-models)                 | mAP50 0.920 (the `s-608` variant: 0.966, 28.6 MB)                    | 7.8 MB          |
| OCR (current pin)  | `cct-xs-v1-global-model`                                                  | US plate_acc 0.905 (author's validation split)                       | ~2.1 MB         |
| OCR (suggested)    | **`cct-xs-v2-global-model`**; `cct-s-v2` is the docs' recommended default | US plate_acc **0.929**, char 0.987 (a different split)               | 3.3 MB / 5.3 MB |
| Second-opinion OCR | PaddleOCR `en_PP-OCRv5_mobile_rec`                                        | 85.25 on Paddle's English recognition set (general text, not plates) | 7.8 MB          |

The current stack totals about **10 MB**, not the 28 MB in `models.yml`. Re-test any OCR swap on
our own plate crops, because the two published numbers use different validation splits.

### Vehicles (rev 7 candidate)

| Model                               | Outputs                                                      | Evidence                                | Size                              |
| ----------------------------------- | ------------------------------------------------------------ | --------------------------------------- | --------------------------------- |
| **NVIDIA TAO VehicleTypeNet**       | coupe, sedan, SUV, van, large vehicle, truck (**no pickup**) | 88% top-1 on >60K North American images | 18.97 MB ONNX                     |
| **NVIDIA TAO VehicleMakeNet**       | 20 makes                                                     | 91% top-1                               | 7.07 MB ONNX                      |
| PaddleClas PULC `vehicle_attribute` | 10 colours + 9 types, **including pickup**                   | mA 90.81 on VeRi (Chinese traffic)      | 7.2 MB                            |
| fast-reid SBS R50-ibn (VeRi)        | vehicle re-ID embedding                                      | VeRi Rank-1 97.0 / mAP 81.9             | `unverified`; the repo is dormant |

Together these replace the catalogue's 1.5 GB ResNet-50 vehicle classifier. Vehicle re-ID answers
"the same car as last night" when the plate is unreadable. The VLM can probably report colour
itself.

## §2 Fine detail (rev 7 candidate)

### Open-vocabulary detection: YOLOE-26 (owner-approved for the slot)

| Model                               | Params                   | LVIS minival AP / APr (zero-shot) | Speed                                                             | Notes                                                                                                                                                                                                                  |
| ----------------------------------- | ------------------------ | --------------------------------- | ----------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **YOLOE-26s**                       | 10.7M                    | 30.8 / 23.9                       | est. 2-6 ms on A5500 TRT; YOLOE-v8-S measured 305.8 FPS on T4 TRT | `set_classes()` bakes the vocabulary into the exported weights, so the text encoder (MobileCLIP2-B) is only needed offline. Only `-seg` checkpoints are published, so a detection-only model must be rebuilt from YAML |
| **YOLOE-26m**                       | 21.3M                    | 35.4 / 31.1                       | est. a few ms                                                     | Best accuracy per millisecond in the survey                                                                                                                                                                            |
| ref: OmDet-Turbo-Tiny               | ~0.1B incl. text encoder | 30.3 / `unverified`               | est. 15-25 ms                                                     | Its "language cache" precomputes text embeddings                                                                                                                                                                       |
| ref: MM-Grounding-DINO-T / LLMDet-T | ~0.2B                    | 41.4 / 34.2 and 44.7 / 37.3       | est. 50-80 ms                                                     | Over both budgets                                                                                                                                                                                                      |
| ref: OWLv2-B/16                     | ~0.2B                    | 43.9 / 40.5                       | well over 50 ms                                                   | 960 px ViT input                                                                                                                                                                                                       |

- **Keep the vocabulary short, and vary it by camera and time of day.** An aerial benchmark found
  that cutting 80 classes to about 3 improved results 15-fold. Examples: `crowbar, bolt cutters,
ladder` at the back fence at night; `package` on the porch by day; `balaclava, ski mask, hood`
  everywhere.
- **Night evidence is only indirect.** The zero-shot thermal results (Thermal-Det) come from LWIR
  cameras, not Foscam near-IR. Measure false positives on our own night footage.

### Weapons

**No published checkpoint deserves trust.**

- The current `Subh775/Threat-Detection-YOLOv8n` reports identical 83.0% recall on every class, on
  an unnamed Roboflow dataset, and calls itself "research and educational purposes".
- Its RF-DETR sibling's test table is a verbatim copy of the YOLOv8n card's.
- On real CCTV, handguns are 16-47 px. The best AP50 on real robbery footage is 57.4 (CCTV-Gun),
  and it falls to 3.7 across datasets.

**Design:**

- Weapon hits reach the VLM as **hints, never triggers**. They come from YOLOE-26 with a high
  threshold, counted only when the box overlaps a person's hand or arm.
- Measure false positives on our night footage and on **US Mock Attack** (real CCTV from 3 cameras,
  with smartphones as distractors).
- **Stop-gap:** `Subh775/Firearm_Detection_Yolov8n` (mAP50 0.890; it reports 324 background false
  positives on validation; gun class only).
- **Fine-tune path:** RF-DETR-N (30.5M params; COCO AP 48.4; 2.3 ms on T4 TRT) or YOLOE, trained
  on WeaponDetection_Grouped (7,615 images) plus hard negatives (phones, tools, umbrellas).

### Person attributes and "face covered"

| Model                                         | Outputs                                                                             | Evidence                                          | Size         |
| --------------------------------------------- | ----------------------------------------------------------------------------------- | ------------------------------------------------- | ------------ |
| PaddleClas PULC `person_attribute` (PP-LCNet) | 26 PA-100K attributes: bags, hat, glasses, holding an object, clothing, orientation | PA-100K mA 78.59; 2.01 ms on a Xeon CPU           | 7.1 MB       |
| PP-Human attribute (PP-HGNet_small)           | same 26 attributes                                                                  | mA 95.4 on an internal mixed set (not comparable) | `unverified` |

- **Neither outputs mask, hood or gloves.** "Face covered" comes from YOLOE-26 prompts, or from
  SigLIP2 zero-shot on head crops, checked on our own footage.
- The LamKser ConvNeXt-S face-occlusion classifier (0.9887 on its own split) needs a detected face,
  so it doesn't help at night or at distance.

## §3 Time and memory (rev 7 candidates)

### Person re-ID

| Model                              | MSMT17 Rank-1 / mAP                   | Params                    | Notes                                                                                                                                                |
| ---------------------------------- | ------------------------------------- | ------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------- |
| **PersonViT ViT-S/16**             | **89.2 / 74.3**                       | ViT-S (`unverified`)      | LUPerson pretraining; weights ~3 years old; ONNX export not documented                                                                               |
| **CLIP-ReID ViT-B/16**             | 88.7 / 73.4                           | 87.5M (est. ~175 MB FP16) | The most robust across domains in a 2026 comparison of 11 models; ONNX export unproven                                                               |
| SOLIDER-REID Swin-T                | 85.9 / 67.4                           | `unverified`              | LUPerson pretraining                                                                                                                                 |
| fast-reid SBS R50-ibn              | 83.9 / 60.6                           | ~23.5M                    | ONNX and TensorRT export documented                                                                                                                  |
| NVIDIA TAO ReIdentificationNet R50 | Market-1501 94.7 / 93.0 (same domain) | 91.9 MB                   | Encrypted; runs only on NVIDIA runtimes                                                                                                              |
| _incumbent_ OSNet-AIN x1.0         | MSMT17→Market **70.1 / 43.3**         | 2.2M                      | **Mislabeled** in the repo as "MSMT17 73.3%": that figure is the multi-source MS+D+C→Market Rank-1, and its training included the withdrawn DukeMTMC |

- **Do not use a general scene embedder for re-ID.** Zero-shot SigLIP2 measured mAP 2.8-14.2% for
  re-ID in the same 2026 comparison.
- None of these publishes a cross-domain score, so run our own cross-camera test before switching.
- **KPR is flagged regardless of the license ruling.** Its Hippocratic License 3.0 prohibits
  surveillance and law-enforcement use.

### Pose

| Model                                                        | COCO AP                                                 | Params                    | Latency                            | Notes                                                                                                                                 |
| ------------------------------------------------------------ | ------------------------------------------------------- | ------------------------- | ---------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------- |
| **RTMPose-s**, top-down on YOLO26 person crops (rtmlib ONNX) | 71.6                                                    | 5.47M                     | 1.39 ms TRT-FP16 on a GTX 1660 Ti  | Crops are upsampled, which suits small, distant people. RTMPose-t: 68.2 / 3.34M / 1.06 ms                                             |
| RTMPose-m                                                    | 74.6 (75.8 with the AIC+COCO checkpoint)                | 13.59M                    | `unverified`                       | Within about 1 AP of ViTPose-B at a sixth of the size                                                                                 |
| **YOLO26-pose**, one pass per frame                          | mAP<sub>pose</sub>50-95: n 57.2, s 63.0, m 68.8, l 70.4 | 2.9 / 10.4 / 21.5 / 25.9M | 1.8 / 2.7 / 5.0 / 6.5 ms on T4 TRT | Same exporter and toolchain as the YOLO26 gate, with no crop loop. It works on the 640 px full frame, so it is weaker on small people |
| DETRPose-S                                                   | 67.0                                                    | 11.5M                     | 4.99 ms on V100 TRT FP16           | Young repo                                                                                                                            |
| _incumbent_ YOLOv8n-pose                                     | —                                                       | —                         | —                                  | Superseded by YOLO26-pose                                                                                                             |

The top-down AP and the YOLO pose mAP use different protocols, so they are not directly
comparable. **Suggested setup:** YOLO26-pose if we want pose inside the detector pass, and
RTMPose-s top-down for small subjects.

### Skeleton action

**No pretrained model covers the residential behaviours:** trying door handles, peering into
windows, climbing a fence, loitering. NVIDIA PoseClassificationNet only has sitting down, getting
up, sitting, standing, walking and jumping.

- **Start from the PYSKL ST-GCN++ NTU-120 2D checkpoint.** It scores 84.4 on NTU120 XSub with
  joints only, and 86.4 with four streams (89.3 on NTU60 XSub). It has 1.39M params and costs 1.95
  GFLOPs per clip. The 2D checkpoints consume **COCO-17 keypoints**, so RTMPose or YOLO26-pose
  output feeds it directly, with no joint remapping.
- **Relevant NTU classes:**
  - falls: A43 falling, A42 staggering;
  - posture: A80 squat down;
  - violence: A50 punch/slap, A51 kicking, A52 pushing, A106 hit with object, A107 wield knife,
    A108 knock over;
  - movement: A99 run on the spot, A27 jump up, A59 walking towards.
- **Domain gap:** NTU is indoor lab footage with near-frontal Kinect viewpoints and full bodies in
  frame. Expect it to degrade on small outdoor IR people, and fine-tune the head.
- **Fine-tune data:** OmniFall (15k videos, 16 fall-related classes; its synthetic split transfers
  as well as staged footage), AVA v2.2 (crouch/kneel, fall down, run, climb, fight, "open a window or
  car door"), Kinetics-700 ("closing door", and possibly "climbing ladder"), plus **clips the owner
  stages on our own cameras, day and IR**. Only the owner's clips cover peering and door handles.
- **Accuracy ceiling:** ProtoGCN (NTU120 XSub 90.9, but as a 6-model ensemble).
- **Split by input:**
  - stills: posture rules or a tiny MLP on keypoints (crouching, lying down);
  - clips: ST-GCN++;
  - loitering and running: dwell-time and displacement rules from the tracker and re-ID, not a
    classifier.

### Scene novelty ("is this unusual for this camera?")

| Embedder                                   | ImageNet zero-shot | Vision params | Notes                                                                                                                                                      |
| ------------------------------------------ | ------------------ | ------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **SigLIP2-B/16-224** (incumbent, resident) | 78.2               | ~86M          | Adds no new model; precompute the text embeddings                                                                                                          |
| **MobileCLIP2-S2**                         | 77.2               | 35.7M         | Within 1 point at ~40% of the vision params. MobileCLIP2-B: 79.4 at 86.3M. There is no documented ONNX export (it is OpenCLIP-based). Worth a head-to-head |
| PE-Core-S16-384                            | 72.7               | ~20M          | 384 px input                                                                                                                                               |
| DINOv2-S/14                                | ImageNet k-NN 79.0 | 22.1M         | No text tower                                                                                                                                              |
| DINOv3 ViT-S/16                            | ImageNet-ReaL 87.0 | 21M           | Stronger dense features, so the better backbone for optional patch-level localisation                                                                      |

Google publishes no SigLIP2 so150m checkpoint. The so150m weights on HF are timm supervised
backbones with no text tower.

**Recipe:** kNN against a per-camera memory bank of global embeddings.

1. L2-normalize each still's vision embedding.
2. Key the bank by (camera, IR vs day mode taken from colour saturation, 2-hour bin plus its
   neighbours). Store only frames from events that were not escalated, capped at about 3k per key
   over a rolling 30-60 days. An exact index is enough at that size.
3. Score each still as the mean cosine distance to its k=5 nearest neighbours, excluding frames
   from the same upload burst.
4. Convert the score to a percentile against the key's leave-one-out scores.
5. Take the maximum over the event's 1-4 stills.
6. Emit nothing until a key holds at least 200 frames. Reset the bank when the camera moves.
7. Optionally, run the same kNN on YOLO26 person crops to get "person crop novelty" (AI-VAD's
   deep-feature idea), and use DINOv3 patch-kNN to show which region changed.

Output line: `scene novelty: 97th percentile for this camera at night (k=5, n=1840)`.

Related methods: PatchCore and AnomalyDINO work on stills (AnomalyDINO: MVTec one-shot AUROC
96.6). AI-VAD partly does: velocity needs consecutive frames, but its pose and CLIP-kNN parts work
on stills. AnomalyCLIP and VideoPatchCore don't fit.

### Trackers

Trackers only help **within a clip**. Across separate uploads, re-ID does the association.

- **roboflow/trackers** (clean-room SORT, ByteTrack, OC-SORT, BoT-SORT; v2.6.1, 2026-09-25) has no
  re-ID branch.
- **BoxMOT** puts one API over ByteTrack, BoT-SORT, OC-SORT, Deep OC-SORT and StrongSORT, with re-ID
  backends.
- The Ultralytics built-in ByteTrack/BoT-SORT is the zero-glue path if pose moves to YOLO26-pose.
- For fixed cameras, turn off BoT-SORT's camera-motion compensation.
- MOT17 HOTA ranges from 63.1 (ByteTrack) to 65.0 (BoT-SORT with re-ID).

## Rev 7 shortlist (proposal, not yet approved)

The order follows expected verdict impact per unit of effort:

1. **Re-ID swap.** The vlm path's re-ID may be a zero-shot CLIP embedder, whose matches are close
   to noise. Candidates: PersonViT ViT-S/16 or CLIP-ReID.
2. **YOLOE-26 open-vocabulary slot.** It covers fine detail, weapon hints (gated on a hand or arm)
   and face covered, in one resident model of a few ms.
3. **Scene-novelty baseline.** It reuses the resident SigLIP2 tower, so it costs almost no VRAM.
   The storage rule is in F12: PostgreSQL, adding pgvector past about 100k vectors.
4. **Vehicle type, make and re-ID.** TAO VehicleTypeNet and VehicleMakeNet (about 26 MB), plus a
   vehicle re-ID embedding.
5. **Pose and action.** The most effort. Start from the NTU-120 ST-GCN++ checkpoint; the
   residential classes need OmniFall, AVA and owner-staged clips.

Each item enters the build the same way Task 3b's specialists did: a synthetic verdict-changing
case, an S1/S4 measurement, and a false-positive measurement on the owner's night footage.

## Traps and corrections found

- **A model's license follows its framework, text encoder and training data, not just its card.**
  For example, anything trained with Ultralytics is AGPL whatever the card says. That no longer
  gates selection (F12), but it explains why cards contradict themselves.
- **AuraFace-v1** ships four InsightFace `antelopev2` files alongside its own `glintr100.onnx`.
- **A metric copied between cards:** the Subh775 RF-DETR table duplicates its YOLOv8n table.
- **Repo corrections:**
  - the OSNet-AIN "MSMT17 73.3%" label (see §3);
  - the `fast-alpr` stack is ~10 MB, not 28 MB, and pins the v1 OCR;
  - `buffalo_l`'s "~1.5 GB" is the loader's cost, not the model's (see §1).
- **Use restrictions, still flagged:**
  - KPR (Hippocratic License 3.0);
  - BlazeFace (its card excludes faces beyond 5 m and surveillance or identity use).
- `rapdataset.com` (the RAP attribute dataset) serves a TLS certificate for unrelated gambling
  domains. Don't download from it.
- **A patent to check before this ships as a product:** US8167430B2 (Motorola Solutions, active
  until 2030-11-09) covers time-of-day anomaly detection in video surveillance. Its claim 1 uses
  adaptive resonance theory networks on motion data, which differs materially from kNN over
  embeddings. This is not a license question, so F12 doesn't cover it.
- The in-house `stgcn_action` (~20 MB) is probably NTU-trained. That's fine under F12, but it
  means the model already shares NTU's indoor-lab domain gap.

## Primary sources (selection)

InsightFace model zoo · fal/AuraFace-v1 · opencv_zoo (YuNet, SFace, eDifFIQA) ·
minchul/cvlface_adaface_ir18_webface4m · Idiap/EdgeFace · ankandrew/fast-alpr, fast-plate-ocr,
open-image-models · NGC TAO VehicleTypeNet, VehicleMakeNet, ReIdentificationNet · PaddleClas PULC ·
docs.ultralytics.com/models/yoloe · omlab/omdet-turbo-swin-tiny-hf · Subh775 threat and firearm
cards · srikarym/CCTV-Gun · roboflow/rf-detr · hustvl/PersonViT · Syliz517/CLIP-ReID ·
KaiyangZhou/deep-person-reid · JDAI-CV/fast-reid · tinyvision/SOLIDER-REID ·
open-mmlab/mmpose (RTMPose, RTMO) · Tau-J/rtmlib · docs.ultralytics.com/tasks/pose ·
SebastianJanampa/DETRPose · kennymckormick/pyskl · firework8/ProtoGCN · NGC PoseClassificationNet ·
apple/MobileCLIP2 · facebook/PE-Core · facebook/dinov2-small · facebook/dinov3-vits16 ·
dammsi/AnomalyDINO · amazon-science/patchcore-inspection · roboflow/trackers ·
mikel-brostrom/boxmot. The full URL for every candidate is in the host session's research reports
(2026-09-25).
