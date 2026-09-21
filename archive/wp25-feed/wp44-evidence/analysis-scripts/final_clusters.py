import json
surs=json.load(open('/tmp/wp25/survivors.json'))
CA='backend.api.routes.gpu_config.x__calculate_auto_assignments__mutmut_'
UD='backend.api.routes.gpu_config.x__update_gpu_devices_in_db__mutmut_'
LC='backend.api.routes.gpu_config.x__get_latest_config_update_time__mutmut_'
K=lambda p,nums:[p+str(n) for n in nums]
C={}
groups={
 'C1_index_erasure': K(CA,[13,54,81,87,93,122,135,170,15,56,83,89,95,124,137,172])+K(UD,[9]),
 'C2_sort_ordering': K(CA,[22,25,27,30,31,33,34,36,37,39,40,41,144,145,147,148,150,151,153,154,155]),
 'C3_detect_payload': K(UD,[2,3,5,6,8,10,11,12,13,14,15,16,17,18,19,20,21]),
 'C4_latency_placement': K(CA,[107,110,111,113,127,128,129,130,131,132,115,116,117,118,119]),
 'C5_isolation_branch': K(CA,[65,66,75,76,77,78]),
 'C6_overflow_chain': K(CA,[51,58,59,49,50,60,61,63]),
 'C7_vram_lookup': K(CA,[44,45,47,48,157,158,160,161]),
 'C8_manual_default': K(CA,[17]),
 'C9_balanced_usage': K(CA,[141,174,175]),
 'C10_updatedat_max': K(LC,[2,3,4]),
 'C11_warn_text': K(CA,[2,99,100,101]),
 'C12_override_dropped': K(CA,[16,57,84,90,96,125,138,173]),
}
assigned=set()
for g,ks in groups.items():
    for k in ks:
        assert k not in assigned, ('dup',k)
        assigned.add(k); C[k]=g
missing=[k for k in surs if k not in assigned]
extra=[k for k in assigned if k not in surs]
print('missing',missing); print('extra',extra)
print({g:len(ks) for g,ks in groups.items()})
print('sum',sum(len(ks) for ks in groups.values()),'of',len(surs))
json.dump(C,open('/tmp/wp25/assignments.json','w'))
