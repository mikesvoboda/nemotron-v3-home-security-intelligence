import json, collections

d = json.load(open('/tmp/wp25/wp44-triage/tms_structured_clusters.json'))
table = open('/tmp/wp25/wp44-triage/tms_table.md').read()
tests = open('/tmp/wp25/wp44-triage/tms_tests.py').read()

counts = {c['pattern']: c['count'] for c in d}
cls = {c['pattern']: c['classification'] for c in d}

# kill map: recompute per-test totals from the spec's KILLS dict so numbers can't drift
src = open('/tmp/wp25/wp44-triage/tms_spec.py').read()
ns = {'__builtins__': __builtins__, 'json': json, 'collections': collections}
exec(src.split("assign = {}")[0], ns)
exec(src[src.index("KILLS = {"):], ns)
KILLS = ns['KILLS']
SPEC = ns['SPEC']
per_test = collections.Counter()
for name, _, _ in SPEC:
    t = KILLS.get(name)
    if t:
        per_test[t] += counts[name]
killed_total = sum(per_test.values())
uncovered = 220 - killed_total

hdr = """# WP4.4 triage dossier — `backend/services/threat_monitor_service.py`

- **Meta snapshot:** `mutants/backend/services/threat_monitor_service.py.meta` — 362 keys: 99 killed, **220 survived**, 43 still unchecked (out of scope).
- **Survivors by function:** `process_multiple_threat_detections` 71 · `process_threat_detection` 54 · `_broadcast_alert_created` 52 · `_trigger_webhooks` 43. (`get_threat_severity`, `_build_dedup_key`, `_check_cooldown`, `__init__` have zero survivors — fully killed.)
- **Method:** all 220 diffs via `uv run mutmut show <key>` (read-only, all succeeded). Note: mutmut's diff hunk headers are against a docstring-stripped baseline, so the `Source lines` column below was re-aligned to the real file by matching removed text within each function's range.
- **Class totals:** TEST-GAP **84** · LOW-VALUE **76** · EQUIVALENT **60** (sums to 220).

## Covering test files

| File | Role | Key gaps (file:line) |
| --- | --- | --- |
| `backend/tests/unit/services/test_threat_monitor_service.py` | sole cover the harness ran for all four survivor functions (`tests_by_mangled_function_name` lists only unit tests) | `mock_session` fixture (52-61) never inspects `add`/`refresh` arguments; broadcast test (665-691) captures `publish.call_args` but asserts NOTHING about channel/payload ("exact format depends on implementation" at ~688); **no unit test ever passes `rule=`**; cooldown tests (698-759) only flip the mocked query result, never inspect the built SQL |
| `backend/tests/integration/services/test_threat_monitor_integration.py` | real-DB cover: persistence (150-237), metadata (239-259), dedup (262-311), webhook (530-554), rule cooldown (557-627) — **but not in the mutmut test-selection**, see below | webhook test asserts only `assert_called_once()` — no args/payload; rule-cooldown test asserts only the `alert2 is None` boolean; metadata test pins only 3 keys |

## Why rule-handling mutants survive despite a real-DB rule test existing

`test_threat_alert_respects_existing_rule_cooldown` (integration, 557-627) passes a real `AlertRule` and WOULD kill the `rule`-dropped mutants: with the rule dropped, alert1 gets default key `front_door:gun:threat`, threat2 (knife) gets `front_door:knife:threat`, cooldown misses, `alert2` is created — `assert alert2 is None` fails. It is not in `tests_by_mangled_function_name`, i.e. the harness's runner only executes the unit suite for this module — and **no unit test passes `rule=` at all**, leaving the whole rule-aware dedup/cooldown surface unasserted (23 mutants across the rule/dedup/cooldown/rule_id clusters). WP4.4 note worth confirming for the runner owner: widening test selection to the integration lane would kill a chunk of these without new code; T3/T4 below close the gap inside the unit lane regardless.

## Cluster table (48 clusters, counts sum to 220)

| Pattern | Count | Class | Source lines | Example keys |
| --- | --- | --- | --- | --- |
"""

foot = """

## Classification notes / evidence

- **EQUIVALENT (60):** (a) 57 logger message/`extra` mutants — no test asserts log text, and both skip branches still `return None`; (b) 3 `SEVERITY_PRIORITY.get` **default-arg** mutants (#12/#14/#15) — every `AlertSeverity` member is a real dict key, the default branch never executes. (Distinct from #11, which clobbers the *key* to `None` — that flattens every rank to 0 and IS killed by T6.)
- **LOW-VALUE (76):** real changes nobody currently asserts and no in-repo consumer matches the shape: 22 `alert_data` + 22 `webhook_data` wire-payload **KEY** renames (the frontend `AlertCreatedPayload` at `frontend/src/types/websocket-events.ts:176-184` expects `alert_id/event_id/severity/message/created_at` — a *different* shape from what this service emits; that pre-existing contract mismatch deserves its own ticket, not a mutation fix); 14+6 `alert_metadata`/`detected_threats` KEY renames (whole dict passes through to the alert API per `backend/api/schemas/alerts.py:805-809`, but no consumer in repo reads the renamed keys — T5's shape pin kills them all anyway); 8 `source` provenance-value clobbers (T5); 2 `now_iso` fallback mutants (dead in production — `created_at` is populated after `session.refresh` — observable only under unit mocks; T1's fallback pin kills); 2 `raise ValueError` message clobbers that `pytest.raises(match=)` substring-matches (leave; asserting exact message text is noise).
- **TEST-GAP (84):** four kill-families, each closed by one drafted test:
  1. **Broadcast wire contract** (20 TEST-GAP + 24 LOW-VALUE renames, lines 483-517): envelope dict/`type` value/`type`+`data` KEYs/channel constant/`publish` args — the one test that touches `publish.call_args` asserts nothing about it; plus `id` fallback `or`→`and` (in production the broadcast id becomes a random uuid instead of `alert.id`).
  2. **Webhook dispatch contract** (15 TEST-GAP + 22 LOW-VALUE renames): `get_webhook_service() -> None` (AttributeError swallowed by the except — webhooks silently stop firing), `trigger_webhooks_for_event(session, ALERT_FIRED, data, event_id=...)` arg clobbers, `channels or []`→`and []`, `matched_conditions` value. Only cover is integration `assert_called_once()` (not run). The `event=None` call-arg mutants are extra-sneaky: they raise inside the try, the except swallows, the alert still returns — invisible without a payload pin.
  3. **Rule-aware dedup/cooldown** (23 TEST-GAP, lines 227-231/326-330 + rule_id kwargs): see integration-lane note above.
  4. **Persistence identity + severity hint/ranking** (26 TEST-GAP + 28 LOW-VALUE shape renames): `session.add(alert)`/`refresh(alert)` → `None` (AsyncMock accepts anything — pure mock weakness, fix is an argument-identity assert); `Alert(event_id/status/dedup_key/channels/rule_id)` clobbers on the multi path; `auto_generated`/`source` flags; `>=`→`>` threshold edge; severity-hint in `severity_key()`/`highest_severity`/`detected_threats` — with two same-type ("weapon") threats only the hint ranks them, and the current fixtures rank by threat_type so hint mutants are invisible.

## Drafted tests (6) — UNVERIFIED, not yet run red/green

Style matches the module's existing test file (same fixtures, `@pytest.mark.asyncio`, local service import). TDD procedure, identical for all six: **check out the cluster's mutant, run the named test — the assertion named in the docstring must FAIL (red); restore the original — it must PASS (green).** Add these imports to the existing header (lines 27-37): `json`, `re`, `timedelta`, `patch`, `AlertRule`, `WebhookEventType`, `import backend.services.threat_monitor_service as tms_module`.

```python
{tests}
```

## Drafted-test kill map

| Test | Cluster survivors killed | ≈ |
| --- | --- | --- |
| T1 broadcast envelope/channel/payload shape | envelope+channel+publish args (TEST-GAP) + alert_data key renames + `id` and-fallback + now_iso fallback | {per_test['T1']} |
| T2 webhook args + payload pins | `get_webhook_service()` None, trigger-call clobbers, webhook_data renames, `channels and []`, event=None on both paths | {per_test['T2']} |
| T3 rule dedup template + rule cooldown window (single) | rule dropped from `_build_dedup_key`/`_check_cooldown`, cooldown_seconds short-circuit, `Alert(rule_id=...)` | {per_test['T3']} |
| T4 multi: rule dedup/cooldown + persisted identity + add/refresh + broadcast wiring | dedup/cooldown, `Alert` identity kwargs, `event=None`/`threat=None` broadcast args | {per_test['T4']} |
| T5 add/refresh argument identity + metadata shape (both paths) | session mock weakness, `auto_generated`, `source`, metadata/detected_threats renames, `channels=[]` | {per_test['T5']} |
| T6 hint-ranked severity + `>=` threshold edge | `>=`→`>`, hint dropped in `severity_key`/`highest_severity`/`detected_threats` | {per_test['T6']} |

**Coverage: {killed_total} of 220 survivors die to the six tests** (all 84 TEST-GAP + 74 of 76 LOW-VALUE). Uncovered: {uncovered} = the 60 EQUIVALENT + 2 `ValueError` message-text clobbers deliberately left as noise.

## Notes for WP4.4 execution

1. `Alert(channels=None)` does **not** raise — `channels` is nullable JSONB (`backend/models/alert.py:118`). Mutant 57 is killed by the `alert.channels == []` equality assert in T5, not by an exception.
2. T3/T4 compile the captured cooldown statement with `literal_binds` and regex the cutoff — `Alert.created_at` is `timestamptz`, so the assertion also locks in the tz-aware-cutoff owner ruling (F2) that the comment at lines 449-454 documents.
3. Do NOT re-triage the 43 `null` (unchecked) keys from this dossier; they land in a later sweep.
4. Pre-existing contract drift found in passing (worth a Linear ticket, separate from WP4.4): `_broadcast_alert_created`'s payload does not match the frontend's `AlertCreatedPayload` (frontend expects `alert_id`+`message`; service sends `id` and no `message`). The drafted T1 pins the *current* service shape, so it stays green if the team decides to fix the drift later only by updating both sides — flag before wiring.
"""

open('/tmp/wp25/wp44-triage/threat_monitor_service.md', 'w').write(hdr + table + foot.format(tests=tests, per_test=per_test, killed_total=killed_total, uncovered=uncovered))
print('per_test', dict(per_test), 'killed', killed_total, 'uncovered', uncovered)
