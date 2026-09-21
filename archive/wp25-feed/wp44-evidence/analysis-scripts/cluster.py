import re, json, collections
txt=open('/tmp/wp25/gpu_config_diffs.txt').read().split('\n')
entries=[]
i=0
while i<len(txt):
    if txt[i].startswith('### '):
        key=txt[i][4:]
        body=[]
        i+=1
        while i<len(txt) and not txt[i].startswith('### '):
            body.append(txt[i]); i+=1
        body=[l for l in body if not re.match(r'^[+-]def x__', l)]
        entries.append((key,body))
    else:
        i+=1
print('entries',len(entries))
# signature: the removed line(s) trimmed
groups=collections.defaultdict(list)
for key,body in entries:
    minus=[l[1:].strip() for l in body if l.startswith('-')]
    plus=[l[1:].strip() for l in body if l.startswith('+')]
    sig=' || '.join(minus)[:160]
    groups[sig].append((key,plus))
for sig,ks in sorted(groups.items(), key=lambda kv:-len(kv[1])):
    print('\n@@@ [%d] %s'%(len(ks),sig))
    for k,plus in ks:
        num=k.split('__mutmut_')[1]
        fn=k.split('.x__')[1].split('__mutmut')[0]
        print('   %-4s %-32s %s'%(num, fn, ' || '.join(plus)[:160]))
