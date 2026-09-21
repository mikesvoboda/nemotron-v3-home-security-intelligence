import json, collections

recs = json.load(open('/tmp/wp25/wp44-triage/recs.json'))
S = {(r['fn'], r['num']): r for r in recs}

SPEC = [
 ("LOG-DEBUG skip messages clobbered (single-threat low-confidence + in-cooldown branches) — both paths still return None", "EQUIVALENT",
   [('process_threat_detection', [10,11,13,14,15,16,17,18,19,43,44,46,47,48,49,50])]),
 ("LOG-INFO 'created threat alert' message/extra payload clobbered", "EQUIVALENT",
   [('process_threat_detection', [83,84,86,87,88,89,90,91,92,93,94,95,96])]),
 ("LOG-INFO 'created multi-threat alert' message/extra payload clobbered", "EQUIVALENT",
   [('process_multiple_threat_detections', [93,94,96,97,98,99,100,101,102,103,104])]),
 ("LOG-DEBUG 'all detections below threshold' message -> None (multi)", "EQUIVALENT",
   [('process_multiple_threat_detections', [5])]),
 ("LOG-DEBUG broadcast-success message/extra clobbered", "EQUIVALENT",
   [('_broadcast_alert_created', [48,49,50,51,52,53,54,55])]),
 ("LOG-WARNING failure-path message+extra clobbered in _trigger_webhooks", "EQUIVALENT",
   [('_trigger_webhooks', [36,37,39,40,41,42,43,44])]),
 ("alert_metadata KEY renames (threat_detection_id/auto_generated) — whole dict is API-surfaced via schemas passthrough; one shape-pin kills all", "LOW-VALUE",
   [('process_threat_detection', [72,73,74,75])]),
 ("alert_metadata KEY renames (multi: threat_type/threat_confidence/threat_detection_id/total_threats/auto_generated) — same API passthrough; shape-pin kills", "LOW-VALUE",
   [('process_multiple_threat_detections', [74,75,76,77,78,79,82,83,84,85])]),
 ("detected_threats entry KEY renames (confidence/severity/detection_id) — entries ride the API metadata passthrough; shape-pin kills", "LOW-VALUE",
   [('process_multiple_threat_detections', [47,48,49,50,55,56])]),
 ("broadcast alert_data KEY renames (payload keys renamed, values intact — wire payload keys no in-repo consumer matches today; one shape-pin assertion kills all 22)", "LOW-VALUE",
   [('_broadcast_alert_created', [5,6,9,10,11,12,13,14,15,16,17,18,19,20,23,24,27,28,29,30,31,32])]),
 ("broadcast envelope KEY renames (\"type\"/\"data\" keys) — envelope keys ARE the client dispatch contract", "TEST-GAP",
   [('_broadcast_alert_created', [34,35,38,39])]),
 ("webhook_data KEY renames (payload keys renamed, values intact — same shape-pin kills all 22)", "LOW-VALUE",
   [('_trigger_webhooks', [3,4,5,6,7,8,9,10,11,12,13,14,15,16,18,19,22,23,24,25,26,27])]),
 ("broadcast 'id': alert.id or str(uuid4()) -> and — in production the broadcast id becomes a random uuid instead of alert.id", "TEST-GAP",
   [('_broadcast_alert_created', [7,8])]),
 ("broadcast now_iso fallback (datetime.now(UTC).isoformat()) -> None / datetime.now(None) — fallback leg is dead in production (created_at always populated after refresh) but observable in the unit fixture; T1 fallback pin kills it", "LOW-VALUE",
   [('_broadcast_alert_created', [2,3])]),
 ("raise ValueError message clobbered (XX..XX) — pytest.raises(match=) substring still matches", "LOW-VALUE",
   [('process_threat_detection', [3,7])]),
 ("alert_metadata['source'] VALUE clobbered (XXsourceXX / SOURCE) — provenance tag, single + multi", "LOW-VALUE",
   [('process_threat_detection', [77,78,79,80]), ('process_multiple_threat_detections', [87,88,89,90])]),
 ("auto_generated=True -> False in alert_metadata (single) — test asserts metadata keys but not this flag", "TEST-GAP",
   [('process_threat_detection', [76])]),
 ("auto_generated=True -> False in alert_metadata (multi) — same flag, multi path", "TEST-GAP",
   [('process_multiple_threat_detections', [86])]),
 ("_build_dedup_key(..., rule) called with rule dropped (single) — AlertRule.dedup_key_template silently unused", "TEST-GAP",
   [('process_threat_detection', [28,31])]),
 ("_build_dedup_key(..., rule) called with rule dropped (multi)", "TEST-GAP",
   [('process_multiple_threat_detections', [29,32])]),
 ("dedup_key = <_build_dedup_key call> -> None (multi) — alert + cooldown keyed on None", "TEST-GAP",
   [('process_multiple_threat_detections', [26])]),
 ("cooldown_seconds = rule.cooldown_seconds if rule else ... short-circuited with 'and False' (single) — rule cooldown silently ignored", "TEST-GAP",
   [('process_threat_detection', [33])]),
 ("cooldown_seconds rule ternary short-circuited (multi)", "TEST-GAP",
   [('process_multiple_threat_detections', [34])]),
 ("_check_cooldown(..., rule) called with rule dropped (single) — cooldown query loses its rule_id filter", "TEST-GAP",
   [('process_threat_detection', [36,38,41])]),
 ("_check_cooldown call -> None / args dropped (multi) — cooldown check skipped entirely", "TEST-GAP",
   [('process_multiple_threat_detections', [36,37,39,42])]),
 ("_trigger_webhooks(alert, event) -> event=None (single) — camera_id/risk_score lost, swallowed by except", "TEST-GAP",
   [('process_threat_detection', [104])]),
 ("_trigger_webhooks(alert, event) -> event=None (multi)", "TEST-GAP",
   [('process_multiple_threat_detections', [112])]),
 ("session.add(alert) / session.refresh(alert) -> None (single) — mock session never type-checks the argument", "TEST-GAP",
   [('process_threat_detection', [81,82])]),
 ("session.add(alert) / session.refresh(alert) -> None (multi)", "TEST-GAP",
   [('process_multiple_threat_detections', [91,92])]),
 ("Alert(channels=[]) -> None / kwarg dropped (single) — breaks the 'channels or []' contract downstream", "TEST-GAP",
   [('process_threat_detection', [57,64])]),
 ("Alert(rule_id=rule.id if rule else None) -> None / dropped / 'and False' (single) — rule linkage lost", "TEST-GAP",
   [('process_threat_detection', [53,60,66])]),
 ("Alert(rule_id=...) -> None / dropped / 'and False' (multi)", "TEST-GAP",
   [('process_multiple_threat_detections', [59,66,72])]),
 ("Alert(event_id/status/dedup_key/channels) -> None or kwarg dropped (multi) — persisted alert loses identity fields", "TEST-GAP",
   [('process_multiple_threat_detections', [58,61,62,63,65,68,69,70])]),
 ("multi valid_threats filter: t.confidence >= threshold -> > (detection exactly at threshold silently dropped)", "TEST-GAP",
   [('process_multiple_threat_detections', [3])]),
 ("multi severity_key(): hint dropped / severity=None / args swapped — highest-severity pick misranked or AttributeError (killable by hint-ranked fixture)", "TEST-GAP",
   [('process_multiple_threat_detections', [6,8,9,10,11])]),
 ("multi SEVERITY_PRIORITY.get default arg mangled (0->None / 0->1 / positional drop) — every AlertSeverity member is a dict key, the default branch never executes", "EQUIVALENT",
   [('process_multiple_threat_detections', [12,14,15])]),
 ("highest_severity = get_threat_severity(highest_threat.threat_type, hint) -> hint dropped — unknown multi-threat mis-tiered", "TEST-GAP",
   [('process_multiple_threat_detections', [23,25])]),
 ("detected_threats['severity']: get_threat_severity(t.threat_type, t.severity) -> hint dropped / call mangled", "TEST-GAP",
   [('process_multiple_threat_detections', [52,53,54])]),
 ("broadcast alert_data dict -> None (publishes {\"data\": null})", "TEST-GAP",
   [('_broadcast_alert_created', [4])]),
 ("broadcast envelope dict -> None (publishes JSON null)", "TEST-GAP",
   [('_broadcast_alert_created', [33])]),
 ("broadcast envelope 'type' VALUE clobbered ('alert.created' -> XXalert.createdXX / ALERT.CREATED) — client never receives the right event type", "TEST-GAP",
   [('_broadcast_alert_created', [36,37])]),
 ("broadcast created_at/updated_at ternary condition -> False: always now_iso fallback, real timestamps discarded", "TEST-GAP",
   [('_broadcast_alert_created', [21,25])]),
 ("broadcast channel constant 'websocket:events' -> None / clobbered (publishes to wrong channel)", "TEST-GAP",
   [('_broadcast_alert_created', [40,41,42])]),
 ("redis_client.publish args clobbered (None channel / None payload / json.dumps(None) / arg dropped)", "TEST-GAP",
   [('_broadcast_alert_created', [43,44,45,46,47])]),
 ("webhook_service = get_webhook_service() -> None — AttributeError swallowed, no webhooks fire", "TEST-GAP",
   [('_trigger_webhooks', [1])]),
 ("trigger_webhooks_for_event call args clobbered (session/ALERT_FIRED/webhook_data/event_id -> None or dropped); webhook_data dict -> None", "TEST-GAP",
   [('_trigger_webhooks', [2,28,29,30,31,32,33,34,35])]),
 ("webhook_data 'channels': or [] -> and [] ; matched_conditions VALUE 'threat_detected' clobbered", "TEST-GAP",
   [('_trigger_webhooks', [17,20,21])]),
 ("_broadcast_alert_created(alert, event, threat) -> event=None / threat=None (multi)", "TEST-GAP",
   [('process_multiple_threat_detections', [106,107])]),
]

assign = {}
dup = False
for name, cls_, members in SPEC:
    for fn, nums in members:
        for n in nums:
            k = (fn, n)
            if k in assign:
                print('DUP', k, name); dup = True
            if k not in S:
                print('UNKNOWN', k, name); dup = True
            assign[k] = name
missing = [k for k in S if k not in assign]
print('unassigned', len(missing), sorted(missing))
assert not missing and not dup

cls = {n: c for n, c, _ in SPEC}
cnt = collections.Counter(assign[k] for k in S)
bycls = collections.Counter(cls[name] for name in assign.values())
out = {
    'spec': [{'name': n, 'cls': c} for n, c, _ in SPEC],
    'assign': {f"{k[0]}|{k[1]}": v for k, v in assign.items()},
    'counts': {n: cnt[n] for n, _, _ in SPEC},
    'byclass': dict(bycls),
    'examples': {},
    'lines': {},
}
ex = collections.defaultdict(list)
ln = collections.defaultdict(set)
for (fn, n), name in assign.items():
    r = S[(fn, n)]
    ex[name].append((n, r['key'], r.get('srcline')))
    if r.get('srcline'):
        ln[name].add(r['srcline'])
for n, _, _ in SPEC:
    ex[n].sort()
    out['examples'][n] = [k for _, k, _ in ex[n][:3]]
    out['lines'][n] = sorted(ln[n])
json.dump(out, open('/tmp/wp25/wp44-triage/tms_clusters.json', 'w'), indent=1)
print('total', sum(cnt.values()), 'byclass', dict(bycls))
for n, c, _ in SPEC:
    print(cnt[n], cls[n], '|', n)

KILLS = {
 "broadcast alert_data dict -> None (publishes {\"data\": null})": "T1",
 "broadcast envelope dict -> None (publishes JSON null)": "T1",
 "broadcast envelope 'type' VALUE clobbered ('alert.created' -> XXalert.createdXX / ALERT.CREATED) — client never receives the right event type": "T1",
 "broadcast envelope KEY renames (\"type\"/\"data\" keys) — envelope keys ARE the client dispatch contract": "T1",
 "broadcast created_at/updated_at ternary condition -> False: always now_iso fallback, real timestamps discarded": "T1",
 "broadcast channel constant 'websocket:events' -> None / clobbered (publishes to wrong channel)": "T1",
 "redis_client.publish args clobbered (None channel / None payload / json.dumps(None) / arg dropped)": "T1",
 "broadcast 'id': alert.id or str(uuid4()) -> and — in production the broadcast id becomes a random uuid instead of alert.id": "T1",
 "broadcast alert_data KEY renames (payload keys renamed, values intact — wire payload keys no in-repo consumer matches today; one shape-pin assertion kills all 22)": "T1",
 "broadcast now_iso fallback (datetime.now(UTC).isoformat()) -> None / datetime.now(None) — fallback leg is dead in production (created_at always populated after refresh) but observable in the unit fixture; T1 fallback pin kills it": "T1",
 "webhook_service = get_webhook_service() -> None — AttributeError swallowed, no webhooks fire": "T2",
 "trigger_webhooks_for_event call args clobbered (session/ALERT_FIRED/webhook_data/event_id -> None or dropped); webhook_data dict -> None": "T2",
 "webhook_data 'channels': or [] -> and [] ; matched_conditions VALUE 'threat_detected' clobbered": "T2",
 "webhook_data KEY renames (payload keys renamed, values intact — same shape-pin kills all 22)": "T2",
 "_trigger_webhooks(alert, event) -> event=None (single) — camera_id/risk_score lost, swallowed by except": "T2",
 "_trigger_webhooks(alert, event) -> event=None (multi)": "T2",
 "_build_dedup_key(..., rule) called with rule dropped (single) — AlertRule.dedup_key_template silently unused": "T3",
 "cooldown_seconds = rule.cooldown_seconds if rule else ... short-circuited with 'and False' (single) — rule cooldown silently ignored": "T3",
 "_check_cooldown(..., rule) called with rule dropped (single) — cooldown query loses its rule_id filter": "T3",
 "Alert(rule_id=rule.id if rule else None) -> None / dropped / 'and False' (single) — rule linkage lost": "T3",
 "_build_dedup_key(..., rule) called with rule dropped (multi)": "T4",
 "dedup_key = <_build_dedup_key call> -> None (multi) — alert + cooldown keyed on None": "T4",
 "cooldown_seconds rule ternary short-circuited (multi)": "T4",
 "_check_cooldown call -> None / args dropped (multi) — cooldown check skipped entirely": "T4",
 "Alert(rule_id=...) -> None / dropped / 'and False' (multi)": "T4",
 "Alert(event_id/status/dedup_key/channels) -> None or kwarg dropped (multi) — persisted alert loses identity fields": "T4",
 "_broadcast_alert_created(alert, event, threat) -> event=None / threat=None (multi)": "T4",
 "Alert(channels=[]) -> None / kwarg dropped (single) — breaks the 'channels or []' contract downstream": "T5",
 "auto_generated=True -> False in alert_metadata (single) — test asserts metadata keys but not this flag": "T5",
 "auto_generated=True -> False in alert_metadata (multi) — same flag, multi path": "T5",
 "alert_metadata['source'] VALUE clobbered (XXsourceXX / SOURCE) — provenance tag, single + multi": "T5",
 "alert_metadata KEY renames (threat_detection_id/auto_generated) — whole dict is API-surfaced via schemas passthrough; one shape-pin kills all": "T5",
 "alert_metadata KEY renames (multi: threat_type/threat_confidence/threat_detection_id/total_threats/auto_generated) — same API passthrough; shape-pin kills": "T5",
 "detected_threats entry KEY renames (confidence/severity/detection_id) — entries ride the API metadata passthrough; shape-pin kills": "T5",
 "session.add(alert) / session.refresh(alert) -> None (single) — mock session never type-checks the argument": "T5",
 "session.add(alert) / session.refresh(alert) -> None (multi)": "T5",
 "multi valid_threats filter: t.confidence >= threshold -> > (detection exactly at threshold silently dropped)": "T6",
 "multi severity_key(): hint dropped / severity=None / args swapped — highest-severity pick misranked or AttributeError (killable by hint-ranked fixture)": "T6",
 "highest_severity = get_threat_severity(highest_threat.threat_type, hint) -> hint dropped — unknown multi-threat mis-tiered": "T6",
 "detected_threats['severity']: get_threat_severity(t.threat_type, t.severity) -> hint dropped / call mangled": "T6",
}
