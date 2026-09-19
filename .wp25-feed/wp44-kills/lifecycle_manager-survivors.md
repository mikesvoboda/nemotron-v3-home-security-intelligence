# services/lifecycle_manager.py surviving-mutant record (STRICT census 2026-09-19, wave-67)

146 mutants; 117 killed pre-WP4.4 (score 80.1%). Wave-67 batch (13 tests + 1 class in
test_lifecycle_manager.py): **16 newly killed**. STRICT census: all 29 open keys
re-probed with synced tests, kill = rc in (1,3), -n 0, 0 no-verdicts.

Coverage map: backoff cap ABOVE the 300.0 library default (monitoring 600.0 /
infra 60.0 services — the ai fixture's 300.0 default masked C1), should_restart
0-1s band (7500/8500 ms probes), handle_unhealthy freeze_time stamp + failure-
count consequence + caplog threshold pair, registry-writes-target-the-service-
name class (update_status/persist_state/update_container_id arg identities).

Module total: (117+16)/146 = **133 = 91.1%** (was 80.1% pre-WP4.4).
13 survivors remain — dossier-predicted exactly: C9 logger(f"...") -> None
message clobbers (LOW-VALUE, zero caplog consumers in this file).
They ARE the surviving-mutant record.

```
backend.services.lifecycle_manager.xǁLifecycleManagerǁdisable_service__mutmut_16
backend.services.lifecycle_manager.xǁLifecycleManagerǁdisable_service__mutmut_4
backend.services.lifecycle_manager.xǁLifecycleManagerǁenable_service__mutmut_17
backend.services.lifecycle_manager.xǁLifecycleManagerǁenable_service__mutmut_4
backend.services.lifecycle_manager.xǁLifecycleManagerǁhandle_missing__mutmut_9
backend.services.lifecycle_manager.xǁLifecycleManagerǁhandle_stopped__mutmut_2
backend.services.lifecycle_manager.xǁLifecycleManagerǁhandle_stopped__mutmut_7
backend.services.lifecycle_manager.xǁLifecycleManagerǁhandle_unhealthy__mutmut_13
backend.services.lifecycle_manager.xǁLifecycleManagerǁrestart_service__mutmut_16
backend.services.lifecycle_manager.xǁLifecycleManagerǁrestart_service__mutmut_18
backend.services.lifecycle_manager.xǁLifecycleManagerǁrestart_service__mutmut_20
backend.services.lifecycle_manager.xǁLifecycleManagerǁstart_service__mutmut_9
backend.services.lifecycle_manager.xǁLifecycleManagerǁstop_service__mutmut_13
```
