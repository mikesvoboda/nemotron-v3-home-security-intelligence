# routes/calibration.py surviving-mutant record (STRICT census 2026-09-19, wave-66)

83 mutants; 45 killed pre-WP4.4 (score 54.2%). Wave-66 batch (3 tests in
`TestWp44CalibrationGaps`, test_calibration.py): **19 newly killed**.
STRICT census: all 38 open keys re-probed with synced tests, kill = rc in (1,3),
-n 0, 0 no-verdicts.

Coverage map: auto-create constructor kwargs (user_id "default", 30/60/85/0.1 —
kills C1's 5 + C2 kwarg-drop + C4 add(None), with refresh supplying ONLY
DB-generated columns so assigned values surface), lookup-statement contract
(`user_calibration.id` select, `user_calibration.user_id = :` predicate,
no NULL/no `!=` — kills C5/C6), PUT no-op-refresh contract asserting mock attrs
AND response JSON 25/55/80/0.15 (kills C7's assignment-target clobbers).
Dossier note vindicated: the C1/C2 real-DB IntegrityError claim was right but
killing needed no real DB once refresh stopped masking the constructor.

Module total: (45+19)/83 = **64 = 77.1%** (was 54.2% pre-WP4.4).
19 survivors remain — dossier-exact: C8 pure log message text (5, EQUIVALENT),
C9 `extra=` payload dropped (4, LOW-VALUE), C10 `extra=` key renames (10,
LOW-VALUE). All log-structure only; no consumer asserts log records.
They ARE the surviving-mutant record.

```
backend.api.routes.calibration.x__apply_calibration_update__mutmut_30
backend.api.routes.calibration.x__apply_calibration_update__mutmut_31
backend.api.routes.calibration.x__apply_calibration_update__mutmut_33
backend.api.routes.calibration.x__apply_calibration_update__mutmut_34
backend.api.routes.calibration.x__apply_calibration_update__mutmut_35
backend.api.routes.calibration.x__apply_calibration_update__mutmut_36
backend.api.routes.calibration.x__apply_calibration_update__mutmut_37
backend.api.routes.calibration.x__apply_calibration_update__mutmut_38
backend.api.routes.calibration.x__apply_calibration_update__mutmut_39
backend.api.routes.calibration.x__apply_calibration_update__mutmut_40
backend.api.routes.calibration.x__apply_calibration_update__mutmut_41
backend.api.routes.calibration.x__apply_calibration_update__mutmut_42
backend.api.routes.calibration.x__apply_calibration_update__mutmut_43
backend.api.routes.calibration.x__apply_calibration_update__mutmut_44
backend.api.routes.calibration.x__get_or_create_calibration__mutmut_21
backend.api.routes.calibration.x__get_or_create_calibration__mutmut_22
backend.api.routes.calibration.x__get_or_create_calibration__mutmut_24
backend.api.routes.calibration.x__get_or_create_calibration__mutmut_25
backend.api.routes.calibration.x__get_or_create_calibration__mutmut_26
```
