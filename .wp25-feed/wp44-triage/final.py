import json, collections
c=json.load(open('/tmp/wp25/wp44-triage/clusters_final.json'))
E=c.pop('E1 other')
P1=[k for k in E if 'XX' not in k and True]
# P1 = window arg dropped (mutmut_5/_7 pattern); the batch_events_15 goes to L1
P1=[k for k in E if not k.endswith('add_batch_events__mutmut_15')]
LEFT=[k for k in E if k.endswith('add_batch_events__mutmut_15')]
c['P1 window arg dropped (equiv)']=P1
c['L1 pfadd value arg']=c['L1 pfadd value arg']+LEFT
names={'A1 tz-arg':'A1','B1 window-compare':'B1','C1 window-start nonzero':'C1','D1 dropped trunc kwarg':'D1',
 'F1 window_start':'F1','G1 window arg dropped':'G1','H1 merged-count key/arg':'H1','I1 pfcount(None)':'I1',
 'J1 pfadd key arg':'J1','K1 pfadd ttl arg':'K1','L1 pfadd value arg':'L1','M1 key=None':'M1',
 'N1 metric arg = None':'N2','N1 metric arg dropped':'N1','O1 window arg = None':'O1','Q1 metric case/prefix':'Q1',
 'P1 window arg dropped (equiv)':'P1'}
out={names[k]:v for k,v in c.items()}
tot=sum(len(v) for v in out.values())
for k in sorted(out): print('%-4s %3d'%(k,len(out[k])))
print('TOTAL',tot,'clusters',len(out))
json.dump(out, open('/tmp/wp25/wp44-triage/clusters_named.json','w'), indent=1)
