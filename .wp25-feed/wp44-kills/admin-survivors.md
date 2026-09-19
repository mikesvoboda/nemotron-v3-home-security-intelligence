# routes/admin.py surviving-mutant record (STRICT census 2026-09-19, wave-66)

102 mutants; 72 killed pre-WP4.4 (score 70.6%). Wave-66 batch (3 tests:
`test_get_sample_cameras_exact_canonical_contract` in test_admin.py;
`test_create_user_assigns_unique_uuid_ids` + `test_admin_access_disabled_message_is_exact`
in test_admin_routes.py): **30/30 newly killed — module fully cleared**.
STRICT census: all 30 open keys, kill = rc in (1,3), -n 0, 0 no-verdicts.
(The first census of this module is quarantined in /tmp/wp25/wp44-kills/pre-wave66-bogus/
— it ran against stale test copies inside mutants/ and structurally could not see
the new tests; see the mutants-tree sync protocol.)

Coverage map: 28 A/B id+name literal mutants (clusters A,B) by the exact-list
contract; `_generate_user_id` str(None) collapse by the UUID/uniqueness test;
`require_admin_access` 403 detail clobber by the byte-exact equality test.

Module total: (72+30)/102 = **102 = 100.0%** (was 70.6% pre-WP4.4).
0 survivors remain — this file is the surviving-mutant record of a cleared module.