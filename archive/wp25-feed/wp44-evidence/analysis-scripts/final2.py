import json
surs=json.load(open('/tmp/wp25/survivors.json'))
CA='backend.api.routes.gpu_config.x__calculate_auto_assignments__mutmut_'
UD='backend.api.routes.gpu_config.x__update_gpu_devices_in_db__mutmut_'
LC='backend.api.routes.gpu_config.x__get_latest_config_update_time__mutmut_'
K=lambda p,nums:[p+str(n) for n in nums]
clusters={
 'T1_index_erasure':      K(CA,[13,15,54,56,81,83,87,89,93,95,122,124,135,137,170,172]),
 'T2_vram_gpu_sort':      K(CA,[22,25,27]),
 'T3_service_order':      K(CA,[30,33,34,36,31,41,144,145,147,148,150,155]),
 'T0_manual_default':     K(CA,[17]),
 'T4_get_default_dead':   K(CA,[37,39,40,45,47,48,151,153,154,158,160,161]),
 'T5_vram_needed_zero':   K(CA,[44,157]),
 'T6_assigned_flag':      K(CA,[50,60,61,63]),
 'T7_remaining_bookkeep': K(CA,[58,59]),
 'T8_fits_boundary':      K(CA,[51]),
 'T9_isolation_logic':    K(CA,[65,66,75,76,77,78]),
 'T10_latency_placement': K(CA,[107,110,111,113,115,116,117,118,119,127,129,130,132]),
 'T11_ternary_equiv':     K(CA,[128,131]),
 'T12_balanced_acc':      K(CA,[141,174,175]),
 'T13_override_dropped':  K(CA,[16,57,84,90,96,125,138,173]),
 'T14_warn_text':         K(CA,[2,99,100,101]),
 'T15_flag_init_none':    K(CA,[49]),
 'T16_updatedat_query':   K(LC,[2,3,4]),
 'T17_detect_payload':    K(UD,[5,6,8,9,10,11,12,13,14,15,16,17,18,19,20,21]),
 'T18_detect_query':      K(UD,[2,3]),
}
allk=[k for ks in clusters.values() for k in ks]
print('cluster total',len(allk),'unique',len(set(allk)))
missing=[k for k in surs if k not in set(allk)]
extra=[k for k in allk if k not in set(surs)]
dup=[k for k in set(allk) if allk.count(k)>1]
print('missing',missing); print('extra',extra); print('dup',dup)
for g,ks in clusters.items(): print(g,len(ks))
