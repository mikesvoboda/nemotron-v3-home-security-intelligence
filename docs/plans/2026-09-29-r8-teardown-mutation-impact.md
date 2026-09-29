# R8 nemotron teardown x mutation bank — measured impact + shield list

**2026-09-29.** Another agent is tearing down the legacy AI pipeline on
`origin/chore/r8-s2-nemotron-teardown` (S1 hard-raise `734f5e40`, S2a hoist
`0ba90d5f`, S2b delete `602379e2`, ledger row `81a92a05`; scope doc
`docs/plans/2026-09-28-r8-legacy-retirement-scope.md`, slices S3–S5 still
ahead: one ai_contract provider per slice, table retirement, frontend panels).
This doc is the MEASURED overlap with the mutation bank so no campaign is
authored into code that is about to be `rm`'d. Numbers read from
`/home/agent/runs/score-b30-final.txt` x `git diff --numstat
origin/main...origin/chore/r8-s2-nemotron-teardown -- backend/services
backend/api/routes` (this session).

## Headline: the merge is a −4.44-point denominator event

- **33 bank rows are deleted outright: 17,966 keys / 14,295 kt / 3,671
  survivors = 15.4% of the denominator.** (4 of the 33 files carry 0 bank
  keys — the `nemotron_*` trio + `__init__.py` — the `do_not_mutate`
  nemotron exclusion already shielded them.)
- Deleted rows' mean score **79.6% > bank mean 68.9%**, so removal LOWERS the
  badge. Priced post-merge bank (full deletes exact; heavy cuts pro-rated by
  surviving-line ratio, disclosed estimate): **~44,500 / ~69,000 ≈ 64.5%**.
  M6 68.9482506662082% is unreachable from 44,483 by anything short of
  ~3,070 kills at the new denominator — the first ~5 ladder campaigns.
- `prompts.py` (campaign #4's subject, 96.0%, closed THIS morning) loses
  **4,052 of 4,547 lines = 89% of the file**: ~3,250 kt of M6's numerator
  rides out with it. Its batch-era battery `test_prompts_batch8.py` is
  deleted by R8 itself; more batteries will die with their modules. This is
  NOT wasted in the ledger sense — the kills are published history — but no
  NEW prompts work may be authored.
- Big survivor-losses to abandon immediately (were ladder rungs #5–#16 at M6):
  `enrichment_pipeline` 420 surv / 5,933 kt, `vision_extractor` 392,
  `vitpose_loader` 317, `florence_extractor` 151, `pose_analysis_service`
  155, `vehicle_damage_loader` 237, + 13 loaders (<200 each). Full DEAD list
  below.

## Shield list — DO NOT build batteries for these (R8 deletes them)

33 rows leaving, with their bank weight (keys / kt / survivors):

```
services/enrichment_pipeline.py      6353  5933   420   (was ladder #6)
services/enrichment_client.py        2684  2512   172
services/vision_extractor.py         1446  1054   392   (was ladder #5)
services/stgcn_loader.py              749   621   128
services/depth_anything_loader.py     595   428   167
services/florence_extractor.py        499   348   151
services/pose_analysis_service.py     465   310   155
services/vitpose_loader.py            624   307   317   (was ladder #12)
services/gender_classifier_loader.py  368   258   110
services/age_classifier_loader.py     353   247   106
services/zero_dce_loader.py           302   247    55
services/threat_detection_loader.py   343   215   128
services/segformer_loader.py          262   197    65
services/vehicle_damage_loader.py     430   193   237
services/package_tracking_service.py  313   188   125
services/vehicle_classifier_loader.py 327   157   170
services/weather_loader.py            279   127   152
services/smoke_fire_loader.py         285   119   166
services/yolo_world_loader.py         139   115    24
services/skeleton_action_service.py   128   106    22
services/violence_loader.py           178   103    75
services/prompt_auto_tuner.py         117    95    22
services/fashion_clip_loader.py       175    84    91
services/pet_classifier_loader.py     155    84    71
services/image_quality_loader.py      175    78    97
services/ai_services.py                90    73    17
services/clip_loader.py                48    43     5
services/florence_loader.py            55    38    17
services/analyzer_facade.py            29    15    14
services/__init__.py (0 keys)  services/nemotron_analyzer.py (0)
services/nemotron_latency_optimizer.py (0)  services/nemotron_streaming.py (0)
```

DO-NOT-START-WITH (survives but cut by R8 or pending S3–S5):
`prompts.py` (−89% of lines), `api/routes/system.py` (−247 lines, 351 surv —
R8 cuts only 4.3%, but S3's ai_contract retirement is aimed near it),
`model_zoo.py`, `ai_fallback.py`, `health_ai_services.py`, `quantization.py`,
`summary_generator.py` (48.2%, 199 surv — tempting, verify against S3 scope
before committing a campaign).

SAFE ladder head (zero R8-branch touches, re-measured post-teardown order):
`event_broadcaster` 723, `batch_aggregator` 644 (touched +2/−1 lines only —
check function hashes at merge), `clip_client` 559, `florence_client` 394
(NOT the deleted florence_loader/florence_extractor), `baseline` 368,
`file_watcher` 339, `redis_json` 338, `cleanup_service` 337,
`vlm_specialists` 336, `onvif_service` 312. Post-teardown ladder crossings
(model, 23,363-survivor pool): 70% ≈ #10, 72% ≈ #16, 75% ≈ #25, 80% ≈ #44,
85% ≈ #69 — the ladder length barely changes (the deleted pool was
high-scoring already), the STARTING POINT moves back to ~64.5%.

## Merge-time protocol (when R8 lands on mutation-testing-s3 — traps are mine)

1. **Orphan mutant copies re-arm the strip family.** `copy_src_dir` skips
   existing targets and NOTHING deletes mutant files for deleted sources, so
   `mutants/backend/services/enrichment_pipeline.py` et al. stay importable
   (measured present RIGHT NOW). R8's own guard test
   `test_r8_s2b_nemotron_deletion.py` asserts those modules raise
   `ModuleNotFoundError` -> RED in the mutant home -> `-x` truncates the
   coverage gather -> **mass bank strip** (the fill#2/#3 mechanism, 12th
   member of the family, this time armed by deletion not absence). Sweep-
   prune FIRST: `rm` the mutant `.py` + `.spans` for every DEAD file (and
   their `.meta`, letting the sanctioned repair re-enumerate), then run the
   green precondition scan BEFORE any generation.
2. **Added-file audit** (ladder-doc protocol): R8 adds 4 test files
   (`test_config_pipeline_mode_hard_raise`, `test_constrained_decoding_hoist`,
   `test_no_legacy_pipeline_branches`, `test_r8_s2b_nemotron_deletion`).
   Measured path-reads: `scripts/vlm_probes/enforcement.py` via `parents[4]`
   — satisfied (`scripts/` in also_copy, and R8 edits it so drift is real);
   `REPO_ROOT/backend` scans — satisfied (`backend/` in also_copy);
   relative `Path("scripts/...")` reads cwd-relative — mutmut cwd is the
   mutant home, satisfied. No new also_copy member needed IF (1) is done.
3. **Guard recalibration before the first post-merge run**: era total drops
   ~93k -> ~70k, so the key-floor **78,000 would trip on a healthy bank** and
   restore a stale one. Refresh `guard-restore.tgz` post-merge + set
   key-floor = new era total − 15%; re-price the kill-line against the
   measured re-queue (219 test files + 58 source files + new
   `constrained_decoding.py` first coverage).
4. **Milestone semantics (OWNER DECISION, see L row):** after the merge no
   completed=true score can be STRICTLY > M6 until campaigns regain ~3,070
   kills. Recommended: record the post-merge re-bank as a disclosed
   **baseline-reset row** in `mutation-history.json` (denominator event, like
   the 09-28 disclosures — NOT a campaign milestone), then resume strict->
   from the new baseline. Alternative: publish nothing until the
   `event_broadcaster`, `batch_aggregator`, `clip_client` closes carry the
   score back over 68.95%. Either way every interim number is rowed
   row-by-row with the −17,966-key disclosure.

## Standing rule for future R8 slices

Before starting ANY campaign: `git diff --name-only origin/main...<r8-branch
or its successor> -- backend/services backend/api/routes` and skip anything
the teardown touches-with-deletion or that S3–S5 scope names. The S2b
DEAD_MODULES/DEAD_LOADERS lists inside
`backend/tests/unit/test_r8_s2b_nemotron_deletion.py` ARE the authoritative
death list — read them, they're maintained by the teardown itself.
