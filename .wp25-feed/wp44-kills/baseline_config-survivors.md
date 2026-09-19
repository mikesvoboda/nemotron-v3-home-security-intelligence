# services/baseline_config.py surviving-mutant record (STRICT census 2026-09-19, wave-66)

110 mutants; 77 killed pre-WP4.4 (score 70.0%). Wave-66 batch (~10 tests in
`TestWp44BaselineConfigGaps`, test_baseline_config.py): **22 newly killed**.
STRICT census: all 33 open keys re-probed with synced tests, kill = rc in (1,3),
-n 0, 0 no-verdicts.

Coverage map: override-gate behavior (C1: existing-override dict with flag
False/absent → globals returned), partial-override global fallback (C2), boundary
values 0.5/1 accepted WITH override_global_config=True (C3), exact `match=`
messages (C9), delete-statement WHERE contracts (C4 `==`→`!=` flip) and
`rowcount or 0` fallback with [0, None] parametrization (C5; -1 is truthy —
excluded as the EQUIVALENT leg), `delete(...)→None/where(None)` argument-type
pins (C6/C7).

Module total: (77+22)/110 = **99 = 90.0%** (was 70.0% pre-WP4.4).
11 survivors remain — ALL dossier cluster C8: set/reset log-message text +
f-string interpolation dict-key clobbers inside `logger.info(...)`
(EQUIVALENT: message text only; no test or consumer inspects log records).
They ARE the surviving-mutant record.

```
backend.services.baseline_config.xǁBaselineConfigServiceǁreset_camera_baseline__mutmut_17
backend.services.baseline_config.xǁBaselineConfigServiceǁset_camera_config__mutmut_30
backend.services.baseline_config.xǁBaselineConfigServiceǁset_camera_config__mutmut_31
backend.services.baseline_config.xǁBaselineConfigServiceǁset_camera_config__mutmut_32
backend.services.baseline_config.xǁBaselineConfigServiceǁset_camera_config__mutmut_33
backend.services.baseline_config.xǁBaselineConfigServiceǁset_camera_config__mutmut_34
backend.services.baseline_config.xǁBaselineConfigServiceǁset_camera_config__mutmut_35
backend.services.baseline_config.xǁBaselineConfigServiceǁset_camera_config__mutmut_36
backend.services.baseline_config.xǁBaselineConfigServiceǁset_camera_config__mutmut_37
backend.services.baseline_config.xǁBaselineConfigServiceǁset_camera_config__mutmut_38
backend.services.baseline_config.xǁBaselineConfigServiceǁset_camera_config__mutmut_39
```
