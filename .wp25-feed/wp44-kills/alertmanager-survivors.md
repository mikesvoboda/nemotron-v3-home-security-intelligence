# routes/alertmanager.py surviving-mutant record (STRICT census 2026-09-19, wave-66)

43 mutants; 9 killed pre-WP4.4 (score 20.9%). Wave-66 batch (4 tests in
`TestWp44AlertmanagerBroadcastGaps`, test_alertmanager.py): **27 newly killed**.
STRICT census: all 34 open keys re-probed with the new tests synced into mutants/,
kill = rc in (1,3), -n 0, 0 no-verdicts.

Coverage map: payload schema + 9 value pins (cluster D key-clobbers + cluster C
dict→None + F create_event arg mutants), resolved `ends_at` ISO string (cluster E),
WebSocketEventType envelope, `publish("events", event)` two-positional contract (cluster G).

Module total: (9+27)/43 = **36 = 83.7%** (was 20.9% pre-WP4.4).
7 survivors remain — 6 debug/success/error log-text mutants (dossier cluster A,
EQUIVALENT: message text only, control flow identical) + 1 warning-handler log-text
(cluster B, LOW-VALUE). They ARE the surviving-mutant record.

```
backend.api.routes.alertmanager.x__broadcast_prometheus_alert__mutmut_2
backend.api.routes.alertmanager.x__broadcast_prometheus_alert__mutmut_3
backend.api.routes.alertmanager.x__broadcast_prometheus_alert__mutmut_38
backend.api.routes.alertmanager.x__broadcast_prometheus_alert__mutmut_4
backend.api.routes.alertmanager.x__broadcast_prometheus_alert__mutmut_40
backend.api.routes.alertmanager.x__broadcast_prometheus_alert__mutmut_42
backend.api.routes.alertmanager.x__broadcast_prometheus_alert__mutmut_5
```
