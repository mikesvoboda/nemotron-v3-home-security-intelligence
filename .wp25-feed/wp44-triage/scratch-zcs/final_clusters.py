import json, re
meta=json.load(open('/agents/agent-nemo2/workspace/mutants/backend/services/zone_crossing_service.py.meta'))
surv=[k for k,v in meta['exit_code_by_key'].items() if v==0]
def fnvar(k):
    t=k.rsplit('.',1)[1]
    m=re.match(r'x.*?ZoneCrossingServiceǁ(.+?)__mutmut_(\d+)',t)
    return m.group(1), int(m.group(2))

clusters = {
 'payload_field_values_unasserted': ('TEST-GAP','process_detection:6,7,17,84,85,87,104,106,126,127,129;_handle_zone_enter:12,14;_handle_zone_exit:14,15,17;_handle_zone_dwell:20,21,22,24'),
 'payload_keys_presence_only': ('TEST-GAP','_emit_zone_exit:12,13,16,17,18,19,20,21,22,23;_emit_zone_dwell:16,17,18,19,20,21,22,23'),
 'publish_payload_unverified': ('TEST-GAP','_emit_zone_enter:42;_emit_zone_exit:59;_emit_zone_dwell:32'),
 'dwell_threshold_boundary': ('TEST-GAP','_handle_zone_dwell:1,9'),
 'dwell_metric_gate_0_to_1': ('TEST-GAP','_emit_zone_exit:37;_emit_zone_dwell:27'),
 'image_dim_or_to_and': ('TEST-GAP','_get_detection_in_zone:4,6;process_detection:48,50'),
 'image_dim_swap': ('TEST-GAP','process_detection:74,75'),
 'channel_default_fallback': ('TEST-GAP','_emit_websocket_event:9,12,15,16'),
 'attr_name_string_mut': ('TEST-GAP','process_detection:12,14,15,23,24'),
 'receiver_none_detection': ('TEST-GAP','process_detection:8,18'),
 'intrusion_branch_flip': ('TEST-GAP','_emit_zone_enter:34'),
 'exit_cleanup_tracking': ('TEST-GAP','_handle_zone_exit:26,27,28'),
 'getattr_default_removed': ('EQUIVALENT','_compute_entity_id:6,24;_compute_entity_type:6,16;process_detection:22,31'),
 'getattr_default_swap_harmless': ('EQUIVALENT','process_detection:10,13,16'),
 'receiver_none_settings': ('EQUIVALENT','_emit_websocket_event:5,7'),
 'priority_sort_default': ('EQUIVALENT','process_detection:60,63,66'),
 'dim_redefault_equivalent': ('EQUIVALENT','process_detection:47,49,70,71'),
 'elif_and_to_or': ('EQUIVALENT','process_detection:119'),
 'entitypos_type_arg_dropped': ('EQUIVALENT','process_detection:39'),
 'log_text_none': ('EQUIVALENT','_emit_websocket_event:22'),
 'enrichment_guard_or_equivalent': ('EQUIVALENT','_compute_entity_id:9;_compute_entity_type:19'),
 'exit_dwell_time_empty_str': ('EQUIVALENT','_handle_zone_exit:8'),
 'tracker_fields_dead': ('LOW-VALUE','process_detection:36,37,41,42,43'),
 'next_default_removed': ('LOW-VALUE','_handle_zone_enter:4;_handle_zone_dwell:14'),
}
CL={}
for name,(cls,spec) in clusters.items():
    for part in spec.split(';'):
        fn,v=part.split(':')
        for vv in v.split(','):
            CL[(fn,int(vv))]=name
missing=[k for k in surv if fnvar(k) not in CL]
extra=set(CL)-set(fnvar(k) for k in surv)
print('missing',missing); print('extra',sorted(extra))
from collections import Counter
c=Counter(CL[fnvar(k)] for k in surv)
tot=0
for name in clusters:
    print(f'{c[name]:3d} {clusters[name][0]:10s} {name}')
    tot+=c[name]
print('TOTAL',tot,'/',len(surv))
json.dump({'clusters':{n:{'classification':clusters[n][0],'keys':[k for k in surv if CL[fnvar(k)]==n]} for n in clusters}},open('/tmp/wp25/wp44-triage/scratch-zcs/final_clusters.json','w'),indent=1)
