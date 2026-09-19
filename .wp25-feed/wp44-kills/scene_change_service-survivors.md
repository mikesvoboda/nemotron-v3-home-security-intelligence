# WP4.4 kill record — backend/services/scene_change_service.py

**Baseline:** 88 mutants, 49 killed by the pre-existing unit suite, 39 survivors.
**Batch:** `TestWp44SceneChangeGaps` (5 tests) appended to
`backend/tests/unit/services/test_scene_change_service.py` (no new imports needed).
**Strict census (drafted tests only, 39/39 keys, 0 no-verdicts): 37 killed / 39 probed.**
Module total after batch: **86/88 = 97.7% killed**.

## Killed (37 — the dossier's TEST-GAP set, C2–C14, plus one EQUIVALENT overturned)

Dossier ruling overturned: C1's `create 6,12,13` (dossier predicted unkillable —
"SQLAlchemy applies the column default") actually died. The constructor is patched
with a kwargs-recording fake, so `detected_at=None` / omitted and `acknowledged`
omitted are directly observable at the call site, before any default fires. Only
C1's `create 14` (acknowledged_at omitted; nullable, None default) held.

| Cluster | Keys | Killing test |
|---|---|---|
| C8 get_scene_change stmt clobber/flip | `get_scene_change 2,3,4,5` | test_get_scene_change_builds_id_equality_query |
| C9+C10 unack query clobber + predicate flips | `get_unacknowledged_for_camera 2,3,4,5,6,7,8,9,10` | test_get_unacknowledged_query_filters_orders_limits |
| C2+C3+C4 create field-loss / kwarg-omit / acknowledged=True | `create_scene_change 2,3,4,5,6,7,8,9,10,11,12,13,16` | test_create_scene_change_persists_all_fields |
| C6 add/refresh(None) | `create_scene_change 17,18` | same (add + refresh arg identity) |
| C5 naive detected_at | `create_scene_change 15` | test_create_scene_change_detected_at_is_utc_aware |
| C7 WS payload key rename | `create_scene_change 36,37` | same (payload["detected_at"] isoformat) |
| C11+C12 wrong-id lookup, naive ack ts, refresh(None) | `acknowledge_scene_change 2,7,8` | test_acknowledge_scene_change_payload_refresh_and_tz |
| C13+C14 payload key rename, guard `and False` | `acknowledge_scene_change 22,23,24` | same (payload["acknowledged_at"] isoformat) |

## Remaining survivors (2 — both EQUIVALENT)

- C1 `create_scene_change__14` — `acknowledged_at=None` omitted; the SQLAlchemy
  column default reproduces None for omitted == explicit None == original.
- C15 `acknowledge_scene_change__25` — guard `if acknowledged_at` → `or True`; the
  field is always truthy when the broadcast fires (just set to now(UTC)), so both
  branches take the isoformat path on every reachable input.

**Module closed: 86 killed + 2 classified = 88 = mutants_total.**

**Census note:** first census (v1) was 36/39 — `create_18` (`session.refresh(None)`)
survived because the batch asserted `refresh.called` but not the argument identity
(dossier C6 covers both halves; the draft covered only `add`). Added
`refresh.call_args[0][0] is captured["__instance__"]`, archived v1 to
`/tmp/wp25/wp44-kills/pre-screfresh/`, re-censused → 37/39.
