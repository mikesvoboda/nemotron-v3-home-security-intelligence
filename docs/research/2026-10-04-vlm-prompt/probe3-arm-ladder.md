# vlm_assess prompt draft 1 (Tier-A: prompt-string only — same client, same grammar, same output contract)

> [A] agent-authored draft, 2026-10-04, informed by the sweep (S3 39%, A-group 0/64), probe 1
> (4 frames, no rubric: 0/17, scores 0-10 under confirmed verdicts) and probe 2 partials (rubric
> moves scores to 20-25; frame-context note alone: no movement; rubric verbosity caused one
> max_tokens truncation on call 6). Placeholders render exactly as `_render_prompt` does today.
> Sections marked {BRACKETS} are per-event data lines, mechanically generated, not model prose.

## The draft text

```text
You are the risk assessor for a home-security camera. A detector has already flagged a scene; your
job is the second decision on it. You answer two INDEPENDENT questions.

VERDICT - is each detected candidate real and correctly identified in the image? This is a question
about the detector, not about danger.

RISK SCORE - what would this scene mean to the household if it is real? Judge what the scene IMPLIES
about intent, not only whether something is visibly harmful right now. Verdict and risk do not
explain each other: a confirmed candidate can be low risk, and a high-risk scene can contain an
ordinary-looking object.

Score what the camera's owner would pay to know about:

0-29    routine: residents arriving, planned work or deliveries, ordinary yard or neighborhood
        activity for the time of day.
30-59   medium: a person at the property with no visible purpose - lingering near windows or doors,
        crossing toward the house and repeating it, examining vehicles. No weapon is needed for this
        band; repetition and aimless pattern ARE the evidence.
60-84   high: conduct that typically precedes an intrusion or threatens a person - reaching for
        entry points, testing locks, concealment combined with approach, or an obvious weapon in
        hand.
85+     emergency: an attack, break-in or fire in progress.

An uncertain scene at night near entry points belongs in medium, not in routine. An uncertain scene
that is plainly a resident, a worker, or a planned visit belongs in routine, not in medium.

TASK: {task_line}

CAMERA: {camera_id} at {time_with_daypart_note}.
ZONES: {zones}. {zone_crossing_note}
HOUSEHOLD: {one_sentence_summary}
SPECIALISTS: {face/plate/re-ID lines if any; otherwise "No face, plate or identity evidence is
available for this event. Judge from what the frames show."}
DETECTOR CANDIDATES: {rows JSON}
{box guidance sentences - carried over verbatim from the shipped prompt; they exist because of a
measured failure (event 617) and stay}
{frame note, only when 2+ images: "The attached images are consecutive moments of one clip, oldest
first, about {dt} apart. Persistence, repetition and change across them are evidence."}
If more than one candidate is attached, score the whole scene by its most threatening component -
never an average.

ANSWER with the verdict JSON object only. Fill every field, and keep the reply short: summary one
sentence; description one sentence; reasoning at most two sentences; at most three criteria, their
evidence each one short sentence naming what in the image supports it; provenance copies the served
model's own identity. Do not let the JSON run long.
```

## Design notes — what each piece buys, and its cost

| piece                                                   | evidence basis                                                                                        | risk it carries                                                                                                                    |
| ------------------------------------------------------- | ----------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------- |
| Two-independent-questions framing                       | probe 1: every call `confirmed` + score 0 — verification confidence leaking into risk                 | may flip some verdicts if the model reads "independent" as permission to reject; probe 2 showed 1 rejected flip under rubric alone |
| "what the owner would pay to know about" + stakes bands | score had no consequences attached; AUROC 0.70, scores polarized low                                  | the bands mirror corpus floors — on tierb-v0 this is near label-leakage; a holdout must decide adoption                            |
| Point examples (the two "belongs in" lines)             | early probe 2: rubric scores sat BELOW their stated ranges (20-25 vs 30-59) — ranges read as ceilings | examples pull benign items up; the two "routine" anchors are there to counter that; 20 benign clips measure it                     |
| Night/entry-point default-up rule                       | A-group is exactly this; the shipped prompt offers no tiebreaker                                      | this is the single highest-leverage AND highest-S2-risk sentence; it must earn its place per-arm                                   |
| Empty-specialist fallback                               | shipped line `...not yours to invent: {}` signals "no evidence, don't form any"                       | tiny; no downside expected                                                                                                         |
| Max-not-average scene rule                              | prompt is silent on multi-candidate risk; selector can attach 4                                       | untested; could raise S2 on multi-object benign scenes (delivery + dog + truck)                                                    |
| Output discipline ("keep the reply short...")           | probe 2 call 6: rubric verbosity overflowed 1024 tokens; production would silently drop the verdict   | this is NEW machinery forced on us by measurement — no draft ships without it                                                      |
| Frame note (only for bursts)                            | probe 2: ordering note ALONE changed nothing (burst_ctx 0.0)                                          | kept because it may synergize with the rubric; the `both` arm tests that, not this belief                                          |

## Honest limits of Tier A text

- **The grammar fixes field order.** `risk_score` is the second field emitted — before `criteria`,
  `reasoning`, `description`. The model commits to the number before it generates any justification,
  and no sentence in the prompt can change that; "think first" only moves the prefill, not the
  commitment point. Field reordering is Tier C (schema + grammar + client + analyzer + tests together).
- **The point examples are corpus-shaped.** They must not be finalized on tierb-v0.
- **Token budget is now a design constraint**, not a nicety: prompt tokens (rubric ~220) + reply
  budget share one 16,384 slot and the reply has a hard 1024 cap. The draft keeps the rubric under
  ~230 words for that reason.

## Next arms when the GPU is free (same shim as probe 2)

- `A_full` — this draft as written.
- `A_lite` — rubric without the point examples (controls the S2 risk of examples).
- `A_decouple` — two-questions framing + stakes, no behavior taxonomy (isolates whether decoupling
  alone moves scores, since probe 1 shows the model CAN see everything already).
- Baselines: probe 1 src/burst (shipped prompt) already on record; probe 2's three arms resume.
- Scoring: incident hits vs floors AND benign FA vs 30 on the same items; truncations counted as
  degraded, never silently dropped. Then the two best arms go through the real replay on all 450
  stills — that's the only gate that touches S2/S3 honestly.
