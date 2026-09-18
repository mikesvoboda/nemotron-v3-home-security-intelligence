import json
surs=set(json.load(open('/tmp/wp25/survivors.json')))
CA='backend.api.routes.gpu_config.x__calculate_auto_assignments__mutmut_'
UD='backend.api.routes.gpu_config.x__update_gpu_devices_in_db__mutmut_'
LC='backend.api.routes.gpu_config.x__get_latest_config_update_time__mutmut_'
K=lambda p,nums:[p+str(n) for n in nums]
clusters={
 'C1':K(CA,[13,15,17]),
 'C2':K(CA,[44,50,51,54,56,58,59,60,61,63,157]),
 'C3':K(CA,[22,25,27]),
 'C4':K(CA,[30,31,33,34,36,41]),
 'C5':K(CA,[144,145,147,148,150,155]),
 'C6':K(CA,[174,175]),
 'C7':K(CA,[65,66,75,76,77,78]),
 'C8':K(CA,[107,110,111,113]),
 'C9':K(CA,[115,116,117,118,119]),
 'C10':K(CA,[127,129,130,132]),
 'C11':K(CA,[81,83,87,89,93,95,122,124,135,137,170,172]),
 'C12':K(LC,[2,3,4]),
 'C13':K(UD,[5,6,8,9,10,11,12,13,14,15,16,17,18,19,20,21]),
 'C14':K(UD,[2,3]),
 'E1':K(CA,[2,99,100,101]),
 'E2':K(CA,[16,57,84,90,96,125,138,173]),
 'E3':K(CA,[128,131]),
 'E4':K(CA,[49]),
 'E5':K(CA,[141]),
 'E6':K(CA,[37,39,40,45,47,48,151,153,154,158,160,161]),
}
allk=[k for ks in clusters.values() for k in ks]
assert len(allk)==len(set(allk)), 'overlap!'
assert set(allk)==surs, ('diff', surs-set(allk), set(allk)-surs)
cls={'TEST-GAP':sum(len(clusters[c]) for c in ['C1','C2','C3','C4','C5','C6','C7','C8','C9','C10','C11','C12','C13','C14']),
     'LOW-VALUE':len(clusters['E6']),
     'EQUIVALENT':sum(len(clusters[c]) for c in ['E1','E2','E3','E4','E5'])}
print({c:len(v) for c,v in clusters.items()})
print(cls, 'TOTAL', sum(cls.values()))
