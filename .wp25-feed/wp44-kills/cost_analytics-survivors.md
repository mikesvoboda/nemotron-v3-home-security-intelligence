# api/routes/cost_analytics.py surviving-mutant record (STRICT census 2026-09-19, wave-67)

110 mutants; 84 killed pre-WP4.4 (score 76.4%). Wave-67 batch (6 tests in
TestCostHistoryFieldSemantics + helpers in test_cost_analytics.py): **25 newly
killed**. STRICT census: all 26 open keys re-probed with synced tests, kill =
rc in (1,3), -n 0, 0 no-verdicts.

Coverage map: per-day usage -> every DailyCostEntry cost field + call-date
identity (C1, kills the `usage=None`/`and False` family), per-day detection
query window as a real tz-bounded count(detections.id) statement + verbatim
scalar carry (C2, 14 keys — the pydantic mock-scalar coercion had made query
corruption schema-invisible), exact per-day count on no-usage days (kills the
`or 1` phantom), model-breakdown placeholder constants (C3), abs=1e-9 token
divisor (C4), and the 90/91-day flip point (C5).

Module total: (84+25)/110 = **109 = 99.1%** (was 76.4% pre-WP4.4).
1 survivor remains — dossier-predicted exactly: C6 400-detail XX-wrap under a
substring match (EQUIVALENT; killing it would couple tests to the full
message, against the file's stable-prefix convention).
It IS the surviving-mutant record.

```
backend.api.routes.cost_analytics.x__validate_date_range__mutmut_6
```
