import json, re, difflib, sys, os
S = open('/agents/agent-nemo2/workspace/mutants/backend/services/segformer_loader.py').read().split('\n')
SPANS = json.load(open('/agents/agent-nemo2/workspace/mutants/backend/services/segformer_loader.py.spans'))['spans']

def region(name):
    a,b = SPANS[name]
    return S[a:b]

FUNCS = ['x_load_segformer_model','x_segment_clothing','x_segment_clothing_batch','x_format_clothing_context','x_format_batch_clothing_context']
out=open('/tmp/wp25/diffs.txt','w')
for f in FUNCS:
    orig = region(f+'__mutmut_orig')
    norm_o=[re.sub(r'\b'+re.escape(f+r'__mutmut_orig')+'\b','FN',l) for l in orig]
    nmax = 0
    for k in SPANS:
        if k.startswith(f+'__mutmut_') and not k.endswith('__mutmut_orig'):
            nmax=max(nmax,int(k.split('__mutmut_')[1]))
    for i in range(1,nmax+1):
        vname=f+'__mutmut_%d'%i
        if vname not in SPANS: continue
        var = region(vname)
        norm_v=[re.sub(r'\b'+re.escape(vname)+'\b','FN',l) for l in var]
        d=list(difflib.unified_diff(norm_o,norm_v,lineterm='',n=1))
        out.write('=== %s\n'%vname)
        body=[l for l in d[2:]]
        if not body: out.write('   <IDENTICAL>\n')
        for l in body: out.write('   '+l+'\n')
out.close()
print('written', os.path.getsize('/tmp/wp25/diffs.txt'))
