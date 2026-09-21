import json, collections

meta = json.load(open('/agents/agent-nemo2/workspace/mutants/backend/services/container_discovery.py.meta'))
ebk = meta['exit_code_by_key']
surv = set(k for k,v in ebk.items() if v==0)
def key_to_bn(k):
    base, num = k.rsplit('__mutmut_',1)
    base = base[len('backend.services.container_discovery.x'):]
    return (base, int(num))
bn_surv = set(key_to_bn(k) for k in surv)

diffs = json.load(open('/tmp/wp25/wp44-triage/diffs.json'))
diff_bn = {}
for k,c in diffs.items():
    base, num = k.rsplit('__mutmut_',1)
    diff_bn[(base,int(num))] = c

missing = bn_surv - set(diff_bn.keys())
print('survivors missing diff:', len(missing))
print('sample missing:', sorted(missing)[:5])

pat = collections.defaultdict(list)
for bn in sorted(bn_surv, key=lambda x:(x[0],x[1])):
    c = diff_bn.get(bn)
    if c is None: continue
    if len(c)==1:
        old,new = c[0]
        sig = (bn[0], old, new)
    else:
        sig = (bn[0], 'MULTI', ' ;; '.join(f'{o} => {n}' for o,n in c))
    pat[sig].append(bn)

print('unique patterns:', len(pat), 'sum:', sum(len(v) for v in pat.values()))
for (base,old,new),keys in sorted(pat.items(), key=lambda x:(-len(x[1]),x[0],x[1])):
    nums = sorted(n for b,n in keys)
    print(f'[{len(keys)}] {base} :: OLD: {old[:160]} :: NEW: {new[:160]} :: nums {nums[:6]}{"..." if len(nums)>6 else ""}')
