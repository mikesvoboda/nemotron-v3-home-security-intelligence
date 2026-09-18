import json, re, collections

rows = json.load(open('eb_classified.json'))
recs = {}
for row in rows:
    recs.setdefault(row['key'], []).append(row)
recs = [{'key': k, 'fn': r[0]['fn'], 'hunks': r} for k, r in recs.items()]

def case_variant(o, n):
    so = re.sub(r'\s+', ' ', o).strip()
    sn = re.sub(r'\s+', ' ', n).strip()
    if so == sn: return True
    if sn == so.upper() or sn == so.lower(): return True
    if sn.replace('XX', '') == so.replace('XX', ''): return True
    a = so.replace('XX', '').upper().replace(' ', '')
    b = sn.replace('XX', '').upper().replace(' ', '')
    return a == b

OV = {
 'x_requires_ack__mutmut_21': 'EQ-requires_ack-default-variants',
 'x_requires_ack__mutmut_27': 'EQ-requires_ack-default-variants',
 'x_requires_ack__mutmut_29': 'EQ-requires_ack-default-variants',
 'x_requires_ack__mutmut_32': 'EQ-requires_ack-default-variants',
 'xǁEventBroadcasterǁrecord_ack__mutmut_6': 'TG-record_ack-baseline-one',
 'xǁEventBroadcasterǁrecord_ack__mutmut_7': 'EQ-record_ack-ge-equivalence',
 'xǁBroadcastRetryMetricsǁrecord_success__mutmut_9': 'EQ-record_success-membership-equivalence',
 'xǁBroadcastRetryMetricsǁto_dict__mutmut_9': 'EQ-metrics-to_dict-key-literals',
 'xǁBroadcastRetryMetricsǁto_dict__mutmut_10': 'EQ-metrics-to_dict-key-literals',
 'xǁBroadcastRetryMetricsǁrecord_success__mutmut_10': 'TG-metrics-counter-reset',
 'xǁBroadcastRetryMetricsǁrecord_failure__mutmut_3': 'TG-metrics-counter-reset',
 'xǁBroadcastRetryMetricsǁrecord_failure__mutmut_6': 'TG-metrics-counter-reset',
 'x_broadcast_with_retry__mutmut_68': 'TG-metrics-counter-reset',
 'x_broadcast_with_retry__mutmut_69': 'TG-metrics-counter-reset',
 'xǁBroadcastRetryMetricsǁto_dict__mutmut_17': 'TG-metrics-success_rate-guard',
 'xǁBroadcastRetryMetricsǁto_dict__mutmut_19': 'TG-metrics-success_rate-guard',
 'x_broadcast_with_retry__mutmut_1': 'EQ-dead-init-assignments',
 'xǁEventBroadcasterǁ__init____mutmut_5': 'EQ-dead-init-assignments',
 'xǁEventBroadcasterǁ__init____mutmut_12': 'TG-init-circuit-breaker-config',
 'xǁEventBroadcasterǁ__init____mutmut_13': 'TG-init-circuit-breaker-config',
 'xǁEventBroadcasterǁ_listen_for_events__mutmut_43': 'TG-listen-recovery-gate',
 'xǁEventBroadcasterǁ_listen_for_events__mutmut_50': 'LV-listener-backoff-constants',
 'xǁEventBroadcasterǁ_listen_for_events__mutmut_53': 'LV-listener-backoff-constants',
 'xǁEventBroadcasterǁ_listen_for_events__mutmut_12': 'EQ-break-vs-return-no-postloop',
 'xǁEventBroadcasterǁ_supervise_listener__mutmut_7': 'EQ-break-vs-return-no-postloop',
 'xǁEventBroadcasterǁ_supervise_listener__mutmut_13': 'EQ-break-vs-return-no-postloop',
 'xǁEventBroadcasterǁ_supervise_listener__mutmut_5': 'LV-supervisor-sleep-arg',
 'xǁEventBroadcasterǁ_handle_healthy_listener__mutmut_1': 'TG-healthy-listener-flag-false',
 'xǁEventBroadcasterǁ_handle_healthy_listener__mutmut_2': 'TG-healthy-listener-flag-false',
 'xǁEventBroadcasterǁ_handle_healthy_listener__mutmut_3': 'TG-healthy-recovery-reset-gate',
 'xǁEventBroadcasterǁ_handle_healthy_listener__mutmut_4': 'TG-healthy-recovery-reset-gate',
 'xǁEventBroadcasterǁ_handle_dead_listener__mutmut_10': 'TG-dead-listener-return-flags',
 'xǁEventBroadcasterǁ_handle_dead_listener__mutmut_16': 'TG-dead-listener-return-flags',
 'xǁEventBroadcasterǁ_handle_dead_listener__mutmut_24': 'TG-dead-listener-return-flags',
 'xǁEventBroadcasterǁ_handle_dead_listener__mutmut_33': 'TG-dead-listener-return-flags',
 'xǁEventBroadcasterǁ_handle_dead_listener__mutmut_17': 'TG-dead-listener-attempt-arithmetic',
 'xǁEventBroadcasterǁ_handle_dead_listener__mutmut_18': 'TG-dead-listener-attempt-arithmetic',
 'xǁEventBroadcasterǁ_handle_dead_listener__mutmut_19': 'TG-dead-listener-attempt-arithmetic',
 'xǁEventBroadcasterǁ_handle_dead_listener__mutmut_23': 'TG-dead-listener-resubscribe-cond',
 'xǁEventBroadcasterǁ_handle_dead_listener__mutmut_25': 'TG-dead-listener-restart-task',
 'xǁEventBroadcasterǁ_handle_dead_listener__mutmut_26': 'TG-dead-listener-restart-task',
 'xǁEventBroadcasterǁ_handle_dead_listener__mutmut_27': 'TG-dead-listener-restart-task',
 'xǁEventBroadcasterǁ_handle_dead_listener__mutmut_28': 'TG-dead-listener-restart-task',
 'xǁEventBroadcasterǁ_resubscribe_for_supervisor__mutmut_2': 'LV-resubscribe-channel-arg',
 'xǁEventBroadcasterǁ_resubscribe_for_supervisor__mutmut_4': 'TG-resubscribe-true-on-failure',
 'xǁEventBroadcasterǁ_send_to_single_client__mutmut_1': 'LV-send-single-if-or',
 'xǁEventBroadcasterǁ_listen_for_events__mutmut_10': 'LV-listen-channel-arg',
 'xǁEventBroadcasterǁconnect__mutmut_2': 'TG-client-format-negotiation',
 'xǁEventBroadcasterǁdisconnect__mutmut_5': 'TG-client-format-negotiation',
 'xǁEventBroadcasterǁstop__mutmut_3': 'TG-stop-listener-health-flag',
 'xǁEventBroadcasterǁstop__mutmut_4': 'TG-stop-listener-health-flag',
 'x_broadcast_alert_with_retry_background__mutmut_10': 'TG-background-alert-lambda-args',
 'x_broadcast_alert_with_retry_background__mutmut_11': 'TG-background-alert-lambda-args',
 'x_broadcast_alert_with_retry_background__mutmut_12': 'TG-background-alert-lambda-args',
 'x_broadcast_alert_with_retry_background__mutmut_13': 'TG-background-alert-lambda-args',
 'x_broadcast_alert_with_retry_background__mutmut_2': 'LV-background-message-type-none',
 'x_broadcast_with_retry__mutmut_10': 'LV-retry-log-gates-and-counters',
 'x_broadcast_with_retry__mutmut_11': 'LV-retry-log-gates-and-counters',
}
LOGCTX_PREFIX = ('logger', 'extra={')

def bucket(r, h):
    o, n, fn = h['old'], h['new'], r['fn']
    ctx = h['ctx'] or ''
    k = r['key'].split('.event_broadcaster.')[1]
    if k in OV: return OV[k]
    so = re.sub(r'\s+', ' ', o).strip()
    # comments
    if so.startswith('#'): return 'EQ-comment-text'
    # full logger call replaced
    if so.startswith('logger.') or 'logger.' in so[:9]:
        return 'EQ-log-message-text' if case_variant(o, n) else 'LV-log-structure'
    # dict-literal context: keys
    in_dict = ctx.startswith('"') or ctx.startswith('degraded_message') or ctx.startswith('shutdown_message') or ctx in ('{',)
    in_log = ctx.startswith(LOGCTX_PREFIX) or 'logger' in ctx or 'raise' in ctx or 'f"(' in ctx or so.startswith('f"')
    if in_log and not in_dict:
        return 'EQ-log-message-text' if case_variant(o, n) else 'LV-log-structure'
    # real-payload literal sites
    if 'model_dump(mode=' in so: return 'EQ-model-dump-mode-noop'
    if so.startswith('subscriber_count = await self._redis.publish'): return 'TG-publish-call-args'
    if so.startswith('validated_message') or so.startswith('validated_data') or so.startswith('validated_update_data') or so.startswith('validated_hourly') or so.startswith('validated_daily') or so.startswith('validated_message_union'): return 'TG-validation-pipeline-bypass'
    if so.startswith('if "type" not in') or so.startswith('data_dict = batch_data.get') or so.startswith('data_dict = message.get') or so.startswith('data_dict: dict'): return 'TG-batch-envelope-guard'
    if fn.endswith('ǁstop') and 'shutdown_message' in so or '"system.shutdown"' in so or '"Server shutting down"' in so or so.startswith('"reconnect"') or (fn.endswith('ǁstop') and in_dict): return 'TG-shutdown-payload-literal'
    if fn.endswith('broadcast_degraded_state') and in_dict: return 'TG-degraded-payload-literal'
    if fn.endswith('broadcast_degraded_state'): return 'EQ-log-message-text' if case_variant(o,n) else 'LV-log-structure'
    if fn.endswith('_send_to_all_clients'):
        if 'track_stats' in so or 'return_exceptions' in so: return 'LV-send-all-stats-flags'
        return 'TG-send-all-format-payload'
    if fn.endswith('ǁconnect'): return 'LV-log-structure'
    if 'raise ' in so and 'f"' in so: return 'EQ-exception-message-text'
    if so.startswith('if attempt > 0'): return 'LV-retry-log-gates-and-counters'
    if fn == 'x_broadcast_with_retry': return 'LV-retry-log-gates-and-counters'
    if fn.endswith('ǁstop'): return 'TG-shutdown-payload-literal' if 'json' in so or 'send_text' in so else ('EQ-log-message-text' if case_variant(o,n) else 'LV-log-structure')
    if '.get(' in so and fn.startswith('xǁEventBroadcasterǁbroadcast_'): return 'TG-payload-literal-shape'
    if re.match(r'^\w+ = \{"type"', so) or so.startswith('{"type"') or re.match(r'^[a-z_]+ = \{', so) or '"type":' in so: return 'TG-payload-literal-shape'
    if so.startswith('"type"') or so.startswith('"data"'): return 'TG-payload-literal-shape'
    if fn.startswith('xǁEventBroadcasterǁbroadcast_'): return 'TG-payload-literal-shape'
    if 'RuntimeError(' in ctx or 'raise' in ctx: return 'EQ-exception-message-text'
    return 'UNASSIGNED::' + fn + '::' + so[:50]

prio = lambda b: 0 if b.startswith('TG') else (1 if b.startswith('LV') else 2)
per_key = {}
for r in recs:
    bs = sorted((bucket(r, h) for h in r['hunks']), key=prio)
    per_key[r['key']] = bs[0]

json.dump(per_key, open('eb_final_clusters.json', 'w'), indent=1)
cnt = collections.Counter(per_key.values())
un = {k: v for k, v in per_key.items() if v.startswith('UN')}
print('total', len(per_key), 'unassigned', len(un))
for k, v in list(un.items())[:30]: print('UN', k, v)
tot = sum(c for b, c in cnt.items() if not b.startswith('UN'))
print('assigned', tot)
for b, c in sorted(cnt.items()): print(f'{c:4d}  {b}')
