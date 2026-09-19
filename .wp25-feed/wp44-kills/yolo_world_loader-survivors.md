# services/yolo_world_loader.py surviving-mutant record (STRICT census 2026-09-19, wave-67)

135 mutants; 108 killed pre-WP4.4 (score 80.0%). Wave-67 batch (4 tests in
test_yolo_world_loader.py): **7 newly killed**. STRICT census: all 27 open keys
re-probed with synced tests, kill = rc in (1,3), -n 0, 0 no-verdicts.

Coverage map: CPU-guard RuntimeError exact message (A), boxes-None continue-vs-
break with a real names dict on the boxes=None head (E), asyncio.wait_for
timeout arg == 15.0 spy + TimeoutError arm returns [] (F).

Module total: (108+7)/135 = **115 = 85.2%** (was 80.0% pre-WP4.4).
20 survivors remain — dossier-predicted exactly: B pure log-message text
(12, EQUIVALENT), C exc_info/extra kwargs on the failure log (7, LOW-VALUE),
D XX-wrapped ImportError suffix under a prefix match (1, LOW-VALUE).
They ARE the surviving-mutant record.

```
backend.services.yolo_world_loader.x_detect_with_prompts__mutmut_71
backend.services.yolo_world_loader.x_load_yolo_world_model__mutmut_11
backend.services.yolo_world_loader.x_load_yolo_world_model__mutmut_16
backend.services.yolo_world_loader.x_load_yolo_world_model__mutmut_17
backend.services.yolo_world_loader.x_load_yolo_world_model__mutmut_18
backend.services.yolo_world_loader.x_load_yolo_world_model__mutmut_19
backend.services.yolo_world_loader.x_load_yolo_world_model__mutmut_20
backend.services.yolo_world_loader.x_load_yolo_world_model__mutmut_22
backend.services.yolo_world_loader.x_load_yolo_world_model__mutmut_25
backend.services.yolo_world_loader.x_load_yolo_world_model__mutmut_26
backend.services.yolo_world_loader.x_load_yolo_world_model__mutmut_27
backend.services.yolo_world_loader.x_load_yolo_world_model__mutmut_29
backend.services.yolo_world_loader.x_load_yolo_world_model__mutmut_30
backend.services.yolo_world_loader.x_load_yolo_world_model__mutmut_31
backend.services.yolo_world_loader.x_load_yolo_world_model__mutmut_32
backend.services.yolo_world_loader.x_load_yolo_world_model__mutmut_33
backend.services.yolo_world_loader.x_load_yolo_world_model__mutmut_34
backend.services.yolo_world_loader.x_load_yolo_world_model__mutmut_35
backend.services.yolo_world_loader.x_load_yolo_world_model__mutmut_36
backend.services.yolo_world_loader.x_load_yolo_world_model__mutmut_6
```
