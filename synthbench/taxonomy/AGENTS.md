# synthbench/taxonomy - Agent Guide

## Purpose

The committed taxonomy (spec §1.2) and the seeded sampler that turns it into fact-only Tier B
specs.

## Files

| File             | What                                                                                                                                                   |
| ---------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `tier_b_v0.yaml` | zones, lighting (hours), weather, artifacts, cameras, properties, clothing, per-class **term lists**, 32 scenarios with labels, risk bands and weights |
| `model.py`       | pydantic models, coherence rules, `compatible_cells` and the lighting/weather/artifact options, `load_taxonomy`, `taxonomy_sha256`                     |
| `sampler.py`     | `allocate` (Balinski-Young quota method), `sample_specs`, `time_in_hours`, `in_hours`, `default_seed`                                                  |

## Rules

- **Editing the YAML changes its sha256.** `python -m synthbench sample` then exits 2 for a
  corpus version built from the old file: a changed taxonomy needs a new corpus version.
- Quote times in the YAML: YAML 1.1 reads `08:00` as a number.
- Terms are lowercase. P3's `synthbench check` requires a prompt to use one term from each
  subject's and prop's class list.
- The draw order in `sampler._one` is part of the contract. Reordering it changes every spec a
  seed produces.
- `--only` batches count toward the corpus's scenario totals. The ±1 share bound holds across
  batches drawn without `--only`; a scenario that `--only` over-represents cannot be taken back
  in an append-only corpus.
- The scenario list, labels, risk bands and weights are the owner's to set. The v0 values are a
  draft (plan ruling P2-R4).
