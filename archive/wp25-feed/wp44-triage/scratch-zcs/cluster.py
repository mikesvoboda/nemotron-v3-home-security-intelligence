import json, re

meta=json.load(open('/agents/agent-nemo2/workspace/mutants/backend/services/zone_crossing_service.py.meta'))
surv=[k for k,v in meta['exit_code_by_key'].items() if v==0]

def fnvar(k):
    t=k.rsplit('.',1)[1]
    m=re.match(r'x.*?ZoneCrossingServiceǁ(.+?)__mutmut_(\d+)',t)
    return m.group(1), int(m.group(2))

# cluster assignment by (fn, variant)
CL={}
def assign(name, fn, variants):
    for v in variants:
        CL[(fn,v)] = name

assign('C01_channel_fallback', '_emit_websocket_event', [5,7,9,12,15,16])
assign('C02_handler_payload_nulled', '_handle_zone_enter', [12,14])
assign('C02_handler_payload_nulled', '_handle_zone_exit', [14,15,17])
assign('C02_handler_payload_nulled', '_handle_zone_dwell', [20,21,22,24])
assign('C02_handler_payload_nulled', 'process_detection', [84,85,87,104,106,126,127,129])
assign('C03_payload_keys_renamed', '_emit_zone_exit', [12,13,16,17,18,19,20,21,22,23])
assign('C03_payload_keys_renamed', '_emit_zone_dwell', [16,17,18,19,20,21,22,23])
assign('C04_threshold_boundaries', '_handle_zone_dwell', [1,9])
assign('C04_threshold_boundaries', '_emit_zone_exit', [37])
assign('C04_threshold_boundaries', '_emit_zone_dwell', [27])
assign('C05_image_dims', '_get_detection_in_zone', [4,6])
assign('C05_image_dims', 'process_detection', [47,48,49,50,70,71,74,75])
assign('C06_next_default', '_handle_zone_enter', [4])
assign('C06_next_default', '_handle_zone_dwell', [14])
assign('C07_getattr_default_none', '_compute_entity_id', [6,24])
assign('C07_getattr_default_none', '_compute_entity_type', [6,16])
assign('C07_getattr_default_none', 'process_detection', [22,31])
assign('C08_getattr_default_swap', 'process_detection', [10,13])
assign('C08_getattr_default_swap', '_emit_websocket_event', [9,12])
# NOTE: ws 9,12 are the getattr(redis_event_channel) default swaps -> belongs to C01? no: C01 covers 5,7,9,12,15,16 channel-related. Move them into C01.
for v in (9,12): CL.pop(('_emit_websocket_event',v))
assign('C01_channel_fallback', '_emit_websocket_event', [9,12])
assign('C08_getattr_default_swap', 'process_detection', [10,13])
assign('C09_receiver_none', 'process_detection', [8,18])
assign('C09_receiver_none', '_emit_websocket_event', [5,7])
# ws 5,7 also claimed by C01; reassign to C09 (receiver swap), keep C01 to default-value mutations
for v in (5,7): CL.pop(('_emit_websocket_event',v))
assign('C09_receiver_none', '_emit_websocket_event', [5,7])
assign('C10_attr_name_string', 'process_detection', [12,14,15,23,24])
assign('C11_sort_key_default', 'process_detection', [60,63,66])
assign('C12_syntax_or_swallow', 'process_detection', [39,87])
# 87 belongs to C02; pop and fix
CL.pop(('process_detection',87)); assign('C02_handler_payload_nulled','process_detection',[87])
assign('C12_syntax_or_swallow', '_handle_zone_enter', [])
assign('C12_syntax_or_swallow', '_emit_zone_enter', [42])
assign('C12_syntax_or_swallow', '_emit_zone_exit', [59])
assign('C12_syntax_or_swallow', '_emit_zone_dwell', [32])
assign('C12_syntax_or_swallow', '_emit_websocket_event', [22])
assign('C12_syntax_or_swallow', '_handle_zone_exit', [8])
assign('C12_syntax_or_swallow', 'process_detection', [39])
assign('C13_elif_and_or', 'process_detection', [119])
assign('C14_tracker_writes_dead', 'process_detection', [36,37,41,42,43])
assign('C15_detection_reads_nulled', 'process_detection', [6,7,16,17])
assign('C16_enrichment_guard', '_compute_entity_id', [9])
assign('C16_enrichment_guard', '_compute_entity_type', [19])
assign('C17_intrusion_flip', '_emit_zone_enter', [34])
assign('C18_exit_cleanup', '_handle_zone_exit', [26,27,28])

unc=[k for k in surv if fnvar(k) not in CL]
print('unassigned', len(unc), [ (fnvar(k)) for k in unc])
from collections import Counter
c=Counter(CL[fnvar(k)] for k in surv)
tot=0
for name in sorted(c): print(name, c[name]); tot+=c[name]
print('TOTAL', tot, 'survivors', len(surv))
