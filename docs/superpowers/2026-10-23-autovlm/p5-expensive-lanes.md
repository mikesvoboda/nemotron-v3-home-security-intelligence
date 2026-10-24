# P5: The expensive lanes

> **Task level. Expand before execution:** when P4 has merged, run superpowers:writing-plans on this file against the then-current tree, one task at a time where a task is large. Task 3 is gated on the system-1 research. Index: [`README.md`](README.md).

**Goal:** The search can explore the C3 and C4 ideas of the catalogue: trained adapters, system-1 decision models, specialist and tracking plugins in fenced containers, and automated tier confirmation.

**Spec:** design [`01`](../../auto-vlm-research/01-architecture.md) §3.11; [`03`](../../auto-vlm-research/03-idea-catalogue.md) §3–8; [`04`](../../auto-vlm-research/04-system-1-research.md).

**Prerequisites:** P4 merged. Each task names its own gate.

---

### Task 1: Trainer lane and model registry

**Files:** create `autovlm/registry.py`, `autovlm/trainer/__init__.py`, `autovlm/trainer/queue.py`; test `backend/tests/unit/autovlm/test_registry.py`.

**Interfaces:** `Registry(root)` with `register(path, kind, provenance) -> Artifact(sha256, kind, provenance)` and `resolve(sha256) -> Path`; provenance records the training data's split and epoch, the base model's sha256, the code commit and the hyperparameters. Training jobs reuse P2's queue with job type `train`; they read only train-split data and public datasets.

**Tests:** registration is content-addressed and idempotent; a provenance naming select or holdout data is refused; a recipe that names an unregistered sha256 fails at submission.

---

### Task 2: QLoRA adapters

**Gate:** the corpus has grown enough that a fresh scenario batch exists which no training job has seen (P4 Task 4).

**Files:** create `autovlm/trainer/lora.py`, a training container definition under `autovlm/trainer/container/`; modify `autovlm/recipe.py` (`adapter: <sha256> | null`).

**Behaviour:** build a supervised dataset from train-split items (the VLM's input as the product sends it, the label's verdict and band as the target) plus public datasets; train a QLoRA adapter on the base model inside an `agent-gpu` container; merge; convert to GGUF and quantize to the recipe's quant with the pinned llama.cpp; register the result (Task 1).

**Tests:** the dataset builder never reads select or holdout ids; the conversion step's output loads in the pinned build (a `gpu`-marked test).

**Acceptance:** an adapted model is compared with its base under OD-26 on select, and then on a fresh scenario batch no training job has seen; a gain that holds only on select is recorded as a finding of overfitting, not as a win.

---

### Task 3: System-1 decision models

**Gate:** the research in design `04` has delivered its report, and the owner has made a go decision for at least one role.

**Files:** create `autovlm/decision/` with one module per approved role; modify `autovlm/recipe.py` (`decision.head: vlm-score | fusion:<sha256> | …`).

**Behaviour:** a fusion head is a registered artifact (Task 1) trained on cached train-split signals; it scores in C1 time from the cache; it is cross-validated by scenario on train, and select is queried once per epoch per model family (P4 Task 5's budget).

**Tests:** the head's features are only those the research's feature map marked available and leak-checked; scenario-grouped cross-validation never splits a scenario across folds; a head trained on one corpus version refuses another without retraining.

---

### Task 4: Plugins in fenced containers

**Files:** create `autovlm/plugins/__init__.py` (the plugin interfaces), `autovlm/executor/fenced.py`; test `backend/tests/unit/autovlm/test_plugins.py`.

**Interfaces:** `PerceptionPlugin.process(frames: list[bytes]) -> dict[str, Any]`, `StatePlugin.process(per_frame: list[dict]) -> dict[str, Any]`; the executor builds the trial commit's plugin code into an image with `agent-gpu build --context` and runs it in a fenced container (no LAN, no host loopback); agent-written code never runs on the host. Plugin outputs are cached like any stage (P2 Task 1).

**Tests:** a plugin that tries to open a host loopback port or read outside its mount fails inside the fence (a `gpu`-marked integration test); outputs are cached by plugin version.

---

### Task 5: Specialist plugins

**Gate per plugin:** each one may be explored freely; promoting one keeps the existing gate (an owner-approved spec revision, a case where it changes the verdict, a false-alarm check on the owner's night footage). Pose needs the owner's spec revision before it is even built, because the deleted `yolov8n-pose` row stays deleted.

**Files:** one module per specialist under `autovlm/plugins/perception/`: `yoloe26.py` (open vocabulary with a threat-object list), `household.py` (SCRFD and recognizer against the corpus's household identities; needs the synthbench identity feature of design `03` §2), `reid.py` (OSNet-AIN, needs multi-camera clips), `attributes.py` (person attributes).

**Behaviour:** each plugin's output reaches the VLM through the context's `specialist_outputs` field, as the product carries specialists today, and is also available to system-1 features.

**Tests:** each plugin's output schema; a plugin's absence or failure is represented explicitly, never as an empty success.

---

### Task 6: Tracking and trajectory grammar

**Files:** `autovlm/plugins/state/tracker.py`, `autovlm/plugins/state/grammar.py`.

**Behaviour:** a tracker over a burst sets track ids, dwell, speed and path; the grammar turns tracks and zones into typed facts (delivery, car-door trying, perimeter loop, tailgating); the facts reach the VLM's context (making `zone_crossing` real) and system-1's features.

**Tests:** on synthetic tracks, each grammar rule fires on its pattern and on no other; the tracker is deterministic for a fixed input.

---

### Task 7: The linear probe

**Gate:** P0's S5 passed.

**Files:** `autovlm/decision/probe.py`.

**Behaviour:** extract the VLM's embedding for each train item once (cached), fit a logistic probe cross-validated by scenario, and expose it as a decision head.

**Tests:** the probe's training reads only train-split embeddings; the embedding cache keys on the model, build and input.

---

### Task 8: Automated Brev confirmation

**Files:** `autovlm/brev.py`, `autovlm/commands/brev.py`.

**Behaviour:** automate P4 Task 7's runbook: provision a Brev VM of the tier, copy the bundle over SSH, run the measurement, record it with `front confirm`, and wipe and delete the VM, which the owner's data ruling for Brev requires.

**Tests (with a fake provider):** the VM is deleted on success, on failure and on interruption; a measurement without a wipe confirmation is not recorded.

---

### Task 9: Corpus features in synthbench

**Planned and merged under synthbench's own process** (its design docs, its plans under `docs/superpowers/`, and the synthbench generation agent), because the change belongs to synthbench. This task states what autovlm needs from it.

**Requirements:**

- **Consistent household identities:** a small, fixed household (residents, a regular visitor, their vehicles) rendered recognisably across many scenes, with identity ids in the labels, never in the stills. Task 5's household match and re-ID need it, and so does the `resident_arrival` false-alarm class (design `03` §2).
- **Multi-camera clips of one event:** the same event seen from two or more cameras with aligned timestamps, for re-ID across cameras and for loitering and casing.
- **Benign hard negatives at volume:** enough benign scenarios that a holdout can certify a 5% S2 bar (design `02` §2).

**Acceptance:** a batch with these features exports through `synthbench export vss` and blinds through P1's `blind` with the identity ids landing only in the labels store.
