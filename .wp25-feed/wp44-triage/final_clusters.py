import json, re, collections

rows = json.load(open('eb_classified.json'))
recs = {}
for row in rows:
    recs.setdefault(row['key'], []).append(row)
recs = [{'key': k, 'fn': r[0]['fn'], 'hunks': r} for k, r in recs.items()]
FN = lambda r: r['fn']

def case_variant(o, n):
    """pure case / XX-wrap / identical text mutation"""
    so = re.sub(r'\s+', ' ', o).strip()
    sn = re.sub(r'\s+', ' ', n).strip()
    if so == sn:
        return True
    if sn == so.upper() or sn == so.lower():
        return True
    if sn == 'XX' + so + 'XX' or sn.replace('XX', '') == so.replace('XX', ''):
        return True
    # key renames inside dict literals: "type"->"TYPE" etc: compare after uppercasing+strip XX
    a = so.replace('XX', '').upper()
    b = sn.replace('XX', '').upper()
    return a == b

LOGCTX = ('logger', 'extra={')

def bucket(r, h):
    o, n, c, fn = h['old'], h['new'], h['ctx'] or '', r['fn']
    so = re.sub(r'\s+', ' ', o).strip()
    # ---- explicit key-level overrides
    key = r['key'].split('.')[-1].replace('__mutmut_', '_')
    ov = {
        'x_requires_ack_21': 'TG-requires_ack-default-score-1',
        'x_requires_ack_27': 'EQ-requires_ack-risklevel-defaults',
        'x_requires_ack_29': 'EQ-requires_ack-risklevel-defaults',
        'x_requires_ack_32': 'EQ-requires_ack-risklevel-defaults',
        'xǁEventBroadcasterǁrecord_ack_6': 'TG-record_ack-baseline-1',
        'xǁEventBroadcasterǁrecord_ack_7': 'EQ-record_ack-ge-same',
        'xǁBroadcastRetryMetricsǁrecord_success_9': 'EQ-record_success-branch-equivalence',
        'xǁBroadcastRetryMetricsǁto_dict_9': 'EQ-metrics-to_dict-key-literals',
        'xǁBroadcastRetryMetricsǁto_dict_10': 'EQ-metrics-to_dict-key-literals',
        'xǁBroadcastRetryMetricsǁrecord_success_10': 'TG-metrics-counter-reset',
        'xǁBroadcastRetryMetricsǁrecord_failure_3': 'TG-metrics-counter-reset',
        'xǁBroadcastRetryMetricsǁrecord_failure_6': 'TG-metrics-counter-reset',
        'xǁBroadcastRetryMetricsǁto_dict_17': 'TG-metrics-success_rate-guard',
        'xǁBroadcastRetryMetricsǁto_dict_19': 'TG-metrics-success_rate-guard',
        'x_broadcast_with_retry_68': 'TG-metrics-counter-reset',
        'x_broadcast_with_retry_69': 'TG-metrics-counter-reset',
        'x_broadcast_with_retry_1': 'EQ-dead-init-variants',
        'xǁEventBroadcasterǁ__init___5': 'EQ-dead-init-variants',
        'xǁEventBroadcasterǁ__init___12': 'TG-init-circuit-breaker-flags',
        'xǁEventBroadcasterǁ__init___13': 'TG-init-circuit-breaker-flags',
        'xǁEventBroadcasterǁ_listen_for_events_43': 'TG-listen-recovery-gate',
        'xǁEventBroadcasterǁ_listen_for_events_50': 'LV-listener-backoff-constants',
        'xǁEventBroadcasterǁ_listen_for_events_53': 'LV-listener-backoff-constants',
        'xǁEventBroadcasterǁ_supervise_listener_7': 'TG-supervisor-break-vs-return',
        'xǁEventBroadcasterǁ_supervise_listener_13': 'TG-supervisor-break-vs-return',
        'xǁEventBroadcasterǁ_supervise_listener_5': 'LV-supervisor-sleep-arg',
        'xǁEventBroadcasterǁ_handle_healthy_listener_1': 'TG-healthy-flag-set-false',
        'xǁEventBroadcasterǁ_handle_healthy_listener_2': 'TG-healthy-flag-set-false',
        'xǁEventBroadcasterǁ_handle_healthy_listener_3': 'TG-healthy-reset-gate',
        'xǁEventBroadcasterǁ_handle_healthy_listener_4': 'TG-healthy-reset-gate',
        'xǁEventBroadcasterǁ_handle_dead_listener_10': 'TG-dead-listener-return-flags',
        'xǁEventBroadcasterǁ_handle_dead_listener_16': 'TG-dead-listener-return-flags',
        'xǁEventBroadcasterǁ_handle_dead_listener_24': 'TG-dead-listener-return-flags',
        'xǁEventBroadcasterǁ_handle_dead_listener_33': 'TG-dead-listener-return-flags',
        'xǁEventBroadcasterǁ_handle_dead_listener_17': 'TG-dead-listener-attempt-arithmetic',
        'xǁEventBroadcasterǁ_handle_dead_listener_18': 'TG-dead-listener-attempt-arithmetic',
        'xǁEventBroadcasterǁ_handle_dead_listener_19': 'TG-dead-listener-attempt-arithmetic',
        'xǁEventBroadcasterǁ_handle_dead_listener_25': 'TG-dead-listener-restart-task',
        'xǁEventBroadcasterǁ_handle_dead_listener_26': 'TG-dead-listener-restart-task',
        'xǁEventBroadcasterǁ_handle_dead_listener_27': 'TG-dead-listener-restart-task',
        'xǁEventBroadcasterǁ_handle_dead_listener_28': 'TG-dead-listener-restart-task',
        'xǁEventBroadcasterǁ_resubscribe_for_supervisor_2': 'LV-resubscribe-channel-arg',
        'xǁEventBroadcasterǁ_resubscribe_for_supervisor_4': 'TG-resubscribe-true-on-failure',
        'xǁEventBroadcasterǁ_send_to_single_client_1': 'LV-send-single-if-or',
        'xǁEventBroadcasterǁconnect_2': 'TG-client-format-map',
        'xǁEventBroadcasterǁdisconnect_5': 'TG-client-format-map',
        'xǁEventBroadcasterǁstop_3': 'TG-stop-listener-health-flag',
        'xǁEventBroadcasterǁstop_4': 'TG-stop-listener-health-flag',
        'x_broadcast_alert_with_retry_background_10': 'TG-background-alert-lambda-args',
        'x_broadcast_alert_with_retry_background_11': 'TG-background-alert-lambda-args',
        'x_broadcast_alert_with_retry_background_12': 'TG-background-alert-lambda-args',
        'x_broadcast_alert_with_retry_background_13': 'TG-background-alert-lambda-args',
        'x_broadcast_alert_with_retry_background_2': 'LV-background-message-type-none',
    }
    k2 = r['key'].split('.event_broadcaster.')[1]
    k3 = k2.replace('__mutmut_', '_')
    if k3 in ov:
        return ov[k3]
    # ---- generic rules
    if 'model_dump(mode=' in so:
        return 'TG-model-dump-mode'
    if '.publish(' in so or so.startswith('subscriber_count = await'):
        return 'TG-publish-call-args'
    if so.startswith('validated_message =') or so.startswith('validated_data =') or so.startswith('validated_message_union ='):
        return 'TG-validation-pipeline-bypass'
    if so.startswith('validated_message = WebSocketServiceStatusMessage(') :
        return 'TG-validation-pipeline-bypass'
    if so.startswith('if "type" not in') or so.startswith('data_dict = batch_data.get'):
        return 'TG-batch-envelope-guard'
    if so.startswith('worker_status_data =') or so.startswith('data_dict["type"]') or so.startswith('data_dict ='):
        return 'TG-payload-literal-shape'
    if fn.endswith('broadcast_degraded_state'):
        if c.startswith(LOGCTX):
            return 'EQ-log-message-text' if case_variant(o, n) else 'LV-log-extras-and-flags'
        return 'TG-degraded-payload-literal'
    if fn.endswith('ǁstop'):
        if c.startswith(LOGCTX):
            return 'EQ-log-message-text' if case_variant(o, n) else 'LV-log-extras-and-flags'
        if '_listener_healthy' in so:
            return 'TG-stop-listener-health-flag'
        return 'TG-shutdown-payload-literal'
    if fn.endswith('_send_to_all_clients'):
        if 'track_stats' in so or 'return_exceptions' in so:
            return 'LV-send-all-format-stats-flags'
        return 'TG-send-all-format-and-payload'
    if fn.endswith('_send_to_single_client'):
        return 'EQ-log-message-text'
    if fn.endswith('ǁconnect'):
        return 'LV-log-extras-and-flags' if case_variant(o, n) is False and 'extra' in c else 'EQ-log-message-text'
    if fn.endswith('broadcast_service_status') and 'WebSocketServiceStatusMessage(' in so:
        return 'TG-validation-pipeline-bypass'
    if fn.endswith('broadcast_ai_threat_detected') or True:
        pass
    # logger context / f-string log continuation lines
    if c.startswith(LOGCTX) or (so.startswith('f"') and '{' in so and c in ('TOP', '') ) or 'logger' in c:
        # payload.get/data_dict.get inside f-string logs are still log-only
        return 'EQ-log-message-text' if case_variant(o, n) else 'LV-log-extras-and-flags'
    # broadcast_* data_dict.get('field', {}) defaults
    if '.get(' in so and fn.startswith('xǁEventBroadcasterǁbroadcast_'):
        return 'TG-payload-literal-shape'
    # get_instance exception text
    if 'RuntimeError(' in c or so.startswith('"EventBroadcaster'):
        return 'EQ-exception-message-text'
    if 'logger' in c:
        return 'EQ-log-message-text'
    return 'UNASSIGNED::' + fn + '::' + so[:40]

# per-survivor: pick highest-priority bucket among hunks (TG > LV > EQ)
prio = lambda b: 0 if b.startswith('TG') else (1 if b.startswith('LV') else 2)
per_key = {}
for r in recs:
    bs = [bucket(r, h) for h in r['hunks']]
    bs.sort(key=prio)
    per_key[r['key']] = bs[0]

cnt = collections.Counter(per_key.values())
un = {k: v for k, v in per_key.items() if v.startswith('UNASSIGNED')}
print('assigned', len(per_key) - len(un), 'unassigned', len(un))
for k, v in un.items():
    print('UN', k, v)
json.dump(per_key, open('eb_per_key.json', 'w'), indent=1)
print()
tot = 0
for b, c in sorted(cnt.items()):
    if b.startswith('UN'): continue
    tot += c
    print(f'{c:4d}  {b}')
print('TOTAL', tot)
