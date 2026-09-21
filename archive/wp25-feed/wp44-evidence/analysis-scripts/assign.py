import json, collections
surs=json.load(open('/tmp/wp25/survivors.json'))
def fn(k): return k.split('.x__')[1].split('__mutmut')[0]
def num(k): return int(k.split('__mutmut_')[1])

# cluster assignment by (function, mutant number)
C={}  # key -> cluster id
def put(cid, keys): 
    for k in keys: C[k]=cid

N=lambda nums,pfx: ['backend.api.routes.gpu_config.x__%s__mutmut_%d'%(pfx,n) for n in nums]
CA='calculate_auto_assignments'; UD='update_gpu_devices_in_db'; LC='get_latest_config_update_time'

# --- TEST-GAP clusters ---
put('TG1_vram_fits_operator', N([51],CA))                                   # >= -> >
put('TG2_vram_remaining_update', N([58,59],CA))                             # -= -> = / +=
put('TG3_overflow_assignment', N([60,61,63],CA))                            # assigned=True/None, not->if
put('TG4_index_none_swap', N([13,54,81,87,93,122,135,170],CA)+N([9],UD))   # gpu_index= / db_index= -> None
put('TG5_manual_default_index', N([17],CA))                                 # manual 0 -> 1
put('TG6_isolation_branch', N([65,66,75],CA))                               # >=2 arity, second_gpu ==
put('TG7_isolation_llm_match', N([76,77,78],CA))                            # == "ai-llm" flipped/case
put('TG8_isolation_single_gpu_idx', N([93,95],CA))                          # gpus[0] -> None/dropped (covered by TG4? separate)
put('TG9_balanced_min', N([141,170,172,174,175],CA))                        # gpu_usage seed/+=/min target
put('TG10_latency_sorted_gpus', N([107,110,111,113],CA))                    # reverse True->False/None, [0]->[1]
put('TG11_latency_other_gpu', N([127,128,129,130,131,132],CA))              # sorted_gpus[-1] / len>1
put('TG12_latency_critical_set', N([115,116,117,118,119],CA))               # critical_services set/`in`
put('TG13_vram_sort_reverse', N([22,25,27,145,155,31,41,144,147,148,30,33,34,36,37,39,40,150,151,153,154],CA))
put('TG14_vram_get_vram_needed', N([44,45,47,48,157,158,160,161],CA))
put('TG15_detect_update_fields', N([10,11,12,13,14,16,17,18,19,20,21],UD))  # db fields None/dropped
put('TG16_detect_create_stmt', N([2,3],UD))                                 # execute(None)/select(None)
put('TG17_updatedat_max', N([2,3,4],LC))                                    # max(updated_at) -> None

# --- EQUIVALENT / LOW-VALUE ---
put('EQ1_warn_text_case', N([2,99,100,101],CA))
put('EQ2_override_none_dropped', N([16,57,84,90,96,125,138,173],CA))
put('LW1_index_dropped', N([15,56,83,89,95,124,137,172],CA))
put('TG18_detect_now_utc', N([5,6],UD))
put('TG19_detect_model_dropped', N([8],UD))

miss=[k for k in surs if k not in C]
extra=[k for k in C if k not in surs]
print('unassigned',miss)
print('extra',extra)
cnt=collections.Counter(C.values())
for cid,c in sorted(cnt.items(), key=lambda x:-x[1]):
    print('%-32s %d'%(cid,c))
print('sum',sum(cnt.values()),'total',len(surs))
json.dump({k.split('.x__')[1]:C[k] for k in surs}, open('/tmp/wp25/assignments.json','w'))
