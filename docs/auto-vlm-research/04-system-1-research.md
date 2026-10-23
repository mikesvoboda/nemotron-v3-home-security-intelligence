# 04. System-1 decision models: an open research brief

> Design proposal; nothing is built or measured. Paths and numbers cited as evidence are as of `origin/main` `9cb9e60b0` (2026-10-23). Back to the [index](README.md).

**Status: questions, not answers.** The owner judged in the design session (decision D8) that this layer needs research before autovlm commits to a design for it. This brief states what that research must answer and how to judge the answers. When the research is done, its report belongs beside this file and this brief's status changes.

## 1. What "system-1" means here

Borrowing the two-system picture of fast and slow thinking: **system-2** is the VLM's deliberate reading of a scene, slow and expensive and able to describe what it sees. **System-1** is a fast, cheap model over structured signals that the rest of the stack already produces: detector classes and confidences, open-vocabulary hits, person attributes, pose flags, tracks and dwell, zone, time of day, household match, re-ID novelty, and the VLM's own score, verdict and checklist answers. System-1 runs on a CPU in microseconds per item and outputs a calibrated probability.

[`03-idea-catalogue.md`](03-idea-catalogue.md) §8 lists four roles it could play: **fusion** (combine all signals into the final decision), **gate** (skip the VLM on confident benign items), **escalation** (send uncertain items to a larger model or to review), and **rule-based severity** (turn the VLM's typed facts into a band through auditable rules).

## 2. Why it might help, and why it might not

**For:**

- **The VLM's score is polarized.** Of 153 S3 misses, 148 carry a confirmed verdict and 127 are scored 10 or below (doc 20). A threshold on that score cannot recover them; signals the VLM does not see might.
- **Diverse signals fail differently.** Fusing weakly correlated signals is the standard remedy for a confident but narrow classifier, and the sweep showed even VLMs disagree on most items.
- **It is cheap to search.** Fusion trials are C1: they re-score cached outputs in seconds.

**Against:**

- **Its inputs mostly do not exist yet.** Tracks are not wired (no non-test code sets `Detection.track_id` at the stamp), specialists are absent from the replay (ISS-024), and household identities are missing from the corpus. A fusion model over today's signals is a fusion of the detector and the VLM.
- **Labels are few and synthetic.** Hundreds of items in tens of scenarios, with truth declared by the generator, not verified (ISS-007).
- **Gating buys cost, not accuracy, where cost does not bind.** Doc 18 measured a warm median of about 6 s against a 30 s budget and a peak of about 9.4–9.6 GiB against 20.4 GiB on the 24 GB tier.
- **It overfits fast.** A C1 search can query a select set hundreds of times an hour.

## 3. Questions the research must answer

### A. Framing

1. What is the decision unit: a still, a burst, a batch window (90 s by default), a track, or an event?
2. What is the target: a binary incident, a severity band, or a ranking that a per-camera floor then thresholds (OD-29)?
3. How does a system-1 decision coexist with the shipped per-camera floor and the notification bands (ISS-018)?

### B. Features

4. Which signals exist at each GPU tier, and what does each cost to produce?
5. How should the VLM's output enter: its score, its verdict, answers to a checklist of targeted questions, or a hidden-state embedding?
6. How should a missing signal be represented, such as a specialist that is off or failed?
7. **Which features secretly encode the generator?** In synthetic data, time of day, camera placement or lighting may be sampled per scenario, so a model can learn the taxonomy's sampling instead of the scene. How do we audit features for that before training?

### C. Model families

8. Which families give calibrated probabilities from a few hundred clustered examples: logistic regression, gradient-boosted trees, small MLPs, Bayesian networks with owner-set priors, rule learners?
9. Are monotonic constraints worth their cost? An owner can then read the model's behaviour ("more dwell never lowers risk").
10. For temporal signals (tracks, frame sequences), what is the smallest model that helps: hand-built features, an HMM, a small sequence model?

### D. Training data

11. How many labelled items does each family need, given clustering by scenario?
12. Can models trained on synthetic labels transfer to real footage, and how would we know without real footage in the search (decision D2)?
13. Can public datasets help, given their different cameras, scenes and label definitions?
14. Do weak labels from a large VLM teacher help or just copy its errors?

### E. Calibration and abstention

15. Isotonic or Platt calibration with clustered data: which holds up on fresh scenarios?
16. Conformal prediction assumes exchangeable items; scenario clustering breaks that. Do group-conditional or cluster-level variants restore a usable guarantee?
17. Can risk-control methods hold S2 at or under 5% with a stated confidence, instead of hoping a fitted threshold transfers?

### F. Cascades and deferral

18. When does gating or escalation change accuracy, not only cost?
19. What deferral policy minimizes the joint error of system-1 and the VLM (the learning-to-defer framing)?
20. Within each tier's VRAM budget, which escalation targets are even resident?

### G. Overfitting at C1 speed

21. How many fusion trials can one select set absorb before its answers stop meaning anything?
22. Should fusion search be confined to scenario-grouped cross-validation on train, with select queried only once per epoch per family?
23. Does a fixed model family with a small hyperparameter budget beat an open search?

### H. Product fit

24. How does a system-1 decision explain itself in an alert ("unknown person, 4 minutes in the backyard, at a window after dark")?
25. Do rule hits surface on the Alerts page, as OD-7 rules for the threat fast path?
26. How does a per-camera model or calibration drift, and who refits it?

## 4. Areas to survey

These are starting points for the research, not claims about what it will find. The research should cite primary sources.

- Home NVR rule engines: zones, object filters, dwell and loitering rules in open-source and commercial camera systems.
- Video anomaly detection with weak labels, including multiple-instance learning on UCF-Crime.
- Fusing VLM outputs with conventional classifiers, and linear probes on multimodal models' hidden states.
- Learning to defer and selective prediction.
- Conformal prediction and conformal risk control under clustered or grouped data.
- Calibration of tree ensembles and small models on small datasets.
- Cascaded inference for vision systems, and what it costs in accuracy.

## 5. What the research should deliver

1. **A report** that answers §3 A to H with recommendations, citing primary sources and marking each claim as measured, published or argued.
2. **A feature map**: each candidate signal, the tier it needs, its cost, its availability today, and its leakage risk.
3. **A first experiment, preregistered**, small enough to run once the P1 realistic baseline exists. For example: a logistic fusion of the VLM score with five signals, cross-validated by scenario on train, queried on select once, against a success criterion fixed before the run.
4. **A go or no-go for each role** (fusion, gate, escalation, rule-based severity), with the evidence that would change the call.

## 6. Prerequisites

- The **P1 realistic baseline** ([`02-evaluation.md`](02-evaluation.md) §3), so that features and labels match what production sees.
- **Tracking** (catalogue §4), before any temporal feature is meaningful.
- **Household identities in the corpus** (catalogue §2), before face match or re-ID can enter a model.
