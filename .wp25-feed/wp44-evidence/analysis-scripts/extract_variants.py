import re, difflib, json, sys

COPY='/agents/agent-nemo2/workspace/mutants/backend/services/pg_notify_listener.py'
src=open(COPY).read().splitlines(keepends=True)

pat=re.compile(r'^(\s*)(?:async\s+)?def (x\S*__mutmut(?:_orig|_\d+))\s*[\(:]')
starts=[]  # (name, start_idx)
for i,l in enumerate(src):
    m=pat.match(l)
    if m:
        starts.append((m.group(2), i))

# block i goes from start_i to start_{i+1}; last one ends at first line matching ^\s*(mutants_|class |@|def [^x]|if |while |# mutmut) at <= its indent... simpler: to first line starting (at same indent) with 'mutants_'
texts={}
for idx,(name,st) in enumerate(starts):
    if idx+1 < len(starts):
        en=starts[idx+1][1]
    else:
        en=len(src)
    # trim: stop at first registration line (unindented 'mutants_...[' )
    ind=len(src[st])-len(src[st].lstrip())
    for j in range(st+1,en):
        l=src[j]
        s=l.strip()
        if not s: continue
        cur=len(l)-len(l.lstrip())
        if s.startswith('mutants_') and cur<=ind:
            en=j; break
    body=src[st:en]
    while body and not body[-1].strip(): body.pop()
    texts[name]=''.join(body)

print("TOTAL_BLOCKS", len(texts), file=sys.stderr)

meta=json.load(open('/agents/agent-nemo2/workspace/mutants/backend/services/pg_notify_listener.py.meta'))
surv=sorted(k for k,v in meta['exit_code_by_key'].items() if v==0)

out=[]
for key in surv:
    vname=key.split('.')[-1]
    orig_name=vname.rsplit('__mutmut',1)[0]+'__mutmut_orig'
    if vname not in texts or orig_name not in texts:
        out.append((key,'MISSING',''))
        continue
    def norm(t, nm):
        # normalize the function name so rename noise disappears
        return t.replace(nm,'FUNCNAME')
    a=norm(texts[orig_name],orig_name).splitlines()
    b=norm(texts[vname],vname).splitlines()
    diff=[l for l in difflib.unified_diff(a,b,lineterm='',n=1) if l.startswith(('+','-')) and not l.startswith(('+++','---'))]
    out.append((key,'DIFF','\n'.join(diff)))

with open('/tmp/wp25/pgnl_diffs.txt','w') as f:
    for key,kind,d in out:
        f.write(f'### {key} [{kind}]\n{d}\n\n')
missing=[k for k,kind,_ in out if kind=='MISSING']
empty=[k for k,kind,d in out if kind=='DIFF' and not d.strip()]
print("MISSING:",missing, file=sys.stderr)
print("EMPTYDIFF:",empty, file=sys.stderr)
