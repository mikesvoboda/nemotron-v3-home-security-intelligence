# Banked artifacts: the 2026-10-04 `vlm_assess` prompt research and probes

The distilled, frozen record is
[`docs/vss-integration/22-prompt-research-and-probes-2026-10-04.md`](../../vss-integration/22-prompt-research-and-probes-2026-10-04.md);
this directory holds the raw material it cites, banked in-repo per doc 22 section 7 before
the session scratchpad was lost. Nothing here is a current-state claim.

| file                                                    | what it is                                                                                                                                                                        |
| ------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `calibration-forecast-report.md`                        | researcher track 1, full report (few-shot, calibration, anchoring, field order, multi-frame) — Q1-Q4 + recommendations, with arXiv IDs and read/verified provenance tags per item |
| `qwen-gemma-portability-report.md`                      | researcher track 2, full report (what prompt-format knowledge is portable between Qwen3-VL and Gemma, family knobs, Gemma 4 facts, box-format traps)                              |
| `probe3-arm-ladder.md`                                  | the probe-3 arm ladder spec (was `prompt-draft-1.md`): the five Tier-A arm texts — two INDEPENDENT questions + band names / + taxonomy / + tiebreakers / + point examples         |
| `probe3.py` / `results3.jsonl`                          | probe-3 harness (5 arms x 37 events, transport shim over the shipped client) and its 185 result rows                                                                              |
| `probe4.py` / `probe4_redo.py` / `results4-final.jsonl` | probe-4 harness (`nc`, `nc_rp1`, `nc_2turn`), the solo re-run of the 11 concurrency-perturbed events, and the corrected 90-row merge the doc 22 table reads                       |

The probe scripts hardcode scratchpad and GPU-out paths and run against a `PROBE_URL` llama
server with the transport shim; they are records of what was executed, not supported entry
points. The captured logprobs (multi-MB per arm) stayed out of the repo; the EV-over-logprobs
method and result are described in doc 22 section 2.
